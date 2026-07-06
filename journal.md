# CorbeauSplat — Journal de bord

**État** : v1.2.2 (CHANGELOG). 262 tests pass. Suite tests réparée (gel infini + 13 échecs fixés). Audit i18n : 459 clés, 9 locales cohérentes.

**Dernières sessions** :
- **2026-07-06 (session 3)** — Optimisation Apple Silicon + responsive GUI. Bug adapt_max_splats (branche morte thermique). 5 onglets QScrollArea pour écran court. Word-wrap minor fixes.
- **2026-07-06 (session 4)** — Analyse COLMAP + 4 améliorations SfM. DSP-SIFT défaut, vocab_tree matcher, loop_detection séquentiel, fallback mapper incrémental. params_tab GUI alignée. Tests 30/34 pass. Graphify 1967 nœuds/3548 arêtes.
- **2026-07-06 (session 5)** — Réparation suite tests (262 pass, 2 skip, 0 fail). Boucle infinie fixée : mocks `readline=""` vs anciens `stdout_iter()`. Pollution cv2 session-wide fixée (import réel d'abord). Fixtures réalignées. `delete_project_content` sécurité : bloque "/" / $HOME / app / ancêtres. CHANGELOG 1.2.2 anglais écrit. Audit i18n complet (459 clés, 9 locales). Commits 62a1531 + fd04f50 poussés. RESTE : confirm_reset ES incohérent, synchro versions app/__init__.py/pyproject.toml.
