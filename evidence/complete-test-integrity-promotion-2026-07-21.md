# Complete test-integrity promotion — 2026-07-21

No production profile, human credential, credential value, credential hash,
pairing secret, or Keychain password was used or recorded. Live verification
used only the isolated `canary-claude` account and stores.

## Red-first enforcement proof

PR #56 preserved two remaining integrity failures in red commit `0f9aba1`:
green production could rewrite a non-runnable fixture under `tests/`, and the
complete suite accepted unittest skips or expected failures. Green commit
`21afc47` protects every file in the test tree, adds a strict standard-library
unittest launcher, removes both environment-dependent skip paths, and gives
the Claude wrapper test an isolated loopback port. Branch/PR runs
`29847925766` and `29847929088`, plus protected-main run `29848163158`, passed.

Independent comparison of that hosted artifact then found a release-boundary
failure: the changed `claude-any` wrapper was not classified as production,
was absent from the immutable artifact, and the Homebrew formula still pinned
the prior bytes. PR #57 preserved all three failures in red commit `30257bd`
and fixed them in green commit `f802bf4`. Branch/PR runs `29848864288` and
`29848866943`, plus protected-main run `29849180132`, passed. The complete gate
now runs 218 Python tests and four shell integration suites with skips and
expected failures treated as failures.

## Protected release

- Merge commit: `ed994de4434eb82d5c08cb41d8738a835e657a3d`.
- Tree: `6a332a1f0515c8b8536d253c0ee3ab7df5c8be09`.
- Release: `ed994de4434e-5179f403c404`.
- Archive SHA-256:
  `5179f403c404ae9396f871a6ee4b767a6674a60f0482ee2b51cb0f43b5f3fc6a`.
- Manifest: 33 verified regular files with normalized 0644/0755 modes.

The protected-main artifact independently matched its external checksum,
commit, tree, member digests, modes, and formula pin. Relative to the prior
deployed release, only `Formula/ai-token.rb`, `claude-any`,
`tools/build-release`, and `tools/verify-tdd-history` changed. Credential,
vault, lifecycle, canary, scheduler, and deployment-unit bytes are identical.

## Three-host reversible promotion

Farol, agent-1, and dedicated macOS UID 502 each installed and verified the
new 33-file release, rolled back to `0f235c2aecce-e2ce134f3805`, verified the
old 32-file release, restored, and verified the new release again. Agent-1 and
macOS initially rejected an archive staged without its external checksum;
installation had not begun, and the complete sequence passed after the
checksum was staged. Each mode-0600 config then atomically changed only
`expect_commit`; the isolated Farol user vault restarted active with result
success and exit status zero.

The manual authority-ordered live matrix passed:

- Farol leader:
  `20260721T164333.342312Z-farol-leader-3870380.json`;
- agent-1 follower:
  `20260721T164339.768734Z-agent-1-follower-35662.json`;
- macOS dedicated follower:
  `20260721T164346.288012Z-Kelvins-MacBook-Air-follower-78694.json`.

Each is a mode-0600 schema-3 record on the exact profile, commit, and release,
with the exact role-specific successful step sequence and a verified immediate
predecessor filename/hash. Atomic collection retained 70 records: 26 from
Farol, 22 from agent-1, and 22 from macOS. Sanitized post-promotion telemetry
contained zero canary 429/rate-limit/cooldown events. The cumulative auditor
correctly returned `no completed soak day`.

Farol's two-hour timer, daily audit timer, isolated vault, agent-1's daily
timer, and the macOS dispatcher remain enabled/active as applicable; the Mac
dispatcher retains last exit zero and its dedicated activation marker. Public
remote staging artifacts and the temporary atomic config helper were removed.

The clean 30-day window is pinned to `ed994de4434e-5179f403c404` for July 22
through August 20 UTC. A real unattended Farol leader run remains required on
this final pin before July 22; post-window anchors, final audits, and the final
physical rollback/restore remain due August 21 UTC.
