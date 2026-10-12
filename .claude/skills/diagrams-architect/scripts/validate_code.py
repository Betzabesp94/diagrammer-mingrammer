#!/usr/bin/env python3
"""Valida un diagrams_src/<slug>.py SIN renderizarlo: ¿el código es exactamente el IR?

    .venv/bin/python scripts/validate_code.py diagrams_src/<slug>.py [--ir <slug>.ir.json] [--strict|--lenient]

Dos modos:
  strict   Para código generado por generate_diagram.py (se detecta por el encabezado). La forma
           del archivo es canónica, así que se extrae por AST y se compara con el IR por igualdad:
           nodos, clases, labels, clusters, aristas, direcciones y etiquetas. Además exige que no
           haya literales de color, fuente o tamaño fuera del bloque STYLE. Si falta --ir busca
           <slug>.ir.json junto al archivo.
  lenient  Para archivos escritos a mano. Valida sintaxis, imports, contexto, convenciones y
           tipografía como hasta ahora; la familia STY y la fidelidad exacta bajan a INFO.

Familias de findings (catálogo en references/validations.md):
  CODE  sintaxis, imports, nodos fuera de `with Diagram`, convenciones del repo, fuentes bloqueadas
  FID   fidelidad del código frente al IR (solo strict)
  STY   estilo fuera de STYLE, clusters sin zona, splines=ortho con label=

Salida: JSON con el contrato unificado. Exit 0 sin ERROR, 1 con ERROR, 2 si falla la herramienta.
"""

import argparse
import ast
import importlib.util
import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import irlib  # noqa: E402

spec = importlib.util.spec_from_file_location("introspect_diagrams", SCRIPT_DIR / "introspect_diagrams.py")
introspect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(introspect)

GENERATED_MARK = "Generado por generate_diagram.py"
STYLE_BEGIN = "# === STYLE ==="
STYLE_END = "# === END STYLE ==="
CORE_NAMES = {"Diagram", "Cluster", "Group", "Edge", "Node"}
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# Patrón heredado (archivos escritos a mano con tarjetas): sigue contándose en modo lenient.
NODE_FACTORY_NAMES = {"service_card", "internal_card"}
EDGE_FACTORY_NAME = "flow"
ANNOTATION_FACTORY_NAMES = {"sticky_note"}
CHAIN_OPS = (ast.RShift, ast.LShift, ast.Sub)


# --- Utilidades de AST ------------------------------------------------------------------


def build_parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def const_str(expr):
    return expr.value if isinstance(expr, ast.Constant) and isinstance(expr.value, str) else None


def kw_map(call):
    return {k.arg: k.value for k in call.keywords if k.arg}


def root_name(expr):
    while isinstance(expr, (ast.Subscript, ast.Attribute)):
        expr = expr.value
    return expr.id if isinstance(expr, ast.Name) else None


def is_call_to(expr, name):
    return isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == name


# --- Dimensiones heredadas (CODE) --------------------------------------------------------


def check_syntax(path, rep):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(str(path), cfile=str(Path(tmp) / "out.pyc"), doraise=True)
        return True
    except py_compile.PyCompileError as exc:
        rep.add("CODE001", "ERROR", "code", f"el archivo no compila: {exc.exc_value}", where=str(path))
        return False


def check_imports(tree, rep):
    """Devuelve (name_to_info, core_aliases) y reporta imports que no existen."""
    name_to_info, core_aliases = {}, {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.module):
            continue
        if node.module == "diagrams":
            for alias in node.names:
                if alias.name in CORE_NAMES:
                    core_aliases[alias.asname or alias.name] = alias.name
                else:
                    rep.add("CODE002", "ERROR", "code", f"'{alias.name}' no es un símbolo público de diagrams",
                            where=f"línea {node.lineno}", subject=alias.name)
        elif node.module.startswith("diagrams."):
            dotted_module = node.module[len("diagrams."):]
            for alias in node.names:
                check = introspect.check_path(f"{dotted_module}.{alias.name}")
                if check["exists"]:
                    name_to_info[alias.asname or alias.name] = {"module": node.module, "class": alias.name}
                else:
                    rep.add("CODE002", "ERROR", "code", f"el import no existe: from {node.module} import {alias.name}",
                            where=f"línea {node.lineno}", subject=alias.name, hint=check.get("error", ""))
    return name_to_info, core_aliases


