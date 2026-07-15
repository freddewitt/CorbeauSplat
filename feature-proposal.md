# Proposition : Stratégie de tests E2E réels pour Sharp, Upscale, 4DGS et 360 Extractor

## Contexte dans le projet

CorbeauSplat v1.2.2 orchestre sur macOS Apple Silicon une chaîne de reconstruction 3D Gaussian Splatting. Seul le tronçon principal est couvert par des tests e2e réels opt-in :

```
images synthétiques → COLMAP (SfM réel) → Brush (entraînement réel)
                    → PlyCleaner → ExportEngine (SPZ)   [7 tests, marqueur e2e]
```

Quatre moteurs « satellites » restent couverts uniquement par des tests mockés (subprocess remplacé par `MagicMock`) :

| Moteur | Fichier moteur | Tests mockés existants | Rôle réel |
|--------|----------------|------------------------|-----------|
| Sharp | `app/core/sharp_engine.py` | `tests/test_sharp_engine.py` (4 classes, ~10 tests) | Estimation de profondeur Apple ML Sharp → nuage de points PLY par image ou par frame vidéo |
| Upscale | `app/core/upscale_engine.py` + `app/upscayl_manager.py` | `tests/test_upscayl_manager.py` (~15 tests) | Upscaling NCNN via binaire `upscayl-bin` standalone |
| 4DGS | `app/core/four_dgs_engine.py` | `tests/test_four_dgs_engine.py` (2 classes, ~10 tests) | Préparation de datasets multi-caméras pour nerfstudio (ffmpeg → COLMAP → `ns-process-data`) |
| 360 Extractor | `app/core/extractor_360_engine.py` | `tests/test_workers.py::TestExtractor360Worker` (2 tests du worker uniquement) | Extraction de vues perspectives depuis une vidéo 360° via le CLI `engines/extractor_360/src/main.py` |

Le graphe (communautés 3, 6, 110, 143, 46) confirme que ces moteurs partagent tous le patron `BaseEngine` (communauté 7) : méthode `is_installed()`, `_execute_command()` (Template Method, communautés 34/46), injection du `IProcessRunner` (DIP). Le pipeline e2e existant (`tests/integration/test_e2e_pipeline.py`, communauté 79) fournit le modèle de référence : fixture module-scoped, génération synthétique numpy+PIL déterministe, skip automatique si binaires absents, vérification d'artefacts distincts par test.

Particularités critiques déduites du graphe :
- **Sharp** dépend d'un venv dédié `.venv_sharp` (Py 3.11, résolu par `_get_sharp_cmd()` avec 4 fallbacks). En mode vidéo, il appelle ffmpeg puis `predict()` par frame et collecte des `.ply`.
- **Upscale** est le seul à **ne pas** nécessiter de venv : `upscayl-bin` est un binaire NCNN standalone découvert par `find_binary()` (3 emplacements + `which`). Les modèles `.bin/.param` sont requis dans `models/upscayl/` ou à côté du binaire.
- **4DGS** est le plus coûteux : il chaîne `ffmpeg` → COLMAP complet (feature_extractor, exhaustive_matcher, mapper) → `ns-process-data` du venv `.venv_4dgs`. Le rendu dépend de COLMAP (déjà testé) **et** de nerfstudio.
- **360 Extractor** est installé via git clone de `nicolasdiolez/360Extractor` dans `engines/extractor_360/` avec venv `.venv_360`. **Aucun test moteur n'existe** — seules 2 assertions sur le parsing de pourcentage du worker.

## Approche recommandée

### 1. Générateurs de données synthétiques (numpy + PIL uniquement)

Suivre rigoureusement `_synthetic_scene.py` : déterministe via `np.random.default_rng(seed)`, sortie PNG (pas JPEG — les descripteurs SIFT le supportent moins), aucune dépendance à cv2/OpenCV dans le venv de test.

#### 1a. `_synthetic_image.py` — pour Sharp et Upscale

Module unique partagé car les deux moteurs consomment des images 2D simples, mais avec des exigences différentes :

