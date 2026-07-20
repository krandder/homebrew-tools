# `ai-any` independent verification — 2026-07-20

This verification did not invoke a real Claude or Codex request and did not
read any credential store. It inspected code, ran hermetic tests, resolved the
installed command chain, and summarized only non-secret event metadata.

## Verified

- `tests/test_ai_any.py` originally passed 12 tests in 0.38 seconds; after the
  authority regression added during review, 13 tests pass in 0.40 seconds.
- The suite covers least-recently-used spread, expiry and `needsRelogin`
  exclusion, 401/429 cooldown and retry, main-account last resort, honest
  non-auth failures, interactive no-retry, leader publish, follower pull, and
  failed-heal cooldown retention.
- Both `/home/kelvin/.local/bin/claude-any` and
  `/home/kelvin/.local/bin/codex-any` are symlinks to the installed executable
  `/home/kelvin/.local/bin/ai-any`.
- Sanitized live logs contain one `select` and one `ok` event for `adriana` for
  each tool, with no recorded failure event.

## Defects found by independent verification

1. Claude leader healing exported `CLAUDE_TOKEN_VAULT_AUTHORITY=yes`, allowing
   an automatic 401 recovery to bypass owner-managed refresh authority. A red
   regression proved the override was present. Canonical source now delegates
   to normal `ai-token publish`, which enforces the authority marker.
2. Claude follower role detection iterated over `open(config)` without closing
   it. Warning-strict execution exposed the leaked handle; canonical source now
   uses a context manager.
3. The live installation is a copied executable, not a link to canonical
   source. At verification time its only code differences from canonical were
   the two fixes above, so it must be updated through the controlled release
   path before being considered converged.

No live file was changed during verification.