def alias_of(core_aliases, *origs):
    return next((b for b, o in core_aliases.items() if o in origs), None)


def find_diagram_with(tree, diagram_name):
    if diagram_name is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                if is_call_to(item.context_expr, diagram_name):
                    return node
    return None


def check_diagram_context(tree, name_to_info, core_aliases, diagram_with, parents, rep):
    tracked = set(name_to_info) | NODE_FACTORY_NAMES | {b for b, o in core_aliases.items() if o == "Node"} | {EDGE_FACTORY_NAME} | ANNOTATION_FACTORY_NAMES
    if diagram_with is None:
        rep.add("CODE006", "ERROR", "code", "no hay ningún `with Diagram(...):` en el archivo")
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in tracked:
            cur, inside = node, False
            while cur in parents:
                cur = parents[cur]
                if cur is diagram_with:
                    inside = True
                    break
            if not inside:
                rep.add("CODE003", "ERROR", "code", f"{node.func.id}(...) se instancia fuera del `with Diagram(...)`",
                        where=f"línea {node.lineno}", subject=node.func.id)


def check_conventions(source, diagram_call, rep):
    checks = {
        "OUT": bool(re.search(
            r'OUT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent\.parent\s*/\s*["\']output["\']\s*/\s*["\'][^"\']+["\']', source)),
        "FMT": bool(re.search(r'FMT\s*=\s*os\.getenv\(\s*["\']FORMAT["\']\s*,\s*["\']png["\']\s*\)', source)),
        "show=False": False, "filename=str(OUT)": False, "outformat=FMT": False,
    }
    if diagram_call is not None:
        for kw in diagram_call.keywords:
            if kw.arg == "show" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                checks["show=False"] = True
            if kw.arg == "filename" and "OUT" in ast.dump(kw.value):
                checks["filename=str(OUT)"] = True
            if kw.arg == "outformat" and "FMT" in ast.dump(kw.value):
                checks["outformat=FMT"] = True
    for name, ok in checks.items():
        if not ok:
            rep.add("CODE004", "ERROR", "code", f"incumple la convención del repo: {name}", subject=name,
                    hint="Ver references/repo_conventions.md.")


def _string_vars(tree):
    values = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and const_str(node.value) is not None):
            values[node.targets[0].id] = node.value.value
    return values


def _resolve_str(expr, var_values):
    s = const_str(expr)
    if s is not None:
        return s
    return var_values.get(expr.id) if isinstance(expr, ast.Name) else None


def check_typography(tree, source, rep):
    """Ninguna fuente hand-drawn (regla dura del repo), ni en fontname ni en FACE="..."."""
    var_values = _string_vars(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if const_str(key) == "fontname":
                    r = _resolve_str(value, var_values)
                    if r:
                        found.append(r)
        elif isinstance(node, ast.keyword) and node.arg == "fontname":
            r = _resolve_str(node.value, var_values)
            if r:
                found.append(r)
    for m in re.finditer(r'FACE=\\?["\']([^"\'>]*)["\']', source):
        v = m.group(1)
        vm = re.fullmatch(r"\{(\w+)\}", v)
        found.append(var_values.get(vm.group(1), "") if vm else v)
    for value in sorted({f for f in found if f}):
        if any(b in value.lower() for b in irlib.BLOCKED_FONTS):
            rep.add("CODE005", "ERROR", "code", f"fuente hand-drawn prohibida: {value!r}", subject=value,
                    hint="Usa Helvetica-Bold (alternativa Arial, luego Times-Roman).")


# --- Modo lenient: conteo heurístico ---------------------------------------------------


def count_clusters(tree, cluster_alias):
    if cluster_alias is None:
        return 0
    return sum(
        1 for n in ast.walk(tree) if isinstance(n, ast.With)
        for item in n.items if is_call_to(item.context_expr, cluster_alias)
    )


def build_name_counts(diagram_with, name_to_info):
    counts = {}

    def count_of(expr):
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and (
                expr.func.id in name_to_info or expr.func.id in NODE_FACTORY_NAMES):
            return 1
        if isinstance(expr, (ast.List, ast.Tuple)):
            return sum(count_of(e) or 0 for e in expr.elts)
        if isinstance(expr, ast.Name) and expr.id in counts:
            return counts[expr.id]
        return None

    for node in ast.walk(diagram_with):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            c = count_of(node.value)
            if c is not None:
                counts[node.targets[0].id] = c
    return counts


def count_nodes(diagram_with, name_to_info):
    return sum(
        1 for n in ast.walk(diagram_with)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and (n.func.id in name_to_info or n.func.id in NODE_FACTORY_NAMES)
    )


def flatten_chain(expr):
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, CHAIN_OPS):
        return flatten_chain(expr.left) + flatten_chain(expr.right)
    return [expr]


