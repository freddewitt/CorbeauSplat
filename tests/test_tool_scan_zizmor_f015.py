"""F-015 — zizmor must keep its findings past 29 alerts.

``tool_scan.cmd_run`` runs zizmor with ``ok_codes=set(range(0, 30))``. zizmor
encodes the number of findings it found in its exit code (0..255): a workflow
with 30+ findings therefore exits with a code outside that range and ``run_cmd``
reports ``ok=False``. The success decision must rest on the parseability of the
JSON output (stdout starting with ``[``), not on the exact exit code value, and
an unparseable output must be recorded as an explicit error — never a silent
discard.

These tests pin that contract so the zizmor branch stays correct even if a
future refactor reuses the ``ok`` flag returned by ``run_cmd``.
"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_SCAN_SCRIPT = REPO_ROOT / "code-audit-skills/code-audit-orchestrator/scripts/tool_scan.py"


def _load_tool_scan():
    spec = importlib.util.spec_from_file_location("tool_scan_F015", TOOL_SCAN_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _zizmor_finding():
    """One realistic zizmor ``json-v1`` finding, parseable by ``parse_zizmor``."""
    return {
        "ident": "dangerous-triggers",
        "desc": "workflow triggered by an untrusted event",
        "locations": [{
            "symbolic": {
                "kind": "Primary",
                "key": {"Local": {"verbatim_path": ".github/workflows/ci.yml"}},
                "annotation": "pull_request_target",
            },
            "concrete": {
                "location": {"start_point": {"row": 0}, "end_point": {"row": 0}},
                "feature": "on: pull_request_target",
            },
        }],
        "determinations": {"severity": "High", "confidence": "High"},
        "ignored": False,
        "fixes": [{"title": "use pull_request instead of pull_request_target"}],
    }


def _make_repo(tmp_path):
    wf = tmp_path / "repo" / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\non: push\n", encoding="utf-8")
    return tmp_path / "repo"


def _run_zizmor(ts, tmp_path, returncode, stdout, stderr=""):
    repo = _make_repo(tmp_path)
    res = SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    ts.run_cmd = lambda cmd, cwd, timeout, ok_codes: (returncode in ok_codes, res)
    ts.which = lambda name: "/usr/bin/fake-zizmor" if name == "zizmor" else None
    ts.version_of = lambda exe, arg="--version": "1.0.0"

    out = tmp_path / "out"
    a = SimpleNamespace(repo=str(repo), out=str(out), tools="zizmor",
                        semgrep_config="p/default", history=False, timeout=60)
    ts.cmd_run(a)
    return repo, out


def test_zizmor_conserves_findings_above_29_alerts(tmp_path):
    """A 30+ finding scan (exit code 30) keeps its findings.

    Fails if the zizmor branch ever gates on ``ok`` from ``run_cmd`` (the
    ``set(range(0, 30))`` ok_codes) instead of on JSON parseability: the
    findings would be discarded and the tool reported as failed.
    """
    ts = _load_tool_scan()
    stdout = json.dumps([_zizmor_finding(), _zizmor_finding(), _zizmor_finding()])
    repo, out = _run_zizmor(ts, tmp_path, returncode=30, stdout=stdout)

    summary = json.loads((out / "tools_summary.json").read_text(encoding="utf-8"))
    assert summary["zizmor"]["ran"] is True
    assert summary["zizmor"]["findings"] == 3
    assert summary["zizmor"]["error"] is None

    raw = out / "findings" / "raw" / "TOOL-zizmor.tool-zizmor.json"
    assert raw.exists()
    payload = json.loads(raw.read_text(encoding="utf-8"))
    assert len(payload["findings"]) == 3


def test_zizmor_clean_run_with_zero_findings(tmp_path):
    """An empty result (exit code 0, ``[]``) still counts as a successful run."""
    ts = _load_tool_scan()
    repo, out = _run_zizmor(ts, tmp_path, returncode=0, stdout="[]")

    summary = json.loads((out / "tools_summary.json").read_text(encoding="utf-8"))
    assert summary["zizmor"]["ran"] is True
    assert summary["zizmor"]["findings"] == 0
    assert summary["zizmor"]["error"] is None


def test_zizmor_fatal_code_with_valid_json_keeps_findings(tmp_path):
    """Exit code 255 (fatal) with a parseable JSON stdout still yields findings.

    Success is decided by parseability of the output, not by the exact exit
    code value: zizmor uses 0..255 for both the finding count and fatal errors.
    """
    ts = _load_tool_scan()
    stdout = json.dumps([_zizmor_finding()])
    repo, out = _run_zizmor(ts, tmp_path, returncode=255, stdout=stdout)

    summary = json.loads((out / "tools_summary.json").read_text(encoding="utf-8"))
    assert summary["zizmor"]["ran"] is True
    assert summary["zizmor"]["findings"] == 1
    assert summary["zizmor"]["error"] is None


def test_zizmor_unparseable_stdout_is_explicit_error(tmp_path):
    """A non-JSON stdout must surface as an explicit error, not a silent discard."""
    ts = _load_tool_scan()
    repo, out = _run_zizmor(ts, tmp_path, returncode=1, stdout="", stderr="fatal: no workflows")

    summary = json.loads((out / "tools_summary.json").read_text(encoding="utf-8"))
    assert summary["zizmor"]["ran"] is False
    assert summary["zizmor"]["findings"] == 0
    assert summary["zizmor"]["error"]
    assert not (out / "findings" / "raw" / "TOOL-zizmor.tool-zizmor.json").exists()


def test_zizmor_garbage_stdout_is_explicit_error(tmp_path):
    """Stdout that starts with ``[`` but is not valid JSON is an explicit error."""
    ts = _load_tool_scan()
    repo, out = _run_zizmor(ts, tmp_path, returncode=1, stdout="[oops", stderr="")

    summary = json.loads((out / "tools_summary.json").read_text(encoding="utf-8"))
    assert summary["zizmor"]["ran"] is False
    assert "illisible" in summary["zizmor"]["error"]
