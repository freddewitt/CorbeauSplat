"""Recognised media formats, shared by every source-scanning site.

A single list so the GUI (source type detection), ColmapEngine (frame
extraction, image ingest) and FourDGSEngine (multi-camera scan) always agree on
what counts as a video and what counts as an image. FFmpeg demuxes every
container listed here, so the source never has to be converted by hand.

Images are trickier: COLMAP reads far more than upscayl-ncnn or OpenCV do, and
nothing in the stack reads HEIC. Rather than maintain a per-tool matrix, any
image outside ``NATIVE_IMAGE_EXTENSIONS`` is converted once on ingest (cf.
``convert_image``), so every downstream step only ever sees JPEG or PNG.
"""
import logging
import pathlib
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = frozenset({
    # Common consumer containers
    ".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".wmv", ".asf",
    ".flv", ".f4v",
    # MPEG program/transport streams (camcorders, drones, screen captures)
    ".mpg", ".mpeg", ".mpe", ".m1v", ".m2v", ".mts", ".m2ts", ".ts", ".vob",
    # Broadcast / pro
    ".mxf", ".dv",
    # Mobile and 360 cameras
    ".3gp", ".3g2", ".insv",
    # Others FFmpeg handles natively
    ".ogv", ".ogg", ".divx", ".rm", ".rmvb",
})


def is_video_file(path) -> bool:
    """True when ``path`` has a recognised video container extension.

    Case-insensitive: iPhone footage arrives as ``.MOV``, action cameras as
    ``.MP4``. Accepts anything with a ``suffix`` attribute (``Path``) or a
    string path.
    """
    return _suffix_of(path) in VIDEO_EXTENSIONS


def without_hwaccel(cmd):
    """Same FFmpeg argv, minus the ``-hwaccel <backend>`` pair.

    VideoToolbox refuses a few streams that FFmpeg decodes fine in software
    (ProRes or 10-bit HEVC inside a ``.mov``, some interlaced transport
    streams). Retrying with this instead of failing keeps every container
    usable.
    """
    out = []
    skip_next = False
    for token in cmd:
        if skip_next:
            skip_next = False
            continue
        if token == "-hwaccel":
            skip_next = True
            continue
        out.append(token)
    return out


# Formats every downstream step reads (COLMAP, OpenCV, upscayl, Sharp, Brush).
NATIVE_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})

# Formats accepted as a source. Everything beyond the native ones is converted
# on ingest: some are refused by upscayl (.tif, .bmp, .tga), one is refused by
# COLMAP (.jp2), and HEIC is refused by both OpenCV and Pillow — yet all of
# them decode fine on macOS, so none of them has to be rejected.
IMAGE_EXTENSIONS = NATIVE_IMAGE_EXTENSIONS | frozenset({
    ".tif", ".tiff", ".bmp", ".webp", ".ppm", ".pgm", ".pnm", ".tga",
    ".jp2", ".gif", ".heic", ".heif",
})

# Formats Pillow cannot open here (no HEIF plugin in either venv); macOS ``sips``
# decodes them natively, so no extra dependency is needed.
_SIPS_ONLY_EXTENSIONS = frozenset({".heic", ".heif"})

CONVERSION_FORMATS = ("png", "jpeg", "off")

_FORMAT_SUFFIX = {"png": ".png", "jpeg": ".jpg"}


def is_image_file(path) -> bool:
    """True when ``path`` has a recognised image extension."""
    return _suffix_of(path) in IMAGE_EXTENSIONS


def image_file_filter() -> str:
    """Qt file-dialog filter listing every accepted image extension."""
    patterns = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTENSIONS))
    return f"Images ({patterns})"


def needs_image_conversion(path) -> bool:
    """True when ``path`` must be converted before the pipeline can use it."""
    suffix = _suffix_of(path)
    return suffix in IMAGE_EXTENSIONS and suffix not in NATIVE_IMAGE_EXTENSIONS


def conversion_suffix(fmt: str) -> str:
    """File suffix written for ``fmt`` ("png" → ``.png``, "jpeg" → ``.jpg``)."""
    return _FORMAT_SUFFIX.get(fmt, ".png")


def convert_image(src, dest, fmt: str = "png") -> bool:
    """Re-encode *src* into *dest* as PNG or JPEG. Returns True on success.

    EXIF is carried over: COLMAP reads the focal length from it to initialise
    the intrinsics (verified for both JPEG and PNG output), and without it it
    falls back on a rough ``1.2 x max(width, height)`` guess.
    """
    suffix = _suffix_of(src)
    if suffix in _SIPS_ONLY_EXTENSIONS:
        return _convert_with_sips(src, dest, fmt)
    try:
        from PIL import Image

        with Image.open(src) as im:
            exif = _exif_bytes(im)
            if fmt == "jpeg":
                out = im.convert("RGB")
                out.save(dest, "JPEG", quality=95, subsampling=0, **({"exif": exif} if exif else {}))
            else:
                has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
                out = im.convert("RGBA" if has_alpha else "RGB")
                out.save(dest, "PNG", **({"exif": exif} if exif else {}))
        return True
    except Exception as exc:  # unreadable, truncated, exotic colour space…
        logger.debug("Pillow could not convert %s (%s) — trying sips", src, exc)
        return _convert_with_sips(src, dest, fmt)


