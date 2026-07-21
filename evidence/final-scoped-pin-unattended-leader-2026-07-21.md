# Final scoped-pin unattended leader — 2026-07-21

The existing Farol systemd timer, without a manual service start or timer
change, ran the isolated leader lifecycle at 18:00 UTC on final protected
release `6201b1920093-f8bd4e418821`.

Record `20260721T180000.055258Z-farol-leader-56855.json` is a regular mode-0600
schema-3 record with `trigger: scheduled`, profile `canary-claude`, full
expected commit `6201b1920093cc605c7e04840c967407ae24d644`, status `ok`, and
exactly `verify-release` then `publish`, both with return code zero. Its
immediate predecessor is the final-pin manual leader record
`20260721T170921.843883Z-farol-leader-4021501.json`; the retained bytes match
the recorded SHA-256 link. The systemd oneshot reports `Result=success` and
`ExecMainStatus=0`.

Sanitized live telemetry after the run contained zero canary 429, rate-limit,
or cooldown events. Atomic three-host collection retained 74 records: 28 from
Farol, 23 from agent-1, and 23 from macOS. The cumulative auditor correctly
returned `no completed soak day`.

This is scheduler-activation evidence only. July 21 UTC contains earlier
releases and manual records and cannot satisfy a soak day. The first eligible
day remains July 22 UTC; the first cumulative one-day proof becomes possible
only after the July 23 post-day anchors exist.
