import platform
import os
import shutil
import subprocess
import functools
from pathlib import Path

@functools.cache
def resolve_project_root() -> Path:
    """Finds project root relative to this script (app/core/system.py)

    Cached via @functools.cache since this is called on every engine
    initialization, every config load, and every binary resolution.
    """
    return Path(__file__).resolve().parent.parent.parent

@functools.cache
def is_apple_silicon():
    """Détecte si on est sur Apple Silicon (résultat mis en cache)"""
    return platform.system() == 'Darwin' and platform.machine() == 'arm64'

def is_running_under_rosetta() -> bool:
    """Detect if Python is running under Rosetta 2 translation on Apple Silicon.

    Rosetta 2 translates x86_64 binaries to ARM64, incurring ~20-40% performance
    penalty on compute-heavy workloads (COLMAP, Brush, upscayl).  This check uses
    sysctl.proc_translated which returns '1' when the current process is being
    translated.

    Returns True if running under Rosetta, else False.
    """
    if not is_apple_silicon():
        return False
    try:
        result = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True
    except (subprocess.SubprocessError, OSError):
        pass
    return False


def get_optimal_threads():
    """Retourne le nombre optimal de threads pour Apple Silicon (P-cores) ou autres plateformes"""
    if is_apple_silicon():
        # Apple Silicon has heterogeneous P-cores (performance) + E-cores (efficiency).
        # For compute-heavy tasks (COLMAP, ffmpeg), we prefer P-cores only.
        # Try multiple sysctl keys in order of preference, as not all keys exist
        # on every macOS version or chip generation.
        for key in (
            "hw.perflevel0.logicalcpu",       # P-core logical count (primary)
            "hw.perflevel0.logicalcpu_max",   # P-core logical max (macOS 14+)
            "hw.perflevel0.physicalcpu",      # P-core physical count
            "hw.physicalcpu",                 # total physical cores (P+E)
        ):
            try:
                result = subprocess.run(
                    ["sysctl", "-n", key],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    cores = int(result.stdout.strip())
                    if cores > 0:
                        # hw.physicalcpu includes E-cores; approximate P-only
                        if key == "hw.physicalcpu":
                            cores = max(1, cores // 2)
                        return cores
            except (ValueError, subprocess.SubprocessError, OSError):
                continue
        # Absolute fallback: os.cpu_count() includes both P and E logical cores;
        # divide by 2 as a conservative P-core estimate (M1: 8→4✓, M1Pro: 10→5≈,
        # M1Max: 10→5≈, M2Pro: 12→6≈, M3Max: 16→8≈, M4Max: 16→8≈).
        cpu_count = os.cpu_count() or 8
        return max(1, cpu_count // 2)
    return os.cpu_count() or 4

def resolve_binary(name):
    """
    Résoud le chemin d'un binaire en priorisant le dossier 'engines' local.
    Retourne le chemin absolu ou le nom si trouvé dans le PATH, sinon None.
    """
    # 1. Chercher dans le dossier engines à la racine du projet
    engines_dir = resolve_project_root() / "engines"
    
    local_path = engines_dir / name
    
    # Cas binaire direct
    if local_path.exists() and os.access(local_path, os.X_OK):
        return str(local_path)
        
    # Cas macOS .app bundle pour COLMAP
    if name == "colmap":
        colmap_app = engines_dir / "COLMAP.app" / "Contents" / "MacOS" / "colmap"
        if colmap_app.exists() and os.access(colmap_app, os.X_OK):
            return str(colmap_app)
            
    # 2. Chercher dans le PATH système
    return shutil.which(name)

def get_device() -> str:
    """Centralized device selection: mps, cuda, or cpu."""
    if is_apple_silicon():
        return "mps"
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    return "cpu"

def get_memory_info() -> dict:
    """Returns memory info for UMA/caching strategies via sysctl + vm_stat.

    On Apple Silicon (UMA), memory_pressure is the most reliable indicator
    since GPU and CPU share the same pool.
    """
    total = 0
    available = 0
    percent = 0.0

    # Total physical memory
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=2
        )
        total = int(result.stdout.strip()) if result.returncode == 0 else 0
    except (ValueError, subprocess.SubprocessError, OSError):
        pass

    # Available memory: use vm_stat to get free + inactive + speculative pages.
    # On Apple Silicon UMA, compressed/inactive pages are effectively "available"
    # since the memory compressor frees them on demand.
    if total > 0:
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                page_size = 16384  # Apple Silicon default page size
                pages = {}
                for line in result.stdout.splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip().strip('"')
                        try:
                            pages[key] = int(val.strip().rstrip("."))
                        except ValueError:
                            pass
                # Page size detection
                if "page size of" in result.stdout:
                    for token in result.stdout.split():
                        try:
                            page_size = int(token)
                            break
                        except ValueError:
                            pass
                free_pages = pages.get("Pages free", 0)
                inactive_pages = pages.get("Pages inactive", 0)
                speculative_pages = pages.get("Pages speculative", 0)
                available_pages = free_pages + inactive_pages + speculative_pages
                available_bytes = available_pages * page_size
                # Clamp to total (vm_stat can report more than hw.memsize
                # if compression reclaims pages from other categories)
                available = min(available_bytes, total)
                percent = round(100.0 * (total - available) / total, 1)
        except (ValueError, subprocess.SubprocessError, OSError):
            pass

    return {"total": total, "available": available, "percent": percent}


def get_thermal_state() -> str:
    """Return the current macOS thermal state via NSProcessInfo.

    On macOS 10.10.3+, NSProcessInfo.thermalState returns an enum:

        NSProcessInfoThermalStateNominal   (0) → "nominal"
        NSProcessInfoThermalStateFair      (1) → "fair"
        NSProcessInfoThermalStateSerious   (2) → "serious"
        NSProcessInfoThermalStateCritical  (3) → "critical"

    On Apple Silicon, sustained compute loads (Brush training, COLMAP
    feature extraction, upscayl) can trigger Fair → Serious → Critical
    after 5-15 minutes of full P-core usage, especially on fanless
    MacBook Air.

    Uses PyObjC (pyobjc-framework-Cocoa, already a dependency) since
    the raw IOKit symbol is not exposed via dlsym on modern macOS.

    Returns one of "nominal", "fair", "serious", "critical", or
    "unknown" on non-macOS platforms.
    """
    if not is_apple_silicon():
        return "unknown"
    try:
        from Foundation import NSProcessInfo
        level = NSProcessInfo.processInfo().thermalState()
        mapping = {0: "nominal", 1: "fair", 2: "serious", 3: "critical"}
        return mapping.get(level, f"unknown({level})")
    except Exception:
        return "unknown"


def adapt_max_splats(max_splats: int) -> int:
    """Reduce *max_splats* under memory pressure or thermal warning.

    On Apple Silicon UMA systems, GPU splats consume the same RAM pool
    as the rest of the system.  Excess splats cause swap → thermal
    throttling → perf collapse.

    Scaling (based on 10M default = ~4 GB VRAM):
      • ≥ 16 GB total → no reduction (full splats)
      •  8-15 GB      → 75% of requested
      •  < 8 GB       → 50% of requested
      •  thermal warning → additional 25% reduction
      •  thermal critical → cap at 2M hard limit

    Returns the adapted max_splats value (never below 500_000).
    """
    mem = get_memory_info()
    total_gb = mem.get("total", 0) / (1024 ** 3)
    pressure = mem.get("percent", 0.0)

    factor = 1.0
    if total_gb < 8:
        factor = 0.5
    elif total_gb < 16:
        factor = 0.75

    # Reduce further under high memory pressure
    if pressure > 85:
        factor *= 0.75
    elif pressure > 75:
        factor *= 0.85

    # Reduce under thermal warning/critical
    thermal = get_thermal_state()
    if thermal == "critical":
        factor = min(factor, 0.2)
    elif thermal == "warning":
        factor = min(factor, 0.5)

    adapted = int(max_splats * factor)
    return max(500_000, adapted)


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


def is_amx_available() -> bool:
    """Detect whether the Apple Matrix coprocessor (AMX) is available.

    AMX is present on all Apple Silicon chips (M1 and later) and is used
    automatically by Accelerate.framework for BLAS/LAPACK operations.
    No user-space configuration is needed — this is purely informational
    for feature gating and logging.
    """
    if not is_apple_silicon():
        return False
    # All Apple Silicon chips have AMX blocks.  The AMX instruction set
    # is accessed exclusively through Accelerate.framework (not directly
    # by user code), so there is no sysctl key to query.  We return True
    # for any arm64 Darwin system.
    return True


def has_neural_engine() -> bool:
    """Detect whether the Apple Neural Engine (ANE) is available.

    The Neural Engine is present on M1 and later Apple Silicon chips,
    as well as A12 Bionic and later iPhone/iPad SoCs.  It is used
    transparently by CoreML when the model and compute unit selection
    allow it (`.appleNeuralEngine`).

    On macOS, there is no official sysctl key to query ANE presence,
    so we check for Apple Silicon as a proxy (all M-series chips have one).
    """
    if not is_apple_silicon():
        return False
    # M1 and later all include a Neural Engine. The exact core count
    # varies (M1: 16-core, M2: 16-core, M3: 16-core, M4: 16-core,
    # M1 Pro/Max: 16-core, M2 Pro/Max: 16-core, M3 Pro/Max: 16-core,
    # M4 Pro/Max: 16-core). No user-space API exposes the count.
    return True


def log_numpy_backend() -> None:
    """Log the BLAS/LAPACK backend used by NumPy.

    On macOS ARM64 with NumPy >= 1.26, Apple Accelerate is the default
    BLAS backend, giving 2-5x speedup over the reference BLAS for linear
    algebra operations.  This is purely informational — no fix needed if
    Accelerate is active.
    """
    try:
        import numpy as np
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            config = np.show_config()
        config_text = buf.getvalue()
        if "accelerate" in config_text.lower():
            print("🔢 NumPy BLAS: Apple Accelerate (optimal)")
        elif "openblas" in config_text.lower():
            print("🔢 NumPy BLAS: OpenBLAS")
        elif "lapack" in config_text.lower():
            print("🔢 NumPy BLAS: LAPACK/BLAS (reference)")
        else:
            print("🔢 NumPy BLAS: unknown (see numpy.show_config())")
    except Exception:
        pass  # NumPy may not be installed in headless/CLI-only mode


def check_ffmpeg_videotoolbox() -> bool:
    """Check if the installed FFmpeg supports VideoToolbox hardware acceleration.

    VideoToolbox provides hardware-accelerated H.264/H.265 decoding on
    Apple Silicon.  Without it, FFmpeg decodes video on CPU, which is
    3-5x slower and generates more heat.

    Returns True if VideoToolbox is available, False otherwise.
    Logs a warning if FFmpeg is present but lacks VideoToolbox support.
    """
    ffmpeg_bin = resolve_binary("ffmpeg")
    if not ffmpeg_bin:
        print("⚠️  FFmpeg introuvable — vérification VideoToolbox impossible.")
        return False

    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-hwaccels"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            hwaccels = result.stdout.lower()
            if "videotoolbox" in hwaccels:
                if is_apple_silicon():
                    print("🎬 FFmpeg: VideoToolbox disponible (accélération HW) ✓")
                return True
            else:
                print(
                    "⚠️  FFmpeg installé SANS VideoToolbox. "
                    "Réinstallez avec : brew reinstall ffmpeg"
                )
                return False
    except (subprocess.SubprocessError, OSError):
        pass
    return False


def check_dependencies():
    """Vérifie si les dépendances nécessaires sont installées

    Returns:
        list[str]: Missing dependencies (empty if all good).
    """
    import warnings

    # Warn if running under Rosetta 2 (x86_64 translation on Apple Silicon)
    if is_running_under_rosetta():
        warnings.warn(
            "Python s'exécute sous Rosetta 2 (traduction x86_64). "
            "Les performances seront dégradées de 20 à 40% sur les tâches "
            "COLMAP, Brush et upscayl. Utilisez un interpréteur Python "
            "ARM64 natif. Conseil : python3.13 (native) depuis homebrew.",
            RuntimeWarning,
            stacklevel=1
        )

    # Vérification NumPy Accelerate (macOS ARM64)
    log_numpy_backend()

    # Vérification FFmpeg VideoToolbox
    check_ffmpeg_videotoolbox()

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
