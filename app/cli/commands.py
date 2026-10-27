#!/usr/bin/env python3
"""CLI command handlers for CorbeauSplat."""
import os
import shutil
import sys
import time
from pathlib import Path as _Path
from urllib.parse import quote

from app.core.brush_engine import BrushEngine
from app.core.brush_presets import BRUSH_DEFAULTS, BRUSH_PRESETS
from app.core.brush_refine import (
    RefineEnvironmentError,
    detect_refine_start_iteration,
    prepare_refine_environment,
)
from app.core.engine import ColmapEngine
from app.core.i18n import tr
from app.core.live_progress import integer_steps
from app.core.params import FEATURE_TO_DEFAULT_MATCHING, ColmapParams, blur_factor_from_strength
from app.core.ply_cleaner import clean_ply, clean_ply_batch
from app.core.sharp_engine import SharpEngine
from app.core.superplat_engine import SuperSplatEngine
from app.core.system import get_brush_build_mode

# Pure logic despite living under app/gui: no Qt import, so the CLI can share
# the exact checkpoint semantics the interface uses instead of a second copy.
from app.gui.chaining_logic import find_checkpoint_plys, is_checkpoint_ply, resolve_checkpoints_dir

# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def _t(key, default, **kwargs):
    """Translate ``key`` and fill its named placeholders."""
    return tr(key, default).format(**kwargs)


def _print_kv(*pairs):
    """Print aligned ``  Label : value`` lines from ``(label_key, default, value)`` triples."""
    for key, default, value in pairs:
        print(f"  {tr(key, default):<12}: {value}")


# ─────────────────────────────────────────────────────────────────────────────
# Run functions
# ─────────────────────────────────────────────────────────────────────────────

def _apply_robust(params: ColmapParams) -> ColmapParams:
    """Apply the robust mode parameters (anti-crash on large scenes)."""
    params.camera_model = "PINHOLE"
    params.ba_refine_extra_params = False
    params.ba_refine_principal_point = False
    params.filter_blurry = True
    return params


def _resolve_matching_type(feature_type: str, matching_type: str | None) -> str:
    """Return the matching type: explicit, or default according to the feature type."""
    if matching_type:
        return matching_type
    return FEATURE_TO_DEFAULT_MATCHING.get(feature_type, 'SIFT_BRUTEFORCE')


def _build_colmap_params(args) -> ColmapParams:
    """Build a complete ColmapParams from the CLI arguments.

    Shared by ``run_colmap`` and ``run_pipeline`` to guarantee that both
    sub-commands produce identical reconstructions for equivalent options.
    Optional parameters missing from ``args`` take the ``ColmapParams``
    defaults.
    """
    feat_type = getattr(args, 'feature_type', 'SIFT')
    match_type = _resolve_matching_type(feat_type, getattr(args, 'matching_type', None))
    params = ColmapParams(
        camera_model=args.camera_model,
        single_camera=not getattr(args, 'no_single_camera', False),
        max_image_size=getattr(args, 'max_image_size', 3200),
        max_num_features=getattr(args, 'max_num_features', 8192),
        feature_type=feat_type,
        matching_type=match_type,
        estimate_affine_shape=getattr(args, 'estimate_affine_shape', True),
        domain_size_pooling=not getattr(args, 'no_domain_size_pooling', False),
        max_ratio=getattr(args, 'max_ratio', 0.8),
        max_distance=getattr(args, 'max_distance', 0.7),
        cross_check=not getattr(args, 'no_cross_check', False),
        guided_matching=getattr(args, 'guided_matching', False),
        ba_refine_focal_length=not getattr(args, 'no_refine_focal', False),
        ba_refine_principal_point=getattr(args, 'refine_principal', False),
        ba_refine_extra_params=not getattr(args, 'no_refine_extra', False),
        min_num_matches=getattr(args, 'min_num_matches', 15),
        matcher_type=getattr(args, 'matcher_type', 'exhaustive'),
        sequential_overlap=getattr(args, 'sequential_overlap', 30),
        undistort_images=args.undistort,
        filter_blurry=getattr(args, 'filter_blur', False),
        blur_factor=blur_factor_from_strength(getattr(args, 'blur_strength', 'medium')),
        use_view_graph_calibration=getattr(args, 'view_graph_calibration', True),
        ignore_watermarks=getattr(args, 'ignore_watermarks', True),
        thermal_throttling=getattr(args, 'thermal_throttling', False),
        image_convert_format=getattr(args, 'convert', 'png'),
        video_trim_start=getattr(args, 'trim_start', None),
        video_trim_end=getattr(args, 'trim_end', None),
    )
    if getattr(args, 'robust', False):
        params = _apply_robust(params)
    return params


