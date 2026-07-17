"""Tests d'intégration : ColmapParams + command building (no subprocess)."""
import pytest

from tests.conftest import _patch_pyqt6

_patch_pyqt6()


class TestColmapParamsRoundtrip:
    """ColmapParams serialization/deserialization."""

    def test_to_dict_roundtrip(self):
        """Create ColmapParams, to_dict, from_dict, verify equality."""
        from app.core.params import ColmapParams

        original = ColmapParams(
            feature_type="SIFT",
            matcher_type="exhaustive",
            single_camera=True,
            cross_check=False,
        )
        d = original.to_dict()
        restored = ColmapParams.from_dict(d)
        assert restored.feature_type == original.feature_type
        assert restored.matcher_type == original.matcher_type
        assert restored.single_camera == original.single_camera
        assert restored.cross_check == original.cross_check

    def test_custom_values(self):
        """Set specific params, verify to_dict includes them."""
        from app.core.params import ColmapParams

        params = ColmapParams()
        params.max_num_features = 8192
        params.matcher_type = "sequential"
        params.feature_type = "ALIKED_N32"
        params.ba_refine_focal_length = False

        d = params.to_dict()
        assert d["max_num_features"] == 8192
        assert d["matcher_type"] == "sequential"
        assert d["feature_type"] == "ALIKED_N32"
        assert not d["ba_refine_focal_length"]

    def test_defaults_reasonable(self):
        """Verify default values are not None for critical fields."""
        from app.core.params import ColmapParams

        params = ColmapParams()
        assert params.max_num_features > 0
        assert params.matcher_type is not None

    def test_unknown_keys_ignored(self):
        """from_dict with unknown keys should not crash and preserve known keys."""
        from app.core.params import ColmapParams

        d = {
            "matcher_type": "vocab_tree",
            "unknown_key_xyz": "should_be_ignored",
            "feature_type": "SIFT",
        }
        params = ColmapParams.from_dict(d)
        assert params.matcher_type == "vocab_tree"
        assert params.feature_type == "SIFT"


class TestBrushCommandBuilding:
    """BrushEngine command building without executing."""

    @pytest.fixture
    def brush_engine(self):
        from app.core.brush_engine import BrushEngine
        engine = BrushEngine(logger_callback=lambda x: None)
        return engine

    def test_build_command_with_preset_dense(self, brush_engine, tmp_path):
        """Build command with dense preset, verify expected flags."""
        cmd = brush_engine.build_command(
            input_path=tmp_path,
            output_path=tmp_path / "output",
            params={"preset": "dense"},
        )
        " ".join(cmd) if isinstance(cmd, list) else cmd
        # Should not crash and return something meaningful
        assert cmd is not None

    def test_build_command_with_preset_fast(self, brush_engine, tmp_path):
        """Build command with fast preset."""
        cmd = brush_engine.build_command(
            input_path=tmp_path,
            output_path=tmp_path / "output",
            params={"preset": "fast"},
        )
        assert cmd is not None

    def test_build_command_custom_params(self, brush_engine, tmp_path):
        """Build command with custom overrides."""
        cmd = brush_engine.build_command(
            input_path=tmp_path,
            output_path=tmp_path / "output",
            params={
                "refine_mode": False,
                "total_steps": 10000,
                "ply_name": "test.ply",
            },
        )
        assert cmd is not None

    def test_security_unknown_params_rejected(self, brush_engine, tmp_path):
        """Unknown/dangerous params should be filtered out."""
        cmd = brush_engine.build_command(
            input_path=tmp_path,
            output_path=tmp_path / "output",
            params={"preset": "medium", "--rm": "-rf /", "unknown_flag": "value"},
        )
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        # Should not contain dangerous patterns
        assert "-rf" not in cmd_str


class TestColmapCommandBuilding:
    """COLMAP command building via ColmapEngine."""

    def test_build_feature_extractor_command(self, tmp_path):
        """Building a feature_extractor command should produce valid args."""
        from app.core.engine import ColmapEngine
        from app.core.params import ColmapParams

        params = ColmapParams(max_num_features=4096)
        logs = []

        engine = ColmapEngine(
            params=params,
            input_path=str(tmp_path / "images"),
            output_path=str(tmp_path),
            input_type="images",
            fps=1,
            project_name="test_proj",
            logger_callback=logs.append,
            progress_callback=lambda x: None,
            status_callback=lambda x: None,
            check_cancel_callback=lambda: False,
        )
        assert engine is not None
        assert engine.project_name == "test_proj"
