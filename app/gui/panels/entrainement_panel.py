"""Panneau Entraînement (étape PIPELINE) — équivalent de l'onglet Brush.

Barre de droite : Preset (dropdown, presets intégrés + personnalisés via
``merge_presets``), bouton « Enregistrer preset », champs essentiels (Steps,
SH Degree, Max Splats, Device), toggle Avancé (Résolution max, Args
supplémentaires, Viewer), sections repliables Densification et Checkpoints,
mode Nouveau/Refine. S'appuie sur ``BrushParams`` (Lot 1) : ``get_params()``
retourne un BrushParams, ``to_engine_params()`` produit la chaîne moteur (tokens
inchangés, allowlist côté BrushEngine).

Centre : mode Manuel/Indépendant (dataset/export/PLY), suivi d'exécution
(placeholder), toggle Visualiser après (bindé run_state).

Lot 3c : UI + BrushParams + presets. Le lancement réel (BrushWorker) passe par
le dispatch orchestré du StudioWindow.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.cli.commands import BRUSH_PRESETS
from app.core.brush_params import BrushParams
from app.core.brush_presets import merge_presets, save_user_preset
from app.core.i18n import add_language_observer, tr
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.dialog_utils import get_existing_directory


class EntrainementPanel:
    """Panneau plain exposant ``center`` et ``right`` (widgets Qt)."""

    def __init__(self, run_state):
        self.run_state = run_state
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        self._reload_presets()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Centre (mode manuel + suivi) ────────────────────────────────────────────
    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.manual_group = QGroupBox()
        mg = QVBoxLayout(self.manual_group)
        self.lbl_dataset = QLabel()
        mg.addWidget(self.lbl_dataset)
        ds_row = QHBoxLayout()
        self.input_path = QLineEdit()
        ds_row.addWidget(self.input_path)
        self.btn_browse_dataset = QPushButton("📁")
        self.btn_browse_dataset.clicked.connect(self._browse_dataset)
        ds_row.addWidget(self.btn_browse_dataset)
        mg.addLayout(ds_row)
        self.lbl_export = QLabel()
        mg.addWidget(self.lbl_export)
        ex_row = QHBoxLayout()
        self.output_path = QLineEdit()
        ex_row.addWidget(self.output_path)
        self.btn_browse_export = QPushButton("📁")
        self.btn_browse_export.clicked.connect(self._browse_export)
        ex_row.addWidget(self.btn_browse_export)
        mg.addLayout(ex_row)
        self.lbl_ply = QLabel()
        mg.addWidget(self.lbl_ply)
        self.ply_name_edit = QLineEdit()
        self.ply_name_edit.setPlaceholderText("output.ply")
        mg.addWidget(self.ply_name_edit)
        layout.addWidget(self.manual_group)

        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        layout.addStretch(1)
        return w

    # ── Barre de droite (preset → essentiel → avancé) ───────────────────────────
    def _build_right(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        # Preset + enregistrer
        preset_row = QHBoxLayout()
        self.lbl_preset = QLabel()
        self.combo_preset = QComboBox()
        self.combo_preset.currentIndexChanged.connect(self._apply_selected_preset)
        preset_row.addWidget(self.lbl_preset)
        preset_row.addWidget(self.combo_preset, 1)
        self.btn_save_preset = QPushButton("💾")
        self.btn_save_preset.clicked.connect(self._save_current_as_preset)
        preset_row.addWidget(self.btn_save_preset)
        layout.addLayout(preset_row)

        # Essentiels
        essential = QFormLayout()
        self.spin_total_steps = QSpinBox()
        self.spin_total_steps.setRange(1, 1_000_000)
        self.spin_total_steps.setValue(30000)
        self.lbl_steps = QLabel()
        essential.addRow(self.lbl_steps, self.spin_total_steps)
        self.sh_spin = QSpinBox()
        self.sh_spin.setRange(0, 4)
        self.sh_spin.setValue(3)
        self.lbl_sh = QLabel()
        essential.addRow(self.lbl_sh, self.sh_spin)
        self.spin_max_splats = QSpinBox()
        self.spin_max_splats.setRange(1000, 100_000_000)
        self.spin_max_splats.setValue(10_000_000)
        self.lbl_max_splats = QLabel()
        essential.addRow(self.lbl_max_splats, self.spin_max_splats)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["mps", "cuda", "cpu"])
        self.lbl_device = QLabel()
        essential.addRow(self.lbl_device, self.device_combo)
        layout.addLayout(essential)

        # Avancé (mémorisé plus tard — Lot 6)
        self.btn_advanced = QPushButton()
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.toggled.connect(self._on_advanced_toggled)
        layout.addWidget(self.btn_advanced)
        self.advanced_group = QWidget()
        ag = QFormLayout(self.advanced_group)
        self.max_resolution_spin = QSpinBox()
        self.max_resolution_spin.setRange(0, 8192)
        self.lbl_res = QLabel()
        ag.addRow(self.lbl_res, self.max_resolution_spin)
        self.custom_args_edit = QLineEdit()
        self.lbl_args = QLabel()
        ag.addRow(self.lbl_args, self.custom_args_edit)
        self.check_viewer = QCheckBox()
        ag.addRow(self.check_viewer)
        self.advanced_group.setVisible(False)
        layout.addWidget(self.advanced_group)

        # Densification (repliable)
        self.densif_group = QGroupBox()
        self.densif_group.setCheckable(True)
        self.densif_group.setChecked(False)
        dg = QFormLayout(self.densif_group)
        self.spin_start_iter = QSpinBox()
        self.spin_start_iter.setRange(0, 1_000_000)
        self.lbl_start_iter = QLabel()
        dg.addRow(self.lbl_start_iter, self.spin_start_iter)
        self.spin_refine = QSpinBox()
        self.spin_refine.setRange(1, 100_000)
        self.spin_refine.setValue(200)
        self.lbl_refine = QLabel()
        dg.addRow(self.lbl_refine, self.spin_refine)
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.0, 1.0)
        self.spin_threshold.setDecimals(5)
        self.spin_threshold.setSingleStep(0.0005)
        self.spin_threshold.setValue(0.003)
        self.lbl_threshold = QLabel()
        dg.addRow(self.lbl_threshold, self.spin_threshold)
        self.spin_fraction = QDoubleSpinBox()
        self.spin_fraction.setRange(0.0, 1.0)
        self.spin_fraction.setSingleStep(0.1)
        self.spin_fraction.setValue(0.2)
        self.lbl_fraction = QLabel()
        dg.addRow(self.lbl_fraction, self.spin_fraction)
        self.spin_growth_stop = QSpinBox()
        self.spin_growth_stop.setRange(0, 1_000_000)
        self.spin_growth_stop.setValue(15000)
        self.lbl_growth_stop = QLabel()
        dg.addRow(self.lbl_growth_stop, self.spin_growth_stop)
        layout.addWidget(self.densif_group)

        # Checkpoints (repliable)
        self.ckpt_group = QGroupBox()
        self.ckpt_group.setCheckable(True)
        self.ckpt_group.setChecked(False)
        cg = QFormLayout(self.ckpt_group)
        self.spin_checkpoint_interval = QSpinBox()
        self.spin_checkpoint_interval.setRange(0, 1_000_000)
        self.spin_checkpoint_interval.setValue(7000)
        self.lbl_ckpt_interval = QLabel()
        cg.addRow(self.lbl_ckpt_interval, self.spin_checkpoint_interval)
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("", "new")
        self.combo_mode.addItem("", "refine")
        self.lbl_mode = QLabel()
        cg.addRow(self.lbl_mode, self.combo_mode)
        layout.addWidget(self.ckpt_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Presets ─────────────────────────────────────────────────────────────────
    def _reload_presets(self):
        """Recharge le dropdown : « défaut » + intégrés + personnalisés."""
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItem(tr("brush_preset_default", "Défaut"), None)
        for name in merge_presets(BRUSH_PRESETS):
            self.combo_preset.addItem(name, name)
        self.combo_preset.blockSignals(False)

    def _apply_selected_preset(self, _index):
        name = self.combo_preset.currentData()
        if not name:
            return
        preset = merge_presets(BRUSH_PRESETS).get(name)
        if preset:
            self.set_params(BrushParams.from_dict({**self.get_params().to_dict(), **preset}))

    def _save_current_as_preset(self):
        name, ok = QInputDialog.getText(self.right, tr("brush_save_preset", "Enregistrer le preset"),
                                        tr("brush_preset_name", "Nom du preset"))
        if ok and name.strip():
            save_user_preset(name.strip(), self.get_params().to_dict())
            self._reload_presets()

    # ── Handlers ────────────────────────────────────────────────────────────────
    def _on_advanced_toggled(self, checked):
        self.advanced_group.setVisible(checked)

    def _browse_dataset(self):
        path = get_existing_directory(self.center, tr("brush_lbl_input", "Dossier dataset"))
        if path:
            self.input_path.setText(path)

    def _browse_export(self):
        path = get_existing_directory(self.center, tr("brush_lbl_output", "Dossier export"))
        if path:
            self.output_path.setText(path)

    # ── Params ────────────────────────────────────────────────────────────────────
    def get_params(self):
        return BrushParams(
            total_steps=self.spin_total_steps.value(),
            sh_degree=self.sh_spin.value(),
            max_splats=self.spin_max_splats.value(),
            device=self.device_combo.currentText(),
            max_resolution=self.max_resolution_spin.value() or None,
            with_viewer=self.check_viewer.isChecked(),
            custom_args=self.custom_args_edit.text(),
            start_iter=self.spin_start_iter.value() or None,
            refine_every=self.spin_refine.value(),
            growth_grad_threshold=self.spin_threshold.value(),
            growth_select_fraction=self.spin_fraction.value(),
            growth_stop_iter=self.spin_growth_stop.value() or None,
            checkpoint_interval=self.spin_checkpoint_interval.value(),
        )

    def set_params(self, params: BrushParams):
        if params.total_steps is not None:
            self.spin_total_steps.setValue(params.total_steps)
        if params.sh_degree is not None:
            self.sh_spin.setValue(params.sh_degree)
        if params.max_splats is not None:
            self.spin_max_splats.setValue(params.max_splats)
        if params.device:
            self.device_combo.setCurrentText(params.device)
        if params.max_resolution is not None:
            self.max_resolution_spin.setValue(params.max_resolution)
        self.check_viewer.setChecked(params.with_viewer)
        self.custom_args_edit.setText(params.custom_args or "")
        if params.start_iter is not None:
            self.spin_start_iter.setValue(params.start_iter)
        if params.refine_every is not None:
            self.spin_refine.setValue(params.refine_every)
        if params.growth_grad_threshold is not None:
            self.spin_threshold.setValue(params.growth_grad_threshold)
        if params.growth_select_fraction is not None:
            self.spin_fraction.setValue(params.growth_select_fraction)
        if params.growth_stop_iter is not None:
            self.spin_growth_stop.setValue(params.growth_stop_iter)
        if params.checkpoint_interval is not None:
            self.spin_checkpoint_interval.setValue(params.checkpoint_interval)

    def get_state(self):
        return self.get_params().to_dict()

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.manual_group.setTitle(tr("brush_group_paths", "Mode manuel / indépendant"))
        self.lbl_dataset.setText(tr("brush_lbl_input", "Dossier dataset (sparse + images)"))
        self.lbl_export.setText(tr("brush_lbl_output", "Dossier export"))
        self.lbl_ply.setText(tr("brush_lbl_ply", "Nom du fichier PLY (optionnel)"))
        self.chk_visualiser.setText(tr("chain_view_after", "Visualiser après"))
        self.lbl_preset.setText(tr("brush_lbl_preset", "Preset"))
        self.btn_save_preset.setToolTip(tr("brush_save_preset", "Enregistrer la config comme preset"))
        self.lbl_steps.setText(tr("brush_lbl_steps", "Steps total"))
        self.lbl_sh.setText(tr("brush_sh_degree", "SH Degree"))
        self.lbl_max_splats.setText(tr("brush_max_splats", "Max Splats"))
        self.lbl_device.setText(tr("brush_device", "Device"))
        self.btn_advanced.setText(tr("toggle_advanced", "Avancé"))
        self.lbl_res.setText(tr("brush_lbl_res", "Résolution max"))
        self.lbl_args.setText(tr("brush_args", "Arguments supplémentaires"))
        self.check_viewer.setText(tr("brush_viewer", "Activer le visualiseur pendant l'entraînement"))
        self.densif_group.setTitle(tr("brush_group_densif", "Densification"))
        self.lbl_start_iter.setText(tr("brush_start_iter", "Start iter"))
        self.lbl_refine.setText(tr("brush_refine_every", "Refine every"))
        self.lbl_threshold.setText(tr("brush_growth_threshold", "Growth grad threshold"))
        self.lbl_fraction.setText(tr("brush_growth_fraction", "Growth select fraction"))
        self.lbl_growth_stop.setText(tr("brush_growth_stop", "Growth stop iter"))
        self.ckpt_group.setTitle(tr("brush_group_ckpt", "Checkpoints"))
        self.lbl_ckpt_interval.setText(tr("brush_ckpt_interval", "Checkpoint interval"))
        self.lbl_mode.setText(tr("brush_lbl_mode", "Mode"))
        self.combo_mode.setItemText(0, tr("brush_mode_new", "Nouveau"))
        self.combo_mode.setItemText(1, tr("brush_mode_refine", "Refine"))
