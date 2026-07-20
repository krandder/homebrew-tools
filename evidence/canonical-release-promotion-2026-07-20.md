# Canonical canary release promotion — 2026-07-20

This supersedes the selected-release and identity status in
`physical-canary-deployment-2026-07-20.md`. No credential, pairing token,
Keychain password, OAuth code, cookie, or credential hash is recorded here.

## Protected release

- Canonical main commit: `e4ab84aefd135fc1a94058efeba731b3cc068406`
- Tree: `dc43004b0e6df383827df724ef9a8d8c5d8584e2`
- Artifact: `ai-token-vault-e4ab84aefd13-a4032cb46d0a.zip`
- Protected main workflow run: `29782505044`, passed
- Manifest payload: 24 regular files, including all nine scheduler/dispatcher
  assets under `deploy/canary/`
- Release gate: 130 Python tests and four shell integration suites

The downloaded archive checksum and manifest were verified before promotion.

## Three-host promotion and rollback

Farol selected `releases/e4ab84aefd13-a4032cb46d0a`, verified its full commit
and 24-file manifest, rolled back to `17743041f1aa-7debc47fda04`, verified that
release, then rolled forward and verified `e4ab84a...` again. Its deployed
service, timer, and alert unit compare byte-for-byte with the selected release;
the timer remains disabled.

Agent-1 completed the identical install, verify, rollback, old-release verify,
roll-forward, and final verify sequence. Its canary and preflight configs are
mode 0600 and pin the full `e4ab84a...` commit. Its service and timer compare
byte-for-byte with the selected release, are mode 0644, and the timer remains
disabled.

The macOS UID-502 account completed the same sequence through the authenticated
UID switch. Its config and preflight files are mode 0600; `run-live` and
`run-scheduled` are mode 0700 and match the selected release. The human-owned
dispatcher is mode 0600, the UID-switch wrapper is mode 0700, and the wrapper's
SHA-256 exactly matches the artifact. A forced dormant dispatch ran once and
exited zero. The canary-owned activation marker remains absent.

## Identity boundary

Cloudflare Email Routing now maps the exact dedicated address
`ai-token-canary@futarchy.ai` to the verified operator mailbox, without changing
the domain's existing MX boundary. A separate Anthropic consumer account was
created for that address. Claude Code authorization then required a paid Claude
Pro or Max subscription. No purchase was authorized, no paid plan was selected,
no OAuth grant or API credential was installed, and temporary browser state was
removed. The three schedules therefore remain deliberately dormant.

