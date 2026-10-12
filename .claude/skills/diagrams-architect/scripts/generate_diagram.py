#!/usr/bin/env python3
"""IR canónico -> diagrams_src/<slug>.py. Emisor puro: no toma ninguna decisión.

    .venv/bin/python scripts/generate_diagram.py <slug>.ir.json [-o diagrams_src/<slug>.py]

Todo lo que hay que decidir (clase, variable, label con wrap, zona de color) ya viene
resuelto en el IR. Aquí solo se da formato, así que el mismo IR produce siempre el mismo
archivo, byte a byte: sin sets, sin timestamps, sin versiones y con el orden del IR.

Orden fijo del archivo:
  imports -> # === OUTPUT === -> # === STYLE === ... # === END STYLE === -> helpers
  -> with Diagram -> nodos sin cluster -> clusters (en profundidad) -> aristas
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

BASE_NODE = "diagrams.Node"
STYLE_BEGIN = "# === STYLE ==="
STYLE_END = "# === END STYLE ==="
INDENT = "    "

SIMPLE_STYLE_KEYS = (
    "FONT_FAMILY", "FONT_FAMILY_BOLD", "FONT_SIZE_TITLE", "FONT_SIZE_CLUSTER", "FONT_SIZE_NODE",
    "FONT_SIZE_EDGE", "FONT_COLOR", "DIRECTION", "NODESEP", "RANKSEP", "SPLINES", "PAD",
    "CLUSTER_MARGIN", "NODE_WIDTH", "LABEL_WRAP", "PENWIDTH_EDGE",
)


def py(value):
    """Literal de Python estable para str / int / bool."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


# --- Bloque STYLE -----------------------------------------------------------------


def collect_extensions(ir):
    """Promueve a constantes los atributos de estilo de `extensions`. Devuelve (consts, mapa)."""
    consts, promoted = [], {}
    subjects = (
        [("node", n["var"].upper(), n) for n in ir["nodes"]]
        + [("cluster", c["id"].upper(), c) for c in ir["clusters"]]
        + [("edge", e["id"].upper(), e) for e in ir["edges"]]
    )
    for kind, key, item in subjects:
        for attr in sorted(item.get("extensions") or {}):
            if attr in irlib.STYLE_ATTRS:
                name = f"EXT_{key}_{attr.upper()}"
                consts.append((name, item["extensions"][attr]))
                promoted[(kind, item["id"], attr)] = name
    return consts, promoted


def style_block(ir, ext_consts):
    st = irlib.resolve_style(ir)
    st["DIRECTION"] = ir["direction"]
    pal = st["PALETTE"]
    width = max(len(k) for k in SIMPLE_STYLE_KEYS)
    lines = [STYLE_BEGIN]
    for key in SIMPLE_STYLE_KEYS[:7]:
        lines.append(f"{key.ljust(width)} = {py(st[key])}")
    lines.append("PALETTE = {")
    lines.append(f'    "bg": {py(pal["bg"])},')
    lines.append('    "zones": [')
    for z in pal["zones"]:
        lines.append(f"        {py(z)},")
    lines.append("    ],")
    for k in ("accent", "border", "edge"):
        lines.append(f'    "{k}": {py(pal[k])},')
    lines.append("}")
    for key in SIMPLE_STYLE_KEYS[7:]:
        lines.append(f"{key.ljust(width)} = {py(st[key])}")
    lines += [
        "",
        "GRAPH_ATTR = {",
        '    "fontname": FONT_FAMILY_BOLD,', '    "fontsize": FONT_SIZE_TITLE,', '    "fontcolor": FONT_COLOR,',
        '    "bgcolor": PALETTE["bg"],', '    "nodesep": NODESEP,', '    "ranksep": RANKSEP,',
        '    "splines": SPLINES,', '    "pad": PAD,', '    "labelloc": "t",', "}",
        "NODE_ATTR = {",
        '    "fontname": FONT_FAMILY,', '    "fontsize": FONT_SIZE_NODE,', '    "fontcolor": FONT_COLOR,',
        '    "width": NODE_WIDTH,', "}",
        "EDGE_ATTR = {",
        '    "fontname": FONT_FAMILY,', '    "fontsize": FONT_SIZE_EDGE,', '    "fontcolor": FONT_COLOR,',
        '    "color": PALETTE["edge"],', '    "penwidth": PENWIDTH_EDGE,', "}",
        "CLUSTER_ATTR = {",
        '    "fontname": FONT_FAMILY_BOLD,', '    "fontsize": FONT_SIZE_CLUSTER,', '    "fontcolor": FONT_COLOR,',
        '    "pencolor": PALETTE["border"],', '    "style": "rounded,filled",', '    "labeljust": "l",',
        '    "margin": CLUSTER_MARGIN,', "}",
        "EDGE_STYLE_BY_TYPE = {",
        '    "network": {},', '    "event": {"style": "dashed"},', '    "data": {},', '    "invocation": {},',
        '    "dependency": {"style": "dotted"},', '    "authentication": {"color": PALETTE["accent"]},', "}",
        'EMPHASIS_EDGE = {"color": PALETTE["accent"], "penwidth": "2.0"}',
    ]
    if any(n["diagrams_class"] == BASE_NODE for n in ir["nodes"]):
        lines.append('LEGEND_NODE = {"shape": "point", "width": "0.1", "color": PALETTE["border"]}')
    if ext_consts:
        lines.append("")
        lines.append("# Atributos de Graphviz tomados de `extensions` en el IR")
        for name, value in ext_consts:
            lines.append(f"{name} = {py(value)}")
    lines.append(STYLE_END)
    return lines


