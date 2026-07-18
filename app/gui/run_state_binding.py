"""Liaison bidirectionnelle entre un drapeau de ``RunState`` et une case à cocher.

Cœur du principe « source de vérité unique » : plusieurs cases (Source,
Reconstruction, Entraînement, modules) peuvent refléter le même drapeau. Chacune
est bindée au **même** ``RunState`` — jamais un état interne indépendant. Quand
l'une change, ``RunState`` notifie et toutes les autres se mettent à jour.

Anti-boucle : la mise à jour depuis l'état utilise ``blockSignals`` pour ne pas
re-déclencher ``toggled`` ; et ``RunState.set_flag`` ne notifie que sur
changement réel.

La fonction accepte tout objet ayant ``isChecked``/``setChecked``/
``blockSignals`` et un signal ``toggled`` avec ``connect`` — donc testable avec
un faux widget, sans Qt.
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
