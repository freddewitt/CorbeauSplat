"""Tests pour app/core/ply_cleaner.py — logique de nettoyage des splats."""
import math

import numpy as np

from app.core.ply_cleaner import PRESETS, compute_keep_mask, resolve_params


def _logit(alpha):
    return math.log(alpha / (1 - alpha))


class TestComputeKeepMask:
    def test_removes_transparent_splats(self):
        # alphas: 0.01 (transparent), 0.9, 0.9 -> opacity_min 0.1 drops the first
        opacity = np.array([_logit(0.01), _logit(0.9), _logit(0.9)])
        zeros = np.zeros(3)
        keep, stats = compute_keep_mask(
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
        keep, stats = compute_keep_mask(
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
        keep, stats = compute_keep_mask(
            x, y, z, opacity, zeros, zeros, zeros,
            opacity_min=0.0, scale_pct=100.0, outlier_pct=90.0,
        )
        assert keep[-1] == False  # noqa: E712 - far floater dropped
        assert stats["removed_outlier"] >= 1

    def test_disabled_thresholds_keep_all(self):
        opacity = np.array([_logit(0.5), _logit(0.5)])
        zeros = np.zeros(2)
        keep, stats = compute_keep_mask(
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
