"""Panneau Visualiser (étape PIPELINE, optionnelle) — équivalent de SuperSplatTab.

Centre : sélection du fichier (.ply/.spz), bouton Démarrer/Arrêter local
(indépendant du bouton Lancer global), statut serveur, rappel URL.
Barre de droite : ports, No UI, position et rotation caméra.

Lot 4 : UI + params + état local du bouton. Le démarrage réel du serveur
(``SuperSplatEngine.start_data_server``/``stop_all``) est câblé dans la phase
moteurs (surface Apple Silicon) ; le closeEvent devra appeler ``stop_all()``.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.widgets.dialog_utils import get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class VisualiserPanel:
    """Panneau plain exposant ``center`` et ``right``."""

    def __init__(self, run_state):
        self.run_state = run_state
        self._running = False
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

        self.btn_toggle = QPushButton()
        self.btn_toggle.clicked.connect(self.toggle_server)
        layout.addWidget(self.btn_toggle)

        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)
        self.lbl_url = QLabel()
        self.lbl_url.setWordWrap(True)
        layout.addWidget(self.lbl_url)
        self.btn_reopen = QPushButton()
        self.btn_reopen.setEnabled(False)
        layout.addWidget(self.btn_reopen)

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

        self.splat_port = QSpinBox()
        self.splat_port.setRange(1024, 65535)
        self.splat_port.setValue(3000)
        self.lbl_splat_port = QLabel()
        form.addRow(self.lbl_splat_port, self.splat_port)
        self.data_port = QSpinBox()
        self.data_port.setRange(1024, 65535)
        self.data_port.setValue(8000)
        self.lbl_data_port = QLabel()
        form.addRow(self.lbl_data_port, self.data_port)

        self.chk_no_ui = QCheckBox()
        form.addRow(self.chk_no_ui)

        self.cam_pos = {}
        self.lbl_cam_pos = QLabel()
        form.addRow(self.lbl_cam_pos)
        for axis in ("x", "y", "z"):
            spin = QDoubleSpinBox()
            spin.setRange(-10000.0, 10000.0)
            spin.setDecimals(3)
            self.cam_pos[axis] = spin
            form.addRow(QLabel(f"Position {axis.upper()}"), spin)

        self.cam_rot = {}
        self.lbl_cam_rot = QLabel()
        form.addRow(self.lbl_cam_rot)
        for axis in ("x", "y", "z"):
            spin = QDoubleSpinBox()
            spin.setRange(-360.0, 360.0)
            spin.setDecimals(1)
            self.cam_rot[axis] = spin
            form.addRow(QLabel(f"Rotation {axis.upper()}"), spin)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def toggle_server(self):
        """Bascule l'état local. Le démarrage réel du serveur SuperSplat est
        câblé dans la phase moteurs (surface Apple Silicon)."""
        self._running = not self._running
        self._refresh_status()

    def is_running(self):
        return self._running

    def _refresh_status(self):
        if self._running:
            self.lbl_status.setText(tr("status_running", "Statut : En cours"))
            self.btn_toggle.setText(tr("btn_stop", "Arrêter"))
        else:
            self.lbl_status.setText(tr("status_stopped", "Statut : Arrêté"))
            self.btn_toggle.setText(tr("btn_start_view", "Démarrer"))

    def _browse_input(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"),
                                     "", "Splats (*.ply *.spz);;Tous (*.*)")
        if path:
            self.input_path.setText(path)

    def retranslate_ui(self):
        self.lbl_input.setText(tr("view_input", "Fichier à visualiser (.ply/.spz)"))
        self.lbl_url.setText("")
        self.btn_reopen.setText(tr("view_reopen", "Rouvrir dans le navigateur"))
        self.lbl_splat_port.setText(tr("lbl_splat_port", "Port SuperSplat"))
        self.lbl_data_port.setText(tr("lbl_data_port", "Port Données"))
        self.chk_no_ui.setText(tr("check_no_ui", "Masquer l'interface (No UI)"))
        self.lbl_cam_pos.setText(tr("view_cam_pos", "Position caméra (X, Y, Z)"))
        self.lbl_cam_rot.setText(tr("view_cam_rot", "Rotation caméra (X, Y, Z°)"))
        self._refresh_status()
