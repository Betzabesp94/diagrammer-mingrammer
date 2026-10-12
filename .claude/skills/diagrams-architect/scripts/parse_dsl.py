#!/usr/bin/env python3
"""Parser determinista del DSL tipo eraser.io -> IR crudo.

    .venv/bin/python scripts/parse_dsl.py diagrams_src/<slug>.diag [--slug x]

Éxito: imprime el IR crudo (JSON) y sale con 0.
Error de sintaxis: imprime un reporte con findings PAR*, cada uno con `línea:columna`,
y sale con 1. No conoce `diagrams`: resolver clases e iconos es trabajo de resolve_ir.py.
La gramática completa está en references/dsl.md.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import irlib  # noqa: E402

DIRECTIVES = ("title", "direction", "provider", "slug", "splines", "legend", "entrypoint", "production")
NODE_ATTRS = {"icon", "label", "service", "standalone"}
GROUP_ATTRS = {"label", "boundary"}
EDGE_ATTRS = {"type", "emphasis"}
DIRECTIONS = ("TB", "BT", "LR", "RL")
SPLINES_VALUES = ("spline", "ortho", "polyline", "curved", "line")


class ParseError(Exception):
    def __init__(self, line, col, message, hint=""):
        super().__init__(message)
        self.line, self.col, self.message, self.hint = line, col, message, hint


# --- Utilidades de escaneo -----------------------------------------------------


def top_level_mask(text):
    """True en cada posición que está fuera de comillas y de corchetes."""
    mask, in_q, depth, i = [], False, 0, 0
    while i < len(text):
        ch = text[i]
        if in_q:
            mask.append(False)
            if ch == "\\" and i + 1 < len(text):
                mask.append(False)
                i += 2
                continue
            if ch == '"':
                in_q = False
        elif ch == '"':
            in_q = True
            mask.append(False)
        elif ch == "[":
            depth += 1
            mask.append(False)
        elif ch == "]":
            depth = max(0, depth - 1)
            mask.append(False)
        else:
            mask.append(depth == 0)
        i += 1
    return mask


def strip_comment(line):
    """Quita `// ...` fuera de comillas. Las líneas que empiezan con # son comentarios."""
    if line.lstrip().startswith("#"):
        return ""
    in_q = False
    for i, ch in enumerate(line):
        if ch == '"' and (i == 0 or line[i - 1] != "\\"):
            in_q = not in_q
        elif not in_q and line.startswith("//", i):
            return line[:i]
    return line


def unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def split_commas(text):
    """Divide por comas fuera de comillas. Devuelve [(offset, trozo)]."""
    parts, start, in_q = [], 0, False
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_q = not in_q
        elif ch == "," and not in_q:
            parts.append((start, text[start:i]))
            start = i + 1
    parts.append((start, text[start:]))
    return parts


def find_unquoted(text, char):
    in_q = False
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_q = not in_q
        elif ch == char and not in_q:
            return i
    return -1


