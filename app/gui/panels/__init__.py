"""Panneaux réels des étapes/​modules du Studio.

Chaque panneau expose deux widgets — ``center`` (zone centrale) et ``right``
(barre de droite) — insérés dans les ``QStackedWidget`` du ``StudioWindow``.
Un panneau est un objet plain (pas un widget Qt) pour rester découplé de
l'assemblage de la fenêtre.

Depuis la fusion de la barre de droite dans le centre (réglages essentiels
puis avancés regroupés dans ``center``, contenu dans un ``QScrollArea``),
``right`` est un ``QWidget()`` vide sans layout attaché pour les panneaux
concernés (``ReconstructionPanel``, ``EntrainementPanel``, ``CleanerPanel``,
``ExportPanel``, ``VisualiserPanel``). ``StudioWindow`` pourra détecter cet
état (``right.layout() is None``) pour masquer la colonne/le séparateur de
droite quand elle est vide — cette détection reste à implémenter côté
``StudioWindow``, ce module ne fait qu'exposer la précondition structurelle.
"""
