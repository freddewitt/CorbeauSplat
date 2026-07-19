## Session 1 — 2026-07-05 — Bootstrap amorçage

**Lot** : Bootstrap amorçage — AGENTS.md canonique, CLAUDE.md, manifest.md (v1.1.0), journal, archiviste, commandes reprise/cloture, graphify (1649 nœuds). Aucun code applicatif modifié.

**Fichiers** : AGENTS.md, CLAUDE.md, manifest.md, journal.md, journal.jsonl, journal_archive.md, .opencode/agent/archiviste.md, .claude/agents/archiviste.md, .opencode/command/reprise.md, .opencode/command/cloture.md, .claude/commands/reprise.md, .claude/commands/cloture.md, graphify-out/

**Décisions** :
- Canonisation AGENTS.md avec règles de style et permissions
- manifest.md mis à jour v1.1.0 + RESTE À FAIRE
- Graphify construit en mode code-only (pas de clé LLM)

**Pièges** : pyproject.toml encore à 1.0.5 alors que code à 1.1.0

## 2026-07-06 (session 3) — Optimisation Apple Silicon + responsive GUI

**Infra** : audit confirmé solide. Get_optimal_threads P-cores ✓, get_device MPS ✓, VideoToolbox ✓, clonefile APFS ✓, nice+setsid ✓, watchdog thermique ✓, RAM adapt ✓. 

**Bug fixé** : `app/core/system.py` adapt_max_splats — branche morte `elif thermal=="warning"` (get_thermal_state ne renvoie jamais "warning", seulement nominal/fair/serious/critical) remplacée par paliers réels : fair→0.75, serious→0.5, critical→0.2. Docstring mise à jour. 2 tests concernés ✓.

**GUI responsive** : 4 onglets (config, sharp, extractor_360, four_dgs) empilaient contenu sans QScrollArea → coupé sur écran court. Enveloppés dans QScrollArea(setWidgetResizable=True). Superplat aussi enveloppé par cohérence.

**Minor fixes** : word-wrap sur ModelCard (upscale_widgets) + 2 labels d'aide (upscale_tab) → fin overflow horizontal. Validés offscreen.

**Reste** : code mort UI optionnel (ExportTab non monté, import QProgressDialog), tests e2e, 10 tests préexistants en échec, i18n complet.

## Session 4 (2026-07-06) — Analyse COLMAP + 4 améliorations SfM

Analyse engine COLMAP (app/core/engine.py) et params croisée FAQ COLMAP 2025 + GLOMAP paper. Config déjà moderne (ALIKED/LightGlue, DSP-SIFT, view graph, GLOMAP). 4 améliorations livrées + passage SIFT par défaut :

1. **params.py** — feature_type='SIFT' (défaut), estimate_affine_shape=True → DSP-SIFT complet (force CPU).
2. **engine.py feature_matching** — branche 'vocab_tree' implémentée (corrige bug latent : tombait en exhaustif).
3. **engine.py feature_matching** — loop_detection vidéo : --SequentialMatching.loop_detection 1 (SIFT only).
4. **engine.py mapper** — fallback colmap mapper incrémental si GLOMAP invalide (méthode _has_valid_sparse_model).
5. **params_tab.py** — alignée : combo feature SIFT, affine cochée, getattr → SIFT/SIFT_BRUTEFORCE.

**Tests** : 30/34 pass (4 préexistants : TestDeleteProjectContent + test_default_for_aliked).
**Graphify** : 1967 nœuds, 3548 arêtes, 137 communautés.
**Caveats** : SIFT+affine force CPU (lent, robuste) ; vocab_tree/loop_detection téléchargent arbre (connexion 1e fois).

## Session 5 (2026-07-06) — Réparation suite tests + audit i18n + CHANGELOG 1.2.2

