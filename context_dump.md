## app/gui/studio_window.py (770 lignes)
```python
"""Fenêtre principale « Studio » — interface en 4 zones.

Assemble : TopBar (haut), Rail (gauche), zone centre + barre de droite
(``QStackedWidget`` pilotés par la sélection du rail), LogBar (bas).

Lancée par défaut depuis ``main.py`` (via ``_launch_gui()`` dans
``app/cli/__init__.py``). Les panneaux PIPELINE (Source, Reconstruction,
Entraînement, Nettoyage, Export, Visualiser) et OUTILS (Brush, Sharp,
SuperSplat, Upscale, SplatTransform, 4DGS, Extracteur 360) sont instanciés
dynamiquement et gérés par ``PageRegistry``.
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

from app import VERSION
from app.core import notifications
from app.core.config_io import ChainConfig, list_configs, load_config, save_config
from app.core.engine import ColmapEngine
from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus
from app.gui.logbar import LogBar
from app.gui.managers import AppLifecycle, SessionManager
from app.gui.panels.cleaner_panel import CleanerPanel
from app.gui.panels.entrainement_panel import EntrainementPanel
from app.gui.panels.export_panel import ExportPanel
from app.gui.panels.extractor360_panel import Extractor360Panel
from app.gui.panels.four_dgs_panel import FourDGSPanel
from app.gui.panels.reconstruction_logic import apply_source_blur_settings
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.sharp_panel import SharpPanel
from app.gui.panels.source_panel import SourcePanel
from app.gui.panels.splat_transform_panel import SplatTransformPanel
from app.gui.panels.upscale_panel import UpscalePanel
from app.gui.panels.visualiser_panel import VisualiserPanel
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail
from app.gui.settings_window import SettingsWindow
from app.gui.studio_nav import PageRegistry
from app.gui.styles import set_dark_theme
from app.gui.topbar import TopBar
from app.gui.widgets.upscale_widgets import TestWorker
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

# Ordre des pages du stacked (étapes PIPELINE puis modules OUTILS).
_PAGE_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)

# Mêmes extensions vidéo que ColmapEngine._prepare_images (app/core/engine.py) —
# sert à déduire l'``input_type`` COLMAP depuis le champ Source, qui ne propose
# pas de sélecteur dédié (glisser-déposer dossier/fichier/vidéo).
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}


def _detect_input_type(path_str):
    """Devine ``images``/``video`` depuis le chemin Source (cf. ``_VIDEO_EXTS``)."""
    path = Path(path_str)
    if path.is_file():
        return "video" if path.suffix.lower() in _VIDEO_EXTS else "images"
    if path.is_dir() and any(f.suffix.lower() in _VIDEO_EXTS for f in path.iterdir() if f.is_file()):
        return "video"
    return "images"


class StudioWindow(QMainWindow):
    """Coquille 4 zones. Sélection du rail → change la page centre + droite."""

    def __init__(self):
        super().__init__()
        self.run_state = RunState()
        self.nav = PageRegistry(_PAGE_KEYS)   # mapping pages + sélection courante
        self._auto_follow = True              # suit l'étape active (désaccouplé au clic manuel)
        self.current_plan = []
        self._plan_index = 0
        self._active_pipeline_step = None
        self._notifications_enabled = False
        self._settings_window = None
        self._active_worker = None
        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)
        # Dernier projet (chemins Source) : rechargé avant l'affichage de la
        # fenêtre, sauvegardé en continu (debounce) et à la fermeture.
        self.session_manager = SessionManager(self)
        self.session_manager.load()
        self._wire_session_autosave()

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        # Taille min réduite pour pouvoir tenir sur petit écran ; taille initiale
        # ajustée à l'écran (comme ColmapGUI) pour éviter que la fenêtre s'ouvre
        # plus large que l'écran et que la barre de droite déborde.
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

        # ── Top bar ───────────────────────────────────────────────────────────
        self.topbar = TopBar()
        self.topbar.settingsRequested.connect(self.open_settings)
        self.topbar.launchRequested.connect(self.on_topbar_launch)
        # Nom de projet : miroir en temps réel avec le champ du panneau Source,
        # via run_state (source de vérité unique — cf. run_state.py).
        self.topbar.projectNameChanged.connect(self._on_topbar_project_name_changed)
        self._project_name_observer = self._on_run_state_project_name_changed
        self.run_state.add_observer(self._project_name_observer)
        self.topbar.set_project_name(self.run_state.project_name)
        root.addWidget(self.topbar)

        # ── Corps : rail | centre | barre de droite ───────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.rail = Rail()
        self.rail.itemSelected.connect(self.on_rail_selected)
        self.rail.setFixedWidth(220)
        body.addWidget(self.rail)

        # Filet fin rail | centre
        body.addWidget(self._vline())

        # Colonne centre : breadcrumb de flux + pile de panneaux.
        center_col = QVBoxLayout()
        center_col.setContentsMargins(8, 0, 8, 0)
        self.breadcrumb = QLabel("")
        self.breadcrumb.setStyleSheet("color: #9aa5ce; padding: 4px 8px;")
        center_col.addWidget(self.breadcrumb)
        self.center_stack = QStackedWidget()
        center_col.addWidget(self.center_stack, stretch=1)
        body.addLayout(center_col, stretch=3)

        # Filet fin centre | barre de droite
        body.addWidget(self._vline())

        # Barre de droite : largeur suffisante pour les accordéons de params, et
        # chaque panneau y gère son propre défilement vertical.
        self.right_stack = QStackedWidget()
        self.right_stack.setFixedWidth(400)
        body.addWidget(self.right_stack)

        # Panneaux réels disponibles (les autres clés restent des placeholders,
        # remplacés aux sous-lots 3b/3c/4/5).
        self.panels = {
            "source": SourcePanel(self.run_state),
            "reconstruction": ReconstructionPanel(self.run_state),
            "entrainement": EntrainementPanel(self.run_state),
            "nettoyage": CleanerPanel(self.run_state),
            "export": ExportPanel(self.run_state),
            "visualiser": VisualiserPanel(self.run_state),
            # Modules OUTILS. Brush ≈ Entraînement (mode manuel) et SuperSplat ≈
            # Visualiser partagent le même écran sous-jacent (cf. spec §2.3).
            "brush": EntrainementPanel(self.run_state, standalone=True),
            "sharp": SharpPanel(self.run_state),
            "supersplat": VisualiserPanel(self.run_state),
            "upscale": UpscalePanel(self.run_state),
            "splattransform": SplatTransformPanel(self.run_state),
            "4dgs": FourDGSPanel(self.run_state),
            "360": Extractor360Panel(self.run_state),
        }

        # Bouton « Lancer » local des modules OUTILS (et de Nettoyage/Export,
        # utilisables seuls hors chaîne pipeline) : chacun démarre son propre
        # worker, le topbar bascule en Annuler pendant l'exécution (cf.
        # _start_tool_worker / on_topbar_launch).
        self.panels["nettoyage"].btn_run.clicked.connect(self._launch_cleaner)
        self.panels["export"].btn_run.clicked.connect(self._launch_export)
        self.panels["360"].btn_run.clicked.connect(self._launch_extractor360)
        self.panels["4dgs"].btn_run.clicked.connect(self._launch_fourdgs)
        self.panels["4dgs"].btn_colmap_only.clicked.connect(self._launch_fourdgs_colmap_only)
        self.panels["sharp"].btn_run.clicked.connect(self._launch_sharp)
        self.panels["splattransform"].btn_run.clicked.connect(self._launch_splat_transform)
        self.panels["upscale"].btn_run.clicked.connect(self._launch_upscale)
        self.panels["brush"].btn_run.clicked.connect(self._launch_brush)
        self.panels["source"].btn_delete_dataset.clicked.connect(self._delete_dataset)

        # Pages ajoutées dans l'ordre de _PAGE_KEYS : leur index correspond à
        # celui de PageRegistry (compteur), déterministe même sous mock PySide6.
        for key in _PAGE_KEYS:
            panel = self.panels.get(key)
            if panel is not None:
                self.center_stack.addWidget(panel.center)
                self.right_stack.addWidget(panel.right)
            else:
                self.center_stack.addWidget(self._placeholder(key, "center"))
                self.right_stack.addWidget(self._placeholder(key, "right"))

        root.addLayout(body, stretch=1)

        # ── Log bar (repliée par défaut) ──────────────────────────────────────
        self.logbar = LogBar()
        root.addWidget(self.logbar)

        # ── Bottom bar: version + lifecycle actions (Restart/Quit) ─────────────
        # Moved out of SettingsWindow: these are global actions of the main
        # window, not settings — better here, always visible, than buried in
        # a dialog.
        root.addWidget(self._build_bottom_bar())

        # Sélection initiale : première étape (programmatique, sans désaccoupler).
        if _PAGE_KEYS:
            self.rail.select(_PAGE_KEYS[0])
            self._show_page(_PAGE_KEYS[0])

    def _wire_session_autosave(self):
        """Déclenche une sauvegarde (debounce 1.5s, cf. SessionManager) sur les
        champs identifiant le projet — filet de sécurité en cas de crash/kill,
        en plus de la sauvegarde immédiate à la fermeture (cf. closeEvent)."""
        source = self.panels.get("source")
        if source is None:
            return
        for field in (source.input_project_name, source.input_path, source.output_path):
            field.textChanged.connect(lambda _text=None: self.session_manager.save())

    def _build_bottom_bar(self):
        """Always-visible bottom bar: software version + lifecycle actions
        (Restart/Quit), moved out of SettingsWindow — these are global
        actions, not settings."""
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(8, 2, 8, 2)

        self.lbl_version = QLabel(f"v{VERSION}")
        self.lbl_version.setStyleSheet("color: #666666; font-size: 10px;")
        row.addWidget(self.lbl_version)
        row.addStretch(1)

        self.btn_relaunch = QPushButton(tr("settings_relaunch", "Relancer"))
        self.btn_relaunch.clicked.connect(self.restart_application)
        row.addWidget(self.btn_relaunch)

        self.btn_quit = QPushButton(tr("settings_quit", "Quitter"))
        self.btn_quit.clicked.connect(self.close)
        row.addWidget(self.btn_quit)

        return w

    def _vline(self):
        """Filet vertical fin séparant deux zones."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedWidth(1)
        line.setStyleSheet("color: #2f3549; background-color: #2f3549;")
        return line

    def _placeholder(self, key, zone):
        """Page provisoire (remplacée par le vrai panneau aux lots 3-5)."""
        w = QLabel(f"[{zone}] {key} — à venir")
        w.setObjectName(f"placeholder_{zone}_{key}")
        return w

    # ── Nom de projet (miroir top bar ↔ panneau Source via run_state) ───────────
    def _on_topbar_project_name_changed(self, text):
        self.run_state.set_field("project_name", text)

    def _on_run_state_project_name_changed(self, key):
        if key != "project_name":
            return
        self.topbar.set_project_name(self.run_state.project_name)

    # ── Navigation ──────────────────────────────────────────────────────────────
    def on_rail_selected(self, key):
        """Sélection manuelle depuis le rail : désaccouple l'auto-follow (même
        logique que le verrou d'auto-scroll des logs) et change la page. Si
        l'étape est en erreur, déplie la barre de logs (clic sur l'icône rouge)."""
        self._auto_follow = False
        self._show_page(key)
        if key in PIPELINE_STEPS and self.run_state.get_status(key) == StepStatus.ERROR:
            self.logbar.set_collapsed(False)

    def _show_page(self, key):
        index = self.nav.select(key)
        if index is None:
            return
        self.center_stack.setCurrentIndex(index)
        self.right_stack.setCurrentIndex(index)

    def follow_step(self, key):
        """Suit l'étape active pendant un run, tant que l'auto-follow n'a pas été
        désaccouplé par un clic manuel."""
        if self._auto_follow:
            self.rail.select(key)
            self._show_page(key)

    def current_page_key(self):
        return self.nav.current

    # ── Lancement (dispatch orchestré) ──────────────────────────────────────────
    def launch(self):
        """Calcule le plan de run selon le mode + les toggles run_state, puis
        démarre réellement la chaîne pipeline (Source → Reconstruction/COLMAP →
        Entraînement/Brush, cf. ``_run_pipeline_step``). Pilote aussi le rail
        (statuts + auto-follow) et le breadcrumb."""
        mode = self.topbar.current_mode()
        plan = plan_pipeline(mode, self.run_state)
        self.current_plan = plan
        self._auto_follow = True
        self.run_state.reset_status()
        self.update_breadcrumb(plan)
        self.logbar.append_log(tr("run_plan", "Plan : ") + " → ".join(plan))
        if plan:
            self._run_pipeline_step(0)
        return plan

    def update_breadcrumb(self, plan):
        self.breadcrumb.setText(" → ".join(plan))

    # ── Enchaînement des workers du pipeline principal ───────────────────────────
    def _run_pipeline_step(self, index):
        """Démarre l'étape ``self.current_plan[index]`` si elle fait partie de la
        chaîne automatisée (Source/Reconstruction/Entraînement). Source n'a pas
        de worker propre (elle ne fait que fournir les chemins consommés par
        Reconstruction) : elle est marquée DONE immédiatement et la chaîne
        enchaîne. Les post-étapes OUTILS (Nettoyage/Export/Visualiser) ne sont
        pas encore automatisées ici — chaîne arrêtée proprement, à continuer
        manuellement via leurs boutons Lancer dédiés (cf. ``_start_tool_worker``)."""
        self._plan_index = index
        if index >= len(self.current_plan):
            self._finish_pipeline_chain(True, tr("run_chain_done", "Chaîne terminée avec succès."))
            return

        step = self.current_plan[index]
        if step == "source":
            self.follow_step("source")
            self.run_state.set_status("source", StepStatus.DONE)
            self.rail.set_step_status("source", StepStatus.DONE)
            self._run_pipeline_step(index + 1)
            return

        if step == "reconstruction":
            worker = self._build_colmap_worker()
            if worker is not None:
                self._start_pipeline_worker("reconstruction", worker)
            return

        if step == "entrainement":
            worker = self._build_brush_worker()
            if worker is not None:
                self._start_pipeline_worker("entrainement", worker)
            return

        # Étape suivante (nettoyage/export/visualiser) : automatisation hors
        # scope de ce câblage — l'utilisateur continue manuellement.
        # No default text passed to tr() here: LanguageManager.tr() applies
        # .format(*args) internally whenever extra args are given AND the key
        # is found — passing both a default string and relying on our own
        # .format(step) afterward would let the default text itself get
        # consumed as the {0} substitution. The key is defined in all 9
        # locales (see assets/locales/*.json), so the plain-key fallback
        # (raw key name) below is a defensive no-op in practice.
        message = tr("run_chain_manual_continue").format(step)
        self._finish_pipeline_chain(True, message)

    def _build_colmap_worker(self):
        """Construit le ``ColmapWorker`` de l'étape Reconstruction depuis les
        chemins de Source (SourcePanel.get_state) et les réglages COLMAP de
        Reconstruction (ReconstructionPanel.get_params → ColmapParams)."""
        source_state = self.panels["source"].get_state()
        input_path = source_state["input_path"].strip()
        output_path = source_state["output_path"].strip()
        if not input_path or not output_path:
            self._fail_pipeline_step("reconstruction", tr("err_no_paths", "Chemins manquants."))
            return None
        project_name = source_state["project_name"].strip() or "Untitled"
        params = apply_source_blur_settings(
            self.panels["reconstruction"].get_params(), source_state
        )
        input_type = _detect_input_type(input_path)
        return ColmapWorker(
            params, input_path, output_path, input_type, source_state["fps"],
            project_name=project_name,
        )

    def _build_brush_worker(self):
        """Construit le ``BrushWorker`` de l'étape Entraînement : dataset =
        dossier du projet créé par COLMAP (output/projet), réglages Brush de
        EntrainementPanel.get_params → BrushParams.to_engine_params (dict plat
        attendu par BrushEngine, cf. app/core/brush_engine.py)."""
        source_state = self.panels["source"].get_state()
        output_path = source_state["output_path"].strip()
        if not output_path:
            self._fail_pipeline_step("entrainement", tr("err_no_paths", "Chemins manquants."))
            return None
        project_name = source_state["project_name"].strip() or "Untitled"
        project_dir = Path(output_path) / project_name
        panel = self.panels["entrainement"]
        params = panel.get_params().to_engine_params()
        ply_name = panel.ply_name_edit.text().strip()
        if ply_name:
            params["ply_name"] = ply_name
        return BrushWorker(
            project_dir, project_dir / "checkpoints", params, project_name=project_name,
        )

    def _start_pipeline_worker(self, step, worker):
        """Démarre le worker d'une étape pipeline : statuts rail/run_state posés
        au moment réel du démarrage (pas juste à la planification), logs relayés,
        topbar basculé en Annuler — même idiome que ``_start_tool_worker``."""
        self.run_state.set_status(step, StepStatus.RUNNING)
        self.rail.set_step_status(step, StepStatus.RUNNING)
        self.follow_step(step)
        self._active_worker = worker
        self._active_pipeline_step = step
        worker.log_signal.connect(self.logbar.append_log)
        if hasattr(worker, "status_signal"):
            worker.status_signal.connect(self.logbar.append_log)
        worker.finished_signal.connect(self._on_pipeline_step_finished)
        self.topbar.set_running(True)
        self.logbar.set_collapsed(False)
        worker.start()

    def _on_pipeline_step_finished(self, success, message):
        """Fin d'une étape pipeline : DONE + étape suivante si succès ; ERROR +
        arrêt de la chaîne (pas d'échec silencieux) sinon."""
        step = self._active_pipeline_step
        worker = self._active_worker
        self._active_worker = None
        self.logbar.append_log(message)
        if success:
            self.run_state.set_status(step, StepStatus.DONE)
            self.rail.set_step_status(step, StepStatus.DONE)
            self._run_pipeline_step(self._plan_index + 1)
            return
        stopped_by_user = bool(worker and getattr(worker, "stopped_by_user", False))
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self.topbar.set_running(False)
        self.logbar.set_collapsed(False)
        if not stopped_by_user:
            self.notify(tr("msg_error", "Erreur"), message)
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _fail_pipeline_step(self, step, message):
        """Échec de construction d'un worker (ex. chemins manquants) : même
        traitement qu'un échec en cours d'exécution, sans worker actif à nettoyer."""
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self.logbar.append_log(message)
        self.logbar.set_collapsed(False)
        self.topbar.set_running(False)
        self._active_worker = None
        self.notify(tr("msg_error", "Erreur"), message)
        QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _finish_pipeline_chain(self, success, message):
        """Fin (normale ou volontairement interrompue) de la chaîne pipeline."""
        self._active_worker = None
        self.topbar.set_running(False)
        self.logbar.append_log(message)
        if success:
            self.notify(tr("msg_success", "Succès"), message)

    # ── Dispatch du bouton unique topbar (Lancer/Annuler) ────────────────────────
    def on_topbar_launch(self):
        """Le topbar n'a qu'un bouton Lancer/Annuler : s'il y a un worker OUTILS
        actif (lancé depuis un bouton local), le clic l'annule ; sinon il lance
        la chaîne pipeline (cf. ``launch``)."""
        if self._active_worker is not None and self._active_worker.isRunning():
            self._cancel_active_worker()
            return
        self.launch()

    def _cancel_active_worker(self):
        worker = self._active_worker
        if worker and worker.isRunning():
            self.logbar.append_log(tr("topbar_cancel", "Annuler") + "…")
            if hasattr(worker, "stop"):
                worker.stop()
            else:
                worker.requestInterruption()

    # ── Lancement des modules OUTILS (bouton local, hors chaîne pipeline) ────────
    def _start_tool_worker(self, worker, finished_signal=None):
        """Démarre un worker OUTILS en tâche de fond : logs relayés vers la
        barre de logs, topbar basculé en Annuler, résultat affiché à la fin."""
        self._active_worker = worker
        worker.log_signal.connect(self.logbar.append_log)
        if hasattr(worker, "status_signal"):
            worker.status_signal.connect(self.logbar.append_log)
        signal = finished_signal if finished_signal is not None else worker.finished_signal
        signal.connect(self._on_tool_finished)
        self.topbar.set_running(True)
        self.logbar.set_collapsed(False)
        worker.start()

    def _on_tool_finished(self, success, message):
        worker = self._active_worker
        self._active_worker = None
        self.topbar.set_running(False)
        self.logbar.append_log(message)
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

    def _launch_cleaner(self):
        panel = self.panels["nettoyage"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        worker = CleanerWorker(input_path, output_path, panel.get_params())
        self._start_tool_worker(worker)

    def _launch_export(self):
        panel = self.panels["export"]
        input_paths = [p for p in panel.input_path.text().split("|") if p.strip()]
        output_dir = panel.output_path.text().strip()
        if not input_paths or not output_dir:
            QMessageBox.critical(self, tr("msg_error", "Erreur"), tr("err_no_paths", "Chemins manquants."))
            return
        worker = ExportWorker(
            input_paths, output_dir, panel.get_format(), options={"scale": panel.get_scale()}
        )
        self._start_tool_worker(worker)

    def _launch_extractor360(self):
        panel = self.panels["360"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        worker = Extractor360Worker(input_path, output_path, panel.get_params())
        self._start_tool_worker(worker)

    def _launch_fourdgs(self):
        panel = self.panels["4dgs"]
        params = panel.get_params()
        if not self._check_paths(params["output_path"]):
            return
        worker = FourDGSWorker(params["input_path"] or None, params["output_path"], params["fps"])
        self._start_tool_worker(worker)

    def _launch_fourdgs_colmap_only(self):
        """Réutilise le mode « COLMAP seul » de ``FourDGSWorker`` (videos_dir
        vide, cf. ancienne logique ``FourDGSTab.run_colmap_only``)."""
        panel = self.panels["4dgs"]
        params = panel.get_params()
        if not self._check_paths(params["output_path"]):
            return
        worker = FourDGSWorker(None, params["output_path"], params["fps"])
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
        else:
            if not self._check_paths(params["input_path"], params["output_path"]):
                return
            worker = SharpWorker(params["input_path"], params["output_path"], params)
        self._start_tool_worker(worker)

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
        if src_params["morton"]:
            st_params["--morton-order"] = True
        if src_params["harmonics"]:
            st_params["--filter-harmonics"] = "0"
        if src_params["decimate"] < 100:
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
        self.logbar.append_log(message)
        if success:
            self.notify(tr("msg_success", "Succès"), message)
        else:
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    # ── Configuration nommée (Charger / Sauvegarder) ────────────────────────────
    def collect_config(self) -> ChainConfig:
        """Agrège l'état des panneaux + drapeaux en une ChainConfig sérialisable."""
        def state_of(key):
            panel = self.panels.get(key)
            return panel.get_state() if panel and hasattr(panel, "get_state") else {}
        return ChainConfig(
            source=state_of("source"),
            colmap=state_of("reconstruction"),
            brush=state_of("entrainement"),
            cleaning=state_of("nettoyage"),
            export=state_of("export"),
            flags=self.run_state.to_dict(),
        )

    def apply_config(self, cfg: ChainConfig):
        """Applique une ChainConfig aux panneaux et aux drapeaux partagés."""
        mapping = {
            "source": cfg.source, "reconstruction": cfg.colmap,
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
                self.logbar.append_log(tr("config_saved", "Configuration sauvegardée : ") + name.strip())
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
                self.logbar.append_log(tr("config_loaded", "Configuration chargée : ") + name)
            except (ValueError, OSError) as e:
                QMessageBox.warning(self, tr("msg_error", "Erreur"), str(e))

    # ── Notifications ───────────────────────────────────────────────────────────
    def set_notifications_enabled(self, enabled: bool):
        self._notifications_enabled = bool(enabled)

    def notify(self, title, message):
        """Notifie l'utilisateur si les notifications sont activées."""
        if self._notifications_enabled:
            notifications.notify(title, message)

    # ── Réglages ──────────────────────────────────────────────────────────────
    def open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.saveRequested.connect(self.save_config_dialog)
            self._settings_window.loadRequested.connect(self.load_config_dialog)
            self._settings_window.notificationsToggled.connect(self.set_notifications_enabled)
            self._settings_window.resetRequested.connect(self.reset_factory)
        self._settings_window.show()
        self._settings_window.raise_()

    def restart_application(self):
        """Relance l'application (cf. ``AppLifecycle.restart``)."""
        AppLifecycle.restart()

    def reset_factory(self, deep=False):
        """Supprime les venvs (et engines/config.json si ``deep``) puis relance
        l'installation/application. Déjà confirmé par ``ResetDialog`` côté
        ``SettingsWindow`` avant l'émission du signal."""
        AppLifecycle.reset_factory(deep)

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.btn_relaunch.setText(tr("settings_relaunch", "Relancer"))
        self.btn_quit.setText(tr("settings_quit", "Quitter"))

    # ── Fermeture ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        """Point de vigilance Lot 4 (PROMPT_CLAUDE_CODE_REFONTE_UI.md) : annule
        un worker OUTILS actif et stoppe SuperSplatEngine pour ne pas laisser de
        serveur local orphelin quand la fenêtre se ferme."""
        self.session_manager.save(immediate=True)
        self._cancel_active_worker()
        for key in ("visualiser", "supersplat"):
            engine = getattr(self.panels.get(key), "engine", None)
            if engine is not None:
                engine.stop_all()
        event.accept()

```

