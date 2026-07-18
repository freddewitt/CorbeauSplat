"""Panneau Source (étape PIPELINE).

Reprend la logique de saisie de ``ConfigTab`` (input, dossier de sortie,
destination checkpoints, FPS, suppression dataset) dans le nouveau layout
centre + barre de droite, avec la hiérarchie essentiel/avancé.

Point d'architecture clé : les toggles de chaînage (« Entraînement après »,
« Nettoyer après », « Exporter après », « Visualiser après ») et
``undistort_images`` sont **bindés sur le ``RunState`` partagé** — pas d'état
interne dupliqué (cf. dette technique cluster B).

Lot 3a : saisie + binding run_state. Le dispatch réel du run (Source →
Reconstruction → Entraînement) est câblé au sous-lot 3c, une fois les 3 panneaux
présents.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit

_BLUR_STRENGTHS = (("light", "Léger"), ("medium", "Moyen"), ("strong", "Fort"))


class SourcePanel:
    """Panneau plain exposant ``center`` et ``right`` (widgets Qt)."""

    def __init__(self, run_state):
        self.run_state = run_state
        # Conserver les observateurs run_state vivants (évite le GC des closures).
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Centre ──────────────────────────────────────────────────────────────────
    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.lbl_project = QLabel()
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        layout.addWidget(self.lbl_project)
        layout.addWidget(self.input_project_name)

        # Entrée (glisser-déposer dossier/fichier/vidéo)
        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = DropLineEdit()
        in_row.addWidget(self.input_path)
        self.btn_browse_input_dir = QPushButton("📁")
        self.btn_browse_input_dir.clicked.connect(self._browse_input_dir)
        in_row.addWidget(self.btn_browse_input_dir)
        self.btn_browse_input_file = QPushButton("🎞")
        self.btn_browse_input_file.clicked.connect(self._browse_input_file)
        in_row.addWidget(self.btn_browse_input_file)
        layout.addLayout(in_row)

        # Dossier de sortie
        self.lbl_output = QLabel()
        layout.addWidget(self.lbl_output)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addLayout(out_row)

        # Destination checkpoints (optionnel)
        self.lbl_ckpt = QLabel()
        self.lbl_ckpt.setWordWrap(True)
        layout.addWidget(self.lbl_ckpt)
        ck_row = QHBoxLayout()
        self.checkpoint_dest = QLineEdit()
        ck_row.addWidget(self.checkpoint_dest)
        self.btn_browse_ckpt = QPushButton("📁")
        self.btn_browse_ckpt.clicked.connect(self._browse_ckpt)
        ck_row.addWidget(self.btn_browse_ckpt)
        layout.addLayout(ck_row)

        # FPS (vidéo)
        fps_row = QHBoxLayout()
        self.lbl_fps = QLabel()
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(2)
        fps_row.addWidget(self.lbl_fps)
        fps_row.addWidget(self.fps_spin)
        fps_row.addStretch(1)
        layout.addLayout(fps_row)

        layout.addStretch(1)

        # Action destructive séparée visuellement.
        self.btn_delete_dataset = QPushButton()
        self.btn_delete_dataset.setStyleSheet("color: #f7768e;")
        layout.addWidget(self.btn_delete_dataset)
        return w

    # ── Barre de droite (essentiel / avancé) ────────────────────────────────────
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

        # ── Automatisation (chaînage) ─── ordre : Brush → Nettoyage → Export → Vue
        self.lbl_automation = QLabel()
        self.lbl_automation.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_automation)

        self.chk_entrainement = QCheckBox()
        self._bind(self.chk_entrainement, "entrainement_apres")
        layout.addWidget(self.chk_entrainement)

        # Nettoyer (n'ouvre rien de plus ici — réglages dans l'étape Nettoyage)
        self.chk_nettoyer = QCheckBox()
        self._bind(self.chk_nettoyer, "nettoyer_apres")
        layout.addWidget(self.chk_nettoyer)

        # Exporter → révèle dossier + format
        self.chk_exporter = QCheckBox()
        self._bind(self.chk_exporter, "exporter_apres")
        layout.addWidget(self.chk_exporter)
        self.export_group = QGroupBox()
        eg = QVBoxLayout(self.export_group)
        self.export_dir = QLineEdit()
        self.export_dir.setPlaceholderText("…")
        eg.addWidget(self.export_dir)
        self.combo_export_format = QComboBox()
        for fmt in ("spz", "glb", "obj", "ply", "xyz"):
            self.combo_export_format.addItem(fmt, fmt)
        eg.addWidget(self.combo_export_format)
        self.export_group.setVisible(False)
        self.chk_exporter.toggled.connect(self.export_group.setVisible)
        layout.addWidget(self.export_group)

        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        # Bouton Avancé (mémorisé plus tard, Lot 3 hiérarchie)
        self.btn_advanced = QPushButton()
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.toggled.connect(self._on_advanced_toggled)
        layout.addWidget(self.btn_advanced)

        self.advanced_group = QWidget()
        ag = QVBoxLayout(self.advanced_group)
        self.chk_upscale = QCheckBox()
        ag.addWidget(self.chk_upscale)
        self.chk_undistort = QCheckBox()
        self._bind(self.chk_undistort, "undistort_images")
        ag.addWidget(self.chk_undistort)
        self.chk_filter_blur = QCheckBox()
        ag.addWidget(self.chk_filter_blur)
        blur_row = QHBoxLayout()
        self.lbl_blur = QLabel()
        self.combo_blur = QComboBox()
        for value, _label in _BLUR_STRENGTHS:
            self.combo_blur.addItem(value, value)
        self.combo_blur.setCurrentIndex(1)  # medium
        blur_row.addWidget(self.lbl_blur)
        blur_row.addWidget(self.combo_blur)
        ag.addLayout(blur_row)
        self.chk_stabilized = QCheckBox()
        ag.addWidget(self.chk_stabilized)
        self.advanced_group.setVisible(False)
        layout.addWidget(self.advanced_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Handlers ────────────────────────────────────────────────────────────────
    def _on_advanced_toggled(self, checked):
        self.advanced_group.setVisible(checked)

    def _browse_input_dir(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_input_file(self):
        path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def _browse_ckpt(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.checkpoint_dest.setText(path)

    # ── Persistance (utilisée par config_io plus tard) ──────────────────────────
    def get_state(self):
        return {
            "project_name": self.input_project_name.text(),
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "checkpoint_dest": self.checkpoint_dest.text(),
            "fps": self.fps_spin.value(),
            "upscale": self.chk_upscale.isChecked(),
            "filter_blur": self.chk_filter_blur.isChecked(),
            "blur_strength": self.combo_blur.currentData(),
            "stabilized": self.chk_stabilized.isChecked(),
            "export_dir": self.export_dir.text(),
            "export_format": self.combo_export_format.currentData(),
        }

    def set_state(self, state):
        if not state:
            return
        self.input_project_name.setText(state.get("project_name", ""))
        self.input_path.setText(state.get("input_path", ""))
        self.output_path.setText(state.get("output_path", ""))
        self.checkpoint_dest.setText(state.get("checkpoint_dest", ""))
        if "fps" in state:
            self.fps_spin.setValue(state["fps"])
        self.chk_upscale.setChecked(state.get("upscale", False))
        self.chk_filter_blur.setChecked(state.get("filter_blur", False))
        if state.get("blur_strength"):
            idx = self.combo_blur.findData(state["blur_strength"])
            if idx >= 0:
                self.combo_blur.setCurrentIndex(idx)
        self.chk_stabilized.setChecked(state.get("stabilized", False))
        self.export_dir.setText(state.get("export_dir", ""))
        if state.get("export_format"):
            idx = self.combo_export_format.findData(state["export_format"])
            if idx >= 0:
                self.combo_export_format.setCurrentIndex(idx)

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.lbl_project.setText(tr("label_project_name", "Nom du projet"))
        self.lbl_input.setText(tr("source_input", "Source (dossier / fichier / vidéo)"))
        self.lbl_output.setText(tr("source_output", "Dossier de sortie"))
        self.lbl_ckpt.setText(tr("source_checkpoint_dest", "Destination des checkpoints (optionnel)"))
        self.lbl_fps.setText(tr("label_fps", "Images/s (vidéo)"))
        self.btn_delete_dataset.setText(tr("source_delete_dataset", "Supprimer le dataset existant"))
        self.lbl_automation.setText(tr("automation_title", "Automatisation"))
        self.chk_entrainement.setText(tr("chain_train_after", "Lancer Brush"))
        self.chk_nettoyer.setText(tr("chain_clean_after", "Nettoyage"))
        self.chk_exporter.setText(tr("chain_export_after", "Exporter"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        self.export_group.setTitle(tr("source_export_options", "Options d'export"))
        self.btn_advanced.setText(tr("toggle_advanced", "Avancé"))
        self.chk_upscale.setText(tr("source_upscale", "Upscaler les images"))
        self.chk_undistort.setText(tr("source_undistort", "Générer images non-distordues"))
        self.chk_filter_blur.setText(tr("source_filter_blur", "Supprimer les images floues"))
        self.lbl_blur.setText(tr("source_blur_strength", "Intensité du filtre flou"))
        self.chk_stabilized.setText(tr("source_stabilized", "Mode stabilisé"))
