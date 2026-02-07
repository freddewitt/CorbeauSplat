from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
import os

class BaseWorker(QThread):
    """Classe de base pour les workers avec signaux standardisés"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.is_running = True
        self.process = None
        
    def stop(self):
        """Arrêt générique du thread et du processus associé"""
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                # On ne fait pas wait() ici car on veut que l'interface reste réactive
                # Le thread se terminera de lui-même quand run() s'arrêtera
            except:
                pass
        self.requestInterruption()
        
    def run_subprocess(self, cmd, cwd=None, env=None, log_prefix=""):
        """Méthode utilitaire pour exécuter un sous-processus et capturer ses logs"""
        try:
            # Fusionner l'env
            actual_env = os.environ.copy()
            if env:
                actual_env.update(env)
            
            self.log_signal.emit(f"Exécution commande: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=cwd,
                env=actual_env,
                bufsize=1,
                universal_newlines=True
            )
            
            for line in self.process.stdout:
                if not self.is_running or self.isInterruptionRequested():
                    self.log_signal.emit("Processus arrêté par l'utilisateur.")
                    self.process.terminate()
                    break
                
                clean_line = line.strip()
                if clean_line:
                    self.log_signal.emit(f"{log_prefix}{clean_line}")
                    self.parse_line(clean_line)
                    
            self.process.wait()
            return self.process.returncode == 0
        except Exception as e:
            self.log_signal.emit(f"Erreur CRITIQUE lors du lancement du processus : {e}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            return False

    def parse_line(self, line):
        """A surcharger pour extraire la progression ou des infos spécifiques"""
        pass
