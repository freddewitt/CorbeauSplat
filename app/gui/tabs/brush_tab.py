import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr
from app.core.system import resolve_binary

class BrushTab(QWidget):
    """Onglet de configuration Brush"""
    
    trainRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Status Check
        self.bin_path = resolve_binary("brush")
        status_layout = QHBoxLayout()
        if self.bin_path:
            status_lbl = QLabel(tr("brush_detected", self.bin_path))
            status_lbl.setStyleSheet("color: #44aa44;")
        else:
            status_lbl = QLabel(tr("brush_not_found"))
            status_lbl.setStyleSheet("color: #aa4444; font-weight: bold;")
        status_layout.addWidget(status_lbl)
        layout.addLayout(status_layout)
        
        # Parameters Group
        param_group = QGroupBox(tr("brush_params"))
        param_layout = QFormLayout()
        
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1000, 100000)
        self.iterations_spin.setValue(30000)
        self.iterations_spin.setSingleStep(1000)
        self.iterations_spin.setMinimumWidth(100)
        param_layout.addRow(tr("brush_iterations"), self.iterations_spin)
        
        # SH Degree
        self.sh_spin = QSpinBox()
        self.sh_spin.setRange(1, 4)
        self.sh_spin.setValue(3)
        self.sh_spin.setMinimumWidth(100)
        param_layout.addRow(tr("brush_sh_degree"), self.sh_spin)
        
        # Device
        from PyQt6.QtWidgets import QComboBox
        self.device_combo = QComboBox()
        self.device_combo.addItems(["mps", "cuda", "cpu", "auto"])
        self.device_combo.setMinimumWidth(150)
        param_layout.addRow(tr("brush_device"), self.device_combo)
        
        # Custom Args
        self.custom_args_edit = QLineEdit()
        self.custom_args_edit.setPlaceholderText("--refine_pose ...")
        param_layout.addRow(tr("brush_args"), self.custom_args_edit)
        
        # Viewer Option
        self.check_viewer = QCheckBox(tr("brush_viewer"))
        self.check_viewer.setChecked(True)
        param_layout.addRow("", self.check_viewer)
        
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        
        # Manual Mode Group
        self.check_independent = QCheckBox(tr("check_brush_independent"))
        self.check_independent.toggled.connect(self.update_ui_state)
        layout.addWidget(self.check_independent)
        
        self.manual_group = QGroupBox(tr("brush_group_paths"))
        manual_layout = QFormLayout()
        
        # Input Path
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.btn_browse_input = QPushButton("...")
        self.btn_browse_input.setMaximumWidth(40)
        self.btn_browse_input.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(self.btn_browse_input)
        manual_layout.addRow(tr("brush_lbl_input"), input_layout)
        
        # Output Path
        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.btn_browse_output = QPushButton("...")
        self.btn_browse_output.setMaximumWidth(40)
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.btn_browse_output)
        manual_layout.addRow(tr("brush_lbl_output"), output_layout)
        
        # PLY Filename
        self.ply_name = QLineEdit()
        self.ply_name.setPlaceholderText("point_cloud.ply")
        manual_layout.addRow(tr("brush_lbl_ply"), self.ply_name)
        
        self.manual_group.setLayout(manual_layout)
        layout.addWidget(self.manual_group)
        
        # Initial state update
        self.update_ui_state()
        
        # Actions
        action_layout = QHBoxLayout()
        
        self.btn_train = QPushButton(tr("btn_train_brush"))
        self.btn_train.setMinimumHeight(40)
        self.btn_train.setStyleSheet("background-color: #2a82da; color: white; font-weight: bold;")
        self.btn_train.clicked.connect(self.trainRequested.emit)
        if not self.bin_path:
            self.btn_train.setEnabled(False)
            
        action_layout.addWidget(self.btn_train)
        
        self.btn_stop = QPushButton(tr("btn_stop"))
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        action_layout.addWidget(self.btn_stop)
        
        layout.addLayout(action_layout)
        
        layout.addStretch()
        
    def get_params(self):
        return {
            "iterations": self.iterations_spin.value(),
            "sh_degree": self.sh_spin.value(),
            "device": self.device_combo.currentText(),
            "custom_args": self.custom_args_edit.text(),
            "with_viewer": self.check_viewer.isChecked(),
            "independent": self.check_independent.isChecked(),
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "ply_name": self.ply_name.text()
        }
        
    def update_ui_state(self):
        enabled = self.check_independent.isChecked()
        self.manual_group.setEnabled(enabled)
        # Maybe hide/show? For now enable/disable is good enough
        
    def browse_input(self):
        path = QFileDialog.getExistingDirectory(self, tr("brush_lbl_input"))
        if path:
            self.input_path.setText(path)
            
    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, tr("brush_lbl_output"))
        if path:
            self.output_path.setText(path)
        
    def set_processing_state(self, is_processing):
        self.btn_train.setEnabled(not is_processing and bool(self.bin_path))
        self.btn_stop.setEnabled(is_processing)
        self.manual_group.setEnabled(not is_processing and self.check_independent.isChecked())
        self.check_independent.setEnabled(not is_processing)
