# Follower/leader reliability evidence — 2026-07-20

Scope: hermetic `ai-token`, `ai-vault`, and `ai-vault-http` behavior only. No
production credential, public OAuth endpoint, live credential store, or live
service was used or mutated.

## Green gate

Command:

```text
tests/run full && git diff --check
```

Result:

- 81 scoped Python tests passed.
- Eight cross-machine cases passed: HTTP and forced-command SSH for complete
  owner/leader/follower convergence, follower CLI launch, and legacy-writer
  rejection, plus established-follower revocation.
- Four shell integration suites passed.
- Formula SHA-256 pins matched all three source artifacts.
- `git diff --check` passed.

## Machine and profile coverage

The lab creates isolated filesystem/process environments for a leader, two
owners, two followers, and an unauthorized machine. It exercises two named
profiles (`alpha` and `beta`) for Claude, Codex, and Kimi through the real
scripts and either the real HTTP handler or the real forced-command vault
shell. Local loopback mock OAuth services supply disposable rotations.

Assertions cover:

- owner-to-leader sync/handoff and leader-to-follower delivery;
- later owner rotation converging both followers without changing the other
  profile;
- real refresh tokens remaining only at the refresh authority;
- follower stores receiving the sentinel refresh token;
- owner credentials remaining byte-identical for owner-managed sync;
- ACL denial for an unauthorized machine;
- ACL revocation during an established lifecycle taking effect on the next
  HTTP/SSH pull, without mutating either side's credential bytes, while an
  unrevoked follower continues to converge;
- real follower CLI launch and selected-profile propagation;
- Kimi and Codex refresh endpoints being blackholed on followers;
- Kimi keepfresh child termination and wait;
- owner-managed Kimi expiry refusing leader refresh;
- current protocol writes succeeding while missing/2.x HTTP and SSH writers
  are rejected;
- a running Claude proxy reading a newly published access token on the next
  request without process restart.

## Defects reproduced red, then fixed

1. Kimi owner snapshots could overwrite newer/equal-conflicting generations,
   accept no expiry generation, and overwrite malformed canonical state.
2. The Kimi leader `serve` path attempted to refresh an expired chain marked
   `refreshAuthority=owner`.
3. `ai-vault-http` broker success raised `NameError` because `time` was not
   imported after the leader publish completed.
4. Codex OAuth was hardwired to the public endpoint, preventing a hermetic
   leader refresh test.
5. Codex canonical receive accepted unversioned, stale, and equal-generation
   conflicting rotating snapshots.
6. A clean Codex follower could not launch because `.codex/` was not created
   before writing `auth.json.tmp`.
7. Claude follower launch could retrieve over HTTP or a shared file but not
   over the supported SSH vault transport.
8. Kimi launched keepfresh from a subshell and did not wait for it, allowing a
   child process to outlive the CLI.
9. HTTP and forced-command SSH accepted unsafe unversioned/legacy credential
   writers.
10. Unclosed embedded-Python reads could emit warning text into a captured
    OAuth response and corrupt JSON parsing under warning-strict execution.

Earlier evidence in this goal also covers the broken `sync-receive` argument,
incorrect backend invocation, formula drift, installed-vs-canonical test drift,
Claude lifecycle rotation/concurrency, and proxy header/framing behavior.

Revocation prevents subsequent vault pulls and HTTP access-token retrieval. It
does not revoke a provider access token already issued to a follower; that token
can remain usable until its provider-side expiry. Immediate session revocation
would require a provider feature and is not claimed by this test.

## Still required before the goal is complete

- deterministic disconnect and crash-point fault injection;
- fake-clock coverage across all lifecycle thresholds;
- physical systemd, launchd, cron, PATH, wrapper, and obsolete-writer inventory
  during disposable-profile canary staging;
- executable generated state-machine/property tests and mutation testing;
- clean-checkout blocking CI/release evidence and immutable release bundles;
- disposable-profile staging on farol/Mac/agent-1, rollback, scheduled canary,
  evidence retention, and the required 30-day green soak.