**Réparation tests** : gel infini + 13 échecs → 262 pass, 2 skip, 0 fail.
- **Cause racine** : refactor session 1 (`_execute_command()` → `runner.readline()` en boucle `while True`), mais 4 fichiers de tests mockaient encore `stdout_iter()`. `MagicMock().readline()` ne renvoie jamais "" (EOF) → boucle infinie.
- **Fix** : mocks stubbent `readline=""` (EOF). test_four_dgs_engine.py, test_sharp_engine.py. Idem test_colmap_engine.py, test_upscayl_manager.py, test_workers.py, test_cli.py pour pollution cv2.
- **Pollution cv2** : 5 fichiers injectaient `sys.modules["cv2"]=MagicMock()` en aveugle → écrasait vrai cv2 pour toute session, cassait 4 tests colmap_pipeline selon ordre collecte. Fix : import réel d'abord, MagicMock seulement si ImportError (headless CI).
- **Fixtures** : SessionManager réalignée (structure v1.0.6 composite cleaner_export_tab), mock conftest pour sparse/0/, test GLB export skip gracieux si trimesh/open3d absents.

**Sécurité `delete_project_content`** : garde minimale (choix utilisateur). Bloque : "/" / $HOME / dossier app / tous ancêtres (via `is_relative_to`). Projets utilisateur (Desktop/Documents) supprimables. 2 tests réécrits + 1 ajouté (test_path_ancestor_of_home_blocked).

**CHANGELOG 1.2.2** (2026-07-06, anglais) : DSP-SIFT défaut, loop_detection séquentiel, vocab_tree matcher, fallback mapper incrémental, 5 onglets QScrollArea, adapt_max_splats fair/serious/critical, delete_project_content garde, tests réparés.

**Audit i18n** : 459 clés fr.json + en.json vérifiées (1 par 1), scan morphologique (aucune terminaison ES), mapping i18n ok (Français→fr.json, etc.), 9 locales identiques. Seul défaut : confirm_reset ES valeur incohérente (long avertissement vs short label) — NON corrigé.

**Git** : commits 62a1531 (25 fichiers, +326/-66 sessions 3-5) + fd04f50 (.gitignore .tokensave/) poussés origin/main.

## Session 6 (2026-07-06) — Reprise

Synchro versions : app/__init__.py + pyproject.toml 1.2.0 → 1.2.2 (alignés CHANGELOG + manifest).
Tests intégration validés (32 pass, 1 skip). Commits 08fb98b + 97a519b poussés localement.
Orchestrateur a retiré « synchro versions » du RESTE À FAIRE. Restent : confirm_reset ES, e2e absent.

### 2026-07-07 (session 1)
Réparation SharpEngine (ModuleNotFoundError: sharp). Cause : dossier `engines/sharp/` source disparu → install éditable cassée. Fix : `SharpEngineDep().install()` reclone dépôt Apple et rétablit éditable. Aucun code modifié. Graphify 2 commits derrière HEAD (non bloquant). RESTE À FAIRE inchangé : confirm_reset ES incohérent, tests e2e réels absents.

## 2026-07-06 (session 6) — Reprise — synchro versions + validation tests intégration

- Synchro versions : app/__init__.py + pyproject.toml passés 1.2.0 → 1.2.2 (alignés CHANGELOG + manifest).
- Tests intégration validés : 32 pass, 1 skip (tests/integration/).
- Commits : 08fb98b (chore: sync version), 97a519b (docs: journal + manifest).
- Git : 2 commits locaux d'avance sur origin/main.
- RESTE À FAIRE mis à jour : point 'synchro versions' retiré. Restent : confirm_reset ES incohérent, tests e2e réels absents.
- Fichiers modifiés : app/__init__.py, pyproject.toml, journal.md, journal.jsonl, manifest.md.
- Graphify rebuild : non.

## Session 2026-07-09 (1)

**Lot** : Amorçage complété + tests e2e réels + feature « Ouvrir le splat »

