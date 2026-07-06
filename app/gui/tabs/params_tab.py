from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGroupBox, QFormLayout, 
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox
)
from app.core.params import ColmapParams, FEATURE_TYPES, MATCHING_TYPES, FEATURE_TO_DEFAULT_MATCHING, COMPATIBLE_MATCHING
from app.core.system import is_apple_silicon, get_optimal_threads
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
        
        self.estimate_affine_check = QCheckBox()
        self.lbl_affine = QLabel(tr("check_affine"))
        extract_layout.addRow(self.lbl_affine, self.estimate_affine_check)
        
        self.domain_pooling_check = QCheckBox()
        self.domain_pooling_check.setChecked(True)
        self.lbl_domain = QLabel(tr("check_domain"))
        extract_layout.addRow(self.lbl_domain, self.domain_pooling_check)

        self.feature_type_combo = QComboBox()
        self.feature_type_combo.addItems(FEATURE_TYPES)
        self.feature_type_combo.setCurrentText('ALIKED_N32')
        self.feature_type_combo.setMinimumWidth(150)
        self.lbl_feature_type = QLabel(tr("lbl_feature_type"))
        extract_layout.addRow(self.lbl_feature_type, self.feature_type_combo)
        self.feature_type_combo.currentTextChanged.connect(self._on_feature_type_changed)
        
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

        self.matching_algo_combo = QComboBox()
        self.matching_algo_combo.addItems(MATCHING_TYPES)
        self.matching_algo_combo.setCurrentText('SIFT_BRUTEFORCE')
        self.matching_algo_combo.setMinimumWidth(180)
        self.lbl_matching_algo = QLabel(tr("lbl_matching_algo"))
        match_layout.addRow(self.lbl_matching_algo, self.matching_algo_combo)

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
        match_layout.addRow(self.lbl_guided, self.guided_match_check)
        
        self.match_group.setLayout(match_layout)
        scroll_layout.addWidget(self.match_group)
        
        # Mapper
        self.mapper_group = QGroupBox(tr("group_mapper"))
        mapper_layout = QFormLayout()
        
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

        self.view_graph_calibration_check = QCheckBox()
        self.view_graph_calibration_check.setChecked(True)
        self.lbl_view_graph_calibration = QLabel(tr("check_view_graph_calibration"))
        mapper_layout.addRow(self.lbl_view_graph_calibration, self.view_graph_calibration_check)

        self.ignore_watermarks_check = QCheckBox()
        self.ignore_watermarks_check.setChecked(True)
        self.lbl_ignore_watermarks = QLabel(tr("check_ignore_watermarks"))
        mapper_layout.addRow(self.lbl_ignore_watermarks, self.ignore_watermarks_check)

        self.thermal_throttling_check = QCheckBox()
        self.lbl_thermal_throttling = QLabel(tr("check_thermal_throttling"))
        mapper_layout.addRow(self.lbl_thermal_throttling, self.thermal_throttling_check)
        
        self.mapper_group.setLayout(mapper_layout)
        scroll_layout.addWidget(self.mapper_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def _on_feature_type_changed(self, feat_type: str):
        compatible = COMPATIBLE_MATCHING.get(feat_type, ['SIFT_BRUTEFORCE'])
        self.matching_algo_combo.clear()
        self.matching_algo_combo.addItems(compatible)
        current = self.matching_algo_combo.currentText()
        default = FEATURE_TO_DEFAULT_MATCHING.get(feat_type, 'SIFT_BRUTEFORCE')
        if current not in compatible:
            self.matching_algo_combo.setCurrentText(default)

    def get_params(self):
        """Récupère les paramètres actuels"""
        return ColmapParams(
            camera_model=self.camera_model_combo.currentText(),
            single_camera=self.single_camera_check.isChecked(),
            max_image_size=self.max_image_spin.value(),
            max_num_features=self.max_features_spin.value(),
            feature_type=self.feature_type_combo.currentText(),
            matching_type=self.matching_algo_combo.currentText(),
            estimate_affine_shape=self.estimate_affine_check.isChecked(),
            domain_size_pooling=self.domain_pooling_check.isChecked(),
            max_ratio=self.max_ratio_spin.value(),
            max_distance=self.max_distance_spin.value(),
            cross_check=self.cross_check_check.isChecked(),
            guided_matching=self.guided_match_check.isChecked(),
            ba_refine_focal_length=self.refine_focal_check.isChecked(),
            ba_refine_principal_point=self.refine_principal_check.isChecked(),
            ba_refine_extra_params=self.refine_extra_check.isChecked(),
            min_num_matches=self.min_matches_spin.value(),
            matcher_type=self.matcher_type_combo.currentText(),
            undistort_images=False, # Géré par ConfigTab pour l'instant, ou on peut le passer ici si on veut
            use_view_graph_calibration=self.view_graph_calibration_check.isChecked(),
            ignore_watermarks=self.ignore_watermarks_check.isChecked(),
            thermal_throttling=self.thermal_throttling_check.isChecked(),
        )

    def set_params(self, params):
        """Met à jour les widgets avec les params"""
        self.camera_model_combo.setCurrentText(params.camera_model)
        self.single_camera_check.setChecked(params.single_camera)
        self.max_image_spin.setValue(params.max_image_size)
        self.max_features_spin.setValue(params.max_num_features)
        feat_type = getattr(params, 'feature_type', 'ALIKED_N32')
        self.feature_type_combo.setCurrentText(feat_type)
        self._on_feature_type_changed(feat_type)
        match_type = getattr(params, 'matching_type', 'ALIKED_LIGHTGLUE')
        if match_type in COMPATIBLE_MATCHING.get(feat_type, []):
            self.matching_algo_combo.setCurrentText(match_type)
        self.estimate_affine_check.setChecked(params.estimate_affine_shape)
        self.domain_pooling_check.setChecked(params.domain_size_pooling)
        self.max_ratio_spin.setValue(params.max_ratio)
        self.max_distance_spin.setValue(params.max_distance)
        self.cross_check_check.setChecked(params.cross_check)
        self.refine_focal_check.setChecked(params.ba_refine_focal_length)
        self.refine_principal_check.setChecked(params.ba_refine_principal_point)
        self.refine_extra_check.setChecked(params.ba_refine_extra_params)
        self.min_matches_spin.setValue(params.min_num_matches)
        self.matcher_type_combo.setCurrentText(params.matcher_type)
        self.view_graph_calibration_check.setChecked(params.use_view_graph_calibration)
        self.ignore_watermarks_check.setChecked(params.ignore_watermarks)
        self.thermal_throttling_check.setChecked(getattr(params, 'thermal_throttling', False))
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
        self.lbl_affine.setText(tr("check_affine"))
        self.lbl_domain.setText(tr("check_domain"))
        self.lbl_feature_type.setText(tr("lbl_feature_type"))
        
        self.match_group.setTitle(tr("group_match"))
        self.lbl_match_type.setText(tr("lbl_match_type"))
        self.lbl_matching_algo.setText(tr("lbl_matching_algo"))
        self.lbl_max_ratio.setText(tr("lbl_max_ratio"))
        self.lbl_max_dist.setText(tr("lbl_max_dist"))
        self.lbl_cross.setText(tr("check_cross"))
        self.lbl_guided.setText(tr("check_guided"))
        
        self.mapper_group.setTitle(tr("group_mapper"))
        self.lbl_focal.setText(tr("check_focal"))
        self.lbl_principal.setText(tr("check_principal"))
        self.lbl_extra.setText(tr("check_extra"))
        self.lbl_min_match.setText(tr("lbl_min_match"))
        self.lbl_view_graph_calibration.setText(tr("check_view_graph_calibration"))
        self.lbl_ignore_watermarks.setText(tr("check_ignore_watermarks"))
        self.lbl_thermal_throttling.setText(tr("check_thermal_throttling"))
