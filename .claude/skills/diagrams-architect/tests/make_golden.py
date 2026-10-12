"""Regenera tests/golden/ a propósito (`make golden`). Úsalo solo si cambió el formato del generador."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_diagram  # noqa: E402
import irlib  # noqa: E402
from helpers import FIXTURES, GOLDEN, build_ir  # noqa: E402

ir = build_ir(FIXTURES / "ok_small.diag")
(GOLDEN / "ok_small.ir.json").write_text(irlib.dump_json(ir), encoding="utf-8")
(GOLDEN / "ok_small.py").write_text(generate_diagram.generate(ir), encoding="utf-8")
print("golden regenerado:", sorted(p.name for p in GOLDEN.iterdir()))
