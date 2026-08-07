# ETAT_DES_LIEUX — CorbeauSplat

> Instantané factuel du dépôt à `HEAD=b4e88db` (2026-07-18), généré en lecture seule pour préparer une refonte de l'interface. Aucun fichier de code n'a été modifié pour produire ce document. Document autosuffisant — pas d'accès au dépôt requis pour l'exploiter.

---

## 1. Métadonnées

- **Version** : `1.5.0` (`pyproject.toml:3`). CHANGELOG.md le confirme (`## [1.5.0] - 2026-07-18`, entrée la plus récente). Aucune divergence détectée entre pyproject, CHANGELOG et libellé UI (`v{VERSION}` dans la barre de statut de `main_window.py`, `VERSION` défini dans `app/__init__.py`).
- **Binding Qt** : PySide6 (migration depuis PyQt6 en v1.5.0). `requirements.txt` : `PySide6>=6.6,<7`. Version installée dans `.venv` : **6.11.1**.
- **Python** : 3.13.12 (`.venv`, exigence `3.13+`) pour l'app principale ; `.venv_sharp` en 3.11 (imposé par le fork Apple ML Sharp) ; `.venv_360` isolé pour l'extracteur 360.
- **Dépendances majeures** (`requirements.txt`) :
  ```
  PySide6>=6.6,<7
  requests>=2.32,<3
  urllib3>=2.0,<3
  numpy>=1.26,<3
  send2trash>=1.8,<2
  pyobjc-framework-Cocoa>=10.0,<11  (darwin only)
  Pillow>=12.3,<13
  plyfile>=0.7,<1
  opencv-python-headless>=4.8,<5
  ```
- **Fichiers `.py` sous `app/`** : 60.
- **Fichiers de test** (`tests/`) : 26 fichiers `.py` (17 en `tests/` racine incluant `__init__.py`, 9 en `tests/integration/` incluant `__init__.py`).
- **`pytest --collect-only`** : **293 tests collectés / 308 items totaux, 15 désélectionnés** (marqueurs e2e non sélectionnés par défaut) — cohérent avec le journal (« 292 pass, 1 skip » lors des dernières exécutions réelles).

---

## 2. Arborescence commentée

### app/cli
- `app/cli/__init__.py` — Package CLI : point d'entrée `main()`, dispatch sous-commandes.
- `app/cli/commands.py` — Handlers des commandes CLI (colmap, brush, sharp, upscale, 4dgs, pipeline).
- `app/cli/launcher.py` — Lance l'interface graphique PySide6 depuis la CLI.
- `app/cli/parser.py` — Définit le parseur argparse et ses sous-commandes.

### app/core
- `app/core/base_engine.py` — Classe de base des moteurs : gestion process, validation de chemins.
- `app/core/brush_engine.py` — Moteur d'entraînement Gaussian Splatting via Brush.
- `app/core/colmap_commands.py` — Construction pure des commandes CLI COLMAP (flags SIFT/ALIKED).
- `app/core/engine.py` — Moteur principal orchestrant le pipeline COLMAP complet.
- `app/core/export_engine.py` — Export de fichiers PLY vers spz/glb/obj/xyz.
- `app/core/extractor_360_engine.py` — Moteur d'extraction de vues depuis vidéos 360°.
- `app/core/four_dgs_engine.py` — Moteur 4D Gaussian Splatting via nerfstudio.
- `app/core/i18n.py` — Gestionnaire de langue/traductions (singleton `LanguageManager`).
- `app/core/params.py` — Dataclass `ColmapParams` : paramètres du pipeline COLMAP.
- `app/core/ply_cleaner.py` — Nettoyage automatique des artefacts dans fichiers PLY splat.
- `app/core/ply_utils.py` — Fichier vidé (ancien encodeur SPZ, remplacé par lib officielle).
- `app/core/sharp_engine.py` — Moteur d'exécution Apple ML Sharp (profondeur).
- `app/core/splat_transform_engine.py` — Wrapper sécurisé du CLI PlayCanvas splat-transform.
- `app/core/superplat_engine.py` — Serveur local + lancement de SuperSplat (visualisation web).
- `app/core/system.py` — Détection matériel (Apple Silicon, mémoire, thermique), résolution binaires.
- `app/core/upscale_engine.py` — Wrapper léger autour du binaire upscayl-bin CLI.

### app/gui
- `app/gui/base_worker.py` — Classe QThread de base avec signaux standardisés.
- `app/gui/main_window.py` — Fenêtre principale `ColmapGUI`, assemble tous les onglets.
- `app/gui/managers.py` — `SessionManager` (sauvegarde session) et `AppLifecycle` (restart/reset).
- `app/gui/styles.py` — Thèmes sombres et feuilles de style Qt.
- `app/gui/workers.py` — Workers QThread pour chaque moteur (COLMAP, Brush, Sharp, etc.).

### app/gui/tabs
- `brush_tab.py` — Onglet UI configuration entraînement Brush.
- `cleaner_export_tab.py` — Onglet UI combinant nettoyage PLY et export.
- `cleaner_tab.py` — Onglet UI de nettoyage des splats PLY (embarqué dans cleaner_export_tab).
- `config_tab.py` — Onglet UI configuration générale (langue, thème, mode, reset).
- `export_tab.py` — Onglet UI export multi-fichiers PLY (**orphelin, non instancié**).
- `extractor_360_tab.py` — Onglet UI extraction vidéo 360°.
- `four_dgs_tab.py` — Onglet UI pipeline 4D Gaussian Splatting.
- `logs_tab.py` — Onglet UI affichage/recherche des logs.
- `params_tab.py` — Onglet UI paramètres du pipeline COLMAP.
- `sharp_tab.py` — Onglet UI prédiction profondeur Apple Sharp.
- `splat_transform_tab.py` — Onglet UI transformation de splats via splat-transform.
- `superplat_tab.py` — Onglet UI serveur/visualisation SuperSplat.
- `upscale_tab.py` — Onglet UI upscaling d'images via upscayl.

### app/gui/widgets
- `dialog_utils.py` — Wrappers `QFileDialog` standardisés.
- `drop_line_edit.py` — `QLineEdit` supportant le glisser-déposer de fichiers.
- `upscale_widgets.py` — Widgets/workers pour installation binaire et modèles upscayl.

### app/scripts
- `checksum_verifier.py` — Vérification SHA-256 des binaires téléchargés.
- `checksums.json` — Table des empreintes SHA-256 attendues par binaire/OS.
- `setup_dependencies.py` — Réexporte les installers pour compatibilité ascendante.

### app/scripts/installers
- `base.py` — Classes de base `EngineDependency`, `PipEngine`, `DependencyManager`.
- `brush.py` — Installateur du moteur Brush (Rust/cargo).
- `extractor_360.py` — Installateur pip de l'extracteur 360°.
- `mapping.py` — Installateur COLMAP via Homebrew.
- `sharp.py` — Installateur pip d'Apple ML Sharp.
- `splat_transform.py` — Installateur npm de splat-transform PlayCanvas.
- `spz.py` — Installateur module Python spz dans le venv principal.
- `supersplat.py` — Installateur npm de SuperSplat.
- `tools.py` — Fonctions utilitaires (cargo, brew, node, versions).
- `upscayl.py` — Installateur binaire upscayl-ncnn depuis GitHub releases.

### app (racine, autre)
- `app/__init__.py` — Définit `VERSION` de l'application.
- `app/upscayl_manager.py` — Recherche, téléchargement et gestion du binaire upscayl-bin.
- `app/upscayl_models.py` — Catalogue des modèles upscayl compatibles ncnn.

