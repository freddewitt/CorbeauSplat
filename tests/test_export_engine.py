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
