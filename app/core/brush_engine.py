import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Tuple

from .base_engine import BaseEngine
from .system import resolve_binary

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
        # Brush runs on wgpu; on Windows/NVIDIA the DX12 and Vulkan backends both
        # target CUDA-class GPUs. We pin DX12 (most reliable on Windows) and let
        # wgpu pick the high-performance (discrete) adapter.
        if device in ("cuda", "auto"):
            env["WGPU_BACKEND"] = "dx12"
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
            args_list = custom_args.split()
            safe_args = []
            i = 0
            while i < len(args_list):
                arg = args_list[i]
                if arg in self.ALLOWED_FLAGS:
                    safe_args.append(arg)
                    if i + 1 < len(args_list) and not args_list[i + 1].startswith("--"):
                        safe_args.append(args_list[i + 1])
                        i += 1
                else:
                    self.log(f"Avertissement de sécurité: paramètre non autorisé ignoré ({arg})")
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
        cmd, env = self.build_command(str(safe_input), str(safe_output), params)
        self.log(f"Lancement Brush: {' '.join(cmd)}")
        return self._execute_command(cmd, env=env)
