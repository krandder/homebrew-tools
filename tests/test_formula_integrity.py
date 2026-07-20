#!/usr/bin/env python3
import hashlib
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACTS = ("ai-token", "ai-vault", "ai-vault-http", "claude-token", "codex-token")


class FormulaIntegrityTest(unittest.TestCase):
    def test_formula_hashes_match_sources(self):
        for name in ARTIFACTS:
            with self.subTest(artifact=name):
                source = ROOT / name
                formula = (ROOT / "Formula" / f"{name}.rb").read_text()
                match = re.search(r'^\s*sha256 "([0-9a-f]{64})"$', formula, re.MULTILINE)
                self.assertIsNotNone(match, "formula must pin a sha256")
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), match.group(1))

    def test_ai_token_and_compatibility_formula_versions_match_canonical_source(self):
        source = (ROOT / "ai-token").read_text()
        version = re.search(r'^VERSION="([^"]+)"$', source, re.MULTILINE).group(1)

        def parts(text):
            return tuple(int(piece) for piece in text.split("."))

        for name in ("ai-token", "claude-token", "codex-token"):
            with self.subTest(formula=name):
                formula = (ROOT / "Formula" / f"{name}.rb").read_text()
                packaged = re.search(r'^\s*version "([^"]+)"$', formula, re.MULTILINE).group(1)
                if name == "ai-token":
                    # Since 3.1.0 the ai-token formula also packages the -any
                    # failover stack, so the formula version may be ahead of
                    # the ai-token script's VERSION (but never behind).
                    self.assertGreaterEqual(parts(packaged), parts(version))
                else:
                    self.assertEqual(packaged, version)


if __name__ == "__main__":
    unittest.main()