def run_colmap(args):
    params = _build_colmap_params(args)

    print(tr("cli_start_colmap"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))

    engine = ColmapEngine(
        params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=integer_steps(lambda x: print(tr("cli_progression", x))),
    )

    success, msg = engine.run()
    if success:
        print(tr("cli_success", msg))
    else:
        print(tr("cli_error", msg))
        sys.exit(1)


def _handle_ply_rename(output_path, params, log=print):
    """Rename the trained checkpoint PLY to ``params["ply_name"]``, if set.

    Qt-free port of ``app/gui/workers.py::BrushWorker.handle_ply_rename()``:
    locate the most recently modified checkpoint under ``output_path`` and
    move it to ``<output_path>/<ply_name>``. Without this, ``--ply_name`` was
    stored but never consumed (audit L4-03).
    """
    ply_name = params.get("ply_name")
    if not ply_name:
        return

    # Sanitisation: strictly a filename, no path components.
    ply_name = _Path(ply_name).name
    if not ply_name.endswith(".ply"):
        ply_name += ".ply"

    output_path = _Path(output_path)
    last_iter = params.get("total_steps", 30000)
    search_dirs = [
        output_path,
        output_path / "point_cloud" / f"iteration_{last_iter}",
        output_path / "point_cloud" / f"iteration_{last_iter // 2}",
    ]

    found_ply = None
    last_mtime = 0.0

    def check_dir(directory):
        nonlocal found_ply, last_mtime
        if not directory.exists():
            return
        for file_path in directory.iterdir():
            if not (file_path.is_file() and file_path.name != ply_name):
                continue
            if not is_checkpoint_ply(file_path, output_path):
                continue
            mt = file_path.stat().st_mtime
            if mt > last_mtime:
                last_mtime = mt
                found_ply = file_path

    for directory in search_dirs:
        check_dir(directory)

    if not found_ply:
        for ply_file_path in find_checkpoint_plys(output_path):
            if ply_file_path.name != ply_name:
                mt = ply_file_path.stat().st_mtime
                if mt > last_mtime:
                    last_mtime = mt
                    found_ply = ply_file_path

    if found_ply:
        dest_path = output_path / ply_name
        try:
            shutil.move(str(found_ply), str(dest_path))
            log(_t("cli_ply_renamed", "PLY file renamed to: {name}", name=ply_name))
        except OSError as e:
            log(_t("cli_ply_rename_error", "PLY rename error: {err}", err=e))
    else:
        log(tr("cli_ply_rename_none", "Warning: no PLY file found to rename."))


def _apply_refine_mode(dataset_root, output_path, params, log=print):
    """Redirect Brush training into a Refine folder when resuming a run.

    Qt-free port of ``app/gui/workers.py::BrushWorker._prepare_refine_environment``
    (shared via ``app.core.brush_refine``): look for the latest checkpoint under
    ``dataset_root/checkpoints`` and, when one exists, build
    ``dataset_root/Refine`` (init.ply + symlinked sparse/images) and point
    ``start_iter`` at the checkpoint's own iteration. Without this,
    ``--refine_mode`` was stored but never consumed (audit L4-04).

    Returns
    -------
    (training_input, training_output): unchanged when no checkpoint exists yet
    (refine mode is then a no-op, exactly like the GUI), or redirected to the
    freshly built Refine folder when one was found.
    """
    dataset_root = _Path(dataset_root)
    try:
        result = prepare_refine_environment(dataset_root, log=log)
    except RefineEnvironmentError as e:
        print(_t("cli_generic_error", "Error: {err}", err=e))
        sys.exit(1)

    refine_dir, latest_ply = result
    if latest_ply is None:
        # No checkpoint found: refine mode is a no-op, train normally.
        return str(dataset_root), str(output_path)

    refine_output = refine_dir / "checkpoints"
    refine_output.mkdir(parents=True, exist_ok=True)
    log(_t("cli_refine_redirected", "Working folder redirected to: {path}", path=refine_dir))

    if params.get("start_iter", 0) == 0:
        total_steps = params.get("total_steps", 30000)
        detected_iter = detect_refine_start_iteration(latest_ply, total_steps)
        params["start_iter"] = detected_iter
        log(_t("cli_refine_start_iter", "Refine: start iteration set to {n}", n=detected_iter))

    return str(refine_dir), str(refine_output)


