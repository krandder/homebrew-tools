# Refresh rate-limit evidence — 2026-07-20

All checks used loopback OAuth servers, fake credentials, temporary homes, and
an injected clock. No provider API or personal credential store was accessed.

## Red evidence

The first Claude regression test made three refresh requests despite a `429`
response carrying `Retry-After: 120`. The expected contract was two requests:
the second invocation, 30 seconds later, must be blocked locally; the third,
after 121 seconds, may contact the endpoint again. This demonstrated that the
old implementation had no durable refresh backoff.

The first Codex implementation test then found that HTTP stderr escaped the
captured result, preventing the cooldown from being written. The same contract
failed and was fixed before expanding the suite.

## Enforced contract

- A 429 persists a mode-0600 cooldown beside the affected credential and a
  provider-wide cooldown in the host refresh-state directory.
- Numeric or HTTP-date `Retry-After` values are normalized; a missing or
  invalid value receives a conservative 60-second fallback and all values are
  capped at one day.
- Claude, Kimi, and Codex check cooldown before refresh and again inside a
  provider-wide refresh lock.
- Concurrent refreshers collapse to one network request.
- A 429 leaves the canonical credential byte-for-byte unchanged.
- One throttled Claude profile blocks another Claude profile on the same host,
  protecting the shared provider/IP boundary.
- Once the injected clock passes the deadline, exactly one new request is
  permitted and a repeated 429 extends the persisted deadline.
- Generated state-machine histories reject every refresh attempt while the
  provider cooldown is active.
