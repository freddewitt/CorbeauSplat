"""Onglet composite : Nettoyage + Export avec chaînage optionnel."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QFrame,
    QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, Qt

from app.gui.tabs.cleaner_tab import CleanerTab
from app.gui.tabs.export_tab import ExportTab
from app.gui.workers import CleanerWorker
from app.core.i18n import tr


class CleanerExportTab(QWidget):
    """Onglet combinant nettoyage et export avec chaînage optionnel."""

    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cleaner_worker = None
        self._last_clean_success = False
        self._last_clean_output = None
        self._last_clean_was_batch = False
        self.init_ui()
        self._connect_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Section Nettoyage ─────────────────────────────────────────────
        cleaner_wrapper = QWidget()
        cleaner_layout = QVBoxLayout(cleaner_wrapper)
        cleaner_layout.setContentsMargins(0, 0, 0, 0)

        self.cleaner_tab = CleanerTab()
        cleaner_layout.addWidget(self.cleaner_tab)

        # Bouton Envoyer vers Export
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_send_to_export = QPushButton(
            tr("cleaner_btn_send_to_export", "Envoyer vers Export")
        )
        self.btn_send_to_export.setEnabled(False)
        self.btn_send_to_export.setMinimumHeight(36)
        self.btn_send_to_export.setStyleSheet(
            "font-size: 14px; font-weight: bold; "
            "background-color: #2a82da; color: white; border-radius: 4px;"
        )
        self.btn_send_to_export.clicked.connect(self._send_to_export)
        btn_row.addWidget(self.btn_send_to_export)
        cleaner_layout.addLayout(btn_row)

        # Ligne de séparation
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        cleaner_layout.addWidget(sep)

        splitter.addWidget(cleaner_wrapper)

        # ── Section Export ────────────────────────────────────────────────
        export_wrapper = QWidget()
        export_layout = QVBoxLayout(export_wrapper)
        export_layout.setContentsMargins(0, 0, 0, 0)

        self.export_tab = ExportTab()
        export_layout.addWidget(self.export_tab)

        splitter.addWidget(export_wrapper)

        # Set initial sizes (60% cleaner, 40% export)
        splitter.setSizes([500, 300])

        layout.addWidget(splitter)

    def _connect_signals(self):
        """Connecte les signaux internes."""
        self.cleaner_tab.cleanRequested.connect(self._on_clean_requested)
        self.cleaner_tab.stopRequested.connect(self._stop_cleaner)
        self.export_tab.log_signal.connect(self.log_signal.emit)

    def _on_clean_requested(self, input_path, output_path, params, recursive):
        """Lance le nettoyage dans un thread, géré par le composite tab."""
        self.btn_send_to_export.setEnabled(False)
        self._last_clean_success = False
        self._last_clean_output = None

        # UI : état "en cours"
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

        self._last_clean_was_batch = self.cleaner_tab.combo_mode.currentData() == "batch"

    def _stop_cleaner(self):
        """Arrête le nettoyage en cours."""
        if self._cleaner_worker and self._cleaner_worker.isRunning():
            self._cleaner_worker.stop()
            self.log_signal.emit("Arrêt du nettoyage demandé...")

    def _on_clean_finished(self, success, message):
        """Fin du nettoyage — met à jour l'UI et active le bouton si succès."""
        self.cleaner_tab.progress_bar.setVisible(False)
        self.cleaner_tab.btn_clean.setEnabled(True)
        self.log_signal.emit(message)
        self.cleaner_tab.lbl_results.setText(message)
        self.cleaner_tab.lbl_results.setVisible(True)

        if success:
            self._last_clean_success = True
            self._last_clean_output = self.cleaner_tab._current_output
            self.btn_send_to_export.setEnabled(True)
            QMessageBox.information(self, tr("msg_success"), message)
        else:
            self._last_clean_success = False
            self._last_clean_output = None
            QMessageBox.warning(self, tr("msg_error"), message)

    def _send_to_export(self):
        """Transfère le(s) fichier(s) nettoyé(s) vers la section Export."""
        if not self._last_clean_output:
            return

        output = Path(self._last_clean_output)

        if self._last_clean_was_batch:
            if output.is_dir():
                ply_files = sorted(output.glob("*.ply"))
                if not ply_files:
                    QMessageBox.information(
                        self,
                        tr("msg_info"),
                        tr("cleaner_no_ply_in_output",
                           "Aucun fichier .ply trouvé dans le dossier de sortie.")
                    )
                    return
                for ply_file in ply_files:
                    self.export_tab.add_file(str(ply_file))
                self.log_signal.emit(
                    f"{len(ply_files)} fichier(s) .ply transféré(s) vers l'export."
                )
            else:
                self.export_tab.add_file(str(output))
        else:
            self.export_tab.add_file(str(output))

        self.btn_send_to_export.setEnabled(False)
        self.log_signal.emit(
            tr("cleaner_sent_to_export", "Fichier(s) envoyé(s) vers l'export.")
        )

    def get_state(self):
        """État combiné pour la persistance de session."""
        return {
            "cleaner": self.cleaner_tab.get_state(),
        }

    def set_state(self, state):
        if not state:
            return
        if "cleaner" in state:
            self.cleaner_tab.set_state(state["cleaner"])