def _build_brush_params(args) -> dict:
    """Assemble Brush params from defaults, preset and explicit CLI overrides.

    Shared by ``run_brush`` and ``run_pipeline``. Options only one sub-command
    defines are read with ``getattr`` and ignored when absent or ``None``.
    """
    params = dict(BRUSH_DEFAULTS)

    if args.preset != "default":
        params.update(BRUSH_PRESETS[args.preset])

    # Explicit args override preset (only when provided by user)
    overrides = {
        "total_steps": "iterations",
        "sh_degree": "sh_degree",
        "start_iter": "start_iter",
        "refine_every": "refine_every",
        "growth_grad_threshold": "growth_grad_threshold",
        "growth_select_fraction": "growth_select_fraction",
        "growth_stop_iter": "growth_stop_iter",
        "max_splats": "max_splats",
        "checkpoint_interval": "checkpoint_interval",
        "max_resolution": "max_resolution",
    }
    for key, arg_name in overrides.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            params[key] = value

    params["device"] = args.device
    params["with_viewer"] = args.with_viewer
    # `pipeline` has no --refine_mode flag of its own today (only `brush`
    # does), so fall back to False when the argument is missing.
    params["refine_mode"] = getattr(args, "refine_mode", False)
    if args.ply_name:
        params["ply_name"] = args.ply_name
    return params


def _print_brush_settings(preset, params):
    """Echo the effective Brush settings (shared by ``brush`` and ``pipeline``)."""
    _print_kv(
        ("cli_lbl_preset", "Preset", preset),
        ("cli_lbl_steps", "Steps", params["total_steps"]),
        ("cli_lbl_sh_degree", "SH degree", params["sh_degree"]),
        ("cli_lbl_device", "Device", params["device"]),
    )


def run_brush(args):
    params = _build_brush_params(args)
    if args.custom_args:
        params["custom_args"] = args.custom_args

    print(tr("cli_start_brush"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))
    _print_brush_settings(args.preset, params)

    engine = BrushEngine(logger_callback=print)

    # Detect build mode from installed binary to use correct flags
    params["build_mode"] = get_brush_build_mode()

    train_input, train_output = args.input, args.output
    if params["refine_mode"]:
        train_input, train_output = _apply_refine_mode(args.input, args.output, params, log=print)

    try:
        returncode = engine.train(train_input, train_output, params=params)
        if returncode == 0:
            _handle_ply_rename(train_output, params, log=print)
            print(tr("msg_success"))
        else:
            print(tr("msg_error"))
            sys.exit(1)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(130)


def _apply_sharp_upscale(args) -> str:
    """Pre-upscale a Sharp image input via upscayl-bin, before prediction.

    Mirrors ``app/gui/workers.py::SharpWorker.run()`` (the GUI's "upscale
    before" checkbox): the input is copied to a temp folder under the output
    directory, upscaled with upscayl-bin, and the upscaled copy is handed to
    Sharp instead of the original. Falls back to the original path — logging
    why — on any failure, same as the GUI (audit L4-02 / L3-02).
    """
    if not getattr(args, "upscale", False):
        return args.input

    from app.core.sharp_upscale import preupscale_image

    upscale_params = {
        "model_id": args.upscale_model or "",
        "scale": args.upscale_scale,
        "format": args.upscale_format,
        "tile": args.upscale_tile,
        "tta": args.upscale_tta,
        "compression": args.upscale_compression,
    }
    upscaled = preupscale_image(args.input, args.output, upscale_params, print)
    return str(upscaled) if upscaled else args.input


def run_sharp(args):
    engine = SharpEngine(logger_callback=print)

    params = {
        "checkpoint": args.checkpoint,
        "device": args.device,
        "verbose": args.verbose,
    }

    if args.mode == "image":
        print(tr("cli_start_sharp"))
        print(tr("cli_input", args.input))
        print(tr("cli_output", args.output))

        sharp_input = _apply_sharp_upscale(args)

        try:
            returncode = engine.predict(sharp_input, args.output, params=params)
            if returncode == 0:
                print(tr("msg_success"))
            else:
                print(tr("msg_error"))
                sys.exit(1)
        except KeyboardInterrupt:
            print(tr("cli_stopping"))
            engine.stop()
            sys.exit(130)
        finally:
            if sharp_input != args.input:
                import shutil
                shutil.rmtree(_Path(args.output) / "temp_upscale", ignore_errors=True)

    else:  # video mode
        # Mirrors the GUI: SharpVideoWorker never reads "upscale" either — the
        # pre-upscale step only exists for the single-image path.
        if getattr(args, "upscale", False):
            print(tr("cli_sharp_upscale_video_ignored", "⚠ --upscale is not supported in video mode - ignored."))
        _run_sharp_video(args, engine, params)