```python
# tests/integration/_synthetic_image.py
def generate_depth_image(out_path: Path, w=640, h=480, seed=7) -> Path:
    """Image RGB avec un dégradé spatial connu + textures multi-octaves.

    Pour Sharp : contenu riche sufficient pour estimer une profondeur non plate
    (zones texturées à plusieurs échelles, comme le fait _make_texture mais 2D).
    Pour Upscale : le dégradé haute fréquence permet de vérifier que le
    suréchantillonnage conserve les détails (test PSNR/perceptuel sur zone centrale).
    """

def generate_upscale_target(out_path: Path, w=160, h=120, seed=11) -> Path:
    """Petite image 160×120 avec motif haute fréquence (lignes + bruit structuré).
    Petite taille = upscale rapide. Le motif permet de vérifier que la sortie est
    effectivement 4× plus grande (640×480) et non une copie brute.
    """
```

Justification : Sharp a besoin de contenu texturé pour produire une profondeur non triviale ; Upscale a besoin d'un petit input (rapidité) avec un motif vérifiable. Deux fonctions, un seul module, ~60 lignes.

#### 1b. `_synthetic_video.py` — pour Sharp (mode vidéo) et 4DGS

```python
def generate_synth_video(out_path: Path, n_frames=8, w=320, h=240,
                         fps=5, seed=7) -> Path:
    """Génère un MP4 court via imageio ou numpy→PIL→frames→ffmpeg.

    IMPORTANT : 4DGS Sharp-video nécessitent un vrai conteneur vidéo lisible par ffmpeg.
    Deux approches :
      (a) Générer des PNG + appeler ffmpeg (déjà requis pour les tests).
      (b) imageio.get_writer('ffmpeg') si imageio disponible dans venv test.
    Préférer (a) car ffmpeg est déjà une dépendance de test requise, et imageio
    n'est pas garanti dans le venv minimal de test.
    Donc : générer n_frames PNG déterministes (déplacement d'un cube texturé),
    puis appeler `ffmpeg -framerate fps -i frame_%03d.png out.mp4` (H.264 libx264).
    """
```

Pour 4DGS, il faut **plusieurs caméras** (le moteur attend un dossier de vidéos `.mp4/.mov/.avi/.mkv`). Le générateur produira `N_CAMERAS` vidéos courtes montrant la même scène sous des angles différents — réutiliser le cube texturé de `_synthetic_scene.py` mais en séquences de frames (mouvement orbital léger par caméra).

#### 1c. `_synthetic_equirectangular.py` — pour 360 Extractor

```python
def generate_360_image(out_path: Path, w=2048, h=1024, seed=7) -> Path:
    """Image équirectangulaire 2:1 avec contenu texturé sur toute la sphère.

    Le 360Extractor découpe cette image en vues perspectives selon layout/camera_count.
    Besoin : contenu variant en longitude ET latitude (sinon découpe trivial faux-positif).
    Méthode : bruit multi-octave comme _make_texture, mais avec gradient longitudinal
    + marqueurs colorés à positions angulaires connues (rouge à 0°, vert à 90°, etc.)
    pour vérifier post-extraction que les bonnes vues sont produites.
    """

def generate_360_video(out_path: Path, n_frames=6, w=1024, h=512,
                       fps=2, seed=7) -> Path:
    """Vidéo 360° courte (ratio 2:1), frames où le contenu bouge légèrement.
    Nécessaire pour tester le mode vidéo + interval + adaptive + motion_threshold.
    """
```

Le ratio 2:1 est **obligatoire** — c'est la signature d'une image équirectangulaire que le 360Extractor valide en entrée.

### 2. Structure des fichiers de test et stratégie de marqueurs

**Un fichier par moteur** sous `tests/integration/` — cohérent avec le graphe où chaque moteur est dans une communauté distincte (3, 6, 46, 143) et facilite le debug ciblé :

