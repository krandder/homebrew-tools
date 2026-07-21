# Kimi incident replay audit — 2026-07-21

Scope: the twelve recurring authentication failure classes named in M2 of
`GOAL-AI-TOKEN-AI-VAULT-TDD.md`. This audit maps each claim to executable
behavior; documentation by itself is not treated as coverage. All tests use
temporary homes, fake credentials, loopback providers, injected clocks, and
local HTTP/SSH transports. No production credential or provider endpoint is
used.

## Executable mapping

1. **Wrong upstream authentication header.**
   `ProxyTest.test_proxy_replaces_auth_and_does_not_forward_stale_gzip_metadata`
   sends stale `Authorization` and `X-Api-Key` values, then proves the proxy
   removes both and sends the current published bearer token.
2. **Decompressed body retaining compression/framing metadata.** The same
   proxy test returns gzip with `Content-Length`, proves the body is usable,
   and proves both stale headers are absent downstream.
3. **Running process holding a frozen access token.** The same live proxy
   process receives a second request after its credential file rotates and
   forwards the new token without changing PID.
4. **Owner and vault refreshing one rotating chain.**
   `ClaudeLifecycleTest.test_owner_authority_refuses_refresh_before_network`,
   both follower/leader matrix transports' expired-owner phase,
   `CredentialStateMachineTest.test_explicit_takeover_is_required_before_owner_chain_refresh`,
   and `TestHeal.test_leader_heal_never_forces_refresh_authority_takeover`
   all prove refusal occurs before any OAuth request unless takeover is
   explicit.
5. **Missing or incorrect refresh-authority marker.**
   `VaultReceiveTest.test_receive_normalizes_missing_or_incorrect_authority_markers`
   drives missing and deliberately inverted markers through the real Claude
   vault-handoff, Claude owner-sync, and Kimi owner-sync boundaries. The
   state-model mutation suite also kills owner-as-vault and vault-as-owner
   mutations.
6. **Stale client overwriting a newer canonical credential.** The Claude,
   Kimi, and Codex stale/conflicting/newer tests in `VaultReceiveTest`, plus
   its generated-generation reference tests, reject regressions and converge
   on the newest valid generation.
7. **Alternate refresh path bypassing the common lock.**
   `CompatibilityShimTest.test_legacy_entrypoints_are_thin_canonical_shims`
   removes independent legacy implementations even under a shadowing PATH;
   the Claude concurrent-publish test and Kimi/Codex concurrent rate-limit
   tests then prove the remaining canonical path collapses concurrent refresh
   attempts to one network request.
8. **Empty or malformed shared credential write.**
   `ClaudeLifecycleTest.test_crashes_before_refresh_replacements_never_truncate_credentials`
   and `test_crash_before_fresh_publish_preserves_previous_shared_credential`
   kill the process immediately before canonical/shared replacement and prove
   readers retain valid prior JSON. Vault crash recovery and malformed
   canonical tests independently fail closed.
9. **Obsolete cron or launchd writer surviving authority transfer.**
   `ServiceEnvironmentTest.test_maintenance_replaces_obsolete_writer_and_authority`
   and `test_launchd_maintenance_rewrites_authority_with_canonical_binary`
   prove exactly one canonical managed writer remains and stale authority is
   removed.
10. **systemd PATH resolving a different or missing executable.**
    `ServiceEnvironmentTest.test_proxy_unit_pins_the_invoked_canonical_binary_and_service_path`
    plants a stale shadow binary, then proves both `ExecStart` and service PATH
    resolve the canonical artifact.
11. **Old client protocol writing through an unsafe endpoint.** The HTTP and
    forced-command SSH `FollowerLeaderMatrixTest` legacy-writer tests reject
    missing and 2.x protocol writers while accepting the current protocol.
12. **Proxy restart, dynamic profile registration, and wrapper resolution.**
    The proxy contract test proves restart, disconnect recovery, and live
    profile registration without a PID change. The generated-wrapper service
    test and compatibility-shim test prove wrapper resolution stays canonical
    under a stale PATH.

## Bugs exposed by this audit

The audit found three claims that were weaker than their names or evidence:

- Claude publication truncated canonical and shared JSON in place although a
  test called the rotation atomic. Red commit `9865fd5` added deterministic
  crash points; green commit `cb9c1e9` changed both refresh and fresh-token
  publication to fsynced private generations plus atomic replacement.
- Formula tests compared checksums only with worktree files. The `ai-token`
  URL therefore referenced older bytes while four scoped formulas still used
  moving `main`. Red commit `b1f94be` exposed all five; green commit `e813843`
  pins one reachable canonical source commit and verifies downloaded bytes,
  checksum, and current source agree.
- Release bytes inherited group-write bits that Git does not track, so clean
  worktrees could produce different archives. Red commit `20f1fd3` reproduced
  two bundles; green commit `00aee32` normalizes payloads to 0644/0755.

The focused replay groups passed 38 proxy/matrix/vault/environment tests and
18 lifecycle/rate-limit/fake-time tests. The complete `tests/run full` release
gate, including all four shell integration suites, passed after the fixes.

