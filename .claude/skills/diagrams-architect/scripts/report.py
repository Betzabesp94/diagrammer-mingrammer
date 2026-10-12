"""Fusiona los reportes de cada etapa en un único JSON compacto (sin CLI).

El modelo lee solo `overall`, `counts` y la lista de findings; el detalle de cada id está en
references/validations.md. Se omiten los campos vacíos para gastar pocos tokens.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

STAGE_ORDER = ("parse_dsl", "validate_ir", "validate_architecture", "validate_code", "validate_layout", "check_determinism")


def compact_finding(finding, stage):
    out = {"id": finding["id"], "severity": finding["severity"], "stage": stage, "message": finding["message"]}
    for key in ("where", "subject", "expected", "found", "hint"):
        value = finding.get(key)
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def mapping_summary(ir):
    """Resumen del mapeo icono -> clase para el reporte final."""
    if not ir:
        return {}
    counts = {}
    for n in ir["nodes"]:
        counts[n["confidence"]] = counts.get(n["confidence"], 0) + 1
    not_exact = [
        {"node": n["id"], "class": n["diagrams_class"], "confidence": n["confidence"]}
        for n in ir["nodes"] if n["confidence"] != "exact" and n.get("role", "service") == "service"
    ]
    return {"by_confidence": dict(sorted(counts.items())), "not_exact": not_exact}


def merge(slug, stages, ir=None, artifacts=None):
    """`stages`: lista de dicts producidos por Report.to_dict(). Devuelve el reporte unificado."""
    ordered = sorted(stages, key=lambda s: STAGE_ORDER.index(s["tool"]) if s["tool"] in STAGE_ORDER else 99)
    findings = []
    for stage in ordered:
        findings += [compact_finding(f, stage["tool"]) for f in stage["findings"]]
    rank = irlib.SEVERITY_RANK
    findings.sort(key=lambda f: (rank[f["severity"]], STAGE_ORDER.index(f["stage"]) if f["stage"] in STAGE_ORDER else 99, f["id"],
                                 f.get("where", ""), f.get("subject", "")))
    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"].lower()] += 1
    overall = "FAIL" if counts["error"] else "WARN" if counts["warning"] else "PASS"
    report = {
        "slug": slug,
        "overall": overall,
        "counts": counts,
        "env": irlib.env_versions(),
        "stages": {s["tool"]: s["overall"] for s in ordered},
        "findings": findings,
    }
    if ir:
        report["mapping"] = mapping_summary(ir)
    if artifacts:
        report["artifacts"] = artifacts
    return report
