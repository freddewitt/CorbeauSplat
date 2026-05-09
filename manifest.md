# CorbeauSplat — Project Manifest

> Version 0.99.3 — macOS Apple Silicon Gaussian Splatting Pipeline

## Identity

- **Purpose**: All-in-one GUI + CLI tool for Gaussian Splatting 3D reconstruction on macOS
- **Author**: Frederick (freddewitt) — github.com/freddewitt/CorbeauSplat
- **License**: MIT
- **Python**: 3.13+ (main), 3.11 (ML Sharp venv)
- **Stack**: PyQt6, COLMAP, Brush (Rust/WGPU), Apple ML Sharp, upscayl-ncnn
- **File count**: ~30 Python files, ~10,500 LOC first-party

## Quickstart

```bash
# GUI mode (default, no args)
python3 main.py

# CLI modes
python3 main.py pipeline -i video.mp4 -o ~/projects --preset dense
python3 main.py colmap -i images/ -o ~/projects
python3 main.py brush -i dataset/ -o dataset/ --preset dense
python3 main.py view -i splat.ply
python3 main.py upscale -i image.png -o ~/out --scale 4
```

## Architecture

```
main.py                         ← Entry: CLI parser or GUI launcher
├── app/
│   ├── __init__.py             ← VERSION = "0.99.1"
│   ├── upscayl_manager.py      ← Binary download, model management
│   ├── upscayl_models.py       ← 6 model catalogue definitions
│   │
│   ├── core/                   ← Business logic (engine layer)
│   │   ├── base_engine.py      ← BaseEngine + IProcessRunner (Template Method)
│   │   ├── engine.py           ← ColmapEngine — SfM pipeline
│   │   ├── brush_engine.py     ← BrushEngine — Gaussian Splat trainer
│   │   ├── sharp_engine.py     ← SharpEngine — Apple ML Sharp
│   │   ├── upscale_engine.py   ← UpscaleEngine — upscayl-ncnn wrapper
│   │   ├── superplat_engine.py ← SuperSplatEngine — web viewer
│   │   ├── four_dgs_engine.py  ← 4DGS data preparation
│   │   ├── extractor_360_engine.py — 360° video extraction
│   │   ├── export_engine.py    ← PLY → SPZ/GLB/OBJ/XYZ export
│   │   ├── i18n.py             ← LanguageManager singleton (9 languages)
│   │   ├── params.py           ← ColmapParams dataclass
│   │   └── system.py           ← Device detection, binary resolution
│   │
│   ├── gui/                    ← PyQt6 interface
│   │   ├── main_window.py      ← ColmapGUI — tab orchestrator
│   │   ├── managers.py         ← SessionManager + AppLifecycle
│   │   ├── workers.py          ← QThread workers (all engines)
│   │   ├── base_worker.py      ← BaseWorker with signals
│   │   ├── styles.py           ← Dark theme QPalette + stylesheet
│   │   └── tabs/               ← 10 tab widgets
│   │       ├── config_tab.py        ← Main dataset config
│   │       ├── brush_tab.py         ← Brush training controls
│   │       ├── upscale_tab.py       ← Model download/upscale
│   │       ├── sharp_tab.py         ← ML Sharp controls
│   │       ├── extractor_360_tab.py ← 360° extractor
│   │       ├── params_tab.py        ← COLMAP advanced params
│   │       ├── superplat_tab.py     ← Viewer controls
│   │       ├── four_dgs_tab.py      ← 4DGS prep controls
│   │       ├── export_tab.py        ← Format export
│   │       └── logs_tab.py          ← Log viewer
│   │
│   └── scripts/
│       └── setup_dependencies.py ← Engine installer (908 lines)
│
├── engines/                     ← External engine binaries/sources
│   ├── brush/                   ← Gaussian Splat trainer binary
│   ├── sharp/                   ← Apple ML Sharp package
│   ├── supersplat/              ← Web viewer (node_modules)
│   ├── glomap-source/           ← Glomap + COLMAP build
│   ├── extractor_360/           ← 360Extractor package
│   └── *.version                ← Engine version tracking
│
├── config.json                  ← User config (session persistence)
├── assets/locales/              ← 9 locale JSON files (fr, en, de, es, it, ja, zh, ru, ar)
└── main.py                      ← Entry point (785 lines)
```

## Key Design Patterns

