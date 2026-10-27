import os
import sys
from collections.abc import Callable
from typing import Any

from .base_engine import BaseEngine, IProcessRunner, PtyProcessRunner
from .live_progress import RateLimiter, parse_brush_bar
from .system import adapt_max_splats, get_thermal_state, resolve_binary

# Seconds between two training-bar lines copied into the log: the bar redraws
# several times a second, the log only needs a heartbeat.
_BAR_LOG_INTERVAL = 15.0


class BrushEngine(BaseEngine):
    """Engine for executing the Brush training pipeline.

    Provides path validation, secure command construction, and structured logging.
    """

    # Extra-args allowlist, split by build mode. The pinned release (v0.3.0)
    # and a source build (git main) do not accept the same options: the lists
    # below were read from `brush --help` of the release binary and from the
    # clap structs of main (crates/brush-{process,train,dataset}/src/config.rs,
    # apps/brush-cli/src/lib.rs) on 2026-10-08. A source build tracks HEAD, so
    # SOURCE_ONLY_FLAGS is a snapshot: refresh it from `brush --help` of the
    # compiled binary when a flag goes missing. Flags build_command() emits
    # itself (--export-path, --total-steps/--total-train-iters, --sh-degree,
    # --with-viewer) are deliberately absent. --save-iterations, --refine-pose,
    # --log-level and --test-split used to be listed although no Brush version
    # knows them (audit D14): a preset using one made Brush abort.
    COMMON_FLAGS = frozenset({
        "--start-iter", "--refine-every", "--growth-grad-threshold",
        "--growth-select-fraction", "--growth-stop-iter", "--max-splats",
        "--eval-every", "--eval-save-to-disk", "--eval-split-every",
        "--export-every", "--export-name", "--max-resolution", "--max-frames",
        "--subsample-frames", "--subsample-points", "--seed",
        "--lr-mean", "--lr-mean-end", "--lr-coeffs-dc", "--lr-coeffs-sh-scale",
        "--lr-opac", "--lr-rotation", "--lr-scale",
        "--ssim-weight", "--lpips-loss-weight", "--match-alpha-weight",
        "--mean-noise-weight",
    })
    RELEASE_ONLY_FLAGS = frozenset({
        "--aux-loss-time", "--lr-scale-end", "--opac-loss-weight",
        "--scale-loss-weight", "--rerun-enabled", "--rerun-log-splats-every",
        "--rerun-log-train-stats-every", "--rerun-max-img-size",
    })
    SOURCE_ONLY_FLAGS = frozenset({
        "--alpha-mode", "--background-color", "--background-noise-strength",
        "--growth-start-iter", "--invert-masks", "--lod-decimation-keep",
        "--lod-image-scale", "--lod-levels", "--lod-refine-steps",
        "--max-scene-batch-cache-size", "--min-scale-factor", "--opac-decay",
        "--random-init-scene-scale", "--render-mode", "--split-at-screen-size",
        "--units-per-meter",
    })
    # Union, kept for callers that only need "is this a Brush flag at all".
    ALLOWED_FLAGS = COMMON_FLAGS | RELEASE_ONLY_FLAGS | SOURCE_ONLY_FLAGS

    @classmethod
    def allowed_flags(cls, build_mode: str | None) -> frozenset[str]:
        """Flags accepted in custom_args for this build mode.

        Anything but "release" counts as a source build, the same rule
        build_command() applies to the total-steps spelling.
        """
        extra = cls.RELEASE_ONLY_FLAGS if build_mode == "release" else cls.SOURCE_ONLY_FLAGS
        return cls.COMMON_FLAGS | extra

    def __init__(self, logger_callback: Callable | None = None, thermal_throttling: bool = False,
                 progress_callback: Callable[[float, float | None], None] | None = None,
                 process_runner: IProcessRunner | None = None) -> None:
        """Initialize the Brush engine.

        Parameters
        ----------
        logger_callback: Optional[Callable]
            Callback to forward log messages to the UI.
        thermal_throttling: bool
            Whether to enable thermal throttling.
        progress_callback: Optional[Callable]
            Called with ``(percent, eta_seconds)`` as the training bar moves;
            ``eta_seconds`` is None until Brush reports a rate.
        process_runner: Optional[IProcessRunner]
            Defaults to a pseudo-terminal, the only way Brush draws its bar.
        """
        if process_runner is None and sys.platform != "win32" \
                and not os.environ.get("CORBEAUSPLAT_NO_PTY"):
            process_runner = PtyProcessRunner()
        super().__init__("Brush", logger_callback, process_runner=process_runner,
                         thermal_throttling=thermal_throttling)
        self.brush_bin = resolve_binary("brush")
        self.progress_callback = progress_callback
        # Set once a training bar has been parsed; the worker's checkpoint
        # poller stands down from then on.
        self.live_progress_seen = False
        self._bar_log_limiter = RateLimiter(_BAR_LOG_INTERVAL)

    def build_command(self, input_path: str, output_path: str,
                      params: dict[str, Any] | None = None) -> tuple[list[str], dict[str, str]]:
        """Build the Brush command list and environment from parameters.

        Parameters
        ----------
        input_path: str
            Path to the input data.
        output_path: str
            Destination directory for training results.
        params: dict, optional
            Training parameters.

        Returns
        -------
        Tuple[List[str], Dict[str, str]]
            The command list and environment dictionary.
        """
        params = params or {}
        cmd = [self.brush_bin]
        cmd.extend(["--export-path", str(output_path)])
        if params.get("total_steps"):
            steps_arg = "--total-steps" if params.get("build_mode") == "release" else "--total-train-iters"
            cmd.extend([steps_arg, str(params["total_steps"])])
        if params.get("sh_degree"):
            cmd.extend(["--sh-degree", str(params["sh_degree"])])
        if params.get("max_resolution"):
            cmd.extend(["--max-resolution", str(params["max_resolution"])])
        if params.get("with_viewer"):
            cmd.append("--with-viewer")
        env = os.environ.copy()
        device = params.get("device", self.device)
        if device == "mps":
            env["WGPU_BACKEND"] = "metal"
            env["WGPU_POWER_PREF"] = "high_performance"
        elif device == "cuda":
            env["WGPU_BACKEND"] = "vulkan"
            env["WGPU_POWER_PREF"] = "high_performance"

        for param_name, flag in [
            ("start_iter", "--start-iter"),
            ("refine_every", "--refine-every"),
            ("growth_grad_threshold", "--growth-grad-threshold"),
            ("growth_select_fraction", "--growth-select-fraction"),
            ("growth_stop_iter", "--growth-stop-iter"),
            ("max_splats", "--max-splats"),
        ]:
            if params.get(param_name) is not None:
                cmd.extend([flag, str(params[param_name])])

        # `or 0` rather than a default argument: the key can be present *with*
        # None from a hand-built dict (CLI, tests), and `None > 0` is a TypeError.
        # BrushParams.to_engine_params() filters None out, so this only bites
        # callers that bypass it.
        ckpt_interval = params.get("checkpoint_interval", 7000) or 0
        if ckpt_interval > 0:
            cmd.extend(["--export-every", str(ckpt_interval)])

        custom_args = params.get("custom_args")
        if custom_args:
            cmd.extend(self._filter_custom_args(custom_args, params.get("build_mode")))
        cmd.append(str(input_path))
        return cmd, env

    def _filter_custom_args(self, custom_args: str, build_mode: str | None) -> list[str]:
        """Keep only allowlisted flags (and their values) from a raw argument string."""
        allowed = self.allowed_flags(build_mode)
        args_list = custom_args.split()
        safe_args: list[str] = []
        i = 0
        while i < len(args_list):
            arg = args_list[i]
            has_value = i + 1 < len(args_list) and not args_list[i + 1].startswith("--")
            if arg in allowed:
                if arg == "--export-name" and has_value and (
                    "/" in args_list[i + 1] or "\\" in args_list[i + 1] or ".." in args_list[i + 1]
                ):
                    self.log(f"Avertissement de sécurité: nom d'export non autorisé ignoré ({args_list[i + 1]})")
                    i += 2
                    continue
                safe_args.append(arg)
                if has_value:
                    safe_args.append(args_list[i + 1])
                    i += 1
            elif arg in self.ALLOWED_FLAGS:
                # A real Brush flag, but for the other build mode: say so,
                # the user may just have picked the wrong mode.
                other = "source" if build_mode == "release" else "release"
                self.log(f"Avertissement: {arg} n'existe que dans le build Brush « {other} », ignoré")
                if has_value:
                    i += 1
            else:
                self.log(f"Avertissement de sécurité: paramètre non autorisé ignoré ({arg})")
                if has_value:
                    i += 1
            i += 1
        return safe_args

    def train(self, input_path: str, output_path: str, params: dict[str, Any] | None = None) -> int:
        """Run the Brush training process.

        Parameters
        ----------
        input_path: str
            Path to the input data.
        output_path: str
            Destination directory for training results.
        params: dict, optional
            Training parameters such as total_steps, sh_degree, device, etc.

        Returns
        -------
        int
            Return code from the executed command (0 on success).
        """
        # Validate input and output paths to prevent path traversal (OWASP-A01)
        safe_input = self.validate_path(input_path)
        safe_output = self.validate_path(output_path)
        if not safe_input or not safe_output:
            raise ValueError("Chemins invalides ou non sécurisés détectés.")
        if not self.brush_bin:
            raise RuntimeError("Exécutable 'brush' non trouvé.")

        # --- Memory & thermal adaptation ---
        eps = params or {}
        # `or`: the key may be present with None (hand-built dicts), which
        # adapt_max_splats() cannot multiply.
        orig_splats = eps.get("max_splats") or 10_000_000
        adapted = adapt_max_splats(orig_splats, thermal_throttling=self.thermal_throttling)
        if adapted < orig_splats:
            reduction_pct = 100 - int(100 * adapted / max(orig_splats, 1))
            thermal_state = get_thermal_state() if self.thermal_throttling else "disabled"
            self.log(
                f"⚠️  Mémoire sous pression (pct={self._mem_pressure():.0f}%, "
                f"thermique={thermal_state}) — "
                f"max_splats réduit de {reduction_pct}% "
                f"({orig_splats:,} → {adapted:,})"
            )
            # A copy, never the caller's dict: mutating it made a reused params
            # dict shrink max_splats again on every run.
            params = dict(eps, max_splats=adapted)

        cmd, env = self.build_command(str(safe_input), str(safe_output), params)
        self.log(f"Lancement Brush: {' '.join(cmd)}")
        # Brush training can exceed 1h on large scenes — use extended wall-clock timeout.
        # Inactivity detection disabled: Brush has legitimately long silent phases
        # (viewer init, checkpoint I/O, heavy computation) that trigger false positives.
        self.live_progress_seen = False
        self._bar_log_limiter = RateLimiter(_BAR_LOG_INTERVAL)
        return self._execute_command(
            cmd, env=env,
            line_callback=self._on_output_line,
            timeout=14400,      # 4h wall-clock safety net
            inactivity_timeout=0,   # disabled — noisy stdout behavior
        )

    def _on_output_line(self, line: str) -> None:
        """Training-bar redraws feed the progress; everything else is logged."""
        bar = parse_brush_bar(line)
        if bar is None:
            self.log(line)
            return
        step, total, rate = bar
        self.live_progress_seen = True
        eta = (total - step) / rate if rate > 0 else None
        if self.progress_callback:
            self.progress_callback(100.0 * step / total, eta)
        if self._bar_log_limiter.ready() or step == total:
            self.log(f"Brush : step {step}/{total}" + (f" · {rate:.1f} it/s" if rate > 0 else ""))

    @staticmethod
    def _mem_pressure() -> float:
        """Return current memory pressure percentage (0-100)."""
        from .system import get_memory_info
        return get_memory_info().get("percent", 0.0)
