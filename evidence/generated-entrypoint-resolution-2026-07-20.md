# Generated entrypoint resolution — 2026-07-20

All checks used temporary homes, fake `crontab`, fake `launchctl`, and generated
files. No installed wrapper, live schedule, service, or credential was read or
changed.

## Red evidence

The first regression expected the generated Codex wrapper to invoke the exact
canonical `ai-token` artifact. It instead contained `exec ai-token ...`, which
allowed an unrelated executable earlier on `PATH` to take over the credential
path. The same ambient-resolution pattern existed in the plain Claude, named
follower, repair, and profile/proxy wrappers.

## Enforced contract

- Every generated wrapper embeds the absolute `AI_TOKEN_SELF` selected by the
  installer; it does not resolve `ai-token` or `claude-token` from runtime
  `PATH`.
- Repair rewrites a previously generated but unpinned named-follower wrapper.
- The systemd proxy unit, cron maintenance entry, and launchd plist all invoke
  the same canonical artifact.
- Reinstalling maintenance removes the prior managed cron writer, keeps
  unrelated cron lines, and leaves exactly one current writer.
- Transferring away from vault authority removes
  `CLAUDE_TOKEN_VAULT_AUTHORITY=yes`; transferring to it adds the flag to the
  sole managed cron/launchd job.

These checks cover generated-file correctness and replacement semantics. A
physical host inventory and activation check remains part of the canary gate.
