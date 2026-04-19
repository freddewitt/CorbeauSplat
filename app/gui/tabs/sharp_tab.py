from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.scripts.setup_dependencies import install_sharp, uninstall_sharp
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QMessageBox, QProgressDialog, QApplication,
    QRadioButton, QButtonGroup, QStackedWidget, QSpinBox, QProgressBar
)

class SharpTab(QWidget):
    """Onglet de configuration Apple ML Sharp"""
    
    predictRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Engine check for initial state
        from app.core.sharp_engine import SharpEngine
        self.engine = SharpEngine()
        self.is_installed = self.engine.is_installed()

        # Activation / Installation Checkbox
        self.chk_activate = QCheckBox(tr("sharp_activate"))
        self.chk_activate.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        self.chk_activate.setChecked(self.is_installed)
        self.chk_activate.clicked.connect(self.on_toggle_activation)
        layout.addWidget(self.chk_activate)
        
        # Status Label (below Checkbox)
        self.status_lbl = QLabel("") # Will be updated
        layout.addWidget(self.status_lbl)
        self.check_status() # Update text/color
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        self.radio_mode_image = QRadioButton(tr("sharp_mode_image"))
        self.radio_mode_video = QRadioButton(tr("sharp_mode_video"))
        self.radio_mode_image.setChecked(True) # default
        
        mode_layout.addWidget(self.radio_mode_image)
        mode_layout.addWidget(self.radio_mode_video)
        mode_layout.addStretch()
        
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_mode_image, 0)
        self.mode_group.addButton(self.radio_mode_video, 1)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        
        layout.addLayout(mode_layout)

        # Stacked Widget for Modes
        self.stacked_widget = QStackedWidget()
        
        # -----------------------------
        # MODE A: Image -> PLY
        # -----------------------------
        self.page_image = QWidget()
        page_image_layout = QVBoxLayout(self.page_image)
        page_image_layout.setContentsMargins(0, 5, 0, 0)
        
        self.path_group = QGroupBox(tr("sharp_group_paths"))
        path_layout = QVBoxLayout()
        
        self.lbl_input = QLabel(tr("sharp_lbl_input"))
        path_layout.addWidget(self.lbl_input)
        
        input_controls = QHBoxLayout()
        self.input_path = DropLineEdit()
        self.input_path.setPlaceholderText(tr("sharp_placeholder_input"))
        self.btn_browse_input_dir = QPushButton(tr("sharp_btn_folder"))
        self.btn_browse_input_dir.clicked.connect(self.browse_input_dir)
        self.btn_browse_input_file = QPushButton(tr("sharp_btn_file"))
        self.btn_browse_input_file.clicked.connect(self.browse_input_file)
        
        input_controls.addWidget(self.input_path)
        input_controls.addWidget(self.btn_browse_input_dir)
        input_controls.addWidget(self.btn_browse_input_file)
        path_layout.addLayout(input_controls)
        
        self.lbl_output = QLabel(tr("sharp_lbl_output"))
        path_layout.addWidget(self.lbl_output)
        
        output_controls = QHBoxLayout()
        self.output_path = DropLineEdit()
        self.output_path.setPlaceholderText(tr("sharp_placeholder_output"))
        self.btn_browse_output = QPushButton(tr("btn_browse"))
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_controls.addWidget(self.output_path)
        output_controls.addWidget(self.btn_browse_output)
        path_layout.addLayout(output_controls)
        
        self.path_group.setLayout(path_layout)
        page_image_layout.addWidget(self.path_group)
        self.stacked_widget.addWidget(self.page_image)
        
        # -----------------------------
        # MODE B: Video -> PLY
        # -----------------------------
        self.page_video = QWidget()
        page_video_layout = QVBoxLayout(self.page_video)
        page_video_layout.setContentsMargins(0, 5, 0, 0)
        
        self.video_group = QGroupBox(tr("sharp_group_paths"))
        video_layout = QVBoxLayout()
        
        self.lbl_video_input = QLabel(tr("sharp_lbl_video_input"))
        video_layout.addWidget(self.lbl_video_input)
        
        video_input_controls = QHBoxLayout()
        self.video_path = DropLineEdit()
        self.video_path.setPlaceholderText(tr("sharp_placeholder_video_input"))
        self.btn_browse_video_file = QPushButton(tr("btn_browse"))
        self.btn_browse_video_file.clicked.connect(self.browse_video_file)
        
        video_input_controls.addWidget(self.video_path)
        video_input_controls.addWidget(self.btn_browse_video_file)
        video_layout.addLayout(video_input_controls)
        
        self.lbl_video_output = QLabel(tr("sharp_lbl_output"))
        video_layout.addWidget(self.lbl_video_output)
        
        video_output_controls = QHBoxLayout()
        self.video_output_path = DropLineEdit()
        self.video_output_path.setPlaceholderText(tr("sharp_placeholder_output"))
        self.btn_browse_video_output = QPushButton(tr("btn_browse"))
        self.btn_browse_video_output.clicked.connect(self.browse_video_output)
        video_output_controls.addWidget(self.video_output_path)
        video_output_controls.addWidget(self.btn_browse_video_output)
        video_layout.addLayout(video_output_controls)
        
        # Frame skip for video mode
        skip_layout = QHBoxLayout()
        self.lbl_frame_skip = QLabel(tr("sharp_lbl_frame_skip"))
        self.spin_frame_skip = QSpinBox()
        self.spin_frame_skip.setMinimum(1)
        self.spin_frame_skip.setMaximum(100)
        self.spin_frame_skip.setValue(1)
        skip_layout.addWidget(self.lbl_frame_skip)
        skip_layout.addWidget(self.spin_frame_skip)
        skip_layout.addStretch()
        video_layout.addLayout(skip_layout)
        
        self.lbl_frame_skip_desc = QLabel(tr("sharp_tip_frame_skip"))
        self.lbl_frame_skip_desc.setStyleSheet("color: #888888; font-size: 11px;")
        video_layout.addWidget(self.lbl_frame_skip_desc)
        
        self.video_group.setLayout(video_layout)
        page_video_layout.addWidget(self.video_group)
        self.stacked_widget.addWidget(self.page_video)

        layout.addWidget(self.stacked_widget)
        
        # -----------------------------
        # SHARED OPTIONS
        # -----------------------------
        self.opt_group = QGroupBox(tr("group_options"))
        opt_layout = QFormLayout()
        
        # Checkpoint
        ckpt_layout = QHBoxLayout()
        self.ckpt_path = DropLineEdit()
        self.ckpt_path.setPlaceholderText(tr("sharp_placeholder_ckpt"))
        self.btn_browse_ckpt = QPushButton(tr("btn_browse"))
        self.btn_browse_ckpt.clicked.connect(self.browse_ckpt)
        ckpt_layout.addWidget(self.ckpt_path)
        ckpt_layout.addWidget(self.btn_browse_ckpt)
        self.lbl_ckpt = QLabel(tr("sharp_lbl_ckpt"))
        opt_layout.addRow(self.lbl_ckpt, ckpt_layout)
        
        # Device
        self.device_combo = QComboBox()
        self.device_combo.addItems(["default", "mps", "cpu", "cuda"])
        self.device_combo.setMinimumWidth(150)
        self.lbl_device = QLabel(tr("sharp_lbl_device"))
        opt_layout.addRow(self.lbl_device, self.device_combo)
        
        # Verbose
        self.verbose_check = QCheckBox(tr("sharp_check_verbose"))
        opt_layout.addRow("", self.verbose_check)

        self.upscale_check = QCheckBox(tr("upscale_check_sharp"))
        opt_layout.addRow("", self.upscale_check)
        
        self.opt_group.setLayout(opt_layout)
        layout.addWidget(self.opt_group)
        
        # Actions
        action_layout = QHBoxLayout()
        
        self.btn_run = QPushButton(tr("sharp_btn_run"))
        self.btn_run.setMinimumHeight(40)
        self.btn_run.setStyleSheet("background-color: #2a82da; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.predictRequested.emit)
            
        action_layout.addWidget(self.btn_run)
        
        self.btn_stop = QPushButton(tr("btn_stop"))
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        action_layout.addWidget(self.btn_stop)

        layout.addLayout(action_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addStretch()
        
    def on_mode_changed(self, button):
        mode_idx = self.mode_group.id(button)
        self.stacked_widget.setCurrentIndex(mode_idx)
        if mode_idx == 1:
            self.btn_run.setText(tr("sharp_btn_run_video"))
        else:
            self.btn_run.setText(tr("sharp_btn_run"))

    def set_processing_state(self, is_processing):
        self.btn_run.setEnabled(not is_processing)
        self.btn_stop.setEnabled(is_processing)
        self.chk_activate.setEnabled(not is_processing)
        self.radio_mode_image.setEnabled(not is_processing)
        self.radio_mode_video.setEnabled(not is_processing)

        if is_processing:
            self.progress_bar.setValue(0)
            if self.radio_mode_image.isChecked():
                self.progress_bar.setRange(0, 0)  # indeterminate / pulsing
            else:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def browse_input_dir(self):
        path = get_existing_directory(self, tr("sharp_dlg_input_dir"))
        if path:
            self.input_path.setText(path)

    def browse_input_file(self):
        path, _ = get_open_file_name(self, tr("sharp_dlg_input_file"), "", "Images (*.png *.jpg *.jpeg *.tif *.tiff)")
        if path:
            self.input_path.setText(path)
            
    def browse_output(self):
        path = get_existing_directory(self, tr("sharp_dlg_output"))
        if path:
            self.output_path.setText(path)
            
    def browse_video_file(self):
        path, _ = get_open_file_name(self, tr("sharp_dlg_video_file"), "", "Videos (*.mp4 *.mov *.avi *.mkv)")
        if path:
            self.video_path.setText(path)
            
    def browse_video_output(self):
        path = get_existing_directory(self, tr("sharp_dlg_output"))
        if path:
            self.video_output_path.setText(path)
            
    def browse_ckpt(self):
        path, _ = get_open_file_name(self, tr("sharp_dlg_ckpt"), "", "PyTorch Model (*.pt)")
        if path:
            self.ckpt_path.setText(path)

    def check_status(self):
        is_installed = self.engine.is_installed()
        if is_installed:
             self.status_lbl.setText(tr("sharp_status_ready"))
             self.status_lbl.setStyleSheet("color: green;")
        else:
             self.status_lbl.setText(tr("sharp_status_missing"))
             self.status_lbl.setStyleSheet("color: orange;")

    def on_toggle_activation(self):
        if self.chk_activate.isChecked():
            if not self.engine.is_installed():
                reply = QMessageBox.question(
                    self, tr("sharp_install_title"),
                    tr("sharp_install_msg"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.install_sharp_module()
                else:
                    self.chk_activate.setChecked(False)
            else:
                self.enable_controls(True)
        else:
            reply = QMessageBox.question(
                self, tr("sharp_uninstall_title"),
                tr("sharp_uninstall_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.uninstall_sharp_module()
            else:
                self.enable_controls(False) # Just disable UI
                self.chk_activate.setChecked(False) # Uncheck it visually

    def enable_controls(self, enabled):
        self.path_group.setEnabled(enabled)
        self.video_group.setEnabled(enabled)
        self.opt_group.setEnabled(enabled)
        self.btn_run.setEnabled(enabled)

    def install_sharp_module(self):
        progress = QProgressDialog(tr("sharp_status_installing"), None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            success = install_sharp()
            if success:
                QMessageBox.information(self, tr("msg_success"), tr("sharp_msg_install_ok"))
                self.enable_controls(True)
                self.check_status()
            else:
                 QMessageBox.critical(self, tr("msg_error"), tr("sharp_msg_install_err"))
                 self.chk_activate.setChecked(False)
                 self.enable_controls(False)
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error"), f"Exception: {e}")
            self.chk_activate.setChecked(False)
        finally:
            progress.close()

    def uninstall_sharp_module(self):
        progress = QProgressDialog(tr("sharp_status_uninstalling"), None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            success = uninstall_sharp()
            if success:
                 QMessageBox.information(self, tr("msg_success"), tr("sharp_msg_uninstall_ok"))
                 self.enable_controls(False)
                 self.check_status()
        except Exception as e:
             QMessageBox.critical(self, tr("msg_error"), f"Exception: {e}")
        finally:
            progress.close()

    def get_params(self):
        mode = "image" if self.radio_mode_image.isChecked() else "video"
        return {
            "mode": mode,
            "enabled": self.chk_activate.isChecked(),
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "video_path": self.video_path.text(),
            "video_output_path": self.video_output_path.text(),
            "skip_frames": self.spin_frame_skip.value(),
            "checkpoint": self.ckpt_path.text(),
            "device": self.device_combo.currentText(),
            "verbose": self.verbose_check.isChecked(),
            "upscale": self.upscale_check.isChecked()
        }

    def set_params(self, params):
        if not params: return
        
        if "enabled" in params:
             enabled = params["enabled"]
             self.chk_activate.setChecked(enabled)
             self.enable_controls(enabled)
             
        if "mode" in params:
            if params["mode"] == "video":
                self.radio_mode_video.setChecked(True)
                self.stacked_widget.setCurrentIndex(1)
            else:
                self.radio_mode_image.setChecked(True)
                self.stacked_widget.setCurrentIndex(0)
             
        if "input_path" in params: self.input_path.setText(params["input_path"])
        if "output_path" in params: self.output_path.setText(params["output_path"])
        if "video_path" in params: self.video_path.setText(params["video_path"])
        if "video_output_path" in params: self.video_output_path.setText(params["video_output_path"])
        if "skip_frames" in params: self.spin_frame_skip.setValue(params["skip_frames"])
            
        if "checkpoint" in params: self.ckpt_path.setText(params["checkpoint"])
        if "device" in params: self.device_combo.setCurrentText(params["device"])
        if "verbose" in params: self.verbose_check.setChecked(params["verbose"])
        if "upscale" in params: self.upscale_check.setChecked(params["upscale"])

    def get_state(self):
        return self.get_params()
        
    def set_state(self, state):
        self.set_params(state)

    def retranslate_ui(self):
        """Update texts when language changes"""
        self.chk_activate.setText(tr("sharp_activate"))
        self.check_status() # Updates status_lbl text
        
        self.radio_mode_image.setText(tr("sharp_mode_image"))
        self.radio_mode_video.setText(tr("sharp_mode_video"))
        
        self.path_group.setTitle(tr("sharp_group_paths"))
        self.lbl_input.setText(tr("sharp_lbl_input"))
        self.input_path.setPlaceholderText(tr("sharp_placeholder_input"))
        self.btn_browse_input_dir.setText(tr("sharp_btn_folder"))
        self.btn_browse_input_file.setText(tr("sharp_btn_file"))
        
        self.lbl_output.setText(tr("sharp_lbl_output"))
        self.output_path.setPlaceholderText(tr("sharp_placeholder_output"))
        self.btn_browse_output.setText(tr("btn_browse"))
        
        self.video_group.setTitle(tr("sharp_group_paths"))
        self.lbl_video_input.setText(tr("sharp_lbl_video_input"))
        self.video_path.setPlaceholderText(tr("sharp_placeholder_video_input"))
        self.btn_browse_video_file.setText(tr("btn_browse"))
        self.lbl_video_output.setText(tr("sharp_lbl_output"))
        self.video_output_path.setPlaceholderText(tr("sharp_placeholder_output"))
        self.btn_browse_video_output.setText(tr("btn_browse"))
        self.lbl_frame_skip.setText(tr("sharp_lbl_frame_skip"))
        
        frame_skip_tip = tr("sharp_tip_frame_skip")
        self.lbl_frame_skip.setToolTip(frame_skip_tip)
        self.spin_frame_skip.setToolTip(frame_skip_tip)
        if hasattr(self, 'lbl_frame_skip_desc'):
            self.lbl_frame_skip_desc.setText(frame_skip_tip)
        
        self.opt_group.setTitle(tr("group_options"))
        self.lbl_ckpt.setText(tr("sharp_lbl_ckpt"))
        self.ckpt_path.setPlaceholderText(tr("sharp_placeholder_ckpt"))
        self.btn_browse_ckpt.setText(tr("btn_browse"))
        self.lbl_device.setText(tr("sharp_lbl_device"))
        self.verbose_check.setText(tr("sharp_check_verbose"))
        self.upscale_check.setText(tr("upscale_check_sharp"))
        
        # update button run according to mode? well, keep it simple and just let it say "Lancer predict"/"Lancer la conversion".
        # actually, let's keep "sharp_btn_run" for both or separate it.
        # sharp_btn_run works well. The requirement originally said "Bouton Lancer la conversion" for video.
        # But maybe just one single button at the bottom is cleaner.
        if self.radio_mode_video.isChecked():
            self.btn_run.setText(tr("sharp_btn_run_video"))
        else:
            self.btn_run.setText(tr("sharp_btn_run"))
        
        self.btn_stop.setText(tr("btn_stop"))
