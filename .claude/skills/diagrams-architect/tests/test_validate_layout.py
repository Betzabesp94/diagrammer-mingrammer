import shutil
import tempfile
import unittest
from pathlib import Path

import generate_diagram
import irlib
import mutate
import validate_layout as vl
from helpers import FIXTURES, build_ir

HAS_DOT = shutil.which("dot") is not None


class GeometryHelpers(unittest.TestCase):
    def test_rect_overlap(self):
        self.assertTrue(vl.rect_overlap((0, 0, 10, 10), (5, 5, 15, 15)))
        self.assertFalse(vl.rect_overlap((0, 0, 10, 10), (10.5, 0, 20, 10)))   # solo se tocan
        self.assertFalse(vl.rect_overlap((0, 0, 10, 10), (0, 20, 10, 30)))

    def test_segments_cross(self):
        self.assertTrue(vl.segments_cross((0, 0), (10, 10), (0, 10), (10, 0)))
        self.assertFalse(vl.segments_cross((0, 0), (10, 0), (0, 5), (10, 5)))

    def test_text_rects_measure_width_and_fonts(self):
        ops = [{"op": "F", "size": 12.0, "face": "Helvetica"},
               {"op": "T", "pt": [50.0, 20.0], "align": "c", "width": 40.0, "text": "x"}]
        rects, widest, fonts = vl.text_rects(ops)
        self.assertEqual((widest, fonts), (40.0, [12.0]))
        self.assertEqual((rects[0][0], rects[0][2]), (30.0, 70.0))

    def test_count_crossings_ignores_edges_sharing_an_endpoint(self):
        names = {1: "a", 2: "b", 3: "c", 4: "d"}
        def edge(t, h, pts):
            return {"tail": t, "head": h, "_draw_": [{"op": "b", "points": pts}]}
        cross = [edge(1, 2, [[0, 0], [10, 10]]), edge(3, 4, [[0, 10], [10, 0]])]
        shared = [edge(1, 2, [[0, 0], [10, 10]]), edge(1, 4, [[0, 10], [10, 0]])]
        self.assertEqual(vl.count_crossings(cross, names), 1)
        self.assertEqual(vl.count_crossings(shared, names), 0)


@unittest.skipUnless(HAS_DOT, "Graphviz no está instalado")
class LayoutOnRealDiagrams(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "diagrams_src").mkdir()

    def layout(self, name, mutation=None, ir_edit=None, **style):
        ir = build_ir(FIXTURES / f"{name}.diag")
        ir["style_overrides"].update(style)
        src = generate_diagram.generate(ir)
        if mutation:
            src = mutation(src)
        py = self.tmp / "diagrams_src" / f"{ir['slug']}.py"
        py.write_text(src, encoding="utf-8")
        if ir_edit:
            ir_edit(ir)
        return vl.validate(py, ir)

    def ids(self, rep):
        return {f["id"] for f in rep.findings}

    def test_clean_diagrams_have_no_warnings(self):
        for name in ("ok_small", "ok_nested"):
            rep = self.layout(name)
            self.assertEqual(rep.overall(), "PASS", (name, rep.to_dict(False)["findings"]))
            self.assertIn("LAY100", self.ids(rep))

    def test_overflowing_label_is_measured(self):
        rep = self.layout("bad_long_label")
        f = next(f for f in rep.findings if f["id"] == "LAY003")
        self.assertGreater(f["found"], f["expected"])

    def test_ortho_with_label_reintroduced_triggers_dot_warning(self):
        rep = self.layout("bad_ortho_label", mutation=mutate.ortho_label_kwarg)
        self.assertIn("LAY010", self.ids(rep))

    def test_generated_xlabel_does_not_trigger_the_warning(self):
        self.assertNotIn("LAY010", self.ids(self.layout("bad_ortho_label")))

    def test_cluster_membership_mismatch_is_an_error(self):
        def move(ir):
            ir["nodes"][1]["cluster"] = None   # el IR dice otra cosa que el código
        rep = self.layout("ok_nested", ir_edit=move)
        self.assertIn("LAY004", self.ids(rep))
        self.assertEqual(rep.overall(), "FAIL")

    def test_huge_canvas_is_flagged(self):
        self.assertIn("LAY008", self.ids(self.layout("bad_big")))

    def test_unreadable_font_is_flagged(self):
        self.assertIn("LAY007", self.ids(self.layout("ok_small", FONT_SIZE_EDGE="6")))

    def test_output_is_deterministic(self):
        a = self.layout("ok_nested").to_dict(with_env=False)
        b = self.layout("ok_nested").to_dict(with_env=False)
        self.assertEqual(a, b)


class NoGraphviz(unittest.TestCase):
    def test_missing_dot_is_info_not_failure(self):
        import os
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            rep = vl.validate(Path("/nonexistent.py"), None)
        finally:
            os.environ["PATH"] = old
        self.assertEqual([f["id"] for f in rep.findings], ["LAY000"])
        self.assertEqual(rep.overall(), "WARN" if rep.counts()["warning"] else "PASS")


if __name__ == "__main__":
    unittest.main()
