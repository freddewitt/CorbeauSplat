"""Tests for COLMAP resume-folder detection (reconstruction_logic.py)."""

from app.gui.panels.reconstruction_logic import (
    RESUME_COLMAP_PROJECT,
    RESUME_EXTERNAL_IMAGES,
    RESUME_INVALID,
    classify_resume_folder,
)


def test_existing_colmap_project_via_images_dir(tmp_path):
    (tmp_path / "images").mkdir()
    assert classify_resume_folder(tmp_path) == RESUME_COLMAP_PROJECT


def test_existing_colmap_project_via_database(tmp_path):
    (tmp_path / "database.db").write_text("x")
    assert classify_resume_folder(tmp_path) == RESUME_COLMAP_PROJECT


def test_existing_colmap_project_via_sparse(tmp_path):
    (tmp_path / "sparse").mkdir()
    assert classify_resume_folder(tmp_path) == RESUME_COLMAP_PROJECT


def test_external_images_folder(tmp_path):
    (tmp_path / "frame001.jpg").write_text("x")
    (tmp_path / "frame002.PNG").write_text("x")
    assert classify_resume_folder(tmp_path) == RESUME_EXTERNAL_IMAGES


def test_colmap_project_takes_precedence_over_loose_images(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "stray.jpg").write_text("x")
    assert classify_resume_folder(tmp_path) == RESUME_COLMAP_PROJECT


def test_empty_folder_is_invalid(tmp_path):
    assert classify_resume_folder(tmp_path) == RESUME_INVALID


def test_folder_without_images_is_invalid(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    assert classify_resume_folder(tmp_path) == RESUME_INVALID


def test_nonexistent_path_is_invalid(tmp_path):
    assert classify_resume_folder(tmp_path / "nope") == RESUME_INVALID


def test_none_and_empty_are_invalid():
    assert classify_resume_folder(None) == RESUME_INVALID
    assert classify_resume_folder("") == RESUME_INVALID


# ── Unusable source diagnostics ──────────────────────────────────────────────

class TestDescribeUnusableSource:
    """detect_source_kind() collapses every failure into "empty".

    The launch path then reported "Chemins manquants", which is wrong whenever
    the path exists and simply holds a format the chain cannot read.
    """

    def test_blank_path(self):
        from app.gui.panels.reconstruction_logic import describe_unusable_source
        assert "Aucun chemin" in describe_unusable_source("")
        assert "Aucun chemin" in describe_unusable_source("   ")

    def test_missing_path_is_named_as_such(self, tmp_path):
        from app.gui.panels.reconstruction_logic import describe_unusable_source
        message = describe_unusable_source(str(tmp_path / "nope"))
        assert "introuvable" in message

    def test_unsupported_file_names_its_format(self, tmp_path):
        """A camera RAW is a real path with a real format — not a missing path."""
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        raw = tmp_path / "IMG_0042.cr2"
        raw.write_bytes(b"\x00")
        message = describe_unusable_source(str(raw))

        assert "IMG_0042.cr2" in message
        assert "cr2" in message
        assert "Chemins manquants" not in message

    def test_folder_lists_what_it_actually_holds(self, tmp_path):
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        folder = tmp_path / "shoot"
        folder.mkdir()
        (folder / "a.cr2").write_bytes(b"\x00")
        (folder / "b.psd").write_bytes(b"\x00")
        message = describe_unusable_source(str(folder))

        assert "cr2" in message and "psd" in message

    def test_empty_folder_is_distinguished(self, tmp_path):
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        folder = tmp_path / "vide"
        folder.mkdir()
        assert "aucun fichier" in describe_unusable_source(str(folder))

    def test_accepted_formats_are_listed(self, tmp_path):
        from app.core.media import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        raw = tmp_path / "x.cr2"
        raw.write_bytes(b"\x00")
        message = describe_unusable_source(str(raw))

        for ext in ("heic", "tiff", "mp4", "mov"):
            assert ext in message
        # The list must come from the shared sets, not a second hand-kept copy.
        assert len(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS) > 30

    def test_conversion_setting_is_surfaced(self, tmp_path):
        """The accepted list is wider than JPEG/PNG only thanks to conversion."""
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        raw = tmp_path / "x.cr2"
        raw.write_bytes(b"\x00")

        default = describe_unusable_source(str(raw))
        assert "PNG" in default and "--convert" in default

        as_jpeg = describe_unusable_source(str(raw), convert_format="jpeg")
        assert "JPEG" in as_jpeg

    def test_conversion_off_is_flagged_as_a_risk(self, tmp_path):
        """With convert=off nothing is converted, so HEIC/TIFF fail downstream."""
        from app.gui.panels.reconstruction_logic import describe_unusable_source

        raw = tmp_path / "x.cr2"
        raw.write_bytes(b"\x00")
        message = describe_unusable_source(str(raw), convert_format="off")

        assert "désactivée" in message
        assert "refusés" in message
