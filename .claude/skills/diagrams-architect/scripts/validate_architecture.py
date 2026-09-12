#!/usr/bin/env python3
"""Corre un set CHICO y determinístico de reglas de Solutions Architect sobre el
modelo intermedio (IR) de una arquitectura, ANTES de traducirla a `diagrams`.

No es un motor de Well-Architected: son cinco chequeos ilustrativos (networking,
seguridad, disponibilidad, observabilidad, complejidad) pensados para atrapar lo
obvio, no para auditar exhaustivamente. Ver references/architecture_rules.md.

Uso:
    .venv/bin/python scripts/validate_architecture.py modelo_ir.json

El IR es el JSON que arma la skill internamente (ver references/ir_schema.md):
{
  "nodes": [{"id": "...", "service": "...", "diagrams_class": "...", "confidence": "exact|inferred|generic|custom|ambiguous", "tags": {...}}],
  "clusters": [{"id": "...", "contains": ["node_id", ...]}],
  "edges": [{"source": "...", "target": "...", "type": "network|event|data|invocation|dependency|authentication"}],
  "constraints": {"production": false, "internet_entrypoint": "node_id", "notes": "..."}
}

Salida: JSON con una lista `findings`, cada uno con severity (ERROR|WARNING|INFO),
category, y message. Exit code 0 siempre (estas reglas nunca son bloqueantes por sí
solas — ver la regla de "un WARNING nunca dispara una corrección silenciosa" en
SKILL.md); es la skill la que decide qué hacer con cada finding, y SIEMPRE debe
reportarlos tal cual, sin resolverlos por su cuenta.
"""

import argparse
import json
import sys
from pathlib import Path

DB_KEYWORDS = [
    "rds", "dynamodb", "aurora", "redshift", "elasticache", "documentdb", "neptune",
    "postgres", "mysql", "mongodb", "mariadb", "cosmosdb", "cloudsql", "bigtable",
    "firestore", "memorystore", "spanner", "sqlserver", "cassandra", "database",
]
ENTRYPOINT_KEYWORDS = [
    "elb", "alb", "nlb", "cloudfront", "apigateway", "route53", "loadbalancing",
    "loadbalancer", "waf", "gateway", "frontdoor", "cdn", "ingress",
]
MONITORING_KEYWORDS = [
    "cloudwatch", "cloudtrail", "xray", "prometheus", "grafana", "datadog",
    "newrelic", "stackdriver", "monitoring", "logging", "opsview", "splunk",
]
PRODUCTION_KEYWORDS = ["produccion", "producción", "production", "alta disponibilidad", "high availability", " ha ", "prod"]

DEFAULT_MAX_NODES = 25


def _lower_class(node):
    return (node.get("diagrams_class") or node.get("service") or "").lower()


def _matches_any(text, keywords):
    return any(k in text for k in keywords)


def check_networking(ir):
    findings = []
    edges = ir.get("edges", [])
    node_ids = {n["id"] for n in ir.get("nodes", [])}
    entrypoint = ir.get("constraints", {}).get("internet_entrypoint")
    incoming = {nid: 0 for nid in node_ids}
    for e in edges:
        if e.get("target") in incoming:
            incoming[e["target"]] += 1
    orphan_roots = [
        nid for nid, count in incoming.items()
        if count == 0 and nid != entrypoint and any(e.get("source") == nid for e in edges)
    ]
    if entrypoint and len(orphan_roots) >= 1:
        findings.append({
            "severity": "WARNING",
            "category": "networking",
            "message": (
                f"Los nodos {orphan_roots} no reciben ninguna conexión entrante y no son el "
                f"entry point declarado ({entrypoint}). Revisar si deberían quedar alcanzables "
                "solo a través de un load balancer / API gateway / CDN, o si falta modelar cómo "
                "reciben tráfico."
            ),
        })
    return findings


def check_security(ir):
    findings = []
    entrypoint = ir.get("constraints", {}).get("internet_entrypoint")
    if not entrypoint:
        return findings
    nodes_by_id = {n["id"]: n for n in ir.get("nodes", [])}
    for e in ir.get("edges", []):
        if e.get("source") == entrypoint:
            target = nodes_by_id.get(e.get("target"))
            if target and _matches_any(_lower_class(target), DB_KEYWORDS):
                findings.append({
                    "severity": "WARNING",
                    "category": "security",
                    "message": (
                        f"El entry point público ({entrypoint}) se conecta directo a "
                        f"'{target.get('id')}' ({target.get('service')}), que parece una base de "
                        "datos. Revisar si falta una capa de aplicación/API entre el tráfico "
                        "público y el dato."
                    ),
                })
    return findings


def check_availability(ir):
    findings = []
    constraints = ir.get("constraints", {})
    notes = " ".join(str(v) for v in constraints.values() if isinstance(v, str)).lower()
    is_production = bool(constraints.get("production")) or _matches_any(notes, PRODUCTION_KEYWORDS)
    if not is_production:
        return findings
    for node in ir.get("nodes", []):
        if _matches_any(_lower_class(node), DB_KEYWORDS):
            tags = node.get("tags", {}) or {}
            if not tags.get("multi_az") and not tags.get("multi_region"):
                findings.append({
                    "severity": "WARNING",
                    "category": "availability",
                    "message": (
                        f"'{node.get('id')}' ({node.get('service')}) parece de base de datos y la "
                        "arquitectura se describe como productiva/HA, pero no está marcada como "
                        "multi-AZ. Confirmar si es Single-AZ intencional o si falta modelarlo."
                    ),
                })
    return findings


def check_observability(ir):
    findings = []
    constraints = ir.get("constraints", {})
    notes = " ".join(str(v) for v in constraints.values() if isinstance(v, str)).lower()
    is_production = bool(constraints.get("production")) or _matches_any(notes, PRODUCTION_KEYWORDS)
    if not is_production:
        return findings
    has_monitoring = any(_matches_any(_lower_class(n), MONITORING_KEYWORDS) for n in ir.get("nodes", []))
    if not has_monitoring:
        findings.append({
            "severity": "INFO",
            "category": "observability",
            "message": (
                "La arquitectura se describe como productiva pero no se ve ningún componente de "
                "logging/monitoreo (CloudWatch, Prometheus, Datadog...). Es solo una observación: "
                "no agregar el componente de oficio, reportarlo como recomendación aparte."
            ),
        })
    return findings


def check_complexity(ir, max_nodes):
    findings = []
    n = len(ir.get("nodes", []))
    if n > max_nodes:
        findings.append({
            "severity": "INFO",
            "category": "complexity",
            "message": (
                f"El diagrama tiene {n} nodos (> {max_nodes}), lo que puede dificultar la lectura. "
                "Sugerir dividirlo en varios diagramas por dominio/capa; no dividirlo automáticamente."
            ),
        })
    return findings


def run_all(ir, max_nodes=DEFAULT_MAX_NODES):
    findings = []
    findings += check_networking(ir)
    findings += check_security(ir)
    findings += check_availability(ir)
    findings += check_observability(ir)
    findings += check_complexity(ir, max_nodes)
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir_path", help="ruta al JSON del modelo intermedio")
    ap.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    args = ap.parse_args()

    ir_path = Path(args.ir_path)
    if not ir_path.exists():
        print(json.dumps({"error": f"no existe {ir_path}"}))
        sys.exit(1)

    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    findings = run_all(ir, args.max_nodes)
    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for f in findings:
        counts[f["severity"]] += 1

    print(json.dumps({"findings": findings, "counts": counts}, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
