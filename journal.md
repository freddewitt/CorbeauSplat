# CorbeauSplat — Journal de bord

**État** : v1.2.2 (CHANGELOG + app/__init__.py + pyproject.toml synchro). 262 tests pass. Suite tests réparée. Audit i18n : 459 clés, 9 locales cohérentes. Git 2 commits local d'avance sur origin/main.

**Dernières sessions** :
- **2026-07-06 (session 4)** — Analyse COLMAP + 4 améliorations SfM. DSP-SIFT défaut, vocab_tree matcher, loop_detection séquentiel, fallback mapper incrémental. params_tab GUI alignée. Tests 30/34 pass. Graphify 1967 nœuds/3548 arêtes.
- **2026-07-06 (session 5)** — Réparation suite tests (262 pass, 2 skip, 0 fail). Boucle infinie fixée : mocks `readline=""` vs anciens `stdout_iter()`. Pollution cv2 session-wide fixée (import réel d'abord). Fixtures réalignées. `delete_project_content` sécurité : bloque "/" / $HOME / app / ancêtres. CHANGELOG 1.2.2 anglais écrit. Audit i18n complet (459 clés, 9 locales). Commits 62a1531 + fd04f50 poussés. RESTE : confirm_reset ES incohérent, synchro versions app/__init__.py/pyproject.toml.
- **2026-07-06 (session 6)** — Synchro versions app/__init__.py + pyproject.toml 1.2.0 → 1.2.2 (alignés CHANGELOG + manifest). Tests intégration validés : 32 pass, 1 skip. Commits 08fb98b + 97a519b poussés localement. RESTE À FAIRE (par orchestrateur) : confirm_reset ES incohérent, tests e2e réels absents.