def _run_sharp_video(args, engine, params):
    """CLI handler for Sharp video mode — delegates to shared SharpEngine.process_video_frames()."""
    video_path = _Path(args.input)
    output_dir = _Path(args.output)
    skip = max(1, args.skip_frames)

    print(_t("cli_sharp_video", "Sharp video: {name} (1 frame / {skip})", name=video_path.name, skip=skip))
    print(tr("cli_output", args.output))

    params["skip_frames"] = skip

    try:
        success_count = engine.process_video_frames(
            video_path=str(video_path),
            output_dir=str(output_dir),
            params=params,
            log_callback=print,
            status_callback=lambda s: print(f"  {s}"),
            progress_callback=None,
            cancel_check=None,
        )
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(130)

    print(_t("cli_sharp_video_done", "Done: {n} frames converted.", n=success_count))
    if success_count == 0:
        sys.exit(1)


def run_supersplat(args):
    engine = SuperSplatEngine()

    if os.path.isfile(args.input):
        data_dir = os.path.dirname(args.input)
        filename = os.path.basename(args.input)
    else:
        data_dir = args.input
        filename = ""

    ok, msg = engine.start_data_server(data_dir, port=args.data_port, viewer_port=args.port)
    if not ok:
        print(f"{tr('msg_error')}: {msg}")
        sys.exit(1)
    print(msg)

    ok, msg = engine.start_supersplat(port=args.port)
    if not ok:
        print(f"{tr('msg_error')}: {msg}")
        engine.stop_all()
        sys.exit(1)
    print(msg)

    # Build URL with optional params
    url = f"http://localhost:{args.port}"
    url_params = []
    if filename:
        data_url = f"http://localhost:{args.data_port}/{quote(filename)}"
        url_params.append(f"load={data_url}")
    if args.no_ui:
        url_params.append("noui")
    if args.cam_pos:
        url_params.append(f"cameraPosition={args.cam_pos.strip()}")
    if args.cam_rot:
        url_params.append(f"cameraRotation={args.cam_rot.strip()}")
    if url_params:
        url += "?" + "&".join(url_params)

    print("\n" + _t("cli_open_url", "Open: {url}", url=url) + "\n")
    print(tr("cli_ctrl_c_hint", "Press Ctrl+C to stop the servers."))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(tr("cli_server_stop"))
        engine.stop_all()
        sys.exit(130)


def run_upscale(args):
    from app.core.upscale_engine import UpscaleEngine

    engine = UpscaleEngine(logger_callback=print)

    if not engine.is_installed():
        print(tr("cli_upscale_no_binary", "Error: upscayl-bin not found. Install it from the Upscale tab of the graphical interface."))
        sys.exit(1)

    upsampler = engine.load_model(
        model_id=args.model,
        scale=args.scale,
        output_format=args.format,
        tile=args.tile,
        tta=args.tta,
        compression=args.compression,
    )
    if not upsampler:
        print(tr("cli_upscale_no_model", "Error: unable to load the model."))
        sys.exit(1)

    input_path = _Path(args.input)
    output_path = _Path(args.output)

    print(_t("cli_upscale_header", "Upscale x{scale} - model: {model}", scale=args.scale, model=args.model))
    _print_kv(
        ("cli_lbl_input", "Input", args.input),
        ("cli_lbl_output", "Output", args.output),
    )

    try:
        if input_path.is_dir():
            success, msg = engine.upscale_folder(
                str(input_path), str(output_path),
                cancel_check=None, **upsampler,
            )
        else:
            success = engine.upscale_image(str(input_path), str(output_path / input_path.name), upsampler)
            msg = tr("up_msg_complete", "Upscale complete.") if success else tr("up_err_failed", "Upscale failed.")
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        sys.exit(130)

    key, default = ("cli_result_ok", "Success: {msg}") if success else ("cli_result_err", "Error: {msg}")
    print(_t(key, default, msg=msg))
    if not success:
        sys.exit(1)


