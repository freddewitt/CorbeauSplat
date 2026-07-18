"""Rail gauche de la fenêtre Studio : sections PIPELINE et OUTILS.

- PIPELINE : 6 étapes (Source → Reconstruction → Entraînement → Nettoyage →
  Export → Visualiser), chacune avec icône + libellé toujours affichés ensemble,
  et un marqueur d'état (coche / activité / erreur) piloté par ``StepStatus``.
- OUTILS : 7 modules indépendants, section repliable **repliée par défaut**.

L'ensemble est dans une ``QScrollArea`` (13 items cumulés → risque de dépassement
vertical sur petit écran, déjà géré ainsi ailleurs dans l'app).

Lot 2 : structure et sélection uniquement, aucun câblage moteur.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, StepStatus
from app.gui.studio_nav import CollapseState

# Modules OUTILS, dans l'ordre du rail.
TOOL_KEYS = ("brush", "sharp", "supersplat", "upscale", "splattransform", "4dgs", "360")

# Icônes minimalistes : glyphes géométriques monochromes (pas d'emoji couleur),
# qui héritent de la couleur du texte. « icône + libellé toujours ensemble ».
_STEP_ICONS = {
    "source": "↧", "reconstruction": "▦", "entrainement": "◆",
    "nettoyage": "◈", "export": "↥", "visualiser": "◉",
}
_TOOL_ICONS = {
    "brush": "◐", "sharp": "◇", "supersplat": "⊙", "upscale": "⤢",
    "splattransform": "⇄", "4dgs": "▷", "360": "◍",
}
_STEP_LABEL_KEYS = {
    "source": ("rail_step_source", "Source"),
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
    "upscale": ("rail_tool_upscale", "Upscale"),
    "splattransform": ("rail_tool_splattransform", "SplatTransform"),
    "4dgs": ("rail_tool_4dgs", "4DGS"),
    "360": ("rail_tool_360", "360 Extractor"),
}

# Style commun des items : alignés à gauche, compacts, minimalistes. La sélection
# et le survol se traduisent par un léger fond (pas de bordure).
_ITEM_STYLE = (
    "QPushButton { text-align: left; padding: 3px 8px; border: none; background: transparent; }"
    "QPushButton:checked { background: rgba(122,162,247,0.20); border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,0.06); border-radius: 4px; }"
)

# Marqueur d'état préfixé au libellé d'une étape PIPELINE.
_STATUS_MARKER = {
    StepStatus.IDLE: "",
    StepStatus.RUNNING: "⏳ ",
    StepStatus.DONE: "✓ ",
    StepStatus.ERROR: "⛔ ",
}


class Rail(QWidget):
    """Colonne de navigation gauche. Émet ``itemSelected(key)`` à chaque clic."""

    itemSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}          # key -> QPushButton
        self._status = {}           # step key -> StepStatus
        self._outils = CollapseState(collapsed=True)
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

        # ── Section PIPELINE ──────────────────────────────────────────────────
        self.lbl_pipeline = QLabel(tr("rail_section_pipeline", "PIPELINE"))
        self._layout.addWidget(self.lbl_pipeline)
        # Un seul groupe exclusif pour toute sélection (13 items).
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key in PIPELINE_STEPS:
            self._status[key] = StepStatus.IDLE
            self._add_item(key, self._layout)

        # ── Section OUTILS (repliable, repliée par défaut) ────────────────────
        self.btn_outils_header = QPushButton()
        self.btn_outils_header.setCheckable(True)
        self.btn_outils_header.setChecked(not self._outils.collapsed)
        self.btn_outils_header.setStyleSheet(_ITEM_STYLE)
        self.btn_outils_header.clicked.connect(self._on_outils_header)
        self._layout.addWidget(self.btn_outils_header)

        self.outils_container = QWidget()
        outils_layout = QVBoxLayout(self.outils_container)
        outils_layout.setContentsMargins(0, 0, 0, 0)
        outils_layout.setSpacing(2)
        for key in TOOL_KEYS:
            self._add_item(key, outils_layout)
        self.outils_container.setVisible(not self._outils.collapsed)
        self._layout.addWidget(self.outils_container)

        self._layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.retranslate_ui()

    def _add_item(self, key, layout):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setStyleSheet(_ITEM_STYLE)
        btn.clicked.connect(lambda _checked=False, k=key: self._on_item_clicked(k))
        self._group.addButton(btn)
        self._buttons[key] = btn
        layout.addWidget(btn)

    # ── Sélection ─────────────────────────────────────────────────────────────
    def _on_item_clicked(self, key):
        self.itemSelected.emit(key)

    def select(self, key):
        """Sélectionne programmatiquement un item (auto-follow pendant un run)."""
        btn = self._buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    # ── Repli/dépli OUTILS ─────────────────────────────────────────────────────
    def _on_outils_header(self):
        self.set_outils_collapsed(not self.btn_outils_header.isChecked())

    def set_outils_collapsed(self, collapsed: bool):
        self._outils.collapsed = bool(collapsed)
        self.outils_container.setVisible(not self._outils.collapsed)
        self.btn_outils_header.setChecked(not self._outils.collapsed)
        self._update_outils_header_text()

    def is_outils_collapsed(self) -> bool:
        return self._outils.collapsed

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

    def _update_outils_header_text(self):
        arrow = "▾" if not self._outils.collapsed else "▸"
        self.btn_outils_header.setText(f"{arrow} " + tr("rail_section_outils", "OUTILS"))

    # ── i18n ───────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.lbl_pipeline.setText(tr("rail_section_pipeline", "PIPELINE"))
        for step in PIPELINE_STEPS:
            self._refresh_step_label(step)
        for key in TOOL_KEYS:
            label = tr(*_TOOL_LABEL_KEYS[key])
            self._buttons[key].setText(f"{_TOOL_ICONS[key]}  {label}")
        self._update_outils_header_text()
