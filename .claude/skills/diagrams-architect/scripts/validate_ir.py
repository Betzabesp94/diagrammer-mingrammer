#!/usr/bin/env python3
"""Valida el IR canónico: ¿el grafo pretendido es válido y dibujable?

    .venv/bin/python scripts/validate_ir.py <ir.json> [--max-nodes 20] [--max-edges 25]

Corre sobre el IR, antes de generar nada. Familias (ids en references/validations.md):

  SCH   esquema, ids únicos, referencias, ciclos de clusters
  CONN  aristas a nodos inexistentes, duplicadas, self-loops, nodos huérfanos
  CLU   clusters vacíos, de un solo nodo, profundidad, labels duplicados, colores
  SIZ   tamaño del diagrama
  FLW   flujo y legibilidad: etiquetas, hubs, bidireccionales, notas y elementos a validar
  TXT   ancho estimado de labels, tamaño de fuente, etiquetas vagas
  STY   fuentes permitidas y contraste del STYLE efectivo
  RES   iconos genéricos, ambigüedades, passthrough y elementos no soportados

Salida: JSON con el contrato unificado. Exit 0 sin ERROR, 1 con ERROR, 2 si falla la herramienta.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

MAX_NODES = 20
MAX_EDGES = 25
MAX_CLUSTER_DEPTH = 3
MAX_ZONES = 5
MIN_FONT_PX = 13  # legibilidad al DPI por defecto de Graphviz (96)
DPI = 96
NODE_TEXT_MARGIN_PT = 8
LEGIBLE_NODES = 14        # SIZ003: tope para una vista legible (Miro o ejecutiva)
MAX_LABEL_WORDS = 3       # FLW002, sin contar conectores
CONNECTORS = {"y", "e", "o", "u", "de", "del", "a", "al", "en", "por", "para", "con", "sin", "la", "el", "los", "las"}
MAX_HUB_DEGREE = 7        # FLW003
MAX_BIDIRECTIONAL = 2     # FLW004
MAX_CALLOUTS = 2          # FLW005


def check_schema(ir, rep):
    """Devuelve True si la estructura es lo bastante sana para seguir con el resto."""
    errs = irlib.schema_errors(ir)
    for path, msg in errs:
        rep.add("SCH001", "ERROR", "schema", msg, where=path)
    return not errs


def check_references(ir, rep):
    nodes, clusters = ir["nodes"], ir["clusters"]
    seen = {}
    for kind, items in (("nodes", nodes), ("clusters", clusters)):
        for i, it in enumerate(items):
            if it["id"] in seen:
                rep.add("SCH004", "ERROR", "schema", f"id duplicado {it['id']!r} (ya existe en {seen[it['id']]})",
                        where=f"{kind}[{i}]", subject=it["id"])
            else:
                seen[it["id"]] = f"{kind}[{i}]"
            if kind == "clusters" and it["id"].startswith("cluster_"):
                rep.add("SCH005", "ERROR", "schema",
                        "el prefijo 'cluster_' está reservado (colisiona con los subgrafos de Graphviz)",
                        where=f"clusters[{i}]", subject=it["id"])
    seen_vars = {}
    for i, n in enumerate(nodes):
        if n["var"] in seen_vars:
            rep.add("SCH004", "ERROR", "schema", f"variable duplicada {n['var']!r}", where=f"nodes[{i}]", subject=n["id"])
        seen_vars[n["var"]] = i

    cluster_ids = {c["id"] for c in clusters}
    for i, n in enumerate(nodes):
        cl = n.get("cluster")
        if cl is not None and cl not in cluster_ids:
            rep.add("SCH006", "ERROR", "schema", f"el cluster {cl!r} no existe", where=f"nodes[{i}].cluster", subject=n["id"])
    for i, c in enumerate(clusters):
        p = c.get("parent")
        if p is not None and p not in cluster_ids:
            rep.add("SCH006", "ERROR", "schema", f"el cluster padre {p!r} no existe", where=f"clusters[{i}].parent", subject=c["id"])

    by_id = {c["id"]: c for c in clusters}
    for c in clusters:
        cur, hops = c["id"], 0
        while cur is not None and cur in by_id and hops <= len(clusters):
            cur = by_id[cur].get("parent")
            hops += 1
        if hops > len(clusters):
            rep.add("SCH007", "ERROR", "schema", "ciclo en el árbol de clusters", subject=c["id"])
            break

    node_ids = {n["id"] for n in nodes}
    for i, e in enumerate(ir["edges"]):
        for end in ("source", "target"):
            if e[end] not in node_ids:
                rep.add("CONN001", "ERROR", "connectivity", f"la arista {e['id']!r} apunta a un nodo inexistente: {e[end]!r}",
                        where=f"edges[{i}].{end}", subject=e["id"])


def check_connectivity(ir, rep):
    nodes_by_id = {n["id"]: n for n in ir["nodes"]}
    seen, touched = {}, set()
    for i, e in enumerate(ir["edges"]):
        if e["source"] not in nodes_by_id or e["target"] not in nodes_by_id:
            continue
        touched.update((e["source"], e["target"]))
        if e["source"] == e["target"]:
            rep.add("CONN004", "WARNING", "connectivity", f"self-loop en {e['source']!r}", where=f"edges[{i}]", subject=e["id"],
                    hint="Una arista de un nodo a sí mismo suele ser un error de modelado.")
        key = (e["source"], e["target"], e["arrow"], e.get("label"))
        if e["arrow"] != "forward":
            key = (frozenset((e["source"], e["target"])), e["arrow"], e.get("label"))
        if key in seen:
            rep.add("CONN002", "WARNING", "connectivity",
                    f"arista duplicada de {e['source']!r} a {e['target']!r} (igual a {seen[key]})", where=f"edges[{i}]", subject=e["id"])
        else:
            seen[key] = e["id"]
    for i, n in enumerate(ir["nodes"]):
        if n.get("role", "service") != "service" or n.get("standalone"):
            continue
        if n["id"] not in touched:
            rep.add("CONN003", "WARNING", "connectivity", f"el nodo {n['id']!r} no tiene aristas", where=f"nodes[{i}]", subject=n["id"],
                    hint="Conéctalo o márcalo como standalone si es intencional.")


def check_clusters(ir, rep):
    clusters = [c for c in ir["clusters"] if c.get("role", "service") == "service"]
    members = {}
    for n in ir["nodes"]:
        members.setdefault(n.get("cluster"), []).append(n["id"])
    children = irlib.cluster_children(ir)

    labels = {}
    for i, c in enumerate(ir["clusters"]):
        if c["label"] in labels:
            rep.add("CLU004", "ERROR", "clusters",
                    f"label de cluster duplicado {c['label']!r}: Graphviz fusiona los subgrafos con el mismo nombre",
                    where=f"clusters[{i}]", subject=c["id"], hint="Usa labels únicos en todo el diagrama.")
        labels[c["label"]] = c["id"]

    for c in clusters:
        direct = members.get(c["id"], [])
        subs = children.get(c["id"], [])
        if not direct and not subs:
            rep.add("CLU001", "WARNING", "clusters", f"el cluster {c['id']!r} está vacío", subject=c["id"])
        elif len(direct) == 1 and not subs and not c.get("boundary"):
            rep.add("CLU002", "WARNING", "clusters", f"el cluster {c['id']!r} tiene un solo nodo", subject=c["id"],
                    hint="Quita el cluster o márcalo boundary si es un límite real (VPC, subnet).")
        depth = irlib.cluster_depth(ir, c["id"])
        if depth > MAX_CLUSTER_DEPTH:
            rep.add("CLU003", "WARNING", "clusters", f"el cluster {c['id']!r} tiene profundidad {depth} (máximo {MAX_CLUSTER_DEPTH})",
                    subject=c["id"])

    zones = {c["id"]: c["zone"] for c in ir["clusters"]}
    by_parent = {}
    for c in clusters:
        by_parent.setdefault(c.get("parent"), []).append(c)
    for parent, sibs in sorted(by_parent.items(), key=lambda kv: (kv[0] is not None, kv[0] or "")):
        if len(sibs) > MAX_ZONES:
            rep.add("CLU006", "ERROR", "clusters",
                    f"{len(sibs)} clusters hermanos exceden la paleta de {MAX_ZONES} zonas",
                    where=f"parent={parent}", subject=str(parent), hint="Divide el diagrama en varios.")
            continue
        seen = {}
        for s in sibs:
            if s["zone"] in seen:
                rep.add("CLU005", "WARNING", "clusters",
                        f"los clusters hermanos {seen[s['zone']]!r} y {s['id']!r} comparten color", subject=s["id"])
            seen[s["zone"]] = s["id"]
        if parent is not None:
            for s in sibs:
                if s["zone"] == zones.get(parent):
                    rep.add("CLU005", "WARNING", "clusters",
                            f"el cluster {s['id']!r} tiene el mismo color que su padre {parent!r}", subject=s["id"])


def check_size(ir, rep, max_nodes, max_edges):
    n_nodes = len(irlib.flow_nodes(ir))
    n_edges = len(irlib.flow_edges(ir))
    if n_nodes > max_nodes:
        rep.add("SIZ001", "WARNING", "size", f"{n_nodes} nodos (umbral {max_nodes})", expected=max_nodes, found=n_nodes,
                hint="Considera dividir el diagrama por dominio o por flujo.")
    if n_edges > max_edges:
        rep.add("SIZ002", "WARNING", "size", f"{n_edges} aristas (umbral {max_edges})", expected=max_edges, found=n_edges,
                hint="Considera dividir el diagrama por dominio o por flujo.")


def is_note(n):
    return (n.get("extensions") or {}).get("shape") == "note"


def visible_edges(ir):
    """Aristas que se dibujan entre componentes: sin las invisibles ni las anclas de las notas."""
    notes = {n["id"] for n in ir["nodes"] if is_note(n)}
    return [e for e in irlib.flow_edges(ir)
            if "invis" not in str((e.get("extensions") or {}).get("style", ""))
            and e["source"] not in notes and e["target"] not in notes]


def label_words(label):
    """Palabras de una etiqueta, sin contar marcadores como '①' o '(3)' ni conectores como 'y' o 'de'."""
    return [w for w in label.split() if any(ch.isalpha() for ch in w) and w.lower().strip("(),.;:") not in CONNECTORS]


def check_flow(ir, rep):
    nodes = irlib.flow_nodes(ir)
    components = [n for n in nodes if not is_note(n)]
    edges = visible_edges(ir)
    connected = {end for e in edges for end in (e["source"], e["target"])}
    # La banda transversal (íconos sin flechas) no cuenta: solo lo que participa del flujo o se marcó standalone.
    in_view = [n for n in components if n["id"] in connected or n.get("standalone")]
    if len(in_view) > LEGIBLE_NODES:
        rep.add("SIZ003", "INFO", "size", f"{len(in_view)} componentes en el flujo (más de {LEGIBLE_NODES} cuesta leerlos en una vista)",
                expected=LEGIBLE_NODES, found=len(in_view),
                hint="Para Miro o una vista ejecutiva, agrupa o divide el diagrama.")
    labeled = [e for e in edges if (e.get("label") or "").strip()]
    main = [e for e in edges if e.get("emphasis")]
    if main:
        # El máximo de etiquetas lo define el flujo principal: solo sus pasos llevan texto.
        secondary = [e for e in labeled if not e.get("emphasis")]
        if secondary:
            rep.add("FLW001", "WARNING", "flow",
                    f"{len(secondary)} flechas fuera del flujo principal llevan etiqueta (el flujo principal tiene {len(main)} pasos)",
                    expected=len(main), found=len(labeled), subject=", ".join(e["id"] for e in secondary),
                    hint="Quita la etiqueta de las relaciones secundarias y explícalas aparte, o márcalas emphasis si son del flujo principal.")
    elif labeled:
        rep.add("FLW007", "INFO", "flow",
                f"no se marcó el flujo principal: no se pudo validar cuáles de las {len(labeled)} flechas con etiqueta deberían llevarla",
                found=len(labeled),
                hint="Marca los pasos del flujo principal con [emphasis: true]; solo esos llevan etiqueta.")
    for e in labeled:
        words = label_words(e["label"])
        if len(words) > MAX_LABEL_WORDS:
            rep.add("FLW002", "WARNING", "flow", f"la etiqueta {e['label']!r} tiene {len(words)} palabras (máximo {MAX_LABEL_WORDS})",
                    subject=e["id"], expected=MAX_LABEL_WORDS, found=len(words),
                    hint="Acórtala a un verbo o un protocolo; el detalle va en la explicación.")
    degree = {}
    for e in edges:
        for end in (e["source"], e["target"]):
            degree[end] = degree.get(end, 0) + 1
    for nid, deg in sorted(degree.items()):
        if deg > MAX_HUB_DEGREE:
            rep.add("FLW003", "WARNING", "flow", f"{nid!r} tiene {deg} conexiones (máximo {MAX_HUB_DEGREE})",
                    subject=nid, expected=MAX_HUB_DEGREE, found=deg,
                    hint="Acerca o agrupa sus vecinos, o divide el diagrama; no sumes más flechas al hub.")
    both = [e for e in edges if e.get("arrow") == "both"]
    if len(both) > MAX_BIDIRECTIONAL:
        rep.add("FLW004", "WARNING", "flow", f"{len(both)} flechas de ida y vuelta (máximo {MAX_BIDIRECTIONAL})",
                expected=MAX_BIDIRECTIONAL, found=len(both), subject=", ".join(e["id"] for e in both),
                hint="Usa una sola dirección: la respuesta de una llamada síncrona está implícita.")
    anchored = {end for e in irlib.flow_edges(ir) if "invis" not in str((e.get("extensions") or {}).get("style", ""))
                for end in (e["source"], e["target"])}
    callouts = [n["id"] for n in nodes if is_note(n) and n["id"] in anchored]
    if len(callouts) > MAX_CALLOUTS:
        rep.add("FLW005", "WARNING", "flow", f"{len(callouts)} notas junto a componentes (máximo {MAX_CALLOUTS})",
                expected=MAX_CALLOUTS, found=len(callouts), subject=", ".join(callouts),
                hint="Deja las notas que aportan; el resto va en la explicación.")
    dashed = {n["id"] for n in components if "dashed" in str((n.get("extensions") or {}).get("style", ""))}
    by_target = {}
    for e in edges:
        if e["source"] in dashed:
            by_target.setdefault(e["target"], []).append(e["source"])
    for target, sources in sorted(by_target.items()):
        if len(sources) > 1:
            rep.add("FLW006", "WARNING", "flow",
                    f"{len(sources)} elementos a validar llegan por separado a {target!r}: {', '.join(sorted(sources))}",
                    subject=target, found=len(sources),
                    hint="Agrúpalos en un cluster punteado con una sola flecha hacia el destino.")


def check_text(ir, style, rep):
    wrap = int(style["LABEL_WRAP"])
    fsize = float(style["FONT_SIZE_NODE"])
    avail = float(style["NODE_WIDTH"]) * 72 - NODE_TEXT_MARGIN_PT
    for i, n in enumerate(ir["nodes"]):
        if n.get("role", "service") != "service":
            continue
        width = irlib.estimate_text_width(n["label_wrapped"], fsize)
        if width > avail:
            rep.add("TXT001", "WARNING", "text",
                    f"el label de {n['id']!r} mide ~{width:.0f}pt y el nodo ofrece {avail:.0f}pt",
                    where=f"nodes[{i}].label_wrapped", subject=n["id"], expected=round(avail), found=round(width),
                    hint=f"Baja LABEL_WRAP (hoy {wrap}) o sube NODE_WIDTH en STYLE.")
    for key in ("FONT_SIZE_NODE", "FONT_SIZE_EDGE", "FONT_SIZE_CLUSTER", "FONT_SIZE_TITLE"):
        px = float(style[key]) * DPI / 72
        if px < MIN_FONT_PX:
            rep.add("TXT002", "WARNING", "text", f"{key}={style[key]}pt equivale a {px:.1f}px a {DPI} dpi (mínimo {MIN_FONT_PX}px)",
                    subject=key, expected=MIN_FONT_PX, found=round(px, 1))
    for i, e in enumerate(ir["edges"]):
        label = (e.get("label") or "").strip().lower()
        if label in irlib.VAGUE_EDGE_LABELS:
            rep.add("TXT003", "WARNING", "text", f"la etiqueta {e['label']!r} no dice nada", where=f"edges[{i}].label", subject=e["id"],
                    hint="Usa un verbo o un protocolo: 'HTTPS', 'publica evento', 'lee'.")


def check_style(style, rep):
    for key in ("FONT_FAMILY", "FONT_FAMILY_BOLD"):
        name = style[key]
        if name not in irlib.ALLOWED_FONTS or any(b in name.lower() for b in irlib.BLOCKED_FONTS):
            rep.add("STY020", "ERROR", "style", f"{key}={name!r} no está en la lista permitida {list(irlib.ALLOWED_FONTS)}", subject=key)
    pal = style["PALETTE"]
    if len(pal["zones"]) > MAX_ZONES:
        rep.add("STY022", "ERROR", "style", f"la paleta tiene {len(pal['zones'])} colores de zona (máximo {MAX_ZONES})", subject="PALETTE.zones")
    for key, value in [("FONT_COLOR", style["FONT_COLOR"]), ("accent", pal["accent"])] + [
        (f"zones[{i}]", z) for i, z in enumerate(pal["zones"])
    ] + [("bg", pal["bg"])]:
        if not irlib.is_hex_color(value):
            rep.add("STY023", "ERROR", "style", f"{key}={value!r} no es un color #RRGGBB", subject=key)
            return
    backgrounds = [("bg", pal["bg"])] + [(f"zones[{i}]", z) for i, z in enumerate(pal["zones"])]
    for name, bg in backgrounds:
        ratio = irlib.contrast_ratio(style["FONT_COLOR"], bg)
        if ratio < 4.5:
            rep.add("STY021", "ERROR", "style", f"contraste {ratio:.2f}:1 entre FONT_COLOR y {name} (mínimo 4.5:1)",
                    subject=name, expected=4.5, found=round(ratio, 2))


def check_resolution(ir, rep):
    """Estado de cada nodo tras resolver su clase (lo deja resolve_ir en meta.resolution)."""
    for info in ir.get("meta", {}).get("resolution", []):
        nid, status = info["node"], info["status"]
        if status == "none":
            rep.add("RES003", "WARNING", "resolution",
                    f"{nid!r}: no hay clase oficial para {info['token']!r}; se usa un icono genérico",
                    subject=nid, hint="Indica icon: <proveedor>-<servicio> o revisa el nombre con introspect_diagrams.py search.")
        elif status == "ambiguous":
            rep.add("RES002", "INFO", "resolution",
                    f"{nid!r}: {info['token']!r} existe en varios módulos; se eligió uno",
                    subject=nid, found=info.get("alternatives"))
        elif info["source"] == "label":
            rep.add("RES004", "INFO", "resolution", f"{nid!r}: icono inferido a partir del label", subject=nid)


def check_unsupported(ir, rep):
    for i, u in enumerate(ir.get("unsupported", [])):
        rep.add("RES010", u.get("severity", "INFO"), "resolution", f"no se pudo dibujar: {u['feature']}",
                where=f"unsupported[{i}]", subject=u["where"], hint=u.get("detail", ""))
    for kind in ("nodes", "edges", "clusters"):
        for i, it in enumerate(ir.get(kind, [])):
            if it.get("extensions"):
                rep.add("RES011", "INFO", "resolution",
                        f"passthrough a Graphviz en {it['id']!r}: {sorted(it['extensions'])}", where=f"{kind}[{i}]", subject=it["id"])


def validate(ir, ir_path="", max_nodes=MAX_NODES, max_edges=MAX_EDGES):
    rep = irlib.Report("validate_ir", target=ir_path, ir=ir_path)
    if not check_schema(ir, rep):
        return rep
    check_references(ir, rep)
    structure_ok = not any(f["severity"] == "ERROR" for f in rep.findings)
    if not structure_ok:
        return rep
    style = irlib.resolve_style(ir)
    check_connectivity(ir, rep)
    check_clusters(ir, rep)
    check_size(ir, rep, max_nodes, max_edges)
    check_flow(ir, rep)
    check_text(ir, style, rep)
    check_style(style, rep)
    check_resolution(ir, rep)
    check_unsupported(ir, rep)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir", help="ruta al IR canónico (.ir.json)")
    ap.add_argument("--max-nodes", type=int, default=MAX_NODES)
    ap.add_argument("--max-edges", type=int, default=MAX_EDGES)
    args = ap.parse_args()
    try:
        ir = irlib.load_ir(args.ir)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"no se pudo leer {args.ir}: {exc}"}))
        return 2
    return validate(ir, args.ir, args.max_nodes, args.max_edges).emit()


if __name__ == "__main__":
    sys.exit(main())
