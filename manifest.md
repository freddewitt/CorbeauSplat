# CorbeauSplat — Project Manifest

> Version 2.0.0 — macOS Apple Silicon Gaussian Splatting Pipeline

## Identity

- **Purpose**: All-in-one GUI + CLI tool for Gaussian Splatting 3D reconstruction on macOS
- **Author**: Frederick (freddewitt) — github.com/freddewitt/CorbeauSplat
- **License**: MIT
- **Python**: 3.13+ (main), 3.11 (ML Sharp venv)
- **Stack**: PySide6, COLMAP/Glomap, Brush (Rust/WGPU), Apple ML Sharp, upscayl-ncnn, opencv-python-headless
- **File count**: ~78 Python files

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

Vue d'ensemble : `main.py` (entry) → `app/cli/` (dispatch CLI) et `app/gui/` (PySide6, `studio_window.py`/`StudioWindow` orchestrateur unique — interface à 3 zones : rail gauche, centre, barre d'activité (`activity_bar.py` — étape en cours, détail, progression, Annuler ; le journal a sa propre fenêtre, `logs_window.py`) — + `panels/` par module) s'appuient tous deux sur `app/core/` (moteurs, tous héritant de `base_engine.py`/BaseEngine : `engine.py`/ColmapEngine, `brush_engine.py`, `sharp_engine.py`, `upscale_engine.py`, `superplat_engine.py`, `four_dgs_engine.py`, `extractor_360_engine.py`, `export_engine.py`, `ply_cleaner.py`, `splat_transform_engine.py`). `colmap_commands.py` isole la construction des argv COLMAP (SRP, extrait de ColmapEngine — v1.2.3). `media.py` centralise les formats acceptés — conteneurs vidéo (FFmpeg) et images, avec la conversion automatique des formats non lisibles par toute la chaîne (HEIC/TIFF/BMP/WebP… → PNG ou JPEG) ; les trois sites de détection (panneau Source, ColmapEngine, FourDGSEngine) y puisent la même liste. `app/scripts/installers/` installe les binaires externes dans `engines/`.

Le rail gauche (hiérarchie statique à trois niveaux : Projet, ENTRAÎNEMENT, OPTIONS, OUTILS) et le bandeau/barre d'activité sont décrits en détail dans `docs/manifest-detail.md`.

Détail (fichiers, classes, patterns, moteurs, dépendances, sécurité) → `graphify query "<question>"` ou `graphify explain "<concept>"`. Ne pas dupliquer ici ce que le graphe retrouve déjà.