def run_4dgs(args):
    from app.core.four_dgs_engine import FourDGSEngine

    engine = FourDGSEngine(logger_callback=print)

    # --input is not required by the parser (it is ignored in --colmap_only
    # mode), so it must be validated here instead once we know which mode
    # actually needs it (audit L4-09b).
    if not args.colmap_only:
        if not args.input:
            print(tr("cli_4dgs_input_required", "Error: --input is required (except in --colmap_only mode)."))
            sys.exit(1)
        if not _Path(args.input).exists():
            print(_t("cli_4dgs_input_missing", "Error: source folder not found: {path}", path=args.input))
            sys.exit(1)

    print(tr("cli_4dgs_prep", "4DGS dataset preparation"))
    _print_kv(
        ("cli_lbl_input", "Input", args.input),
        ("cli_lbl_output", "Output", args.output),
    )

    try:
        if args.colmap_only:
            print(tr("cli_4dgs_colmap_only", "COLMAP-only mode."))
            success = engine.run_colmap(args.output)
        else:
            _print_kv(("cli_lbl_fps", "FPS", args.fps))
            success = engine.process_dataset(args.input, args.output, fps=args.fps)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(130)

    print(tr("cli_done_ok", "Completed successfully.") if success else tr("cli_4dgs_failed", "Error during processing."))
    if not success:
        sys.exit(1)


def _clean_overrides(args):
    """Collect the explicitly given cleaning thresholds."""
    overrides = {}
    if args.opacity_min is not None:
        overrides["opacity_min"] = args.opacity_min
    if args.scale_pct is not None:
        overrides["scale_pct"] = args.scale_pct
    if args.outlier_pct is not None:
        overrides["outlier_pct"] = args.outlier_pct
    return overrides


def _clean_folder(args, input_path, output_path, overrides):
    """Folder mode: clean every .ply of ``input_path`` into ``output_path``."""
    print(_t("cli_clean_batch", "Batch cleaning: {src} → {dst}", src=input_path, dst=output_path))
    _print_kv(
        ("cli_lbl_severity", "Severity", args.strength),
        ("cli_lbl_recursive", "Recursive", tr("cli_yes", "yes") if args.recursive else tr("cli_no", "no")),
    )
    if overrides:
        _print_kv(("cli_lbl_overrides", "Overrides", overrides))

    try:
        all_stats = clean_ply_batch(
            input_path, output_path,
            strength=args.strength, overrides=overrides or None,
            log=print, recursive=args.recursive,
        )
        success = sum(1 for s in all_stats if "error" not in s)
        failed = len(all_stats) - success
        for s in all_stats:
            if "error" in s:
                print(_t("cli_clean_item_err", "  ✗ {file}: {err}", file=s["file"], err=s["error"]))
            else:
                print(_t("cli_clean_item_ok", "  ✓ {file}: {kept}/{total} splats kept",
                         file=s["file"], kept=s["kept"], total=s["total"]))
        print(_t("cli_clean_batch_done", "Done: {ok} succeeded, {failed} failed.", ok=success, failed=failed))
        if failed > 0:
            sys.exit(1)
    except ValueError as e:
        print(_t("cli_generic_error", "Error: {err}", err=e))
        sys.exit(1)


def _clean_single(args, overrides):
    """Single file mode."""
    print(_t("cli_clean_single", "PLY cleaning: {src} → {dst}", src=args.input, dst=args.output))
    _print_kv(("cli_lbl_severity", "Severity", args.strength))
    if overrides:
        _print_kv(("cli_lbl_overrides", "Overrides", overrides))

    try:
        stats = clean_ply(args.input, args.output, strength=args.strength, overrides=overrides or None, log=print)
        print(_t("cli_clean_single_done", "Done: {kept}/{total} splats kept ({removed} removed)",
                 kept=stats["kept"], total=stats["total"], removed=stats["removed"]))
    except (ValueError, FileNotFoundError) as e:
        print(_t("cli_generic_error", "Error: {err}", err=e))
        sys.exit(1)


