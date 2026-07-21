#!/usr/bin/env python3
"""Formula-installed wrappers must be repo files, never symlink write targets."""

import os
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMULA = (ROOT / "Formula/ai-token.rb").read_text()


def has_symlink_component(path):
    return any(part.is_symlink() for part in (path, *path.parents))


class WrapperFilesTest(unittest.TestCase):
    def test_formula_bin_sources_are_real_files(self):
        names = re.findall(r'bin\.install "([^"]+)"', FORMULA)
        names += re.search(r'%w\[(.*?)\]\.each \{ \|tool\| bin\.install resource\(tool\) \}', FORMULA, re.S).group(1).split()
        for name in names:
            with self.subTest(name=name):
                path = ROOT / name
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertFalse(has_symlink_component(path))


if os.environ.get("LIVE") == "1":
    class LiveKimiWrapperFilesTest(unittest.TestCase):
        def test_live_kimi_wrappers_are_real_files(self):
            for name in ("kimi", "kimi-any"):
                with self.subTest(name=name):
                    path = Path.home() / ".local/bin" / name
                    self.assertTrue(path.is_file())
                    self.assertFalse(path.is_symlink())
                    self.assertFalse(has_symlink_component(path))
