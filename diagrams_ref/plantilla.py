"""Plantilla para un diagrama nuevo.

Cómo usarla:
    cp diagrams_src/plantilla.py diagrams_src/mi_diagrama.py
    # 1) cambiá el nombre del archivo de salida en OUT
    # 2) cambiá el título del Diagram
    # 3) importá los iconos que necesites y armá los nodos
    make render FILE=mi_diagrama.py
"""

import os
from pathlib import Path

from diagrams import Cluster, Diagram

# Importá acá los iconos que uses (ver el listado de módulos en el README):
from diagrams.aws.compute import EC2
from diagrams.aws.network import ELB
from diagrams.aws.storage import S3

# --- Salida -----------------------------------------------------------------
# Cambiá "plantilla" por el nombre que quieras para la imagen.
OUT = Path(__file__).resolve().parent.parent / "output" / "plantilla"
FMT = os.getenv("FORMAT", "png")
# ----------------------------------------------------------------------------

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

with Diagram(
    "Título del diagrama",
    filename=str(OUT),
    outformat=FMT,
    show=False,
    graph_attr=graph_attr_title,
    node_attr=node_attr,
    edge_attr=edge_attr,
    direction="LR",
):
    entrada = ELB("entrada")

    with Cluster("Grupo"):
        app = EC2("app")

    bucket = S3("bucket")

    entrada >> app >> bucket
