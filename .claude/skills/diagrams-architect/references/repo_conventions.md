# Convenciones de este repo (diagrammer-mingrammer)

Confirmadas leyendo `diagrams_src/plantilla.py`, `diagrams_src/ejemplo_aws.py`,
`Makefile` y `render.sh` — no asumidas de memoria. Si esos archivos cambian en el
futuro, estas notas pueden quedar desactualizadas; en caso de duda, releelos.

## Anatomía de `diagrams_src/<slug>.py`

```python
import os
from pathlib import Path

from diagrams import Cluster, Diagram
from diagrams.aws.compute import EC2
from diagrams.aws.network import ELB

OUT = Path(__file__).resolve().parent.parent / "output" / "<slug>"
FMT = os.getenv("FORMAT", "png")

with Diagram(
    "Título legible",
    filename=str(OUT),
    outformat=FMT,
    show=False,
    direction="LR",  # o TB/RL/BT
):
    lb = ELB("entrada")
    with Cluster("VPC"):
        app = EC2("app")
    lb >> app
```

Puntos que `scripts/validate_diagram.py` chequea automáticamente, no hace falta
revisarlos a mano:

- `OUT` resuelto vía `Path(__file__).resolve().parent.parent / "output" / "<slug>"`
  (nunca una ruta relativa fija — así el script produce el mismo resultado sin
  importar desde qué directorio se lo ejecute).
- `FMT = os.getenv("FORMAT", "png")`.
- `show=False` en el `Diagram(...)` (siempre, en código versionado).
- `filename=str(OUT)` y `outformat=FMT`.
- Todo nodo (`EC2(...)`, `RDS(...)`, etc.) creado dentro del `with Diagram(...):`
  activo — si no, `diagrams` lanza `EnvironmentError` en runtime.

## Nombre de archivo = nombre del diagrama

Un diagrama por archivo. El slug (`<slug>.py`) es el mismo nombre que usa `OUT`
para la imagen en `output/`. Elegí un slug en `kebab_case` o `snake_case` corto y
descriptivo del sistema, no del tipo de nodo (`customer-platform`, no
`aws_diagram_1`).

## Nombrá variables por el rol, no por el tipo de nodo

`web`, `db`, `cola_eventos` — no `ec2_1`, `n2`. El `.py` es la documentación de la
arquitectura, tiene que leerse como tal.

## `Cluster` es para límites reales

VPC, subnet, namespace de k8s, dominio de negocio — no para "que quede prolijo".
Anidar clusters sin que exista ese límite real hace que el diagrama mienta sobre
la infra real.

## Estilo de `Edge`

Etiquetar una `Edge` (label/color/style) solo cuando la flecha no se explica sola:
protocolo, sincronía (`style="dashed"` para async) o criticidad
(`color="firebrick"` para una ruta crítica). No decorar cada conexión sin razón.

## Tipografía: siempre Helvetica-Bold, nunca fuentes "hand-drawn"

El `fontname` de `graph_attr`/`node_attr`/`edge_attr` es **siempre
`Helvetica-Bold`** por defecto — es la fuente que ya usan `plantilla.py` y
`ejemplo_aws.py`, y está confirmada instalada en el entorno del equipo. Si
`Helvetica-Bold` no estuviera disponible en el entorno donde se renderiza, el
fallback es, en este orden: **`Arial`**, después **`Times-Roman`**.

**No uses `Bradley Hand` ni ninguna otra fuente "hand-drawn"/informal**, aunque
el pedido describa una estética tipo pizarra/Miro/sketchnote. Ese tipo de
fuentes suele ser una fuente del sistema operativo local (no del paquete
`diagrams` ni de Graphviz): puede estar instalada en la máquina donde se
generó el diagrama y faltar en la de otra persona o en CI, y Graphviz no
avisa cuando eso pasa — simplemente sustituye por un sans-serif genérico en
silencio, así que el resultado deja de ser reproducible entre máquinas sin que
nadie lo note. La estética "pizarra colaborativa" (colores pastel, clusters
redondeados, sticky notes con `shape="note"`) se logra igual sin tocar la
tipografía — ver más abajo.

## `direction`

`LR` para flujos de request/pipeline (entra por un lado, sale por el otro), `TB`
para arquitecturas en capas (presentación/aplicación/datos apiladas). Elegilo
según el tipo de arquitectura, no por default.

## Comandos del repo

```bash
make check                       # verifica python + graphviz + diagrams — nunca instalar nada si falta
make render FILE=<slug>.py       # -> output/<slug>.png
make render FILE=<slug>.py FMT=svg
./render.sh <slug>               # equivalente sin make
```

`render.sh` ya maneja la resolución del intérprete (usa `.venv/bin/python` si
existe) y valida que `dot` (Graphviz) y `diagrams` estén disponibles antes de
intentar renderizar — no reimplementes ese chequeo, usalo.

## Multi-formato sin duplicar el diagrama

Si hace falta más de un formato del mismo diagrama, usá
`outformat=["png", "svg"]` en el `Diagram(...)`, no dos bloques `with Diagram`.

## Generá diagramas grandes con datos, no a mano

Un loop corto sobre una lista/dict es preferible a repetir `EC2("web-N")` a mano.
Si el loop puede generar la misma conexión más de una vez, pasá `strict=True` al
`Diagram(...)` para que Graphviz la colapse en una sola arista.
