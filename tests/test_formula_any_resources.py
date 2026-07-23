#!/usr/bin/env python3
"""The ai-token formula must ship exactly the any-proxies this repo ships.

For each changed -any wrapper/proxy resource in Formula/ai-token.rb: the pinned URL
commit must be reachable in the local git object store, the pinned sha256
must match the file at that commit, and — the drift guard — it must also
match the file at HEAD. A proxy change that lands without a formula re-pin
turns this test red; the re-pin turns it green. Hermetic: the local git
object store only, no network.
"""

import hashlib
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESOURCES = ("claude-any", "codex-any",
             "any-proxy.mjs", "codex-any-proxy.mjs", "kimi-any-proxy.mjs")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class FormulaAnyProxyResourcesTest(unittest.TestCase):
    def test_any_resources_pin_the_repo_files(self):
        formula = (ROOT / "Formula" / "ai-token.rb").read_text()
        for name in RESOURCES:
            with self.subTest(resource=name):
                match = re.search(
                    r'resource "' + re.escape(name) + r'" do\s*'
                    r'url "https://raw\.githubusercontent\.com/krandder/homebrew-tools/([0-9a-f]{40})/'
                    + re.escape(name) + r'"\s*sha256 "([0-9a-f]{64})"',
                    formula)
                self.assertIsNotNone(match, f"formula must pin {name} with an immutable commit URL + sha256")
                commit, pinned = match.group(1), match.group(2)
                subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                               cwd=ROOT, check=True)
                at_pin = git("show", f"{commit}:{name}")
                self.assertEqual(sha256(at_pin), pinned,
                                 "pinned sha256 must match the file at the pinned commit")
                at_head = git("show", f"HEAD:{name}")
                self.assertEqual(sha256(at_head), pinned,
                                 f"formula ships a stale {name}: re-pin the resource to the repo's proxy")


if __name__ == "__main__":
    unittest.main()
