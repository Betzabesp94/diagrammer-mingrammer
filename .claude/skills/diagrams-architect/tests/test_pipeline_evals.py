"""Corre evals/pipeline_evals.json: cada caso es verificable por script (ids de finding, no prosa)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import irlib
import mutate
import pipeline
import validate_code
import validate_layout
import check_determinism
from helpers import SKILL

EVALS = json.loads((SKILL / "evals" / "pipeline_evals.json").read_text(encoding="utf-8"))
HAS_DOT = shutil.which("dot") is not None
NEEDS_DOT = {"validate_layout", "check_determinism"}


def append_comment(src):
    return src + "\n# parche manual\n"


MUTATIONS = {"append_comment": append_comment, "ortho_label_kwarg": mutate.ortho_label_kwarg}


class PipelineEvals(unittest.TestCase):
    def run_case(self, case):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "diagrams_src").mkdir()
        src = SKILL / case["input"]
        diag = tmp / "diagrams_src" / src.name
        shutil.copy(src, diag)
        report = pipeline.run(diag, render=True)
        found = {f"{f['stage']}:{f['id']}" for f in report["findings"]}
        py = tmp / "diagrams_src" / f"{diag.stem}.py"
        ir_path = tmp / "diagrams_src" / f"{diag.stem}.ir.json"

        after = case.get("after")
        if after:
            py.write_text(MUTATIONS[after["mutate"]](py.read_text()), encoding="utf-8")
            ir = irlib.load_ir(ir_path)
            runners = {
                "validate_code": lambda: validate_code.validate(py, ir, strict=True),
                "validate_layout": lambda: validate_layout.validate(py, ir),
                "check_determinism": lambda: check_determinism.validate(py, ir),
            }
            for name in after["run"]:
                rep = runners[name]().to_dict(with_env=False)
                found |= {f"{name}:{f['id']}" for f in rep["findings"]}
        return report, found, py

    def test_cases(self):
        for case in EVALS["cases"]:
            expect = case["expect"]
            needs_dot = any(s in NEEDS_DOT for s in expect.get("stages", {})) or any(
                i.split(":")[0] in NEEDS_DOT for i in expect.get("include", [])
            ) or (case.get("after") and set(case["after"]["run"]) & NEEDS_DOT)
            with self.subTest(case["id"], title=case["title"]):
                if needs_dot and not HAS_DOT:
                    self.skipTest("Graphviz no está instalado")
                report, found, py = self.run_case(case)
                if "overall" in expect:
                    self.assertEqual(report["overall"], expect["overall"], report["findings"])
                for stage, status in expect.get("stages", {}).items():
                    self.assertEqual(report["stages"].get(stage), status, (stage, report["stages"]))
                for fid in expect.get("include", []):
                    self.assertIn(fid, found, sorted(found))
                for fid in expect.get("exclude", []):
                    self.assertNotIn(fid, found, sorted(found))
                for fid, prefix in expect.get("where_prefix", {}).items():
                    where = next(f["where"] for f in report["findings"] if f"{f['stage']}:{f['id']}" == fid)
                    self.assertTrue(where.startswith(prefix), where)
                if expect.get("no_py"):
                    self.assertFalse(py.exists(), "no debía generarse el .py")
                text = py.read_text() if py.exists() else ""
                for frag in expect.get("py_contains", []):
                    self.assertIn(frag, text)
                for frag in expect.get("py_not_contains", []):
                    self.assertNotIn(frag, text)
                if expect.get("mapping_not_generic"):
                    self.assertNotIn("generic", report["mapping"]["by_confidence"])


if __name__ == "__main__":
    unittest.main()
