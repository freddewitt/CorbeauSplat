"""Panneau Reconstruction (étape PIPELINE) — équivalent de ParamsTab.

Reprend les accordéons Feature Extraction / Matching / Mapper de ``ParamsTab``
dans le centre (fusionnés depuis l'ancienne barre de droite, cf.
``app.gui.panels`` docstring), et migre ici la logique « Reprise de COLMAP »
(avant dans ConfigTab), étendue au cas « dossier externe → nouveau projet à
la volée » (cf. reconstruction_logic.classify_resume_folder).

``undistort_images`` est exécuté réellement ici (section Mapper) et bindé sur le
``RunState`` partagé — dupliqué en raccourci dans Source, même source de vérité.
Les toggles Entraînement/Visualiser après sont aussi bindés sur run_state.

Lot 3b : UI + params + détection de reprise. Le dispatch réel (lancer COLMAP,
créer le projet à la volée) est câblé au sous-lot 3c.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.params import (
    COMPATIBLE_MATCHING,
    FEATURE_TO_DEFAULT_MATCHING,
    FEATURE_TYPES,
    MATCHING_TYPES,
    ColmapParams,
)
from app.core.system import get_optimal_threads, is_apple_silicon
from app.gui.panels.reconstruction_logic import (
    RESUME_COLMAP_PROJECT,
    RESUME_EXTERNAL_IMAGES,
    RESUME_INVALID,
    classify_resume_folder,
)
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.cancel_button import CancelButton
from app.gui.widgets.dialog_utils import get_existing_directory

_CAMERA_MODELS = ['SIMPLE_PINHOLE', 'PINHOLE', 'SIMPLE_RADIAL', 'RADIAL', 'OPENCV', 'OPENCV_FISHEYE']
_MATCHER_TYPES = ['exhaustive', 'sequential', 'vocab_tree']


class ReconstructionPanel:
    """Panneau plain exposant ``center`` et ``right`` (widgets Qt)."""

    def __init__(self, run_state):
        self.run_state = run_state
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Centre (reprise + projet + chaînage + accordéons) ───────────────────────
    def _build_center(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)


        # Bannière Apple Silicon (reprise telle quelle de ParamsTab)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(is_apple_silicon())
        layout.addWidget(self.info_label)

        # Reprise de COLMAP (dossier existant OU dossier externe → nouveau projet)
        self.lbl_resume = QLabel()
        self.lbl_resume.setWordWrap(True)
        layout.addWidget(self.lbl_resume)
        resume_row = QHBoxLayout()
        self.resume_path = QLineEdit()
        self.resume_path.textChanged.connect(self._on_resume_path_changed)
        resume_row.addWidget(self.resume_path)
        self.btn_browse_resume = QPushButton("📁")
        self.btn_browse_resume.clicked.connect(self._browse_resume)
        resume_row.addWidget(self.btn_browse_resume)
        layout.addLayout(resume_row)
        self.lbl_resume_status = QLabel()
        self.lbl_resume_status.setWordWrap(True)
        layout.addWidget(self.lbl_resume_status)

        # Nom projet / dossier de sortie (si pas déjà connus du contexte)
        self.lbl_project = QLabel()
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        layout.addWidget(self.lbl_project)
        layout.addWidget(self.input_project_name)

        self.lbl_output = QLabel()
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addWidget(self.lbl_output)
        layout.addLayout(out_row)

        # Chaînage (mêmes drapeaux que Source, source de vérité unique)
        self.chk_entrainement = QCheckBox()
        self._bind(self.chk_entrainement, "entrainement_apres")
        layout.addWidget(self.chk_entrainement)
        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        # ── Migré depuis _build_right : accordéons Feature Extraction / Matching / Mapper ──
        self.extract_group = QGroupBox()
        ex = QFormLayout(self.extract_group)
        ex.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.camera_model_combo = QComboBox()
        self.camera_model_combo.addItems(_CAMERA_MODELS)
        self.camera_model_combo.setCurrentText('SIMPLE_RADIAL')
        self.lbl_camera_model = QLabel()
        ex.addRow(self.lbl_camera_model, self.camera_model_combo)
        self.single_camera_check = QCheckBox()
        self.single_camera_check.setChecked(True)
        self.lbl_single_cam = QLabel()
        ex.addRow(self.lbl_single_cam, self.single_camera_check)
        self.max_image_spin = QSpinBox()
        self.max_image_spin.setRange(640, 8192)
        self.max_image_spin.setValue(3200)
        self.lbl_max_img = QLabel()
        ex.addRow(self.lbl_max_img, self.max_image_spin)
        self.max_features_spin = QSpinBox()
        self.max_features_spin.setRange(1024, 32768)
        self.max_features_spin.setValue(8192)
        self.lbl_max_feat = QLabel()
        ex.addRow(self.lbl_max_feat, self.max_features_spin)
        self.estimate_affine_check = QCheckBox()
        self.estimate_affine_check.setChecked(True)
        self.lbl_affine = QLabel()
        ex.addRow(self.lbl_affine, self.estimate_affine_check)
        self.domain_pooling_check = QCheckBox()
        self.domain_pooling_check.setChecked(True)
        self.lbl_domain = QLabel()
        ex.addRow(self.lbl_domain, self.domain_pooling_check)
        self.feature_type_combo = QComboBox()
        self.feature_type_combo.addItems(FEATURE_TYPES)
        self.feature_type_combo.setCurrentText('SIFT')
        self.feature_type_combo.currentTextChanged.connect(self._on_feature_type_changed)
        self.lbl_feature_type = QLabel()
        ex.addRow(self.lbl_feature_type, self.feature_type_combo)
        layout.addWidget(self.extract_group)

        # Matching
        self.match_group = QGroupBox()
        mt = QFormLayout(self.match_group)
        mt.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.matcher_type_combo = QComboBox()
        self.matcher_type_combo.addItems(_MATCHER_TYPES)
        self.matcher_type_combo.setCurrentText('exhaustive')
        self.matcher_type_combo.currentTextChanged.connect(self._update_sequential_enabled)
        self.lbl_match_type = QLabel()
        mt.addRow(self.lbl_match_type, self.matcher_type_combo)
        self.sequential_overlap_spin = QSpinBox()
        self.sequential_overlap_spin.setRange(1, 100)
        self.sequential_overlap_spin.setValue(30)
        self.lbl_sequential_overlap = QLabel()
        mt.addRow(self.lbl_sequential_overlap, self.sequential_overlap_spin)
        self.matching_algo_combo = QComboBox()
        self.matching_algo_combo.addItems(MATCHING_TYPES)
        self.matching_algo_combo.setCurrentText('SIFT_BRUTEFORCE')
        self.lbl_matching_algo = QLabel()
        mt.addRow(self.lbl_matching_algo, self.matching_algo_combo)
        self.max_ratio_spin = QDoubleSpinBox()
        self.max_ratio_spin.setRange(0.1, 1.0)
        self.max_ratio_spin.setSingleStep(0.1)
        self.max_ratio_spin.setValue(0.8)
        self.lbl_max_ratio = QLabel()
        mt.addRow(self.lbl_max_ratio, self.max_ratio_spin)
        self.max_distance_spin = QDoubleSpinBox()
        self.max_distance_spin.setRange(0.1, 1.0)
        self.max_distance_spin.setSingleStep(0.1)
        self.max_distance_spin.setValue(0.7)
        self.lbl_max_dist = QLabel()
        mt.addRow(self.lbl_max_dist, self.max_distance_spin)
        self.cross_check_check = QCheckBox()
        self.cross_check_check.setChecked(True)
        self.lbl_cross = QLabel()
        mt.addRow(self.lbl_cross, self.cross_check_check)
        self.guided_match_check = QCheckBox()
        self.lbl_guided = QLabel()
        mt.addRow(self.lbl_guided, self.guided_match_check)
        self.min_matches_spin = QSpinBox()
        self.min_matches_spin.setRange(5, 100)
        self.min_matches_spin.setValue(15)
        self.lbl_min_match = QLabel()
        mt.addRow(self.lbl_min_match, self.min_matches_spin)
        layout.addWidget(self.match_group)

        # Mapper
        self.mapper_group = QGroupBox()
        mp = QFormLayout(self.mapper_group)
        mp.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.refine_focal_check = QCheckBox()
        self.refine_focal_check.setChecked(True)
        self.lbl_focal = QLabel()
        mp.addRow(self.lbl_focal, self.refine_focal_check)
        self.refine_principal_check = QCheckBox()
        self.lbl_principal = QLabel()
        mp.addRow(self.lbl_principal, self.refine_principal_check)
        self.refine_extra_check = QCheckBox()
        self.refine_extra_check.setChecked(True)
        self.lbl_extra = QLabel()
        mp.addRow(self.lbl_extra, self.refine_extra_check)
        self.view_graph_calibration_check = QCheckBox()
        self.view_graph_calibration_check.setChecked(True)
        self.lbl_view_graph = QLabel()
        mp.addRow(self.lbl_view_graph, self.view_graph_calibration_check)
        self.ignore_watermarks_check = QCheckBox()
        self.ignore_watermarks_check.setChecked(True)
        self.lbl_ignore_watermarks = QLabel()
        mp.addRow(self.lbl_ignore_watermarks, self.ignore_watermarks_check)
        self.thermal_throttling_check = QCheckBox()
        self.lbl_thermal = QLabel()
        mp.addRow(self.lbl_thermal, self.thermal_throttling_check)
        # undistort exécuté ici, bindé run_state (dupliqué avec Source)
        self.undistort_check = QCheckBox()
        self._bind(self.undistort_check, "undistort_images")
        self.lbl_undistort = QLabel()
        mp.addRow(self.lbl_undistort, self.undistort_check)
        layout.addWidget(self.mapper_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._update_sequential_enabled()

        # Local Launch button (bottom of center, same idiom as other panels).
        # Wiring (StudioWindow._launch_reconstruction) is done by a later pass.
        self.btn_run = QPushButton()
        self.btn_run.setStyleSheet("font-weight: bold;")
        outer.addWidget(self.btn_run)

        self.btn_cancel = CancelButton()
        outer.addWidget(self.btn_cancel)
        return w

    def _build_right(self):
        return QWidget()

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Comportements ────────────────────────────────────────────────────────────
    def _on_feature_type_changed(self, feat_type):
        compatible = COMPATIBLE_MATCHING.get(feat_type, ['SIFT_BRUTEFORCE'])
        self.matching_algo_combo.clear()
        self.matching_algo_combo.addItems(compatible)
        if self.matching_algo_combo.currentText() not in compatible:
            self.matching_algo_combo.setCurrentText(
                FEATURE_TO_DEFAULT_MATCHING.get(feat_type, 'SIFT_BRUTEFORCE'))

    def _update_sequential_enabled(self, *_):
        self.sequential_overlap_spin.setEnabled(self.matcher_type_combo.currentText() == 'sequential')

    def _on_resume_path_changed(self, text):
        kind = classify_resume_folder(text) if text.strip() else RESUME_INVALID
        self.lbl_resume_status.setText(self._resume_status_text(kind))

    def _resume_status_text(self, kind):
        if kind == RESUME_COLMAP_PROJECT:
            return tr("recon_resume_existing", "Projet COLMAP existant — reprise")
        if kind == RESUME_EXTERNAL_IMAGES:
            return tr("recon_resume_external", "Dossier d'images externe — nouveau projet à la volée")
        return ""

    def _browse_resume(self):
        path = get_existing_directory(self.center, tr("recon_resume", "Reprise de COLMAP"))
        if path:
            self.resume_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    # ── Params ────────────────────────────────────────────────────────────────────
    def get_params(self):
        """Construit ColmapParams depuis les widgets ; undistort depuis run_state."""
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
            sequential_overlap=self.sequential_overlap_spin.value(),
            undistort_images=self.run_state.undistort_images,
            use_view_graph_calibration=self.view_graph_calibration_check.isChecked(),
            ignore_watermarks=self.ignore_watermarks_check.isChecked(),
            thermal_throttling=self.thermal_throttling_check.isChecked(),
        )

    def set_params(self, params):
        self.camera_model_combo.setCurrentText(params.camera_model)
        self.single_camera_check.setChecked(params.single_camera)
        self.max_image_spin.setValue(params.max_image_size)
        self.max_features_spin.setValue(params.max_num_features)
        feat_type = getattr(params, 'feature_type', 'SIFT')
        self.feature_type_combo.setCurrentText(feat_type)
        self._on_feature_type_changed(feat_type)
        match_type = getattr(params, 'matching_type', 'SIFT_BRUTEFORCE')
        if match_type in COMPATIBLE_MATCHING.get(feat_type, []):
            self.matching_algo_combo.setCurrentText(match_type)
        self.estimate_affine_check.setChecked(params.estimate_affine_shape)
        self.domain_pooling_check.setChecked(params.domain_size_pooling)
        self.max_ratio_spin.setValue(params.max_ratio)
        self.max_distance_spin.setValue(params.max_distance)
        self.cross_check_check.setChecked(params.cross_check)
        self.guided_match_check.setChecked(getattr(params, 'guided_matching', False))
        self.sequential_overlap_spin.setValue(getattr(params, 'sequential_overlap', 30))
        self.refine_focal_check.setChecked(params.ba_refine_focal_length)
        self.refine_principal_check.setChecked(params.ba_refine_principal_point)
        self.refine_extra_check.setChecked(params.ba_refine_extra_params)
        self.min_matches_spin.setValue(params.min_num_matches)
        self.matcher_type_combo.setCurrentText(params.matcher_type)
        self.view_graph_calibration_check.setChecked(params.use_view_graph_calibration)
        self.ignore_watermarks_check.setChecked(params.ignore_watermarks)
        self.thermal_throttling_check.setChecked(getattr(params, 'thermal_throttling', False))
        self.run_state.undistort_images = getattr(params, 'undistort_images', False)
        self._update_sequential_enabled()

    def get_state(self):
        return self.get_params().to_dict()

    def set_state(self, state):
        if state:
            self.set_params(ColmapParams.from_dict(state))

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.info_label.setText(tr("info_cpu", get_optimal_threads()))
        self.lbl_resume.setText(tr("recon_resume", "Reprise de COLMAP (dossier projet ou images)"))
        self.lbl_project.setText(tr("label_project_name", "Nom du projet"))
        self.lbl_output.setText(tr("source_output", "Dossier de sortie"))
        self.chk_entrainement.setText(tr("chain_train_after", "Lancer Brush"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        self.extract_group.setTitle(tr("group_extract", "Extraction de caractéristiques"))
        self.match_group.setTitle(tr("group_match", "Correspondances"))
        self.mapper_group.setTitle(tr("group_mapper", "Mapper"))
        self.lbl_camera_model.setText(tr("lbl_camera_model", "Modèle caméra"))
        self.lbl_single_cam.setText(tr("check_single_cam", "Caméra unique"))
        self.lbl_max_img.setText(tr("lbl_max_img", "Taille image max"))
        self.lbl_max_feat.setText(tr("lbl_max_feat", "Caractéristiques max"))
        self.lbl_affine.setText(tr("check_affine", "Estimer forme affine"))
        self.lbl_domain.setText(tr("check_domain", "Domain size pooling"))
        self.lbl_feature_type.setText(tr("lbl_feature_type", "Type de caractéristique"))
        self.lbl_match_type.setText(tr("lbl_match_type", "Type de matcher"))
        self.lbl_sequential_overlap.setText(tr("lbl_sequential_overlap", "Chevauchement séquentiel"))
        self.lbl_matching_algo.setText(tr("lbl_matching_algo", "Algorithme de matching"))
        self.lbl_max_ratio.setText(tr("lbl_max_ratio", "Ratio max"))
        self.lbl_max_dist.setText(tr("lbl_max_dist", "Distance max"))
        self.lbl_cross.setText(tr("check_cross", "Vérification croisée"))
        self.lbl_guided.setText(tr("check_guided", "Guided matching"))
        self.lbl_min_match.setText(tr("lbl_min_match", "Correspondances min"))
        self.lbl_focal.setText(tr("check_focal", "Affiner focale"))
        self.lbl_principal.setText(tr("check_principal", "Affiner point principal"))
        self.lbl_extra.setText(tr("check_extra", "Affiner params extra"))
        self.lbl_view_graph.setText(tr("check_view_graph_calibration", "Calibration view-graph"))
        self.lbl_ignore_watermarks.setText(tr("check_ignore_watermarks", "Ignorer filigranes"))
        self.lbl_thermal.setText(tr("check_thermal_throttling", "Limitation thermique"))
        self.lbl_undistort.setText(tr("source_undistort", "Générer images non-distordues"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
        self._on_resume_path_changed(self.resume_path.text())
