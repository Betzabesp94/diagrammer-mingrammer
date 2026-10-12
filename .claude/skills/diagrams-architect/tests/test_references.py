"""Las referencias versionadas de diagrams_ref/ deben estar al día y cumplir los criterios de calidad."""

import shutil
import tempfile
import unittest
from pathlib import Path

import generate_diagram
import irlib
import pipeline
import validate_architecture
from helpers import REPO, build_ir

REFS = REPO / "diagrams_ref"
NAMES = ("ejemplo_aws", "plantilla")


class References(unittest.TestCase):
    def test_committed_artifacts_are_not_stale(self):
        """El .ir.json y el .py versionados son exactamente lo que genera hoy el .diag."""
        for name in NAMES:
            with self.subTest(name):
                ir = build_ir(REFS / f"{name}.diag")
                self.assertEqual((REFS / f"{name}.ir.json").read_text(), irlib.dump_json(ir),
                                 f"{name}.ir.json desactualizado: ejecuta `make diagram IN=diagrams_ref/{name}.diag`")
                self.assertEqual((REFS / f"{name}.py").read_text(), generate_diagram.generate(ir),
                                 f"{name}.py desactualizado: ejecuta `make diagram IN=diagrams_ref/{name}.diag`")

    def test_every_icon_is_an_official_exact_class(self):
        for name in NAMES:
            ir = build_ir(REFS / f"{name}.diag")
            for n in ir["nodes"]:
                with self.subTest(name, node=n["id"]):
                    self.assertEqual(n["confidence"], "exact")
                    self.assertNotIn(".generic.", n["diagrams_class"])

    def test_ejemplo_aws_is_a_sound_architecture(self):
        ir = build_ir(REFS / "ejemplo_aws.diag")
        self.assertEqual(validate_architecture.validate(ir).counts()["warning"], 0)
        by_id = {n["id"]: n for n in ir["nodes"]}
        self.assertIn("rds", by_id["db"]["diagrams_class"].lower())
        self.assertTrue(by_id["db"]["tags"].get("multi_az"))
        labels = {c["label"] for c in ir["clusters"]}
        self.assertTrue({"VPC", "Subred pública", "Subred de aplicación", "Subred de datos"} <= labels)
        # la base de datos solo recibe tráfico de la capa de aplicación, nunca del entrypoint
        entry = ir["constraints"]["internet_entrypoint"]
        self.assertFalse([e for e in ir["edges"] if e["source"] == entry and e["target"] == "db"])

    def test_the_pipeline_passes_on_the_references(self):
        for name in NAMES:
            with self.subTest(name):
                tmp = Path(tempfile.mkdtemp())
                self.addCleanup(shutil.rmtree, tmp, True)
                (tmp / "diagrams_src").mkdir()
                shutil.copy(REFS / f"{name}.diag", tmp / "diagrams_src" / f"{name}.diag")
                rep = pipeline.run(tmp / "diagrams_src" / f"{name}.diag")
                self.assertIn(rep["overall"], ("PASS", "WARN"), rep["findings"])
                self.assertEqual(rep["counts"]["error"], 0)


if __name__ == "__main__":
    unittest.main()
