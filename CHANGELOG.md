# Changelog

## [0.99.3] - 2026-04-28

### 🐞 Bug Fixes
- **Batch 1 (critical)**: removed duplicate `super().stop()` call; switched `sqlite3.connect()` to context manager; replaced hardcoded `"ffmpeg"` with `shutil.which()`; moved `frames_dir` cleanup into a `finally` block.
- **Batch 2 (major)**: replaced `input_path`/`input_type` mutations in `ColmapWorker` with engine reconstruction; `SuperSplat.start_supersplat()` now uses `self.runner.start()` instead of raw `subprocess.Popen`; resolved filename collision in `_prepare_images` with an increment counter; fixed duplicate `# 3.` comment in `sharp_engine.py`; replaced raw `str(e)` error messages with full logging + generic user message; replaced `shell=True` for Rust installation with `urlretrieve` + direct execution.
- **Batch 3 (minor)**: `universal_newlines` → `text` in 3 files; removed redundant `bufsize=1`; removed inline `import shutil as _sh` in loop (already imported at module level); replaced double image read in `_check_and_normalize_resolution` with a cache; `cls.__annotations__` → `dataclasses.fields`.
- **Batch 4 + Legacy**: added timeouts to GitHub downloads (`urlretrieve` → `urlopen` with 30-120s timeout); replaced `# noqa: F401` with `importlib.util.find_spec`; added `missing_ok=True` to `unlink()`; removed `app/weights/` directory (2 .pth); cleaned up `[AUDIT]` tags across 6 files.

### 🐞 Bug Fixes (continued)
- **GLOMAP build failure**: switched `-DFETCH_COLMAP=ON` — the Homebrew COLMAP installation does not export the `colmap::colmap` CMake target required by GLOMAP. GLOMAP now builds its own COLMAP; the SQLite WAL crash that originally motivated `FETCH_COLMAP=OFF` is handled by `_convert_db_journal_mode()`.

### 📦 Code Quality
- **23 fixes** applied across 15 files, covering security, maintainability, and performance.

## [0.99.2] - 2026-04-26

### ✨ New Features
- **CLI `pipeline` subcommand**: single command that chains COLMAP reconstruction and Brush training end-to-end. Accepts all essential COLMAP flags (`--type`, `--fps`, `--camera_model`, `--matcher_type`, `--use_glomap`, `--undistort`) and Brush flags (`--preset`, `--iterations`, `--sh_degree`, `--device`, `--with_viewer`). The dataset path is resolved automatically from `--output / --project_name` and passed directly to Brush.
- **CLI restructured as subcommands**: the flat `--train / --predict / --view` flag system is replaced by discrete subcommands (`colmap`, `brush`, `sharp`, `view`, `upscale`, `4dgs`, `extract360`), each with its own `--help` page. No-argument behaviour is unchanged (launches the GUI).
- **CLI — `upscale` subcommand**: new command exposing the full upscayl-bin pipeline from the terminal. Supports single images and folders; flags: `--model`, `--scale` (2/3/4), `--format`, `--tile`, `--tta`, `--compression`.
- **CLI — `4dgs` subcommand**: new command for 4D Gaussian Splatting dataset preparation. Runs frame extraction + Nerfstudio (or COLMAP fallback). `--colmap_only` skips extraction and processes an existing dataset.
- **CLI — `extract360` subcommand**: new command for 360° video extraction. Full flag parity with the GUI tab: `--interval`, `--resolution`, `--camera_count`, `--layout`, `--ai_mask`, `--ai_skip`, `--adaptive`, `--motion_threshold`.
- **CLI `brush` — presets**: `--preset fast / std / dense` applies a curated parameter set in one flag. Individual flags (`--iterations`, `--growth_grad_threshold`, etc.) always override the preset when explicitly passed.
- **CLI `brush` — advanced parameters**: `--start_iter`, `--refine_every`, `--growth_grad_threshold`, `--growth_select_fraction`, `--growth_stop_iter`, `--max_splats`, `--checkpoint_interval`, `--max_resolution`, `--with_viewer`, `--ply_name`, `--custom_args` — full parity with the GUI.
- **CLI `sharp` — video mode**: `--mode video` processes a video frame by frame, writing one `.ply` per frame. `--skip_frames N` processes 1 frame every N. `--upscale` triggers pre-prediction upscaling via upscayl-bin.
- **CLI `view` — URL options**: `--no_ui` hides the SuperSplat interface; `--cam_pos X,Y,Z` and `--cam_rot X,Y,Z` set the initial camera state.
- **CLI `colmap` — advanced parameters**: full parity with the Params tab — `--matcher_type`, `--max_image_size`, `--max_num_features`, `--max_ratio`, `--max_distance`, `--min_model_size`, `--min_num_matches`, `--multiple_models`, `--no_single_camera`, `--no_cross_check`, `--no_domain_size_pooling`, `--estimate_affine_shape`, `--no_refine_focal`, `--refine_principal`, `--no_refine_extra`.

