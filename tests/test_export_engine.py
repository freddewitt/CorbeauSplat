import struct

import pytest

from app.core.export_engine import ExportEngine


def make_ply_ascii(path, vertices):
    with open(path, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")
        for v in vertices:
            f.write(f"{v[0]} {v[1]} {v[2]} {v[3]} {v[4]} {v[5]}\n")


def make_ply_binary(path, vertices):
    with open(path, "wb") as f:
        header = (
            "ply\n"
            "format binary_little_endian 1.0\n"
            f"element vertex {len(vertices)}\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
            "property uchar red\n"
            "property uchar green\n"
            "property uchar blue\n"
            "end_header\n"
        )
        f.write(header.encode("ascii"))
        for v in vertices:
            f.write(struct.pack("<fffBBB", *v))


SAMPLE_VERTICES = [
    (1.0, 2.0, 3.0, 255, 0, 0),
    (4.0, 5.0, 6.0, 0, 255, 0),
    (7.0, 8.0, 9.0, 0, 0, 255),
]


@pytest.fixture
def engine():
    return ExportEngine()


class TestExportXyz:
    def test_ascii_ply_to_xyz(self, engine, tmp_path):
        ply_file = tmp_path / "input.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "xyz")
        assert result is True

        xyz_file = out_dir / "input.xyz"
        assert xyz_file.exists()
        lines = xyz_file.read_text().strip().splitlines()
        assert len(lines) == 3
        parts = lines[0].split()
        assert len(parts) == 3
        assert float(parts[0]) == 1.0
        assert float(parts[1]) == 2.0
        assert float(parts[2]) == 3.0

    def test_binary_ply_to_xyz(self, engine, tmp_path):
        ply_file = tmp_path / "input.ply"
        make_ply_binary(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "xyz")
        assert result is True

        xyz_file = out_dir / "input.xyz"
        assert xyz_file.exists()
        lines = xyz_file.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_xyz_with_colors(self, engine, tmp_path):
        ply_file = tmp_path / "colored.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "xyz", options={"include_colors": True})
        assert result is True

        xyz_file = out_dir / "colored.xyz"
        lines = xyz_file.read_text().strip().splitlines()
        assert len(lines) == 3
        parts = lines[0].split()
        assert len(parts) == 6
        assert parts[3] == "255"
        assert parts[4] == "0"
        assert parts[5] == "0"

    def test_xyz_custom_delimiter(self, engine, tmp_path):
        ply_file = tmp_path / "delim.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "xyz", options={"delimiter": ","})
        assert result is True

        xyz_file = out_dir / "delim.xyz"
        lines = xyz_file.read_text().strip().splitlines()
        parts = lines[0].split(",")
        assert len(parts) == 3
        assert float(parts[0]) == 1.0


class TestExportPly:
    def test_copy_ply(self, engine, tmp_path):
        ply_file = tmp_path / "copyme.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "ply")
        assert result is True
        assert (out_dir / "copyme.ply").exists()

    def test_compressed_ply(self, engine, tmp_path):
        ply_file = tmp_path / "gz.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "ply", options={"compress": True})
        assert result is True
        assert (out_dir / "gz.ply.gz").exists()


class TestExportEdgeCases:
    def test_missing_input_file(self, engine, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = engine.export("/nonexistent/file.ply", str(out_dir), "xyz")
        assert result is False

    def test_unsupported_format(self, engine, tmp_path):
        ply_file = tmp_path / "input.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "stl")
        assert result is False

    def test_empty_ply(self, engine, tmp_path):
        ply_file = tmp_path / "empty.ply"
        make_ply_ascii(ply_file, [])
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = engine.export(str(ply_file), str(out_dir), "xyz")
        assert result is True
        xyz_file = out_dir / "empty.xyz"
        assert xyz_file.read_text().strip() == ""


def make_ply_splat(path, vertices):
    """Write a binary PLY holding Gaussian Splat colours (f_dc_0..2) instead of RGB."""
    with open(path, "wb") as f:
        header = (
            "ply\n"
            "format binary_little_endian 1.0\n"
            f"element vertex {len(vertices)}\n"
            "property float x\n"
            "property float y\n"
            "property float z\n"
            "property float f_dc_0\n"
            "property float f_dc_1\n"
            "property float f_dc_2\n"
            "end_header\n"
        )
        f.write(header.encode("ascii"))
        for v in vertices:
            f.write(struct.pack("<ffffff", *v))


def make_ply_positions_only(path, vertices):
    with open(path, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("end_header\n")
        for v in vertices:
            f.write(f"{v[0]} {v[1]} {v[2]}\n")


# 0.5 + SH_C0 * f_dc, clipped to [0, 1]: +1.7724539 saturates to 255, -1.7724539 to 0,
# and 0.0 lands mid-grey (127 after the uint8 cast).
SPLAT_VERTICES = [
    (1.0, 2.0, 3.0, 1.7724539, -1.7724539, 0.0),
    (4.0, 5.0, 6.0, -1.7724539, 1.7724539, 0.0),
    (7.0, 8.0, 9.0, 0.0, 0.0, 1.7724539),
]

POSITION_ONLY_VERTICES = [
    (1.0, 2.0, 3.0),
    (4.0, 5.0, 6.0),
]


class TestExtractColors:
    def test_reads_classic_rgb(self, tmp_path):
        from plyfile import PlyData

        from app.core.export_engine import _extract_colors

        ply_file = tmp_path / "rgb.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        colors = _extract_colors(PlyData.read(str(ply_file))['vertex'])

        assert colors is not None
        assert colors.shape == (3, 3)
        assert list(colors[0]) == [255, 0, 0]
        assert list(colors[2]) == [0, 0, 255]

    def test_reconstructs_rgb_from_spherical_harmonics(self, tmp_path):
        from plyfile import PlyData

        from app.core.export_engine import _extract_colors

        ply_file = tmp_path / "splat.ply"
        make_ply_splat(ply_file, SPLAT_VERTICES)
        colors = _extract_colors(PlyData.read(str(ply_file))['vertex'])

        assert colors is not None
        assert colors.shape == (3, 3)
        assert list(colors[0]) == [255, 0, 127]
        assert list(colors[1]) == [0, 255, 127]
        # Not a single flat colour: the whole point of the SH branch.
        assert len({tuple(row) for row in colors}) == 3

    def test_returns_none_without_colors(self, tmp_path):
        from plyfile import PlyData

        from app.core.export_engine import _extract_colors

        ply_file = tmp_path / "bare.ply"
        make_ply_positions_only(ply_file, POSITION_ONLY_VERTICES)

        assert _extract_colors(PlyData.read(str(ply_file))['vertex']) is None


class TestSplatColorsInExports:
    def test_xyz_keeps_splat_colors(self, engine, tmp_path):
        ply_file = tmp_path / "splat.ply"
        make_ply_splat(ply_file, SPLAT_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(
            str(ply_file), str(out_dir), "xyz", options={"include_colors": True}
        ) is True

        lines = (out_dir / "splat.xyz").read_text().strip().splitlines()
        assert len(lines) == 3
        assert lines[0].split()[3:] == ["255", "0", "127"]
        assert lines[1].split()[3:] == ["0", "255", "127"]

    def test_obj_keeps_splat_colors(self, engine, tmp_path):
        ply_file = tmp_path / "splat.ply"
        make_ply_splat(ply_file, SPLAT_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(str(ply_file), str(out_dir), "obj") is True

        rows = [
            line.split()
            for line in (out_dir / "splat.obj").read_text().splitlines()
            if line.startswith("v ")
        ]
        assert len(rows) == 3
        assert [float(c) for c in rows[0][4:]] == [1.0, 0.0, pytest.approx(0.498, abs=0.002)]
        assert len({tuple(row[4:]) for row in rows}) == 3

    def test_glb_trimesh_keeps_splat_colors(self, engine, tmp_path):
        trimesh = pytest.importorskip("trimesh")
        ply_file = tmp_path / "splat.ply"
        make_ply_splat(ply_file, SPLAT_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(
            str(ply_file), str(out_dir), "glb", options={"method": "trimesh"}
        ) is True

        glb_file = out_dir / "splat.glb"
        assert glb_file.exists()
        loaded = trimesh.load(str(glb_file), force='scene')
        cloud = next(iter(loaded.geometry.values()))
        assert len({tuple(c[:3]) for c in cloud.colors}) == 3

    def test_export_without_colors_still_succeeds(self, engine, tmp_path):
        messages = []
        engine.logger_callback = messages.append
        ply_file = tmp_path / "bare.ply"
        make_ply_positions_only(ply_file, POSITION_ONLY_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(
            str(ply_file), str(out_dir), "xyz", options={"include_colors": True}
        ) is True

        lines = (out_dir / "bare.xyz").read_text().strip().splitlines()
        assert [len(line.split()) for line in lines] == [3, 3]
        assert any("aucune couleur" in m for m in messages)


class TestExportPlyAscii:
    def test_binary_ply_becomes_ascii(self, engine, tmp_path):
        ply_file = tmp_path / "binary.ply"
        make_ply_binary(ply_file, SAMPLE_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(
            str(ply_file), str(out_dir), "ply", options={"ascii_format": True}
        ) is True

        output = out_dir / "binary.ply"
        text = output.read_text()
        assert text.startswith("ply\nformat ascii 1.0\n")
        assert "1 2 3 255 0 0" in text

    def test_ascii_conversion_preserves_splat_fields(self, engine, tmp_path):
        ply_file = tmp_path / "splat.ply"
        make_ply_splat(ply_file, SPLAT_VERTICES)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        assert engine.export(
            str(ply_file), str(out_dir), "ply", options={"ascii_format": True}
        ) is True

        from plyfile import PlyData
        vertex = PlyData.read(str(out_dir / "splat.ply"))['vertex']
        assert 'f_dc_0' in (vertex.data.dtype.names or ())
        assert len(vertex) == 3


class TestExportPlySameFileGuard:
    def test_copy_onto_itself_is_refused(self, engine, tmp_path):
        messages = []
        engine.logger_callback = messages.append
        ply_file = tmp_path / "same.ply"
        make_ply_ascii(ply_file, SAMPLE_VERTICES)
        before = ply_file.read_bytes()

        assert engine.export(str(ply_file), str(tmp_path), "ply") is False
        assert ply_file.read_bytes() == before
        assert any("même fichier" in m for m in messages)


class TestAssimpTimeout:
    def test_hanging_assimp_is_abandoned(self, engine, tmp_path, monkeypatch):
        import subprocess as sp

        from app.core import export_engine as ee

        messages = []
        engine.logger_callback = messages.append
        monkeypatch.setattr(ee.shutil, "which", lambda name: "/usr/bin/assimp" if name == "assimp" else None)

        def hang(*args, **kwargs):
            assert kwargs["timeout"] == ee.ASSIMP_TIMEOUT_SECONDS
            raise sp.TimeoutExpired(cmd="assimp", timeout=kwargs["timeout"])

        monkeypatch.setattr(ee.subprocess, "run", hang)

        assert engine._convert_obj_to_glb(tmp_path / "in.obj", tmp_path / "out.glb") is False
        assert any("n'a pas répondu" in m for m in messages)


class TestExportAvailability:
    """is_available() used to be a hardcoded True, so its two guards were inert."""

    def test_core_formats_available_when_plyfile_present(self, engine):
        # plyfile is a hard dependency of the app, so these always resolve.
        for fmt in ("ply", "xyz", "obj"):
            assert engine.missing_dependency(fmt) is None
            assert engine.is_available(fmt) is True

    def test_missing_backend_is_named(self, engine, monkeypatch):
        from app.core import export_engine as ee

        monkeypatch.setattr(ee.importlib.util, "find_spec", lambda name: None)
        monkeypatch.setattr(ee.shutil, "which", lambda name: None)

        assert engine.missing_dependency("spz") == "spz"
        assert engine.missing_dependency("glb") == "trimesh, open3d or assimp"
        assert engine.is_available("glb") is False

    def test_glb_accepts_any_one_backend(self, engine, monkeypatch):
        from app.core import export_engine as ee

        monkeypatch.setattr(ee.importlib.util, "find_spec", lambda name: None)
        monkeypatch.setattr(ee.shutil, "which", lambda name: "/usr/bin/assimp" if name == "assimp" else None)

        assert engine.missing_dependency("glb") is None

    def test_unknown_format_is_reported(self, engine):
        assert "unknown format" in engine.missing_dependency("dae")

    def test_export_refuses_before_doing_work(self, engine, tmp_path, monkeypatch):
        """The failure is announced up front instead of after a conversion runs."""
        from app.core import export_engine as ee

        src = tmp_path / "in.ply"
        make_ply_ascii(src, [(0.0, 0.0, 0.0, 255, 255, 255)])
        monkeypatch.setattr(ee.importlib.util, "find_spec", lambda name: None)
        monkeypatch.setattr(ee.shutil, "which", lambda name: None)

        messages = []
        engine.logger_callback = messages.append

        assert engine.export(str(src), str(tmp_path / "out"), "spz") is False
        assert any("dépendance manquante" in m for m in messages)
