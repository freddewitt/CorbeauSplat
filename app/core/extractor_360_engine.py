import os
import subprocess
from pathlib import Path
from .base_engine import BaseEngine
from app.scripts.setup_dependencies import install_extractor_360, get_venv_360_python, uninstall_extractor_360, resolve_project_root

from app.core.i18n import tr

class Extractor360Engine(BaseEngine):
    def __init__(self, logger_callback=None):
        super().__init__("360Extractor", logger_callback)
        self.root_dir = Path(resolve_project_root())
        self.engines_dir = self.root_dir / "engines"
        self.extractor_dir = self.engines_dir / "extractor_360"
        self.venv_python = Path(get_venv_360_python())
        self.script_path = self.extractor_dir / "src" / "main.py"

    def is_installed(self):
        """Checks if venv and script exist"""
        return self.venv_python.exists() and self.script_path.exists()

    def install(self):
        """Installs via setup_dependencies"""
        install_extractor_360()

    def uninstall(self):
        """Uninstalls"""
        uninstall_extractor_360()

    def run_extraction(self, input_path, output_dir, params, progress_callback=None, log_callback=None, check_cancel_callback=None):
        """
        Runs the extraction CLI.
        params: dict of arguments mirroring CLI args
        """
        if not self.is_installed():
            if log_callback: log_callback("Error: 360Extractor not installed.")
            return False

        cmd = [
            self.venv_python,
            self.script_path,
            "--input", input_path,
            "--output", output_dir
        ]

        # Map params to CLI args
        # interval
        if "interval" in params:
            cmd.extend(["--interval", str(params["interval"])])
        
        # format
        if "format" in params:
            cmd.extend(["--format", params["format"]])
            
        # resolution
        if "resolution" in params:
            cmd.extend(["--resolution", str(params["resolution"])])
            
        # camera-count
        if "camera_count" in params:
            cmd.extend(["--camera-count", str(params["camera_count"])])
            
        # quality
        if "quality" in params:
            cmd.extend(["--quality", str(params["quality"])])
            
        # layout
        if "layout" in params:
            cmd.extend(["--layout", params["layout"]])
            
        # AI options
        if params.get("ai_mask", False):
            cmd.append("--ai-mask")
        
        if params.get("ai_skip", False):
            cmd.append("--ai-skip")
            
        if params.get("adaptive", False):
            cmd.append("--adaptive")
            if "motion_threshold" in params:
                cmd.extend(["--motion-threshold", str(params["motion_threshold"])])

        if log_callback:
            # Use map(str, ...) to handle Path objects in the list
            log_callback(f"Command: {' '.join(map(str, cmd))}")

        # Run process
        # We use Popen to capture stdout/stderr for progress
        env = os.environ.copy()
        # Ensure we don't conflict with system python path if set
        env["PYTHONPATH"] = "" 
        
        # Ensure all arguments are strings for subprocess
        cmd_str = [str(arg) for arg in cmd]
        
        self.process = subprocess.Popen(
            cmd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            env=env,
            cwd=self.extractor_dir # Important for relative paths in script if any
        )

        for line in self.process.stdout:
            if check_cancel_callback and check_cancel_callback():
                if log_callback: log_callback("Processus arrêté par l'utilisateur.")
                self.stop()
                return False
            line = line.strip()
            if not line: continue
            
            if log_callback:
                log_callback(line)
            
            # Simple progress parsing if script outputs [XX%]
            # The script uses tqdm or logging. If tqdm, it outputs carriage returns or newlines.
            # "10%|...|"
            if "%" in line and progress_callback:
                try:
                    # Very naive parsing, depends on tqdm output format
                    # or custom logging [XX%]
                    if "[" in line and "%]" in line:
                         # [ 10%] ...
                         part = line.split("[")[1].split("%]")[0]
                         progress_callback(int(part.strip()))
                except:
                    pass

        return self.process.wait() == 0
