#!/usr/bin/env python3
"""Introspecciona la instalación REAL de `diagrams` (no un listado memorizado).

Esta skill nunca debe adivinar un import "porque suena correcto". Cada clase que
termina en un diagrama generado tiene que haber pasado por este script (o por su
misma lógica) primero. Corre siempre con el mismo intérprete que usa el repo:

    .venv/bin/python scripts/introspect_diagrams.py <comando> ...

Comandos:
  version                         -> {"version": "0.25.1"}
  providers                       -> lista de paquetes de proveedor (aws, gcp, k8s, ...)
  modules <provider>              -> submódulos de un proveedor (ej: aws -> compute, network, ...)
  classes <provider>.<modulo>     -> clases Node reales en ese módulo (ej: aws.compute -> EC2, ECS, ...)
  check <ruta.de.Clase>           -> valida un path completo, ej: aws.compute.EC2 o diagrams.aws.compute.EC2
  search <keyword> [--providers a,b]  -> busca la keyword en todas las clases disponibles

Toda la salida es JSON por stdout, pensada para que la skill la parsee, no para
que alguien la lea "a ojo". Un `check` o `search` sin resultados es la señal para
degradar el nodo a `diagrams.generic.*` o `diagrams.custom.Custom` (ver
references/ir_schema.md) en vez de inventar un import.
"""

import argparse
import importlib
import json
import pkgutil
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version


def get_version():
    try:
        return pkg_version("diagrams")
    except PackageNotFoundError:
        return None


def _node_base():
    from diagrams import Node

    return Node


def iter_provider_names():
    import diagrams

    return sorted(m.name for m in pkgutil.iter_modules(diagrams.__path__) if m.ispkg)


def iter_submodules(provider):
    pkg = importlib.import_module(f"diagrams.{provider}")
    return sorted(m.name for m in pkgutil.iter_modules(pkg.__path__))


def iter_classes(dotted_module):
    """dotted_module ej: 'aws.compute' (sin el prefijo 'diagrams.')."""
    mod = importlib.import_module(f"diagrams.{dotted_module}")
    Node = _node_base()
    classes = []
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, Node) and obj is not Node:
            classes.append(name)
    return sorted(classes)


def check_path(dotted_path):
    """Valida un path tipo 'aws.compute.EC2' o 'diagrams.aws.compute.EC2'."""
    dp = dotted_path[len("diagrams.") :] if dotted_path.startswith("diagrams.") else dotted_path
    parts = dp.split(".")
    if len(parts) < 2:
        return {"exists": False, "error": "esperaba <provider>.<modulo>.<Clase>", "path": dotted_path}
    *mod_parts, cls_name = parts
    mod_dotted = "diagrams." + ".".join(mod_parts)
    try:
        mod = importlib.import_module(mod_dotted)
    except ImportError as e:
        return {"exists": False, "error": f"módulo {mod_dotted} no existe: {e}", "path": dotted_path}
    obj = getattr(mod, cls_name, None)
    if obj is None:
        return {"exists": False, "error": f"{cls_name} no está en {mod_dotted}", "path": dotted_path}
    Node = _node_base()
    if not (isinstance(obj, type) and issubclass(obj, Node)):
        return {
            "exists": False,
            "error": f"{cls_name} existe en {mod_dotted} pero no es una clase Node de diagrams",
            "path": dotted_path,
        }
    return {
        "exists": True,
        "module": mod_dotted,
        "class": cls_name,
        "import_statement": f"from {mod_dotted} import {cls_name}",
    }


def search(keyword, providers=None):
    kw = keyword.lower()
    results = []
    provs = providers or iter_provider_names()
    for prov in provs:
        try:
            submods = iter_submodules(prov)
        except Exception:
            continue
        for sub in submods:
            dotted = f"{prov}.{sub}"
            try:
                classes = iter_classes(dotted)
            except Exception:
                continue
            for cls in classes:
                if kw in cls.lower():
                    results.append(
                        {
                            "class": cls,
                            "module": f"diagrams.{dotted}",
                            "import_statement": f"from diagrams.{dotted} import {cls}",
                        }
                    )
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version")
    sub.add_parser("providers")

    p_mod = sub.add_parser("modules")
    p_mod.add_argument("provider")

    p_cls = sub.add_parser("classes")
    p_cls.add_argument("dotted_module", help="ej: aws.compute")

    p_chk = sub.add_parser("check")
    p_chk.add_argument("dotted_path", help="ej: aws.compute.EC2 o diagrams.aws.compute.EC2")

    p_search = sub.add_parser("search")
    p_search.add_argument("keyword")
    p_search.add_argument("--providers", help="lista separada por comas, ej: aws,gcp", default=None)

    args = ap.parse_args()

    try:
        if args.cmd == "version":
            out = {"diagrams_version": get_version()}
        elif args.cmd == "providers":
            out = {"providers": iter_provider_names()}
        elif args.cmd == "modules":
            out = {"provider": args.provider, "modules": iter_submodules(args.provider)}
        elif args.cmd == "classes":
            out = {"module": f"diagrams.{args.dotted_module}", "classes": iter_classes(args.dotted_module)}
        elif args.cmd == "check":
            out = check_path(args.dotted_path)
        elif args.cmd == "search":
            provs = args.providers.split(",") if args.providers else None
            out = {"keyword": args.keyword, "matches": search(args.keyword, provs)}
        else:  # pragma: no cover
            ap.error("comando desconocido")
            return
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stdout)
        sys.exit(1)

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
