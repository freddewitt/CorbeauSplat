#!/usr/bin/env python3
"""CLI command handlers for CorbeauSplat."""
import os
import sys
import time
from pathlib import Path as _Path

from app.core.brush_engine import BrushEngine
from app.core.engine import ColmapEngine
from app.core.i18n import tr
from app.core.params import ColmapParams
from app.core.superplat_engine import SuperSplatEngine
from app.core.system import get_brush_build_mode

# ─────────────────────────────────────────────────────────────────────────────
# Brush defaults and presets
# ─────────────────────────────────────────────────────────────────────────────

BRUSH_DEFAULTS = {
    "total_steps": 30000,
    "sh_degree": 3,
    "start_iter": 0,
    "refine_every": 200,
    "growth_grad_threshold": 0.003,
    "growth_select_fraction": 0.2,
    "growth_stop_iter": 15000,
    "max_splats": 10_000_000,
    "checkpoint_interval": 7000,
    "max_resolution": 0,
    "with_viewer": False,
    "refine_mode": False,
}

_BLUR_FACTORS = {"light": 0.5, "medium": 0.7, "strong": 0.85}


BRUSH_PRESETS = {
    "fast": {
        "total_steps": 7000, "refine_every": 100,
        "growth_grad_threshold": 0.01, "growth_select_fraction": 0.2,
        "growth_stop_iter": 6000,
    },
    "std": {
        "total_steps": 30000, "refine_every": 200,
        "growth_grad_threshold": 0.003, "growth_select_fraction": 0.2,
        "growth_stop_iter": 15000,
    },
    "dense": {
        "total_steps": 50000, "refine_every": 100,
        "growth_grad_threshold": 0.0005, "growth_select_fraction": 0.6,
        "growth_stop_iter": 40000,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Run functions
# ─────────────────────────────────────────────────────────────────────────────

def run_colmap(args):
    params = ColmapParams(
        camera_model=args.camera_model,
        single_camera=not args.no_single_camera,
        max_image_size=args.max_image_size,
        max_num_features=args.max_num_features,
        estimate_affine_shape=args.estimate_affine_shape,
        domain_size_pooling=not args.no_domain_size_pooling,
        max_ratio=args.max_ratio,
        max_distance=args.max_distance,
        cross_check=not args.no_cross_check,
        min_model_size=args.min_model_size,
        multiple_models=args.multiple_models,
        ba_refine_focal_length=not args.no_refine_focal,
        ba_refine_principal_point=args.refine_principal,
        ba_refine_extra_params=not args.no_refine_extra,
        min_num_matches=args.min_num_matches,
        matcher_type=args.matcher_type,
        undistort_images=args.undistort,
        use_glomap=args.use_glomap,
        filter_blurry=args.filter_blur,
        blur_factor=_BLUR_FACTORS.get(args.blur_strength, 0.7),
    )

    print(tr("cli_start_colmap"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))

    engine = ColmapEngine(
        params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=lambda x: print(tr("cli_progression", x)),
    )

    success, msg = engine.run()
    if success:
        print(tr("cli_success", msg))
    else:
        print(tr("cli_error", msg))
        sys.exit(1)


def run_brush(args):
    params = dict(BRUSH_DEFAULTS)

    if args.preset != "default":
        params.update(BRUSH_PRESETS[args.preset])

    # Explicit args override preset (only when provided by user)
    if args.iterations is not None:           params["total_steps"] = args.iterations
    if args.sh_degree is not None:            params["sh_degree"] = args.sh_degree
    if args.start_iter is not None:           params["start_iter"] = args.start_iter
    if args.refine_every is not None:         params["refine_every"] = args.refine_every
    if args.growth_grad_threshold is not None: params["growth_grad_threshold"] = args.growth_grad_threshold
    if args.growth_select_fraction is not None: params["growth_select_fraction"] = args.growth_select_fraction
    if args.growth_stop_iter is not None:     params["growth_stop_iter"] = args.growth_stop_iter
    if args.max_splats is not None:           params["max_splats"] = args.max_splats
    if args.checkpoint_interval is not None:  params["checkpoint_interval"] = args.checkpoint_interval
    if args.max_resolution is not None:       params["max_resolution"] = args.max_resolution

    params["device"] = args.device
    params["refine_mode"] = args.refine_mode
    params["with_viewer"] = args.with_viewer
    if args.custom_args: params["custom_args"] = args.custom_args
    if args.ply_name:    params["ply_name"] = args.ply_name

    print(tr("cli_start_brush"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))
    print(f"  Preset     : {args.preset}")
    print(f"  Steps      : {params['total_steps']}")
    print(f"  SH degree  : {params['sh_degree']}")
    print(f"  Device     : {params['device']}")

    engine = BrushEngine(logger_callback=print)

    # Detect build mode from installed binary to use correct flags
    params["build_mode"] = get_brush_build_mode()

    try:
        returncode = engine.train(args.input, args.output, params=params)
        if returncode == 0:
            print(tr("msg_success"))
        else:
            print(tr("msg_error"))
            sys.exit(1)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()


def run_supersplat(args):
    engine = SuperSplatEngine()

    if os.path.isfile(args.input):
        data_dir = os.path.dirname(args.input)
        filename = os.path.basename(args.input)
    else:
        data_dir = args.input
        filename = ""

    ok, msg = engine.start_data_server(data_dir, port=args.data_port)
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
        data_url = f"http://localhost:{args.data_port}/{filename}"
        url_params.append(f"load={data_url}")
    if args.no_ui:
        url_params.append("noui")
    if args.cam_pos:
        url_params.append(f"cameraPosition={args.cam_pos.strip()}")
    if args.cam_rot:
        url_params.append(f"cameraRotation={args.cam_rot.strip()}")
    if url_params:
        url += "?" + "&".join(url_params)

    print(f"\nAccédez à : {url}\n")
    print("Appuyez sur Ctrl+C pour arrêter les serveurs.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(tr("cli_server_stop"))
        engine.stop_all()


def run_upscale(args):
    from app.core.upscale_engine import UpscaleEngine

    engine = UpscaleEngine(logger_callback=print)

    if not engine.is_installed():
        print("Erreur : upscayl-bin introuvable. Installez-le depuis l'onglet Upscale de l'interface graphique.")
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
        print("Erreur : impossible de charger le modèle.")
        sys.exit(1)

    input_path = _Path(args.input)
    output_path = _Path(args.output)

    print(f"Upscale x{args.scale} — modèle : {args.model}")
    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")

    try:
        if input_path.is_dir():
            success, msg = engine.upscale_folder(
                str(input_path), str(output_path),
                cancel_check=None, **upsampler,
            )
        else:
            success = engine.upscale_image(str(input_path), str(output_path / input_path.name), upsampler)
            msg = "Upscale terminé." if success else "Upscale échoué."
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        sys.exit(0)

    print(f"{'Succès' if success else 'Erreur'} : {msg}")
    if not success:
        sys.exit(1)


def run_4dgs(args):
    from app.core.four_dgs_engine import FourDGSEngine

    engine = FourDGSEngine(logger_callback=print)

    if not args.colmap_only and not _Path(args.input).exists():
        print(f"Erreur : dossier source introuvable : {args.input}")
        sys.exit(1)

    print("Préparation dataset 4DGS")
    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")

    try:
        if args.colmap_only:
            print("Mode COLMAP uniquement.")
            success = engine.run_colmap(args.output)
        else:
            print(f"  FPS    : {args.fps}")
            success = engine.process_dataset(args.input, args.output, fps=args.fps)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(0)

    print("Terminé avec succès." if success else "Erreur lors du traitement.")
    if not success:
        sys.exit(1)


def run_extract360(args):
    from app.core.extractor_360_engine import Extractor360Engine

    engine = Extractor360Engine(logger_callback=print)

    if not engine.is_installed():
        print("Erreur : Extracteur 360° non installé. Activez-le depuis l'onglet 360° de l'interface graphique.")
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

    print("Extraction vidéo 360°")
    print(f"  Input       : {args.input}")
    print(f"  Output      : {args.output}")
    print(f"  Interval    : {args.interval}s")
    print(f"  Résolution  : {args.resolution}px")
    print(f"  Caméras     : {args.camera_count}")

    try:
        success = engine.run_extraction(
            args.input, args.output, params,
            log_callback=print,
            progress_callback=lambda x: print(f"  Progression : {x}%"),
        )
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(0)

    print("Terminé avec succès." if success else "Erreur lors de l'extraction.")
    if not success:
        sys.exit(1)


def run_pipeline(args):
    """Pipeline complet COLMAP → Brush."""

    _sep = lambda title: print(f"\n{'─' * 50}\n  {title}\n{'─' * 50}")

    # ── Étape 1 : COLMAP ──────────────────────────────────────────────────────
    _sep("Étape 1/2 — Reconstruction COLMAP")
    print(f"  Input       : {args.input}")
    print(f"  Output      : {args.output}")
    print(f"  Projet      : {args.project_name}")
    print(f"  Type        : {args.type}")
    if args.type == "video":
        print(f"  FPS         : {args.fps}")

    colmap_params = ColmapParams(
        camera_model=args.camera_model,
        matcher_type=args.matcher_type,
        max_image_size=args.max_image_size,
        undistort_images=args.undistort,
        use_glomap=args.use_glomap,
        filter_blurry=args.filter_blur,
        blur_factor=_BLUR_FACTORS.get(args.blur_strength, 0.7),
    )

    colmap_engine = ColmapEngine(
        colmap_params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=lambda x: print(f"  Progression : {x}%"),
    )

    try:
        success, msg = colmap_engine.run()
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        colmap_engine.stop()
        sys.exit(0)

    if not success:
        print(f"\nErreur COLMAP : {msg}")
        sys.exit(1)

    dataset_path = _Path(args.output) / args.project_name
    print(f"\nDataset prêt : {dataset_path}")

    # ── Étape 2 : Brush ───────────────────────────────────────────────────────
    _sep("Étape 2/2 — Entraînement Brush")

    brush_params = dict(BRUSH_DEFAULTS)

    if args.preset != "default":
        brush_params.update(BRUSH_PRESETS[args.preset])

    if args.iterations is not None: brush_params["total_steps"] = args.iterations
    if args.sh_degree is not None:  brush_params["sh_degree"] = args.sh_degree
    if args.max_resolution is not None: brush_params["max_resolution"] = args.max_resolution
    brush_params["device"] = args.device
    brush_params["with_viewer"] = args.with_viewer
    if args.ply_name: brush_params["ply_name"] = args.ply_name

    print(f"  Dataset     : {dataset_path}")
    print(f"  Preset      : {args.preset}")
    print(f"  Steps       : {brush_params['total_steps']}")
    print(f"  SH degree   : {brush_params['sh_degree']}")
    print(f"  Device      : {brush_params['device']}")

    brush_engine = BrushEngine(logger_callback=print)

    # Detect build mode from installed binary to use correct flags
    brush_params["build_mode"] = get_brush_build_mode()

    try:
        returncode = brush_engine.train(str(dataset_path), str(dataset_path), params=brush_params)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        brush_engine.stop()
        sys.exit(0)

    if returncode == 0:
        print(f"\nPipeline terminé. Splat disponible dans : {dataset_path}")
    else:
        print(f"\nBrush a retourné une erreur (code {returncode}).")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Command dispatch
# ─────────────────────────────────────────────────────────────────────────────

DISPATCH = {
    "pipeline":    run_pipeline,
    "colmap":      run_colmap,
    "brush":       run_brush,
    "view":        run_supersplat,
    "upscale":     run_upscale,
    "4dgs":        run_4dgs,
    "extract360":  run_extract360,
}
