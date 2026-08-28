"""Rail gauche de la fenêtre Studio : "Projet" + groupes ENTRAÎNEMENT, OPTIONS
et OUTILS.

- "Projet" (étape ``source``) : item racine, en tête, style permanent distinct
  (fond teinté + liseré accent) pour marquer que c'est la racine de l'arbre.
- ENTRAÎNEMENT : cœur du pipeline — Reconstruction, Entraînement, Visualiser.
- OPTIONS : traitements optionnels chaînés au pipeline (cases à cocher type
  ``upscaler_avant``) — Upscale, Nettoyage, Export, Extraction 360. Cet ordre
  de *lecture* ne reflète volontairement pas l'ordre d'*exécution* :
  Extraction 360 et Upscale s'exécutent avant Reconstruction. La séquence
  réelle est portée par ``PIPELINE_STEPS`` et ``plan_pipeline()``.
  ENTRAÎNEMENT et OPTIONS sont toutes deux visuellement enfants de "Projet"
  (filet vertical + tiret par item, chacune avec icône + libellé toujours
  affichés ensemble, et un marqueur d'état coche / activité / erreur piloté
  par ``StepStatus``) — pour ne pas laisser croire qu'elles sont indépendantes
  du projet, contrairement à OUTILS. Toujours visibles, aucun repli.
- OUTILS : 6 modules indépendants, séparés par un filet horizontal, sans lien
  d'arbre avec "Projet". Toujours visibles, aucun repli.

L'ensemble est dans une ``QScrollArea`` (14 items cumulés → risque de dépassement
vertical sur petit écran, déjà géré ainsi ailleurs dans l'app).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, StepStatus
from app.gui.styles import DEFAULT_THEME, THEMES, get_saved_theme

# Modules OUTILS, dans l'ordre du rail. "360" (Extractor360Panel autonome) a
# été retiré : contrairement à Brush/SuperSplat, il n'apportait aucun
# comportement distinct de l'étape "extraction360" (OPTIONS), qui se lance
# déjà seule depuis son propre bouton — la double instance était redondante.
TOOL_KEYS = ("brush", "sharp", "supersplat", "splattransform", "4dgs")

# Group layout, in rail order. "kind" drives how _build_group() renders it:
#  - "root": Projet alone, no label, no tree line, permanent accent styling.
#  - "tree": items are visual children of Projet — a continuous vertical trunk
#    plus a short dash connects each item back to the trunk.
#  - "separated": visually independent group, split off by a horizontal rule,
#    no vertical link back to Projet.
_GROUPS = (
    {"id": "source", "kind": "root", "keys": ("source",), "label": None},
    {
        "id": "entrainement",
        "kind": "tree",
        "keys": ("reconstruction", "entrainement", "visualiser"),
        "label": ("rail_section_entrainement", "ENTRAÎNEMENT"),
    },
    {
        "id": "options",
        "kind": "tree",
        # À l'exécution, Extraction 360 et Upscale tournent AVANT Reconstruction
        # — c'est PIPELINE_STEPS (run_state.py) et plan_pipeline() qui font foi
        # pour la séquence. Cette liste ne pilote que l'affichage : le rail
        # retrouve ses boutons par clé (self._buttons[key]), jamais par position.
        "keys": ("upscale", "nettoyage", "export", "extraction360"),
        "label": ("rail_section_options", "OPTIONS"),
    },
    {
        "id": "outils",
        "kind": "separated",
        "keys": TOOL_KEYS,
        "label": ("rail_section_outils", "OUTILS"),
    },
)

# Icônes minimalistes : glyphes géométriques monochromes (pas d'emoji couleur),
# qui héritent de la couleur du texte. « icône + libellé toujours ensemble ».
_STEP_ICONS = {
    # Projet = racine de l'arbre, d'où la maison (⌂ U+2302, symbole technique
    # monochrome — pas l'emoji 🏠, qui casserait l'héritage de couleur).
    # Nettoyage est passé de ◈ à ⊘ : deux losanges (◆/◈) côte à côte dans la
    # même colonne étaient indistinguables à 13px, et ⊘ dit mieux le retrait.
    "source": "⌂", "reconstruction": "▦", "entrainement": "◆", "upscale": "⤢",
    "nettoyage": "⊘", "export": "↥", "visualiser": "◉", "extraction360": "◍",
}
_TOOL_ICONS = {
    "brush": "◐", "sharp": "◇", "supersplat": "⊙",
    "splattransform": "⇄", "4dgs": "▷",
}
_STEP_LABEL_KEYS = {
    "source": ("rail_step_projet", "Projet"),
    "extraction360": ("rail_step_extraction360", "Extraction 360°"),
    "upscale": ("rail_step_upscale", "Upscale"),
    "reconstruction": ("rail_step_reconstruction", "Reconstruction"),
    "entrainement": ("rail_step_entrainement", "Entraînement"),
    "nettoyage": ("rail_step_nettoyage", "Nettoyage"),
    "export": ("rail_step_export", "Export"),
    "visualiser": ("rail_step_visualiser", "Visualiser"),
}
_TOOL_LABEL_KEYS = {
    "brush": ("rail_tool_brush", "Brush"),
    "sharp": ("rail_tool_sharp", "ML Sharp"),
    "supersplat": ("rail_tool_supersplat", "SuperSplat"),
    "splattransform": ("rail_tool_splattransform", "SplatTransform"),
    "4dgs": ("rail_tool_4dgs", "4DGS"),
}

# Theme colors resolved once at import time. styles.py does not currently
# broadcast a "theme changed" signal that live widgets can subscribe to, so
# this mirrors the same non-reactive approach already used below for
# _ITEM_STYLE's hardcoded selection accent (it only reflects the theme saved
# in config.json at process start, same as the rest of the rail).
_THEME = THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])
_BORDER_COLOR = _THEME["border"]
_MUTED_COLOR = _THEME["muted"]

# Same blue as _ITEM_STYLE's ``:checked`` state below (#7aa2f7 == rgba(122,162,247)).
# Projet's permanent accent intentionally matches this literal rather than the
# live theme accent, so it never drifts from the existing selection color.
_ROOT_ACCENT = "#7aa2f7"

# Style commun des items : alignés à gauche, compacts, minimalistes. La sélection
# et le survol se traduisent par un léger fond (pas de bordure).
_ITEM_STYLE = (
    "QPushButton { text-align: left; padding: 3px 8px; border: none; background: transparent; }"
    "QPushButton:checked { background: rgba(122,162,247,0.20); border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,0.06); border-radius: 4px; }"
)

# Layered on top of _ITEM_STYLE for the "Projet" root item only: permanent
# tinted background + left accent bar, larger/bolder text, regardless of
# checked state. Declarations here are additive on the cascade — properties
# _ITEM_STYLE already sets for ``:checked`` (like border-radius) and are not
# redeclared here keep their base value, so the selection highlight still
# reads clearly against the permanent tint (0.20 vs 0.14 alpha).
_ROOT_EXTRA_STYLE = (
    "QPushButton {"
    " padding-left: 16px; font-weight: 700; font-size: 13px;"
    f" background: rgba(122,162,247,0.14); border-left: 3px solid {_ROOT_ACCENT}; }}"
    "QPushButton:checked {"
    f" background: rgba(122,162,247,0.20); border-left: 3px solid {_ROOT_ACCENT}; }}"
)

# Layered on top of _ITEM_STYLE for OUTILS items: lighter indentation than the
# PARAMÈTRES tree (no dash/trunk to make room for), between Projet's 16px and
# the tree items' ~36px.
_OUTILS_EXTRA_STYLE = "QPushButton { padding-left: 20px; }"

# Vertical trunk connecting PARAMÈTRES items back to Projet.
_TREE_TRUNK_STYLE = f"border: none; border-left: 1px solid {_BORDER_COLOR};"
# Short horizontal dash bridging the trunk to each item row.
_DASH_STYLE = f"border: none; background-color: {_BORDER_COLOR};"
# Full-width rule separating OUTILS from PARAMÈTRES.
_SEPARATOR_STYLE = f"border: none; border-top: 1px solid {_BORDER_COLOR};"
# Static (non-clickable) group label: small caps, muted, no dropdown affordance.
_GROUP_LABEL_STYLE = (
    f"color: {_MUTED_COLOR}; font-size: 10px; font-weight: 700;"
    " letter-spacing: 1px; background: transparent;"
)

# Marqueur d'état préfixé au libellé d'une étape PIPELINE.
_STATUS_MARKER = {
    StepStatus.IDLE: "",
    StepStatus.RUNNING: "⏳ ",
    StepStatus.DONE: "✓ ",
    StepStatus.ERROR: "⛔ ",
}


def item_label(key: str) -> str:
    """Libellé traduit d'un item du rail — étape ou outil, chaîne vide si inconnu.

    Exposé pour la barre d'activité, qui doit nommer l'étape en cours avec
    exactement le même mot que le rail : deux tables de libellés parallèles
    auraient dérivé au premier renommage.
    """
    if key in _STEP_LABEL_KEYS:
        return tr(*_STEP_LABEL_KEYS[key])
    if key in _TOOL_LABEL_KEYS:
        return tr(*_TOOL_LABEL_KEYS[key])
    return ""


class Rail(QWidget):
    """Colonne de navigation gauche. Émet ``itemSelected(key)`` à chaque clic."""

    itemSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}          # key -> QPushButton
        self._status = {}           # step key -> StepStatus
        self._labels = {}           # group id -> (QLabel, (i18n_key, default))
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

        # Un seul groupe exclusif pour toute sélection (14 items).
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        # ── Projet, PARAMÈTRES, OUTILS — toujours visibles, aucun repli ────────
        for spec in _GROUPS:
            self._build_group(spec)

        self._layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.retranslate_ui()

    def _build_group(self, spec):
        """Dispatch to the renderer matching this group's "kind"."""
        kind = spec["kind"]
        if kind == "root":
            self._build_root(spec)
        elif kind == "tree":
            self._build_tree_group(spec)
        elif kind == "separated":
            self._build_separated_group(spec)
        else:
            raise ValueError(f"Unknown rail group kind: {kind!r}")

    def _build_root(self, spec):
        """Build the standalone "Projet" item: permanent accent, no wrapper."""
        (key,) = spec["keys"]
        self._status[key] = StepStatus.IDLE
        btn = self._add_item(key, self._layout)
        btn.setStyleSheet(_ITEM_STYLE + _ROOT_EXTRA_STYLE)

    def _build_tree_group(self, spec):
        """Build a group whose items read as visual children of Projet: a
        continuous vertical trunk on the left, each item joined to it by a
        short horizontal dash (standard file-tree pattern).
        """
        trunk = QFrame()
        trunk.setStyleSheet(_TREE_TRUNK_STYLE)
        trunk_layout = QVBoxLayout(trunk)
        trunk_layout.setContentsMargins(12, 4, 0, 4)
        trunk_layout.setSpacing(2)

        label = QLabel(self)
        label.setStyleSheet(_GROUP_LABEL_STYLE)
        label.setContentsMargins(6, 0, 0, 4)
        trunk_layout.addWidget(label)
        self._labels[spec["id"]] = (label, spec["label"])

        for key in spec["keys"]:
            if key in PIPELINE_STEPS:
                self._status[key] = StepStatus.IDLE
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            dash = QFrame()
            dash.setFixedSize(8, 1)
            dash.setStyleSheet(_DASH_STYLE)
            row_layout.addWidget(dash)
            self._add_item(key, row_layout)
            trunk_layout.addWidget(row)

        self._layout.addWidget(trunk)

    def _build_separated_group(self, spec):
        """Build an independent group (OUTILS): full-width rule, lighter
        indentation, no vertical link back to Projet.
        """
        self._layout.addSpacing(10)
        rule = QFrame()
        rule.setStyleSheet(_SEPARATOR_STYLE)
        rule.setFixedHeight(1)
        self._layout.addWidget(rule)
        self._layout.addSpacing(6)

        label = QLabel(self)
        label.setStyleSheet(_GROUP_LABEL_STYLE)
        label.setContentsMargins(20, 0, 0, 4)
        self._layout.addWidget(label)
        self._labels[spec["id"]] = (label, spec["label"])

        for key in spec["keys"]:
            btn = self._add_item(key, self._layout)
            btn.setStyleSheet(_ITEM_STYLE + _OUTILS_EXTRA_STYLE)

    def _add_item(self, key, layout):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setStyleSheet(_ITEM_STYLE)
        btn.clicked.connect(lambda _checked=False, k=key: self._on_item_clicked(k))
        self._group.addButton(btn)
        self._buttons[key] = btn
        layout.addWidget(btn)
        return btn

    # ── Sélection ─────────────────────────────────────────────────────────────
    def _on_item_clicked(self, key):
        self.itemSelected.emit(key)

    def select(self, key):
        """Sélectionne programmatiquement un item (auto-follow pendant un run)."""
        btn = self._buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    # ── État des étapes ────────────────────────────────────────────────────────
    def set_step_status(self, step: str, status: StepStatus):
        if step not in self._status:
            raise KeyError(f"Étape inconnue: {step}")
        self._status[step] = StepStatus(status)
        self._refresh_step_label(step)

    def _refresh_step_label(self, step):
        key_default = _STEP_LABEL_KEYS[step]
        label = tr(*key_default)
        marker = _STATUS_MARKER.get(self._status[step], "")
        self._buttons[step].setText(f"{marker}{_STEP_ICONS[step]}  {label}")

    def _refresh_group_label(self, group_id):
        label, key_default = self._labels[group_id]
        label.setText(tr(*key_default))

    # ── i18n ───────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        for step in PIPELINE_STEPS:
            self._refresh_step_label(step)
        for key in TOOL_KEYS:
            label = tr(*_TOOL_LABEL_KEYS[key])
            self._buttons[key].setText(f"{_TOOL_ICONS[key]}  {label}")
        for group_id in self._labels:
            self._refresh_group_label(group_id)
