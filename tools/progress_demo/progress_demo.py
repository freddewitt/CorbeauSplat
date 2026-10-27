#!/usr/bin/env python3
"""Live-progress demo: the real engines and widgets, fake COLMAP and Brush.

Runs a short pipeline (extraction → sequential matching with loop detection →
mapper → undistortion → Brush training) through the actual ``ColmapEngine``,
``BrushEngine``, ``PtyProcessRunner``, ``ActivityBar`` and ``ProgressRing``.
Only the two binaries are stand-ins (``fake_colmap.py``, ``fake_brush.py``),
printing the same lines as the real tools, so it needs no GPU and touches no
project. About a minute end to end.

    .venv/bin/python tools/progress_demo/progress_demo.py
    ... --pipe            Brush on a plain pipe, the old behaviour (no bar)
    ... --exhaustive      exhaustive matcher instead of sequential
    ... --snapshots DIR   save a window grab every second, quit when done
"""

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QThread, QTimer, Signal  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.base_engine import SubprocessRunner  # noqa: E402
from app.core.brush_engine import BrushEngine  # noqa: E402
from app.core.engine import ColmapCallbacks, ColmapEngine  # noqa: E402
from app.core.params import ColmapParams  # noqa: E402
from app.gui.activity_bar import ActivityBar  # noqa: E402
from app.gui.styles import set_dark_theme  # noqa: E402
from app.gui.widgets.progress_ring import ProgressRing  # noqa: E402


class DemoPipeline(QThread):
    """Same signal shape as the real workers, so the widgets are wired alike."""
    step_signal = Signal(str)
    log_signal = Signal(str)
    status_signal = Signal(str)
    progress_signal = Signal(float)
    eta_signal = Signal(float)

    def __init__(self, workdir: Path, exhaustive: bool, pipe: bool):
        super().__init__()
        self.workdir, self.exhaustive, self.pipe = workdir, exhaustive, pipe

    def _colmap(self, engine, sub, label):
        cmd = [sys.executable, str(HERE / "fake_colmap.py"), sub]
        return engine.run_command(cmd, label, status_prefix=label)

    def run(self):
        images = self.workdir / "images"
        images.mkdir(parents=True, exist_ok=True)
        for i in range(40):
            (images / f"frame_{i:04d}.jpg").touch()

        params = ColmapParams()
        params.matcher_type = "exhaustive" if self.exhaustive else "sequential"
        engine = ColmapEngine(
            params, str(images), str(self.workdir), "images", 1, "demo",
            ColmapCallbacks(logger=self.log_signal.emit, progress=self.progress_signal.emit,
                            status=self.status_signal.emit),
        )

        # Same phase slices and order as ColmapEngine._run_reconstruction_pipeline.
        self.step_signal.emit("Reconstruction")
        engine._enter_phase(25, 50)
        self._colmap(engine, "feature_extractor", "Analyse")
        loop = params.matcher_type == "sequential"
        engine._enter_phase(50, 75, passes=(0.65, 0.35) if loop else (1.0,))
        self._colmap(engine, f"{params.matcher_type}_matcher", "Comparaison")
        engine._enter_phase(75, 90, expected_images=engine._count_images(images))
        self._colmap(engine, "mapper", "Reconstruction 3D")
        engine._enter_phase(90, 95)
        self._colmap(engine, "image_undistorter", "Correction optique")
        engine._enter_phase(95, 100)
        self.progress_signal.emit(100)

        self.step_signal.emit("Entraînement")
        brush = BrushEngine(
            logger_callback=self.log_signal.emit,
            progress_callback=self._brush_progress,
            process_runner=SubprocessRunner() if self.pipe else None,
        )
        fake = HERE / "fake_brush.py"
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        brush.brush_bin = str(fake)
        out = self.workdir / "checkpoints"
        out.mkdir(exist_ok=True)
        brush.train(str(self.workdir), str(out),
                    {"total_steps": 3000, "checkpoint_interval": 1000, "max_splats": 1_000_000})
        self.progress_signal.emit(100)
        self.log_signal.emit("Demo terminée.")

    def _brush_progress(self, percent, eta):
        # Mirrors BrushWorker._on_live_progress.
        self.progress_signal.emit(min(99.9, percent))
        self.eta_signal.emit(-1.0 if eta is None else float(eta))


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CorbeauSplat — live progress demo")
        self.resize(900, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.ring = ProgressRing()
        top.addWidget(self.ring)
        hint = QLabel("Fake COLMAP + Brush, real engines and widgets.")
        top.addWidget(hint, 1)
        layout.addLayout(top)

        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(400)
        layout.addWidget(self.log, 1)

        self.bar = ActivityBar()
        layout.addWidget(self.bar)

    def wire(self, worker: DemoPipeline):
        worker.step_signal.connect(self.bar.set_step)
        for sig in (worker.log_signal, worker.status_signal):
            sig.connect(self.bar.set_activity)
            sig.connect(self.log.appendPlainText)
        worker.progress_signal.connect(self.bar.set_progress)
        worker.progress_signal.connect(self.ring.set_value)
        worker.eta_signal.connect(self.bar.set_eta)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipe", action="store_true")
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--snapshots", type=Path)
    args = ap.parse_args()

    app = QApplication(sys.argv)
    set_dark_theme(app)
    win = DemoWindow()
    win.show()

    tmp = tempfile.TemporaryDirectory(prefix="corbeau_demo_")
    worker = DemoPipeline(Path(tmp.name), args.exhaustive, args.pipe)
    win.wire(worker)
    win.ring.start()

    if args.snapshots:
        args.snapshots.mkdir(parents=True, exist_ok=True)
        shots = [0]

        def grab():
            shots[0] += 1
            win.grab().save(str(args.snapshots / f"frame_{shots[0]:03d}.png"))

        timer = QTimer(win)
        timer.timeout.connect(grab)
        timer.start(1000)
        worker.finished.connect(lambda: QTimer.singleShot(1200, lambda: (grab(), app.quit())))

    worker.finished.connect(win.ring.stop)
    QTimer.singleShot(400, worker.start)
    code = app.exec()
    worker.wait(5000)
    tmp.cleanup()
    return code


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    sys.exit(main())
