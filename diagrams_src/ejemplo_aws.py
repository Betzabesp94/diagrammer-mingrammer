"""Ejemplo: aplicación web chica en AWS (5 nodos).

Route53 -> ELB -> 2x EC2 (dentro de una VPC) -> RDS

Correr este archivo genera la imagen directamente:
    python diagrams_src/ejemplo_aws.py
    make render FILE=ejemplo_aws.py
"""

import os
from pathlib import Path

from diagrams import Cluster, Diagram
from diagrams.aws.compute import EC2
from diagrams.aws.database import RDS
from diagrams.aws.network import ELB, Route53

FONT = "Helvetica-Bold"  # o "Arial" / "Helvetica"  / "Courier"— confirmadas instaladas

# Definir los atributos del grafo con una nueva fuente
graph_attr_title = {
    "fontname": FONT, # Solamente afecta el titulo
    "fontsize": "22", # Font size (e.g. "14")
    # "fillcolor":  – Background color (e.g. "lightblue" or "#000000")
    # "pencolor":  – Border color (e.g. "#12b886")
    # "penwidth":  – Border thickness (e.g. "2")
    # "fontname":  – Font style (e.g. "Helvetica-Bold")
    # "labeljust":  – Text alignment (e.g. "c" for center")
    # "splines":  – Arrow shape (e.g. "curved")
}

graph_attr = {
    "fontname": FONT, # Solamente afecta el titulo
    "fontsize": "14", # Font size (e.g. "14")
    # "fillcolor":  – Background color (e.g. "lightblue" or "#000000")
    # "pencolor":  – Border color (e.g. "#12b886")
    # "penwidth":  – Border thickness (e.g. "2")
    # "fontname":  – Font style (e.g. "Helvetica-Bold")
    # "labeljust":  – Text alignment (e.g. "c" for center")
    # "splines":  – Arrow shape (e.g. "curved")
}

node_attr = {"fontname": FONT, "fontsize": "14"}
edge_attr = {"fontname": FONT, "fontsize": "14"}

# --- Salida -----------------------------------------------------------------
# La ruta se resuelve a partir de este archivo, así el PNG siempre cae en
# /output sin importar desde qué directorio se ejecute el script.
OUT = Path(__file__).resolve().parent.parent / "output" / "ejemplo_aws"
FMT = os.getenv("FORMAT", "png")  # override: FORMAT=svg python diagrams_src/ejemplo_aws.py
# ----------------------------------------------------------------------------

with Diagram(
    "Web app en AWS",
    filename=str(OUT),
    outformat=FMT,
    show=False,  # no abrir el visor de imágenes al terminar
    graph_attr=graph_attr_title,
    node_attr=node_attr,
    edge_attr=edge_attr,
    direction="LR",  # izquierda -> derecha (TB, BT, LR, RL)
):
    dns = Route53("DNS")

    with Cluster("VPC 10.0.0.0/16", graph_attr=graph_attr):
        lb = ELB("Load balancer")

        with Cluster("Subnet privada", graph_attr=graph_attr    ):
            web = [EC2("web-1"), EC2("web-2")]

        db = RDS("Postgres")

    # El operador >> crea la flecha. Con una lista se hace fan-out / fan-in.
    dns >> lb >> web >> db
