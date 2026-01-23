import os
import subprocess
import signal
import sys
from app.core.system import resolve_binary

class SharpEngine:
    """Moteur d'execution pour Apple ML Sharp"""
    
    def __init__(self):
        # On cherche l'executable 'sharp' qui devrait etre dans le venv
        self.process = None
        
    def _get_sharp_cmd(self):
        # 1. Look for .venv_sharp dedicated environment
        # Root is 2 levels up from app/core/ (app/core/ -> app/ -> root/)
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sharp_venv_bin = os.path.join(root_dir, ".venv_sharp", "bin")
        
        # Check binary in venv_sharp
        sharp_bin = os.path.join(sharp_venv_bin, "sharp")
        if os.path.exists(sharp_bin) and os.access(sharp_bin, os.X_OK):
            return [sharp_bin]
            
        # Check python in venv_sharp -> run module
        sharp_python = os.path.join(sharp_venv_bin, "python3")
        if os.path.exists(sharp_python):
             return [sharp_python, "-m", "sharp.cli"]

        # 2. Try to find 'sharp' in the same bin dir as python executable (venv main)
        # Fallback if dedicated venv failed
        venv_bin = os.path.dirname(sys.executable)
        sharp_bin = os.path.join(venv_bin, "sharp")
        if os.path.exists(sharp_bin) and os.access(sharp_bin, os.X_OK):
            return [sharp_bin]

        # 3. Check global PATH
        from shutil import which
        if which("sharp"):
            return ["sharp"]
            
        # 3. Fallback: Run module (correct entry point based on pyproject.toml)
        # Entry point is sharp.cli:main_cli, so we should run -m sharp.cli if possible, 
        # but 'python -m sharp' failed. Let's try explicit module.
        return [sys.executable, "-m", "sharp.cli"]
    def is_installed(self):
        """Vérifie si Sharp est disponible (venv_sharp ou local)"""
        # Check venv_sharp binary
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sharp_venv_bin = os.path.join(root_dir, ".venv_sharp", "bin", "sharp")
        if os.path.exists(sharp_venv_bin): return True
        
        from shutil import which
        import importlib.util
        
        # 1. Check binary
        if which("sharp"): return True
        
        # 2. Check module
        if importlib.util.find_spec("sharp") is not None:
            return True
            
        return False

    def predict(self, input_path, output_path, checkpoint=None, device="default", verbose=False):
        """
        Lance la prediction Sharp.
        """
        cmd = self._get_sharp_cmd()
        
        cmd.extend(["predict"])
        cmd.extend(["-i", input_path])
        cmd.extend(["-o", output_path])
        
        if checkpoint:
            cmd.extend(["-c", checkpoint])
            
        if device and device != "default":
            cmd.extend(["--device", device])
            
        if verbose:
            cmd.append("--verbose")
            
        # Environnement
        env = os.environ.copy()
        
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

    def stop(self):
        """Arrête le processus en cours"""
        if self.process and self.process.poll() is None:
            if sys.platform != "win32":
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            else:
                self.process.terminate()
            self.process.wait()
