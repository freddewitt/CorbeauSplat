"""Stop button, placed under the Launch button of every panel.

Stopping used to live in the bottom bar — a leftover of the previous
architecture, where the log bar carried the action. It now sits next to the
button that started the work: that is where people look for it.

The button retranslates itself. Nine panels carry one; better that than nine
identical lines in nine ``retranslate_ui()``, which would have ended up drifting
apart (``splat_transform_panel`` had precisely forgotten the one for its
``btn_run``, hence a button with no text).
"""

from PySide6.QtWidgets import QPushButton

from app.core.i18n import add_language_observer, tr


class CancelButton(QPushButton):
    """Disabled while no worker runs — ``StudioWindow`` enables it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEnabled(False)
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setText(tr("topbar_cancel", "Annuler"))