## app/gui/topbar.py (114 lignes)
```python
"""Top bar de la fenêtre Studio.

Nom de projet éditable (miroir du champ Source), pastille de statut moteurs,
dropdown mode pipeline (Gsplat / Sharp / 4DGS), bouton Lancer unique, icône
réglages généraux (ouvre ``SettingsWindow``).

Lot 2 : structure et signaux, aucun câblage moteur.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.core.i18n import add_language_observer, tr

# Modes de pipeline exposés dans le dropdown (valeur interne, clé i18n, défaut).
PIPELINE_MODES = (
    ("gsplat", "mode_gsplat", "Gsplat"),
    ("sharp", "mode_sharp", "Sharp"),
    ("4dgs", "mode_4dgs", "4DGS"),
)


class TopBar(QWidget):
    """Barre supérieure. Émet des signaux de haut niveau (aucune logique métier)."""

    projectNameChanged = Signal(str)
    modeChanged = Signal(str)
    launchRequested = Signal()
    settingsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_project = QLabel(tr("topbar_project", "Projet :"))
        layout.addWidget(self.lbl_project)

        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        self.input_project_name.textChanged.connect(self.projectNameChanged.emit)
        layout.addWidget(self.input_project_name)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        self.lbl_mode = QLabel(tr("topbar_mode", "Mode :"))
        layout.addWidget(self.lbl_mode)
        self.combo_mode = QComboBox()
        for value, key, default in PIPELINE_MODES:
            self.combo_mode.addItem(tr(key, default), value)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.combo_mode)

        self.btn_launch = QPushButton(tr("topbar_launch", "Lancer"))
        self.btn_launch.clicked.connect(self.launchRequested.emit)
        layout.addWidget(self.btn_launch)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        self.btn_settings.clicked.connect(self.settingsRequested.emit)
        layout.addWidget(self.btn_settings)

    def _on_mode_changed(self, index):
        value = self.combo_mode.itemData(index)
        if value:
            self.modeChanged.emit(value)

    def set_project_name(self, name: str) -> None:
        """Met à jour l'affichage du nom de projet sans re-déclencher
        ``projectNameChanged`` (mise à jour programmatique, p. ex. depuis le
        champ miroir du panneau Source)."""
        if self.input_project_name.text() == name:
            return
        self.input_project_name.blockSignals(True)
        self.input_project_name.setText(name)
        self.input_project_name.blockSignals(False)

    def set_running(self, running: bool):
        """Bascule le bouton Lancer ↔ Annuler selon l'état du pipeline."""
        if running:
            self.btn_launch.setText(tr("topbar_cancel", "Annuler"))
            self.btn_launch.setStyleSheet("color: #f7768e;")
        else:
            self.btn_launch.setText(tr("topbar_launch", "Lancer"))
            self.btn_launch.setStyleSheet("")

    def current_mode(self) -> str:
        return self.combo_mode.itemData(self.combo_mode.currentIndex())

    def set_status_text(self, text: str):
        """Met à jour la pastille « X moteurs prêts »."""
        self.lbl_status.setText(text)

    def retranslate_ui(self):
        self.lbl_project.setText(tr("topbar_project", "Projet :"))
        self.lbl_mode.setText(tr("topbar_mode", "Mode :"))
        self.btn_launch.setText(tr("topbar_launch", "Lancer"))
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        for i, (_value, key, default) in enumerate(PIPELINE_MODES):
            self.combo_mode.setItemText(i, tr(key, default))

```