## Known Issues & Gaps

 1. **E2E réel = pipeline principal seulement** — `pytest -m e2e` couvre COLMAP → Brush → clean → export SPZ (7 tests, ~21 s). Upscale/Sharp/360/4DGS couverts en e2e réel (21 tests, ~6 min, marqueurs dédiés). Suite par défaut : **1023 pass, 5 skip** (2026-09-23), dont 5 fichiers lançant un PySide6 **réel en sous-processus** via `tests/_real_qt.py` — le mock PySide6 de `conftest.py` est global à la session et irréversible, donc un vrai panneau ne peut être instancié qu'ainsi, et `coverage` ne suit pas l'enfant sans `parallel = true` + amorçage explicite (sans quoi les panneaux paraissent non couverts tout en s'exécutant). Couverture **68 %**. Marqueurs e2e : `e2e_sharp`, `e2e_upscale`, `e2e_4dgs`, `e2e_360` en plus de `e2e` umbrella (e2e désélectionné). GLB export tests skip si `trimesh`/`open3d` absents
 2. **Workers tested headless via mock PySide6** — `conftest.py` patches PySide6 at session scope, but import chain still requires numpy mock for CI

## Changelog Highlights

| Version | Key Changes |
|---------|-------------|
| **2.0.0** (2026-09-23) | **Version stable.** Audit « version stable » (`docs/AUDIT_STABLE.md`, rapports par lot dans `docs/audit-stable/`) : 9 lots — GUI panneau par panneau, CLI argument par argument, automatisation scénario par scénario, e2e réels. 78 défauts relevés, **54 corrigés avec tests de régression**. Bloquants : reprise COLMAP jamais câblée ; sortie Sharp non isolée par projet ; PLY introuvable sans étape Brush ; format Upscale `jpeg` refusé ; `extract360 --layout` par défaut refusé ; 4DGS mono-caméra impossible ; **sous-modèle COLMAP** : le mapper mettait l'ébauche en `sparse/0` et le vrai modèle en `sparse/1` (nouveau `app/core/sparse_models.py`, promotion du plus grand modèle, pipeline principal et 4DGS) ; FFmpeg 9 refusait `-vsync`. Nouveautés issues de l'audit : `sharp --upscale` réel, `brush --refine_mode` réel (`app/core/brush_refine.py` partagé GUI/CLI), trim vidéo en 4DGS, `skip_frames` Sharp et « Récursif » Nettoyage dans la GUI, device Brush `auto`, flags de chaînage restaurés à la reprise. Dernières décisions : réglage Notifications persisté dans `config.json` (L6-01) ; cases « Nettoyage/Exporter/SuperSplat après » et « Lancer Brush » honorées par les boutons Lancer locaux des pages OUTILS via le mécanisme de chaîne (L3-05/L5-08, un seul slot `finished_signal`). **1023 tests**, e2e réels 28/28. |
| **2.0.0-rc1** (2026-09-20) | Première release candidate, publiée sur `main` (la 1.5.1 vit désormais sur la branche `v1`). Code identique à beta.5 ; README réécrit pour la v2 (chaîne en un clic, plage vidéo, conversion d'images, galerie Upscale, configurations nommées), `.serena` et `opencode.multimodel.json` sortis du suivi git. Reste : validation manuelle sur Mac (points 6 et 7). |

_Historique 2026-09-20 (beta.5 : plan d'audit 8 lots, audit de code complet ; journal réparé, chargement de configuration sans téléchargement) et versions ≤ beta.4 : `docs/manifest-detail.md`. Versions ≤ 1.0.6 : `CHANGELOG.md` (historique complet)._

## Pipeline Flow

Source (vidéo/images) → [Extraction 360] → [Upscale] → FFmpeg (si vidéo) → filtre flou → COLMAP (features/matcher/mapper) → [Undistortion] → Brush (config + entraînement) → .ply → [Nettoyage] → [Export SPZ/GLB/OBJ/XYZ]. Séquence réelle : `PIPELINE_STEPS` / `plan_pipeline()`. Diagramme détaillé → `docs/manifest-detail.md`.

## i18n

9 languages via `assets/locales/{lang}.json`, **283 keys each**. `LanguageManager` singleton with Observer pattern. Fallback chain: selected → `en.json` → `fr.json` → empty dict.

Verrouillé par `tests/test_locales.py` : les 9 fichiers doivent avoir exactement les mêmes clés, aucune clé ne doit être orpheline (jamais référencée dans `app/`), et toute clé passée en littéral à `tr()` doit exister dans les 9 langues.

## Dual-Venv Setup

- **`.venv/`**: Main app (Python 3.13 recommended, PySide6, etc.)
- **`.venv_sharp/`**: ML Sharp (Python 3.11 — required by Apple's fork)
- **`.venv_360/`**: 360Extractor (isolated environment)

## CLI Subcommands

`pipeline`, `colmap`, `brush`, `sharp`, `view`, `upscale`, `4dgs`, `extract360`, `clean`, `splattransform`

Each has `--help`. No subcommand = GUI mode. Full reference: `CLI.md`

`pipeline` runs COLMAP → Brush, then Cleaning and Export when asked:
`--clean [light|medium|strong]` (bare flag = medium) and `--export FORMAT`
(`--export_output` to redirect). Checkpoints land in
`<output>/<project>/checkpoints`, the same place the interface uses.

## RESTE À FAIRE (priorisé)

### 🔄 Audit « version stable » 2026-09-23 — `docs/AUDIT_STABLE.md`
- Lots 0-9 ✅ (54 correctifs + tests, re-base 1023 pass, ruff/mypy propres, e2e réels 28/28 dont pipeline COLMAP+Brush). **Version 2.0.0 stable** (CHANGELOG, pyproject, `app/__init__.py`). Non commité.
- L6-01 ✅ (accord utilisateur pour `config.json`), L3-05/L5-08 ✅ câblés (`_start_tool_worker(post_steps=, ply_root=)` → `_run_tool_post_steps`).
- **À trancher par l'utilisateur** : L5-07 (annulation bloquante jusqu'à ~7 s, à mesurer en réel) ; D3 (FPS vidéo 2 GUI vs 5 CLI) ; L6-02/L6-04 (voir tableau).
- Backlog mineur (10) : D5, D8, D9, D13, D14, D18, L3-08, L3-11, L5-10, M11.

### Tâches ouvertes
- **M8 non traité** : `linux_brush` vide dans `checksums.json`, en attente d'accord explicite (sans effet réel, projet macOS).
- **M11 non traité (faible priorité)** : `_build_center()` de `reconstruction_panel` (190 l.) et `entrainement_panel` (194 l.), découpage mécanique impossible (variables locales partagées).
- ✅ **Câblage conversion d'images + Upscale depuis l'interface** validé le 2026-09-22 (Qt réel offscreen, vrai upscayl-bin) : chaîne Source → Upscale → Reconstruction avec `upscaler_avant` sur dossier mixte jpg/tif/bmp/webp/heic, et bouton Lancer local (dossier et HEIC seul). Filtre « Parcourir › Image » aligné sur `media.IMAGE_EXTENSIONS` le 2026-09-23 (audit L2-02).
- **Source = `<projet>/images/` lui-même** (2026-09-22, non commité au moment de l'écriture) : les originaux sont déplacés dans `images_src/` (protocole de l'upscale) et `images/` est reconstruit converti ; l'upscale enchaîné agrandit alors les copies d'`images/` via `images_upscaling/`. Voir `ColmapEngine._move_project_images_aside` / `_run_upscale`. **Chaîne complète validée le 2026-09-22** (Qt réel offscreen, vrais COLMAP/Brush/upscayl/SuperSplat, tous drapeaux : flou, undistort, upscale, Brush, clean, export spz, viewer) sur source images et vidéo ; 3 défauts corrigés, non commités : format 360 envoyé `jpeg` (→ `jpg`, data du combo), upscale non récursif après Extraction 360 (→ `rglob` + `_staged_names(root=)`), sorties Nettoyage/Export collées au 1er projet lors d'un 2e lancement (→ `is_chain_owned` + `_chain_prefilled`). **Reste** : reconstruction 360 sur vraies données (le panorama synthétique n'a pas assez de texture pour COLMAP).
3. **E2E 4DGS Phase A** ✅ — session 12, 4 tests (mode COLMAP dégradé), marqueur `e2e_4dgs`. Phase B (nerfstudio, `.venv_4dgs`) restante. (ffmpeg + COLMAP + nerfstudio, coûteux)
6. **Validation manuelle sur Mac de la refonte session 14** — aucun test automatisé ne couvre le rendu Qt réel. À vérifier : FPS visible seulement en source vidéo, bannière de mélange images+vidéo, colonne droite et filet masqués sur les bons écrans, chaînage réel bout-en-bout sur vraies données, molette sur les combos Réglages (ne doit plus rien changer), bannière 4DGS et tooltip `4dgs` du combo Mode. **Ajouts du 2026-09-17 à vérifier aussi** : galerie de modèles Upscale (volet droit — poids affiché, Télécharger puis Supprimer, modèles « Inclus » sans action, combo et cartes qui restent d'accord) ; réglages COLMAP du panneau 4DGS (chevauchement grisé hors matcher séquentiel) ; « Lancer » en mode Sharp puis en mode 4DGS depuis le panneau Source.
7. **Validation manuelle sur Mac des chantiers du 2026-08-07** (Upscale, champs Projet, suppressions, 360) — la GUI PySide6 n'a pas été exécutée pendant le chantier. À vérifier : Upscale en tête du groupe PARAMÈTRES (filet vertical continu l'incluant) et absent d'OUTILS ; colonne droite et filet masqués sur la page Upscale ; toggle « Upscaler avant reconstruction » en tête du bloc Automatisation, décoché au démarrage ; **chaîne source images** — fichiers présents dans `<sortie>/<projet>/images_upscaled` *avant* le démarrage de COLMAP et dossier source d'origine intact ; **chaîne source vidéo** — message différé affiché puis `images_src/` créé pendant la Reconstruction ; bouton Lancer local depuis PARAMÈTRES › Upscale, indépendant du Lancer global ; sauvegarde/rechargement d'une configuration nommée avec réglages Upscale non-défaut. **Extraction 360** — en tête de PARAMÈTRES (avant Upscale) tout en restant dans OUTILS, les deux pages devant être indépendantes (saisir un chemin dans l'une ne change rien dans l'autre) ; chaîne `source_360` seul puis `source_360` + `upscaler_avant`, avec `images_360/` peuplé *avant* `images_upscaled/`, lui-même *avant* le démarrage de COLMAP. **Champs Projet** — `checkpoint_dest` renseigné : l'export chaîné doit retrouver le PLY dans `<destination>/<projet>/` (c'est le cas de régression réel du chantier) ; `export_dir`/`export_format` renseignés : le run chaîné doit les respecter plutôt que la saisie du panneau Export. **Suppressions** — 🗑 grisé sur « Défaut » et sur un preset intégré, actif sur un preset personnel ; bouton « Supprimer… » des Réglages (liste, confirmation, disparition effective).
10. **L'épinglage Brush devra être bumpé à la main** à chaque release amont (`brush_release` + empreinte, ensemble). C'est désormais **signalé au démarrage** au lieu de casser l'installation, mais ça reste une action manuelle récurrente. Automatiser suppose une racine de confiance indépendante de l'artefact (attestations GitHub/sigstore) — pas le sidecar `.sha256`, qui vient de la même origine.
14. **360Extractor `--export-colmap`** (2026-09-11) — flag découvert lors de l'audit dépendances tierces, non intégré. Écrit une calibration virtuelle + config de rig + script `reconstruct.py` en plus des images extraites, exploitables par COLMAP (`rig_configurator`) pour éviter à la Reconstruction de redeviner des poses caméra déjà connues (utile en 360°, layout `cube`). **Non implémenté** : upstream indique lui-même « full reconstruction qualification is pending » — feature encore expérimentale côté 360Extractor. Design d'intégration esquissé si repris : flag `RunState.extraction360_export_colmap` (opt-in, actif seulement si layout `cube`), `Extractor360Engine` ajoute `--export-colmap`, `_build_colmap_worker()` bascule vers un chemin de reconstruction assisté (logique répliquée dans `colmap_commands.py`, pas d'appel au script externe généré, pour rester cohérent avec les garanties sécurité du reste du code) avec repli automatique sur la Reconstruction standard en cas d'échec/COLMAP trop ancien. Pas de changement d'ordre du pipeline nécessaire (Extraction 360 tourne déjà avant Reconstruction). À reprendre seulement après validation de la qualité de sortie côté 360Extractor.
15. **LightGlue/ALIKED déjà actif, LoMa (COLMAP 4.2.0) à évaluer** (2026-09-13) — Audit ONNX : `SIFT_LIGHTGLUE`/`ALIKED_LIGHTGLUE` sont déjà entièrement câblés (`app/core/params.py`, `app/core/colmap_commands.py`, CLI `app/cli/parser.py`, GUI `reconstruction_panel.py`) et accélérés par défaut sur Mac via CoreML (`COLMAP_COREML_ENABLED` actif inconditionnellement sur macOS dans le build COLMAP, `use_gpu=1` non surchargé par l'app) — **à vérifier en pratique** avant de considérer le gain acquis : logs `GLOG_v=2` doivent afficher « Enabling CoreML execution provider », sinon repli silencieux vers le CPU. Piste ouverte : matcher **LoMa** (`LOMA_B/B128/L/G/R`, PR colmap/colmap#4524, mergé en 4.2.0 — version déjà installée) annoncé plus robuste que LightGlue sur scènes difficiles (faible texture, gros mouvements caméra), mais poids encore hébergés sur le repo perso de l'auteur (pas encore asset officiel COLMAP). **Non implémenté** — à ajouter seulement si un test réel (comparaison sur nos propres jeux d'images) montre LightGlue insuffisant ; extension mineure des mêmes structures, aucune nouvelle dépendance.

## Graphify
Un graphe de connaissance est maintenu dans `graphify-out/`. Pour toute question d'architecture : `graphify query "<question>"`. Hook post-commit installé → graphe rafraîchi automatiquement après chaque commit (extraction code AST ; l'extraction sémantique des docs nécessite une clé API, sinon ignorée).