### assets/locales
9 fichiers `{ar,de,en,es,fr,it,ja,ru,zh}.json` — traductions interface (fr = langue par défaut).

### tests
- `tests/conftest.py` — Fixtures partagées et mock PySide6 pour toute la suite.
- `tests/test_base_engine.py` — Tests validation de chemins de BaseEngine.
- `tests/test_brush_engine.py` — Tests construction de commande BrushEngine.
- `tests/test_cli.py` — Tests dispatch et parsing argparse de la CLI.
- `tests/test_colmap_engine.py` — Tests ColmapEngine (suppression projet, sécurité chemins).
- `tests/test_export_engine.py` — Tests export PLY (xyz, glb, obj, etc.).
- `tests/test_extractor_360_engine.py` — Tests Extractor360Engine.
- `tests/test_four_dgs_engine.py` — Tests fonctions module FourDGSEngine.
- `tests/test_managers.py` — Tests AppLifecycle et SessionManager.
- `tests/test_ply_cleaner.py` — Tests logique de nettoyage des splats PLY.
- `tests/test_setup_dependencies.py` — Tests setup_dependencies.py et app/core/system.py.
- `tests/test_sharp_engine.py` — Tests traitement de frames vidéo SharpEngine.
- `tests/test_upscayl_manager.py` — Tests upscayl_manager.py (téléchargement, vérification).
- `tests/test_workers.py` — Tests BaseWorker et workers spécialisés GUI.

### tests/integration
- `_synthetic_image.py` — Générateurs d'images 2D synthétiques (numpy+PIL).
- `_synthetic_scene.py` — Générateur de scène 3D synthétique pour tests e2e COLMAP.
- `conftest.py` — Fixtures d'intégration (projets COLMAP factices, binaires mockés).
- `test_cleaner_export_integration.py` — Tests intégration PlyCleaner → ExportEngine.
- `test_colmap_pipeline.py` — Tests intégration pipeline COLMAP (binaires mockés).
- `test_e2e_pipeline.py` — Test end-to-end réel COLMAP → Brush → Clean → Export.
- `test_e2e_sharp.py` — Test end-to-end réel Sharp sur image synthétique.
- `test_e2e_upscale.py` — Test end-to-end réel upscaling via upscayl-bin.
- `test_engine_params_integration.py` — Tests intégration ColmapParams et construction commandes.
- `test_security_i18n_integration.py` — Tests intégration validation chemins + i18n.

---

## 3. Couche moteurs (`app/core/`)

### BaseEngine (`app/core/base_engine.py`, ~L123-345)

Template Method : `_execute_command()` (L209-297) centralise l'exécution subprocess — démarre via `self.runner`, boucle de lecture avec timeout select-based, gère timeout global, timeout d'inactivité, annulation (`stop_requested`), watchdog thermique (`_check_thermal_abort`), callback de ligne/logging. Pas de méthode abstraite formelle : chaque moteur implémente ses propres points d'entrée publics (`run`, `train`, `predict`, `transform`, `export`…) qui appellent `_execute_command()` en interne.

```python
def __init__(self, name, logger_callback=None, process_runner: IProcessRunner | None = None, thermal_throttling: bool = False)
def validate_path(self, path)                    # L313 — resolve() + catch, AUCUN contrôle de confinement
def is_safe_path(self, path)                      # L323 — validate_path + .exists()
def _check_initial_thermal(self)                  # L147
def _check_thermal_abort(self) -> bool             # L163 — watchdog périodique (30s), abort si "critical"
def log(self, message, level=logging.INFO)         # L199
def stop(self)                                      # L204
def _kill_process(self, process)                   # L299
def cleanup_temp_files(self, patterns)              # L328
def validate_path_standalone(path, project_root=None)  # L337, fonction libre module-level
```
Constante : `_THERMAL_CHECK_INTERVAL = 30`.

**`IProcessRunner`** (L16-42) — dépendance injectée (`process_runner` au constructeur, défaut `SubprocessRunner()`), DIP pour testabilité :
```python
start(self, cmd: list, env: dict | None = None, **kwargs)
poll(self)
wait(self, timeout=None)
terminate(self)
stdout_iter(self) -> Iterator[str]
readline(self, timeout: float | None = None) -> str | None
get_returncode(self) -> int
```
`SubprocessRunner(IProcessRunner)` (L44-120) : implémentation `subprocess.Popen`, `os.setsid()` + `os.nice(10)` via `preexec_fn` (non-Windows), kill par groupe de process (SIGTERM/SIGKILL).

### `app/core/colmap_commands.py` — fonctions pures (extraites de ColmapEngine, SRP)
```python
def build_feature_extraction_command(colmap_bin, database_path, images_dir, params, num_threads, image_list_path=None) -> tuple[list, str]
def build_feature_matching_command(colmap_bin, database_path, params, num_threads) -> tuple[list, str]
def build_global_mapper_command(colmap_bin, database_path, images_dir, sparse_dir, params, num_threads) -> list
def build_incremental_mapper_command(colmap_bin, database_path, images_dir, sparse_dir, params, num_threads) -> list
def build_image_undistorter_command(colmap_bin, images_dir, sparse_dir, output_dir, params) -> tuple[list, str]
```
Consomme `ColmapParams` (duck-typed via `Any`).

### ColmapEngine (`app/core/engine.py`, L112-928)
Outil externe : binaire COLMAP (+ GLOMAP `global_mapper` optionnel) via `colmap_commands.py` ; pilote aussi `ffmpeg` et délègue à `UpscaleEngine`. Consomme `ColmapParams`.
```python
def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled", logger_callback=None, progress_callback=None) -> None
def project_path(self) -> Path                    # @property
def is_cancelled(self) -> bool
def run(self) -> tuple[bool, str]
def extract_frames_from_video(self, video_path, images_dir, prefix=None) -> bool
def run_command(self, cmd, description, status_prefix=None) -> bool
def feature_extraction(self, database_path, images_dir) -> bool
def feature_matching(self, database_path) -> bool
def mapper(self, database_path, images_dir, sparse_dir) -> bool
def image_undistorter(self, images_dir, sparse_dir, output_dir) -> bool
def create_brush_config(self, project_dir, images_dir, sparse_dir) -> None
def stop(self)
```
Fonction libre module-level : `delete_project_content(target_path) -> tuple[bool, str]` — suppression sandboxée vers la corbeille (bloque `/`, `$HOME`, racine projet, ancêtres), via `send2trash`.

### BrushEngine (`app/core/brush_engine.py`, L9-168)
Outil externe : Brush (binaire Rust), résolu via `resolve_binary("brush")`. Consomme un `dict[str, Any]` (pas de dataclass) : `total_steps`, `sh_degree`, `max_resolution`, `with_viewer`, `device`, `checkpoint_interval`, `custom_args`, `build_mode` + allowlist `ALLOWED_FLAGS`.
```python
def __init__(self, logger_callback=None, thermal_throttling=False) -> None
def build_command(self, input_path, output_path, params=None) -> tuple[list[str], dict[str, str]]
def train(self, input_path, output_path, params=None) -> int
```

### SharpEngine (`app/core/sharp_engine.py`, L11-249)
Outil externe : Apple ML "sharp" (inférence image unique → 3D Gaussian Splat), résolu via `.venv_sharp` dédié. Consomme un `dict` (`checkpoint`, `device`, `verbose`, `skip_frames` pour vidéo).
```python
def __init__(self, logger_callback=None)
def is_installed(self)
def predict(self, input_path, output_path, params=None) -> int
def process_video_frames(self, video_path, output_dir, params=None, log_callback=None, status_callback=None, progress_callback=None, cancel_check=None) -> int
```

