#!/usr/bin/env python3
import hashlib
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACTS = ("ai-token", "ai-vault", "ai-vault-http")


class FormulaIntegrityTest(unittest.TestCase):
    def test_formula_hashes_match_sources(self):
        for name in ARTIFACTS:
            with self.subTest(artifact=name):
                source = ROOT / name
                formula = (ROOT / "Formula" / f"{name}.rb").read_text()
                match = re.search(r'^\s*sha256 "([0-9a-f]{64})"$', formula, re.MULTILINE)
                self.assertIsNotNone(match, "formula must pin a sha256")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), match.group(1))


if __name__ == "__main__":
    unittest.main()
