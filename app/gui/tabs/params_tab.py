import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGroupBox, QFormLayout, 
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QMessageBox
)
from app.core.params import ColmapParams
from app.core.system import is_apple_silicon, get_optimal_threads, resolve_binary
from app.core.i18n import tr, add_language_observer

class ParamsTab(QWidget):
    """Onglet des paramètres COLMAP"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        if is_apple_silicon():
            self.info_label = QLabel(tr("info_cpu", get_optimal_threads()))
            layout.addWidget(self.info_label)
        else:
            self.info_label = None
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Feature Extraction
        self.extract_group = QGroupBox(tr("group_extract"))
        extract_layout = QFormLayout()
        
        self.camera_model_combo = QComboBox()
        self.camera_model_combo.addItems(['SIMPLE_PINHOLE', 'PINHOLE', 'SIMPLE_RADIAL', 
                                          'RADIAL', 'OPENCV', 'OPENCV_FISHEYE'])
        self.camera_model_combo.setCurrentText('SIMPLE_RADIAL')
        self.camera_model_combo.setMinimumWidth(180)
        self.lbl_camera_model = QLabel(tr("lbl_camera_model"))
        extract_layout.addRow(self.lbl_camera_model, self.camera_model_combo)
        
        self.single_camera_check = QCheckBox()
        self.single_camera_check.setChecked(True)
        self.lbl_single_cam = QLabel(tr("check_single_cam"))
        extract_layout.addRow(self.lbl_single_cam, self.single_camera_check)
        
        self.max_image_spin = QSpinBox()
        self.max_image_spin.setRange(640, 8192)
        self.max_image_spin.setValue(3200)
        self.max_image_spin.setMinimumWidth(100)
        self.lbl_max_img = QLabel(tr("lbl_max_img"))
        extract_layout.addRow(self.lbl_max_img, self.max_image_spin)
        
        self.max_features_spin = QSpinBox()
        self.max_features_spin.setRange(1024, 32768)
        self.max_features_spin.setValue(8192)
        self.max_features_spin.setMinimumWidth(100)
        self.lbl_max_feat = QLabel(tr("lbl_max_feat"))
        extract_layout.addRow(self.lbl_max_feat, self.max_features_spin)
        
        self.force_cpu_check = QCheckBox()
        self.force_cpu_check.setEnabled(False)
        self.lbl_force_cpu = QLabel(tr("check_force_cpu"))
        extract_layout.addRow(self.lbl_force_cpu, self.force_cpu_check)
        
        self.estimate_affine_check = QCheckBox()
        self.lbl_affine = QLabel(tr("check_affine"))
        extract_layout.addRow(self.lbl_affine, self.estimate_affine_check)
        
        self.domain_pooling_check = QCheckBox()
        self.domain_pooling_check.setChecked(True)
        self.lbl_domain = QLabel(tr("check_domain"))
        extract_layout.addRow(self.lbl_domain, self.domain_pooling_check)
        
        self.extract_group.setLayout(extract_layout)
        scroll_layout.addWidget(self.extract_group)
        
        # Feature Matching
        self.match_group = QGroupBox(tr("group_match"))
        match_layout = QFormLayout()
        
        self.matcher_type_combo = QComboBox()
        self.matcher_type_combo.addItems(['exhaustive', 'sequential', 'vocab_tree'])
        self.matcher_type_combo.setCurrentText('exhaustive')
        self.matcher_type_combo.setMinimumWidth(150)
        self.lbl_match_type = QLabel(tr("lbl_match_type"))
        match_layout.addRow(self.lbl_match_type, self.matcher_type_combo)
        
        self.max_ratio_spin = QDoubleSpinBox()
        self.max_ratio_spin.setRange(0.1, 1.0)
        self.max_ratio_spin.setSingleStep(0.1)
        self.max_ratio_spin.setValue(0.8)
        self.max_ratio_spin.setMinimumWidth(100)
        self.lbl_max_ratio = QLabel(tr("lbl_max_ratio"))
        match_layout.addRow(self.lbl_max_ratio, self.max_ratio_spin)
        
        self.max_distance_spin = QDoubleSpinBox()
        self.max_distance_spin.setRange(0.1, 1.0)
        self.max_distance_spin.setSingleStep(0.1)
        self.max_distance_spin.setValue(0.7)
        self.max_distance_spin.setMinimumWidth(100)
        self.lbl_max_dist = QLabel(tr("lbl_max_dist"))
        match_layout.addRow(self.lbl_max_dist, self.max_distance_spin)
        
        self.cross_check_check = QCheckBox()
        self.cross_check_check.setChecked(True)
        self.lbl_cross = QLabel(tr("check_cross"))
        match_layout.addRow(self.lbl_cross, self.cross_check_check)
        
        self.guided_match_check = QCheckBox()
        self.guided_match_check.setEnabled(False)
        self.lbl_guided = QLabel(tr("check_guided"))
        
        self.match_group.setLayout(match_layout)
        scroll_layout.addWidget(self.match_group)
        
        # Mapper
        self.mapper_group = QGroupBox(tr("group_mapper"))
        mapper_layout = QFormLayout()
        
        self.min_model_spin = QSpinBox()
        self.min_model_spin.setRange(3, 100)
        self.min_model_spin.setValue(10)
        self.min_model_spin.setMinimumWidth(100)
        self.lbl_min_model = QLabel(tr("lbl_min_model"))
        mapper_layout.addRow(self.lbl_min_model, self.min_model_spin)

        self.use_glomap_check = QCheckBox()
        self.use_glomap_check.setText(tr("check_use_glomap"))
        self.lbl_glomap = QLabel(tr("lbl_glomap"))
        mapper_layout.addRow(self.lbl_glomap, self.use_glomap_check)
        
        self.multiple_models_check = QCheckBox()
        self.lbl_multi_model = QLabel(tr("check_multi_model"))
        mapper_layout.addRow(self.lbl_multi_model, self.multiple_models_check)
        
        self.refine_focal_check = QCheckBox()
        self.refine_focal_check.setChecked(True)
        self.lbl_focal = QLabel(tr("check_focal"))
        mapper_layout.addRow(self.lbl_focal, self.refine_focal_check)
        
        self.refine_principal_check = QCheckBox()
        self.lbl_principal = QLabel(tr("check_principal"))
        mapper_layout.addRow(self.lbl_principal, self.refine_principal_check)
        
        self.refine_extra_check = QCheckBox()
        self.refine_extra_check.setChecked(True)
        self.lbl_extra = QLabel(tr("check_extra"))
        mapper_layout.addRow(self.lbl_extra, self.refine_extra_check)
        
        self.min_matches_spin = QSpinBox()
        self.min_matches_spin.setRange(5, 100)
        self.min_matches_spin.setValue(15)
        self.min_matches_spin.setMinimumWidth(100)
        self.lbl_min_match = QLabel(tr("lbl_min_match"))
        mapper_layout.addRow(self.lbl_min_match, self.min_matches_spin)
        
        self.mapper_group.setLayout(mapper_layout)
        scroll_layout.addWidget(self.mapper_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def get_params(self):
        """Récupère les paramètres actuels"""
        return ColmapParams(
            camera_model=self.camera_model_combo.currentText(),
            single_camera=self.single_camera_check.isChecked(),
            max_image_size=self.max_image_spin.value(),
            max_num_features=self.max_features_spin.value(),
            force_cpu=self.force_cpu_check.isChecked(),
            estimate_affine_shape=self.estimate_affine_check.isChecked(),
            domain_size_pooling=self.domain_pooling_check.isChecked(),
            max_ratio=self.max_ratio_spin.value(),
            max_distance=self.max_distance_spin.value(),
            cross_check=self.cross_check_check.isChecked(),
            guided_matching=self.guided_match_check.isChecked(),
            min_model_size=self.min_model_spin.value(),
            multiple_models=self.multiple_models_check.isChecked(),
            ba_refine_focal_length=self.refine_focal_check.isChecked(),
            ba_refine_principal_point=self.refine_principal_check.isChecked(),
            ba_refine_extra_params=self.refine_extra_check.isChecked(),
            min_num_matches=self.min_matches_spin.value(),
            matcher_type=self.matcher_type_combo.currentText(),
            use_glomap=self.use_glomap_check.isChecked(),
            undistort_images=False, # Géré par ConfigTab pour l'instant, ou on peut le passer ici si on veut
        )

    def set_params(self, params):
        """Met à jour les widgets avec les params"""
        self.camera_model_combo.setCurrentText(params.camera_model)
        self.single_camera_check.setChecked(params.single_camera)
        self.max_image_spin.setValue(params.max_image_size)
        self.max_features_spin.setValue(params.max_num_features)
        self.force_cpu_check.setChecked(params.force_cpu)
        self.estimate_affine_check.setChecked(params.estimate_affine_shape)
        self.domain_pooling_check.setChecked(params.domain_size_pooling)
        self.max_ratio_spin.setValue(params.max_ratio)
        self.max_distance_spin.setValue(params.max_distance)
        self.cross_check_check.setChecked(params.cross_check)
        self.min_model_spin.setValue(params.min_model_size)
        self.multiple_models_check.setChecked(params.multiple_models)
        self.refine_focal_check.setChecked(params.ba_refine_focal_length)
        self.refine_principal_check.setChecked(params.ba_refine_principal_point)
        self.refine_extra_check.setChecked(params.ba_refine_extra_params)
        self.min_matches_spin.setValue(params.min_num_matches)
        self.matcher_type_combo.setCurrentText(params.matcher_type)
        self.use_glomap_check.setChecked(params.use_glomap)
        # undistort est dans config tab

    def get_state(self):
        return self.get_params().to_dict()
        
    def set_state(self, state):
        self.set_params(ColmapParams.from_dict(state))

    def retranslate_ui(self):
        """Update texts when language changes"""
        if self.info_label:
            self.info_label.setText(tr("info_cpu", get_optimal_threads()))
            
        self.extract_group.setTitle(tr("group_extract"))
        self.lbl_camera_model.setText(tr("lbl_camera_model"))
        self.lbl_single_cam.setText(tr("check_single_cam"))
        self.lbl_max_img.setText(tr("lbl_max_img"))
        self.lbl_max_feat.setText(tr("lbl_max_feat"))
        self.lbl_force_cpu.setText(tr("check_force_cpu"))
        self.lbl_affine.setText(tr("check_affine"))
        self.lbl_domain.setText(tr("check_domain"))
        
        self.match_group.setTitle(tr("group_match"))
        self.lbl_match_type.setText(tr("lbl_match_type"))
        self.lbl_max_ratio.setText(tr("lbl_max_ratio"))
        self.lbl_max_dist.setText(tr("lbl_max_dist"))
        self.lbl_cross.setText(tr("check_cross"))
        self.lbl_guided.setText(tr("check_guided"))
        
        self.mapper_group.setTitle(tr("group_mapper"))
        self.lbl_min_model.setText(tr("lbl_min_model"))
        self.lbl_glomap.setText(tr("lbl_glomap"))
        self.use_glomap_check.setText(tr("check_use_glomap"))
        self.lbl_multi_model.setText(tr("check_multi_model"))
        self.lbl_focal.setText(tr("check_focal"))
        self.lbl_principal.setText(tr("check_principal"))
        self.lbl_extra.setText(tr("check_extra"))
        self.lbl_min_match.setText(tr("lbl_min_match"))
