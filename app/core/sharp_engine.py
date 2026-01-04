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
        # Si installe dans le venv, 'sharp' doit etre dans le path
        from shutil import which
        if which("sharp"):
            return ["sharp"]
            
        # Fallback: python -m sharp? (if module)
        return [sys.executable, "-m", "sharp"]

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
