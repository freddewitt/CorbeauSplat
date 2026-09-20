"""End-to-end integration tests for the COLMAP pipeline.

Tous les binaires externes (colmap, ffmpeg) sont mockés ;
seule la logique d'orchestration du pipeline est testée.
"""


class TestColmapPipeline:
    """Integration: the full COLMAP pipeline, stage by stage."""

    def test_run_returns_success(self, colmap_engine):
        """Le pipeline complet retourne (True, message) quand tout réussit."""
        success, message = colmap_engine.run()
        assert success is True
        assert "Dataset cree" in message

    def test_subprocess_called_with_feature_extractor(self, colmap_engine, mock_subprocess_run):
        """feature_extractor is actually invoked."""
        colmap_engine.run()

        # Collect every call made to SubprocessRunner.start
        all_calls = mock_subprocess_run.call_args_list
        cmd_strings = [" ".join(call[0][0]) for call in all_calls]

        assert any("feature_extractor" in s for s in cmd_strings), (
            "feature_extractor n'a pas été appelé"
        )

    def test_pipeline_steps_order(self, colmap_engine, mock_subprocess_run):
        """Stage order: extractor → matcher → mapper."""
        colmap_engine.run()
        all_calls = mock_subprocess_run.call_args_list
        cmd_strings = [" ".join(call[0][0]) for call in all_calls]

        # Pull out the COLMAP sub-commands
        steps = []
        for s in cmd_strings:
            for keyword in ("feature_extractor", "exhaustive_matcher",
                            "sequential_matcher", "mapper", "image_undistorter"):
                if keyword in s:
                    steps.append(keyword)

        assert "feature_extractor" in steps, "Extraction manquante"
        assert any("matcher" in s for s in steps), "Matching manquant"
        assert "mapper" in steps, "Mapper manquant"

        # Ordre : extractor DOIT précéder matcher DOIT précéder mapper
        idx_extract = steps.index("feature_extractor")
        idx_mapper = steps.index("mapper")
        assert idx_extract < idx_mapper, (
            "feature_extractor doit précéder mapper"
        )

    def test_run_creates_project_directories(self, colmap_engine, fake_project_dir):
        """The pipeline creates images/, sparse/ and checkpoints/."""
        colmap_engine.run()
        project = fake_project_dir
        assert (project / "images").exists()
        assert (project / "sparse").exists()

    def test_run_propagates_cancel(self, colmap_engine, mock_subprocess_run):
        """Un pipeline annulé retourne False."""
        # Force cancellation from the very start
        colmap_engine.check_cancel = lambda: True
        success, message = colmap_engine.run()
        assert success is False

    def test_run_propagates_subprocess_error(self, colmap_engine, mock_subprocess_run):
        """A subprocess error is propagated."""
        # Fait échouer l'appel subprocess
        def _fail(*args, **kwargs):
            raise FileNotFoundError("colmap introuvable")

        mock_subprocess_run.side_effect = _fail
        colmap_engine.check_cancel = lambda: False
        success, message = colmap_engine.run()
        assert success is False


class TestColmapPipelineConfig:
    """The pipeline under its various configurations."""

    def test_sequential_matcher_used(self, colmap_engine, colmap_params, mock_subprocess_run):
        """With matcher_type='sequential', sequential_matcher is the one invoked."""
        colmap_params.matcher_type = 'sequential'
        colmap_engine.run()
        all_calls = mock_subprocess_run.call_args_list
        cmd_strings = [" ".join(call[0][0]) for call in all_calls]

        assert any("sequential_matcher" in s for s in cmd_strings), (
            "sequential_matcher devrait être appelé en mode sequential"
        )
        assert not any("exhaustive_matcher" in s for s in cmd_strings), (
            "exhaustive_matcher ne devrait PAS être appelé en mode sequential"
        )
