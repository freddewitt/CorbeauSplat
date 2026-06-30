import http.server
import logging
import os
import socketserver
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .base_engine import BaseEngine
from .system import resolve_project_root


class SuperSplatEngine(BaseEngine):
    """Engine to manage the SuperSplat viewer and its accompanying data server.

    The engine provides methods to start/stop the SuperSplat HTTP server (served via
    ``npx serve``) and a lightweight data server that serves PLY files with proper
    CORS headers. All operations are logged using the structured logger inherited
    from :class:`BaseEngine`.
    """

    def __init__(self, logger_callback: Callable | None = None) -> None:
        """Create a new ``SuperSplatEngine`` instance.

        Parameters
        ----------
        logger_callback: Callable, optional
            Callback used by the base class to forward log messages to the UI.
        """
        super().__init__("SuperSplat", logger_callback)
        self.data_server_process: subprocess.Popen | None = None
        self.data_server_thread: threading.Thread | None = None
        self.httpd: socketserver.TCPServer | None = None

    def get_supersplat_path(self) -> Path:
        """Return the absolute path to the bundled SuperSplat distribution."""
        return resolve_project_root() / "engines" / "supersplat"

    # ---------------------------------------------------------------------
    # SuperSplat viewer management
    # ---------------------------------------------------------------------
    def start_supersplat(self, port: int = 3000) -> tuple[bool, str]:
        """Launch the SuperSplat viewer using ``npx serve``.

        Parameters
        ----------
        port: int, default 3000
            Port on which the viewer will be reachable.

        Returns
        -------
        (bool, str)
            ``True`` and a success message on success, otherwise ``False`` and the
            error description.
        """
        splat_path = self.get_supersplat_path()
        if not splat_path.exists():
            return False, "Moteur SuperSplat non trouvé"

        # Ensure any previous instance is stopped before starting a new one.
        self.stop_supersplat()

        # On Windows npx is a .cmd shim; route through cmd.exe so it is launchable.
        npx = ["cmd", "/c", "npx"] if os.name == "nt" else ["npx"]
        cmd = [*npx, "serve", "dist", "-p", str(port), "--no-clipboard"]
        try:
            self.runner.start(cmd, env=os.environ.copy(), cwd=str(splat_path))

            def _consume_stdout():
                for line in self.runner.stdout_iter():
                    stripped = line.strip()
                    if stripped:
                        self.log(stripped)

            threading.Thread(target=_consume_stdout, daemon=True).start()
            self.log(f"SuperSplat démarré sur http://localhost:{port}")
            return True, f"SuperSplat démarré sur http://localhost:{port}"
        except Exception as e:
            self.log(f"Erreur lors du démarrage de SuperSplat : {e}", level=logging.ERROR)
            return False, str(e)

    def stop_supersplat(self) -> None:
        """Terminate the SuperSplat viewer process if it is running."""
        self.runner.terminate()
        self.log("SuperSplat arrêté")

    # ---------------------------------------------------------------------
    # Data server (CORS‑enabled) management
    # ---------------------------------------------------------------------
    def start_data_server(self, directory: str, port: int = 8000) -> tuple[bool, str]:
        """Start a lightweight HTTP server that serves files from *directory*.

        The server binds only to ``127.0.0.1`` and adds a permissive CORS header so
        that the SuperSplat viewer can fetch local assets.
        """
        self.stop_data_server()

        dir_path = Path(directory).expanduser().resolve()
        if not dir_path.is_dir():
            return False, "Dossier de données introuvable"

        allowed_origin = f"http://localhost:{port}"

        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            """Simple request handler that injects a safe ``Access-Control-Allow-Origin`` header."""

            def end_headers(self):  # pragma: no cover – exercised via runtime
                origin = self.headers.get('Origin')
                safe = bool(origin) and urlparse(origin).hostname in ('localhost', '127.0.0.1')
                self.send_header('Access-Control-Allow-Origin', origin if safe else allowed_origin)
                super().end_headers()

            def log_message(self, format, *args):  # Suppress noisy default logging
                return

        class _ReuseAddrTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        bind_event = threading.Event()
        bind_error: dict = {"e": None}

        def run_server():  # pragma: no cover – runs in a background thread
            from functools import partial
            handler = partial(CORSRequestHandler, directory=str(dir_path))
            try:
                self.httpd = _ReuseAddrTCPServer(("127.0.0.1", port), handler)
            except Exception as e:
                # Bind failed (port busy, permission). Report it to the caller
                # instead of claiming success on a server that never started.
                bind_error["e"] = e
                self.log(f"Erreur Data Server: {e}", level=logging.ERROR)
                bind_event.set()
                return
            bind_event.set()
            try:
                self.httpd.serve_forever()
            except Exception as e:
                self.log(f"Erreur Data Server: {e}", level=logging.ERROR)

        self.data_server_thread = threading.Thread(target=run_server, daemon=True)
        self.data_server_thread.start()
        # Wait for the bind attempt so we never report success on a dead server.
        if not bind_event.wait(timeout=3.0):
            return False, "Délai de démarrage du serveur de données dépassé"
        if bind_error["e"] is not None:
            return False, (f"Le serveur de données n'a pas pu démarrer "
                           f"(port {port} occupé ?) : {bind_error['e']}")
        self.log(f"Serveur de données démarré sur http://localhost:{port}")
        return True, f"Serveur de données démarré sur http://localhost:{port}"

    def stop_data_server(self) -> None:
        """Shut down the data server and clean up its thread."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.log("Data server arrêté")
        if self.data_server_thread:
            self.data_server_thread.join(timeout=1)
            self.data_server_thread = None

    def stop_all(self) -> None:
        """Convenience method to stop both the viewer and the data server."""
        self.stop_supersplat()
        self.stop_data_server()
