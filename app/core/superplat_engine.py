import os
import subprocess
import sys
import threading
import http.server
import socketserver
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Tuple, Optional, Callable

from .base_engine import BaseEngine
from .system import resolve_project_root

class SuperSplatEngine(BaseEngine):
    """Engine to manage the SuperSplat viewer and its accompanying data server.

    The engine provides methods to start/stop the SuperSplat HTTP server (served via
    ``npx serve``) and a lightweight data server that serves PLY files with proper
    CORS headers. All operations are logged using the structured logger inherited
    from :class:`BaseEngine`.
    """

    def __init__(self, logger_callback: Optional[Callable] = None) -> None:
        """Create a new ``SuperSplatEngine`` instance.

        Parameters
        ----------
        logger_callback: Callable, optional
            Callback used by the base class to forward log messages to the UI.
        """
        super().__init__("SuperSplat", logger_callback)
        self.supersplat_process: Optional[subprocess.Popen] = None
        self.data_server_process: Optional[subprocess.Popen] = None
        self.data_server_thread: Optional[threading.Thread] = None
        self.httpd: Optional[socketserver.TCPServer] = None

    def get_supersplat_path(self) -> Path:
        """Return the absolute path to the bundled SuperSplat distribution."""
        return resolve_project_root() / "engines" / "supersplat"

    # ---------------------------------------------------------------------
    # SuperSplat viewer management
    # ---------------------------------------------------------------------
    def start_supersplat(self, port: int = 3000) -> Tuple[bool, str]:
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

        cmd = ["npx", "serve", "dist", "-p", str(port), "--no-clipboard"]
        try:
            self.runner.start(cmd, env=os.environ.copy(), cwd=str(splat_path))
            self.supersplat_process = getattr(self.runner, '_process', None)
            self.log(f"SuperSplat démarré sur http://localhost:{port}")
            return True, f"SuperSplat démarré sur http://localhost:{port}"
        except Exception as e:
            self.log(f"Erreur lors du démarrage de SuperSplat : {e}", level=logging.ERROR)
            return False, str(e)

    def stop_supersplat(self) -> None:
        """Terminate the SuperSplat viewer process if it is running."""
        if self.supersplat_process:
            self._kill_process(self.supersplat_process)
            self.supersplat_process = None
            self.log("SuperSplat arrêté")

    # ---------------------------------------------------------------------
    # Data server (CORS‑enabled) management
    # ---------------------------------------------------------------------
    def start_data_server(self, directory: str, port: int = 8000) -> Tuple[bool, str]:
        """Start a lightweight HTTP server that serves files from *directory*.

        The server binds only to ``127.0.0.1`` and adds a permissive CORS header so
        that the SuperSplat viewer can fetch local assets.
        """
        self.stop_data_server()

        dir_path = Path(directory).resolve()
        # Prevent path traversal – only allow directories inside the project root.
        project_root = resolve_project_root().resolve()
        if not str(dir_path).startswith(str(project_root)):
            return False, "Dossier de données hors du répertoire du projet"
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

        def run_server():  # pragma: no cover – runs in a background thread
            from functools import partial
            handler = partial(CORSRequestHandler, directory=str(dir_path))
            try:
                self.httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
                self.httpd.serve_forever()
            except Exception as e:
                self.log(f"Erreur Data Server: {e}", level=logging.ERROR)

        self.data_server_thread = threading.Thread(target=run_server, daemon=True)
        self.data_server_thread.start()
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
