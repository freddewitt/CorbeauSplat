import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox, QComboBox, QDoubleSpinBox, 
    QFileDialog, QScrollArea, QFrame
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
        # Layout principal (contient Status + Scroll + Boutons)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 1. Status Check (Fixe en haut)
        self.bin_path = resolve_binary("brush")
        status_layout = QHBoxLayout()
        if self.bin_path:
            status_lbl = QLabel(tr("brush_detected", self.bin_path))
            status_lbl.setStyleSheet("color: #44aa44;")
        else:
            status_lbl = QLabel(tr("brush_not_found"))
            status_lbl.setStyleSheet("color: #aa4444; font-weight: bold;")
        status_layout.addWidget(status_lbl)
        main_layout.addLayout(status_layout)
        
        # 2. Zone de défilement pour les paramètres
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
        
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0) # Marge droite pour la scrollbar
        
        # --- Contenu des paramètres ---
        
        # A. Core Parameters Group (Paramètres principaux)
        param_group = QGroupBox(tr("brush_params"))
        param_layout = QFormLayout()
        
        # Total Steps (Moved to top as requested)
        self.spin_total_steps = self.create_spin(30000, 1000, 200000, 1000, tr("brush_lbl_steps"))
        param_layout.addRow(tr("brush_lbl_steps"), self.spin_total_steps)
        
        # SH Degree
        self.sh_spin = QSpinBox()
        self.sh_spin.setRange(1, 4)
        self.sh_spin.setValue(3)
        self.sh_spin.setMinimumWidth(100)
        param_layout.addRow(tr("brush_sh_degree"), self.sh_spin)
        
        # Device
        self.device_combo = QComboBox()
        self.device_combo.addItems(["mps", "cuda", "cpu", "auto"])
        self.device_combo.setMinimumWidth(150)
        param_layout.addRow(tr("brush_device"), self.device_combo)
        
        # Custom Args
        self.custom_args_edit = QLineEdit()
        self.custom_args_edit.setPlaceholderText("--refine_pose ...")
        param_layout.addRow(tr("brush_args"), self.custom_args_edit)
        
        # Max Resolution Manual
        res_layout = QHBoxLayout()
        self.max_resolution_spin = QSpinBox()
        self.max_resolution_spin.setRange(0, 16384)
        self.max_resolution_spin.setValue(0)
        self.max_resolution_spin.setSpecialValueText(tr("brush_res_default"))
        self.max_resolution_spin.setMinimumWidth(120)
        self.max_resolution_spin.setToolTip("Définir une limite de résolution (côté le plus long). Laisser à 0 pour le défaut.")
        
        warn_label = QLabel(tr("brush_res_warn"))
        warn_label.setStyleSheet("color: #888888; font-size: 11px;")
        
        res_layout.addWidget(QLabel(tr("brush_lbl_res")))
        res_layout.addWidget(self.max_resolution_spin)
        res_layout.addWidget(warn_label)
        res_layout.addStretch()
        param_layout.addRow(res_layout)

        # Viewer Option
        self.check_viewer = QCheckBox(tr("brush_viewer"))
        self.check_viewer.setChecked(True)
        param_layout.addRow("", self.check_viewer)
        
        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        
        # B. Workflow Configuration
        # 1. Independent Checkbox
        self.check_independent = QCheckBox(tr("check_brush_independent"))
        self.check_independent.toggled.connect(self.on_manual_toggled)
        layout.addWidget(self.check_independent)
        
        # 2. Training Mode 
        mode_layout = QHBoxLayout()
        # mode_layout.addWidget(QLabel(tr("brush_lbl_mode")))
        # Use Form Layout style for alignment? Or just clean VBox for this section
        # Let's use a FormLayout for Mode & Preset to align labels nicely
        workflow_form = QFormLayout()
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(tr("brush_mode_new"), "new")
        self.combo_mode.addItem(tr("brush_mode_refine"), "refine")
        self.combo_mode.setToolTip("Nouvel entrainement: Crée un nouveau modèle.\nRaffiner: Reprend depuis le dernier checkpoint trouvé.")
        self.combo_mode.currentIndexChanged.connect(self.update_visibility)
        workflow_form.addRow(tr("brush_lbl_mode"), self.combo_mode)

        # 3. Preset (Moved here, just below Training Mode)
        self.combo_preset = QComboBox()
        self.combo_preset.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_preset.addItem(tr("brush_preset_default"), "default")
        self.combo_preset.addItem(tr("brush_preset_fast"), "fast")
        self.combo_preset.addItem(tr("brush_preset_std"), "std")
        self.combo_preset.addItem(tr("brush_preset_dense"), "dense")
        self.combo_preset.currentIndexChanged.connect(self.apply_preset)
        workflow_form.addRow(tr("brush_lbl_preset"), self.combo_preset)
        
        layout.addLayout(workflow_form)
        
        # 4. Manual Dataset Path (Visible only if Independent)
        self.manual_group = QGroupBox(tr("brush_group_paths"))
        manual_layout = QFormLayout()
        
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.btn_browse_input = QPushButton("...")
        self.btn_browse_input.setMaximumWidth(40)
        self.btn_browse_input.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(self.btn_browse_input)
        manual_layout.addRow(tr("brush_lbl_input"), input_layout)
        
        self.manual_group.setLayout(manual_layout)
        layout.addWidget(self.manual_group)

        # Division Visual
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 5. Show Details Checkbox (Below dataset folder)
        self.check_details = QCheckBox(tr("brush_check_details"))
        self.check_details.toggled.connect(self.update_visibility)
        layout.addWidget(self.check_details)
        
        # C. Advanced Params Container (Visible only if check_details)
        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        
        # Advanced Params Grid
        grid_layout = QVBoxLayout()
        
        # Row 1: Start Iter 
        row1 = QHBoxLayout()
        self.spin_start_iter = self.create_spin(0, 0, 200000, 1000, tr("brush_lbl_start"))
        row1.addWidget(QLabel(tr("brush_lbl_start")))
        row1.addWidget(self.spin_start_iter)
        row1.addStretch()
        grid_layout.addLayout(row1)
        
        # Row 2: Refine Every & Growth Stop
        row2 = QHBoxLayout()
        self.spin_refine = self.create_spin(200, 50, 5000, 50, tr("brush_lbl_refine"))
        self.spin_growth_stop = self.create_spin(15000, 0, 200000, 1000, tr("brush_lbl_stop"))
        row2.addWidget(QLabel(tr("brush_lbl_refine")))
        row2.addWidget(self.spin_refine)
        row2.addSpacing(10)
        row2.addWidget(QLabel(tr("brush_lbl_stop")))
        row2.addWidget(self.spin_growth_stop)
        grid_layout.addLayout(row2)
        
        # Row 3: Threshold & Fraction
        row3 = QHBoxLayout()
        self.spin_threshold = self.create_double_spin(0.003, 0.0001, 0.1, 4, 0.0001, tr("brush_lbl_threshold"))
        self.spin_fraction = self.create_double_spin(0.2, 0.0, 1.0, 2, 0.1, tr("brush_lbl_fraction"))
        row3.addWidget(QLabel(tr("brush_lbl_threshold")))
        row3.addWidget(self.spin_threshold)
        row3.addSpacing(10)
        row3.addWidget(QLabel(tr("brush_lbl_fraction")))
        row3.addWidget(self.spin_fraction)
        grid_layout.addLayout(row3)
        
        # Row 4: Max Splats
        row4 = QHBoxLayout()
        self.spin_max_splats = self.create_spin(10000000, 100000, 100000000, 100000, tr("brush_lbl_max_splats"))
        row4.addWidget(QLabel(tr("brush_lbl_max_splats")))
        row4.addWidget(self.spin_max_splats)
        grid_layout.addLayout(row4)
        
        details_layout.addLayout(grid_layout)
        
        layout.addWidget(self.details_container)

        layout.addStretch() # Pousse le contenu vers le haut
        
        # Fin de la zone scrollable
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # 3. Actions (Fixe en bas)
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
        
        main_layout.addLayout(action_layout)
        
        # Initial state update
        self.update_visibility()

    def create_spin(self, val, min_v, max_v, step, tooltip=""):
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(val)
        s.setSingleStep(step)
        s.setToolTip(tooltip)
        return s

    def create_double_spin(self, val, min_v, max_v, decimals, step, tooltip=""):
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v)
        s.setDecimals(decimals)
        s.setValue(val)
        s.setSingleStep(step)
        s.setToolTip(tooltip)
        return s
        
    def apply_preset(self, index):
        data = self.combo_preset.currentData()
        if data == "default":
            self.spin_total_steps.setValue(30000)
            self.spin_refine.setValue(200)
            self.spin_threshold.setValue(0.003)
            self.spin_fraction.setValue(0.2)
            self.spin_growth_stop.setValue(15000)
        elif data == "fast":
            self.spin_total_steps.setValue(7000)
            self.spin_refine.setValue(100)
            self.spin_threshold.setValue(0.01) # Very coarse
            self.spin_fraction.setValue(0.2)
            self.spin_growth_stop.setValue(6000)
        elif data == "std":
            self.spin_total_steps.setValue(30000)
            self.spin_refine.setValue(200)
            self.spin_threshold.setValue(0.003)
            self.spin_fraction.setValue(0.2)
            self.spin_growth_stop.setValue(15000)
        elif data == "dense":
            self.spin_total_steps.setValue(50000)
            self.spin_refine.setValue(100)
            self.spin_threshold.setValue(0.0005) # Aggressive
            self.spin_fraction.setValue(0.6)
            self.spin_growth_stop.setValue(40000) # Late stop
            
    def on_manual_toggled(self, checked):
        """Force 'New' mode when entering manual mode"""
        if checked:
            idx = self.combo_mode.findData("new")
            if idx >= 0: self.combo_mode.setCurrentIndex(idx)
        self.update_visibility()

    def browse_input(self):
        path = QFileDialog.getExistingDirectory(self, tr("brush_lbl_input"))
        if path:
            self.input_path.setText(path)

    def update_visibility(self):
        # 1. Manual Path visibility
        independent = self.check_independent.isChecked()
        self.manual_group.setVisible(independent)
        
        # 2. Advanced Details visibility
        details = self.check_details.isChecked()
        self.details_container.setVisible(details)
        
    def set_processing_state(self, is_processing):
        self.btn_train.setEnabled(not is_processing and bool(self.bin_path))
        self.btn_stop.setEnabled(is_processing)
        self.check_independent.setEnabled(not is_processing)
        self.combo_mode.setEnabled(not is_processing)
        self.combo_preset.setEnabled(not is_processing)
        self.manual_group.setEnabled(not is_processing and self.check_independent.isChecked())

    def get_params(self):
        """Retourne les parametres"""
        # Note: iterations replaced by total_steps
        return {
            "iterations": self.spin_total_steps.value(), # Keeping key compatible for engine
            "total_steps": self.spin_total_steps.value(),
            "start_iter": self.spin_start_iter.value(),
            "refine_every": self.spin_refine.value(),
            "growth_grad_threshold": self.spin_threshold.value(),
            "growth_select_fraction": self.spin_fraction.value(),
            "growth_stop_iter": self.spin_growth_stop.value(),
            "max_splats": self.spin_max_splats.value(),
            "refine_mode": (self.combo_mode.currentData() == "refine"),
            
            "sh_degree": self.sh_spin.value(),
            "device": self.device_combo.currentText(),
            "custom_args": self.custom_args_edit.text(),
            "max_resolution": self.max_resolution_spin.value(),
            "with_viewer": self.check_viewer.isChecked(),
            "independent": self.check_independent.isChecked(),
            "input_path": self.input_path.text(),
            "show_details": self.check_details.isChecked()
        }
        
    def set_params(self, params):
        """Restaure les parametres"""
        if not params: return
        
        if "total_steps" in params: self.spin_total_steps.setValue(params["total_steps"])
        elif "iterations" in params: self.spin_total_steps.setValue(params["iterations"]) # Fallback
        
        if "start_iter" in params: self.spin_start_iter.setValue(params["start_iter"])
        if "refine_every" in params: self.spin_refine.setValue(params["refine_every"])
        if "growth_grad_threshold" in params: self.spin_threshold.setValue(params["growth_grad_threshold"])
        if "growth_select_fraction" in params: self.spin_fraction.setValue(params["growth_select_fraction"])
        if "growth_stop_iter" in params: self.spin_growth_stop.setValue(params["growth_stop_iter"])
        if "max_splats" in params: self.spin_max_splats.setValue(params["max_splats"])
        if "refine_mode" in params:
             idx = self.combo_mode.findData("refine" if params["refine_mode"] else "new")
             if idx >= 0: self.combo_mode.setCurrentIndex(idx)
        
        if "sh_degree" in params: self.sh_spin.setValue(params["sh_degree"])
        if "device" in params: self.device_combo.setCurrentText(params["device"])
        if "custom_args" in params: self.custom_args_edit.setText(params["custom_args"])
        if "max_resolution" in params: self.max_resolution_spin.setValue(params["max_resolution"])
        if "with_viewer" in params: self.check_viewer.setChecked(params["with_viewer"])
        if "independent" in params: self.check_independent.setChecked(params["independent"])
        
        # Details state
        if "show_details" in params: self.check_details.setChecked(params["show_details"])
        
        # Manual paths
        if "input_path" in params: self.input_path.setText(params["input_path"])
        
        self.update_visibility()
