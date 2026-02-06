import os
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import pyqtSignal

class DropLineEdit(QLineEdit):
    """
    A QLineEdit that accepts file drops.
    Emits fileDropped(str) signal when a valid path is dropped.
    """
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                paths = []
                for url in urls:
                    path = url.toLocalFile()
                    if path:
                        paths.append(path)
                
                if paths:
                    # Join multiple paths with a pipe separator
                    joined_paths = "|".join(paths)
                    self.setText(joined_paths)
                    self.fileDropped.emit(joined_paths)
                    event.acceptProposedAction()
        else:
            super().dropEvent(event)
