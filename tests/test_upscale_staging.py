"""Upscale staging must never let two sources share one staged file name."""
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.gui.widgets.upscale_widgets import _staged_names, run_upscale_job


def test_same_stem_sources_get_distinct_names():
    a, b = Path("a.jpg"), Path("a.png")
    names = _staged_names([a, b], "_m_x4", "png")
    assert len(set(names.values())) == 2


def test_unique_stems_keep_their_plain_name():
    names = _staged_names([Path("a.jpg"), Path("b.png")], "_m_x4", "png")
    assert names[Path("a.jpg")] == "a_m_x4.png"
    assert names[Path("b.png")] == "b_m_x4.png"


def test_run_upscale_job_stages_both_same_stem_images(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    Image.new("RGB", (4, 4), "red").save(src / "a.jpg")
    Image.new("RGB", (4, 4), "blue").save(src / "a.png")
    staged = []

    def fake_run(tmp_in, out, params, **kwargs):
        staged.extend(sorted(p.name for p in Path(tmp_in).iterdir()))
        kwargs["done_callback"](True)

    with patch("app.upscayl_manager.find_binary", return_value="/bin/x"), \
            patch("app.upscayl_manager.run_upscayl", side_effect=fake_run):
        ok, _ = run_upscale_job(
            str(src), str(tmp_path / "out"),
            {"model_id": "m", "scale": 4, "format": "png"}, lambda *_: None, lambda: False)
    assert ok is True
    assert len(staged) == 2