## app/gui/rail.py (190 lignes)
```python
"""Rail gauche de la fenêtre Studio : sections PIPELINE et OUTILS.

- PIPELINE : 6 étapes (Source → Reconstruction → Entraînement → Nettoyage →
  Export → Visualiser), chacune avec icône + libellé toujours affichés ensemble,
  et un marqueur d'état (coche / activité / erreur) piloté par ``StepStatus``.
- OUTILS : 7 modules indépendants, section repliable **repliée par défaut**.

L'ensemble est dans une ``QScrollArea`` (13 items cumulés → risque de dépassement
vertical sur petit écran, déjà géré ainsi ailleurs dans l'app).

Lot 2 : structure et sélection uniquement, aucun câblage moteur.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, StepStatus
from app.gui.studio_nav import CollapseState

# Modules OUTILS, dans l'ordre du rail.
TOOL_KEYS = ("brush", "sharp", "supersplat", "upscale", "splattransform", "4dgs", "360")

# Icônes minimalistes : glyphes géométriques monochromes (pas d'emoji couleur),
# qui héritent de la couleur du texte. « icône + libellé toujours ensemble ».
_STEP_ICONS = {
    "source": "↧", "reconstruction": "▦", "entrainement": "◆",
    "nettoyage": "◈", "export": "↥", "visualiser": "◉",
}
_TOOL_ICONS = {
    "brush": "◐", "sharp": "◇", "supersplat": "⊙", "upscale": "⤢",
    "splattransform": "⇄", "4dgs": "▷", "360": "◍",
}
_STEP_LABEL_KEYS = {
    "source": ("rail_step_source", "Source"),
    "reconstruction": ("rail_step_reconstruction", "Reconstruction"),
    "entrainement": ("rail_step_entrainement", "Entraînement"),
    "nettoyage": ("rail_step_nettoyage", "Nettoyage"),
    "export": ("rail_step_export", "Export"),
    "visualiser": ("rail_step_visualiser", "Visualiser"),
}
_TOOL_LABEL_KEYS = {
    "brush": ("rail_tool_brush", "Brush"),
    "sharp": ("rail_tool_sharp", "ML Sharp"),
    "supersplat": ("rail_tool_supersplat", "SuperSplat"),
    "upscale": ("rail_tool_upscale", "Upscale"),
    "splattransform": ("rail_tool_splattransform", "SplatTransform"),
    "4dgs": ("rail_tool_4dgs", "4DGS"),
    "360": ("rail_tool_360", "360 Extractor"),
}

# Style commun des items : alignés à gauche, compacts, minimalistes. La sélection
# et le survol se traduisent par un léger fond (pas de bordure).
_ITEM_STYLE = (
    "QPushButton { text-align: left; padding: 3px 8px; border: none; background: transparent; }"
    "QPushButton:checked { background: rgba(122,162,247,0.20); border-radius: 4px; }"
    "QPushButton:hover { background: rgba(255,255,255,0.06); border-radius: 4px; }"
)

# Marqueur d'état préfixé au libellé d'une étape PIPELINE.
_STATUS_MARKER = {
    StepStatus.IDLE: "",
    StepStatus.RUNNING: "⏳ ",
    StepStatus.DONE: "✓ ",
    StepStatus.ERROR: "⛔ ",
}


class Rail(QWidget):
    """Colonne de navigation gauche. Émet ``itemSelected(key)`` à chaque clic."""

    itemSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}          # key -> QPushButton
        self._status = {}           # step key -> StepStatus
        self._outils = CollapseState(collapsed=True)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)

        # ── Section PIPELINE ──────────────────────────────────────────────────
        self.lbl_pipeline = QLabel(tr("rail_section_pipeline", "PIPELINE"))
        self._layout.addWidget(self.lbl_pipeline)
        # Un seul groupe exclusif pour toute sélection (13 items).
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for key in PIPELINE_STEPS:
            self._status[key] = StepStatus.IDLE
            self._add_item(key, self._layout)

        # ── Section OUTILS (repliable, repliée par défaut) ────────────────────
        self.btn_outils_header = QPushButton()
        self.btn_outils_header.setCheckable(True)
        self.btn_outils_header.setChecked(not self._outils.collapsed)
        self.btn_outils_header.setStyleSheet(_ITEM_STYLE)
        self.btn_outils_header.clicked.connect(self._on_outils_header)
        self._layout.addWidget(self.btn_outils_header)

        self.outils_container = QWidget()
        outils_layout = QVBoxLayout(self.outils_container)
        outils_layout.setContentsMargins(0, 0, 0, 0)
        outils_layout.setSpacing(2)
        for key in TOOL_KEYS:
            self._add_item(key, outils_layout)
        self.outils_container.setVisible(not self._outils.collapsed)
        self._layout.addWidget(self.outils_container)

        self._layout.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)
        self.retranslate_ui()

    def _add_item(self, key, layout):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setStyleSheet(_ITEM_STYLE)
        btn.clicked.connect(lambda _checked=False, k=key: self._on_item_clicked(k))
        self._group.addButton(btn)
        self._buttons[key] = btn
        layout.addWidget(btn)

    # ── Sélection ─────────────────────────────────────────────────────────────
    def _on_item_clicked(self, key):
        self.itemSelected.emit(key)

    def select(self, key):
        """Sélectionne programmatiquement un item (auto-follow pendant un run)."""
        btn = self._buttons.get(key)
        if btn is not None:
            btn.setChecked(True)

    # ── Repli/dépli OUTILS ─────────────────────────────────────────────────────
    def _on_outils_header(self):
        self.set_outils_collapsed(not self.btn_outils_header.isChecked())

    def set_outils_collapsed(self, collapsed: bool):
        self._outils.collapsed = bool(collapsed)
        self.outils_container.setVisible(not self._outils.collapsed)
        self.btn_outils_header.setChecked(not self._outils.collapsed)
        self._update_outils_header_text()

    def is_outils_collapsed(self) -> bool:
        return self._outils.collapsed

    # ── État des étapes ────────────────────────────────────────────────────────
    def set_step_status(self, step: str, status: StepStatus):
        if step not in self._status:
            raise KeyError(f"Étape inconnue: {step}")
        self._status[step] = StepStatus(status)
        self._refresh_step_label(step)

    def _refresh_step_label(self, step):
        key_default = _STEP_LABEL_KEYS[step]
        label = tr(*key_default)
        marker = _STATUS_MARKER.get(self._status[step], "")
        self._buttons[step].setText(f"{marker}{_STEP_ICONS[step]}  {label}")

    def _update_outils_header_text(self):
        arrow = "▾" if not self._outils.collapsed else "▸"
        self.btn_outils_header.setText(f"{arrow} " + tr("rail_section_outils", "OUTILS"))

    # ── i18n ───────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.lbl_pipeline.setText(tr("rail_section_pipeline", "PIPELINE"))
        for step in PIPELINE_STEPS:
            self._refresh_step_label(step)
        for key in TOOL_KEYS:
            label = tr(*_TOOL_LABEL_KEYS[key])
            self._buttons[key].setText(f"{_TOOL_ICONS[key]}  {label}")
        self._update_outils_header_text()

```

