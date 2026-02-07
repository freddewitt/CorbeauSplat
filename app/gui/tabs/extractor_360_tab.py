from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, 
    QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

from app.core.i18n import tr, add_language_observer
from app.core.extractor_360_engine import Extractor360Engine
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name

class InstallWorker(QThread):
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, engine, install=True):
        super().__init__()
        self.engine = engine
        self.install_mode = install
        
    def run(self):
        try:
            if self.install_mode:
                self.engine.install()
                self.finished_signal.emit(True, tr("360_msg_install_ok"))
            else:
                self.engine.uninstall()
                self.finished_signal.emit(True, tr("360_msg_uninstall_ok"))
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class Extractor360Tab(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = Extractor360Engine()
        self.install_worker = None
        self.init_ui()
        self.update_ui_state()
        add_language_observer(self.retranslate_ui)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        self.lbl_header = QLabel(tr("360_header"))
        self.lbl_header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.lbl_header)
        
        self.lbl_desc = QLabel(tr("360_desc"))
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #888; margin-bottom: 15px;")
        layout.addWidget(self.lbl_desc)
        
        # Activation
        self.check_activate = QCheckBox(tr("360_activate"))
        self.check_activate.clicked.connect(self.on_activate_clicked)
        layout.addWidget(self.check_activate)
        
        # Params Group
        self.group_params = QGroupBox(tr("360_group_params"))
        param_layout = QVBoxLayout(self.group_params)
        
        # Interval
        h_interval = QHBoxLayout()
        self.lbl_interval = QLabel(tr("360_lbl_interval"))
        h_interval.addWidget(self.lbl_interval)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setValue(1.0)
        self.spin_interval.setSingleStep(0.1)
        self.spin_interval.setToolTip(tr("360_tip_interval"))
        h_interval.addWidget(self.spin_interval)
        param_layout.addLayout(h_interval)
        
        # Resolution
        h_res = QHBoxLayout()
        self.lbl_res = QLabel(tr("360_lbl_resolution"))
        h_res.addWidget(self.lbl_res)
        self.spin_res = QSpinBox()
        self.spin_res.setRange(512, 8192)
        self.spin_res.setValue(2048)
        self.spin_res.setSingleStep(256)
        self.spin_res.setToolTip(tr("360_tip_res"))
        h_res.addWidget(self.spin_res)
        param_layout.addLayout(h_res)
        
        # Layout
        h_layout = QHBoxLayout()
        self.lbl_layout = QLabel(tr("360_lbl_layout"))
        h_layout.addWidget(self.lbl_layout)
        self.combo_layout = QComboBox()
        self.combo_layout.addItem(tr("360_layout_ring"), "ring")
        self.combo_layout.addItem(tr("360_layout_cube"), "cube")
        self.combo_layout.addItem(tr("360_layout_fib"), "fibonacci")
        self.combo_layout.setToolTip(tr("360_tip_layout"))
        h_layout.addWidget(self.combo_layout)
        param_layout.addLayout(h_layout)
        
        # Camera Count
        h_cam = QHBoxLayout()
        self.lbl_cam = QLabel(tr("360_lbl_cameras"))
        h_cam.addWidget(self.lbl_cam)
        self.spin_cam = QSpinBox()
        self.spin_cam.setRange(1, 24)
        self.spin_cam.setValue(6)
        self.spin_cam.setToolTip(tr("360_tip_cameras"))
        h_cam.addWidget(self.spin_cam)
        param_layout.addLayout(h_cam)
        
        # Quality
        h_qua = QHBoxLayout()
        self.lbl_quality = QLabel(tr("360_lbl_quality"))
        h_qua.addWidget(self.lbl_quality)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(95)
        self.spin_quality.setToolTip(tr("360_tip_quality"))
        h_qua.addWidget(self.spin_quality)
        param_layout.addLayout(h_qua)
        
        # Format
        h_fmt = QHBoxLayout()
        self.lbl_format = QLabel(tr("360_lbl_format"))
        h_fmt.addWidget(self.lbl_format)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["jpg", "png"])
        self.combo_format.setToolTip(tr("360_tip_format"))
        h_fmt.addWidget(self.combo_format)
        param_layout.addLayout(h_fmt)
        
        layout.addWidget(self.group_params)
        
        # AI Group
        self.group_ai = QGroupBox(tr("360_group_ai"))
        ai_layout = QVBoxLayout(self.group_ai)
        
        self.check_ai_mask = QCheckBox(tr("360_check_ai_mask"))
        self.check_ai_mask.setToolTip(tr("360_tip_ai_mask"))
        ai_layout.addWidget(self.check_ai_mask)
        
        self.check_ai_skip = QCheckBox(tr("360_check_ai_skip"))
        self.check_ai_skip.setToolTip(tr("360_tip_ai_skip"))
        ai_layout.addWidget(self.check_ai_skip)
        
        self.check_adaptive = QCheckBox(tr("360_check_adaptive"))
        self.check_adaptive.setToolTip(tr("360_tip_adaptive"))
        ai_layout.addWidget(self.check_adaptive)
        
        h_thresh = QHBoxLayout()
        self.lbl_threshold = QLabel(tr("360_lbl_threshold"))
        h_thresh.addWidget(self.lbl_threshold)
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.01, 1.0)
        self.spin_threshold.setValue(0.5)
        self.spin_threshold.setSingleStep(0.05)
        self.spin_threshold.setToolTip(tr("360_tip_threshold"))
        h_thresh.addWidget(self.spin_threshold)
        ai_layout.addLayout(h_thresh)
        
        layout.addWidget(self.group_ai)
        
        # Standalone Extraction Group
        self.group_standalone = QGroupBox(tr("360_btn_extract_only"))
        standalone_layout = QVBoxLayout(self.group_standalone)
        
        # Input Path
        input_layout = QHBoxLayout()
        self.lbl_input = QLabel(tr("360_lbl_input"))
        input_layout.addWidget(self.lbl_input)
        self.input_edit = DropLineEdit()
        input_layout.addWidget(self.input_edit)
        self.btn_browse_input = QPushButton(tr("btn_browse"))
        self.btn_browse_input.clicked.connect(self.browse_video)
        input_layout.addWidget(self.btn_browse_input)
        standalone_layout.addLayout(input_layout)
        
        # Output Path
        output_layout = QHBoxLayout()
        self.lbl_output = QLabel(tr("360_lbl_output"))
        output_layout.addWidget(self.lbl_output)
        self.output_edit = DropLineEdit()
        output_layout.addWidget(self.output_edit)
        self.btn_browse_output = QPushButton(tr("btn_browse"))
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.btn_browse_output)
        standalone_layout.addLayout(output_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        standalone_layout.addWidget(self.progress_bar)
        
        # Action Button
        self.btn_extract = QPushButton(tr("360_btn_extract_only"))
        self.btn_extract.setFixedHeight(40)
        self.btn_extract.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_extract.clicked.connect(self.run_standalone_extraction)
        standalone_layout.addWidget(self.btn_extract)
        
        layout.addWidget(self.group_standalone)
        
        # Status
        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)
        
        layout.addStretch()

    def browse_video(self):
        file, _ = get_open_file_name(self, tr("360_lbl_input"), "", "Videos (*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV);;Tous (*.*)")
        if file:
            self.input_edit.setText(file)

    def browse_output(self):
        d = get_existing_directory(self, tr("360_lbl_output"))
        if d:
            self.output_edit.setText(d)

    def run_standalone_extraction(self):
        input_path = self.input_edit.text()
        output_dir = self.output_edit.text()
        
        if not input_path or not output_dir:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_paths"))
            return
            
        self.set_processing_state(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        from app.gui.workers import Extractor360Worker
        self.extract_worker = Extractor360Worker()
        self.extract_worker.engine = self.engine
        self.extract_worker.input_path = input_path
        self.extract_worker.output_path = output_dir
        self.extract_worker.params = self.get_params()
        
        self.extract_worker.progress_signal.connect(self.progress_bar.setValue)
        self.extract_worker.finished_signal.connect(self.on_extraction_finished)
        self.extract_worker.start()

    def on_extraction_finished(self, success, message):
        self.set_processing_state(False)
        self.progress_bar.setVisible(False)
        if success:
            QMessageBox.information(self, tr("msg_success"), tr("360_msg_success"))
        else:
            QMessageBox.critical(self, tr("msg_error"), message)

    def set_processing_state(self, is_processing):
        self.btn_extract.setEnabled(not is_processing)
        self.group_params.setDisabled(is_processing)
        self.group_ai.setDisabled(is_processing)
        self.check_activate.setDisabled(is_processing)
        if is_processing:
            self.btn_extract.setText(tr("msg_processing"))
        else:
            self.btn_extract.setText(tr("360_btn_extract_only"))
        
    def update_ui_state(self):
        installed = self.engine.is_installed()
        
        # Block signals to prevent recursion if we changed checks programmatically
        self.check_activate.blockSignals(True)
        self.check_activate.setChecked(installed)
        self.check_activate.blockSignals(False)
        
        self.group_params.setEnabled(installed)
        self.group_ai.setEnabled(installed)
        
        if installed:
            self.lbl_status.setText(tr("360_status_ready"))
            self.lbl_status.setStyleSheet("color: green;")
        else:
            self.lbl_status.setText(tr("360_status_missing"))
            self.lbl_status.setStyleSheet("color: gray;")

    def on_activate_clicked(self):
        current_state = self.check_activate.isChecked() # State AFTER click
        installed = self.engine.is_installed()
        
        if current_state and not installed:
            # User wants to activate -> Install
            reply = QMessageBox.question(
                self, 
                tr("msg_warning"), 
                tr("360_install_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_install(True)
            else:
                self.check_activate.setChecked(False) # Revert
                
        elif not current_state and installed:
            # User wants to deactivate -> Uninstall?
            reply = QMessageBox.question(
                self, 
                tr("msg_warning"),
                tr("360_uninstall_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_install(False)
            else:
                self.check_activate.setChecked(True) # Revert

    def start_install(self, install):
        self.group_params.setEnabled(False)
        self.group_ai.setEnabled(False)
        self.check_activate.setEnabled(False)
        self.lbl_status.setText(tr("360_status_installing") if install else tr("upscale_uninstalling"))
        
        self.install_worker = InstallWorker(self.engine, install)
        self.install_worker.finished_signal.connect(self.on_install_finished)
        self.install_worker.start()
        
    def on_install_finished(self, success, message):
        self.check_activate.setEnabled(True)
        if success:
            QMessageBox.information(self, tr("msg_success"), message)
        else:
            QMessageBox.critical(self, tr("msg_error"), message)
            
        self.update_ui_state()

    def set_params(self, params):
        if not params: return
        
        if "enabled" in params: self.check_activate.setChecked(params["enabled"])
        if "interval" in params: self.spin_interval.setValue(params["interval"])
        if "resolution" in params: self.spin_res.setValue(params["resolution"])
        if "camera_count" in params: self.spin_cam.setValue(params["camera_count"])
        if "quality" in params: self.spin_quality.setValue(params["quality"])
        
        if "layout" in params:
            idx = self.combo_layout.findData(params["layout"])
            if idx >= 0: self.combo_layout.setCurrentIndex(idx)
            
        if "format" in params:
            self.combo_format.setCurrentText(params["format"])
            
        if "ai_mask" in params: self.check_ai_mask.setChecked(params["ai_mask"])
        if "ai_skip" in params: self.check_ai_skip.setChecked(params["ai_skip"])
        if "adaptive" in params: self.check_adaptive.setChecked(params["adaptive"])
        if "motion_threshold" in params: self.spin_threshold.setValue(params["motion_threshold"])
        
        self.update_ui_state()

    def get_state(self):
        return self.get_params()
        
    def set_state(self, state):
        self.set_params(state)
        
        self.update_ui_state()

    def get_params(self):
        """Retourne les paramètres actuels sous forme de dictionnaire"""
        return {
            "enabled": self.check_activate.isChecked(),
            "interval": self.spin_interval.value(),
            "resolution": self.spin_res.value(),
            "camera_count": self.spin_cam.value(),
            "quality": self.spin_quality.value(),
            "layout": self.combo_layout.currentData(),
            "format": self.combo_format.currentText(),
            "ai_mask": self.check_ai_mask.isChecked(),
            "ai_skip": self.check_ai_skip.isChecked(),
            "adaptive": self.check_adaptive.isChecked(),
            "motion_threshold": self.spin_threshold.value()
        }

    def retranslate_ui(self):
        """Update texts when language changes"""
        self.lbl_header.setText(tr("360_header"))
        self.lbl_desc.setText(tr("360_desc"))
        self.check_activate.setText(tr("360_activate"))
        self.group_params.setTitle(tr("360_group_params"))
        self.lbl_interval.setText(tr("360_lbl_interval"))
        self.spin_interval.setToolTip(tr("360_tip_interval"))
        self.lbl_res.setText(tr("360_lbl_resolution"))
        self.spin_res.setToolTip(tr("360_tip_res"))
        self.lbl_layout.setText(tr("360_lbl_layout"))
        self.combo_layout.setToolTip(tr("360_tip_layout"))
        self.combo_layout.setItemText(0, tr("360_layout_ring"))
        self.combo_layout.setItemText(1, tr("360_layout_cube"))
        self.combo_layout.setItemText(2, tr("360_layout_fib"))
        self.lbl_cam.setText(tr("360_lbl_cameras"))
        self.spin_cam.setToolTip(tr("360_tip_cameras"))
        self.lbl_quality.setText(tr("360_lbl_quality"))
        self.spin_quality.setToolTip(tr("360_tip_quality"))
        self.lbl_format.setText(tr("360_lbl_format"))
        self.combo_format.setToolTip(tr("360_tip_format"))
        
        self.group_ai.setTitle(tr("360_group_ai"))
        self.check_ai_mask.setText(tr("360_check_ai_mask"))
        self.check_ai_mask.setToolTip(tr("360_tip_ai_mask"))
        self.check_ai_skip.setText(tr("360_check_ai_skip"))
        self.check_ai_skip.setToolTip(tr("360_tip_ai_skip"))
        self.check_adaptive.setText(tr("360_check_adaptive"))
        self.check_adaptive.setToolTip(tr("360_tip_adaptive"))
        self.lbl_threshold.setText(tr("360_lbl_threshold"))
        self.spin_threshold.setToolTip(tr("360_tip_threshold"))
        
        self.group_standalone.setTitle(tr("360_btn_extract_only"))
        self.lbl_input.setText(tr("360_lbl_input"))
        self.btn_browse_input.setText(tr("btn_browse"))
        self.lbl_output.setText(tr("360_lbl_output"))
        self.btn_browse_output.setText(tr("btn_browse"))
        self.btn_extract.setText(tr("360_btn_extract_only") if self.btn_extract.isEnabled() else tr("msg_processing"))
        
        self.update_ui_state()
