# Changelog

## [1.2.3] - 2026-07-10

### ✨ New Features (Training)
- **Resume COLMAP**: New "Resume COLMAP" button in the Training tab (Output group). It re-runs the COLMAP reconstruction reusing the images already extracted in `<project>/images`, skipping the expensive frame-extraction and upscaling steps. The previous reconstruction (`sparse/` + `database.db`) is overwritten. Useful when COLMAP failed or needs re-running without redoing extraction/upscale. Chains Brush training automatically if the auto-brush checkbox is checked. Works for both the Gsplat and 360 pipelines (the 360 extractor is not re-run). If no images are found in the project folder, an explicit error is shown and nothing is launched.

### ✨ New Features (Brush training)
- **Custom checkpoints destination**: The Training tab now offers an optional "Checkpoints destination" field. When set, Brush checkpoints are written to `<destination>/<project name>/` instead of the default `<dataset>/checkpoints`, and after a successful training run only the most recent checkpoint `.ply` is kept (intermediate checkpoints and empty folders are removed). Applies to the automatic COLMAP → Brush pipeline; leaving the field empty preserves the previous behaviour (all checkpoints kept). The setting is remembered across sessions and translated in all 9 locales.

### 🐛 Fixes
- **i18n: Training tab widgets not retranslated on language switch**: The "Selection type" label, the Folder/File(s) radio buttons and the "Upscale images" checkbox were missing from `retranslate_ui()`, so they kept their construction-time language when the user switched languages (e.g. leftover Spanish text in a French UI). They are now retranslated like the rest of the tab. Affected all languages equally; translation data itself was already correct.
- **i18n: removed orphan key** `brush_build_mode` from `de.json` (unused, no `tr()` reference) so all 9 locales are key-aligned.

## [1.2.2] - 2026-07-06

### ✨ New Features (SfM / reconstruction)
- **DSP-SIFT as default features**: Default `feature_type` is now `SIFT` with both `estimate_affine_shape` and `domain_size_pooling` enabled — full DSP-SIFT, as recommended by the COLMAP FAQ. More correspondences and more robust matching, at the cost of CPU-side computation. Default `matching_type` is `SIFT_BRUTEFORCE`. (Replaces the `ALIKED_N32` / `ALIKED_LIGHTGLUE` defaults introduced in 1.2.0; ALIKED remains selectable.)
- **Sequential matcher loop detection**: `--SequentialMatching.loop_detection` is enabled for SIFT sequential matching. It closes loops when the camera revisits an already-filmed area (object turntables, looped rooms), avoiding drift and ghost geometry. Enabled for SIFT only — the vocabulary tree it relies on is SIFT-based and incompatible with ALIKED.
- **Vocabulary-tree matcher**: New `matcher_type='vocab_tree'` runs `colmap vocab_tree_matcher`, matching by visual similarity. Far faster than exhaustive matching on large, unordered photo collections (beyond ~500 images). COLMAP downloads and caches the SIFT vocabulary tree on first use.
- **Incremental mapper fallback**: If `global_mapper` (GLOMAP) produces no usable reconstruction, the pipeline now automatically falls back to the incremental `colmap mapper`, restarting from a clean sparse directory. A new `_has_valid_sparse_model()` check verifies that `sparse/0/` holds a complete reconstruction (cameras + images + points3D, `.bin` or `.txt`) before accepting a result — the pipeline never silently returns an empty reconstruction.

### 🛠 Improvements
- **Responsive tabs on short screens**: The Config, 360 Extractor, 4DGS, ML Sharp, and SuperSplat tabs are now wrapped in a `QScrollArea`. Their content stays reachable by scrolling instead of being clipped off the bottom on short displays. Minor word-wrap fixes on the Upscale hints.
- **GUI defaults aligned with the engine**: `params_tab` feature-type / matching-type defaults now match the SIFT / DSP-SIFT engine defaults.

