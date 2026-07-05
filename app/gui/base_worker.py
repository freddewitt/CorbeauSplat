from PyQt6.QtCore import QThread, pyqtSignal

class BaseWorker(QThread):
    """Classe de base pour les workers avec signaux standardisés"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
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
            try:
                self.process.terminate()
            except OSError:
                pass
        self.requestInterruption()

    def parse_line(self, line):
        """A surcharger pour extraire la progression ou des infos spécifiques"""
