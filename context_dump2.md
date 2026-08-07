## app/gui/settings_window.py (213 lignes)
```python
"""Independent general settings window (gear icon in the top bar).

Groups what isn't specific to any one workflow tab: Theme, Language,
Load/Save the full configuration, end-of-run notifications, factory reset.

Anything specific to a single panel (e.g. Brush build mode, COLMAP thermal
throttling) belongs in that panel's own right-side sidebar instead — this
window is for cross-cutting, app-wide settings only.

Theme and Language are functional (styling / i18n, not business logic).
Load/Save and notifications are exposed as signals/state, wired to the
engines elsewhere. Factory reset is wired to ``AppLifecycle``
(``app/gui/managers.py``) — equivalent of the old ``ConfigTab``/``ResetDialog``:
``resetRequested`` is only emitted after explicit confirmation in
``ResetDialog`` (Light/Deep choice or Cancel).

Restart/Quit are no longer here: they are global actions of the main window
(always accessible), moved to ``StudioWindow``'s bottom bar instead of being
buried in this dialog.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.i18n import add_language_observer, get_current_lang, set_language, tr
from app.gui.styles import get_saved_theme, save_theme, set_dark_theme

# (code langue, libellé natif) — miroir de ConfigTab, les 9 locales du projet.
_LANGUAGES = (
    ("fr", "Français"), ("en", "English"), ("de", "Deutsch"), ("it", "Italiano"),
    ("es", "Español"), ("ar", "العربية"), ("ru", "Русский"), ("zh", "中文"),
    ("ja", "日本語"),
)
# (code thème, libellé) — miroir de ConfigTab.
_THEMES = (("slate", "Slate + Indigo"), ("graphite", "Graphite + Teal"), ("blue", "Bleu modernisé"))


class _NoScrollComboBox(QComboBox):
    """Combo box that ignores the wheel unless it holds focus.

    Theme and language are persisted the moment the selection changes, so a
    stray scroll over this dialog would otherwise silently switch the whole UI
    to another language and save it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ResetDialog(QDialog):
    """Confirmation avant réinitialisation aux valeurs d'usine (Light/Deep),
    équivalent de l'ancien ``ConfigTab.ResetDialog``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("btn_reset", "Réinitialisation Usine"))
        self.setMinimumWidth(420)
        self.result_deep = None

        layout = QVBoxLayout(self)

        lbl = QLabel(tr("confirm_reset", "Choisissez le niveau de réinitialisation :"))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.btn_light = QPushButton(tr("reset_light", "Light Reset (Envs)"))
        layout.addWidget(self.btn_light)
        desc_light = QLabel(tr("reset_light_desc", "Supprime les .venv (Python) et relance l'install."))
        desc_light.setWordWrap(True)
        layout.addWidget(desc_light)

        self.btn_deep = QPushButton(tr("reset_deep", "Deep Reset (Factory)"))
        layout.addWidget(self.btn_deep)
        desc_deep = QLabel(tr("reset_deep_desc", "Supprime TOUT (Envs + Engines + Config). Radical."))
        desc_deep.setWordWrap(True)
        layout.addWidget(desc_deep)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self.btn_cancel = QPushButton(tr("btn_cancel", "Annuler"))
        layout.addWidget(self.btn_cancel)

        self.btn_light.clicked.connect(lambda: self._done_with(False))
        self.btn_deep.clicked.connect(lambda: self._done_with(True))
        self.btn_cancel.clicked.connect(self.reject)

    def _done_with(self, deep):
        self.result_deep = deep
        self.accept()


class SettingsWindow(QDialog):
    """Réglages généraux. Émet des signaux pour les actions câblées ailleurs."""

    loadRequested = Signal()
    saveRequested = Signal()
    resetRequested = Signal(bool)
    notificationsToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        self.setModal(False)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # évite débordement horizontal (libellés longs)

        # Thème (fonctionnel)
        self.combo_theme = _NoScrollComboBox()
        self.combo_theme.setMinimumWidth(200)
        self.combo_theme.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for code, label in _THEMES:
            self.combo_theme.addItem(label, code)
        idx = self.combo_theme.findData(get_saved_theme())
        if idx >= 0:
            self.combo_theme.setCurrentIndex(idx)
        self.combo_theme.currentIndexChanged.connect(self._on_theme)
        self.lbl_theme = QLabel(tr("theme_change", "Thème"))
        form.addRow(self.lbl_theme, self.combo_theme)

        # Langue (fonctionnel)
        self.combo_lang = _NoScrollComboBox()
        self.combo_lang.setMinimumWidth(200)
        self.combo_lang.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for code, label in _LANGUAGES:
            self.combo_lang.addItem(label, code)
        idx = self.combo_lang.findData(get_current_lang())
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        self.combo_lang.currentIndexChanged.connect(self._on_lang)
        self.lbl_lang = QLabel(tr("lang_change", "Langue"))
        form.addRow(self.lbl_lang, self.combo_lang)

        # notifications de fin d'exécution
        self.chk_notifications = QCheckBox(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.chk_notifications.toggled.connect(self.notificationsToggled.emit)
        form.addRow(self.chk_notifications)

        layout.addLayout(form)

        # Charger / Sauvegarder la configuration complète (câblage Lot 6)
        self.lbl_current_config = QLabel(tr("settings_current_config", "Paramètres actuels"))
        self.lbl_current_config.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_current_config)
        cfg_row = QHBoxLayout()
        self.btn_load = QPushButton(tr("settings_load", "Charger…"))
        self.btn_load.clicked.connect(self.loadRequested.emit)
        cfg_row.addWidget(self.btn_load)
        self.btn_save = QPushButton(tr("settings_save", "Sauvegarder…"))
        self.btn_save.clicked.connect(self.saveRequested.emit)
        cfg_row.addWidget(self.btn_save)
        layout.addLayout(cfg_row)

        # Reset (Restart/Quit now live in StudioWindow's bottom bar — global
        # actions, not settings).
        self.btn_reset = QPushButton(tr("settings_reset", "Réinitialiser"))
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self.btn_reset)

        self.setWindowTitle(tr("settings_title", "Réglages généraux"))

    # ── Slots fonctionnels ──────────────────────────────────────────────────────
    def _on_theme(self, index):
        name = self.combo_theme.itemData(index)
        if name:
            save_theme(name)
            set_dark_theme(QApplication.instance(), name)

    def _on_lang(self, index):
        code = self.combo_lang.itemData(index)
        if code and code != get_current_lang():
            set_language(code)

    def _on_reset_clicked(self):
        """Réinitialisation destructive : jamais exécutée sans confirmation
        explicite (choix Light/Deep) dans ``ResetDialog``."""
        diag = ResetDialog(self)
        if diag.exec():
            self.resetRequested.emit(diag.result_deep)

    def retranslate_ui(self):
        self.setWindowTitle(tr("settings_title", "Réglages généraux"))
        self.lbl_current_config.setText(tr("settings_current_config", "Paramètres actuels"))
        self.lbl_theme.setText(tr("theme_change", "Thème"))
        self.lbl_lang.setText(tr("lang_change", "Langue"))
        self.chk_notifications.setText(tr("settings_notifications", "Notifications de fin d'exécution"))
        self.btn_load.setText(tr("settings_load", "Charger…"))
        self.btn_save.setText(tr("settings_save", "Sauvegarder…"))
        self.btn_reset.setText(tr("settings_reset", "Réinitialiser"))

```