### 🔒 Security
- **`delete_project_content()` safety guard**: The "delete dataset content" action (send-to-trash) now blocks catastrophic targets — the filesystem root (`/`), `$HOME` itself, the application directory, and any ancestor of those (e.g. `/Users`). User project folders (Desktop, Documents, elsewhere) remain deletable. Previously only the exact application directory and `$HOME` were blocked, so `/`, a `$HOME` sub-directory, or a path outside those areas would have been trashed without a guard.

### 🐞 Bug Fixes
- **`adapt_max_splats()` dead thermal branch**: The thermal-reduction logic tested `elif thermal == "warning"`, but `get_thermal_state()` (NSProcessInfo) never returns `"warning"` — it returns `nominal` / `fair` / `serious` / `critical`. The branch was dead, so only `critical` ever reduced the splat budget. Replaced with the real thermal tiers: `fair` → cap factor 0.75, `serious` → 0.5, `critical` → 0.2.
- **Test suite infinite hang**: After the 1.2.1 refactor, `BaseEngine._execute_command()` reads process output via `runner.readline()` in a `while True` loop, but several engine tests still mocked the old `stdout_iter()` API. A bare `MagicMock().readline()` never returns `""` (EOF), so the loop spun forever and the whole suite hung. Test runner mocks now stub `readline` to return EOF.
- **`cv2` mock clobbering the real module session-wide**: Four test modules injected `sys.modules["cv2"] = MagicMock()` unconditionally at import time. When collected before the COLMAP integration tests, this replaced the real (installed) `cv2` for the entire session, breaking `cv2.imread` and making the reconstruction-pipeline tests fail depending on collection order. The stubs now import the real module first and fall back to a mock only when it is genuinely absent (headless CI). Same guard applied to `send2trash`.
- **Stale tests realigned with current behaviour**: the ALIKED default-matching test (now `ALIKED_LIGHTGLUE`), the `SessionManager` fixture (composite `cleaner_export_tab.cleaner_tab` structure from 1.0.6), and the GLB export integration test (now skips gracefully when `trimesh` / `open3d` are absent, since `export()` returns `False` rather than raising).

## [1.2.1] - 2026-07-06

### 🐞 Bug Fixes
- **Brush timeout after 3600s**: `BaseEngine._execute_command()` had a hard-coded wall-clock timeout of 3600s. Brush training on large scenes (30k steps, AI-generated video) regularly exceeds 1h, causing premature termination. Fixed by extending the Brush timeout to 14400s (4h) and making it configurable via `config.json` (`training_timeout`).
- **Inactivity timeout false positives**: Added an `inactivity_timeout` parameter (detects processes with no stdout output for N seconds) that triggered incorrectly on Brush — the trainer has legitimate silent phases (viewer init, checkpoint I/O, heavy computation). Disabled for Brush (`inactivity_timeout=0`). The parameter remains available in `BaseEngine._execute_command()` for other engines.

### 🔧 Changed
- **`BaseEngine._execute_command()`**: New `inactivity_timeout: float = 0` parameter. When > 0, the process is terminated if no stdout line is received for that duration. Wall-clock timeout retained as safety net. Backward compatible — all existing callers unchanged.
- **`config.json`**: Added `"training_timeout": 14400` at the root level (configurable wall-clock timeout for training processes).

### 🛠 Improvements
- **Distinct timeout messages**: Wall-clock and inactivity timeouts now log different messages ("Timeout after Xs (wall-clock)" vs "Inactivity timeout after Xs (no stdout for Ys)"), making it immediately clear which protection triggered.

## [1.2.0] - 2026-07-05

