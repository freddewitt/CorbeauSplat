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
