# CorbeauSplat — Journal de bord

**État** : v1.2.1. 4 items RESTE À FAIRE livrés. Tests intégration 32/33 pass, CI headless OK, pyproject 1.2.0. Graphify 1960 nœuds. Proxy Headroom ne sert pas deepseek-v4-flash — archiviste/testeur/chercheur/optimiseur configurés avec ce modèle échouent.

**Dernières sessions** :
- **2026-07-05 (session 3)** — Clôture RESTE À FAIRE. ExportTab async confirmé. 3 fichiers tests intégration (cleaner→export, engine→params, security→i18n). 32/33 pass, 1 skip. CI headless : numpy mock conditionnel conftest, guard test_workers retiré. Bug colmap_pipeline réparé (mock_subprocess_run crée database.db). pyproject.toml 1.2.0. Graphify rebuild 1960 nœuds/3546 arêtes.
- **2026-07-05 (session 2)** — Session lourde (8 lots, ~100 fichiers). Migration glomap→global_mapper, force_cpu mort, --GlobalMapper.*, min/multiple_models supprimés, thermal throttling optionnel, copier/rechercher/auto-scroll logs, view_graph_calibrator + ignore_watermarks + ALIKED/LightGlue défaut, version → 1.2.0.
- **2026-07-05 (session 1)** — Bootstrap amorçage : AGENTS.md, manifest.md, journal.md, graphify-out/.
- **2026-07-06 (session 1)** — Fix timeout Brush 3600s. `base_engine.py` : nouveau paramètre `inactivity_timeout` (détection processus gelé, 10min sans stdout). `brush_engine.py` : timeout étendu 4h. `config.json` : clé `training_timeout: 14400`. 49/49 tests Brush + base_engine passent.
