"""Two-way binding between a ``RunState`` flag/field and a widget.

Core of the "single source of truth" principle: several widgets (Source,
Reconstruction, Entraînement, modules, top bar) can mirror the same flag or
field. Each is bound to the **same** ``RunState`` — never to an independent
internal state. When one changes, ``RunState`` notifies and all the others
update.

Loop guard: updating from the state uses ``blockSignals`` so as not to
re-trigger ``toggled``/``textChanged``; and ``RunState.set_flag``/``set_field``
only notify on a real change.

``bind_flag_checkbox`` accepts any object with ``isChecked``/``setChecked``/
``blockSignals`` and a ``toggled`` signal with ``connect``. ``bind_text_field``
accepts any object with ``text``/``setText``/``blockSignals`` and a
``textChanged`` signal with ``connect`` — hence testable with a fake widget,
without Qt.
"""


def bind_flag_checkbox(checkbox, run_state, flag):
    """Bind ``checkbox`` to the ``flag`` of ``run_state``, both ways.

    Returns the registered observer (useful to detach it when needed)."""
    checkbox.setChecked(run_state.get_flag(flag))

    def _on_toggled(checked):
        run_state.set_flag(flag, bool(checked))

    checkbox.toggled.connect(_on_toggled)

    def _on_state_changed(key):
        if key != flag:
            return
        checkbox.blockSignals(True)
        checkbox.setChecked(run_state.get_flag(flag))
        checkbox.blockSignals(False)

    run_state.add_observer(_on_state_changed)
    return _on_state_changed


def bind_text_field(line_edit, run_state, field):
    """Bind ``line_edit`` to the ``field`` text field of ``run_state``, both
    ways (same idiom as ``bind_flag_checkbox``, for a ``QLineEdit`` or a
    testable equivalent — ``text``/``setText``/``blockSignals``/``textChanged``).

    Returns the registered observer (useful to detach it when needed)."""
    line_edit.setText(run_state.get_field(field))

    def _on_text_changed(text):
        run_state.set_field(field, text)

    line_edit.textChanged.connect(_on_text_changed)

    def _on_state_changed(key):
        if key != field:
            return
        if line_edit.text() == run_state.get_field(field):
            return
        line_edit.blockSignals(True)
        line_edit.setText(run_state.get_field(field))
        line_edit.blockSignals(False)

    run_state.add_observer(_on_state_changed)
    return _on_state_changed
