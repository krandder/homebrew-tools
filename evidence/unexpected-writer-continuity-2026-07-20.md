# Unexpected credential-writer continuity — 2026-07-20

No live credential, provider endpoint, vault, installation, service, or
schedule was read or changed. Tests use temporary files and fake installed
release commands.

## Red

Commit `0537f71` introduced the contract before implementation. The live
runner evidence lacked `state_before`/`state_after`, a file changed between two
runs was accepted, and schema-2 soak records were rejected by the older schema
parser. A separate red case proved a mode-0644 credential was also accepted.

## Green contract

For the designated leader, the runner snapshots the canonical profile and
published follower file. For a Linux follower, it snapshots the isolated local
Claude credential. Metadata contains only file existence, size, inode, mtime,
ctime, and mode—never credential bytes, token values, or content hashes.

Before invoking even `install-release verify`, a run compares current metadata
with the latest retained final metadata for the same host/profile/role. An
unexplained difference writes sanitized failed evidence and exits nonzero.
Expected publish/pull mutations are captured as the new final state, allowing
the next run to chain from them. Existing credential paths must be regular
mode-0600 files.

The soak verifier separately orders every successful host/role history and
checks the same final-to-initial chain, so a defective or bypassed runner cannot
turn discontinuous evidence into a green soak report. Actual alert delivery
will use the declarative scheduler's native nonzero-failure hook once the live
profile and units are authorized.

The clean release gate passed 112 Python tests and four shell integration
suites without retry. The checksum-verified artifact retained the same 15
manifested payload files.
