"""Onglet Nettoyage : charge un .ply, le nettoie (floaters/ciel/bruit),
prévisualise dans SuperSplat puis sauvegarde."""
import shutil
import webbrowser
from pathlib import Path
from urllib.parse import quote

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.ply_cleaner import resolve_params
from app.core.superplat_engine import SuperSplatEngine
from app.gui.widgets.dialog_utils import get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class CleanerTab(QWidget):
    """Nettoyage automatique d'un Gaussian Splat (.ply)."""

    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview_engine = SuperSplatEngine()
        self.worker = None
        self.cleaned_path = None
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_info = QLabel(tr(
            "cleaner_info",
            "Nettoie un splat .ply : retire le ciel, les « floaters », les splats "
            "transparents et les points isolés. L'original n'est jamais modifié."
        ))
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        # ── Fichier d'entrée ─────────────────────────────────────────────
        self.file_group = QGroupBox(tr("cleaner_group_file", "Fichier .ply"))
        file_layout = QHBoxLayout()
        self.input_path = DropLineEdit()
        self.input_path.setPlaceholderText(tr("placeholder_ply", "Chemin vers un fichier .ply"))
        self.input_path.fileDropped.connect(lambda p: self.input_path.setText(p.split("|")[0]))
        file_layout.addWidget(self.input_path)
        self.btn_browse = QPushButton(tr("btn_browse"))
        self.btn_browse.clicked.connect(self.browse_input)
        file_layout.addWidget(self.btn_browse)
        self.file_group.setLayout(file_layout)
        layout.addWidget(self.file_group)

        # ── Réglages ─────────────────────────────────────────────────────
        self.settings_group = QGroupBox(tr("cleaner_group_settings", "Réglages de nettoyage"))
        settings_layout = QFormLayout()

        self.combo_strength = QComboBox()
        self.combo_strength.addItem(tr("blur_light", "Léger"), "light")
        self.combo_strength.addItem(tr("blur_medium", "Moyen"), "medium")
        self.combo_strength.addItem(tr("blur_strong", "Fort"), "strong")
        self.combo_strength.setCurrentIndex(1)
        self.combo_strength.currentIndexChanged.connect(self._apply_preset_to_fields)
        self.lbl_strength = QLabel(tr("cleaner_strength", "Sévérité :"))
        settings_layout.addRow(self.lbl_strength, self.combo_strength)

        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.0, 1.0)
        self.spin_opacity.setSingleStep(0.01)
        self.spin_opacity.setDecimals(2)
        self.lbl_opacity = QLabel(tr("cleaner_opacity", "Opacité min :"))
        settings_layout.addRow(self.lbl_opacity, self.spin_opacity)

        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(80.0, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(1)
        self.lbl_scale = QLabel(tr("cleaner_scale", "Taille (percentile gardé) :"))
        settings_layout.addRow(self.lbl_scale, self.spin_scale)

        self.spin_outlier = QDoubleSpinBox()
        self.spin_outlier.setRange(80.0, 100.0)
        self.spin_outlier.setSingleStep(0.1)
        self.spin_outlier.setDecimals(1)
        self.lbl_outlier = QLabel(tr("cleaner_outlier", "Distance (percentile gardé) :"))
        settings_layout.addRow(self.lbl_outlier, self.spin_outlier)

        self.settings_group.setLayout(settings_layout)
        layout.addWidget(self.settings_group)
        self._apply_preset_to_fields()

        # ── Actions ──────────────────────────────────────────────────────
        action_layout = QHBoxLayout()
        self.btn_clean = QPushButton(tr("cleaner_btn_clean", "Analyser & Nettoyer"))
        self.btn_clean.setMinimumHeight(40)
        self.btn_clean.setStyleSheet("background-color: #2a82da; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_clean.clicked.connect(self.run_clean)
        action_layout.addWidget(self.btn_clean)

        self.btn_preview = QPushButton(tr("cleaner_btn_preview", "Prévisualiser"))
        self.btn_preview.setMinimumHeight(40)
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self.preview)
        action_layout.addWidget(self.btn_preview)

        self.btn_save = QPushButton(tr("cleaner_btn_save", "Sauvegarder sous…"))
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_as)
        action_layout.addWidget(self.btn_save)
        layout.addLayout(action_layout)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(self.stats_label)

        layout.addStretch()

    # ── Settings helpers ────────────────────────────────────────────────
    def _apply_preset_to_fields(self):
        params = resolve_params(self.combo_strength.currentData())
        self.spin_opacity.setValue(params["opacity_min"])
        self.spin_scale.setValue(params["scale_pct"])
        self.spin_outlier.setValue(params["outlier_pct"])

    def _overrides(self):
        return {
            "opacity_min": self.spin_opacity.value(),
            "scale_pct": self.spin_scale.value(),
            "outlier_pct": self.spin_outlier.value(),
        }

    # ── Actions ─────────────────────────────────────────────────────────
    def browse_input(self):
        path, _ = get_open_file_name(
            self, tr("select_ply", "Sélectionner un fichier PLY"), "",
            "Gaussian Splat (*.ply);;Tous (*.*)"
        )
        if path:
            self.input_path.setText(path)

    def run_clean(self):
        from app.gui.workers import CleanerWorker

        in_str = self.input_path.text().strip()
        if not in_str:
            QMessageBox.warning(self, tr("msg_warning"), tr("cleaner_no_input", "Sélectionnez un fichier .ply."))
            return
        in_path = Path(in_str)
        if not in_path.exists():
            QMessageBox.critical(self, tr("msg_error"), tr("cleaner_input_missing", "Fichier introuvable."))
            return

        self.cleaned_path = in_path.with_name(f"{in_path.stem}_cleaned.ply")
        self.btn_clean.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.progress.setVisible(True)
        self.stats_label.setText(tr("status_cleaning", "Nettoyage du splat..."))

        self.worker = CleanerWorker(
            str(in_path), str(self.cleaned_path),
            strength=self.combo_strength.currentData(),
            overrides=self._overrides(),
        )
        self.worker.log_signal.connect(self.log_signal.emit)
        self.worker.finished_signal.connect(self.on_clean_done)
        self.worker.start()

    def on_clean_done(self, success, message):
        self.progress.setVisible(False)
        self.btn_clean.setEnabled(True)
        if success and self.worker and self.worker.stats:
            s = self.worker.stats
            pct = (100.0 * s["removed"] / s["total"]) if s["total"] else 0.0
            self.stats_label.setText(
                tr("cleaner_stats", "Résultat :") + "\n"
                + f"  • {s['kept']:,} / {s['total']:,} splats conservés "
                + f"({s['removed']:,} retirés, {pct:.1f} %)\n"
                + f"  • transparence : {s['removed_opacity']:,}   "
                + f"taille : {s['removed_scale']:,}   "
                + f"isolés : {s['removed_outlier']:,}\n"
                + f"  → {self.cleaned_path}"
            )
            self.btn_preview.setEnabled(True)
            self.btn_save.setEnabled(True)
        else:
            self.stats_label.setText(f"❌ {message}")
            QMessageBox.critical(self, tr("msg_error"), message)

    def preview(self):
        if not self.cleaned_path or not self.cleaned_path.exists():
            return
        port, data_port = 3000, 8000
        ok, msg = self.preview_engine.start_supersplat(port)
        if not ok:
            QMessageBox.critical(self, tr("msg_error"), f"SuperSplat: {msg}")
            return
        self.preview_engine.start_data_server(str(self.cleaned_path.parent), data_port)
        data_url = f"http://localhost:{data_port}/{self.cleaned_path.name}"
        url = f"http://localhost:{port}?load={quote(data_url, safe=':/')}"
        QTimer.singleShot(1500, lambda: webbrowser.open(url))
        self.log_signal.emit(tr("cleaner_preview_msg", f"Aperçu : {url}"))

    def save_as(self):
        if not self.cleaned_path or not self.cleaned_path.exists():
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, tr("cleaner_btn_save", "Sauvegarder sous…"),
            str(self.cleaned_path), "Gaussian Splat (*.ply)"
        )
        if not dest:
            return
        try:
            shutil.copy2(str(self.cleaned_path), dest)
            self.log_signal.emit(tr("cleaner_saved", f"Sauvegardé : {dest}"))
            QMessageBox.information(self, tr("msg_success"), f"{dest}")
        except OSError as e:
            QMessageBox.critical(self, tr("msg_error"), str(e))

    def closeEvent(self, event):
        self.preview_engine.stop_all()
        super().closeEvent(event)

    # ── Persistence ─────────────────────────────────────────────────────
    def get_state(self):
        return {
            "input_path": self.input_path.text(),
            "strength": self.combo_strength.currentData(),
        }

    def set_state(self, state):
        if not state:
            return
        if "input_path" in state:
            self.input_path.setText(state["input_path"])
        if "strength" in state:
            idx = self.combo_strength.findData(state["strength"])
            if idx >= 0:
                self.combo_strength.setCurrentIndex(idx)
        self._apply_preset_to_fields()

    def retranslate_ui(self):
        self.lbl_info.setText(tr("cleaner_info"))
        self.file_group.setTitle(tr("cleaner_group_file", "Fichier .ply"))
        self.input_path.setPlaceholderText(tr("placeholder_ply"))
        self.btn_browse.setText(tr("btn_browse"))
        self.settings_group.setTitle(tr("cleaner_group_settings", "Réglages de nettoyage"))
        self.lbl_strength.setText(tr("cleaner_strength", "Sévérité :"))
        self.lbl_opacity.setText(tr("cleaner_opacity", "Opacité min :"))
        self.lbl_scale.setText(tr("cleaner_scale", "Taille (percentile gardé) :"))
        self.lbl_outlier.setText(tr("cleaner_outlier", "Distance (percentile gardé) :"))
        self.btn_clean.setText(tr("cleaner_btn_clean", "Analyser & Nettoyer"))
        self.btn_preview.setText(tr("cleaner_btn_preview", "Prévisualiser"))
        self.btn_save.setText(tr("cleaner_btn_save", "Sauvegarder sous…"))
