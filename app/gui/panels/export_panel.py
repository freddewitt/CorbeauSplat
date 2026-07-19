"""Panneau Export (étape PIPELINE, optionnelle).

Construit directement sur ``ExportEngine``/``ExportWorker`` (cf. audit Lot 0 :
l'ancienne ExportTab a été supprimée, pas de résurrection — on s'appuie sur le
moteur intact).

Centre : sélection PLY (unique/multiple), dossier de sortie, progression.
Barre de droite : format cible, échelle, avertissement de dépendance manquante.

Lot 4 : UI + params. Le lancement réel (ExportWorker) passe par le dispatch /
bouton local (câblage moteurs, phase Apple Silicon).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.export_engine import ExportEngine
from app.core.i18n import add_language_observer, tr
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_names
from app.gui.widgets.drop_line_edit import DropLineEdit


class ExportPanel:
    """Panneau plain exposant ``center`` et ``right``."""

    def __init__(self, run_state):
        self.run_state = run_state
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

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
        self.combo_format = QComboBox()
        for fmt in ExportEngine.SUPPORTED_FORMATS:
            self.combo_format.addItem(fmt, fmt)
        self.combo_format.currentIndexChanged.connect(self._update_warning)
        self.lbl_format = QLabel()
        form.addRow(self.lbl_format, self.combo_format)

        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.01, 1000.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setValue(1.0)
        self.lbl_scale = QLabel()
        form.addRow(self.lbl_scale, self.spin_scale)
        layout.addLayout(form)

        self.lbl_warning = QLabel()
        self.lbl_warning.setWordWrap(True)
        self.lbl_warning.setStyleSheet("color: #e0af68;")
        layout.addWidget(self.lbl_warning)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def get_format(self):
        return self.combo_format.currentData()

    def get_scale(self):
        return self.spin_scale.value()

    def get_state(self):
        return {"format": self.get_format(), "scale": self.get_scale()}

    def set_state(self, state):
        if not state:
            return
        if state.get("format"):
            idx = self.combo_format.findData(state["format"])
            if idx >= 0:
                self.combo_format.setCurrentIndex(idx)
        if "scale" in state:
            self.spin_scale.setValue(state["scale"])

    def _update_warning(self, *_):
        # GLB nécessite une dépendance optionnelle (trimesh/open3d/assimp/blender).
        if self.get_format() == "glb":
            self.lbl_warning.setText(tr("export_glb_warning",
                                        "GLB nécessite trimesh/open3d (ou assimp/blender)."))
        else:
            self.lbl_warning.setText("")

    def _browse_input(self):
        paths, _ = get_open_file_names(self.center, tr("btn_browse", "Parcourir"), "",
                                       "Splats (*.ply *.spz);;Tous (*.*)")
        if paths:
            self.input_path.setText("|".join(paths))

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def retranslate_ui(self):
        self.lbl_input.setText(tr("export_input", "Fichier(s) PLY à exporter"))
        self.lbl_output.setText(tr("export_output", "Dossier de sortie"))
        self.lbl_format.setText(tr("export_format", "Format cible"))
        self.lbl_scale.setText(tr("export_scale", "Échelle"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
        self._update_warning()
