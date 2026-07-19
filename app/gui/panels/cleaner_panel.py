"""Panneau Nettoyage (étape PIPELINE, optionnelle) — équivalent de CleanerTab.

Centre : mode (fichier unique / batch), sélection PLY, dossier/fichier de sortie.
Barre de droite : intensité (Léger/Moyen/Fort) + réglages avancés
(opacity_min, scale_pct, outlier_pct). Réutilise ``resolve_params`` /
``PRESETS`` de ``ply_cleaner`` (moteur inchangé).

Lot 4 : UI + params. Le lancement réel (CleanerWorker) passe par le dispatch
orchestré / le bouton local (câblage moteurs, phase Apple Silicon).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.ply_cleaner import resolve_params
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit

_STRENGTHS = (("light", "Léger"), ("medium", "Moyen"), ("strong", "Fort"))


class CleanerPanel:
    """Panneau plain exposant ``center`` et ``right``."""

    def __init__(self, run_state):
        self.run_state = run_state
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        mode_row = QHBoxLayout()
        self.lbl_mode = QLabel()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("", "single")
        self.combo_mode.addItem("", "batch")
        mode_row.addWidget(self.lbl_mode)
        mode_row.addWidget(self.combo_mode)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = DropLineEdit()
        in_row.addWidget(self.input_path)
        self.btn_browse_input = QPushButton("📁")
        self.btn_browse_input.clicked.connect(self._browse_input)
        in_row.addWidget(self.btn_browse_input)
        layout.addLayout(in_row)

        self.lbl_output = QLabel()
        layout.addWidget(self.lbl_output)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addLayout(out_row)

        layout.addStretch(1)

        self.btn_run = QPushButton()
        self.btn_run.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.btn_run)
        return w

    def _build_right(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.combo_strength = QComboBox()
        for value, _label in _STRENGTHS:
            self.combo_strength.addItem(value, value)
        self.combo_strength.setCurrentIndex(1)  # medium
        self.lbl_strength = QLabel()
        form.addRow(self.lbl_strength, self.combo_strength)
        layout.addLayout(form)

        self.advanced_group = QGroupBox()
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        ag = QFormLayout(self.advanced_group)
        ag.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.0, 1.0)
        self.spin_opacity.setSingleStep(0.01)
        self.spin_opacity.setDecimals(3)
        self.spin_opacity.setValue(0.10)
        self.lbl_opacity = QLabel()
        ag.addRow(self.lbl_opacity, self.spin_opacity)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(90.0, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(1)
        self.spin_scale.setValue(99.5)
        self.lbl_scale = QLabel()
        ag.addRow(self.lbl_scale, self.spin_scale)
        self.spin_outlier = QDoubleSpinBox()
        self.spin_outlier.setRange(90.0, 100.0)
        self.spin_outlier.setSingleStep(0.1)
        self.spin_outlier.setDecimals(1)
        self.spin_outlier.setValue(99.5)
        self.lbl_outlier = QLabel()
        ag.addRow(self.lbl_outlier, self.spin_outlier)
        layout.addWidget(self.advanced_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def is_batch(self):
        return self.combo_mode.currentData() == "batch"

    def get_params(self):
        """Retourne les paramètres de nettoyage résolus (preset ou surcharges)."""
        strength = self.combo_strength.currentData()
        if self.advanced_group.isChecked():
            overrides = {
                "opacity_min": self.spin_opacity.value(),
                "scale_pct": self.spin_scale.value(),
                "outlier_pct": self.spin_outlier.value(),
            }
            return resolve_params(strength, overrides)
        return resolve_params(strength)

    def get_state(self):
        return {
            "mode": self.combo_mode.currentData(),
            "strength": self.combo_strength.currentData(),
            "advanced": self.advanced_group.isChecked(),
            "opacity_min": self.spin_opacity.value(),
            "scale_pct": self.spin_scale.value(),
            "outlier_pct": self.spin_outlier.value(),
        }

    def set_state(self, state):
        if not state:
            return
        if state.get("mode"):
            idx = self.combo_mode.findData(state["mode"])
            if idx >= 0:
                self.combo_mode.setCurrentIndex(idx)
        if state.get("strength"):
            idx = self.combo_strength.findData(state["strength"])
            if idx >= 0:
                self.combo_strength.setCurrentIndex(idx)
        self.advanced_group.setChecked(state.get("advanced", False))
        if "opacity_min" in state:
            self.spin_opacity.setValue(state["opacity_min"])
        if "scale_pct" in state:
            self.spin_scale.setValue(state["scale_pct"])
        if "outlier_pct" in state:
            self.spin_outlier.setValue(state["outlier_pct"])

    def _browse_input(self):
        if self.is_batch():
            path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        else:
            path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"), "", "PLY (*.ply)")
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def retranslate_ui(self):
        self.lbl_mode.setText(tr("cleaner_mode", "Mode"))
        self.combo_mode.setItemText(0, tr("cleaner_mode_single", "Fichier unique"))
        self.combo_mode.setItemText(1, tr("cleaner_mode_batch", "Dossier (batch)"))
        self.lbl_input.setText(tr("cleaner_input", "Fichier / dossier PLY"))
        self.lbl_output.setText(tr("cleaner_output", "Sortie nettoyée"))
        self.lbl_strength.setText(tr("cleaner_strength", "Intensité"))
        self.advanced_group.setTitle(tr("cleaner_advanced", "Réglages avancés"))
        self.lbl_opacity.setText(tr("cleaner_opacity", "Opacité mini"))
        self.lbl_scale.setText(tr("cleaner_scale_pct", "Taille max (%)"))
        self.lbl_outlier.setText(tr("cleaner_outlier_pct", "Outliers (%)"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