### 🐞 Bug Fixes
- **`--use_glomap` missing from CLI**: the flag was documented in `CLI.md` but never wired into `get_parser()`. Added to the `colmap` subcommand.
- **`run_brush` treated engine return value as a process**: `BrushEngine.train()` returns an `int` (return code) after the engine refactor, but the old `run_brush` iterated over `process.stdout`. Fixed to use the return code directly.

### 📖 Documentation
- **`CLI.md` rewritten**: full reference for all 7 subcommands with flag tables, default values, preset breakdown, and four end-to-end pipeline examples (standard 3DGS, high-quality scan, quick preview, single photo to 3D).

## [0.99.1] - 2026-04-19

### ✨ New Features
- **Upscale tab — redesigned action panel**: the "Quick Test" section is replaced by a full source/destination form with dedicated File and Folder buttons (drag-and-drop supported), a Destination folder picker, and a prominent Upscale button. Both single files and entire folders are supported as input.
- **Scale x1 (quality pass without resolution change)**: available in both the Upscale tab and the Quick Test panel. Upscayl runs at the model's native scale then each output image is resized back to its original dimensions via Pillow LANCZOS, preserving resolution while gaining sharpness.
- **ML Sharp — progress bar**: a slim 6 px progress bar appears below the action buttons while Sharp is running. Image mode shows an indeterminate pulse; video mode fills 0 → 100 % frame by frame.

### 🐞 Bug Fixes
- **upscayl-bin not stopped on user cancel**: `run_upscayl()` now accepts a `cancel_check` callback tested on every stdout line. The subprocess is terminated immediately when the user clicks Stop. Propagated through `UpscaleEngine.upscale_folder()`, `ColmapEngine._run_upscale()`, and `SharpWorker`.
- **GLOMAP crash "SQL logic error"**: two-part fix — (1) `database.db` is deleted before each reconstruction run to avoid leftover WAL artefacts; (2) after COLMAP feature matching the database is converted from WAL to DELETE journal mode (`PRAGMA journal_mode=DELETE`) so GLOMAP's bundled SQLite can open it without crashing.
- **GLOMAP / COLMAP schema mismatch (root cause)**: GLOMAP was compiled with its own COLMAP snapshot (Nov 2025 commit) whose database schema differs from Homebrew COLMAP 4.0.3. The build script now passes `-DFETCH_COLMAP=OFF -DCMAKE_PREFIX_PATH=$(brew --prefix)` so GLOMAP is compiled against the installed COLMAP — schemas match after reinstall.
- **Completion dialogs showed raw i18n key `msg_sharp_done`**: `tr()` returns the key itself when no translation is found. SharpWorker now emits a plain string; `on_sharp_finished` and `on_brush_finished` display dedicated literary messages defined in `fr.json`.

### 🛠 Improvements
- **Literary completion messages**: Sharp and Brush completion dialogs now display evocative French prose instead of technical status strings. Keys added to `fr.json`: `sharp_done_title/body`, `sharp_error_title/body`, `brush_done_title/body`, `brush_error_title/body`.
- **Centralised upscayl-bin call**: `run_upscayl()` in `upscayl_manager.py` is now the single function that builds the command and calls the subprocess. `UpscaleEngine.upscale_folder()` and all workers delegate to it — no duplicate subprocess logic.
- **`resize_to_original()` helper**: added to `upscayl_manager.py`, used by both the Upscale tab test worker and the x1 pipeline in `BrushWorker`.
- **Pillow added to `requirements.txt`** (`>=10.0,<12`) for the x1 resize step.
- **App icon regenerated**: `icon.icns` rebuilt from the current pixel-art crow PNG at all required resolutions (16 → 1024 px). macOS icon cache cleared.
- **Tab order**: Entraînement → Brush → SuperSplat → Apple ML Sharp → 4DGS → 360 Extractor → Upscale → Paramètres COLMAP → Logs.

## [0.99] - 2026-04-19

### 🔒 Security
- **Shell injection closed** (`managers.py`): `AppLifecycle.restart()` was building a shell command with `shell=True` and unsanitized `sys.argv` arguments. Replaced with a safe `Popen` list and a strict allowlist for argv flags.
- **Shell injection closed** (`managers.py`): `AppLifecycle.reset_factory()` was running `rm -rf` via an f-string with `shell=True`. Replaced with a temporary Python subprocess that calls `shutil.rmtree` directly — no shell involved.
- **ffmpeg filter injection** (`workers.py`): `skip_frames` was interpolated into a `-vf select=not(mod(...))` expression without validation. Now clamped to `max(1, int(skip))` before use.
- **`fps` validation** (`four_dgs_engine.py`): `extract_frames()` now clamps fps to `max(1, int(fps))` to prevent divide-by-zero and ffmpeg crashes.

