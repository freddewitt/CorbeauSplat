#!/usr/bin/env python3
"""Suivi du plan de correction (audit/fix_plan.json) pour le skill code-audit-fixer.

Sous-commandes
next prochaines tâches traiter (dépendances satisfaites, ordre du plan)
show une tâche en détail
relocate retrouve l'emplacement actuel du code visé (les lignes bougent après chaque correction)
update change le statut d'une tâche ; 'fixed' EXIGE des preuves (test rouge avant, vert après, suite saine)
confirm marque une commande de vérification comme confirmée par l'utilisateur (ou l'ajoute)
summary comptes statut et priorité
report écrit audit/FIX_REPORT.md

Garde-fou marquer une tâche 'fixed' sans avoir vu le test échouer avant correctif est refusé,
car une part importante des validations d'agents ne discrimine pas le bug (le test passait déjà)
et les correctifs "qui passent tests" sans supprimer la cause sont un mode d'échec documenté.

Sécurité (F-005) : confirm refuse les commandes dont la recette est contrôlée par le dépôt audité
(make, npm/pnpm/yarn/bun run, cargo, gradle, mvn, dotnet, ...) : confirmer reviendrait à valider
l'exécution d'un Makefile/package.json du dépôt, c'est-à-dire du code arbitraire hostile possible.
Le portail de confirmation partage la liste blanche de run_checks.py (ALLOWED / METACHARS).
Stdlib uniquement, Python 3.8+.
"""
import argparse
import difflib
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

STATUSES = {"todo", "in_progress", "fixed", "blocked", "stale", "skipped", "hold"}
PRIO = ["P0", "P1", "P2", "P3"]