| Pattern | Location | Usage |
|---------|----------|-------|
| Template Method | `BaseEngine._execute_command()` | All engines delegate process execution |
| Dependency Injection | `IProcessRunner` interface | Testable process execution |
| Singleton | `LanguageManager` | Single i18n instance |
| Observer | `LanguageManager.add_observer()` | UI retranslation on language change |
| SRP | `SessionManager`, `AppLifecycle` | Separated from MainWindow |
| Strategy | `BRUSH_PRESETS` dict | Named parameter profiles |

## Engines

| Engine | Input | Output | Binary |
|--------|-------|--------|--------|
| **ColmapEngine** | Video/images | COLMAP dataset (sparse + dense) | `colmap` / `glomap` |
| **BrushEngine** | COLMAP dataset | Gaussian Splat `.ply` | `brush` (Rust) |
| **SharpEngine** | Image/video | `.ply` splat | `sharp` (Apple ML) |
| **UpscaleEngine** | Image/folder | Upscaled images | `upscayl-bin` (NCNN) |
| **SuperSplatEngine** | `.ply` file | Web viewer | `npx serve` |
| **FourDGSEngine** | Multi-cam videos | Nerfstudio dataset | COLMAP + ns-process-data |
| **Extractor360Engine** | 360° video | Planar images | 360Extractor venv |
| **ExportEngine** | `.ply` file | SPZ/GLB/OBJ/XYZ/PLY | Python |

## Dependencies

**Python** (requirements.txt): PyQt6, requests, urllib3, numpy, send2trash, pyobjc-framework-Cocoa, Pillow, plyfile

**System**: FFmpeg, COLMAP, Homebrew, Xcode CLT

**Run-time downloaded**: upscayl-bin (auto-install from GitHub releases), upscayl models (6 custom models)

## Security

- Path traversal validation in `BaseEngine.validate_path()` — restricts to project root + home
- Project name sanitization in `engine.py:99` — rejects `..`, `/`, `\`
- Shell injection prevention: no `shell=True` anywhere in the codebase
- CORS hardening in `SuperSplatEngine` — only allows localhost origins
- Custom args allowlist in `BrushEngine` — only known flags accepted
- 24 security findings fixed in v0.99.3 audit (3 critical, 8 major, 13 minor)

## Known Issues & Gaps

1. **Zero test coverage** — no unit tests for any engine (~10,500 untested LOC)
2. **`gui/widgets/dialog_utils.py`**: Created dialog helpers but config_tab.py still uses raw `QFileDialog` in some paths

## Recently Fixed (v0.99.3+)

| File | Issue | Fix |
|------|-------|-----|
| `engine.py` | `sizes` dict used before init (NameError crash) | Added `sizes = {}` |
| `extractor_360_engine.py` | Raw `subprocess.Popen` bypassing Template Method | Refactored to use `_execute_command()` |
| `main.py` | BRUSH defaults duplicated 3x | Extracted `BRUSH_DEFAULTS` constant |
| `managers.py` | `!r` repr injection in cleanup script | Replaced with `json.dumps` |
| `export_engine.py` | Blender f-string injection + temp file leak | Replaced with JSON-serialized temp script + finally cleanup |
| `workers.py` | Hardcoded iteration 30000/7000 paths | Use `params["total_steps"]` |
| `workers.py` | Hardcoded refine fallback iter 30000 | Use `params["total_steps"]` |
| `i18n.py` | `save_config()` dropped keys on save | Preserves existing config keys |
| `params_tab.py` | `guided_match_check` widget orphaned (never in layout) | Added to match_layout |
| `export_tab.py` | `log()` was a no-op | Now emits `log_signal` |
| `upscale_engine.py` | `**kwargs` swallowed unknown args silently | Made params explicit |

## Pipeline Flow

```
Input (Video/Images)
  → [Extractor360] (if 360 mode)
  → [FFmpeg frame extraction] (if video)
  → [Upscale] (if enabled)
  → [COLMAP feature_extractor / matcher / mapper]
  → [Undistortion] (if enabled)
  → [Brush Config JSON]
  → [Brush Training]
  → Output .ply file
  → [Export to SPZ/GLB/OBJ/XYZ]
```

## i18n

9 languages via `assets/locales/{lang}.json`. `LanguageManager` singleton with Observer pattern. Fallback chain: selected → `en.json` → `fr.json` → empty dict.

## Dual-Venv Setup

- **`.venv/`**: Main app (Python 3.13+ with PyQt6, etc.)
- **`.venv_sharp/`**: ML Sharp (Python 3.11 — required by Apple's fork)
- **`.venv_360/`**: 360Extractor (isolated environment)

## CLI Subcommands

`pipeline`, `colmap`, `brush`, `sharp`, `view`, `upscale`, `4dgs`, `extract360`

Each has `--help`. No subcommand = GUI mode.