### 🐞 Bug Fixes
- **`NameError: tr` in extractor_360_engine** — `tr()` was called in two places without being imported. Added missing import; previously caused a hard crash at runtime whenever 360 extraction started or finished.
- **`FourDGSWorker.stop()` did not propagate** — `super().stop()` was never called, so `stop_requested` was never set to `True` and the engine loop never interrupted.
- **Upscale format mismatch** (`upscale_engine.py`) — `load_model()` returned key `"format"` but `upscale_folder()` expects `"output_format"`, silently ignoring the user's format setting. Key renamed; output filename in `SharpWorker` now uses the correct extension.
- **Upscale x1 scale added** — `upscale_tab.py` now exposes `x1 (denoise only)` alongside x2/x3/x4; x4 remains default.
- **`upscayl_check_sharp` locale stale** — All 9 locales still referenced `Real-ESRGAN` in the Sharp upscale checkbox label. Updated to `upscayl-ncnn`.
- **`upscale_install_msg` stale** — Five locales mentioned `Torch, RealESRGAN (~2GB)`. Updated to reflect upscayl-bin standalone binary (~30 MB).
- **Stop dialog false positive** — `on_finished` / `on_brush_finished` / `on_process_finished` detected user-requested stops by matching the string `"Arrete"` in the message, which broke silently when messages changed. Replaced with a proper `stopped_by_user` flag on `BaseWorker`.
- **`IndentationError` in `four_dgs_tab.py`** — extra leading space in two `return` statements caused a startup crash. Fixed.

### 🛠 Code Quality (Audit v2026.1)
- **`psutil` removed from `system.py`** — `get_memory_info()` imported `psutil` which was never in `requirements.txt`; replaced with a `sysctl hw.memsize` call.
- **`requirements.txt` pinned** — All 6 dependencies now use `>=X,<Y` range pins instead of unpinned names, preventing silent regressions on major version bumps.
- **Bare `except:` eliminated** — 18 occurrences replaced with typed exceptions (`OSError`, `json.JSONDecodeError`, `subprocess.CalledProcessError`, `TypeError`, etc.) across `i18n.py`, `managers.py`, `setup_dependencies.py`, `base_worker.py`, `workers.py`, and tab files.
- **`print()` replaced by `logging`** — `i18n.py` and `managers.py` now use `logging.getLogger(__name__)` with proper levels (`error`, `warning`, `debug`).
- **`import traceback / subprocess / time / os`** — 10 in-function imports moved to module top-level.
- **i18n coverage improved** — Added `confirm_delete_dataset`, `btn_cancel`, `four_dgs_install_ok`, `err_brush_missing`, `logs_saved`, `upscale_bundled_warning` across all 9 languages. Removed `REALESRGAN_PIP` dead constant from `setup_dependencies.py`.
- **`BaseWorker.stop()`** — Added `stopped_by_user` flag; bare `except` replaced with `except OSError`.
- **Qt signal disconnect** — `except Exception: pass` on `signal.disconnect()` replaced with `except TypeError` (the correct Qt6 exception for disconnecting an unconnected slot).

## [0.98] - 2026-04-19

### ✨ New Features — Upscale Module (complete rewrite)
- **upscayl-ncnn replaces Real-ESRGAN**: The upscale engine now uses `upscayl-bin`, a standalone NCNN-based binary with no Python venv required. No pip dependencies, no build issues.
- **Startup auto-install**: `upscayl-bin` is automatically downloaded from the latest GitHub release at first launch (macOS arm64). Bundled models are extracted alongside.
- **Interactive update prompt**: When a newer version of `upscayl-bin` is detected at startup, the user is asked before updating (same pattern as Brush/Glomap).
- **Model catalogue** (6 curated models, duplicates removed):
  - `Real-ESRGAN x4+` — general ⭐ (bundled)
  - `Real-ESRGAN General` — fast variant (bundled)
  - `4xLSDIR` — ultra fidelity (custom download)
  - `4xNomos8kSC` — texture detail (custom download)
  - `Real-ESRGAN Anime` — stylized content (bundled)
  - `NMKD-Siax` — low-compression sources (custom download)
- **Upscale tab redesign**: scrollable model list with per-model status, download and delete buttons; configuration section (model, scale, format, compression, TTA, tile size); quick test on a single image.
- **"Enable Upscale" moved to Training tab**: the workflow toggle is now in the Training tab alongside other pipeline options (was buried in the Upscale tab).
- **Startup model check**: `on_startup_ready()` logs which models are available and warns if none are installed.
- **Smart model directory detection**: automatically detects models from `./models/upscayl/`, the binary's bundle, or Upscayl.app — no `-m` flag passed when using a system binary.

