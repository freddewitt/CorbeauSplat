import contextlib
import logging
import os
import select as _select
import signal
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .system import get_device, resolve_project_root


class IProcessRunner:
    """Abstract interface for running a system process (DIP & testability)"""
    def start(self, cmd: list, env: dict | None = None, **kwargs):
        raise NotImplementedError()

    def poll(self):
        raise NotImplementedError()

    def wait(self, timeout=None):
        raise NotImplementedError()

    def terminate(self):
        raise NotImplementedError()

    def stdout_iter(self) -> Iterator[str]:
        raise NotImplementedError()

    def readline(self, timeout: float | None = None) -> str | None:
        """Read a single line from stdout, with optional select-based timeout.

        Returns a line string (may be empty or end with newline), or None on timeout,
        or empty string on EOF.
        """
        raise NotImplementedError()

    def get_returncode(self) -> int:
        raise NotImplementedError()

class SubprocessRunner(IProcessRunner):
    """Concrete OS implementation through subprocess"""
    def __init__(self):
        self._process = None

    def start(self, cmd: list, env: dict | None = None, **kwargs):
        base_kwargs: dict[str, Any] = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.STDOUT,
            'text': True,
        }
        base_kwargs.update(kwargs)

        # New session group so terminate() can kill the whole process tree.
        # No os.nice(): on Apple Silicon a lowered priority steers COLMAP,
        # Brush and Sharp toward the E-cores and slows them down, while the
        # GUI is a separate process the macOS scheduler keeps responsive
        # on its own.
        if sys.platform != "win32":
            base_kwargs['start_new_session'] = True

        self._process = subprocess.Popen(cmd, env=env, **base_kwargs)
        return self._process

    def poll(self):
        if self._process:
            return self._process.poll()
        return None

    def wait(self, timeout=None):
        if self._process:
            return self._process.wait(timeout)
        return None

    def terminate(self):
        if not self._process:
            return
        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            else:
                self._process.terminate()
            self._process.wait(timeout=5)
        except (ProcessLookupError, PermissionError, OSError, subprocess.TimeoutExpired):
            self._process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                # unrecoverable zombie — process will be reaped by OS
                self._process.wait(timeout=2)

    def stdout_iter(self) -> Iterator[str]:
        if getattr(self._process, 'stdout', None):
            yield from self._process.stdout

    def readline(self, timeout: float | None = None) -> str | None:
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
        if self._process:
            return self._process.returncode
        return -1


class PtyProcessRunner(SubprocessRunner):
    """Runs the process on a pseudo-terminal instead of a pipe.

    Some tools only draw their progress when they believe a person is
    watching: Brush's indicatif bar checks ``isatty(stderr)`` and stays hidden
    on a pipe, which is why training used to report nothing. On a pty the bar
    is drawn, and redrawn in place with ``\\r``, so output is split on both
    ``\\r`` and ``\\n`` — each redraw becomes one "line" for the engine.

    The terminal is made wide so indicatif does not truncate the bar's text.
    """

    _COLUMNS = 240
    _READ_SIZE = 4096

    def __init__(self):
        super().__init__()
        self._master_fd: int | None = None
        self._pending: list[str] = []
        self._partial = ""
        self._decoder = None
        self._eof = False

    def start(self, cmd: list, env: dict | None = None, **kwargs):
        import codecs
        import fcntl
        import pty
        import struct
        import termios

        master_fd, slave_fd = pty.openpty()
        with contextlib.suppress(OSError):
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", 50, self._COLUMNS, 0, 0))
        try:
            self._process = subprocess.Popen(
                cmd, env=env, stdin=subprocess.DEVNULL,
                stdout=slave_fd, stderr=slave_fd,
                start_new_session=True, **kwargs,
            )
        finally:
            # The child holds its own copy; keeping ours would stop EOF from
            # ever reaching the master once the child exits.
            os.close(slave_fd)
        self._master_fd = master_fd
        self._pending, self._partial, self._eof = [], "", False
        # Incremental: a multi-byte bar glyph (█) can straddle two reads.
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        return self._process

    def stdout_iter(self) -> Iterator[str]:
        while True:
            line = self.readline()
            if not line:
                return
            yield line

    def readline(self, timeout: float | None = None) -> str | None:
        """Next ``\\r``/``\\n``-delimited segment, None on timeout, "" on EOF."""
        while not self._pending:
            if self._eof or self._master_fd is None:
                return self._flush_partial()
            if timeout is not None:
                ready, _, _ = _select.select([self._master_fd], [], [], timeout)
                if not ready:
                    return None
            try:
                chunk = os.read(self._master_fd, self._READ_SIZE)
            except OSError:
                # macOS raises EIO on the master once the child side is gone.
                chunk = b""
            if not chunk:
                self._eof = True
                self._close_master()
                continue
            self._split(self._decoder.decode(chunk))
        return self._pending.pop(0)

    def _split(self, text: str) -> None:
        from .live_progress import strip_ansi

        text = self._partial + text
        parts = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self._partial = parts.pop()
        # Terminal codes (colors, "erase line" before a redraw) would otherwise
        # land in the log as garbage. Empty segments (a bare "\r" before a
        # redraw) are dropped too, since "" is the EOF marker for the caller.
        parts = (strip_ansi(p) for p in parts)
        self._pending.extend(p + "\n" for p in parts if p.strip())

    def _flush_partial(self) -> str:
        rest, self._partial = self._partial, ""
        return rest + "\n" if rest.strip() else ""

    def _close_master(self) -> None:
        if self._master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._master_fd)
            self._master_fd = None

    def wait(self, timeout=None):
        try:
            return super().wait(timeout)
        finally:
            if self._process and self._process.poll() is not None:
                self._close_master()


