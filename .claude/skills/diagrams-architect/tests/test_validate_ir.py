import unittest

import irlib
import validate_ir
from helpers import base_ir, cluster, edge, ids, mutated, node


def run(ir, **kw):
    return validate_ir.validate(ir, "mem", **kw)


class ValidateIR(unittest.TestCase):
    def test_base_is_clean(self):
        rep = run(base_ir())
        self.assertEqual(rep.overall(), "PASS", rep.to_dict(False)["findings"])

    def test_schema_errors(self):
        cases = {
            "falta campo": lambda ir: ir.pop("nodes"),
            "enum": lambda ir: ir["edges"][0].update(arrow="reverse"),
            "patron id": lambda ir: ir["nodes"][0].update(id="Web-1"),
            "campo desconocido": lambda ir: ir["nodes"][0].update(colour="rojo"),
            "version": lambda ir: ir.update(schema_version=1),
            "tipo": lambda ir: ir["clusters"][0].update(zone="0"),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertIn("SCH001", ids(run(mutated(fn))))

    def test_references(self):
        self.assertIn("SCH004", ids(run(mutated(lambda ir: ir["nodes"].append(node("web", cluster="vpc"))))))
        self.assertIn("SCH006", ids(run(mutated(lambda ir: ir["nodes"][0].update(cluster="nope")))))
        self.assertIn("SCH006", ids(run(mutated(lambda ir: ir["clusters"][0].update(parent="nope")))))
        self.assertIn("SCH005", ids(run(mutated(lambda ir: ir["clusters"].append(cluster("cluster_x", "X", zone=1))))))

        def cyc(ir):
            ir["clusters"] = [cluster("a", "A", parent="b"), cluster("b", "B", parent="a", zone=1)]
            for n in ir["nodes"]:
                n["cluster"] = "a"
        self.assertIn("SCH007", ids(run(mutated(cyc))))

    def test_connectivity(self):
        self.assertIn("CONN001", ids(run(mutated(lambda ir: ir["edges"].append(edge("e3", "api", "ghost"))))))
        self.assertIn("CONN002", ids(run(mutated(lambda ir: ir["edges"].append(edge("e3", "web", "api", "HTTPS"))))))
        self.assertIn("CONN004", ids(run(mutated(lambda ir: ir["edges"].append(edge("e3", "web", "web", "loop"))))))
        self.assertIn("CONN003", ids(run(mutated(lambda ir: ir["nodes"].append(node("lonely", cluster="vpc"))))))

    def test_standalone_not_orphan(self):
        ir = mutated(lambda ir: ir["nodes"].append(node("lonely", cluster="vpc", standalone=True)))
        self.assertNotIn("CONN003", ids(run(ir)))

    def test_clusters(self):
        def empty(ir):
            ir["clusters"].append(cluster("vacio", "Vacio", zone=1))
        self.assertIn("CLU001", ids(run(mutated(empty))))

        def single(ir):
            ir["clusters"].append(cluster("solo", "Solo", zone=1))
            ir["nodes"].append(node("x", cluster="solo"))
            ir["edges"].append(edge("e3", "web", "x", "lee"))
        self.assertIn("CLU002", ids(run(mutated(single))))

        def single_boundary(ir):
            single(ir)
            ir["clusters"][-1]["boundary"] = True
        self.assertNotIn("CLU002", ids(run(mutated(single_boundary))))

        def deep(ir):
            ir["clusters"] += [cluster("c2", "C2", parent="vpc", zone=1), cluster("c3", "C3", parent="c2", zone=2),
                               cluster("c4", "C4", parent="c3", zone=3)]
            ir["nodes"] += [node("a1", cluster="c4"), node("a2", cluster="c4")]
            ir["edges"].append(edge("e3", "a1", "a2", "lee"))
        self.assertIn("CLU003", ids(run(mutated(deep))))

        def dup(ir):
            ir["clusters"].append(cluster("otro", "VPC", zone=1))
            ir["nodes"].append(node("y", cluster="otro"))
            ir["edges"].append(edge("e3", "web", "y", "lee"))
        self.assertIn("CLU004", ids(run(mutated(dup))))

        def same_color(ir):
            ir["clusters"].append(cluster("otro", "Otro", zone=0, boundary=True))
            ir["nodes"].append(node("y", cluster="otro"))
            ir["edges"].append(edge("e3", "web", "y", "lee"))
        self.assertIn("CLU005", ids(run(mutated(same_color))))

    def test_six_siblings_is_error(self):
        def six(ir):
            ir["clusters"] = [cluster(f"c{i}", f"C{i}", zone=i % 5, boundary=True) for i in range(6)]
            ir["nodes"] = [node(f"n{i}", cluster=f"c{i}") for i in range(6)]
            ir["edges"] = [edge(f"e{i}", f"n{i}", f"n{i + 1}", "lee") for i in range(5)]
        rep = run(mutated(six))
        self.assertIn("CLU006", ids(rep))
        self.assertEqual(rep.overall(), "FAIL")

    def test_size(self):
        def big(ir):
            ir["nodes"] = [node(f"n{i}", cluster="vpc") for i in range(22)]
            ir["edges"] = [edge(f"e{i}", f"n{i % 22}", f"n{(i + 1) % 22}", "lee") for i in range(27)]
        got = ids(run(mutated(big)))
        self.assertIn("SIZ001", got)
        self.assertIn("SIZ002", got)

    def test_long_label_flags_overflow(self):
        ir = mutated(lambda ir: ir["nodes"][0].update(label_wrapped="Supercalifragilisticexpialidocious"))
        self.assertIn("TXT001", ids(run(ir)))

    def test_vague_edge_label(self):
        ir = mutated(lambda ir: ir["edges"][0].update(label="usa"))
        self.assertIn("TXT003", ids(run(ir)))

    def test_small_font(self):
        ir = mutated(lambda ir: ir.update(style_overrides={"FONT_SIZE_EDGE": "6"}))
        self.assertIn("TXT002", ids(run(ir)))

    def test_style_checks(self):
        self.assertIn("STY020", ids(run(mutated(lambda ir: ir.update(style_overrides={"FONT_FAMILY": "Comic Sans MS"})))))
        self.assertIn("STY021", ids(run(mutated(lambda ir: ir.update(style_overrides={"FONT_COLOR": "#CCCCCC"})))))
        zones7 = {"PALETTE": {"zones": ["#E8F1FA"] * 6}}
        self.assertIn("STY022", ids(run(mutated(lambda ir: ir.update(style_overrides=zones7)))))

    def test_default_palette_meets_wcag_aa(self):
        pal = irlib.DEFAULT_STYLE["PALETTE"]
        for bg in [pal["bg"], *pal["zones"]]:
            self.assertGreaterEqual(irlib.contrast_ratio(irlib.DEFAULT_STYLE["FONT_COLOR"], bg), 4.5)

    def test_output_is_deterministic(self):
        ir = mutated(lambda ir: ir["edges"].append(edge("e3", "ghost", "api")))
        a = run(ir).to_dict(with_env=False)
        b = run(ir).to_dict(with_env=False)
        self.assertEqual(a, b)

    def test_unsupported_and_extensions_are_reported(self):
        def ext(ir):
            ir["unsupported"] = [{"where": "edges[0]", "feature": "curva manual"}]
            ir["nodes"][0]["extensions"] = {"penwidth": "2"}
        got = ids(run(mutated(ext)))
        self.assertIn("RES010", got)
        self.assertIn("RES011", got)


    def test_flow_and_legibility(self):
        def hub(n_spokes, **edge_kw):
            def fn(ir):
                ir["nodes"] = [node("hub", cluster="vpc")] + [node(f"n{i}", cluster="vpc") for i in range(n_spokes)]
                ir["edges"] = [edge(f"e{i}", "hub", f"n{i}", **edge_kw) for i in range(n_spokes)]
            return fn
        self.assertNotIn("FLW003", ids(run(mutated(hub(7)))))
        self.assertIn("FLW003", ids(run(mutated(hub(8)))))
        self.assertIn("SIZ003", ids(run(mutated(hub(15)))))
        unmarked = ids(run(mutated(hub(8, label="lee"))))
        self.assertIn("FLW007", unmarked)
        self.assertNotIn("FLW001", unmarked)

        def main_flow(ir):  # 3 pasos principales con etiqueta y 1 secundaria con etiqueta
            hub(4, label="lee")(ir)
            for e in ir["edges"][:3]:
                e["emphasis"] = True
        got = run(mutated(main_flow)).to_dict(False)["findings"]
        flw = [f for f in got if f["id"] == "FLW001"]
        self.assertEqual(len(flw), 1)
        self.assertEqual(flw[0]["subject"], "e3")
        self.assertEqual(flw[0]["expected"], 3)
        self.assertNotIn("FLW001", ids(run(mutated(lambda ir: [e.update(emphasis=True) for e in ir["edges"]]))))
        self.assertIn("FLW004", ids(run(mutated(hub(3, arrow="both")))))
        self.assertNotIn("FLW004", ids(run(mutated(hub(2, arrow="both")))))
        long_label = run(mutated(lambda ir: ir["edges"][0].update(label="① envía la nota y la guía de estilo")))
        self.assertIn("FLW002", ids(long_label))
        short_label = run(mutated(lambda ir: ir["edges"][0].update(label="① consultas y decisiones del panel")))
        self.assertNotIn("FLW002", ids(short_label))

    def test_callouts_and_dashed_sources(self):
        note = {"shape": "note"}

        def callouts(ir):
            for i in range(3):
                ir["nodes"].append(node(f"nota{i}", cluster="vpc", extensions=note))
                ir["edges"].append(edge(f"a{i}", "api", f"nota{i}", arrow="none", extensions={"style": "dotted"}))
        got = ids(run(mutated(callouts)))
        self.assertIn("FLW005", got)
        self.assertNotIn("FLW003", got)  # las anclas de notas no cuentan como conexiones del hub

        def dashed(ir):
            for i in range(2):
                ir["nodes"].append(node(f"x{i}", cluster="vpc", extensions={"style": "dashed"}))
                ir["edges"].append(edge(f"d{i}", f"x{i}", "db"))
        self.assertIn("FLW006", ids(run(mutated(dashed))))

        def dashed_grouped(ir):
            dashed(ir)
            ir["clusters"].append(cluster("origen", "Origen a validar", zone=1, extensions={"style": "rounded,dashed"}))
            for n in ir["nodes"]:
                if n["id"].startswith("x"):
                    n["cluster"] = "origen"
        self.assertNotIn("FLW006", ids(run(mutated(dashed_grouped))))

        def hub_with_group(ir):  # 6 vecinos propios + 3 fuentes de un mismo cluster punteado = 7 conexiones
            ir["nodes"] = [node("hub", cluster="vpc")] + [node(f"n{i}", cluster="vpc") for i in range(6)]
            ir["edges"] = [edge(f"e{i}", "hub", f"n{i}") for i in range(6)]
            ir["clusters"].append(cluster("ext", "Externo", zone=1, extensions={"style": "dashed"}))
            for i in range(3):
                ir["nodes"].append(node(f"x{i}", cluster="ext"))
                ir["edges"].append(edge(f"g{i}", f"x{i}", "hub"))
        self.assertNotIn("FLW003", ids(run(mutated(hub_with_group))))


if __name__ == "__main__":
    unittest.main()
