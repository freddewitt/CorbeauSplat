# CorbeauSplat — Project Manifest

> Version 1.2.2 — macOS Apple Silicon Gaussian Splatting Pipeline

## Identity

- **Purpose**: All-in-one GUI + CLI tool for Gaussian Splatting 3D reconstruction on macOS
- **Author**: Frederick (freddewitt) — github.com/freddewitt/CorbeauSplat
- **License**: MIT
- **Python**: 3.13+ (main), 3.11 (ML Sharp venv)
- **Stack**: PyQt6, COLMAP/Glomap, Brush (Rust/WGPU), Apple ML Sharp, upscayl-ncnn, opencv-python-headless
- **File count**: ~74 Python files

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

Vue d'ensemble : `main.py` (entry) → `app/cli/` (dispatch CLI) et `app/gui/` (PyQt6, `main_window.py` orchestrateur + `tabs/` par moteur) s'appuient tous deux sur `app/core/` (moteurs, tous héritant de `base_engine.py`/BaseEngine : `engine.py`/ColmapEngine, `brush_engine.py`, `sharp_engine.py`, `upscale_engine.py`, `superplat_engine.py`, `four_dgs_engine.py`, `extractor_360_engine.py`, `export_engine.py`, `ply_cleaner.py`, `splat_transform_engine.py`). `app/scripts/installers/` installe les binaires externes dans `engines/`.

Détail (fichiers, classes, patterns, moteurs, dépendances, sécurité) → `graphify query "<question>"` ou `graphify explain "<concept>"`. Ne pas dupliquer ici ce que le graphe retrouve déjà.

## Known Issues & Gaps

 1. **E2E réel = pipeline principal seulement** — `pytest -m e2e` couvre COLMAP → Brush → clean → export SPZ (7 tests, ~21 s). Upscale/Sharp couverts en e2e réel (8 tests, ~145 s) ; 360/4DGS restent mockés. Suite par défaut : 291 pass, 2 skip. Marqueurs e2e : `e2e_sharp`, `e2e_upscale`, `e2e_4dgs`, `e2e_360` en plus de `e2e` umbrella (e2e désélectionné). GLB export tests skip si `trimesh`/`open3d` absents
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

1. **Commit** working tree (checkpoints Brush + bugfix SplatTransform + tests e2e P0-P2)
2. **E2E 360 Extractor** (`.venv_360` requis, générateur équirectangulaire à créer)
3. **E2E Sharp vidéo** (ffmpeg + Sharp predict par frame)
4. **E2E 4DGS** (ffmpeg + COLMAP + nerfstudio, coûteux)

> Résolu : **manifest.md allégé** (détail archi renvoyé vers `graphify query`) — session 2026-07-15. **`test_export_spz_created`** revérifié (isolé + suite complète + suite e2e) : passe systématiquement, l'échec signalé était obsolète — session 2026-07-15.

> Résolu : **tests e2e réels** — sessions 2026-07-09 et 2026-07-12. P0 (Upscale, 4 tests, upscayl-bin réel), P1 (360 Extractor, 25 tests unitaires mock), P2 (Sharp image, 4 tests, Sharp réel ~142s). Voir `feature-proposal.md` pour le design P3-P5.

## Graphify

Un graphe de connaissance est maintenu dans `graphify-out/`. Pour toute question d'architecture : `graphify query "<question>"`. Hook post-commit installé → graphe rafraîchi automatiquement après chaque commit (extraction code AST ; l'extraction sémantique des docs nécessite une clé API, sinon ignorée).
