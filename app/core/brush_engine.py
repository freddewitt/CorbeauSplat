import os
import logging
import shlex
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple

from .base_engine import BaseEngine
from .system import resolve_binary, adapt_max_splats, get_thermal_state

class BrushEngine(BaseEngine):
    """Engine for executing the Brush training pipeline.

    Provides path validation, secure command construction, and structured logging.
    """

    ALLOWED_FLAGS = {
        "--save-iterations", "--log-level", "--test-split",
        "--start-iter", "--refine-every", "--growth-grad-threshold",
        "--growth-select-fraction", "--growth-stop-iter", "--max-splats",
        "--eval-every", "--export-every", "--max-resolution", "--refine-pose"
    }

    def __init__(self, logger_callback: Optional[Callable] = None) -> None:
        """Initialize the Brush engine.

        Parameters
        ----------
        logger_callback: Optional[Callable]
            Callback to forward log messages to the UI.
        """
        super().__init__("Brush", logger_callback)
        self.brush_bin = resolve_binary("brush")
        self.process = None

    def build_command(self, input_path: str, output_path: str,
                      params: Optional[Dict[str, Any]] = None) -> Tuple[List[str], Dict[str, str]]:
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

        ckpt_interval = params.get("checkpoint_interval", 7000)
        if ckpt_interval > 0:
            cmd.extend(["--export-every", str(ckpt_interval)])

        custom_args = params.get("custom_args")
        build_mode = params.get("build_mode")
        if custom_args:
            try:
                args_list = shlex.split(custom_args)
            except ValueError as e:
                self.log(f"Erreur de parsing des arguments personnalisés: {e}")
                args_list = custom_args.split()  # fallback for backward compat
            safe_args = []
            i = 0
            # Flags that expect a numeric value
            _numeric_flags = {
                "--save-iterations", "--start-iter", "--refine-every",
                "--growth-grad-threshold", "--growth-select-fraction",
                "--growth-stop-iter", "--max-splats", "--eval-every",
                "--export-every", "--max-resolution",
            }
            # Flags that expect a path value
            _path_flags = {"--refine-pose"}
            while i < len(args_list):
                arg = args_list[i]
                if arg not in self.ALLOWED_FLAGS:
                    self.log(f"Avertissement de sécurité: paramètre non autorisé ignoré ({arg})")
                    i += 1
                    continue

                safe_args.append(arg)
                if i + 1 < len(args_list):
                    next_arg = args_list[i + 1]
                    # Refuse values that look like flags (start with '-')
                    if next_arg.startswith("-"):
                        self.log(f"Avertissement: valeur suspecte '{next_arg}' ignorée pour {arg}")
                        i += 2  # skip flag + suspicious value
                        continue
                    # Path-valued flags → validate via validate_path
                    if arg in _path_flags:
                        safe_val = self.validate_path(next_arg)
                        if safe_val is not None:
                            safe_args.append(str(safe_val))
                        else:
                            self.log(f"SECURITY: chemin non autorisé ignoré: {next_arg}")
                        i += 2  # consumed flag + value
                        continue
                    # Numeric-valued flags → coerce, refuse non-numeric garbage
                    if arg in _numeric_flags:
                        try:
                            float(next_arg)  # coerce to numeric
                            safe_args.append(next_arg)
                        except ValueError:
                            self.log(f"Valeur non numérique ignorée pour {arg}: {next_arg}")
                        i += 2  # consumed flag + value
                        continue
                    # Other allowed flags — accept value as-is
                    safe_args.append(next_arg)
                    i += 2  # consumed flag + value
                    continue
                # No value to consume
                i += 1
            cmd.extend(safe_args)
        cmd.append(str(input_path))
        return cmd, env

    def train(self, input_path: str, output_path: str, params: Optional[Dict[str, Any]] = None) -> int:
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
        orig_splats = eps.get("max_splats", 10_000_000)
        adapted = adapt_max_splats(orig_splats)
        if adapted < orig_splats:
            reduction_pct = 100 - int(100 * adapted / max(orig_splats, 1))
            thermal_state = get_thermal_state()
            self.log(
                f"⚠️  Mémoire sous pression (pct={self._mem_pressure():.0f}%, "
                f"thermique={thermal_state}) — "
                f"max_splats réduit de {reduction_pct}% "
                f"({orig_splats:,} → {adapted:,})"
            )
            if eps is params:
                params["max_splats"] = adapted
            else:
                params = dict(eps, max_splats=adapted)

        cmd, env = self.build_command(str(safe_input), str(safe_output), params)
        self.log(f"Lancement Brush: {' '.join(cmd)}")
        return self._execute_command(cmd, env=env)

    @staticmethod
    def _mem_pressure() -> float:
        """Return current memory pressure percentage (0-100)."""
        from .system import get_memory_info
        return get_memory_info().get("percent", 0.0)