## app/gui/logbar.py (73 lignes)
```python
"""Barre de logs repliable en bas de la fenêtre Studio.

Repliée par défaut, persistante à travers les écrans. Réutilise **littéralement**
``LogsTab`` (Effacer/Copier/Sauvegarder/Rechercher + auto-scroll lock déjà en
place) plutôt que de réimplémenter ce comportement : le contenu de la barre EST
un ``LogsTab``, encapsulé sous un en-tête repliable.
"""

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from app.core.i18n import add_language_observer, tr
from app.gui.studio_nav import CollapseState
from app.gui.tabs.logs_tab import LogsTab


class LogBar(QWidget):
    """Conteneur repliable autour d'un ``LogsTab``. Replié par défaut."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = CollapseState(collapsed=True)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_header = QPushButton()
        self.btn_header.setCheckable(True)
        self.btn_header.setChecked(not self._state.collapsed)
        self.btn_header.clicked.connect(self._on_header)
        layout.addWidget(self.btn_header)

        self.logs = LogsTab()
        self.logs.setVisible(not self._state.collapsed)
        layout.addWidget(self.logs)

        self._update_header_text()

    def _on_header(self):
        self.set_collapsed(not self.btn_header.isChecked())

    def set_collapsed(self, collapsed: bool):
        self._state.collapsed = bool(collapsed)
        self.logs.setVisible(not self._state.collapsed)
        self.btn_header.setChecked(not self._state.collapsed)
        self._update_header_text()

    def is_collapsed(self) -> bool:
        return self._state.collapsed

    # ── Délégation vers le LogsTab encapsulé ────────────────────────────────────
    def append_log(self, message):
        self.logs.append_log(message)

    def clear_log(self):
        self.logs.clear_log()

    def expand_and_search(self, text: str = ""):
        """Déplie la barre (utilisé plus tard au clic sur l'icône d'erreur du
        rail). Le scroll jusqu'à l'entrée concernée sera câblé au Lot 6."""
        self.set_collapsed(False)
        if text:
            self.logs.search_input.setText(text)
            self.logs._find_next()

    def _update_header_text(self):
        arrow = "▾" if not self._state.collapsed else "▸"
        self.btn_header.setText(f"{arrow} " + tr("logbar_title", "Logs"))

    def retranslate_ui(self):
        self._update_header_text()

```

## app/gui/panels/source_panel.py (272 lignes)
```python
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
from app.gui.run_state_binding import bind_flag_checkbox, bind_text_field
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
        # Miroir de la top bar : source de vérité unique dans run_state (cf.
        # bind_text_field, même idiome que les drapeaux de chaînage).
        self._bindings.append(bind_text_field(self.input_project_name, self.run_state, "project_name"))
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

        # ── Options avancées ─── toujours visibles (plus de repli/dépli)
        self.lbl_advanced = QLabel()
        self.lbl_advanced.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_advanced)

        self.advanced_group = QWidget()
        ag = QVBoxLayout(self.advanced_group)
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

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Handlers ────────────────────────────────────────────────────────────────
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
            "filter_blur": self.chk_filter_blur.isChecked(),
            "blur_strength": self.combo_blur.currentData(),
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
        self.lbl_advanced.setText(tr("toggle_advanced", "Avancé"))
        self.chk_undistort.setText(tr("source_undistort", "Générer images non-distordues"))
        self.chk_filter_blur.setText(tr("source_filter_blur", "Supprimer les images floues"))
        self.lbl_blur.setText(tr("source_blur_strength", "Intensité du filtre flou"))

```