## app/core/system.py (374 lignes)
```python
import contextlib
import functools
import os
import platform
import shutil
import subprocess
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
                        with contextlib.suppress(ValueError):
                            pages[key] = int(val.strip().rstrip("."))
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


def adapt_max_splats(max_splats: int, thermal_throttling: bool = True) -> int:
    """Reduce *max_splats* under memory pressure or thermal warning.

    On Apple Silicon UMA systems, GPU splats consume the same RAM pool
    as the rest of the system.  Excess splats cause swap → thermal
    throttling → perf collapse.

    Scaling (based on 10M default = ~4 GB VRAM):
      • ≥ 16 GB total → no reduction (full splats)
      •  8-15 GB      → 75% of requested
      •  < 8 GB       → 50% of requested
      •  thermal fair    → cap factor at 0.75
      •  thermal serious → cap factor at 0.5
      •  thermal critical → cap factor at 0.2

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

    # Reduce under thermal warning/critical.
    # get_thermal_state() returns nominal/fair/serious/critical (NSProcessInfo).
    if thermal_throttling:
        thermal = get_thermal_state()
        if thermal == "critical":
            factor = min(factor, 0.2)
        elif thermal == "serious":
            factor = min(factor, 0.5)
        elif thermal == "fair":
            factor = min(factor, 0.75)

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


def log_numpy_backend() -> None:
    """Log the BLAS/LAPACK backend used by NumPy.

    On macOS ARM64 with NumPy >= 1.26, Apple Accelerate is the default
    BLAS backend, giving 2-5x speedup over the reference BLAS for linear
    algebra operations.  This is purely informational — no fix needed if
    Accelerate is active.
    """
    try:
        import contextlib
        import io

        import numpy as np
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            np.show_config()
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

```

## Résumé

Les 2 fichiers demandés ont été trouvés à leur chemin exact, aucun "FICHIER INTROUVABLE".
