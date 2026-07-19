"""Top bar de la fenêtre Studio.

Nom de projet éditable (miroir du champ Source), pastille de statut moteurs,
dropdown mode pipeline (Gsplat / Sharp / 4DGS), bouton Lancer unique, icône
réglages généraux (ouvre ``SettingsWindow``).

Lot 2 : structure et signaux, aucun câblage moteur.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.core.i18n import add_language_observer, tr

# Modes de pipeline exposés dans le dropdown (valeur interne, clé i18n, défaut).
PIPELINE_MODES = (
    ("gsplat", "mode_gsplat", "Gsplat"),
    ("sharp", "mode_sharp", "Sharp"),
    ("4dgs", "mode_4dgs", "4DGS"),
)


class TopBar(QWidget):
    """Barre supérieure. Émet des signaux de haut niveau (aucune logique métier)."""

    projectNameChanged = Signal(str)
    modeChanged = Signal(str)
    launchRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_project = QLabel(tr("topbar_project", "Projet :"))
        layout.addWidget(self.lbl_project)

        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        self.input_project_name.textChanged.connect(self.projectNameChanged.emit)
        layout.addWidget(self.input_project_name)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        self.lbl_mode = QLabel(tr("topbar_mode", "Mode :"))
        layout.addWidget(self.lbl_mode)
        self.combo_mode = QComboBox()
        for value, key, default in PIPELINE_MODES:
            self.combo_mode.addItem(tr(key, default), value)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.combo_mode)

        self.btn_launch = QPushButton(tr("topbar_launch", "Lancer"))
        self.btn_launch.clicked.connect(self.launchRequested.emit)
        layout.addWidget(self.btn_launch)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        self.btn_settings.clicked.connect(self.settingsRequested.emit)
        layout.addWidget(self.btn_settings)

    def _on_mode_changed(self, index):
        value = self.combo_mode.itemData(index)
        if value:
            self.modeChanged.emit(value)

    def set_running(self, running: bool):
        """Bascule le bouton Lancer ↔ Annuler selon l'état du pipeline."""
        if running:
            self.btn_launch.setText(tr("topbar_cancel", "Annuler"))
            self.btn_launch.setStyleSheet("color: #f7768e;")
        else:
            self.btn_launch.setText(tr("topbar_launch", "Lancer"))
            self.btn_launch.setStyleSheet("")

    def current_mode(self) -> str:
        return self.combo_mode.itemData(self.combo_mode.currentIndex())

    def set_status_text(self, text: str):
        """Met à jour la pastille « X moteurs prêts »."""
        self.lbl_status.setText(text)

    def retranslate_ui(self):
        self.lbl_project.setText(tr("topbar_project", "Projet :"))
        self.lbl_mode.setText(tr("topbar_mode", "Mode :"))
        self.btn_launch.setText(tr("topbar_launch", "Lancer"))
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        for i, (_value, key, default) in enumerate(PIPELINE_MODES):
            self.combo_mode.setItemText(i, tr(key, default))
