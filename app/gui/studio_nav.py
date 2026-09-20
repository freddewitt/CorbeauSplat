"""Studio navigation logic, kept out of Qt so it stays testable.

Classes inheriting from a Qt widget cannot be instantiated under the tests'
PySide6 mock (they become MagicMocks). So the pure logic — page mapping, current
selection, collapsed state — is extracted here, and the rail and the Studio
window delegate to it. These objects are testable in CI; the Qt rendering stays
validated manually on Apple Silicon.
"""


class PageRegistry:
    """Map each rail item key to a page index (centre/right) and remember the
    current selection."""

    def __init__(self, keys):
        keys = list(keys)
        self._index = {k: i for i, k in enumerate(keys)}
        self.current = keys[0] if keys else None

    def index_of(self, key):
        """Index of the page, or None when the key is unknown."""
        return self._index.get(key)

    def select(self, key):
        """Select a page. Returns its index, or None (selection unchanged) when
        the key is unknown."""
        index = self._index.get(key)
        if index is None:
            return None
        self.current = key
        return index

    def keys(self):
        return list(self._index)

    def as_dict(self):
        return dict(self._index)