def operand_count(expr, name_counts, name_to_info):
    """Cuántos nodos representa un operando, o None si no es un nodo conocido."""
    if isinstance(expr, (ast.List, ast.Tuple)):
        parts = [operand_count(e, name_counts, name_to_info) for e in expr.elts]
        return sum(p or 0 for p in parts) if any(p for p in parts) else None
    if isinstance(expr, ast.Name):
        return name_counts.get(expr.id)
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and (
            expr.func.id in name_to_info or expr.func.id in NODE_FACTORY_NAMES):
        return 1
    return None


def count_edges(diagram_with, name_counts, name_to_info, edge_alias, parents):
    """Una cadena de >>, << o - cuenta como arista solo si algún operando es un nodo conocido.

    Así `i - 1` (aritmética) no infla el conteo, y `a - b` sigue siendo una arista válida.
    """
    total = 0
    for node in ast.walk(diagram_with):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, CHAIN_OPS)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, CHAIN_OPS):
            continue
        edge_names = {n for n in (edge_alias, "link") if n}
        chain = [o for o in flatten_chain(node) if not any(is_call_to(o, n) for n in edge_names)]
        counts = [operand_count(o, name_counts, name_to_info) for o in chain]
        if not any(counts):
            continue
        for i in range(len(chain) - 1):
            total += (counts[i] or 1) * (counts[i + 1] or 1)
    total += sum(1 for n in ast.walk(diagram_with) if is_call_to(n, EDGE_FACTORY_NAME))
    return total


# --- Modo strict: extracción canónica y fidelidad exacta -----------------------------------


class Extracted:
    def __init__(self):
        self.nodes = {}      # nodeid -> {var, cls, label, cluster, line}
        self.clusters = {}   # label -> {parent, zone, line}
        self.edges = []      # {source, target, arrow, label, type, emphasis, line}
        self.forms = []      # (line, mensaje) de formas no canónicas
        self.edge_label_kwargs = []  # (line, 'label'|'xlabel')