def _exif_bytes(im):
    """EXIF payload of an open image, or None.

    ``info["exif"]`` is empty for TIFF, where Pillow exposes the tags through
    ``getexif()`` instead — reading both keeps the camera metadata (focal
    length above all) whatever the source format.
    """
    try:
        exif = im.getexif()
        if len(exif):
            return exif.tobytes()
    except Exception:  # malformed EXIF must never fail the conversion
        pass
    return im.info.get("exif")


def _convert_with_sips(src, dest, fmt: str) -> bool:
    """Convert through macOS ``sips`` (the only HEIC decoder available here)."""
    sips = shutil.which("sips")
    if not sips:
        return False
    try:
        result = subprocess.run(  # nosec B603 - fixed binary, paths are ours
            [sips, "-s", "format", "png" if fmt != "jpeg" else "jpeg",
             str(src), "--out", str(dest)],
            capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("sips failed on %s: %s", src, exc)
        return False
    return result.returncode == 0 and _exists_nonempty(dest)


def _exists_nonempty(path) -> bool:
    try:
        return path.stat().st_size > 0
    except (AttributeError, OSError):
        import os

        return os.path.isfile(path) and os.path.getsize(path) > 0


def _suffix_of(path) -> str:
    suffix = getattr(path, "suffix", None)
    if suffix is None:
        text = str(path)
        dot = text.rfind(".")
        suffix = text[dot:] if dot > text.replace("\\", "/").rfind("/") else ""
    return suffix.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Video probing and preview, for the in/out range selection
# ─────────────────────────────────────────────────────────────────────────────

def probe_video_duration(path) -> float | None:
    """Duration of `path` in seconds, or None when it cannot be determined.

    Uses ffprobe rather than a Qt media player: ffmpeg is already a hard
    dependency and reads every container in VIDEO_EXTENSIONS, while Qt's
    backend silently fails on several of them (.mts, .insv, .mxf).
    """
    ffprobe = shutil.which("ffprobe") or _sibling_of_ffmpeg("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(  # nosec B603 - fixed argv, no shell
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.debug("ffprobe failed on %s: %s", path, e)
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def extract_preview_frame(path, timestamp: float, dest, width: int = 640) -> bool:
    """Write a single JPEG of `path` at `timestamp` seconds into `dest`.

    `-ss` is placed before `-i` so ffmpeg seeks by keyframe instead of decoding
    from the start: scrubbing a long video stays responsive. The frame can
    therefore land slightly before the requested timestamp, which is acceptable
    for a preview — the extraction itself uses the exact value.
    """
    ffmpeg = shutil.which("ffmpeg") or _sibling_of_ffmpeg("ffmpeg")
    if not ffmpeg:
        return False
    dest = str(dest)
    cmd = [ffmpeg, "-y", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(path),
           "-frames:v", "1", "-vf", f"scale={width}:-2", "-qscale:v", "3", dest]
    try:
        result = subprocess.run(  # nosec B603 - fixed argv, no shell
            cmd, capture_output=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.debug("preview extraction failed at %.3fs: %s", timestamp, e)
        return False
    return result.returncode == 0 and _exists_nonempty(dest)


def _sibling_of_ffmpeg(name: str) -> str | None:
    """Find `name` next to the resolved ffmpeg, for bundled installs."""
    from .system import resolve_binary

    ffmpeg = resolve_binary("ffmpeg")
    if not ffmpeg:
        return None
    candidate = pathlib.Path(ffmpeg).parent / name
    return str(candidate) if candidate.exists() else None


def format_timecode(seconds: float) -> str:
    """Render seconds as MM:SS.s, or H:MM:SS.s past an hour."""
    seconds = max(0.0, float(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{int(hours)}:{int(minutes):02d}:{secs:04.1f}"
    return f"{int(minutes):02d}:{secs:04.1f}"


# Recognised, in order: "H:MM:SS.s", "MM:SS.s", "SS.s". A bare number is read
# as seconds, so "90" and "1:30" both mean the same instant.
_TIMECODE_RE = re.compile(
    r"^\s*(?:(?:(?P<h>\d+):)?(?P<m>\d{1,2}):)?(?P<s>\d{1,2}(?:[.,]\d+)?)\s*$"
)


def parse_timecode(text) -> float | None:
    """Read a typed timecode into seconds, or None when it is not one.

    The inverse of ``format_timecode``, so a value shown in the interface can
    be copied back in. Returns None rather than raising: callers are editable
    fields, where a half-typed value is normal and must not be treated as an
    error.
    """
    if text is None:
        return None
    match = _TIMECODE_RE.match(str(text))
    if not match:
        return None
    hours = int(match.group("h") or 0)
    minutes = int(match.group("m") or 0)
    seconds = float(match.group("s").replace(",", "."))
    if minutes > 59 or (match.group("m") and seconds >= 60):
        return None
    return hours * 3600 + minutes * 60 + seconds


# Containers whose seeking and preview are dependable enough not to warn about.
# Everything else in VIDEO_EXTENSIONS still works, but keyframe layout in the
# broadcast and action-camera formats (.mts, .insv, .mxf) makes a scrubbed
# frame land further from the requested instant.
PREFERRED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov"})


def is_preferred_video(path) -> bool:
    """True when the container is one seeking handles precisely."""
    return _suffix_of(path) in PREFERRED_VIDEO_EXTENSIONS