```
tests/integration/
├── _synthetic_scene.py          (existant — COLMAP/Brush)
├── _synthetic_image.py          (nouveau — Sharp + Upscale)
├── _synthetic_video.py          (nouveau — Sharp vidéo + 4DGS)
├── _synthetic_equirectangular.py (nouveau — 360 Extractor)
├── test_e2e_pipeline.py         (existant — 7 tests)
├── test_e2e_sharp.py            (nouveau)
├── test_e2e_upscale.py          (nouveau)
├── test_e2e_4dgs.py             (nouveau)
├── test_e2e_extractor_360.py    (nouveau)
└── _e2e_helpers.py              (nouveau — facteurs communs, voir §3)
```

**Marqueurs : garder `e2e` unique + marqueurs spécifiques en complément.** Pytest supporte l'intersection/exclusion de marqueurs. Configuration `pyproject.toml` mise à jour :

```toml
markers = [
    "e2e: pipeline end-to-end réel avec vrais binaires — lent, opt-in (couvre tous)",
    "e2e_sharp: e2e réel Sharp (nécessite .venv_sharp + ffmpeg)",
    "e2e_upscale: e2e réel Upscale (nécessite upscayl-bin + modèles)",
    "e2e_4dgs: e2e réel 4DGS (nécessite .venv_4dgs + ffmpeg + colmap)",
    "e2e_360: e2e réel 360 Extractor (nécessite .venv_360)",
]
```

`addopts = "-m 'not e2e'"` reste — désélectionne tout par défaut. On sélectionne finement :

```bash
pytest -m e2e              # tous (comportement inchangé)
pytest -m e2e_sharp        # Sharp uniquement
pytest -m "e2e and not e2e_4dgs"  # tout sauf le plus coûteux
```

Justification du choix (vs. marqueurs multiples exclusifs) : la barre `pytest -m e2e` actuelle doit continuer à capturer **tous** les e2e (attente utilisateur explicite), donc `e2e` reste un umbrella. Les marqueurs spécifiques permettent le filtrage et l'exclusion des moteurs non installés sans skip-noise dans le rapport.

### 3. Skip conditions (binaires / venvs) — module `_e2e_helpers.py`

Chaque moteur a sa propre chaîne de dépendances. Centraliser dans un helper pour éviter la duplication et harmoniser les messages :

```python
# tests/integration/_e2e_helpers.py
from __future__ import annotations
from pathlib import Path
import shutil, sys
from app.core.system import resolve_binary, resolve_project_root

def _venv_python(venv_name: str) -> Path | None:
    root = resolve_project_root()
    py = root / venv_name / "bin" / "python"
    return py if py.exists() else None

def sharp_ready() -> tuple[bool, str]:
    """Sharp : venv_sharp OU module sharp importable OU binaire sharp sur PATH."""
    from app.core.sharp_engine import SharpEngine  # is_installed wrapper
    # Mais on force une vérification plus stricte pour l'e2e :
    venv = resolve_project_root() / ".venv_sharp" / "bin" / "sharp"
    if venv.exists():
        return True, f"sharp venv: {venv}"
    if shutil.which("sharp"):
        return True, "sharp sur PATH"
    if _venv_python(".venv_sharp"):
        return True, "python venv_sharp + module sharp"
    return False, ".venv_sharp absent (sharp ni binaire ni python/module)"

def upscale_ready() -> tuple[bool, str]:
    from app.upscayl_manager import find_binary, get_effective_models_dir
    b = find_binary()
    if not b:
        return False, "upscayl-bin introuvable (./bin, /Applications/Upscayl.app, PATH)"
    m = get_effective_models_dir()
    if m and any(m.glob("*.bin")):
        return True, f"{b} + modèles {m}"
    return False, f"upscayl-bin trouvé ({b}) mais modèles .bin/.param manquants"

def fourdgs_ready() -> tuple[bool, str]:
    missing = []
    if not resolve_binary("ffmpeg"): missing.append("ffmpeg")
    if not resolve_binary("colmap"): missing.append("colmap")
    ns = resolve_project_root() / ".venv_4dgs" / "bin" / "ns-process-data"
    if not ns.exists():
        # Mode dégradé testable mais incomplet — on exige ns-process-data
        missing.append("ns-process-data (.venv_4dgs)")
    return (not missing), ", ".join(missing)

def extractor_360_ready() -> tuple[bool, str]:
    from app.core.extractor_360_engine import Extractor360Engine
    eng = Extractor360Engine()
    if eng.is_installed():
        return True, f"{eng.venv_python} + {eng.script_path}"
    return False, ".venv_360 ou engines/extractor_360/src/main.py absent"

# Décorateurs de skip prêts à l'emploi
import pytest
requires_sharp = pytest.mark.skipif(
    not sharp_ready()[0], reason=f"e2e Sharp : {sharp_ready()[1]}")
requires_upscale = pytest.mark.skipif(
    not upscale_ready()[0], reason=f"e2e Upscale : {upscale_ready()[1]}")
requires_4dgs = pytest.mark.skipif(
    not fourdgs_ready()[0], reason=f"e2e 4DGS : {fourdgs_ready()[1]}")
requires_360 = pytest.mark.skipif(
    not extractor_360_ready()[0], reason=f"e2e 360 : {extractor_360_ready()[1]}")
```

