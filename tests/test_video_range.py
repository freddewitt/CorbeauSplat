"""In/out range selection on a single video, from the probe to the ffmpeg call.

The GUI half runs against a real Qt in a subprocess (the suite's PySide6 mock
is process-global); the engine half runs in-process, since nothing there needs
Qt. The extraction is exercised against a real ffmpeg on a generated clip: the
whole point of the feature is that fewer frames come out, and only a real run
proves that.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.engine import ColmapEngine
from app.core.params import ColmapParams

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FFMPEG = shutil.which("ffmpeg")


@pytest.fixture(scope="module")
def clip():
    """A 12-second test pattern, the shortest thing that makes a range visible."""
    if not FFMPEG:
        pytest.skip("ffmpeg not available")
    tmp = Path(tempfile.mkdtemp(prefix="corbeau_clip_"))
    path = tmp / "sample.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "lavfi", "-i", "testsrc=duration=12:size=320x240:rate=25",
         "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, timeout=120,
    )
    if not path.exists():
        pytest.skip("could not generate the test clip")
    yield path
    shutil.rmtree(tmp, ignore_errors=True)


# ── media helpers ────────────────────────────────────────────────────────────

class TestMediaHelpers:
    def test_duration_is_probed(self, clip):
        from app.core.media import probe_video_duration
        assert probe_video_duration(clip) == pytest.approx(12.0, abs=0.2)

    def test_unreadable_path_returns_none(self, tmp_path):
        from app.core.media import probe_video_duration
        assert probe_video_duration(tmp_path / "nope.mp4") is None

    def test_preview_frame_is_written(self, clip, tmp_path):
        from app.core.media import extract_preview_frame
        dest = tmp_path / "f.jpg"
        assert extract_preview_frame(clip, 6.0, dest) is True
        assert dest.stat().st_size > 0

    @pytest.mark.parametrize("seconds,expected", [
        (0.0, "00:00.0"), (6.0, "00:06.0"), (75.4, "01:15.4"), (3725.2, "1:02:05.2"),
    ])
    def test_timecode_formatting(self, seconds, expected):
        from app.core.media import format_timecode
        assert format_timecode(seconds) == expected


class TestTimecodeParsing:
    """Typed entry: the inverse of format_timecode, so a shown value pastes back."""

    @pytest.mark.parametrize("text,expected", [
        ("90", 90.0), ("1:30", 90.0), ("00:06.0", 6.0),
        ("1:02:05.2", 3725.2), ("3,5", 3.5), ("  7  ", 7.0),
    ])
    def test_accepted_forms(self, text, expected):
        from app.core.media import parse_timecode
        assert parse_timecode(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["", "abc", "1:70", "99:99:99", None, "1:2:3:4"])
    def test_rejected_forms_return_none(self, text):
        """None, not an exception: the caller is an editable field, where a
        half-typed value is normal."""
        from app.core.media import parse_timecode
        assert parse_timecode(text) is None

    @pytest.mark.parametrize("seconds", [0.0, 6.0, 75.4, 3725.2])
    def test_round_trip_through_formatting(self, seconds):
        from app.core.media import format_timecode, parse_timecode
        assert parse_timecode(format_timecode(seconds)) == pytest.approx(seconds, abs=0.05)


class TestPreferredContainers:
    @pytest.mark.parametrize("name", ["clip.mp4", "clip.MOV", "clip.mov"])
    def test_mp4_and_mov_are_preferred(self, name):
        from app.core.media import is_preferred_video
        assert is_preferred_video(name) is True

    @pytest.mark.parametrize("name", ["clip.mts", "clip.insv", "clip.mxf", "clip.avi"])
    def test_other_containers_are_flagged(self, name):
        """Still supported — they just seek less precisely, so the dialog warns."""
        from app.core.media import is_preferred_video
        assert is_preferred_video(name) is False


# ── engine: the range must reach ffmpeg, and reduce the output ───────────────

def _command_for(trim_start, trim_end, clip, out_dir):
    params = ColmapParams(video_trim_start=trim_start, video_trim_end=trim_end)
    engine = ColmapEngine(params, str(clip), str(out_dir), "video", 5,
                          logger_callback=lambda _m: None)
    with patch.object(ColmapEngine, "_execute_command", return_value=0) as run:
        engine.extract_frames_from_video(str(clip), out_dir)
    return run.call_args[0][0]


class TestTrimReachesFfmpeg:
    def test_no_trim_leaves_the_command_untouched(self, clip, tmp_path):
        cmd = _command_for(None, None, clip, tmp_path)
        assert "-ss" not in cmd and "-t" not in cmd

    def test_range_becomes_seek_and_duration(self, clip, tmp_path):
        """`-t` carries a duration, not an end timestamp.

        After a pre-input `-ss`, ffmpeg counts `-to` from the seek point, so
        passing the end timestamp there would silently cut the wrong span.
        """
        cmd = _command_for(3.0, 9.0, clip, tmp_path)
        assert cmd[cmd.index("-ss") + 1] == "3.000"
        assert cmd[cmd.index("-t") + 1] == "6.000"
        # seek before the input, duration after it
        assert cmd.index("-ss") < cmd.index("-i") < cmd.index("-t")

    def test_backwards_range_is_ignored(self, clip, tmp_path):
        """ffmpeg accepts a non-positive -t and writes nothing, which reads as
        a broken extraction rather than a bad setting."""
        cmd = _command_for(9.0, 3.0, clip, tmp_path)
        assert "-ss" not in cmd and "-t" not in cmd

    def test_start_only_seeks_without_bounding(self, clip, tmp_path):
        cmd = _command_for(4.0, None, clip, tmp_path)
        assert cmd[cmd.index("-ss") + 1] == "4.000"
        assert "-t" not in cmd


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not available")
class TestRealExtraction:
    def _extract(self, clip, out_dir, trim_start, trim_end):
        params = ColmapParams(video_trim_start=trim_start, video_trim_end=trim_end)
        engine = ColmapEngine(params, str(clip), str(out_dir.parent), "video", 5,
                              logger_callback=lambda _m: None)
        engine.extract_frames_from_video(str(clip), out_dir)
        return len(list(out_dir.glob("*.jpg")))

    def test_whole_video_yields_every_frame(self, clip, tmp_path):
        assert self._extract(clip, tmp_path / "all", None, None) == pytest.approx(60, abs=2)

    def test_range_yields_only_its_own_frames(self, clip, tmp_path):
        """The feature's actual promise: a 6-second window at 5 fps is 30 images."""
        assert self._extract(clip, tmp_path / "cut", 3.0, 9.0) == pytest.approx(30, abs=2)


