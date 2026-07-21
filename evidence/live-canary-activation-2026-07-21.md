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

- Merged PR: #19
- Canonical commit: `6b6857b8f93b6e7ff60af6d0038f36efb78ef853`
- Tree: `eddc0fd5d193992c9e9b79cb08da6fd0e080633e`
- Artifact: `ai-token-vault-6b6857b8f93b-5bb02b78dc10.zip`
- Installed manifest: 28 regular payload files

The artifact passed the complete local gate, protected push and pull-request
release gates, checksum verification, and exact installed-manifest verification
on farol, agent-1, and macOS. The live leader published successfully. Both
followers pulled and checked successfully. Evidence files are regular mode-0600
records and contain only lifecycle return codes and credential metadata.

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

## Schedules and soak boundary

- Farol systemd timer: enabled and waiting; forced scheduled service passed.
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
