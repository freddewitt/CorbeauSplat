"""Fixtures d'intégration pour CorbeauSplat.

Importe le conftest racine (mock PyQt6) puis fournit des fixtures
pour créer des projets COLMAP factices et mocker les binaires externes.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

import pytest

# Importe le conftest parent (mock PyQt6 + send2trash)
from tests.conftest import _patch_pyqt6
_patch_pyqt6()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _touch(path: Path):
    """Crée un fichier vide (ou une arborescence si .bin)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def _minimal_jpeg(path: Path):
    """Crée un fichier JPEG 1×1 valide (11 octets — marqueur SOI + EOI).

    Suffisant pour que ``cv2.imread`` ne retourne pas None, évitant le crash
    dans ``_check_and_normalize_resolution``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal JPEG: SOI (FFD8) + APP0 + SOF0 + SOS + EOI (FFD9)
    path.write_bytes(bytes([
        0xFF, 0xD8,  # SOI
        0xFF, 0xE0,  # APP0
        0x00, 0x10,  # length
        0x4A, 0x46, 0x49, 0x46, 0x00,  # "JFIF\0"
        0x01, 0x01,  # version
        0x00,        # units
        0x00, 0x01,  # X density
        0x00, 0x01,  # Y density
        0x00, 0x00,  # thumbnail
        0xFF, 0xDB,  # DQT
        0x00, 0x43, 0x00,  # 64 bytes of quant table
        0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07,
        0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14,
        0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12, 0x13,
        0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A,
        0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20, 0x22,
        0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29, 0x2C,
        0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39,
        0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34, 0x32,
        0xFF, 0xC0,  # SOF0
        0x00, 0x0B,  # length
        0x01,        # precision
        0x00, 0x01,  # height = 1
        0x00, 0x01,  # width = 1
        0x01,        # number of components
        0x01, 0x11, 0x00,  # component 1
        0xFF, 0xC4,  # DHT
        0x00, 0x1F, 0x00,
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        0xFF, 0xDA,  # SOS
        0x00, 0x08,  # length
        0x01, 0x00,  # component
        0x00, 0x3F, 0x00,
        0x7F,        # single MCU
        0xFF, 0xD9,  # EOI
    ]))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_project_dir(tmp_path: Path) -> Path:
    """Crée une arborescence COLMAP factice complète.

    Retourne le chemin du projet (tmp_path / "test_project").
    """
    project = tmp_path / "test_project"
    images_dir = project / "images"
    sparse_0 = project / "sparse" / "0"
    distorted = project / "distorted"

    # Quelques images factices (nécessaires pour valider l'entrée et passer cv2.imread)
    for i in range(3):
        _minimal_jpeg(images_dir / f"frame_{i:04d}.jpg")

    # Fichiers COLMAP binaires factices
    for name in ("points3D.bin", "images.bin", "cameras.bin"):
        _touch(sparse_0 / name)

    _touch(distorted / ".gitkeep")
    return project


@pytest.fixture
def mock_resolve_binary():
    """Patch `resolve_binary` pour retourner des chemins factices.

    Tous les appels à resolve_binary('colmap'), resolve_binary('glomap'), etc.
    retournent un chemin local sans vérifier l'existence réelle.
    """
    def _fake_resolve(name: str):
        return f"/usr/local/bin/{name}"

    with patch("app.core.engine.resolve_binary", side_effect=_fake_resolve):
        yield


@pytest.fixture
def mock_subprocess_run():
    """Patch `BaseEngine._execute_command` pour éviter tout appel système réel.

    Simule également la création de database.db par COLMAP feature_extractor
    (nécessaire pour l'étape view_graph_calibration qui copie la base).
    """
    def _side_effect(cmd, *args, **kwargs):
        # COLMAP feature_extractor creates database.db — simulate this
        cmd_list = list(cmd) if not isinstance(cmd, str) else cmd.split()
        if "feature_extractor" in cmd_list and "--database_path" in cmd_list:
            try:
                db_idx = cmd_list.index("--database_path") + 1
                from pathlib import Path
                db_path = Path(cmd_list[db_idx])
                db_path.parent.mkdir(parents=True, exist_ok=True)
                db_path.touch()
            except (ValueError, IndexError):
                pass
        return 0

    with patch("app.core.base_engine.BaseEngine._execute_command", side_effect=_side_effect) as mock:
        yield mock


@pytest.fixture
def colmap_params():
    """Crée un objet ColmapParams avec des valeurs par défaut pour les tests."""
    from app.core.params import ColmapParams
    return ColmapParams()


@pytest.fixture
def colmap_engine(fake_project_dir, colmap_params, mock_resolve_binary, mock_subprocess_run):
    """Crée une instance ColmapEngine prête pour les tests d'intégration.

    Tous les binaires sont mockés — aucun appel système réel n'est effectué.
    Le projet factice est pré-initialisé dans fake_project_dir.
    """
    from app.core.engine import ColmapEngine

    output_dir = fake_project_dir.parent  # tmp_path
    logs: list[str] = []

    engine = ColmapEngine(
        params=colmap_params,
        input_path=str(fake_project_dir / "images"),
        output_path=str(output_dir),
        input_type="images",
        fps=1,
        project_name=fake_project_dir.name,
        logger_callback=logs.append,
        progress_callback=lambda x: None,
        status_callback=lambda x: None,
        check_cancel_callback=lambda: False,
    )
    return engine
