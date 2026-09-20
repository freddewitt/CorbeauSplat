import contextlib

from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    """Base class for the workers, with standardised signals"""
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
        """Generic stop of the thread and of the associated process"""
        self.is_running = False
        self.stopped_by_user = True
        if self.process:
            with contextlib.suppress(OSError):
                self.process.terminate()
        self.requestInterruption()

    def parse_line(self, line):
        """To override in order to extract progress or specific information"""
