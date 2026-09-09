"""Source panel (PIPELINE step).

Carries over ``ConfigTab``'s input logic (input, output folder, checkpoint
destination, FPS, dataset deletion) into the new center + right bar layout,
with the essential/advanced hierarchy.

Key architecture point: the chaining toggles ("Train after", "Clean after",
"Export after", "Visualize after") and ``undistort_images`` are **bound to
the shared ``RunState``** — no duplicated internal state (cf. cluster B
technical debt).

Batch 3a: input + run_state binding. The actual run dispatch (Source →
Reconstruction → Training) is wired in sub-batch 3c, once the 3 panels
are in place.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
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

from app.core.export_engine import ExportEngine
from app.core.i18n import add_language_observer, tr
from app.gui.panels.reconstruction_logic import detect_source_kind
from app.gui.run_state_binding import bind_flag_checkbox, bind_text_field
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.progress_ring import ProgressRing

_BLUR_STRENGTHS = (("light", "Léger"), ("medium", "Moyen"), ("strong", "Fort"))

# Pipeline modes dropdown, migrated from the former ``topbar.py`` (internal
# value, i18n key, French default). Kept verbatim so existing i18n keys and
# ``current_mode()``/``set_running()`` callers keep working unchanged.
PIPELINE_MODES = (
    ("gsplat", "mode_gsplat", "Gsplat"),
    ("sharp", "mode_sharp", "Sharp"),
    ("4dgs", "mode_4dgs", "4DGS"),
)

# Source type dropdown (internal value, i18n key, French default). "auto" lets
# detect_source_kind() decide from the Input field content; the other two
# force the resolved kind regardless of what's on disk.
_SOURCE_TYPES = (
    ("auto", "source_type_auto", "Auto"),
    ("images", "source_type_images", "Images"),
    ("video", "source_type_video", "Vidéo"),
)


class SourcePanel:
    """Plain panel exposing ``center`` and ``right`` (Qt widgets)."""

    def __init__(self, run_state):
        self.run_state = run_state
        # Keep the run_state observers alive (avoids GC of the closures).
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Center ────────────────────────────────────────────────────────────────
    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.lbl_project = QLabel()
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        # Mirror of the top bar: single source of truth in run_state (cf.
        # bind_text_field, same idiom as the chaining flags).
        self._bindings.append(bind_text_field(self.input_project_name, self.run_state, "project_name"))
        layout.addWidget(self.lbl_project)
        layout.addWidget(self.input_project_name)

        # Pipeline mode (migrated from topbar.py, which will disappear).
        # KNOWN LIMITATION (cf. ETAT_DES_LIEUX.md §11 question 1): only "gsplat"
        # actually routes to COLMAP+Brush when btn_run is clicked. "sharp" and
        # "4dgs" stay selectable here but launching does not execute them — they
        # are only reachable via OUTILS > Sharp and OUTILS > 4DGS (COLMAP dataset
        # prep only for the latter). 4DGS has no Apple Silicon trainer available
        # to date, so this is not a regression, just an unfinished routing.
        mode_row = QHBoxLayout()
        self.lbl_mode = QLabel()
        self.combo_mode = QComboBox()
        for value, key, default in PIPELINE_MODES:
            self.combo_mode.addItem(tr(key, default), value)
        fourdgs_index = self.combo_mode.findData("4dgs")
        self.combo_mode.setItemData(
            fourdgs_index,
            tr(
                "fourdgs_mode_tooltip",
                "Préparation de dataset uniquement — pas d'entraînement disponible sur Apple Silicon.",
            ),
            Qt.ItemDataRole.ToolTipRole,
        )
        mode_row.addWidget(self.lbl_mode)
        mode_row.addWidget(self.combo_mode)
        layout.addLayout(mode_row)

        # Source type (Images / Video / Auto) — drives the FPS field's visibility.
        self.lbl_source_type = QLabel()
        source_type_row = QHBoxLayout()
        self.combo_source_type = QComboBox()
        for value, key, default in _SOURCE_TYPES:
            self.combo_source_type.addItem(tr(key, default), value)
        self.combo_source_type.setCurrentIndex(0)  # "auto" by default
        self.combo_source_type.currentIndexChanged.connect(self._evaluate_source_type)
        source_type_row.addWidget(self.lbl_source_type)
        source_type_row.addWidget(self.combo_source_type)
        layout.addLayout(source_type_row)

        # Input (drag-and-drop folder/file/video)
        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = DropLineEdit()
        # Debounce ~300ms: avoids rescanning the disk on every keystroke when
        # "Auto" is selected.
        self._source_type_timer = QTimer()
        self._source_type_timer.setSingleShot(True)
        self._source_type_timer.timeout.connect(self._evaluate_source_type)
        self.input_path.textChanged.connect(lambda _text: self._source_type_timer.start(300))
        in_row.addWidget(self.input_path)
        self.btn_browse_input_dir = QPushButton("📁")
        self.btn_browse_input_dir.clicked.connect(self._browse_input_dir)
        in_row.addWidget(self.btn_browse_input_dir)
        self.btn_browse_input_file = QPushButton("🎞")
        self.btn_browse_input_file.clicked.connect(self._browse_input_file)
        in_row.addWidget(self.btn_browse_input_file)
        layout.addLayout(in_row)

        # FPS (video)
        fps_row = QHBoxLayout()
        self.lbl_fps = QLabel()
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(2)
        fps_row.addWidget(self.lbl_fps)
        fps_row.addWidget(self.fps_spin)
        fps_row.addStretch(1)
        layout.addLayout(fps_row)

        # Error banner — images+video mix detected in Auto mode.
        self.lbl_err_mixed = QLabel()
        self.lbl_err_mixed.setWordWrap(True)
        self.lbl_err_mixed.setStyleSheet("color: #e0af68;")
        self.lbl_err_mixed.setVisible(False)
        layout.addWidget(self.lbl_err_mixed)

        # Output folder
        self.lbl_output = QLabel()
        layout.addWidget(self.lbl_output)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addLayout(out_row)

        # Checkpoint destination (optional)
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

        layout.addStretch(1)

        # Main action button, visually separated above the destructive
        # button. Not connected here — StudioWindow connects to it in a
        # later pass (replaces topbar.launchRequested).
        self.btn_run = QPushButton()
        # objectName-based rule in styles.py's _STYLESHEET ($accent /
        # $highlight_text) so this button stays the single accented primary
        # action across all 3 themes and theme switches, without redeclaring
        # background/color here (which would conflict with set_running()'s
        # Launch/Cancel toggle — see set_running() below).
        self.btn_run.setObjectName("btn_primary")

        # Activity ring, directly above Launch. Hidden while idle, so the panel
        # looks unchanged outside a run. Centred rather than stretched: a ring
        # widened to the panel would stop reading as a ring.
        ring_row = QHBoxLayout()
        ring_row.addStretch(1)
        self.progress_ring = ProgressRing()
        ring_row.addWidget(self.progress_ring)
        ring_row.addStretch(1)
        layout.addLayout(ring_row)

        layout.addWidget(self.btn_run)

        # Generous spacing + separator rule: the destructive action must
        # never be mistaken for the primary action above.
        layout.addSpacing(20)
        delete_separator = QFrame()
        delete_separator.setFrameShape(QFrame.Shape.HLine)
        delete_separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(delete_separator)
        layout.addSpacing(8)

        self.btn_delete_dataset = QPushButton()
        self.btn_delete_dataset.setStyleSheet("color: #f7768e;")
        layout.addWidget(self.btn_delete_dataset)

        self._evaluate_source_type()
        return w

    # ── Right bar (essential / advanced) ────────────────────────────────────────
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

        # ── Advanced options ─── always visible (no more collapse/expand)
        self.lbl_advanced = QLabel()
        self.lbl_advanced.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_advanced)

        self.advanced_group = QWidget()
        ag = QVBoxLayout(self.advanced_group)
        # Source 360°: first pre-step. It produces the folder of planar
        # images that Upscale then COLMAP consume — hence its position first,
        # before Undistort. Unchecked by default.
        self.chk_360 = QCheckBox()
        self._bind(self.chk_360, "source_360")
        ag.addWidget(self.chk_360)
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
        layout.addWidget(self.advanced_group)

        # ── Automation (chaining) ─── actual execution order:
        # 360 → Upscale → Brush → Clean → Export → View
        self.lbl_automation = QLabel()
        self.lbl_automation.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_automation)

        # Upscale: second pre-step (it enlarges images before COLMAP).
        # Unchecked by default, unlike Brush.
        self.chk_upscaler = QCheckBox()
        self._bind(self.chk_upscaler, "upscaler_avant")
        layout.addWidget(self.chk_upscaler)

        self.chk_entrainement = QCheckBox()
        self._bind(self.chk_entrainement, "entrainement_apres")
        # Brush checked by default — bind_flag_checkbox() just imposed the
        # run_state value ("entrainement_apres" defaults to False); we correct
        # it afterward (emits toggled -> syncs run_state).
        self.chk_entrainement.setChecked(True)
        layout.addWidget(self.chk_entrainement)

        # Clean (opens nothing more here — settings live in the Clean step)
        self.chk_nettoyer = QCheckBox()
        self._bind(self.chk_nettoyer, "nettoyer_apres")
        layout.addWidget(self.chk_nettoyer)

        # Export → reveals folder + format
        self.chk_exporter = QCheckBox()
        self._bind(self.chk_exporter, "exporter_apres")
        layout.addWidget(self.chk_exporter)
        self.export_group = QGroupBox()
        eg = QVBoxLayout(self.export_group)
        self.export_dir = QLineEdit()
        self.export_dir.setPlaceholderText("…")
        eg.addWidget(self.export_dir)
        self.combo_export_format = QComboBox()
        # Same source as the Export panel's combo: two hardcoded lists would
        # drift apart, and `findData` would silently ignore the setting.
        for fmt in ExportEngine.SUPPORTED_FORMATS:
            self.combo_export_format.addItem(fmt, fmt)
        eg.addWidget(self.combo_export_format)
        self.export_group.setVisible(False)
        self.chk_exporter.toggled.connect(self.export_group.setVisible)
        layout.addWidget(self.export_group)

        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        # ── Settings ─── full-config Load/Save/Delete + factory reset, moved
        # here from the General Settings window: project-workflow actions the
        # user reaches for right where they work, not app-wide preferences.
        self.settings_group = QGroupBox()
        sg = QVBoxLayout(self.settings_group)
        cfg_row = QHBoxLayout()
        self.btn_settings_load = QPushButton()
        cfg_row.addWidget(self.btn_settings_load)
        self.btn_settings_save = QPushButton()
        cfg_row.addWidget(self.btn_settings_save)
        self.btn_settings_delete = QPushButton()
        cfg_row.addWidget(self.btn_settings_delete)
        sg.addLayout(cfg_row)
        self.btn_settings_reset = QPushButton()
        self.btn_settings_reset.setStyleSheet("color: #f7768e;")
        sg.addWidget(self.btn_settings_reset)
        layout.addWidget(self.settings_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Public API ───────────────────────────────────────────────────────────────
    def current_mode(self) -> str:
        """Same semantics as the former ``TopBar.current_mode()``."""
        return self.combo_mode.itemData(self.combo_mode.currentIndex())

    def set_running(self, running: bool):
        """Toggle btn_run between Launch and Cancel, same idiom as the former
        ``TopBar.set_running()`` (reuses its ``topbar_launch``/``topbar_cancel``
        i18n keys). Not connected to anything here — StudioWindow wires it up in
        a later pass."""
        if running:
            self.btn_run.setText(tr("topbar_cancel", "Annuler"))
        else:
            self.btn_run.setText(tr("topbar_launch", "Lancer"))
        # Dynamic property ([running="true"]) drives the accent -> $bright
        # swap declared in styles.py's _STYLESHEET — never touch this
        # button's stylesheet directly here, or it would permanently
        # override the theme-aware #btn_primary rule on the first toggle.
        self.btn_run.setProperty("running", running)
        self.btn_run.style().unpolish(self.btn_run)
        self.btn_run.style().polish(self.btn_run)

    # ── Handlers ────────────────────────────────────────────────────────────────
    def _evaluate_source_type(self):
        """Re-derive FPS field visibility and the mixed-content banner from the
        current Input field + Source type selection."""
        forced = self.combo_source_type.currentData()
        if forced in ("images", "video"):
            is_video = forced == "video"
            is_mixed = False
        else:
            kind = detect_source_kind(self.input_path.text())
            is_video = kind == "video"
            is_mixed = kind == "mixed"
        self.fps_spin.setVisible(is_video)
        self.lbl_fps.setVisible(is_video)
        self.lbl_err_mixed.setVisible(is_mixed)
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

    # ── Persistence (used by config_io later) ────────────────────────────────────
    def get_state(self):
        return {
            "project_name": self.input_project_name.text(),
            "mode": self.combo_mode.currentData(),
            "source_type": self.combo_source_type.currentData(),
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "checkpoint_dest": self.checkpoint_dest.text(),
            "fps": self.fps_spin.value(),
            "filter_blur": self.chk_filter_blur.isChecked(),
            "blur_strength": self.combo_blur.currentData(),
            "export_dir": self.export_dir.text(),
            "export_format": self.combo_export_format.currentData(),
        }

    def set_state(self, state):
        if not state:
            return
        self.input_project_name.setText(state.get("project_name", ""))
        # Absent from configs saved before the mode/type migration — falls back
        # to the widgets' own defaults ("gsplat" / "auto").
        if state.get("mode"):
            idx = self.combo_mode.findData(state["mode"])
            if idx >= 0:
                self.combo_mode.setCurrentIndex(idx)
        if state.get("source_type"):
            idx = self.combo_source_type.findData(state["source_type"])
            if idx >= 0:
                self.combo_source_type.setCurrentIndex(idx)
        self.input_path.setText(state.get("input_path", ""))
        self.output_path.setText(state.get("output_path", ""))
        self.checkpoint_dest.setText(state.get("checkpoint_dest", ""))
        if "fps" in state:
            self.fps_spin.setValue(state["fps"])
        self.chk_filter_blur.setChecked(state.get("filter_blur", False))
        if state.get("blur_strength"):
            idx = self.combo_blur.findData(state["blur_strength"])
            if idx >= 0:
                self.combo_blur.setCurrentIndex(idx)
        self.export_dir.setText(state.get("export_dir", ""))
        if state.get("export_format"):
            idx = self.combo_export_format.findData(state["export_format"])
            if idx >= 0:
                self.combo_export_format.setCurrentIndex(idx)
        self._evaluate_source_type()

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.lbl_project.setText(tr("label_project_name", "Nom du projet"))
        self.lbl_mode.setText(tr("topbar_mode", "Mode :"))
        for i, (value, key, default) in enumerate(PIPELINE_MODES):
            self.combo_mode.setItemText(i, tr(key, default))
            if value == "4dgs":
                self.combo_mode.setItemData(
                    i,
                    tr(
                        "fourdgs_mode_tooltip",
                        "Préparation de dataset uniquement — pas d'entraînement disponible sur Apple Silicon.",
                    ),
                    Qt.ItemDataRole.ToolTipRole,
                )
        self.lbl_source_type.setText(tr("source_type_label", "Type de source"))
        for i, (_value, key, default) in enumerate(_SOURCE_TYPES):
            self.combo_source_type.setItemText(i, tr(key, default))
        self.lbl_input.setText(tr("source_input", "Source (dossier / fichier / vidéo)"))
        self.lbl_err_mixed.setText(
            tr("err_source_mixed_types", "Le dossier contient à la fois des images et des vidéos.")
        )
        self.lbl_output.setText(tr("source_output", "Dossier de sortie"))
        self.lbl_ckpt.setText(tr("source_checkpoint_dest", "Destination des checkpoints (optionnel)"))
        self.lbl_fps.setText(tr("label_fps", "Images/s (vidéo)"))
        self.btn_run.setText(tr("topbar_launch", "Lancer"))
        self.btn_delete_dataset.setText(tr("source_delete_dataset", "Supprimer le dataset existant"))
        self.lbl_automation.setText(tr("automation_title", "Automatisation"))
        self.chk_360.setText(tr("chain_360_before", "Source 360°"))
        self.chk_upscaler.setText(tr("chain_upscale_before", "Upscaler avant reconstruction"))
        self.chk_entrainement.setText(tr("chain_train_after", "Lancer Brush"))
        self.chk_nettoyer.setText(tr("chain_clean_after", "Nettoyage"))
        self.chk_exporter.setText(tr("chain_export_after", "Exporter"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        self.export_group.setTitle(tr("source_export_options", "Options d'export"))
        self.settings_group.setTitle(tr("settings_current_config", "Paramètres actuels"))
        self.btn_settings_load.setText(tr("settings_load", "Charger…"))
        self.btn_settings_save.setText(tr("settings_save", "Sauvegarder…"))
        self.btn_settings_delete.setText(tr("settings_delete", "Supprimer…"))
        self.btn_settings_reset.setText(tr("settings_reset", "Réinitialiser"))
        self.lbl_advanced.setText(tr("toggle_advanced", "Avancé"))
        self.chk_undistort.setText(tr("source_undistort", "Générer images non-distordues"))
        self.chk_filter_blur.setText(tr("source_filter_blur", "Supprimer les images floues"))
        self.lbl_blur.setText(tr("source_blur_strength", "Intensité du filtre flou"))
