# Physical fleet inventory — 2026-07-20

This was a read-only pre-canary inspection. It did not read credential files,
invoke a provider, pull/publish tokens, change a service, edit cron, or install
an artifact.

Protected canonical commit: `bc4d9ef99e22298a42a3db0a0ce05daa2788fc34`.
Its hosted `release-gate` run `29770165333` passed and its downloaded artifact
checksum and embedded manifest were verified independently.

## farol (Linux, vault authority)

Both `/home/kelvin/.local/bin` and the active Adriana profile resolve the same
stale files. `ai-token claude --version` reports 3.0.1.

| command | installed SHA-256 | protected SHA-256 |
|---|---|---|
| `ai-token` | `331315fd8b903df8c81ab95f903a2af8e267f01d3ee317ef5db648bd858c81b8` | `841b52e895b6c672c22386028001e51d4e7677e638169970bde4ae0356a5598a` |
| `ai-vault` | `9b4b342fc5f505a2f3463f095269370d1c7e48278b9025945a02d49dc2448650` | `9243a323ee8f6abd4e8324591204490ae17dbdcb044efc3a00e8ac7ac98d7c15` |
| `ai-vault-http` | `20850069454b77a5b0ef7aea9d98faf000b5be5d7a0f1f2b0ef0f9fec403fc0b` | `591147cd71571c003c031816172404e95c95612a6ba1da006415074a3353c148` |
| `claude-token` | `403572c0574bc9ae976e22f2bcf21dcec5d435535acbee2aa7fbdeb8b02021f6` | `75e8a46c0ec9a24654a6a22de0f67eeb5ad8dfbd082ab29a02d07b1a66e18d73` |
| `codex-token` | `3b3a1e1c839037951e7b31751ef6b5d99a69cb8b87774e3eb1f1ba9ec94f0a6f` | `2e59e3ab3148a6a164a6e661177699963fb3cf166315731fee23b7df85cf92b9` |

Live/scheduled writers:

- `claude-token-proxy.service`: enabled and running;
  `ExecStart=/home/kelvin/.local/bin/claude-token proxy`.
- `ai-token-kimi-sync.timer`: enabled and waiting, every 300 seconds;
  its service executes `/home/kelvin/.local/bin/ai-token kimi sync`.
- marked maintenance cron: every two hours with
  `CLAUDE_TOKEN_VAULT_AUTHORITY=yes`, invoking
  `/home/kelvin/.local/bin/claude-token maintain`.

The nested profile session was neutralized for inspection with explicit
`HOME=/home/kelvin` and `AI_TOKEN_REAL_HOME=/home/kelvin`; no nested store was
created.

## Kelvin's MacBook Air (Darwin, follower/owner)

Direct read-only access used the documented userspace-Tailscale SOCKS path.
Homebrew links `ai-token`, `claude-token`, and `codex-token` to the 3.0.1
formula, and all three have SHA-256
`331315fd8b903df8c81ab95f903a2af8e267f01d3ee317ef5db648bd858c81b8`.
`ai-vault` and `ai-vault-http` are absent. No marked maintenance cron or
`com.krandder.claude-token-maintain.plist` exists.

The non-interactive SSH environment also lacks `bash` and `python3` on `PATH`;
deployment verification must therefore supply the tested service PATH rather
than relying on the login shell.

## agent-1 (Linux follower)

The userspace Tailscale control plane reports `agent-1` online. SSH reached the
host but rejected the available public key, so installed versions, hashes, and
schedules remain unverified. No alternative user/key was guessed.

## Canary gate

Physical promotion is not safe yet. Required next conditions are:

1. designate the non-human canary profile;
2. obtain approved `agent-1` read-only/deployment access;
3. stage the protected artifact in content-addressed roots without selecting
   it for live writers;
4. verify exact commits on all reachable hosts; and
5. switch only the dedicated canary writer, with the current stale paths
   retained as the rollback target.
