import os
import sys
import signal
import select as _select
import subprocess
import logging
from pathlib import Path
from typing import Iterator, Optional
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
        
    def readline(self, timeout: float = None) -> Optional[str]:
        """Read a single line from stdout, with optional select-based timeout.
        
        Returns a line string (may be empty or end with newline), or None on timeout,
        or empty string on EOF.
        """
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
        }
        base_kwargs.update(kwargs)
        
        # Sécurisation du process group + nice value pour tâches compute
        # os.nice(10) sur macOS donne une priorité "background" au sous-processus :
        #   - Le scheduler préfère les E-cores aux P-cores
        #   - Le throttling thermique est plus agressif
        #   - L'UI reste réactive même pendant COLMAP/Brush/Sharp
        if sys.platform != "win32":
            def _preexec_with_nice():
                """Setup child process: new session group + background priority."""
                try:
                    os.setsid()
                    # nice=10 → background priority (E-core preference on AS)
                    os.nice(10)
                except OSError:
                    pass  # non-critical, continue

            base_kwargs['preexec_fn'] = _preexec_with_nice
            
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
            else:
                self._process.terminate()
            self._process.wait(timeout=5)
        except (ProcessLookupError, PermissionError, OSError, subprocess.TimeoutExpired):
            self._process.kill()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass  # unrecoverable zombie — process will be reaped by OS
            
    def stdout_iter(self) -> Iterator[str]:
        if getattr(self._process, 'stdout', None):
            for line in self._process.stdout:
                yield line
                
    def readline(self, timeout: float = None) -> Optional[str]:
        """Read a single line using select for non-blocking timeout support."""
        if not self._process or not self._process.stdout:
            return ""
        fd = self._process.stdout.fileno()
        if timeout is not None:
            ready, _, _ = _select.select([fd], [], [], timeout)
            if not ready:
                return None  # timeout — no data available
        return self._process.stdout.readline()
                
    def get_returncode(self) -> int:
        if self._process: return self._process.returncode
        return -1


class BaseEngine:
    """
    Base class for all engines to consolidate common logic.
    """
    _THERMAL_CHECK_INTERVAL = 30  # seconds between thermal state checks

    def __init__(self, name, logger_callback=None, process_runner: IProcessRunner = None):
        self.name = name
        self.logger_callback = logger_callback
        self.device = get_device()
        self.project_root = resolve_project_root()
        self.stop_requested = False
        self._last_thermal_check = 0.0

        # If thermal state is already serious at init time, warn immediately
        self._check_initial_thermal()

        self.logger = logging.getLogger(self.name)
        
        # SOLID-DIP : Injection abstraite pour tests (mockable)
        self.runner = process_runner or SubprocessRunner()
        self.process = None # Retro-compatibilité temporaire

    def _check_initial_thermal(self):
        """Log a warning if thermal state is already degraded at startup."""
        try:
            from .system import get_thermal_state
            state = get_thermal_state()
            if state in ("serious", "critical"):
                self.log(
                    f"⚠️  État thermique {state.upper()} au démarrage — "
                    f"les performances seront réduites.",
                    level=logging.WARNING
                )
        except Exception:
            pass

    def _check_thermal_abort(self) -> bool:
        """Periodic thermal watchdog — checks state and returns True to abort.

        Called from _execute_command every _THERMAL_CHECK_INTERVAL seconds.
        If thermal state is critical, sets stop_requested and returns True.
        """
        import time
        now = time.monotonic()
        if now - self._last_thermal_check < self._THERMAL_CHECK_INTERVAL:
            return False
        self._last_thermal_check = now

        try:
            from .system import get_thermal_state
            state = get_thermal_state()
            if state == "critical":
                self.log(
                    "🔥 État thermique CRITIQUE — arrêt de la tâche en cours. "
                    "Laissez l'ordinateur refroidir avant de relancer.",
                    level=logging.WARNING
                )
                self.stop_requested = True
                self.runner.terminate()
                return True
            elif state in ("serious", "fair"):
                self.log(
                    f"🌡️  État thermique: {state.upper()} — "
                    f"sous-processus en cours, attendez le refroidissement.",
                    level=logging.WARNING
                )
        except Exception:
            pass
        return False

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)
        if self.logger_callback:
            self.logger_callback(message)

    def stop(self):
        self.stop_requested = True
        self.runner.terminate()
        self._kill_process(self.process) # Legacy cleanup

    def _execute_command(self, cmd: list, env: dict = None, line_callback=None,
                         timeout: float = 3600, **kwargs) -> int:
        """
        GoF-Template Method : Exécution générique centralisée de processus
        Délègue à l'IProcessRunner injecté, gère la boucle standard et l'annulation.
        Utilise ``readline`` avec timeout select-based pour éviter le blocage
        indéfini si le processus externe gèle sans fermer stdout.
        Retourne le returncode (0 si succès, -1 si annulé ou erreur).
        
        Inclut un watchdog thermique qui interrompt la tâche si l'état
        thermique Apple Silicon passe à "critical".
        """
        import time as _time
        
        if self.stop_requested: return -1
        
        self.log(f"Exec: {' '.join(map(str, cmd))}")
        try:
            self.runner.start(cmd, env=env, **kwargs)
            self.process = getattr(self.runner, '_process', None) # Legacy mapping
            
            read_timeout = min(self._THERMAL_CHECK_INTERVAL, 10.0)  # check every N seconds
            start_time = _time.monotonic()
            while True:
                # Global timeout — prevents indefinite blocking if the external binary
                # freezes without closing stdout.
                elapsed = _time.monotonic() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    self.log(f"Timeout after {timeout}s (frozen stdout) — forcing termination", level=logging.WARNING)
                    self.runner.terminate()
                    return -1
                
                line = self.runner.readline(timeout=min(remaining, read_timeout))
                
                # None = select timeout (no data available yet), keep looping
                if line is None:
                    pass  # will loop back and re-check elapsed / stop_requested / thermal
                elif line == "":
                    break  # EOF
                else:
                    if self.stop_requested:
                        self.runner.terminate()
                        return -1
                    
                    # Thermal watchdog every N seconds
                    if self._check_thermal_abort():
                        return -1
                    
                    stripped = line.strip()
                    if stripped:
                        if line_callback:
                            line_callback(stripped)
                        else:
                            self.log(stripped)
                        
            return self.runner.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.log(f"Timeout after {timeout}s — forcing termination", level=logging.WARNING)
            self.runner.terminate()
            return -1
        except Exception as e:
            self.logger.error("Exception in _execute_command", exc_info=True)
            self.log(f"Exception: {e}", level=logging.ERROR)
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
        """Resolves a path and returns it. No containment checks."""
        if not path:
            return None
        try:
            return Path(path).resolve()
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


def validate_path_standalone(path, project_root=None):
    """Resolve a path without containment checks."""
    if not path:
        return None
    try:
        return Path(path).resolve()
    except (TypeError, ValueError, OSError):
        return None
