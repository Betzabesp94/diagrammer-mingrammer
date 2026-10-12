"""Los diagramas escritos a mano (diagrams_src/, ignorado por git) no deben romperse."""

import unittest

import validate_code
from helpers import REPO

SRC = REPO / "diagrams_src"
FILES = sorted(SRC.glob("*.py")) if SRC.is_dir() else []


@unittest.skipUnless(FILES, "no hay diagramas de usuario en diagrams_src/ (normal en un clone nuevo)")
class UserDiagramsStillPass(unittest.TestCase):
    def test_no_errors_in_lenient_mode(self):
        for path in FILES:
            with self.subTest(path.name):
                rep = validate_code.validate(path, None, strict=False)
                errors = [f for f in rep.findings if f["severity"] == "ERROR"]
                self.assertEqual(errors, [], errors)

    def test_hand_written_files_are_not_detected_as_generated(self):
        for path in FILES:
            self.assertNotIn(validate_code.GENERATED_MARK, path.read_text()[:400])


if __name__ == "__main__":
    unittest.main()
