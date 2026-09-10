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

with Diagram(
    "Título del diagrama",
    filename=str(OUT),
    outformat=FMT,
    show=False,
    direction="LR",
):
    entrada = ELB("entrada")

    with Cluster("Grupo"):
        app = EC2("app")

    bucket = S3("bucket")

    entrada >> app >> bucket