### ✨ New Features
- **Logs tab enhancements**: Added "Copy" button to copy all log content to clipboard, a collapsible search bar with find-next/find-previous navigation, and an auto-scroll lock that lets users scroll up freely during training without being forced back to the bottom.
- **Thermal throttling now optional**: Thermal watchdog and adaptive max_splats reduction are disabled by default. Opt-in via GUI checkbox or `--thermal-throttling` CLI flag.
- **View graph calibration in pipeline**: `view_graph_calibrator` runs automatically between feature matching and `global_mapper`. Copies the database, calibrates intrinsics from the view graph, and feeds the calibrated copy to the mapper. Essential for AI-generated video. Toggle via `--view-graph-calibration` / `--no-view-graph-calibration`.
- **Ignore watermarks option**: `--GlobalMapper.ignore_watermarks` enabled by default. GUI checkbox and `--ignore-watermarks` / `--no-ignore-watermarks` CLI flags.
- **ALIKED + LightGlue as defaults**: Feature type defaults to `ALIKED_N32` and matching to `ALIKED_LIGHTGLUE`. More robust on AI-generated frames with inconsistent geometry or illumination.

### 🔧 Changed
- **glomap → colmap global_mapper**: Removed standalone `glomap` binary, WAL→DELETE SQLite hack, `_convert_db_journal_mode()`, `GlomapEngineDep`, and `use_glomap` parameter. All reconstruction uses `colmap global_mapper`.
- **GlobalMapper option prefix**: Mapper options use `--GlobalMapper.*` instead of `--Mapper.*`.

### 🗑 Removed
- **`force_cpu`**: Dead parameter never wired to COLMAP commands. Removed from params, GUI, config, and all 9 locale files.
- **`min_model_size` and `multiple_models`**: Not supported by `global_mapper`. Removed from all layers.
- **`GlomapEngineDep`**: Deleted from installer. COLMAP 4.0+ includes GLOMAP natively.

### 🐞 Bug Fixes
- Fixed `AttributeError` crash where `self.params.thermal_throttling` was accessed before `self.params` assignment in `ColmapEngine.__init__`.

## [1.1.0] - 2026-07-04

