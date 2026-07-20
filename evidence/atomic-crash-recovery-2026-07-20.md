# Atomic credential crash recovery — 2026-07-20

The hermetic vault lab injects abrupt process exits immediately before and
after canonical Claude credential replacement.

- Before replacement, the command fails and the old canonical credential
  remains byte-for-byte intact and valid.
- The staged file is mode 0600. A retry removes the abandoned target-specific
  staging file, installs the newer generation, and leaves no credential temp.
- After replacement, the command fails but the canonical file is already the
  complete newer generation—not an empty or partial document.
- Retrying the same generation is idempotent and completes publication/audit.

The temporary filename is scoped to the destination basename so cleanup for
one profile cannot delete a concurrent staging file for another profile.
No real credential or production path participates in this test.
