# Changelog

## [v0.22] - 2026-01-13

### Fixed
-   **Python 3.14 Support**: Updated `numpy`, `pyarrow`, and `rerun-sdk` to versions compatible with Python 3.14 on macOS.
-   **Localization**: Fixed missing "Project Name" translation in English.

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
