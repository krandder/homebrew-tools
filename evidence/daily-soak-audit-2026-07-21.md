# Daily cumulative live-soak audit — 2026-07-21

This evidence contains no credential, pairing secret, provider response, or
credential hash.

## Completion gap

The lifecycle services already alert on a nonzero run. They cannot alert when
a timer is silently disabled, a host disappears, or a scheduled process never
starts. Without an independent deadline check, the final 30-day verifier could
be the first component to report a missing early soak day.

## Red and green

Commit `12c102c` preserves failing hermetic and deployment regressions requiring
a daily cumulative audit after all three scheduled anchors. Commit `39eecb4`
adds the minimum implementation:

- `tools/audit-live-soak` calls the existing atomic collector and existing
  soak verifier in a temporary mode-0700 workspace;
- every completed day from 2026-07-22 through the previous UTC day is checked
  cumulatively, including the verifier's next-day scheduled anchors;
- the fixed required matrix is farol leader, agent-1 follower, and dedicated
  macOS follower;
- the activation day is a successful no-op because no qualifying day is yet
  complete; and
- a farol systemd timer runs at 04:40 UTC, after the 04:00, 04:10, and 04:20
  anchors, with failures routed through the existing canonical incident unit.

No new evidence format, state database, remote protocol, credential reader, or
alert path was added. The auditor reads only the designated profile and full
commit from the existing canary configuration. Collection output is removed
after verification; the authoritative per-host evidence remains retained.

The focused suites, deterministic artifact test, complete hard gate, and
red-before-green verifier passed locally. A real invocation on 2026-07-21 UTC
returned `no completed soak day` without connecting to a follower or writing
an incident. Protected CI and exact release promotion remain required before
the timer is enabled.
