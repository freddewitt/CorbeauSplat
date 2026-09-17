"""TOOLS module 4DGS (multi-camera dataset preparation for Nerfstudio).

No usable .ply output → no Clean/Export/View chaining.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
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
from app.gui.widgets.cancel_button import CancelButton
from app.gui.widgets.dialog_utils import get_existing_directory

_CAMERA_MODELS = ['SIMPLE_PINHOLE', 'PINHOLE', 'SIMPLE_RADIAL', 'RADIAL', 'OPENCV', 'OPENCV_FISHEYE']
# Only the two modes FourDGSEngine.run_colmap actually implements; vocab_tree,
# offered by the Reconstruction panel, would silently fall back to exhaustive here.
_MATCHER_TYPES = ['exhaustive', 'sequential']


class FourDGSPanel:
    def __init__(self, run_state):
        self.run_state = run_state
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.lbl_desc = QLabel()
        self.lbl_desc.setWordWrap(True)
        layout.addWidget(self.lbl_desc)
        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)

        # Permanent scope notice: no dismiss button, this is a lasting
        # limitation (no native Apple Silicon 4DGS training solution exists),
        # not a one-off onboarding hint.
        self.lbl_scope_notice = QLabel()
        self.lbl_scope_notice.setWordWrap(True)
        layout.addWidget(self.lbl_scope_notice)

        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = QLineEdit()
        in_row.addWidget(self.input_path)
        self.btn_browse_input = QPushButton("📁")
        self.btn_browse_input.clicked.connect(self._browse_input)
        in_row.addWidget(self.btn_browse_input)
        layout.addLayout(in_row)

        self.lbl_output = QLabel()
        layout.addWidget(self.lbl_output)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addLayout(out_row)

        self.btn_run = QPushButton()
        self.btn_run.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.btn_run)

        self.btn_cancel = CancelButton()
        layout.addWidget(self.btn_cancel)
        layout.addStretch(1)
        return w

    def _build_right(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        form = QFormLayout(content)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # avoid horizontal overflow (long labels)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        self.lbl_fps = QLabel()
        form.addRow(self.lbl_fps, self.fps_spin)
        self.chk_upscale_before = QCheckBox()
        self.lbl_upscale_before = QLabel()
        form.addRow(self.lbl_upscale_before, self.chk_upscale_before)
        # Unchecked by default: Launch does the full extraction + COLMAP;
        # checking it skips extraction and just reruns COLMAP (ex-dedicated button).
        self.chk_colmap_only = QCheckBox()
        self.lbl_colmap_only = QLabel()
        form.addRow(self.lbl_colmap_only, self.chk_colmap_only)

        # COLMAP settings. Defaults mirror FourDGSEngine.run_colmap: OPENCV and
        # a single camera model, which suits a homogeneous multi-camera rig.
        self.camera_model_combo = QComboBox()
        self.camera_model_combo.addItems(_CAMERA_MODELS)
        self.camera_model_combo.setCurrentText('OPENCV')
        self.lbl_camera_model = QLabel()
        form.addRow(self.lbl_camera_model, self.camera_model_combo)

        self.single_camera_check = QCheckBox()
        self.single_camera_check.setChecked(True)
        self.lbl_single_cam = QLabel()
        form.addRow(self.lbl_single_cam, self.single_camera_check)

        self.matcher_type_combo = QComboBox()
        self.matcher_type_combo.addItems(_MATCHER_TYPES)
        self.matcher_type_combo.setCurrentText('exhaustive')
        self.matcher_type_combo.currentTextChanged.connect(self._update_sequential_enabled)
        self.lbl_match_type = QLabel()
        form.addRow(self.lbl_match_type, self.matcher_type_combo)

        self.sequential_overlap_spin = QSpinBox()
        self.sequential_overlap_spin.setRange(1, 100)
        self.sequential_overlap_spin.setValue(10)
        self.lbl_sequential_overlap = QLabel()
        form.addRow(self.lbl_sequential_overlap, self.sequential_overlap_spin)
        self._update_sequential_enabled()

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _update_sequential_enabled(self, *_):
        self.sequential_overlap_spin.setEnabled(self.matcher_type_combo.currentText() == "sequential")

    def _browse_input(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def get_params(self):
        """Return the 4DGS parameters as a dict."""
        return {
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "fps": self.fps_spin.value(),
            "upscale": self.chk_upscale_before.isChecked(),
            "colmap_only": self.chk_colmap_only.isChecked(),
            "camera_model": self.camera_model_combo.currentText(),
            "single_camera": self.single_camera_check.isChecked(),
            "matcher_type": self.matcher_type_combo.currentText(),
            "sequential_overlap": self.sequential_overlap_spin.value(),
        }

    def retranslate_ui(self):
        self.lbl_desc.setText(tr("four_dgs_desc",
                                 "Extrait des frames de vidéos synchronisées et prépare un dataset Nerfstudio."))
        self.lbl_status.setText(tr("four_dgs_status", "Statut d'installation"))
        self.lbl_scope_notice.setText(tr(
            "fourdgs_scope_notice",
            "Ce module prépare le dataset (extraction + reconstruction COLMAP au format "
            "Nerfstudio) uniquement. Aucune solution d'entraînement 4D Gaussian Splatting "
            "native Apple Silicon n'est disponible à ce jour — l'entraînement doit être "
            "fait ailleurs (GPU NVIDIA ou service cloud).",
        ))
        self.lbl_input.setText(tr("four_dgs_input", "Source vidéos (dossier multi-caméras)"))
        self.lbl_output.setText(tr("four_dgs_output", "Destination dataset"))
        self.lbl_colmap_only.setText(tr("four_dgs_colmap_only", "Reconstruction COLMAP seulement"))
        self.lbl_fps.setText(tr("four_dgs_lbl_fps", "Extraction FPS"))
        self.lbl_upscale_before.setText(tr("four_dgs_upscale_before", "Upscaler avant reconstruction"))
        self.lbl_camera_model.setText(tr("lbl_camera_model", "Modèle caméra"))
        self.lbl_single_cam.setText(tr("check_single_cam", "Caméra unique"))
        self.lbl_match_type.setText(tr("lbl_match_type", "Type de matcher"))
        self.lbl_sequential_overlap.setText(tr("lbl_sequential_overlap", "Chevauchement séquentiel"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