## app/gui/panels/reconstruction_panel.py (390 lignes)
```python
"""Panneau Reconstruction (étape PIPELINE) — équivalent de ParamsTab.

Reprend les accordéons Feature Extraction / Matching / Mapper de ``ParamsTab``
dans la barre de droite, et migre ici la logique « Reprise de COLMAP » (avant
dans ConfigTab), étendue au cas « dossier externe → nouveau projet à la volée »
(cf. reconstruction_logic.classify_resume_folder).

``undistort_images`` est exécuté réellement ici (section Mapper) et bindé sur le
``RunState`` partagé — dupliqué en raccourci dans Source, même source de vérité.
Les toggles Entraînement/Visualiser après sont aussi bindés sur run_state.

Lot 3b : UI + params + détection de reprise. Le dispatch réel (lancer COLMAP,
créer le projet à la volée) est câblé au sous-lot 3c.
"""

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.core.params import (
    COMPATIBLE_MATCHING,
    FEATURE_TO_DEFAULT_MATCHING,
    FEATURE_TYPES,
    MATCHING_TYPES,
    ColmapParams,
)
from app.core.system import get_optimal_threads, is_apple_silicon
from app.gui.panels.reconstruction_logic import (
    RESUME_COLMAP_PROJECT,
    RESUME_EXTERNAL_IMAGES,
    RESUME_INVALID,
    classify_resume_folder,
)
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.dialog_utils import get_existing_directory

_CAMERA_MODELS = ['SIMPLE_PINHOLE', 'PINHOLE', 'SIMPLE_RADIAL', 'RADIAL', 'OPENCV', 'OPENCV_FISHEYE']
_MATCHER_TYPES = ['exhaustive', 'sequential', 'vocab_tree']


class ReconstructionPanel:
    """Panneau plain exposant ``center`` et ``right`` (widgets Qt)."""

    def __init__(self, run_state):
        self.run_state = run_state
        self._bindings = []
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Centre ──────────────────────────────────────────────────────────────────
    def _build_center(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Bannière Apple Silicon (reprise telle quelle de ParamsTab)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setVisible(is_apple_silicon())
        layout.addWidget(self.info_label)

        # Reprise de COLMAP (dossier existant OU dossier externe → nouveau projet)
        self.lbl_resume = QLabel()
        self.lbl_resume.setWordWrap(True)
        layout.addWidget(self.lbl_resume)
        resume_row = QHBoxLayout()
        self.resume_path = QLineEdit()
        self.resume_path.textChanged.connect(self._on_resume_path_changed)
        resume_row.addWidget(self.resume_path)
        self.btn_browse_resume = QPushButton("📁")
        self.btn_browse_resume.clicked.connect(self._browse_resume)
        resume_row.addWidget(self.btn_browse_resume)
        layout.addLayout(resume_row)
        self.lbl_resume_status = QLabel()
        self.lbl_resume_status.setWordWrap(True)
        layout.addWidget(self.lbl_resume_status)

        # Nom projet / dossier de sortie (si pas déjà connus du contexte)
        self.lbl_project = QLabel()
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        layout.addWidget(self.lbl_project)
        layout.addWidget(self.input_project_name)

        self.lbl_output = QLabel()
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("📁")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addWidget(self.lbl_output)
        layout.addLayout(out_row)

        # Chaînage (mêmes drapeaux que Source, source de vérité unique)
        self.chk_entrainement = QCheckBox()
        self._bind(self.chk_entrainement, "entrainement_apres")
        layout.addWidget(self.chk_entrainement)
        self.chk_visualiser = QCheckBox()
        self._bind(self.chk_visualiser, "visualiser_apres")
        layout.addWidget(self.chk_visualiser)

        layout.addStretch(1)
        return w

    # ── Barre de droite : accordéons ────────────────────────────────────────────
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

        # Feature Extraction
        self.extract_group = QGroupBox()
        ex = QFormLayout(self.extract_group)
        ex.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.camera_model_combo = QComboBox()
        self.camera_model_combo.addItems(_CAMERA_MODELS)
        self.camera_model_combo.setCurrentText('SIMPLE_RADIAL')
        self.lbl_camera_model = QLabel()
        ex.addRow(self.lbl_camera_model, self.camera_model_combo)
        self.single_camera_check = QCheckBox()
        self.single_camera_check.setChecked(True)
        self.lbl_single_cam = QLabel()
        ex.addRow(self.lbl_single_cam, self.single_camera_check)
        self.max_image_spin = QSpinBox()
        self.max_image_spin.setRange(640, 8192)
        self.max_image_spin.setValue(3200)
        self.lbl_max_img = QLabel()
        ex.addRow(self.lbl_max_img, self.max_image_spin)
        self.max_features_spin = QSpinBox()
        self.max_features_spin.setRange(1024, 32768)
        self.max_features_spin.setValue(8192)
        self.lbl_max_feat = QLabel()
        ex.addRow(self.lbl_max_feat, self.max_features_spin)
        self.estimate_affine_check = QCheckBox()
        self.estimate_affine_check.setChecked(True)
        self.lbl_affine = QLabel()
        ex.addRow(self.lbl_affine, self.estimate_affine_check)
        self.domain_pooling_check = QCheckBox()
        self.domain_pooling_check.setChecked(True)
        self.lbl_domain = QLabel()
        ex.addRow(self.lbl_domain, self.domain_pooling_check)
        self.feature_type_combo = QComboBox()
        self.feature_type_combo.addItems(FEATURE_TYPES)
        self.feature_type_combo.setCurrentText('SIFT')
        self.feature_type_combo.currentTextChanged.connect(self._on_feature_type_changed)
        self.lbl_feature_type = QLabel()
        ex.addRow(self.lbl_feature_type, self.feature_type_combo)
        layout.addWidget(self.extract_group)

        # Matching
        self.match_group = QGroupBox()
        mt = QFormLayout(self.match_group)
        mt.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.matcher_type_combo = QComboBox()
        self.matcher_type_combo.addItems(_MATCHER_TYPES)
        self.matcher_type_combo.setCurrentText('exhaustive')
        self.matcher_type_combo.currentTextChanged.connect(self._update_sequential_enabled)
        self.lbl_match_type = QLabel()
        mt.addRow(self.lbl_match_type, self.matcher_type_combo)
        self.sequential_overlap_spin = QSpinBox()
        self.sequential_overlap_spin.setRange(1, 100)
        self.sequential_overlap_spin.setValue(30)
        self.lbl_sequential_overlap = QLabel()
        mt.addRow(self.lbl_sequential_overlap, self.sequential_overlap_spin)
        self.matching_algo_combo = QComboBox()
        self.matching_algo_combo.addItems(MATCHING_TYPES)
        self.matching_algo_combo.setCurrentText('SIFT_BRUTEFORCE')
        self.lbl_matching_algo = QLabel()
        mt.addRow(self.lbl_matching_algo, self.matching_algo_combo)
        self.max_ratio_spin = QDoubleSpinBox()
        self.max_ratio_spin.setRange(0.1, 1.0)
        self.max_ratio_spin.setSingleStep(0.1)
        self.max_ratio_spin.setValue(0.8)
        self.lbl_max_ratio = QLabel()
        mt.addRow(self.lbl_max_ratio, self.max_ratio_spin)
        self.max_distance_spin = QDoubleSpinBox()
        self.max_distance_spin.setRange(0.1, 1.0)
        self.max_distance_spin.setSingleStep(0.1)
        self.max_distance_spin.setValue(0.7)
        self.lbl_max_dist = QLabel()
        mt.addRow(self.lbl_max_dist, self.max_distance_spin)
        self.cross_check_check = QCheckBox()
        self.cross_check_check.setChecked(True)
        self.lbl_cross = QLabel()
        mt.addRow(self.lbl_cross, self.cross_check_check)
        self.guided_match_check = QCheckBox()
        self.lbl_guided = QLabel()
        mt.addRow(self.lbl_guided, self.guided_match_check)
        self.min_matches_spin = QSpinBox()
        self.min_matches_spin.setRange(5, 100)
        self.min_matches_spin.setValue(15)
        self.lbl_min_match = QLabel()
        mt.addRow(self.lbl_min_match, self.min_matches_spin)
        layout.addWidget(self.match_group)

        # Mapper
        self.mapper_group = QGroupBox()
        mp = QFormLayout(self.mapper_group)
        mp.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.refine_focal_check = QCheckBox()
        self.refine_focal_check.setChecked(True)
        self.lbl_focal = QLabel()
        mp.addRow(self.lbl_focal, self.refine_focal_check)
        self.refine_principal_check = QCheckBox()
        self.lbl_principal = QLabel()
        mp.addRow(self.lbl_principal, self.refine_principal_check)
        self.refine_extra_check = QCheckBox()
        self.refine_extra_check.setChecked(True)
        self.lbl_extra = QLabel()
        mp.addRow(self.lbl_extra, self.refine_extra_check)
        self.view_graph_calibration_check = QCheckBox()
        self.view_graph_calibration_check.setChecked(True)
        self.lbl_view_graph = QLabel()
        mp.addRow(self.lbl_view_graph, self.view_graph_calibration_check)
        self.ignore_watermarks_check = QCheckBox()
        self.ignore_watermarks_check.setChecked(True)
        self.lbl_ignore_watermarks = QLabel()
        mp.addRow(self.lbl_ignore_watermarks, self.ignore_watermarks_check)
        self.thermal_throttling_check = QCheckBox()
        self.lbl_thermal = QLabel()
        mp.addRow(self.lbl_thermal, self.thermal_throttling_check)
        # undistort exécuté ici, bindé run_state (dupliqué avec Source)
        self.undistort_check = QCheckBox()
        self._bind(self.undistort_check, "undistort_images")
        self.lbl_undistort = QLabel()
        mp.addRow(self.lbl_undistort, self.undistort_check)
        layout.addWidget(self.mapper_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._update_sequential_enabled()
        return w

    def _bind(self, checkbox, flag):
        self._bindings.append(bind_flag_checkbox(checkbox, self.run_state, flag))

    # ── Comportements ────────────────────────────────────────────────────────────
    def _on_feature_type_changed(self, feat_type):
        compatible = COMPATIBLE_MATCHING.get(feat_type, ['SIFT_BRUTEFORCE'])
        self.matching_algo_combo.clear()
        self.matching_algo_combo.addItems(compatible)
        if self.matching_algo_combo.currentText() not in compatible:
            self.matching_algo_combo.setCurrentText(
                FEATURE_TO_DEFAULT_MATCHING.get(feat_type, 'SIFT_BRUTEFORCE'))

    def _update_sequential_enabled(self, *_):
        self.sequential_overlap_spin.setEnabled(self.matcher_type_combo.currentText() == 'sequential')

    def _on_resume_path_changed(self, text):
        kind = classify_resume_folder(text) if text.strip() else RESUME_INVALID
        self.lbl_resume_status.setText(self._resume_status_text(kind))

    def _resume_status_text(self, kind):
        if kind == RESUME_COLMAP_PROJECT:
            return tr("recon_resume_existing", "Projet COLMAP existant — reprise")
        if kind == RESUME_EXTERNAL_IMAGES:
            return tr("recon_resume_external", "Dossier d'images externe — nouveau projet à la volée")
        return ""

    def _browse_resume(self):
        path = get_existing_directory(self.center, tr("recon_resume", "Reprise de COLMAP"))
        if path:
            self.resume_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    # ── Params ────────────────────────────────────────────────────────────────────
    def get_params(self):
        """Construit ColmapParams depuis les widgets ; undistort depuis run_state."""
        return ColmapParams(
            camera_model=self.camera_model_combo.currentText(),
            single_camera=self.single_camera_check.isChecked(),
            max_image_size=self.max_image_spin.value(),
            max_num_features=self.max_features_spin.value(),
            feature_type=self.feature_type_combo.currentText(),
            matching_type=self.matching_algo_combo.currentText(),
            estimate_affine_shape=self.estimate_affine_check.isChecked(),
            domain_size_pooling=self.domain_pooling_check.isChecked(),
            max_ratio=self.max_ratio_spin.value(),
            max_distance=self.max_distance_spin.value(),
            cross_check=self.cross_check_check.isChecked(),
            guided_matching=self.guided_match_check.isChecked(),
            ba_refine_focal_length=self.refine_focal_check.isChecked(),
            ba_refine_principal_point=self.refine_principal_check.isChecked(),
            ba_refine_extra_params=self.refine_extra_check.isChecked(),
            min_num_matches=self.min_matches_spin.value(),
            matcher_type=self.matcher_type_combo.currentText(),
            sequential_overlap=self.sequential_overlap_spin.value(),
            undistort_images=self.run_state.undistort_images,
            use_view_graph_calibration=self.view_graph_calibration_check.isChecked(),
            ignore_watermarks=self.ignore_watermarks_check.isChecked(),
            thermal_throttling=self.thermal_throttling_check.isChecked(),
        )

    def set_params(self, params):
        self.camera_model_combo.setCurrentText(params.camera_model)
        self.single_camera_check.setChecked(params.single_camera)
        self.max_image_spin.setValue(params.max_image_size)
        self.max_features_spin.setValue(params.max_num_features)
        feat_type = getattr(params, 'feature_type', 'SIFT')
        self.feature_type_combo.setCurrentText(feat_type)
        self._on_feature_type_changed(feat_type)
        match_type = getattr(params, 'matching_type', 'SIFT_BRUTEFORCE')
        if match_type in COMPATIBLE_MATCHING.get(feat_type, []):
            self.matching_algo_combo.setCurrentText(match_type)
        self.estimate_affine_check.setChecked(params.estimate_affine_shape)
        self.domain_pooling_check.setChecked(params.domain_size_pooling)
        self.max_ratio_spin.setValue(params.max_ratio)
        self.max_distance_spin.setValue(params.max_distance)
        self.cross_check_check.setChecked(params.cross_check)
        self.guided_match_check.setChecked(getattr(params, 'guided_matching', False))
        self.sequential_overlap_spin.setValue(getattr(params, 'sequential_overlap', 30))
        self.refine_focal_check.setChecked(params.ba_refine_focal_length)
        self.refine_principal_check.setChecked(params.ba_refine_principal_point)
        self.refine_extra_check.setChecked(params.ba_refine_extra_params)
        self.min_matches_spin.setValue(params.min_num_matches)
        self.matcher_type_combo.setCurrentText(params.matcher_type)
        self.view_graph_calibration_check.setChecked(params.use_view_graph_calibration)
        self.ignore_watermarks_check.setChecked(params.ignore_watermarks)
        self.thermal_throttling_check.setChecked(getattr(params, 'thermal_throttling', False))
        self.run_state.undistort_images = getattr(params, 'undistort_images', False)
        self._update_sequential_enabled()

    def get_state(self):
        return self.get_params().to_dict()

    def set_state(self, state):
        if state:
            self.set_params(ColmapParams.from_dict(state))

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        self.info_label.setText(tr("info_cpu", get_optimal_threads()))
        self.lbl_resume.setText(tr("recon_resume", "Reprise de COLMAP (dossier projet ou images)"))
        self.lbl_project.setText(tr("label_project_name", "Nom du projet"))
        self.lbl_output.setText(tr("source_output", "Dossier de sortie"))
        self.chk_entrainement.setText(tr("chain_train_after", "Lancer Brush"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        self.extract_group.setTitle(tr("group_extract", "Extraction de caractéristiques"))
        self.match_group.setTitle(tr("group_match", "Correspondances"))
        self.mapper_group.setTitle(tr("group_mapper", "Mapper"))
        self.lbl_camera_model.setText(tr("lbl_camera_model", "Modèle caméra"))
        self.lbl_single_cam.setText(tr("check_single_cam", "Caméra unique"))
        self.lbl_max_img.setText(tr("lbl_max_img", "Taille image max"))
        self.lbl_max_feat.setText(tr("lbl_max_feat", "Caractéristiques max"))
        self.lbl_affine.setText(tr("check_affine", "Estimer forme affine"))
        self.lbl_domain.setText(tr("check_domain", "Domain size pooling"))
        self.lbl_feature_type.setText(tr("lbl_feature_type", "Type de caractéristique"))
        self.lbl_match_type.setText(tr("lbl_match_type", "Type de matcher"))
        self.lbl_sequential_overlap.setText(tr("lbl_sequential_overlap", "Chevauchement séquentiel"))
        self.lbl_matching_algo.setText(tr("lbl_matching_algo", "Algorithme de matching"))
        self.lbl_max_ratio.setText(tr("lbl_max_ratio", "Ratio max"))
        self.lbl_max_dist.setText(tr("lbl_max_dist", "Distance max"))
        self.lbl_cross.setText(tr("check_cross", "Vérification croisée"))
        self.lbl_guided.setText(tr("check_guided", "Guided matching"))
        self.lbl_min_match.setText(tr("lbl_min_match", "Correspondances min"))
        self.lbl_focal.setText(tr("check_focal", "Affiner focale"))
        self.lbl_principal.setText(tr("check_principal", "Affiner point principal"))
        self.lbl_extra.setText(tr("check_extra", "Affiner params extra"))
        self.lbl_view_graph.setText(tr("check_view_graph_calibration", "Calibration view-graph"))
        self.lbl_ignore_watermarks.setText(tr("check_ignore_watermarks", "Ignorer filigranes"))
        self.lbl_thermal.setText(tr("check_thermal_throttling", "Limitation thermique"))
        self.lbl_undistort.setText(tr("source_undistort", "Générer images non-distordues"))
        self._on_resume_path_changed(self.resume_path.text())

```

