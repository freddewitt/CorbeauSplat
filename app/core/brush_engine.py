import os
import sys
import subprocess
from pathlib import Path
from .base_engine import BaseEngine
from .system import resolve_binary

class BrushEngine(BaseEngine):
    """Moteur d'exécution pour Brush"""
    
    def __init__(self, logger_callback=None):
        super().__init__("Brush", logger_callback)
        self.brush_bin = resolve_binary("brush")
        self.process = None
        
    def train(self, input_path, output_path, params=None):
        """
        Lance l'entraînement Brush.
        params: dict of training parameters
        """
        if not self.brush_bin:
            raise RuntimeError("Exécutable 'brush' non trouvé.")
            
        params = params or {}
        cmd = [self.brush_bin]
        
        # Standard Options
        cmd.extend(["--export-path", str(output_path)])
        
        if params.get("total_steps"):
            cmd.extend(["--total-steps", str(params["total_steps"])])
            
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

        # Custom arguments (sanitized via shlex in caller or here)
        custom_args = params.get("custom_args")
        if custom_args:
            import shlex
            cmd.extend(shlex.split(custom_args))
            
        # Positional argument: source path
        cmd.append(str(input_path))
        
        # Lancement
        print(f"Lancement Brush: {' '.join(map(str, cmd))}")
        
        kwargs = {}
        if sys.platform != "win32":
            kwargs['preexec_fn'] = os.setsid
            
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env,
            **kwargs
        )
        
        return self.process

    def stop(self):
        """Arrête le processus en cours"""
        if self.process and self.process.poll() is None:
            if sys.platform != "win32":
                import os
                try: os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except: pass
            else:
                self.process.terminate()
            self.process.wait()