### 🐞 Bug Fixes
- **Upscale tab crash on startup**: `get_effective_models_dir()` returning `None` caused a `TypeError` in `_ModelCard` — fallback to local models dir prevents the crash.
- **Bundled models now visible in combo**: when `upscayl-bin` is present, bundled models appear in the active model selector even before individual files are downloaded locally.

## [0.96] - 2026-04-17 → 2026-04-18

### ✨ New Features
- **Standalone Brush Launcher**: Added a "Lancer Brush uniquement" button to launch the Brush application independently without feeding any dataset, ideal for visualizing without processing.
- **Enhanced Sharp Video Integration**: The ML Sharp's "Video → PLY" mode is now fully accessible from the main Training (Config) tab, allowing direct conversion of videos skipping the dedicated isolated tab. It introduces an integrated Frame Skip selector directly in the Config tab that correctly syncs with the engine.

### 🛠 Improvements & Fixes
- **UI Alignment & Theming**: Fixed misaligned action buttons in the Brush tab by standardizing Qt stylesheets, ensuring cross-platform native button behaviors do not break the layout.

### 🏗 Upscale Architecture (2026-04-18)
- **Dedicated `.venv_upscale` environment**: Real-ESRGAN and its dependencies (`torch`, `basicsr`, `realesrgan`) are now installed in an isolated Python 3.11 venv, permanently resolving the `basicsr 1.4.2` incompatibility with Python 3.13.
- **Subprocess architecture**: `upscale_engine.py` delegates execution to `upscale_runner.py` via subprocess (same pattern as Sharp). Public API (`load_model`, `upscale_image`, `upscale_folder`) is unchanged. Real-time progress reporting via stdout.
- **Faster `is_installed()` check**: now uses `pip show` instead of importing torch, avoiding a 30-60s startup timeout.
- **5 Upscale module bugs fixed**: `is_installed()` did not actually detect realesrgan; anime model (`RealESRGAN_x4plus_anime_6B`) was unhandled in `load_model()`; `on_toggle_activation()` always disabled the UI even on cancel; model download blocked the GUI thread (moved to `QThread`); dead code and unused import removed.

### 🐞 Bug Fixes (2026-04-18)
- **Brush Engine**: `--max-resolution` and `--refine-pose` were silently blocked by the custom args security whitelist — both flags are now allowed.
- **Brush Tab**: `ply_name` field was never transmitted to the worker nor restored on session reload — both `get_params()` and `set_params()` are now correct.
- **SharpVideoWorker**: Missing FFmpeg now raises a clear user-facing error instead of an unhandled `FileNotFoundError`.
- **Brush Version Detection**: In source build mode, `get_remote_version()` now returns the HEAD commit hash (not the release tag), eliminating a false "update available" prompt on every launch.
- **Glomap Startup**: Version check is now skipped unless `use_glomap=True` in config, removing an unnecessary network call at startup for users who don't use Glomap.
- **`requirements.txt`**: Removed `basicsr`, `facexlib`, `gfpgan`, `realesrgan` (incompatible with Python 3.13, installed on-demand by the upscale engine). Removed `numpy<2` and `urllib3<2` version pins.
- **i18n**: Added 14 missing translation keys across all 9 languages (`btn_launch_supersplat`, `btn_stop_supersplat`, `err_360_*`, `err_sharp`, `err_upscale_*`, `status_360_*`, `status_upscale_done`). Fixed `btn_brush_standalone` which was untranslated in 8 languages.

### ✨ New Features (2026-04-18)
- **SuperSplat Tab**: Simplified to a single toggle button — "Start SuperSplat" launches both servers and automatically opens the browser after 1.5s; the button switches to "Stop SuperSplat" while running.
- **Interactive Update Prompt**: Brush and Glomap now prompt the user at startup when a new version is detected, instead of silently skipping or auto-updating. Other engines (COLMAP, Sharp, Upscale) retain silent auto-update.
- **`--clean` flag for `run.command`**: Running `./run.command --clean` performs a full deep reset (deletes `.venv`, engines, config) with confirmation before launching.
- **Python 3.13 Priority**: `run.command` now tries Python 3.13 and 3.12 before older versions when creating the virtual environment.

## [0.95] - 2026-04-10

### ✨ New Features
- **Video to 3D Sequence (Apple Sharp)**: The Apple Sharp tab now supports converting entire videos into a sequence of `.ply` Gaussian splats.
  - Automatically extracts video frames via FFmpeg.
  - Added an adjustable "Frame Skip" parameter to accelerate long videos and save storage by sampling at precise intervals.
  - The UI now features a dynamic toggle (QStackedWidget) switching seamlessly between "Image → PLY" and "Video → PLY" modes.
- **Global Localization**: Full support for the new Video features integrated into all 9 supported languages (EN, FR, ES, DE, IT, JA, ZH, RU, AR).

