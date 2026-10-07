# Kept identical to pyproject.toml's version; the bottom bar shows
# f"v{VERSION}" (AppBar).
VERSION = "2.0.1"

# Size the in-process NumPy/Accelerate thread pools (PLY cleaning) to the
# P-cores. These variables are only read when NumPy first loads, so they must
# be set here, before any submodule imports it. Values already exported by the
# user are kept.
import os as _os  # noqa: E402

from .core.system import compute_env as _compute_env  # noqa: E402

for _key, _value in _compute_env({}).items():
    _os.environ.setdefault(_key, _value)

# Pillow's decompression-bomb guard is meant for untrusted uploads on a server.
# This is a local desktop tool processing the user's own photogrammetry/drone
# images, which routinely exceed the default 89-megapixel heuristic — so keep
# the guard armed but set a generous ceiling here (before any submodule imports
# PIL) instead of at each call site. 500 Mpx sits above every realistic source
# frame and upscale intermediate (the x1 path reopens ~289 Mpx outputs), while
# Pillow still refuses anything above 2x = 1 Gpx at Image.open, before decode.
import PIL.Image  # noqa: E402

PIL.Image.MAX_IMAGE_PIXELS = 500_000_000
