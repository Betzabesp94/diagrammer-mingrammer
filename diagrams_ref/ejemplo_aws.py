"""Aplicación web en AWS

Generado por generate_diagram.py desde ejemplo_aws.ir.json. No editar a mano:
cambia el .diag y vuelve a ejecutar `make diagram`."""

import os
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2
from diagrams.aws.database import RDS
from diagrams.aws.general import Users
from diagrams.aws.network import ALB, Route53

# === OUTPUT ===
OUT = Path(__file__).resolve().parent.parent / "output" / "ejemplo_aws"
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
    "Aplicación web en AWS",
    filename=str(OUT),
    outformat=FMT,
    show=False,
    direction=DIRECTION,
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
):
    usuarios = Users("Usuarios", nodeid="usuarios")
    dns = Route53("Route 53", nodeid="dns")
    with Cluster("VPC", graph_attr=zone(0)):
        with Cluster("Subred pública", graph_attr=zone(1)):
            alb = ALB("Balanceador de\ncarga", nodeid="alb")
        with Cluster("Subred de aplicación", graph_attr=zone(2)):
            web_1 = EC2("Web 1", nodeid="web_1")
            web_2 = EC2("Web 2", nodeid="web_2")
        with Cluster("Subred de datos", graph_attr=zone(3)):
            db = RDS("Base de datos", nodeid="db")

    # --- edges ---
    usuarios >> link(label="consulta DNS") >> dns
    usuarios >> link(label="HTTPS") >> alb
    alb >> link(label="HTTP") >> web_1
    alb >> link(label="HTTP") >> web_2
    web_1 >> link(label="SQL") >> db
    web_2 >> link(label="SQL") >> db