def _chain_export_after_clean(args, input_path):
    """Optional chaining: Clean → Export (``--then_export``)."""
    from app.core.export_engine import ExportEngine

    then_format = args.then_export
    export_output = args.export_output

    # Determine the files to export
    if input_path.is_dir():
        # clean_ply_batch() mirrors the input tree into the output folder
        # when --recursive is set (ply_cleaner.py), so cleaned files can
        # live in sub-folders. A non-recursive glob here silently dropped
        # them from the export (audit L4-05).
        glob_pattern = "**/*.ply" if args.recursive else "*.ply"
        export_sources = sorted(_Path(args.output).glob(glob_pattern))
        export_root = _Path(export_output) if export_output else _Path(args.output)
        msg_sources = _t("cli_files_in_dir", "{n} files in {dir}", n=len(export_sources), dir=args.output)
    else:
        export_sources = [_Path(args.output)]
        export_root = _Path(export_output) if export_output else _Path(args.output).parent
        msg_sources = str(args.output)

    print("\n" + tr("cli_chain_header", "── Clean → Export chaining ──"))
    _print_kv(
        ("cli_lbl_format", "Format", then_format),
        ("cli_lbl_sources", "Sources", msg_sources),
        ("cli_lbl_dest", "Dest.", export_root),
    )

    engine = ExportEngine(logger_callback=print)
    success_count = 0
    for src in export_sources:
        if src.exists():
            ok = engine.export(str(src), str(export_root), then_format)
            if ok:
                success_count += 1
                print(_t("cli_export_item_ok", "  ✓ {name} → {fmt}", name=src.name, fmt=then_format))
            else:
                print(_t("cli_export_item_fail", "  ✗ {name} → failed", name=src.name))
        else:
            print(_t("cli_export_item_missing", "  ⚠️  {name} not found - skipped", name=src.name))

    print(_t("cli_export_done", "Export finished: {ok}/{total} succeeded.", ok=success_count, total=len(export_sources)))
    if success_count < len(export_sources):
        sys.exit(1)


def run_clean(args):
    """Clean one .ply file, or every .ply of a folder."""
    overrides = _clean_overrides(args)

    input_path = _Path(args.input)
    output_path = _Path(args.output)

    if input_path.is_dir():
        _clean_folder(args, input_path, output_path, overrides)
    else:
        _clean_single(args, overrides)

    if getattr(args, "then_export", None):
        _chain_export_after_clean(args, input_path)


def run_splat_transform(args):
    """Convert or filter Gaussian Splat files via PlayCanvas splat-transform."""
    from app.core.splat_transform_engine import SplatTransformEngine

    engine = SplatTransformEngine(logger_callback=print)

    if not engine.is_available():
        print(tr(
            "cli_st_not_found",
            "Error: splat-transform not found.\n"
            "Install it by running:  python3 app/scripts/setup_dependencies.py\n"
            "or manually:  cd engines/splat-transform && npm install @playcanvas/splat-transform",
        ))
        sys.exit(1)

    input_path = _Path(args.input)
    output_dir = _Path(args.output)

    if not input_path.exists():
        print(_t("cli_st_input_missing", "Error: input file not found: {path}", path=input_path))
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_path.stem}.{args.format}"

    params = {"--overwrite": True}
    if args.filter_nan:
        params["--filter-nan"] = True
    if args.filter_harmonics is not None:
        params["--filter-harmonics"] = args.filter_harmonics
    if args.decimate is not None:
        params["--decimate"] = args.decimate
    if args.morton_order:
        params["--morton-order"] = True

    print(f"SplatTransform: {input_path} → {output_file}")
    _print_kv(("cli_lbl_format", "Format", args.format))
    shown = [k if v is True else f"{k} {v}" for k, v in params.items() if k != "--overwrite"]
    if shown:
        _print_kv(("cli_lbl_options", "Options", ", ".join(shown)))

    try:
        returncode = engine.transform(str(input_path), str(output_file), params)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(130)

    if returncode == 0:
        print(tr("msg_success"))
    else:
        print(tr("msg_error"))
        sys.exit(1)


