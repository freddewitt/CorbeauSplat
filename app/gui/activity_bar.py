"""Barre d'activité, en bas de la fenêtre Studio.

Remplace l'ancienne ``LogBar``. Le journal n'est plus ici — il a sa propre
fenêtre (``logs_window.py``), ouverte par un bouton de la barre du bas. Ne reste
que ce qu'on veut voir en permanence sans rien ouvrir :

    Reconstruction   Feature extraction: image 42/210   [████░░ 42%]

L'arrêt n'est plus ici : il vit sous le bouton Lancer de chaque panneau
(``widgets/cancel_button.py``), au contact de l'action qu'il interrompt.

- **l'étape** en cours (libellé du rail, donc traduit) ;
- **le détail** de ce qu'elle fait à l'instant : dernière ligne remontée par le
  worker, tronquée au milieu — les chemins de fichiers se ressemblent tous par
  la gauche, c'est la fin qui identifie la ligne ;
- **la progression**, uniquement pour les workers qui en émettent une. COLMAP,
  360, Sharp vidéo et Export le font ; l'entraînement Brush non (son moteur ne
  reçoit qu'un ``logger_callback``), d'où une barre masquée dans ce cas plutôt
  qu'une barre figée à 0 % qui laisserait croire à un blocage.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QWidget,
)

from app.core.i18n import add_language_observer
from app.gui.styles import DEFAULT_THEME, THEMES, get_saved_theme

# Résolu à l'import, comme dans rail.py : styles.py ne diffuse pas de signal de
# changement de thème auquel un widget vivant pourrait s'abonner.
_MUTED = THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])["muted"]


class ActivityBar(QWidget):
    """Étape courante + détail + progression. Toujours visible, sans action."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail = ""
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(10)

        self.lbl_step = QLabel()
        self.lbl_step.setStyleSheet("font-weight: 600; background: transparent;")
        row.addWidget(self.lbl_step)

        self.lbl_detail = QLabel()
        self.lbl_detail.setStyleSheet(f"color: {_MUTED}; background: transparent;")
        self.lbl_detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        row.addWidget(self.lbl_detail, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        row.addWidget(self.progress)

    # ── Étape et détail ─────────────────────────────────────────────────────────
    def set_step(self, label):
        """Étape en cours, libellé déjà traduit (cf. ``rail.item_label``)."""
        self.lbl_step.setText(str(label or ""))

    def set_activity(self, message):
        """Détail courant. Branché à la fois sur ``log_signal`` et
        ``status_signal`` : ``BrushWorker`` n'émet que le premier, se limiter au
        statut laisserait l'entraînement sans le moindre retour visible."""
        text = str(message or "").strip()
        self._detail = text.splitlines()[-1] if text else ""
        self._refresh_detail()

    def _refresh_detail(self):
        fm = self.lbl_detail.fontMetrics()
        width = max(120, self.lbl_detail.width())
        self.lbl_detail.setText(
            fm.elidedText(self._detail, Qt.TextElideMode.ElideMiddle, width)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_detail()

    # ── Progression ─────────────────────────────────────────────────────────────
    def set_progress(self, value):
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, int(value))))

    def reset_activity(self):
        """Fin de run : ni libellé résiduel, ni barre figée sur sa dernière valeur."""
        self._detail = ""
        self.lbl_step.clear()
        self.lbl_detail.clear()
        self.progress.setValue(0)
        self.progress.setVisible(False)

    def retranslate_ui(self):
        """Rien à retraduire aujourd'hui : l'étape et le détail sont poussés
        déjà traduits par ``StudioWindow``. Conservée pour rester abonnable au
        changement de langue si un libellé fixe apparaît ici."""
