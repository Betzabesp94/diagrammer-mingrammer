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
    direction="LR",  # izquierda -> derecha (TB, BT, LR, RL)
):
    dns = Route53("dns")

    with Cluster("VPC 10.0.0.0/16"):
        lb = ELB("load balancer")

        with Cluster("Subnet privada"):
            web = [EC2("web-1"), EC2("web-2")]

        db = RDS("postgres")

    # El operador >> crea la flecha. Con una lista se hace fan-out / fan-in.
    dns >> lb >> web >> db