def run_extract360(args):
    from app.core.extractor_360_engine import Extractor360Engine

    engine = Extractor360Engine(logger_callback=print)

    if not engine.is_installed():
        print(tr("cli_x360_not_installed", "Error: 360° extractor not installed. Enable it from the 360° tab of the graphical interface."))
        sys.exit(1)

    params = {
        "interval":         args.interval,
        "format":           args.format,
        "resolution":       args.resolution,
        "camera_count":     args.camera_count,
        "quality":          args.quality,
        "layout":           args.layout,
        "ai_mask":          args.ai_mask,
        "ai_skip":          args.ai_skip,
        "adaptive":         args.adaptive,
        "motion_threshold": args.motion_threshold,
    }

    print(tr("cli_x360_header", "360° video extraction"))
    _print_kv(
        ("cli_lbl_input", "Input", args.input),
        ("cli_lbl_output", "Output", args.output),
        ("cli_lbl_interval", "Interval", f"{args.interval}s"),
        ("cli_lbl_resolution", "Resolution", f"{args.resolution}px"),
        ("cli_lbl_cameras", "Cameras", args.camera_count),
    )

    try:
        success = engine.run_extraction(
            args.input, args.output, params,
            log_callback=print,
            progress_callback=integer_steps(lambda x: print("  " + tr("cli_progression", x))),
        )
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(130)

    print(tr("cli_done_ok", "Completed successfully.") if success else tr("cli_x360_failed", "Error during extraction."))
    if not success:
        sys.exit(1)


def _sep(title):
    print(f"\n{'─' * 50}\n  {title}\n{'─' * 50}")


def _step_title(index, total, key, default):
    """``Step i/n - <title>`` header text for the pipeline."""
    return _t("cli_step_header", "Step {i}/{n} - {title}", i=index, n=total, title=tr(key, default))


def _pipeline_colmap_step(args, total_steps):
    """Step 1 of ``pipeline``: COLMAP. Returns the dataset path."""
    _sep(_step_title(1, total_steps, "cli_step_colmap", "COLMAP reconstruction"))
    _print_kv(
        ("cli_lbl_input", "Input", args.input),
        ("cli_lbl_output", "Output", args.output),
        ("cli_lbl_project", "Project", args.project_name),
        ("cli_lbl_type", "Type", args.type),
    )
    if args.type == "video":
        _print_kv(("cli_lbl_fps", "FPS", args.fps))

    colmap_params = _build_colmap_params(args)

    colmap_engine = ColmapEngine(
        colmap_params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=integer_steps(lambda x: print("  " + tr("cli_progression", x))),
    )

    try:
        success, msg = colmap_engine.run()
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        colmap_engine.stop()
        sys.exit(130)

    if not success:
        print("\n" + _t("cli_colmap_error", "COLMAP error: {msg}", msg=msg))
        sys.exit(1)

    dataset_path = _Path(args.output) / args.project_name
    print("\n" + _t("cli_dataset_ready", "Dataset ready: {path}", path=dataset_path))
    return dataset_path


def _pipeline_brush_step(args, dataset_path, total_steps):
    """Step 2 of ``pipeline``: Brush. Returns ``(checkpoints_dir, brush_params)``."""
    _sep(_step_title(2, total_steps, "cli_step_brush", "Brush training"))

    brush_params = _build_brush_params(args)

    # Same checkpoint layout as the GUI. The CLI used to pass dataset_path as
    # its own output, so a project started here and reopened in the interface
    # (or the reverse) did not find its checkpoints where the other expected
    # them. resolve_checkpoints_dir() is the single source of that semantics.
    checkpoints_dir = resolve_checkpoints_dir({
        "output_path": args.output,
        "project_name": args.project_name,
        "checkpoint_dest": "",
    }) or dataset_path
    checkpoints_dir = _Path(checkpoints_dir)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    _print_kv(
        ("cli_lbl_dataset", "Dataset", dataset_path),
        ("cli_lbl_checkpoints", "Checkpoints", checkpoints_dir),
    )
    _print_brush_settings(args.preset, brush_params)

    brush_engine = BrushEngine(logger_callback=print)

    # Detect build mode from installed binary to use correct flags
    brush_params["build_mode"] = get_brush_build_mode()

    train_input, train_output = str(dataset_path), str(checkpoints_dir)
    if brush_params["refine_mode"]:
        train_input, train_output = _apply_refine_mode(dataset_path, checkpoints_dir, brush_params, log=print)
    checkpoints_dir = _Path(train_output)

    try:
        returncode = brush_engine.train(train_input, train_output, params=brush_params)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        brush_engine.stop()
        sys.exit(130)

    if returncode != 0:
        print("\n" + _t("cli_brush_error", "Brush returned an error (code {code}).", code=returncode))
        sys.exit(1)

    print("\n" + _t("cli_training_done", "Training finished. Splat available in: {path}", path=checkpoints_dir))
    return checkpoints_dir, brush_params


