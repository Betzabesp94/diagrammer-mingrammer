"""Todo id de finding que emiten los scripts debe estar documentado en references/validations.md."""

import re
import unittest

from helpers import SCRIPTS, SKILL

ID_RE = re.compile(r'"((?:PAR|SCH|RES|CONN|CLU|SIZ|TXT|STY|CODE|FID|LAY|DET|ARQ)\d{3})"')
DOC = (SKILL / "references" / "validations.md").read_text(encoding="utf-8")


def documented():
    ids = set()
    for m in re.finditer(r"\b((?:PAR|SCH|RES|CONN|CLU|SIZ|TXT|STY|CODE|FID|LAY|DET|ARQ)\d{3})\b", DOC):
        ids.add(m.group(1))
    # rangos y pares escritos como 'STY001–STY004' o 'SIZ001 / SIZ002'
    for fam, a, b in re.findall(r"\b([A-Z]{3,4})(\d{3})[–-][A-Z]{3,4}(\d{3})\b", DOC):
        ids |= {f"{fam}{n:03d}" for n in range(int(a), int(b) + 1)}
    for fam, a, b in re.findall(r"\b([A-Z]{3,4})(\d{3}) / (?:[A-Z]{3,4})?(\d{3})\b", DOC):
        ids |= {f"{fam}{a}", f"{fam}{b}"}
    return ids


class Catalog(unittest.TestCase):
    def test_every_emitted_id_is_documented(self):
        emitted = {}
        for path in SCRIPTS.glob("*.py"):
            for fid in ID_RE.findall(path.read_text(encoding="utf-8")):
                emitted.setdefault(fid, path.name)
        missing = {fid: src for fid, src in emitted.items() if fid not in documented()}
        self.assertEqual(missing, {}, "ids sin documentar en validations.md")

    def test_every_documented_id_is_emitted_somewhere(self):
        text = "\n".join(p.read_text(encoding="utf-8") for p in SCRIPTS.glob("*.py"))
        ghosts = sorted(i for i in documented() if f'"{i}"' not in text)
        self.assertEqual(ghosts, [], "ids documentados que ningún script emite")


if __name__ == "__main__":
    unittest.main()
