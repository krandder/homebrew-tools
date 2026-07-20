# Proxy startup deadline — 2026-07-20

After branch and pull-request release gates both passed commit `25d0bbf`, the
protected merge created main commit `23d32282bc0d7483a677daf887ee184fbdcd2e52`.
Its push run `29769775946` failed because the proxy had not begun listening
within the test's fixed 100 × 20ms probe loop.

The failure was not rerun. The harness now uses one monotonic 10-second startup
deadline and fails immediately with captured stdout/stderr if the proxy exits.
This accommodates hosted cold-start variance without retrying a failed test or
weakening any behavioral assertion.

The complete proxy test was then run 20 consecutive times locally with
fail-fast semantics: 20 passed, 0 failed. Hosted evidence is supplied by the
required branch and pull-request gates for this change.
