#!/usr/bin/env python3
"""Reglas pequeñas y deterministas de Solutions Architect sobre el IR canónico.

    .venv/bin/python scripts/validate_architecture.py <slug>.ir.json [--skip-isolated]

No es un motor de Well-Architected: son cuatro chequeos para atrapar lo obvio, no para auditar.
Ninguno emite ERROR, así que nunca bloquea: los findings llegan al reporte tal cual y el
usuario decide. Nunca se corrigen en silencio cambiando la topología pedida.

  ARQ001 networking      nodos a los que no llega tráfico y no son el entrypoint
  ARQ002 security        el entrypoint público conecta directo a una base de datos
  ARQ003 availability    base de datos sin multi_az/multi_region en una arquitectura productiva
  ARQ004 observability   arquitectura productiva sin logging ni monitoreo (INFO)
  ARQ010 networking      no se declaró entrypoint: las reglas de red y seguridad no se pudieron aplicar (INFO)

El tamaño del diagrama no está aquí: lo cubren SIZ001 y SIZ002 en validate_ir.py.
`--skip-isolated` omite los nodos sin ninguna arista de ARQ001, porque validate_ir ya los reporta
como CONN003 (lo usa el pipeline para no duplicar el hallazgo).

Declara el entrypoint y el entorno en el .diag con `entrypoint: Nombre` y `production: true`.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

DB_KEYWORDS = (
    "rds", "dynamodb", "aurora", "redshift", "elasticache", "documentdb", "neptune",
    "postgres", "mysql", "mongodb", "mariadb", "cosmosdb", "cloudsql", "bigtable",
    "firestore", "memorystore", "spanner", "sqlserver", "cassandra", ".database.",
)
MONITORING_KEYWORDS = (
    "cloudwatch", "cloudtrail", "xray", "prometheus", "grafana", "datadog",
    "newrelic", "stackdriver", "monitoring", "logging", "opsview", "splunk",
)
PRODUCTION_RE = re.compile(r"\b(producci[oó]n|production|alta disponibilidad|high availability|ha|prod)\b", re.IGNORECASE)


def _text(node):
    return f"{node.get('diagrams_class', '')} {node.get('service', '')}".lower()


def _matches(text, keywords):
    return any(k in text for k in keywords)


def is_production(ir):
    constraints = ir.get("constraints") or {}
    if constraints.get("production"):
        return True
    return bool(PRODUCTION_RE.search(str(constraints.get("notes", ""))))


def check_networking(ir, rep, skip_isolated):
    entrypoint = (ir.get("constraints") or {}).get("internet_entrypoint")
    if not entrypoint:
        rep.add("ARQ010", "INFO", "architecture",
                "no se declaró entrypoint: no se verificó la alcanzabilidad ni la exposición a internet",
                hint="Agrega `entrypoint: <nodo>` al inicio del .diag.")
        return False
    nodes = irlib.flow_nodes(ir)
    edges = irlib.flow_edges(ir)
    incoming = {n["id"]: 0 for n in nodes}
    outgoing = {n["id"]: 0 for n in nodes}
    for e in edges:
        if e["target"] in incoming:
            incoming[e["target"]] += 1
        if e["source"] in outgoing:
            outgoing[e["source"]] += 1
        if e.get("arrow") in ("both", "none"):
            if e["source"] in incoming:
                incoming[e["source"]] += 1
            if e["target"] in outgoing:
                outgoing[e["target"]] += 1
    unreachable = []
    for n in nodes:  # orden del IR: el mensaje no depende del hash de los ids
        nid = n["id"]
        if nid == entrypoint or n.get("standalone") or incoming[nid]:
            continue
        isolated = not outgoing[nid]
        if isolated and skip_isolated:
            continue
        unreachable.append(nid)
    if unreachable:
        rep.add("ARQ001", "WARNING", "architecture",
                f"a los nodos {unreachable} no llega ninguna conexión y no son el entrypoint ({entrypoint})",
                subject=",".join(unreachable), found=unreachable,
                hint="Revisa si deberían recibir tráfico a través de un balanceador, API gateway o CDN, o si falta modelarlo.")
    return True


def check_security(ir, rep):
    entrypoint = (ir.get("constraints") or {}).get("internet_entrypoint")
    if not entrypoint:
        return
    by_id = {n["id"]: n for n in ir["nodes"]}
    for e in irlib.flow_edges(ir):
        if e["source"] == entrypoint and e["target"] in by_id and _matches(_text(by_id[e["target"]]), DB_KEYWORDS):
            rep.add("ARQ002", "WARNING", "architecture",
                    f"el entrypoint público ({entrypoint}) conecta directo a {e['target']!r}, que parece una base de datos",
                    subject=e["target"],
                    hint="Revisa si falta una capa de aplicación o API entre el tráfico público y el dato.")


def check_availability(ir, rep):
    if not is_production(ir):
        return
    for n in irlib.flow_nodes(ir):
        if _matches(_text(n), DB_KEYWORDS):
            tags = n.get("tags") or {}
            if not tags.get("multi_az") and not tags.get("multi_region"):
                rep.add("ARQ003", "WARNING", "architecture",
                        f"{n['id']!r} parece una base de datos y la arquitectura es productiva, pero no está marcada multi_az",
                        subject=n["id"], hint="Confirma si es Single-AZ a propósito o agrega `tag.multi_az: true`.")


def check_observability(ir, rep):
    if is_production(ir) and not any(_matches(_text(n), MONITORING_KEYWORDS) for n in irlib.flow_nodes(ir)):
        rep.add("ARQ004", "INFO", "architecture",
                "arquitectura productiva sin componentes de logging ni monitoreo (CloudWatch, Prometheus, Datadog...)",
                hint="Es una observación: no se agrega solo, va como recomendación aparte.")


def validate(ir, ir_path="", skip_isolated=False):
    rep = irlib.Report("validate_architecture", target=ir_path, ir=ir_path)
    check_networking(ir, rep, skip_isolated)
    check_security(ir, rep)
    check_availability(ir, rep)
    check_observability(ir, rep)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir", help="IR canónico (.ir.json)")
    ap.add_argument("--skip-isolated", action="store_true", help="no repetir los nodos sin aristas (los cubre CONN003)")
    args = ap.parse_args()
    try:
        ir = irlib.load_ir(args.ir)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"no se pudo leer {args.ir}: {exc}"}))
        return 2
    return validate(ir, args.ir, args.skip_isolated).emit()


if __name__ == "__main__":
    sys.exit(main())
