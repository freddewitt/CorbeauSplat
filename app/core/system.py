import os
import platform
import shutil
from pathlib import Path

# Common install locations for COLMAP on Windows. The official pre-built
# packages ship a `COLMAP.bat` shim alongside `colmap.exe` in a `bin/` folder.
_WINDOWS_COLMAP_HINTS = (
    r"C:\COLMAP",
    r"C:\Program Files\COLMAP",
    r"C:\Program Files\colmap",
)


def resolve_project_root() -> Path:
    """Finds project root relative to this script (app/core/system.py)"""
    return Path(__file__).resolve().parent.parent.parent


def is_windows() -> bool:
    return os.name == "nt" or platform.system() == "Windows"


def has_cuda() -> bool:
    """Detects an NVIDIA CUDA GPU via the `nvidia-smi` utility."""
    return shutil.which("nvidia-smi") is not None


def get_optimal_threads() -> int:
    """Returns a sensible thread count for compute-heavy work (COLMAP, ffmpeg)."""
    return os.cpu_count() or 4


def _windows_exe_candidates(name: str):
    """Yields plausible executable file names for `name` on Windows."""
    lowered = name.lower()
    if lowered.endswith((".exe", ".bat", ".cmd")):
        yield name
        return
    for ext in (".exe", ".bat", ".cmd"):
        yield name + ext


def _search_subtree(base: Path, exe_names):
    """Returns the first matching executable found anywhere under `base`."""
    if not base.exists():
        return None
    for exe in exe_names:
        for found in base.rglob(exe):
            if found.is_file():
                return str(found)
    return None


def resolve_binary(name):
    """
    Resolves the path of a binary, prioritising the local 'engines' folder
    (including auto-extracted COLMAP/ffmpeg subtrees), then well-known Windows
    install locations, then the system PATH.

    Returns the absolute path (str) or None if not found.
    """
    engines_dir = resolve_project_root() / "engines"

    # 1. Local engines/ folder — accept bare name and Windows extensions
    candidate_names = [name]
    if is_windows():
        candidate_names = list(_windows_exe_candidates(name))
    for cand in candidate_names:
        local_path = engines_dir / cand
        if local_path.exists() and os.access(local_path, os.X_OK):
            return str(local_path)

    # 2. Auto-installed engines extracted into a dedicated subfolder.
    #    COLMAP: prefer colmap.exe — COLMAP.bat cannot be launched directly via
    #    subprocess without a shell. The bundled DLLs are made discoverable
    #    separately (see ColmapEngine.run_command).
    if name == "colmap":
        found = _search_subtree(engines_dir / "colmap", ("colmap.exe", "colmap"))
        if found:
            return found
        if is_windows():
            for hint in _WINDOWS_COLMAP_HINTS:
                found = _search_subtree(Path(hint), ("colmap.exe",))
                if found:
                    return found
    elif name == "ffmpeg":
        found = _search_subtree(engines_dir / "ffmpeg", ("ffmpeg.exe", "ffmpeg"))
        if found:
            return found

    # 3. System PATH. On Windows prefer the .exe so the result is always
    #    launchable via subprocess without a shell.
    if is_windows() and not name.lower().endswith((".exe", ".bat", ".cmd")):
        which_exe = shutil.which(name + ".exe")
        if which_exe:
            return which_exe
    return shutil.which(name)


def get_device() -> str:
    """Centralized device selection: cuda when an NVIDIA GPU is present, else cpu."""
    if has_cuda():
        return "cuda"
    return "cpu"


def get_memory_info() -> dict:
    """Returns total/available/percent memory using OS-native probes.

    On Windows this uses GlobalMemoryStatusEx via ctypes. Falls back to a
    best-effort estimate when the probe is unavailable.
    """
    total = 0
    available = 0
    percent = 0.0

    if is_windows():
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = int(stat.ullTotalPhys)
                available = int(stat.ullAvailPhys)
                percent = float(stat.dwMemoryLoad)
        except (OSError, AttributeError, ValueError):
            pass

    # Cross-platform fallback (also covers non-Windows dev/CI environments)
    if total == 0:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            avail_pages = os.sysconf("SC_AVPHYS_PAGES")
            total = page_size * phys_pages
            available = page_size * avail_pages
            if total > 0:
                percent = round(100.0 * (total - available) / total, 1)
        except (ValueError, OSError, AttributeError):
            pass

    return {"total": total, "available": available, "percent": percent}


def get_brush_build_mode() -> str:
    """Detect Brush build mode from engines/brush.version.

    Returns "release" for tagged versions (e.g. v0.3.0), "source" for
    source builds (e.g. 2a8c4f1-source), defaults to "release".
    """
    version_file = resolve_project_root() / "engines" / "brush.version"
    if version_file.exists():
        version = version_file.read_text().strip()
        if "source" in version:
            return "source"
    return "release"


def check_dependencies():
    """Vérifie si les dépendances nécessaires sont installées"""
    missing = []

    # Check ffmpeg
    if resolve_binary('ffmpeg') is None:
        missing.append('ffmpeg')

    # Check colmap
    if resolve_binary('colmap') is None:
        missing.append('colmap')

    # Check send2trash
    import importlib.util
    if importlib.util.find_spec("send2trash") is None:
        missing.append('send2trash')

    return missing
