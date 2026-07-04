"""Onglet de nettoyage des splats (PLY Cleaner)."""
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QDoubleSpinBox,
    QMessageBox, QProgressBar, QFormLayout, QCheckBox,
)
from app.gui.widgets.dialog_utils import (
    get_open_file_name, get_existing_directory, get_save_file_name,
)
from PyQt6.QtCore import pyqtSignal, Qt

from app.core.ply_cleaner import PRESETS, resolve_params
from app.core.i18n import tr


class CleanerTab(QWidget):
    """Onglet : Charger un .ply / dossier → ajuster les seuils → nettoyer."""

    cleanRequested = pyqtSignal(str, str, dict, bool)   # input_path, output_path, params, recursive
    stopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_input = ""
        self._current_output = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ── Mode ─────────────────────────────────────────────────────────────
        mode_group = QGroupBox(tr("cleaner_mode_group", "Mode"))
        mode_layout = QVBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(tr("cleaner_mode_single", "Fichier unique"), "single")
        self.combo_mode.addItem(tr("cleaner_mode_batch", "Dossier (tous les .ply)"), "batch")
        self.combo_mode.currentIndexChanged.connect(self._toggle_mode)
        mode_layout.addWidget(self.combo_mode)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # ── Groupe Entrée ────────────────────────────────────────────────────
        self.input_group = QGroupBox(tr("cleaner_input_group", "Fichier à nettoyer"))
        input_layout = QVBoxLayout()

        # Mode fichier unique
        self.single_input_widget = QWidget()
        single_row = QHBoxLayout(self.single_input_widget)
        single_row.setContentsMargins(0, 0, 0, 0)
        self.btn_load = QPushButton(tr("cleaner_btn_load", "Charger un fichier .ply"))
        self.btn_load.clicked.connect(self._browse_input)
        single_row.addWidget(self.btn_load)
        self.lbl_input = QLabel(tr("cleaner_no_file", "Aucun fichier chargé"))
        self.lbl_input.setStyleSheet("color: #888;")
        single_row.addWidget(self.lbl_input, 1)
        input_layout.addWidget(self.single_input_widget)

        # Mode dossier
        self.dir_input_widget = QWidget()
        dir_row = QHBoxLayout(self.dir_input_widget)
        dir_row.setContentsMargins(0, 0, 0, 0)
        self.btn_load_dir = QPushButton(tr("cleaner_btn_load_dir", "Choisir un dossier..."))
        self.btn_load_dir.clicked.connect(self._browse_input_dir)
        dir_row.addWidget(self.btn_load_dir)
        self.lbl_input_dir = QLabel(tr("cleaner_no_dir", "Aucun dossier choisi"))
        self.lbl_input_dir.setStyleSheet("color: #888;")
        dir_row.addWidget(self.lbl_input_dir, 1)
        self.dir_input_widget.setVisible(False)
        input_layout.addWidget(self.dir_input_widget)

        # Récursif (mode dossier)
        self.chk_recursive = QCheckBox(tr("cleaner_recursive", "Parcourir les sous-dossiers"))
        self.chk_recursive.setVisible(False)
        input_layout.addWidget(self.chk_recursive)

        self.input_group.setLayout(input_layout)
        layout.addWidget(self.input_group)

        # ── Groupe Paramètres ────────────────────────────────────────────────
        params_group = QGroupBox(tr("cleaner_params_group", "Paramètres"))
        form = QFormLayout(params_group)

        self.combo_strength = QComboBox()
        self.combo_strength.addItem(tr("cleaner_light", "Léger (conserve presque tout)"), "light")
        self.combo_strength.addItem(tr("cleaner_medium", "Moyen (équilibré)"), "medium")
        self.combo_strength.addItem(tr("cleaner_strong", "Fort (supprime le bruit)"), "strong")
        self.combo_strength.currentIndexChanged.connect(self._update_custom)
        form.addRow(tr("cleaner_strength", "Intensité :"), self.combo_strength)

        # Seuils fins (custom)
        self.chk_custom = QCheckBox(tr("cleaner_custom", "Réglages avancés"))
        self.chk_custom.toggled.connect(self._toggle_custom)
        form.addRow(self.chk_custom)

        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.0, 1.0)
        self.spin_opacity.setSingleStep(0.01)
        self.spin_opacity.setValue(0.10)
        self.spin_opacity.setDecimals(3)
        form.addRow(tr("cleaner_opacity", "Opacité mini :"), self.spin_opacity)

        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(90.0, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setValue(99.5)
        self.spin_scale.setDecimals(1)
        form.addRow(tr("cleaner_scale_pct", "Taille max (%) :"), self.spin_scale)

        self.spin_outlier = QDoubleSpinBox()
        self.spin_outlier.setRange(90.0, 100.0)
        self.spin_outlier.setSingleStep(0.1)
        self.spin_outlier.setValue(99.5)
        self.spin_outlier.setDecimals(1)
        form.addRow(tr("cleaner_outlier_pct", "Distance max (%) :"), self.spin_outlier)

        self._toggle_custom(False)
        params_group.setLayout(form)
        layout.addWidget(params_group)

        # ── Groupe Sortie ────────────────────────────────────────────────────
        self.output_group = QGroupBox(tr("cleaner_output_group", "Destination"))
        out_layout = QVBoxLayout()

        # Sortie fichier unique
        self.single_output_widget = QWidget()
        single_out_row = QHBoxLayout(self.single_output_widget)
        single_out_row.setContentsMargins(0, 0, 0, 0)
        self.btn_output = QPushButton(tr("cleaner_btn_output", "Enregistrer sous..."))
        self.btn_output.clicked.connect(self._browse_output)
        single_out_row.addWidget(self.btn_output)
        self.lbl_output = QLabel(tr("cleaner_no_output", "Aucune destination choisie"))
        self.lbl_output.setStyleSheet("color: #888;")
        single_out_row.addWidget(self.lbl_output, 1)
        out_layout.addWidget(self.single_output_widget)

        # Sortie dossier
        self.dir_output_widget = QWidget()
        dir_out_row = QHBoxLayout(self.dir_output_widget)
        dir_out_row.setContentsMargins(0, 0, 0, 0)
        self.btn_output_dir = QPushButton(tr("cleaner_btn_output_dir", "Dossier de destination..."))
        self.btn_output_dir.clicked.connect(self._browse_output_dir)
        dir_out_row.addWidget(self.btn_output_dir)
        self.lbl_output_dir = QLabel(tr("cleaner_no_output_dir", "Aucun dossier choisi"))
        self.lbl_output_dir.setStyleSheet("color: #888;")
        dir_out_row.addWidget(self.lbl_output_dir, 1)
        self.dir_output_widget.setVisible(False)
        out_layout.addWidget(self.dir_output_widget)

        self.output_group.setLayout(out_layout)
        layout.addWidget(self.output_group)

        # ── Bouton d'action ──────────────────────────────────────────────────
        self.btn_clean = QPushButton(tr("cleaner_btn_clean", "Nettoyer"))
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

    def _toggle_mode(self):
        """Bascule entre mode fichier unique et mode dossier."""
        is_batch = self.combo_mode.currentData() == "batch"
        self.single_input_widget.setVisible(not is_batch)
        self.dir_input_widget.setVisible(is_batch)
        self.chk_recursive.setVisible(is_batch)
        self.single_output_widget.setVisible(not is_batch)
        self.dir_output_widget.setVisible(is_batch)

        # Update group titles
        if is_batch:
            self.input_group.setTitle(tr("cleaner_input_dir_group", "Dossier source"))
            self.output_group.setTitle(tr("cleaner_output_dir_group", "Dossier destination"))
        else:
            self.input_group.setTitle(tr("cleaner_input_group", "Fichier à nettoyer"))
            self.output_group.setTitle(tr("cleaner_output_group", "Destination"))

        self._update_btn_state()

    def _browse_input(self):
        path, _ = get_open_file_name(
            self, tr("cleaner_btn_load", "Charger un .ply"),
            "", "PLY (*.ply);;Tous (*)"
        )
        if path:
            self._current_input = path
            self.lbl_input.setText(os.path.basename(path))
            self._update_btn_state()

    def _browse_input_dir(self):
        path = get_existing_directory(
            self, tr("cleaner_btn_load_dir", "Choisir un dossier contenant des .ply")
        )
        if path:
            self._current_input = path
            self.lbl_input_dir.setText(path)
            self._update_btn_state()

    def _browse_output(self):
        path, _ = get_save_file_name(
            self, tr("cleaner_btn_output", "Enregistrer sous"),
            "", "PLY (*.ply);;Tous (*)"
        )
        if path:
            if not path.lower().endswith(".ply"):
                path += ".ply"
            self._current_output = path
            self.lbl_output.setText(os.path.basename(path))
            self._update_btn_state()

    def _browse_output_dir(self):
        path = get_existing_directory(
            self, tr("cleaner_btn_output_dir", "Choisir le dossier de destination")
        )
        if path:
            self._current_output = path
            self.lbl_output_dir.setText(path)
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

        recursive = self.chk_recursive.isChecked() if self.combo_mode.currentData() == "batch" else False
        self.cleanRequested.emit(self._current_input, self._current_output, params, recursive)

    def get_state(self):
        return {
            "mode": self.combo_mode.currentData(),
            "strength": self.combo_strength.currentData(),
            "custom": self.chk_custom.isChecked(),
            "opacity_min": self.spin_opacity.value(),
            "scale_pct": self.spin_scale.value(),
            "outlier_pct": self.spin_outlier.value(),
            "input": self._current_input,
            "output": self._current_output,
            "recursive": self.chk_recursive.isChecked(),
        }

    def set_state(self, state):
        if not state:
            return
        if "mode" in state:
            idx = self.combo_mode.findData(state["mode"])
            if idx >= 0:
                self.combo_mode.setCurrentIndex(idx)
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
            if self.combo_mode.currentData() == "batch":
                self.lbl_input_dir.setText(self._current_input)
            else:
                self.lbl_input.setText(os.path.basename(self._current_input))
        if state.get("output"):
            self._current_output = state["output"]
            if self.combo_mode.currentData() == "batch":
                self.lbl_output_dir.setText(self._current_output)
            else:
                self.lbl_output.setText(os.path.basename(self._current_output))
        if "recursive" in state:
            self.chk_recursive.setChecked(state["recursive"])
        self._update_btn_state()
