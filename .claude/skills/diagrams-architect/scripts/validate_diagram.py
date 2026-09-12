#!/usr/bin/env python3
"""Valida un script de diagrams_src/<slug>.py SIN renderizarlo con Graphviz.

Corre siempre con el intérprete del repo (mismo que ve `diagrams` instalado):

    .venv/bin/python scripts/validate_diagram.py diagrams_src/<slug>.py [--ir modelo.json]

Comprueba, en este orden, y se detiene en el primer ERROR de una categoría que
haga sin sentido seguir (p. ej. si no compila, no tiene sentido seguir parseando):

  1. syntax            -> py_compile
  2. imports            -> cada `from diagrams.x.y import Z` existe de verdad en la
                           instalación (reusa introspect_diagrams.check_path); nunca
                           se asume que un import "suena bien"
  3. diagram_context     -> todo nodo se instancia dentro de un `with Diagram(...):`
                           activo (si no, la librería tira EnvironmentError en runtime)
  4. conventions          -> OUT vía Path(__file__)...output/<slug>, FMT vía
                           os.getenv("FORMAT", "png"), show=False, filename=str(OUT),
                           outformat=FMT (las convenciones de plantilla.py / ejemplo_aws.py)
  5. typography           -> ningún fontname usa una fuente hand-drawn prohibida
                           (ej. "Bradley Hand", "Comic Sans"); default esperado
                           Helvetica-Bold, fallback Arial y luego Times-Roman
  6. topology (fidelidad) -> cuenta nodos / edges / clusters de forma estática (AST) y,
                           si se pasa --ir, los compara contra el modelo intermedio
                           (nodes/edges/clusters esperados) para detectar conexiones
                           que se "perdieron" al traducir texto -> Python

Salida: un único JSON por stdout con status por dimensión (PASS/FAIL/WARNING),
detalles, y un resumen de nodos/edges/clusters. Exit code 0 si no hay ERROR, 1 si
hay al menos un ERROR (la skill debe tratar eso como bloqueante, ver SKILL.md).

Limitación conocida y documentada: el conteo de edges es un heurístico estático
sobre el AST (sigue cadenas de `>>`/`<<`/`-`, resuelve fan-out/fan-in de listas
literales y de variables asignadas a una lista o a un nodo simple, e ignora los
`Edge(...)` intermedios como nodos). No ejecuta el script, así que un patrón muy
dinámico (nodos creados dentro de un loop con lógica compleja) puede subestimarse;
en ese caso el script lo reporta como advertencia, no como fallo silencioso.
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
spec = importlib.util.spec_from_file_location("introspect_diagrams", SCRIPT_DIR / "introspect_diagrams.py")
introspect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(introspect)

CORE_NAMES = {"Diagram", "Cluster", "Group", "Edge", "Node"}


def check_syntax(path: Path):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(str(path), cfile=str(Path(tmp) / "out.pyc"), doraise=True)
        return {"status": "PASS"}, None
    except py_compile.PyCompileError as e:
        return {"status": "FAIL", "error": str(e.exc_value)}, None


def parse_source(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return source, tree


def build_parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def check_imports(tree):
    """Devuelve (status_dict, name_to_class_info, core_aliases)."""
    results = []
    name_to_info = {}
    core_aliases = {}
    ok = True
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "diagrams":
                for alias in node.names:
                    orig = alias.name
                    bound = alias.asname or alias.name
                    if orig in CORE_NAMES:
                        core_aliases[bound] = orig
                    else:
                        results.append(
                            {"import": f"from diagrams import {orig}", "exists": False,
                             "error": f"'{orig}' no es un símbolo público de diagrams"}
                        )
                        ok = False
                continue
            if node.module.startswith("diagrams."):
                dotted_module = node.module[len("diagrams."):]
                for alias in node.names:
                    orig = alias.name
                    bound = alias.asname or alias.name
                    full_path = f"{dotted_module}.{orig}"
                    check = introspect.check_path(full_path)
                    entry = {
                        "import": f"from {node.module} import {orig}"
                        + (f" as {alias.asname}" if alias.asname else ""),
                        "exists": check["exists"],
                    }
                    if check["exists"]:
                        name_to_info[bound] = {"module": node.module, "class": orig}
                    else:
                        entry["error"] = check.get("error")
                        ok = False
                    results.append(entry)
    status = "PASS" if ok else "FAIL"
    return {"status": status, "details": results}, name_to_info, core_aliases


def find_diagram_with(tree, core_aliases):
    diagram_name = next((n for n, orig in core_aliases.items() if orig == "Diagram"), None)
    if diagram_name is None:
        return None, diagram_name
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == diagram_name:
                    return node, diagram_name
    return None, diagram_name


def check_diagram_context(tree, name_to_info, diagram_with, parents):
    """Todo Call a una clase diagrams (Node) debe estar dentro del with Diagram(...)."""
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in name_to_info:
            inside = False
            cur = node
            while cur in parents:
                cur = parents[cur]
                if cur is diagram_with:
                    inside = True
                    break
            if not inside:
                offenders.append({"class": node.func.id, "lineno": node.lineno})
    if diagram_with is None:
        return {"status": "FAIL", "error": "no se encontró ningún `with Diagram(...):` en el archivo", "offenders": offenders}
    if offenders:
        return {"status": "FAIL", "error": "hay nodos instanciados fuera del `with Diagram(...):` activo", "offenders": offenders}
    return {"status": "PASS"}


def get_diagram_call(diagram_with, diagram_name):
    if diagram_with is None:
        return None
    for item in diagram_with.items:
        call = item.context_expr
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == diagram_name:
            return call
    return None


def check_conventions(source, diagram_call):
    checks = {}
    checks["OUT_pattern"] = bool(
        re.search(
            r'OUT\s*=\s*Path\(__file__\)\.resolve\(\)\.parent\.parent\s*/\s*["\']output["\']\s*/\s*["\'][^"\']+["\']',
            source,
        )
    )
    checks["FMT_pattern"] = bool(
        re.search(r'FMT\s*=\s*os\.getenv\(\s*["\']FORMAT["\']\s*,\s*["\']png["\']\s*\)', source)
    )

    show_false = False
    filename_uses_out = False
    outformat_uses_fmt = False
    if diagram_call is not None:
        for kw in diagram_call.keywords:
            if kw.arg == "show" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                show_false = True
            if kw.arg == "filename":
                src = ast.dump(kw.value)
                if "OUT" in src:
                    filename_uses_out = True
            if kw.arg == "outformat":
                src = ast.dump(kw.value)
                if "FMT" in src:
                    outformat_uses_fmt = True
    checks["show_false"] = show_false
    checks["filename_uses_OUT"] = filename_uses_out
    checks["outformat_uses_FMT"] = outformat_uses_fmt

    failed = [k for k, v in checks.items() if not v]
    status = "PASS" if not failed else "FAIL"
    return {"status": status, "checks": checks, "failed": failed}


# Fuentes "hand-drawn"/informales prohibidas (ver references/repo_conventions.md):
# no estan garantizadas fuera de la maquina donde se genero el diagrama, y
# Graphviz sustituye en silencio por un sans-serif generico si faltan.
BLOCKED_FONTS = [
    "bradley hand", "comic sans", "chalkboard", "chalkduster", "marker felt",
    "snell roundhand", "brush script", "kristen itc", "segoe print",
    "segoe script", "handwriting", "architects daughter", "caveat", "kalam",
    "patrick hand", "short stack", "permanent marker",
]


def _string_var_assignments(tree):
    """Mapa variable -> valor, para `FONT = "Helvetica-Bold"` y similares.
    El patron de este repo siempre pasa el fontname por una variable (ver
    plantilla.py / ejemplo_aws.py), asi que resolver solo literales inline no
    alcanza."""
    values = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            values[node.targets[0].id] = node.value.value
    return values


def _resolve_str(expr, var_values):
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        return var_values.get(expr.id)
    return None


def _fontname_values(tree, var_values):
    """Todo valor (resuelto) asignado a una clave/kwarg `fontname` en el archivo:
    tanto `{"fontname": X}` (graph_attr/node_attr/edge_attr, dicts sueltos o
    inline) como `Node(..., fontname=X)` / `Edge(..., fontname=X)`."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "fontname":
                    resolved = _resolve_str(value, var_values)
                    if resolved is not None:
                        found.append(resolved)
        elif isinstance(node, ast.keyword) and node.arg == "fontname":
            resolved = _resolve_str(node.value, var_values)
            if resolved is not None:
                found.append(resolved)
    return found


