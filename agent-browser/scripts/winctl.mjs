// Window control for the agent browser: `show` restores + focuses the
// window for manual interaction, `minimize` puts everything away again.
import { chromium } from 'playwright-core'
import { execFileSync } from 'node:child_process'

const PORT = process.env.AGENT_BROWSER_CDP_PORT ?? '9222'
const mode = process.argv[2]
if (!['show', 'minimize'].includes(mode)) {
  console.error('usage: winctl.mjs show|minimize')
  process.exit(2)
}

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
const cdp = await browser.newBrowserCDPSession()
const { targetInfos } = await cdp.send('Target.getTargets')
for (const t of targetInfos.filter((t) => t.type === 'page')) {
  try {
    const { windowId } = await cdp.send('Browser.getWindowForTarget', {
      targetId: t.targetId,
    })
    await cdp.send('Browser.setWindowBounds', {
      windowId,
      bounds: { windowState: mode === 'show' ? 'normal' : 'minimized' },
    })
  } catch {}
}
if (mode === 'show') {
  // Bring the agent instance (identified by its data dir) to front.
  const pid = execFileSync('pgrep', ['-f', 'user-data-dir=.*agent-chrome'])
    .toString()
    .split('\n')[0]
    .trim()
  execFileSync('osascript', [
    '-e',
    `tell application "System Events" to set frontmost of (first process whose unix id is ${pid}) to true`,
  ])
}
await browser.close()
