# Live-canary runner evidence — 2026-07-20

No production credential, provider endpoint, vault, installed executable,
service, or schedule was read or changed. Every lifecycle command below used a
fake installed release and a temporary dedicated home.

## Red

Commit `74a3bcc` added nine contract tests before the runner existed. The
targeted suite failed with `FileNotFoundError` for `tools/run-live-canary`,
including the separate macOS follower/keychain guard.

## Green contract

The smallest implementation makes the runner part of the checksummed release
payload and enforces these boundaries before invoking `ai-token`:

- execution requires the explicit `--live` flag;
- the designation is an unwritable-by-peers, non-symlink, exact schema-1 file;
  it is Claude-only, sets `non_human: true`, and names a `canary-*` profile;
- the dedicated home, release root, evidence directory, and full expected
  commit are explicit;
- `current` must resolve inside the immutable release store and pass
  `install-release verify --expect-commit` before the exact release binary is
  used;
- ambient profile-scoped `HOME` and hostile `PATH` are replaced, including at
  interpreter startup;
- leader execution publishes only the designated profile; follower execution
  pulls then checks only from the dedicated home;
- schema-1 macOS follower execution fails before any command because Claude's
  current keychain service is process-wide; schema 2 permits the follower only
  when the kernel account name and password-database home exactly match the
  designated `ai-token-canary*` OS account;
- subprocess output is discarded, and atomic mode-0600 evidence records only
  step names and return codes; and
- a failed verification or lifecycle step stops the sequence immediately.

The hermetic contract passes nine tests. A real canary remains intentionally
disabled until Kelvin designates the non-human profile and dedicated per-host
homes.

The first complete-suite run also rejected historical fixture artifacts because
the installer tried to compile a canary runner they legitimately did not
contain. The installer now syntax-checks the runner only when the manifest
includes it, preserving rollback and installation compatibility with older
valid releases. The complete gate then passed 100 Python tests and four shell
integration suites without a retry.
