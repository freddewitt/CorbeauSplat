import os
import sys
import subprocess
import signal
from pathlib import Path
from .base_engine import BaseEngine
from .system import resolve_binary, resolve_project_root

class SharpEngine(BaseEngine):
    """Moteur d'execution pour Apple ML Sharp"""
    
    def __init__(self, logger_callback=None):
        super().__init__("Sharp", logger_callback)
        self.process = None
        
    def _get_sharp_cmd(self):
        # 1. Look for .venv_sharp dedicated environment
        root_dir = resolve_project_root()
        sharp_venv_bin = root_dir / ".venv_sharp" / "bin"
        
        # Check binary in venv_sharp
        sharp_bin = sharp_venv_bin / "sharp"
        if sharp_bin.exists() and os.access(sharp_bin, os.X_OK):
            return [str(sharp_bin)]
            
        # Check python in venv_sharp -> run module
        sharp_python = sharp_venv_bin / "python3"
        if sharp_python.exists():
             return [str(sharp_python), "-m", "sharp.cli"]
 
        # 2. Try to find 'sharp' in the same bin dir as python executable (venv main)
        # Fallback if dedicated venv failed
        venv_bin = Path(sys.executable).parent
        sharp_bin = venv_bin / "sharp"
        if sharp_bin.exists() and os.access(sharp_bin, os.X_OK):
            return [str(sharp_bin)]
 
        # 3. Check global PATH
        from shutil import which
        if which("sharp"):
            return ["sharp"]
            
        # 3. Fallback: Run module
        return [sys.executable, "-m", "sharp.cli"]
    def is_installed(self):
        """Vérifie si Sharp est disponible (venv_sharp ou local)"""
        # Check venv_sharp binary
        root_dir = resolve_project_root()
        sharp_venv_bin = root_dir / ".venv_sharp" / "bin" / "sharp"
        if sharp_venv_bin.exists(): return True
        
        from shutil import which
        import importlib.util
        
        # 1. Check binary
        if which("sharp"): return True
        
        # 2. Check module
        if importlib.util.find_spec("sharp") is not None:
            return True
            
        return False

    def predict(self, input_path, output_path, params=None):
        """
        Lance la prediction Sharp.
        params: dict of prediction parameters
        """
        params = params or {}
        cmd = self._get_sharp_cmd()
        
        cmd.extend(["predict"])
        # Prepare paths
        input_path = Path(input_path).resolve()
        output_path = Path(output_path).resolve()
        
        cmd.extend(["-i", str(input_path)])
        cmd.extend(["-o", str(output_path)])
        
        checkpoint = params.get("checkpoint")
        if checkpoint:
            cmd.extend(["-c", str(Path(checkpoint).resolve())])
            
        device = params.get("device", self.device)
        if device and device != "default":
            cmd.extend(["--device", device])
            
        if params.get("verbose"):
            cmd.append("--verbose")
            
        # Environnement
        env = os.environ.copy()
        
        # Ensure all args are strings for Popen
        cmd = [str(arg) for arg in cmd]
        
        print(f"Lancement Sharp: {' '.join(cmd)}")
        
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

    # stop method inherited and improved in SharpEngine if needed, 
    # but BaseEngine has a basic one. We keep the process-specific stop here.
    def stop(self):
        """Arrête le processus en cours"""
        super().stop()
        if self.process and self.process.poll() is None:
            if sys.platform != "win32":
                try: os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except Exception as e: self.log(f"Warning: Failed to kill process group: {e}")
            else:
                self.process.terminate()
            self.process.wait()
