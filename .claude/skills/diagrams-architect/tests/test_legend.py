import unittest

import generate_diagram
import irlib
import parse_dsl
import resolve_ir
import validate_code
import validate_ir
from helpers import FIXTURES, build_ir


def ir_of(text):
    return resolve_ir.resolve(parse_dsl.parse(text, "t"))


class Legend(unittest.TestCase):
    def test_no_legend_when_all_arrows_are_plain(self):
        ir = build_ir(FIXTURES / "ok_small.diag")
        self.assertEqual(ir["legend"], {"auto": True, "entries": []})
        self.assertFalse([n for n in ir["nodes"] if n["role"] == "legend"])
        self.assertFalse([c for c in ir["clusters"] if c.get("role") == "legend"])

    def test_legend_lists_each_meaningful_stroke_once_in_first_appearance_order(self):
        ir = build_ir(FIXTURES / "ok_legend.diag")
        self.assertEqual([e["key"] for e in ir["legend"]["entries"]],
                         ["authentication", "event", "dependency", "emphasis"])
        legend_edges = [e for e in ir["edges"] if e["role"] == "legend"]
        self.assertEqual([e["label"] for e in legend_edges],
                         ["autenticación", "evento asíncrono", "dependencia", "flujo destacado"])
        self.assertEqual(len([n for n in ir["nodes"] if n["role"] == "legend"]), 2 * len(legend_edges))

    def test_two_edges_of_the_same_type_make_one_entry(self):
        ir = ir_of('A\nB\nC\nA > B: "x" [type: event]\nB > C: "y" [type: event]\n')
        self.assertEqual([e["key"] for e in ir["legend"]["entries"]], ["event"])

    def test_legend_off_disables_it(self):
        ir = ir_of('legend: off\nA\nB\nA > B: "x" [type: event]\n')
        self.assertFalse([n for n in ir["nodes"] if n["role"] == "legend"])

    def test_legend_does_not_pollute_flow_checks(self):
        ir = build_ir(FIXTURES / "ok_legend.diag")
        rep = validate_ir.validate(ir)
        self.assertEqual(rep.overall(), "PASS", rep.to_dict(False)["findings"])
        self.assertEqual(len(irlib.flow_nodes(ir)), 6)
        self.assertEqual(len(irlib.flow_edges(ir)), 6)

    def test_legend_cluster_does_not_count_as_a_sibling(self):
        text = "".join(f'G{i} [boundary: true] {{\n  N{i}a\n  N{i}b\n}}\nN{i}a > N{i}b: "lee" [type: event]\n' for i in range(5))
        rep = validate_ir.validate(ir_of(text))
        self.assertNotIn("CLU006", {f["id"] for f in rep.findings})

    def test_generated_code_is_valid_strict_and_uses_base_node(self):
        import tempfile
        from pathlib import Path
        ir = build_ir(FIXTURES / "ok_legend.diag")
        src = generate_diagram.generate(ir)
        self.assertIn("from diagrams import Cluster, Diagram, Edge, Node", src)
        self.assertEqual(src.count("**LEGEND_NODE"), 8)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "diagrams_src").mkdir()
            py = Path(tmp) / "diagrams_src" / "ok_legend.py"
            py.write_text(src)
            rep = validate_code.validate(py, ir)
        self.assertEqual(rep.overall(), "PASS", rep.to_dict(False)["findings"])

    def test_is_deterministic(self):
        a = generate_diagram.generate(build_ir(FIXTURES / "ok_legend.diag"))
        b = generate_diagram.generate(build_ir(FIXTURES / "ok_legend.diag"))
        self.assertEqual(a, b)

    def test_ir_with_legend_passes_the_schema(self):
        self.assertEqual(irlib.schema_errors(build_ir(FIXTURES / "ok_legend.diag")), [])


if __name__ == "__main__":
    unittest.main()
