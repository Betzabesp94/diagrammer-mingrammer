"""El texto de la skill debe estar en español latinoamericano neutro, sin voseo.

Usa una lista curada de formas de voseo (no una regex de acentos finales, que daría falsos positivos
con palabras como 'está', 'acá' o 'así').
"""

import re
import unittest
from pathlib import Path

from helpers import SKILL

VOSEO = [
    # imperativos
    "generá", "armá", "usá", "corré", "mirá", "decí", "fijate", "acordate", "tené", "poné", "hacé", "elegí",
    "agregá", "confiá", "seguí", "copiá", "volvé", "pasá", "escribí", "revisá", "ejecutá", "creá", "cambiá",
    "editá", "buscá", "mantené", "evitá", "tratá", "dibujá", "reportá", "anotá", "preguntá", "instalá", "verificá",
    "confirmá", "asigná", "guardá", "degradá", "omití", "corregí", "volcá", "pedí", "dejá", "elegí", "sumá",
    # con pronombre enclítico
    "dibujame", "pasame", "agregale", "armame", "hacelo", "usalo", "decilo", "mirala", "copialo", "tratalo",
    "anotala", "agregalo", "guardalo", "reportalo", "comparalo", "volcala", "dejala", "decíselo", "instalalo",
    # presente voseante y pronombre
    "vos", "tenés", "podés", "sos", "querés", "necesitás", "preferís", "dividís", "contás", "notás", "vas a",
    "hacés", "decís", "sabés", "usás", "armás", "mirás", "pedís", "elegís", "ponés",
]
PATTERN = re.compile(r"(?<![\wáéíóúñ])(" + "|".join(re.escape(w) for w in sorted(set(VOSEO), key=len, reverse=True)) + r")(?![\wáéíóúñ])",
                     re.IGNORECASE)
# Excepciones: palabras de la lista que son legítimas en otro sentido.
ALLOWED_CONTEXT = ()

SUFFIXES = {".md", ".json", ".py", ".sh", ".diag"}
SKIP_PARTS = {"__pycache__", "golden"}


def skill_files():
    for path in sorted(SKILL.rglob("*")):
        if path.is_file() and path.suffix in SUFFIXES and not SKIP_PARTS & set(path.parts):
            yield path
    root = SKILL.parent.parent.parent
    for extra in ("render.sh", "Makefile", "diagrams_ref/plantilla.diag", "diagrams_ref/ejemplo_aws.diag"):
        if (root / extra).exists():
            yield root / extra


class NoVoseo(unittest.TestCase):
    def test_no_voseo_forms_anywhere_in_the_skill(self):
        bad = []
        for path in skill_files():
            if path.name == "test_no_voseo.py":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for m in PATTERN.finditer(line):
                    bad.append(f"{path.name}:{n}: {m.group(0)!r}  |  {line.strip()[:90]}")
        self.assertEqual(bad, [], "formas de voseo:\n" + "\n".join(bad[:40]))

    def test_detector_catches_real_voseo(self):
        for text in ("Usá el comando", "dibujame esto", "vos podés", "confirmá la versión", "Corré make"):
            self.assertTrue(PATTERN.search(text), text)

    def test_detector_ignores_neutral_spanish(self):
        for text in ("Usa el comando", "no instales Graphviz", "no cambies nada", "dibuja esto", "tú puedes", "está listo", "así", "acá", "aquí está",
                     "también", "después", "elegir", "pasar", "corregir", "mostrar"):
            self.assertFalse(PATTERN.search(text), text)


if __name__ == "__main__":
    unittest.main()
