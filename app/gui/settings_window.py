"""Independent general settings window (gear icon in the top bar).

Groups what isn't specific to any one workflow tab: Theme, Language,
end-of-run notifications, plus an app identity footer (name/version and a
changelog link).

Anything specific to a single panel (e.g. Brush build mode, COLMAP thermal
throttling) belongs in that panel's own right-side sidebar instead — this
window is for cross-cutting, app-wide settings only.

Load/Save/Delete of the full configuration and the factory reset now live in
``SourcePanel``'s right sidebar (Settings block, below Automation) — they are
project-workflow actions the user reaches for right where they work, not
app-wide preferences. ``ResetDialog`` (Light/Deep choice) still lives in this
module and is reused from ``StudioWindow`` for that button.

Theme and Language are functional (styling / i18n, not business logic).
Notifications are exposed as signals/state, wired to the engines elsewhere.

Restart/Quit are no longer here: they are global actions of the main window
(always accessible), moved to ``StudioWindow``'s bottom bar instead of being
buried in this dialog.
"""

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
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

from app import VERSION
from app.core.i18n import add_language_observer, get_current_lang, set_language, tr
from app.core.system import resolve_project_root
from app.gui.styles import get_saved_theme, save_theme, set_dark_theme

# (language code, native label) — mirrors ConfigTab, the project's 9 locales.
_LANGUAGES = (
    ("fr", "Français"), ("en", "English"), ("de", "Deutsch"), ("it", "Italiano"),
    ("es", "Español"), ("ar", "العربية"), ("ru", "Русский"), ("zh", "中文"),
    ("ja", "日本語"),
)
# (theme code, label) — mirrors ConfigTab.
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
    """Confirmation before resetting to factory values (Light/Deep),
    equivalent of the old ``ConfigTab.ResetDialog``."""

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
    """General settings. Emits signals for actions wired elsewhere."""

    notificationsToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # avoid horizontal overflow (long labels)

        # Theme (functional)
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

        # end-of-run notifications
        self.chk_notifications = QCheckBox(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.chk_notifications.toggled.connect(self.notificationsToggled.emit)
        form.addRow(self.chk_notifications)

        layout.addLayout(form)
        layout.addStretch(1)

        # Footer: app identity (name + version) and a changelog link, pinned
        # to the bottom via the stretch above, centered and set apart from
        # the form with extra top margin so it doesn't crowd the last row.
        footer = QVBoxLayout()
        footer.setContentsMargins(0, 24, 0, 0)
        footer.setSpacing(4)

        self.lbl_app_identity = QLabel(f"CorbeauSplat v{VERSION}")
        self.lbl_app_identity.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lbl_app_identity.setStyleSheet("color: #666666; font-size: 10px;")
        footer.addWidget(self.lbl_app_identity)

        self.btn_changelog = QPushButton(tr("settings_changelog_link", "Voir le changelog"))
        self.btn_changelog.setFlat(True)
        self.btn_changelog.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_changelog.setStyleSheet(
            "border: none; padding: 0; color: #7aa2f7; font-size: 10px;"
        )
        self.btn_changelog.clicked.connect(self._open_changelog)
        changelog_row = QHBoxLayout()
        changelog_row.addStretch(1)
        changelog_row.addWidget(self.btn_changelog)
        changelog_row.addStretch(1)
        footer.addLayout(changelog_row)

        layout.addLayout(footer)

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

    def _open_changelog(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolve_project_root() / "CHANGELOG.md")))

    def retranslate_ui(self):
        self.setWindowTitle(tr("settings_title", "Réglages généraux"))
        self.lbl_theme.setText(tr("theme_change", "Thème"))
        self.lbl_lang.setText(tr("lang_change", "Langue"))
        self.chk_notifications.setText(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.btn_changelog.setText(tr("settings_changelog_link", "Voir le changelog"))
