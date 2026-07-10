# CorbeauSplat — Project Manifest

> Version 1.2.2 — macOS Apple Silicon Gaussian Splatting Pipeline

## Identity

- **Purpose**: All-in-one GUI + CLI tool for Gaussian Splatting 3D reconstruction on macOS
- **Author**: Frederick (freddewitt) — github.com/freddewitt/CorbeauSplat
- **License**: MIT
- **Python**: 3.13+ (main), 3.11 (ML Sharp venv)
- **Stack**: PyQt6, COLMAP/Glomap, Brush (Rust/WGPU), Apple ML Sharp, upscayl-ncnn, opencv-python-headless
- **File count**: ~70 Python files, ~15,978 LOC first-party

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
python3 main.py clean -i splat.ply --strength strong
python3 main.py clean -i noisy.ply -o cleaned.ply --then-export spz
```

## Architecture

```
main.py                         ← Entry: CLI parser or GUI launcher
├── app/
│   ├── __init__.py             ← VERSION = "1.0.5"
│   ├── upscayl_manager.py      ← Binary download, model management
│   ├── upscayl_models.py       ← 6 model catalogue definitions
│   │
│   ├── cli/                    ← CLI subcommand dispatch
│   │   ├── __init__.py         ← main() entry, dispatcher
│   │   ├── parser.py           ← argparse 9 subcommands
│   │   ├── commands.py         ← 9 run_* handlers (557 lines)
│   │   └── launcher.py         ← GUI launcher helper
│   │
│   ├── core/                   ← Business logic (engine layer)
│   │   ├── base_engine.py      ← BaseEngine + IProcessRunner (Template Method)
│   │   ├── engine.py           ← ColmapEngine — SfM pipeline (929 lines)
│   │   ├── brush_engine.py     ← BrushEngine — Gaussian Splat trainer
│   │   ├── sharp_engine.py     ← SharpEngine — Apple ML Sharp
│   │   ├── upscale_engine.py   ← UpscaleEngine — upscayl-ncnn wrapper
│   │   ├── superplat_engine.py ← SuperSplatEngine — web viewer
│   │   ├── four_dgs_engine.py  ← 4DGS data preparation
│   │   ├── extractor_360_engine.py — 360° video extraction
│   │   ├── export_engine.py    ← PLY → SPZ/GLB/OBJ/XYZ export (540 lines)
│   │   ├── ply_cleaner.py      ← PLY noise/floaters removal
│   │   ├── ply_utils.py        ← PLY parsing utilities
│   │   ├── i18n.py             ← LanguageManager singleton (9 languages)
│   │   ├── params.py           ← ColmapParams dataclass
│   │   └── system.py           ← Device detection, binary resolution
│   │
│   ├── gui/                    ← PyQt6 interface
│   │   ├── main_window.py      ← ColmapGUI — tab orchestrator
│   │   ├── managers.py         ← SessionManager + AppLifecycle
│   │   ├── workers.py          ← QThread workers (all engines + Cleaner)
│   │   ├── base_worker.py      ← BaseWorker with signals
│   │   ├── styles.py           ← Dark theme QPalette + stylesheet
│   │   ├── widgets/            ← Reusable widget components
│   │   │   ├── dialog_utils.py ← QFileDialog wrappers
│   │   │   ├── drop_line_edit.py ← Drag & drop text input
│   │   │   └── upscale_widgets.py ← Upscale-specific controls
│   │   └── tabs/               ← 10 tab widgets
│   │       ├── brush_tab.py         ← Brush training controls
│   │       ├── cleaner_export_tab.py← Clean + Export composite tab (v1.0.6)
│   │       ├── config_tab.py        ← Main dataset config
│   │       ├── extractor_360_tab.py ← 360° extractor
│   │       ├── four_dgs_tab.py      ← 4DGS prep controls
│   │       ├── logs_tab.py          ← Log viewer
│   │       ├── params_tab.py        ← COLMAP advanced params
│   │       ├── sharp_tab.py         ← ML Sharp controls
│   │       ├── superplat_tab.py     ← Viewer controls
│   │       └── upscale_tab.py       ← Model download/upscale
│   │
│   └── scripts/
│       ├── setup_dependencies.py ← Engine installer (orchestrator)
│       ├── checksum_verifier.py  ← Download integrity checks
│       ├── checksums.json        ← Hash manifest
│       └── installers/           ← 9 modular installer modules
│           ├── base.py           ← EngineDependency base class
│           ├── brush.py          ← Brush (Rust) installer
│           ├── extractor_360.py  ← 360Extractor venv installer
│           ├── mapping.py        ← COLMAP + Glomap build/install
│           ├── sharp.py          ← ML Sharp venv installer
│           ├── supersplat.py     ← SuperSplat npm installer
│           ├── tools.py          ← Shared utilities (193 lines)
│           └── upscayl.py        ← upscayl-bin downloader
│
├── engines/                     ← External engine binaries/sources
│   ├── brush/                   ← Gaussian Splat trainer binary
│   ├── brush.version
│   ├── sharp/                   ← Apple ML Sharp package
│   ├── sharp.version
│   ├── supersplat/              ← Web viewer (node_modules)
│   ├── supersplat.version
│   ├── glomap/                  ← Glomap binary
│   ├── glomap-source/           ← Glomap + COLMAP build tree
│   ├── glomap.version
│   ├── extractor_360/           ← 360Extractor package
│   ├── extractor_360.version
│   ├── .crates.toml / .crates2.json ← Rust crate registry cache
│
├── config.json                  ← User config (session persistence)
├── assets/locales/              ← 9 locale JSON files (fr, en, de, es, it, ja, zh, ru, ar)
├── CLI.md                       ← Full CLI reference (319 lines)
├── CHANGELOG.md                 ← Release history
├── pyproject.toml               ← Tool config (ruff, mypy, pytest)
└── main.py                      ← Entry point (13 lines, delegated to app/cli/)
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
| Strategy | `CLEANER_PRESETS` dict | Named PLY clean severity presets |

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
| **PlyCleaner** | `.ply` file/dir | Clean `.ply` (noise/floaters removed) | Python (native) |

