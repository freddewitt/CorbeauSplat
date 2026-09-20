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


class TestNonFiniteSplats:
    """A single NaN/Inf splat must not poison np.percentile and empty the whole cloud."""

    def test_single_nan_scale_keeps_finite_splats(self):
        n = 5
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, math.log(0.01))
        scales[2] = float("nan")
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, scales, scales, scales,
            opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
        )
        assert stats["kept"] == n - 1
        assert keep[2] == False  # noqa: E712
        assert stats["removed_scale"] >= 1

    def test_nan_scale_and_giant_splat_both_handled(self):
        n = 6
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, math.log(0.01))
        scales[0] = math.log(100.0)   # giant, must still be dropped
        scales[1] = float("nan")      # must not poison the percentile
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, scales, scales, scales,
            opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
        )
        assert keep[0] == False  # noqa: E712
        assert keep[1] == False  # noqa: E712
        assert stats["kept"] == n - 2

    def test_positive_inf_scale_handled(self):
        n = 4
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, math.log(0.01))
        scales[1] = float("inf")
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, scales, scales, scales,
            opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
        )
        assert stats["kept"] == n - 1
        assert keep[1] == False  # noqa: E712

    def test_negative_inf_scale_does_not_crash_or_empty(self):
        n = 4
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, math.log(0.01))
        scales[2] = float("-inf")  # size collapses to 0 — a tiny splat, not a failure
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            zeros, zeros, zeros, opacity, scales, scales, scales,
            opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
        )
        assert stats["kept"] > 0

    def test_single_nan_coordinate_keeps_finite_splats(self):
        n = 5
        x = np.array([0.0, 0.0, 0.0, 0.0, float("nan")])
        y = np.zeros(n)
        z = np.zeros(n)
        opacity = np.full(n, _logit(0.9))
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            x, y, z, opacity, zeros, zeros, zeros,
            opacity_min=0.0, scale_pct=100.0, outlier_pct=90.0,
        )
        assert stats["kept"] == n - 1
        assert keep[4] == False  # noqa: E712
        assert stats["removed_outlier"] >= 1

    def test_inf_coordinate_handled(self):
        n = 4
        x = np.array([0.0, 0.0, float("inf"), 0.0])
        y = np.zeros(n)
        z = np.zeros(n)
        opacity = np.full(n, _logit(0.9))
        zeros = np.zeros(n)
        keep, stats = compute_clean_mask(
            x, y, z, opacity, zeros, zeros, zeros,
            opacity_min=0.0, scale_pct=100.0, outlier_pct=90.0,
        )
        assert stats["kept"] == n - 1
        assert keep[2] == False  # noqa: E712

    def test_all_nan_scale_raises(self):
        n = 3
        opacity = np.full(n, _logit(0.9))
        scales = np.full(n, float("nan"))
        zeros = np.zeros(n)
        with pytest.raises(ValueError):
            compute_clean_mask(
                zeros, zeros, zeros, opacity, scales, scales, scales,
                opacity_min=0.0, scale_pct=95.0, outlier_pct=100.0,
            )

    def test_all_nan_coordinates_raises(self):
        n = 3
        x = np.full(n, float("nan"))
        y = np.zeros(n)
        z = np.zeros(n)
        opacity = np.full(n, _logit(0.9))
        zeros = np.zeros(n)
        with pytest.raises(ValueError):
            compute_clean_mask(
                x, y, z, opacity, zeros, zeros, zeros,
                opacity_min=0.0, scale_pct=100.0, outlier_pct=90.0,
            )

    def test_healthy_cloud_produces_identical_mask(self):
        """On all-finite input the fix must not change a single mask bit."""
        rng = np.random.default_rng(0)
        n = 40
        x = rng.normal(0, 1, n)
        y = rng.normal(0, 1, n)
        z = rng.normal(0, 1, n)
        opacity = rng.normal(0.5, 1, n)
        s0 = rng.normal(-5, 1, n)
        s1 = rng.normal(-5, 1, n)
        s2 = rng.normal(-5, 1, n)

        keep, stats = compute_clean_mask(
            x, y, z, opacity, s0, s1, s2,
            opacity_min=0.05, scale_pct=99.5, outlier_pct=99.5,
        )

        # Recompute with the pre-fix formulas: the result must be identical.
        alpha = 1.0 / (1.0 + np.exp(-opacity))
        m_op = alpha >= 0.05
        sizes = np.maximum.reduce([np.exp(s0), np.exp(s1), np.exp(s2)])
        m_sc = sizes <= np.percentile(sizes, 99.5)
        cx, cy, cz = np.median(x), np.median(y), np.median(z)
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
        m_out = dist <= np.percentile(dist, 99.5)
        expected = m_op & m_sc & m_out

        assert list(keep) == list(expected)
        assert stats["kept"] == int(expected.sum())


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

def _write_splat_ply(path, n=8, extra_element=False, nan_scale_at=None, nan_coord_at=None):
    """Write a minimal but valid Gaussian Splat PLY, optionally with a second element.

    `nan_scale_at` (int or "all") injects NaN into scale_0 of the given vertices;
    `nan_coord_at` (int or "all") injects NaN into x of the given vertices.
    """
    from plyfile import PlyData, PlyElement

    dtype = [(name, "f4") for name in ("x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2")]
    verts = np.zeros(n, dtype=dtype)
    verts["opacity"] = _logit(0.9)          # well above every preset's floor
    verts["scale_0"] = verts["scale_1"] = verts["scale_2"] = -5.0
    if nan_scale_at is not None:
        idx = range(n) if nan_scale_at == "all" else [nan_scale_at]
        for i in idx:
            verts["scale_0"][i] = float("nan")
    if nan_coord_at is not None:
        idx = range(n) if nan_coord_at == "all" else [nan_coord_at]
        for i in idx:
            verts["x"][i] = float("nan")
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


class TestCleanPlyNonFinite:
    """In-place cleaning must never replace the project file with an empty cloud."""

    def test_in_place_nan_scale_keeps_cloud(self, tmp_path):
        from plyfile import PlyData

        target = _write_splat_ply(tmp_path / "splat.ply", n=10, nan_scale_at=3)
        stats = clean_ply(target, target, strength="light")

        assert stats["kept"] == 9
        assert PlyData.read(str(target))["vertex"].count == 9

    def test_in_place_nan_coordinate_keeps_cloud(self, tmp_path):
        from plyfile import PlyData

        target = _write_splat_ply(tmp_path / "splat.ply", n=10, nan_coord_at=5)
        stats = clean_ply(target, target, strength="light")

        assert stats["kept"] == 9
        assert PlyData.read(str(target))["vertex"].count == 9

    def test_all_nan_scale_raises_and_preserves_file(self, tmp_path):
        target = _write_splat_ply(tmp_path / "splat.ply", n=5, nan_scale_at="all")
        original = target.read_bytes()

        with pytest.raises(ValueError):
            clean_ply(target, target, strength="light")

        assert target.read_bytes() == original
        assert not list(tmp_path.glob("*.tmp"))
