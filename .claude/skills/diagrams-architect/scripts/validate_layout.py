#!/usr/bin/env python3
"""Valida el layout ya dibujado: ¿el diagrama se lee? Mide con la geometría real de Graphviz.

    .venv/bin/python scripts/validate_layout.py diagrams_src/<slug>.py [--ir <slug>.ir.json] [--max-crossings 4]

Ejecuta el .py con FORMAT=dot (deja output/<slug>.dot ya con posiciones), corre `dot -Tjson`
sobre él y revisa la geometría. Como el generador fija `nodeid=` (el id del IR), cada objeto
del JSON se asocia a su nodo por identidad, sin heurísticas.

  LAY001 solapamiento nodo-nodo (incluye el texto del label)   LAY002 etiqueta de arista sobre un nodo
  LAY003 label más ancho que su nodo (medido, no estimado)     LAY004 membresía de cluster distinta del IR
  LAY005 nodo fuera del borde de su cluster                    LAY006 cruces de aristas sobre el umbral
  LAY007 fuente ilegible al DPI de salida                      LAY008 lienzo demasiado grande para leerse
  LAY010 ortho con etiquetas (aviso de dot)
  LAY000 sin Graphviz: layout no verificado (INFO, nunca falla)  LAY100 resumen de métricas

Nunca instala Graphviz. Exit 0 sin ERROR, 1 con ERROR, 2 si falla la herramienta.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

MAX_CROSSINGS = 4
MAX_CANVAS_PT = 3000  # por lado; más allá, al reducirlo para verlo el texto deja de leerse
MIN_FONT_PX = 13
DEFAULT_DPI = 96
EPS = 1.0  # puntos de tolerancia geométrica
TEXT_MARGIN_PT = 8
BENIGN_WARNINGS = ("No loadimage plugin",)


def to_pt(pair):
    x, y = (float(v) for v in pair.split(","))
    return x, y


def rect_overlap(a, b, eps=EPS):
    """Rectángulos (x0, y0, x1, y1) que se pisan en más de `eps` por eje."""
    return min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps


def text_rects(ops):
    """Cajas de los textos de una lista de operaciones xdot (F fija el tamaño, T dibuja)."""
    size, rects, widest, fonts = 12.0, [], 0.0, []
    for op in ops or []:
        kind = op.get("op")
        if kind == "F":
            size = float(op["size"])
            fonts.append(size)
        elif kind == "T":
            x, y = op["pt"]
            w = float(op["width"])
            left = x - w / 2 if op.get("align") == "c" else x if op.get("align") == "l" else x - w
            rects.append((left, y - 0.25 * size, left + w, y + 0.8 * size))
            widest = max(widest, w)
    return rects, widest, fonts


def segments_cross(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


def edge_polyline(edge):
    pts = []
    for op in edge.get("_draw_", []):
        if op.get("op") == "b":
            pts.extend(tuple(p) for p in op["points"])
    return pts


def count_crossings(edges, names):
    """Pares de aristas (sin extremo común) cuya polilínea de control se cruza. Es una cota aproximada."""
    polys = [(names[e["tail"]], names[e["head"]], edge_polyline(e)) for e in edges]
    total = 0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            ti, hi, pi = polys[i]
            tj, hj, pj = polys[j]
            if {ti, hi} & {tj, hj}:
                continue
            if any(segments_cross(pi[a], pi[a + 1], pj[b], pj[b + 1])
                   for a in range(len(pi) - 1) for b in range(len(pj) - 1)):
                total += 1
    return total


def run_layout(py_path, slug):
    """Ejecuta el .py con FORMAT=dot y devuelve la ruta del .dot (o un mensaje de error)."""
    env = dict(os.environ, FORMAT="dot")
    res = subprocess.run([sys.executable, str(py_path)], capture_output=True, text=True, env=env, timeout=300)
    dot_file = Path(py_path).resolve().parent.parent / "output" / f"{slug}.dot"
    if res.returncode != 0 or not dot_file.exists():
        return None, (res.stderr or res.stdout).strip()[-600:]
    return dot_file, ""


def analyze(dot_file, ir, max_crossings, rep):
    res = subprocess.run(["dot", "-Tjson", str(dot_file)], capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        rep.add("LAY099", "ERROR", "layout", f"dot no pudo procesar el layout: {res.stderr.strip()[:300]}")
        return
    graph = json.loads(res.stdout)
    warnings = [l for l in res.stderr.splitlines() if l.strip() and not any(b in l for b in BENIGN_WARNINGS)]
    if any("Orthogonal edges do not currently handle edge labels" in w for w in warnings):
        rep.add("LAY010", "WARNING", "layout", "splines=ortho con etiquetas en las aristas: Graphviz las coloca mal",
                hint="Usa SPLINES='spline' o xlabel.")
    for w in sorted({w for w in warnings if "Orthogonal edges" not in w}):
        rep.add("LAY099", "INFO", "layout", f"aviso de dot: {w.strip()}")

    objects = graph.get("objects", [])
    names = {o["_gvid"]: o["name"] for o in objects}
    clusters = [o for o in objects if o["name"].startswith("cluster_")]
    nodes = [o for o in objects if not o["name"].startswith("cluster_")]
    ir_nodes = {n["id"]: n for n in ir["nodes"]} if ir else {}

    boxes, fonts = {}, []
    for n in nodes:
        x, y = to_pt(n["pos"])
        w, h = float(n["width"]) * 72, float(n["height"]) * 72
        body = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        rects, widest, nf = text_rects(n.get("_ldraw_"))
        fonts += nf
        visual = body
        for r in rects:
            visual = (min(visual[0], r[0]), min(visual[1], r[1]), max(visual[2], r[2]), max(visual[3], r[3]))
        boxes[n["name"]] = {"body": body, "visual": visual}
        if rects and widest > w - TEXT_MARGIN_PT:
            rep.add("LAY003", "WARNING", "layout", f"el label de {n['name']!r} mide {widest:.0f}pt y el nodo ofrece {w - TEXT_MARGIN_PT:.0f}pt",
                    subject=n["name"], expected=round(w - TEXT_MARGIN_PT), found=round(widest),
                    hint="Baja LABEL_WRAP o sube NODE_WIDTH en STYLE (NODE_WIDTH también agranda el icono).")

    ordered = sorted(boxes)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if rect_overlap(boxes[a]["visual"], boxes[b]["visual"]):
                rep.add("LAY001", "WARNING", "layout", f"{a!r} y {b!r} se solapan", subject=f"{a},{b}")

    edges = graph.get("edges", [])
    for e in edges:
        for r in text_rects(e.get("_ldraw_"))[0]:
            for name in ordered:
                if rect_overlap(r, boxes[name]["body"]):
                    rep.add("LAY002", "WARNING", "layout",
                            f"la etiqueta {e.get('label', '')!r} de {names[e['tail']]}->{names[e['head']]} cae sobre {name!r}",
                            subject=f"{names[e['tail']]}->{names[e['head']]}")

    members = {}
    for c in clusters:
        label = c["name"][len("cluster_"):]
        in_cluster = {names[i] for i in c.get("nodes", [])}
        members[label] = in_cluster
        llx, lly, urx, ury = (float(v) for v in c["bb"].split(","))
        for name in sorted(in_cluster):
            bx = boxes[name]["body"]
            if bx[0] < llx - EPS or bx[1] < lly - EPS or bx[2] > urx + EPS or bx[3] > ury + EPS:
                rep.add("LAY005", "WARNING", "layout", f"el nodo {name!r} sobresale del cluster {label!r}", subject=name)
    if ir:
        label_of = {c["id"]: c["label"] for c in ir["clusters"]}
        parent_of = {c["id"]: c.get("parent") for c in ir["clusters"]}
        expected = {label: set() for label in label_of.values()}
        for n in ir["nodes"]:
            cid = n.get("cluster")
            while cid is not None:
                expected[label_of[cid]].add(n["id"])
                cid = parent_of[cid]
        for label in sorted(set(expected) | set(members)):
            if expected.get(label, set()) != members.get(label, set()):
                rep.add("LAY004", "ERROR", "layout", f"la membresía del cluster {label!r} no coincide con el IR",
                        subject=label, expected=sorted(expected.get(label, [])), found=sorted(members.get(label, [])))

    crossings = count_crossings(edges, names)
    if crossings > max_crossings:
        rep.add("LAY006", "WARNING", "layout", f"~{crossings} cruces de aristas (umbral {max_crossings})",
                expected=max_crossings, found=crossings, hint="Cálculo aproximado. Reordena los grupos o divide el diagrama.")
    for e in edges:
        fonts += text_rects(e.get("_ldraw_"))[2]
    fonts += text_rects(graph.get("_ldraw_"))[2]
    dpi = float(graph.get("dpi") or DEFAULT_DPI)
    if fonts and min(fonts) * dpi / 72 < MIN_FONT_PX:
        rep.add("LAY007", "WARNING", "layout", f"fuente mínima {min(fonts):g}pt = {min(fonts) * dpi / 72:.1f}px a {dpi:g} dpi (mínimo {MIN_FONT_PX}px)",
                expected=MIN_FONT_PX, found=round(min(fonts) * dpi / 72, 1))

    llx, lly, urx, ury = (float(v) for v in graph["bb"].split(","))
    if max(urx - llx, ury - lly) > MAX_CANVAS_PT:
        rep.add("LAY008", "WARNING", "layout", f"lienzo de {urx - llx:.0f}x{ury - lly:.0f}pt (máximo {MAX_CANVAS_PT}pt por lado): al reducirlo no se lee",
                expected=MAX_CANVAS_PT, found=round(max(urx - llx, ury - lly)), hint="Divide el diagrama o cambia DIRECTION a TB.")
    rep.add("LAY100", "INFO", "layout", f"lienzo de {urx - llx:.0f}x{ury - lly:.0f}pt, {len(nodes)} nodos, {len(edges)} aristas, ~{crossings} cruces",
            found={"width_pt": round(urx - llx), "height_pt": round(ury - lly), "crossings": crossings})


def validate(py_path, ir=None, max_crossings=MAX_CROSSINGS):
    py_path = Path(py_path)
    rep = irlib.Report("validate_layout", target=str(py_path))
    if not shutil.which("dot"):
        rep.add("LAY000", "INFO", "layout", "falta Graphviz (dot): el layout no se verificó",
                hint="Instálalo (brew install graphviz) y repite; este script nunca instala nada.")
        return rep
    slug = ir["slug"] if ir else py_path.stem
    dot_file, err = run_layout(py_path, slug)
    if dot_file is None:
        rep.add("LAY099", "ERROR", "layout", f"no se pudo generar el layout con FORMAT=dot: {err}")
        return rep
    analyze(dot_file, ir, max_crossings, rep)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="ruta al .py generado")
    ap.add_argument("--ir", help="IR canónico (por defecto <slug>.ir.json junto al archivo, si existe)")
    ap.add_argument("--max-crossings", type=int, default=MAX_CROSSINGS)
    args = ap.parse_args()
    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"no existe {path}"}))
        return 2
    ir = None
    ir_path = Path(args.ir) if args.ir else path.with_suffix(".ir.json")
    if ir_path.exists():
        ir = irlib.load_ir(ir_path)
    return validate(path, ir, args.max_crossings).emit()


if __name__ == "__main__":
    sys.exit(main())
