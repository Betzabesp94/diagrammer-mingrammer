#!/usr/bin/env python3
"""IR crudo -> IR canónico. Único lugar donde el IR se expande.

    .venv/bin/python scripts/resolve_ir.py <crudo.json> [-o <slug>.ir.json]

Hace, en este orden y siempre igual:
  1. resuelve icono/label -> `diagrams_class` real (vía introspect_diagrams), con `confidence`
  2. completa defaults (tipo de arista, roles, boundary)
  3. calcula `var` por nodo y `label_wrapped` (el generador no decide nada)
  4. asigna `zone` a cada cluster (distinto de sus hermanos y de su padre)
  5. inyecta la leyenda automática cuando hay aristas con trazo con significado (evento, dependencia, autenticación, énfasis)

El generador y los validadores leen solo el resultado; no recalculan nada.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

FALLBACK_CLASS = "diagrams.generic.blank.Blank"
LEGEND_NODE_CLASS = "diagrams.Node"
# Tipos de arista con trazo propio (ver EDGE_STYLE_BY_TYPE en el bloque STYLE) y su texto en la leyenda.
LEGEND_TEXT = {"event": "evento asíncrono", "dependency": "dependencia", "authentication": "autenticación"}
LEGEND_EMPHASIS_TEXT = "flujo destacado"
RESERVED_VARS = {"os", "zone", "path", "out", "fmt", "diagram", "cluster", "edge", "node"}
LABEL_STRIP_PREFIXES = ("amazon ", "aws ")


def _load_introspect():
    path = Path(__file__).resolve().parent / "introspect_diagrams.py"
    spec = importlib.util.spec_from_file_location("introspect_diagrams", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_icon(icon, default_provider, providers):
    """'aws-api-gateway' -> ('aws', 'api-gateway'); sin prefijo conocido usa el proveedor del diagrama."""
    head, _, rest = icon.partition("-")
    if rest and head in providers:
        return head, rest
    return default_provider, icon


def resolve_node_class(node, provider, providers, indexes, introspect):
    """Devuelve (diagrams_class, confidence, info) para un nodo."""
    def index_for(prov):
        if prov not in indexes:
            indexes[prov] = introspect.build_index([prov]) if prov in providers else {}
        return indexes[prov]

    icon = node.get("icon")
    if icon:
        prov, token = split_icon(icon, provider, providers)
        res = introspect.resolve_in(index_for(prov), token)
        source = "icon"
    else:
        label = node["label"]
        candidates = [label]
        low = label.lower()
        for pref in LABEL_STRIP_PREFIXES:
            if low.startswith(pref):
                candidates.append(label[len(pref):])
        res = {"status": "none", "token": label}
        for cand in candidates:
            res = introspect.resolve_in(index_for(provider), cand)
            if res["status"] != "none":
                break
        source = "label"
    info = {"node": node["id"], "source": source, "status": res["status"], "token": res["token"]}
    if node.get("line"):
        info["line"] = node["line"]
    if res["status"] == "none":
        return FALLBACK_CLASS, "generic", info
    if res["status"] == "ambiguous":
        info["alternatives"] = res["alternatives"]
    confidence = "exact" if source == "icon" and res["status"] == "exact" else "inferred"
    return res["diagrams_class"], confidence, info


def assign_zones(clusters):
    """Zona por cluster: distinta de sus hermanos ya asignados y de su padre (si se puede)."""
    nzones = len(irlib.DEFAULT_STYLE["PALETTE"]["zones"])
    zone_of, used_by_parent = {}, {}
    by_parent = {}
    for c in clusters:
        by_parent.setdefault(c["parent"], []).append(c)

    def visit(parent):
        for c in by_parent.get(parent, []):
            sibs = used_by_parent.setdefault(parent, set())
            avoid_parent = zone_of.get(parent) if parent is not None else None
            choice = next((z for z in range(nzones) if z not in sibs and z != avoid_parent), None)
            if choice is None:
                choice = next((z for z in range(nzones) if z not in sibs), None)
            if choice is None:
                choice = len(sibs) % nzones
            zone_of[c["id"]] = choice
            sibs.add(choice)
            visit(c["id"])

    visit(None)
    return zone_of


def build_legend(nodes, clusters, edges):
    """Inyecta la leyenda como parte del IR: un cluster con una arista de muestra por cada trazo con significado.

    Vive en el IR (no en el generador) para que el código siga siendo igual al IR. Cada muestra son dos
    puntos unidos por una arista real del mismo tipo, así la leyenda enseña el trazo y el color de verdad.
    """
    flow = [e for e in edges if e["role"] == "flow"]
    entries = []
    for e in flow:
        if e["type"] in LEGEND_TEXT and e["type"] not in [x["key"] for x in entries]:
            entries.append({"key": e["type"], "type": e["type"], "emphasis": False, "text": LEGEND_TEXT[e["type"]]})
    if any(e["emphasis"] for e in flow):
        entries.append({"key": "emphasis", "type": "network", "emphasis": True, "text": LEGEND_EMPHASIS_TEXT})
    if not entries:
        return {"auto": True, "entries": []}
    root_zones = {c["zone"] for c in clusters if c["parent"] is None}
    zone = next((z for z in range(len(irlib.DEFAULT_STYLE["PALETTE"]["zones"])) if z not in root_zones), 0)
    clusters.append({"id": "legend", "label": "Leyenda", "parent": None, "zone": zone, "boundary": True,
                     "role": "legend", "extensions": {}})
    for entry in entries:
        for side in ("a", "b"):
            nid = f"legend_{entry['key']}_{side}"
            nodes.append({"id": nid, "var": nid, "label": "", "label_wrapped": "", "diagrams_class": LEGEND_NODE_CLASS,
                          "confidence": "exact", "cluster": "legend", "standalone": True, "role": "legend",
                          "tags": {}, "extensions": {}})
        edges.append({"id": f"legend_{entry['key']}", "source": f"legend_{entry['key']}_a", "target": f"legend_{entry['key']}_b",
                      "arrow": "forward", "label": entry["text"], "type": entry["type"], "emphasis": entry["emphasis"],
                      "role": "legend", "extensions": {}})
    return {"auto": True, "entries": [{"key": e["key"], "text": e["text"]} for e in entries]}


def resolve(raw):
    introspect = _load_introspect()
    providers = set(introspect.iter_provider_names())
    style = irlib.resolve_style(raw)
    wrap = int(style["LABEL_WRAP"])
    provider = raw.get("provider", "aws")
    indexes, resolution = {}, []

    taken_vars = set()
    nodes = []
    for n in raw["nodes"]:
        cls, conf, info = resolve_node_class(n, provider, providers, indexes, introspect)
        var = irlib.slugify_var(n["id"], RESERVED_VARS, taken_vars)
        taken_vars.add(var)
        resolution.append(info)
        out = {"id": n["id"], "var": var, "label": n["label"], "label_wrapped": irlib.wrap_label(n["label"], wrap)}
        if n.get("service"):
            out["service"] = n["service"]
        if n.get("icon"):
            out["icon"] = n["icon"]
        out.update(
            diagrams_class=cls, confidence=conf, cluster=n.get("cluster"), standalone=bool(n.get("standalone")),
            role="service", tags=dict(n.get("tags") or {}), extensions=dict(n.get("extensions") or {}),
        )
        nodes.append(out)

    zones = assign_zones(raw["clusters"])
    clusters = []
    for c in raw["clusters"]:
        clusters.append({
            "id": c["id"], "label": c["label"], "parent": c.get("parent"), "zone": zones[c["id"]],
            "boundary": bool(c.get("boundary")), "extensions": dict(c.get("extensions") or {}),
        })

    edges = []
    for e in raw["edges"]:
        out = {"id": e["id"], "source": e["source"], "target": e["target"], "arrow": e["arrow"]}
        if e.get("label"):
            out["label"] = e["label"]
        out.update(type=e.get("type", "network"), emphasis=bool(e.get("emphasis")), role="flow",
                   extensions=dict(e.get("extensions") or {}))
        edges.append(out)

    legend = dict(raw.get("legend") or {"auto": True})
    if legend.get("auto", True):
        legend = build_legend(nodes, clusters, edges)

    ir = {
        "schema_version": irlib.SCHEMA_VERSION,
        "title": raw["title"], "slug": raw["slug"], "provider": provider, "direction": raw.get("direction", "LR"),
        "nodes": nodes, "clusters": clusters, "edges": edges,
        "constraints": dict(raw.get("constraints") or {}),
        "style_overrides": dict(raw.get("style_overrides") or {}),
        "legend": legend,
        "unsupported": list(raw.get("unsupported") or []),
        "meta": {**(raw.get("meta") or {}), "resolver_version": 1, "resolution": resolution},
    }
    return ir


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", help="IR crudo (salida de parse_dsl.py)")
    ap.add_argument("-o", "--output", help="escribe el IR canónico aquí en vez de stdout")
    args = ap.parse_args()
    try:
        raw = irlib.load_ir(args.raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"no se pudo leer {args.raw}: {exc}"}))
        return 2
    out = irlib.dump_json(resolve(raw))
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
