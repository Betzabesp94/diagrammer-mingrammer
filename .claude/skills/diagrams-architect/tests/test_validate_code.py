import shutil
import tempfile
import unittest
from pathlib import Path

import mutate
import validate_code
from helpers import FIXTURES, GOLDEN, build_ir
import generate_diagram
import irlib


class Workspace(unittest.TestCase):
    """Genera ok_small en un directorio temporal con la misma estructura del repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "diagrams_src").mkdir()
        self.ir = build_ir(FIXTURES / "ok_small.diag")
        self.src = generate_diagram.generate(self.ir)

    def check(self, src=None, ir=None, **kw):
        path = self.tmp / "diagrams_src" / "ok_small.py"
        path.write_text(src if src is not None else self.src, encoding="utf-8")
        return validate_code.validate(path, ir if ir is not None else self.ir, **kw)

    def ids(self, rep):
        return {f["id"] for f in rep.findings}


class ValidateCodeStrict(Workspace):
    def test_generated_code_is_clean(self):
        rep = self.check()
        self.assertEqual(rep.overall(), "PASS", rep.to_dict(False)["findings"])

    def test_nested_and_ortho_fixtures_are_clean_or_only_expected(self):
        for name in ("ok_nested", "bad_orphan", "bad_ortho_label"):
            ir = build_ir(FIXTURES / f"{name}.diag")
            rep = self.check(generate_diagram.generate(ir), ir)
            self.assertEqual(rep.counts()["error"], 0, (name, rep.to_dict(False)["findings"]))

    def test_seeded_defects_are_detected(self):
        cases = [
            ("arista faltante", mutate.drop_edge, "FID004"),
            ("arista invertida", mutate.reverse_edge, "FID006"),
            ("etiqueta distinta", mutate.change_edge_label, "FID007"),
            ("arista no canónica", mutate.non_canonical_edge, "FID010"),
            ("nodo extra", mutate.extra_node, "FID002"),
            ("nodo faltante", mutate.remove_node, "FID001"),
            ("nodo en otro cluster", mutate.move_node_to_root, "FID008"),
            ("zona distinta", mutate.change_zone, "FID013"),
            ("sin nodeid", mutate.remove_nodeid, "FID010"),
            ("fontsize fuera de STYLE", mutate.inject_edge_fontsize, "STY002"),
            ("fontname literal fuera de STYLE", mutate.inject_font_literal, "STY002"),
            ("color hex suelto fuera de STYLE", mutate.inject_hex_outside_style, "STY001"),
            ("color= literal en una arista", mutate.inject_edge_color, "STY002"),
            ("cluster sin zona", mutate.cluster_without_zone, "STY005"),
            ("ortho con label", mutate.ortho_splines, "STY010"),
            ("fuente bloqueada", mutate.blocked_font, "CODE005"),
            ("import inexistente", mutate.break_import, "CODE002"),
            ("sin show=False", mutate.remove_show_false, "CODE004"),
        ]
        for name, fn, expected in cases:
            with self.subTest(name):
                rep = self.check(fn(self.src))
                self.assertIn(expected, self.ids(rep), rep.to_dict(False)["findings"])
                self.assertEqual(rep.overall(), "FAIL")

    def test_missing_style_markers(self):
        src = self.src.replace("# === STYLE ===\n", "").replace("# === END STYLE ===\n", "")
        self.assertIn("STY000", self.ids(self.check(src)))

    def test_syntax_error_stops_early(self):
        rep = self.check(self.src + "\ndef roto(:\n")
        self.assertEqual(self.ids(rep), {"CODE001"})

    def test_no_ir_warns(self):
        path = self.tmp / "diagrams_src" / "ok_small.py"
        path.write_text(self.src, encoding="utf-8")
        self.assertIn("FID000", {f["id"] for f in validate_code.validate(path, None).findings})

    def test_output_is_deterministic(self):
        src = mutate.drop_edge(self.src)
        self.assertEqual(self.check(src).to_dict(False), self.check(src).to_dict(False))


class ValidateCodeLenient(Workspace):
    def test_style_family_is_downgraded_to_info(self):
        rep = self.check(mutate.inject_hex_outside_style(self.src), strict=False)
        sev = {f["severity"] for f in rep.findings if f["id"].startswith("STY") and f["id"] != "STY010"}
        self.assertEqual(sev <= {"INFO"}, True)
        self.assertEqual(rep.counts()["error"], 0)

    def test_hard_rules_still_block_in_lenient(self):
        self.assertIn("CODE005", self.ids(self.check(mutate.blocked_font(self.src), strict=False)))
        self.assertIn("CODE002", self.ids(self.check(mutate.break_import(self.src), strict=False)))

    def test_lenient_aggregates_repeated_style_findings(self):
        rep = self.check(self.src.replace("# === STYLE ===", "# otra cosa"), strict=False)
        sty = [f for f in rep.findings if f["id"] == "STY000"]
        self.assertEqual(len(sty), 1)

    def test_arithmetic_minus_is_not_an_edge(self):
        src = self.src.replace("    # --- edges ---", "    n = 5 - 1\n    m = n - 2\n\n    # --- edges ---", 1)
        found = next(f for f in self.check(src, strict=False).findings if f["id"] == "FID020")["found"]
        self.assertEqual(found["edges"], 6)

    def test_edge_count_still_counts_real_minus_edges(self):
        found = next(f for f in self.check(self.src, strict=False).findings if f["id"] == "FID020")["found"]
        self.assertEqual((found["nodes"], found["edges"], found["clusters"]), (5, 6, 2))


if __name__ == "__main__":
    unittest.main()
