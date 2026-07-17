# CorbeauSplat — Journal de bord

**État** : v1.2.2 (graphify-out/ regénéré, 2002 nœuds, 3747 arêtes, 120 communautés). 292 pass, 1 skip, 0 fail. Arbre modifié (audit + corrections C1+I1-I5), non committé. Branche main 2 commits d'avance origin/main.

**Dernières sessions** :
- **2026-07-17 (session 4)** — Bugfix crash Brush disque externe déconnecté (try/except OSError + QMessageBox). Audit complet audit-report.md (7.5/10) : C1 timeout 3600s insuffisant + I1-I5 importants + M1-M8 mineurs. Corrections appliquées par @optimiseur : engine.py/four_dgs_engine.py (14400s), workers.py (symlink repli), upscayl_manager.py (SHA256 strict), sharp_engine.py (runner), main_window.py (on_finished), tests adapté. 292 pass, 1 skip, 0 fail. Non committé. P3-P5 e2e + mineurs pour future passe.
- **2026-07-17 (session 3)** — Régénération complète du graphe de connaissance graphify-out/. 123 fichiers scannés (97 code, 11 docs, 12 images, 0 vidéo). Extraction : 1950 nœuds AST + 75 nœuds sémantiques = 2016 nœuds extraits → 2002 nœuds après build, 3747 arêtes, 120 communautés. 30 communautés labellisées manuellement. HTML interactif généré. 92% EXTRACTED, 8% INFERRED, 0% AMBIGUOUS. Pas de code modifié, pas de feature livrée. RESTE À FAIRE inchangé : P3 (e2e 360), P4 (e2e Sharp vidéo), P5 (e2e 4DGS).
