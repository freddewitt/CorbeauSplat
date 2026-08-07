"""Independent general settings window (gear icon in the top bar).

Groups what isn't specific to any one workflow tab: Theme, Language,
Load/Save the full configuration, end-of-run notifications, factory reset.

Anything specific to a single panel (e.g. Brush build mode, COLMAP thermal
throttling) belongs in that panel's own right-side sidebar instead — this
window is for cross-cutting, app-wide settings only.

Theme and Language are functional (styling / i18n, not business logic).
Load/Save and notifications are exposed as signals/state, wired to the
engines elsewhere. Factory reset is wired to ``AppLifecycle``
(``app/gui/managers.py``) — equivalent of the old ``ConfigTab``/``ResetDialog``:
``resetRequested`` is only emitted after explicit confirmation in
``ResetDialog`` (Light/Deep choice or Cancel).

Restart/Quit are no longer here: they are global actions of the main window
(always accessible), moved to ``StudioWindow``'s bottom bar instead of being
buried in this dialog.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.i18n import add_language_observer, get_current_lang, set_language, tr
from app.gui.styles import get_saved_theme, save_theme, set_dark_theme

# (code langue, libellé natif) — miroir de ConfigTab, les 9 locales du projet.
_LANGUAGES = (
    ("fr", "Français"), ("en", "English"), ("de", "Deutsch"), ("it", "Italiano"),
    ("es", "Español"), ("ar", "العربية"), ("ru", "Русский"), ("zh", "中文"),
    ("ja", "日本語"),
)
# (code thème, libellé) — miroir de ConfigTab.
_THEMES = (("slate", "Slate + Indigo"), ("graphite", "Graphite + Teal"), ("blue", "Bleu modernisé"))


class _NoScrollComboBox(QComboBox):
    """Combo box that unconditionally ignores the mouse wheel.

    Theme and language are persisted the moment the selection changes, so a
    stray scroll over this dialog would otherwise silently switch the whole UI
    to another language and save it. Selection must go through a click on the
    dropdown list instead — clicking the closed combo also gives it focus, so
    a focus-based check was not a reliable guard here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class ResetDialog(QDialog):
    """Confirmation avant réinitialisation aux valeurs d'usine (Light/Deep),
    équivalent de l'ancien ``ConfigTab.ResetDialog``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("btn_reset", "Réinitialisation Usine"))
        self.setMinimumWidth(420)
        self.result_deep = None

        layout = QVBoxLayout(self)

        lbl = QLabel(tr("confirm_reset", "Choisissez le niveau de réinitialisation :"))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.btn_light = QPushButton(tr("reset_light", "Light Reset (Envs)"))
        layout.addWidget(self.btn_light)
        desc_light = QLabel(tr("reset_light_desc", "Supprime les .venv (Python) et relance l'install."))
        desc_light.setWordWrap(True)
        layout.addWidget(desc_light)

        self.btn_deep = QPushButton(tr("reset_deep", "Deep Reset (Factory)"))
        layout.addWidget(self.btn_deep)
        desc_deep = QLabel(tr("reset_deep_desc", "Supprime TOUT (Envs + Engines + Config). Radical."))
        desc_deep.setWordWrap(True)
        layout.addWidget(desc_deep)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self.btn_cancel = QPushButton(tr("btn_cancel", "Annuler"))
        layout.addWidget(self.btn_cancel)

        self.btn_light.clicked.connect(lambda: self._done_with(False))
        self.btn_deep.clicked.connect(lambda: self._done_with(True))
        self.btn_cancel.clicked.connect(self.reject)

    def _done_with(self, deep):
        self.result_deep = deep
        self.accept()


class SettingsWindow(QDialog):
    """Réglages généraux. Émet des signaux pour les actions câblées ailleurs."""

    loadRequested = Signal()
    saveRequested = Signal()
    deleteRequested = Signal()
    resetRequested = Signal(bool)
    notificationsToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)

        # Thème (fonctionnel)
        self.combo_theme = _NoScrollComboBox()
        self.combo_theme.setMinimumWidth(200)
        self.combo_theme.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for code, label in _THEMES:
            self.combo_theme.addItem(label, code)
        idx = self.combo_theme.findData(get_saved_theme())
        if idx >= 0:
            self.combo_theme.setCurrentIndex(idx)
        self.combo_theme.currentIndexChanged.connect(self._on_theme)
        self.lbl_theme = QLabel(tr("theme_change", "Thème"))
        form.addRow(self.lbl_theme, self.combo_theme)

        # Langue (fonctionnel)
        self.combo_lang = _NoScrollComboBox()
        self.combo_lang.setMinimumWidth(200)
        self.combo_lang.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for code, label in _LANGUAGES:
            self.combo_lang.addItem(label, code)
        idx = self.combo_lang.findData(get_current_lang())
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        self.combo_lang.currentIndexChanged.connect(self._on_lang)
        self.lbl_lang = QLabel(tr("lang_change", "Langue"))
        form.addRow(self.lbl_lang, self.combo_lang)

        # notifications de fin d'exécution
        self.chk_notifications = QCheckBox(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.chk_notifications.toggled.connect(self.notificationsToggled.emit)
        form.addRow(self.chk_notifications)

        layout.addLayout(form)

        # Charger / Sauvegarder la configuration complète (câblage Lot 6)
        self.lbl_current_config = QLabel(tr("settings_current_config", "Paramètres actuels"))
        self.lbl_current_config.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_current_config)
        cfg_row = QHBoxLayout()
        self.btn_load = QPushButton(tr("settings_load", "Charger…"))
        self.btn_load.clicked.connect(self.loadRequested.emit)
        cfg_row.addWidget(self.btn_load)
        self.btn_save = QPushButton(tr("settings_save", "Sauvegarder…"))
        self.btn_save.clicked.connect(self.saveRequested.emit)
        cfg_row.addWidget(self.btn_save)
        self.btn_delete_config = QPushButton(tr("settings_delete", "Supprimer…"))
        self.btn_delete_config.clicked.connect(self.deleteRequested.emit)
        cfg_row.addWidget(self.btn_delete_config)
        layout.addLayout(cfg_row)

        # Reset (Restart/Quit now live in StudioWindow's bottom bar — global
        # actions, not settings).
        self.btn_reset = QPushButton(tr("settings_reset", "Réinitialiser"))
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self.btn_reset)

        self.setWindowTitle(tr("settings_title", "Réglages généraux"))

    # ── Slots fonctionnels ──────────────────────────────────────────────────────
    def _on_theme(self, index):
        name = self.combo_theme.itemData(index)
        if name:
            save_theme(name)
            set_dark_theme(QApplication.instance(), name)

    def _on_lang(self, index):
        code = self.combo_lang.itemData(index)
        if code and code != get_current_lang():
            set_language(code)

    def _on_reset_clicked(self):
        """Réinitialisation destructive : jamais exécutée sans confirmation
        explicite (choix Light/Deep) dans ``ResetDialog``."""
        diag = ResetDialog(self)
        if diag.exec():
            self.resetRequested.emit(diag.result_deep)

    def retranslate_ui(self):
        self.setWindowTitle(tr("settings_title", "Réglages généraux"))
        self.lbl_current_config.setText(tr("settings_current_config", "Paramètres actuels"))
        self.lbl_theme.setText(tr("theme_change", "Thème"))
        self.lbl_lang.setText(tr("lang_change", "Langue"))
        self.chk_notifications.setText(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.btn_load.setText(tr("settings_load", "Charger…"))
        self.btn_save.setText(tr("settings_save", "Sauvegarder…"))
        self.btn_reset.setText(tr("settings_reset", "Réinitialiser"))
