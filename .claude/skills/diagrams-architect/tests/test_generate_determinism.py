import ast
import os
import re
import subprocess
import sys
import unittest

import generate_diagram
import irlib
from helpers import FIXTURES, GOLDEN, SCRIPTS, build_ir


class GenerateDeterminism(unittest.TestCase):
    def setUp(self):
        self.ir = build_ir(FIXTURES / "ok_small.diag")

    def test_same_ir_same_bytes(self):
        a = generate_diagram.generate(self.ir).encode()
        b = generate_diagram.generate(build_ir(FIXTURES / "ok_small.diag")).encode()
        self.assertEqual(a, b)

    def test_matches_golden(self):
        self.assertEqual(generate_diagram.generate(self.ir), (GOLDEN / "ok_small.py").read_text(),
                         "el formato cambió: si es a propósito, ejecuta `make golden`")
        self.assertEqual(irlib.dump_json(self.ir), (GOLDEN / "ok_small.ir.json").read_text())

    def test_independent_of_hash_seed(self):
        outs = []
        for seed in ("0", "1", "12345"):
            res = subprocess.run(
                [sys.executable, str(SCRIPTS / "generate_diagram.py"), str(GOLDEN / "ok_small.ir.json")],
                capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": seed},
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            outs.append(res.stdout)
        self.assertEqual(len(set(outs)), 1)

    def test_no_timestamps_versions_or_absolute_paths(self):
        src = generate_diagram.generate(self.ir)
        self.assertNotRegex(src, r"\d{4}-\d{2}-\d{2}")
        self.assertNotRegex(src, r"\b\d+\.\d+\.\d+\b")
        self.assertNotIn("/Users/", src)
        self.assertNotIn("uuid", src)

    def test_fixed_section_order(self):
        src = generate_diagram.generate(self.ir)
        marks = ["import os", "# === OUTPUT ===", "# === STYLE ===", "# === END STYLE ===", "def zone(",
                 "with Diagram(", "# --- edges ---"]
        positions = [src.index(m) for m in marks]
        self.assertEqual(positions, sorted(positions))

    def test_output_is_valid_python_with_repo_conventions(self):
        src = generate_diagram.generate(self.ir)
        ast.parse(src)
        self.assertRegex(src, r'OUT = Path\(__file__\)\.resolve\(\)\.parent\.parent / "output" / "ok_small"')
        self.assertIn('FMT = os.getenv("FORMAT", "png")', src)
        self.assertIn("show=False", src)
        self.assertIn("nodeid=", src)

    def test_style_has_the_required_variables(self):
        src = generate_diagram.generate(self.ir)
        block = src[src.index("# === STYLE ==="):src.index("# === END STYLE ===")]
        for name in ("FONT_FAMILY", "FONT_SIZE_TITLE", "FONT_SIZE_CLUSTER", "FONT_SIZE_NODE", "FONT_SIZE_EDGE",
                     "PALETTE", "DIRECTION", "NODESEP", "RANKSEP", "SPLINES"):
            with self.subTest(name):
                self.assertRegex(block, rf"(?m)^{name}\s*=")

    def test_every_cluster_gets_an_explicit_zone(self):
        src = generate_diagram.generate(build_ir(FIXTURES / "ok_nested.diag"))
        self.assertEqual(len(re.findall(r"with Cluster\(", src)), len(re.findall(r"graph_attr=zone\(\d", src)))

    def test_xlabel_only_with_ortho(self):
        spline = generate_diagram.generate(build_ir(FIXTURES / "ok_small.diag"))
        ortho = generate_diagram.generate(build_ir(FIXTURES / "bad_ortho_label.diag"))
        self.assertIn("link(label=", spline)
        self.assertNotIn("xlabel", spline)
        self.assertIn("xlabel=", ortho)
        self.assertNotRegex(ortho, r"link\([^)]*\blabel=")

    def test_extensions_are_promoted_into_style(self):
        import parse_dsl, resolve_ir
        ir = resolve_ir.resolve(parse_dsl.parse('A [icon: aws-ec2, gv.penwidth: 2, gv.peripheries: 2]\nB\nA > B: "lee"\n', "t"))
        src = generate_diagram.generate(ir)
        style = src[src.index("# === STYLE ==="):src.index("# === END STYLE ===")]
        self.assertIn('EXT_A_PENWIDTH = "2"', style)      # atributo de estilo -> constante en STYLE
        self.assertIn("penwidth=EXT_A_PENWIDTH", src)
        self.assertIn('peripheries="2"', src)             # no es de estilo -> literal en el call site
        self.assertNotIn("EXT_A_PERIPHERIES", src)


if __name__ == "__main__":
    unittest.main()