Évaluation **au moment de l'import** du module de test (comme `_COLMAP`/`_BRUSH` dans `test_e2e_pipeline.py`), pas dans la fixture — sinon pytest-collection-time collecte des tests et le skip bruyant apparaît à chaque run.

### 4. Ordonnancement des priorités et justification

| Priorité | Moteur | Complexité | Justification |
|----------|--------|-----------|---------------|
| **P0** | Upscale | **S** | Binaire standalone (pas de venv), une image d'entrée, un fichier de sortie. Vérification triviale : output `4×` plus grand que l'input, format correct, non vide. Le plus rapide à mettre en place et à exécuter (<5s). Pose le pattern pour les autres. |
| **P1** | 360 Extractor — **unit tests** | **S** | Le moteur a **zéro** test aujourd'hui. Créer le module `tests/test_extractor_360_engine.py` (mocks) doit précéder l'e2e (cf. §5). Pas de binaire requis → peut être livré immédiatement, sans infrastructure. |
| **P2** | Sharp (mode image) | **M** | Venv `.venv_sharp` requis + import du module `sharp`. `predict()` sur une image → PLY. Vérification de la structure PLY (en-tête + points non vides). Réutilise `_synthetic_image.generate_depth_image`. |
| **P3** | 360 Extractor — **e2e** | **M** | Dépend des tests unitaires (P1) et de l'installation venv_360. Générateur équirectangulaire spécifique. Lacunes dans la doc du 360Extractor externe (cf. risques) → itération probable. |
| **P4** | Sharp (mode vidéo) | **M** | Combinaison Sharp + ffmpeg sur petit MP4 synthétique. Réutilise `_synthetic_video`. Plus lent (extraction N frames + predict par frame). |
| **P5** | 4DGS | **L** | Triple dépendance (ffmpeg + colmap + nerfstudio venv). Plusieurs caméras synthétiques + COLMAP complet. Temps d'exécution élevé (~minutes). Risque de dégradation du graphe COLMAP sur scène trop synthétique. À faire en dernier. |

### 5. Conception du module de tests unitaires pour Extractor 360

`tests/test_extractor_360_engine.py` à créer — suit rigoureusement le squelette de `tests/test_four_dgs_engine.py` (mêmes classes de test, mêmes patterns de mock). Concerne `Extractor360Engine` uniquement (pas le worker, déjà couvert par `TestExtractor360Worker`).

**Classes et tests proposés :**

