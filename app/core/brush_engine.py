import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from .base_engine import BaseEngine
from .system import resolve_binary

class BrushEngine(BaseEngine):
    """Engine for executing the Brush training pipeline.

    Provides path validation, secure command construction, and structured logging.
    """

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
        params = params or {}
        cmd = [self.brush_bin]
        # Standard Options
        cmd.extend(["--export-path", str(safe_output)])
        if params.get("total_steps"):
            cmd.extend(["--total-train-iters", str(params["total_steps"])])
        if params.get("sh_degree"):
            cmd.extend(["--sh-degree", str(params["sh_degree"])])
        if params.get("with_viewer"):
            cmd.append("--with-viewer")
        # Device handling via BaseEngine/system
        env = os.environ.copy()
        device = params.get("device", self.device)
        if device == "mps":
            env["WGPU_BACKEND"] = "metal"
            env["WGPU_POWER_PREF"] = "high_performance"
        elif device == "cuda":
            env["WGPU_BACKEND"] = "vulkan"
            env["WGPU_POWER_PREF"] = "high_performance"
        # Secure custom arguments (OWASP-A03)
        custom_args = params.get("custom_args")
        if custom_args:
            allowed_flags = {
                "--save-iterations", "--log-level", "--test-split",
                "--start-iter", "--refine-every", "--growth-grad-threshold",
                "--growth-select-fraction", "--growth-stop-iter", "--max-splats",
                "--eval-every", "--max-resolution", "--refine-pose"
            }
            args_list = custom_args.split()
            safe_args = []
            i = 0
            while i < len(args_list):
                arg = args_list[i]
                if arg in allowed_flags:
                    safe_args.append(arg)
                    if i + 1 < len(args_list) and not args_list[i + 1].startswith("--"):
                        safe_args.append(args_list[i + 1])
                        i += 1
                else:
                    self.log(f"Avertissement de sécurité: paramètre non autorisé ignoré ({arg})")
                i += 1
            cmd.extend(safe_args)
        # Positional argument: source path
        cmd.append(str(safe_input))
        # Execute command via Template Method
        self.log(f"Lancement Brush: {' '.join(cmd)}")
        return self._execute_command(cmd, env=env)
