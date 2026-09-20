"""Container support: any video FFmpeg can demux must reach the pipeline.

Regression: the three scanning sites each carried their own four-extension
tuple, so anything outside mp4/mov/avi/mkv was silently classified as "no video
here". They now share ``app/core/media.py``.
"""
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.core.media import (
    VIDEO_EXTENSIONS,
    conversion_suffix,
    convert_image,
    is_image_file,
    is_video_file,
    needs_image_conversion,
    without_hwaccel,
)
from app.gui.panels.reconstruction_logic import detect_source_kind


class TestIsVideoFile:
    @pytest.mark.parametrize("name", [
        "clip.mp4", "clip.mov", "clip.m4v", "clip.mkv", "clip.webm", "clip.avi",
        "clip.wmv", "clip.flv", "clip.mpg", "clip.mpeg", "clip.mts", "clip.m2ts",
        "clip.ts", "clip.mxf", "clip.3gp", "clip.insv", "clip.ogv", "clip.vob",
    ])
    def test_known_containers(self, tmp_path, name):
        assert is_video_file(tmp_path / name)

    @pytest.mark.parametrize("name", ["IMG_0001.MOV", "GX010042.MP4", "clip.MkV"])
    def test_extension_case_is_ignored(self, tmp_path, name):
        """iPhone footage arrives as .MOV, action cameras as .MP4."""
        assert is_video_file(tmp_path / name)

    @pytest.mark.parametrize("name", ["photo.jpg", "photo.png", "splat.ply", "notes"])
    def test_non_videos(self, tmp_path, name):
        assert not is_video_file(tmp_path / name)

    def test_accepts_plain_strings(self):
        assert is_video_file("/tmp/clip.Mov")
        assert not is_video_file("/tmp/photo.jpg")
        assert not is_video_file("/tmp/no_extension")


class TestDetectSourceKind:
    @pytest.mark.parametrize("name", ["clip.mkv", "clip.webm", "IMG_1.MOV", "clip.m4v"])
    def test_single_video_file(self, tmp_path, name):
        video = tmp_path / name
        video.write_bytes(b"x")
        assert detect_source_kind(str(video)) == "video"

    def test_folder_of_mixed_containers(self, tmp_path):
        for name in ("a.mkv", "b.webm", "c.MOV", "d.mts"):
            (tmp_path / name).write_bytes(b"x")
        assert detect_source_kind(str(tmp_path)) == "video"

    def test_folder_with_images_and_exotic_video_is_mixed(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x")
        (tmp_path / "b.webm").write_bytes(b"x")
        assert detect_source_kind(str(tmp_path)) == "mixed"


class TestCollectVideoPaths:
    def test_every_container_is_collected(self, tmp_path):
        from app.core.engine import ColmapEngine

        for name in ("a.mkv", "b.webm", "c.MOV", "d.mts", "e.insv", "f.jpg"):
            (tmp_path / name).write_bytes(b"x")

        engine = ColmapEngine.__new__(ColmapEngine)
        engine.input_path = tmp_path
        collected = {p.name for p in ColmapEngine._collect_video_paths(engine)}

        assert collected == {"a.mkv", "b.webm", "c.MOV", "d.mts", "e.insv"}

    def test_extension_list_is_shared(self):
        """One list, so the panel and the engines cannot drift apart again."""
        from app.gui.panels import reconstruction_logic

        assert reconstruction_logic._VIDEO_EXTS is VIDEO_EXTENSIONS


class TestWithoutHwaccel:
    def test_drops_the_flag_and_its_value(self):
        cmd = ["ffmpeg", "-hwaccel", "videotoolbox", "-i", "clip.mov", "out_%04d.jpg"]
        assert without_hwaccel(cmd) == ["ffmpeg", "-i", "clip.mov", "out_%04d.jpg"]

    def test_leaves_a_software_command_untouched(self):
        cmd = ["ffmpeg", "-i", "clip.mov", "out_%04d.jpg"]
        assert without_hwaccel(cmd) == cmd


class TestHardwareDecodeFallback:
    """VideoToolbox rejects ProRes / 10-bit HEVC .mov files that FFmpeg decodes
    fine in software — the container must not be refused for that."""

    @patch("app.core.engine.resolve_binary", side_effect=lambda x: x)
    @patch("app.core.engine.is_apple_silicon", return_value=True)
    def _engine(self, tmp_path, mock_silicon=None, mock_resolve=None):
        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matcher_type = "sequential"
        return ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "video", 5, logger_callback=lambda *_: None,
        )

    def test_retries_in_software_when_hwaccel_fails(self, tmp_path):
        engine = self._engine(tmp_path)
        engine.is_silicon = True
        images_dir = tmp_path / "images"

        with patch.object(engine, "_execute_command", side_effect=[1, 0]) as mock_exec:
            result = engine.extract_frames_from_video(str(tmp_path / "clip.mov"), images_dir)

        assert result is True
        first_cmd, second_cmd = (call.args[0] for call in mock_exec.call_args_list)
        assert "-hwaccel" in first_cmd
        assert "-hwaccel" not in second_cmd

    def test_no_retry_when_hardware_decode_succeeds(self, tmp_path):
        engine = self._engine(tmp_path)
        engine.is_silicon = True

        with patch.object(engine, "_execute_command", return_value=0) as mock_exec:
            engine.extract_frames_from_video(str(tmp_path / "clip.mov"), tmp_path / "images")

        assert mock_exec.call_count == 1

    def test_four_dgs_retries_in_software(self, tmp_path):
        from app.core.four_dgs_engine import FourDGSEngine

        engine = FourDGSEngine(logger_callback=lambda *_: None)
        engine.stop_requested = False

        with patch("app.core.four_dgs_engine.is_apple_silicon", return_value=True), \
             patch.object(engine, "_execute_command", side_effect=[1, 0]) as mock_exec:
            assert engine.extract_frames(str(tmp_path / "cam.mov"), tmp_path / "out", fps=5)

        first_cmd, second_cmd = (call.args[0] for call in mock_exec.call_args_list)
        assert "-hwaccel" in first_cmd
        assert "-hwaccel" not in second_cmd


