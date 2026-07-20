# Canonical release-boundary evidence — 2026-07-20

No live service, credential, scheduler, or installed executable was changed.
All behavior checks used temporary homes, fake executables, and local git
repositories.

## Red evidence and repairs

1. The checked-in `claude-token` and `codex-token` entrypoints contained 1,141
   and 875 lines of independent credential logic despite being documented as
   compatibility shims. A new test failed until both became thin exec shims to
   canonical `ai-token`.
2. The first shim selected an installed `ai-token 3.0.1` from PATH ahead of the
   co-located canonical `3.0.4` artifact. The regression harness now places a
   deliberate stale writer first on PATH and proves the adjacent artifact wins.
3. `proxy-install` embedded `command -v claude-token` into systemd. With a fake
   stale writer first on PATH, the generated unit failed its canonical-path
   assertion. `ai-token` now records its invoked absolute path, and systemd,
   launchd, and cron call that exact artifact with the `claude` backend explicit.

## Release gate

`tools/build-release` refuses tracked worktree changes, runs `tests/run full`,
and creates a deterministic ZIP containing the three canonical services,
compatibility entrypoints, onboarding shim, and matching Homebrew formulae.
`MANIFEST.json` records the commit, tree, commit time, modes, and SHA-256 of
every payload file, including the build/install tooling. The bundle receives a content-addressed name and an
external SHA-256 file. Rebuilding the same commit is byte-identical; dirty
source is rejected before tests or output creation.

GitHub Actions now invokes this single release gate and retains the resulting
ZIP and checksum as a workflow artifact. A contract test fixes push, pull
request, manual, and daily scheduled triggers and forbids `continue-on-error`.
Checkout uses the current Node-24-based `actions/checkout@v6`; artifact upload
uses `actions/upload-artifact@v7`.
The expanded local gate passed 91 Python tests and four shell integration
suites.
