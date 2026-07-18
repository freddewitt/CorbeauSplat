"""Logique de navigation du Studio, isolée de Qt pour être testable.

Les classes qui héritent d'un widget Qt ne sont pas instanciables sous le mock
PySide6 des tests (elles deviennent des MagicMock). On extrait donc ici la
logique pure — mapping des pages, sélection courante, état de repli — que le
rail, la logbar et la fenêtre Studio délèguent. Ces objets sont testables en CI ;
le rendu Qt reste validé manuellement sur Apple Silicon.
"""


class PageRegistry:
    """Associe chaque clé d'item du rail à un index de page (centre/droite) et
    mémorise la sélection courante."""

    def __init__(self, keys):
        keys = list(keys)
        self._index = {k: i for i, k in enumerate(keys)}
        self.current = keys[0] if keys else None

    def index_of(self, key):
        """Index de la page, ou None si la clé est inconnue."""
        return self._index.get(key)

    def select(self, key):
        """Sélectionne une page. Retourne son index, ou None (sélection
        inchangée) si la clé est inconnue."""
        index = self._index.get(key)
        if index is None:
            return None
        self.current = key
        return index

    def keys(self):
        return list(self._index)

    def as_dict(self):
        return dict(self._index)


class CollapseState:
    """État de repli d'une section (OUTILS, barre de logs). Repliée par défaut."""

    def __init__(self, collapsed=True):
        self.collapsed = bool(collapsed)

    def set(self, collapsed):
        self.collapsed = bool(collapsed)
        return self.collapsed

    def toggle(self):
        self.collapsed = not self.collapsed
        return self.collapsed
