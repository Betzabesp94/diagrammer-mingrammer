"""Primitivas compartidas por el generador y los validadores (sin CLI).

Todo lo que el generador y un validador necesitan calcular igual vive aquí, para
que no puedan divergir: el wrap de labels, el nombre de variable de un nodo, el
contraste, el contrato de findings y los valores por defecto del bloque STYLE.

Solo usa la biblioteca estándar. No importa `diagrams`.
"""

import builtins
import json
import keyword
import re
import shutil
import subprocess
import sys
import unicodedata
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

SCHEMA_VERSION = 2
TOOL_VERSION = 1

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SEVERITY_RANK = {"ERROR": 0, "WARNING": 1, "INFO": 2}

# Atributos de Graphviz que cuentan como "estilo": nunca deben aparecer como
# literal fuera del bloque STYLE del .py generado.
STYLE_ATTRS = frozenset(
    {
        "fontname", "fontsize", "fontcolor", "color", "fillcolor", "bgcolor",
        "pencolor", "penwidth", "style", "splines", "nodesep", "ranksep", "pad",
        "width", "height", "labelloc", "labeljust",
    }
)

# Valores por defecto del bloque STYLE. Son la única fuente de verdad: el
# generador los emite y los validadores los leen (contraste, fuentes, anchos).
DEFAULT_STYLE = {
    "FONT_FAMILY": "Helvetica",
    "FONT_FAMILY_BOLD": "Helvetica-Bold",
    "FONT_SIZE_TITLE": "20",
    "FONT_SIZE_CLUSTER": "13",
    "FONT_SIZE_NODE": "12",
    "FONT_SIZE_EDGE": "10",
    "FONT_COLOR": "#1F2933",
    "PALETTE": {
        "bg": "#FFFFFF",
        "zones": ["#E8F1FA", "#EAF4EC", "#F5EDF7", "#FDF4E3", "#FBECEC"],
        "accent": "#C2410C",
        "border": "#9AA5B1",
        "edge": "#6B7785",
    },
    "DIRECTION": "LR",
    "NODESEP": "0.70",
    "RANKSEP": "0.95",
    "SPLINES": "spline",
    "PAD": "0.5",
    "CLUSTER_MARGIN": "16",
    "NODE_WIDTH": "1.4",
    "LABEL_WRAP": 15,
    "PENWIDTH_EDGE": "1.0",
}

# Familias tipográficas permitidas (una sola familia sans) y bloqueadas.
ALLOWED_FONTS = ("Helvetica", "Helvetica-Bold", "Arial", "Arial-BoldMT", "Times-Roman")
BLOCKED_FONTS = (
    "bradley hand", "comic sans", "chalkboard", "chalkduster", "marker felt",
    "snell roundhand", "brush script", "kristen itc", "segoe print",
    "segoe script", "handwriting", "architects daughter", "caveat", "kalam",
    "patrick hand", "short stack", "permanent marker",
)

# Etiquetas de arista que no dicen nada: se rechazan por vagas.
VAGUE_EDGE_LABELS = frozenset({"usa", "conecta", "se conecta", "conecta a", "usa a", "uses", "connects"})

# Tipos de arista y su significado en la leyenda.
EDGE_TYPES = ("network", "event", "data", "invocation", "dependency", "authentication")


# --- Findings ----------------------------------------------------------------


class Finding(dict):
    """Un hallazgo del contrato JSON unificado."""

    def __init__(self, fid, severity, family, message, where="", subject="",
                 expected=None, found=None, hint="", blocking=None):
        super().__init__(
            id=fid,
            severity=severity,
            family=family,
            where=where,
            subject=subject,
            message=message,
            expected=expected,
            found=found,
            hint=hint,
            blocking=(severity == "ERROR") if blocking is None else blocking,
        )