## app/gui/panels/entrainement_panel.py (395 lignes)
```python
"""Panneau Entraînement (étape PIPELINE) — équivalent de l'onglet Brush.

Barre de droite : Preset (dropdown, presets intégrés + personnalisés via
``merge_presets``), bouton « Enregistrer preset », champs essentiels (Steps,
SH Degree, Max Splats, Device), toggle Avancé (Résolution max, Args
supplémentaires, Viewer, Mode de build — auto-détecté depuis le binaire
installé, cf. ``get_brush_build_mode``), sections repliables Densification et
Checkpoints, mode Nouveau/Refine. S'appuie sur ``BrushParams`` (Lot 1) :
``get_params()`` retourne un BrushParams, ``to_engine_params()`` produit la
chaîne moteur (tokens inchangés, allowlist côté BrushEngine).

Centre : mode Manuel/Indépendant (dataset/export/PLY), suivi d'exécution
(placeholder), toggle Visualiser après (bindé run_state).

Lot 3c : UI + BrushParams + presets. Le lancement réel (BrushWorker) passe par
le dispatch orchestré du StudioWindow.
"""

from PySide6.QtCore import Qt
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
from app.core.system import get_brush_build_mode
from app.gui.run_state_binding import bind_flag_checkbox
from app.gui.widgets.dialog_utils import get_existing_directory

# (build_mode value, i18n key, default label) — moved here from SettingsWindow:
# this is a Brush-specific setting, not a global one. Initial value is
# auto-detected from the installed binary (cf. get_brush_build_mode); the
# dropdown lets an informed user override it if needed (e.g. after manually
# swapping binaries).
_BUILD_MODES = (("release", "settings_build_release", "Binaire release"),
                ("source", "settings_build_source", "Compilé source"))


class EntrainementPanel:
    """Panneau plain exposant ``center`` et ``right`` (widgets Qt)."""

    def __init__(self, run_state, standalone=False):
        self.run_state = run_state
        self.standalone = standalone
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

        # Local Launch button: standalone use only (OUTILS "Brush" module). The
        # PIPELINE Training step is driven by the top bar's single Launch/Cancel
        # button instead (cf. StudioWindow._run_pipeline_step).
        if self.standalone:
            self.btn_run = QPushButton()
            self.btn_run.setStyleSheet("font-weight: bold;")
            layout.addWidget(self.btn_run)

        layout.addStretch(1)
        return w

    # ── Barre de droite (preset → essentiel → avancé) ───────────────────────────
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
        essential.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
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
        ag.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.max_resolution_spin = QSpinBox()
        self.max_resolution_spin.setRange(0, 8192)
        self.lbl_res = QLabel()
        ag.addRow(self.lbl_res, self.max_resolution_spin)
        self.custom_args_edit = QLineEdit()
        self.lbl_args = QLabel()
        ag.addRow(self.lbl_args, self.custom_args_edit)
        self.check_viewer = QCheckBox()
        # Checked by default: without it the Brush viewer window never opens
        # during training, and the option is easy to miss (tucked under
        # "Advanced").
        self.check_viewer.setChecked(True)
        ag.addRow(self.check_viewer)
        # Build mode: which CLI flag spelling BrushEngine must use depends on
        # whether the installed binary is a tagged release or a source build
        # (cf. build_command in brush_engine.py) — auto-detected here from the
        # installed binary so training works out of the box; only override if
        # you know you've manually swapped binaries.
        self.combo_build_mode = QComboBox()
        for value, key, default in _BUILD_MODES:
            self.combo_build_mode.addItem(tr(key, default), value)
        idx = self.combo_build_mode.findData(get_brush_build_mode())
        if idx >= 0:
            self.combo_build_mode.setCurrentIndex(idx)
        self.lbl_build_mode = QLabel()
        ag.addRow(self.lbl_build_mode, self.combo_build_mode)
        self.advanced_group.setVisible(False)
        layout.addWidget(self.advanced_group)

        # Densification (repliable)
        self.densif_group = QGroupBox()
        self.densif_group.setCheckable(True)
        self.densif_group.setChecked(False)
        dg = QFormLayout(self.densif_group)
        dg.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
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
        cg.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs, bug combo_mode)
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
            build_mode=self.combo_build_mode.currentData(),
            refine_mode=self.combo_mode.currentData() == "refine",
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
        if params.build_mode:
            idx = self.combo_build_mode.findData(params.build_mode)
            if idx >= 0:
                self.combo_build_mode.setCurrentIndex(idx)
        if params.refine_mode:
            self.combo_mode.setCurrentIndex(1)
        else:
            self.combo_mode.setCurrentIndex(0)

    def get_state(self):
        return self.get_params().to_dict()

    def set_state(self, state):
        if state:
            self.set_params(BrushParams.from_dict(state))

    # ── i18n ────────────────────────────────────────────────────────────────────
    def retranslate_ui(self):
        # Item 0 ("Défaut", data=None) only — preset names (index 1+) are
        # literal, user-chosen strings, never translated.
        self.combo_preset.setItemText(0, tr("brush_preset_default", "Défaut"))
        self.manual_group.setTitle(tr("brush_group_paths", "Mode manuel / indépendant"))
        self.lbl_dataset.setText(tr("brush_lbl_input", "Dossier dataset (sparse + images)"))
        self.lbl_export.setText(tr("brush_lbl_output", "Dossier export"))
        self.lbl_ply.setText(tr("brush_lbl_ply", "Nom du fichier PLY (optionnel)"))
        self.chk_visualiser.setText(tr("chain_view_after", "Lancer dans SuperSplat"))
        if self.standalone:
            self.btn_run.setText(tr("btn_run", "Lancer"))
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
        self.lbl_build_mode.setText(tr("settings_build_mode", "Mode de build Brush"))
        for i, (_value, key, default) in enumerate(_BUILD_MODES):
            self.combo_build_mode.setItemText(i, tr(key, default))
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

```