def extract_canonical(diagram_with, name_to_info, core_aliases):
    ex = Extracted()
    cluster_alias = alias_of(core_aliases, "Cluster", "Group")
    node_alias = alias_of(core_aliases, "Node")
    name_to_info = dict(name_to_info)
    if node_alias:
        name_to_info[node_alias] = {"module": "diagrams", "class": "Node"}
    var_to_id = {}

    def visit(body, stack):
        for stmt in body:
            if isinstance(stmt, ast.Pass):
                continue
            if isinstance(stmt, ast.Assign):
                call = stmt.value
                ok = (len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                      and isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                      and call.func.id in name_to_info)
                label = const_str(call.args[0]) if ok and call.args else None
                nodeid = const_str(kw_map(call).get("nodeid")) if ok else None
                if not (ok and label is not None and nodeid):
                    ex.forms.append((stmt.lineno, "asignación no canónica: se esperaba `var = Clase(\"label\", nodeid=\"id\")`"))
                    continue
                info = name_to_info[call.func.id]
                var_to_id[stmt.targets[0].id] = nodeid
                ex.nodes[nodeid] = {"var": stmt.targets[0].id, "cls": f"{info['module']}.{info['class']}",
                                    "label": label, "cluster": stack[-1] if stack else None, "line": stmt.lineno}
            elif isinstance(stmt, ast.With):
                item = stmt.items[0].context_expr if len(stmt.items) == 1 else None
                if cluster_alias and item is not None and is_call_to(item, cluster_alias) and item.args:
                    label = const_str(item.args[0])
                    ga = kw_map(item).get("graph_attr")
                    zone = None
                    if is_call_to(ga, "zone") and ga.args and isinstance(ga.args[0], ast.Constant):
                        zone = ga.args[0].value
                    if label is None:
                        ex.forms.append((stmt.lineno, "Cluster sin label literal"))
                        continue
                    ex.clusters[label] = {"parent": stack[-1] if stack else None, "zone": zone, "line": stmt.lineno}
                    visit(stmt.body, stack + [label])
                else:
                    ex.forms.append((stmt.lineno, "bloque `with` no canónico dentro del Diagram"))
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.BinOp):
                parse_edge(stmt, var_to_id, ex)
            else:
                ex.forms.append((stmt.lineno, f"sentencia no canónica ({type(stmt).__name__}) dentro del Diagram"))

    visit(diagram_with.body, [])
    return ex


def parse_edge(stmt, var_to_id, ex):
    outer = stmt.value
    inner = outer.left
    good = (isinstance(inner, ast.BinOp) and type(inner.op) is type(outer.op)
            and isinstance(outer.op, (ast.RShift, ast.Sub))
            and isinstance(inner.left, ast.Name) and isinstance(outer.right, ast.Name)
            and is_call_to(inner.right, "link"))
    if not good:
        ex.forms.append((stmt.lineno, "arista no canónica: se esperaba `a >> link(...) >> b` o `a - link(...) - b`"))
        return
    link = inner.right
    kws = kw_map(link)
    flag = lambda k: isinstance(kws.get(k), ast.Constant) and kws[k].value is True  # noqa: E731
    if isinstance(outer.op, ast.RShift):
        arrow = "forward"
    else:
        arrow = "both" if flag("forward") and flag("reverse") else "none"
    label = None
    for key in ("label", "xlabel"):
        if key in kws:
            label = const_str(kws[key])
            ex.edge_label_kwargs.append((stmt.lineno, key))
    etype = const_str(link.args[0]) if link.args else "network"
    src, dst = var_to_id.get(inner.left.id), var_to_id.get(outer.right.id)
    if src is None or dst is None:
        ex.forms.append((stmt.lineno, f"la arista usa una variable que no es un nodo declarado: "
                                      f"{inner.left.id if src is None else outer.right.id}"))
        return
    ex.edges.append({"source": src, "target": dst, "arrow": arrow, "label": label, "type": etype,
                     "emphasis": flag("emphasis"), "line": stmt.lineno})


