/**
 * Live-table browser benchmark (Phase 5 slice 5.5).
 *
 * Closes the one budget row that jsdom cannot: "UI live-table commit under full
 * tick rate ≤ 16 ms (60 fps)" (docs/PERFORMANCE.md). This mounts the REAL
 * pieces — `useLiveQuotes`, `useVirtualRows`, `PriceCell`, the themed table —
 * in a real browser with real layout and paint, drives them from a stubbed
 * WebSocket at a chosen tick rate, and reports:
 *
 *  - **React commit duration** per commit, via `<Profiler>` `actualDuration`.
 *    This is literally the quantity the budget names.
 *  - **Frame intervals** from rAF timestamps, and how many exceeded 16.7 ms.
 *  - **Long tasks** (>50 ms main-thread blocks) via PerformanceObserver.
 *
 * It is NOT wired to the backend on purpose: the tick→publish path has its own
 * measured budget, and the market is shut outside session hours. What is under
 * test here is the client's cost to apply and paint a full-rate tape.
 *
 * Served by the dev server at /perf/live-table-bench.html and driven headlessly
 * by `frontend/perf/run-bench.mjs`, which reads `window.__BENCH_RESULT__`.
 */

import { Profiler, useEffect, useMemo, useRef, useState } from 'react'

import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { useVirtualRows } from '@/hooks/useVirtualRows'
import { PriceCell } from '@/components/ui/PriceCell'
import { VirtualSpacer, VirtualViewport } from '@/components/ui/virtual-table'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { formatINR, formatPct } from '@/lib/format'
import { BenchSocket } from './benchSocket'

const ROW_HEIGHT = 41
const COLUMNS = 6

export interface BenchResult {
  rows: number
  ticksPerSecond: number
  durationMs: number
  ticksDelivered: number
  commits: number
  commitMs: { p50: number; p95: number; p99: number; max: number }
  frameMs: { p50: number; p95: number; p99: number; max: number }
  frames: number
  /**
   * Genuinely dropped frames. NOT "> 16.7": a 60 Hz vsync lands at 16.67–16.8
   * ms, so counting that as a drop reports jitter as jank. A frame past 20 ms
   * missed its slot; past 33 ms the user sees a visible stutter.
   */
  framesOver20: number
  framesOver33: number
  longTasks: number
  longTaskMsTotal: number
}

declare global {
  interface Window {
    __BENCH_RESULT__?: BenchResult
    __BENCH_ERROR__?: string
  }
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0
  const i = Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1))
  return Math.round(sorted[i] * 1000) / 1000
}

const params = new URLSearchParams(window.location.search)
const ROWS = Number(params.get('rows') ?? 300)
const TICKS_PER_SECOND = Number(params.get('tps') ?? 2000)
const DURATION_MS = Number(params.get('ms') ?? 10_000)
/** Ticks are delivered in bursts, as a batched fan-out really arrives. */
const BURST_INTERVAL_MS = 20

const SYMBOLS = Array.from({ length: ROWS }, (_, i) => `SYM${String(i).padStart(4, '0')}`)
const BASE_PRICES = SYMBOLS.map((_, i) => 100 + (i % 500))

