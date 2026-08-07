"""Bouton d'arrêt, placé sous le bouton Lancer de chaque panneau.

L'arrêt vivait dans la barre du bas — héritage de l'architecture précédente, où
la barre de logs portait l'action. Il est désormais au contact du bouton qui a
déclenché le travail : c'est là qu'on le cherche.

Le bouton se retraduit lui-même. Neuf panneaux en portent un ; autant éviter neuf
lignes identiques dans neuf ``retranslate_ui()``, qui auraient fini par diverger
(``splat_transform_panel`` avait justement oublié celle de son ``btn_run``, d'où
un bouton sans texte).
"""

from PySide6.QtWidgets import QPushButton

from app.core.i18n import add_language_observer, tr


class CancelButton(QPushButton):
    """Désactivé tant qu'aucun worker ne tourne — ``StudioWindow`` l'active."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEnabled(False)
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setText(tr("topbar_cancel", "Annuler"))
