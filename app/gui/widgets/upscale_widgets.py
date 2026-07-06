import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)


class BinaryInstallWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str)

    def run(self):
        try:
            from app.upscayl_manager import download_binary
            download_binary(log_callback=self.log_signal.emit)
            self.finished.emit(True, "upscayl-bin installed.")
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelDownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str, str)

    def __init__(self, model_id: str, url_bin: str, url_param: str):
        super().__init__()
        self.model_id  = model_id
        self.url_bin   = url_bin
        self.url_param = url_param

    def run(self):
        try:
            from app.upscayl_manager import download_model_files
            ok = download_model_files(
                self.url_bin, self.url_param, self.model_id,
                log_callback=self.log_signal.emit
            )
            self.finished.emit(ok, self.model_id,
                               "Downloaded." if ok else "Download failed.")
        except Exception as e:
            self.finished.emit(False, self.model_id, str(e))


class TestWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str)

    def __init__(self, input_path: str, output_dir: str, params: dict):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.params     = params

    def run(self):
        try:
            from app.upscayl_manager import run_upscayl, find_binary, resize_to_original
            from app.upscayl_models import get_model
            import shutil as _shutil
            import tempfile as _tempfile

            model_id = self.params.get("model_id", "")
            if not model_id:
                self.finished.emit(False, "Aucun mod\u00e8le s\u00e9lectionn\u00e9.")
                return
            if not find_binary():
                self.finished.emit(False, "upscayl-bin introuvable.")
                return

            fmt       = self.params.get("format", "png")
            req_scale = self.params.get("scale", 4)
            src       = Path(self.input_path)

            x1_mode = (req_scale == 1)
            if x1_mode:
                m = get_model(model_id)
                actual_scale = m.scale if m else 4
            else:
                actual_scale = req_scale

            upscayl_params = {
                "model_id":    model_id,
                "scale":       actual_scale,
                "format":      fmt,
                "tile":        self.params.get("tile", 0),
                "tta":         self.params.get("tta", False),
                "compression": self.params.get("compression", 0),
            }

            if src.is_dir():
                if x1_mode:
                    from PIL import Image as _PIL
                    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
                    orig_sizes = {}
                    for f in src.iterdir():
                        if f.is_file() and f.suffix.lower() in image_exts:
                            with _PIL.open(f) as im:
                                orig_sizes[f.stem + "." + fmt] = im.size

                success = [False]
                run_upscayl(str(src), self.output_dir, upscayl_params,
                            log_callback=self.log_signal.emit,
                            done_callback=lambda ok: success.__setitem__(0, ok))
                if success[0] and x1_mode:
                    resize_to_original(self.output_dir, orig_sizes)
            else:
                if x1_mode:
                    from PIL import Image as _PIL
                    with _PIL.open(src) as im:
                        orig_sizes = {src.stem + "." + fmt: im.size}

                with _tempfile.TemporaryDirectory(prefix="upscayl_in_") as tmp_in:
                    _shutil.copy2(src, Path(tmp_in) / src.name)
                    success = [False]
                    run_upscayl(tmp_in, self.output_dir, upscayl_params,
                                log_callback=self.log_signal.emit,
                                done_callback=lambda ok: success.__setitem__(0, ok))
                    if success[0] and x1_mode:
                        resize_to_original(self.output_dir, orig_sizes)

            self.finished.emit(success[0], self.output_dir if success[0] else "Upscale \u00e9chou\u00e9.")
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelCard(QFrame):
    download_requested = pyqtSignal(str)
    delete_requested   = pyqtSignal(str)

    def __init__(self, model, models_dir: Path, recommended: bool = False):
        super().__init__()
        self.model      = model
        self.models_dir = models_dir
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        info = QVBoxLayout()
        name = QLabel(f"<b>{self.model.label}</b>")
        desc = QLabel(self.model.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888; font-size: 11px;")
        info.addWidget(name)
        info.addWidget(desc)
        layout.addLayout(info, stretch=1)

        badge = QLabel(f"x{self.model.scale}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(32)
        badge.setStyleSheet(
            "background: #2a82da; color: white; border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 2px 4px;"
        )
        layout.addWidget(badge)

        self.lbl_status = QLabel()
        self.lbl_status.setFixedWidth(120)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.lbl_status)

        self.btn_action = QPushButton()
        self.btn_action.setFixedWidth(90)
        layout.addWidget(self.btn_action)

        self.refresh()

    def refresh(self):
        downloaded = self.model.is_downloaded(self.models_dir)
        if downloaded:
            size = self.model.size_on_disk_mb(self.models_dir)
            self.lbl_status.setText(f"\u2705 {size} MB")
            self.lbl_status.setStyleSheet("color: #44aa44; font-size: 11px;")
            self.btn_action.setText("Delete")
            self.btn_action.setStyleSheet("color: #cc4444;")
            try:
                self.btn_action.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.btn_action.clicked.connect(
                lambda: self.delete_requested.emit(self.model.id)
            )
            self.btn_action.setEnabled(True)
        elif self.model.bundled and not self.model.url_bin:
            self.lbl_status.setText("Bundled")
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText("\u2014")
            self.btn_action.setEnabled(False)
        else:
            self.lbl_status.setText("Not installed")
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText("Download")
            self.btn_action.setStyleSheet("")
            try:
                self.btn_action.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.btn_action.clicked.connect(
                lambda: self.download_requested.emit(self.model.id)
            )
            self.btn_action.setEnabled(True)

    def set_downloading(self, active: bool):
        self.btn_action.setEnabled(not active)
        if active:
            self.lbl_status.setText("Downloading\u2026")
            self.lbl_status.setStyleSheet("color: #2a82da; font-size: 11px;")
