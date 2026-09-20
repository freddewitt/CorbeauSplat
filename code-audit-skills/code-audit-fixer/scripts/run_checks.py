#!/usr/bin/env python3
"""Lance les vérifications du projet (tests, lint, build) de façon contrôlée et compare à une ligne de base.

Usage :
  run_checks.py --label baseline                       # avant toute modification
  run_checks.py --label F-003 --compare audit/fix/checks/baseline.json
  run_checks.py --label F-003 --cmd "pytest -q tests/test_login.py" --kinds test

Sécurité :
  - les commandes viennent de audit/fix_plan.json (champ commands) ; seules celles marquées
    "confirmed" sont lancées, sauf --allow-unconfirmed (à réserver à un accord explicite de l'utilisateur) ;
  - une commande n'est lancée que si elle correspond à un lanceur direct sûr (pytest, ruff, mypy,
    flake8, eslint, tsc, go test/vet/build...). Le texte des documents du dépôt peut contenir des
    commandes piégées : elles ne sont jamais exécutées sans confirmation ;
  - les lanceurs dont la RECETTE est contrôlée par le dépôt audité (make, npm/pnpm/yarn/bun run,
    cargo, gradle, mvn, dotnet, composer, bundle exec rspec, vendor/bin/phpunit, tox, nox) sont
    REFUSÉS par défaut : la recette (Makefile, package.json, ...) vient d'un fichier du dépôt, donc
    un dépôt hostile peut faire exécuter du code arbitraire sans aucun métacaractère dans la commande
    (ex. `make test`). Seul un accord humain explicite, par invocation avec --allow-recipe-run,
    les autorise (dépôt de confiance uniquement) ;
  - pas de shell : la commande est découpée et lancée directement, les métacaractères sont inertes et refusés.
Sortie : JSON sur stdout ; journaux complets dans <out>/<label>-<type>.log. Code de sortie 0 si la suite est saine.
Stdlib uniquement, Python 3.8+.
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

# Invocations directes sûres : l'outil agit sur le dépôt sans recette définie par un fichier
# du dépôt (pytest, ruff, mypy, ... n'exécutent pas de script de build contrôlé par le dépôt).
ALLOWED = re.compile(
    r"^(pytest|python3? -m pytest|"
    r"go (test|vet|build) [\w./\-. ]*|"
    r"ruff check[\w .\-/]*|mypy[\w .\-/]*|flake8[\w .\-/]*|eslint[\w .\-/@]*|tsc[\w .\-/]*)( [\w:./=@\-\[\]]*)*$")
# Lanceurs dont la recette est contrôlée par le dépôt audité (Makefile, package.json scripts,
# Cargo.toml, pom.xml, build.gradle, .csproj, tox.ini, ...). Refusés par défaut : `make test`
# n'a besoin d'AUCUN métacaractère pour exécuter le code arbitraire de la recette du dépôt.
RECIPE_RUN = re.compile(
    r"^(tox|nox|"
    r"(npm|pnpm|yarn|bun)( run)? (test|lint|typecheck|build|check)( [\w:./=@ -]*)?|"
    r"cargo (test|clippy|check|build)( [\w\-. ]*)?|"
    r"mvn( -[\w=.]+)* (test|verify)|\./?gradlew?( -[\w=.]+)* (test|check|build)|gradle (test|check|build)|"
    r"make (test|lint|check|build)|bundle exec rspec|composer (test|lint)|vendor/bin/phpunit|dotnet (test|build))"
    r"( [\w:./=@\-\[\]]*)*$")
METACHARS = re.compile(r"[;&|`$<>\n\\]")


def parse_failures(kind, output):
    failed = set()
    for line in output.splitlines():
        line = line.strip()
        m = re.match(r"^(FAILED|ERROR) (\S+)", line)  # pytest
        if m:
            failed.add(m.group(2))
        m = re.match(r"^--- FAIL: (\S+)", line)  # go test
        if m:
            failed.add(m.group(1))
        m = re.match(r"^test (\S+) \.\.\. FAILED", line)  # cargo test
        if m:
            failed.add(m.group(1))
    return sorted(failed)


def summary_line(output):
    lines = [l for l in output.strip().splitlines() if l.strip()]
    for l in reversed(lines):
        if re.search(r"(passed|failed|error|ok\b|FAIL|PASS|Tests?:|test result)", l):
            return l.strip()[:200]
    return lines[-1][:200] if lines else ""


def collect_commands(plan_path, kinds, explicit, allow_unconfirmed):
    if explicit:
        return [(kinds[0] if kinds else "test", explicit)]
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    res = []
    for kind in kinds:
        for c in plan.get("commands", {}).get(kind, []):
            if c.get("confirmed") or allow_unconfirmed:
                res.append((kind, c["cmd"]))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--plan", default="audit/fix_plan.json")
    ap.add_argument("--out", default="audit/fix/checks")
    ap.add_argument("--label", required=True)
    ap.add_argument("--kinds", default="test,lint")
    ap.add_argument("--cmd", default="", help="commande explicite (soumise à la même liste blanche)")
    ap.add_argument("--compare", default="", help="fichier JSON de la ligne de base")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--allow-unconfirmed", action="store_true")
    ap.add_argument("--allow-recipe-run", action="store_true",
                    help="autorise explicitement les lanceurs dont la recette est contrôlée par le dépôt "
                         "audité (make, npm/pnpm/yarn/bun run, cargo, gradle, mvn, dotnet, ...). Un dépôt "
                         "hostile peut y cacher du code arbitraire : à n'utiliser que sur un dépôt de confiance.")
    a = ap.parse_args()

    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()]
    cmds = collect_commands(a.plan, kinds, a.cmd, a.allow_unconfirmed)
    if not cmds:
        sys.exit("Aucune commande à lancer : aucune n'est confirmée dans %s. Demander à l'utilisateur de confirmer (ou fournir --cmd)." % a.plan)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for kind, cmd in cmds:
        recipe = bool(RECIPE_RUN.match(cmd))
        if METACHARS.search(cmd):
            results.append({"kind": kind, "cmd": cmd, "exit_code": None, "refused": "commande contenant des métacaractères"})
            continue
        if not ALLOWED.match(cmd):
            if not recipe or not a.allow_recipe_run:
                reason = ("recette contrôlée par le dépôt audité" if recipe
                          else "commande hors liste blanche")
                if recipe and not a.allow_recipe_run:
                    reason += " : refusée par défaut, exiger --allow-recipe-run (dépôt de confiance uniquement)"
                results.append({"kind": kind, "cmd": cmd, "exit_code": None, "refused": reason})
                continue
        start = time.time()
        try:
            res = subprocess.run(shlex.split(cmd), cwd=a.repo, capture_output=True, text=True, timeout=a.timeout)
            code, text = res.returncode, (res.stdout or "") + (res.stderr or "")
        except subprocess.TimeoutExpired:
            code, text = 124, "délai dépassé (%ds)" % a.timeout
        except OSError as exc:
            code, text = 127, "commande introuvable : %s" % exc
        log = out / ("%s-%s.log" % (a.label, kind))
        if recipe:
            text = "ATTENTION : recette contrôlée par le dépôt audité, exécutée sur accord explicite (--allow-recipe-run).\n" + text
        log.write_text(text[-200000:], encoding="utf-8")
        entry = {"kind": kind, "cmd": cmd, "exit_code": code, "seconds": round(time.time() - start, 1),
                 "failed_tests": parse_failures(kind, text), "summary": summary_line(text), "log": str(log)}
        if recipe:
            entry["recipe_run"] = True
        results.append(entry)

    verdict = "ok"
    new_failures = []
    if a.compare:
        try:
            base = json.loads(Path(a.compare).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sys.exit("Ligne de base illisible : %s" % a.compare)
        base_by = {(r["kind"], r["cmd"]): r for r in base["results"]}
        for r in results:
            b = base_by.get((r["kind"], r["cmd"]))
            if r.get("exit_code") in (None, 0):
                continue
            if b is None or b.get("exit_code") == 0:
                new_failures += r["failed_tests"] or ["%s : échec global (%s)" % (r["cmd"], r["summary"])]
            else:
                new_failures += sorted(set(r["failed_tests"]) - set(b.get("failed_tests", [])))
        verdict = "new_failures" if new_failures else "ok"
    elif any(r.get("exit_code") not in (0,) for r in results):
        verdict = "baseline_broken" if a.label == "baseline" else "new_failures"

    doc = {"label": a.label, "verdict": verdict, "new_failures": new_failures, "results": results}
    (out / ("%s.json" % a.label)).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    sys.exit(0 if verdict == "ok" else 1)


if __name__ == "__main__":
    main()
