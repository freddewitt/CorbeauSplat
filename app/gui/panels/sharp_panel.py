"""Module OUTILS ML Sharp (Photo/Vidéo → PLY).

Centre : statut moteur, toggle Image/Vidéo, entrée (DropLineEdit), sortie.
Barre de droite : device, checkpoint optionnel, verbose, upscaler avant, et
toggles Nettoyer/Exporter/Visualiser après (le module produit un .ply).

Lot 5 : UI + params. Lancement réel (SharpWorker/SharpVideoWorker) = phase moteurs.
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
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.cancel_button import CancelButton
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class SharpPanel:
    def __init__(self, run_state):
        self.run_state = run_state
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)

        mode_row = QHBoxLayout()
        self.radio_image = QRadioButton()
        self.radio_image.setChecked(True)
        self.radio_video = QRadioButton()
        mode_row.addWidget(self.radio_image)
        mode_row.addWidget(self.radio_video)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

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
        self.btn_cancel = CancelButton()
        layout.addWidget(self.btn_cancel)
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
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["mps", "cuda", "cpu"])
        self.lbl_device = QLabel()
        form.addRow(self.lbl_device, self.device_combo)
        ck_row = QHBoxLayout()
        self.checkpoint_edit = QLineEdit()
        self.btn_browse_ckpt = QPushButton("📁")
        self.btn_browse_ckpt.clicked.connect(self._browse_ckpt)
        ck_row.addWidget(self.checkpoint_edit)
        ck_row.addWidget(self.btn_browse_ckpt)
        self.lbl_ckpt = QLabel()
        form.addRow(self.lbl_ckpt, ck_row)
        layout.addLayout(form)

        self.chk_verbose = QCheckBox()
        layout.addWidget(self.chk_verbose)
        self.chk_upscale_before = QCheckBox()
        layout.addWidget(self.chk_upscale_before)

        self.lbl_automation = QLabel()
        self.lbl_automation.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_automation)
        self.chk_nettoyer = QCheckBox()
        self._bind(self.chk_nettoyer, "nettoyer_apres")
        layout.addWidget(self.chk_nettoyer)
        self.chk_exporter = QCheckBox()
        self._bind(self.chk_exporter, "exporter_apres")
        layout.addWidget(self.chk_exporter)
        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    def is_video(self):
        return self.radio_video.isChecked()

    def get_params(self):
        """Retourne les paramètres Sharp sous forme de dict."""
        return {
            "mode": "video" if self.is_video() else "image",
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "video_path": self.input_path.text() if self.is_video() else "",
            "video_output_path": self.output_path.text() if self.is_video() else "",
            "device": self.device_combo.currentText(),
            "checkpoint": self.checkpoint_edit.text(),
            "verbose": self.chk_verbose.isChecked(),
            "upscale": self.chk_upscale_before.isChecked(),
        }

    def _browse_input(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def _browse_ckpt(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"), "", "Checkpoint (*.pt)")
        if path:
            self.checkpoint_edit.setText(path)

    def retranslate_ui(self):
        self.lbl_status.setText(tr("sharp_status", "Moteur ML Sharp"))
        self.radio_image.setText(tr("sharp_mode_image", "Image → PLY"))
        self.radio_video.setText(tr("sharp_mode_video", "Vidéo → PLY"))
        self.lbl_input.setText(tr("sharp_input", "Entrée (image / vidéo)"))
        self.lbl_output.setText(tr("sharp_output", "Dossier de sortie"))
        self.lbl_device.setText(tr("brush_device", "Device"))
        self.lbl_ckpt.setText(tr("sharp_checkpoint", "Checkpoint (.pt)"))
        self.chk_verbose.setText(tr("sharp_verbose", "Mode Verbose"))
        self.chk_upscale_before.setText(tr("sharp_upscale_before", "Upscaler avant traitement"))
        self.lbl_automation.setText(tr("automation_title", "Automatisation"))
        self.chk_nettoyer.setText(tr("chain_clean_after", "Nettoyage"))
        self.chk_exporter.setText(tr("chain_export_after", "Exporter"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