class Report:
    """Acumula findings y los serializa con orden estable."""

    def __init__(self, tool, target="", ir=""):
        self.tool = tool
        self.target = str(target)
        self.ir = str(ir)
        self.findings = []

    def add(self, *args, **kwargs):
        self.findings.append(Finding(*args, **kwargs))

    def extend(self, other):
        self.findings.extend(other.findings if isinstance(other, Report) else other)

    def counts(self):
        c = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            c[f["severity"].lower()] += 1
        return c

    def overall(self):
        c = self.counts()
        if c["error"]:
            return "FAIL"
        if c["warning"]:
            return "WARN"
        return "PASS"

    def to_dict(self, with_env=True):
        ordered = sorted(
            self.findings, key=lambda f: (SEVERITY_RANK[f["severity"]], f["id"], f["where"], f["subject"])
        )
        out = {
            "tool": self.tool,
            "tool_version": TOOL_VERSION,
            "target": self.target,
            "ir": self.ir,
            "overall": self.overall(),
            "counts": self.counts(),
            "findings": ordered,
        }
        if with_env:
            out["env"] = env_versions()
        return out

    def emit(self):
        """Imprime el JSON y devuelve el código de salida (0 sin ERROR, 1 con ERROR)."""
        print(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        return 1 if self.counts()["error"] else 0


# --- Entorno -----------------------------------------------------------------


def env_versions():
    try:
        diagrams_v = pkg_version("diagrams")
    except PackageNotFoundError:
        diagrams_v = None
    return {
        "python": "%d.%d.%d" % sys.version_info[:3],
        "diagrams": diagrams_v,
        "graphviz_dot": graphviz_version(),
    }


def graphviz_version():
    dot = shutil.which("dot")
    if not dot:
        return None
    try:
        res = subprocess.run([dot, "-V"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"version\s+(\S+)", res.stderr or res.stdout or "")
    return m.group(1) if m else None


# --- IR ----------------------------------------------------------------------


def load_ir(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(obj):
    """Serialización estable: orden de claves del dict, sangría fija, \\n final."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def cluster_children(ir):
    """Mapa cluster_id -> [cluster_id hijos] en orden del IR (None = raíz)."""
    children = {None: []}
    for c in ir.get("clusters", []):
        children.setdefault(c["id"], [])
    for c in ir.get("clusters", []):
        children.setdefault(c.get("parent"), []).append(c["id"])
    return children


def cluster_depth(ir, cid):
    """Profundidad de un cluster (los de la raíz tienen profundidad 1)."""
    by_id = {c["id"]: c for c in ir.get("clusters", [])}
    depth, seen = 0, set()
    while cid is not None and cid in by_id and cid not in seen:
        seen.add(cid)
        depth += 1
        cid = by_id[cid].get("parent")
    return depth


def flow_nodes(ir):
    return [n for n in ir.get("nodes", []) if n.get("role", "service") == "service"]


def flow_edges(ir):
    return [e for e in ir.get("edges", []) if e.get("role", "flow") == "flow"]


# --- Nombres y texto -----------------------------------------------------------


def slugify_id(text):
    """Texto libre -> identificador `^[a-z][a-z0-9_]*$` (determinista)."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    if not slug:
        slug = "n"
    if slug[0].isdigit():
        slug = "n_" + slug
    return slug


def slugify_var(node_id, reserved, taken):
    """Nombre de variable Python para un nodo, sin colisiones.

    `reserved`: nombres de nivel de módulo que no se pueden pisar (imports,
    constantes de STYLE, helpers). `taken`: variables ya asignadas, en orden del IR.
    """
    base = slugify_id(node_id)
    if keyword.iskeyword(base) or hasattr(builtins, base) or base in reserved:
        base += "_"
    name, i = base, 2
    while name in taken:
        name = f"{base}_{i}"
        i += 1
    return name


def wrap_label(text, width):
    """Wrap voraz por palabras. Una palabra más larga que `width` se corta duro.

    Determinista: mismo texto y ancho -> mismo resultado. Respeta los `\\n` que
    ya estén en el texto como saltos de línea explícitos.
    """
    lines = []
    for raw in str(text).split("\n"):
        current = ""
        for word in raw.split():
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return "\n".join(lines)


# Anchos de Helvetica (unidades de 1/1000 em) para ASCII imprimible, tomados de
# las métricas AFM estándar. Estimación previa al render; la medición exacta la
# hace validate_layout con las métricas reales de Graphviz.
_HELV = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191,
    "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278,
    ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556, "@": 1015,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722,
    "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667,
    "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667,
    "Y": 667, "Z": 611, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556, "h": 556,
    "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556,
    "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722, "x": 500,
    "y": 500, "z": 500, "{": 334, "|": 260, "}": 334, "~": 584,
}
for _d in "0123456789":
    _HELV[_d] = 556


def estimate_text_width(text, fontsize, bold=False):
    """Ancho estimado, en puntos, de la línea más ancha del texto."""
    factor = 1.07 if bold else 1.0
    widest = 0.0
    for line in str(text).split("\n"):
        w = sum(_HELV.get(ch, 556) for ch in line) / 1000.0 * float(fontsize) * factor
        widest = max(widest, w)
    return widest


# --- Color ---------------------------------------------------------------------


def _channel(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg, bg):
    """Contraste WCAG 2.x entre dos colores `#RRGGBB`."""
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def is_hex_color(value):
    return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None


# --- Schema (subconjunto de JSON Schema) ----------------------------------------

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "ir.schema.json"

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, tname):
    if tname == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if tname == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[tname])


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(value, schema=None, path="$"):
    """Valida `value` contra el subconjunto de JSON Schema que usa ir.schema.json.

    Devuelve una lista de (path, mensaje), en orden estable. Soporta: type,
    enum, pattern, minimum, required, properties, additionalProperties=false e
    items. Es a propósito mínimo: el schema es el contrato y este intérprete
    no tiene reglas propias, así que no pueden desincronizarse.
    """
    if schema is None:
        schema = load_schema()
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append((path, f"valor {value!r} fuera de {schema['enum']}"))
        return errors
    types = schema.get("type")
    if types is not None:
        tlist = types if isinstance(types, list) else [types]
        if not any(_type_ok(value, t) for t in tlist):
            errors.append((path, f"se esperaba {'|'.join(tlist)}, llegó {type(value).__name__}"))
            return errors
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append((path, f"{value!r} no cumple el patrón {schema['pattern']}"))
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        errors.append((path, f"{value} es menor que el mínimo {schema['minimum']}"))
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append((f"{path}.{key}", "falta el campo requerido"))
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append((f"{path}.{key}", "campo desconocido"))
        for key, sub in props.items():
            if key in value:
                errors.extend(schema_errors(value[key], sub, f"{path}.{key}"))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], f"{path}[{i}]"))
    return errors


# --- STYLE efectivo -------------------------------------------------------------


def resolve_style(ir=None):
    """STYLE efectivo: DEFAULT_STYLE + `style_overrides` del IR (PALETTE se mezcla por clave)."""
    style = json.loads(json.dumps(DEFAULT_STYLE))
    for key, val in ((ir or {}).get("style_overrides") or {}).items():
        if key == "PALETTE" and isinstance(val, dict):
            style["PALETTE"].update(val)
        else:
            style[key] = val
    return style