## app/gui/panels/cleaner_panel.py (208 lignes)
```python
"""Panneau Nettoyage (étape PIPELINE, optionnelle) — équivalent de CleanerTab.

Centre : mode (fichier unique / batch), sélection PLY, dossier/fichier de sortie.
Barre de droite : intensité (Léger/Moyen/Fort) + réglages avancés
(opacity_min, scale_pct, outlier_pct). Réutilise ``resolve_params`` /
``PRESETS`` de ``ply_cleaner`` (moteur inchangé).

Lot 4 : UI + params. Le lancement réel (CleanerWorker) passe par le dispatch
orchestré / le bouton local (câblage moteurs, phase Apple Silicon).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from app.core.ply_cleaner import resolve_params
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit

_STRENGTHS = (("light", "Léger"), ("medium", "Moyen"), ("strong", "Fort"))


class CleanerPanel:
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

        mode_row = QHBoxLayout()
        self.lbl_mode = QLabel()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("", "single")
        self.combo_mode.addItem("", "batch")
        mode_row.addWidget(self.lbl_mode)
        mode_row.addWidget(self.combo_mode)
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
        self.combo_strength = QComboBox()
        for value, _label in _STRENGTHS:
            self.combo_strength.addItem(value, value)
        self.combo_strength.setCurrentIndex(1)  # medium
        self.lbl_strength = QLabel()
        form.addRow(self.lbl_strength, self.combo_strength)
        layout.addLayout(form)

        self.advanced_group = QGroupBox()
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        ag = QFormLayout(self.advanced_group)
        ag.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
        self.spin_opacity = QDoubleSpinBox()
        self.spin_opacity.setRange(0.0, 1.0)
        self.spin_opacity.setSingleStep(0.01)
        self.spin_opacity.setDecimals(3)
        self.spin_opacity.setValue(0.10)
        self.lbl_opacity = QLabel()
        ag.addRow(self.lbl_opacity, self.spin_opacity)
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(90.0, 100.0)
        self.spin_scale.setSingleStep(0.1)
        self.spin_scale.setDecimals(1)
        self.spin_scale.setValue(99.5)
        self.lbl_scale = QLabel()
        ag.addRow(self.lbl_scale, self.spin_scale)
        self.spin_outlier = QDoubleSpinBox()
        self.spin_outlier.setRange(90.0, 100.0)
        self.spin_outlier.setSingleStep(0.1)
        self.spin_outlier.setDecimals(1)
        self.spin_outlier.setValue(99.5)
        self.lbl_outlier = QLabel()
        ag.addRow(self.lbl_outlier, self.spin_outlier)
        layout.addWidget(self.advanced_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def is_batch(self):
        return self.combo_mode.currentData() == "batch"

    def get_params(self):
        """Retourne les paramètres de nettoyage résolus (preset ou surcharges)."""
        strength = self.combo_strength.currentData()
        if self.advanced_group.isChecked():
            overrides = {
                "opacity_min": self.spin_opacity.value(),
                "scale_pct": self.spin_scale.value(),
                "outlier_pct": self.spin_outlier.value(),
            }
            return resolve_params(strength, overrides)
        return resolve_params(strength)

    def get_state(self):
        return {
            "mode": self.combo_mode.currentData(),
            "strength": self.combo_strength.currentData(),
            "advanced": self.advanced_group.isChecked(),
            "opacity_min": self.spin_opacity.value(),
            "scale_pct": self.spin_scale.value(),
            "outlier_pct": self.spin_outlier.value(),
        }

    def set_state(self, state):
        if not state:
            return
        if state.get("mode"):
            idx = self.combo_mode.findData(state["mode"])
            if idx >= 0:
                self.combo_mode.setCurrentIndex(idx)
        if state.get("strength"):
            idx = self.combo_strength.findData(state["strength"])
            if idx >= 0:
                self.combo_strength.setCurrentIndex(idx)
        self.advanced_group.setChecked(state.get("advanced", False))
        if "opacity_min" in state:
            self.spin_opacity.setValue(state["opacity_min"])
        if "scale_pct" in state:
            self.spin_scale.setValue(state["scale_pct"])
        if "outlier_pct" in state:
            self.spin_outlier.setValue(state["outlier_pct"])

    def _browse_input(self):
        if self.is_batch():
            path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        else:
            path, _ = get_open_file_name(self.center, tr("btn_browse", "Parcourir"), "", "PLY (*.ply)")
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    def retranslate_ui(self):
        self.lbl_mode.setText(tr("cleaner_mode", "Mode"))
        self.combo_mode.setItemText(0, tr("cleaner_mode_single", "Fichier unique"))
        self.combo_mode.setItemText(1, tr("cleaner_mode_batch", "Dossier (batch)"))
        self.lbl_input.setText(tr("cleaner_input", "Fichier / dossier PLY"))
        self.lbl_output.setText(tr("cleaner_output", "Sortie nettoyée"))
        self.lbl_strength.setText(tr("cleaner_strength", "Intensité"))
        self.advanced_group.setTitle(tr("cleaner_advanced", "Réglages avancés"))
        self.lbl_opacity.setText(tr("cleaner_opacity", "Opacité mini"))
        self.lbl_scale.setText(tr("cleaner_scale_pct", "Taille max (%)"))
        self.lbl_outlier.setText(tr("cleaner_outlier_pct", "Outliers (%)"))
        self.btn_run.setText(tr("btn_run", "Lancer"))

```

## app/gui/panels/export_panel.py (157 lignes)
```python
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
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)
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

```

## app/gui/panels/visualiser_panel.py (233 lignes)
```python
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

```

## app/core/i18n.py (154 lignes)
```python
import json
import logging

from app.core.system import resolve_project_root

logger = logging.getLogger(__name__)

DEFAULT_LANG = "en"


def _locales_dir():
    return resolve_project_root() / "assets" / "locales"


def is_known_lang(lang_code):
    """True if ``lang_code`` is a plain code with a matching locale file.

    The isalnum() guard keeps a config-supplied value from escaping the
    locales directory (e.g. "../../secrets").
    """
    if not isinstance(lang_code, str) or not lang_code.isalnum():
        return False
    return (_locales_dir() / f"{lang_code}.json").exists()


class LanguageManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_lang = DEFAULT_LANG
            cls._instance._translations = {}
            cls._instance._observers = []
            cls._instance.load_config()
            cls._instance._load_translations()
        return cls._instance

    def add_observer(self, callback):
        """Add a callback to be notified when language changes"""
        if callback not in self._observers:
            self._observers.append(callback)

    def _load_translations(self):
        """Load translations from JSON for the current language"""
        try:
            locales_dir = resolve_project_root() / "assets" / "locales"
            lang_path = locales_dir / f"{self.current_lang}.json"

            # Fallback to English if current lang doesn't exist
            if not lang_path.exists():
                lang_path = locales_dir / "en.json"

            # Final fallback to French if nothing found (core default)
            if not lang_path.exists():
                lang_path = locales_dir / "fr.json"

            if lang_path.exists():
                with open(lang_path, encoding="utf-8") as f:
                    self._translations = json.load(f)
            else:
                self._translations = {}
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Error loading translations: %s", e)
            self._translations = {}

    def load_config(self):
        config_file = resolve_project_root() / "config.json"
        try:
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    saved = config.get("language")
                    if is_known_lang(saved):
                        self.current_lang = saved
                    else:
                        logger.warning(
                            "Langue invalide dans %s (%r) — repli sur %s",
                            config_file, saved, DEFAULT_LANG,
                        )
                        self.current_lang = DEFAULT_LANG
                    logger.info(
                        "Langue chargée au démarrage : %s (depuis %s, clé 'language'=%r)",
                        self.current_lang, config_file, saved,
                    )
            else:
                logger.info(
                    "Langue au démarrage : %s (défaut — %s introuvable)",
                    self.current_lang, config_file,
                )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                "Could not load language config from %s: %s — repli sur %s",
                config_file, e, self.current_lang,
            )

    def save_config(self):
        try:
            config_file = resolve_project_root() / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file) as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        config = existing
            config["language"] = self.current_lang
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Langue enregistrée : %s (dans %s)", self.current_lang, config_file)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not save language config to %s: %s", config_file, e)

    def set_language(self, lang_code):
        if not is_known_lang(lang_code):
            logger.warning("Changement de langue ignoré : code inconnu %r", lang_code)
            return
        self.current_lang = lang_code
        self._load_translations() # Reload on change
        self.save_config()
        for cb in self._observers:
            try:
                cb()
            except Exception:
                logger.exception("Error notifying language observer: %s", cb)

    def tr(self, key, *args):
        text = self._translations.get(key)
        if text is None:
            if args:
                text = str(args[0])
                args = args[1:]
            else:
                text = key
        if args:
            try:
                text = text.format(*args)
            except (IndexError, KeyError) as e:
                logger.debug("i18n format error for key '%s': %s", key, e)
        return text

# Global instance convenience
_lm = LanguageManager()

def tr(key, *args):
    return _lm.tr(key, *args)

def get_current_lang():
    return _lm.current_lang

def set_language(lang_code):
    _lm.set_language(lang_code)

def add_language_observer(callback):
    _lm.add_observer(callback)

```

