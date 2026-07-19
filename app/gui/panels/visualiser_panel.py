"""Panneau Visualiser (étape PIPELINE, optionnelle) — équivalent de SuperSplatTab.

Centre : sélection du fichier (.ply/.spz), bouton Démarrer/Arrêter local
(indépendant du bouton Lancer global), statut serveur, rappel URL.
Barre de droite : ports, No UI, position et rotation caméra.

Le démarrage/arrêt réel du serveur (``SuperSplatEngine.start_supersplat`` +
``start_data_server``) est câblé sur le bouton local ``btn_toggle`` — pas un
``Worker``/``QThread`` comme les autres modules (serveur continu, pas un
traitement avec fin), donc indépendant du bouton Lancer/Annuler global de la
topbar. ``StudioWindow.closeEvent`` appelle ``self.engine.stop_all()`` en
sécurité pour ne pas laisser de serveur orphelin à la fermeture.
"""

import webbrowser
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.superplat_engine import SuperSplatEngine
from app.gui.widgets.dialog_utils import get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class VisualiserPanel:
    """Panneau plain exposant ``center`` et ``right``."""

    def __init__(self, run_state):
        self.run_state = run_state
        self._running = False
        # Instancié dès maintenant (comme l'ancien SuperSplatTab) pour que le
        # closeEvent de StudioWindow puisse toujours appeler stop_all(), même
        # avant que toggle_server() ne soit câblé au moteur réel.
        self.engine = SuperSplatEngine()
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
        self.btn_reopen.clicked.connect(self._open_browser)
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
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)

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
        """Démarre ou arrête réellement le serveur SuperSplat (bouton local
        indépendant du bouton Lancer/Annuler global)."""
        if self._running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        success, msg = self.engine.start_supersplat(self.splat_port.value())
        if not success:
            QMessageBox.critical(self.center, tr("msg_error", "Erreur"), msg)
            return

        path_str = self.input_path.text().strip()
        if path_str:
            path = Path(path_str)
            if path.exists():
                directory = path if path.is_dir() else path.parent
                success_data, msg_data = self.engine.start_data_server(
                    str(directory), self.data_port.value()
                )
                if not success_data:
                    QMessageBox.warning(self.center, tr("msg_warning", "Attention"), msg_data)
                    self.engine.stop_supersplat()
                    return

        self._running = True
        self.btn_reopen.setEnabled(True)
        self._refresh_status()
        # Ouvre le navigateur après 1.5s pour laisser le serveur démarrer.
        QTimer.singleShot(1500, self._open_browser)

    def _stop_server(self):
        self.engine.stop_all()
        self._running = False
        self.btn_reopen.setEnabled(False)
        self._refresh_status()

    def _build_url(self):
        url = f"http://localhost:{self.splat_port.value()}"
        params = []

        path_str = self.input_path.text().strip()
        if path_str:
            path = Path(path_str)
            if path.exists():
                data_url = f"http://localhost:{self.data_port.value()}/{path.name}"
                params.append(f"load={quote(data_url, safe=':/')}")

        if self.chk_no_ui.isChecked():
            params.append("noui")

        pos = [self.cam_pos[axis].value() for axis in ("x", "y", "z")]
        if any(pos):
            params.append("cameraPosition=" + ",".join(f"{v:g}" for v in pos))
        rot = [self.cam_rot[axis].value() for axis in ("x", "y", "z")]
        if any(rot):
            params.append("cameraRotation=" + ",".join(f"{v:g}" for v in rot))

        if params:
            url += "?" + "&".join(params)
        return url

    def _open_browser(self):
        if not self._running:
            return
        url = self._build_url()
        self.lbl_url.setText(url)
        webbrowser.open(url)

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
