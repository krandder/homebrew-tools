# Goal coverage audit — 2026-07-20

This audit compares the authoritative goal with current canonical tests and
deployed evidence. A green unit test is not treated as proof of a physical
deployment.

At this audit point the clean local release gate passes 108 Python tests and
four shell integration suites.

## Proven in canonical CI

- M1's hermetic laboratory covers loopback OAuth/API behavior, injected time,
  concurrency, temporary stores, restricted service paths, 401/429/5xx,
  rotation, gzip/framing, SSE disconnects, crashes, and legacy clients without
  personal credentials.
- Every named M2 incident class has a permanent test. The final weak spot was
  proxy topology: `test_ai_token_proxy.py` now proves a running process creates
  a newly registered profile listener without restarting, then proves a clean
  process restart rebinds the registry and still injects the latest token.
- The owner/leader/follower matrix exercises Claude, Codex, and Kimi, two
  profiles, two followers, HTTP and forced-command SSH, rotation, revocation,
  follower launch, and old-writer rejection.
- M3 now models all named authority, generation, expiry, refresh, sync/handoff,
  takeover, failure, relogin, and recovery transitions. Deterministic tests
  cover the accepted/rejected outcome set for all 12 declared transitions,
  20,000 generated events preserve the invariants, crash tests surround atomic
  replacement, and all 18 selected safety mutants are killed.
- M4 is enforced by strict GitHub branch protection, the blocking complete
  suite, clean-tree deterministic packaging, checksums, formula pins, and
  content-addressed installation/verification/rollback.
- M5 has a guarded live runner but only hermetic execution evidence.
- M6 now has an executable consecutive-day and cross-host convergence gate,
  but no real scheduled evidence days.

## Not yet proven

- farol, Mac, and agent-1 still run or expose stale/unverified installations;
  agent-1 access is unavailable, and the non-human canary profile is unnamed.
- The Mac follower path needs a dedicated OS account/keychain; a directory-only
  disposable home cannot isolate Claude's process-wide keychain service.
- No declarative fleet timer, first-failure alert, cross-host evidence
  collection, or unexpected-writer measurement is deployed.
- The physical staging, canary, limited rollout, rollback, final restore drill,
  and 30 consecutive green days have not happened.

The goal therefore remains active.
