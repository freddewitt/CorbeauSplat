import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSpinBox, QMessageBox,
    QProgressDialog, QApplication, QScrollArea, QFrame, QSlider,
    QFileDialog, QSizePolicy,
)

from app.core.i18n import tr, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit


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
            from app.upscayl_manager import run_upscayl, find_binary, resize_to_original
            from app.upscayl_models import get_model
            import shutil as _shutil
            import tempfile as _tempfile

            model_id = self.params.get("model_id", "")
            if not model_id:
                self.finished.emit(False, "Aucun modèle sélectionné.")
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
                # Folder input: collect original sizes for x1 then run directly
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
                # Single file: wrap in a temp folder
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

            self.finished.emit(success[0], self.output_dir if success[0] else "Upscale échoué.")
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
        elif self.model.bundled and not self.model.url_bin:
            # Truly bundled (no separate download URL) — requires reinstalling binary
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

    log_signal = pyqtSignal(str)

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
        else:
            hint = QLabel("✅ upscayl-bin is installed. Download models below to use them.")
            hint.setStyleSheet("color: #44aa44; font-size: 11px;")
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
        self.combo_scale.addItem("x1 (qualité sans changement de résolution)", 1)
        self.combo_scale.addItem("x2", 2)
        self.combo_scale.addItem("x4 (default)", 4)
        self.combo_scale.setCurrentIndex(2)
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
        test_grp = QGroupBox("Upscale")
        test_form = QFormLayout(test_grp)

        # Source (file or folder)
        src_row = QHBoxLayout()
        self.edit_test_src = DropLineEdit()
        self.edit_test_src.setPlaceholderText("Fichier ou dossier source…")
        src_row.addWidget(self.edit_test_src, stretch=1)
        btn_src_file = QPushButton("Fichier")
        btn_src_file.setFixedWidth(70)
        btn_src_file.clicked.connect(self._pick_test_src_file)
        src_row.addWidget(btn_src_file)
        btn_src_dir = QPushButton("Dossier")
        btn_src_dir.setFixedWidth(70)
        btn_src_dir.clicked.connect(self._pick_test_src_dir)
        src_row.addWidget(btn_src_dir)
        test_form.addRow("Source :", src_row)

        # Destination folder
        dest_row = QHBoxLayout()
        self.edit_test_dest = DropLineEdit()
        self.edit_test_dest.setPlaceholderText("Dossier de destination…")
        dest_row.addWidget(self.edit_test_dest, stretch=1)
        btn_dest = QPushButton("Parcourir…")
        btn_dest.setFixedWidth(90)
        btn_dest.clicked.connect(self._pick_test_dest)
        dest_row.addWidget(btn_dest)
        test_form.addRow("Destination :", dest_row)

        # Launch row
        launch_row = QHBoxLayout()
        self.btn_test = QPushButton("Upscale")
        self.btn_test.setMinimumHeight(32)
        self.btn_test.setStyleSheet(
            "background-color: #2a82da; color: white; font-weight: bold; border-radius: 4px;"
        )
        self.btn_test.clicked.connect(self._run_test)
        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setStyleSheet("color: #888; font-size: 11px;")
        launch_row.addWidget(self.btn_test)
        launch_row.addWidget(self.lbl_test_result, stretch=1)
        test_form.addRow("", launch_row)

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
        from app.upscayl_models import MODELS
        self.combo_model.blockSignals(True)
        prev = self.combo_model.currentData()
        self.combo_model.clear()

        for m in MODELS:
            if self._models_dir and m.is_downloaded(self._models_dir):
                self.combo_model.addItem(f"✅ {m.label}", m.id)
            else:
                self.combo_model.addItem(f"⬇️ {m.label} (click Download)", m.id)

        if not self.combo_model.count():
            self.combo_model.addItem("(no models available)", "")

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

    def _pick_test_src_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner une image source", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp)",
        )
        if path:
            self.edit_test_src.setText(path)

    def _pick_test_src_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier source", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self.edit_test_src.setText(path)

    def _pick_test_dest(self):
        path = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier de destination", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self.edit_test_dest.setText(path)

    def _run_test(self):
        from app.upscayl_models import get_model
        src = self.edit_test_src.text().strip()
        dest = self.edit_test_dest.text().strip()

        if not src:
            self.lbl_test_result.setText("⚠ Sélectionnez une source.")
            return
        if not Path(src).exists():
            self.lbl_test_result.setText("⚠ Source introuvable.")
            return
        if not dest:
            self.lbl_test_result.setText("⚠ Sélectionnez un dossier de destination.")
            return

        # Check if model is downloaded
        params = self.get_params()
        model_id = params.get("model_id", "")
        model = get_model(model_id)
        if model and not model.is_downloaded(self._models_dir):
            self.lbl_test_result.setText(f"⚠ Modèle non téléchargé. Cliquez sur Download pour '{model.label}'.")
            return

        self.lbl_test_result.setText("En cours…")
        self.btn_test.setEnabled(False)

        self._test_worker = _TestWorker(src, dest, params)
        self._test_worker.log_signal.connect(self.log_signal)
        self._test_worker.finished.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, success: bool, result: str):
        self.btn_test.setEnabled(True)
        if success:
            self.lbl_test_result.setText("✅ Terminé.")
            subprocess.Popen(["open", result])
        else:
            self.lbl_test_result.setText(f"❌ {result}")

    # ──────────────────────────────────────────── params / state

    def get_params(self) -> dict:
        return {
            "model_id":    self.combo_model.currentData() or "",
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