class TestImageFormats:
    def test_native_formats_need_no_conversion(self, tmp_path):
        for name in ("a.jpg", "b.JPEG", "c.png"):
            assert is_image_file(tmp_path / name)
            assert not needs_image_conversion(tmp_path / name)

    @pytest.mark.parametrize("name", [
        "scan.tif", "scan.tiff", "shot.bmp", "shot.webp", "shot.ppm", "shot.tga",
        "shot.jp2", "shot.gif", "IMG_0042.HEIC", "IMG_0042.heif",
    ])
    def test_extra_formats_are_accepted_and_converted(self, tmp_path, name):
        """Refusing them was gratuitous: COLMAP or sips reads every one."""
        assert is_image_file(tmp_path / name)
        assert needs_image_conversion(tmp_path / name)

    def test_unknown_extensions_stay_out(self, tmp_path):
        assert not is_image_file(tmp_path / "splat.ply")
        assert not is_image_file(tmp_path / "clip.mov")

    def test_detect_source_kind_sees_them(self, tmp_path):
        (tmp_path / "IMG_1.HEIC").write_bytes(b"x")
        (tmp_path / "IMG_2.tif").write_bytes(b"x")
        assert detect_source_kind(str(tmp_path)) == "images"


def _write_png(path, size=(64, 48), exif=None):
    import numpy as np
    from PIL import Image

    arr = (np.random.default_rng(0).random((size[1], size[0], 3)) * 255).astype("uint8")
    im = Image.fromarray(arr)
    im.save(path, **({"exif": exif} if exif else {}))
    return path


class TestConvertImage:
    @pytest.mark.parametrize("src_ext,fmt", [
        ("tif", "png"), ("bmp", "png"), ("webp", "jpeg"), ("gif", "png"), ("tga", "jpeg"),
    ])
    def test_round_trip(self, tmp_path, src_ext, fmt):
        from PIL import Image

        src = tmp_path / f"shot.{src_ext}"
        Image.open(_write_png(tmp_path / "seed.png")).save(src)
        dest = tmp_path / ("out" + conversion_suffix(fmt))

        assert convert_image(src, dest, fmt)
        with Image.open(dest) as out:
            assert out.size == (64, 48)

    def test_exif_is_carried_over(self, tmp_path):
        """COLMAP initialises the intrinsics from the EXIF focal length."""
        from PIL import Image

        seed = Image.open(_write_png(tmp_path / "seed.png"))
        exif = seed.getexif()
        exif[0x0110] = "iPhone 15 Pro"
        exif.get_ifd(0x8769)[0x920A] = (2400, 100)  # FocalLength = 24 mm
        src = tmp_path / "shot.webp"
        seed.save(src, exif=exif)

        dest = tmp_path / "shot.png"
        assert convert_image(src, dest, "png")

        with Image.open(dest) as out:
            assert out.getexif().get(0x0110) == "iPhone 15 Pro"
            assert out.getexif().get_ifd(0x8769).get(0x920A) == (2400, 100)

    def test_camera_tags_survive_a_tiff(self, tmp_path):
        """Pillow exposes TIFF metadata through getexif(), not info["exif"]."""
        from PIL import Image

        seed = Image.open(_write_png(tmp_path / "seed.png"))
        exif = seed.getexif()
        exif[0x0110] = "iPhone 15 Pro"
        src = tmp_path / "scan.tif"
        seed.save(src, exif=exif)

        dest = tmp_path / "scan.png"
        assert convert_image(src, dest, "png")
        with Image.open(dest) as out:
            assert out.getexif().get(0x0110) == "iPhone 15 Pro"

    def test_unreadable_file_reports_failure(self, tmp_path):
        broken = tmp_path / "broken.tif"
        broken.write_bytes(b"not an image")
        assert not convert_image(broken, tmp_path / "out.png", "png")

    @pytest.mark.skipif(not shutil.which("sips"), reason="macOS sips required")
    def test_heic_goes_through_sips(self, tmp_path):
        """Neither Pillow nor OpenCV decodes HEIC here; sips does."""
        from PIL import Image

        seed = _write_png(tmp_path / "seed.png")
        heic = tmp_path / "IMG_0042.heic"
        subprocess.run(["sips", "-s", "format", "heic", str(seed), "--out", str(heic)],
                       capture_output=True, check=True)

        dest = tmp_path / "IMG_0042.png"
        assert convert_image(heic, dest, "png")
        with Image.open(dest) as out:
            assert out.size == (64, 48)


