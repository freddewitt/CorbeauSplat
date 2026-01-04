from PyQt6.QtCore import QThread, pyqtSignal

class BaseWorker(QThread):
    """Classe de base pour les workers"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.is_running = True
        
    def stop(self):
        """Arrêt générique"""
        self.is_running = False
        self.requestInterruption()
        # Override dans les enfants pour arrêter les processus spécifiques
        self.wait()