# --- Imports -------------------------------------------------------------------------


def import_plan(ir):
    """Devuelve (líneas de import, {diagrams_class: nombre local}). Orden alfabético estable."""
    classes = sorted({n["diagrams_class"] for n in ir["nodes"] if n["diagrams_class"] != BASE_NODE})
    by_name = {}
    for dotted in classes:
        mod, _, name = dotted.rpartition(".")
        by_name.setdefault(name, []).append(mod)
    local, by_module = {}, {}
    for dotted in classes:
        mod, _, name = dotted.rpartition(".")
        alias = name
        if len(by_name[name]) > 1:
            alias = "".join(part.capitalize() for part in mod.split(".")[1:]) + name
        local[dotted] = alias
        by_module.setdefault(mod, []).append((name, alias))
    lines = []
    for mod in sorted(by_module):
        items = ", ".join(n if n == a else f"{n} as {a}" for n, a in sorted(by_module[mod]))
        lines.append(f"from {mod} import {items}")
    return lines, local


# --- Cuerpo --------------------------------------------------------------------------


def node_call(n, local, promoted):
    if n["diagrams_class"] == BASE_NODE:
        return f"{n['var']} = Node({py(n['label_wrapped'])}, nodeid={py(n['id'])}, **LEGEND_NODE)"
    args = [py(n["label_wrapped"]), f"nodeid={py(n['id'])}"]
    for attr in sorted(n.get("extensions") or {}):
        ref = promoted.get(("node", n["id"], attr))
        args.append(f"{attr}={ref}" if ref else f"{attr}={py(n['extensions'][attr])}")
    return f"{n['var']} = {local[n['diagrams_class']]}({', '.join(args)})"


def zone_call(c, promoted):
    extra = []
    for attr in sorted(c.get("extensions") or {}):
        ref = promoted.get(("cluster", c["id"], attr))
        extra.append(f"{attr}={ref}" if ref else f"{attr}={py(c['extensions'][attr])}")
    return f"zone({', '.join([str(c['zone'])] + extra)})"


def edge_statement(e, ir, var_of, promoted):
    args = []
    if e["type"] != "network":
        args.append(py(e["type"]))
    if e.get("emphasis"):
        args.append("emphasis=True")
    if e["arrow"] == "both":
        args += ["forward=True", "reverse=True"]
    if e.get("label"):
        ortho = irlib.resolve_style(ir)["SPLINES"] == "ortho"
        args.append(f"{'xlabel' if ortho else 'label'}={py(e['label'])}")
    for attr in sorted(e.get("extensions") or {}):
        ref = promoted.get(("edge", e["id"], attr))
        args.append(f"{attr}={ref}" if ref else f"{attr}={py(e['extensions'][attr])}")
    op = ">>" if e["arrow"] == "forward" else "-"
    return f"{var_of[e['source']]} {op} link({', '.join(args)}) {op} {var_of[e['target']]}"


