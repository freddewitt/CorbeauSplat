# Changelog

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