def run_pipeline(args):
    """COLMAP → Brush pipeline, then cleaning and export when requested."""
    # Step count depends on the opt-in flags, so the headers do not promise
    # "1/2" while four steps are about to run.
    total_steps = 2 + bool(getattr(args, "clean", None)) + bool(getattr(args, "export", None))

    dataset_path = _pipeline_colmap_step(args, total_steps)
    checkpoints_dir, brush_params = _pipeline_brush_step(args, dataset_path, total_steps)

    # ── Steps 3-4: optional Clean and Export ─────────────────────────────────
    # `pipeline` used to stop here, so it did not reproduce the GUI chain
    # (Reconstruction → Training → Cleaning → Export) its name promises.
    # Both steps are opt-in: --clean and --export.
    #
    # The ply_name rename happens after, not before: _run_pipeline_post_steps
    # locates its source checkpoint with the same is_checkpoint_ply() pattern
    # match _handle_ply_rename uses to *produce* the renamed file, so renaming
    # first would make the checkpoint invisible to Clean/Export (audit L4-03).
    _run_pipeline_post_steps(args, checkpoints_dir, total_steps)
    _handle_ply_rename(checkpoints_dir, brush_params, log=print)


def _latest_checkpoint_ply(checkpoints_dir):
    """Newest checkpoint produced by the training, or None.

    Uses the same rule as the interface (`find_checkpoint_plys`) so both agree
    on which files belong to the run and which belong to the user.
    """
    plys = find_checkpoint_plys(_Path(checkpoints_dir))
    if not plys:
        return None
    return max(plys, key=lambda p: p.stat().st_mtime)


def _run_pipeline_post_steps(args, checkpoints_dir, total_steps):
    """Chain cleaning and export after a successful training."""
    wants_clean = getattr(args, "clean", None)
    wants_export = getattr(args, "export", None)
    if not wants_clean and not wants_export:
        return

    source_ply = _latest_checkpoint_ply(checkpoints_dir)
    if source_ply is None:
        print("\n" + tr("cli_no_checkpoint", "⚠️  No checkpoint .ply found - cleaning and export skipped."))
        return

    if wants_clean:
        _sep(_step_title(3, total_steps, "cli_step_clean", "Cleaning"))
        cleaned = source_ply.with_name(f"{source_ply.stem}_cleaned.ply")
        _print_kv(
            ("cli_lbl_source", "Source", source_ply.name),
            ("cli_lbl_severity", "Severity", wants_clean),
        )
        try:
            stats = clean_ply(str(source_ply), str(cleaned), strength=wants_clean, log=print)
        except (ValueError, FileNotFoundError, MemoryError) as e:
            print(_t("cli_clean_failed", "Error during cleaning: {err}", err=e))
            sys.exit(1)
        print(_t("cli_clean_item", "  ✓ {name} ({kept} splats kept)", name=cleaned.name, kept=stats.get('kept', '?')))
        source_ply = cleaned

    if wants_export:
        from app.core.export_engine import ExportEngine

        step = 4 if wants_clean else 3
        _sep(_step_title(step, total_steps, "cli_step_export", "Export"))
        export_root = _Path(getattr(args, "export_output", None) or source_ply.parent)
        engine = ExportEngine(logger_callback=print)

        missing = engine.missing_dependency(wants_export)
        if missing:
            print(_t("exp_log_missing_dependency",
                     "Error: {fmt} export unavailable - missing dependency: {dep}",
                     fmt=wants_export, dep=missing))
            sys.exit(1)

        _print_kv(
            ("cli_lbl_source", "Source", source_ply.name),
            ("cli_lbl_format", "Format", wants_export),
            ("cli_lbl_dest", "Dest.", export_root),
        )
        if not engine.export(str(source_ply), str(export_root), wants_export):
            print(tr("cli_export_failed", "Error: export failed."))
            sys.exit(1)
        print(f"  ✓ {source_ply.stem}.{wants_export}")


# ─────────────────────────────────────────────────────────────────────────────
# Command dispatch
# ─────────────────────────────────────────────────────────────────────────────

DISPATCH = {
    "pipeline":         run_pipeline,
    "colmap":           run_colmap,
    "brush":            run_brush,
    "sharp":            run_sharp,
    "view":             run_supersplat,
    "upscale":          run_upscale,
    "4dgs":             run_4dgs,
    "extract360":       run_extract360,
    "clean":            run_clean,
    "splattransform":   run_splat_transform,
}
