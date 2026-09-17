# Valid PEP 440 spelling: normalized to "2.0.0b1" by packaging/setuptools,
# so identical to pyproject.toml's version, but more readable in the
# bottom bar (AppBar displays f"v{VERSION}").
VERSION = "2.0.0-beta.4"

# Pillow's decompression-bomb guard is meant for untrusted uploads on a server.
# This is a local desktop tool processing the user's own photogrammetry/drone
# images, which routinely exceed the default 89-megapixel heuristic — disable
# it here (before any submodule imports PIL) instead of at each call site.
import PIL.Image  # noqa: E402

PIL.Image.MAX_IMAGE_PIXELS = None