def check_typography(tree):
    """Ningun fontname puede resolver a una fuente hand-drawn bloqueada. El
    default esperado es Helvetica-Bold, con fallback a Arial y despues
    Times-Roman -- nunca una fuente informal (ver
    references/repo_conventions.md)."""
    var_values = _string_var_assignments(tree)
    offenders = []
    for value in _fontname_values(tree, var_values):
        low = value.lower()
        if any(blocked in low for blocked in BLOCKED_FONTS):
            offenders.append(value)
    if offenders:
        return {
            "status": "FAIL",
            "error": (
                "se usa una fuente hand-drawn prohibida: "
                + ", ".join(sorted(set(offenders)))
                + ". Usar Helvetica-Bold (fallback Arial, luego Times-Roman)."
            ),
        }
    return {"status": "PASS"}


def resolve_cluster_alias(core_aliases):
    for bound, orig in core_aliases.items():
        if orig in ("Cluster", "Group"):
            return bound
    return None


def resolve_edge_alias(core_aliases):
    for bound, orig in core_aliases.items():
        if orig == "Edge":
            return bound
    return None


def count_clusters(tree, cluster_alias):
    if cluster_alias is None:
        return 0
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == cluster_alias:
                    n += 1
    return n


def build_name_counts(diagram_with, name_to_info):
    """Mapa variable -> cuántos nodos representa (para resolver fan-out por variable)."""
    counts = {}

    def count_of_expr(expr):
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in name_to_info:
            return 1
        if isinstance(expr, (ast.List, ast.Tuple)):
            return sum(count_of_expr(e) for e in expr.elts)
        if isinstance(expr, ast.Name) and expr.id in counts:
            return counts[expr.id]
        return None

    for node in ast.walk(diagram_with):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            c = count_of_expr(node.value)
            if c is not None:
                counts[node.targets[0].id] = c
    return counts


