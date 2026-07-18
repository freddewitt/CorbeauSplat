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
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import VERSION
from app.core.i18n import add_language_observer, tr
from app.core.run_state import PIPELINE_STEPS, RunState
from app.gui.logbar import LogBar
from app.gui.panels.reconstruction_panel import ReconstructionPanel
from app.gui.panels.source_panel import SourcePanel
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
        self._settings_window = None
        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Top bar ───────────────────────────────────────────────────────────
        self.topbar = TopBar()
        self.topbar.settingsRequested.connect(self.open_settings)
        root.addWidget(self.topbar)

        # ── Corps : rail | centre | barre de droite ───────────────────────────
        body = QHBoxLayout()
        self.rail = Rail()
        self.rail.itemSelected.connect(self.on_rail_selected)
        self.rail.setFixedWidth(220)
        body.addWidget(self.rail)

        self.center_stack = QStackedWidget()
        body.addWidget(self.center_stack, stretch=3)

        self.right_stack = QStackedWidget()
        self.right_stack.setFixedWidth(280)
        body.addWidget(self.right_stack)

        # Panneaux réels disponibles (les autres clés restent des placeholders,
        # remplacés aux sous-lots 3b/3c/4/5).
        self.panels = {
            "source": SourcePanel(self.run_state),
            "reconstruction": ReconstructionPanel(self.run_state),
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

        # Sélection initiale : première étape.
        if _PAGE_KEYS:
            self.rail.select(_PAGE_KEYS[0])
            self.on_rail_selected(_PAGE_KEYS[0])

    def _placeholder(self, key, zone):
        """Page provisoire (remplacée par le vrai panneau aux lots 3-5)."""
        w = QLabel(f"[{zone}] {key} — à venir")
        w.setObjectName(f"placeholder_{zone}_{key}")
        return w

    # ── Navigation ──────────────────────────────────────────────────────────────
    def on_rail_selected(self, key):
        """Change la page affichée au centre et à droite selon l'item du rail."""
        index = self.nav.select(key)
        if index is None:
            return
        self.center_stack.setCurrentIndex(index)
        self.right_stack.setCurrentIndex(index)

    def current_page_key(self):
        return self.nav.current

    # ── Réglages ──────────────────────────────────────────────────────────────
    def open_settings(self):
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
            self._settings_window.quitRequested.connect(self.close)
        self._settings_window.show()
        self._settings_window.raise_()

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