### UpscaleEngine (`app/core/upscale_engine.py`, L13-156)
Outil externe : `upscayl-bin` (NCNN), localisé via `app.upscayl_manager.find_binary()`. Pas de dataclass — dict produit par `load_model()`.
```python
def __init__(self, logger_callback=None)
def is_installed(self) -> bool
def load_model(self, model_id="realesrgan-x4plus", scale=4, output_format="png", tile=0, tta=False, compression=0) -> dict | None
def upscale_image(self, input_path, output_path, upsampler, face_enhance=False) -> bool
def upscale_folder(self, input_dir, output_dir, model_id="realesrgan-x4plus", scale=4, output_format="png", custom_scale=None, tile=0, tta=False, compression=0, cancel_check=None) -> tuple[bool, str]
```

### SuperSplatEngine (`app/core/superplat_engine.py`, L15-148)
Pas de binaire natif : lance `npx serve` (Node) pour le viewer web SuperSplat bundlé (`engines/supersplat`), + serveur statique Python (`http.server`/`socketserver`) CORS-enabled pour les assets PLY. Pas de dataclass.
```python
def __init__(self, logger_callback=None) -> None
def get_supersplat_path(self) -> Path
def start_supersplat(self, port=3000) -> tuple[bool, str]
def stop_supersplat(self) -> None
def start_data_server(self, directory, port=8000) -> tuple[bool, str]
def stop_data_server(self) -> None
def stop_all(self) -> None
```

### FourDGSEngine (`app/core/four_dgs_engine.py`, L25-176)
Outils externes : `ffmpeg`, binaire COLMAP (repli), `ns-process-data` (Nerfstudio) dans `.venv_4dgs`. Pas de dataclass (args positionnels : `video_path`, `output_dir`, `fps`, `videos_dir`, `dataset_root`).
```python
def __init__(self, logger_callback=None, status_callback=None)
def check_nerfstudio(self)
def extract_frames(self, video_path, output_dir, fps=5)
def run_colmap(self, dataset_root)
def process_dataset(self, videos_dir, output_dir, fps=5)
```

### Extractor360Engine (`app/core/extractor_360_engine.py`, L15-141)
Outil externe : CLI Python bundlé `extractor_360` (`engines/extractor_360/src/main.py`) dans venv dédié `.venv_360`. Consomme un `dict` (`interval`, `format`, `resolution`, `camera_count`, `quality`, `layout`, `ai_mask`, `ai_skip`, `adaptive`, `motion_threshold`).
```python
def __init__(self, logger_callback=None)
def is_installed(self)
def install(self)
def uninstall(self)
def run_extraction(self, input_path, output_dir, params, progress_callback=None, log_callback=None, status_callback=None, check_cancel_callback=None)
```

### ExportEngine (`app/core/export_engine.py`, L9-478)
Pas de binaire unique — dispatch vers `plyfile`, `trimesh`, `open3d`, `spz` (nianticlabs), et repli CLI externes `assimp`/`blender` pour GLB. Consomme `options: dict | None`.
```python
def __init__(self, logger_callback=None) -> None
def is_available(self) -> bool
def export(self, input_path, output_path, output_format, scale=1.0, options=None) -> bool
```
`SUPPORTED_FORMATS = ["spz", "glb", "obj", "ply", "xyz"]`.

### ply_cleaner.py (`app/core/ply_cleaner.py`) — module de fonctions, **pas** une sous-classe BaseEngine
Utilise `validate_path_standalone` directement. Pas d'outil externe (NumPy + `plyfile` en process).
```python
def compute_clean_mask(x, y, z, opacity, s0, s1, s2, opacity_min=0.10, scale_pct=99.5, outlier_pct=99.5)
def resolve_params(strength="medium", overrides=None)
def clean_ply(input_path, output_path, strength="medium", overrides=None, log=None)
def clean_ply_batch(input_dir, output_dir, strength="medium", overrides=None, log=None, recursive=False)
```
`PRESETS` : `light`/`medium`/`strong` → `{opacity_min, scale_pct, outlier_pct}`.

### SplatTransformEngine (`app/core/splat_transform_engine.py`, L19-127)
Outil externe : CLI Node.js PlayCanvas `splat-transform`. Consomme `dict[str, Any] | None`, restreint à `ALLOWED_FLAGS_BOOLEAN` (`--filter-nan`, `--morton-order`, `--quiet`, `--overwrite`, `--summary`) et `ALLOWED_FLAGS_VALUE` (`--filter-harmonics`, `--decimate`, `--gpu`). Rejette explicitement les chemins d'entrée `http://`/`https://` (anti-SSRF, docstring du fichier).
```python
def __init__(self, logger_callback=None) -> None
def is_available(self) -> bool
def transform(self, input_path, output_path, params=None) -> int
```

---

## 4. Paramètres et dataclasses

`ColmapParams` (`app/core/params.py:19`) est **la seule** `@dataclass` de la couche paramètres. Tous les autres moteurs consomment des `dict` bruts (voir §3).

### Champs de `ColmapParams`

| # | Champ | Type | Défaut |
|---|---|---|---|
| 1 | `camera_model` | `str` | `'SIMPLE_RADIAL'` |
| 2 | `single_camera` | `bool` | `True` |
| 3 | `max_image_size` | `int` | `3200` |
| 4 | `max_num_features` | `int` | `8192` |
| 5 | `feature_type` | `str` | `'SIFT'` |
| 6 | `matching_type` | `str` | `'SIFT_BRUTEFORCE'` |
| 7 | `estimate_affine_shape` | `bool` | `True` |
| 8 | `domain_size_pooling` | `bool` | `True` |
| 9 | `max_ratio` | `float` | `0.8` |
| 10 | `max_distance` | `float` | `0.7` |
| 11 | `cross_check` | `bool` | `True` |
| 12 | `guided_matching` | `bool` | `False` |
| 13 | `ba_refine_focal_length` | `bool` | `True` |
| 14 | `ba_refine_principal_point` | `bool` | `False` |
| 15 | `ba_refine_extra_params` | `bool` | `True` |
| 16 | `min_num_matches` | `int` | `15` |
| 17 | `matcher_type` | `str` | `'exhaustive'` (exhaustive/sequential/vocab_tree) |
| 18 | `sequential_overlap` | `int` | `30` |
| 19 | `undistort_images` | `bool` | `False` |
| 20 | `filter_blurry` | `bool` | `False` |
| 21 | `blur_factor` | `float` | `0.7` |
| 22 | `thermal_throttling` | `bool` | `False` |
| 23 | `use_view_graph_calibration` | `bool` | `True` |
| 24 | `ignore_watermarks` | `bool` | `True` |

Méthodes : `to_dict()` (→ `asdict(self)`), `from_dict(cls, data)` (filtre les clés inconnues via `fields(cls)`).

