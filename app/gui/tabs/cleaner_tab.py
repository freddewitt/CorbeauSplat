"""Onglet de nettoyage des splats (PLY Cleaner)."""
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QMessageBox, QProgressBar, QFormLayout, QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from app.core.ply_cleaner import PRESETS, resolve_params
from app.core.i18n import tr


class CleanerTab(QWidget):
    """Onglet : Charger un .ply → ajuster les seuils → nettoyer → prévisualiser → sauvegarder."""

    cleanRequested = pyqtSignal(str, str, dict)   # input_path, output_path, params
    stopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_input = ""
        self._current_output = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ── Groupe Entrée ────────────────────────────────────────────────────
        input_group = QGroupBox(tr("cleaner_input_group", "Fichier à nettoyer"))
        input_layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton(tr("cleaner_btn_load", "Charger un fichier .ply"))
        self.btn_load.clicked.connect(self._browse_input)
        btn_row.addWidget(self.btn_load)

        self.lbl_input = QLabel(tr("cleaner_no_file", "Aucun fichier chargé"))
        self.lbl_input.setStyleSheet("color: #888;")
        btn_row.addWidget(self.lbl_input, 1)
        input_layout.addLayout(btn_row)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # ── Groupe Paramètres ────────────────────────────────────────────────
        params_group = QGroupBox(tr("cleaner_params_group", "Paramètres de nettoyage"))
        form = QFormLayout(params_group)

        self.combo_strength = QComboBox()
        self.combo_strength.addItem(tr("cleaner_light", "Léger (conserve presque tout)"), "light")
        self.combo_strength.addItem(tr("cleaner_medium", "Moyen (équilibré)"), "medium")
        self.combo_strength.addItem(tr("cleaner_strong", "Fort (supprime le bruit)"), "strong")
        self.combo_strength.currentIndexChanged.connect(self._update_custom)
        form.addRow(tr("cleaner_strength", "Intensité du nettoyage :"), self.combo_strength)

        # Seuils fins (custom)
        self.chk_custom = QCheckBox(tr("cleaner_custom", "Réglages avancés"))
        self.chk_custom.toggled.connect(self._toggle_custom)
        form.addRow(self.chk_custom)

        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.0, 1.0)
        self.spin_opacity.setSingleStep(0.01)
        self.spin_opacity.setValue(0.10)
        self.spin_opacity.setDecimals(3)
        form.addRow(tr("cleaner_opacity", "Opacité minimale (élimine le bruit transparent) :"), self.spin_opacity)

        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(90.0, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setValue(99.5)
        self.spin_scale.setDecimals(1)
        form.addRow(tr("cleaner_scale_pct", "Taille max en % (élimine les splats géants) :"), self.spin_scale)

        self.spin_outlier = QDoubleSpinBox()
        self.spin_outlier.setRange(90.0, 100.0)
        self.spin_outlier.setSingleStep(0.1)
        self.spin_outlier.setValue(99.5)
        self.spin_outlier.setDecimals(1)
        form.addRow(tr("cleaner_outlier_pct", "Distance max en % (élimine les flotteurs isolés) :"), self.spin_outlier)

        self._toggle_custom(False)
        params_group.setLayout(form)
        layout.addWidget(params_group)

        # ── Groupe Sortie ────────────────────────────────────────────────────
        output_group = QGroupBox(tr("cleaner_output_group", "Fichier nettoyé"))
        out_layout = QVBoxLayout()

        out_btn_row = QHBoxLayout()
        self.btn_output = QPushButton(tr("cleaner_btn_output", "Enregistrer sous..."))
        self.btn_output.clicked.connect(self._browse_output)
        out_btn_row.addWidget(self.btn_output)

        self.lbl_output = QLabel(tr("cleaner_no_output", "Aucune destination choisie"))
        self.lbl_output.setStyleSheet("color: #888;")
        out_btn_row.addWidget(self.lbl_output, 1)
        out_layout.addLayout(out_btn_row)

        output_group.setLayout(out_layout)
        layout.addWidget(output_group)

        # ── Bouton d'action ──────────────────────────────────────────────────
        self.btn_clean = QPushButton(tr("cleaner_btn_clean", "Nettoyer le splat"))
        self.btn_clean.setMinimumHeight(50)
        self.btn_clean.setStyleSheet(
            "font-size: 16px; font-weight: bold; background-color: #2a82da; color: white;"
        )
        self.btn_clean.clicked.connect(self._request_clean)
        self.btn_clean.setEnabled(False)
        layout.addWidget(self.btn_clean)

        # ── Progression ──────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ── Résultats ────────────────────────────────────────────────────────
        self.lbl_results = QLabel("")
        self.lbl_results.setWordWrap(True)
        self.lbl_results.setVisible(False)
        layout.addWidget(self.lbl_results)

        layout.addStretch()

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("cleaner_btn_load", "Charger un .ply"),
            "", "PLY (*.ply);;Tous (*)"
        )
        if path:
            self._current_input = path
            self.lbl_input.setText(os.path.basename(path))
            self._update_btn_state()

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("cleaner_btn_output", "Enregistrer sous"),
            "", "PLY (*.ply);;Tous (*)"
        )
        if path:
            if not path.lower().endswith(".ply"):
                path += ".ply"
            self._current_output = path
            self.lbl_output.setText(os.path.basename(path))
            self._update_btn_state()

    def _update_btn_state(self):
        self.btn_clean.setEnabled(
            bool(self._current_input) and bool(self._current_output)
        )

    def _toggle_custom(self, visible):
        self.spin_opacity.setVisible(visible)
        self.spin_scale.setVisible(visible)
        self.spin_outlier.setVisible(visible)

    def _update_custom(self):
        """Met à jour les spin box custom d'après le preset sélectionné."""
        strength = self.combo_strength.currentData()
        p = PRESETS.get(strength, PRESETS["medium"])
        self.spin_opacity.setValue(p["opacity_min"])
        self.spin_scale.setValue(p["scale_pct"])
        self.spin_outlier.setValue(p["outlier_pct"])

    def _request_clean(self):
        """Prépare les paramètres et émet le signal."""
        if self.chk_custom.isChecked():
            overrides = {
                "opacity_min": self.spin_opacity.value(),
                "scale_pct": self.spin_scale.value(),
                "outlier_pct": self.spin_outlier.value(),
            }
            params = resolve_params("medium", overrides)
        else:
            strength = self.combo_strength.currentData()
            params = resolve_params(strength)

        self.cleanRequested.emit(self._current_input, self._current_output, params)

    def get_state(self):
        return {
            "strength": self.combo_strength.currentData(),
            "custom": self.chk_custom.isChecked(),
            "opacity_min": self.spin_opacity.value(),
            "scale_pct": self.spin_scale.value(),
            "outlier_pct": self.spin_outlier.value(),
            "input": self._current_input,
            "output": self._current_output,
        }

    def set_state(self, state):
        if not state:
            return
        if "strength" in state:
            idx = self.combo_strength.findData(state["strength"])
            if idx >= 0:
                self.combo_strength.setCurrentIndex(idx)
        if "custom" in state:
            self.chk_custom.setChecked(state["custom"])
        if "opacity_min" in state:
            self.spin_opacity.setValue(state["opacity_min"])
        if "scale_pct" in state:
            self.spin_scale.setValue(state["scale_pct"])
        if "outlier_pct" in state:
            self.spin_outlier.setValue(state["outlier_pct"])
        if state.get("input"):
            self._current_input = state["input"]
            self.lbl_input.setText(os.path.basename(self._current_input))
        if state.get("output"):
            self._current_output = state["output"]
            self.lbl_output.setText(os.path.basename(self._current_output))
        self._update_btn_state()
