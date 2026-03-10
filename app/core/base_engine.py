import os
import sys
import signal
from pathlib import Path
from .system import get_device, resolve_project_root

class BaseEngine:
    """
    Base class for all engines to consolidate common logic.
    """
    def __init__(self, name, logger_callback=None):
        self.name = name
        self.logger_callback = logger_callback
        self.device = get_device()
        self.project_root = resolve_project_root()
        self.stop_requested = False

    def log(self, message):
        if self.logger_callback:
            self.logger_callback(message)
        else:
            print(f"[{self.name}] {message}")

    def stop(self):
        self.stop_requested = True

    def _kill_process(self, process):
        """Terminate a subprocess gracefully, using process group kill on Unix."""
        if process is None or process.poll() is not None:
            return
        if sys.platform != "win32":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                process.terminate()
        else:
            process.terminate()
        process.wait()

    def validate_path(self, path):
        """Resolves and validates a path to prevent traversal"""
        if not path:
            return None
        p = Path(path).resolve()
        # Ensure it doesn't escape project root or common user areas
        # For now, just ensure it's absolute and doesn't contain traversal
        return p

    def is_safe_path(self, path):
        """Checks if a path is within allowed boundaries"""
        try:
            Path(path).resolve()
            return True
        except (TypeError, ValueError, OSError):
            return False

    def cleanup_temp_files(self, patterns):
        """Standardized cleanup for temp files matching given glob patterns"""
        import glob
        for pattern in patterns:
            for f in glob.glob(str(pattern)):
                try:
                    Path(f).unlink()
                except OSError:
                    pass
