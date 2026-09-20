"""Real panels of the Studio steps/modules.

Each panel exposes two widgets — ``center`` (central zone) and ``right`` (right
bar) — inserted into the ``QStackedWidget`` of ``StudioWindow``. A panel is a
plain object (not a Qt widget) so it stays decoupled from the window assembly.

Since the right bar was merged into the centre (essential then advanced settings
grouped in ``center``, held in a ``QScrollArea``), ``right`` is an empty
``QWidget()`` with no layout attached for the panels concerned
(``ReconstructionPanel``, ``EntrainementPanel``, ``CleanerPanel``,
``ExportPanel``, ``VisualiserPanel``). ``StudioWindow`` will be able to detect
that state (``right.layout() is None``) to hide the right column/separator when
it is empty — that detection is still to be implemented on the ``StudioWindow``
side, this module only exposes the structural precondition.
"""
