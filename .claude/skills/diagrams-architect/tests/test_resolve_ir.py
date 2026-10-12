import importlib
import unittest

import irlib
import resolve_ir
from helpers import FIXTURES, build_ir


class ResolveIR(unittest.TestCase):
    def setUp(self):
        self.small = build_ir(FIXTURES / "ok_small.diag")

    def test_every_resolved_class_really_exists(self):
        """Ninguna clase inventada: se importa cada diagrams_class resuelta."""
        from diagrams import Node

        for name in ("ok_small", "ok_nested", "bad_orphan"):
            ir = build_ir(FIXTURES / f"{name}.diag")
            for n in ir["nodes"]:
                with self.subTest(fixture=name, node=n["id"]):
                    mod, _, cls = n["diagrams_class"].rpartition(".")
                    obj = getattr(importlib.import_module(mod), cls)
                    self.assertTrue(issubclass(obj, Node))

    def test_icon_resolution_is_exact(self):
        classes = {n["id"]: (n["diagrams_class"], n["confidence"]) for n in self.small["nodes"]}
        self.assertEqual(classes["web"], ("diagrams.aws.compute.EC2", "exact"))
        self.assertEqual(classes["db"], ("diagrams.aws.database.RDS", "exact"))

    def test_label_inference_and_generic_fallback(self):
        ir = resolve_ir.resolve(__import__("parse_dsl").parse("API Gateway\nAlgo Inventado XYZ\nA > B\n", "t"))
        by_id = {n["id"]: n for n in ir["nodes"]}
        self.assertEqual((by_id["api_gateway"]["diagrams_class"], by_id["api_gateway"]["confidence"]),
                         ("diagrams.aws.network.APIGateway", "inferred"))
        self.assertEqual((by_id["algo_inventado_xyz"]["diagrams_class"], by_id["algo_inventado_xyz"]["confidence"]),
                         ("diagrams.generic.blank.Blank", "generic"))

    def test_ambiguity_is_reported_not_hidden(self):
        ir = build_ir(FIXTURES / "ok_nested.diag")
        amb = [r for r in ir["meta"]["resolution"] if r["status"] == "ambiguous"]
        self.assertTrue(amb)
        self.assertIn("alternatives", amb[0])

    def test_wrap_and_vars(self):
        ir = resolve_ir.resolve(__import__("parse_dsl").parse('list [icon: aws-ec2, label: "Servicio de procesamiento de pedidos"]\n', "t"))
        n = ir["nodes"][0]
        self.assertEqual(n["var"], "list_")  # no pisa el builtin
        self.assertTrue(all(len(line) <= irlib.DEFAULT_STYLE["LABEL_WRAP"] for line in n["label_wrapped"].split("\n")))

    def test_zones_differ_between_siblings_and_from_parent(self):
        ir = build_ir(FIXTURES / "ok_nested.diag")
        z = {c["id"]: c["zone"] for c in ir["clusters"]}
        self.assertNotEqual(z["publica"], z["privada"])
        self.assertNotEqual(z["vpc"], z["publica"])
        self.assertNotEqual(z["vpc"], z["privada"])

    def test_defaults_are_completed(self):
        e = self.small["edges"][0]
        self.assertEqual((e["type"], e["role"], e["emphasis"]), ("network", "flow", False))
        self.assertEqual(self.small["nodes"][0]["role"], "service")

    def test_canonical_ir_passes_the_schema(self):
        for name in ("ok_small", "ok_nested", "bad_orphan", "bad_big"):
            self.assertEqual(irlib.schema_errors(build_ir(FIXTURES / f"{name}.diag")), [], name)

    def test_same_input_same_ir(self):
        self.assertEqual(irlib.dump_json(self.small), irlib.dump_json(build_ir(FIXTURES / "ok_small.diag")))


if __name__ == "__main__":
    unittest.main()