### ✨ New Features
- **SplatTransformEngine**: New autonomous engine wrapping [PlayCanvas `@playcanvas/splat-transform`](https://github.com/playcanvas/splat-transform) v2.7.1 (MIT). Converts between PLY, SPZ, GLB, and CSV formats; supports `--filter-nan` (degenerate splat removal), `--filter-harmonics` (SH band reduction), `--decimate` (point count reduction), and `--morton-order` (spatial reordering for GPU cache efficiency). Installed locally in `engines/splat-transform/` via npm — does not affect global node environment.
  - **Security**: HTTP/HTTPS inputs blocked at engine level (SSRF prevention). Strict flag allowlist (`ALLOWED_FLAGS_BOOLEAN` / `ALLOWED_FLAGS_VALUE`). All paths validated through `BaseEngine.validate_path()`. Arguments always passed as list — no `shell=True`.
  - **GUI tab "SplatTransform"**: input file picker with drag-and-drop, output folder picker, format selector (PLY / SPZ / GLB / CSV), and filter controls. Stop button. i18n (9 languages).
  - **CLI subcommand `splattransform`**: `python3 main.py splattransform -i scene.ply -o ~/out --format spz [--filter-nan] [--filter-harmonics 1] [--decimate 50%] [--morton-order]`
- **Official SPZ export (nianticlabs/spz v3.0.0)**: Replaced the previous homemade SPZ encoder with the official [`nianticlabs/spz`](https://github.com/nianticlabs/spz) Python bindings (MIT, compiled via CMake/nanobind). SPZ files produced by CorbeauSplat are now compatible with standard SPZ viewers.
  - **Breaking change**: Files exported as SPZ by earlier versions used a non-standard format (header `SPZ\0`, no real compression). They are not compatible with the new encoder or standard viewers.
  - The `spz` library is installed into the main `.venv` (not a separate venv) by `setup_dependencies.py`, which clones the repo at tag `v3.0.0` and runs `pip install .`.
  - If `spz` is not installed, the export fails immediately with a clear message pointing to the installer.
- **Post-training options (Entraînement tab)**: Two new checkboxes in the Options section of the Entraînement tab allow chaining PlyCleaner and/or format export automatically after every Brush training run.
  - **"Nettoyer après (PlyCleaner)"** — runs PlyCleaner on all `.ply` files in the output directory; produces `{stem}_cleaned.ply` files (originals preserved). Strength selectable: Léger / Moyen / Fort.
  - **"Exporter ensuite"** — exports the resulting files to SPZ or GLB using ExportEngine (pure Python, no Node.js). Runs only if at least one of the two options is active.
  - Managed by `PostTrainingWorker`, which chains both steps and is interruptible mid-run.
- **Standalone Nettoyage tab**: The former "Nettoyage + Export" composite tab is now a dedicated cleaning-only tab. Single-file or batch-directory cleaning via PlyCleaner — independent of the training pipeline. Format conversion is now handled exclusively by the SplatTransform tab.

### 🗑 Removed
- **`app/core/ply_utils.py`**: All 6 helper functions (`compress_scale`, `compress_rotation`, `compress_alpha`, `write_spz_header`, `write_spz_data`, `parse_ply_manual`) that powered the old homemade SPZ encoder have been removed. The file is now empty and can be deleted.
- **`import math` in `export_engine.py`**: Was only used for the homemade quaternion normalisation in `_export_spz` — removed with the old encoder.
- **ExportTab from composite tab**: Removed the integrated Export section from the Nettoyage tab. Export is now handled by SplatTransform (format conversion) or the post-training pipeline (automatic SPZ/GLB after Brush).

### 🐞 Bug Fixes
- **SuperSplat re-install loop**: `SuperSplatEngineDep.install()` was calling `get_remote_version()` a second time at the end to save the installed version. If that network call failed or timed out, an empty string was written to the version file — causing every subsequent startup to detect a SHA mismatch and prompt for re-install. Fixed by reading the local HEAD SHA via `git rev-parse HEAD` (`_local_head_sha()`) after the git reset — no network dependency.

### 🛠 Improvements
- **Entraînement tab — two-column Options layout**: The Options group now displays reconstruction options (left column) and post-training options (right column) side by side, separated by a vertical divider. Dropdown menus for PlyCleaner strength and export format appear indented below their respective checkboxes, avoiding any horizontal crushing.
- **`PostTrainingWorker`**: New `BaseWorker` subclass that sequences PlyCleaner and ExportEngine after Brush training. Fully interruptible (`isInterruptionRequested()`), streams progress to the log panel, and emits a summary on completion.

## [1.0.6] - 2026-07-04

### ✨ New Features
- **Cleaner + Export tabs merged**: The two separate tabs (Cleaner, Export) are now combined into a single "Clean + Export" composite tab with two visually distinct sections (vertical QSplitter). A "Send to Export" button transfers cleaned files to the export section — disabled by default, enabled only after a successful cleaning run.
  - Single-file mode: transfers the cleaned `.ply` directly to the export file list
  - Batch mode: globs all `.ply` files from the output directory and adds them to the export list
  - Explicit user control: the button never auto-triggers export — the user chooses format and options before clicking "Export"
- **CLI `clean --then-export`**: New `--then-export FORMAT` flag (values: `spz`, `glb`, `obj`, `ply`, `xyz`) chains an automatic multi-format export after cleaning. Optional `--export-output PATH` sets the export destination (defaults to the same directory as the clean output). Reuses `ExportEngine.export()` with default format options.
  - File mode: exports the single cleaned file
  - Directory mode: exports all `.ply` files found in the output directory
  - Example: `python3 main.py clean -i noisy.ply -o cleaned.ply --then-export spz`

### 🐞 Bug Fixes
- **`ExportTab.log_signal` missing**: `ExportTab.log()` called `self.log_signal.emit(msg)` but `log_signal` was never declared as a class attribute — any log call from `ExportEngine` (e.g. on the first progress message) caused an `AttributeError` crash. Added `log_signal = pyqtSignal(str)` to the `ExportTab` class.

### 🛠 Improvements
- **CleanerWorker lifecycle moved to composite tab**: `CleanerExportTab` now manages the `CleanerWorker` thread internally — no longer owned by `main_window.py`. This isolates the worker lifecycle and signal wiring within the composite tab, reducing coupling.
- **Session persistence adapted**: `SessionManager` now references `self.mw.cleaner_export_tab.cleaner_tab` for the cleaner params save/load cycle (previously `self.mw.cleaner_tab`). No state schema change — backward compatible.

### 📖 Documentation
- **CLI.md updated**: New "Chaining (Clean → Export)" subsection with examples and flag table for `--then-export` and `--export-output`.

## [1.0.5] - 2026-07-03

### 🐞 Bug Fixes
- **Cleaner batch mode**: hidden files (Apple Double `._*.ply`) are no longer processed — filtered via `f.name.startswith('.')` in `clean_ply_batch()` and `CleanerWorker.run()`
- **`compute_keep_mask` renamed to `compute_clean_mask`**: more explicit name for the filter mask computation function (used in `ply_cleaner.py` and tests)

## [1.0.4] - 2026-06-30

### 🛠 Improvements
- **GUI path validation relaxed (Option B)**: paths selected via QFileDialog/NSOpenPanel (Browse button) are no longer subject to the `project_root`/`Desktop`/`Documents` containment check. Strict validation is preserved for CLI and manual input. Fixes legitimate user folders being blocked when located outside the 3 allowed directories.

### 🔒 Security
- **`validate_path()` with `gui_trusted`**: GUI paths are now marked as trusted via `engine.gui_trusted = True` in Workers, bypassing the containment check. The CLI remains protected.

## [1.0.3] - 2026-06-26

### ✨ New Features
- **Cleaner tab**: new dedicated tab for cleaning Gaussian Splat .ply files — removes artifacts (transparent splats, oversized splats, outliers) without altering survivors.
  - **Load a .ply file**: selection via native dialog (`QFileDialog`)
  - **Severity combo** (Light / Medium / Strong): three predefined presets (`light`/`medium`/`strong`) with opacity thresholds + scale/distance percentiles
  - **Fine-tuning**: manual override of minimum opacity (0–1), max size in % (90–100), outlier distance in % (90–100)
  - **CLI**: new `clean-ply` subcommand with the same options (`--strength`, `--opacity`, `--scale`, `--outlier`) in `app/cli/commands.py`
  - Dedicated Qt Worker: `CleanerWorker` in `app/gui/workers.py` with progress bar and statistics display
- **Blurry image filtering**: the `select_blurry_files()` function and its parameters (`filter_blurry`, `blur_factor`) are now wired into the full COLMAP pipeline (GUI + CLI).
  - **Strength combo** (Light / Medium / Strong): mapping `light=0.5`, `medium=0.7`, `strong=0.9` for `blur_factor` in `ConfigTab` and CLI `--blur-strength`
  - **Robust mode (large scenes)**: new `--robust` parameter in CLI COLMAP/pipeline + checkbox in `ConfigTab` — applies stable parameters (camera model, matching) to prevent crashes on large datasets

### 🔒 Security
- **Command injection in `restart()`**: replaced `bash -c` with f-string by two direct `subprocess.run()`/`subprocess.Popen()` calls in `AppLifecycle.restart()`. Eliminates shell injection risk via paths containing quotes or spaces.
- **`validate_path()` restricted**: path validation in `BaseEngine` no longer covers the entire `$HOME`, only `project_root` + `Desktop` and `Documents`. Reduces attack surface for sensitive paths.

### 🐞 Bug Fixes
- **SPZ export crashes at runtime**: missing `import math` in `export_engine.py` — `math.sqrt()` was used without importing math. SPZ export is now functional.
- **Blurry image filter inactive**: the `filter_blurry`/`blur_factor` feature and `select_blurry_files()` function were defined and tested but never called in the pipeline. Now wired into `_process_input()` via a new `_filter_blurry_images()` method.

### 🛠 Improvements
- **Timeout in `_execute_command()`**: added a `timeout=3600s` (1h) parameter on external binary execution (COLMAP, Brush, ffmpeg). `TimeoutExpired` kills the process and returns -1, preventing indefinite hangs.
- **Dead code removed**: orphaned `_parse_ply_manual` block (~120 lines, duplicated with `ply_utils.parse_ply_manual()`) removed from `export_engine.py`.
- **Tests updated**: `test_valid_path_inside_home` replaced by `test_valid_path_inside_desktop` and `test_valid_path_inside_documents` to reflect the new path policy.
- **CleanerWorker integrated** into `main_window.py` with `cleanRequested`/`stopRequested` signals, auto-switch to the Logs tab, indeterminate progress bar
- **CleanerTab connected** to `SessionManager` for parameter persistence between sessions
- **CLI `clean-ply`** added to `parser.py` and `commands.py` — supports `--strength`, `--opacity`, `--scale`, `--outlier`
- **`_blur_factor_from_strength()`**: utility function in `commands.py` to convert preset name to float value

### 🧪 Testing
- **224/224 tests pass** (stable, 0 flaky).

## [1.0.2] - 2026-06-26

### ⚡ Apple Silicon Optimizations (10 changes)

This release focuses entirely on macOS Apple Silicon performance, thermal management, and system detection. Every engine and subprocess now runs with ARM64-native awareness.

#### 🔍 System Detection & Diagnostics
- **Rosetta 2 detection**: `is_running_under_rosetta()` checks `sysctl.proc_translated` — warns the user if Python runs under x86_64 translation (20-40% perf penalty).
- **FFmpeg VideoToolbox check**: `check_ffmpeg_videotoolbox()` verifies HW-accelerated decoding is available; suggests `brew reinstall ffmpeg` if missing.
- **NumPy Accelerate verification**: Startup now logs the BLAS backend — confirms Apple Accelerate is active on ARM64.
- **Thermal state monitoring**: `get_thermal_state()` reads `NSProcessInfo.thermalState()` via PyObjC — returns nominal/fair/serious/critical.
- **Function result caching**: `resolve_project_root()` and `is_apple_silicon()` decorated with `@functools.cache` — eliminates redundant calls during engine init and binary resolution.

#### 🧠 Adaptive Resource Management
- **Thermal watchdog**: `BaseEngine._execute_command()` now polls thermal state every 30 seconds during any subprocess execution. If `critical` is detected, the task is stopped gracefully and a warning is logged.
- **Memory-adaptive max_splats**: `BrushEngine.train()` calls `adapt_max_splats()` before launching training. Reduces splat count based on RAM total (<8GB → 50%, <16GB → 75%), memory pressure (>75% → 85%, >85% → 75%), and thermal state (serious → 50%, critical → 20%).
- **Adaptive upscayl tile size**: `UpscaleEngine.load_model()` calculates optimal NCNN tile size from available RAM (<8GB → 256px, 8-16GB → 512px, ≥16GB → auto). Pressure >80% halves the tile to avoid swap.

#### ⚙️ Process & I/O Optimization
- **Background nice value**: `SubprocessRunner.start()` now applies `nice(10)` to all child processes (COLMAP, Brush, Sharp, FFmpeg). On Apple Silicon, this tells the scheduler to prefer E-cores over P-cores, keeping the UI responsive.
- **APFS clonefile for image copies**: `_apfs_copy()` uses `clonefile(2)` via ctypes on macOS APFS volumes — near-instant copy-on-write (30-50% faster on large batches) with automatic fallback to `shutil.copy2`.

### 🛠 Improvements
- **`system.py`**: `check_dependencies()` now also runs `log_numpy_backend()` and `check_ffmpeg_videotoolbox()` for early diagnostics.
- **`brush_engine.py`**: Exposed `_mem_pressure()` static method for external monitoring.
- **`run.command`**: Architecture detection already present — no changes needed.

### 🔧 Internal
- Added `import functools`, `import ctypes`, `import sys` where needed.
- New module-level functions: `is_running_under_rosetta()`, `get_thermal_state()`, `adapt_max_splats()`, `check_ffmpeg_videotoolbox()`, `log_numpy_backend()`, `_apfs_copy()`.
- New base engine methods: `_check_initial_thermal()`, `_check_thermal_abort()`.

## [1.0.1] - 2026-06-18

### 🐞 Bug Fixes
- **4DGS installation fails on Python 3.13 (Issue #6)**: PyAV (`av`) < 14.0.0 has no pre-compiled wheel for Python 3.13 ARM64 and fails to compile with Cython 3.x (stricter `noexcept` signature checks). `install_dependencies()` now pre-installs `av>=14.0.0 --only-binary :all:` before nerfstudio, bypassing Cython compilation entirely.
- **4DGS activation crash on Mac M4 (Issue #5)**: `import subprocess` was missing from `four_dgs_tab.py`. Already fixed in a prior commit. The installation command is now robust with pip upgrade + PyAV wheel pre-install (see above).
- **Test suite flaky failures (20 tests)**: `test_managers.py` patched PyQt6 with bare `MagicMock()` instances, causing `isinstance` checks to raise `TypeError` and `QThread` subclasses to fail with `issubclass() arg 1 must be a class`. Fixed by introducing `tests/conftest.py` with proper class-based mocks (`_MockQThread`, `_MockPyQtSignal`) and a real PyQt6 module hierarchy.
- **`TestColmapWorker.test_stop_calls_engine_stop`**: Missing `worker.process = None` caused `AttributeError` in `BaseWorker.stop()`. Added the missing attribute initialization.

### 🛠 Improvements
- **Installation robustness**: `install_dependencies()` now upgrades pip before installing packages and adds detailed logging for each step.
- **Test infrastructure**: New `tests/conftest.py` provides session-scoped PyQt6 mocking that all test modules share, eliminating module import order issues.

### 🧪 Testing
- **209/209 tests pass** (up from 189/209 with 20 flaky failures).

## [1.0.0] - 2026-06-17

### 🎉 Major Milestone — First Stable Release

After extensive security hardening, architectural refactoring, and comprehensive test coverage, CorbeauSplat reaches version 1.0.0.

### 🔒 Security
- **`checksums.json` populated**: Real SHA256 hashes for Brush, upscayl-bin, and Glomap binaries — download integrity is now enforced (was a no-op on empty hashes).
- **nerfstudio isolated** in dedicated `.venv_4dgs` venv — no longer pollutes the main interpreter with pip installs at runtime.
- **`AppLifecycle.reset_factory()` secured**: Deletion paths are now validated against `project_root` via `relative_to()` before any `shutil.rmtree()` call.
- **`ColmapEngine.delete_project_content()` hardened**: Uses `validate_path()` containment check instead of binary `/` / `$HOME` blocklist.

### 🏗 Architecture
- **`main.py` refactored**: 753 lines → 13 lines. CLI parser extracted to `app/cli/parser.py`, commands to `app/cli/commands.py`, GUI launcher to `app/cli/launcher.py`.
- **`setup_dependencies.py` refactored**: 993 lines → 100 lines. 8 modular installers in `app/scripts/installers/` (`base.py`, `brush.py`, `sharp.py`, `mapping.py`, `supersplat.py`, `extractor_360.py`, `upscayl.py`, `tools.py`).
- **Sharp video logic unified**: `SharpEngine.process_video_frames()` is now the single implementation — both CLI and GUI worker delegate to it.
- **`BrushTab.run_standalone()` fixed**: Now uses `BrushEngine.build_command()` and respects `build_mode` (`--total-steps` vs `--total-train-iters`).
- **13 new modules** created in the refactoring, total codebase now at 38+ files.

### 🧪 Testing
- **Test coverage massively expanded**: from 39 tests to 210+ tests across 11 test files.
- **New test files**: `test_cli.py` (27), `test_colmap_engine.py` (23), `test_upscayl_manager.py` (27), `test_sharp_engine.py` (9), `test_four_dgs_engine.py` (15), `test_setup_dependencies.py` (31), `test_managers.py` (18), `test_workers.py` (20, skip without PyQt6).
- **Coverage by module**: upscayl_manager 90%+, CLI 95%+, ColmapEngine 80%+, SharpEngine 80%+, managers 70%+.

### 📦 Dependency & Quality
- `pyproject.toml` configured with Ruff + MyPy + Pytest (CI-ready).
- `requirements.txt` uses bounded version ranges (`>=X,<Y`) for reproducibility.
- `requirements.lock` with pinned versions for reproducible builds.
- `requirements-dev.txt` for CI/development tooling.
- CI pipeline expanded to 4 jobs: lint, test (3 Python versions), test-gui (macOS), pip-audit.

### 🔒 Security (post-release hardening)
- **Homebrew installation secured**: `run.command` now downloads the install script from a pinned tag (`4.4.23`), verifies its SHA256 checksum before execution, and rejects on mismatch. No more blind `curl | bash`.
- **`checksums.json` completed**: `darwin_rustup` and `linux_rustup` SHA256 fingerprints added (`6c30b75a...`).
- **`ColmapEngine.delete_project_content()` restricted**: Removed `Path.home()` allowance — deletions are now limited to `project_root` only.
- **`DropLineEdit` containment validation**: New `set_allowed_base_dirs()` method. ConfigTab and BrushTab now validate dropped paths against the project root.
- **Upscayl model integrity**: `UpscaylModel.sha256_bin`/`sha256_param` fields added. `verify_integrity()` and post-download SHA256 verification for 3 of 6 models (realesrgan, 4xLSDIR, 4xNomos8kSC).
- **Exception hygiene**: Bare `except:` in `install_node_js()` and `install_build_tools()` replaced with typed `(subprocess.CalledProcessError, OSError)` handlers.

### 🏗 Code Quality
- **`app/core/ply_utils.py` created**: SPZ compression functions and manual PLY parser extracted from `export_engine.py` (722→658 lines) as standalone, testable functions.

## [0.99.5] - 2026-05-13

### 🐞 Bug Fixes
- **COLMAP false update prompt**: Homebrew revision suffixes (e.g., `4.0.4_2`) were not stripped before version comparison, causing a "new version available" prompt on every startup even when COLMAP was up to date. Fixed by normalizing the local version string in `ColmapBrewDep`.
- **Brush binary argument mismatch**: The pre-compiled Brush binary (v0.3.0) renamed `--total-train-iters` to `--total-steps`, causing a crash when using the release build. `BrushEngine.train()` now selects the correct flag based on the configured `build_mode` (`release` vs `source`).
- **SuperSplat update failures**: Corrupted `.git` directories and npm optional-dependency bugs (#4828) caused silent install failures. Added `_git_is_own_repo()` validation and `_npm_install()` retry logic with `node_modules` + `package-lock.json` cleanup.
- **Extractor360Worker crash**: `Extractor360Worker()` was instantiated without required arguments (`input_path`, `output_path`, `params`) in `extractor_360_tab.py`, causing a `TypeError` when running standalone 360° extraction. Fixed by passing all required arguments to the constructor.

### 🛠 Improvements
- **Startup update policy**: COLMAP, Sharp, SuperSplat, and Extractor 360 now prompt the user before updating (same pattern as Brush and Glomap), preventing silent background upgrades.
- **Git safety in launcher**: `run.command` now detects if the local repository is ahead of the remote and skips the pull, preventing accidental overwrite of local commits.

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
- **Tab order**: Training → Brush → SuperSplat → Apple ML Sharp → 4DGS → 360 Extractor → Upscale → COLMAP Parameters → Logs.

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
