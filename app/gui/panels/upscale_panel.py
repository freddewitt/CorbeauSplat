"""Module OUTILS Upscale (upscayl-ncnn). Sortie image → pas de chaînage .ply."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from app.gui.widgets.dialog_utils import get_existing_directory
from app.gui.widgets.drop_line_edit import DropLineEdit


class UpscalePanel:
    def __init__(self, run_state):
        self.run_state = run_state
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)
        self.lbl_catalog = QLabel()
        self.lbl_catalog.setWordWrap(True)
        layout.addWidget(self.lbl_catalog)

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

        self.combo_model = QComboBox()
        self.lbl_model = QLabel()
        form.addRow(self.lbl_model, self.combo_model)
        self.combo_scale = QComboBox()
        for s in (1, 2, 4):
            self.combo_scale.addItem(f"x{s}", s)
        self.combo_scale.setCurrentIndex(2)
        self.lbl_scale = QLabel()
        form.addRow(self.lbl_scale, self.combo_scale)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG", "JPEG", "WebP"])
        self.lbl_format = QLabel()
        form.addRow(self.lbl_format, self.combo_format)
        self.spin_tile = QSpinBox()
        self.spin_tile.setRange(0, 1024)
        self.lbl_tile = QLabel()
        form.addRow(self.lbl_tile, self.spin_tile)

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
        self.lbl_status.setText(tr("up_status", "Moteur Upscale"))
        self.lbl_catalog.setText(tr("up_catalog", "Catalogue des modèles (à télécharger/gérer)"))
        self.lbl_input.setText(tr("up_input", "Source (fichier ou dossier)"))
        self.lbl_output.setText(tr("up_output", "Destination"))
        self.lbl_model.setText(tr("up_model", "Modèle actif"))
        self.lbl_scale.setText(tr("up_output_scale", "Échelle de sortie"))
        self.lbl_format.setText(tr("up_output_format", "Format de sortie"))
        self.lbl_tile.setText(tr("up_tile", "Taille des tuiles"))
