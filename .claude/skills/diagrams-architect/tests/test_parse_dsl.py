import unittest

import parse_dsl
from helpers import FIXTURES


def parse(text):
    return parse_dsl.parse(text, "t")


def edges(ir):
    return [(e["source"], e["arrow"], e["target"], e["label"]) for e in ir["edges"]]


class ParseDSL(unittest.TestCase):
    def test_operators_are_normalized(self):
        ir = parse("A\nB\nA > B: \"x\"\nA < B\nA <> B\nA - B\n")
        self.assertEqual(edges(ir), [
            ("a", "forward", "b", "x"),
            ("b", "forward", "a", None),   # A < B  ==  B -> A
            ("a", "both", "b", None),
            ("a", "none", "b", None),
        ])

    def test_fan_out_and_fan_in(self):
        ir = parse("A > B, C: \"invoca\"\nX, Y > Z\n")
        self.assertEqual(edges(ir), [
            ("a", "forward", "b", "invoca"), ("a", "forward", "c", "invoca"),
            ("x", "forward", "z", None), ("y", "forward", "z", None),
        ])

    def test_groups_nest_and_assign_clusters(self):
        ir = parse("VPC [boundary: true] {\n  Sub {\n    N [icon: aws-ec2]\n  }\n  M\n}\nN > M\n")
        by_id = {c["id"]: c for c in ir["clusters"]}
        self.assertEqual(by_id["sub"]["parent"], "vpc")
        self.assertTrue(by_id["vpc"]["boundary"])
        self.assertEqual({n["id"]: n["cluster"] for n in ir["nodes"]}, {"n": "sub", "m": "vpc"})

    def test_attributes_tags_and_passthrough(self):
        ir = parse('DB [icon: aws-rds, label: "Base, principal", tag.multi_az: true, gv.penwidth: 2, standalone: true]\n')
        n = ir["nodes"][0]
        self.assertEqual(n["label"], "Base, principal")
        self.assertEqual(n["tags"], {"multi_az": True})
        self.assertEqual(n["extensions"], {"penwidth": "2"})
        self.assertTrue(n["standalone"])

    def test_edge_attributes(self):
        ir = parse('A\nB\nA > B: "evento" [type: event, emphasis: true, gv.penwidth: 3]\n')
        e = ir["edges"][0]
        self.assertEqual((e["type"], e["emphasis"], e["extensions"]), ("event", True, {"penwidth": "3"}))

    def test_hyphen_in_names_is_not_an_operator(self):
        ir = parse("Back-end\nFront\nFront - Back-end\n")
        self.assertEqual([n["id"] for n in ir["nodes"]], ["back_end", "front"])
        self.assertEqual(ir["edges"][0]["arrow"], "none")

    def test_comments_and_quotes(self):
        ir = parse('// comentario\n# otro\nA\nB\nA > B: "con // adentro"  // cola\n')
        self.assertEqual(ir["edges"][0]["label"], "con // adentro")

    def test_directives(self):
        ir = parse("title: Hola\ndirection: TB\nsplines: ortho\nlegend: off\nstyle.LABEL_WRAP: 20\nA\n")
        self.assertEqual((ir["title"], ir["direction"], ir["legend"]), ("Hola", "TB", {"auto": False}))
        self.assertEqual(ir["style_overrides"], {"LABEL_WRAP": 20, "SPLINES": "ortho"})

    def test_ids_are_unique_across_nodes_and_clusters(self):
        ir = parse("G {\n  N\n}\nG2 {\n  N2\n}\n")
        ids = [n["id"] for n in ir["nodes"]] + [c["id"] for c in ir["clusters"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_cluster_prefix_is_reserved_so_it_is_renamed(self):
        ir = parse("Cluster Uno {\n  N\n}\n")
        self.assertFalse(ir["clusters"][0]["id"].startswith("cluster_"))

    def test_errors_carry_line_and_column(self):
        cases = {
            "A > B > C\n": (1, "una sola conexión"),
            "A [icono: x]\n": (1, "no válido para nodo"),
            "G {\n  A\n": (1, "sin cerrar"),
            "A\nB\nA > B: \n": (3, "etiqueta vacía"),
            "}\n": (1, "sin grupo"),
            "A\nA [icon: aws-ec2]\n": (2, "ya fue declarado"),
            "G {\n}\nG {\n}\n": (3, "ya existe"),
            "A > B [type: raro]\n": (1, "type debe ser"),
            "direction: XX\n": (1, "direction"),
            "style.NOPE: 1\n": (1, "no es una variable"),
        }
        for text, (line, frag) in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(parse_dsl.ParseError) as cm:
                    parse(text)
                self.assertEqual(cm.exception.line, line)
                self.assertIn(frag, cm.exception.message)
                self.assertGreaterEqual(cm.exception.col, 1)

    def test_same_input_same_output(self):
        text = (FIXTURES / "ok_nested.diag").read_text()
        self.assertEqual(parse(text), parse(text))


if __name__ == "__main__":
    unittest.main()
