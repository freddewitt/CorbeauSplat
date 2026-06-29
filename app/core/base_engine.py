import logging
import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

from .system import get_device, resolve_project_root

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class IProcessRunner:
    """Interface abstraite pour l'exécution d'un processus systéme (DIP & Testabilité)"""
    def start(self, cmd: list, env: dict = None, **kwargs):
        raise NotImplementedError()

    def poll(self):
        raise NotImplementedError()

    def wait(self, timeout=None):
        raise NotImplementedError()

    def terminate(self):
        raise NotImplementedError()

    def stdout_iter(self) -> Iterator[str]:
        raise NotImplementedError()

    def get_returncode(self) -> int:
        raise NotImplementedError()

class SubprocessRunner(IProcessRunner):
    """Implémentation concrète de l'OS via subprocess"""
    def __init__(self):
        self._process = None

    def start(self, cmd: list, env: dict = None, **kwargs):
        base_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'text': True,
            'bufsize': 1,  # line-buffered: flush COLMAP/bundle-adjustment progress
                           # promptly so the long global-BA phase doesn't look frozen
        }
        base_kwargs.update(kwargs)

        # Sécurisation du process group pour permettre de kill l'arbre process
        if sys.platform != "win32" and 'preexec_fn' not in base_kwargs:
            base_kwargs['preexec_fn'] = os.setsid

        self._process = subprocess.Popen(cmd, env=env, **base_kwargs)
        return self._process

    def poll(self):
        if self._process: return self._process.poll()
        return None

    def wait(self, timeout=None):
        if self._process: return self._process.wait(timeout)
        return None

    def terminate(self):
        if not self._process: return
        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                self._process.wait(timeout=5)
            else:
                # On Windows a `cmd /c npx ...` wrapper spawns child node/colmap
                # processes that process.terminate() does NOT kill, leaving them
                # orphaned (e.g. holding the SuperSplat port). Kill the whole tree.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._process.wait(timeout=5)
        except (ProcessLookupError, PermissionError, OSError, subprocess.TimeoutExpired):
            try:
                self._process.kill()
                self._process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def stdout_iter(self) -> Iterator[str]:
        if getattr(self._process, 'stdout', None):
            for line in self._process.stdout:
                yield line

    def get_returncode(self) -> int:
        if self._process: return self._process.returncode
        return -1


class BaseEngine:
    """
    Base class for all engines to consolidate common logic.
    """
    def __init__(self, name, logger_callback=None, process_runner: IProcessRunner = None):
        self.name = name
        self.logger_callback = logger_callback
        self.device = get_device()
        self.project_root = resolve_project_root()
        self.stop_requested = False

        self.logger = logging.getLogger(self.name)

        # SOLID-DIP : Injection abstraite pour tests (mockable)
        self.runner = process_runner or SubprocessRunner()
        self.process = None # Retro-compatibilité temporaire

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)
        if self.logger_callback:
            self.logger_callback(message)

    def stop(self):
        self.stop_requested = True
        self.runner.terminate()
        self._kill_process(self.process) # Legacy cleanup

    def _execute_command(self, cmd: list, env: dict = None, line_callback=None, **kwargs) -> int:
        """
        GoF-Template Method : Exécution générique centralisée de processus
        Délègue à l'IProcessRunner injecté, gère la boucle standard et l'annulation.
        Retourne le returncode (0 si succès, -1 si annulé ou erreur).
        """
        if self.stop_requested: return -1

        self.log(f"Exec: {' '.join(map(str, cmd))}")
        try:
            self.runner.start(cmd, env=env, **kwargs)
            self.process = getattr(self.runner, '_process', None) # Legacy mapping

            for line in self.runner.stdout_iter():
                if self.stop_requested:
                    self.runner.terminate()
                    return -1

                stripped = line.strip()
                if stripped:
                    if line_callback:
                        line_callback(stripped)
                    else:
                        self.log(stripped)

            return self.runner.wait()
        except Exception as e:
            self.logger.error("Exception in _execute_command", exc_info=True)
            self.log(f"Exception: {e}", level=logging.ERROR)
            # Never leave the child running if streaming/parsing threw — otherwise a
            # COLMAP/Brush process would be orphaned (zombie holding the GPU/port).
            try:
                self.runner.terminate()
            except Exception:
                self.logger.debug("terminate() after exception failed", exc_info=True)
            return -1

    def _kill_process(self, process):
        """Terminate a subprocess gracefully, using process group kill on Unix."""
        # Maintenu pour la retro-compatibilité directe de certains Worker
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
        """Resolves and validates a user-supplied path.

        This is a desktop tool that operates on the user's own files, so any
        absolute location (including other drives, e.g. ``I:\\projects``) is
        allowed — the previous home/project containment broke legitimate output
        folders. We still reject ``..`` parent-traversal segments, which are the
        real escape vector for crafted/relative inputs.
        """
        if not path:
            return None
        try:
            raw = Path(path)
            if ".." in raw.parts:
                self.log(f"SECURITY WARNING: path traversal rejected: {path}")
                return None
            return raw.resolve()
        except (TypeError, ValueError, OSError) as e:
            self.log(f"ERROR: Invalid path attempt : {path} ({e})")
            return None

    def is_safe_path(self, path):
        """Checks if a path is within allowed boundaries and accessible"""
        p = self.validate_path(path)
        return p is not None and p.exists()

    def cleanup_temp_files(self, patterns):
        """Standardized cleanup for temp files matching given glob patterns"""
        import glob
        for pattern in patterns:
            for f in glob.glob(str(pattern)):
                try:
                    Path(f).unlink()
                except OSError:
                    pass
