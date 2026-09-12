# Design system "pizarra colaborativa" (estilo Miro)

Patrón **opcional**, para cuando el usuario pide explícitamente una estética
más visual/informal ("estilo Miro", "board colaborativo", "pizarra", "que se
vea menos técnico") en vez del diagrama simple de siempre. Por default seguí
usando el patrón clásico de `references/repo_conventions.md`
(`ClassName("label")` + `a >> b`) — es más corto y ya cumple con todas las
convenciones del repo. Activá este design system solo cuando el pedido lo
justifique; no es más "correcto" que el patrón clásico, es más *visual*.

**La arquitectura no cambia.** Este patrón es una capa de rendering sobre los
mismos nodos/edges/clusters del modelo intermedio (`references/ir_schema.md`)
— nunca uses la estética como excusa para agregar, quitar o reinterpretar
componentes o conexiones.

## Por qué existe

Un diagrama de `diagrams` por default (ícono + una línea de texto debajo, en
`Sans-Serif`, con `nodesep`/`ranksep` grandes) es legible pero se lee como "un
grafo generado por código". Graphviz soporta **HTML-like labels**
(`label=<<TABLE>...</TABLE>>`) desde hace años, y la librería `graphviz` que
usa `diagrams` por debajo pasa ese string tal cual al motor de render sin
tocarlo — no es un hack ni una API no documentada, es la forma estándar de
Graphviz de dibujar una tabla con texto enriquecido dentro de un nodo. Eso
permite armar tarjetas con ícono + título + subtítulo + descripción, badges
numerados, y "cápsulas" de texto — mucho más cerca de un board de Miro que el
ícono+label por default.

## Piezas del design system

Copiá estas funciones (helpers) al principio del `.py`, junto a las
constantes de color, tal como hoy se copia `plantilla.py`. Ver
`assets/design_system_template.py` para el bloque completo listo para pegar.

### 1. Paleta y tipografía centralizadas

Un diccionario de colores por zona (`ZONE_*`), colores de card
(`CARD_BORDER`/`CARD_TITLE`/`CARD_SUBTITLE`/`CARD_DESC`), y los estilos
semánticos de conexión (`EDGE_STYLES`, ver más abajo) definidos **una sola
vez** arriba del archivo. Esto es lo que hace que un segundo diagrama
generado por la skill se vea consistente con el primero.

**Tipografía: sigue la misma regla dura del resto del repo.** `FONT_BOLD =
"Helvetica-Bold"` para títulos, `FONT_REG = "Helvetica"` para subtítulos y
descripciones (misma familia, menor peso — así se logra jerarquía visual sin
salir de una fuente reproducible). Nunca una fuente "hand-drawn": ni en
`fontname`, ni en un `FACE="..."` dentro de un label HTML — `validate_diagram.py`
chequea las dos formas.

### 2. `service_card()` — tarjeta de un servicio con ícono oficial

```python
import diagrams
from pathlib import Path

_ICONS_BASE = Path(diagrams.__file__).resolve().parent.parent

def _icon_file(node_cls) -> str:
    # _icon_dir / _icon son atributos de clase reales de cada Node de
    # diagrams (ver diagrams/__init__.py, Node._load_icon) -- no un hack,
    # es la misma ruta que arma la librería internamente. Resolverla en
    # tiempo de ejecución (no al generar el .py) mantiene el script portable:
    # apunta a la instalación de `diagrams` de la máquina donde se corre.
    return str(_ICONS_BASE / node_cls._icon_dir / node_cls._icon)

def service_card(container, node_id, node_cls, title, subtitle, description):
    icon = _icon_file(node_cls)
    label = (
        "<"
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" '
        f'STYLE="ROUNDED" COLOR="{CARD_BORDER}" BGCOLOR="white">'
        f'<TR><TD FIXEDSIZE="TRUE" WIDTH="36" HEIGHT="36"><IMG SRC="{icon}" SCALE="TRUE"/></TD></TR>'
        f'<TR><TD><FONT FACE="{FONT_BOLD}" POINT-SIZE="12" COLOR="{CARD_TITLE}">{title}</FONT></TD></TR>'
        f'<TR><TD><FONT FACE="{FONT_REG}" POINT-SIZE="9" COLOR="{CARD_SUBTITLE}">{subtitle}</FONT></TD></TR>'
        f'<TR><TD><FONT FACE="{FONT_REG}" POINT-SIZE="8" COLOR="{CARD_DESC}">{description}</FONT></TD></TR>'
        "</TABLE>>"
    )
    container.node(node_id, label, shape="plaintext")
    return node_id
```

`container` es el `Cluster` o el `Diagram` donde tiene que vivir el nodo
(ambos exponen `.node(id, label, **attrs)` — API pública de `diagrams`, la
misma que ya usa `sticky_note()` en la versión anterior de este documento).
`node_id` es un string simple elegido por vos (`"cloudfront"`, `"backend"`) —
ya no hay un objeto `Node` de por medio, así que ese id es lo que después le
pasás a `flow()`.

**Regla dura, igual que en el patrón clásico:** `node_cls` tiene que ser una
clase importada y verificada con `introspect_diagrams.py` — nunca un ícono
inventado. El nivel de confianza (`exact`/`inferred`/`generic`/`custom`) se
sigue reportando igual que siempre (sección de mapeos del reporte final).

### 3. `internal_card()` — componente sin ícono oficial

Para nodos de confianza `generic`/`custom` (lógica interna, un canal de
comunicación, un módulo sin ícono de proveedor): mismo lenguaje visual que
`service_card()` pero sin ícono y con borde punteado, para que se distinga a
simple vista de un servicio con ícono real:

```python
def internal_card(container, node_id, title, description):
    label = (
        "<"
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" '
        f'STYLE="ROUNDED,DASHED" COLOR="{GENERIC_BORDER}" BGCOLOR="white">'
        f'<TR><TD><FONT FACE="{FONT_BOLD}" POINT-SIZE="11" COLOR="{GENERIC_TITLE}">{title}</FONT></TD></TR>'
        f'<TR><TD><FONT FACE="{FONT_REG}" POINT-SIZE="8" COLOR="{GENERIC_DESC}">{description}</FONT></TD></TR>'
        "</TABLE>>"
    )
    container.node(node_id, label, shape="plaintext")
    return node_id
```

### 4. `flow()` — arista numerada con badge + cápsula

```python
EDGE_STYLES = {
    "runtime":       {"color": "#455A64", "style": "solid",  "badge": "#1E88E5"},  # llamada sincronica (HTTP, persistencia)
    "realtime":      {"color": "#8E24AA", "style": "dashed", "badge": "#8E24AA"},  # websocket / push en vivo
    "internal":      {"color": "#795548", "style": "dotted", "badge": "#795548"},  # invocacion interna, mismo proceso
    "observability": {"color": "#AD1457", "style": "dotted", "badge": "#AD1457"},  # logs / metricas hacia afuera del flujo
}

def flow(diagram, source_id, target_id, number, text, kind="runtime"):
    style = EDGE_STYLES[kind]
    label = (
        "<"
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="2" CELLPADDING="0"><TR>'
        f'<TD BGCOLOR="{style["badge"]}" STYLE="ROUNDED" WIDTH="20" HEIGHT="20" FIXEDSIZE="TRUE">'
        f'<FONT FACE="{FONT_BOLD}" POINT-SIZE="10" COLOR="white">{number}</FONT></TD>'
        f'<TD BGCOLOR="white" STYLE="ROUNDED" CELLPADDING="4">'
        f'<FONT FACE="{FONT_REG}" POINT-SIZE="9" COLOR="{CARD_TITLE}">{text}</FONT></TD>'
        "</TR></TABLE>>"
    )
    diagram.dot.edge(source_id, target_id, label=label, color=style["color"], style=style["style"], penwidth="1.4")
```

`diagram` es el objeto que devuelve `with Diagram(...) as diagram:`.
`diagram.dot` es el `graphviz.Digraph` interno (atributo público, no
privado — es como la propia librería `diagrams` arma el grafo). Usar
`diagram.dot.edge(...)` directo (en vez de `Node.__rshift__`) es necesario
porque ya no hay objetos `Node`, pero el efecto en el `.dot` final es el
mismo tipo de sentencia `id1 -> id2 [attrs]`.

**Las 4 categorías (`runtime`/`realtime`/`internal`/`observability`) son
semánticas, no decorativas.** Elegí la que corresponda al `type` que ya tiene
esa arista en el modelo intermedio (`network`→`runtime`, un canal en vivo→
`realtime`, `invocation` dentro del mismo proceso→`internal`,
telemetría→`observability`). No inventes una categoría nueva por arista salvo
que ninguna de las 4 describa bien la conexión — en ese caso agregala al
diccionario `EDGE_STYLES` con su propio color, no reutilices un color que ya
significa otra cosa en el mismo diagrama.

### 5. `sticky_note()` — nota adhesiva

Igual que en la versión anterior de este patrón: forma `note` real de
Graphviz (esquina doblada), amarilla, sin conectarse a ninguna flecha. Usala
para constraints/advertencias explícitas del pedido (ej. "esto no escala
horizontalmente"), nunca para inventar una recomendación que el usuario no
pidió — esa va en el reporte final, no en el diagrama.

```python
def sticky_note(container, node_id, text):
    container.node(
        node_id, text,
        shape="note", style="filled",
        fillcolor="#FFF59D", color="#F9A825", fontcolor="#5D4037",
        fontname=FONT_BOLD, fontsize="11", margin="0.22,0.16",
    )
    return node_id
```

Si el texto es largo, cortalo en 2-3 líneas cortas (`\n`) en vez de una sola
línea larga — dos sticky notes lado a lado con líneas largas chocan entre sí
(el `shape=note` no hace wrap automático de texto).

## Layout: cómo reducir el espacio vacío

- `graph_attr`: `nodesep` entre `0.4` y `0.5`, `ranksep` entre `0.55` y `0.7`
  (los defaults de `diagrams`, pensados para íconos+label grandes, dejan
  demasiado aire entre cards compactas). `pad` bajo (`"0.3"`).
- Cada `Cluster` con `margin` alto en su `graph_attr` (`"20"`–`"26"`): más
  padding *interno* (para que no quede pegado al borde) sin agregar espacio
  *entre* clusters.
- Preferí `direction="TB"` para arquitecturas en capas (presentación /
  aplicación / datos apiladas) — con muchas cards y edges cruzados, `LR`
  tiende a producir más cruces (ver `repo_conventions.md`, sección
  `direction`).
- Un componente sin ninguna arista (ej. una nota de IaC fuera del runtime) no
  tiene rank forzado por Graphviz; declararlo en su propio `Cluster` chico,
  después de las zonas del flujo principal, suele alcanzar para que quede
  aparte sin pelear por espacio con el flujo activo — no hace falta forzar
  posiciones con coordenadas absolutas.

## Título del diagrama con jerarquía

Sobrescribí el label del grafo (que por default es texto plano abajo) con un
HTML label arriba:

```python
graph_attr = {
    ...
    "labelloc": "t",
    "label": (
        "<"
        f'<FONT FACE="{FONT_BOLD}" POINT-SIZE="22" COLOR="{CARD_TITLE}">Título del sistema</FONT><BR/>'
        f'<FONT FACE="{FONT_REG}" POINT-SIZE="12" COLOR="{CARD_SUBTITLE}">Subtítulo / fase / alcance</FONT>'
        ">"
    ),
}
```

## Elementos fuera del flujo runtime (IaC, notas de contexto)

Un componente que no participa de ningún `flow()` (tooling de IaC, un
diagrama de referencia, un dato de contexto) se lee como "una zona más" si se
lo mete en un `Cluster` con el mismo tratamiento visual que las zonas reales.
Dale un tratamiento distinto y explícitamente más apagado: borde punteado
gris, sin color de fondo de zona, título en `FONT_REG` (no bold) y en un tono
apagado:

```python
with Cluster("Fuera del runtime", graph_attr={
    "bgcolor": "white", "pencolor": "#CFD8DC", "style": "dashed,rounded",
    "fontname": FONT_REG, "fontsize": "11", "fontcolor": "#78909C", "margin": "20",
}) as iac_zone:
    iac = service_card(iac_zone, "iac", ...)
```

## Ejemplo completo (genérico)

```python
import os
from pathlib import Path

import diagrams
from diagrams import Cluster, Diagram
from diagrams.aws.compute import Fargate
from diagrams.aws.database import RDS
from diagrams.aws.network import CloudFront
from diagrams.aws.storage import S3
from diagrams.onprem.client import User

OUT = Path(__file__).resolve().parent.parent / "output" / "servicio-web"
FMT = os.getenv("FORMAT", "png")

FONT_BOLD, FONT_REG = "Helvetica-Bold", "Helvetica"
CARD_BORDER, CARD_TITLE, CARD_SUBTITLE, CARD_DESC = "#B0BEC5", "#263238", "#546E7A", "#90A4AE"
ZONE_FRONTEND = {"bg": "#E3F2FD", "border": "#90CAF9"}
ZONE_DATOS = {"bg": "#E8F5E9", "border": "#A5D6A7"}

# ... (pegar aca service_card / flow / EDGE_STYLES, ver assets/design_system_template.py)

with Diagram(
    "servicio-web", filename=str(OUT), outformat=FMT, show=False, direction="TB",
    graph_attr={"fontname": FONT_BOLD, "nodesep": "0.45", "ranksep": "0.6", "pad": "0.3"},
) as diagram:
    user = service_card(diagram, "user", User, "Usuario final", "Navegador web", "Consume la app")

    with Cluster("Frontend", graph_attr={"bgcolor": ZONE_FRONTEND["bg"], "pencolor": ZONE_FRONTEND["border"], "margin": "22"}) as frontend:
        cdn = service_card(frontend, "cdn", CloudFront, "Amazon CloudFront", "CDN", "Entrega el frontend")
        bucket = service_card(frontend, "bucket", S3, "Amazon S3", "Frontend estatico", "Origen de CloudFront")

    with Cluster("Backend", graph_attr={"bgcolor": "#FFE0B2", "pencolor": "#FFCC80", "margin": "22"}) as backend_zone:
        api = service_card(backend_zone, "api", Fargate, "API", "ECS Fargate", "Instancia unica")

    with Cluster("Datos", graph_attr={"bgcolor": ZONE_DATOS["bg"], "pencolor": ZONE_DATOS["border"], "margin": "22"}) as datos:
        db = service_card(datos, "db", RDS, "Amazon RDS", "Base de datos", "Fuente de datos productiva")

    flow(diagram, user, cdn, 1, "Solicita la app", "runtime")
    flow(diagram, cdn, bucket, 2, "Sirve contenido estatico", "runtime")
    flow(diagram, user, api, 3, "Llama a la API", "runtime")
    flow(diagram, api, db, 4, "Lee/escribe datos", "runtime")
```

## Qué valida `scripts/validate_diagram.py` sobre este patrón

El validador reconoce **los dos patrones a la vez** (podés mezclarlos en un
mismo archivo): cuenta como nodo tanto una instancia clásica (`EC2(...)`)
como una llamada a `service_card()`/`internal_card()`; cuenta como edge tanto
una cadena `a >> b` como una llamada a `flow()`; `sticky_note()` nunca cuenta
como nodo de arquitectura. La validación de tipografía también revisa los
`FACE="..."` dentro de los labels HTML, no solo los `fontname=` de siempre.
No hace falta pasarle ningún flag especial — corré
`scripts/validate_diagram.py diagrams_src/<slug>.py --ir <ir.json>` igual que
con el patrón clásico.
