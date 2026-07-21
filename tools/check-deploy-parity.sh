#!/usr/bin/env bash
# Compare farol's running proxy sources with origin/main. Usage: tools/check-deploy-parity.sh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
status=0
for pair in 'any-proxy.mjs:claude-any-proxy.service' 'codex-any-proxy.mjs:codex-any-proxy.service' 'kimi-any-proxy.mjs:kimi-any-proxy.service'; do
  file="${pair%%:*}"
  deployed="$(systemctl --user cat "${pair#*:}" 2>/dev/null | awk -v file="$file" '/^ExecStart=/ { for (i = 1; i <= NF; i++) if ($i ~ ("/" file "$")) print $i }' | head -n1)"
  if [[ -z "$deployed" || ! -f "$deployed" ]] || [[ "$(sha256sum "$deployed" | cut -d' ' -f1)" != "$(git show "origin/main:$file" | sha256sum | cut -d' ' -f1)" ]]; then
    echo "DIVERGED $file"
    status=1
  else
    echo "MATCH $file"
  fi
done
exit "$status"
