#!/usr/bin/env bash
# DEPRECATED (2026-07-22): raw-script installs caused the legacy-shadow mess
# (old ~/.local/bin/*-token files winning PATH over the brew shims).
# The brew tap is the only supported install path now; this shim forwards to
# the idempotent bootstrap that handles every machine state.
echo "install.sh is deprecated — running the brew bootstrap instead..."
exec bash "$(cd "$(dirname "$0")" && pwd)/bootstrap.sh" "$@"