def parse_value(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return unquote(raw)
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def parse_attrs(text, lineno, col0, allowed, kind):
    """`k: v, k: "v, con coma"` -> (atributos, tags, extensiones)."""
    attrs, tags, ext = {}, {}, {}
    if not text.strip():
        return attrs, tags, ext
    for off, chunk in split_commas(text):
        if not chunk.strip():
            raise ParseError(lineno, col0 + off, "atributo vacío (coma de más)")
        c = find_unquoted(chunk, ":")
        if c < 0:
            raise ParseError(lineno, col0 + off, f"se esperaba 'clave: valor' y llegó {chunk.strip()!r}")
        key, val = chunk[:c].strip(), parse_value(chunk[c + 1:])
        kcol = col0 + off + (len(chunk) - len(chunk.lstrip()))
        if key.startswith("tag."):
            tags[key[4:]] = val
        elif key.startswith("gv."):
            ext[key[3:]] = val if isinstance(val, str) else json.dumps(val)
        elif key in allowed:
            attrs[key] = val
        else:
            raise ParseError(lineno, kcol, f"atributo {key!r} no válido para {kind}",
                             hint=f"Permitidos: {', '.join(sorted(allowed))}, tag.<k>, gv.<k>")
    return attrs, tags, ext


def split_name_attrs(text, lineno, col0, allowed, kind):
    """`Nombre [a: b]` -> (nombre, atributos...)."""
    b = find_unquoted(text, "[")
    if b < 0:
        name, inner = text, ""
    else:
        end = text.rfind("]")
        if end < b or text[end + 1:].strip():
            raise ParseError(lineno, col0 + max(end, b), "falta el ']' de cierre o sobra texto después de los atributos")
        name, inner = text[:b], text[b + 1:end]
    name = unquote(name)
    if not name:
        raise ParseError(lineno, col0, f"falta el nombre del {kind}")
    attrs, tags, ext = parse_attrs(inner, lineno, col0 + b + 1 if b >= 0 else col0, allowed, kind)
    return name, attrs, tags, ext


# --- Parser ----------------------------------------------------------------------


class Parser:
    def __init__(self, text, slug_hint=""):
        self.lines = text.splitlines()
        self.slug_hint = slug_hint
        self.directives = {}
        self.directive_lines = {}
        self.style = {}
        self.nodes, self.clusters, self.edges = [], [], []
        self.node_by_name, self.cluster_by_name = {}, {}
        self.taken = set()
        self.stack = []  # ids de clusters abiertos
        self.open_lines = []

    # ids únicos compartidos entre nodos y clusters, en orden de creación
    def new_id(self, name, prefix_fix=False):
        base = irlib.slugify_id(name)
        if prefix_fix and base.startswith("cluster_"):
            base = "c_" + base[len("cluster_"):]
        cid, i = base, 2
        while cid in self.taken:
            cid = f"{base}_{i}"
            i += 1
        self.taken.add(cid)
        return cid

    def current_cluster(self):
        return self.stack[-1] if self.stack else None

    def get_node(self, name, lineno, explicit=False):
        node = self.node_by_name.get(name)
        if node is None:
            node = {
                "id": self.new_id(name), "label": name, "cluster": self.current_cluster(),
                "standalone": False, "tags": {}, "extensions": {}, "implicit": not explicit, "line": lineno,
            }
            self.nodes.append(node)
            self.node_by_name[name] = node
        return node

    def run(self):
        for lineno, raw in enumerate(self.lines, 1):
            line = strip_comment(raw).rstrip()
            if not line.strip():
                continue
            self.statement(line, lineno)
        if self.stack:
            raise ParseError(self.open_lines[-1], 1, "grupo sin cerrar: falta un '}'")
        return self.build()

    def statement(self, line, lineno):
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        col = indent + 1

        if text == "}":
            if not self.stack:
                raise ParseError(lineno, col, "'}' sin grupo abierto")
            self.stack.pop()
            self.open_lines.pop()
            return

        m = re.match(r"^(title|direction|provider|slug|splines|legend|entrypoint|production|style\.[A-Z_]+)\s*:\s*(.*)$", text)
        if m and not self.stack:
            self.directive(m.group(1), m.group(2), lineno, col)
            return
        if m and self.stack:
            raise ParseError(lineno, col, f"la directiva {m.group(1)!r} solo va al inicio, fuera de los grupos")

        if text.endswith("{"):
            self.group(text[:-1].strip(), lineno, col)
            return

        ops = self.find_operators(text)
        if len(ops) > 1:
            raise ParseError(lineno, col + ops[1][0], "una línea admite una sola conexión",
                             hint="Escribe una arista por línea (no hay cadenas A > B > C).")
        if ops:
            self.connection(text, ops[0], lineno, col)
        else:
            self.declare_node(text, lineno, col)

    def directive(self, key, value, lineno, col):
        value = unquote(value)
        if key.startswith("style."):
            name = key[len("style."):]
            if name not in irlib.DEFAULT_STYLE or name == "PALETTE":
                raise ParseError(lineno, col, f"{name!r} no es una variable de STYLE editable por directiva",
                                 hint="Variables: " + ", ".join(sorted(k for k in irlib.DEFAULT_STYLE if k != "PALETTE")))
            self.style[name] = int(value) if name == "LABEL_WRAP" and value.isdigit() else value
            return
        if key == "direction" and value not in DIRECTIONS:
            raise ParseError(lineno, col, f"direction debe ser una de {DIRECTIONS}")
        if key == "splines" and value not in SPLINES_VALUES:
            raise ParseError(lineno, col, f"splines debe ser una de {SPLINES_VALUES}")
        if key == "legend" and value not in ("on", "off"):
            raise ParseError(lineno, col, "legend debe ser 'on' u 'off'")
        if key == "production" and value not in ("true", "false"):
            raise ParseError(lineno, col, "production debe ser 'true' o 'false'")
        self.directives[key] = value
        self.directive_lines[key] = (lineno, col)

    def group(self, head, lineno, col):
        name, attrs, tags, ext = split_name_attrs(head, lineno, col, GROUP_ATTRS, "grupo")
        if tags:
            raise ParseError(lineno, col, "los grupos no admiten tag.*")
        if name in self.cluster_by_name:
            raise ParseError(lineno, col, f"el grupo {name!r} ya existe (línea {self.cluster_by_name[name]['line']})",
                             hint="Los labels de grupo deben ser únicos: Graphviz fusiona los repetidos.")
        cluster = {
            "id": self.new_id(name, prefix_fix=True), "label": attrs.get("label", name), "parent": self.current_cluster(),
            "boundary": bool(attrs.get("boundary", False)), "extensions": ext, "line": lineno,
        }
        self.clusters.append(cluster)
        self.cluster_by_name[name] = cluster
        self.stack.append(cluster["id"])
        self.open_lines.append(lineno)

    def declare_node(self, text, lineno, col):
        name, attrs, tags, ext = split_name_attrs(text, lineno, col, NODE_ATTRS, "nodo")
        if name in self.cluster_by_name:
            raise ParseError(lineno, col, f"{name!r} ya es un grupo (línea {self.cluster_by_name[name]['line']})")
        node = self.node_by_name.get(name)
        if node is not None and not node["implicit"]:
            raise ParseError(lineno, col, f"el nodo {name!r} ya fue declarado en la línea {node['line']}")
        node = self.get_node(name, lineno, explicit=True)
        node.update(implicit=False, line=lineno, cluster=self.current_cluster())
        if "label" in attrs:
            node["label"] = str(attrs["label"])
        for k in ("icon", "service"):
            if k in attrs:
                node[k] = str(attrs[k])
        node["standalone"] = bool(attrs.get("standalone", False))
        node["tags"].update(tags)
        node["extensions"].update(ext)

    def find_operators(self, text):
        mask = top_level_mask(text)
        ops, i = [], 0
        while i < len(text):
            if mask[i]:
                if text.startswith("<>", i):
                    ops.append((i, 2, "both"))
                    i += 2
                    continue
                if text[i] == ">":
                    ops.append((i, 1, "forward"))
                elif text[i] == "<":
                    ops.append((i, 1, "reverse"))
                elif text[i] == "-" and 0 < i < len(text) - 1 and text[i - 1].isspace() and text[i + 1].isspace():
                    ops.append((i, 1, "none"))
            i += 1
        return ops

    def names(self, text, lineno, col0, side):
        out = []
        for off, chunk in split_commas(text):
            name = unquote(chunk)
            if not name:
                raise ParseError(lineno, col0 + off, f"falta un nombre en el lado {side} de la conexión")
            out.append(name)
        return out

    def connection(self, text, op, lineno, col):
        pos, width, kind = op
        left_text, rest = text[:pos], text[pos + width:]
        attr_text, b = "", find_unquoted(rest, "[")
        if b >= 0:
            end = rest.rfind("]")
            if end < b or rest[end + 1:].strip():
                raise ParseError(lineno, col + pos + width + max(b, end), "falta el ']' de cierre o sobra texto tras los atributos")
            attr_text, rest = rest[b + 1:end], rest[:b]
        label = None
        c = find_unquoted(rest, ":")
        if c >= 0:
            label = unquote(rest[c + 1:])
            rest = rest[:c]
            if not label:
                raise ParseError(lineno, col + pos + width + c, "etiqueta vacía después de ':'")
        left = self.names(left_text, lineno, col, "izquierdo")
        right = self.names(rest, lineno, col + pos + width, "derecho")
        attrs, tags, ext = parse_attrs(attr_text, lineno, col + pos + width + max(b, 0) + 1, EDGE_ATTRS, "arista")
        if tags:
            raise ParseError(lineno, col, "las aristas no admiten tag.*")
        etype = attrs.get("type")
        if etype is not None and etype not in irlib.EDGE_TYPES:
            raise ParseError(lineno, col, f"type debe ser uno de {irlib.EDGE_TYPES}")
        for ln in left:
            for rn in right:
                a, b2 = self.get_node(ln, lineno), self.get_node(rn, lineno)
                src, dst, arrow = (a, b2, "forward") if kind == "forward" else (
                    (b2, a, "forward") if kind == "reverse" else (a, b2, kind))
                edge = {
                    "id": f"e{len(self.edges) + 1}", "source": src["id"], "target": dst["id"], "arrow": arrow,
                    "label": label, "emphasis": bool(attrs.get("emphasis", False)), "extensions": dict(ext), "line": lineno,
                }
                if etype is not None:
                    edge["type"] = etype
                self.edges.append(edge)

    def build(self):
        title = self.directives.get("title", "")
        slug = self.directives.get("slug") or self.slug_hint or irlib.slugify_id(title or "diagrama")
        ir = {
            "schema_version": irlib.SCHEMA_VERSION,
            "title": title or slug,
            "slug": irlib.slugify_id(slug),
            "provider": self.directives.get("provider", "aws"),
            "direction": self.directives.get("direction", "LR"),
            "nodes": self.nodes,
            "clusters": self.clusters,
            "edges": self.edges,
            "style_overrides": dict(self.style),
            "legend": {"auto": self.directives.get("legend", "on") == "on"},
            "meta": {"parser_version": 1},
        }
        if "splines" in self.directives:
            ir["style_overrides"]["SPLINES"] = self.directives["splines"]
        constraints = {}
        if "entrypoint" in self.directives:
            name = self.directives["entrypoint"]
            node = self.node_by_name.get(name)
            if node is None:
                line, col = self.directive_lines["entrypoint"]
                raise ParseError(line, col, f"entrypoint {name!r} no es un nodo del diagrama")
            constraints["internet_entrypoint"] = node["id"]
        if "production" in self.directives:
            constraints["production"] = self.directives["production"] == "true"
        if constraints:
            ir["constraints"] = constraints
        return ir


def parse(text, slug_hint=""):
    return Parser(text, slug_hint).run()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="archivo .diag")
    ap.add_argument("--slug", default="", help="slug por defecto (si el archivo no declara 'slug:')")
    ap.add_argument("-o", "--output", help="escribe el IR crudo aquí en vez de stdout")
    args = ap.parse_args()
    try:
        text = Path(args.path).read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"error": f"no se pudo leer {args.path}: {exc}"}))
        return 2
    slug = args.slug or irlib.slugify_id(Path(args.path).stem)
    try:
        ir = parse(text, slug)
    except ParseError as exc:
        rep = irlib.Report("parse_dsl", target=args.path)
        rep.add("PAR001", "ERROR", "parse", exc.message, where=f"{exc.line}:{exc.col}", hint=exc.hint)
        return rep.emit()
    ir["meta"]["source"] = Path(args.path).name
    out = irlib.dump_json(ir)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