### Constantes associées (`app/core/params.py:3-15`)
```python
FEATURE_TYPES = ['SIFT', 'ALIKED_N16ROT', 'ALIKED_N32']
MATCHING_TYPES = ['SIFT_BRUTEFORCE', 'ALIKED_BRUTEFORCE', 'SIFT_LIGHTGLUE', 'ALIKED_LIGHTGLUE']
FEATURE_TO_DEFAULT_MATCHING = {'SIFT': 'SIFT_BRUTEFORCE', 'ALIKED_N16ROT': 'ALIKED_LIGHTGLUE', 'ALIKED_N32': 'ALIKED_LIGHTGLUE'}
COMPATIBLE_MATCHING = {'SIFT': ['SIFT_BRUTEFORCE', 'SIFT_LIGHTGLUE'], 'ALIKED_N16ROT': ['ALIKED_BRUTEFORCE', 'ALIKED_LIGHTGLUE'], 'ALIKED_N32': ['ALIKED_BRUTEFORCE', 'ALIKED_LIGHTGLUE']}
```
Consommées par `app/gui/tabs/params_tab.py` (combos feature-type / matching).

### Cross-référence champ ↔ onglet ↔ get_params/set_params

| Champ | Onglet | get_params | set_params | Remarque |
|---|---|---|---|---|
| `camera_model` … `matcher_type` (17 champs, L204-220) | `params_tab.py` | Oui | Oui | OK, correspondance directe widget↔champ |
| `guided_matching` | `params_tab.py` (`guided_match_check`) | Oui (L215) | **Non** — jamais écrit dans `set_params()` | **ORPHELIN (écriture)**. Widget désactivé en permanence (`setEnabled(False)` init L139) → toujours décoché en pratique ; une valeur persistée `True` est perdue au rechargement |
| `matching_type` | `params_tab.py` | Oui | Oui, mais conditionnel (L236-238) | Si la valeur sauvegardée n'est pas compatible avec `feature_type` courant, elle est silencieusement ignorée (repli sur ce que le combo contient déjà) |
| `sequential_overlap` | — | **Aucun widget dans aucun onglet** | **Non** | **ORPHELIN complet** — champ consommé en aval (`colmap_commands.py:66`, `--SequentialMatching.overlap`) et testé unitairement, mais aucune UI ni flag CLI ; seul le défaut `30` est jamais atteint malgré `matcher_type='sequential'` sélectionnable dans le combo |
| `undistort_images` | possédé par `config_tab.py` (`undistort_check`), pas `params_tab.py` | Non via `ParamsTab.get_params()` (hardcodé `False` en interne, commentaire "Géré par ConfigTab") ; vraie valeur assemblée dans `main_window.get_current_params()` | Non via `ParamsTab.set_params()` (commentaire explicite) ; restauré via `ConfigTab.set_state()` | **Champ cross-tab** : source de vérité éclatée entre deux onglets |
| `filter_blurry` | `config_tab.py` (`chk_filter_blur`) | Non via `ParamsTab` ; assemblé post-hoc dans `main_window.py:195` | Non via `ParamsTab` ; via `ConfigTab.set_state()` | Même schéma cross-tab que `undistort_images` |
| `blur_factor` | `config_tab.py` (`combo_blur_strength`) | Non via `ParamsTab` ; dérivé dans `main_window.py:196-198` via mapping en dur `{"light":0.5,"medium":0.7,"strong":0.9}` | Non via `ParamsTab` ; via `ConfigTab.set_state()` | Cross-tab **et** mapping numérique dupliqué indépendamment dans `app/cli/commands.py::_blur_factor_from_strength()` — deux implémentations séparées (GUI vs CLI) du même mapping, risque de divergence |
| `thermal_throttling`, `use_view_graph_calibration`, `ignore_watermarks` | `params_tab.py` | Oui | Oui | OK |

**Persistance de session** : `ParamsTab.get_state()` appelle `self.get_params().to_dict()` — donc l'état de session persisté pour `ParamsTab` **n'inclut jamais** les vraies valeurs de `undistort_images`/`filter_blurry`/`blur_factor` (elles restent dans le bloc JSON de `ConfigTab`). Comportement voulu (dual-homing) mais source de confusion si on lit le JSON de `ParamsTab` isolément.

---

## 5. Couche GUI (`app/gui/`)

### `main_window.py` — classe `ColmapGUI(QMainWindow)`
Fenêtre principale : possède le `QTabWidget`, instancie tous les onglets, câble leurs signaux vers des slots d'orchestration, pilote les workers (COLMAP, Brush, Sharp, SplatTransform, 4DGS, post-training).

Méthodes :
```python
def __init__(self)
def init_ui(self)
def retranslate_ui(self)
def apply_tab_styling(self)
def get_current_params(self)
def get_upscale_config(self)
def get_extractor_360_config(self)
def process(self)
def resume_colmap(self)
def stop_process(self)
def on_finished(self, success, message)
def delete_dataset(self)
def train_brush(self, force_auto=False)
def stop_brush(self)
def on_brush_finished(self, success, message)
def _run_post_training(self, output_path, clean, strength, export, fmt)
def _on_post_training_finished(self, success, message)
def _show_training_done_dialog(self, output_path)
def _open_latest_splat(self, output_path)
def run_sharp(self)
def stop_sharp(self)
def on_sharp_finished(self, success, message)
def run_splat_transform(self, input_path, output_path, params)
def stop_splat_transform(self)
def _on_splat_transform_finished(self, success, message)
def restart_application(self)
def reset_factory(self, deep=False)
def closeEvent(self, event)
```

Onglets instanciés (ordre exact, main_window.py L74-105) :

| # | Attribut | Classe | Titre (en) |
|---|---|---|---|
| 1 | `config_tab` | ConfigTab | "Training" |
| 2 | `brush_tab` | BrushTab | "Brush" |
| 3 | `superplat_tab` | SuperSplatTab | "SuperSplat" |
| 4 | `cleaner_export_tab` | CleanerExportTab | "Cleaning" |
| 5 | `splat_transform_tab` | SplatTransformTab | "SplatTransform" |
| 6 | `sharp_tab` | SharpTab | "Apple ML Sharp" |
| 7 | `four_dgs_tab` | FourDGSTab | "4DGS" |
| 8 | `extractor_360_tab` | Extractor360Tab | "360 Extractor" |
| 9 | `upscale_tab` | UpscaleTab | "Upscale" |
| 10 | `params_tab` | ParamsTab | "COLMAP Parameters" |
| 11 | `logs_tab` | LogsTab | "Logs" |

Plus un `QLabel` non-onglet dans la barre de statut affichant `v{VERSION}`.

`ExportTab` (`export_tab.py`) est **orphelin** : jamais importé/instancié dans `main_window.py` ni ailleurs (seulement `if __name__ == "__main__"`). `CleanerTab` n'est pas ajouté directement au `QTabWidget` — embarqué dans `CleanerExportTab` via `QScrollArea`.

### Onglets — méthodes d'interface partagées

