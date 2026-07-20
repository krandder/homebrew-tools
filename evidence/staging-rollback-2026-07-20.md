# Immutable staging and rollback evidence — 2026-07-20

This drill used a `mktemp` installation root and deleted it after verification.
No live executable, service, scheduler, credential, or user profile changed.

## Artifact

- Source commit: `10ff127fe8539bc6f668c94c8757118b1f9c05d5`
- Source tree: `41e31eaf923bc25fd01f46ad54f54d3eb2f022b8`
- Artifact: `ai-token-vault-10ff127fe853-75abc91d0298.zip`
- Payload entries: 13
- External SHA-256 verification: passed
- Clean-tree release gate: 72 Python tests and four shell integration suites

## Promotion and rollback drill

The installer first selected the previously verified release
`056c066f0629-859625d04069`, then atomically promoted
`10ff127fe853-75abc91d0298`. The `previous` link resolved to the first release
and each installed directory retained its embedded `MANIFEST.json`.

`tools/install-release rollback` then atomically restored
`056c066f0629-859625d04069` as `current` and retained the promoted release as
`previous`, making the operation reversible. The deployment journal contained
exactly six ordered records:

1. first `install-intent` and `install`;
2. promotion `install-intent` and `install`;
3. `rollback-intent` and `rollback`.

Separate hermetic tests prove checksum corruption and archive path traversal
cannot alter the active release.
