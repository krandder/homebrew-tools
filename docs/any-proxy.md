# any-proxy: the hung-listener wedge (2026-07-22) and the three layers against it

## Incident

On 2026-07-22 the claude any-proxy (`any-proxy.mjs`, launchd-managed on the
mac, `127.0.0.1:7800`) wedged after ~4h of uptime: the process was alive and
the LISTEN socket was open, but no request was ever served again. Every
client retry just added another parked connection.

## Wedge mechanism

`forward()` called `fetch()` to `api.anthropic.com` with **no timeout**. When
an upstream connection stalls (accepts the request, never sends response
headers), the request parks forever. Claude Code runs with
`CLAUDE_CODE_MAX_RETRIES=99`, so every retried client request opened a new
socket while the old one stayed parked; sockets stacked until the accept
backlog filled and the listener stopped serving entirely. launchd/systemd
never intervened: they supervise **pids**, and a hung process is a perfectly
healthy pid.

## The three layers

1. **Timeouts + /healthz (any-proxy.mjs itself)**
   - `forward()` aborts the upstream call after
     `CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS` (default `120000`) waiting for
     **response headers**; the timer is cleared once headers arrive, so
     streaming bodies stay untimed (legit Anthropic streams run 10+ min). An
     abort takes the same upstream-error path as any `fetch()` throw:
     failover to the next profile, or a 502 when the pool is exhausted.
   - `GET /healthz` answers `200 {"ok":true,"inflight":<n>,"uptime_s":<n>}`
     without touching profile selection or any state file — cheap enough for
     a 20s probe, and answered even while other requests are parked.
   - Per-request total budget `CLAUDE_PROXY_REQUEST_BUDGET_MS` (default
     `900000`): the response is destroyed past the budget, so no request can
     park a socket longer than 15 min even mid-stream.
   - `server.headersTimeout = 65000` and `server.requestTimeout = 300000`
     (explicit): stalled **client** headers/bodies die instead of parking.

2. **Watchdog (bin/proxy-watchdog.sh)** — restarts the service when the
   health endpoint dies, covering the hung-but-alive case supervisors can't
   see:

   ```bash
   proxy-watchdog.sh [--once] <service-name> <health-url> [max-failures=2]
   ```

   Every 20s it runs `curl -fsS --max-time 3 <health-url>`; after
   `<max-failures>` consecutive failures it restarts the service
   (`launchctl kickstart -k gui/$(id -u)/<service-name>` on macOS,
   `systemctl --user restart <service-name>` under systemd; otherwise it
   logs and exits 1). Log lines go to stderr. `--once` runs a single check
   pass and exits 0 (useful for cron/manual checks).

3. **Wrapper health probe** — see below.

## Wrapper health probe

Client wrappers (`claude-any` on the mac, and any equivalent) MUST NOT trust
a listening port as proof of life. Before selecting the proxy, probe the
health endpoint with a hard 2s cap and fall back (next profile / direct
upstream) when it doesn't answer:

```bash
proxy_healthy() {  # proxy_healthy <port>
    curl -fsS --max-time 2 "http://127.0.0.1:$1/healthz" >/dev/null 2>&1
}

if proxy_healthy 7800; then
    export ANTHROPIC_BASE_URL="http://127.0.0.1:7800"
else
    # wedged or down: fall back instead of parking on a dead listener
    unset ANTHROPIC_BASE_URL
fi
```

A probe without `--max-time` re-introduces the original bug one layer down:
the wrapper itself parks on the wedged proxy.

## Ops: installing the watchdog

### launchd (macOS)

`~/Library/LaunchAgents/com.futarchy.claude-any-proxy-watchdog.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.futarchy.claude-any-proxy-watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/proxy-watchdog.sh</string>
        <string>com.futarchy.claude-any-proxy</string>
        <string>http://127.0.0.1:7800/healthz</string>
        <string>2</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/claude-any-proxy-watchdog.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.futarchy.claude-any-proxy-watchdog.plist
```

(The first argument is the launchd label of the *proxy* service — the
watchdog runs `launchctl kickstart -k gui/$(id -u)/com.futarchy.claude-any-proxy`.)

### systemd --user (Linux)

`~/.config/systemd/user/claude-any-proxy-watchdog.service`:

```ini
[Unit]
Description=claude any-proxy watchdog (restart on /healthz failure)
After=claude-any-proxy.service

[Service]
ExecStart=%h/.local/bin/proxy-watchdog.sh claude-any-proxy.service http://127.0.0.1:7800/healthz 2
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now claude-any-proxy-watchdog.service
```

## Environment knobs

| Variable | Default | Effect |
| --- | --- | --- |
| `CLAUDE_PROXY_UPSTREAM_TIMEOUT_MS` | `120000` | Max wait for upstream **response headers** before aborting and failing over. Body streaming after headers is untimed. |
| `CLAUDE_PROXY_REQUEST_BUDGET_MS` | `900000` | Hard per-request ceiling, streaming included; the response is destroyed past the budget. |
| `CLAUDE_PROXY_UPSTREAM` | `https://api.anthropic.com` | Upstream base URL (tests point it at a stub). |
| `CLAUDE_PROXY_ANY_PORT` | `7800` | Listen port, loopback only. |
| `CLAUDE_PROXY_NO_HEAL` | unset | `1` disables the async heal (`ai-token publish`) on 401s. |
