import json
import os
import subprocess
import sys
import unittest

import validate_architecture as va
from helpers import FIXTURES, SCRIPTS, base_ir, build_ir, edge, mutated, node


def ids(rep):
    return [f["id"] for f in rep.to_dict(with_env=False)["findings"]]


def with_constraints(**c):
    def fn(ir):
        ir["constraints"] = c
    return fn


class ValidateArchitecture(unittest.TestCase):
    def test_never_emits_an_error(self):
        rep = va.validate(build_ir(FIXTURES / "bad_architecture.diag"))
        self.assertEqual(rep.counts()["error"], 0)

    def test_bad_design_is_flagged(self):
        got = ids(va.validate(build_ir(FIXTURES / "bad_architecture.diag")))
        self.assertIn("ARQ001", got)   # Web y Batch no reciben tráfico
        self.assertIn("ARQ002", got)   # el entrypoint conecta directo a la base de datos
        self.assertIn("ARQ003", got)   # producción sin multi_az
        self.assertIn("ARQ004", got)   # sin monitoreo

    def test_good_reference_has_no_warnings(self):
        from pathlib import Path
        from helpers import REPO
        ir = build_ir(REPO / "diagrams_ref" / "ejemplo_aws.diag")
        rep = va.validate(ir)
        self.assertEqual(rep.counts()["warning"], 0, rep.to_dict(False)["findings"])

    def test_missing_entrypoint_is_reported_not_skipped_silently(self):
        self.assertEqual(ids(va.validate(base_ir())), ["ARQ010"])

    def test_isolated_node_is_reported(self):
        ir = mutated(lambda ir: (with_constraints(internet_entrypoint="web")(ir), ir["nodes"].append(node("solo", cluster="vpc"))))
        rep = va.validate(ir)
        f = next(f for f in rep.findings if f["id"] == "ARQ001")
        self.assertIn("solo", f["found"])

    def test_skip_isolated_leaves_them_to_conn003(self):
        ir = mutated(lambda ir: (with_constraints(internet_entrypoint="web")(ir), ir["nodes"].append(node("solo", cluster="vpc"))))
        self.assertNotIn("ARQ001", ids(va.validate(ir, skip_isolated=True)))

    def test_standalone_node_is_not_flagged(self):
        ir = mutated(lambda ir: (with_constraints(internet_entrypoint="web")(ir),
                                 ir["nodes"].append(node("solo", cluster="vpc", standalone=True))))
        self.assertNotIn("ARQ001", ids(va.validate(ir)))

    def test_bidirectional_edge_makes_both_ends_reachable(self):
        def fn(ir):
            with_constraints(internet_entrypoint="web")(ir)
            ir["nodes"].append(node("peer", cluster="vpc"))
            ir["edges"].append(edge("e3", "web", "peer", "sincroniza", arrow="both"))
        ir = mutated(fn)
        self.assertNotIn("ARQ001", ids(va.validate(ir)))

    def test_multi_az_tag_silences_availability(self):
        def fn(ir):
            with_constraints(internet_entrypoint="web", production=True)(ir)
            ir["nodes"][2]["tags"] = {"multi_az": True}
        self.assertNotIn("ARQ003", ids(va.validate(mutated(fn))))

    def test_production_word_boundaries(self):
        """'product' (como en 'productos') no debe activar el modo productivo."""
        ir = mutated(with_constraints(notes="catálogo de productos"))
        self.assertFalse(va.is_production(ir))
        self.assertTrue(va.is_production(mutated(with_constraints(notes="entorno de producción"))))

    def test_message_order_is_independent_of_hash_seed(self):
        ir = build_ir(FIXTURES / "bad_architecture.diag")
        from helpers import REPO
        path = REPO / "output" / "_arch_seed_test.ir.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(ir), encoding="utf-8")
        self.addCleanup(path.unlink)
        outs = set()
        for seed in ("0", "1", "42", "999"):
            res = subprocess.run([sys.executable, str(SCRIPTS / "validate_architecture.py"), str(path)],
                                 capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": seed})
            outs.add(res.stdout)
        self.assertEqual(len(outs), 1)

    def test_not_in_service_role_nodes_are_ignored(self):
        ir = build_ir(FIXTURES / "ok_legend.diag")
        self.assertEqual([f for f in va.validate(ir).findings if f["id"] == "ARQ001"], [])


if __name__ == "__main__":
    unittest.main()
