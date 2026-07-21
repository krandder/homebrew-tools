#!/usr/bin/env python3
import hashlib
import pathlib
import re
import subprocess
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

    def test_formula_urls_pin_the_exact_current_sources(self):
        for name in ARTIFACTS:
            with self.subTest(artifact=name):
                source = (ROOT / name).read_bytes()
                formula = (ROOT / "Formula" / f"{name}.rb").read_text()
                match = re.search(
                    r'url "https://raw\.githubusercontent\.com/krandder/homebrew-tools/'
                    r'([0-9a-f]{40})/' + re.escape(name) + r'"\s*'
                    r'version "[^"]+"\s*sha256 "([0-9a-f]{64})"',
                    formula,
                )
                self.assertIsNotNone(
                    match, "formula must use an immutable canonical commit URL",
                )
                commit, pinned = match.groups()
                subprocess.run(
                    ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                    cwd=ROOT,
                    check=True,
                )
                downloaded = subprocess.check_output(
                    ["git", "show", f"{commit}:{name}"], cwd=ROOT,
                )
                self.assertEqual(hashlib.sha256(downloaded).hexdigest(), pinned)
                self.assertEqual(downloaded, source)

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

    def test_ai_token_formula_pins_the_current_claude_any_wrapper(self):
        source = (ROOT / "claude-any").read_bytes()
        formula = (ROOT / "Formula" / "ai-token.rb").read_text()
        match = re.search(
            r'resource "claude-any" do\s*'
            r'url "https://raw\.githubusercontent\.com/krandder/homebrew-tools/'
            r'([0-9a-f]{40})/claude-any"\s*sha256 "([0-9a-f]{64})"',
            formula,
        )
        self.assertIsNotNone(match, "claude-any must use an immutable canonical URL")
        commit, pinned = match.groups()
        downloaded = subprocess.check_output(
            ["git", "show", f"{commit}:claude-any"], cwd=ROOT,
        )
        self.assertEqual(hashlib.sha256(downloaded).hexdigest(), pinned)
        self.assertEqual(downloaded, source)


if __name__ == "__main__":
    unittest.main()
