"""Fenêtre principale « Studio » — nouvelle interface en 4 zones.

Assemble : TopBar (haut), Rail (gauche), zone centre + barre de droite
(``QStackedWidget`` pilotés par la sélection du rail), LogBar (bas).

Lot 2 : squelette visuel. Les pages centre/droite sont des placeholders ; les
panneaux réels (Source, Reconstruction, …) et le câblage moteur arrivent aux
lots 3-5. ``main_window.py`` (``ColmapGUI``) reste l'interface active — la
bascule finale se fait au Lot 7. Cette fenêtre n'est donc pas encore lancée
depuis ``main.py``.
"""

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import VERSION
from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus
from app.gui.logbar import LogBar
from app.gui.panels.entrainement_panel import EntrainementPanel
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.source_panel import SourcePanel
from app.gui.pipeline_planner import plan_pipeline
from app.gui.rail import TOOL_KEYS, Rail
from app.gui.settings_window import SettingsWindow
from app.gui.studio_nav import PageRegistry
from app.gui.styles import set_dark_theme
from app.gui.topbar import TopBar

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
        self._settings_window = None
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
        self.topbar.launchRequested.connect(self.launch)
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
        }

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
        logique que le verrou d'auto-scroll des logs) et change la page."""
        self._auto_follow = False
        self._show_page(key)

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

    # ── Réglages ──────────────────────────────────────────────────────────────
    def open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.quitRequested.connect(self.close)
        self._settings_window.show()
        self._settings_window.raise_()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
