# Convenciones del repo

Las aplica el generador; este archivo explica qué esperar y cómo trabajar con los archivos.

## Carpetas

| Carpeta | Contenido | Git |
|---|---|---|
| `diagrams_ref/` | referencias: `plantilla.diag` y `ejemplo_aws.diag` con su `.ir.json` y su `.py` generados | versionada |
| `diagrams_src/` | tus diagramas: `<slug>.diag` (lo que editas), `<slug>.ir.json` y `<slug>.py` (generados) | ignorada |
| `output/` | `<slug>.png`/`.svg`/`.dot` y `<slug>.report.json` | ignorada |

Si publicas en Miro, `diagrams_src/miro_boards.json` asocia cada proyecto con su board y `diagrams_src/<slug>.miro.json`
guarda el frame de cada diagrama (ver `miro.md`); ambos quedan ignorados.

Nunca agregues a git nada de `diagrams_src/`. No edites los `.py` ni los `.ir.json`: cambia el `.diag`.

## Anatomía del `.py` generado

Orden fijo: docstring → imports → `# === OUTPUT ===` (`OUT`, `FMT`) → `# === STYLE ===` →
helpers `zone()` y `link()` → `with Diagram(...)` → nodos sin cluster → clusters (en profundidad) →
aristas. Convenciones que validan `validate_code.py` y `check_determinism.py`:

- `OUT = Path(__file__).resolve().parent.parent / "output" / "<slug>"`, independiente del directorio de trabajo.
- `FMT = os.getenv("FORMAT", "png")`; el render usa `filename=str(OUT)` y `outformat=FMT`.
- `show=False`.
- Cada nodo lleva `nodeid="<id del IR>"`: así el SVG y el layout usan los ids del IR y no un uuid.
- Variables con nombre de rol (`api_gw`, `orders_db`), no `node1`.
- Sin timestamps ni versiones dentro del archivo: van en `env` del reporte.

## Comandos

```bash
make diagram IN=diagrams_src/<slug>.diag   # valida, genera, renderiza, mide y deja el reporte
make validate FILE=diagrams_src/<slug>.py  # valida un .py (estricto si lo generó la skill)
make render FILE=<slug>.py [FMT=svg]       # solo renderizar
make all                                   # renderiza todos los .py de diagrams_ref/ y diagrams_src/
make test                                  # pruebas de la skill
make evals                                 # evals verificables por script
```

## Archivos escritos a mano

Se validan, no se regeneran. `validate_code.py` los trata en modo lenient: sintaxis, imports,
convenciones y tipografía siguen bloqueando; la familia STY baja a INFO y se agrupa. Para pasar un
diagrama viejo al flujo nuevo, descríbelo en un `.diag`.

## Dirección y formatos

`direction: LR` para flujos de datos o de petición; `TB` para jerarquías o capas. Para obtener varios
formatos usa `FORMAT=svg make render FILE=...`.
