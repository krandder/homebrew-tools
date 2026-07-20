# Post-deploy verification and scheduled CI — 2026-07-20

All installer checks used temporary release roots and synthetic bundles. No
live installation, symlink, service, or scheduler was changed.

## Red evidence

`tools/install-release verify` did not exist: the first tests failed at command
parsing. After an artifact was selected, there was no supported way to prove
that its installed bytes still matched the retained manifest or that a host
selected the expected commit.

## Enforced contract

`tools/install-release verify --root ROOT [--expect-commit SHA]` now:

- resolves `current` only inside the content-addressed release store;
- validates manifest schema, commit, tree, and canonical service presence;
- compares every installed payload hash and mode with `MANIFEST.json`;
- rejects missing, extra, unmanifested, or symlinked payloads;
- fails when the selected commit differs from the expected commit;
- never changes the selected release on failure; and
- prints a JSON commit/tree report and records a successful `verify` event in
  the deployment journal.

The canonical GitHub workflow is contract-tested to remain blocking, invoke
the single `tools/build-release` gate, retain artifacts for 30 days, and run on
push, pull request, manual dispatch, and daily at 03:17 UTC. The schedule is
version-controlled but has not run remotely because this goal has not pushed
or deployed the commits.
