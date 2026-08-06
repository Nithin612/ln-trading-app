/**
 * Headless driver for the live-table browser benchmark (Phase 5 slice 5.5).
 *
 * Launches system Chrome with remote debugging, loads the bench page from the
 * running Vite dev server, waits for `window.__BENCH_RESULT__`, prints it as
 * JSON, and exits non-zero if the commit budget is missed.
 *
 * Zero dependencies on purpose — this box cannot install packages (the pnpm
 * store its node_modules is linked to was pruned by a snap refresh), so this
 * speaks CDP over Node 22's built-in global WebSocket.
 *
 *   node perf/run-bench.mjs [--url http://localhost:5173] [--rows 300]
 *                           [--tps 2000] [--ms 10000] [--budget 16.7]
 */

import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`)
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback
}

const BASE = arg('url', 'http://localhost:5173')
const ROWS = arg('rows', '300')
const TPS = arg('tps', '2000')
const MS = Number(arg('ms', '10000'))
const BUDGET_MS = Number(arg('budget', '16.7'))
const CHROME = arg('chrome', '/usr/bin/google-chrome')
const PORT = Number(arg('port', '9333'))

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function getJson(path, method = 'GET') {
  const res = await fetch(`http://127.0.0.1:${PORT}${path}`, { method })
  if (!res.ok) throw new Error(`CDP ${path} -> ${res.status}`)
  return res.json()
}

/** Minimal CDP client: send a command, await its matching id. */
function cdp(ws) {
  let nextId = 1
  const pending = new Map()
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data)
    const p = pending.get(msg.id)
    if (p) {
      pending.delete(msg.id)
      msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result)
    }
  })
  return (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++
      pending.set(id, { resolve, reject })
      ws.send(JSON.stringify({ id, method, params }))
    })
}

async function main() {
  const profile = await mkdtemp(join(tmpdir(), 'bench-chrome-'))
  const chrome = spawn(
    CHROME,
    [
      '--headless=new',
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-extensions',
      '--window-size=1600,1000',
      // Keep rAF running at a real cadence in headless.
      '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows',
      '--disable-background-timer-throttling',
      'about:blank',
    ],
    { stdio: 'ignore' },
  )

  const cleanup = async () => {
    chrome.kill('SIGKILL')
    await rm(profile, { recursive: true, force: true }).catch(() => {})
  }

  try {
    // Wait for the debugging endpoint.
    let version = null
    for (let i = 0; i < 100; i++) {
      try {
        version = await getJson('/json/version')
        break
      } catch {
        await sleep(100)
      }
    }
    if (!version) throw new Error('Chrome did not expose a debugging port')

    const url = `${BASE}/perf/live-table-bench.html?rows=${ROWS}&tps=${TPS}&ms=${MS}`
    // Chrome >= 111 requires PUT on /json/new.
    const target = await getJson(`/json/new?${encodeURIComponent(url)}`, 'PUT')
    const ws = new WebSocket(target.webSocketDebuggerUrl)
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true })
      ws.addEventListener('error', rej, { once: true })
    })
    const send = cdp(ws)
    await send('Runtime.enable')

    const deadline = Date.now() + MS + 60_000
    let result = null
    while (Date.now() < deadline) {
      const { result: r } = await send('Runtime.evaluate', {
        expression: 'JSON.stringify(window.__BENCH_RESULT__ ?? null)',
        returnByValue: true,
      })
      const parsed = r?.value ? JSON.parse(r.value) : null
      if (parsed) {
        result = parsed
        break
      }
      await sleep(500)
    }
    if (!result) throw new Error('benchmark did not report a result in time')

    result.chrome = version.Browser
    console.log(JSON.stringify(result, null, 2))

    const withinBudget = result.commitMs.p99 <= BUDGET_MS
    console.log(
      `\ncommit p99 ${result.commitMs.p99} ms vs budget ${BUDGET_MS} ms -> ` +
        (withinBudget ? 'MET' : 'MISSED'),
    )
    console.log(
      `frames ${result.frames} (${result.framesOver20} > 20 ms, ` +
        `${result.framesOver33} > 33 ms), long tasks ${result.longTasks}, ` +
        `ticks delivered ${result.ticksDelivered}`,
    )
    await cleanup()
    process.exit(withinBudget ? 0 : 1)
  } catch (err) {
    console.error(String(err))
    await cleanup()
    process.exit(2)
  }
}

void main()
