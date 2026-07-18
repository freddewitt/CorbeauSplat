"""Module OUTILS 4DGS (préparation dataset multi-caméras pour Nerfstudio).

Pas de sortie .ply exploitable → pas de chaînage Nettoyer/Exporter/Visualiser.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from app.gui.widgets.dialog_utils import get_existing_directory


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

        self.btn_colmap_only = QPushButton()
        layout.addWidget(self.btn_colmap_only)

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
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        self.lbl_fps = QLabel()
        form.addRow(self.lbl_fps, self.fps_spin)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _browse_input(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def retranslate_ui(self):
        self.lbl_desc.setText(tr("four_dgs_desc",
                                 "Extrait des frames de vidéos synchronisées et prépare un dataset Nerfstudio."))
        self.lbl_status.setText(tr("four_dgs_status", "Statut d'installation"))
        self.lbl_input.setText(tr("four_dgs_input", "Source vidéos (dossier multi-caméras)"))
        self.lbl_output.setText(tr("four_dgs_output", "Destination dataset"))
        self.btn_colmap_only.setText(tr("four_dgs_colmap_only", "Reconstruction COLMAP seulement"))
        self.lbl_fps.setText(tr("four_dgs_lbl_fps", "Extraction FPS"))
