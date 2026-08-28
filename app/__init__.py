# Orthographe PEP 440 valide : normalisée en "2.0.0b1" par packaging/setuptools,
# donc identique à la version de pyproject.toml, mais plus lisible dans la barre
# du bas (AppBar affiche f"v{VERSION}").
VERSION = "2.0.0-beta.3"

# Pillow's decompression-bomb guard is meant for untrusted uploads on a server.
# This is a local desktop tool processing the user's own photogrammetry/drone
# images, which routinely exceed the default 89-megapixel heuristic — disable
# it here (before any submodule imports PIL) instead of at each call site.
import PIL.Image  # noqa: E402

PIL.Image.MAX_IMAGE_PIXELS = None
