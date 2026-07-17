import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.upscale_widgets import (
    BinaryInstallWorker,
    ModelCard,
    ModelDownloadWorker,
    TestWorker,
)

# ──────────────────────────────────────────────────────────────────────────────
# Main tab
# ──────────────────────────────────────────────────────────────────────────────

class UpscaleTab(QWidget):

    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_cards: dict[str, ModelCard] = {}
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
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #888; font-size: 11px;")
            engine_lay.addWidget(hint)
        else:
            hint = QLabel("\u2705 upscayl-bin is installed. Download models below to use them.")
            hint.setWordWrap(True)
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
            card = ModelCard(model, self._models_dir,
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
        self._install_worker = BinaryInstallWorker()
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

        worker = ModelDownloadWorker(model_id, model.url_bin, model.url_param)
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
        path, _ = get_open_file_name(
            self, "Sélectionner une image source", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp)",
        )
        if path:
            self.edit_test_src.setText(path)

    def _pick_test_src_dir(self):
        path = get_existing_directory(
            self, "Sélectionner un dossier source"
        )
        if path:
            self.edit_test_src.setText(path)

    def _pick_test_dest(self):
        path = get_existing_directory(
            self, "Sélectionner le dossier de destination"
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

        self._test_worker = TestWorker(src, dest, params)
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
