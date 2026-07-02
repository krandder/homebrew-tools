// Keeps the agent browser invisible: every window is forced to stay
// minimized, enforced event-driven over CDP the moment a target is created.
// Paused while the operator has asked for the window via the `show` flag.
import { chromium } from 'playwright-core'
import { existsSync } from 'node:fs'

const PORT = process.env.AGENT_BROWSER_CDP_PORT ?? '9222'
const DATA_DIR =
  process.env.AGENT_BROWSER_DATA_DIR ?? `${process.env.HOME}/.agent-chrome`
const SHOW_FLAG = `${DATA_DIR}/.show`

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
const cdp = await browser.newBrowserCDPSession()

const minimizeWindowOf = async (targetId) => {
  if (existsSync(SHOW_FLAG)) return
  try {
    const { windowId } = await cdp.send('Browser.getWindowForTarget', {
      targetId,
    })
    const { bounds } = await cdp.send('Browser.getWindowBounds', { windowId })
    if (bounds.windowState !== 'minimized') {
      await cdp.send('Browser.setWindowBounds', {
        windowId,
        bounds: { windowState: 'minimized' },
      })
    }
  } catch {
    // Target may be gone already, or windowless (workers etc.) — fine.
  }
}

cdp.on('Target.targetCreated', ({ targetInfo }) => {
  if (targetInfo.type === 'page') void minimizeWindowOf(targetInfo.targetId)
})
await cdp.send('Target.setDiscoverTargets', { discover: true })

// Ensure at least one (minimized) window exists so new tabs join it instead
// of spawning fresh windows, and sweep any currently visible windows.
const ctx = browser.contexts()[0]
if (ctx && ctx.pages().length === 0) {
  await ctx.newPage()
}
const { targetInfos } = await cdp.send('Target.getTargets')
for (const t of targetInfos) {
  if (t.type === 'page') await minimizeWindowOf(t.targetId)
}

// Low-frequency sweep as a backstop (also re-minimizes after `hide`).
setInterval(async () => {
  try {
    const { targetInfos } = await cdp.send('Target.getTargets')
    for (const t of targetInfos) {
      if (t.type === 'page') await minimizeWindowOf(t.targetId)
    }
  } catch {
    process.exit(1) // browser went away; run.sh/launchd restarts us
  }
}, 5000)
