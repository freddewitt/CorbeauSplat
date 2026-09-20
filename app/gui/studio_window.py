"""Main "Studio" window — a four-zone interface.

Assembles: Rail (left), centre zone + right bar (``QStackedWidget`` driven
by the rail selection), ``ActivityBar`` (bottom: current step, detail,
progress) and the bottom bar (global actions, including opening the log).
The Launch/Cancel button and the pipeline mode selector now live in
``SourcePanel`` (the former TopBar is gone).

The log is no longer part of the main window: it has its own
(``logs_window.py``), fed continuously and opened on demand.

Launched by default from ``main.py`` (via ``_launch_gui()`` in
``app/cli/__init__.py``). The PIPELINE panels (Source, Reconstruction,
Entraînement, Nettoyage, Export, Visualiser) and the OUTILS ones (Brush,
Sharp, SuperSplat, Upscale, SplatTransform, 4DGS) are instantiated
dynamically and managed by ``PageRegistry``.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core import notifications
from app.core.base_engine import validate_path_standalone
from app.core.config_io import (
    ChainConfig,
    delete_config,
    list_configs,
    load_config,
    save_config,
)
from app.core.engine import ColmapEngine
from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus
from app.gui.activity_bar import ActivityBar
from app.gui.appbar import AppBar
from app.gui.chaining_logic import (
    keeps_only_latest_checkpoint,
    resolve_checkpoints_dir,
    resolve_export_dir,
    resolve_export_format,
)
from app.gui.logs_window import LogsWindow
from app.gui.managers import AppLifecycle, SessionManager
from app.gui.panels.cleaner_panel import CleanerPanel
from app.gui.panels.entrainement_panel import EntrainementPanel
from app.gui.panels.export_panel import ExportPanel
from app.gui.panels.extractor360_panel import Extractor360Panel
from app.gui.panels.four_dgs_panel import FourDGSPanel
from app.gui.panels.reconstruction_logic import (
    apply_source_settings,
    describe_unusable_source,
    detect_source_kind,
)
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.sharp_panel import SharpPanel
from app.gui.panels.source_panel import SourcePanel
from app.gui.panels.splat_transform_panel import SplatTransformPanel
from app.gui.panels.upscale_panel import UpscalePanel
from app.gui.panels.visualiser_panel import VisualiserPanel
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail, item_label
from app.gui.settings_window import ResetDialog, SettingsWindow
from app.gui.studio_nav import PageRegistry
from app.gui.styles import set_dark_theme
from app.gui.widgets.upscale_widgets import TestWorker, UpscaleImagesWorker
from app.gui.workers import (
    BrushWorker,
    CleanerWorker,
    ColmapWorker,
    ExportWorker,
    Extractor360Worker,
    FourDGSWorker,
    SharpVideoWorker,
    SharpWorker,
    SplatTransformWorker,
)

# Stacked page order (PIPELINE steps, then OUTILS modules).
_PAGE_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)


class StudioWindow(QMainWindow):
    """Four-zone shell. Rail selection → swaps the centre + right page."""

    def __init__(self):
        super().__init__()
        self.run_state = RunState()
        self.nav = PageRegistry(_PAGE_KEYS)   # page mapping + current selection
        self.current_plan = []
        self.current_pipeline_mode = "gsplat"
        self._plan_index = 0
        self._active_pipeline_step = None
        # Current image folder of the chain: every pre-step that produces
        # a new folder (Extraction 360, then Upscale) overwrites it, and the
        # next step reads it instead of the raw Source path. Reset on every
        # ``launch()`` so a run without a pre-step does not reuse the folder
        # of a previous run.
        self._pipeline_images_dir = None
        self._pending_upscale_params = None
        self._notifications_enabled = False
        self._settings_window = None
        self._active_worker = None
        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)
        # Last project (Source paths): reloaded before the window is shown,
        # saved continuously (debounce) and on close.
        self.session_manager = SessionManager(self)
        self.session_manager.load()
        self._wire_session_autosave()

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        # Min size lowered so it fits on a small screen; initial size fitted
        # to the screen (like ColmapGUI) to keep the window from opening wider
        # than the screen, with the right bar overflowing.
        self.setMinimumSize(820, 560)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.resize(int(geo.width() * 0.9), int(geo.height() * 0.9))
            self.move(geo.topLeft())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self.appbar = AppBar()
        root.addWidget(self.appbar)

        # ── Body: rail | centre | right bar ───────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.rail = Rail()
        self.rail.itemSelected.connect(self.on_rail_selected)
        self.rail.setFixedWidth(220)
        body.addWidget(self.rail)

        # Thin rule rail | centre
        body.addWidget(self._vline())

        # Centre column: flow breadcrumb + panel stack.
        center_col = QVBoxLayout()
        center_col.setContentsMargins(8, 0, 8, 0)
        self.breadcrumb = QLabel("")
        self.breadcrumb.setStyleSheet("color: #9aa5ce; padding: 4px 8px;")
        center_col.addWidget(self.breadcrumb)
        self.center_stack = QStackedWidget()
        center_col.addWidget(self.center_stack, stretch=1)
        body.addLayout(center_col, stretch=3)

        # Thin rule centre | right bar (hidden along with the right bar
        # when the current panel has no right content, cf. _show_page).
        self._center_right_vline = self._vline()
        body.addWidget(self._center_right_vline)

        # Right bar: wide enough for the parameter accordions, and each
        # panel handles its own vertical scrolling there.
        self.right_stack = QStackedWidget()
        self.right_stack.setFixedWidth(400)
        body.addWidget(self.right_stack)

        # Real panels available (the other keys stay placeholders, replaced
        # in sub-batches 3b/3c/4/5).
        self.panels = {
            "source": SourcePanel(self.run_state),
            "extraction360": Extractor360Panel(self.run_state),
            "upscale": UpscalePanel(self.run_state),
            "reconstruction": ReconstructionPanel(self.run_state),
            "entrainement": EntrainementPanel(self.run_state),
            "nettoyage": CleanerPanel(self.run_state),
            "export": ExportPanel(self.run_state),
            "visualiser": VisualiserPanel(self.run_state),
            # OUTILS modules. Brush ≈ Entraînement (manual mode) and SuperSplat ≈
            # Visualiser share the same underlying screen (cf. spec §2.3).
            "brush": EntrainementPanel(self.run_state, standalone=True),
            "sharp": SharpPanel(self.run_state),
            "supersplat": VisualiserPanel(self.run_state),
            "splattransform": SplatTransformPanel(self.run_state),
            "4dgs": FourDGSPanel(self.run_state),
        }

        # Local "Launch" button of the OUTILS modules (and of Reconstruction/
        # Nettoyage/Export, usable on their own outside the pipeline chain):
        # each starts its own worker, SourcePanel switches to Cancel while it
        # runs (cf. _start_tool_worker / on_launch_clicked).
        self.panels["nettoyage"].btn_run.clicked.connect(self._launch_cleaner)
        self.panels["export"].btn_run.clicked.connect(self._launch_export)
        self.panels["extraction360"].btn_run.clicked.connect(self._launch_extraction360)
        self.panels["4dgs"].btn_run.clicked.connect(self._launch_fourdgs)
        self.panels["sharp"].btn_run.clicked.connect(self._launch_sharp)
        self.panels["splattransform"].btn_run.clicked.connect(self._launch_splat_transform)
        # Upscale is a PARAMÈTRES step: this button only runs the local
        # upscale on the paths typed into the panel, independently of the
        # chain (driven by the ``upscaler_avant`` flag on the Projet side).
        self.panels["upscale"].btn_run.clicked.connect(self._launch_upscale)
        self.panels["brush"].btn_run.clicked.connect(self._launch_brush)
        self.panels["reconstruction"].btn_run.clicked.connect(self._launch_reconstruction)
        self.panels["source"].btn_delete_dataset.clicked.connect(self._delete_dataset)
        # Single Launch/Cancel button (ex-topbar), now carried by SourcePanel.
        self.panels["source"].btn_run.clicked.connect(self.on_launch_clicked)
        # Settings block (moved from the General Settings window: config
        # load/save/delete and factory reset are project-workflow actions).
        self.panels["source"].btn_settings_load.clicked.connect(self.load_config_dialog)
        self.panels["source"].btn_settings_save.clicked.connect(self.save_config_dialog)
        self.panels["source"].btn_settings_delete.clicked.connect(self.delete_config_dialog)
        self.panels["source"].btn_settings_reset.clicked.connect(self._on_reset_clicked)
        # Stop button under every panel's Run button. A single worker runs at a
        # time (``_active_worker``), so they all interrupt the same thing —
        # whichever page the user happens to be on.
        for panel in self.panels.values():
            button = getattr(panel, "btn_cancel", None)
            if button is not None:
                button.clicked.connect(self._cancel_active_worker)

        # Pages added in _PAGE_KEYS order: their index matches PageRegistry's
        # (a counter), deterministic even under a mocked PySide6.
        for key in _PAGE_KEYS:
            panel = self.panels.get(key)
            if panel is not None:
                self.center_stack.addWidget(panel.center)
                self.right_stack.addWidget(panel.right)
            else:
                self.center_stack.addWidget(self._placeholder(key, "center"))
                self.right_stack.addWidget(self._placeholder(key, "right"))

        root.addLayout(body, stretch=1)

        # ── Log: dedicated window, fed continuously even when closed ───────────
        # Built here (never shown by default) so the whole run history is
        # there on first open, including what happened before anyone
        # thought to look.
        self.logs_window = LogsWindow(self)

        # ── Activity bar: current step, detail, progress, Cancel ───────────────
        self.activity_bar = ActivityBar()
        root.addWidget(self.activity_bar)

        # ── Bottom bar: version + lifecycle actions (Restart/Quit) ─────────────
        # Moved out of SettingsWindow: these are global actions of the main
        # window, not settings — better here, always visible, than buried in
        # a dialog.
        root.addWidget(self._build_bottom_bar())

        # Initial selection: first step (programmatic, nothing disconnected).
        if _PAGE_KEYS:
            self.rail.select(_PAGE_KEYS[0])
            self._show_page(_PAGE_KEYS[0])

    def _wire_session_autosave(self):
        """Trigger a save (1.5s debounce, cf. SessionManager) on the fields
        identifying the project — a safety net on crash/kill, on top of the
        immediate save on close (cf. closeEvent).
        """
        source = self.panels.get("source")
        if source is None:
            return
        for field in (source.input_project_name, source.input_path, source.output_path):
            field.textChanged.connect(lambda _text=None: self.session_manager.save())

    def _build_bottom_bar(self):
        """Always-visible bottom bar: lifecycle actions (Restart/Quit), moved
        out of SettingsWindow — these are global actions, not settings.
        The version now lives in the AppBar (top), not shown twice here."""
        w = QWidget()
        row = QHBoxLayout(w)
        # Margins more generous than the original 2px, and asymmetric: this
        # is the only bar flush with the window's bottom edge. At 2px the
        # buttons reached 899px in a 900px window — the rounded corner and the
        # macOS window shadow made them read as clipped. The horizontal one
        # aligns on AppBar (10px).
        row.setContentsMargins(10, 6, 10, 8)
        row.addStretch(1)

        # General settings (ex-topbar): moved here when the TopBar went away,
        # reuses the same i18n tooltip key. The glyph alone being ambiguous,
        # a text label goes with it (dedicated key: the small-caps style of
        # rail_section_entrainement does not suit this context).
        self.btn_settings = QPushButton(f"⚙ {tr('btn_settings_label', 'Paramètres')}")
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        self.btn_settings.clicked.connect(self.open_settings)
        row.addWidget(self.btn_settings)

        # Log: the bottom of the window now only shows the current activity,
        # the full detail (with search/copy/save) opens here.
        self.btn_logs = QPushButton(f"▤ {tr('logbar_title', 'Logs')}")
        self.btn_logs.clicked.connect(self.logs_window.show_logs)
        row.addWidget(self.btn_logs)

        self.btn_relaunch = QPushButton(tr("settings_relaunch", "Relancer"))
        self.btn_relaunch.clicked.connect(self.restart_application)
        row.addWidget(self.btn_relaunch)

        self.btn_quit = QPushButton(tr("settings_quit", "Quitter"))
        self.btn_quit.clicked.connect(self.close)
        row.addWidget(self.btn_quit)

        return w

    def _vline(self):
        """Thin vertical rule separating two zones."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedWidth(1)
        line.setStyleSheet("color: #2f3549; background-color: #2f3549;")
        return line

    def _placeholder(self, key, zone):
        """Temporary page (replaced by the real panel in batches 3-5)."""
        w = QLabel(f"[{zone}] {key} — à venir")
        w.setObjectName(f"placeholder_{zone}_{key}")
        return w

    # ── Navigation ──────────────────────────────────────────────────────────────
    def on_rail_selected(self, key):
        """Rail selection changes the page. If the step failed, opens the log
        window (clicking the red marker)."""
        self._show_page(key)
        if key in PIPELINE_STEPS and self.run_state.get_status(key) == StepStatus.ERROR:
            self.logs_window.show_logs()

    def _panel_has_right_content(self, key):
        """Structural check (not a hardcoded key list): a panel's right column
        is considered empty when ``right`` has no layout or an empty one (cf.
        the many panels whose ``_build_right()`` just returns a bare
        ``QWidget()`` since their controls were merged into the center)."""
        panel = self.panels.get(key)
        right = getattr(panel, "right", None) if panel else None
        layout = right.layout() if right else None
        return bool(layout and layout.count() > 0)

    def _show_page(self, key):
        index = self.nav.select(key)
        if index is None:
            return
        self.center_stack.setCurrentIndex(index)
        self.right_stack.setCurrentIndex(index)
        has_right = self._panel_has_right_content(key)
        self.right_stack.setVisible(has_right)
        self._center_right_vline.setVisible(has_right)

    def _set_cancel_enabled(self, enabled: bool):
        """Toggle every panel's Cancel button at once.

        A single worker runs at a time, but it is not necessarily the one the
        user is looking at: a chained run walks through several panels. Enabling
        only the active step's button would leave Cancel greyed out on the page
        actually on screen — which is where the user reaches for it.
        """
        for panel in self.panels.values():
            button = getattr(panel, "btn_cancel", None)
            if button is not None:
                button.setEnabled(bool(enabled))

    def current_page_key(self):
        return self.nav.current

    # ── Launch (orchestrated dispatch) ──────────────────────────────────────────
    def launch(self):
        """Compute the run plan from the mode + the run_state toggles, then
        actually start the pipeline chain (Source → Reconstruction/COLMAP →
        Entraînement/Brush, cf. ``_run_pipeline_step``). Also drives the rail
        (statuses + auto-follow) and the breadcrumb.
        """
        mode = self.panels["source"].current_mode()
        plan = plan_pipeline(mode, self.run_state)
        self.current_plan = plan
        # The plan only names steps; "reconstruction" means COLMAP, Sharp or the
        # 4DGS dataset prep depending on the mode, so the chain has to remember it.
        self.current_pipeline_mode = mode
        self._pipeline_images_dir = None
        self._pending_upscale_params = None
        self.run_state.reset_status()
        self.update_breadcrumb(plan)
        self.logs_window.append_log(tr("run_plan", "Plan : ") + " → ".join(plan))
        if plan:
            self._run_pipeline_step(0)
        return plan

    def update_breadcrumb(self, plan):
        self.breadcrumb.setText(" → ".join(plan))

    # ── Chaining of the main pipeline workers ────────────────────────────────────
    def _run_pipeline_step(self, index):
        """Start the ``self.current_plan[index]`` step. Source has no worker of
        its own (it only supplies the paths consumed by Reconstruction): it is
        marked DONE immediately and the chain moves on. The OUTILS post-steps
        (Nettoyage/Export/Visualiser) only appear in ``self.current_plan``
        when their matching ``run_state`` flag is on (cf. ``plan_pipeline``);
        when they are there, they are pre-filled from the previous step's
        output then chained automatically like Reconstruction/Entraînement.
        """
        self._plan_index = index
        if index >= len(self.current_plan):
            self._finish_pipeline_chain(True, tr("run_chain_done", "Chaîne terminée avec succès."))
            return

        step = self.current_plan[index]
        if step == "source":
            self.run_state.set_status("source", StepStatus.DONE)
            self.rail.set_step_status("source", StepStatus.DONE)
            self._run_pipeline_step(index + 1)
            return

        if step == "extraction360":
            worker = self._build_extraction360_worker()
            if worker is not None:
                self._start_pipeline_worker("extraction360", worker)
            return

        if step == "upscale":
            worker = self._build_upscale_worker()
            if worker is not None:
                self._start_pipeline_worker("upscale", worker)
            elif self._pending_upscale_params is not None:
                # Video source: the images do not exist yet, the upscale is
                # delegated to COLMAP, which runs it right after frame extraction
                # and before feature extraction (cf.
                # ``ColmapEngine._process_input``).
                self.logs_window.append_log(
                    tr("run_upscale_deferred",
                       "Upscale : source vidéo — les trames seront agrandies au "
                       "début de la Reconstruction, avant COLMAP.")
                )
                self.run_state.set_status("upscale", StepStatus.DONE)
                self.rail.set_step_status("upscale", StepStatus.DONE)
                self._run_pipeline_step(index + 1)
            return

        if step == "reconstruction":
            worker = self._build_reconstruction_worker()
            if worker is not None:
                self._start_pipeline_worker("reconstruction", worker)
            return

        if step == "entrainement":
            worker = self._build_brush_worker()
            if worker is not None:
                self._start_pipeline_worker("entrainement", worker)
            return

        if step == "nettoyage":
            self._prefill_cleaner_from_brush()
            worker = self._build_cleaner_worker()
            if worker is not None:
                self._start_pipeline_worker("nettoyage", worker)
            else:
                self._fail_pipeline_step("nettoyage", tr("err_no_paths", "Chemins manquants."))
            return

        if step == "export":
            self._prefill_export_from_previous()
            worker = self._build_export_worker()
            if worker is not None:
                self._start_pipeline_worker("export", worker)
            else:
                self._fail_pipeline_step("export", tr("err_no_paths", "Chemins manquants."))
            return

        if step == "visualiser":
            self._prefill_visualiser_from_previous()
            self._run_visualiser_pipeline_step()
            return

        # Defensive: ``plan_pipeline`` only produces keys handled above, so
        # this branch should never run.
        message = tr("run_chain_manual_continue").format(step)
        self._finish_pipeline_chain(True, message)

    def _resolve_source_type(self, step, input_path, source_state):
        """Source type (``images``/``video``) for the ``step`` step, or None if
        undecidable — in which case the step is already marked as failed.

        Honours the user's explicit choice (Images/Vidéo) over auto-detection
        when they made one (SourcePanel.combo_source_type, "auto" by default).
        Shared by Upscale and Reconstruction, which must classify the same
        source the same way.
        """
        forced_type = (source_state.get("source_type") or "auto").strip()
        if forced_type in ("images", "video"):
            return forced_type
        input_type = detect_source_kind(input_path)
        if input_type == "mixed":
            self._fail_pipeline_step(
                step,
                tr(
                    "err_source_mixed_types",
                    "Le dossier contient à la fois des images et des vidéos — "
                    "choisissez explicitement le type de source.",
                ),
            )
            return None
        if input_type == "empty":
            # "empty" covers everything detect_source_kind cannot classify, so
            # reporting "Chemins manquants" was wrong whenever the path existed
            # and simply held an unreadable format (camera RAW, PSD…).
            self._fail_pipeline_step(
                step,
                describe_unusable_source(
                    input_path,
                    convert_format=source_state.get("convert") or "png",
                ),
            )
            return None
        return input_type

    def _build_extraction360_worker(self):
        """Build the worker of the Extraction 360 step.

        Unlike Upscale, this step does not transform the images in place: it
        **produces a new folder** of planar images out of an equirectangular
        source (video or photos). That folder becomes the chain's current image
        folder (``_pipeline_images_dir``), which Upscale then COLMAP consume
        instead of the original source.

        The source type is not resolved here: the extractor accepts video as
        well as images, and its output is always an image folder.
        """
        source_state = self.panels["source"].get_state()
        input_path = source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not input_path or not output_path:
            self._fail_pipeline_step("extraction360", tr("err_no_paths", "Chemins manquants."))
            return None
        project_name = source_state["project_name"].strip() or "Untitled"
        images_360 = Path(output_path) / project_name / "images_360"
        safe_out = validate_path_standalone(str(images_360))
        if safe_out is None:
            self._fail_pipeline_step("extraction360", tr("err_no_paths", "Chemins manquants."))
            return None
        safe_out.mkdir(parents=True, exist_ok=True)
        self._pipeline_images_dir = str(safe_out)
        panel = self.panels["extraction360"]
        panel.input_path.setText(input_path)
        panel.output_path.setText(str(safe_out))
        return Extractor360Worker(input_path, str(safe_out), panel.get_params())

    def _launch_extraction360(self):
        """Standalone run of the Extraction 360 step from OPTIONS, on the paths
        typed into the panel — without going through the full chain.
        """
        panel = self.panels["extraction360"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        self._start_tool_worker(Extractor360Worker(input_path, output_path, panel.get_params()))

    def _build_upscale_worker(self):
        """Build the worker of the Upscale step, which enlarges the images
        *before* COLMAP reads them.

        If Extraction 360 ran just before, the source is the planar image folder
        it produced (``_pipeline_images_dir``) — so always images, never a
        video. Otherwise there are two cases, since the project images do not
        exist yet at this stage:
        - **image source**: an ``UpscaleImagesWorker`` writes the enlarged
          images into ``<output>/<project>/images_upscaled``, which
          ``_build_colmap_worker`` then takes as input. The user's source
          folder stays untouched.
        - **video source**: nothing to enlarge until the frames are extracted.
          We fill ``_pending_upscale_params``, which ``_build_colmap_worker``
          passes on to ``ColmapWorker``: the engine enlarges the frames right
          after extraction and before COLMAP (the ``upscale_config`` mechanism
          already in place in ``engine.py``). Returns None without failing —
          the caller chains on.
        """
        source_state = self.panels["source"].get_state()
        input_path = source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not input_path or not output_path:
            self._fail_pipeline_step("upscale", tr("err_no_paths", "Chemins manquants."))
            return None

        params = self.panels["upscale"].get_params()
        if self._pipeline_images_dir:
            input_path, input_type = self._pipeline_images_dir, "images"
        else:
            input_type = self._resolve_source_type("upscale", input_path, source_state)
            if input_type is None:
                return None
            if input_type == "video":
                self._pending_upscale_params = {**params, "active": True}
                return None

        project_name = source_state["project_name"].strip() or "Untitled"
        upscaled_dir = Path(output_path) / project_name / "images_upscaled"
        self._pipeline_images_dir = str(upscaled_dir)
        return UpscaleImagesWorker(input_path, str(upscaled_dir), params)

    def _build_reconstruction_worker(self):
        """Pick the Reconstruction worker matching the Source panel's mode.

        The three modes share the step slot but not the engine: Gsplat runs
        COLMAP, Sharp runs Apple ML Sharp inference, 4DGS prepares a Nerfstudio
        dataset. Before this, every mode fell through to COLMAP, so picking
        Sharp or 4DGS in the Source dropdown changed nothing on Launch."""
        if self.current_pipeline_mode == "sharp":
            return self._build_sharp_pipeline_worker()
        if self.current_pipeline_mode == "4dgs":
            return self._build_fourdgs_pipeline_worker()
        return self._build_colmap_worker()

    def _build_sharp_pipeline_worker(self):
        """``SharpWorker`` for the Sharp mode, fed by the Source paths.

        Sharp's own settings (device, checkpoint, verbose) still come from the
        OUTILS Sharp panel; only the paths are taken from Source, so that the
        chained run and the standalone button stay consistent. Video inputs are
        rejected here: the pipeline's Source step feeds image folders, and
        Sharp's video mode has its own worker in the OUTILS panel."""
        source_state = self.panels["source"].get_state()
        input_path = self._pipeline_images_dir or source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not input_path or not output_path:
            self._fail_pipeline_step("reconstruction", tr("err_no_paths", "Chemins manquants."))
            return None
        params = self.panels["sharp"].get_params()
        params.update({"mode": "image", "input_path": input_path, "output_path": output_path})
        return SharpWorker(input_path, output_path, params)

    def _build_fourdgs_pipeline_worker(self):
        """``FourDGSWorker`` for the 4DGS mode, fed by the Source paths.

        Source points at the multi-camera video folder; the 4DGS panel keeps
        supplying FPS and the COLMAP settings. Upscale is already handled by the
        pipeline's own Upscale step, hence no ``upscale_params`` here."""
        source_state = self.panels["source"].get_state()
        videos_dir = source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not videos_dir or not output_path:
            self._fail_pipeline_step("reconstruction", tr("err_no_paths", "Chemins manquants."))
            return None
        panel_params = self.panels["4dgs"].get_params()
        colmap_params = {
            key: panel_params[key]
            for key in ("camera_model", "single_camera", "matcher_type", "sequential_overlap")
            if key in panel_params
        }
        project_name = source_state["project_name"].strip() or "Untitled"
        return FourDGSWorker(
            videos_dir, str(Path(output_path) / project_name),
            source_state["fps"] or panel_params["fps"],
            colmap_params=colmap_params,
        )

    def _build_colmap_worker(self):
        """Build the ``ColmapWorker`` of the Reconstruction step from the Source
        paths (SourcePanel.get_state) and the COLMAP settings of Reconstruction
        (ReconstructionPanel.get_params → ColmapParams).

        If the Upscale step ran just before, the input becomes the enlarged
        image folder it produced (cf. ``_build_upscale_worker``).
        """
        source_state = self.panels["source"].get_state()
        input_path = source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not input_path or not output_path:
            self._fail_pipeline_step("reconstruction", tr("err_no_paths", "Chemins manquants."))
            return None
        project_name = source_state["project_name"].strip() or "Untitled"
        params = apply_source_settings(
            self.panels["reconstruction"].get_params(), source_state
        )
        if self._pipeline_images_dir:
            input_path, input_type = self._pipeline_images_dir, "images"
        else:
            input_type = self._resolve_source_type("reconstruction", input_path, source_state)
            if input_type is None:
                return None
        return ColmapWorker(
            params, input_path, output_path, input_type, source_state["fps"],
            project_name=project_name,
            upscale_params=self._pending_upscale_params,
        )

    def _build_brush_worker(self):
        """Build the ``BrushWorker`` of the Entraînement step: dataset = the
        project folder created by COLMAP (output/project), Brush settings from
        EntrainementPanel.get_params → BrushParams.to_engine_params (the flat
        dict expected by BrushEngine, cf. app/core/brush_engine.py).
        """
        source_state = self.panels["source"].get_state()
        output_path = source_state["output_path"].strip()
        if not output_path:
            self._fail_pipeline_step("entrainement", tr("err_no_paths", "Chemins manquants."))
            return None
        project_name = source_state["project_name"].strip() or "Untitled"
        project_dir = Path(output_path) / project_name
        checkpoints_dir = resolve_checkpoints_dir(source_state)
        if checkpoints_dir is None:
            self._fail_pipeline_step(
                "entrainement",
                tr("err_checkpoint_dest_invalid",
                   "Destination des checkpoints invalide."),
            )
            return None
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        panel = self.panels["entrainement"]
        params = panel.get_params().to_engine_params()
        params["refine_mode"] = panel.combo_mode.currentData() == "refine"
        ply_name = panel.ply_name_edit.text().strip()
        if ply_name:
            params["ply_name"] = ply_name
        return BrushWorker(
            project_dir, checkpoints_dir, params, project_name=project_name,
            # Original semantics of the field (CHANGELOG 1.2.3): a custom
            # destination only keeps the last checkpoint; an empty field =
            # historical behaviour, every checkpoint kept.
            keep_only_latest=keeps_only_latest_checkpoint(source_state),
        )



    # ── Pre-filling the OUTILS post-steps from the previous step's output
    # (cf. Section G: Entraînement → Nettoyage → Export → Visualiser chaining,
    # only when the matching ``run_state`` flag is on) ────────────────────────────────
    def _find_latest_ply(self, directory: Path):
        """Most recently modified ``.ply`` file under ``directory`` (recursive),
        or ``None``. Same lookup idiom as ``BrushWorker.handle_ply_rename``
        (app/gui/workers.py), but simpler: the final name chosen by Brush is
        unknown here (it depends on ``ply_name``/``project_name``), so we read
        the filesystem back once training is over rather than duplicating its
        renaming logic.
        """
        if not directory.exists():
            return None
        latest, latest_mtime = None, -1.0
        for ply_path in directory.rglob("*.ply"):
            try:
                mtime = ply_path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest, latest_mtime = ply_path, mtime
        return latest

    def _latest_brush_ply(self):
        """PLY produced by the last Entraînement step, in the project's
        checkpoints folder (cf. ``_build_brush_worker``).
        """
        checkpoints_dir = resolve_checkpoints_dir(self.panels["source"].get_state())
        if checkpoints_dir is None:
            return None
        return self._find_latest_ply(checkpoints_dir)

    def _resolve_ply_output(self):
        """Most relevant PLY path to hand to the next step: the Nettoyage
        output when that step is on (``nettoyer_apres``), otherwise the PLY
        produced by Entraînement.
        """
        if self.run_state.nettoyer_apres:
            cleaned = self.panels["nettoyage"].output_path.text().strip()
            if cleaned:
                return cleaned
        latest_ply = self._latest_brush_ply()
        return str(latest_ply) if latest_ply is not None else ""

    def _prefill_cleaner_from_brush(self):
        """Pre-fill the Nettoyage panel with the PLY produced by Entraînement,
        before the worker is built (cf. ``_build_cleaner_worker``).
        """
        latest_ply = self._latest_brush_ply()
        if latest_ply is None:
            return
        panel = self.panels["nettoyage"]
        panel.input_path.setText(str(latest_ply))
        if not panel.output_path.text().strip():
            panel.output_path.setText(str(latest_ply.with_name(f"clean_{latest_ply.name}")))

    def _prefill_export_from_previous(self):
        """Pre-fill the Export panel from the previous step's output (Nettoyage
        when on, otherwise Entraînement directly).

        The "Export folder" and "Format" fields of the Projet panel, when they
        are filled in, win over whatever is typed into the Export panel: they
        are the *chain* settings, whereas the Export panel also serves local
        runs. Left empty, the previous behaviour is unchanged (folder of the
        source PLY, current format of the panel).
        """
        source_path = self._resolve_ply_output()
        if not source_path:
            return
        source_state = self.panels["source"].get_state()
        panel = self.panels["export"]
        panel.input_path.setText(source_path)

        export_dir = resolve_export_dir(
            source_state, source_path, panel.output_path.text()
        )
        if export_dir is not None:
            panel.output_path.setText(export_dir)

        export_format = resolve_export_format(source_state)
        if export_format:
            idx = panel.combo_format.findData(export_format)
            if idx >= 0:
                panel.combo_format.setCurrentIndex(idx)

    def _prefill_visualiser_from_previous(self):
        """Pre-fill the Visualiser panel from the previous step's output (same
        rule as ``_prefill_export_from_previous``).
        """
        source_path = self._resolve_ply_output()
        if source_path:
            self.panels["visualiser"].input_path.setText(source_path)

    def _run_visualiser_pipeline_step(self):
        """Visualiser step of the chain: ``VisualiserPanel`` is not a
        Worker/QThread (persistent server via ``toggle_server()``), so there is
        no classic DONE/ERROR driven by a ``finished_signal``. The step is
        marked DONE as soon as the server starts successfully (without waiting
        for a run to end); if the start fails, ERROR.
        """
        panel = self.panels["visualiser"]
        self.run_state.set_status("visualiser", StepStatus.RUNNING)
        self.rail.set_step_status("visualiser", StepStatus.RUNNING)
        if not panel.is_running():
            panel.toggle_server()
        if panel.is_running():
            self.run_state.set_status("visualiser", StepStatus.DONE)
            self.rail.set_step_status("visualiser", StepStatus.DONE)
            self._run_pipeline_step(self._plan_index + 1)
        else:
            self._fail_pipeline_step(
                "visualiser",
                tr("err_visualiser_start", "Échec du démarrage du serveur SuperSplat."),
            )

    def _start_pipeline_worker(self, step, worker):
        """Start the worker of a pipeline step: rail/run_state statuses set at
        the real start time (not at planning time), logs relayed, SourcePanel
        switched to Cancel — same idiom as ``_start_tool_worker``.
        """
        self.run_state.set_status(step, StepStatus.RUNNING)
        self.rail.set_step_status(step, StepStatus.RUNNING)
        self._active_worker = worker
        self._active_pipeline_step = step
        self.activity_bar.set_step(item_label(step))
        self._wire_worker_feedback(worker)
        worker.finished_signal.connect(self._on_pipeline_step_finished)
        self.panels["source"].set_running(True)
        self._set_cancel_enabled(True)
        self.panels["source"].progress_ring.start()
        # The log no longer opens by itself at start-up: the bar header now
        # shows the activity even when collapsed (cf.
        # ``_wire_worker_feedback``). It only unfolds on error.
        worker.start()

    def _wire_worker_feedback(self, worker):
        """Relay a worker's logs, status and progress to the bottom bar.

        ``progress_signal`` was emitted by four workers (COLMAP, 360, Sharp
        video, Export) but connected nowhere: the progress was computed then
        thrown away. It now feeds the header bar.

        The activity is wired to ``log_signal`` **and** ``status_signal``:
        ``BrushWorker`` (the training) only emits the first — its engine gets
        no ``status_callback`` — so sticking to the status alone would leave it
        mute.
        """
        worker.log_signal.connect(self.logs_window.append_log)
        worker.log_signal.connect(self.activity_bar.set_activity)
        if hasattr(worker, "status_signal"):
            worker.status_signal.connect(self.logs_window.append_log)
            worker.status_signal.connect(self.activity_bar.set_activity)
        if hasattr(worker, "progress_signal"):
            worker.progress_signal.connect(self.activity_bar.set_progress)
            worker.progress_signal.connect(self.panels["source"].progress_ring.set_value)

    def _on_pipeline_step_finished(self, success, message):
        """End of a pipeline step: DONE + next step on success; ERROR + chain
        stopped (no silent failure) otherwise.
        """
        step = self._active_pipeline_step
        worker = self._active_worker
        self._active_worker = None
        self.logs_window.append_log(message)
        if success:
            self.run_state.set_status(step, StepStatus.DONE)
            self.rail.set_step_status(step, StepStatus.DONE)
            self._run_pipeline_step(self._plan_index + 1)
            return
        stopped_by_user = bool(worker and getattr(worker, "stopped_by_user", False))
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        if not stopped_by_user:
            self.notify(tr("msg_error", "Erreur"), message)
            self._show_error_dialog(message)

    def _fail_pipeline_step(self, step, message):
        """Failure while building a worker (e.g. missing paths): same handling
        as a failure during the run, with no active worker to clean up.
        """
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self.logs_window.append_log(message)
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        self._active_worker = None
        self.notify(tr("msg_error", "Erreur"), message)
        self._show_error_dialog(message)

    def _show_error_dialog(self, message):
        """Error dialog offering the log rather than forcing it open.

        The log window is never raised on its own; the failed step also turns ⛔
        in the rail, and clicking it opens the log (cf. on_rail_selected).
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("msg_error", "Erreur"))
        box.setText(message)
        btn_logs = box.addButton(
            tr("btn_view_logs", "Voir le journal"), QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is btn_logs:
            self.logs_window.show_logs()

    def _finish_pipeline_chain(self, success, message):
        """End (normal or deliberately interrupted) of the pipeline chain."""
        self._active_worker = None
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        self.logs_window.append_log(message)
        if success:
            self.notify(tr("msg_success", "Succès"), message)

    # ── Dispatch of the single Launch/Cancel button (ex-topbar, carried by SourcePanel) ─
    def on_launch_clicked(self):
        """``SourcePanel.btn_run`` only has one Launch/Cancel button: when an
        OUTILS worker is active (started from a local button), the click
        cancels it; otherwise it starts the pipeline chain (cf. ``launch``).
        """
        if self._active_worker is not None and self._active_worker.isRunning():
            self._cancel_active_worker()
            return
        self.launch()

    def _cancel_active_worker(self):
        worker = self._active_worker
        if worker and worker.isRunning():
            self.logs_window.append_log(tr("topbar_cancel", "Annuler") + "…")
            if hasattr(worker, "stop"):
                worker.stop()
            else:
                worker.requestInterruption()

    # ── Launching the OUTILS modules (local button, outside the pipeline chain) ──
    def _start_tool_worker(self, worker, finished_signal=None):
        """Start an OUTILS worker in the background: logs relayed to the log
        bar, SourcePanel switched to Cancel, result shown at the end.

        A second click on Launch while a worker is already running would
        overwrite ``self._active_worker`` without keeping a Python reference to
        the old thread: Qt would garbage-collect it while its OS thread is
        still running ("QThread: Destroyed while thread is still running") —
        an immediate crash (SIGABRT). Hence the guard below.
        """
        existing = self._active_worker
        if existing is not None and existing.isRunning():
            self.logs_window.append_log(
                tr("err_worker_already_running", "Un traitement est déjà en cours.")
            )
            return
        self._active_worker = worker
        # An OUTILS worker has no pipeline step: we name the page it was
        # started from, which is the one the user is looking at.
        self.activity_bar.set_step(item_label(self.nav.current))
        self._wire_worker_feedback(worker)
        signal = finished_signal if finished_signal is not None else worker.finished_signal
        signal.connect(self._on_tool_finished)
        self.panels["source"].set_running(True)
        self._set_cancel_enabled(True)
        self.panels["source"].progress_ring.start()
        worker.start()

    def _on_tool_finished(self, success, message):
        worker = self._active_worker
        self._active_worker = None
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        self.logs_window.append_log(message)
        stopped_by_user = bool(worker and getattr(worker, "stopped_by_user", False))
        if success:
            self.notify(tr("msg_success", "Succès"), message)
        elif not stopped_by_user:
            self.notify(tr("msg_error", "Erreur"), message)
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _check_paths(self, *paths) -> bool:
        if all(p and str(p).strip() for p in paths):
            return True
        QMessageBox.critical(self, tr("msg_error", "Erreur"), tr("err_no_paths", "Chemins manquants."))
        return False

    def _build_cleaner_worker(self):
        """Build the ``CleanerWorker`` from the current fields of the Nettoyage
        panel. Shared by ``_launch_cleaner`` (local button, outside the chain)
        and the ``nettoyage`` step of the pipeline chain (cf.
        ``_run_pipeline_step``), which pre-fills the fields before the call
        (cf. ``_prefill_cleaner_from_brush``).
        """
        panel = self.panels["nettoyage"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not input_path or not output_path:
            return None
        return CleanerWorker(input_path, output_path, panel.get_params())

    def _launch_cleaner(self):
        panel = self.panels["nettoyage"]
        if not self._check_paths(panel.input_path.text().strip(), panel.output_path.text().strip()):
            return
        self._start_tool_worker(self._build_cleaner_worker())

    def _build_export_worker(self):
        """Build the ``ExportWorker`` from the current fields of the Export
        panel. Shared by ``_launch_export`` (local button, outside the chain)
        and the ``export`` step of the pipeline chain (cf.
        ``_run_pipeline_step``).
        """
        panel = self.panels["export"]
        input_paths = [p for p in panel.input_path.text().split("|") if p.strip()]
        output_dir = panel.output_path.text().strip()
        if not input_paths or not output_dir:
            return None
        return ExportWorker(
            input_paths, output_dir, panel.get_format(), options={"scale": panel.get_scale()}
        )

    def _launch_export(self):
        worker = self._build_export_worker()
        if worker is None:
            QMessageBox.critical(self, tr("msg_error", "Erreur"), tr("err_no_paths", "Chemins manquants."))
            return
        self._start_tool_worker(worker)

    def _launch_reconstruction(self):
        """Standalone run (outside the chain) of the Reconstruction panel, same
        idiom as ``_launch_cleaner``/``_launch_export``. Reuses
        ``_build_colmap_worker`` (which already drives the pipeline chain) — on
        a build failure (missing paths, mixed source…), it already fails the
        step cleanly through ``_fail_pipeline_step``.

        The "Lancer Brush" checkbox (``run_state.entrainement_apres``) is
        visible in this panel: without the hook below it did nothing for this
        button (only the global Source chain read it), which made it
        misleading. So we chain on to Brush manually when it is ticked.
        """
        worker = self._build_colmap_worker()
        if worker is not None:
            worker.finished_signal.connect(self._on_reconstruction_standalone_finished)
            self._start_tool_worker(worker)

    def _on_reconstruction_standalone_finished(self, success, message):
        """Chain on to Brush after a successful standalone reconstruction, when
        "Lancer Brush" is ticked — cf. ``_launch_reconstruction``.
        """
        if success and self.run_state.entrainement_apres:
            self._launch_entrainement()

    def _launch_entrainement(self):
        """Standalone run (outside the chain) of the Entraînement tab (PIPELINE),
        same idiom as ``_launch_reconstruction``. Reuses
        ``_build_brush_worker`` — dataset = the project folder produced by
        COLMAP (Source/output + project name), NOT the manual
        ``input_path``/``output_path`` fields of standalone mode (those are
        never filled in here and would point at the wrong folder, cf. the
        OUTILS "Brush" module for manual use).
        """
        worker = self._build_brush_worker()
        if worker is not None:
            self._start_tool_worker(worker)

    def _fourdgs_upscale_params(self, params):
        """Merges the shared Upscale panel's settings (model, scale, tile...) with
        the 4DGS checkbox's own on/off state — same pattern as ``_launch_sharp``."""
        upscale_checked = params.get("upscale", False)
        return {**self.panels["upscale"].get_params(), "active": upscale_checked}

    def _launch_fourdgs(self):
        """Unticked (default): full extraction + COLMAP, on the videos of the
        Source field. Ticked: "COLMAP only", videos ignored (videos_dir=None,
        cf. the former ``FourDGSTab.run_colmap_only`` logic) — to re-run the
        reconstruction on already extracted frames without going through FFmpeg
        again.
        """
        panel = self.panels["4dgs"]
        params = panel.get_params()
        if not self._check_paths(params["output_path"]):
            return
        videos_dir = None if params.get("colmap_only") else (params["input_path"] or None)
        colmap_params = {
            key: params[key]
            for key in ("camera_model", "single_camera", "matcher_type", "sequential_overlap")
            if key in params
        }
        worker = FourDGSWorker(
            videos_dir, params["output_path"], params["fps"],
            upscale_params=self._fourdgs_upscale_params(params),
            colmap_params=colmap_params,
        )
        self._start_tool_worker(worker)

    def _launch_sharp(self):
        panel = self.panels["sharp"]
        params = panel.get_params()
        upscale_checked = params.get("upscale", False)
        params.update(self.panels["upscale"].get_params())
        params["upscale"] = upscale_checked
        if params["mode"] == "video":
            if not self._check_paths(params["video_path"], params["video_output_path"]):
                return
            worker = SharpVideoWorker(params["video_path"], params["video_output_path"], params)
            worker.long_run_signal.connect(self._confirm_sharp_long_run)
        else:
            if not self._check_paths(params["input_path"], params["output_path"]):
                return
            worker = SharpWorker(params["input_path"], params["output_path"], params)
        self._start_tool_worker(worker)

    def _confirm_sharp_long_run(self, worker, total_frames: int, estimated_seconds: float):
        """Ask before committing the machine to a very long Sharp video run.

        Runs on the GUI thread, woken by SharpVideoWorker.long_run_signal; the
        worker is blocked meanwhile and resumes on answer_long_run().
        """
        hours = estimated_seconds / 3600
        duration = (
            tr("sharp_duration_hours", "{h} h").format(h=f"{hours:.1f}")
            if hours >= 1
            else tr("sharp_duration_minutes", "{m} min").format(m=int(estimated_seconds // 60))
        )
        answer = QMessageBox.question(
            self,
            tr("sharp_long_run_title", "Traitement très long"),
            tr(
                "sharp_long_run_body",
                "Sharp va traiter {n} images une par une, soit environ {d} de calcul "
                "sans interruption. Lancer quand même ?",
            ).format(n=total_frames, d=duration),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        worker.answer_long_run(answer == QMessageBox.StandardButton.Yes)

    def _launch_splat_transform(self):
        panel = self.panels["splattransform"]
        input_path = panel.input_path.text().strip()
        output_dir = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_dir):
            return
        src_params = panel.get_params()
        output_path = str(Path(output_dir) / f"{Path(input_path).stem}.{src_params['format']}")
        st_params = {"--overwrite": True}
        if src_params["filter_nan"]:
            st_params["--filter-nan"] = True
        if src_params["filter_floaters"]:
            st_params["--filter-floaters"] = True
        if src_params["morton"]:
            st_params["--morton-order"] = True
        if src_params["harmonics"]:
            st_params["--filter-harmonics"] = "0"
        if src_params["decimate"] < 100:
            if src_params["format"] != "ply":
                QMessageBox.critical(
                    self, tr("msg_error", "Erreur"),
                    tr("err_decimate_ply_only",
                       "La décimation nécessite une sortie au format .ply."),
                )
                return
            st_params["--decimate"] = f"{src_params['decimate']:.0f}%"
        worker = SplatTransformWorker(input_path, output_path, st_params)
        self._start_tool_worker(worker)

    def _launch_upscale(self):
        panel = self.panels["upscale"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        worker = TestWorker(input_path, output_path, panel.get_params())
        self._start_tool_worker(worker, finished_signal=worker.finished)

    def _launch_brush(self):
        """OUTILS "Brush" module (manual/standalone mode of the Training panel,
        cf. entrainement_panel.py): trains directly on an already-prepared
        dataset (sparse + images), without going through the Source →
        Reconstruction pipeline chain."""
        panel = self.panels["brush"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        params = panel.get_params().to_engine_params()
        params["refine_mode"] = panel.combo_mode.currentData() == "refine"
        ply_name = panel.ply_name_edit.text().strip()
        if ply_name:
            params["ply_name"] = ply_name
        worker = BrushWorker(input_path, output_path, params, project_name=Path(input_path).name)
        self._start_tool_worker(worker)

    def _delete_dataset(self):
        """Destructive button in the Source panel (``btn_delete_dataset``):
        empties the project's output folder (out/project), except images, via
        ``ColmapEngine.delete_project_content`` (built-in safety checks, sends
        to trash — never a permanent delete). Was left unwired since the UI
        redesign."""
        source_state = self.panels["source"].get_state()
        output_path = source_state["output_path"].strip()
        project_name = source_state["project_name"].strip()
        if not self._check_paths(output_path, project_name):
            return
        target = Path(output_path) / project_name
        reply = QMessageBox.question(
            self, tr("source_delete_dataset", "Supprimer le dataset existant"),
            tr("confirm_delete_dataset",
               "Supprimer tout le contenu de ce projet, à l'exception des images ? "
               "Le contenu sera mis à la corbeille."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        success, message = ColmapEngine.delete_project_content(target)
        self.logs_window.append_log(message)
        if success:
            self.notify(tr("msg_success", "Succès"), message)
        else:
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    # ── Named configuration (Load / Save) ───────────────────────────────────────
    def collect_config(self) -> ChainConfig:
        """Aggregate the panel state + flags into a serialisable ChainConfig."""
        def state_of(key):
            panel = self.panels.get(key)
            return panel.get_state() if panel and hasattr(panel, "get_state") else {}
        return ChainConfig(
            source=state_of("source"),
            extraction360=state_of("extraction360"),
            upscale=state_of("upscale"),
            colmap=state_of("reconstruction"),
            brush=state_of("entrainement"),
            cleaning=state_of("nettoyage"),
            export=state_of("export"),
            flags=self.run_state.to_dict(),
        )

    def apply_config(self, cfg: ChainConfig):
        """Apply a ChainConfig to the panels and to the shared flags."""
        mapping = {
            "source": cfg.source, "extraction360": cfg.extraction360,
            "upscale": cfg.upscale, "reconstruction": cfg.colmap,
            "entrainement": cfg.brush, "nettoyage": cfg.cleaning, "export": cfg.export,
        }
        for key, state in mapping.items():
            panel = self.panels.get(key)
            if panel and hasattr(panel, "set_state"):
                panel.set_state(state)
        self.run_state.load_dict(cfg.flags or {})

    def save_config_dialog(self):
        name, ok = QInputDialog.getText(self, tr("settings_save", "Sauvegarder"),
                                        tr("config_name", "Nom de la configuration"))
        if ok and name.strip():
            try:
                save_config(name.strip(), self.collect_config())
                self.logs_window.append_log(tr("config_saved", "Configuration sauvegardée : ") + name.strip())
            except (ValueError, OSError) as e:
                QMessageBox.warning(self, tr("msg_error", "Erreur"), str(e))

    def load_config_dialog(self):
        names = list_configs()
        if not names:
            QMessageBox.information(self, tr("settings_load", "Charger"),
                                   tr("config_none", "Aucune configuration sauvegardée."))
            return
        name, ok = QInputDialog.getItem(self, tr("settings_load", "Charger"),
                                        tr("config_choose", "Configuration :"), names, 0, False)
        if ok and name:
            try:
                self.apply_config(load_config(name))
                self.logs_window.append_log(tr("config_loaded", "Configuration chargée : ") + name)
            except (ValueError, OSError) as e:
                QMessageBox.warning(self, tr("msg_error", "Erreur"), str(e))

    def delete_config_dialog(self):
        """Same idiom as ``load_config_dialog`` (pick from the list), plus a
        confirmation: the operation removes a file and cannot be undone.
        """
        names = list_configs()
        if not names:
            QMessageBox.information(self, tr("settings_delete", "Supprimer"),
                                   tr("config_none", "Aucune configuration sauvegardée."))
            return
        name, ok = QInputDialog.getItem(self, tr("settings_delete", "Supprimer"),
                                        tr("config_choose", "Configuration :"), names, 0, False)
        if not (ok and name):
            return
        confirm = QMessageBox.question(
            self, tr("settings_delete", "Supprimer"),
            # Same as _delete_selected_preset: no default on a key with {0}.
            tr("config_delete_confirm").format(name),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            if delete_config(name):
                self.logs_window.append_log(tr("config_deleted", "Configuration supprimée : ") + name)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, tr("msg_error", "Erreur"), str(e))

    # ── Notifications ───────────────────────────────────────────────────────────
    def set_notifications_enabled(self, enabled: bool):
        self._notifications_enabled = bool(enabled)

    def notify(self, title, message):
        """Notify the user when notifications are enabled."""
        if self._notifications_enabled:
            notifications.notify(title, message)

    # ── Settings ──────────────────────────────────────────────────────────────
    def open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.notificationsToggled.connect(self.set_notifications_enabled)
        self._settings_window.show()
        self._settings_window.raise_()

    def _on_reset_clicked(self):
        """Destructive reset: never executed without explicit confirmation
        (Light/Deep choice) in ``ResetDialog``."""
        diag = ResetDialog(self)
        if diag.exec():
            self.reset_factory(diag.result_deep)

    def restart_application(self):
        """Restart the application (cf. ``AppLifecycle.restart``)."""
        AppLifecycle.restart()

    def reset_factory(self, deep=False):
        """Delete the venvs (and engines/config.json when ``deep``) then re-run
        the install/application. Already confirmed by ``ResetDialog`` on the
        ``SettingsWindow`` side before the signal is emitted.
        """
        AppLifecycle.reset_factory(deep)

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.btn_settings.setText(f"⚙ {tr('btn_settings_label', 'Paramètres')}")
        self.btn_logs.setText(f"▤ {tr('logbar_title', 'Logs')}")
        self.btn_relaunch.setText(tr("settings_relaunch", "Relancer"))
        self.btn_quit.setText(tr("settings_quit", "Quitter"))

    # ── Closing ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        """Watch point of Lot 4 (PROMPT_CLAUDE_CODE_REFONTE_UI.md): cancels an
        active OUTILS worker and stops SuperSplatEngine so no orphan local
        server is left behind when the window closes.
        """
        self.session_manager.save(immediate=True)
        self._cancel_active_worker()
        for key in ("visualiser", "supersplat"):
            engine = getattr(self.panels.get(key), "engine", None)
            if engine is not None:
                engine.stop_all()
        event.accept()