# ── panel bridge ─────────────────────────────────────────────────────────────

class TestSourceBridge:
    def test_trim_is_carried_onto_params(self):
        from app.gui.panels.reconstruction_logic import apply_source_settings
        params = apply_source_settings(
            ColmapParams(), {"video_trim": {"start": 2.5, "end": 7.5}}
        )
        assert (params.video_trim_start, params.video_trim_end) == (2.5, 7.5)

    @pytest.mark.parametrize("state", [{}, {"video_trim": None}, {"video_trim": "nonsense"}])
    def test_absent_or_malformed_trim_means_whole_video(self, state):
        """Configurations saved before the feature existed must still work."""
        from app.gui.panels.reconstruction_logic import apply_source_settings
        params = apply_source_settings(ColmapParams(), state)
        assert params.video_trim_start is None and params.video_trim_end is None


# ── GUI: button state and dialog, under a real Qt ────────────────────────────

_GUI_SCRIPT = '''
import json, pathlib, warnings
warnings.simplefilter("ignore")
from PySide6.QtWidgets import QApplication
app = QApplication([])
from app.core.run_state import RunState
from app.gui.panels.source_panel import SourcePanel
from app.gui.widgets.video_range_dialog import VideoRangeDialog

clip = pathlib.Path(CLIP)
folder = clip.parent / "many"
folder.mkdir(exist_ok=True)
for name in ("a.mp4", "b.mp4"):
    if not (folder / name).exists():
        (folder / name).write_bytes(clip.read_bytes())

results = {}
panel = SourcePanel(RunState())
for label, path in (("empty", ""), ("single_video", str(clip)),
                    ("folder_of_videos", str(folder))):
    panel.input_path.setText(path)
    panel._evaluate_source_type()
    results[label] = panel.btn_video_range.isEnabled()

dialog = VideoRangeDialog(clip)
results["duration"] = dialog.duration
dialog.slider.setValue(250); dialog._set_in()
dialog.slider.setValue(750); dialog._set_out()
dialog._accept()
results["selected"] = dialog.selected_range

whole = VideoRangeDialog(clip); whole._reset(); whole._accept()
results["whole_video_selection"] = whole.selected_range

backwards = VideoRangeDialog(clip)
backwards.slider.setValue(750); backwards._set_in()
backwards.slider.setValue(250); backwards._set_out()
results["backwards_start"] = backwards.start_s

panel.input_path.setText(str(clip))
panel._evaluate_source_type()
panel._video_trim = {"start": 3.0, "end": 9.0}
panel._trim_source = str(clip)
results["state_roundtrip"] = panel.get_state()["video_trim"]

restored = SourcePanel(RunState())
restored.set_state(panel.get_state())
results["restored"] = restored.get_state()["video_trim"]

typed = VideoRangeDialog(clip)
results["fields_start"] = [typed.edit_in.text(), typed.edit_out.text()]
typed.edit_in.setText("00:03.0"); typed._apply_typed_in()
typed.edit_out.setText("9"); typed._apply_typed_out()
typed._accept()
results["typed_range"] = typed.selected_range

bad = VideoRangeDialog(clip)
bad.edit_in.setText("pas un timecode"); bad._apply_typed_in()
results["typed_invalid_start"] = bad.start_s
results["typed_invalid_field"] = bad.edit_in.text()

order = VideoRangeDialog(clip)
order.edit_in.setText("11"); order._apply_typed_in()
order.edit_out.setText("2"); order._apply_typed_out()
results["typed_out_before_in"] = [order.start_s, order.end_s]

over = VideoRangeDialog(clip)
over.edit_out.setText("999"); over._apply_typed_out()
results["typed_beyond_duration"] = over.end_s

mts = clip.parent / "hint.mts"
if not mts.exists():
    mts.write_bytes(clip.read_bytes())
hinted = VideoRangeDialog(mts)
results["hint_other"] = bool(hinted.lbl_hint.text())
plain = VideoRangeDialog(clip)
results["hint_preferred"] = bool(plain.lbl_hint.text())

print("RESULTS=" + json.dumps(results))
'''


