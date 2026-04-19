import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSpinBox, QMessageBox,
    QProgressDialog, QApplication, QScrollArea, QFrame, QSlider,
    QFileDialog, QSizePolicy,
)

from app.core.i18n import tr, add_language_observer


# ──────────────────────────────────────────────────────────────────────────────
# Background workers
# ──────────────────────────────────────────────────────────────────────────────

class _BinaryInstallWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str)   # success, message

    def run(self):
        try:
            from app.upscayl_manager import download_binary
            download_binary(log_callback=self.log_signal.emit)
            self.finished.emit(True, "upscayl-bin installed.")
        except Exception as e:
            self.finished.emit(False, str(e))


class _ModelDownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str, str)   # success, model_id, message

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


class _TestWorker(QThread):
    log_signal = pyqtSignal(str)
    finished   = pyqtSignal(bool, str)

    def __init__(self, input_path: str, output_dir: str, params: dict):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.params     = params

    def run(self):
        try:
            from app.core.upscale_engine import UpscaleEngine
            engine = UpscaleEngine(logger_callback=self.log_signal.emit)
            fmt = self.params.get("format", "png")
            model = engine.load_model(
                model_id=self.params.get("model_id", "realesrgan-x4plus"),
                scale=self.params.get("scale", 4),
                output_format=fmt,
                tile=self.params.get("tile", 0),
                tta=self.params.get("tta", False),
                compression=self.params.get("compression", 0),
            )
            if not model:
                self.finished.emit(False, "Could not load model.")
                return
            input_path = Path(self.input_path)
            output_path = Path(self.output_dir) / (input_path.stem + "." + fmt)
            success = engine.upscale_image(self.input_path, output_path, model)
            self.finished.emit(success, self.output_dir if success else "Test failed.")
        except Exception as e:
            self.finished.emit(False, str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Model card widget
# ──────────────────────────────────────────────────────────────────────────────

class _ModelCard(QFrame):
    download_requested = pyqtSignal(str)   # model_id
    delete_requested   = pyqtSignal(str)   # model_id

    def __init__(self, model, models_dir: Path, recommended: bool = False):
        super().__init__()
        self.model      = model
        self.models_dir = models_dir
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        # Left: name + description
        info = QVBoxLayout()
        name = QLabel(f"<b>{self.model.label}</b>")
        desc = QLabel(self.model.description)
        desc.setStyleSheet("color: #888; font-size: 11px;")
        info.addWidget(name)
        info.addWidget(desc)
        layout.addLayout(info, stretch=1)

        # Scale badge
        badge = QLabel(f"x{self.model.scale}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(32)
        badge.setStyleSheet(
            "background: #2a82da; color: white; border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 2px 4px;"
        )
        layout.addWidget(badge)

        # Status + actions
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
            self.lbl_status.setText(f"✅ {size} MB")
            self.lbl_status.setStyleSheet("color: #44aa44; font-size: 11px;")
            self.btn_action.setText("Delete")
            self.btn_action.setStyleSheet("color: #cc4444;")
            try:
                self.btn_action.clicked.disconnect()
            except TypeError:
                pass
            self.btn_action.clicked.connect(
                lambda: self.delete_requested.emit(self.model.id)
            )
            self.btn_action.setEnabled(True)
        elif self.model.bundled:
            self.lbl_status.setText("Bundled")
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText("—")
            self.btn_action.setEnabled(False)
        else:
            self.lbl_status.setText("Not installed")
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText("Download")
            self.btn_action.setStyleSheet("")
            try:
                self.btn_action.clicked.disconnect()
            except Exception:
                pass
            self.btn_action.clicked.connect(
                lambda: self.download_requested.emit(self.model.id)
            )
            self.btn_action.setEnabled(True)

    def set_downloading(self, active: bool):
        self.btn_action.setEnabled(not active)
        if active:
            self.lbl_status.setText("Downloading…")
            self.lbl_status.setStyleSheet("color: #2a82da; font-size: 11px;")


# ──────────────────────────────────────────────────────────────────────────────
# Main tab
# ──────────────────────────────────────────────────────────────────────────────

class UpscaleTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_cards: dict[str, _ModelCard] = {}
        self._active_workers: list[QThread] = []
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    # ──────────────────────────────────────────── build UI

    def init_ui(self):
        from app.upscayl_manager import find_binary, get_effective_models_dir, get_models_dir
        from app.upscayl_models import MODELS

        self._models_dir = get_effective_models_dir() or get_models_dir()

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Engine status ─────────────────────────────────────────────────
        engine_grp = QGroupBox("Engine")
        engine_lay = QVBoxLayout(engine_grp)

        binary = find_binary()
        status_row = QHBoxLayout()
        self.lbl_binary_status = QLabel()
        self._update_binary_status(binary)
        status_row.addWidget(self.lbl_binary_status, stretch=1)

        self.btn_reinstall = QPushButton("Reinstall")
        self.btn_reinstall.setToolTip("Force re-download of upscayl-bin from GitHub")
        self.btn_reinstall.clicked.connect(self._install_binary)
        status_row.addWidget(self.btn_reinstall)

        engine_lay.addLayout(status_row)

        if binary is None:
            hint = QLabel("upscayl-bin will be installed automatically on next launch.")
            hint.setStyleSheet("color: #888; font-size: 11px;")
            engine_lay.addWidget(hint)

        root.addWidget(engine_grp)

        # ── Models list ───────────────────────────────────────────────────
        models_grp = QGroupBox("Models")
        models_outer = QVBoxLayout(models_grp)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(280)

        container = QWidget()
        self._model_list_layout = QVBoxLayout(container)
        self._model_list_layout.setSpacing(4)
        self._model_list_layout.setContentsMargins(0, 0, 0, 0)

        for model in MODELS:
            card = _ModelCard(model, self._models_dir,
                              recommended=False)
            card.download_requested.connect(self._download_model)
            card.delete_requested.connect(self._delete_model)
            self._model_cards[model.id] = card
            self._model_list_layout.addWidget(card)

        self._model_list_layout.addStretch()
        scroll.setWidget(container)
        models_outer.addWidget(scroll)
        root.addWidget(models_grp)

        # ── Configuration ─────────────────────────────────────────────────
        config_grp = QGroupBox("Configuration")
        config_lay = QFormLayout(config_grp)

        # Active model
        self.combo_model = QComboBox()
        self._refresh_model_combo()
        self.lbl_model = QLabel("Active Model:")
        config_lay.addRow(self.lbl_model, self.combo_model)

        # Scale
        self.combo_scale = QComboBox()
        self.combo_scale.addItem("x1 (denoise only)", 1)
        self.combo_scale.addItem("x2", 2)
        self.combo_scale.addItem("x3", 3)
        self.combo_scale.addItem("x4 (default)", 4)
        self.combo_scale.setCurrentIndex(3)
        self.lbl_scale = QLabel("Output Scale:")
        config_lay.addRow(self.lbl_scale, self.combo_scale)

        # Format
        self.combo_format = QComboBox()
        self.combo_format.addItem("PNG (lossless)", "png")
        self.combo_format.addItem("JPEG", "jpg")
        self.combo_format.addItem("WebP", "webp")
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        self.lbl_format = QLabel("Output Format:")
        config_lay.addRow(self.lbl_format, self.combo_format)

        # Compression (JPG/WebP only)
        compression_row = QHBoxLayout()
        self.slider_compression = QSlider(Qt.Orientation.Horizontal)
        self.slider_compression.setRange(0, 100)
        self.slider_compression.setValue(80)
        self.lbl_compression_val = QLabel("80")
        self.slider_compression.valueChanged.connect(
            lambda v: self.lbl_compression_val.setText(str(v))
        )
        compression_row.addWidget(self.slider_compression)
        compression_row.addWidget(self.lbl_compression_val)
        self.lbl_compression = QLabel("Compression:")
        self.compression_widget = QWidget()
        self.compression_widget.setLayout(compression_row)
        self.compression_widget.setVisible(False)
        config_lay.addRow(self.lbl_compression, self.compression_widget)

        # Tile size
        self.spin_tile = QSpinBox()
        self.spin_tile.setRange(0, 4096)
        self.spin_tile.setValue(0)
        self.spin_tile.setSpecialValueText("Auto (0)")
        self.spin_tile.setSuffix(" px")
        self.lbl_tile = QLabel("Tile Size:")
        config_lay.addRow(self.lbl_tile, self.spin_tile)

        # TTA
        self.chk_tta = QCheckBox("TTA mode  ⚠ Slow but better quality")
        config_lay.addRow("", self.chk_tta)

        root.addWidget(config_grp)

        # ── Quick test ────────────────────────────────────────────────────
        test_grp = QGroupBox("Quick Test")
        test_lay = QVBoxLayout(test_grp)

        # Destination folder row
        dest_row = QHBoxLayout()
        self.lbl_test_dest = QLabel("Dossier de sortie :")
        dest_row.addWidget(self.lbl_test_dest)
        self.lbl_test_dest_path = QLabel("(dossier temporaire)")
        self.lbl_test_dest_path.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_test_dest_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        dest_row.addWidget(self.lbl_test_dest_path, stretch=1)
        self.btn_test_dest = QPushButton("Parcourir…")
        self.btn_test_dest.setFixedWidth(90)
        self.btn_test_dest.clicked.connect(self._pick_test_dest)
        dest_row.addWidget(self.btn_test_dest)
        self._test_output_dir: str | None = None
        test_lay.addLayout(dest_row)

        # Launch row
        launch_row = QHBoxLayout()
        self.btn_test = QPushButton("Tester sur une image…")
        self.btn_test.clicked.connect(self._run_test)
        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setStyleSheet("color: #888; font-size: 11px;")
        launch_row.addWidget(self.btn_test)
        launch_row.addWidget(self.lbl_test_result, stretch=1)
        test_lay.addLayout(launch_row)

        root.addWidget(test_grp)

        root.addStretch()

    # ──────────────────────────────────────────── helpers

    def _update_binary_status(self, binary):
        from app.upscayl_manager import get_version
        if binary:
            ver = get_version(binary)
            self.lbl_binary_status.setText(f"✅  {binary}  —  {ver}")
            self.lbl_binary_status.setStyleSheet("color: #44aa44;")
        else:
            self.lbl_binary_status.setText("⚠️  upscayl-bin not found")
            self.lbl_binary_status.setStyleSheet("color: #cc6600; font-weight: bold;")

    def _refresh_model_combo(self):
        from app.upscayl_manager import find_binary, is_using_local_binary
        from app.upscayl_models import MODELS
        self.combo_model.blockSignals(True)
        prev = self.combo_model.currentData()
        self.combo_model.clear()

        binary_present = find_binary() is not None
        local_binary   = is_using_local_binary()

        for m in MODELS:
            locally_downloaded = m.is_downloaded(self._models_dir) if self._models_dir else False
            # Bundled models are available when any binary is present
            # (system/app install has them built-in; local install extracts them)
            available = locally_downloaded or (m.bundled and binary_present)
            if available:
                self.combo_model.addItem(m.label, m.id)

        if not self.combo_model.count():
            self.combo_model.addItem("(install upscayl-bin first)", "")

        idx = self.combo_model.findData(prev)
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
        self.combo_model.blockSignals(False)

    def _on_format_changed(self):
        fmt = self.combo_format.currentData()
        self.compression_widget.setVisible(fmt in ("jpg", "webp"))

    # ──────────────────────────────────────────── binary install

    def _install_binary(self):
        reply = QMessageBox.question(
            self, "Reinstall upscayl-bin",
            "Download the latest upscayl-bin release for macOS arm64?\n"
            "Bundled models will also be extracted to ./models/upscayl/.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_reinstall.setEnabled(False)
        self._install_worker = _BinaryInstallWorker()
        self._install_worker.finished.connect(self._on_binary_installed)
        self._install_worker.start()

    def _on_binary_installed(self, success: bool, msg: str):
        self.btn_reinstall.setEnabled(True)
        from app.upscayl_manager import find_binary
        binary = find_binary()
        self._update_binary_status(binary)
        if success:
            self._refresh_all_cards()
            self._refresh_model_combo()
            QMessageBox.information(self, tr("msg_success"), msg)
        else:
            QMessageBox.critical(self, tr("msg_error"), msg)

    # ──────────────────────────────────────────── model download / delete

    def _download_model(self, model_id: str):
        from app.upscayl_models import get_model
        model = get_model(model_id)
        if not model or not model.url_bin:
            QMessageBox.warning(self, tr("msg_warning"),
                                tr("upscale_bundled_warning",
                                   "This model is bundled with the binary.\nInstall upscayl-bin first."))
            return

        card = self._model_cards.get(model_id)
        if card:
            card.set_downloading(True)

        worker = _ModelDownloadWorker(model_id, model.url_bin, model.url_param)
        worker.finished.connect(self._on_model_downloaded)
        self._active_workers.append(worker)
        worker.start()

    def _on_model_downloaded(self, success: bool, model_id: str, msg: str):
        card = self._model_cards.get(model_id)
        if card:
            card.refresh()
        self._refresh_model_combo()
        if not success:
            QMessageBox.warning(self, tr("msg_error"), msg)

    def _delete_model(self, model_id: str):
        reply = QMessageBox.question(
            self, "Delete model",
            f"Delete model '{model_id}'? (.bin and .param files will be removed)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for ext in (".bin", ".param"):
            f = self._models_dir / f"{model_id}{ext}"
            f.unlink(missing_ok=True)
        card = self._model_cards.get(model_id)
        if card:
            card.refresh()
        self._refresh_model_combo()

    def _refresh_all_cards(self):
        for card in self._model_cards.values():
            card.refresh()

    # ──────────────────────────────────────────── quick test

    def _pick_test_dest(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sortie du test", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._test_output_dir = folder
            # Truncate long paths for display
            display = folder if len(folder) <= 60 else "…" + folder[-57:]
            self.lbl_test_dest_path.setText(display)
            self.lbl_test_dest_path.setStyleSheet("color: #ddd; font-size: 11px;")
        else:
            self._test_output_dir = None
            self.lbl_test_dest_path.setText("(dossier temporaire)")
            self.lbl_test_dest_path.setStyleSheet("color: #888; font-size: 11px;")

    def _run_test(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner une image de test", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp)"
        )
        if not path:
            return

        if self._test_output_dir:
            out_dir = self._test_output_dir
        else:
            import tempfile
            out_dir = tempfile.mkdtemp(prefix="upscayl_test_")

        self.lbl_test_result.setText("En cours…")
        self.btn_test.setEnabled(False)

        self._test_worker = _TestWorker(path, out_dir, self.get_params())
        self._test_worker.finished.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, success: bool, result: str):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_result.setText(f"✅ Saved to {result}")
            subprocess.Popen(["open", result])
        else:
            self.lbl_test_result.setText(f"❌ {result}")

    # ──────────────────────────────────────────── params / state

    def get_params(self) -> dict:
        return {
            "model_id":    self.combo_model.currentData() or "realesrgan-x4plus",
            "scale":       self.combo_scale.currentData() or 4,
            "format":      self.combo_format.currentData() or "png",
            "tile":        self.spin_tile.value(),
            "tta":         self.chk_tta.isChecked(),
            "compression": self.slider_compression.value(),
        }

    def set_params(self, params: dict):
        if not params:
            return
        idx = self.combo_model.findData(params.get("model_id", ""))
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
        idx = self.combo_scale.findData(params.get("scale", 4))
        if idx >= 0:
            self.combo_scale.setCurrentIndex(idx)
        idx = self.combo_format.findData(params.get("format", "png"))
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)
        if "tile" in params:
            self.spin_tile.setValue(params["tile"])
        if "tta" in params:
            self.chk_tta.setChecked(params["tta"])
        if "compression" in params:
            self.slider_compression.setValue(params["compression"])

    def get_state(self) -> dict:
        return self.get_params()

    def set_state(self, state: dict):
        self.set_params(state)

    # ──────────────────────────────────────────── i18n (minimal, uses fallbacks)

    def retranslate_ui(self):
        pass
