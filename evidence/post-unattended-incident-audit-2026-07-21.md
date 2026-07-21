# Post-unattended incident audit — 2026-07-21

This audit contains no credential, pairing secret, provider response, or
credential hash.

## First unattended matrix

The first scheduler-native leader/follower matrix completed successfully:

- farol leader: `Result=success`, exit zero at 04:00 UTC;
- agent-1 follower: `Result=success`, exit zero at 04:10 UTC; and
- macOS follower: launchd run count two, last exit zero at 04:20 UTC.

Neither Linux `OnFailure` unit had a journal entry after midnight UTC. The
macOS dispatcher had no error output. The canonical incident store gained no
ai-token/ai-vault incident from this unattended matrix. Its only canary record
remains the deliberately induced 2026-07-20 agent-1 pre-activation failure,
stored as `health-check-fail`.

## Taxonomy defect found

The farol direct `OnFailure` unit supplied `auth-credential` to the canonical
incident writer. That category is not in the writer's accepted taxonomy, so a
real farol unit failure would have been retained under the fallback
`unexpected-behavior` category. The authenticated follower route already used
the intended supported category, `health-check-fail`; delivery and retention
were not affected, but direct leader failures would have been misclassified.

Commit `c1bc76a` preserves a focused failing deployment regression for this
exact mismatch. Commit `8cb1e4c` makes the smallest production change: the
farol unit now uses `health-check-fail`. Commit `7ad4a4a` additionally verifies
that the authenticated follower route invokes the same taxonomy. No external
incident infrastructure was changed.

## Protected promotion

PR #34 passed the complete local gate, the red-before-green history verifier,
both protected pull-request release gates, and protected main run
`29802395103`. The downloaded immutable artifact was independently verified:

- commit: `bdbd1babd9f8208cd1ff2f40fab4d1016855aca0`;
- tree: `6537ea90d3365efa3bcf40c577aae4315ed31096`;
- release: `bdbd1babd9f8-102ff6b0110f`; and
- archive SHA-256:
  `102ff6b0110fea0e208309e0fe4cb79e5a9fc154a2ea7951f1217320ff30bb0e`.

Farol, agent-1, and the dedicated macOS UID each installed and verified the
new release, rolled back to `253597d3255e-052616a82b39`, verified it, restored
the new release, and verified it again. Farol's isolated vault and timer are
active, agent-1's timer is active, and the macOS dispatcher remains loaded
with last exit zero. The installed farol failure unit is byte-for-byte from the
new artifact and uses `health-check-fail`. The macOS dispatcher and dedicated
UID-switch runner hashes match the new manifest.

All three roles then passed the exact manual lifecycle on the new release. The
atomic collector retained 33 total records: 9 farol, 12 agent-1, and 12 macOS.
Temporary staging archives were removed from all three machines after exact
verification.

## Continuity guard exercised by a real operator write

Before promotion, an explicit agent-1 pull was used to verify the newly
activated `ai@futarchy.ai` account for the `cao-mnx-mm` handoff. That pull was
outside `run-live-canary`, so the first post-promotion agent-1 lifecycle
correctly failed at `writer-continuity` and retained
`20260721T045558.543938Z-agent-1-follower-3694269.json`. Nothing was deleted or
rewritten. A second designated lifecycle began from that failed record's final
metadata and passed pull/check, preserving an unbroken evidence chain.

The consumer wrapper itself does not write the credential file: `claude run`
validates a temporary vault response and injects the fresh access token into
the provider process. The detected write was the explicit operator `pull`, not
normal consumer traffic. Existing hermetic writer-drift tests already require
this fail-closed behavior; no exception was added for the operator action.

The clean soak does not begin until 2026-07-22 UTC, so the retained
activation-day failure does not discard a qualifying soak day. The required
window is now pinned to release `bdbd1babd9f8-102ff6b0110f` through
2026-08-20 UTC, followed by all three scheduled 2026-08-21 anchors.
