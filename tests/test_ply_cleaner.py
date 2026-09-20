"""Tests for app/core/ply_cleaner.py — splat cleaning logic."""
import math
from unittest.mock import patch

import numpy as np
import pytest

from app.core.ply_cleaner import (
    PRESETS,
    CleaningCancelled,
    clean_ply,
    compute_clean_mask,
    resolve_params,
)


def _logit(alpha):
    return math.log(alpha / (1 - alpha))


class TestComputeKeepMask:
    def test_removes_transparent_splats(self):
        # alphas: 0.01 (transparent), 0.9, 0.9 -> opacity_min 0.1 drops the first
        opacity = np.array([_logit(0.01), _logit(0.9), _logit(0.9)])
        zeros = np.zeros(3)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, zeros, zeros, zeros,
            opacity_min=0.1, scale_pct=100.0, outlier_pct=100.0,
        )
        assert list(keep) == [False, True, True]
        assert stats["removed_opacity"] == 1
        assert stats["kept"] == 2

    def test_removes_oversized_splats(self):
        # one giant splat (log-scale large) vs small ones
        n = 10
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, math.log(0.01))
        scales[0] = math.log(100.0)  # giant
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, scales, scales, scales,
            opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
        )
        assert keep[0] == False  # noqa: E712 - the giant is dropped
        assert stats["removed_scale"] >= 1

    def test_removes_spatial_outlier(self):
        # 9 points near origin, 1 far away
        x = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1000.0])
        y = np.zeros(10)
        z = np.zeros(10)
        opacity = np.full(10, _logit(0.9))
        zeros = np.zeros(10)
        keep, stats = compute_clean_mask(
            x, y, z, opacity, zeros, zeros, zeros,
            opacity_min=0.0, scale_pct=100.0, outlier_pct=90.0,
        )
        assert keep[-1] == False  # noqa: E712 - far floater dropped
        assert stats["removed_outlier"] >= 1

    def test_disabled_thresholds_keep_all(self):
        opacity = np.array([_logit(0.5), _logit(0.5)])
        zeros = np.zeros(2)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, zeros, zeros, zeros,
            opacity_min=0.0, scale_pct=100.0, outlier_pct=100.0,
        )
        assert keep.all()
        assert stats["removed"] == 0


class TestPresets:
    def test_presets_exist(self):
        assert set(PRESETS) == {"light", "medium", "strong"}

    def test_resolve_params_overrides(self):
        p = resolve_params("medium", {"opacity_min": 0.42})
        assert p["opacity_min"] == 0.42
        assert p["scale_pct"] == PRESETS["medium"]["scale_pct"]

    def test_resolve_params_unknown_falls_back_to_medium(self):
        assert resolve_params("nope") == PRESETS["medium"]


# ─────────────────────────────────────────────────────────────────────────────
# clean_ply I/O contract — atomicity, element preservation, cancellation
# ─────────────────────────────────────────────────────────────────────────────

def _write_splat_ply(path, n=8, extra_element=False):
    """Write a minimal but valid Gaussian Splat PLY, optionally with a second element."""
    from plyfile import PlyData, PlyElement

    dtype = [(name, "f4") for name in ("x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2")]
    verts = np.zeros(n, dtype=dtype)
    verts["opacity"] = _logit(0.9)          # well above every preset's floor
    verts["scale_0"] = verts["scale_1"] = verts["scale_2"] = -5.0
    elements = [PlyElement.describe(verts, "vertex")]

    if extra_element:
        cams = np.zeros(2, dtype=[("id", "i4"), ("focal", "f4")])
        cams["id"] = [7, 8]
        elements.append(PlyElement.describe(cams, "camera"))

    PlyData(elements, text=False).write(str(path))
    return path


class TestCleanPlyIO:
    def test_in_place_cleaning_is_safe(self, tmp_path):
        """Cleaning a file onto itself yields a complete PLY, not a truncated one."""
        from plyfile import PlyData

        target = _write_splat_ply(tmp_path / "splat.ply", n=10)
        stats = clean_ply(target, target, strength="light")

        assert stats["total"] == 10
        assert PlyData.read(str(target))["vertex"].count == stats["kept"]

    def test_failed_write_leaves_original_intact(self, tmp_path):
        """If the write fails, the original file is preserved and no .tmp is left behind."""
        target = _write_splat_ply(tmp_path / "splat.ply", n=10)
        original = target.read_bytes()

        with patch("plyfile.PlyData.write", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                clean_ply(target, target, strength="light")

        assert target.read_bytes() == original
        assert not list(tmp_path.glob("*.tmp"))

    def test_non_vertex_elements_are_preserved(self, tmp_path):
        """Elements other than `vertex` no longer vanish silently."""
        from plyfile import PlyData

        src = _write_splat_ply(tmp_path / "in.ply", n=6, extra_element=True)
        out = tmp_path / "out.ply"
        clean_ply(src, out, strength="light")

        result = PlyData.read(str(out))
        assert "camera" in result
        assert list(result["camera"]["id"]) == [7, 8]

    def test_cancel_check_stops_before_writing(self, tmp_path):
        """An active cancel_check raises CleaningCancelled without writing anything."""
        src = _write_splat_ply(tmp_path / "in.ply", n=6)
        out = tmp_path / "out.ply"

        with pytest.raises(CleaningCancelled):
            clean_ply(src, out, strength="light", cancel_check=lambda: True)

        assert not out.exists()

    def test_memory_warning_when_file_exceeds_available_ram(self, tmp_path):
        """A file too large for the available RAM triggers a warning."""
        src = _write_splat_ply(tmp_path / "in.ply", n=6)
        messages = []

        with patch("app.core.system.get_memory_info", return_value={"available": 1}):
            clean_ply(src, tmp_path / "out.ply", strength="light", log=messages.append)

        assert any("AVERTISSEMENT" in m for m in messages)