```python
class TestExtractor360EngineCallbacks:
    """Vérifie le report de tr()/i18n comme le font les autres moteurs."""

class TestExtractor360EnginePaths:
    def test_root_dir_resolved(self): ...
    def test_engines_dir_resolved(self): ...
    def test_script_path_is_src_main_py(self): ...

class TestExtractor360EngineIsInstalled:
    """Même pattern que FourDGSEngine.check_nerfstudio."""
    def test_is_installed_when_venv_and_script_exist(self, tmp_path): ...
    def test_is_installed_false_when_venv_missing(self, tmp_path): ...
    def test_is_installed_false_when_script_missing(self, tmp_path): ...

class TestExtractor360EngineInstall:
    def test_install_delegates_to_setup_dependencies(self): ...
    def test_uninstall_delegates(self): ...

class TestExtractor360EngineRunExtraction:
    """Tests de construction de commande — comme TestBuildCommandParams brush."""
    _DEFAULT_PARAMS = {"interval": 5, "format": "jpg", "resolution": 1024,
                       "camera_count": 4, "quality": 80, "layout": "grid"}

    def test_basic_command(self, tmp_path): ...
    def test_command_includes_input_output(self): ...
    def test_interval_param_mapped_to_cli(self): ...
    def test_format_param_mapped(self): ...
    def test_resolution_param_mapped(self): ...
    def test_camera_count_param_mapped(self): ...
    def test_quality_param_mapped(self): ...
    def test_layout_param_mapped(self): ...
    def test_ai_mask_adds_flag(self): ...
    def test_ai_skip_adds_flag(self): ...
    def test_adaptive_adds_flag_and_motion_threshold(self): ...
    def test_adaptive_without_motion_threshold(self): ...

class TestExtractor360EngineRunExtractionSecurity:
    """Validation des chemins — today's only « sécurité » invariants partagés."""
    def test_invalid_input_path_returns_false(self): ...
    def test_invalid_output_path_returns_false(self): ...
    def test_returns_false_when_not_installed(self): ...

class TestExtractor360EngineRunExtractionEnv:
    def test_pythonpath_isolated_from_app(self):
        """env.pop('PYTHONPATH') doit être appliqué — anti-fuite de packages."""
    def test_cwd_is_extractor_dir(self): ...

class TestExtractor360EngineRunExtractionProgress:
    def test_line_handler_extracts_percentage(self):
        """Vérifie que '[42%] ...' → progress_callback(42)."""
    def test_line_handler_ignores_non_percentage(self): ...
    def test_returns_false_on_cancel(self): ...
    def test_returns_true_on_zero_returncode(self): ...
```

Mock strategy : `BaseEngine.__new__` + `MagicMock` du `runner` (pattern `test_four_dgs_engine.py`), `resolve_project_root` patché vers `tmp_path`, `engine.venv_python` et `engine.script_path` surchargés. ~25 tests, ~250 lignes.

### 6. Détail e2e par moteur (squelette de chaque test file)

Tous suivent le patron `test_e2e_pipeline.py` : `pytestmark = pytest.mark.e2e` + `pytest.mark.e2e_<moteur>`, fixture module-scoped exécutant le pipeline réel une fois, tests vérifiant des artefacts distincts.

#### test_e2e_upscale.py (P0)
```python
@pytestmark = [pytest.mark.e2e, pytest.mark.e2e_upscale]
@requires_upscale
class TestE2EUpscale:
    @pytest.fixture(scope="module")
    def upscale_run(self, tmp_path_factory):
        # generate small PNG (160×120), load_model(scale=4), upscale_image -> 640×480
        ...
    def test_output_file_exists(self, upscale_run): ...
    def test_output_dimensions_4x(self, upscale_run):
        # PIL.Image.open → size == (640, 480)
    def test_output_is_not_trivial_copy(self, upscale_run):
        # hash différent de l'input, et taille fichier >
    def test_reproducible_format(self, upscale_run): ...  # png par défaut
```

#### test_e2e_sharp.py (P2)
```python
@pytestmark = [pytest.mark.e2e, pytest.mark.e2e_sharp]
@requires_sharp
class TestE2ESharpImage:
    @pytest.fixture(scope="module")
    def sharp_run(self, tmp_path_factory):
        # generate_depth_image 640×480, engine.predict(image, out_dir)
        ...
    def test_returns_zero(self, sharp_run): ...
    def test_ply_artifact_produced(self, sharp_run):
        # au moins un .ply dans out_dir
    def test_ply_has_valid_header(self, sharp_run):
        # parse "ply\nformat ascii 1.0" ou binary
    def test_ply_point_count_nontrivial(self, sharp_run):
        # > 1000 vertices
```

