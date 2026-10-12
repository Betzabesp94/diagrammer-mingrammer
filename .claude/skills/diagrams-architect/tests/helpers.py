"""Utilidades comunes de las pruebas (solo stdlib)."""

import copy
import json
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
REPO = SKILL.parent.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = Path(__file__).resolve().parent / "golden"

sys.path.insert(0, str(SCRIPTS))


def node(nid, label=None, cls="diagrams.aws.compute.EC2", cluster=None, **extra):
    label = label or nid
    n = {
        "id": nid, "var": nid, "label": label, "label_wrapped": label,
        "diagrams_class": cls, "confidence": "exact", "cluster": cluster,
    }
    n.update(extra)
    return n


def cluster(cid, label=None, parent=None, zone=0, **extra):
    c = {"id": cid, "label": label or cid, "parent": parent, "zone": zone}
    c.update(extra)
    return c


def edge(eid, source, target, label=None, **extra):
    e = {"id": eid, "source": source, "target": target, "arrow": "forward"}
    if label is not None:
        e["label"] = label
    e.update(extra)
    return e


def base_ir():
    """IR canónico mínimo y sano: 3 nodos en un cluster, 2 aristas con label."""
    return {
        "schema_version": 2, "title": "Prueba", "slug": "prueba", "provider": "aws", "direction": "LR",
        "nodes": [
            node("web", "Web", cluster="vpc"),
            node("api", "API", cluster="vpc"),
            node("db", "DB", "diagrams.aws.database.RDS", cluster="vpc"),
        ],
        "clusters": [cluster("vpc", "VPC", boundary=True)],
        "edges": [edge("e1", "web", "api", "HTTPS"), edge("e2", "api", "db", "SQL")],
    }


def mutated(fn):
    ir = copy.deepcopy(base_ir())
    fn(ir)
    return ir


def ids(report):
    d = report.to_dict(with_env=False) if hasattr(report, "to_dict") else report
    return [f["id"] for f in d["findings"]]


def run_script(name, *args, env=None, cwd=None):
    """Ejecuta un script de la skill con el intérprete actual."""
    import os

    full_env = dict(os.environ)
    full_env.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        capture_output=True, text=True, env=full_env, cwd=cwd or REPO,
    )


def run_json(name, *args, **kw):
    res = run_script(name, *args, **kw)
    try:
        return res.returncode, json.loads(res.stdout), res.stderr
    except json.JSONDecodeError:
        raise AssertionError(f"{name} no devolvió JSON.\nstdout={res.stdout}\nstderr={res.stderr}")


def build_ir(diag_path):
    """.diag -> IR canónico, en proceso (mismo camino que make diagram)."""
    import parse_dsl
    import resolve_ir

    text = Path(diag_path).read_text(encoding="utf-8")
    raw = parse_dsl.parse(text, Path(diag_path).stem)
    raw["meta"]["source"] = Path(diag_path).name
    return resolve_ir.resolve(raw)
