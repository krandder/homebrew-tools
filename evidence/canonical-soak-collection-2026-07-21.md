# Canonical soak evidence collection — 2026-07-21

The collector handles only sanitized canary evidence. It never opens a
credential store, token, Keychain password, OAuth response, or provider API.

## Defect and red proof

The first exhaustive three-host audit required ad hoc copy commands. Its Mac
archive initially inherited a group the SSH user could not read, and BSD tar
materialized AppleDouble entries from provenance xattrs. Although the retry
copied all 29 records, that procedure was not canonical or mechanically
fail-closed against omission and unsafe archive members.

Commit `5d048f1` first added three hermetic collector contracts. All failed with
`FileNotFoundError` because `tools/collect-live-soak` did not exist.

## Green implementation and live proof

Commit `3dad014` adds an operator-only standard-library collector. Its live mode
is fixed to the three approved canary locations. It creates short-lived remote
tar archives, explicitly disables macOS copyfile metadata, assigns the Mac
archive to `staff` mode 0640, copies every member, and removes remote staging in
`finally`. Output is built in a mode-0700 sibling directory and atomically
selected only after every source passes validation; records and the
`COLLECTION.manifest` are mode 0600.

Hermetic tests reject traversal, nesting, symlinks, AppleDouble files,
permissive modes, duplicate names, invalid/non-JSON members, an existing
destination, and partial output. Archive mode permits the same checks without
SSH.

A real live-mode smoke test collected all retained evidence in one invocation:
8 farol records, 10 agent-1 records, and 11 macOS records, 29 total. The output
directory was mode 0700; every record and manifest was mode 0600. Both remote
staging searches were empty after completion. The pinned canary runtime was not
changed or restarted.