Mode vidéo séparé dans une seconde `class TestE2ESharpVideo` marquée `@requires_sharp` + skipif ffmpeg manquant.

#### test_e2e_4dgs.py (P5)
```python
@pytestmark = [pytest.mark.e2e, pytest.mark.e2e_4dgs]
@requires_4dgs
class TestE2E4DGS:
    @pytest.fixture(scope="module")
    def dataset_run(self, tmp_path_factory):
        # generate N_CAMERAS vidéos synthétiques, engine.process_dataset(...)
        ...
    def test_extracted_frames_per_camera(self, dataset_run): ...
    def test_colmap_sparse_model_built(self, dataset_run): ...
    def test_ns_process_data_transforms(self, dataset_run): ...
    def test_no_temp_frames_leftover(self, dataset_run): ...
```

#### test_e2e_extractor_360.py (P3)
```python
@pytestmark = [pytest.mark.e2e, pytest.mark.e2e_360]
@requires_360
class TestE2EExtractor360:
    @pytest.fixture(scope="module")
    def extract_run(self, tmp_path_factory):
        # generate_360_image 2048×1024, run_extraction(
        #   params={"camera_count": 4, "layout": "grid", "format": "jpg", ...})
        ...
    def test_returns_true(self, extract_run): ...
    def test_output_images_count_matches_camera_count(self, extract_run): ...
    def test_output_images_are_not_equirectangular(self, extract_run):
        # ratio != 2:1 (vues perspectives découpées)
    def test_output_resolution_matches_param(self, extract_run): ...
```
Variante vidéo séparée avec `generate_360_video` + params `interval` et `adaptive`.

## Complexité estimée

| Moteur | Complexité | Effort | Justification |
|--------|-----------|--------|----------------|
| Upscale e2e (P0) | **S** | 0.5 j | Générateur trivial + un seul moteur simple. Pattern posé. |
| 360 Extractor unit tests (P1) | **S** | 0.5 j | Aucune dépendance runtime. Pattern mocké éprouvé (`test_four_dgs_engine.py`). |
| Sharp image e2e (P2) | **M** | 1 j | Venv à vérifier + parser PLY en sortie + générateur texturé. |
| 360 Extractor e2e (P3) | **M** | 1–1.5 j | Format équirectangulaire + CLI externe sous-documented + itérations. |
| Sharp video e2e (P4) | **M** | 1 j | Vidéo synthétique + ffmpeg + predict par frame + cleanup. |
| 4DGS e2e (P5) | **L** | 2–3 j | Triple dépendance + COLMAP complet + données multi-caméras + risques de régression de reconstruction. |
| **Total** | — | **~6–7 j** | Générateurs + helpers amortis entre moteurs. |

## Risques

1. **Sortie du 360Extractor mal connue.** Le code externe `engines/extractor_360/src/main.py` n'est pas dans le dépôt (git clone à l'install). Son format de sortie exact (noms de fichiers, structure de dossiers) est inféré du CLI args, pas vérifié. Les assertions sur `camera_count` images risquent d'être fausses si le layout produit un autre nombre. **Mitigation :** P1 (unit tests) avant P3 ; premiers tests e2e basés sur « au moins une image produite », puis raffinés.

2. **4DGS dépend de COLMAP + nerfstudio.** Deux couches successives où la scène synthétique peut échouer : pas assez de features (déjà résolu pour le pipeline COLMAP/Brush, mais avec des vues 24 × 800×600 — les vidéos 4DGS seront plus petites et moins texturées). Le `mapper` COLMAP peut produire un modèle sparse vide → `ns-process-data` en échec. **Mitigation :** réutiliser `_synthetic_scene.generate_scene` pour alimenter les frames des vidéos, validation itérative sur de petites populations.