def compare_with_ir(ex, ir, rep):
    for line, msg in ex.forms:
        rep.add("FID010", "ERROR", "fidelity", msg, where=f"línea {line}")

    ir_nodes = {n["id"]: n for n in ir["nodes"]}
    cluster_label = {c["id"]: c["label"] for c in ir["clusters"]}
    for nid, n in ir_nodes.items():
        got = ex.nodes.get(nid)
        if got is None:
            rep.add("FID001", "ERROR", "fidelity", f"el nodo {nid!r} del IR no está en el código", subject=nid)
            continue
        if got["cls"] != n["diagrams_class"]:
            rep.add("FID003", "ERROR", "fidelity", f"clase distinta en {nid!r}", subject=nid,
                    expected=n["diagrams_class"], found=got["cls"], where=f"línea {got['line']}")
        if got["label"] != n["label_wrapped"]:
            rep.add("FID009", "ERROR", "fidelity", f"label distinto en {nid!r}", subject=nid,
                    expected=n["label_wrapped"], found=got["label"], where=f"línea {got['line']}")
        want_cluster = cluster_label.get(n.get("cluster"))
        if got["cluster"] != want_cluster:
            rep.add("FID008", "ERROR", "fidelity", f"{nid!r} está en otro cluster", subject=nid,
                    expected=want_cluster, found=got["cluster"], where=f"línea {got['line']}")
        if got["var"] != n["var"]:
            rep.add("FID014", "ERROR", "fidelity", f"variable distinta en {nid!r}", subject=nid,
                    expected=n["var"], found=got["var"], where=f"línea {got['line']}")
    for nid, got in ex.nodes.items():
        if nid not in ir_nodes:
            rep.add("FID002", "ERROR", "fidelity", f"el código tiene un nodo que no está en el IR: {nid!r}",
                    subject=nid, where=f"línea {got['line']}")

    ir_clusters = {c["label"]: c for c in ir["clusters"]}
    for label, c in ir_clusters.items():
        got = ex.clusters.get(label)
        if got is None:
            rep.add("FID008", "ERROR", "fidelity", f"el cluster {label!r} del IR no está en el código", subject=label)
            continue
        if got["parent"] != cluster_label.get(c.get("parent")):
            rep.add("FID008", "ERROR", "fidelity", f"el cluster {label!r} tiene otro padre", subject=label,
                    expected=cluster_label.get(c.get("parent")), found=got["parent"])
        if got["zone"] != c["zone"]:
            rep.add("FID013", "ERROR", "fidelity", f"zona de color distinta en {label!r}", subject=label,
                    expected=c["zone"], found=got["zone"])
    for label, got in ex.clusters.items():
        if label not in ir_clusters:
            rep.add("FID008", "ERROR", "fidelity", f"el código tiene un cluster que no está en el IR: {label!r}",
                    subject=label, where=f"línea {got['line']}")

    remaining = list(ex.edges)
    for e in ir["edges"]:
        match = next((c for c in remaining if (c["source"], c["target"]) == (e["source"], e["target"])), None)
        if match is None:
            rev = next((c for c in remaining if (c["source"], c["target"]) == (e["target"], e["source"])), None)
            if rev is not None and e["arrow"] == "forward":
                rep.add("FID006", "ERROR", "fidelity", f"dirección invertida en {e['id']}", subject=e["id"],
                        expected=f"{e['source']} -> {e['target']}", found=f"{rev['source']} -> {rev['target']}",
                        where=f"línea {rev['line']}")
                remaining.remove(rev)
            else:
                rep.add("FID004", "ERROR", "fidelity", f"falta la arista {e['id']} ({e['source']} -> {e['target']})",
                        subject=e["id"])
            continue
        remaining.remove(match)
        if match["arrow"] != e["arrow"]:
            rep.add("FID006", "ERROR", "fidelity", f"flecha distinta en {e['id']}", subject=e["id"],
                    expected=e["arrow"], found=match["arrow"], where=f"línea {match['line']}")
        if (match["label"] or None) != (e.get("label") or None):
            rep.add("FID007", "ERROR", "fidelity", f"etiqueta distinta en {e['id']}", subject=e["id"],
                    expected=e.get("label"), found=match["label"], where=f"línea {match['line']}")
        if match["type"] != e["type"]:
            rep.add("FID012", "ERROR", "fidelity", f"tipo de arista distinto en {e['id']}", subject=e["id"],
                    expected=e["type"], found=match["type"], where=f"línea {match['line']}")
        if match["emphasis"] != bool(e.get("emphasis")):
            rep.add("FID012", "ERROR", "fidelity", f"énfasis distinto en {e['id']}", subject=e["id"],
                    expected=bool(e.get("emphasis")), found=match["emphasis"], where=f"línea {match['line']}")
    for extra in remaining:
        rep.add("FID005", "ERROR", "fidelity", f"el código tiene una arista que no está en el IR: "
                f"{extra['source']} -> {extra['target']}", where=f"línea {extra['line']}")


# --- Familia STY: estilo fuera de STYLE -----------------------------------------------------


