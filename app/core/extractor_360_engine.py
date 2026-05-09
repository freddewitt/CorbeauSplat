import os
import subprocess
from pathlib import Path
from .base_engine import BaseEngine
from .i18n import tr
from app.scripts.setup_dependencies import install_extractor_360, get_venv_360_python, uninstall_extractor_360, resolve_project_root


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

    def run_extraction(self, input_path, output_dir, params, progress_callback=None, log_callback=None, status_callback=None, check_cancel_callback=None):
        """
        Runs the extraction CLI.
        params: dict of arguments mirroring CLI args
        """
        if status_callback: status_callback(tr("status_extracting_360", "Extraction vidéo 360°..."))
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
        # Isolate from the main app's PYTHONPATH to avoid package conflicts
        env.pop("PYTHONPATH", None)
        
        # Ensure all arguments are strings for subprocess
        cmd_str = [str(arg) for arg in cmd]

        # Use BaseEngine's Template Method for process execution
        def line_handler(line: str):
            if log_callback:
                log_callback(line)
            if "%" in line and progress_callback:
                try:
                    if "[" in line and "%]" in line:
                        part = line.split("[")[1].split("%]")[0]
                        progress_callback(int(part.strip()))
                except (ValueError, IndexError):
                    pass

        if status_callback:
            status_callback(tr("status_extracting_360", "Extraction vidéo 360°..."))

        returncode = self._execute_command(cmd_str, env=env, cwd=str(self.extractor_dir), line_callback=line_handler)

        if check_cancel_callback and check_cancel_callback():
            if log_callback:
                log_callback("Processus arrêté par l'utilisateur.")
            return False

        if status_callback:
            status_callback(tr("status_ready", "Traitement terminé !"))
        return returncode == 0
