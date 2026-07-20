#!/usr/bin/env python3
"""Hermetic tests for imgpush and kimg (the Mac <-> farol image bridge).

kimg runs against a tmp KIMG_DIR. imgpush is driven with fake osascript / ssh
/ scp stubs placed first in PATH: the fake osascript serves a canned
`clipboard info` answer and "writes" the clipboard PNG by copying a fixture to
the output path imgpush hands to the heredoc form. Deterministic; no macOS,
no network, no real /tmp/kimi-images.
"""

import base64
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

OSASCRIPT_STUB = """#!/usr/bin/env bash
# argv[1] == "-e"  -> `clipboard info` query: print the canned answer.
# otherwise        -> heredoc form `osascript - <out>`: "write" the clipboard PNG.
if [ "${1:-}" = "-e" ]; then
  cat "$CAP_DIR/clipboard-info"
else
  out=""
  for a in "$@"; do out="$a"; done
  cp "$CAP_DIR/fixture.png" "$out"
fi
"""

RECORDER_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$CAP_DIR/__NAME__.argv"
"""


class KimgTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "kimi-images"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, mtime):
        path = self.dir / name
        path.write_bytes(b"x")
        os.utime(path, (mtime, mtime))
        return path

    def run_kimg(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "KIMG_DIR": str(self.dir)}
        return subprocess.run(["bash", str(ROOT / "kimg")],
                              env=env, text=True, capture_output=True, timeout=30)

    def test_newest_png_wins(self):
        self.dir.mkdir()
        self.write("a.png", mtime=time.time() - 100)
        newest = self.write("b.png", mtime=time.time())
        result = self.run_kimg()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(newest))

    def test_non_image_files_are_ignored(self):
        self.dir.mkdir()
        png = self.write("a.png", mtime=time.time() - 100)
        self.write("notes.txt", mtime=time.time())
        result = self.run_kimg()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(png))

    def test_empty_dir(self):
        self.dir.mkdir()
        result = self.run_kimg()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no images", result.stderr)

    def test_missing_dir(self):
        result = self.run_kimg()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no images", result.stderr)


class ImgpushTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.cap = base / "cap"
        self.stubbin = base / "bin"
        self.cap.mkdir()
        self.stubbin.mkdir()
        (self.cap / "fixture.png").write_bytes(PNG_1X1)
        for name, body in (("osascript", OSASCRIPT_STUB),
                           ("ssh", RECORDER_STUB.replace("__NAME__", "ssh")),
                           ("scp", RECORDER_STUB.replace("__NAME__", "scp"))):
            path = self.stubbin / name
            path.write_text(body)
            path.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_imgpush(self, clipboard_info):
        (self.cap / "clipboard-info").write_text(clipboard_info)
        env = {
            "PATH": f"{self.stubbin}:/usr/bin:/bin",
            "HOME": str(self.cap),
            "CAP_DIR": str(self.cap),
        }
        return subprocess.run(["bash", str(ROOT / "imgpush")],
                              env=env, text=True, capture_output=True, timeout=30)

    def test_no_image_in_clipboard_fails(self):
        result = self.run_imgpush("«class RTF », «class utf8»\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no image", result.stderr)
        self.assertFalse((self.cap / "scp.argv").exists(),
                         "scp must not run when the clipboard has no image")

    def test_image_is_pushed_to_farol(self):
        result = self.run_imgpush("«class PNGf», «class utf8»\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^/tmp/kimi-images/\d{8}-\d{6}\.png$")
        ssh_argv = (self.cap / "ssh.argv").read_text().splitlines()
        self.assertEqual(ssh_argv, ["farol", "mkdir -p /tmp/kimi-images"])
        scp_argv = (self.cap / "scp.argv").read_text().splitlines()
        self.assertEqual(scp_argv[0], "-q")
        self.assertRegex(scp_argv[-1], r"^farol:/tmp/kimi-images/\d{8}-\d{6}\.png$")
        self.assertFalse(Path(scp_argv[1]).exists(),
                         "imgpush must remove its local temp file after the push")


if __name__ == "__main__":
    unittest.main()
