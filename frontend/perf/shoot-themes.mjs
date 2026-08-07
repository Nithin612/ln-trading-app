/**
 * Screenshot the theme gallery in every theme (Phase 5 visual smoke).
 *
 * Same zero-dependency CDP approach as run-bench.mjs. Writes full-page PNGs so
 * the new components can be inspected in themes nobody looks at by accident.
 *
 *   node perf/shoot-themes.mjs --out /tmp/themes [--url http://localhost:5199]
 */

import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const arg = (n, d) => {
  const i = process.argv.indexOf(`--${n}`)
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : d
}

const BASE = arg('url', 'http://localhost:5199')
const OUT = arg('out', '/tmp/themes')
const PORT = Number(arg('port', '9355'))
const THEMES = (arg('themes', 'slate,daybreak,carbon,midnight,ocean')).split(',')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const profile = await mkdtemp(join(tmpdir(), 'shoot-chrome-'))
const chrome = spawn('/usr/bin/google-chrome', [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
  '--force-device-scale-factor=1', '--window-size=1600,1200', 'about:blank',
], { stdio: 'ignore' })

const cleanup = async () => {
  chrome.kill('SIGKILL')
  await rm(profile, { recursive: true, force: true }).catch(() => {})
}

try {
  await mkdir(OUT, { recursive: true })
  let up = false
  for (let i = 0; i < 100 && !up; i++) {
    try { await fetch(`http://127.0.0.1:${PORT}/json/version`); up = true } catch { await sleep(100) }
  }
  if (!up) throw new Error('chrome debugging port never came up')

  for (const theme of THEMES) {
    const url = `${BASE}/perf/theme-gallery.html?theme=${theme}`
    const target = await (await fetch(
      `http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' },
    )).json()
    const ws = new WebSocket(target.webSocketDebuggerUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    let id = 1
    const pending = new Map()
    ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data)
      const p = pending.get(m.id)
      if (p) { pending.delete(m.id); m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result) }
    })
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const i = id++; pending.set(i, { resolve, reject })
      ws.send(JSON.stringify({ id: i, method, params }))
    })

    await send('Page.enable')
    await sleep(2500) // let styles + fonts settle
    const { cssContentSize } = await send('Page.getLayoutMetrics')
    const shot = await send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: 1600, height: Math.min(cssContentSize.height, 6000), scale: 1 },
    })
    const file = join(OUT, `${theme}.png`)
    await writeFile(file, Buffer.from(shot.data, 'base64'))
    console.log(`${theme} -> ${file} (${Math.round(cssContentSize.height)}px tall)`)
    // Just drop the socket — awaiting a CDP call after close() would never
    // settle, and Chrome is killed wholesale at the end anyway.
    ws.close()
  }
  await cleanup()
  process.exit(0)
} catch (e) {
  console.error(String(e))
  await cleanup()
  process.exit(2)
}
