# Thirty-day soak evidence gate — 2026-07-20

No live credential, provider endpoint, vault, installation, service, or
schedule participated. Tests use generated JSON records in temporary
directories.

## Red

Commit `df55c76` defined six soak contracts before the verifier existed. All
six failed with `FileNotFoundError` for `tools/verify-live-soak`.

## Green contract

The standard-library verifier requires, by default, 30 consecutive UTC days.
For each day, every explicitly required `host:role` pair must have evidence
from the same non-human `canary-*` profile and full release commit. Successful
leader evidence must contain exactly `verify-release` then `publish`;
successful follower evidence must contain exactly `verify-release`, `pull`,
then `check`, all with zero return codes.

It fails on the first in-window failed/running record, missing host-day, mixed
commit, wrong profile, malformed schema or timestamp, symlink, non-regular
file, non-0600 mode, or fabricated successful step list. A later green retry
cannot conceal an earlier failure. The verifier produces a machine-readable
summary only after the complete matrix passes.

Schema 2 also requires a continuous chain of credential-file metadata for each
host and role. The gate compares each successful run's final metadata with the
next run's initial metadata and rejects unexplained between-run changes. It
never reads or stores credential bytes or hashes.

The release payload includes the verifier, while the installer remains able to
install and roll back older valid artifacts that predate it. The real soak
remains unstarted until the dedicated profile and scheduled host roles are
designated and deployed.

The clean release gate passed 108 Python tests and four shell integration
suites without retry. Its checksum-verified artifact contains 15 manifested
payload files, including `tools/verify-live-soak`.
