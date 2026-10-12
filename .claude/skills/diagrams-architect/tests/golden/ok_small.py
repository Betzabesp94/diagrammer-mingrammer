"""Web app en AWS

Generado por generate_diagram.py desde ok_small.ir.json. No editar a mano:
cambia el .diag y vuelve a ejecutar `make diagram`."""

import os
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.database import ElastiCache, RDS
from diagrams.aws.general import Users

# === OUTPUT ===
OUT = Path(__file__).resolve().parent.parent / "output" / "ok_small"
FMT = os.getenv("FORMAT", "png")

# === STYLE ===
FONT_FAMILY       = "Helvetica"
FONT_FAMILY_BOLD  = "Helvetica-Bold"
FONT_SIZE_TITLE   = "20"
FONT_SIZE_CLUSTER = "13"
FONT_SIZE_NODE    = "12"
FONT_SIZE_EDGE    = "10"
FONT_COLOR        = "#1F2933"
PALETTE = {
    "bg": "#FFFFFF",
    "zones": [
        "#E8F1FA",
        "#EAF4EC",
        "#F5EDF7",
        "#FDF4E3",
        "#FBECEC",
    ],
    "accent": "#C2410C",
    "border": "#9AA5B1",
    "edge": "#6B7785",
}
DIRECTION         = "LR"
NODESEP           = "0.70"
RANKSEP           = "0.95"
SPLINES           = "spline"
PAD               = "0.5"
CLUSTER_MARGIN    = "16"
NODE_WIDTH        = "1.4"
LABEL_WRAP        = 15
PENWIDTH_EDGE     = "1.0"

GRAPH_ATTR = {
    "fontname": FONT_FAMILY_BOLD,
    "fontsize": FONT_SIZE_TITLE,
    "fontcolor": FONT_COLOR,
    "bgcolor": PALETTE["bg"],
    "nodesep": NODESEP,
    "ranksep": RANKSEP,
    "splines": SPLINES,
    "pad": PAD,
    "labelloc": "t",
}
NODE_ATTR = {
    "fontname": FONT_FAMILY,
    "fontsize": FONT_SIZE_NODE,
    "fontcolor": FONT_COLOR,
    "width": NODE_WIDTH,
}
EDGE_ATTR = {
    "fontname": FONT_FAMILY,
    "fontsize": FONT_SIZE_EDGE,
    "fontcolor": FONT_COLOR,
    "color": PALETTE["edge"],
    "penwidth": PENWIDTH_EDGE,
}
CLUSTER_ATTR = {
    "fontname": FONT_FAMILY_BOLD,
    "fontsize": FONT_SIZE_CLUSTER,
    "fontcolor": FONT_COLOR,
    "pencolor": PALETTE["border"],
    "style": "rounded,filled",
    "labeljust": "l",
    "margin": CLUSTER_MARGIN,
}
EDGE_STYLE_BY_TYPE = {
    "network": {},
    "event": {"style": "dashed"},
    "data": {},
    "invocation": {},
    "dependency": {"style": "dotted"},
    "authentication": {"color": PALETTE["accent"]},
}
EMPHASIS_EDGE = {"color": PALETTE["accent"], "penwidth": "2.0"}
# === END STYLE ===


def zone(index, **extra):
    return {**CLUSTER_ATTR, "bgcolor": PALETTE["zones"][index], **extra}


def link(kind="network", emphasis=False, **attrs):
    style = {**EDGE_ATTR, **EDGE_STYLE_BY_TYPE[kind]}
    if emphasis:
        style.update(EMPHASIS_EDGE)
    return Edge(**style, **attrs)


with Diagram(
    "Web app en AWS",
    filename=str(OUT),
    outformat=FMT,
    show=False,
    direction=DIRECTION,
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
):
    usuarios = Users("Usuarios", nodeid="usuarios")
    with Cluster("VPC", graph_attr=zone(0)):
        web = EC2("Servidor web", nodeid="web")
        api = EC2("API", nodeid="api")
        with Cluster("Datos", graph_attr=zone(1)):
            db = RDS("Base de datos", nodeid="db")
            cache = ElastiCache("Cache", nodeid="cache")

    # --- edges ---
    usuarios >> link(label="HTTPS") >> web
    web >> link(label="invoca") >> api
    web >> link(label="invoca") >> cache
    api - link(forward=True, reverse=True, label="SQL") - db
    api >> link() >> cache
    web - link() - usuarios
