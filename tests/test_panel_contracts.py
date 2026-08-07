"""Contrats statiques des panneaux GUI (analyse AST, sans Qt ni display).

Motivation (audit 2026-08-07) : la couche `app/gui/panels/` concentre
l'orchestration mais n'avait aucun test. La classe de bug récurrente y est
« widget créé, jamais relu » — quatre findings d'affilée (chk_upscale,
chk_stabilized, tta/compression, chk_filter_blur/combo_blur). Ces tests la
détectent sans instancier Qt.
"""
import ast
import pathlib

import pytest

from app.core.params import ColmapParams
from app.gui.panels.reconstruction_logic import apply_source_blur_settings

ROOT = pathlib.Path(__file__).resolve().parent.parent
PANELS_DIR = ROOT / "app" / "gui" / "panels"

# Widgets de saisie : leur valeur doit être lue quelque part, sinon le réglage
# affiché à l'utilisateur n'a aucun effet. Les widgets purement décoratifs
# (QLabel, QGroupBox…) sont hors périmètre.
INPUT_WIDGETS = {
    "QCheckBox", "QComboBox", "QSpinBox", "QDoubleSpinBox",
    "QLineEdit", "QSlider", "QRadioButton", "QPlainTextEdit",
    "DropLineEdit",
}

PANEL_FILES = sorted(p for p in PANELS_DIR.glob("*.py") if p.name != "__init__.py")


def _input_widget_attributes(tree):
    """``self.<name>`` assigned from a direct INPUT_WIDGETS constructor call."""
    names = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        ctor = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if ctor not in INPUT_WIDGETS:
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                names[target.attr] = node.lineno
    return names


def _attribute_reads(tree, assigned_lines):
    """``self.<name>`` occurrences outside of the creating assignment line."""
    reads = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.lineno != assigned_lines.get(node.attr)
        ):
            reads.add(node.attr)
    return reads


@pytest.mark.parametrize("panel_file", PANEL_FILES, ids=lambda p: p.stem)
def test_every_input_widget_is_read_back(panel_file):
    """Tout widget de saisie doit être relu (get_params/get_state/handler).

    Un widget seulement construit et posé dans un layout est un réglage mort :
    l'utilisateur le manipule, rien ne le consomme.
    """
    tree = ast.parse(panel_file.read_text())
    created = _input_widget_attributes(tree)
    read = _attribute_reads(tree, created)
    orphans = sorted(name for name in created if name not in read)
    assert orphans == [], (
        f"{panel_file.name} : widgets de saisie jamais relus {orphans}"
    )


@pytest.mark.parametrize("panel_file", PANEL_FILES, ids=lambda p: p.stem)
def test_every_combo_is_populated(panel_file):
    """Tout QComboBox doit être rempli quelque part dans son panneau.

    Complète le test précédent, qui ne voyait que les *lectures* : `combo_model`
    d'UpscalePanel était bien lu par get_params() — mais jamais peuplé, donc
    toujours vide, et l'upscale échouait sur « Aucun modèle sélectionné ».
    Un combo est considéré rempli s'il reçoit addItem/addItems/setModel, ou s'il
    est passé à une méthode de rafraîchissement du panneau.
    """
    source = panel_file.read_text()
    tree = ast.parse(source)

    combos = {
        name: line
        for name, line in _input_widget_attributes(tree).items()
        if f"self.{name} = QComboBox()" in source
    }
    unpopulated = sorted(
        name for name in combos
        if not any(
            f"self.{name}.{filler}" in source
            for filler in ("addItem", "addItems", "setModel", "insertItem")
        )
    )
    assert unpopulated == [], (
        f"{panel_file.name} : QComboBox jamais peuplés {unpopulated}"
    )


def test_source_blur_settings_reach_colmap_params():
    """Régression : la case « images floues » de Source doit atteindre le moteur.

    Avant correction, ReconstructionPanel.get_params() ignorait filter_blurry et
    blur_factor, et rien ne reportait les widgets de SourcePanel — le filtre ne
    s'exécutait jamais depuis la GUI (ColmapEngine exige filter_blurry=True).
    """
    params = apply_source_blur_settings(
        ColmapParams(), {"filter_blur": True, "blur_strength": "strong"}
    )
    assert params.filter_blurry is True
    assert params.blur_factor > 0


def test_source_blur_settings_disabled_by_default():
    params = apply_source_blur_settings(ColmapParams(), {})
    assert params.filter_blurry is False


def test_source_blur_strength_changes_factor():
    light = apply_source_blur_settings(ColmapParams(), {"filter_blur": True, "blur_strength": "light"})
    strong = apply_source_blur_settings(ColmapParams(), {"filter_blur": True, "blur_strength": "strong"})
    assert light.blur_factor != strong.blur_factor
