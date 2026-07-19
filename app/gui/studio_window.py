"""Fenêtre principale « Studio » — nouvelle interface en 4 zones.

Assemble : TopBar (haut), Rail (gauche), zone centre + barre de droite
(``QStackedWidget`` pilotés par la sélection du rail), LogBar (bas).

Lot 2 : squelette visuel. Les pages centre/droite sont des placeholders ; les
panneaux réels (Source, Reconstruction, …) et le câblage moteur arrivent aux
lots 3-5. ``main_window.py`` (``ColmapGUI``) reste l'interface active — la
bascule finale se fait au Lot 7. Cette fenêtre n'est donc pas encore lancée
depuis ``main.py``.
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import VERSION
from app.core import notifications
from app.core.config_io import ChainConfig, list_configs, load_config, save_config
from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus
from app.gui.logbar import LogBar
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
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail
from app.gui.settings_window import SettingsWindow
from app.gui.studio_nav import PageRegistry
from app.gui.styles import set_dark_theme
from app.gui.topbar import TopBar
from app.gui.widgets.upscale_widgets import TestWorker
from app.gui.workers import (
    CleanerWorker,
    Extractor360Worker,
    ExportWorker,
    FourDGSWorker,
    SharpVideoWorker,
    SharpWorker,
    SplatTransformWorker,
)

# Ordre des pages du stacked (étapes PIPELINE puis modules OUTILS).
_PAGE_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)


class StudioWindow(QMainWindow):
    """Coquille 4 zones. Sélection du rail → change la page centre + droite."""

    def __init__(self):
        super().__init__()
        self.run_state = RunState()
        self.nav = PageRegistry(_PAGE_KEYS)   # mapping pages + sélection courante
        self._auto_follow = True              # suit l'étape active (désaccouplé au clic manuel)
        self.current_plan = []
        self._notifications_enabled = False
        self._settings_window = None
        self._active_worker = None
        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)

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
            "brush": EntrainementPanel(self.run_state),
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

        # Version discrète
        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #666666; font-size: 10px; padding: 2px;")
        self.statusBar().addPermanentWidget(version_label)

        # Sélection initiale : première étape (programmatique, sans désaccoupler).
        if _PAGE_KEYS:
            self.rail.select(_PAGE_KEYS[0])
            self._show_page(_PAGE_KEYS[0])

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
        pilote le rail (statuts + auto-follow) et le breadcrumb.

        Note : le câblage des moteurs/workers réels (ColmapWorker/BrushWorker/
        PostTrainingWorker) est la surface validée sur Apple Silicon — voir
        REFONTE_UI_PROGRESS.md. Ici on établit le plan et le pilotage UI."""
        mode = self.topbar.current_mode()
        plan = plan_pipeline(mode, self.run_state)
        self.current_plan = plan
        self._auto_follow = True
        self.run_state.reset_status()
        self.update_breadcrumb(plan)
        self.logbar.append_log(tr("run_plan", "Plan : ") + " → ".join(plan))
        if plan:
            first = plan[0]
            self.run_state.set_status(first, StepStatus.RUNNING)
            self.rail.set_step_status(first, StepStatus.RUNNING)
            self.follow_step(first)
        return plan

    def update_breadcrumb(self, plan):
        self.breadcrumb.setText(" → ".join(plan))

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
            self._settings_window.quitRequested.connect(self.close)
            self._settings_window.saveRequested.connect(self.save_config_dialog)
            self._settings_window.loadRequested.connect(self.load_config_dialog)
            self._settings_window.notificationsToggled.connect(self.set_notifications_enabled)
        self._settings_window.show()
        self._settings_window.raise_()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))

    # ── Fermeture ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        """Point de vigilance Lot 4 (PROMPT_CLAUDE_CODE_REFONTE_UI.md) : annule
        un worker OUTILS actif et stoppe SuperSplatEngine pour ne pas laisser de
        serveur local orphelin quand la fenêtre se ferme."""
        self._cancel_active_worker()
        for key in ("visualiser", "supersplat"):
            engine = getattr(self.panels.get(key), "engine", None)
            if engine is not None:
                engine.stop_all()
        event.accept()