**Fichiers créés** : tests/integration/_synthetic_scene.py, test_e2e_pipeline.py ; .opencode/agent/ (9 agents : orchestrateur, chercheur, integrateur, optimiseur, refonteur, testeur, validateur, archiviste)

**Fichiers modifiés** : pyproject.toml (e2e marker), app/gui/main_window.py, assets/locales/*.json (9, +2 clés), .claude/agents/ (4 : blocs Interdits)

**Environnement** : opencv-python-headless .venv 4.13

**Décisions** : Tests e2e RÉELS COLMAP→Brush→clean→export SPZ, scène synthétique numpy+PIL (pas data/réseau, opt-in 'pytest -m e2e'), 9 agents .opencode/ créés, hook graphify post-commit + post-checkout.

**Pièges** : cv2 mock pollution cassant tests COLMAP (fix install), COLMAP 2 modèles features faibles (résolu PNG multi-octave), numpy 2.x ptp() supprimé, pytest mark skipif ne décore pas fixture.

**Tests** : 263 pass/1 skip (défaut) ; 7 pass ~21s (e2e). **Commits** : 2e82496 + ff3bb75 poussés.


## 2026-07-10 (session 1) — Feature destination perso checkpoints Brush

Champ optionnel « Destination des checkpoints » + Parcourir dans groupe Sortie config_tab. Vide → défaut (`<dataset>/checkpoints`).
Mode COLMAP→Brush auto : checkpoints → `<dest>/<nom_projet>/` ; après succès seul .ply récent conservé (intermédiaires + vides supprimés).
Mémorisé sessions (get_state/set_state), traduit 9 locales.

**Décision** : nettoyage « dernier checkpoint » UNIQUEMENT destination perso renseignée (flux défaut garde tous — mode Refine les cherche).

**Fichiers** : config_tab.py (UI, browse, state, retranslate) ; main_window.py (train_brush, keep_only_latest) ; workers.py (param, _prune_to_latest_checkpoint) ; 9 locales (label_ckpt_dest, ckpt_dest_placeholder, ckpt_dest_tip) ; test_workers.py (+2 tests, worker.keep_only_latest=False dans test_run_success).

Tests 264 pass, 0 fail, 2 skip. py_compile OK. Graphify 2027 nœuds, 3662 arêtes.

Working tree non committé. RESTE : (1) commit ; (2) e2e réel Sharp/Upscale/4DGS/360 ; (3) alléger manifest.md.
## Session 2026-07-12 — Bugfix SplatTransform + e2e P0/P1/P2 livrés

### Contexte
Reprise session 2026-07-10 (feature checkpoints Brush, working tree non committé).

### Déroulé
**1. Bugfix SplatTransformTab crash**
- `_browse_input()` ligne 227 ne déstructurait pas `QFileDialog.getOpenFileName()` (retourne tuple PyQt6).
- Fix : `path = get_open_file_name(` → `path, _ = get_open_file_name(`.
- Fichier : `app/gui/tabs/splat_transform_tab.py:227`.
- Tests : 266 pass, 2 skip, 0 fail.

**2. Tests e2e réels — phases P0, P1, P2**
- P0 (Upscale e2e) : `_synthetic_image.py` (générateur 160×120) + `test_e2e_upscale.py` (4 tests, upscayl-bin). 4 pass.
- P1 (360 Extractor unit) : `test_extractor_360_engine.py` (303 lignes, 25 tests mock). 25 pass.
- P2 (Sharp image e2e) : `generate_depth_image()` (640×480) + `test_e2e_sharp.py` (4 tests, Sharp Apple ML, 142s). 4 pass.
- Marqueurs pytest : `e2e_sharp`, `e2e_upscale`, `e2e_4dgs`, `e2e_360` (pyproject.toml).
- Proposition : `feature-proposal.md` (407 lignes, design P3-P5).

### État final
- Tests : 291 pass, 2 skip, 15 deselected, 0 fail.
- Nouveaux fichiers : 5 (3 test modules + 1 generator + 1 proposal).
- Fichiers modifiés : 2 (splat_transform_tab.py:227, pyproject.toml marqueurs).
- Working tree NON COMMITTÉ (cumule session 2026-07-10 + cette session).

### RESTE À FAIRE
1. Commit working tree
2. P3 : 360 Extractor e2e (.venv_360 requis)
3. P4 : Sharp vidéo e2e (ffmpeg + Sharp predict par frame)
4. P5 : 4DGS e2e (ffmpeg + COLMAP + nerfstudio)
5. Alléger manifest.md
6. SPZ export test (préexistant échec)

### Pièges
- `getOpenFileName` tuple PyQt6 : seul SplatTransform manquait la déstructuration (corrigé).
- Sharp predict ~142s Apple Silicon (timeout tests 300s).

## 2026-07-15 Session 2 — Allègement manifest.md + audit SRP ColmapEngine

**Lot** : Allègement manifest.md + audit SRP ColmapEngine + commits P0-P2 e2e

**Modifications clés** :
- manifest.md réduit 227→97 lignes : Architecture/Patterns/Engines/Dependencies/Security → résumé + pointeur graphify
- Commit 12f260f : bugfix SplatTransformTab._browse_input() tuple PyQt6 (ligne 227) + tests e2e P0-P2
- Audit SRP ColmapEngine (~1006 lignes) : extraction colmap_commands.py (178 lignes, 5 fonctions pures)
- Commit 3f8e51d : refactor orchestration vs construction CLI COLMAP ; engine.py 1006→901

**Décisions** :
- test_export_spz_created revérifié passe systématiquement ; "known issue" retiré manifest
- ColmapEngine.mapper() garde logique repli global→incremental ; signatures inchangées
- Autres méthodes jugées non-extractibles (étapes pipeline une fois chacune)
- uv.lock (891 lignes, no [tool.uv]) laissé untracked volontairement

**Résultats** :
- 292 passed, 1 skipped, 15 deselected
- Vérification manuelle Apple Silicon OK ("ça a fonctionné")
- 2 commits d'avance origin/main (non pushé)


### 2026-07-17 (session 3) — Régénération complète du graphe graphify-out/

123 fichiers scannés (97 code, 11 docs, 12 images, 0 vidéo). Extraction : 1950 nœuds AST + 75 nœuds sémantiques = 2016 nœuds extraits → 2002 nœuds après build, 3747 arêtes, 120 communautés. 30 communautés labellisées manuellement. HTML interactif généré. 92% EXTRACTED, 8% INFERRED, 0% AMBIGUOUS. Pas de code modifié, pas de feature livrée. État inchangé : v1.2.2, 292 pass, 1 skip, 0 fail. 2 commits en avance sur origin/main (non pushé). RESTE À FAIRE inchangé : P3 (e2e 360), P4 (e2e Sharp vidéo), P5 (e2e 4DGS).

## Session 2026-07-17/4 — Bugfix Brush disque externe + Audit complet + Corrections C1–I5

**Bugfix crash** : Abort trap 6 app entière quand disque externe cible (`/Volumes/T7/...`) déconnecté lors du mkdir dans `train_brush()`. Solution : `try/except OSError` + `QMessageBox.critical` (2 lieux : mode Indépendant ~L452, mode Automatique ~L484).

**Audit complet** par @auditeur → audit-report.md (note 7.5/10). **Critique C1** : timeout 3600s insuffisant (COLMAP matching/mapper/undistort/frames + 4DGS trop court pour gros datasets). **Importants I1–I5** : (I1) Refine exFAT symlink sans repli copytree ; (I2) upscayl SHA256 mismatch continue install (trust violation) ; (I3) Sharp FFmpeg bloquant (non annulable) ; (I4) delete_project_content fail silent ; (I5) on_finished teste mauvais worker.

**Corrections** par @optimiseur : engine.py (timeout 14400s, delete retourne status) ; four_dgs_engine.py (14400s) ; workers.py (symlink + copytree repli) ; upscayl_manager.py (SHA256 → RuntimeError) ; sharp_engine.py (FFmpeg via runner) ; main_window.py (on_finished via sender()) ; tests adapté. 292 pass, 1 skip, 0 fail.

**État** : changements appliqués, arbre modifié, non committé avant archiviste. P3–P5 e2e + M1–M8 mineurs pour future passe.

**2026-07-17 (session 5)** — Diagnostic CI complet (run 29564984659, commit 611f216).
Causes identifiées, aucune correction appliquée, plan priorisé en attente exécution.
4 blocages : (1) lint ruff sans scope → 1483 erreurs (verify_imports.py script debug + app/cli/__init__.py I001/F401) ;
(2) audit pyobjc-framework-Cocoa sans marker darwin → compile Linux → ModuleNotFoundError pkg_resources ;
(3) test_colmap_pipeline mock image vide (régression 611f216) ; (4) ci.yml ruff/mypy/pip-audit sans version figée.
Plan validé utilisateur : restreindre lint scope app/, ruff --fix + manual, marker darwin pyobjc, corriger fixture, pin versions ci.yml.
Priorité absolue : résoudre 4 blocages CI avant tout commit. P3-P5 e2e + mineurs M1-M8 inchangés.

## Session 6 (2026-07-17) — Fix CI + mypy + Pillow

Corrections 3 domaines : dépendances manquantes, CI GitHub Actions Ubuntu 24.04, typage Python PEP 484.

**(1) opencv-python-headless** : utilisée requirements.txt (>=4.8,<5) mais absente requirements.lock → ajoutée 4.13.0.92.

**(2) CI GitHub Actions** : Ubuntu 24.04 runner renomma paquets OpenGL → libegl1-mesa → libegl1, libgl1-mesa-glx → libgl1.

**(3) Pillow 11.3.0** : 8 CVE connues (PYSEC-2026-*) → upgraded 12.3.0 (API stable, Image.LANCZOS présent).

**(4) Mypy 27 erreurs** : annotations Optional implicites (PEP 484 interdit), collisions vars (p/pct, tar_member, f/out_f), bugs réels.
  - engine.py : ctypes.CDLLError n'existe pas (except tuple cascadait), mapper() cast sparse_dir inutile, upscale_config dynamique.
  - installers/brush.py : zip vs tar members renommées, handle fichier collisionnant.
  - upscayl_manager.py, splat_transform_tab.py, export_engine.py, base_engine.py : annotations manquantes.

**(5) test_setup_dependencies.py** : test_check_xcode_tools_present manquait skipif sys.platform != "darwin" (fail Linux).

**Commits** : c83c1fc + be924e9 + ca4ab1b. **Tests** : 292 pass, 0 fail. **CI** : vérifiée verte (gh run watch).


## 2026-07-18 — Session 7 : Migration PyQt6→PySide6 v1.5.0 + Thèmes + i18n Upscale

**Migration bindings** : PyQt6 6.11.0 → PySide6 6.11.1 (même Qt). Remplacement mécanique pyqtSignal→Signal, imports refactorisés app/ + tests/. PySide6 déjà .venv → 1:1. Tests conftest réécrit + PYTEST_QT_API=pyside6. Requirements.txt/lock/pyproject bumped PySide6 6.11.1. Version 1.5.0 : app/__init__ + pyproject + tag git annoté poussé.

**Fonctionnalités** : 3 thèmes sombres (slate/graphite/blue) app/gui/styles.py, menu config_tab déroulant, persisté config.json. i18n Upscale ~46 clés 9 locales, upscale_tab tr()+retranslate_ui, ModelCard traduit + observer. Fix PySide6 disconnect(None) warning : mémoriser handler, déconnecter seul.

**Docs** : CHANGELOG [1.5.0] anglais emoji, README crédit Qt for Python LGPL.

**Commits** e7d5688/b4e88db poussés origin/main, tag v1.5.0. Tests 292/1/15 (baseline stable). GUI validée macOS utilisateur.

RESTE : P3-P5 e2e (360/Sharp vidéo/4DGS), M1-M8 mineurs.

## Session 8 — 2026-07-18 — Audit ETAT_DES_LIEUX.md (lecture seule)

Reprise session 7 (v1.5.0). Tâche : génération ETAT_DES_LIEUX.md (669 lignes) — cartographie factuelle complète et autosuffisante du code destinée refonte interface externe. 

**Couvert** : moteurs app/core/ (8 classes), dataclasses/params cross-ref get_params/set_params, GUI app/gui/ (main_window + 13 onglets + 3 managers + 4 workers + 5 widgets custom + styles), couplages flux (signaux/slots COLMAP→Brush→Clean→Export, mode automatique/manuel, post-training dialog), i18n (9 locales, 516 clés alignées), sécurité (validate_path 4 checks, shell=True engine, Brush allowlist, SuperSplat CORS, sanitisation projet), tests (292 pass), dette technique/anomalies.

**Lecture seule stricte** : zéro modification code, zéro exécution build/GUI. 6 agents Explore parallèles : moteurs, dataclasses, GUI, flux/couplages, i18n/sécurité/tests/anomalies, arborescence/métadonnées.

**Anomalies factuelles documentées (non corrigées)** : guided_matching dead (désactivé UI, jamais écrit set_params), sequential_overlap orphelin (aucune UI/CLI), split split_true_of_reality undistort_images/filter_blurry/blur_factor entre ParamsTab-ConfigTab, double mapping blur_factor (GUI vs CLI), ExportTab orpheline (jamais instanciée), 2 chemins Brush (orchestré vs standalone fire-forget), workers FourDGS/360 dupliqués, import privé GUI→CLI (_apply_robust).

**Résultat** : Aucun commit, aucun push. Manifest.md inchangé. RESTE À FAIRE inchangé (P3-P5 e2e, M1-M8 mineurs audit).

## Session 9 (2026-07-18) — Correction dette technique audit + version 1.5.1

Suite session 8 (ETAT_DES_LIEUX.md audit). 6 correctifs appliqués (A-F) :
- A. guided_matching : case réactivée params_tab.py, écriture set_params()
- B. sequential_overlap : QSpinBox ajouté, i18n 9 locales (en/fr/de/es/it/ja/ru/zh/ar)
- C. blur_factor : unifié params.py::blur_factor_from_strength() (était dupliqué GUI+CLI)
- D. ExportTab (code mort jamais instanciée) supprimée ; ExportEngine/ExportWorker inchangés
- E. Brush standalone : subprocess Popen fire-and-forget → BrushWorker (logs+arrêt propre)
- F. FourDGS/360Tab : orchestration unique main_window (suppression instanciation locale worker)

Tests : 292 passed, 1 skipped, 15 deselected. Version 1.5.0→1.5.1 (app/__init__.py + pyproject.toml).
CHANGELOG [1.5.1] - 2026-07-18. Commits 74bd4d1 (6 correctifs, 17 fichiers) + 765722a (CHANGELOG, 3 fichiers).
Fichiers hors commit (choix délibéré) : PROMPT_CLAUDE_CODE_REFONTE_UI.md, REFONTE_UI_SPEC.md (notes utilisateur).
manifest.md inchangé (v1.5.1 déjà mis à jour session 8). Aucun push. graphify update lancé séparément.

## 2026-07-18 — Session 10, Suite 5 : Refonte UI Lot 6 — Clôture

**Lot 6** : Charger/Sauvegarder config, Notifications, i18n 9 langues (93 clés +610/fichier).

**Livré** :
- Config I/O `StudioWindow` : `collect_config()`/`apply_config()` agrègent état panneaux + `run_state` → `ChainConfig` (app/core/config_io.py Lot 1) ; dialogs `save_config_dialog()`/`load_config_dialog()` QInputDialog ; get/set_state() Src/Reco/Entraîn/Nettoy/Export.
- Notifications macOS : `app/core/notifications.py` is_available/notify via pyobjc-framework-Cocoa NSUserNotificationCenter (zéro dépendance, pyobjc déjà utilisé) ; toggle Réglages ⟷ SettingsWindow ; hook `StudioWindow.notify()` câblé (pas appelé sans run réel).
- Icône erreur rail : cliquer étape ERROR déplie auto logbar (`on_rail_selected`).
- i18n : 9 langues 93 clés ajoutées, parité vérifiée (sous-agent + revérif indépendante).
- Tests : notifications.py (2 tests dégradation gracieux pyobjc).

**Résultat** : 376 pass, 1 skip, 15 deselected. Lint ruff OK.

**État global** : Lots 1-6 UI/logique terminés, non activés dans main.py (ColmapGUI inchangée). Cahier des charges Refonte UI : switch au Lot 7 APRÈS câblage moteurs réels (pour validation StudioWindow avant suppression ColmapGUI).

**Reste** : (1) Câblage moteurs: launch() dispatch workers, boutons locaux, closeEvent, notifications déclenchées. (2) Lot 7 nettoyage + bascule main.py. (3) Bug scroll horiz barre droite (différé user, documenté REFONTE_UI_PROGRESS.md).

**Commit** : 5996564 "feat(refonte-ui): Lot 6 — config charger/sauvegarder, notifications, i18n 9 langues".


## 2026-07-18 — Session 10, suite 6

**Lot** : Reprise — P0 câblage moteurs annulé
**HEAD** : 5996564
**Tests** : 376 pass (inchangé)

### Ce qui a été fait
- Lecture de reprise (manifest.md, journal.md, GRAPH_REPORT.md)
- Vérification graphe : désynchronisé d'un commit (basé Lot 5, HEAD est Lot 6) — nécessitera `graphify update` à la prochaine session
- P0 "câblage moteurs réels dans launch()" priorisé par l'utilisateur
- Sous-agent intégrateur lancé pour le P0 puis **annulé** par l'utilisateur — rien n'a été modifié

### RESTE À FAIRE priorisé (inchangé)
- **P0** : Câblage moteurs réels dans launch() (surface Apple Silicon)
- **P1** : Bug scroll horizontal barre droite
- **P2** : Lot 7 (nettoyage anciens onglets + bascule main.py vers StudioWindow)
- `graphify update` (graphe 1 commit derrière)

### Décision
Session annulée, pas de commit, pas de modification. P0 demandé mais annulé avant exécution. `graphify update` nécessaire à la reprise.

## 2026-07-19 — Session 10 suite 8 — Refonte UI terminée (8 lots)

**Commits** : 6cbfb38, 3e0a608, 18c52f6, 78ba2a8, 56a5588, 619705d, 4de8d53

**Réalisations** : 
- Socle préparatoire câblage moteurs (bouton Lancer/Annuler + collecte réglages 7 panneaux OUTILS)
- Correction journal session précédente
- Câblage réel moteurs studio_window.py : 7 workers (Cleaner, Export, Extractor360, FourDGS, Sharp, SplatTransform, Upscale)
- Lot 5 complet : 9 tests intégration (1 par module)
- Fix i18n : 22 clés manquantes rail PIPELINE + 9 locales cohérentes
- Lot 7 bascule StudioWindow : suppression ColmapGUI + 11 onglets, closeEvent SuperSplat
- AppLifecycle rebranchée (reset factory + relancer)

**Vérifications** : StudioWindow lancée (PySide6 réel), 13 panneaux rendus, i18n visuel.

**État** : Interface fonctionnelle. **P0 next : validation manuelle utilisateur données réelles.**

Tests : 385 passed, 1 skipped, 15 deselected

## Session 10 suite 9 (2026-07-19) — Résolution bug scroll horizontal barre droite

**Lot** : Résolution complète bug scroll horizontal barre droite (commit 149111d).

**Bug identifié** : Géométrie réelle a montré qu'un champ du panneau Entraînement (`combo_mode`, "Modo de Entrenamiento") dépassait le bord droit de la fenêtre de 34px en espagnol, faute de place dans la colonne droite (400px fixe).

**Fix appliqué** : `setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)` sur les 18 `QFormLayout` du projet. Permet aux champs longs de passer à la ligne suivante plutôt que de déborder.

**Vérification** : 10 panneaux + Réglages testés sans débordement, français/anglais/russe vérifiés, instanciation réelle StudioWindow (PySide6, pas mock).

**État** : Tous les points connus du chantier refonte UI (8 lots) sont maintenant fermés côté code. Reste : P0 validation manuelle utilisateur sur données réelles (3 pipelines + 7 modules) + décision SessionManager orphelin.

## Session 10 suite 10 (2026-07-19) — Accessibilité lancement app

**Commit** : `984d465`

**Lot** : Rend le lancement plus accessible aux non-développeurs

**Changements clés** :
- Renommage `run.command` → `Lancer CorbeauSplat.command` (git mv)
- Nouveau `app/scripts/set_launcher_icon.py` : applique assets/icon.icns au lanceur Finder via NSWorkspace/pyobjc, idempotent, appelé best-effort chaque démarrage
- Terminal simplifié (3 lignes FR vs bannières Xcode/Homebrew/pip)
- Option `--verbose`/`CORBEAU_VERBOSE=1` restaure affichage détaillé débogage
- Prompts bloquants + erreurs réelles toujours visibles
- Références mises à jour : app/gui/managers.py, tests/test_managers.py, README.md, 5 locales i18n

**Tests** : 385 passed, 1 skipped, 15 deselected

**Notes** : Icône Finder vérifiée appliquée (flag personnalisé + com.apple.ResourceFork).

## 2026-07-19 — Session 10 clôture : Refonte UI 8 lots terminée

**Commits** : 6cbfb38, 3e0a608, 18c52f6, 78ba2a8, 56a5588, 619705d, 4de8d53, 149111d, 984d465

**Bilan chantier refonte UI** : 8 lots livrés (Lots 0-7), tous sur main. Câblage réel moteurs réalisé. Interfaces UI branchées workers réels (7 modules OUTILS : Cleaner, Export, Extractor360, FourDGS, Sharp, SplatTransform, Upscale). Lot 7 : bascule StudioWindow, suppression ColmapGUI + 11 onglets. closeEvent() ferme proprement SuperSplat. 385 tests pass, 1 skip, 15 deselect (stable).

**Features** : Socle préparatoire câblage moteurs + correction journal. Câblage réel dispatch workers. Lot 5 orchestration COLMAP-only 4DGS (9 tests intégration). Fix i18n 22 clés manquantes rail PIPELINE (9 locales). Lot 7 transition StudioWindow (suppression 11 fichiers onglets). SuperSplat réel VisualiserPanel. Fix débordement QFormLayout WrapLongRows (18 endroits). Accessibilité lancement : run.command → 'Lancer CorbeauSplat.command' (git mv), icône Finder (NSWorkspace/pyobjc), terminal simplifié.

**Tests** : 385 pass, 1 skip, 15 deselect. StudioWindow PySide6 réel vérifiée macOS, 13 panneaux rendus, aucune erreur.

**Reste P0** : Validation manuelle utilisateur sur données réelles (3 pipelines COLMAP→Brush→Export + 7 modules OUTILS avec vrais fichiers). Aucun outil automatisé ne peut la remplacer.

**SessionManager** : Orphelin après Lot 7, décision technique reportée (rebrancher ou supprimer ?).

**Manifest.md** : RESTE À FAIRE mis à jour. Aucune modification code/config.json. REFONTE_UI_PROGRESS.md documente tous points fermés côté code.