def _run_checks_module():
    """Charge run_checks.py (même dossier) pour partager sa liste blanche de commandes.

    Le module est chargé par chemin (pas d'import par nom) pour fonctionner quel que soit
    sys.path : c'est la source unique d'ALLOWED / METACHARS côté confirmation.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("run_checks", os.path.join(here, "run_checks.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        sys.exit("Plan illisible (%s) : %s" % (path, exc))


def save(path, plan):
    d = Path(path).parent
    fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def task_by_id(plan, tid):
    for t in plan["tasks"]:
        if t["id"] == tid:
            return t
    sys.exit("Tâche inconnue : %s" % tid)


def plan_order(plan):
    order = []
    for b in plan.get("batches", []):
        order += b["tasks"]
    return order


def brief(t, full=False):
    if full:
        return t
    return {"id": t["id"], "title": t["title"], "priority": t["priority"], "difficulty": t["difficulty"], "batch": t["batch"],
            "category": t["category"], "targets": t["targets"], "status": t["status"], "attempts": t["attempts"],
            "depends_on": t["depends_on"], "manual_actions": t["manual_actions"]}


def cmd_next(a):
    plan = load(a.plan)
    done = {t["id"] for t in plan["tasks"] if t["status"] == "fixed"}
    wanted_ids = {x.strip() for x in a.ids.split(",")} if a.ids else None
    diffs = {x.strip() for x in a.difficulty.split(",")} if a.difficulty else None
    maxp = PRIO.index(a.max_priority) if a.max_priority else 3
    out = []
    for tid in plan_order(plan):
        t = task_by_id(plan, tid)
        if t["status"] not in ("todo", "in_progress") or not t["eligible"]:
            continue
        if wanted_ids and tid not in wanted_ids:
            continue
        if PRIO.index(t["priority"]) > maxp or (diffs and t["difficulty"] not in diffs):
            continue
        if not all(d in done for d in t["depends_on"]):
            continue
        out.append(brief(t, a.full))
        if len(out) >= a.limit:
            break
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_show(a):
    print(json.dumps(task_by_id(load(a.plan), a.id), indent=2, ensure_ascii=False))


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def cmd_relocate(a):
    plan = load(a.plan)
    t = task_by_id(plan, a.id)
    tg = t["targets"][0]
    repo = Path(a.repo).resolve()
    target = (repo / tg["file"]).resolve()
    try:
        target.relative_to(repo)
    except ValueError:
        print(json.dumps({"found": False, "reason": "chemin hors du dépôt refusé : %s" % tg["file"]}, ensure_ascii=False))
        return
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        print(json.dumps({"found": False, "reason": "fichier introuvable : %s" % tg["file"]}, ensure_ascii=False))
        return
    ev = [norm(l) for l in t["evidence"].splitlines() if norm(l)]
    if not ev:
        print(json.dumps({"found": False, "reason": "aucune preuve textuelle à rechercher"}, ensure_ascii=False))
        return
    cands = []
    for i, l in enumerate(lines):
        if norm(l) == ev[0] or difflib.SequenceMatcher(None, norm(l), ev[0]).ratio() > 0.9:
            block = [norm(x) for x in lines[i:i + len(ev)]]
            ratio = difflib.SequenceMatcher(None, " ".join(block), " ".join(ev)).ratio()
            if ratio > 0.85:
                cands.append((abs(i + 1 - tg["line_start"]), i + 1, ratio))
    if not cands:
        print(json.dumps({"found": False, "reason": "la preuve n'apparaît plus dans le fichier : déjà corrigé ou code modifié (statut 'stale' à considérer)"}, ensure_ascii=False))
        return
    cands.sort()
    _, start, ratio = cands[0]
    print(json.dumps({"found": True, "file": tg["file"], "line_start": start, "line_end": start + len(ev) - 1,
                      "moved_by": start - tg["line_start"], "match_ratio": round(ratio, 2), "candidates": len(cands)}, ensure_ascii=False))


def cmd_update(a):
    plan = load(a.plan)
    t = task_by_id(plan, a.id)
    if a.status not in STATUSES:
        sys.exit("Statut invalide : %s (attendus : %s)" % (a.status, ", ".join(sorted(STATUSES))))
    ev = t.setdefault("evidence_of_fix", {})
    for key, val in (("failing_before", a.failing_before), ("passing_after", a.passing_after), ("suite", a.suite), ("rescan", a.rescan)):
        if val is not None:
            ev[key] = val
    if a.status == "fixed":
        ok = ev.get("failing_before") == "true" and ev.get("passing_after") == "true" and ev.get("suite") == "ok"
        if not ok and not a.waiver:
            sys.exit("Refusé : 'fixed' exige --failing-before true (le test échouait avant le correctif), --passing-after true et "
                     "--suite ok (aucune nouvelle défaillance). Preuves actuelles : %s. Si aucun test n'est possible, utiliser "
                     "--waiver \"raison\" (consignée dans le rapport)." % json.dumps(ev, ensure_ascii=False))
        if a.waiver:
            ev["waiver"] = a.waiver
        if not a.commit:
            sys.exit("Refusé : 'fixed' exige --commit <hash>.")
    if a.status == "blocked" and not a.note:
        sys.exit("Refusé : 'blocked' exige --note avec la raison.")
    t["status"] = a.status
    if a.commit:
        t["commit"] = a.commit
    if a.attempt:
        t["attempts"] = t.get("attempts", 0) + 1
    if a.tests:
        t.setdefault("tests_added", []).extend(x.strip() for x in a.tests.split(","))
    if a.note:
        t["notes"].append("%s : %s" % (time.strftime("%Y-%m-%d %H:%M"), a.note))
    save(a.plan, plan)
    print(json.dumps({"id": t["id"], "status": t["status"], "attempts": t["attempts"], "commit": t.get("commit")}, ensure_ascii=False))


def cmd_confirm(a):
    plan = load(a.plan)
    rc = _run_checks_module()
    if rc.METACHARS.search(a.cmd) or not rc.ALLOWED.match(a.cmd):
        recipe = bool(rc.RECIPE_RUN.match(a.cmd)) if hasattr(rc, "RECIPE_RUN") else False
        if recipe:
            sys.exit("Refusé : %r est un lanceur dont la recette est contrôlée par le dépôt audité "
                     "(make, npm/pnpm/yarn/bun run, cargo, gradle, mvn, dotnet, ...). La confirmer "
                     "validerait l'exécution de code du dépôt sans inspection préalable. "
                     "Pour un dépôt de confiance, exécuter run_checks.py avec --allow-recipe-run." % a.cmd)
        sys.exit("Refusé : %r ne passe pas la liste blanche de run_checks.py (ALLOWED). "
                 "Commande non reconnue ou contenant des métacaractères." % a.cmd)
    cmds = plan.setdefault("commands", {}).setdefault(a.kind, [])
    for c in cmds:
        if c["cmd"] == a.cmd:
            c["confirmed"] = True
            break
    else:
        cmds.append({"cmd": a.cmd, "source": "fournie par l'utilisateur", "trusted": True, "confirmed": True})
    save(a.plan, plan)
    print(json.dumps({"kind": a.kind, "cmd": a.cmd, "confirmed": True}, ensure_ascii=False))


def cmd_summary(a):
    plan = load(a.plan)
    from collections import Counter
    c = Counter(t["status"] for t in plan["tasks"])
    by_p = {p: Counter(t["status"] for t in plan["tasks"] if t["priority"] == p and t["eligible"]) for p in PRIO}
    print(json.dumps({"par_statut": dict(c), "par_priorité": {p: dict(v) for p, v in by_p.items() if v}}, indent=2, ensure_ascii=False))


def cmd_report(a):
    plan = load(a.plan)
    tasks = plan["tasks"]
    L = ["# FIX_REPORT : rapport de correction", "",
         "Plan de base : commit %s. Généré le %s." % (plan["meta"].get("base_commit") or "inconnu", time.strftime("%Y-%m-%d %H:%M")), ""]
    from collections import Counter
    c = Counter(t["status"] for t in tasks)
    L += ["## Résumé", "", "- Corrigés : **%d** ; bloqués : %d ; obsolètes : %d ; ignorés : %d ; restant à faire : %d ; en attente de vérification : %d." % (
        c["fixed"], c["blocked"], c["stale"], c["skipped"], c["todo"] + c["in_progress"], c["hold"]), ""]
    L += ["## Tâches", "", "| ID | Priorité | Difficulté | Statut | Commit | Tentatives | Tests ajoutés |", "|---|---|---|---|---|---|---|"]
    for tid in plan_order(plan) + [t["id"] for t in tasks if not t["eligible"]]:
        t = task_by_id(plan, tid)
        L.append("| %s | %s | %s | %s | %s | %d | %s |" % (t["id"], t["priority"], t["difficulty"], t["status"], t.get("commit") or "", t.get("attempts", 0), ", ".join(t.get("tests_added", [])) or ""))
    L += ["", "## Preuves de correction", ""]
    for t in tasks:
        if t["status"] == "fixed":
            ev = t.get("evidence_of_fix", {})
            L.append("- **%s** : test rouge avant=%s, vert après=%s, suite=%s, rescan=%s%s" % (
                t["id"], ev.get("failing_before"), ev.get("passing_after"), ev.get("suite"), ev.get("rescan", "n/a"),
                " ; DÉROGATION : %s" % ev["waiver"] if ev.get("waiver") else ""))
    blocked = [t for t in tasks if t["status"] in ("blocked", "stale")]
    L += ["", "## Bloqués ou obsolètes", ""]
    L += ["- **%s** (%s) : %s" % (t["id"], t["status"], " | ".join(t["notes"][-2:]) or "sans note") for t in blocked] or ["_aucun_"]
    L += ["", "## Actions humaines requises", ""]
    acts = [(t["id"], m) for t in tasks if t["status"] in ("fixed", "blocked", "todo") for m in t["manual_actions"]]
    L += ["- **%s** : %s" % x for x in acts] or ["_aucune_"]
    L += ["", "## Risque résiduel", ""]
    rest = [t for t in tasks if t["status"] in ("todo", "in_progress", "blocked", "stale", "hold") and t["priority"] in ("P0", "P1")]
    L += ["- %s (%s, %s) : %s" % (t["id"], t["priority"], t["status"], t["title"]) for t in rest] or ["_aucun finding P0/P1 restant_"]
    L += ["", "## Suite recommandée", "",
          "1. Relire la branche de correction et ses commits un par un (un commit par finding).",
          "2. Relancer l'audit en mode différentiel sur les fichiers modifiés (`chunk_repo.py --since <commit de base>`) pour vérifier qu'aucun nouveau défaut n'a été introduit.",
          "3. Exécuter les actions humaines ci-dessus (rotation de secrets, migrations).",
          "4. Ouvrir la demande de fusion avec ce rapport en description.", ""]
    Path(a.out).write_text("\n".join(L), encoding="utf-8")
    print("Écrit : %s" % a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", default="audit/fix_plan.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next"); p.add_argument("--limit", type=int, default=1); p.add_argument("--max-priority", choices=PRIO)
    p.add_argument("--difficulty", default=""); p.add_argument("--ids", default=""); p.add_argument("--full", action="store_true"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("show"); p.add_argument("id"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("relocate"); p.add_argument("id"); p.add_argument("--repo", default="."); p.set_defaults(fn=cmd_relocate)
    p = sub.add_parser("update"); p.add_argument("id"); p.add_argument("--status", required=True)
    p.add_argument("--commit", default=""); p.add_argument("--note", default=""); p.add_argument("--tests", default="")
    p.add_argument("--attempt", action="store_true", help="incrémente le compteur de tentatives")
    p.add_argument("--failing-before", choices=["true", "false"]); p.add_argument("--passing-after", choices=["true", "false"])
    p.add_argument("--suite", choices=["ok", "new_failures", "baseline_broken"]); p.add_argument("--rescan", default=None)
    p.add_argument("--waiver", default="", help="raison d'une dérogation à l'exigence de preuve (consignée)")
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser("confirm"); p.add_argument("--cmd", required=True); p.add_argument("--kind", default="test", choices=["test", "lint", "build"])
    p.set_defaults(fn=cmd_confirm)
    p = sub.add_parser("summary"); p.set_defaults(fn=cmd_summary)
    p = sub.add_parser("report"); p.add_argument("--out", default="audit/FIX_REPORT.md"); p.set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
