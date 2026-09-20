"""Tests for app/core/superplat_engine.py — preconditions and the data server."""
from unittest.mock import MagicMock, patch

from app.core.i18n import tr
from app.core.superplat_engine import SuperSplatEngine


def _engine(tmp_path):
    engine = SuperSplatEngine()
    engine.get_supersplat_path = lambda: tmp_path / "supersplat"
    return engine


class TestStartPreconditions:
    """`npx serve dist` fails with a node-level message that names nothing."""

    def test_missing_engine_is_reported(self, tmp_path):
        ok, msg = _engine(tmp_path).start_supersplat()
        assert ok is False
        # Compared against tr(), not a French fragment: these messages are
        # translated now, and the active language depends on the environment.
        assert msg == tr("err_supersplat_not_found", "Moteur SuperSplat non trouvé")

    def test_unbuilt_engine_is_reported(self, tmp_path):
        (tmp_path / "supersplat").mkdir()
        ok, msg = _engine(tmp_path).start_supersplat()
        assert ok is False
        assert "dist" in msg

    def test_missing_npx_is_reported(self, tmp_path):
        (tmp_path / "supersplat" / "dist").mkdir(parents=True)
        with patch("app.core.superplat_engine.shutil.which", return_value=None):
            ok, msg = _engine(tmp_path).start_supersplat()
        assert ok is False
        assert "npx" in msg


class TestDataServer:
    def test_missing_directory_is_reported(self, tmp_path):
        ok, msg = _engine(tmp_path).start_data_server(str(tmp_path / "nope"))
        assert ok is False
        assert msg == tr("err_data_dir_missing", "Dossier de données introuvable")

    def test_httpd_is_bound_before_start_returns(self, tmp_path):
        """stop_data_server() used to race the worker thread assigning self.httpd.

        Binding in the calling thread closes the window where stop() saw None
        and returned, leaving a server running unreferenced.
        """
        engine = _engine(tmp_path)
        served = tmp_path / "data"
        served.mkdir()

        ok, _msg = engine.start_data_server(str(served), port=0)
        try:
            assert ok is True
            assert engine.httpd is not None
        finally:
            engine.stop_data_server()
        assert engine.httpd is None

    def test_bind_failure_is_returned_not_raised(self, tmp_path):
        engine = _engine(tmp_path)
        served = tmp_path / "data"
        served.mkdir()

        with patch("app.core.superplat_engine.socketserver.TCPServer.__init__",
                   side_effect=OSError("address in use")):
            ok, msg = engine.start_data_server(str(served), port=9)
        assert ok is False
        assert msg == tr("err_data_server_bind", "address in use")

    def test_cors_fallback_names_the_viewer_port(self, tmp_path):
        """The allowed origin must be the viewer's port, not the data server's.

        It was built from the data port, naming this server as the origin
        allowed to call it — never the origin that actually asks (audit I12).
        """
        engine = _engine(tmp_path)
        served = tmp_path / "data"
        served.mkdir()

        captured = {}

        class _Spy:
            def __init__(self, addr, handler):
                captured["handler"] = handler

            def serve_forever(self):
                pass

            def shutdown(self):
                pass

            def server_close(self):
                pass

        with patch("app.core.superplat_engine.socketserver.TCPServer", _Spy):
            ok, _ = engine.start_data_server(str(served), port=8000, viewer_port=3000)
            assert ok is True

            handler_cls = captured["handler"].func
            instance = MagicMock(spec=handler_cls)
            instance.headers = {}
            sent = []
            instance.send_header = lambda k, v: sent.append((k, v))
            with patch.object(handler_cls.__bases__[0], "end_headers", lambda self: None):
                handler_cls.end_headers(instance)

        origins = [v for k, v in sent if k == "Access-Control-Allow-Origin"]
        assert origins == ["http://localhost:3000"]
        engine.stop_data_server()
