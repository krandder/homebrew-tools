# Final-pin unattended leader evidence — 2026-07-21

The existing farol systemd timer, without a manual service start or timer
change, ran the isolated leader lifecycle at 16:00 UTC on final protected
release `0f235c2aecce-e2ce134f3805`.

Record `20260721T160000.285306Z-farol-leader-3612450.json` is a regular
mode-0600 schema-3 record with `trigger: scheduled`, profile
`canary-claude`, full expected commit
`0f235c2aecce82ea5dd7761f3d9b7707a0157230`, status `ok`, and exactly
`verify-release` then `publish`, both with return code zero. Its immediate
predecessor filename and SHA-256 link match the retained prior farol record.
The systemd oneshot reports `Result=success` and exit status zero.

Sanitized live event telemetry contained no canary 429, rate-limit, or
cooldown event after the run. Atomic three-host collection retained all 67
records: 25 from farol, 21 from agent-1, and 21 from macOS. The cumulative
auditor correctly exited zero with `no completed soak day`.

This is final-pin scheduler activation evidence only. July 21 UTC contains
earlier releases and historical failures and cannot satisfy a soak day. The
first eligible day remains July 22 UTC; agent-1 and macOS retain their existing
04:10 and 04:20 UTC schedules, and the first cumulative one-day audit becomes
eligible only after the July 23 anchors exist.
