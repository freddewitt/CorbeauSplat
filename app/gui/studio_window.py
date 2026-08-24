"""Fenêtre principale « Studio » — interface en 4 zones.

Assemble : Rail (gauche), zone centre + barre de droite (``QStackedWidget``
pilotés par la sélection du rail), ``ActivityBar`` (bas : étape en cours, détail,
progression) et barre du bas (actions globales, dont l'ouverture du
journal). Le bouton Lancer/Annuler et le sélecteur de mode pipeline vivent
désormais dans ``SourcePanel`` (l'ancienne TopBar a disparu).

Le journal n'est plus dans la fenêtre principale : il a la sienne
(``logs_window.py``), alimentée en continu et ouverte à la demande.

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
from app.gui.panels.reconstruction_logic import apply_source_blur_settings, detect_source_kind
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.sharp_panel import SharpPanel
from app.gui.panels.source_panel import SourcePanel
from app.gui.panels.splat_transform_panel import SplatTransformPanel
from app.gui.panels.upscale_panel import UpscalePanel
from app.gui.panels.visualiser_panel import VisualiserPanel
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail, item_label
from app.gui.settings_window import SettingsWindow
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

# Ordre des pages du stacked (étapes PIPELINE puis modules OUTILS).
_PAGE_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)


class StudioWindow(QMainWindow):
    """Coquille 4 zones. Sélection du rail → change la page centre + droite."""

    def __init__(self):
        super().__init__()
        self.run_state = RunState()
        self.nav = PageRegistry(_PAGE_KEYS)   # mapping pages + sélection courante
        self.current_plan = []
        self._plan_index = 0
        self._active_pipeline_step = None
        # Dossier d'images courant de la chaîne : chaque pré-étape qui produit
        # un nouveau dossier (Extraction 360, puis Upscale) l'écrase, et l'étape
        # suivante le lit à la place du chemin Source brut. Réinitialisé à chaque
        # ``launch()`` pour qu'un run sans pré-étape ne réutilise pas le dossier
        # d'un run précédent.
        self._pipeline_images_dir = None
        self._pending_upscale_params = None
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

        self.appbar = AppBar()
        root.addWidget(self.appbar)

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

        # Filet fin centre | barre de droite (masqué avec la barre de droite
        # quand le panneau courant n'a pas de contenu droit, cf. _show_page).
        self._center_right_vline = self._vline()
        body.addWidget(self._center_right_vline)

        # Barre de droite : largeur suffisante pour les accordéons de params, et
        # chaque panneau y gère son propre défilement vertical.
        self.right_stack = QStackedWidget()
        self.right_stack.setFixedWidth(400)
        body.addWidget(self.right_stack)

        # Panneaux réels disponibles (les autres clés restent des placeholders,
        # remplacés aux sous-lots 3b/3c/4/5).
        self.panels = {
            "source": SourcePanel(self.run_state),
            "extraction360": Extractor360Panel(self.run_state),
            "upscale": UpscalePanel(self.run_state),
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
            "splattransform": SplatTransformPanel(self.run_state),
            "4dgs": FourDGSPanel(self.run_state),
            "360": Extractor360Panel(self.run_state),
        }

        # Bouton « Lancer » local des modules OUTILS (et de Reconstruction/
        # Nettoyage/Export, utilisables seuls hors chaîne pipeline) : chacun
        # démarre son propre worker, SourcePanel bascule en Annuler pendant
        # l'exécution (cf. _start_tool_worker / on_launch_clicked).
        self.panels["nettoyage"].btn_run.clicked.connect(self._launch_cleaner)
        self.panels["export"].btn_run.clicked.connect(self._launch_export)
        self.panels["360"].btn_run.clicked.connect(self._launch_extractor360)
        self.panels["extraction360"].btn_run.clicked.connect(self._launch_extraction360)
        self.panels["4dgs"].btn_run.clicked.connect(self._launch_fourdgs)
        self.panels["4dgs"].btn_colmap_only.clicked.connect(self._launch_fourdgs_colmap_only)
        self.panels["sharp"].btn_run.clicked.connect(self._launch_sharp)
        self.panels["splattransform"].btn_run.clicked.connect(self._launch_splat_transform)
        # Upscale est une étape PARAMÈTRES : ce bouton ne lance que l'upscale
        # local sur les chemins saisis dans le panneau, indépendamment de la
        # chaîne (que pilote le drapeau ``upscaler_avant`` côté Projet).
        self.panels["upscale"].btn_run.clicked.connect(self._launch_upscale)
        self.panels["brush"].btn_run.clicked.connect(self._launch_brush)
        self.panels["reconstruction"].btn_run.clicked.connect(self._launch_reconstruction)
        self.panels["source"].btn_delete_dataset.clicked.connect(self._delete_dataset)
        # Bouton Lancer/Annuler unique (ex-topbar), désormais porté par SourcePanel.
        self.panels["source"].btn_run.clicked.connect(self.on_launch_clicked)
        # Stop button under every panel's Run button. A single worker runs at a
        # time (``_active_worker``), so they all interrupt the same thing —
        # whichever page the user happens to be on.
        for panel in self.panels.values():
            button = getattr(panel, "btn_cancel", None)
            if button is not None:
                button.clicked.connect(self._cancel_active_worker)

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

        # ── Journal : fenêtre dédiée, alimentée en continu même fermée ─────────
        # Construite ici (jamais affichée d'office) pour que l'historique complet
        # du run soit présent dès la première ouverture, y compris ce qui s'est
        # produit avant qu'on pense à regarder.
        self.logs_window = LogsWindow(self)

        # ── Barre d'activité : étape en cours, détail, progression, Annuler ────
        self.activity_bar = ActivityBar()
        root.addWidget(self.activity_bar)

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
        """Always-visible bottom bar: lifecycle actions (Restart/Quit), moved
        out of SettingsWindow — these are global actions, not settings.
        The version now lives in the AppBar (top), not shown twice here."""
        w = QWidget()
        row = QHBoxLayout(w)
        # Marges plus généreuses que les 2px d'origine, et asymétriques : c'est
        # la seule barre collée au bord bas de la fenêtre. À 2px, les boutons
        # arrivaient à 899px dans une fenêtre de 900 — l'arrondi et l'ombre de
        # fenêtre macOS les faisaient lire comme tronqués. L'horizontale s'aligne
        # sur AppBar (10px).
        row.setContentsMargins(10, 6, 10, 8)
        row.addStretch(1)

        # Réglages généraux (ex-topbar) : déplacé ici avec la disparition de la
        # TopBar, réutilise la même clé i18n de tooltip. Le glyphe seul étant
        # ambigu, un libellé texte l'accompagne (clé dédiée : le style petites
        # capitales de rail_section_parametres ne convient pas à ce contexte).
        self.btn_settings = QPushButton(f"⚙ {tr('btn_settings_label', 'Paramètres')}")
        self.btn_settings.setToolTip(tr("topbar_settings", "Réglages généraux"))
        self.btn_settings.clicked.connect(self.open_settings)
        row.addWidget(self.btn_settings)

        # Journal : le bas de la fenêtre ne montre plus que l'activité en cours,
        # le détail complet (avec recherche/copie/sauvegarde) s'ouvre ici.
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

    # ── Lancement (dispatch orchestré) ──────────────────────────────────────────
    def launch(self):
        """Calcule le plan de run selon le mode + les toggles run_state, puis
        démarre réellement la chaîne pipeline (Source → Reconstruction/COLMAP →
        Entraînement/Brush, cf. ``_run_pipeline_step``). Pilote aussi le rail
        (statuts + auto-follow) et le breadcrumb."""
        mode = self.panels["source"].current_mode()
        plan = plan_pipeline(mode, self.run_state)
        self.current_plan = plan
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

    # ── Enchaînement des workers du pipeline principal ───────────────────────────
    def _run_pipeline_step(self, index):
        """Démarre l'étape ``self.current_plan[index]``. Source n'a pas de
        worker propre (elle ne fait que fournir les chemins consommés par
        Reconstruction) : elle est marquée DONE immédiatement et la chaîne
        enchaîne. Les post-étapes OUTILS (Nettoyage/Export/Visualiser)
        n'apparaissent dans ``self.current_plan`` que si leur drapeau
        ``run_state`` correspondant est actif (cf. ``plan_pipeline``) ; quand
        elles y sont, elles sont pré-remplies depuis la sortie de l'étape
        précédente puis enchaînées automatiquement comme Reconstruction/
        Entraînement."""
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
                # Source vidéo : les images n'existent pas encore, l'upscale est
                # délégué à COLMAP qui l'exécutera juste après l'extraction des
                # trames et avant l'extraction des features (cf.
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
            worker = self._build_colmap_worker()
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

        # Défensif : ``plan_pipeline`` ne produit que des clés reconnues
        # ci-dessus, cette branche ne devrait donc jamais s'exécuter.
        message = tr("run_chain_manual_continue").format(step)
        self._finish_pipeline_chain(True, message)

    def _resolve_source_type(self, step, input_path, source_state):
        """Type de source (``images``/``video``) pour l'étape ``step``, ou None
        si indéterminable — auquel cas l'étape est déjà marquée en échec.

        Respecte le choix explicite de l'utilisateur (Images/Vidéo) plutôt que
        la détection auto s'il en a fait un (SourcePanel.combo_source_type,
        "auto" par défaut). Partagé par Upscale et Reconstruction, qui doivent
        classer la même source de la même manière."""
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
            self._fail_pipeline_step(step, tr("err_no_paths", "Chemins manquants."))
            return None
        return input_type

    def _build_extraction360_worker(self):
        """Construit le worker de l'étape Extraction 360.

        Contrairement à Upscale, cette étape ne transforme pas les images sur
        place : elle **produit un nouveau dossier** d'images planaires à partir
        d'une source équirectangulaire (vidéo ou photos). Ce dossier devient le
        dossier d'images courant de la chaîne (``_pipeline_images_dir``), que
        l'Upscale puis COLMAP consommeront à la place de la source d'origine.

        Le type de source n'est pas résolu ici : l'extracteur accepte vidéo comme
        images, et sa sortie est toujours un dossier d'images."""
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
        """Lancement autonome de l'étape Extraction 360 depuis PARAMÈTRES, sur
        les chemins saisis dans le panneau — même idiome que
        ``_launch_extractor360`` pour l'instance OUTILS."""
        panel = self.panels["extraction360"]
        input_path = panel.input_path.text().strip()
        output_path = panel.output_path.text().strip()
        if not self._check_paths(input_path, output_path):
            return
        self._start_tool_worker(Extractor360Worker(input_path, output_path, panel.get_params()))

    def _build_upscale_worker(self):
        """Construit le worker de l'étape Upscale, qui agrandit les images
        *avant* que COLMAP ne les lise.

        Si l'Extraction 360 a tourné juste avant, la source est le dossier
        d'images planaires qu'elle a produit (``_pipeline_images_dir``) — donc
        toujours des images, jamais une vidéo. Sinon, deux cas, car les images du
        projet n'existent pas encore à ce stade :
        - **source images** : un ``UpscaleImagesWorker`` écrit les images
          agrandies dans ``<sortie>/<projet>/images_upscaled``, que
          ``_build_colmap_worker`` prendra ensuite comme entrée. Le dossier
          source de l'utilisateur reste intact.
        - **source vidéo** : rien à agrandir tant que les trames ne sont pas
          extraites. On renseigne ``_pending_upscale_params``, que
          ``_build_colmap_worker`` transmet à ``ColmapWorker`` : le moteur
          agrandit les trames juste après extraction et avant COLMAP
          (mécanisme ``upscale_config`` déjà en place dans ``engine.py``).
          Renvoie alors None sans échec — l'appelant enchaîne.
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

    def _build_colmap_worker(self):
        """Construit le ``ColmapWorker`` de l'étape Reconstruction depuis les
        chemins de Source (SourcePanel.get_state) et les réglages COLMAP de
        Reconstruction (ReconstructionPanel.get_params → ColmapParams).

        Si l'étape Upscale a tourné juste avant, l'entrée devient le dossier
        d'images agrandies qu'elle a produit (cf. ``_build_upscale_worker``)."""
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
            # Sémantique d'origine du champ (CHANGELOG 1.2.3) : une destination
            # personnalisée ne conserve que le dernier checkpoint ; champ vide =
            # comportement historique, tous les checkpoints gardés.
            keep_only_latest=keeps_only_latest_checkpoint(source_state),
        )



    # ── Pré-remplissage des post-étapes OUTILS depuis la sortie de l'étape
    # précédente (cf. Section G : chaînage Entraînement → Nettoyage → Export →
    # Visualiser, uniquement quand le drapeau ``run_state`` correspondant est actif) ──
    def _find_latest_ply(self, directory: Path):
        """Fichier ``.ply`` le plus récemment modifié sous ``directory``
        (récursif), ou ``None``. Même idiome de recherche que
        ``BrushWorker.handle_ply_rename`` (app/gui/workers.py), en plus simple :
        on ne connaît pas ici le nom final choisi par Brush (dépend de
        ``ply_name``/``project_name``), donc on relit le système de fichiers
        une fois l'entraînement terminé plutôt que de dupliquer sa logique de
        renommage."""
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
        """PLY produit par la dernière étape Entraînement, dans le dossier de
        checkpoints du projet (cf. ``_build_brush_worker``)."""
        checkpoints_dir = resolve_checkpoints_dir(self.panels["source"].get_state())
        if checkpoints_dir is None:
            return None
        return self._find_latest_ply(checkpoints_dir)

    def _resolve_ply_output(self):
        """Chemin PLY le plus pertinent à transmettre à l'étape suivante :
        sortie de Nettoyage si cette étape est active (``nettoyer_apres``),
        sinon PLY produit par l'Entraînement."""
        if self.run_state.nettoyer_apres:
            cleaned = self.panels["nettoyage"].output_path.text().strip()
            if cleaned:
                return cleaned
        latest_ply = self._latest_brush_ply()
        return str(latest_ply) if latest_ply is not None else ""

    def _prefill_cleaner_from_brush(self):
        """Pré-remplit le panneau Nettoyage avec le PLY produit par
        l'Entraînement, avant construction du worker (cf. ``_build_cleaner_worker``)."""
        latest_ply = self._latest_brush_ply()
        if latest_ply is None:
            return
        panel = self.panels["nettoyage"]
        panel.input_path.setText(str(latest_ply))
        if not panel.output_path.text().strip():
            panel.output_path.setText(str(latest_ply.with_name(f"clean_{latest_ply.name}")))

    def _prefill_export_from_previous(self):
        """Pré-remplit le panneau Export depuis la sortie de l'étape précédente
        (Nettoyage si actif, sinon directement l'Entraînement).

        Les champs « Dossier d'export » et « Format » du panneau Projet, quand
        ils sont renseignés, l'emportent sur ce qui est saisi dans le panneau
        Export : ce sont les réglages de la *chaîne*, alors que le panneau Export
        sert aussi au lancement local. Laissés vides, le comportement précédent
        est inchangé (dossier du PLY source, format courant du panneau)."""
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
        """Pré-remplit le panneau Visualiser depuis la sortie de l'étape
        précédente (même règle que ``_prefill_export_from_previous``)."""
        source_path = self._resolve_ply_output()
        if source_path:
            self.panels["visualiser"].input_path.setText(source_path)

    def _run_visualiser_pipeline_step(self):
        """Étape Visualiser de la chaîne : ``VisualiserPanel`` n'est pas un
        Worker/QThread (serveur persistant via ``toggle_server()``), donc pas de
        DONE/ERROR classique piloté par un ``finished_signal``. L'étape est
        marquée DONE dès que le serveur démarre avec succès (sans bloquer sur
        une fin d'exécution) ; en cas d'échec de démarrage, ERROR."""
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
        """Démarre le worker d'une étape pipeline : statuts rail/run_state posés
        au moment réel du démarrage (pas juste à la planification), logs relayés,
        SourcePanel basculé en Annuler — même idiome que ``_start_tool_worker``."""
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
        # Le journal ne s'ouvre plus de force au démarrage : l'en-tête de la
        # barre affiche désormais l'activité même repliée (cf.
        # ``_wire_worker_feedback``). Il ne se déplie plus que sur erreur.
        worker.start()

    def _wire_worker_feedback(self, worker):
        """Relaie logs, statut et progression d'un worker vers la barre du bas.

        ``progress_signal`` était émis par quatre workers (COLMAP, 360, Sharp
        vidéo, Export) mais n'était connecté nulle part : la progression était
        calculée puis jetée. Elle alimente maintenant la barre de l'en-tête.

        L'activité est branchée sur ``log_signal`` **et** ``status_signal`` :
        ``BrushWorker`` (l'entraînement) n'émet que le premier — son moteur ne
        reçoit pas de ``status_callback`` — donc se limiter au statut le
        laisserait muet."""
        worker.log_signal.connect(self.logs_window.append_log)
        worker.log_signal.connect(self.activity_bar.set_activity)
        if hasattr(worker, "status_signal"):
            worker.status_signal.connect(self.logs_window.append_log)
            worker.status_signal.connect(self.activity_bar.set_activity)
        if hasattr(worker, "progress_signal"):
            worker.progress_signal.connect(self.activity_bar.set_progress)
            worker.progress_signal.connect(self.panels["source"].progress_ring.set_value)

    def _on_pipeline_step_finished(self, success, message):
        """Fin d'une étape pipeline : DONE + étape suivante si succès ; ERROR +
        arrêt de la chaîne (pas d'échec silencieux) sinon."""
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
        # Le journal ne s'ouvre plus tout seul, même sur erreur : la boîte de
        # dialogue ci-dessous porte déjà le message, et l'étape passe en ⛔ dans
        # le rail — un clic dessus ouvre le journal (cf. on_rail_selected).
        if not stopped_by_user:
            self.notify(tr("msg_error", "Erreur"), message)
            QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _fail_pipeline_step(self, step, message):
        """Échec de construction d'un worker (ex. chemins manquants) : même
        traitement qu'un échec en cours d'exécution, sans worker actif à nettoyer."""
        self.run_state.set_status(step, StepStatus.ERROR)
        self.rail.set_step_status(step, StepStatus.ERROR)
        self.logs_window.append_log(message)
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        self._active_worker = None
        self.notify(tr("msg_error", "Erreur"), message)
        QMessageBox.warning(self, tr("msg_error", "Erreur"), message)

    def _finish_pipeline_chain(self, success, message):
        """Fin (normale ou volontairement interrompue) de la chaîne pipeline."""
        self._active_worker = None
        self.panels["source"].set_running(False)
        self._set_cancel_enabled(False)
        self.activity_bar.reset_activity()
        self.panels["source"].progress_ring.stop()
        self.logs_window.append_log(message)
        if success:
            self.notify(tr("msg_success", "Succès"), message)

    # ── Dispatch du bouton unique Lancer/Annuler (ex-topbar, porté par SourcePanel) ──
    def on_launch_clicked(self):
        """``SourcePanel.btn_run`` n'a qu'un bouton Lancer/Annuler : s'il y a un
        worker OUTILS actif (lancé depuis un bouton local), le clic l'annule ;
        sinon il lance la chaîne pipeline (cf. ``launch``)."""
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

    # ── Lancement des modules OUTILS (bouton local, hors chaîne pipeline) ────────
    def _start_tool_worker(self, worker, finished_signal=None):
        """Démarre un worker OUTILS en tâche de fond : logs relayés vers la
        barre de logs, SourcePanel basculé en Annuler, résultat affiché à la fin.

        Un second clic sur Lancer pendant qu'un worker tourne déjà écraserait
        ``self._active_worker`` sans garder de référence Python vers l'ancien
        thread : celui-ci se ferait garbage-collecter par Qt alors que son
        thread OS tourne encore ("QThread: Destroyed while thread is still
        running") — crash immédiat (SIGABRT). D'où le garde-fou ci-dessous.
        """
        existing = self._active_worker
        if existing is not None and existing.isRunning():
            self.logs_window.append_log(
                tr("err_worker_already_running", "Un traitement est déjà en cours.")
            )
            return
        self._active_worker = worker
        # Un worker OUTILS n'a pas d'étape de pipeline : on nomme la page depuis
        # laquelle il a été lancé, qui est celle que l'utilisateur regarde.
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
        """Construit le ``CleanerWorker`` depuis les champs actuels du panneau
        Nettoyage. Partagé par ``_launch_cleaner`` (bouton local, hors chaîne)
        et l'étape ``nettoyage`` de la chaîne pipeline (cf. ``_run_pipeline_step``),
        qui pré-remplit les champs avant l'appel (cf. ``_prefill_cleaner_from_brush``)."""
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
        """Construit l'``ExportWorker`` depuis les champs actuels du panneau
        Export. Partagé par ``_launch_export`` (bouton local, hors chaîne) et
        l'étape ``export`` de la chaîne pipeline (cf. ``_run_pipeline_step``)."""
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
        """Lancement autonome (hors chaîne) du panneau Reconstruction, même
        idiome que ``_launch_cleaner``/``_launch_export``. Réutilise
        ``_build_colmap_worker`` (déjà pilote la chaîne pipeline) — sur échec
        de construction (chemins manquants, source mixte…), il échoue déjà
        proprement l'étape via ``_fail_pipeline_step``."""
        worker = self._build_colmap_worker()
        if worker is not None:
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

    # ── Configuration nommée (Charger / Sauvegarder) ────────────────────────────
    def collect_config(self) -> ChainConfig:
        """Agrège l'état des panneaux + drapeaux en une ChainConfig sérialisable."""
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
        """Applique une ChainConfig aux panneaux et aux drapeaux partagés."""
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
        """Même idiome que ``load_config_dialog`` (choix dans la liste), plus une
        confirmation : l'opération retire un fichier et n'est pas annulable."""
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
            # Idem _delete_selected_preset : pas de défaut sur une clé à {0}.
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
        """Notifie l'utilisateur si les notifications sont activées."""
        if self._notifications_enabled:
            notifications.notify(title, message)

    # ── Réglages ──────────────────────────────────────────────────────────────
    def open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.saveRequested.connect(self.save_config_dialog)
            self._settings_window.loadRequested.connect(self.load_config_dialog)
            self._settings_window.deleteRequested.connect(self.delete_config_dialog)
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
        self.btn_settings.setText(f"⚙ {tr('btn_settings_label', 'Paramètres')}")
        self.btn_logs.setText(f"▤ {tr('logbar_title', 'Logs')}")
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