## Dependencies

**Python** (requirements.txt): PyQt6, requests, urllib3, numpy, send2trash, pyobjc-framework-Cocoa, Pillow, plyfile, opencv-python-headless

**Python** (dev, pyproject.toml): ruff, mypy, pytest, pytest-qt, pip-audit, pip-tools

**System**: FFmpeg, COLMAP, Homebrew, Xcode CLT, Rust (for Brush build), Node.js (for SuperSplat)

**Run-time downloaded**: upscayl-bin (auto-install from GitHub releases), upscayl models (6 custom models)

## Security

- Path traversal validation in `BaseEngine.validate_path()` — restricts to project root + Desktop + Documents (v1.0.3+)
- GUI paths trusted via `gui_trusted` flag (v1.0.4) — bypasses containment check for QFileDialog selections
- Project name sanitization in `engine.py` — rejects `..`, `/`, `\`
- Shell injection prevention: no `shell=True` anywhere in the codebase
- CORS hardening in `SuperSplatEngine` — only allows localhost origins
- Custom args allowlist in `BrushEngine` — only known flags accepted
- Shell injection fixed in `AppLifecycle.restart()` (v1.0.3) — replaced `bash -c` f-string with direct subprocess calls
- 24+ security findings fixed since v0.99.3

## Known Issues & Gaps

 1. **E2E réel = pipeline principal seulement** — `pytest -m e2e` couvre COLMAP → Brush → clean → export SPZ (7 tests, ~21 s). Sharp/Upscale/4DGS/360 restent mockés. Suite par défaut : 263 pass, 1 skip (e2e désélectionné). GLB export tests skip si `trimesh`/`open3d` absents
 2. **Workers tested headless via mock PyQt6** — `conftest.py` patches PyQt6 at session scope, but import chain still requires numpy mock for CI

## Changelog Highlights (v1.0.1 → v1.0.6)

| Version | Key Changes |
|---------|-------------|
| **1.2.2** (2026-07-06) | SfM COLMAP : défaut **SIFT + DSP-SIFT** (`estimate_affine_shape=True`, force CPU) ; `vocab_tree` fonctionnel (était un no-op silencieux) ; `loop_detection` séquentiel (SIFT) ; **repli auto** `global_mapper`→`mapper` incrémental si pas de `sparse/0` valide (`_has_valid_sparse_model`). GUI responsive (5 onglets `QScrollArea`). `adapt_max_splats` : branche thermique morte corrigée (fair/serious/critical). Sécurité : `delete_project_content` bloque `/`, `$HOME`, dossier app + ancêtres. Réparation suite de tests (gel infini `readline`/EOF, pollution `cv2` session-wide) → **262 pass, 2 skip**. |
| **1.2.1** (2026-07-06) | Fix timeout Brush 3600s → 14400s configurable (`training_timeout`) ; `inactivity_timeout` dans `BaseEngine._execute_command()` (désactivé pour Brush — phases silencieuses). Rétrocompatible. |
| **1.2.0** (2026-07-05) | ExportTab async confirmé ; CI headless worker tests débloqués ; tests d'intégration étendus ; `pyproject.toml` → 1.2.0 |

_Versions ≤ 1.0.6 : voir `CHANGELOG.md` (historique complet)._

## Pipeline Flow

```
Input (Video/Images)
  → [Extractor360] (if 360 mode)
  → [FFmpeg frame extraction] (if video)
  → [Blurry image filter] (if enabled)
  → [Upscale] (if enabled)
  → [COLMAP feature_extractor / matcher / mapper]
  → [Undistortion] (if enabled)
  → [Brush Config JSON]
  → [Brush Training]
  → Output .ply file
  → [PlyCleaner] (optional PLY noise/floaters removal)
  → [Export to SPZ/GLB/OBJ/XYZ]