## [0.9] - 2026-03-15

### 🏗 Architecture & Codebase Refactoring (Audit V3)
- **SOLID Re-Architecture**: Replaced rigid subprocess execution with `IProcessRunner` abstraction, deeply decoupled the UI from the application state via `SessionManager` and `AppLifecycle`, and simplified the dependency injection mechanism.
- **Security Hardening (OWASP)**: Closed Command Injection flaws in the Brush Engine and eliminated Path Traversal vulnerabilities globally by validating every input and output path against safe directories and characters.
- **Template Method Design**: Eliminated 300+ lines of duplicate execution loops across engines by integrating a unified Template Method parsing execution standard (`_execute_command`).
- **Observability**: Replaced scattered print statements with proper structural logging implementation. Extracted all UI engine feedback strings to the localizer.

### ⚡ Performance optimization
- **UI Responsiveness Engine**: Relocated heavy JSON file write operations out of the main QT GUI loop, completely removing application freezes when checking checkboxes via a debounced write cycle.
- **Micro-management**: Split 150-line God objects and functions into focused, readable modules. Standardized variable names site-wide per Clean Code guidelines.

## [0.81] - 2026-03-15

### ✨ New Features
-   **Advanced Reset Factory**: Introduced a multi-level reset system with a custom, high-visibility dialog.
    -   **Light Reset**: Cleans Python environments (.venv) only.
    -   **Deep Reset**: Full wipe of environments, engine binaries, and configuration files.
-   **Self-Repairing Environments**: `setup_dependencies.py` now automatically detects and repairs broken virtual environments (e.g., caused by Homebrew Python upgrades breaking symlinks).
-   **Direct Source Selection**: Replaced ambiguous popups with persistent radio buttons in the Training tab for "Folder" vs "Files" selection.

### 🛠 Improvements
-   **Reset UI Polish**: Custom styled dialog with large buttons and detailed descriptions for better clarity across all languages.
-   **Maintenance**: Exhaustive cleanup of `.venv_360` and sync-conflict files during resets.

### 🐞 Bug Fixes
-   **`config_tab.py`**: Fixed a critical `IndentationError` and missing imports introduced during the UI refactor that prevented the application from launching after a factory reset.

## [0.8] - 2026-03-10

### ✨ New Features & Languages
-   **Multi-language Expansion**: Added full localization for **Arabic (AR)**, **Russian (RU)**, **Chinese (ZH)**, and **Japanese (JA)**.
-   **Training Mode Selector**: Refactored the "Entraînement" tab to use a dropdown for Training Mode (Gsplat, ML Sharp, 360 Extractor, 4DGS) instead of generic radio buttons, adapting the UI dynamically for each mode.
-   **GSplat Source Type**: Re-added an explicit "Images / Video" selector specifically when Gsplat mode is chosen, to correctly inform the underlying pipeline.
-   **Persistent Input Selection**: Replaced folder/file selection popups with dedicated radio buttons in the Training tab for a smoother, non-intrusive workflow.
-   **Upscale Restoration**: Re-enabled the "Upscale (Real-ESRGAN)" toggle for Gsplat, Sharp, and 360 modes, fully integrated with the progress bar.
-   **Live Progress Bar**: Added a unified progress bar and status indicator for all engine workflows (COLMAP, Sharp, 4DGS, 360).

### 🛠 Improvements
-   **UI Cleanup**: Removed outdated source checkboxes in favor of the unified mode selector.
-   **Localization UI**: Displayed languages in their own native scripts in the language selector.
-   **Apple Silicon Optimization**: Verified and hardcoded robust thread counting (`get_optimal_threads`) avoiding e-cores bottlenecking for C++ processing frameworks.
-   **Code Audit**: Removed dozens of unused, dead, or deprecated imports across `app/`.

