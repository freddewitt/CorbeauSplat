"""Tests for app/core/upscale_engine.py — the adaptive tile logic and paths.

The module sat at 17% coverage; its tile sizing is pure arithmetic driven by
system memory, which is worth pinning because a wrong tile crashes upscayl-bin
with SIGBUS on unified-memory Apple Silicon.
"""
from unittest.mock import patch

import pytest

from app.core.upscale_engine import UpscaleEngine


@pytest.fixture
def engine():
    eng = UpscaleEngine()
    eng.logger_callback = lambda *_a, **_k: None
    return eng


def _with_memory(total_gb, percent=10.0):
    return patch("app.core.system.get_memory_info",
                 return_value={"total": int(total_gb * 1024 ** 3), "percent": percent})


class TestLoadModel:
    def test_returns_none_when_binary_missing(self, engine):
        with patch.object(engine, "_binary", return_value=None):
            assert engine.load_model() is None

    def test_model_id_is_passed_through_untouched(self, engine):
        """The old heuristic rewrote 'realesrgan-x4plus' at scale 2 into
        'realesrgan-2plus', a model that does not exist (audit I2)."""
        with patch.object(engine, "_binary", return_value="/bin/upscayl"), _with_memory(32):
            params = engine.load_model(model_id="realesrgan-x4plus", scale=2)
        assert params["model_id"] == "realesrgan-x4plus"
        assert params["scale"] == 2

    @pytest.mark.parametrize("total_gb,expected", [(4, 256), (12, 512), (32, 1024)])
    def test_tile_adapts_to_total_memory(self, engine, total_gb, expected):
        with patch.object(engine, "_binary", return_value="/bin/upscayl"), _with_memory(total_gb):
            assert engine.load_model(tile=0)["tile"] == expected

    def test_high_pressure_halves_the_tile(self, engine):
        with patch.object(engine, "_binary", return_value="/bin/upscayl"), _with_memory(32, percent=91.0):
            assert engine.load_model(tile=0)["tile"] == 512

    def test_tile_never_drops_below_128(self, engine):
        with patch.object(engine, "_binary", return_value="/bin/upscayl"), _with_memory(4, percent=95.0):
            assert engine.load_model(tile=0)["tile"] == 128

    def test_explicit_tile_is_not_recomputed(self, engine):
        with patch.object(engine, "_binary", return_value="/bin/upscayl"):
            assert engine.load_model(tile=384)["tile"] == 384

    def test_other_options_survive(self, engine):
        with patch.object(engine, "_binary", return_value="/bin/upscayl"):
            params = engine.load_model(tile=256, output_format="jpg", tta=True, compression=80)
        assert (params["output_format"], params["tta"], params["compression"]) == ("jpg", True, 80)


class TestUpscaleFolder:
    def test_no_model_is_refused(self, engine):
        ok, msg = engine.upscale_folder("/in", "/out", model_id="")
        assert ok is False
        assert "No model" in msg

    def test_custom_scale_overrides_scale(self, engine, tmp_path):
        """custom_scale exists so a caller can force a size the model is not named for."""
        captured = {}

        def fake_run(input_dir, output, params, **kwargs):
            captured.update(params)
            kwargs["done_callback"](True)

        with patch("app.upscayl_manager.run_upscayl", fake_run):
            engine.upscale_folder(str(tmp_path), str(tmp_path / "out"),
                                  model_id="realesrgan-x4plus", scale=4, custom_scale=2)
        assert captured["scale"] == 2


class TestUpscaleImage:
    def test_falsy_upsampler_is_refused(self, engine):
        assert engine.upscale_image("/in.png", "/out.png", None) is False

    def test_invalid_input_is_refused(self, engine):
        with patch.object(engine, "validate_path", return_value=None):
            assert engine.upscale_image("", "/out.png", {"model_id": "m"}) is False

    def test_single_file_is_staged_through_a_temp_folder(self, engine, tmp_path):
        """upscayl-bin works on folders, so one image is copied into a temp dir."""
        src = tmp_path / "in.png"
        src.write_bytes(b"x")
        out = tmp_path / "out" / "in.png"

        with patch.object(engine, "upscale_folder", return_value=(True, "ok")) as mock_folder:
            assert engine.upscale_image(str(src), str(out), {"model_id": "m"}) is True

        staged_dir = mock_folder.call_args.kwargs["input_dir"]
        assert staged_dir != str(tmp_path)
        assert mock_folder.call_args.kwargs["output_dir"] == str(out.parent)
