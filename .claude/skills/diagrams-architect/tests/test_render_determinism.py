import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import check_determinism
import generate_diagram
import mutate
from helpers import FIXTURES, build_ir

HAS_DOT = shutil.which("dot") is not None


@unittest.skipUnless(HAS_DOT, "Graphviz no está instalado")
class RenderDeterminism(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "diagrams_src").mkdir()
        self.ir = build_ir(FIXTURES / "ok_nested.diag")
        self.py = self.tmp / "diagrams_src" / "ok_nested.py"
        self.py.write_text(generate_diagram.generate(self.ir), encoding="utf-8")

    def svg(self, seed="0", py=None):
        env = dict(os.environ, FORMAT="svg", PYTHONHASHSEED=seed)
        res = subprocess.run([sys.executable, str(py or self.py)], capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        return (self.tmp / "output" / "ok_nested.svg").read_bytes()

    def test_two_renders_are_byte_identical(self):
        self.assertEqual(self.svg(), self.svg())

    def test_independent_of_hash_seed(self):
        self.assertEqual(self.svg("0"), self.svg("999"))

    def test_node_ids_in_svg_are_the_ir_ids_not_uuids(self):
        svg = self.svg().decode()
        for n in self.ir["nodes"]:
            self.assertIn(f"<title>{n['id']}</title>", svg)

    def test_check_determinism_passes_on_generated_code(self):
        rep = check_determinism.validate(self.py, self.ir)
        self.assertEqual(rep.overall(), "PASS", rep.to_dict(False)["findings"])

    def test_editing_only_style_changes_the_render_and_is_info(self):
        before = self.svg()
        self.py.write_text(mutate.edit_style_only(self.py.read_text()), encoding="utf-8")
        after = self.svg()
        self.assertNotEqual(before, after)
        self.assertIn('font-size="14.00"', after.decode())
        rep = check_determinism.validate(self.py, self.ir, render=False)
        self.assertEqual([f["id"] for f in rep.findings], ["DET004"])
        self.assertEqual(rep.counts()["error"], 0)

    def test_editing_code_outside_style_is_an_error(self):
        self.py.write_text(self.py.read_text() + "\n# parche manual\n", encoding="utf-8")
        rep = check_determinism.validate(self.py, self.ir, render=False)
        self.assertEqual([f["id"] for f in rep.findings], ["DET001"])


if __name__ == "__main__":
    unittest.main()
