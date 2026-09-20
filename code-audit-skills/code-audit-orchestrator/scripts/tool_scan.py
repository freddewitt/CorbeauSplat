#!/usr/bin/env python3
"""Détecte et lance les scanners de sécurité déterministes installés, puis convertit leurs
résultats au format des findings du pipeline (findings/raw/TOOL-<outil>.tool-<outil>.json).

Pourquoi : un scanner à règles ne rate pas les motifs connus et ne se fatigue pas ; le LLM
apporte le contexte et le tri. Un finding trouvé par un outil ET par un scout gagne en priorité
à la fusion (deux sources indépendantes). Approche hybride, documentée pour réduire fortement
les faux positifs par rapport au scanner seul.

Sous-commandes :
  detect   outils disponibles et pertinents pour ce dépôt (JSON)
  run      lance les outils choisis (lecture seule) et écrit les findings

Sécurité : les outils sont lancés sans réseau quand c'est possible (zizmor --offline).
semgrep télécharge ses règles depuis le registre si --semgrep-config est un pack (le code n'est
pas envoyé, --metrics=off). gitleaks ne conserve jamais la valeur des secrets : elle est masquée.
Adaptateurs testés sur de vraies sorties : bandit, semgrep, gitleaks, zizmor.
osv-scanner : adaptateur écrit d'après le format documenté, non testé sur le binaire réel.
Stdlib uniquement, Python 3.8+.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CWE_CATEGORY = {
    "89": "sql-injection", "564": "sql-injection", "78": "command-injection", "77": "command-injection", "88": "command-injection",
    "22": "path-traversal", "23": "path-traversal", "73": "path-traversal", "79": "xss", "80": "xss", "918": "ssrf",
    "502": "insecure-deserialization", "327": "weak-crypto", "328": "weak-crypto", "326": "weak-crypto", "330": "weak-random",
    "338": "weak-random", "798": "hardcoded-secret", "259": "hardcoded-secret", "321": "hardcoded-secret", "352": "csrf",
    "287": "auth-bypass", "306": "auth-bypass", "862": "broken-access-control", "863": "broken-access-control", "639": "idor",
    "94": "code-injection", "95": "code-injection", "611": "xxe", "601": "open-redirect", "1104": "vulnerable-dependency",
    "937": "vulnerable-dependency", "1035": "vulnerable-dependency", "362": "race-condition", "703": "error-handling",
    "400": "resource-exhaustion", "770": "resource-exhaustion", "295": "tls-validation", "312": "cleartext-storage",
    "532": "sensitive-log", "1321": "prototype-pollution", "117": "log-injection",
}

_SECRET_ASSIGN = re.compile(r"""(?i)((?:pass(?:word|wd)?|secret|token|api[_-]?key|private[_-]?key|credential|auth)[\w.-]*["']?\s*[:=]\s*|hardcoded (?:password|secret|key|token):\s*)(["'])([^"'\n]{6,})\2""")
_SECRET_TOKENS = re.compile(r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$))")


def mask_secrets(text):
    """Masque les valeurs de secrets dans un texte (défense en profondeur : aucun secret en clair dans les artefacts)."""
    if not isinstance(text, str) or not text:
        return text
    text = _SECRET_ASSIGN.sub(lambda m: "%s%s%s****%s" % (m.group(1), m.group(2), m.group(3)[:4], m.group(2)), text)
    return _SECRET_TOKENS.sub(lambda m: m.group(0)[:4] + "****", text)


SEVERITY_BAND = [(9.0, "critical"), (7.0, "high"), (4.0, "medium"), (0.1, "low")]


def which(name):
    return shutil.which(name)


def version_of(exe, arg="--version"):
    try:
        res = subprocess.run([exe, arg], capture_output=True, text=True, timeout=30)
        text = (res.stdout or res.stderr).strip()
        return text.splitlines()[0] if text else "inconnue"
    except (OSError, subprocess.SubprocessError):
        return "inconnue"


def band(score):
    for limit, name in SEVERITY_BAND:
        if score >= limit:
            return name
    return "info"


def rel_path(repo, p):
    p = str(p).replace("\\", "/")
    try:
        return Path(p).resolve().relative_to(repo).as_posix() if Path(p).is_absolute() else re.sub(r"^(\./)+", "", p)
    except ValueError:
        return p


def source_lines(repo, rel, start, end, limit=320):
    try:
        lines = (repo / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[max(0, start - 1):max(start, end)])[:limit]


def cwe_of(values):
    for v in values if isinstance(values, list) else [values]:
        m = re.search(r"(\d+)", str(v))
        if m:
            return "CWE-" + m.group(1), CWE_CATEGORY.get(m.group(1))
    return "", None


def finding(**kw):
    base = {"file": "", "line_start": 1, "line_end": 1, "category": "", "cwe": "", "severity": "medium", "confidence": 0.6,
            "title": "", "evidence": "", "attack_path": "", "impact": "", "fix": ""}
    base.update(kw)
    for k in ("title", "evidence", "impact", "fix", "attack_path"):
        base[k] = mask_secrets(base[k])
    return base


# --------------------------------------------------------------------------- adaptateurs

def parse_bandit(data, repo):
    conf = {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.4}
    sev = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    out = []
    for r in data.get("results", []):
        rel = rel_path(repo, r.get("filename", ""))
        lr = r.get("line_range") or [r.get("line_number", 1)]
        cwe, cat = cwe_of(r.get("issue_cwe", {}).get("id"))
        out.append(finding(file=rel, line_start=min(lr), line_end=max(lr), category=cat or ("bandit-" + str(r.get("test_id", "")).lower()),
                           cwe=cwe, severity=sev.get(r.get("issue_severity"), "medium"), confidence=conf.get(r.get("issue_confidence"), 0.5),
                           title="[bandit %s] %s" % (r.get("test_id"), r.get("issue_text", "")),
                           evidence=source_lines(repo, rel, min(lr), max(lr))))
    return out


def parse_semgrep(data, repo):
    sev = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
    conf = {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.4}
    out = []
    for r in data.get("results", []):
        extra, meta = r.get("extra", {}), r.get("extra", {}).get("metadata", {})
        rel = rel_path(repo, r.get("path", ""))
        start, end = r["start"]["line"], r["end"]["line"]
        cwe, cat = cwe_of(meta.get("cwe", []))
        out.append(finding(file=rel, line_start=start, line_end=end, category=cat or str(r.get("check_id", "")).split(".")[-1],
                           cwe=cwe, severity=sev.get(extra.get("severity"), "medium"),
                           confidence=conf.get(str(meta.get("confidence", "")).upper(), 0.6),
                           title="[semgrep %s] %s" % (str(r.get("check_id", "")).split(".")[-1], extra.get("message", "")[:200]),
                           evidence=source_lines(repo, rel, start, end),  # semgrep masque parfois les lignes: on relit la source
                           fix=str(extra.get("fix", ""))[:200]))
    return out


def parse_gitleaks(data, repo):
    out = []
    for r in data if isinstance(data, list) else []:
        rel = rel_path(repo, r.get("File", ""))
        secret = r.get("Secret", "") or ""
        line = source_lines(repo, rel, r.get("StartLine", 1), r.get("EndLine", 1))
        masked = line.replace(secret, secret[:4] + "****") if secret and secret in line else "(ligne masquée : contient un secret)"
        history = bool(r.get("Commit"))
        out.append(finding(file=rel, line_start=r.get("StartLine", 1), line_end=r.get("EndLine", 1), category="hardcoded-secret", cwe="CWE-798",
                           severity="high", confidence=0.7 if r.get("Entropy", 0) > 3.5 else 0.5,
                           title="[gitleaks %s] %s%s" % (r.get("RuleID"), r.get("Description", "secret détecté"),
                                                         " (dans l'historique git, commit %s)" % str(r.get("Commit"))[:8] if history else ""),
                           evidence=masked[:200],
                           impact="Secret exposé dans le dépôt : à considérer comme compromis et à révoquer/roter, pas seulement à supprimer du code.",
                           fix="Retirer du code, charger depuis l'environnement ou un gestionnaire de secrets, roter le secret, purger l'historique si nécessaire."))
    return out


def parse_zizmor(data, repo):
    sev = {"High": "high", "Medium": "medium", "Low": "low", "Informational": "info"}
    conf = {"High": 0.85, "Medium": 0.65, "Low": 0.45}
    out = []
    for r in data if isinstance(data, list) else []:
        if r.get("ignored"):
            continue
        loc = next((l for l in r.get("locations", []) if l.get("symbolic", {}).get("kind") == "Primary"), (r.get("locations") or [None])[0])
        if not loc:
            continue
        path = loc["symbolic"]["key"].get("Local", {}).get("verbatim_path", "")
        c = loc.get("concrete", {}).get("location", {})
        start, end = c.get("start_point", {}).get("row", 0) + 1, c.get("end_point", {}).get("row", 0) + 1
        det = r.get("determinations", {})
        cat = {"template-injection": "ci-template-injection", "dangerous-triggers": "ci-dangerous-trigger"}.get(r.get("ident"), "ci-" + str(r.get("ident")))
        out.append(finding(file=rel_path(repo, path), line_start=start, line_end=end, category=cat,
                           severity=sev.get(det.get("severity"), "medium"), confidence=conf.get(det.get("confidence"), 0.5),
                           title="[zizmor %s] %s : %s" % (r.get("ident"), r.get("desc", ""), loc["symbolic"].get("annotation", "")),
                           evidence=(loc.get("concrete", {}).get("feature", "") or "")[:300],
                           fix="; ".join(f.get("title", "") for f in r.get("fixes", []))[:200]))
    return out


def parse_osv(data, repo):
    out = []
    for res in data.get("results", []):
        rel = rel_path(repo, (res.get("source") or {}).get("path", ""))
        for pk in res.get("packages", []):
            p = pk.get("package", {})
            best = {}
            for grp in pk.get("groups", []):
                for i in grp.get("ids", []):
                    try:
                        best[i] = float(grp.get("max_severity", 0) or 0)
                    except ValueError:
                        best[i] = 0.0
            for v in pk.get("vulnerabilities", []):
                score = best.get(v.get("id"), 0.0)
                dbs = str((v.get("database_specific") or {}).get("severity", "")).lower()
                severity = band(score) if score else (dbs if dbs in ("critical", "high", "medium", "low") else "medium")
                cwe, _ = cwe_of((v.get("database_specific") or {}).get("cwe_ids", []))
                out.append(finding(file=rel, line_start=1, line_end=1, category="vulnerable-dependency", cwe=cwe or "CWE-1104",
                                   severity=severity, confidence=0.7,
                                   title="[osv] %s@%s : %s %s" % (p.get("name"), p.get("version"), v.get("id"), (v.get("summary") or "")[:120]),
                                   evidence="%s@%s (%s)" % (p.get("name"), p.get("version"), p.get("ecosystem")),
                                   impact="Dépendance vulnérable. Vérifier si le code appelle la fonction concernée (atteignabilité) avant de prioriser.",
                                   fix="Mettre à jour %s vers une version corrigée (voir %s) et relancer les tests." % (p.get("name"), v.get("id"))))
    return out


# --------------------------------------------------------------------------- exécution

def run_cmd(cmd, cwd, timeout, ok_codes):
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return res.returncode in ok_codes, res


def tool_relevance(repo):
    files = subprocess.run(["git", "-C", str(repo), "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.split("\n") if (repo / ".git").exists() else []
    if not files or files == [""]:
        files = [os.path.relpath(os.path.join(r, f), repo) for r, d, fs in os.walk(repo) for f in fs if ".git" not in r]
    has = lambda pred: any(pred(f) for f in files)
    return {
        "semgrep": has(lambda f: f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".c", ".cpp", ".cs", ".rs", ".kt"))),
        "bandit": has(lambda f: f.endswith(".py")),
        "gitleaks": True,
        "zizmor": has(lambda f: f.startswith(".github/workflows/")),
        "osv-scanner": has(lambda f: Path(f).name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "requirements.txt", "go.mod", "Cargo.lock", "Gemfile.lock", "composer.lock", "pom.xml", "uv.lock"}),
    }


def cmd_detect(a):
    repo = Path(a.repo).resolve()
    rel = tool_relevance(repo)
    res = {}
    for name, relevant in rel.items():
        exe = which(name)
        res[name] = {"installed": bool(exe), "relevant": relevant, "version": version_of(exe) if exe else None,
                     "usable": bool(exe) and relevant}
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_run(a):
    repo = Path(a.repo).resolve()
    out = Path(a.out).resolve()
    raw = out / "findings" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rel = tool_relevance(repo)
    wanted = [t.strip() for t in a.tools.split(",")] if a.tools else [t for t, r in rel.items() if r]
    summary = {}
    for name in wanted:
        exe = which(name)
        entry = {"ran": False, "findings": 0, "error": None, "version": None}
        summary[name] = entry
        if not exe:
            entry["error"] = "non installé"
            continue
        entry["version"] = version_of(exe)
        start = time.time()
        tmp = None
        try:
            if name == "bandit":
                ok, res = run_cmd([exe, "-r", str(repo), "-f", "json", "-q", "--exit-zero", "-x", "*/tests/*,*/node_modules/*,*/.venv/*,*/venv/*,*/audit/*,*/.opencode/*,*/.agents/*,*/.claude/*"], repo, a.timeout, {0})
                findings = parse_bandit(json.loads(res.stdout), repo) if ok else None
            elif name == "semgrep":
                cfg = a.semgrep_config
                ok, res = run_cmd([exe, "--config", cfg, "--json", "--metrics=off", "--disable-version-check", "--quiet", "--exclude", "audit", "--exclude", ".opencode", "--exclude", ".agents", "--exclude", ".claude", "."], repo, a.timeout, {0, 1})
                findings = parse_semgrep(json.loads(res.stdout), repo) if ok and res.stdout.strip() else None
            elif name == "gitleaks":
                findings, seen = [], set()
                for git_mode in ([False, True] if a.history else [False]):
                    fd, tmp = tempfile.mkstemp(suffix=".json")
                    os.close(fd)
                    cmd = [exe, "detect", "-s", str(repo), "--report-format", "json", "--report-path", tmp, "--no-banner", "--exit-code", "0"]
                    if not git_mode:
                        cmd.insert(2, "--no-git")
                    ok, res = run_cmd(cmd, repo, a.timeout, {0})
                    if ok:
                        for f in parse_gitleaks(json.loads(Path(tmp).read_text(encoding="utf-8") or "[]"), repo):
                            key = (f["file"], f["line_start"], f["title"].split("]")[0])
                            if key not in seen:
                                seen.add(key)
                                findings.append(f)
                    os.unlink(tmp)  # le rapport brut de gitleaks contient les secrets en clair
                    tmp = None
                    if not ok:
                        findings = None
                        break
            elif name == "zizmor":
                wf = repo / ".github" / "workflows"
                ok, res = run_cmd([exe, "--format", "json-v1", "--offline", "--no-progress", str(wf)], repo, a.timeout, set(range(0, 256)))
                findings = parse_zizmor(json.loads(res.stdout), repo) if res.stdout.strip().startswith("[") else None
                ok = findings is not None
            elif name == "osv-scanner":
                ok, res = run_cmd([exe, "scan", "source", "--format", "json", "-r", str(repo)], repo, a.timeout, {0, 1})
                if not ok or not res.stdout.strip().startswith("{"):
                    ok, res = run_cmd([exe, "--format", "json", "-r", str(repo)], repo, a.timeout, {0, 1})
                findings = parse_osv(json.loads(res.stdout), repo) if ok and res.stdout.strip().startswith("{") else None
            else:
                entry["error"] = "outil inconnu"
                continue
        except subprocess.TimeoutExpired:
            entry["error"] = "délai dépassé (%ds)" % a.timeout
            continue
        except (ValueError, OSError, KeyError) as exc:
            entry["error"] = "sortie illisible: %s" % exc
            continue
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)  # le rapport brut de gitleaks contient les secrets en clair
        if findings is None:
            entry["error"] = ((res.stderr or res.stdout or "").strip().splitlines() or ["échec"])[-1][:200]
            continue
        entry.update({"ran": True, "findings": len(findings), "seconds": round(time.time() - start, 1)})
        (raw / ("TOOL-%s.tool-%s.json" % (name, name))).write_text(
            json.dumps({"chunk_id": "TOOL-" + name, "findings": findings}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "tools_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, e in summary.items():
        print("%-12s %s" % (name, ("%d finding(s), %s" % (e["findings"], e["version"])) if e["ran"] else "ignoré : %s" % e["error"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("detect"); p.add_argument("--repo", default="."); p.set_defaults(fn=cmd_detect)
    p = sub.add_parser("run"); p.add_argument("--repo", default="."); p.add_argument("--out", default="audit")
    p.add_argument("--tools", default="", help="liste séparée par des virgules (défaut: tous les outils pertinents installés)")
    p.add_argument("--semgrep-config", default="p/default", help="pack du registre (p/default, p/security-audit) ou chemin de règles locales")
    p.add_argument("--history", action="store_true", help="gitleaks: analyser aussi l'historique git")
    p.add_argument("--timeout", type=int, default=900); p.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
