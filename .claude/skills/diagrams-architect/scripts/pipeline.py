#!/usr/bin/env python3
"""Orquestador: .diag -> IR -> validar -> .py -> validar -> render -> layout -> determinismo -> reporte.

    .venv/bin/python scripts/pipeline.py diagrams_src/<slug>.diag [--no-render]

Es lo que ejecuta `make diagram IN=...`. Escribe junto al .diag el IR (<slug>.ir.json) y el
código (<slug>.py), y en output/ el render y <slug>.report.json. Imprime ese mismo reporte.

Se detiene en la primera etapa con ERROR, porque seguir sobre un resultado roto solo agrega ruido:
  parse_dsl -> validate_ir -> validate_architecture (no bloquea) -> generate -> validate_code -> render
  -> validate_layout -> check_determinism

Exit 0 con PASS o WARN, 1 con FAIL, 2 si falla la herramienta.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_determinism  # noqa: E402
import generate_diagram  # noqa: E402
import irlib  # noqa: E402
import parse_dsl  # noqa: E402
import report as report_mod  # noqa: E402
import resolve_ir  # noqa: E402
import validate_architecture  # noqa: E402
import validate_code  # noqa: E402
import validate_ir  # noqa: E402
import validate_layout  # noqa: E402

REPO = Path(__file__).resolve().parents[4]


def has_errors(stage):
    return stage["counts"]["error"] > 0


def render_png(py_path):
    """Renderiza con render.sh (la convención del repo). Devuelve (ruta o None, mensaje)."""
    script = REPO / "render.sh"
    res = subprocess.run([str(script), str(py_path)], capture_output=True, text=True, timeout=300, env=dict(os.environ, FORMAT="png"))
    png = py_path.resolve().parent.parent / "output" / f"{py_path.stem}.png"
    if res.returncode != 0 or not png.exists():
        return None, (res.stderr or res.stdout).strip()[-400:]
    return png, ""


def run(diag_path, render=True):
    diag = Path(diag_path)
    stages, artifacts, ir = [], {"diag": str(diag)}, None
    slug = irlib.slugify_id(diag.stem)

    def finish():
        rep = report_mod.merge(slug, stages, ir, artifacts)
        out_dir = diag.resolve().parent.parent / "output"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{slug}.report.json").write_text(irlib.dump_json(rep), encoding="utf-8")
        return rep

    try:
        raw = parse_dsl.parse(diag.read_text(encoding="utf-8"), slug)
    except parse_dsl.ParseError as exc:
        prep = irlib.Report("parse_dsl", target=str(diag))
        prep.add("PAR001", "ERROR", "parse", exc.message, where=f"{exc.line}:{exc.col}", hint=exc.hint)
        stages.append(prep.to_dict(with_env=False))
        return finish()
    raw["meta"]["source"] = diag.name  # solo el nombre: la ruta no debe entrar en un IR determinista
    ir = resolve_ir.resolve(raw)
    slug = ir["slug"]
    ir_path = diag.parent / f"{slug}.ir.json"
    py_path = diag.parent / f"{slug}.py"
    ir_path.write_text(irlib.dump_json(ir), encoding="utf-8")
    artifacts["ir"] = str(ir_path)

    stages.append(validate_ir.validate(ir, str(ir_path)).to_dict(with_env=False))
    if has_errors(stages[-1]):
        return finish()

    stages.append(validate_architecture.validate(ir, str(ir_path), skip_isolated=True).to_dict(with_env=False))

    py_path.write_text(generate_diagram.generate(ir), encoding="utf-8")
    artifacts["py"] = str(py_path)
    stages.append(validate_code.validate(py_path, ir, strict=True).to_dict(with_env=False))
    if has_errors(stages[-1]):
        return finish()

    if not render:
        return finish()
    if not shutil.which("dot"):
        stages.append(validate_layout.validate(py_path, ir).to_dict(with_env=False))  # emite LAY000 (INFO)
        return finish()
    png, err = render_png(py_path)
    if png is None:
        prep = irlib.Report("validate_layout", target=str(py_path))
        prep.add("LAY099", "ERROR", "layout", f"el render falló: {err}")
        stages.append(prep.to_dict(with_env=False))
        return finish()
    artifacts["png"] = str(png)
    stages.append(validate_layout.validate(py_path, ir).to_dict(with_env=False))
    stages.append(check_determinism.validate(py_path, ir).to_dict(with_env=False))
    return finish()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("diag", help="archivo .diag")
    ap.add_argument("--no-render", action="store_true", help="solo valida y genera; no renderiza ni mide el layout")
    args = ap.parse_args()
    if not Path(args.diag).exists():
        print(json.dumps({"error": f"no existe {args.diag}"}))
        return 2
    rep = run(args.diag, render=not args.no_render)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 1 if rep["overall"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
