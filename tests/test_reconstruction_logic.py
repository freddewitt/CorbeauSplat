"""Tests de la détection de dossier de reprise COLMAP (reconstruction_logic.py)."""

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
