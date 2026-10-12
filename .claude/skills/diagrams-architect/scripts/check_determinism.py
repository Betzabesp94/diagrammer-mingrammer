#!/usr/bin/env python3
"""Comprueba el determinismo del pipeline y registra las versiones del entorno.

    .venv/bin/python scripts/check_determinism.py diagrams_src/<slug>.py --ir diagrams_src/<slug>.ir.json

  DET001  regenerar el .py desde el IR no da los mismos bytes que el archivo en disco
  DET004  solo difiere el bloque STYLE (edición manual legítima; INFO)
  DET002  renderizar el .py dos veces da SVG distintos
  DET000  sin Graphviz: solo se verificó la generación (INFO)

El criterio es "misma máquina, mismas versiones": otra versión de Graphviz o de la fuente cambia
las métricas de texto y por tanto el layout. Por eso las versiones van en `env` del reporte y no
dentro del .py. La comparación de render se hace en SVG (byte a byte); el PNG no es reproducible
por metadatos de la librería de compresión.

Exit 0 sin ERROR, 1 con ERROR, 2 si falla la herramienta.
"""

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_diagram  # noqa: E402
import irlib  # noqa: E402


def render_svg(py_path, slug):
    env = dict(os.environ, FORMAT="svg")
    res = subprocess.run([sys.executable, str(py_path)], capture_output=True, text=True, env=env, timeout=300)
    svg = Path(py_path).resolve().parent.parent / "output" / f"{slug}.svg"
    if res.returncode != 0 or not svg.exists():
        return None, (res.stderr or res.stdout).strip()[-400:]
    return svg.read_bytes(), ""


def split_style(src):
    """(código sin el bloque STYLE, bloque STYLE). Permite distinguir una edición legítima de STYLE."""
    begin, end = "# === STYLE ===", "# === END STYLE ==="
    if begin not in src or end not in src:
        return src, ""
    i, j = src.index(begin), src.index(end) + len(end)
    return src[:i] + src[j:], src[i:j]


def first_difference(a, b):
    la, lb = a.decode("utf-8", "replace").splitlines(), b.decode("utf-8", "replace").splitlines()
    for line in difflib.unified_diff(la, lb, lineterm="", n=0):
        if not line.startswith(("---", "+++", "@@")):
            return line[:160]
    return ""


def validate(py_path, ir, render=True):
    py_path = Path(py_path)
    rep = irlib.Report("check_determinism", target=str(py_path))
    expected = generate_diagram.generate(ir)
    on_disk = py_path.read_text(encoding="utf-8")
    if expected != on_disk:
        body_exp, style_exp = split_style(expected)
        body_disk, style_disk = split_style(on_disk)
        if body_exp == body_disk and style_exp != style_disk:
            rep.add("DET004", "INFO", "determinism",
                    "el bloque STYLE del .py se editó a mano: sirve para probar, pero se sobrescribe al regenerar",
                    hint="Para conservarlo usa style.<VARIABLE>: <valor> en el .diag.")
        else:
            rep.add("DET001", "ERROR", "determinism", "el .py en disco no es lo que genera el IR (se editó a mano o el IR cambió)",
                    hint="Regenera con `make diagram`; no edites el .py. Primera diferencia: "
                    + first_difference(on_disk.encode(), expected.encode()))
    if not render:
        return rep
    if not shutil.which("dot"):
        rep.add("DET000", "INFO", "determinism", "sin Graphviz: solo se verificó la generación, no el render")
        return rep
    first, err = render_svg(py_path, ir["slug"])
    second, err2 = render_svg(py_path, ir["slug"]) if first is not None else (None, "")
    if first is None or second is None:
        rep.add("DET003", "ERROR", "determinism", f"no se pudo renderizar el SVG: {err or err2}")
    elif first != second:
        rep.add("DET002", "ERROR", "determinism", "dos renders del mismo .py dieron SVG distintos",
                hint="Primera diferencia: " + first_difference(first, second))
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="ruta al .py generado")
    ap.add_argument("--ir", required=True, help="IR canónico del que salió el .py")
    ap.add_argument("--no-render", action="store_true", help="solo verifica la generación")
    args = ap.parse_args()
    try:
        ir = irlib.load_ir(args.ir)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": f"no se pudo leer {args.ir}: {exc}"}))
        return 2
    return validate(args.path, ir, render=not args.no_render).emit()


if __name__ == "__main__":
    sys.exit(main())
