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

import sys
from pathlib import Path

from PySide6.QtCore import Qt
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
from app.core.config_io import (
    ChainConfig,
    delete_config,
    list_configs,
    load_config,
    save_config,
)
from app.core.engine import ColmapEngine
from app.core.i18n import add_language_observer, get_current_lang, tr
from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus
from app.gui.activity_bar import ActivityBar
from app.gui.appbar import AppBar
from app.gui.logs_window import LogsWindow
from app.gui.managers import AppLifecycle, SessionManager
from app.gui.panels.cleaner_panel import CleanerPanel
from app.gui.panels.entrainement_panel import EntrainementPanel
from app.gui.panels.export_panel import ExportPanel
from app.gui.panels.extractor360_panel import Extractor360Panel
from app.gui.panels.four_dgs_panel import FourDGSPanel
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.sharp_panel import SharpPanel
from app.gui.panels.source_panel import SourcePanel
from app.gui.panels.splat_transform_panel import SplatTransformPanel
from app.gui.panels.upscale_panel import UpscalePanel
from app.gui.panels.visualiser_panel import VisualiserPanel
from app.gui.pipeline_orchestrator import (
    PipelineContext,
    PipelineOrchestrator,
    build_splat_transform_params,
    decimate_needs_ply,
    merge_sharp_params,
)
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail, item_label
from app.gui.settings_window import SettingsWindow
from app.gui.studio_nav import PageRegistry
from app.gui.styles import DEFAULT_THEME, THEMES, get_saved_theme, set_dark_theme

# Worker classes are resolved by name through ``_WorkerNamespace`` (late
# lookup, handed to the Qt-free pipeline orchestrator): the imports below look
# unused to the linter but are required.
from app.gui.workers import (  # noqa: F401
    BrushWorker,
    CleanerWorker,
    ColmapJob,
    ColmapWorker,
    ExportWorker,
    Extractor360Worker,
    FourDGSWorker,
    LocalUpscaleWorker,
    SharpVideoWorker,
    SharpWorker,
    SplatTransformWorker,
    UpscaleImagesWorker,
)

# Stacked page order (PIPELINE steps, then OUTILS modules).
_PAGE_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)

# Languages written right-to-left: the whole UI is mirrored for them (G3).
_RTL_LANGS = frozenset({"ar"})


def _theme_color(key):
    """Colour of the saved theme, read when a widget is built."""
    return THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])[key]


def _is_safe_project_name(name):
    """True when ``name`` stays a single folder under the output path.

    The project name is joined to the output folder everywhere
    (``Path(output) / project``): "..", "." or a separator would point the
    run — or the "delete dataset" button — at a folder outside the project.
    Same rule ColmapEngine already enforces on its side.
    """
    name = (name or "").strip()
    return name not in ("", ".", "..") and "/" not in name and "\\" not in name


def _ctx_field(name):
    """Window attribute backed by a ``PipelineContext`` field."""
    return property(
        lambda self: getattr(self._ctx, name),
        lambda self, value: setattr(self._ctx, name, value),
    )


class _WorkerNamespace:
    """Worker classes, looked up in this module when used.

    The orchestrator is Qt-free, so it receives the ``QThread`` workers through
    this namespace. The lookup is late (not a snapshot) so replacing a worker
    class on this module — as the tests do — is honoured.
    """

    def __getattr__(self, name):
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(name) from None


