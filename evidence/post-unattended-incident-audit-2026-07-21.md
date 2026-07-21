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

## Promotion boundary

The protected live canary remains pinned to release
`253597d3255e-052616a82b39` until this change passes the complete hard gate,
protected pull-request checks, and an exact three-host promotion. The clean
soak does not begin until 2026-07-22 UTC, so a protected promotion on the
excluded activation day does not discard a qualifying soak day. No live unit
was edited in place and no historical evidence was removed.
