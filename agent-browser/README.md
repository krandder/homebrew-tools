# agent-browser

An always-running, **always-hidden** Google Chrome instance that AI agents
(Claude Code, Codex, anything speaking the Chrome DevTools Protocol) can drive —
navigate, click, read, screenshot — **without ever stealing focus or painting on
your screen**, while carrying your real logins.

## Why

Agent browser automation normally either (a) attaches to your visible Chrome and
fights you for focus, or (b) runs a fresh profile that's logged into nothing.
This gives you a third option: a **separate Chrome instance** that boots from a
**synced clone of one of your real Chrome profiles** (so it's already
authenticated everywhere) and runs **headless by default** — it never connects a
window at all, so there is no Dock icon, no window flash, and nothing that can
take focus, while screenshots and the full CDP surface keep working.

## How it works

- **Separate instance, real binary.** Runs `/Applications/Google Chrome.app`
  with its own `--user-data-dir` (`~/.agent-chrome`) and
  `--remote-debugging-port` (default 9222). Uses the real Chrome binary (not
  Chrome-for-Testing) so cloned cookies decrypt against the same Keychain
  "Chrome Safe Storage" item.
- **Synced identity.** `sync-profile.sh` rsyncs a chosen profile (default
  `Default`) out of your live Chrome data dir into the clone, minus caches.
  Re-run it whenever a session expires. Your Chrome keeps running during sync.
- **Invisible, structurally.** The instance runs with `--headless=new`, so
  macOS registers it as `ApplicationType=BackgroundOnly`: no Dock icon, no
  minimized-window tiles, and `bringToFront` calls from automation clients
  cannot pop anything on screen. (An earlier design kept a headed instance
  minimized via a CDP sentinel; minimized windows still create Dock tiles and
  can be restored on top by `Page.bringToFront`, so headless replaced it.)
  Headless Chrome advertises `HeadlessChrome` in the User-Agent, which some
  sites reject — `run.sh` overrides it with the normal Chrome UA for the
  installed version. A LaunchAgent keeps the whole thing alive across logins
  and Chrome updates.
- **On-demand human access.** `show` restarts the instance **headed** and
  raises a window (for a login or 2FA); `hide` restarts it headless. While
  headed, the sentinel (`scripts/sentinel.mjs`) keeps agent-opened windows
  minimized. Note the restart drops tabs agents had open.

## Install

Requires Google Chrome and Node (`brew install node`).

```sh
./install.sh                              # clone the "Default" profile
AGENT_BROWSER_PROFILE="Profile 2" ./install.sh   # clone a specific profile
```

Then point any CDP client at `http://127.0.0.1:9222`. For example:

```sh
# Claude Code (Playwright MCP)
claude mcp add --scope user agent-browser -- \
  npx -y @playwright/mcp@latest --cdp-endpoint http://127.0.0.1:9222

# Codex (chrome-devtools-mcp)
# args = ["-y", "chrome-devtools-mcp@latest", "--browserUrl", "http://127.0.0.1:9222"]
```

## Commands

| Command | What it does |
|---|---|
| `sync-profile.sh` | Refresh the clone from your real Chrome profile (run after a login/session expires) |
| `show` | Restart headed and bring a window to the front for manual interaction |
| `hide` | Restart headless (fully invisible) |

## Configuration (env)

| Variable | Default | Meaning |
|---|---|---|
| `AGENT_BROWSER_PROFILE` | `Default` | Which Chrome profile directory to clone/run |
| `AGENT_BROWSER_CDP_PORT` | `9222` | DevTools port the instance listens on |
| `AGENT_BROWSER_DATA_DIR` | `~/.agent-chrome` | The clone's user-data-dir |
| `AGENT_BROWSER_PREFIX` | `~/agent-browser` | Install location |
| `AGENT_BROWSER_LABEL` | `com.agent-browser` | LaunchAgent label `show`/`hide` restart |

## Security notes

- The clone carries the chosen profile's cookies/sessions — that's the point.
  Pick a profile **without** wallet extensions if agents shouldn't touch them.
- The CDP port is bound to localhost, but any local process can drive it. This
  is a real widening of local attack surface versus having no debug port.
- Nothing secret lives in this repo; auth state lives only in the local
  `~/.agent-chrome` clone, which is never committed.