```

## i18n

9 languages via `assets/locales/{lang}.json`. `LanguageManager` singleton with Observer pattern. Fallback chain: selected → `en.json` → `fr.json` → empty dict.

## Dual-Venv Setup

- **`.venv/`**: Main app (Python 3.13+ with PyQt6, etc.)
- **`.venv_sharp/`**: ML Sharp (Python 3.11 — required by Apple's fork)
- **`.venv_360/`**: 360Extractor (isolated environment)

## CLI Subcommands

`pipeline`, `colmap`, `brush`, `sharp`, `view`, `upscale`, `4dgs`, `extract360`, `clean`

Each has `--help`. No subcommand = GUI mode. Full reference: `CLI.md`

## RESTE À FAIRE (priorisé)

_Aucun point ouvert prioritaire._ Pistes possibles : couvrir Sharp/Upscale/4DGS en e2e réel (upscayl à installer) ; taille de `manifest.md` à réduire (arbre d'archi = détail → `graphify query`).

> Résolu : **tests e2e réels** — session 2026-07-09. Pipeline complet COLMAP → Brush → clean → export SPZ sur scène synthétique générée à la volée (`tests/integration/_synthetic_scene.py`), 7 tests opt-in `pytest -m e2e` (désélectionnés par défaut). Au passage : `opencv-python-headless` réinstallé dans `.venv` (manquait → fuite de mock cv2 qui cassait 4 tests mockés en run complet).
> Résolu : `confirm_reset` (ES) — session 2026-07-08 (aligné sur en/fr). Audit i18n : 9 locales cohérentes.

## Graphify

Un graphe de connaissance est maintenu dans `graphify-out/`. Pour toute question d'architecture : `graphify query "<question>"`. Hook post-commit installé → graphe rafraîchi automatiquement après chaque commit (extraction code AST ; l'extraction sémantique des docs nécessite une clé API, sinon ignorée).
