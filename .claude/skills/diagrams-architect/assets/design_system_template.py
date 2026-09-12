"""Bloque copy-paste del design system "pizarra colaborativa" (estilo Miro).

Cómo usarlo (igual que diagrams_src/plantilla.py):
    1. Copiá todo este bloque al principio de tu diagrams_src/<slug>.py, justo
       después de resolver OUT/FMT.
    2. Ajustá los colores de ZONE_* si querés otra paleta pastel.
    3. Reemplazá los `service_card(...)` / `internal_card(...)` / `flow(...)`
       del bloque de ejemplo (al final, comentado) por los de tu arquitectura.

Ver references/design_system.md para la explicación completa de cada pieza
(por qué HTML-like labels, por qué `diagram.dot.edge()`, las 4 categorías
semánticas de `flow()`) y references/repo_conventions.md para las convenciones
generales del repo (OUT, FMT, show=False, etc.) que este bloque no reemplaza.

No uses este patrón por default: es más código que el patrón clásico
(`ClassName("label")` + `a >> b`) y solo vale la pena cuando el pedido
explícitamente busca una estética más visual/informal ("estilo Miro",
"pizarra colaborativa", "board"). Para un diagrama de arquitectura normal, el
patrón clásico ya cumple todas las convenciones del repo con menos código.
"""

import diagrams
from pathlib import Path

# --- Tipografia: misma regla dura que el resto del repo ---------------------
# Nunca "hand-drawn" (Bradley Hand, Comic Sans, etc.) -- ver
# references/repo_conventions.md. FONT_BOLD para titulos, FONT_REG (misma
# familia, sin bold) para subtitulos/descripciones -- asi se logra jerarquia
# visual sin salir de una fuente reproducible en cualquier maquina/CI.
FONT_BOLD = "Helvetica-Bold"
FONT_REG = "Helvetica"

# --- Paleta: zonas (fondo pastel + borde de cada Cluster) --------------------
# Ajustar libremente; mantener tonos pastel suaves y un borde ~2 tonos mas
# oscuro que el fondo para que el limite de la zona se lea sin ser agresivo.
ZONE_FRONTEND = {"bg": "#E3F2FD", "border": "#90CAF9"}
ZONE_BACKEND = {"bg": "#FFE0B2", "border": "#FFCC80"}
ZONE_DATOS = {"bg": "#E8F5E9", "border": "#A5D6A7"}

# --- Paleta: cards de servicio (icono real + titulo + subtitulo + desc) -----
CARD_BORDER = "#B0BEC5"
CARD_TITLE = "#263238"
CARD_SUBTITLE = "#546E7A"
CARD_DESC = "#90A4AE"

# --- Paleta: cards de componente interno (sin icono oficial) -----------------
GENERIC_BORDER = "#8D6E63"
GENERIC_TITLE = "#4E342E"
GENERIC_DESC = "#795548"

# --- Paleta: sticky notes -----------------------------------------------------
STICKY_BG = "#FFF59D"
STICKY_BORDER = "#F9A825"
STICKY_TEXT = "#5D4037"

# --- Estilos semanticos de conexion ------------------------------------------
# 4 categorias, no decorativas: elegi la que corresponda al `type` de la
# arista en el modelo intermedio (ver references/ir_schema.md).
#   runtime        llamada sincronica normal (HTTP, persistencia)
#   realtime       websocket / push en vivo
#   internal       invocacion interna, mismo proceso/instancia
#   observability  telemetria (logs/metricas) hacia afuera del flujo principal
EDGE_STYLES = {
    "runtime": {"color": "#455A64", "style": "solid", "badge": "#1E88E5"},
    "realtime": {"color": "#8E24AA", "style": "dashed", "badge": "#8E24AA"},
    "internal": {"color": "#795548", "style": "dotted", "badge": "#795548"},
    "observability": {"color": "#AD1457", "style": "dotted", "badge": "#AD1457"},
}

# Path base de los iconos empaquetados con `diagrams`, resuelto en tiempo de
# ejecucion contra la instalacion real (portable a cualquier maquina).
_ICONS_BASE = Path(diagrams.__file__).resolve().parent.parent


def _icon_file(node_cls) -> str:
    return str(_ICONS_BASE / node_cls._icon_dir / node_cls._icon)


def service_card(container, node_id: str, node_cls, title: str, subtitle: str, description: str) -> str:
    """Card de un servicio con icono oficial verificado (ver
    scripts/introspect_diagrams.py). `container` es el Cluster o Diagram
    donde vive el nodo; ambos exponen `.node(id, label, **attrs)`."""
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


def internal_card(container, node_id: str, title: str, description: str) -> str:
    """Card para un componente SIN icono oficial (confianza generic/custom
    del IR): borde punteado, sin icono."""
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


def sticky_note(container, node_id: str, text: str) -> str:
    """Nota adhesiva (forma "note" real de Graphviz). No se conecta con
    flechas. Si el texto es largo, cortalo en 2-3 lineas cortas con \\n --
    el shape=note no hace wrap automatico y dos notas lado a lado con lineas
    largas chocan entre si."""
    container.node(
        node_id, text,
        shape="note", style="filled",
        fillcolor=STICKY_BG, color=STICKY_BORDER, fontcolor=STICKY_TEXT,
        fontname=FONT_BOLD, fontsize="11", margin="0.22,0.16",
    )
    return node_id


def flow(diagram, source_id: str, target_id: str, number: int, text: str, kind: str = "runtime") -> None:
    """Arista numerada: badge circular con el numero + capsula con el texto.
    `diagram` es el objeto de `with Diagram(...) as diagram:` -- se usa
    `diagram.dot.edge(...)` (atributo publico) porque ya no hay objetos Node
    de por medio para usar `>>`."""
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


# --- Graph/cluster attrs recomendados (pegar dentro de tu with Diagram(...)) -
#
# graph_attr = {
#     "fontname": FONT_BOLD, "bgcolor": "white", "pad": "0.3",
#     "nodesep": "0.45", "ranksep": "0.6", "labelloc": "t",
#     "label": (
#         "<"
#         f'<FONT FACE="{FONT_BOLD}" POINT-SIZE="22" COLOR="{CARD_TITLE}">Titulo</FONT><BR/>'
#         f'<FONT FACE="{FONT_REG}" POINT-SIZE="12" COLOR="{CARD_SUBTITLE}">Subtitulo</FONT>'
#         ">"
#     ),
# }
#
# with Cluster("Nombre de la zona", graph_attr={
#     "bgcolor": ZONE_FRONTEND["bg"], "pencolor": ZONE_FRONTEND["border"],
#     "fontname": FONT_BOLD, "fontsize": "13", "margin": "22",
# }) as zona:
#     nodo = service_card(zona, "id_nodo", ClaseDeDiagrams, "Titulo", "Subtitulo", "Descripcion corta")
#
# flow(diagram, origen_id, destino_id, 1, "Texto del paso", "runtime")
