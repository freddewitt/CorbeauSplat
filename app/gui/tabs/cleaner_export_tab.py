"""Onglet de nettoyage PLY standalone (fichier unique ou batch)."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QScrollArea, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal

from app.gui.tabs.cleaner_tab import CleanerTab
from app.gui.workers import CleanerWorker
from app.core.i18n import tr


class CleanerExportTab(QWidget):
    """Onglet de nettoyage PLY : fichier unique ou batch, sans export intégré.

    L'export est géré par l'onglet SplatTransform.
    Le nettoyage post-entraînement est géré par le post-traitement de BrushTab.
    """

    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cleaner_worker = None
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.cleaner_tab = CleanerTab()
        scroll.setWidget(self.cleaner_tab)
        outer.addWidget(scroll)

    def _connect_signals(self):
        self.cleaner_tab.cleanRequested.connect(self._on_clean_requested)
        self.cleaner_tab.stopRequested.connect(self._stop_cleaner)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_clean_requested(self, input_path, output_path, params, recursive):
        self.cleaner_tab.progress_bar.setVisible(True)
        self.cleaner_tab.progress_bar.setRange(0, 0)
        self.cleaner_tab.lbl_results.setVisible(False)
        self.cleaner_tab.btn_clean.setEnabled(False)

        self.log_signal.emit(f"Nettoyage PLY : {input_path} → {output_path}")

        self._cleaner_worker = CleanerWorker(
            input_path, output_path, params, recursive=recursive
        )
        self._cleaner_worker.log_signal.connect(self.log_signal.emit)
        self._cleaner_worker.finished_signal.connect(self._on_clean_finished)
        self._cleaner_worker.start()

    def _stop_cleaner(self):
        if self._cleaner_worker and self._cleaner_worker.isRunning():
            self._cleaner_worker.stop()
            self.log_signal.emit(tr("cleaner_stop_requested", "Arrêt du nettoyage demandé…"))

    def _on_clean_finished(self, success, message):
        self.cleaner_tab.progress_bar.setVisible(False)
        self.cleaner_tab.btn_clean.setEnabled(True)
        self.log_signal.emit(message)
        self.cleaner_tab.lbl_results.setText(message)
        self.cleaner_tab.lbl_results.setVisible(True)

        if success:
            QMessageBox.information(self, tr("msg_success"), message)
        else:
            QMessageBox.warning(self, tr("msg_error"), message)

    # ── State persistence ─────────────────────────────────────────────────────

    def get_state(self):
        return {"cleaner": self.cleaner_tab.get_state()}

    def set_state(self, state):
        if state and "cleaner" in state:
            self.cleaner_tab.set_state(state["cleaner"])
