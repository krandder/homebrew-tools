#!/usr/bin/env bash
# proxy-watchdog — restart a wedged local proxy service when its /healthz dies.
#
#   proxy-watchdog.sh [--once] <service-name> <health-url> [max-failures=2]
#
# Every 20s: curl -fsS --max-time 3 <health-url>. After <max-failures>
# CONSECUTIVE failures, restart the service: launchctl kickstart -k on macOS,
# systemctl --user restart under systemd. A hung-but-listening proxy is
# invisible to launchd/systemd (they only reap DEAD processes), so the health
# endpoint — not the pid — decides. Log lines go to stderr. --once runs a
# single check pass and exits 0.
set -u

ONCE=0
if [ "${1:-}" = "--once" ]; then ONCE=1; shift; fi

SERVICE="${1:-}"
URL="${2:-}"
MAXFAIL="${3:-2}"
if [ -z "$SERVICE" ] || [ -z "$URL" ]; then
    echo "usage: proxy-watchdog.sh [--once] <service-name> <health-url> [max-failures=2]" >&2
    exit 2
fi

log() { echo "proxy-watchdog: $*" >&2; }

fails=0
while :; do
    if curl -fsS --max-time 3 "$URL" >/dev/null 2>&1; then
        fails=0
    else
        fails=$((fails + 1))
        log "health check failed ($fails/$MAXFAIL): $URL"
        if [ "$fails" -ge "$MAXFAIL" ]; then
            if command -v launchctl >/dev/null 2>&1; then
                log "restarting $SERVICE: launchctl kickstart -k gui/$(id -u)/$SERVICE"
                launchctl kickstart -k "gui/$(id -u)/$SERVICE"
            elif systemctl --user show-environment >/dev/null 2>&1; then
                log "restarting $SERVICE: systemctl --user restart $SERVICE"
                systemctl --user restart "$SERVICE"
            else
                log "no usable service manager (launchctl / systemctl --user); giving up"
                exit 1
            fi
            fails=0
        fi
    fi
    [ "$ONCE" = 1 ] && exit 0
    sleep 20
done