| Onglet (fichier) | Classe | Titre | Rôle | get_params | set_params | get_state | set_state | retranslate_ui |
|---|---|---|---|---|---|---|---|---|
| brush_tab.py | BrushTab | "Brush" | Config/lancement entraînement Brush | ✅ | ✅ | ✅ | ✅ | ✅ |
| cleaner_export_tab.py | CleanerExportTab | "Cleaning" | Conteneur CleanerTab + câblage CleanerWorker | ❌ | ❌ | ✅ | ✅ | ❌ |
| cleaner_tab.py | CleanerTab | (embarqué) | UI nettoyage PLY (fichier/batch) | ❌ | ❌ | ✅ | ✅ | ❌ |
| config_tab.py | ConfigTab | "Training" | Config générale (chemins, mode, options, lancement) | ❌ (accesseurs `get_*` dédiés) | ❌ | ✅ | ✅ | ✅ |
| export_tab.py | ExportTab | "PLY Export" (**orphelin**) | Export standalone non câblé | ❌ | ❌ | ❌ | ❌ | ✅ |
| extractor_360_tab.py | Extractor360Tab | "360 Extractor" | Config extraction vidéo 360° | ✅ | ✅ | ✅ | ✅ | ✅ |
| four_dgs_tab.py | FourDGSTab | "4DGS" | Config préparation dataset 4DGS | ✅ | ✅ | ✅ | ✅ | ✅ |
| logs_tab.py | LogsTab | "Logs" | Affichage logs | ❌ | ❌ | ❌ | ❌ | ✅ |
| params_tab.py | ParamsTab | "COLMAP Parameters" | Formulaire `ColmapParams` | ✅ | ✅ | ✅ | ✅ | ✅ |
| sharp_tab.py | SharpTab | "Apple ML Sharp" | Config prédiction Sharp | ✅ | ✅ | ✅ | ✅ | ✅ |
| splat_transform_tab.py | SplatTransformTab | "SplatTransform" | Config/lancement splat-transform | ❌ | ❌ | ✅ | ✅ | ✅ |
| superplat_tab.py | SuperSplatTab | "SuperSplat" | Contrôle serveur viewer SuperSplat | ❌ | ❌ | ✅ | ✅ | ✅ |
| upscale_tab.py | UpscaleTab | "Upscale" | Config upscaling Upscayl | ✅ | ✅ | ✅ | ✅ | ✅ |

### `managers.py`
**`SessionManager(main_window)`** — SRP : persistance JSON uniquement.
```python
def get_session_file(self) -> Path       # resolve_project_root() / "config.json"
def save(self, immediate=False)           # debounce 1500ms via QTimer, sauf immediate=True
def _do_save(self)
def load(self)
```
Persiste dans **`config.json`** (racine projet), JSON `indent=2`. Clés : `language` + `tab_mapping` (`config`, `colmap_params`, `brush_params`, `sharp_params`, `cleaner_params`, `upscale_params`, `extractor_360_params`, `four_dgs_params`, `superplat_params`). Préfère `get_state()`/`set_state()` si présents, sinon repli sur `get_params()`/`set_params()` (`.to_dict()` si dispo). `colmap_params` traité via `ColmapParams.from_dict()`. `styles.py` lit/écrit aussi `config.json` (clé `"theme"` séparée).

**`AppLifecycle`** — SRP : restart/reset OS. Méthodes statiques :
```python
restart(save_callback=None)     # sauvegarde optionnelle, os.execv ou Popen, quit+exit
reset_factory(deep=False)       # supprime .venv/.venv_sharp/.venv_360 (+engines/config.json si deep), relance
```

### `workers.py` + `base_worker.py`

`BaseWorker(QThread)` — signaux communs :
```python
log_signal = Signal(str)
progress_signal = Signal(int)
status_signal = Signal(str)
finished_signal = Signal(bool, str)
```

| Worker | Base | Moteur piloté | Signaux |
|---|---|---|---|
| Extractor360Worker | BaseWorker | Extractor360Engine | log, progress, status, finished |
| ColmapWorker | BaseWorker | ColmapEngine (+ Extractor360Engine en interne pour 360) | log, progress, status, finished |
| BrushWorker | BaseWorker | BrushEngine | log, finished |
| SharpWorker | BaseWorker | SharpEngine (+ Upscayl via `upscayl_manager.run_upscayl`) | log, status, finished |
| SharpVideoWorker | BaseWorker | SharpEngine (`process_video_frames`) | log, progress, status, finished |
| CleanerWorker | BaseWorker | aucun (fonction `ply_cleaner.clean_ply` directe) | log, finished |
| SplatTransformWorker | BaseWorker | SplatTransformEngine | log, finished |
| FourDGSWorker | BaseWorker | FourDGSEngine | log, status, finished |
| PostTrainingWorker | BaseWorker | aucun (appelle `clean_ply` + `ExportEngine`) | log, finished |
| ExportWorker | BaseWorker | ExportEngine | log, progress, status, finished |

Tous les `__init__` acceptent `engine=None` (DIP) sauf `CleanerWorker`, `PostTrainingWorker`, `ExportWorker`.

### `widgets/`
- **`dialog_utils.py`** — wrappers fonction-module autour de `QFileDialog` : `get_dialog_options()`, `get_existing_directory()`, `get_open_file_name()`, `get_open_file_names()`, `get_save_file_name()`.
- **`drop_line_edit.py`** — `DropLineEdit(QLineEdit)` : `fileDropped = Signal(str)`, `_validate_path(self, path) -> bool`, gestion drag&drop.
- **`upscale_widgets.py`** — `BinaryInstallWorker`, `ModelDownloadWorker`, `TestWorker` (QThread), `ModelCard(QFrame)` (`download_requested`/`delete_requested` signals, `refresh()`, `set_downloading()`, observer i18n).

### `styles.py`
Hybride **QPalette + stylesheet QSS** (pas de couleurs en dur éparpillées, sauf quelques `setStyleSheet` ponctuels ex. label version). `THEMES` : 3 thèmes nommés `slate` (défaut, Slate+Indigo), `graphite` (Graphite+Teal), `blue`. Chaque thème = dict de rôles sémantiques (`window, surface, base, text, muted, accent, border, btn, btn_hover, btn_press, disabled, highlight_text, bright`). `_STYLESHEET` = `string.Template` QSS paramétré par ces rôles. `get_saved_theme()`/`save_theme()` lisent/écrivent la clé `"theme"` dans `config.json`. `set_dark_theme(app_instance, theme)` construit un `QPalette` + applique le QSS — appelé depuis `main_window.__init__`.

---

## 6. Couplages et flux

### Flux « Lancer »

