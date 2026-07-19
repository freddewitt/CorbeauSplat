"""Module OUTILS 360 Extractor (équirectangulaire → images planaires).

Sortie en images → pas de chaînage Nettoyer/Exporter/Visualiser.
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
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class Extractor360Panel:
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

        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = DropLineEdit()
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

        layout.addStretch(1)

        self.btn_run = QPushButton()
        self.btn_run.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.btn_run)
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
        layout = QVBoxLayout(content)

        form = QFormLayout()
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setSingleStep(0.1)
        self.spin_interval.setValue(1.0)
        self.lbl_interval = QLabel()
        form.addRow(self.lbl_interval, self.spin_interval)
        self.spin_res = QSpinBox()
        self.spin_res.setRange(512, 8192)
        self.spin_res.setValue(1920)
        self.lbl_res = QLabel()
        form.addRow(self.lbl_res, self.spin_res)
        self.combo_layout = QComboBox()
        self.lbl_layout = QLabel()
        form.addRow(self.lbl_layout, self.combo_layout)
        self.spin_cameras = QSpinBox()
        self.spin_cameras.setRange(1, 12)
        self.spin_cameras.setValue(4)
        self.lbl_cameras = QLabel()
        form.addRow(self.lbl_cameras, self.spin_cameras)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(90)
        self.lbl_quality = QLabel()
        form.addRow(self.lbl_quality, self.spin_quality)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["JPEG", "PNG"])
        self.lbl_format = QLabel()
        form.addRow(self.lbl_format, self.combo_format)
        layout.addLayout(form)

        self.ai_group = QGroupBox()
        self.ai_group.setCheckable(True)
        self.ai_group.setChecked(False)
        ag = QFormLayout(self.ai_group)
        self.chk_mask_operator = QCheckBox()
        ag.addRow(self.chk_mask_operator)
        self.chk_skip_operator = QCheckBox()
        ag.addRow(self.chk_skip_operator)
        self.chk_adaptive = QCheckBox()
        ag.addRow(self.chk_adaptive)
        self.spin_motion = QDoubleSpinBox()
        self.spin_motion.setRange(0.0, 1.0)
        self.spin_motion.setSingleStep(0.01)
        self.lbl_motion = QLabel()
        ag.addRow(self.lbl_motion, self.spin_motion)
        layout.addWidget(self.ai_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _browse_input(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def get_params(self):
        """Retourne les paramètres d'extraction 360 sous forme de dict."""
        return {
            "interval": self.spin_interval.value(),
            "resolution": self.spin_res.value(),
            "layout": self.combo_layout.currentText(),
            "cameras": self.spin_cameras.value(),
            "quality": self.spin_quality.value(),
            "format": self.combo_format.currentText().lower(),
            "mask_operator": self.chk_mask_operator.isChecked(),
            "skip_operator": self.chk_skip_operator.isChecked(),
            "adaptive": self.chk_adaptive.isChecked(),
            "motion_threshold": self.spin_motion.value(),
        }

    def retranslate_ui(self):
        self.lbl_desc.setText(tr("360_desc",
                                 "Convertit des vidéos/images 360° équirectangulaires en images planaires."))
        self.lbl_status.setText(tr("360_status", "Moteur 360 Extractor"))
        self.lbl_input.setText(tr("360_input", "Vidéo source"))
        self.lbl_output.setText(tr("360_output", "Dossier de sortie"))
        self.lbl_interval.setText(tr("360_lbl_interval", "Intervalle (s)"))
        self.lbl_res.setText(tr("360_lbl_resolution", "Résolution (px)"))
        self.lbl_layout.setText(tr("360_lbl_layout", "Disposition caméras"))
        self.lbl_cameras.setText(tr("360_lbl_cameras", "Nb caméras"))
        self.lbl_quality.setText(tr("360_lbl_quality", "Qualité JPEG"))
        self.lbl_format.setText(tr("360_lbl_format", "Format"))
        self.ai_group.setTitle(tr("360_ai_group", "IA avancé"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
        self.chk_mask_operator.setText(tr("360_mask_operator", "Masquer opérateur (YOLO)"))
        self.chk_skip_operator.setText(tr("360_skip_operator", "Sauter images avec opérateur"))
        self.chk_adaptive.setText(tr("360_adaptive", "Intervalle adaptatif"))
        self.lbl_motion.setText(tr("360_motion", "Seuil mouvement"))
