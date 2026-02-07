from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QFont
from app.core.i18n import tr, add_language_observer
from app.gui.widgets.dialog_utils import get_save_file_name

class LogsTab(QWidget):
    """Onglet des logs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Monaco", 10))
        layout.addWidget(self.log_text)
        
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton(tr("btn_clear_log"))
        self.btn_clear.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(self.btn_clear)
        
        self.btn_save_log = QPushButton(tr("btn_save_log"))
        self.btn_save_log.clicked.connect(self.save_logs)
        btn_layout.addWidget(self.btn_save_log)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def append_log(self, message):
        """Ajoute au log"""
        self.log_text.append(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        
    def clear_log(self):
        self.log_text.clear()
        
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
                QMessageBox.information(self, tr("msg_success"), "Logs sauvegardes!")
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error"), f"Impossible de sauvegarder:\n{str(e)}")

    def retranslate_ui(self):
        """Update texts when language changes"""
        self.btn_clear.setText(tr("btn_clear_log"))
        self.btn_save_log.setText(tr("btn_save_log"))