| Bouton | Slot main_window / onglet | Worker | Moteur | Ordre des étapes |
|---|---|---|---|---|
| "Lancer le traitement" (`btn_process`, config_tab) → `processRequested` | `ColmapGUI.process()` — dispatch sur `config_tab.get_training_mode()` | mode gsplat : `ColmapWorker` | `ColmapEngine.run()` | `_validate_and_setup_paths` → `_process_input` (extraction vidéo/copie, filtre flou optionnel, upscale optionnel, normalisation résolution) → `_run_reconstruction_pipeline` : reset DB → `feature_extraction` → (si séquentiel) tri images DB → `feature_matching` → (optionnel) calibration view-graph → `mapper` → (optionnel) `image_undistorter` → `create_brush_config` |
| idem, mode sharp | `process()` branche sharp | `SharpVideoWorker` (vidéo) ou `SharpWorker` (image) | `SharpEngine.process_video_frames`/`predict` | upscale optionnel (SharpWorker) → prédiction Sharp |
| idem, mode 360 | `process()` branche 360 | `ColmapWorker` (extractor_360_params.enabled=True) | `Extractor360Engine.run_extraction` puis `ColmapEngine.run()` | extraction 360→perspective dans `ColmapWorker.run()` → nouveau `ColmapEngine` pointé sur images extraites → pipeline COLMAP standard |
| idem, mode 4dgs | `process()` branche 4dgs | `FourDGSWorker` (instance main_window) | `FourDGSEngine.process_dataset()` | étape unique |
| "Reprise COLMAP" (`btn_resume_colmap`) → `resumeColmapRequested` | `ColmapGUI.resume_colmap()` | `ColmapWorker` (upscale/360 params=None), `engine.resume_colmap=True` forcé | `ColmapEngine.run()` | saute extraction/upscale (valide images déjà présentes) → pipeline reconstruction identique |
| "Lancer l'entraînement Brush" (`btn_train`) → `trainRequested` | `ColmapGUI.train_brush(force_auto=False)` | `BrushWorker` | `BrushEngine.train()` | résolution dataset root → setup mode refine (symlinks checkpoint) si actif → renommage checkpoints existants → archive si non-refine → `engine.train()` → renommage post-succès → prune si `keep_only_latest` → **chaîne vers post-training** (§ ci-dessous) |
| auto-déclenché après succès COLMAP si `config_tab.get_auto_brush()` | `on_finished()` appelle `train_brush(force_auto=True)` | idem | idem | — |
| "Lancer Brush uniquement" (`btn_run_standalone`) | `BrushTab.run_standalone()` — **local à l'onglet, contourne main_window/workers.py** | aucun QThread — `subprocess.Popen` détaché, fire-and-forget | `BrushEngine.build_command()` (construction cmd seulement, `.train()` jamais appelé) | lancement process externe, aucun log/progress renvoyé au GUI |
| "Lancer Apple ML Sharp" (`btn_run`) → `predictRequested` | `ColmapGUI.run_sharp()` | `SharpWorker`/`SharpVideoWorker` selon `params["mode"]` | `SharpEngine.predict`/`process_video_frames` | image : upscale optionnel → predict ; vidéo : extraction frames → Sharp par frame |
| "Run splat-transform" (`btn_run`) → `transformRequested` | `ColmapGUI.run_splat_transform()` | `SplatTransformWorker` | `SplatTransformEngine.transform()` | `is_available()` check → `transform()` |
| "Extraire" 360 standalone (`btn_extract`) | `Extractor360Tab.run_standalone_extraction()` — **local à l'onglet** | `Extractor360Worker` (instancié dans l'onglet) | `Extractor360Engine.run_extraction()` | étape unique |
| "Lancer" 4DGS complet (`btn_run`) | `FourDGSTab.run_process()` — **instance FourDGSWorker distincte de celle de main_window** | `FourDGSWorker(videos_dir, output_dir, fps)` | `FourDGSEngine.process_dataset()` | étape unique |
| "COLMAP seul" 4DGS (`btn_colmap`) | `FourDGSTab.run_colmap_only()` | `FourDGSWorker(None, output_dir, fps)` | `FourDGSEngine.run_colmap()` | COLMAP seul |
| "Nettoyer" PLY standalone (`btn_clean`) | `CleanerExportTab._on_clean_requested()` | `CleanerWorker` | `clean_ply()` | fichier unique ou boucle glob batch |
| "Exporter" (`btn_export`, orphelin) | `ExportTab.start_export()` — **local, onglet non câblé** | `ExportWorker` | `ExportEngine.export()` | boucle par fichier |
| "Démarrer/Arrêter SuperSplat" (`btn_start`) | `SuperSplatTab.toggle_server()` — **pas de QThread** | aucun (appels synchrones directs) | `SuperSplatEngine.start_supersplat()` puis `start_data_server()` optionnel ; stop via `stop_supersplat()` | démarrage process → data server si chemin fourni → ouverture navigateur |
| "Stop" (tous onglets) | handler local → `stop_process`/`stop_brush`/`stop_sharp`/`stop_splat_transform` ou local | `.stop()` sur le `BaseWorker` concerné | `.stop()` moteur | — |
| "Réinstaller Brush" (`btn_reinstall_brush`) | `BrushTab.on_reinstall_clicked()` → `restartRequested` | aucun (routine d'installation) | install + `AppLifecycle.restart` | install → relance app |
| "Supprimer le dataset" (`btn_delete_dataset`) → `deleteDatasetRequested` | `ColmapGUI.delete_dataset()` | aucun | `ColmapEngine.delete_project_content()` (statique) | confirmation → suppression |
| "Quitter"/"Relancer"/"Réinitialiser" | `close`/`restart_application`/`reset_factory` | aucun | `AppLifecycle.restart`/`reset_factory` | — |

**Point notable** : `BrushTab` a **deux chemins distincts** pour lancer Brush — `trainRequested` (via main_window → `BrushWorker` QThread, logs + chaînage post-training complet) vs `run_standalone()` (contourne totalement main_window, `subprocess.Popen` fire-and-forget, sans logs/signal finished/post-training). De même, `FourDGSTab` et `Extractor360Tab` instancient **leurs propres** workers, indépendants de ceux orchestrés depuis l'onglet Config — deux chemins de code indépendants par fonctionnalité (tab-local vs main_window-orchestré).

### Connexions de signaux

Onglet → main_window (`ColmapGUI.init_ui()`, L113-134) :

| Émetteur | Signal | Récepteur.slot |
|---|---|---|
| ConfigTab | processRequested | ColmapGUI.process |
| ConfigTab | resumeColmapRequested | ColmapGUI.resume_colmap |
| ConfigTab | stopRequested | ColmapGUI.stop_process |
| ConfigTab | deleteDatasetRequested | ColmapGUI.delete_dataset |
| ConfigTab | quitRequested | ColmapGUI.close |
| ConfigTab | relaunchRequested | ColmapGUI.restart_application |
| ConfigTab | resetRequested | ColmapGUI.reset_factory |
| BrushTab | trainRequested | ColmapGUI.train_brush |
| BrushTab | stopRequested | ColmapGUI.stop_brush |
| BrushTab | restartRequested | ColmapGUI.restart_application |
| SharpTab | predictRequested | ColmapGUI.run_sharp |
| SharpTab | stopRequested | ColmapGUI.stop_sharp |
| CleanerExportTab | log_signal | LogsTab.append_log |
| SplatTransformTab | transformRequested | ColmapGUI.run_splat_transform |
| SplatTransformTab | stopRequested | ColmapGUI.stop_splat_transform |

Worker → main_window (câblage ad hoc à chaque lancement) :

| Émetteur | Signal | Récepteur.slot |
|---|---|---|
| ColmapWorker | log/progress/status/finished | LogsTab.append_log / ConfigTab.progress_bar.setValue / ConfigTab.lbl_status.setText / ColmapGUI.on_finished |
| SharpWorker/SharpVideoWorker (depuis process()) | idem | idem → ColmapGUI.on_sharp_finished |
| FourDGSWorker (instance main_window) | idem | idem → ColmapGUI.on_finished |
| BrushWorker | log/finished | LogsTab.append_log / ColmapGUI.on_brush_finished |
| PostTrainingWorker | log/finished | LogsTab.append_log / ColmapGUI._on_post_training_finished |
| SharpWorker/SharpVideoWorker (depuis run_sharp()) | progress | ConfigTab **et** SharpTab.progress_bar (double câblage, guardé par hasattr) |
| SplatTransformWorker | log/finished | LogsTab.append_log / ColmapGUI._on_splat_transform_finished |

Câblage intra-onglet (îlots isolés, jamais remontés à main_window) : `CleanerTab↔CleanerExportTab`, `CleanerWorker↔CleanerExportTab`, `Extractor360Worker/InstallWorker↔Extractor360Tab`, `FourDGSWorker↔FourDGSTab`, `ExportWorker↔ExportTab`, `ModelCard↔UpscaleTab`, `SessionManager._save_timer↔_do_save`.

Couplage additionnel (non-signal) : `main_window.get_upscale_config()`/`get_extractor_360_config()`/`get_current_params()` lisent directement les widgets de `upscale_tab`, `extractor_360_tab`, `config_tab`, `params_tab` — couplage de type "pull de config", fonctionnellement équivalent au couplage par signal pour l'assemblage des paramètres au lancement.

### Chaînage post-entraînement

Déclencheur : `BrushWorker.finished_signal` → `ColmapGUI.on_brush_finished()`.
1. Lit `post_clean = config_tab.get_post_clean()`, `post_export = config_tab.get_post_export()` (checkboxes `chk_clean_after`/`chk_export_after`).
2. Si succès et (post_clean ou post_export) : instancie `PostTrainingWorker(output_path, post_clean, clean_strength, post_export, export_format)`, câble log/finished, `.start()`.
3. Sinon : affiche directement le dialogue de fin (`_show_training_done_dialog`).

`PostTrainingWorker.run()` (workers.py L720-780) :
1. Glob `*.ply` non-récursif dans `output_path`.
2. Si `clean` : `clean_ply()` par fichier, ajoute le résultat (nettoyé ou original si échec) à `to_export`.
3. Sinon : `to_export` = fichiers PLY originaux.
4. Si `export` : `ExportEngine().export()` par fichier de `to_export`.
5. `finished_signal(True, "Post-traitement terminé…")`.

Clean et export sont deux flags booléens indépendants (pas de flag combiné "then-export") ; quand les deux sont actifs, export s'exécute sur les fichiers nettoyés (dépendance séquentielle clean→export).

### Logique de « mode »

Dispatch dans `ColmapGUI.process()` (L218-340), sur `mode = config_tab.get_training_mode()` (combo `combo_mode`) :
```
if mode == "gsplat":  ... ColmapWorker(extractor_360_params=None) ...
elif mode == "sharp": ... SharpWorker/SharpVideoWorker selon input_type ...
elif mode == "360":   ... ColmapWorker(extractor_360_params=get_extractor_360_config()) ...
elif mode == "4dgs":  ... FourDGSWorker(input_path, fps) ...
```
Pas d'enum/objet stratégie — chaîne brute comparée par `==` à un seul point de dispatch (`process()`), mais avec re-dérivation en aval : `get_extractor_360_config()` recalcule `enabled = (mode=="360")`, et `ColmapWorker.run()` contient son propre gate `if extractor_360_params.get("enabled")` (workers.py:90) — le dispatch de mode est donc dupliqué entre `main_window.process()` (quel worker construire) et `ColmapWorker.run()` (si l'étape 360 s'exécute). Sharp a un second niveau de mode interne (`params.get("mode","image")` → image/vidéo), redispatché indépendamment dans `process()` (L256-264) et `run_sharp()` (L618).

---

## 7. i18n

**Mécanisme** : `LanguageManager` (`app/core/i18n.py`), singleton via `__new__` (L11), Observer pattern. Singleton module-level `_lm = LanguageManager()` (L100) derrière des wrappers libres.
```python
def add_observer(self, callback)             # L21
def _load_translations(self)                  # L26 — assets/locales/{lang}.json, repli en→fr
def load_config(self) / save_config(self)      # L49/L59 — clé "language" dans config.json
def set_language(self, lang_code)              # L74 — recharge + sauvegarde + notifie tous les observateurs
def tr(self, key, *args)                       # L84 — lookup dict + repli str.format
# wrappers module-level : tr(), get_current_lang(), set_language(), add_language_observer()
```
`tr()` : clé absente → utilise `args[0]` si fourni, sinon retourne la clé brute. `set_language()` protège chaque callback observateur en try/except.

**Locales** (`assets/locales/*.json`) : `ar, de, en, es, fr, it, ja, ru, zh` — **516 clés chacune** (comptage à plat, clés imbriquées jointes par `.`). **Diff exhaustif** (union des 9 fichiers vs chaque fichier) : **0 clé manquante** dans n'importe quelle locale — les 9 locales sont parfaitement alignées. Cohérent avec CHANGELOG [1.2.3] (clé orpheline `brush_build_mode` retirée de `de.json`) et [1.5.0] (i18n Upscale ajouté aux 9 locales).

**Re-traduction d'un widget** : chaque onglet/fenêtre s'enregistre en `__init__` (`add_language_observer(self.retranslate_ui)`) et expose `retranslate_ui(self)` sans argument. Trouvé dans 12 fichiers : `main_window.py` + les 11 onglets (sauf `cleaner_export_tab.py`, `cleaner_tab.py`, `splat_transform_tab.py`... — voir tableau §5 pour le détail présent/absent). `set_language()` appelle tous les `retranslate_ui()` enregistrés.

---

## 8. Sécurité (état actuel)

**Points d'appel `validate_path()`** :
```
app/core/sharp_engine.py:75,76,83,93
app/core/extractor_360_engine.py:48,49
app/core/four_dgs_engine.py:120,121
app/core/splat_transform_engine.py:92,93,98
app/core/brush_engine.py:128,129
app/core/base_engine.py:313 (définition), 325 (is_safe_path)
app/core/engine.py:200,224,233
app/core/ply_cleaner.py:105,108,157,158 (via alias validate_path_standalone)
app/core/upscale_engine.py:100,104,107,130,131,137
app/gui/widgets/drop_line_edit.py:44 (appelle sa propre méthode locale _validate_path, L30 — vérif GUI distincte, sans lien avec base_engine)
```
Définition (`base_engine.py:313-321`) : `Path(path).resolve()` + catch `TypeError/ValueError/OSError` → log erreur + `None`. **Docstring explicite : "No containment checks"** — résolution uniquement, pas de confinement/jail. `validate_path_standalone` (L337) même comportement, fonction libre. `is_safe_path()` (L323) ajoute `.exists()`.

**`shell=True`** : `grep -rn "shell=True" app/` → **aucune occurrence réelle**. Seul hit : commentaire dans `splat_transform_engine.py:7` ("shell=True is never used"). `SubprocessRunner.start()` appelle `subprocess.Popen(cmd, ...)` avec `cmd` en liste.

**Allowlist Brush** (`app/core/brush_engine.py:15-20`) :
```python
ALLOWED_FLAGS = {
    "--save-iterations", "--log-level", "--test-split",
    "--start-iter", "--refine-every", "--growth-grad-threshold",
    "--growth-select-fraction", "--growth-stop-iter", "--max-splats",
    "--eval-every", "--export-every", "--max-resolution", "--refine-pose"
}
```
Appliquée dans `build_command()` (~L92-106) sur `params["custom_args"]` (texte libre splitté) : tout token hors allowlist est éliminé avec log d'avertissement. 13 flags autorisés.

**CORS SuperSplat** (`app/core/superplat_engine.py:88-129`, `start_data_server()`) : bind uniquement sur `127.0.0.1`. `CORSRequestHandler.end_headers()` reflète l'`Origin` de la requête si son hostname est `localhost`/`127.0.0.1`, sinon repli sur `http://localhost:{port}`. Pas de restriction explicite `Access-Control-Allow-Methods`/`-Headers` (serveur GET-only via `SimpleHTTPRequestHandler`).

**Sanitisation nom de projet** : aucune fonction `sanitiz*` dans `app/` (0 résultat grep). Vérification inline en liste noire (`engine.py:206`) :
```python
if ".." in self.project_name or "/" in self.project_name or "\\" in self.project_name:
```
Blocklist de sous-chaînes, pas une allowlist regex ; pas de sanitizer dédié.

---

## 9. Tests

**Organisation** : `tests/*.py` (17 fichiers, unitaires, un par moteur/module) + `tests/integration/*.py` (8 fichiers + 2 helpers synthétiques). `tests/conftest.py` mocke PySide6 au scope session (skip si le vrai binding est déjà importé). `tests/integration/conftest.py` réinvoque `_patch_pyqt6()` du conftest racine + ajoute des fixtures d'intégration (`fake_project_dir` avec JPEG 1×1 réels pour que `cv2.imread` réussisse, `mock_resolve_binary`).

**Couverture** :
- Couvert : construction de commandes des moteurs, validation de chemins, `_execute_command()`, dispatch CLI (`test_cli.py`), classes worker (`test_workers.py` — Base/Colmap/Brush/Sharp/SharpVideo/Extractor360), intégration i18n+sécurité, pipeline e2e réel sur données synthétiques.
- **Non couvert** : aucun fichier `test_*_tab.py` — les 11 classes d'onglets GUI (`app/gui/tabs/*.py`) et `app/gui/widgets/*.py` n'ont **aucun test unitaire direct**, y compris leurs implémentations de `retranslate_ui()`. La GUI n'est exercée qu'indirectement via la couche de mock Qt lors de l'import des modules workers/managers.
- **Mock subprocess** : pas de `patch("subprocess.Popen")` direct — repose sur l'interface DIP `IProcessRunner`/`SubprocessRunner` injectable ; les tests injectent un runner mocké (contrat `readline()` en particulier, historique du bug de gel infini en v1.2.2).

**Mock PySide6** (`tests/conftest.py`) : classes stand-in légères (`_MockQThread`, `_MockPyQtSignal`) assignées sur un `MagicMock()` de `PySide6.QtCore` — garde en tête de fichier : si le vrai `PySide6` est déjà importé dans `sys.modules`, le mock est sauté entièrement (pas d'interférence avec une exécution réelle). Variable d'environnement associée : `PYTEST_QT_API=pyside6`.

---

## 10. Dette technique et anomalies repérées

- **`ColmapParams.guided_matching`** : lu par `get_params()` mais jamais écrit par `set_params()` ; widget (`guided_match_check`) désactivé en permanence (`setEnabled(False)`) → champ mort en pratique (§4).
- **`ColmapParams.sequential_overlap`** : aucune UI, aucun flag CLI, seul le défaut (`30`) est jamais atteint malgré `matcher_type="sequential"` sélectionnable dans le combo (§4).
- **`matching_type`** : `set_params()` peut ignorer silencieusement une valeur sauvegardée incompatible avec `feature_type` (repli sur l'état courant du combo, pas d'avertissement utilisateur) (§4).
- **`undistort_images`/`filter_blurry`/`blur_factor`** : source de vérité éclatée entre `ParamsTab` (dataclass) et `ConfigTab` (widgets réels) ; `blur_factor` a deux implémentations indépendantes du mapping texte→float (GUI `main_window.py` vs CLI `commands.py::_blur_factor_from_strength()`) (§4).
- **`ExportTab`** (`app/gui/tabs/export_tab.py`) : orpheline, jamais instanciée par `main_window.py` — code mort côté GUI (mais `ExportEngine`/`ExportWorker` restent utilisés ailleurs, via `PostTrainingWorker`) (§5, §6).
- **`BrushTab.run_standalone()`** : chemin parallèle à `trainRequested`, contourne totalement main_window/BrushWorker (`subprocess.Popen` fire-and-forget, pas de logs/signal finished/post-training) (§6).
- **`FourDGSTab`/`Extractor360Tab`** : instancient leurs propres workers, indépendants de ceux pilotés par `ColmapGUI.process()` via le sélecteur de mode — deux chemins de code par fonctionnalité (§6).
- **Dispatch de mode dupliqué** : `main_window.process()` choisit le worker, mais `ColmapWorker.run()` recontient son propre gate sur `extractor_360_params.enabled` ; le mode Sharp image/vidéo est redispatché indépendamment dans `process()` et `run_sharp()` (§6).
- **`setEnabled(False)`** : 29 occurrences dans `app/gui/`, toutes examinées — correspondent à des états transitoires légitimes (désactivation pendant job en cours), sauf `guided_matching` ci-dessus qui est permanent. `cleaner_export_tab.py:55` accède directement au widget d'un enfant (`self.cleaner_tab.btn_clean.setEnabled(False)`) plutôt que via une API propre — fuite d'encapsulation mineure.
- **`QFileDialog` bruts** : aucun — tous les appels passent par `app/gui/widgets/dialog_utils.py` (`grep -rn "QFileDialog\." app/gui/ | grep -v dialog_utils.py` → vide). Pas d'anomalie ici.
- **Import inter-couches** : `app/gui/main_window.py:200` importe `_apply_robust` (préfixe `_`, privé) depuis `app/cli/commands.py` — la GUI dépend d'un helper interne du CLI plutôt qu'un module `core` partagé. `app/cli/launcher.py:22` importe `ColmapGUI` depuis `app/gui/main_window.py` — attendu (le CLI lance la GUI sans sous-commande).
- **CHANGELOG vs code** : cohérence globale confirmée pour [1.5.0] (PySide6, thèmes, i18n Upscale) et [1.2.3] (clés i18n alignées). Le mécanisme `delete_project_content()` (garde-fou suppression documenté en [1.2.2]) n'a pas été inspecté en détail dans le passage sécurité de cet audit (hors du périmètre grep demandé — `validate_path`/`shell=True`/allowlist/CORS/sanitisation). L'allowlist Brush, le CORS SuperSplat et la liste noire de nom de projet ne sont mentionnés dans aucune entrée CHANGELOG récente malgré leur nature sécuritaire.

---

## Questions ouvertes

1. **Défaut `feature_type` = `SIFT`** alors que `ALIKED_N16ROT`/`ALIKED_N32` existent comme options plus récentes (`FEATURE_TYPES`) — choix de défaut à trancher ou déjà intentionnel (compat matérielle) ?
2. **`guided_matching`** : champ mort par désactivation UI permanente — à réactiver, ou supprimer le champ dataclass/checkbox ?
3. **`sequential_overlap`** : orphelin complet — ajouter un widget, ou retirer le champ et l'option `matcher_type="sequential"` si elle n'est jamais pleinement utilisable ?
4. **Éclatement `undistort_images`/`filter_blurry`/`blur_factor` entre `ParamsTab` et `ConfigTab`** : dual-homing voulu à l'origine, mais source de confusion pour une refonte — faut-il unifier dans un seul onglet/dataclass ?
5. **Deux implémentations du mapping `blur_factor`** (GUI vs CLI) : à fusionner dans `app/core/` pour éviter la divergence ?
6. **`ExportTab` orpheline** : à re-brancher dans `main_window`, ou supprimer définitivement (son moteur/worker restent utilisés via `PostTrainingWorker`) ?
7. **Double chemin Brush** (`trainRequested` orchestré vs `run_standalone()` fire-and-forget) : la refonte doit-elle conserver ce raccourci sans logs, ou l'aligner sur le chemin orchestré ?
8. **Workers dupliqués par fonctionnalité** (main_window vs tab-local pour FourDGS/Extractor360) : fusionner en un seul point d'orchestration lors de la refonte ?
9. **`main_window.py:200` important un helper privé (`_apply_robust`) de `app/cli/commands.py`** : ce helper devrait-il migrer vers `app/core/` comme point de partage légitime CLI/GUI ?
10. **CORS SuperSplat** : reflet d'`Origin` sans restriction de méthodes/headers explicite — actuellement mitigé par le bind `127.0.0.1` uniquement ; à confirmer si suffisant dans le cadre de la refonte (ex. si un futur mode réseau local est envisagé).