### 🐞 Bug Fixes
-   **`UpscaleEngine` Compatibility**: Hotfixed a critical `ModuleNotFoundError` (`torchvision.transforms.functional_tensor`) caused by newer `torchvision` versions (0.15+).
-   **Bus Error 10 on macOS**: Patched a critical SIGBUS crash triggered when `cv2` (and NumPy's Accelerate framework) attempted to natively initialize itself inside a QThread sub-worker. `cv2` is now safely pre-loaded on the main UI thread.

## [0.75] - 2026-03-03

### 🛠 Bug Fixes (Critical)
-   **`engine.py`**: Added missing `from .i18n import tr` import — without it, any cancellation or error during COLMAP processing would crash with a `NameError`.
-   **`four_dgs_engine.py`**: Removed broken `log()` override that called the non-existent `self.logger` attribute (correct name is `self.logger_callback` inherited from `BaseEngine`). Also removed a redundant `stop()` override.
-   **`brush_engine.py`**: Added missing `import signal` — `signal.SIGTERM` was used in `stop()` without being imported, causing a `NameError` on process termination.
-   **`engine.py`**: Removed an unreachable `concurrent.futures.ThreadPoolExecutor` block that appeared after a `return True` statement and was never executed.
-   **`workers.py` — `Extractor360Worker`**: Added missing `__init__` method. The class referenced `self.engine`, `self.input_path`, `self.output_path`, and `self.params` but never assigned them, causing an immediate `AttributeError` on use.
-   **`workers.py` — `FourDGSWorker`**: Fixed `stop()` which wrote to `self._is_running` (wrong attribute, never read) instead of calling `super().stop()` to properly signal thread interruption.

### 🛡 Security
-   **`superplat_engine.py`**: Fixed CORS origin validation — the previous `"localhost" in origin` substring check could be bypassed by a crafted hostname like `evil.localhost.com`. Replaced with strict `urlparse().hostname` comparison.
-   **`extractor_360_engine.py`**: Replaced `env["PYTHONPATH"] = ""` (which broke the subprocess's module resolution) with `env.pop("PYTHONPATH", None)` for clean isolation.
-   **`base_engine.py`**: Narrowed bare `except:` in `is_safe_path()` to `except (TypeError, ValueError, OSError)`.

### ⚡ Apple Silicon Optimization
-   **`system.py` — `get_optimal_threads()`**: Now queries `sysctl hw.perflevel0.logicalcpu` to retrieve the actual **P-core count** on Apple Silicon (e.g. 4 on M1/M2). Previously used an 80% heuristic of total cores, which inadvertently scheduled compute-heavy tasks (COLMAP, ffmpeg) on efficiency cores.

### 🏗 Refactoring & Code Quality
-   **`base_engine.py`**: Extracted shared `_kill_process(process)` helper — consolidates three identical `os.killpg` / `signal.SIGTERM` implementations previously duplicated in `brush_engine`, `superplat_engine`, and `sharp_engine`.
-   **`engine.py`**: Replaced 3× `rglob(ext)` calls (three separate filesystem traversals) with a single `rglob('*')` + `suffix.lower()` filter. Also fixes case-insensitive matching for `.JPG`/`.PNG` extensions. `_IMAGE_EXTS` promoted to module-level constant.
-   **`four_dgs_engine.py`**: Replaced `readline()` while-loop with cleaner `for line in process.stdout:` iteration.
-   **`config_tab.py`**: Removed duplicate `quitRequested = pyqtSignal()` signal definition.
-   **`extractor_360_engine.py`**: Narrowed bare `except:` to `except (ValueError, IndexError)` in progress parsing.

## [0.74] - 2026-03-01

### ✨ Installation & Stability
-   **Brush Engine Optimization**: 
    -   **Native Binaries**: The dependency installer now downloads the official, pre-compiled `v0.3.0` release binaries of Brush for macOS (Apple Silicon), Windows, and Linux rather than building from source. This entirely bypasses the Rust toolchain requirements and typical `cargo` compilation errors.
    -   **Fail-safe Compilation**: If the binary download fails or the platform is unsupported, the `cargo install` fallback is now strictly pinned to tag `v0.3.0` with `--locked` dependencies, preventing build breakages caused by upstream library updates (like the previous `naga` crate issue).

## [0.73] - 2026-02-18

### ✨ New Features
-   **Auto-Update**: Added support for automatic updates of engines (starting with Glomap) via `config.json` (`glomap_auto_update: true`).
-   **Interactive Updates**: Improved update flow to ask the user for confirmation when auto-update is disabled, ensuring no silent failures or skipped updates.

### 🛠 Fixes
-   **Glomap Build**: Fixed CMakeCache errors by automatically cleaning the `build` directory before recompiling.
-   **SuperSplat Update**: Fixed git conflicts (package-lock.json) by forcing a reset before pulling updates.
-   **Dependency Script**: Corrected configuration loading for nested `config` keys.

## [0.72] - 2026-02-07

### Added
- **Multi-language Support**: Extensive localization for **German (DE)**, **Italian (IT)**, and **Spanish (ES)**.
- **Enhanced Translation Engine**: ~1140 total translation keys across all 5 supported languages (FR, EN, DE, IT, ES).
- **UI Localization**: Integrated new language options in the Config tab for real-time switching.

## [v0.71] - 2026-02-07

### ✨ Stability & UX Improvements
- **360 Extraction Workflow**: Implemented recursive image search and automatic AI mask filtering (*.mask.png), resolving the "0 images found" issue.
- **English Startup Experience**: fully translated `run.command` and `setup_dependencies.py` for a consistent first-launch experience.
- **Detailed Component Audit**: Each engine (Sharp, Brush, Glomap, etc.) now reports its individual status (Ready/Missing/Update) during startup with visual markers.
- **UI Visual Hierarchy**: Secondary/Utility tabs now use muted gray coloring to help users focus on the core photogrammetry workflow.
- **Sharp Path Handling**: Hardened absolute path resolution to allow using system folders like the Desktop for output without permission errors.

### 🛠 Bug Fixes
- Fixed missing `shutil` import in the core engine.
- Fixed `TypeError` in command logging for several engines.
- Repaired broken environments for Sharp and 360Extractor after refactor.

## [v0.7] - 2026-02-07

### ✨ New Features (Major)
-   **Live Localization (FR/EN)**:
    -   100% localization coverage achieved for all 10 core UI tabs.
    -   Implemented a robust **Observer Pattern** for real-time language switching.
    -   UI elements now update instantly (labels, tooltips, placeholders, window titles) without requiring an application restart.
-   **Consolidated UI Architecture**: 
    -   Standardized the `retranslate_ui` pattern across the entire application interface.
    -   Centralized all user-facing strings in `i18n.py` for easier future translations.

### 🏗 Architecture & Cleanup
-   **Unified Engine Core**: Consistently using `BaseEngine` across all modules (`Colmap`, `Brush`, `Sharp`, `360`, `4DGS`, `Upscale`, `SuperSplat`).
-   **Worker Refactoring**: Simplified UI workers by offloading command logic to the core engine layer.
-   **Code Hardening**: Improved error handling and path validation in the base engine classes.

### 🛠 Improvements & Fixes
-   **Sync**: Fixed missing or duplicated translation keys in `i18n.py`.
-   **UX**: Improved placeholder clarity and consistency across all tabs.
-   **Versioning**: Standardized project versioning centrally in `app/__init__.py`.

## [v0.6] - 2026-02-06

### ✨ New Features (Major)
-   **360 Extractor Integration (Experimental)**: 
    -   Dedicated module to convert **360° videos** (Equirectangular) into planar images for photogrammetry.
    -   **Smart Extraction**: Supports **YOLO-based masking** to remove the operator/cameraman.
    -   **Adaptive Intervals**: Motion detection to skip static frames.
    -   **Flexible Layouts**: Ring, Cube Map, Fibonacci distribution.
    -   **Seamless Workflow**: Use as a standalone tool or check "360 Source" in Config to pre-process before COLMAP.

## [v0.5] - 2026-02-06

### ✨ New Features (Major)
-   **Multi-Camera Support**: You can now use **multiple video sources** simultaneously to assemble your dataset.
-   **4DGS Restoration**: The experimental 4D Gaussian Splatting module is back! (Dedicated COLMAP pipeline compatible with Nerfstudio).
-   **Optional Activation**: Heavy modules (**Apple ML Sharp** and **Real-ESRGAN Upscale**) are now activated on demand via checkboxes in their respective tabs.
    -   **Disk Space Saving**: Uninstallation possible.
    -   **Faster Startup**: Conditional dependency checks.

### 🛠 Improvements
-   **UX**: Tabs reorganized for better workflow logic.
-   **Setup**: Dependency script now respects user configuration (`config.json`) to avoid unnecessary checks/installations.

## [v0.4] - 2026-01-23

### 🏗 Architecture & Performance (Total Refactor)
-   **Python 3.13+ & JIT**: Added native detection for modern Python versions to enable Free-threading and JIT optimizations.
-   **Apple Silicon Optimization**: 
    -   Rewrite of thread management logic to exploit **Performance Cores** (P-Cores) on Apple Silicon chips without blocking the UI.
    -   Vectorization improvements via `numpy` and native library bindings.
-   **Dual-Environment**: Implemented a dedicated sandbox (`.venv_sharp`) for Apple ML Sharp (Python 3.11) preventing conflicts with the main application (Python 3.13+).
-   **Factory Reset**: Added a "Nuclear Option" in Config Tab to wipe virtual environments and perform a clean re-install.

### ✨ New Features
-   **Factory Reset**: A GUI button to safely delete local environments and restart installation from scratch.
-   **Expert Mode**: New "check_environment_optimization" routine at startup detailed in logs.
-   **Upscale Integration**: Added support for Real-ESRGAN to upscale input images/videos before processing, improving detail release in final splats.

### 🛡 Security & Cleanup
-   **Subprocess Hardening**: Audited and secured shell calls throughout the core engine.
-   **Legacy Code Removal**: Removed deprecated 3.9 compatibility layers.


## [0.3] - 2026-01-21

### Added
- **New 4DGS Module**: Preparation of 4D Gaussian Splatting datasets (Multi-camera video -> Nerfstudio format).
    - Automatic synced frame extraction (camXX).
    - Automated COLMAP pipeline (Features, Matches, Reconstruction).
    - Integration of `ns-process-data`.
- **Optional Activation**: The 4DGS module is disabled by default. A checkbox allows activation and automatically installs **Nerfstudio** (~4GB) in the virtual environment.
- **Smart Check**: 4DGS dependency verification occurs upon activation rather than at startup (improving launch speed).

### Optimized
- **Apple Silicon**: Optimization of the 4DGS engine.
    - FFmpeg hardware acceleration (`videotoolbox`).
    - Multithread management (`OMP`, `VECLIB`) aligned with performance cores.
    - GPU SIFT disabled (often unstable on macOS).

### Fixed
- Fixed a bug with a missing import (`os`) in the system manager.

## [v0.22] - 2026-01-13

### Added
-   **Drag and Drop**: Added support for dragging files and folders into input fields in Config, Brush, and Sharp tabs.
-   **Auto-Detection**: Dragging a video file or folder in Config Tab automatically selects the correct input type.

### Fixed
-   **System Stability**: Fixed a bug where running the application would freeze drag-and-drop operations in macOS Finder.
-   **Python 3.14 Support**: Updated `numpy`, `pyarrow`, and `rerun-sdk` to versions compatible with Python 3.14 on macOS.
-   **Localization**: Fixed missing "Project Name" translation in English.

### Security & Optimization (Audit)
-   **Performance**: Implemented parallel image copying for faster dataset preparation (using `ThreadPoolExecutor`).
-   **Security**: Hardened local data server by restricting CORS to `localhost` origins.
-   **Refactoring**: Moved file deletion logic from GUI to Core engine for better separation of concerns.

## [v0.21] - 2026-01-10

### Fixed
-   **Robust Installation**: Significantly improved the `run.command` launch script.
    -   Silent failures during dependency installation are now detected.
    -   Detailed error logs are shown to the user if installation fails.
    -   Added explicit health check for `PyQt6` to prevent crash-on-launch loops.
-   **Dependency Management**: 
    -   Added `requirements.lock` to ensure reproducible builds.
    -   Added automatic `pip` upgrade check.

## [v0.20] - 2026-01-08

### Added
-   **Dependency Automation**: The installation script now automatically installs missing tools (Rust, Node.js, CMake, Ninja) via Homebrew or official installers, making setup much easier.

### Fixed
-   **Documentation**: Updated README with correct installation instructions and removed manual dependency steps.
-   **Code Safety**: Added safety checks for directory deletion in the "Refine" workflow.
-   **Cleanup**: Removed unused code and improved internal logic.

## [v0.19] - 2026-01-08

### Added
-   **Auto Update Check**: The launcher (`run.command`) now checks for new versions on startup and prompts the user to update.

### Fixed
-   **Dataset Deletion Safety**: Fixed a critical bug where "Delete Dataset" would remove the entire output folder. It now correctly targets the project subdirectory and only deletes its content, preserving the folder structure.

## [v0.18] - 2026-01-07

### Added
-   **Project Workflow**: New "Project Name" field. The application now organizes outputs into a structured project folder (`[Output]/[ProjectName]`) containing `images`, `sparse`, and `checkpoints`.
-   **Auto-Copy Images**: When using a folder of images as input, they are now automatically copied into the project's `columns` directory, ensuring the project is self-contained.
-   **Session Persistence**: The application now saves your settings (paths, parameters, window state) on exit and restores them on the next launch.
-   **Brush Output**: Brush training now correctly targets the project's `checkpoints` directory.
-   **Brush Densification & UI**:
    -   Complete redesign of the Brush tab for better readability.
    -   New "Training Mode" selector: Start from Scratch vs Refine (Auto-resume).
    -   Exposed advanced Densification parameters (hidden by default under "Show Details").
    -   Added Presets for densification strategies (Default, Fast, Standard, Aggressive).
    -   Added specific "Manual Mode" toggle defaulting to "New Training".
-   **UX Improvements**: Reordered tabs (Sharp after SuperSplat), fixed Max Resolution UI, and improved translations.

## [v0.16] - 2026-01-05

### Added
-   **Glomap Integration**: Added support for [Glomap](https://github.com/colmap/glomap) as an alternative Structure-from-Motion (SfM) mapper.
    -   New parameter `--use_glomap` in CLI and "Utiliser Glomap" checkbox in GUI.
    -   Automatic installation checking at startup.
    -   Support for compiling Glomap from source (requires Xcode/Homebrew).

### Changed
-   **Dependency Management**: Refactored `setup_dependencies.py` to improve maintainability and reduce code duplication.
-   **Startup Flow**: The application now intelligently checks for missing engines or updates for all components (Brush, Sharp, SuperSplat, Glomap) at launch.

### Fixed
-   Fixed macOS compilation issues for Glomap by explicitly detecting and linking `libomp` (OpenMP) via Homebrew.

## [v0.15]
-   Initial support for Brush, Sharp, and SuperSplat integration.
