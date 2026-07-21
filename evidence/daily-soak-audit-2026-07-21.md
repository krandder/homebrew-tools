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
red-before-green verifier passed locally. PR #36 passed both protected
pull-request gates and protected main run `29803432173`. The downloaded
artifact was independently verified:

- commit: `7269e0bc502c2fba27a191788c42e0a872136df8`;
- tree: `f66a68fbe86063fcd50a098dc14361ca61996a43`;
- release: `7269e0bc502c-061c79a5d0b0`;
- archive SHA-256:
  `061c79a5d0b0986bf4a07739424d1b8884726cc069f88dd52ebf6f058ac1e497`;
  and
- manifest: 32 regular payload files, including the auditor, collector, and
  audit service/timer at the required modes.

Farol, agent-1, and the dedicated macOS UID each installed and verified the
release, rolled back to `bdbd1babd9f8-102ff6b0110f`, verified it, restored the
new release, and verified it again. All three roles then passed a linked manual
lifecycle record on the new release. Atomic collection retained all 36 records:
10 farol, 13 agent-1, and 13 macOS.

The installed audit service passed a real pre-window invocation with
`no completed soak day`; it did not connect to a follower or file an incident.
Its timer is enabled and waiting for 04:40 UTC. Both installed unit files match
the protected artifact byte-for-byte, and failures route through the corrected
`health-check-fail` incident unit. Temporary staging archives were removed from
all three machines after verification.
