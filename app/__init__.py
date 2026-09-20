# Valid PEP 440 spelling: normalized to "2.0.0b1" by packaging/setuptools,
# so identical to pyproject.toml's version, but more readable in the
# bottom bar (AppBar displays f"v{VERSION}").
VERSION = "2.0.0-beta.5"

# Pillow's decompression-bomb guard is meant for untrusted uploads on a server.
# This is a local desktop tool processing the user's own photogrammetry/drone
# images, which routinely exceed the default 89-megapixel heuristic — so keep
# the guard armed but set a generous ceiling here (before any submodule imports
# PIL) instead of at each call site. 500 Mpx sits above every realistic source
# frame and upscale intermediate (the x1 path reopens ~289 Mpx outputs), while
# Pillow still refuses anything above 2x = 1 Gpx at Image.open, before decode.
import PIL.Image  # noqa: E402

PIL.Image.MAX_IMAGE_PIXELS = 500_000_000
