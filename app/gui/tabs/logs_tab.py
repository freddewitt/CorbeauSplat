from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.widgets.dialog_utils import get_save_file_name


class LogsTab(QWidget):
    """Onglet des logs"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Barre de recherche (cachée par défaut)
        self.search_container = QWidget()
        search_layout = QHBoxLayout(self.search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search logs...")
        search_layout.addWidget(self.search_input)

        self.btn_find_next = QPushButton("▼")
        self.btn_find_next.setToolTip("Find next")
        self.btn_find_next.clicked.connect(self._find_next)
        search_layout.addWidget(self.btn_find_next)

        self.btn_find_prev = QPushButton("▲")
        self.btn_find_prev.setToolTip("Find previous")
        self.btn_find_prev.clicked.connect(self._find_prev)
        search_layout.addWidget(self.btn_find_prev)

        self.search_container.setVisible(False)
        layout.addWidget(self.search_container)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monaco", 10))
        layout.addWidget(self.log_text)

        # Suivi du scroll pour verrouiller l'auto-scroll
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)

        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton(tr("btn_clear_log"))
        self.btn_clear.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(self.btn_clear)

        self.btn_copy_log = QPushButton(tr("btn_copy_log"))
        self.btn_copy_log.clicked.connect(self.copy_logs)
        btn_layout.addWidget(self.btn_copy_log)

        self.btn_save_log = QPushButton(tr("btn_save_log"))
        self.btn_save_log.clicked.connect(self.save_logs)
        btn_layout.addWidget(self.btn_save_log)

        self.btn_search = QPushButton(tr("btn_search"))
        self.btn_search.setCheckable(True)
        self.btn_search.clicked.connect(self.toggle_search)
        btn_layout.addWidget(self.btn_search)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _find_next(self):
        text = self.search_input.text()
        if text:
            self.log_text.find(text)

    def _find_prev(self):
        text = self.search_input.text()
        if text:
            self.log_text.find(text, QTextEdit.FindFlag.FindBackward)

    def toggle_search(self):
        self.search_container.setVisible(self.btn_search.isChecked())
        if self.btn_search.isChecked():
            self.search_input.setFocus()

    def _on_scroll_changed(self, value):
        scrollbar = self.log_text.verticalScrollBar()
        self._auto_scroll = value >= scrollbar.maximum() - 1

    def append_log(self, message):
        """Ajoute au log"""
        self.log_text.append(message)
        if self._auto_scroll:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def clear_log(self):
        self.log_text.clear()

    def copy_logs(self):
        """Copie les logs dans le presse-papiers"""
        QApplication.clipboard().setText(self.log_text.toPlainText())

    def save_logs(self):
        """Sauvegarde les logs"""
        filename, _ = get_save_file_name(
            self, tr("btn_save_log"),
            "", "Fichier texte (*.txt);;Tous (*.*)"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, tr("msg_success"), tr("logs_saved", "Logs sauvegardés !"))
            except OSError as e:
                QMessageBox.critical(self, tr("msg_error"), f"{tr('err_save_log', 'Impossible de sauvegarder')}:\n{e}")

    def retranslate_ui(self):
        """Update texts when language changes"""
        self.btn_clear.setText(tr("btn_clear_log"))
        self.btn_copy_log.setText(tr("btn_copy_log"))
        self.btn_save_log.setText(tr("btn_save_log"))
        self.btn_search.setText(tr("btn_search"))
