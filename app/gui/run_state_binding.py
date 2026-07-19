"""Liaison bidirectionnelle entre un drapeau/champ de ``RunState`` et un widget.

Cœur du principe « source de vérité unique » : plusieurs widgets (Source,
Reconstruction, Entraînement, modules, top bar) peuvent refléter le même
drapeau ou champ. Chacun est bindé au **même** ``RunState`` — jamais un état
interne indépendant. Quand l'un change, ``RunState`` notifie et tous les
autres se mettent à jour.

Anti-boucle : la mise à jour depuis l'état utilise ``blockSignals`` pour ne pas
re-déclencher ``toggled``/``textChanged`` ; et ``RunState.set_flag``/
``set_field`` ne notifient que sur changement réel.

``bind_flag_checkbox`` accepte tout objet ayant ``isChecked``/``setChecked``/
``blockSignals`` et un signal ``toggled`` avec ``connect``. ``bind_text_field``
accepte tout objet ayant ``text``/``setText``/``blockSignals`` et un signal
``textChanged`` avec ``connect`` — donc testables avec un faux widget, sans Qt.
"""


def bind_flag_checkbox(checkbox, run_state, flag):
    """Lie ``checkbox`` au drapeau ``flag`` de ``run_state`` dans les deux sens.

    Retourne l'observateur enregistré (utile pour le détacher au besoin)."""
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
    """Lie ``line_edit`` au champ texte ``field`` de ``run_state`` dans les deux
    sens (même idiome que ``bind_flag_checkbox``, pour un ``QLineEdit`` ou
    équivalent testable — ``text``/``setText``/``blockSignals``/``textChanged``).

    Retourne l'observateur enregistré (utile pour le détacher au besoin)."""
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
