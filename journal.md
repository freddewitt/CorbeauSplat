# CorbeauSplat — Journal de bord

**État** : v1.2.1. 4 items RESTE À FAIRE livrés. Tests 30/34 pass (SfM COLMAP 4 améliorations). Graphify 1967 nœuds.

**Dernières sessions** :
- **2026-07-05 (session 3)** — Clôture RESTE À FAIRE. ExportTab async confirmé. 3 fichiers tests intégration (cleaner→export, engine→params, security→i18n). 32/33 pass, 1 skip. CI headless : numpy mock conditionnel conftest, guard test_workers retiré. Bug colmap_pipeline réparé (mock_subprocess_run crée database.db). pyproject.toml 1.2.0. Graphify rebuild 1960 nœuds/3546 arêtes.
- **2026-07-06 (session 1)** — Fix timeout Brush 3600s. `base_engine.py` : nouveau paramètre `inactivity_timeout` (détection processus gelé, 10min sans stdout). `brush_engine.py` : timeout étendu 4h. `config.json` : clé `training_timeout: 14400`. 49/49 tests Brush + base_engine passent.
- **2026-07-06 (session 2)** — Fix round 2 : `inactivity_timeout=600s` trop court, Brush a des phases silencieuses (init viewer, checkpoint I/O) → désactivé (`inactivity_timeout=0`). CHANGELOG section 1.2.1 ajoutée et pushée.
- **2026-07-06 (session 3)** — Optimisation Apple Silicon + responsive GUI. Bug adapt_max_splats : branche morte `elif thermal=="warning"` remplacée par paliers réels fair→0.75, serious→0.5, critical→0.2. 5 onglets enveloppés QScrollArea pour écran court. Word-wrap minor fixes. Infra confirmée solide.
- **2026-07-06 (session 4)** — Analyse COLMAP + 4 améliorations SfM. Feature par défaut SIFT + estimate_affine (DSP-SIFT complet), vocab_tree implémenté, loop_detection vidéo, fallback mapper incrémental si GLOMAP invalide. GUI params_tab alignée. Tests 30/34 pass (4 préexistants). Graphify 1967 nœuds/3548 arêtes.