class BaseEngine:
    """
    Base class for all engines to consolidate common logic.
    """
    _THERMAL_CHECK_INTERVAL = 30  # seconds between thermal state checks

    def __init__(self, name, logger_callback=None, process_runner: IProcessRunner | None = None, thermal_throttling: bool = False):
        self.name = name
        self.logger_callback = logger_callback
        self.device = get_device()
        self.project_root = resolve_project_root()
        self.stop_requested = False
        self._last_thermal_check = 0.0
        self.thermal_throttling = thermal_throttling
        # Must exist before _check_initial_thermal(): self.log() uses it, and the
        # AttributeError was swallowed, so the startup warning never showed.
        self.logger = logging.getLogger(self.name)

        # If thermal state is already serious at init time, warn immediately
        self._check_initial_thermal()

        # SOLID-DIP: abstract injection for tests (mockable)
        self.runner = process_runner or SubprocessRunner()
        self.process = None # Temporary backward compatibility

    def _check_initial_thermal(self):
        """Log a warning if thermal state is already degraded at startup."""
        if not self.thermal_throttling:
            return
        try:
            from .system import get_thermal_state
            state = get_thermal_state()
            if state in ("serious", "critical"):
                self.log(
                    f"⚠️  État thermique {state.upper()} au démarrage — "
                    f"les performances seront réduites.",
                    level=logging.WARNING
                )
        except Exception as e:
            self.logger.debug("Initial thermal check failed: %s", e)

    def _check_thermal_abort(self) -> bool:
        """Periodic thermal watchdog — checks state and returns True to abort.

        Called from _execute_command every _THERMAL_CHECK_INTERVAL seconds.
        If thermal state is critical, sets stop_requested and returns True.
        """
        if not self.thermal_throttling:
            return False
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
        except Exception as e:
            self.logger.debug("Thermal check failed: %s", e)
        return False

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)
        if self.logger_callback:
            self.logger_callback(message)

    def stop(self):
        self.stop_requested = True
        self.runner.terminate()
        self._kill_process(self.process) # Legacy cleanup

    def _execute_command(self, cmd: list, env: dict | None = None, line_callback=None,
                         timeout: float = 3600, inactivity_timeout: float = 0, **kwargs) -> int:
        """
        GoF Template Method: centralised generic process execution.
        Delegates to the injected IProcessRunner, handles the standard loop and
        cancellation. Uses ``readline`` with a select-based timeout to avoid
        blocking forever when the external process freezes without closing
        stdout. Returns the returncode (0 on success, -1 when cancelled or on
        error).

        Parameters
        ----------
        timeout : float
            Wall-clock timeout in seconds (safety net).  Default 3600.
        inactivity_timeout : float
            Max seconds without any stdout line before the process is considered
            frozen and terminated.  0 (default) disables inactivity detection.

        Includes a thermal watchdog that interrupts the task when the Apple
        Silicon thermal state turns "critical".
        """
        import time as _time

        if self.stop_requested:
            return -1

        # Full line (absolute user paths) only at DEBUG; INFO gets basenames.
        self.logger.debug("Exec: %s", " ".join(map(str, cmd)))
        self.log("Exec: " + self._redact_cmd(cmd))
        try:
            self.runner.start(cmd, env=env, **kwargs)
            self.process = getattr(self.runner, '_process', None) # Legacy mapping

            read_timeout = min(self._THERMAL_CHECK_INTERVAL, 10.0)  # check every N seconds
            start_time = _time.monotonic()
            last_output_time = start_time  # track last stdout activity for inactivity timeout
            while True:
                now = _time.monotonic()
                elapsed = now - start_time
                remaining = timeout - elapsed

                if self._deadline_exceeded(remaining, timeout, now - last_output_time,
                                           inactivity_timeout):
                    return -1
                # Checked every iteration, including select timeouts, so a
                # silent process still honours cancellation and the watchdog.
                if self.stop_requested:
                    self.runner.terminate()
                    return -1
                if self._check_thermal_abort():
                    return -1

                line = self.runner.readline(timeout=min(remaining, read_timeout))

                # None = select timeout (no data available yet), keep looping
                if line is None:
                    continue
                if line == "":
                    break  # EOF
                last_output_time = _time.monotonic()  # reset inactivity timer on actual output
                self._dispatch_line(line, line_callback)

            return self.runner.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.log(f"Timeout after {timeout}s — forcing termination", level=logging.WARNING)
            self.runner.terminate()
            return -1
        except Exception as e:
            self.logger.error("Exception in _execute_command", exc_info=True)
            self.log(f"Exception: {e}", level=logging.ERROR)
            return -1

    def _dispatch_line(self, line: str, line_callback=None) -> None:
        """Hand one non-empty stdout line to the callback, or log it."""
        stripped = line.strip()
        if not stripped:
            return
        if line_callback:
            line_callback(stripped)
        else:
            self.log(stripped)

    @staticmethod
    def _redact_cmd(cmd: list) -> str:
        """Command line with absolute paths reduced to their basename."""
        parts = []
        for arg in map(str, cmd):
            if os.sep in arg and not arg.startswith("-"):
                arg = os.path.basename(arg.rstrip(os.sep)) or arg
            parts.append(arg)
        return " ".join(parts)

    def _deadline_exceeded(self, remaining: float, timeout: float, idle: float,
                           inactivity_timeout: float) -> bool:
        """Terminate the process and return True when a wall-clock or
        inactivity timeout has been hit."""
        # Wall-clock timeout — safety net for runaway processes
        if remaining <= 0:
            self.log(f"Timeout after {timeout}s (wall-clock) — forcing termination", level=logging.WARNING)
            self.runner.terminate()
            return True
        # Inactivity timeout — detects frozen/blocked processes
        if inactivity_timeout > 0 and idle >= inactivity_timeout:
            self.log(
                f"Inactivity timeout after {idle:.0f}s "
                f"(no stdout for {inactivity_timeout}s) — forcing termination",
                level=logging.WARNING
            )
            self.runner.terminate()
            return True
        return False

    def _kill_process(self, process):
        """Terminate a subprocess gracefully, using process group kill on Unix."""
        # Kept for the direct backward compatibility of some Workers
        if process is None or process.poll() is not None:
            return
        if sys.platform != "win32":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                process.terminate()
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # SIGTERM ignored: escalate rather than block the caller forever.
            process.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)

    def validate_path(self, path):
        """Resolves a path and returns it. No containment checks."""
        if not path:
            return None
        try:
            return Path(path).resolve()
        except (TypeError, ValueError, OSError) as e:
            self.log(f"Path resolution failed: {path} ({e})")
            return None

    def path_exists(self, path):
        """Resolve `path` and report whether it exists on disk.

        Renamed from `is_safe_path()`, which promised a containment check it
        never performed: callers reading the old name could believe they were
        filtering directory traversal while only existence was tested. This
        app deliberately has no containment to enforce — the user picks input
        and output folders anywhere (Desktop, Documents, external volumes) —
        so the honest contract is the one stated here. Deletion is the only
        operation that needs a guard; see `ColmapEngine.delete_project_content`.
        """
        p = self.validate_path(path)
        return p is not None and p.exists()

    def cleanup_temp_files(self, patterns):
        """Standardized cleanup for temp files matching given glob patterns"""
        import glob
        for pattern in patterns:
            for f in glob.glob(str(pattern)):
                with contextlib.suppress(OSError):
                    Path(f).unlink()


def validate_path_standalone(path):
    """Resolve a path without containment checks.

    The former `project_root` parameter was never read by the body; it is
    dropped rather than kept as a decorative argument that suggests a
    confinement this function does not perform. Ruff would not have caught it,
    since the ARG rules are disabled for this codebase.
    """
    if not path:
        return None
    try:
        return Path(path).resolve()
    except (TypeError, ValueError, OSError):
        return None
