#!/usr/bin/env python3
"""ai-as shared-state contract tests.

Catches the 2026-07-20 bug class: codex-<profile> wrappers run codex with a
per-profile HOME, so any state that lives under ~/.codex must be explicitly
shared or it silently splits (sessions invisible to `resume`, goals not
resuming). These tests assert the sharing contract holds for every profile
and that the wrapper's self-heal + logging code is still in place.

Run: python3 test_ai_as.py   (exit 1 on any failure; cron-daily on farol)
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

HOME = os.path.expanduser("~")
PROFILES = os.path.join(HOME, ".codex-profiles")
SHARED_CODEX = os.path.join(HOME, ".codex")
AI_AS = os.path.join(HOME, ".local/bin/ai-as")
AI_VAULT = os.path.join(HOME, ".local/bin/ai-vault")

failures = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        failures.append(label)


def profiles():
    if not os.path.isdir(PROFILES):
        return []
    return sorted(d for d in os.listdir(PROFILES)
                  if os.path.isdir(os.path.join(PROFILES, d)) and not d.startswith("."))


def main():
    profs = profiles()
    check(len(profs) >= 1, f"codex profiles discovered ({len(profs)}): {', '.join(profs)}")

    for p in profs:
        base = os.path.join(PROFILES, p, ".codex")
        # 1. sessions symlinked into the shared tree
        sdir = os.path.join(base, "sessions")
        check(os.path.islink(sdir)
              and os.path.realpath(sdir) == os.path.realpath(os.path.join(SHARED_CODEX, "sessions")),
              f"{p}: sessions -> shared tree")
        # 2. sessions content actually visible through the link
        try:
            visible = os.listdir(sdir)
            check(len(visible) > 0, f"{p}: sessions content visible through link ({len(visible)} entries)")
        except OSError as e:
            check(False, f"{p}: sessions unreadable: {e}")
        # 3. goals db trio linked to the same file
        for f in ("goals_1.sqlite", "goals_1.sqlite-shm", "goals_1.sqlite-wal"):
            g = os.path.join(base, f)
            shared = os.path.join(SHARED_CODEX, f)
            ok = (os.path.islink(g) and os.path.exists(shared)
                  and os.path.realpath(g) == os.path.realpath(shared))
            # -shm/-wal may legitimately not exist yet on the shared side; the
            # db file itself is the hard requirement.
            check(ok or (f != "goals_1.sqlite" and not os.path.exists(g)),
                  f"{p}: {f} -> shared goals db")

    # 4. shared goals db is the one every profile resolves to, and is readable
    gdb = os.path.join(SHARED_CODEX, "goals_1.sqlite")
    try:
        db = sqlite3.connect(f"file:{gdb}?mode=ro", uri=True)
        n = db.execute("SELECT COUNT(*) FROM thread_goals").fetchone()[0]
        check(n >= 1, f"shared goals db readable ({n} thread_goals)")
    except Exception as e:
        check(False, f"shared goals db readable: {e}")

    # 5. wrapper self-heal + logging still deployed (regression guard)
    src = open(AI_AS).read() if os.path.exists(AI_AS) else ""
    check("merged per-profile sessions into shared tree" in src, "ai-as: sessions self-heal present")
    check("goals_1.sqlite-shm" in src, "ai-as: goals self-heal present")
    check("log_ai_as" in src and "ai-as.log" in src, "ai-as: event logging present")

    # 6. vault stale/rotation guard still deployed (2026-07-20 leni regression)
    vsrc = open(AI_VAULT).read() if os.path.exists(AI_VAULT) else ""
    check("stale Claude credential snapshot rejected" in vsrc
          and "conflicting Claude credential rotation rejected" in vsrc,
          "ai-vault: stale/rotation push guard present")

    # 7. HOME normalization + loud-fail (2026-07-20 codex-adriana 401 incident):
    # a profile-flavored HOME (inside a claude-<p> session) must resolve to the
    # real base, and a missing credential must die loudly, not create an empty
    # profile.
    check('PROFILES_BASE="${HOME%/.claude-profiles/*}"' in src,
          "ai-as: HOME normalization present")
    import subprocess, tempfile, shutil
    fake = Path(tempfile.mkdtemp(prefix="ai-as-home-"))
    try:
        prof = fake / ".codex-profiles" / "adriana" / ".codex"
        prof.mkdir(parents=True)
        (prof / "auth.json").write_text(json.dumps({"tokens": {"access_token": "x", "refresh_token": "y"}}))
        (fake / ".codex-profiles" / "adriana" / ".role").write_text("follower")
        bin_dir = fake / "stubbin"   # NOT $PROFILES_BASE/bin — resolve_real_binary skips that
        bin_dir.mkdir()
        stub = bin_dir / "codex"
        stub.write_text("#!/usr/bin/env bash\necho \"STUB-HOME=$HOME\"\n")
        stub.chmod(0o755)
        link_dir = fake / "links"    # symlink form must live apart from the stub binary
        link_dir.mkdir()
        (link_dir / "codex-adriana").symlink_to(AI_AS)
        env = dict(os.environ)
        env["HOME"] = str(fake / ".claude-profiles" / "azsantos")
        (fake / ".claude-profiles" / "azsantos").mkdir(parents=True)
        base_path = str(bin_dir) + ":" + env.get("PATH", "")
        env["PATH"] = base_path
        r = subprocess.run(["bash", AI_AS, "codex", "adriana"], env=env,
                           capture_output=True, text=True, timeout=30)
        check("STUB-HOME=" + str(fake / ".codex-profiles" / "adriana") in r.stdout,
              "ai-as normalizes profile-flavored HOME (direct form)")
        env["PATH"] = str(link_dir) + ":" + base_path
        r = subprocess.run(["codex-adriana"], env=env,
                           capture_output=True, text=True, timeout=30)
        check("STUB-HOME=" + str(fake / ".codex-profiles" / "adriana") in r.stdout,
              "ai-as normalizes profile-flavored HOME (symlink form)")
        r2 = subprocess.run(["bash", AI_AS, "codex", "noprof"], env=env,
                            capture_output=True, text=True, timeout=30)
        check(r2.returncode == 1 and "no codex auth" in r2.stderr,
              "ai-as fails loudly on missing codex auth")
        check(not (fake / ".codex-profiles" / "noprof").exists(),
              "ai-as must not silently create an empty profile")
    finally:
        shutil.rmtree(fake, ignore_errors=True)

    print(f"\n{len(failures)} failure(s)" if failures else "\nai-as contract tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
