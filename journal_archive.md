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
