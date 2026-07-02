import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.core.brush_engine import BrushEngine


@pytest.fixture
def engine():
    with patch("app.core.brush_engine.resolve_binary", return_value="/usr/local/bin/brush"):
        eng = BrushEngine()
        eng.project_root = Path("/tmp/test_project")
        return eng


class TestBuildCommandReleaseMode:
    def test_basic_command(self, engine):
        cmd, env = engine.build_command("/input/data", "/output/run")
        assert cmd[0] == "/usr/local/bin/brush"
        assert "--export-path" in cmd
        assert "/output/run" in cmd
        assert "/input/data" in cmd

    def test_total_steps_release_flag(self, engine):
        params = {"total_steps": 7000, "build_mode": "release"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--total-steps" in cmd
        idx = cmd.index("--total-steps")
        assert cmd[idx + 1] == "7000"

    def test_total_steps_source_flag(self, engine):
        params = {"total_steps": 3000, "build_mode": "source"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--total-train-iters" in cmd
        idx = cmd.index("--total-train-iters")
        assert cmd[idx + 1] == "3000"

    def test_no_total_steps_when_absent(self, engine):
        cmd, env = engine.build_command("/input", "/output", {})
        assert "--total-steps" not in cmd
        assert "--total-train-iters" not in cmd


class TestBuildCommandParams:
    def test_sh_degree(self, engine):
        params = {"sh_degree": 3}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--sh-degree" in cmd
        assert cmd[cmd.index("--sh-degree") + 1] == "3"

    def test_max_resolution(self, engine):
        params = {"max_resolution": 1024}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--max-resolution" in cmd
        assert cmd[cmd.index("--max-resolution") + 1] == "1024"

    def test_with_viewer(self, engine):
        params = {"with_viewer": True}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--with-viewer" in cmd

    def test_checkpoint_interval(self, engine):
        params = {"checkpoint_interval": 5000}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--export-every" in cmd
        assert cmd[cmd.index("--export-every") + 1] == "5000"

    def test_checkpoint_interval_zero_skipped(self, engine):
        params = {"checkpoint_interval": 0}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--export-every" not in cmd

    def test_densify_params_included(self, engine):
        params = {
            "start_iter": 500,
            "refine_every": 100,
            "growth_grad_threshold": 0.0002,
            "growth_select_fraction": 0.5,
            "growth_stop_iter": 15000,
            "max_splats": 1000000,
        }
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--start-iter" in cmd
        assert cmd[cmd.index("--start-iter") + 1] == "500"
        assert "--refine-every" in cmd
        assert cmd[cmd.index("--refine-every") + 1] == "100"
        assert "--growth-grad-threshold" in cmd
        assert cmd[cmd.index("--growth-grad-threshold") + 1] == "0.0002"
        assert "--growth-select-fraction" in cmd
        assert cmd[cmd.index("--growth-select-fraction") + 1] == "0.5"
        assert "--growth-stop-iter" in cmd
        assert cmd[cmd.index("--growth-stop-iter") + 1] == "15000"
        assert "--max-splats" in cmd
        assert cmd[cmd.index("--max-splats") + 1] == "1000000"

    def test_none_params_are_skipped(self, engine):
        params = {"start_iter": None, "refine_every": None}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--start-iter" not in cmd
        assert "--refine-every" not in cmd


class TestBuildCommandEnv:
    def test_cuda_device_sets_vulkan_default(self, engine):
        params = {"device": "cuda"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert env["WGPU_BACKEND"] == "vulkan"
        assert env["WGPU_POWER_PREF"] == "high_performance"

    def test_auto_device_sets_vulkan_default(self, engine):
        params = {"device": "auto"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert env["WGPU_BACKEND"] == "vulkan"
        assert env["WGPU_POWER_PREF"] == "high_performance"

    def test_wgpu_backend_override(self, engine):
        cmd, env = engine.build_command("/input", "/output", {"device": "cuda"}, backend_override="dx12")
        assert env["WGPU_BACKEND"] == "dx12"
        cmd, env = engine.build_command("/input", "/output", {"device": "cuda", "wgpu_backend": "dx12"})
        assert env["WGPU_BACKEND"] == "dx12"

    def test_cpu_device_no_wgpu_override(self, engine):
        params = {"device": "cpu"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "WGPU_BACKEND" not in env


class TestBuildCommandCustomArgs:
    def test_allowed_flag_included(self, engine):
        params = {"custom_args": "--ssim-weight 0.3"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--ssim-weight" in cmd
        assert "0.3" in cmd

    def test_disallowed_flag_filtered(self, engine):
        params = {"custom_args": "--malicious-flag value"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--malicious-flag" not in cmd

    def test_mixed_allowed_and_disallowed(self, engine):
        params = {"custom_args": "--lpips-loss-weight 0.05 --evil-flag payload --eval-split-every 8"}
        cmd, env = engine.build_command("/input", "/output", params)
        assert "--lpips-loss-weight" in cmd
        assert "--eval-split-every" in cmd
        assert "--evil-flag" not in cmd

    def test_phantom_brush_flags_rejected(self, engine):
        # These flags do NOT exist in Brush v0.3.0 — passing them makes Brush
        # abort with a clap "unexpected argument" error, so the whitelist must
        # filter them out (they used to be wrongly whitelisted).
        params = {"custom_args": "--refine-pose --test-split 0.1 --log-level debug --save-iterations 5000"}
        cmd, env = engine.build_command("/input", "/output", params)
        for phantom in ("--refine-pose", "--test-split", "--log-level", "--save-iterations"):
            assert phantom not in cmd