3. **Venvs non installés en CI/dev sans GUI.** `.venv_sharp`, `.venv_4dgs`, `.venv_360` sont créés via l'installeur de l'app (PipEngine). En environnement CI minimal, ces venvs n'existeront pas et les tests e2e seront systématiquement skip. **Mitigation :** skip silencieux via les marqueurs `_e2e_helpers.py` ; CI peut opt-in en installant via `python -m app.scripts.setup_dependencies` avant `pytest -m e2e_sharp`.

4. **upscayl-bin téléchargé à la volée.** Le binaire n'est pas versionné. Une version récente peut introduire un flag incompatible ou un nouveau format de sortie. **Mitigation :** assertions robustes (dimensions via PIL, non-vide, ratio), pas sur le contenu exact ; tolérance sur le scale (vérifier `>= 3.5×` plutôt que `== 4×` selon le modèle).

5. **Sharp model checkpoint optionnel.** `predict()` accepte un `-c` mais n'exige pas de checkpoint si le module sharp fournit un défaut. Si la version installée exige un checkpoint absent, le smoke test échouera. **Mitigation :** skip additionnel si `sharp predict -h` indique l'obligation d'un checkpoint.

6. **`_synthetic_video.py` via ffmpeg de test.** Si ffmpeg n'est pas dans le venv de test (mais pytest l'utilise déjà pour 4DGS/Sharp), le générateur doit échouer proprement en skip et non en collection-error. **Mitigation :** skipif `resolve_binary("ffmpeg") is None` au niveau du module.

7. **Tests e2e lents accumulés.** Avec 4 nouveaux moteurs e2e, `pytest -m e2e` peut passer de ~2 min (pipeline actuel) à 10+ min. **Mitigation :** marqueurs spécifiques permettent `pytest -m "e2e and not e2e_4dgs"` pour le développement rapide ; 4DGS relégué en job séparé le cas échéant.

## Points d'intégration (fichiers impactés, déduits du graphe)

| Fichier | Nature de l'impact |
|---------|--------------------|
| `pyproject.toml` | Ajout des 4 marqueurs `e2e_*` dans la section `markers` (communauté 25/79). |
| `tests/integration/_synthetic_image.py` | **Nouveau** — génér Sharp + Upscale. |
| `tests/integration/_synthetic_video.py` | **Nouveau** — génér MP4 (Sharp vidéo + 4DGS). |
| `tests/integration/_synthetic_equirectangular.py` | **Nouveau** — génér image/vidéo 360°. |
| `tests/integration/_e2e_helpers.py` | **Nouveau** — skip conditions centralisées. |
| `tests/integration/test_e2e_upscale.py` | **Nouveau** — dépend `app.core.upscale_engine.UpscaleEngine`, `app.upscayl_manager.run_upscayl` (communautés 110/133). |
| `tests/integration/test_e2e_sharp.py` | **Nouveau** — dépend `app.core.sharp_engine.SharpEngine.predict` et `process_video_frames` (communauté 6). |
| `tests/integration/test_e2e_4dgs.py` | **Nouveau** — dépend `app.core.four_dgs_engine.FourDGSEngine` (communauté 3), `resolve_binary` (communauté 7). |
| `tests/integration/test_e2e_extractor_360.py` | **Nouveau** — dépend `app.core.extractor_360_engine.Extractor360Engine` (communauté 143/46). |
| `tests/test_extractor_360_engine.py` | **Nouveau** — mock unit tests du moteur (P1, prérequis). |
| `tests/integration/test_e2e_pipeline.py` | **Pas de modification** — référence à conserver intacte. |
| `app/core/upscale_engine.py` / `sharp_engine.py` / `four_dgs_engine.py` / `extractor_360_engine.py` | **Pas de modification** — les tests consomment l'API publique existante. |
| `app/upscayl_manager.py` | **Pas de modification** — `find_binary`, `get_effective_models_dir`, `run_upscayl` déjà exposés. |
| `app/scripts/installers/extractor_360.py` | **Pas de modification** — utilisé transitivement pour install en CI. |

Aucun changement de code applicatif requis : la proposition est strictement additive côté tests, conformément à la contrainte de ne pas déstabiliser les moteurs éprouvés.