"""Panneaux réels des étapes/​modules du Studio.

Chaque panneau expose deux widgets — ``center`` (zone centrale) et ``right``
(barre de droite) — insérés dans les ``QStackedWidget`` du ``StudioWindow``.
Un panneau est un objet plain (pas un widget Qt) pour rester découplé de
l'assemblage de la fenêtre.
"""
