"""TOOLS module SplatTransform. Produces .ply/.spz/.splat → chaining possible."""

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
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.cancel_button import CancelButton
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class SplatTransformPanel:
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
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # avoid horizontal overflow (long labels)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["ply", "spz", "splat"])
        self.combo_format.currentTextChanged.connect(self._on_format_changed)
        self.lbl_format = QLabel()
        form.addRow(self.lbl_format, self.combo_format)
        layout.addLayout(form)

        self.filter_group = QGroupBox()
        fg = QVBoxLayout(self.filter_group)
        self.chk_filter_nan = QCheckBox()
        fg.addWidget(self.chk_filter_nan)
        self.chk_filter_floaters = QCheckBox()
        fg.addWidget(self.chk_filter_floaters)
        self.chk_morton = QCheckBox()
        fg.addWidget(self.chk_morton)
        self.chk_harmonics = QCheckBox()
        fg.addWidget(self.chk_harmonics)
        dec_row = QHBoxLayout()
        self.lbl_decimate = QLabel()
        self.spin_decimate = QDoubleSpinBox()
        self.spin_decimate.setRange(1.0, 100.0)
        self.spin_decimate.setValue(100.0)
        dec_row.addWidget(self.lbl_decimate)
        dec_row.addWidget(self.spin_decimate)
        fg.addLayout(dec_row)
        layout.addWidget(self.filter_group)

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

    def _on_format_changed(self, fmt):
        # --decimate requires a .ply output upstream; grey it out for other
        # formats instead of letting the user hit the launch-time error.
        is_ply = fmt == "ply"
        self.spin_decimate.setEnabled(is_ply)
        self.lbl_decimate.setEnabled(is_ply)
        if not is_ply:
            self.spin_decimate.setValue(100.0)

    def _browse_input(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"), "",
                                     "Splats (*.ply *.spz *.splat);;Tous (*.*)")
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def get_params(self):
        """Return the SplatTransform parameters as a dict."""
        return {
            "format": self.combo_format.currentText(),
            "filter_nan": self.chk_filter_nan.isChecked(),
            "filter_floaters": self.chk_filter_floaters.isChecked(),
            "morton": self.chk_morton.isChecked(),
            "harmonics": self.chk_harmonics.isChecked(),
            "decimate": self.spin_decimate.value(),
        }

    def retranslate_ui(self):
        # The only panel of the ten to have forgotten this line: its Launch
        # button used to show up empty, built with no text and never retranslated.
        self.btn_run.setText(tr("btn_run", "Lancer"))
        self.lbl_status.setText(tr("st_status", "Moteur SplatTransform"))
        self.lbl_input.setText(tr("st_input", "Entrée (.ply/.spz/.splat)"))
        self.lbl_output.setText(tr("st_output", "Dossier de sortie"))
        self.lbl_format.setText(tr("st_lbl_format", "Format de sortie"))
        self.filter_group.setTitle(tr("st_group_filters", "Filtres"))
        self.chk_filter_nan.setText(tr("st_filter_nan", "Supprimer splats dégénérés"))
        self.chk_filter_floaters.setText(tr("st_filter_floaters", "Supprimer îlots isolés"))
        self.chk_morton.setText(tr("st_morton", "Optimiser l'ordre spatial"))
        self.chk_harmonics.setText(tr("st_harmonics", "Réduire harmoniques sphériques"))
        self.lbl_decimate.setText(tr("st_decimate", "Décimer (% conservé)"))
        self.lbl_automation.setText(tr("automation_title", "Automatisation"))
        self.chk_nettoyer.setText(tr("chain_clean_after", "Nettoyage"))
        self.chk_exporter.setText(tr("chain_export_after", "Exporter"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
