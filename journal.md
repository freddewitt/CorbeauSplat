# CorbeauSplat — Journal de bord

**État** : v1.2.2 (graphify-out/ regénéré, 2002 nœuds, 3747 arêtes, 120 communautés). 292 pass, 1 skip, 0 fail. CI cassée (lint, audit, test-gui, tests 3.10-3.12) — diagnostic complet, plan priorisé en attente exécution.

**Dernières sessions** :
- **2026-07-17 (session 5)** — Diagnostic CI complet (run 29564984659). 4 blocages : (1) lint ruff sans scope → 1483 erreurs (verify_imports.py script debug oublié + app/cli/__init__.py I001/F401) ; (2) audit pyobjc-framework-Cocoa sans marker darwin → compile Linux → ModuleNotFoundError pkg_resources ; (3) test_colmap_pipeline mock image vide (régression 611f216) ; (4) ci.yml ruff/mypy/pip-audit sans version figée. Plan : restreindre lint scope app/, ruff --fix + manual, marker darwin pyobjc, corriger fixture test, pin versions ci.yml. Aucun code modifié.
- **2026-07-17 (session 4)** — Bugfix crash Brush disque externe (try/except OSError + QMessageBox). Audit complet audit-report.md (7.5/10) : C1 timeout 3600s insuffisant + I1-I5 importants + M1-M8 mineurs. Corrections appliquées par @optimiseur : engine.py/four_dgs_engine.py (14400s), workers.py (symlink repli), upscayl_manager.py (SHA256 strict), sharp_engine.py (runner), main_window.py (on_finished), tests adapté. 292 pass, 1 skip, 0 fail. Non committé. P3-P5 e2e + mineurs pour future passe.