class TestIngestConversion:
    """Conversion happens on the way into the project folder, never in place."""

    def _engine(self, tmp_path, fmt="png"):
        from app.core.engine import ColmapEngine
        from app.core.params import ColmapParams

        engine = ColmapEngine.__new__(ColmapEngine)
        engine.params = ColmapParams(image_convert_format=fmt)
        engine.input_path = tmp_path / "source"
        engine.log = lambda *_: None
        engine.progress = lambda *_: None
        engine.status = lambda *_: None
        engine.is_cancelled = lambda: False
        return engine

    def _source(self, tmp_path):
        from PIL import Image

        src = tmp_path / "source"
        src.mkdir()
        seed = Image.open(_write_png(tmp_path / "seed.png"))
        seed.save(src / "keep.jpg")
        seed.save(src / "keep.png")
        seed.save(src / "scan.tif")
        seed.save(src / "shot.webp")
        return src

    def test_converts_only_what_needs_it(self, tmp_path):
        src = self._source(tmp_path)
        images_dir = tmp_path / "project" / "images"
        images_dir.mkdir(parents=True)
        engine = self._engine(tmp_path)

        assert engine._prepare_images_from_files(images_dir)

        produced = sorted(p.name for p in images_dir.iterdir())
        assert produced == ["keep.jpg", "keep.png", "scan.png", "shot.png"]
        # Originals are left exactly as they were.
        assert sorted(p.name for p in src.iterdir()) == ["keep.jpg", "keep.png", "scan.tif", "shot.webp"]

    def test_jpeg_target_format(self, tmp_path):
        self._source(tmp_path)
        images_dir = tmp_path / "project" / "images"
        images_dir.mkdir(parents=True)
        engine = self._engine(tmp_path, fmt="jpeg")

        assert engine._prepare_images_from_files(images_dir)
        assert sorted(p.name for p in images_dir.iterdir()) == [
            "keep.jpg", "keep.png", "scan.jpg", "shot.jpg",
        ]

    def test_off_copies_untouched(self, tmp_path):
        self._source(tmp_path)
        images_dir = tmp_path / "project" / "images"
        images_dir.mkdir(parents=True)
        engine = self._engine(tmp_path, fmt="off")

        assert engine._prepare_images_from_files(images_dir)
        assert sorted(p.name for p in images_dir.iterdir()) == [
            "keep.jpg", "keep.png", "scan.tif", "shot.webp",
        ]

    def test_conversion_failure_falls_back_to_a_plain_copy(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "broken.tif").write_bytes(b"not an image")
        images_dir = tmp_path / "project" / "images"
        images_dir.mkdir(parents=True)
        engine = self._engine(tmp_path)

        assert engine._prepare_images_from_files(images_dir)
        assert [p.name for p in images_dir.iterdir()] == ["broken.tif"]


class TestConversionSetting:
    def test_default_is_png(self):
        from app.core.params import ColmapParams

        assert ColmapParams().image_convert_format == "png"

    def test_cli_flag_reaches_the_params(self):
        from types import SimpleNamespace

        from app.cli.commands import _build_colmap_params

        args = SimpleNamespace(camera_model="SIMPLE_RADIAL", undistort=False, convert="jpeg")
        assert _build_colmap_params(args).image_convert_format == "jpeg"

    def test_cli_defaults_to_png_when_absent(self):
        from types import SimpleNamespace

        from app.cli.commands import _build_colmap_params

        args = SimpleNamespace(camera_model="SIMPLE_RADIAL", undistort=False)
        assert _build_colmap_params(args).image_convert_format == "png"


class TestHeicIngestNote:
    @pytest.mark.skipif(not shutil.which("sips"), reason="macOS sips required")
    def test_heic_conversion_warns_about_the_lost_focal_length(self, tmp_path):
        """sips drops the Exif sub-IFD: COLMAP then guesses the focal length."""
        from app.core.engine import ColmapEngine
        from app.core.params import ColmapParams

        src = tmp_path / "source"
        src.mkdir()
        seed = _write_png(tmp_path / "seed.png")
        subprocess.run(["sips", "-s", "format", "heic", str(seed),
                        "--out", str(src / "IMG_0042.heic")], capture_output=True, check=True)

        images_dir = tmp_path / "project" / "images"
        images_dir.mkdir(parents=True)
        logs = []
        engine = ColmapEngine.__new__(ColmapEngine)
        engine.params = ColmapParams()
        engine.input_path = src
        engine.log = logs.append
        engine.progress = lambda *_: None
        engine.status = lambda *_: None
        engine.is_cancelled = lambda: False

        assert engine._prepare_images_from_files(images_dir)
        assert [p.name for p in images_dir.iterdir()] == ["IMG_0042.png"]
        assert any("focale EXIF" in line for line in logs)
