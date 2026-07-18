import contextlib

from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    """Classe de base pour les workers avec signaux standardisés"""
    log_signal = Signal(str)
    progress_signal = Signal(int)
    status_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.stopped_by_user = False
        self.process = None

    def stop(self):
        """Arrêt générique du thread et du processus associé"""
        self.is_running = False
        self.stopped_by_user = True
        if self.process:
            with contextlib.suppress(OSError):
                self.process.terminate()
        self.requestInterruption()

    def parse_line(self, line):
        """A surcharger pour extraire la progression ou des infos spécifiques"""