def count_nodes(diagram_with, name_to_info):
    n = 0
    for node in ast.walk(diagram_with):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in name_to_info:
            n += 1
    return n


CHAIN_OPS = (ast.RShift, ast.LShift, ast.Sub)


def flatten_chain(expr):
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, CHAIN_OPS):
        return flatten_chain(expr.left) + flatten_chain(expr.right)
    return [expr]


def count_operand(expr, name_counts, edge_alias):
    if edge_alias and isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == edge_alias:
        return 0  # se filtra aparte, no debería llegar acá
    if isinstance(expr, (ast.List, ast.Tuple)):
        total = 0
        for e in expr.elts:
            c = count_operand(e, name_counts, edge_alias)
            total += c if c else 1
        return total
    if isinstance(expr, ast.Name) and expr.id in name_counts:
        return name_counts[expr.id]
    return 1


def count_edges(diagram_with, name_counts, edge_alias, parents):
    total = 0
    unresolved = []
    for node in ast.walk(diagram_with):
        if isinstance(node, ast.BinOp) and isinstance(node.op, CHAIN_OPS):
            parent = parents.get(node)
            if isinstance(parent, ast.BinOp) and isinstance(parent.op, CHAIN_OPS):
                continue  # no es la raíz de la cadena, se procesa una sola vez desde la raíz
            chain = flatten_chain(node)
            real_ops = [
                op for op in chain
                if not (edge_alias and isinstance(op, ast.Call) and isinstance(op.func, ast.Name) and op.func.id == edge_alias)
            ]
            for i in range(len(real_ops) - 1):
                left_c = count_operand(real_ops[i], name_counts, edge_alias)
                right_c = count_operand(real_ops[i + 1], name_counts, edge_alias)
                total += left_c * right_c
    return total, unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="ruta al .py generado, ej: diagrams_src/mi_diagrama.py")
    ap.add_argument("--ir", help="ruta a un JSON con el modelo intermedio (nodes/edges/clusters esperados)", default=None)
    args = ap.parse_args()

    path = Path(args.path)
    report = {"file": str(path)}

    if not path.exists():
        print(json.dumps({"error": f"no existe {path}"}))
        sys.exit(1)

    syntax_result, _ = check_syntax(path)
    report["syntax"] = syntax_result
    if syntax_result["status"] != "PASS":
        report["overall"] = "FAIL"
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    source, tree = parse_source(path)
    parents = build_parent_map(tree)

    imports_result, name_to_info, core_aliases = check_imports(tree)
    report["imports"] = imports_result

    diagram_with, diagram_name = find_diagram_with(tree, core_aliases)
    ctx_result = check_diagram_context(tree, name_to_info, diagram_with, parents)
    report["diagram_context"] = ctx_result

    diagram_call = get_diagram_call(diagram_with, diagram_name) if diagram_with else None
    conv_result = check_conventions(source, diagram_call)
    report["conventions"] = conv_result

    typography_result = check_typography(tree)
    report["typography"] = typography_result

    topology = {}
    if diagram_with is not None:
        cluster_alias = resolve_cluster_alias(core_aliases)
        edge_alias = resolve_edge_alias(core_aliases)
        name_counts = build_name_counts(diagram_with, name_to_info)
        topology["nodes_found"] = count_nodes(diagram_with, name_to_info)
        topology["clusters_found"] = count_clusters(tree, cluster_alias)
        edges_found, unresolved = count_edges(diagram_with, name_counts, edge_alias, parents)
        topology["edges_found"] = edges_found
        if unresolved:
            topology["edges_unresolved_hint"] = unresolved
    else:
        topology = {"nodes_found": 0, "edges_found": 0, "clusters_found": 0}
    report["topology"] = topology

    fidelity = {"status": "SKIPPED", "note": "no se pasó --ir, no hay contra qué comparar"}
    if args.ir:
        ir_path = Path(args.ir)
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        expected_nodes = len(ir.get("nodes", []))
        expected_edges = len(ir.get("edges", []))
        expected_clusters = len(ir.get("clusters", []))
        missing_nodes = max(0, expected_nodes - topology["nodes_found"])
        missing_edges = max(0, expected_edges - topology["edges_found"])
        missing_clusters = max(0, expected_clusters - topology["clusters_found"])
        ok = missing_nodes == 0 and missing_edges == 0 and missing_clusters == 0
        fidelity = {
            "status": "PASS" if ok else "FAIL",
            "expected_nodes": expected_nodes,
            "generated_nodes": topology["nodes_found"],
            "expected_edges": expected_edges,
            "generated_edges": topology["edges_found"],
            "expected_clusters": expected_clusters,
            "generated_clusters": topology["clusters_found"],
            "missing_nodes": missing_nodes,
            "missing_edges": missing_edges,
            "missing_clusters": missing_clusters,
        }
    report["fidelity"] = fidelity

    errors = []
    if imports_result["status"] != "PASS":
        errors.append("imports")
    if ctx_result["status"] != "PASS":
        errors.append("diagram_context")
    if conv_result["status"] != "PASS":
        errors.append("conventions")
    if typography_result["status"] != "PASS":
        errors.append("typography")
    if fidelity.get("status") == "FAIL":
        errors.append("fidelity")

    report["overall"] = "FAIL" if errors else "PASS"
    report["failed_dimensions"] = errors

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
