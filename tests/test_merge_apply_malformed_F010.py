"""F-010 — ``merge_findings.cmd_apply`` must skip malformed result entries.

``cmd_apply`` iterates over the entries of each ``result_*.json`` found in the
verification directory. That directory is writable by the audited repo, so the
entry type is not trusted: a hostile file can be a list of plain strings
(``["F-001"]``) instead of a list of dicts. Before the fix, ``r.get("id")`` on
a ``str`` raises ``AttributeError`` and the whole ``apply`` command aborts —
the malformed entry must be reported and skipped, and a valid entry in another
file must still be applied.
"""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MERGE_SCRIPT = REPO_ROOT / "code-audit-skills/code-audit-orchestrator/scripts/merge_findings.py"


def _load_merge():
    spec = importlib.util.spec_from_file_location("merge_findings_F010", MERGE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_merged(tmp_path, findings):
    path = tmp_path / "merged.json"
    path.write_text(json.dumps({"findings": findings}, ensure_ascii=False), encoding="utf-8")
    return path


def _write_result(verif_dir: Path, name: str, payload):
    path = verif_dir / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_string_list_result_is_skipped_and_pipeline_continues(tmp_path, capsys):
    """A result file holding ``["F-001"]`` must not abort ``cmd_apply``.

    Fails before the fix: ``r.get("id")`` on a ``str`` raises
    ``AttributeError`` and the command dies instead of reporting the ignored
    entry and finishing.
    """
    mf = _load_merge()
    verif = tmp_path / "verification"
    verif.mkdir()
    _write_merged(tmp_path, [{"id": "F-001", "title": "t", "file": "f", "line_start": 1, "line_end": 1, "severity": "low", "status": "todo"}])
    _write_result(verif, "result_bad.json", ["F-001"])

    out = tmp_path / "out"
    out.mkdir()
    a = argparse_namespace(tmp_path, verif, out)
    mf.cmd_apply(a)

    text = capsys.readouterr().out
    assert "entrée ignorée" in text
    assert "Statuts:" in text
    final = json.loads((out / "final.json").read_text(encoding="utf-8"))
    assert final["findings"][0]["status"] == "todo"


def test_valid_result_file_is_still_applied(tmp_path, capsys):
    """A well-formed result dict keeps its normal behaviour (no over-correction)."""
    mf = _load_merge()
    verif = tmp_path / "verification"
    verif.mkdir()
    _write_merged(tmp_path, [{"id": "F-001", "title": "t", "file": "f", "line_start": 1, "line_end": 1, "severity": "low", "status": "todo"}])
    _write_result(verif, "result_ok.json", {"results": [{"id": "F-001", "verdict": "confirmed", "severity_final": "high"}]})

    out = tmp_path / "out"
    out.mkdir()
    mf.cmd_apply(argparse_namespace(tmp_path, verif, out))

    capsys.readouterr()
    final = json.loads((out / "final.json").read_text(encoding="utf-8"))
    assert final["findings"][0]["status"] == "confirmed"
    assert final["findings"][0]["severity_final"] == "high"


def argparse_namespace(merged_dir: Path, verif_dir: Path, out_dir: Path):
    import argparse
    return argparse.Namespace(merged=str(merged_dir / "merged.json"), verification=str(verif_dir), out=str(out_dir))
