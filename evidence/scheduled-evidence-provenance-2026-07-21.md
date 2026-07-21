# Scheduled evidence provenance — 2026-07-21

No production credential or credential hash participated in these tests. The
fixtures use generated metadata and sanitized JSON records in temporary
directories.

## Defect

Schema-2 evidence did not identify its entrypoint. A forced successful run
could therefore satisfy a day intended to prove scheduler-native execution.
The verifier also could not detect omission of a failed record when the next
record's credential metadata happened to match.

## Red and green

Commit `9c41476` first added deterministic regressions for both gaps and for a
missing post-window host/role anchor. The old runner emitted schema 2, accepted
an arbitrary trigger value, and the old verifier rejected the new fixtures
before it could enforce any provenance or chain.

Commit `37a9ff8` introduced schema 3. Linux services and the macOS scheduled
wrapper explicitly mark scheduled invocation; direct runs default to manual.
Each record links to the exact SHA-256 digest and filename of the previous
sanitized record for that host and role. The verifier requires scheduled daily
coverage, validates every consecutive link, rejects a missing or modified
predecessor, and requires a successful scheduled post-window anchor for every
required host/role.

Credential contents remain excluded. The hash covers only the already-safe
mode-0600 evidence JSON. The targeted 29-test gate and the complete fast suite
passed without retry.
