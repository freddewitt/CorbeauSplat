"""F-014 — ``fixplan.cmd_relocate`` must confine plan file reads to the repo.

``cmd_relocate`` reads ``repo / tg["file"]`` from ``fix_plan.json``, an input
that is not trusted (it ships with the audited repo). A hostile plan can point
``file`` at an absolute path or use ``..`` to escape the repo: with pathlib,
``Path("/repo") / "/etc/passwd" == Path("/etc/passwd")``, turning the
command into an arbitrary file read plus a line-oracle (``found`` /
``line_start`` / ``match_ratio``). ``cmd_relocate`` must resolve the target
and refuse anything that does not stay inside the repo.
"""
import argparse
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXPLAN_SCRIPT = REPO_ROOT / "code-audit-skills/code-audit-fixer/scripts/fixplan.py"


def _load_fixplan():
    spec = importlib.util.spec_from_file_location("fixplan_F014", FIXPLAN_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_plan(tmp_path: Path, repo: Path, file_ref, evidence) -> Path:
    plan = {
        "meta": {"base_commit": "test"},
        "tasks": [{
            "id": "F-014-T",
            "title": "t",
            "priority": "P3",
            "difficulty": "easy",
            "batch": "B10",
            "category": "path-traversal",
            "status": "todo",
            "attempts": 0,
            "eligible": True,
            "depends_on": [],
            "manual_actions": [],
            "evidence": evidence,
            "targets": [{"file": file_ref, "line_start": 1, "line_end": 1, "symbol": None, "node_id": None}],
        }]
    }
    path = tmp_path / "fix_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def test_absolute_target_outside_repo_is_refused(tmp_path, capsys):
    """A plan whose ``file`` is an absolute path outside the repo is refused.

    Fails before the fix: ``cmd_relocate`` reads the file verbatim, matches the
    evidence and reports ``found: true`` — the arbitrary-read oracle. After the
    fix the target is resolved and rejected for escaping the repo.
    """
    fp = _load_fixplan()
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = tmp_path / "secret.py"
    secret.write_text("REPO_ROOT = None\n", encoding="utf-8")

    plan = _write_plan(tmp_path, repo, str(secret), "REPO_ROOT = None")
    a = argparse.Namespace(plan=str(plan), id="F-014-T", repo=str(repo))

    fp.cmd_relocate(a)
    out = json.loads(capsys.readouterr().out)

    assert out["found"] is False
    assert "hors du dépôt" in out["reason"]


def test_dotdot_target_escaping_repo_is_refused(tmp_path, capsys):
    """A ``../`` traversal in ``file`` is resolved then refused."""
    fp = _load_fixplan()
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    secret = tmp_path / "secret.py"
    secret.write_text("TOKEN = 'x'\n", encoding="utf-8")

    plan = _write_plan(tmp_path, repo, "sub/../../secret.py", "TOKEN = 'x'")
    a = argparse.Namespace(plan=str(plan), id="F-014-T", repo=str(repo))

    fp.cmd_relocate(a)
    out = json.loads(capsys.readouterr().out)

    assert out["found"] is False
    assert "hors du dépôt" in out["reason"]


def test_symlink_escaping_repo_is_refused(tmp_path, capsys):
    """A symlink inside the repo that points outside is followed and refused."""
    fp = _load_fixplan()
    repo = tmp_path / "repo"
    repo.mkdir()
    secret = tmp_path / "secret.py"
    secret.write_text("FLAG = 1\n", encoding="utf-8")
    (repo / "link.py").symlink_to(secret)

    plan = _write_plan(tmp_path, repo, "link.py", "FLAG = 1")
    a = argparse.Namespace(plan=str(plan), id="F-014-T", repo=str(repo))

    fp.cmd_relocate(a)
    out = json.loads(capsys.readouterr().out)

    assert out["found"] is False
    assert "hors du dépôt" in out["reason"]


def test_legitimate_file_inside_repo_still_found(tmp_path, capsys):
    """An ordinary in-repo target keeps working (no over-correction)."""
    fp = _load_fixplan()
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "core.py").write_text("def helper():\n    return 1\n", encoding="utf-8")

    plan = _write_plan(tmp_path, repo, "src/core.py", "def helper():")
    a = argparse.Namespace(plan=str(plan), id="F-014-T", repo=str(repo))

    fp.cmd_relocate(a)
    out = json.loads(capsys.readouterr().out)

    assert out["found"] is True
    assert out["line_start"] == 1


def test_missing_file_still_reports_not_found(tmp_path, capsys):
    """A non-existent in-repo path keeps the original 'not found' behaviour."""
    fp = _load_fixplan()
    repo = tmp_path / "repo"
    repo.mkdir()

    plan = _write_plan(tmp_path, repo, "src/absent.py", "def helper():")
    a = argparse.Namespace(plan=str(plan), id="F-014-T", repo=str(repo))

    fp.cmd_relocate(a)
    out = json.loads(capsys.readouterr().out)

    assert out["found"] is False