def style_region(source):
    lines = source.splitlines()
    begin = next((i + 1 for i, l in enumerate(lines) if l.strip() == STYLE_BEGIN), None)
    end = next((i + 1 for i, l in enumerate(lines) if l.strip() == STYLE_END), None)
    if begin is None or end is None or end < begin:
        return None
    return begin, end


def literal_style_value(value, style_names):
    """True si el valor NO resuelve a una constante de STYLE (o sea, es un literal)."""
    if isinstance(value, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.List, ast.Tuple)):
        return True
    return root_name(value) not in style_names


def effective_splines(tree, region):
    """SPLINES efectivo: constante SPLINES, clave "splines", curvestyle=; si no, el default de la librería."""
    found = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "SPLINES" and const_str(node.value):
            found = node.value.value
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if const_str(k) == "splines" and const_str(v):
                    found = v.value
        elif isinstance(node, ast.keyword) and node.arg == "curvestyle" and const_str(node.value):
            found = node.value.value
    return found or "ortho"


class _Pending:
    """En modo lenient agrupa los STY repetidos en un finding por id (con conteo)."""

    def __init__(self, rep, strict):
        self.rep, self.strict, self.items = rep, strict, {}

    def add(self, fid, severity, family, message, **kw):
        if self.strict or severity != "INFO":
            self.rep.add(fid, severity, family, message, **kw)
        else:
            self.items.setdefault(fid, []).append((message, kw))

    def flush(self):
        for fid, occ in sorted(self.items.items()):
            msg, kw = occ[0]
            self.rep.add(fid, "INFO", "style", f"{msg} (x{len(occ)} en el archivo; se muestra la primera)",
                         where=kw.get("where", ""), subject=kw.get("subject", ""), found=len(occ), hint=kw.get("hint", ""))


def check_style(tree, source, rep, strict):
    rep, sev = _Pending(rep, strict), "ERROR" if strict else "INFO"
    region = style_region(source)
    if region is None:
        rep.add("STY000", sev, "style", f"faltan las marcas {STYLE_BEGIN} / {STYLE_END}",
                hint="El bloque STYLE concentra toda fuente, color y tamaño.")
        style_names, begin, end = set(), 0, 0
    else:
        begin, end = region
        style_names = {
            t.id for n in tree.body if isinstance(n, ast.Assign) and begin <= n.lineno <= end
            for t in n.targets if isinstance(t, ast.Name)
        }

    def outside(node):
        ln = getattr(node, "lineno", None)
        return ln is not None and not (begin <= ln <= end)

    flagged = set()
    fonts = {f.lower() for f in irlib.ALLOWED_FONTS}
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in irlib.STYLE_ATTRS and outside(node.value):
            if literal_style_value(node.value, style_names):
                rep.add("STY002", sev, "style", f"{node.arg}= con valor fuera de STYLE", where=f"línea {node.value.lineno}",
                        subject=node.arg, hint="Define una constante en el bloque STYLE y úsala aquí.")
                flagged.add(id(node.value))
        elif isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if const_str(k) in irlib.STYLE_ATTRS and outside(v) and literal_style_value(v, style_names):
                    rep.add("STY003", sev, "style", f"clave {const_str(k)!r} con valor fuera de STYLE",
                            where=f"línea {v.lineno}", subject=const_str(k))
                    flagged.add(id(v))
    docstring = ast.get_docstring(tree, clean=False)
    for node in ast.walk(tree):
        s = const_str(node) if isinstance(node, ast.Constant) else None
        if s is None or id(node) in flagged or not outside(node):
            continue
        if docstring is not None and s == docstring:
            continue
        if HEX_RE.match(s):
            rep.add("STY001", sev, "style", f"color {s!r} fuera de STYLE", where=f"línea {node.lineno}", subject=s)
        elif s.lower() in fonts or any(b in s.lower() for b in irlib.BLOCKED_FONTS):
            rep.add("STY004", sev, "style", f"familia tipográfica {s!r} fuera de STYLE", where=f"línea {node.lineno}", subject=s)

    for call in (n for n in ast.walk(tree) if is_call_to(n, "Cluster")):
        if not is_call_to(kw_map(call).get("graph_attr"), "zone"):
            rep.add("STY005", sev, "style", "Cluster sin graph_attr=zone(...): usaría el color por defecto de la librería",
                    where=f"línea {call.lineno}")

    if effective_splines(tree, region) == "ortho":
        labelled = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("Edge", "link")
            and any(k.arg == "label" for k in n.keywords)
        ]
        if labelled:
            rep.add("STY010", "ERROR" if strict else "WARNING", "style",
                    "splines=ortho con label=: Graphviz no coloca bien las etiquetas de aristas ortogonales",
                    where=f"línea {labelled[0].lineno}", hint="Usa xlabel o cambia SPLINES a 'spline'.")
    rep.flush()