class StudioWindow(QMainWindow):
    """Four-zone shell. Rail selection → swaps the centre + right page."""

    # Class-level defaults of the OUTILS post-step state (L3-05/L5-08), so
    # the chain helpers behave when nothing set them (no tool launched yet).
    # (``_tool_ply_root`` / ``_tool_producer_label`` live in the chain context.)
    _tool_post_steps = ()
    _retired_worker = None

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
        # Output fields the chain filled in itself (Nettoyage, Export), so a
        # later run may replace them while a value typed by the user is kept.
        self._chain_prefilled = {}
        # L6-01: the toggle lives in config.json; it used to reset to off on
        # every launch while the Settings checkbox never showed it either.
        self._notifications_enabled = notifications.get_saved_enabled()
        self._settings_window = None
        self._active_worker = None
        # Worker whose finished signal was just handled: kept referenced
        # until the next one finishes, so its QThread is never garbage
        # collected while the OS thread is still unwinding (SIGABRT).
        self._retired_worker = None
        # L3-05/L5-08: post-steps (Nettoyage/Export/Visualiser…) requested by
        # the OUTILS "Lancer" button that started the active tool worker, and
        # where that tool wrote its PLY (None → the chain's usual lookup).
        self._tool_post_steps = []
        self._tool_ply_root = None
        self._tool_producer_label = None
        self.init_ui()
        self._apply_layout_direction()
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
        self.breadcrumb.setStyleSheet(f"color: {_theme_color('muted')}; padding: 4px 8px;")
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
            # Visualiser reuse the same panel classes, but each page is its own
            # instance: only run_state flags and Brush presets are shared (L3-08).
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
        # load/save/delete are project-workflow actions).
        self.panels["source"].btn_settings_load.clicked.connect(self.load_config_dialog)
        self.panels["source"].btn_settings_save.clicked.connect(self.save_config_dialog)
        self.panels["source"].btn_settings_delete.clicked.connect(self.delete_config_dialog)
        # D4/L5-09: ReconstructionPanel (and the post-step checkboxes that
        # have no effect in some modes) react to the pipeline mode selector.
        self.panels["source"].combo_mode.currentIndexChanged.connect(self._on_source_mode_changed)
        self._on_source_mode_changed()
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
            panel = self.panels[key]
            self.center_stack.addWidget(panel.center)
            self.right_stack.addWidget(panel.right)

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

        L5-05: the chaining flags (``run_state``) used to be saved only on
        close, never on this crash-safety path — a kill between two toggles
        and the next text edit silently lost them. ``RunState._notify`` fires
        for flags, ``project_name`` (already covered above) and every rail
        step status alike, so ``_on_run_state_changed_for_autosave`` filters
        down to actual flags.
        """
        source = self.panels.get("source")
        if source is None:
            return
        for field in (source.input_project_name, source.input_path, source.output_path):
            field.textChanged.connect(lambda _text=None: self.session_manager.save())
        self.run_state.add_observer(self._on_run_state_changed_for_autosave)

    def _on_run_state_changed_for_autosave(self, key):
        """Debounced autosave on an actual chaining-flag change (L5-05) — see
        ``_wire_session_autosave`` for why the filter is needed."""
        if key in self.run_state.to_dict():
            self.session_manager.save()

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
        border = _theme_color("border")
        line.setStyleSheet(f"color: {border}; background-color: {border};")
        return line

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

    def _reset_run_ui(self):
        """Back to the idle state once nothing runs anymore: Launch instead of
        Cancel, local Launch buttons re-enabled, activity bar and ring cleared."""
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self._set_tool_launch_buttons_enabled(True)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()

    def _set_tool_launch_buttons_enabled(self, enabled: bool):
        """Grey out every panel's local "Lancer" button while a worker is
        active (L3-12), Source's own Launch/Cancel excluded (toggled
        separately by ``set_running``). A click on an OUTILS Lancer button
        while a worker already ran was silently absorbed by
        ``_start_tool_worker``'s guard, with no visual sign it did nothing.
        """
        for key, panel in self.panels.items():
            if key == "source":
                continue
            button = getattr(panel, "btn_run", None)
            if button is not None:
                button.setEnabled(bool(enabled))

    def _on_source_mode_changed(self, _index=None):
        """React to SourcePanel's pipeline mode selector (D4/L5-09).

        ``combo_mode`` used to drive nothing outside ``launch()``:
        ReconstructionPanel (COLMAP settings, Resume) stayed active and
        editable in Sharp/4DGS, where it is entirely ignored
        (``_build_reconstruction_worker`` never reads it there) — greyed out
        here instead, with an explanatory tooltip (D4).

        The post-step checkboxes are greyed the same way when their flag has
        no effect for the current mode, per ``plan_pipeline``: Entraînement
        only runs for "gsplat"; Nettoyage/Export/Visualiser run for "gsplat"
        and "sharp" but never for "4dgs" (the plan is truncated right after
        Reconstruction there, cf. L5-09).
        """
        mode = self.panels["source"].current_mode()
        recon_panel = self.panels["reconstruction"]
        is_gsplat = mode == "gsplat"
        recon_panel.center.setEnabled(is_gsplat)
        recon_tooltip = (
            "" if is_gsplat else
            tr("tip_recon_ignored_non_gsplat",
               "Réglages ignorés hors mode Gsplat — la Reconstruction utilise "
               "Sharp ou la préparation de dataset 4DGS à la place de COLMAP.")
        )
        recon_panel.center.setToolTip(recon_tooltip)

        source = self.panels["source"]
        is_4dgs = mode == "4dgs"
        no_effect_tooltip = tr(
            "tip_no_effect_4dgs",
            "Sans effet en mode 4DGS : la chaîne s'arrête après la "
            "Reconstruction (pas d'entraîneur Apple Silicon).",
        )
        source.chk_entrainement.setEnabled(is_gsplat)
        source.chk_entrainement.setToolTip(
            "" if is_gsplat else
            tr("tip_no_effect_non_gsplat",
               "Sans effet hors mode Gsplat : seul ce mode entraîne avec Brush.")
        )
        for checkbox in (source.chk_nettoyer, source.chk_exporter, source.chk_visualiser):
            checkbox.setEnabled(not is_4dgs)
            checkbox.setToolTip("" if not is_4dgs else no_effect_tooltip)

    # ── Launch (orchestrated dispatch) ──────────────────────────────────────────
    def launch(self):
        """Compute the run plan from the mode + the run_state toggles, then
        actually start the pipeline chain (Source → Reconstruction/COLMAP →
        Entraînement/Brush, cf. ``_run_pipeline_step``). Also drives the rail
        (statuses + auto-follow) and the breadcrumb.
        """
        mode = self.panels["source"].current_mode()
        project_name = self.panels["source"].get_state()["project_name"]
        if project_name.strip() and not _is_safe_project_name(project_name):
            self._fail_pipeline_step("source", self._invalid_project_name_message())
            return []
        plan = plan_pipeline(mode, self.run_state)
        self.current_plan = plan
        # The plan only names steps; "reconstruction" means COLMAP, Sharp or the
        # 4DGS dataset prep depending on the mode, so the chain has to remember it.
        self.current_pipeline_mode = mode
        self._pipeline_images_dir = None
        self._pending_upscale_params = None
        self._tool_ply_root = None
        self._tool_producer_label = None
        self.run_state.reset_status()
        self.update_breadcrumb(plan)
        self.logs_window.append_log(tr("run_plan", "Plan : ") + " → ".join(plan))
        if plan:
            self._run_pipeline_step(0)
        return plan

    @staticmethod
    def _invalid_project_name_message():
        return tr(
            "err_project_name_invalid",
            "Nom de projet invalide : il ne doit pas contenir « / », « \\ » "
            "ni être « . » ou « .. ».",
        )

    def update_breadcrumb(self, plan):
        self.breadcrumb.setText(" → ".join(plan))

    # ── Chaining of the main pipeline workers ────────────────────────────────────
    # The chaining logic (step registry, worker builders, PLY lookup, prefill)
    # lives in ``app.gui.pipeline_orchestrator``; the methods below keep the
    # window's historical names and forward to it.
    @property
    def _ctx(self):
        """Chain state, created on first use (also on __init__-less windows)."""
        ctx = getattr(self, "_pipeline_ctx", None)
        if ctx is None:
            ctx = self._pipeline_ctx = PipelineContext()
        return ctx

    @property
    def _orchestrator(self):
        orch = getattr(self, "_pipeline_orch", None)
        if orch is None:
            orch = self._pipeline_orch = PipelineOrchestrator(
                self, _WorkerNamespace(), self._ctx
            )
        return orch

    current_plan = _ctx_field("plan")
    current_pipeline_mode = _ctx_field("mode")
    _plan_index = _ctx_field("plan_index")
    _pipeline_images_dir = _ctx_field("images_dir")
    _pending_upscale_params = _ctx_field("pending_upscale_params")
    _chain_prefilled = _ctx_field("chain_prefilled")
    _tool_ply_root = _ctx_field("tool_ply_root")
    _tool_producer_label = _ctx_field("tool_producer_label")

    def _run_pipeline_step(self, index):
        self._orchestrator.run_step(index)

    def _resolve_source_type(self, step, input_path, source_state):
        return self._orchestrator.resolve_source_type(step, input_path, source_state)

    def _build_extraction360_worker(self):
        return self._orchestrator.build_extraction360_worker()

    def _build_upscale_worker(self):
        return self._orchestrator.build_upscale_worker()

    def _build_reconstruction_worker(self):
        return self._orchestrator.build_reconstruction_worker()

    def _build_sharp_pipeline_worker(self):
        return self._orchestrator.build_sharp_pipeline_worker()

    def _build_fourdgs_pipeline_worker(self):
        return self._orchestrator.build_fourdgs_pipeline_worker()

    def _build_colmap_worker(self):
        return self._orchestrator.build_colmap_worker()

    def _build_brush_worker(self):
        return self._orchestrator.build_brush_worker()

    def _build_cleaner_worker(self):
        return self._orchestrator.build_cleaner_worker()

    def _build_export_worker(self):
        return self._orchestrator.build_export_worker()

    def _find_latest_ply(self, directory: Path):
        return self._orchestrator.find_latest_ply(directory)

    def _latest_reconstruction_ply(self):
        return self._orchestrator.latest_reconstruction_ply()

    def _missing_producer_message(self):
        return self._orchestrator.missing_producer_message()

    def _resolve_ply_output(self):
        return self._orchestrator.resolve_ply_output()

    def _prefill_cleaner_from_brush(self):
        self._orchestrator.prefill_cleaner_from_brush()

    def _prefill_export_from_previous(self):
        self._orchestrator.prefill_export_from_previous()

    def _prefill_visualiser_from_previous(self):
        self._orchestrator.prefill_visualiser_from_previous()

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
        self._set_tool_launch_buttons_enabled(False)
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
        if hasattr(worker, "eta_signal"):
            worker.eta_signal.connect(self.activity_bar.set_eta)

    def _on_pipeline_step_finished(self, success, message):
        """End of a pipeline step: DONE + next step on success; ERROR + chain
        stopped (no silent failure) otherwise.
        """
        step = self._active_pipeline_step
        worker = self._active_worker
        self._active_worker = None
        self._retired_worker = worker
        self.logs_window.append_log(message)
        if success:
            self.run_state.set_status(step, StepStatus.DONE)
            self.rail.set_step_status(step, StepStatus.DONE)
            self._run_pipeline_step(self._plan_index + 1)
            return
        stopped_by_user = bool(worker and getattr(worker, "stopped_by_user", False))
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self._reset_run_ui()
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
        self._reset_run_ui()
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
        self._reset_run_ui()
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
    def _post_steps_from_flags(self, *candidates):
        """Ordered post-steps among ``candidates`` whose ``run_state`` flag is
        on — the same toggles ``plan_pipeline`` reads, restricted to the
        checkboxes the calling OUTILS page actually shows (L3-05/L5-08).
        """
        flags = {
            "entrainement": self.run_state.entrainement_apres,
            "nettoyage": self.run_state.nettoyer_apres,
            "export": self.run_state.exporter_apres,
            "visualiser": self.run_state.visualiser_apres,
        }
        return [step for step in candidates if flags.get(step, False)]

    def _start_tool_worker(self, worker, finished_signal=None, post_steps=(),
                           ply_root=None, producer_label=None):
        """Start an OUTILS worker in the background: logs relayed to the log
        bar, SourcePanel switched to Cancel, result shown at the end.

        ``post_steps`` (L3-05/L5-08) are the chain steps to run once the tool
        succeeds — the "Nettoyage/Exporter/SuperSplat après" checkboxes shown
        on the tool's own page. They go through ``_run_pipeline_step`` like
        the main chain, from ``_on_tool_finished``: a single slot on the
        worker's finished signal, never a second chained ``connect`` (which
        would let the two slots race for ``self._active_worker``).
        ``ply_root`` tells the post-steps where the tool wrote its PLY.

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
        self._tool_post_steps = list(post_steps)
        self._tool_ply_root = ply_root
        self._tool_producer_label = producer_label
        # An OUTILS worker has no pipeline step: we name the page it was
        # started from, which is the one the user is looking at.
        self.activity_bar.set_step(item_label(self.nav.current))
        self._wire_worker_feedback(worker)
        signal = finished_signal if finished_signal is not None else worker.finished_signal
        signal.connect(self._on_tool_finished)
        self.panels["source"].set_running(True)
        self._set_cancel_enabled(True)
        self._set_tool_launch_buttons_enabled(False)
        self.panels["source"].progress_ring.start()
        worker.start()

    def _on_tool_finished(self, success, message):
        worker = self._active_worker
        self._active_worker = None
        self._retired_worker = worker
        post_steps, self._tool_post_steps = list(self._tool_post_steps), []
        if success and post_steps:
            # L3-05/L5-08: hand over to the chain mechanism, which resets the
            # Launch/Cancel state itself when it ends (or fails).
            self.logs_window.append_log(message)
            self._run_tool_post_steps(post_steps)
            return
        self._reset_run_ui()
        self.logs_window.append_log(message)
        stopped_by_user = bool(worker and getattr(worker, "stopped_by_user", False))
        if success:
            self.notify(tr("msg_success", "Succès"), message)
        elif not stopped_by_user:
            self.notify(tr("msg_error", "Erreur"), message)
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _run_tool_post_steps(self, steps):
        """Run ``steps`` as a mini plan after a successful OUTILS launch
        (L3-05/L5-08). Same code path as the main chain: pre-fill from the
        tool's output (``_tool_ply_root``), rail statuses, error dialog.
        """
        self.current_plan = list(steps)
        for step in self.current_plan:
            self.run_state.set_status(step, StepStatus.IDLE)
            self.rail.set_step_status(step, StepStatus.IDLE)
        self.update_breadcrumb(self.current_plan)
        self.logs_window.append_log(tr("run_plan", "Plan : ") + " → ".join(self.current_plan))
        self._run_pipeline_step(0)

    def _check_paths(self, *paths) -> bool:
        if all(p and str(p).strip() for p in paths):
            return True
        QMessageBox.critical(self, tr("msg_error", "Erreur"), tr("err_no_paths", "Chemins manquants."))
        return False

    def _launch_cleaner(self):
        panel = self.panels["nettoyage"]
        if not self._check_paths(panel.input_path.text().strip(), panel.output_path.text().strip()):
            return
        self._start_tool_worker(self._build_cleaner_worker())

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

        The "Lancer Brush" and "SuperSplat après" checkboxes are visible in
        this panel (L5-08): they are honoured as post-steps of this button,
        through the same chain mechanism as the global Launch. (An earlier
        fix connected a second slot on ``finished_signal`` to relaunch Brush;
        both slots then raced for ``_active_worker`` — cf. ``_start_tool_worker``.)
        """
        worker = self._build_colmap_worker()
        if worker is not None:
            # D5: this button always builds a COLMAP worker, so the mode is
            # forced to "gsplat" — the same rule as plan_pipeline(), which only
            # chains Brush in that mode. Sharp/4DGS never reach this path.
            self.current_pipeline_mode = "gsplat"
            self._start_tool_worker(
                worker, post_steps=self._post_steps_from_flags("entrainement", "visualiser")
            )

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
        params = merge_sharp_params(
            self.panels["sharp"].get_params(), self.panels["upscale"].get_params()
        )
        built = self._build_sharp_tool_worker(params)
        if built is None:
            return
        worker, ply_root = built
        # L3-05: the page's "Nettoyage/Exporter/SuperSplat après" checkboxes
        # apply to this button too, on the PLY Sharp writes in its output folder.
        self._start_tool_worker(
            worker,
            post_steps=self._post_steps_from_flags("nettoyage", "export", "visualiser"),
            ply_root=ply_root,
            producer_label="Sharp",
        )

    def _build_sharp_tool_worker(self, params):
        """``(worker, ply_root)`` for the Sharp page's mode, or None when the
        required paths are missing (the user has already been told)."""
        if params["mode"] == "video":
            if not self._check_paths(params["video_path"], params["video_output_path"]):
                return None
            worker = SharpVideoWorker(params["video_path"], params["video_output_path"], params)
            worker.long_run_signal.connect(self._confirm_sharp_long_run)
            return worker, Path(params["video_output_path"])
        if not self._check_paths(params["input_path"], params["output_path"]):
            return None
        worker = SharpWorker(params["input_path"], params["output_path"], params)
        return worker, Path(params["output_path"])

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

    def _warn_decimate_needs_ply(self):
        QMessageBox.critical(
            self, tr("msg_error", "Erreur"),
            tr("err_decimate_ply_only", "La décimation nécessite une sortie au format .ply."),
        )

    def _launch_splat_transform(self):
        panel = self.panels["splattransform"]
        input_path = panel.input_path.text().strip()
        output_dir = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_dir):
            return
        src_params = panel.get_params()
        if decimate_needs_ply(src_params):
            self._warn_decimate_needs_ply()
            return
        output_path = str(Path(output_dir) / f"{Path(input_path).stem}.{src_params['format']}")
        worker = SplatTransformWorker(
            input_path, output_path, build_splat_transform_params(src_params)
        )
        # L3-05: post-steps run on the converted file itself; Nettoyage/Export
        # need a .ply, so a non-PLY output fails those steps with a clear
        # message naming SplatTransform (``missing_producer_message``).
        self._start_tool_worker(
            worker,
            post_steps=self._post_steps_from_flags("nettoyage", "export", "visualiser"),
            ply_root=Path(output_path),
            producer_label="SplatTransform",
        )

    def _launch_upscale(self):
        panel = self.panels["upscale"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        worker = LocalUpscaleWorker(input_path, output_path, panel.get_params())
        self._start_tool_worker(worker, finished_signal=worker.finished_signal)

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
        # L3-05: this page only shows "SuperSplat après"; the PLY lands in
        # the tool's own output folder, not the Projet panel's checkpoints.
        self._start_tool_worker(
            worker,
            post_steps=self._post_steps_from_flags("visualiser"),
            ply_root=Path(output_path),
            producer_label="Brush",
        )

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
        if not _is_safe_project_name(project_name):
            QMessageBox.critical(
                self, tr("msg_error", "Erreur"), self._invalid_project_name_message()
            )
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
            self._settings_window.resetRequested.connect(self.reset_factory)
        self._settings_window.show()
        self._settings_window.raise_()

    def restart_application(self):
        """Restart the application (cf. ``AppLifecycle.restart``)."""
        AppLifecycle.restart()

    def reset_factory(self, deep=False):
        """Delete the venvs (and engines/config.json when ``deep``) then re-run
        the install/application. Already confirmed by ``ResetDialog`` on the
        ``SettingsWindow`` side before the signal is emitted.
        """
        AppLifecycle.reset_factory(deep)

    def _apply_layout_direction(self):
        """Mirror the whole UI for right-to-left languages (Arabic), back to
        left-to-right otherwise. Application-wide, so dialogs follow too."""
        direction = (
            Qt.LayoutDirection.RightToLeft if get_current_lang() in _RTL_LANGS
            else Qt.LayoutDirection.LeftToRight
        )
        QApplication.setLayoutDirection(direction)

    def retranslate_ui(self):
        self._apply_layout_direction()
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
        # A cancelled worker is stopped but its OS thread may still be running:
        # wait (bounded) so the QThread is not destroyed while alive (SIGABRT,
        # cf. _start_tool_worker) and the run is not left mid-write.
        worker = self._active_worker
        if worker is not None and worker.wait(5000) is False:
            # L5-06: the first wait() timed out — a running QThread must never
            # be destroyed. Ask again, then force it before the window is
            # allowed to close under it.
            self.logs_window.append_log(
                tr("log_forced_stop_on_close",
                   "Un traitement ne s'est pas arrêté après 5 s — arrêt forcé avant fermeture.")
            )
            worker.requestInterruption()
            worker.terminate()
            # Bounded: a deferred termination must not hang the close forever.
            if not worker.wait(2000):
                print("[WARN] worker still alive 2 s after terminate(); closing anyway",
                      file=sys.stderr)
        for key in ("visualiser", "supersplat"):
            wait_start = getattr(self.panels.get(key), "wait_start", None)
            if wait_start is not None:
                wait_start()
            engine = getattr(self.panels.get(key), "engine", None)
            if engine is not None:
                engine.stop_all()
        event.accept()
