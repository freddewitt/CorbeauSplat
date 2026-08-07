"""Fenêtre dédiée au journal d'exécution.

Le journal occupait le bas de la fenêtre principale, replié par défaut : illisible
une fois déplié (quelques lignes de haut), et il écrasait le contenu de l'écran en
s'ouvrant. Il vit désormais dans sa propre fenêtre, **non modale** — on peut la
laisser ouverte pendant un run et continuer à travailler dans le Studio.

Le contenu EST un ``LogsTab``, comme l'ancienne barre : recherche, copie,
sauvegarde et verrou d'auto-défilement y sont déjà en place, rien à réimplémenter.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from app.core.i18n import add_language_observer, tr
from app.gui.tabs.logs_tab import LogsTab


class LogsWindow(QDialog):
    """Journal complet, ouvert à la demande depuis la barre du bas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Non modale : un run peut durer des heures, bloquer le Studio pendant
        # qu'on lit ses logs n'aurait aucun sens.
        self.setModal(False)
        self.resize(900, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.logs = LogsTab()
        layout.addWidget(self.logs)

        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Délégation vers le LogsTab encapsulé ────────────────────────────────────
    def append_log(self, message):
        """Alimentée en continu, que la fenêtre soit visible ou non.

        C'est délibéré : l'historique complet du run doit être là à la première
        ouverture, y compris ce qui s'est produit avant qu'on pense à regarder.
        """
        self.logs.append_log(message)

    def clear_log(self):
        self.logs.clear_log()

    def show_logs(self, search: str = ""):
        """Affiche la fenêtre (et la ramène au premier plan si déjà ouverte)."""
        self.show()
        self.raise_()
        self.activateWindow()
        if search:
            self.logs.search_input.setText(search)
            self.logs._find_next()

    def retranslate_ui(self):
        self.setWindowTitle(tr("logbar_title", "Logs"))