# --- Principal ---------------------------------------------------------------------------------


def validate(path, ir=None, strict=None):
    path = Path(path)
    rep = irlib.Report("validate_code", target=str(path), ir="")
    if not check_syntax(path, rep):
        return rep
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    if strict is None:
        strict = GENERATED_MARK in "\n".join(source.splitlines()[:6])
    parents = build_parent_map(tree)

    name_to_info, core_aliases = check_imports(tree, rep)
    diagram_name = alias_of(core_aliases, "Diagram")
    diagram_with = find_diagram_with(tree, diagram_name)
    check_diagram_context(tree, name_to_info, core_aliases, diagram_with, parents, rep)
    diagram_call = None
    if diagram_with is not None:
        diagram_call = next(i.context_expr for i in diagram_with.items if is_call_to(i.context_expr, diagram_name))
    check_conventions(source, diagram_call, rep)
    check_typography(tree, source, rep)

    ex = None
    if diagram_with is not None and strict:
        ex = extract_canonical(diagram_with, name_to_info, core_aliases)
        if ir is None:
            rep.add("FID000", "WARNING", "fidelity", "no hay IR contra el que comparar (--ir o <slug>.ir.json junto al archivo)")
        else:
            rep.ir = ir.get("meta", {}).get("source", "")
            compare_with_ir(ex, ir, rep)
    elif diagram_with is not None:
        edge_alias = alias_of(core_aliases, "Edge")
        counts = build_name_counts(diagram_with, name_to_info)
        found = {
            "nodes": count_nodes(diagram_with, name_to_info),
            "edges": count_edges(diagram_with, counts, name_to_info, edge_alias, parents),
            "clusters": count_clusters(tree, alias_of(core_aliases, "Cluster", "Group")),
        }
        rep.add("FID020", "INFO", "fidelity", f"modo lenient: {found['nodes']} nodos, {found['edges']} aristas, "
                f"{found['clusters']} clusters (conteo heurístico)", found=found)
        if ir is not None:
            want = {"nodes": len(ir["nodes"]), "edges": len(ir["edges"]), "clusters": len(ir["clusters"])}
            for k in want:
                if found[k] < want[k]:
                    rep.add("FID021", "WARNING", "fidelity", f"faltan {k}: el IR tiene {want[k]} y el código ~{found[k]}",
                            expected=want[k], found=found[k])
    check_style(tree, source, rep, strict)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="ruta al .py, ej: diagrams_src/mi_diagrama.py")
    ap.add_argument("--ir", help="IR canónico (por defecto <slug>.ir.json junto al archivo, si existe)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="fuerza el modo estricto")
    mode.add_argument("--lenient", action="store_true", help="fuerza el modo permisivo (archivos escritos a mano)")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"no existe {path}"}))
        return 2
    ir = None
    ir_path = Path(args.ir) if args.ir else path.with_suffix(".ir.json")
    if ir_path.exists():
        try:
            ir = irlib.load_ir(ir_path)
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps({"error": f"no se pudo leer {ir_path}: {exc}"}))
            return 2
    elif args.ir:
        print(json.dumps({"error": f"no existe {args.ir}"}))
        return 2
    strict = True if args.strict else False if args.lenient else None
    return validate(path, ir, strict).emit()


if __name__ == "__main__":
    sys.exit(main())