def emit_cluster(ir, cid, depth, lines, local, promoted):
    pad = INDENT * depth
    c = next(x for x in ir["clusters"] if x["id"] == cid)
    lines.append(f"{pad}with Cluster({py(c['label'])}, graph_attr={zone_call(c, promoted)}):")
    body = 0
    for n in ir["nodes"]:
        if n.get("cluster") == cid:
            lines.append(f"{pad}{INDENT}{node_call(n, local, promoted)}")
            body += 1
    for child in ir["clusters"]:
        if child.get("parent") == cid:
            emit_cluster(ir, child["id"], depth + 1, lines, local, promoted)
            body += 1
    if not body:
        lines.append(f"{pad}{INDENT}pass")


def generate(ir):
    ext_consts, promoted = collect_extensions(ir)
    import_lines, local = import_plan(ir)
    var_of = {n["id"]: n["var"] for n in ir["nodes"]}
    core = ["Diagram"]
    if ir["clusters"]:
        core.append("Cluster")
    if ir["edges"]:
        core.append("Edge")
    if any(n["diagrams_class"] == BASE_NODE for n in ir["nodes"]):
        core.append("Node")
    core.sort()

    out = [
        '"""' + ir["title"].replace('"""', "'''").replace("\\", "/") + "",
        "",
        f"Generado por generate_diagram.py desde {ir['slug']}.ir.json. No editar a mano:",
        'cambia el .diag y vuelve a ejecutar `make diagram`."""',
        "",
        "import os",
        "from pathlib import Path",
        "",
        f"from diagrams import {', '.join(core)}",
        *import_lines,
        "",
        "# === OUTPUT ===",
        f'OUT = Path(__file__).resolve().parent.parent / "output" / {py(ir["slug"])}',
        'FMT = os.getenv("FORMAT", "png")',
        "",
        *style_block(ir, ext_consts),
        "",
        "",
        "def zone(index, **extra):",
        f'{INDENT}return {{**CLUSTER_ATTR, "bgcolor": PALETTE["zones"][index], **extra}}',
    ]
    if ir["edges"]:
        out += [
            "",
            "",
            'def link(kind="network", emphasis=False, **attrs):',
            f"{INDENT}style = {{**EDGE_ATTR, **EDGE_STYLE_BY_TYPE[kind]}}",
            f"{INDENT}if emphasis:",
            f"{INDENT * 2}style.update(EMPHASIS_EDGE)",
            f"{INDENT}return Edge(**style, **attrs)",
        ]
    out += [
        "",
        "",
        "with Diagram(",
        f"{INDENT}{py(ir['title'])},",
        f"{INDENT}filename=str(OUT),",
        f"{INDENT}outformat=FMT,",
        f"{INDENT}show=False,",
        f"{INDENT}direction=DIRECTION,",
        f"{INDENT}graph_attr=GRAPH_ATTR,",
        f"{INDENT}node_attr=NODE_ATTR,",
        "):",
    ]
    body = []
    for n in ir["nodes"]:
        if n.get("cluster") is None:
            body.append(f"{INDENT}{node_call(n, local, promoted)}")
    for c in ir["clusters"]:
        if c.get("parent") is None:
            emit_cluster(ir, c["id"], 1, body, local, promoted)
    if ir["edges"]:
        body.append("")
        body.append(f"{INDENT}# --- edges ---")
        for e in ir["edges"]:
            body.append(f"{INDENT}{edge_statement(e, ir, var_of, promoted)}")
    out += body or [f"{INDENT}pass"]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ir", help="IR canónico (.ir.json)")
    ap.add_argument("-o", "--output", help="archivo .py de salida (si no, stdout)")
    args = ap.parse_args()
    try:
        ir = irlib.load_ir(args.ir)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"no se pudo leer {args.ir}: {exc}"}))
        return 2
    errs = irlib.schema_errors(ir)
    if errs:
        print(json.dumps({"error": "el IR no cumple el esquema; ejecuta validate_ir.py", "first": errs[0]}))
        return 2
    src = generate(ir)
    if args.output:
        Path(args.output).write_text(src, encoding="utf-8")
    else:
        sys.stdout.write(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
