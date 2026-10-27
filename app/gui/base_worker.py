import contextlib

from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    """Base class for the workers, with standardised signals"""
    log_signal = Signal(str)
    # float: COLMAP and Brush now report sub-percent steps (int emits still work)
    progress_signal = Signal(float)
    # Seconds left in the current step, or -1 when unknown. Only Brush emits it.
    eta_signal = Signal(float)
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
