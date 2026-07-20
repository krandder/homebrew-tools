# Hosted CI enforcement — 2026-07-20

Repository: `krandder/homebrew-tools`; protected branch: `main`.

## First hosted red

Run `29769238303` executed the canonical `tools/build-release` gate on commit
`4b3f04ef7ef92c3e59cc73677f00dfadb90788cb`. It failed before artifact upload
because Node 24 appended a handler error to a truncated SSE stream. This was a
hosted-runtime-only reproduction of the proxy disconnect bug; the gate did not
retry or pass it through.

## Hosted green

Commit `9042e53f40aa8d8f79b5a6c55e09e868fa24a1f2` fixed the response boundary.
Run `29769477661` passed `release-gate` in 1m15s and uploaded artifact
`ai-token-vault-9042e53f40aa8d8f79b5a6c55e09e868fa24a1f2` (52,504 bytes),
retained until 2026-08-19.

## Branch enforcement

GitHub's branch-protection API then reported:

- required check: `release-gate`, pinned to GitHub Actions app id `15368`;
- strict status checks: enabled;
- enforcement for administrators: enabled;
- force pushes: disabled; and
- branch deletion: disabled.

The workflow also runs daily at 03:17 UTC and supports manual dispatch. This
evidence change itself is delivered through a protected-branch pull request,
so it must pass the newly required check before merge.
