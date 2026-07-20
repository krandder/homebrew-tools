# Fake-clock lifecycle boundaries — 2026-07-20

The lifecycle suite fixes time at epoch `4102444800` and checks both sides of
the credential decisions without sleeping or contacting provider endpoints.

## Red evidence

At exactly 60 seconds of remaining Kimi lifetime, the leader made zero refresh
requests and published the existing token. Followers require strictly more
than 60 seconds and therefore rejected that publication immediately. The
leader refresh predicate used `< now+60`; the consumer used `> now+60`.

The leader predicate is now `<= now+60`. The loopback regression observes one
refresh, a rotated canonical credential, and a follower publication carrying
the fresh access token plus the non-refreshing sentinel.

## Boundary matrix

- Claude and Kimi follower tokens: 60 seconds is rejected; 61 is accepted.
- Codex follower launch: 60 seconds is rejected before CLI execution; 61 is
  accepted and launches with refresh blackholed.
- Claude vault refresh: exactly 9,000 seconds is published without refresh;
  8,999 seconds performs one serialized refresh.
- Provider `Retry-After`: refresh is blocked before the persisted deadline and
  allowed at/after expiry, with a one-day cap.

All refresh responses come from the loopback OAuth server. No wall-clock wait,
public provider, or personal credential is used.
