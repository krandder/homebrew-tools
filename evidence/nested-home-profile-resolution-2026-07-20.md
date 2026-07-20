# Nested HOME profile-resolution incident — 2026-07-20

Reported symptom: `codex-adriana` returned 401 when launched from a Codex
profile session. The `ai-as` wrapper treated the session's
`HOME=/home/kelvin/.codex-profiles/adriana` as the machine root and silently
created a second, credential-less `.codex-profiles` tree. Manually prefixing
`HOME=/home/kelvin` selected the intended profile and succeeded.

No personal credential was read for this reproduction. A temporary machine
home contains a sibling `fixture` profile while the subprocess receives a
nested `HOME=.../.codex-profiles/adriana`. The original canonical `ai-token`
failed to find `fixture`.

`ai-token` now infers the machine root when HOME is inside either a Codex or
Claude profile tree. Explicit `AI_TOKEN_REAL_HOME` remains authoritative. The
regression proves Codex resolves the sibling canonical auth file, Claude
reports the machine-level profile/shared directories, and neither path creates
a nested profile tree.

This protects the canonical token/vault boundary even when a caller supplies a
profile-scoped HOME. The separately installed `ai-as` implementation and its
live-topology test remain under Kimi's concurrent review; they were not copied,
executed, or modified by this goal.