@pytest.fixture(scope="module")
def gui(clip):
    script = f"CLIP = {str(clip)!r}\n" + _GUI_SCRIPT
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=180, cwd=str(PROJECT_ROOT),
        env={"QT_QPA_PLATFORM": "offscreen", "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": str(Path.home()), "PYTHONPATH": str(PROJECT_ROOT)},
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULTS=")), None)
    if line is None:
        if "No module named 'PySide6'" in proc.stderr:
            pytest.skip("real PySide6 not importable in this environment")
        pytest.fail(f"real-Qt subprocess produced no report:\n{proc.stderr[-2000:]}")
    return json.loads(line.removeprefix("RESULTS="))


class TestButtonAvailability:
    def test_disabled_without_a_source(self, gui):
        assert gui["empty"] is False

    def test_enabled_for_a_single_video(self, gui):
        assert gui["single_video"] is True

    def test_disabled_for_a_folder_of_videos(self, gui):
        """A folder holds several timelines; one in/out pair cannot describe it."""
        assert gui["folder_of_videos"] is False


class TestDialog:
    def test_duration_is_read(self, gui):
        assert gui["duration"] == pytest.approx(12.0, abs=0.2)

    def test_marks_become_a_range(self, gui):
        assert gui["selected"] == {"start": 3.0, "end": 9.0}

    def test_whole_video_reports_no_trim(self, gui):
        """None keeps a no-op trim out of the config and out of the command."""
        assert gui["whole_video_selection"] is None

    def test_out_before_in_is_corrected(self, gui):
        """Marking an out point earlier than the in point resets the start."""
        assert gui["backwards_start"] == 0.0


class TestPanelState:
    def test_trim_is_exposed_in_state(self, gui):
        assert gui["state_roundtrip"] == {"start": 3.0, "end": 9.0}

    def test_trim_survives_set_state(self, gui):
        assert gui["restored"] == {"start": 3.0, "end": 9.0}


class TestTypedEntry:
    def test_fields_start_on_the_full_span(self, gui):
        assert gui["fields_start"] == ["00:00.0", "00:12.0"]

    def test_typed_values_become_the_range(self, gui):
        """Both shown form and bare seconds are accepted."""
        assert gui["typed_range"] == {"start": 3.0, "end": 9.0}

    def test_unparsable_entry_leaves_the_mark_alone(self, gui):
        assert gui["typed_invalid_start"] == 0.0

    def test_unparsable_entry_is_rewritten_from_the_mark(self, gui):
        """The field cannot be left showing something the range does not hold."""
        assert gui["typed_invalid_field"] == "00:00.0"

    def test_out_typed_before_in_is_refused(self, gui):
        start, end = gui["typed_out_before_in"]
        assert start == 11.0
        assert end > start

    def test_out_beyond_the_duration_is_clamped(self, gui):
        assert gui["typed_beyond_duration"] == pytest.approx(12.0, abs=0.2)


class TestContainerHint:
    def test_no_hint_for_mp4(self, gui):
        assert gui["hint_preferred"] is False

    def test_hint_shown_for_other_containers(self, gui):
        """Trimming still works; the advice is about seek precision."""
        assert gui["hint_other"] is True