## app/gui/managers.py (205 lignes)
```python
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.system import resolve_project_root

logger = logging.getLogger(__name__)

class SessionManager:
    """SOLID-SRP : persiste le dernier projet (état du panneau Source — chemins
    source/sortie, nom de projet, options associées) dans ``config.json``, sous
    la clé ``"last_project"``.

    ``config.json`` est partagé avec ``LanguageManager`` (clé ``"language"``,
    cf. ``app/core/i18n.py``) : toute écriture ici lit d'abord le fichier
    existant, ne modifie que sa propre clé, puis réécrit l'ensemble — jamais de
    remplacement complet du fichier, pour ne pas écraser les autres clés.
    """

    CONFIG_KEY = "last_project"

    def __init__(self, main_window):
        self.mw = main_window
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

    def get_session_file(self) -> Path:
        return resolve_project_root() / "config.json"

    def save(self, immediate=False):
        """Optimisation Perf-IO : Debounce de la sauvegarde JSON pour ne pas geler l'UI"""
        if immediate:
            self._save_timer.stop()
            self._do_save()
        else:
            self._save_timer.start(1500) # Debounce 1.5s

    def _source_panel(self):
        return self.mw.panels.get("source") if hasattr(self.mw, "panels") else None

    def _do_save(self):
        panel = self._source_panel()
        if panel is None or not hasattr(panel, "get_state"):
            return
        self._write_merged(panel.get_state())

    def _write_merged(self, project_state):
        """Lit ``config.json`` existant, met à jour uniquement ``CONFIG_KEY``,
        réécrit — même principe de fusion que ``LanguageManager.save_config``."""
        session_file = self.get_session_file()
        config = {}
        if session_file.exists():
            try:
                with open(session_file, encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        config = existing
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Session: config.json illisible, fusion prudente: %s", e)

        config[self.CONFIG_KEY] = project_state
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            logger.error("Erreur sauvegarde session: %s", e)

    def load(self):
        session_file = self.get_session_file()
        if not session_file.exists():
            return

        try:
            with open(session_file, encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Erreur chargement session: %s", e)
            return

        if not isinstance(config, dict):
            return
        project_state = config.get(self.CONFIG_KEY)
        if not project_state:
            return

        panel = self._source_panel()
        if panel is not None and hasattr(panel, "set_state"):
            panel.set_state(project_state)


class AppLifecycle:
    """SOLID-SRP : Responsable du redemarrage OS et processus externes"""
    @staticmethod
    def restart(save_callback=None):
        if save_callback:
            try:
                save_callback()
            except Exception as e:
                logger.warning("Error saving session before restart: %s", e)

        root_dir = resolve_project_root()
        python = sys.executable
        main_py = root_dir / "main.py"

        engines_dir = root_dir / "engines"
        needs_setup = not (engines_dir / "brush").exists()

        if needs_setup and sys.platform != "win32":
            logger.info("Reinstall detected: running setup before relaunch...")
            # Build safe argv: whitelist known flags only
            safe_argv = [a for a in sys.argv[1:] if a in ("--gui", "--debug", "--reset")]
            # FIX(AUDIT): use direct subprocess calls instead of bash -c
            # to prevent command injection via f-string interpolation.
            subprocess.run(
                [python, "-m", "app.scripts.setup_dependencies", "--startup"],
                cwd=str(root_dir)
            )
            subprocess.Popen(
                [python, str(main_py)] + safe_argv,
                cwd=str(root_dir), start_new_session=True
            )
            QApplication.quit()
            sys.exit(0)

        # Relance normale
        args = [python, str(main_py)] + sys.argv[1:]
        logger.info("Relaunching via execv: %s", args)

        if sys.platform != "win32":
            try:
                os.execv(python, args)
            except OSError as e:
                logger.warning("execv failed: %s. Falling back to Popen.", e)

        kwargs = {}
        if sys.platform != "win32":
            kwargs["start_new_session"] = True

        subprocess.Popen(args, cwd=str(root_dir), **kwargs)
        QApplication.quit()
        sys.exit(0)

    @staticmethod
    def reset_factory(deep=False):
        QApplication.quit()

        root_dir = resolve_project_root().resolve()
        run_cmd = root_dir / "CorbeauSplat.command"

        # Collect deletion targets (relative names only)
        targets_rel = [".venv", ".venv_sharp", ".venv_360"]

        if deep:
            targets_rel.append("engines")
            targets_rel.append("config.json")

        logger.info("Reset Factory %s initié sur: %s", "DEEP" if deep else "LIGHT", root_dir)

        # Validate containment: every target must resolve inside project root
        import shutil as _shutil
        for rel in list(targets_rel):
            target = (root_dir / rel).resolve()
            try:
                target.relative_to(root_dir)
            except ValueError:
                logger.warning("Reset blocked: path outside project root — %s", target)
                targets_rel.remove(rel)
            else:
                # Remove the target if it exists
                if not target.exists():
                    continue
                try:
                    logger.warning("Reset: removing %s", target)
                    if target.is_dir():
                        _shutil.rmtree(target, ignore_errors=False)
                    else:
                        target.unlink()
                except OSError as e:
                    logger.warning("Reset: could not remove %s — %s", target, e)

        # Also clean deep sync-conflict files
        if deep:
            for p in root_dir.glob("config.sync-conflict-*"):
                try:
                    p.relative_to(root_dir)
                    logger.warning("Reset: removing %s", p)
                    p.unlink()
                except (ValueError, OSError):
                    pass

        # Relaunch via CorbeauSplat.command
        if run_cmd.exists():
            logger.info("Reset: relaunching via %s", run_cmd)
            subprocess.Popen(["open", str(run_cmd)], start_new_session=True)
        else:
            logger.warning("Reset: launcher not found at %s, relaunching main.py", run_cmd)
            subprocess.Popen([sys.executable, str(root_dir / "main.py"), "--gui"], start_new_session=True)
        sys.exit(0)

```

## app/core/config_io.py (121 lignes)
```python
"""Sauvegarde/chargement de configurations *nommées et réutilisables* de la
chaîne complète (icônes Charger/Sauvegarder du top bar).

Distinct de ``SessionManager`` (qui persiste l'unique session GUI courante dans
``config.json``) : ici plusieurs configurations nommées, réutilisables, chacune
dans son fichier sous ``configs/``.

La sérialisation par section réutilise le contrat ``to_dict``/``from_dict`` déjà
en place (``ColmapParams``, ``BrushParams``, ``RunState``) plutôt que de
dupliquer une logique parallèle. ``from_dict`` étant tolérant aux clés
manquantes/inconnues, une config sauvegardée par une version antérieure se
recharge sans casser.
"""

import json
import logging
from dataclasses import asdict, dataclass, field

from .params import ColmapParams
from .run_state import RunState
from .system import resolve_project_root

logger = logging.getLogger(__name__)

CONFIG_VERSION = 1


def configs_dir():
    """Dossier des configurations nommées (créé à la demande)."""
    d = resolve_project_root() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_safe_config_name(name: str) -> bool:
    """Même règle que la sanitisation du nom de projet (``engine.py``) : pas de
    ``..``, ``/`` ni ``\\``, et non vide."""
    if not name or not name.strip():
        return False
    return ".." not in name and "/" not in name and "\\" not in name


@dataclass
class ChainConfig:
    """Configuration complète de la chaîne, sérialisable vers un fichier nommé."""

    version: int = CONFIG_VERSION
    source: dict = field(default_factory=dict)     # input_path, output_path, project_name, fps…
    colmap: dict = field(default_factory=dict)     # ColmapParams.to_dict()
    brush: dict = field(default_factory=dict)      # BrushParams.to_dict()
    cleaning: dict = field(default_factory=dict)   # intensité, opacity_min, scale_pct, outlier_pct
    export: dict = field(default_factory=dict)     # format cible, scale…
    flags: dict = field(default_factory=dict)      # RunState.to_dict()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChainConfig":
        """Reconstruit une config depuis un dict, tolérant aux sections
        manquantes et aux versions antérieures."""
        if not isinstance(data, dict):
            return cls()
        data = _migrate(dict(data))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    # Helpers typés : rechargent des objets à partir des sections, en s'appuyant
    # sur la tolérance de leurs from_dict respectifs.
    def colmap_params(self) -> ColmapParams:
        return ColmapParams.from_dict(self.colmap or {})

    def run_state(self) -> RunState:
        return RunState.from_dict(self.flags or {})


def _migrate(data: dict) -> dict:
    """Point d'extension pour les migrations de schéma futures. Aujourd'hui
    identité (version 1). Les versions inconnues sont chargées au mieux."""
    return data


def save_config(name: str, config: ChainConfig | dict) -> "object":
    """Écrit une configuration nommée. Retourne le chemin du fichier."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    data = config.to_dict() if isinstance(config, ChainConfig) else dict(config)
    data.setdefault("version", CONFIG_VERSION)
    path = configs_dir() / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_config(name: str) -> ChainConfig:
    """Charge une configuration nommée. Lève ``FileNotFoundError`` si absente."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return ChainConfig.from_dict(json.load(f))


def list_configs() -> list:
    """Noms des configurations disponibles (triés)."""
    try:
        return sorted(p.stem for p in configs_dir().glob("*.json"))
    except OSError as e:
        logger.warning("Impossible de lister les configurations: %s", e)
        return []


def delete_config(name: str) -> bool:
    """Supprime une configuration nommée. Retourne True si un fichier a été retiré."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False

```

## Résumé

Les 13 fichiers demandés ont tous été trouvés, aucun "FICHIER INTROUVABLE".
Chemins résolus par grep (non donnés littéralement dans la demande) :
- Reconstruction/COLMAP → `app/gui/panels/reconstruction_panel.py` (classe `ReconstructionPanel`, matché sur `ColmapParams`)
- Nettoyage → `app/gui/panels/cleaner_panel.py` (classe `CleanerPanel`, matché sur `_launch_cleaner`/`Nettoyage`)
- Export → `app/gui/panels/export_panel.py` (matché sur `_launch_export`)
- Visualiser → `app/gui/panels/visualiser_panel.py` (classe `VisualiserPanel`, matché sur `toggle_server`)
- LanguageManager → `app/core/i18n.py` (matché sur `class LanguageManager`)
