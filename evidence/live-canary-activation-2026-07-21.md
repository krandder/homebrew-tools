# Live canary activation — 2026-07-21

This supersedes the credential, selected-release, and scheduler status in the
2026-07-20 physical-deployment and promotion records. It contains no access
token, refresh token, pairing token, OAuth code, Keychain password, cookie, or
credential hash.

## Identity and authority

- Dedicated Anthropic identity: `ai@futarchy.ai`
- Entitlement: Claude Max
- Profile: `canary-claude`
- Refresh authority: isolated farol vault only
- Followers: access token plus `__follower_no_refresh__` sentinel
- Temporary farol native login credential: removed after validated vault
  handoff

Claude Code reported the expected email and Max subscription before handoff.
The canonical and shared files are regular mode-0600 files. A real inference
from agent-1 through `/home/kas/.local/bin/claude-canary-claude` returned the
expected sentinel response, proving the isolated follower path reaches the
provider without copying refresh authority.

## Protected release and live matrix

- Current merged PR: #23
- Canonical commit: `699237941a26255fb4cec25282479d54387f7eff`
- Tree: `924e13dbd33abbfd7a11851e76c7f1fe837adeec`
- Artifact: `ai-token-vault-699237941a26-a25d9f0a55dd.zip`
- Installed manifest: 28 regular payload files

The artifact passed the complete local gate, protected push and pull-request
release gates, checksum verification, and exact installed-manifest verification
on farol, agent-1, and macOS. The live leader published successfully. Both
followers pulled and checked successfully. Evidence files are regular mode-0600
records and contain only lifecycle return codes and credential metadata.

A forced post-promotion matrix retained one successful record from each
required host/role pair. `verify-live-soak --days 1 --through 2026-07-21`
accepted exactly those three records with the protected commit and immutable
release ID. This proves deployment convergence; it does not count as the first
unattended cycle or as a clean soak day.

## Live defect and TDD disposition

The first macOS pull fetched a fresh sentinel-only follower credential over the
authenticated vault route, then exited 44 before creating its first dedicated
Keychain item. `security find-generic-password` uses exit 44 for an absent item;
under `set -euo pipefail`, the assignment aborted before the already-intended OS
account fallback.

The repair followed the required order:

1. `25f1eef` added a deterministic macOS first-pull regression and failed with
   exit 44 before `add-generic-password`.
2. `fd37c7b` made the smallest production change: tolerate absence while
   resolving the optional existing Keychain account.
3. `7216cad` updated the pinned Homebrew source checksum.
4. PR #19 passed `verify-tdd-history`, the complete suite, and protected CI
   before merge and deployment.

The original failed evidence is retained. The same dedicated UID/keychain then
passed pull and check on the protected release.

## Soak convergence hardening

The M6 audit found that the verifier checked the recorded full commit but
ignored each record's immutable release ID. Commit `8dc212d` first proved that
two different artifact IDs could pass the convergence gate. Commit `cd6bf13`
then required every in-window record to carry a valid content-addressed release
ID with the expected commit prefix and made any cross-host mismatch fatal. PR
#21 preserved that red-to-green history, passed the complete and protected
release gates, and was promoted and live-checked on all three hosts before the
first unattended run.

## Leader cadence hardening

The approved agent-1 consumer runs every 15 minutes, but Claude access tokens
last about eight hours and `ai-vault serve` intentionally never refreshes on a
follower request. A daily leader publish could therefore leave followers
without a fresh generation for most of a day. Commit `3c18376` first made the
deployment test fail unless the farol timer ran every two hours while both
follower canaries remained daily. Commit `48cbbf2` made that smallest scheduler
change. PR #23 passed the complete suite, TDD-history gate, and hard CI before
merge and exact three-host promotion.

The two-hour publish cadence does not imply a two-hour provider refresh
cadence. A publish with more than 2.5 hours of access-token life remaining
makes no refresh request, and every actual refresh remains protected by the
provider-wide cooldown and persisted rate-limit state.

One manual Mac verification initially invoked `tools/run-live-canary` directly
instead of the deployed `run-live` wrapper, bypassing the dedicated Keychain
unlock and returning 36 at the pull step. That sanitized failed record remains
retained as pre-soak evidence. The real deployed wrapper passed immediately on
the same release, and its successful record is the one used in the convergence
matrix.

## Schedules and soak boundary

- Farol systemd timer: enabled every two hours; forced service passed. This
  keeps the approved 15-minute agent-1 consumer inside a published access-token
  generation while the publish path and global cooldown prevent refresh
  hammering.
- Agent-1 systemd timer: enabled and waiting; forced scheduled service passed.
- macOS login-session dispatcher: loaded; UID-502 mode-0600 activation marker
  present; canary-owned scheduled wrapper passed; dispatcher last exit zero.

Activation occurred on 2026-07-21 UTC. That UTC day contains the retained
pre-fix Mac failure and cannot be counted as green. No evidence is deleted or
overwritten to hide it. The required clean window is therefore 2026-07-22
through 2026-08-20 UTC. After the latter day is complete, `verify-live-soak`
may run on 2026-08-21 UTC with all three required host/role pairs and this exact
profile/commit. Any failure in the window resets the qualifying start date.

The final restore/rollback drill and post-soak incident/writer audit remain M6
exit work.