export function LiveTableBench() {
  const viewportRef = useRef<HTMLDivElement>(null)
  const commitDurations = useRef<number[]>([])
  const frameTimes = useRef<number[]>([])
  const ticksDelivered = useRef(0)
  const longTasks = useRef<number[]>([])
  const [done, setDone] = useState(false)

  const symbols = useMemo(() => SYMBOLS, [])
  const { quotes } = useLiveQuotes(symbols)
  const win = useVirtualRows(viewportRef, { count: ROWS, rowHeight: ROW_HEIGHT })

  useEffect(() => {
    let stopped = false
    let rafId = 0
    let last = performance.now()

    // Frame cadence.
    const onFrame = (t: number) => {
      frameTimes.current.push(t - last)
      last = t
      if (!stopped) rafId = requestAnimationFrame(onFrame)
    }
    rafId = requestAnimationFrame(onFrame)

    // Main-thread blocks.
    let observer: PerformanceObserver | undefined
    try {
      observer = new PerformanceObserver((list) => {
        for (const e of list.getEntries()) longTasks.current.push(e.duration)
      })
      observer.observe({ entryTypes: ['longtask'] })
    } catch {
      /* longtask unsupported — reported as 0 */
    }

    // Tick driver: deliver the per-burst share every BURST_INTERVAL_MS.
    const perBurst = Math.max(1, Math.round((TICKS_PER_SECOND * BURST_INTERVAL_MS) / 1000))
    let cursor = 0
    const pump = setInterval(() => {
      const sock = BenchSocket.current
      if (!sock || sock.readyState !== BenchSocket.OPEN) return
      for (let i = 0; i < perBurst; i++) {
        const idx = cursor++ % SYMBOLS.length
        // Move the price every tick so PriceCell actually flashes and the DOM
        // genuinely changes — a constant price would flatter the numbers.
        const ltp = BASE_PRICES[idx] + ((cursor % 97) - 48) / 20
        sock.onmessage?.({
          data: `{"type":"ltp","data":{"symbol":"${SYMBOLS[idx]}","ltp":${ltp},"ts":"t"}}`,
        })
        ticksDelivered.current++
      }
    }, BURST_INTERVAL_MS)

    const stop = setTimeout(() => {
      stopped = true
      clearInterval(pump)
      cancelAnimationFrame(rafId)
      observer?.disconnect()

      const commits = [...commitDurations.current].sort((a, b) => a - b)
      // Drop the first frame delta (mount) — it is not steady state.
      const frames = [...frameTimes.current.slice(1)].sort((a, b) => a - b)
      window.__BENCH_RESULT__ = {
        rows: ROWS,
        ticksPerSecond: TICKS_PER_SECOND,
        durationMs: DURATION_MS,
        ticksDelivered: ticksDelivered.current,
        commits: commits.length,
        commitMs: {
          p50: quantile(commits, 0.5), p95: quantile(commits, 0.95),
          p99: quantile(commits, 0.99), max: quantile(commits, 1),
        },
        frameMs: {
          p50: quantile(frames, 0.5), p95: quantile(frames, 0.95),
          p99: quantile(frames, 0.99), max: quantile(frames, 1),
        },
        frames: frames.length,
        framesOver20: frames.filter((f) => f > 20).length,
        framesOver33: frames.filter((f) => f > 33).length,
        longTasks: longTasks.current.length,
        longTaskMsTotal: Math.round(longTasks.current.reduce((a, b) => a + b, 0)),
      }
      setDone(true)
    }, DURATION_MS)

    return () => {
      stopped = true
      clearInterval(pump)
      clearTimeout(stop)
      cancelAnimationFrame(rafId)
      observer?.disconnect()
    }
  }, [])

  const visible = useMemo(
    () => SYMBOLS.slice(win.startIndex, win.endIndex),
    [win.startIndex, win.endIndex],
  )

  return (
    <Profiler
      id="live-table"
      onRender={(_id, _phase, actualDuration) => {
        commitDurations.current.push(actualDuration)
      }}
    >
      <div style={{ padding: 16 }}>
        <h1 data-testid="bench-status">
          {done ? 'BENCH_DONE' : `running ${ROWS} rows @ ${TICKS_PER_SECOND} ticks/s`}
        </h1>
        <VirtualViewport ref={viewportRef} className="max-h-[70vh]">
          <Table aria-label="bench live table">
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead numeric>LTP</TableHead>
                <TableHead numeric>Entry</TableHead>
                <TableHead numeric>SL</TableHead>
                <TableHead numeric>TP</TableHead>
                <TableHead numeric>Conf</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <VirtualSpacer height={win.padTop} colSpan={COLUMNS} />
              {visible.map((sym, i) => {
                const base = BASE_PRICES[win.startIndex + i]
                return (
                  <TableRow key={sym} style={{ height: ROW_HEIGHT }}>
                    <TableCell>{sym}</TableCell>
                    <TableCell numeric>
                      <PriceCell
                        value={quotes[sym]?.ltp}
                        format={(n) => `₹${formatINR(n)}`}
                      />
                    </TableCell>
                    <TableCell numeric>₹{formatINR(base)}</TableCell>
                    <TableCell numeric>₹{formatINR(base * 0.98)}</TableCell>
                    <TableCell numeric>₹{formatINR(base * 1.04)}</TableCell>
                    <TableCell numeric>{formatPct(72, { signed: false })}</TableCell>
                  </TableRow>
                )
              })}
              <VirtualSpacer height={win.padBottom} colSpan={COLUMNS} />
            </TableBody>
          </Table>
        </VirtualViewport>
      </div>
    </Profiler>
  )
}

