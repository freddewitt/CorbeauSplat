"""Planification du run pipeline (chaînage conditionnel), isolée de Qt.

Décide, selon le mode (Gsplat / Sharp / 4DGS) et les drapeaux de ``RunState``,
la liste ordonnée des étapes à exécuter au clic sur « Lancer ». Logique pure,
donc testable sous le mock PySide6 (le prompt Lot 3 demande explicitement de
tester ce chaînage conditionnel).

Règles :
- **Extraction 360** : intercalée juste après Source si ``source_360`` — elle
  convertit une source équirectangulaire en un *nouveau* dossier d'images
  planaires, que les étapes suivantes consomment à la place de la source.
- **Upscale** : intercalé entre Source et Reconstruction si ``upscaler_avant``
  (il agrandit les images *avant* que COLMAP ne les lise), tous modes confondus.
- **Gsplat** : Source → Reconstruction (COLMAP), puis Entraînement (Brush) si
  ``entrainement_apres`` ; les post-étapes suivent leurs propres toggles.
- **Sharp** : Source → Reconstruction (inférence Sharp, pas d'Entraînement),
  puis post-étapes selon toggles.
- **4DGS** : tronqué à Source → (Extraction 360) → (Upscale) → Reconstruction (pas de sortie .ply
  exploitable).
"""

_MODES = ("gsplat", "sharp", "4dgs")


def plan_pipeline(mode, run_state):
    """Retourne la liste ordonnée des clés d'étapes à exécuter."""
    if mode not in _MODES:
        mode = "gsplat"

    # Pré-étape optionnelle : elle doit précéder Reconstruction, sinon COLMAP
    # aurait déjà consommé les images d'origine.
    pre_steps = ["source"]
    # Ordre imposé par les données : l'extraction 360 produit le dossier
    # d'images planaires que l'upscale agrandit ensuite, et que COLMAP lit.
    if run_state.source_360:
        pre_steps.append("extraction360")
    if run_state.upscaler_avant:
        pre_steps.append("upscale")

    if mode == "4dgs":
        return [*pre_steps, "reconstruction"]

    steps = [*pre_steps, "reconstruction"]

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
