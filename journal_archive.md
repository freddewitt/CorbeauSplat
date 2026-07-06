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
