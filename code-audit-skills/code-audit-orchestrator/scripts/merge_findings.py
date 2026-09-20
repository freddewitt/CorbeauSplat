#!/usr/bin/env python3
"""Fusionne les findings bruts (scouts et scanners), prépare la vérification, applique les verdicts.

  merge     audit/findings/raw/*.json -> audit/merged.json + audit/verification/batch_NN.json
            (--graph : atteignabilité par finding ; --baseline : ignore les findings déjà tranchés)
  apply     audit/merged.json + audit/verification/result_*.json -> audit/final.json
  baseline  enregistre les findings tranchés (faux positifs...) pour ne pas les revérifier au prochain audit

Nom des fichiers bruts : <chunk_id>.<slug-du-modèle>.json (ex. C003.deepseek-v4-1-flash.json),
slug sans point. Contenu accepté : {"chunk_id": ..., "findings": [...]} ou directement une liste.
Tous les textes passent par un masqueur de secrets. Stdlib uniquement, Python 3.8+.
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


_SECRET_ASSIGN = re.compile(r"""(?i)((?:pass(?:word|wd)?|secret|token|api[_-]?key|private[_-]?key|credential|auth)[\w.-]*["']?\s*[:=]\s*|hardcoded (?:password|secret|key|token):\s*)(["'])([^"'\n]{6,})\2""")
_SECRET_TOKENS = re.compile(r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$))")


def mask_secrets(text):
    """Masque les valeurs de secrets dans un texte (défense en profondeur : aucun secret en clair dans les artefacts)."""
    if not isinstance(text, str) or not text:
        return text
    text = _SECRET_ASSIGN.sub(lambda m: "%s%s%s****%s" % (m.group(1), m.group(2), m.group(3)[:4], m.group(2)), text)
    return _SECRET_TOKENS.sub(lambda m: m.group(0)[:4] + "****", text)


SEV_W = {"critical": 10, "high": 6, "medium": 3, "low": 1, "info": 0.3}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]
VERDICTS = {"confirmed", "likely", "false_positive", "needs_info"}
LINE_TOLERANCE = 5
sys.path.insert(0, str(Path(__file__).resolve().parent))


def model_from_name(path):
    parts = path.name.split(".")
    return ".".join(parts[1:-1]) if len(parts) >= 3 else "unknown"


def load_raw(raw_dir):
    findings, errors = [], []
    for path in sorted(Path(raw_dir).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append("%s: JSON invalide (%s)" % (path.name, exc))
            continue
        items = data if isinstance(data, list) else data.get("findings", [])
        chunk_id = path.name.split(".")[0] if isinstance(data, list) else data.get("chunk_id", path.name.split(".")[0])
        model = model_from_name(path)
        for it in items:
            f = normalize(it, chunk_id, model)
            if f is None:
                errors.append("%s: finding ignoré (champs file/line_start/title manquants)" % path.name)
            else:
                findings.append(f)
    return findings, errors


def clean_path(p):
    s = str(p).replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s


def normalize(it, chunk_id, model):
    if not isinstance(it, dict) or not it.get("file") or not it.get("title"):
        return None
    try:
        start = int(it.get("line_start"))
        end = int(it.get("line_end") or start)
    except (TypeError, ValueError):
        return None
    sev = str(it.get("severity", "medium")).lower()
    if sev not in SEV_W:
        sev = "medium"
    try:
        conf = min(1.0, max(0.0, float(it.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return {
        "file": clean_path(it["file"]),
        "line_start": min(start, end), "line_end": max(start, end),
        "category": str(it.get("category", "")).lower().strip(),
        "cwe": str(it.get("cwe", "")).upper().strip(),
        "severity": sev, "confidence": conf, "title": mask_secrets(str(it["title"]).strip()),
        "evidence": mask_secrets(it.get("evidence", "")),
        "attack_path": mask_secrets(it.get("attack_path", it.get("exploit_scenario", ""))),
        "impact": mask_secrets(it.get("impact", "")), "fix": mask_secrets(it.get("fix", "")),
        "chunk_ids": [chunk_id], "sources": [model],
    }


def same_issue(a, b):
    if a["file"] != b["file"]:
        return False
    if a["line_start"] > b["line_end"] + LINE_TOLERANCE or b["line_start"] > a["line_end"] + LINE_TOLERANCE:
        return False
    if a["cwe"] and a["cwe"] == b["cwe"]:
        return True
    if a["category"] and a["category"] == b["category"]:
        return True
    return difflib.SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio() > 0.6


def dedupe(findings):
    merged = []
    for f in sorted(findings, key=lambda x: (x["file"], x["line_start"])):
        target = next((m for m in merged if same_issue(m, f)), None)
        if target is None:
            merged.append(dict(f, alt_titles=[]))
            continue
        base_better = (SEV_W[f["severity"]], f["confidence"]) > (SEV_W[target["severity"]], target["confidence"])
        for k in ("evidence", "attack_path", "impact", "fix"):  # le texte le plus riche l'emporte
            if len(str(f[k] or "")) > len(str(target[k] or "")):
                target[k] = f[k]
        if base_better:
            for k in ("title", "category", "cwe"):
                if f[k]:
                    if k == "title" and target["title"] != f["title"]:
                        target["alt_titles"].append(target["title"])
                    target[k] = f[k]
        elif f["title"] != target["title"]:
            target["alt_titles"].append(f["title"])
        target["severity"] = max(target["severity"], f["severity"], key=lambda s: SEV_W[s])
        target["confidence"] = max(target["confidence"], f["confidence"])
        target["line_start"] = min(target["line_start"], f["line_start"])
        target["line_end"] = max(target["line_end"], f["line_end"])
        target["chunk_ids"] = sorted(set(target["chunk_ids"] + f["chunk_ids"]))
        target["sources"] = sorted(set(target["sources"] + f["sources"]))
    return merged


def fingerprint(m):
    """Empreinte stable (indépendante des numéros de ligne) pour reconnaître un finding d'un audit à l'autre."""
    ev = re.sub(r"\s+", " ", str(m.get("evidence", ""))).strip().lower()[:160]
    base = "%s|%s|%s" % (m["file"], m.get("category", ""), ev or str(m["title"]).lower()[:80])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def load_baseline(path):
    if not path or not Path(path).is_file():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("fingerprints", {})
    except (OSError, ValueError):
        return {}


def module_of(path):
    return "/".join(path.split("/")[:-1][:2]) or "."


def cmd_merge(a):
    prev = Path(a.out) / "merged.json"
    if prev.exists() and not a.force:
        try:
            done = any(f.get("verification") for f in json.loads(prev.read_text(encoding="utf-8"))["findings"])
        except (OSError, ValueError, KeyError):
            done = False
        if done or list((Path(a.out) / "verification").glob("result_*.json")):
            sys.exit("Des vérifications existent déjà: relancer merge écraserait les ids. Utilisez --force pour forcer.")
    findings, errors = load_raw(a.raw)
    if not findings and not errors:
        sys.exit("Aucun finding brut dans %s" % a.raw)
    merged = dedupe(findings)
    baseline = load_baseline(a.baseline)
    graph = None
    if a.graph:
        try:
            from graph_tool import Graph, reach_info
            graph = Graph(a.graph)
        except Exception as exc:  # graphe absent ou illisible : on continue sans
            errors.append("graphe ignoré: %s" % exc)
    for m in merged:
        m["votes"] = len(m["sources"])
        if graph is not None:
            m["graph"] = reach_info(graph, m["file"], m["line_start"])
        reach = (m.get("graph") or {}).get("reachable")
        factor = 1.25 if reach is True else 0.8 if reach is False else 1.0  # atteignable depuis un point d'entrée = plus urgent à vérifier
        m["score"] = round(SEV_W[m["severity"]] * m["confidence"] * (1 + 0.5 * (m["votes"] - 1)) * factor, 2)
    merged.sort(key=lambda m: -m["score"])
    for i, m in enumerate(merged, 1):
        m["id"] = "F-%03d" % i
        m["fingerprint"] = fingerprint(m)
        m["status"] = "unverified"
        m["verification"] = None
        if m["fingerprint"] in baseline:
            m["status"] = "suppressed"
            m["suppressed_reason"] = baseline[m["fingerprint"]].get("reason", "connu (baseline)")

    active = [m for m in merged if m["status"] != "suppressed"]
    urgent = [m for m in active if m["severity"] in ("critical", "high") and (m["confidence"] >= 0.3 or m["votes"] >= 2)]
    selected = urgent[: a.max_verify]
    for m in active:
        if len(selected) >= a.max_verify:
            break
        if m not in selected and m["severity"] != "info":
            selected.append(m)
    overflow = [m["id"] for m in urgent if m not in selected]
    for m in selected:
        m["status"] = "to_verify"

    out = Path(a.out)
    vdir = out / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    for old in vdir.glob("batch_*.json"):
        old.unlink()
    ordered = sorted(selected, key=lambda m: (module_of(m["file"]), m["file"], m["line_start"]))
    batches = [ordered[i:i + a.batch_size] for i in range(0, len(ordered), a.batch_size)]
    for n, batch in enumerate(batches, 1):
        payload = {
            "batch_id": "B%02d" % n,
            "files_needed": sorted({m["file"] for m in batch}),
            "findings": [{k: m[k] for k in ("id", "file", "line_start", "line_end", "category", "cwe", "severity",
                                             "confidence", "title", "evidence", "attack_path", "impact", "fix",
                                             "sources", "graph") if k in m} for m in batch],
        }
        (vdir / ("batch_%02d.json" % n)).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    doc = {"findings": merged, "overflow_unverified_high": overflow, "parse_errors": errors}
    (out / "merged.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    sev = Counter(m["severity"] for m in merged)
    supp = sum(1 for m in merged if m["status"] == "suppressed")
    if supp:
        print("%d finding(s) déjà connus (baseline) : non revérifiés" % supp)
    print("Bruts: %d -> fusionnés: %d (%s)" % (
        len(findings), len(merged), ", ".join("%s %d" % (s, sev[s]) for s in SEV_ORDER if sev[s])))
    print("À vérifier: %d en %d lot(s) de %d max -> %d appel(s) au vérificateur" % (
        len(selected), len(batches), a.batch_size, len(batches)))
    if overflow:
        print("ATTENTION: %d finding(s) critique/high hors budget de vérification: %s" % (len(overflow), ", ".join(overflow)))
    for e in errors:
        print("Avertissement:", e)


def cmd_apply(a):
    doc = json.loads(Path(a.merged).read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in doc["findings"]}
    unknown = []
    for path in sorted(Path(a.verification).glob("result_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print("Avertissement: %s illisible (%s)" % (path.name, exc))
            continue
        try:
            if isinstance(data, dict):
                results = data.get("results")
            elif isinstance(data, list):
                results = data
            else:
                print("Avertissement: entrée ignorée dans %s (%r)" % (path.name, type(data).__name__))
                continue
            if not isinstance(results, list):
                print("Avertissement: entrée ignorée dans %s (%r)" % (path.name, type(results).__name__))
                continue
            for r in results:
                try:
                    if not isinstance(r, dict):
                        print("Avertissement: entrée ignorée dans %s (%r)" % (path.name, r))
                        continue
                    m = by_id.get(r.get("id"))
                    if m is None:
                        unknown.append(str(r.get("id")))
                        continue
                    verdict = str(r.get("verdict", "")).lower()
                    if verdict not in VERDICTS:
                        print("Avertissement: verdict invalide pour %s: %r" % (m["id"], verdict))
                        continue
                    m["verification"] = r
                    m["status"] = verdict
                    sev = str(r.get("severity_final", "")).lower()
                    m["severity_final"] = sev if sev in SEV_W else m["severity"]
                except Exception as exc:
                    print("Avertissement: entrée ignorée dans %s (%s)" % (path.name, exc))
        except Exception as exc:
            print("Avertissement: %s ignoré (%s)" % (path.name, exc))

    out = Path(a.out)
    (out / "final.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    status = Counter(m["status"] for m in doc["findings"])
    verified = sum(status[k] for k in VERDICTS)
    print("Statuts: " + ", ".join("%s %d" % (k, v) for k, v in sorted(status.items())))
    if verified:
        fp = status["false_positive"] / verified
        print("Taux de faux positifs du scout (sur les findings vérifiés): %.0f%% (%d/%d)" % (
            100 * fp, status["false_positive"], verified))
    kept = [m for m in doc["findings"] if m["status"] in ("confirmed", "likely")]
    kept.sort(key=lambda m: SEV_ORDER.index(m.get("severity_final", m["severity"])))
    for m in kept:
        print(" %s [%s/%s] %s:%d %s" % (m["id"], m["status"], m.get("severity_final", m["severity"]),
                                         m["file"], m["line_start"], m["title"]))
    if unknown:
        print("Avertissement: ids inconnus dans les résultats:", ", ".join(unknown))
    print("Écrit: %s" % (out / "final.json"))


def cmd_baseline(a):
    doc = json.loads(Path(a.final).read_text(encoding="utf-8"))
    path = Path(a.out)
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"fingerprints": {}}
    wanted = {s.strip() for s in a.statuses.split(",")}
    added = 0
    for m in doc["findings"]:
        if m["status"] in wanted and m.get("fingerprint"):
            reason = (m.get("verification") or {}).get("reasoning") or m.get("suppressed_reason") or m["status"]
            current["fingerprints"][m["fingerprint"]] = {"reason": str(reason)[:200], "status": m["status"], "title": m["title"], "file": m["file"]}
            added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Baseline: %d entrée(s) ajoutée(s), %d au total -> %s" % (added, len(current["fingerprints"]), path))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--raw", default="audit/findings/raw")
    m.add_argument("--out", default="audit")
    m.add_argument("--max-verify", type=int, default=15, help="nombre max de findings envoyés au vérificateur")
    m.add_argument("--batch-size", type=int, default=4, help="findings par appel de vérification")
    m.add_argument("--baseline", default="audit/baseline.json", help="findings déjà tranchés à ne pas revérifier (défaut audit/baseline.json)")
    m.add_argument("--graph", default="", help="graph.json de graphify : ajoute symbole et atteignabilité à chaque finding")
    m.add_argument("--force", action="store_true", help="écraser même si des vérifications existent")
    m.set_defaults(fn=cmd_merge)
    b = sub.add_parser("baseline", help="enregistre des findings tranchés (faux positifs, risques acceptés) pour les audits suivants")
    b.add_argument("--final", default="audit/final.json")
    b.add_argument("--out", default="audit/baseline.json")
    b.add_argument("--statuses", default="false_positive", help="statuts à enregistrer, séparés par des virgules")
    b.set_defaults(fn=cmd_baseline)
    p = sub.add_parser("apply")
    p.add_argument("--merged", default="audit/merged.json")
    p.add_argument("--verification", default="audit/verification")
    p.add_argument("--out", default="audit")
    p.set_defaults(fn=cmd_apply)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
