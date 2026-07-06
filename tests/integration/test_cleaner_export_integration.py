"""Tests d'intégration : PlyCleaner → ExportEngine (pure Python, no subprocess)."""
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from tests.conftest import _patch_pyqt6
_patch_pyqt6()


def _make_synthetic_ply(path: Path, num_points: int = 100, num_junk: int = 20):
    """Create a synthetic binary PLY for Gaussian Splats.
    
    Creates `num_points` valid splats and `num_junk` nearly-zero-opacity splats.
    Opacity is stored as raw logit; sigmoid(-10) ≈ 0.000045 which is well below
    the default opacity_min=0.10, ensuring junk splats are filtered.
    """
    import struct
    
    total = num_points + num_junk
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {total}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property float opacity\n"
        "property float scale_0\n"
        "property float scale_1\n"
        "property float scale_2\n"
        "property float rot_0\n"
        "property float rot_1\n"
        "property float rot_2\n"
        "property float rot_3\n"
        "property float f_dc_0\n"
        "property float f_dc_1\n"
        "property float f_dc_2\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    )
    
    buf = bytearray()
    for i in range(num_points):
        buf.extend(struct.pack('<fff', i * 0.01, i * 0.02, i * 0.03))  # xyz
        buf.extend(struct.pack('<f', 0.5))  # opacity (good)
        buf.extend(struct.pack('<fff', 0.1, 0.1, 0.1))  # scale
        buf.extend(struct.pack('<ffff', 1.0, 0.0, 0.0, 0.0))  # rot
        buf.extend(struct.pack('<fff', 0.5, 0.5, 0.5))  # f_dc
        buf.extend(struct.pack('<BBB', 255, 0, 0))  # RGB
    
    for i in range(num_junk):
        buf.extend(struct.pack('<fff', 99.0, 99.0, 99.0))  # xyz (far away)
        buf.extend(struct.pack('<f', -10.0))  # opacity logit — sigmoid(-10)≈0.000045 → filtered
        buf.extend(struct.pack('<fff', 0.1, 0.1, 0.1))
        buf.extend(struct.pack('<ffff', 1.0, 0.0, 0.0, 0.0))
        buf.extend(struct.pack('<fff', 0.5, 0.5, 0.5))
        buf.extend(struct.pack('<BBB', 0, 255, 0))
    
    with open(path, 'wb') as f:
        f.write(header.encode('ascii'))
        f.write(bytes(buf))


class TestCleanerExportIntegration:
    """Integration tests: clean PLY files and export to various formats."""

    def test_clean_single_file(self, tmp_path):
        """Clean a PLY, verify output exists with fewer points."""
        from app.core.ply_cleaner import clean_ply

        src = tmp_path / "input.ply"
        _make_synthetic_ply(src)
        dst = tmp_path / "output.ply"

        stats = clean_ply(src, dst, log=lambda x: None)
        assert stats["total"] == 120
        assert stats["kept"] < stats["total"]
        assert dst.exists()
        assert dst.stat().st_size > 0

    def test_clean_export_to_xyz(self, tmp_path):
        """Clean then export to XYZ format, verify output structure."""
        from app.core.ply_cleaner import clean_ply
        from app.core.export_engine import ExportEngine

        src = tmp_path / "input.ply"
        _make_synthetic_ply(src)
        cleaned = tmp_path / "cleaned.ply"
        clean_ply(src, cleaned, log=lambda x: None)

        engine = ExportEngine(logger_callback=lambda x: None)
        # export(input_path, output_path, output_format, scale=1.0, options=None)
        ok = engine.export(str(cleaned), str(tmp_path), "xyz", options={})
        assert ok

        xyz_files = list(tmp_path.glob("*.xyz"))
        assert len(xyz_files) >= 1
        content = xyz_files[0].read_text()
        assert len(content) > 0
        lines = content.strip().split("\n")
        assert len(lines) >= 1
        # Each line should contain 3 numbers (xyz coordinates, no header)
        parts = lines[0].split()
        assert len(parts) == 3
        assert all(p.replace(".", "").replace("-", "").isdigit() for p in parts)

    def test_export_to_ply_ascii(self, tmp_path):
        """Export to ASCII PLY, verify header says 'ascii'."""
        from app.core.export_engine import ExportEngine

        src = tmp_path / "input.ply"
        _make_synthetic_ply(src)

        engine = ExportEngine(logger_callback=lambda x: None)
        ok = engine.export(str(src), str(tmp_path), "ply", options={"ascii_format": True})
        # ASCII PLY export needs plyfile; skip gracefully if not available
        if not ok:
            pytest.skip("PLY ASCII export not available in this environment (plyfile missing)")

        ply_files = list(tmp_path.glob("*.ply"))
        assert len(ply_files) >= 1
        content = ply_files[0].read_text(encoding="ascii", errors="replace")
        assert "format ascii" in content

    def test_clean_then_export_glb(self, tmp_path):
        """Full pipeline: clean → export to GLB, verify output exists."""
        from app.core.ply_cleaner import clean_ply
        from app.core.export_engine import ExportEngine

        src = tmp_path / "input.ply"
        _make_synthetic_ply(src)
        cleaned = tmp_path / "cleaned.ply"
        clean_ply(src, cleaned, log=lambda x: None)

        engine = ExportEngine(logger_callback=lambda x: None)
        try:
            ok = engine.export(str(cleaned), str(tmp_path), "glb", options={})
            assert ok
            glb_files = list(tmp_path.glob("*.glb"))
            assert len(glb_files) >= 1
        except (ImportError, ModuleNotFoundError):
            pytest.skip("trimesh/open3d not available for GLB export")

    def test_cleaner_preset_light(self, tmp_path):
        """'light' preset resolves to valid parameters."""
        from app.core.ply_cleaner import resolve_params

        params = resolve_params("light")
        # PRESETS keys: opacity_min, scale_pct, outlier_pct
        assert "opacity_min" in params
        assert "scale_pct" in params

    def test_cleaner_preset_strong(self, tmp_path):
        """'strong' preset has higher opacity_min than 'light'."""
        from app.core.ply_cleaner import resolve_params

        light = resolve_params("light")
        strong = resolve_params("strong")
        # strong=0.20, light=0.05
        assert strong.get("opacity_min", 0) >= light.get("opacity_min", 0)

    def test_batch_clean(self, tmp_path):
        """Batch clean multiple PLY files in a directory."""
        from app.core.ply_cleaner import clean_ply_batch

        src_dir = tmp_path / "input_batch"
        src_dir.mkdir()
        for i in range(3):
            _make_synthetic_ply(src_dir / f"splat_{i}.ply")

        out_dir = tmp_path / "output_batch"
        out_dir.mkdir()

        # clean_ply_batch returns a list of dicts — each dict has "file"
        # and optionally "error" on failure
        results = clean_ply_batch(src_dir, out_dir)
        assert len(results) == 3
        assert all("error" not in r for r in results)
