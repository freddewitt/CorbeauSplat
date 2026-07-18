"""Planification du run pipeline (chaînage conditionnel), isolée de Qt.

Décide, selon le mode (Gsplat / Sharp / 4DGS) et les drapeaux de ``RunState``,
la liste ordonnée des étapes à exécuter au clic sur « Lancer ». Logique pure,
donc testable sous le mock PySide6 (le prompt Lot 3 demande explicitement de
tester ce chaînage conditionnel).

Règles :
- **Gsplat** : Source → Reconstruction (COLMAP), puis Entraînement (Brush) si
  ``entrainement_apres`` ; les post-étapes suivent leurs propres toggles.
- **Sharp** : Source → Reconstruction (inférence Sharp, pas d'Entraînement),
  puis post-étapes selon toggles.
- **4DGS** : tronqué à Source → Reconstruction (pas de sortie .ply exploitable).
"""

_MODES = ("gsplat", "sharp", "4dgs")


def plan_pipeline(mode, run_state):
    """Retourne la liste ordonnée des clés d'étapes à exécuter."""
    if mode not in _MODES:
        mode = "gsplat"

    if mode == "4dgs":
        return ["source", "reconstruction"]

    steps = ["source", "reconstruction"]

    # Entraînement : Gsplat uniquement, et seulement si demandé.
    if mode == "gsplat" and run_state.entrainement_apres:
        steps.append("entrainement")

    # Post-étapes optionnelles, communes Gsplat/Sharp, pilotées par leurs toggles.
    if run_state.nettoyer_apres:
        steps.append("nettoyage")
    if run_state.exporter_apres:
        steps.append("export")
    if run_state.visualiser_apres:
        steps.append("visualiser")

    return steps
