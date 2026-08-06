/**
 * Live-layer render-cost measurements (Phase 5 slice 5.5).
 *
 * These are the DETERMINISTIC half of the Phase-5 perf budget. They pin the
 * property the UI budget actually rests on — that render count is a function of
 * FRAMES, not of tick count — at a tick rate well past anything the live worker
 * produces, and they fail if that decoupling ever regresses.
 *
 * What they are NOT: an in-browser frame-rate measurement. jsdom does no
 * layout, paint or compositing, so "≤ 16 ms commit / 60 fps" cannot be
 * concluded here — that verdict needs a real browser against a replayed
 * session and is recorded as unproven in docs/PERFORMANCE.md.
 */

import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { useAuthStore } from '@/store/authStore'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static readonly OPEN = 1
  static readonly CLOSED = 3

  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null

  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
  }
  send(d: string) { this.sent.push(d) }
  close() { this.readyState = FakeWebSocket.CLOSED }
  serverOpen() { this.readyState = FakeWebSocket.OPEN; this.onopen?.() }
  tick(symbol: string, ltp: number) {
    this.onmessage?.({
      data: JSON.stringify({ type: 'ltp', data: { symbol, ltp, ts: 't' } }),
    })
  }
}

const FRAME_MS = 16

/** Universe sizes: ~2,055 instruments is the real full-universe subscription. */
const SYMBOLS_500 = Array.from({ length: 500 }, (_, i) => `SYM${i}`)

beforeEach(() => {
  vi.useFakeTimers()
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => setTimeout(cb, FRAME_MS) as unknown as number)
  vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))
  useAuthStore.setState({ accessToken: 'tok' })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('live layer render cost', () => {
  it('renders once per frame regardless of how many ticks land in it', () => {
    let renders = 0
    renderHook(() => {
      renders++
      return useLiveQuotes(SYMBOLS_500)
    })
    const ws = FakeWebSocket.instances[0]
    act(() => ws.serverOpen())
    const before = renders

    const FRAMES = 60
    const TICKS_PER_FRAME = 200 // 12,000 ticks total — far past the real rate
    // One act() PER FRAME: batching everything into a single act would measure
    // React's own batching (it collapses to 1 render), not the per-frame flush.
    for (let f = 0; f < FRAMES; f++) {
      act(() => {
        for (let t = 0; t < TICKS_PER_FRAME; t++) {
          ws.tick(SYMBOLS_500[t % SYMBOLS_500.length], 100 + t)
        }
        vi.advanceTimersByTime(FRAME_MS)
      })
    }

    // The whole point: 12,000 ticks cost 60 renders, not 12,000.
    expect(renders - before).toBe(FRAMES)
  })

  it('costs the same renders whether 10 or 10,000 ticks arrive in one frame', () => {
    function measure(tickCount: number): number {
      let renders = 0
      const { unmount } = renderHook(() => {
        renders++
        return useLiveQuotes(SYMBOLS_500)
      })
      const ws = FakeWebSocket.instances.at(-1)!
      act(() => ws.serverOpen())
      const before = renders
      act(() => {
        for (let t = 0; t < tickCount; t++) {
          ws.tick(SYMBOLS_500[t % SYMBOLS_500.length], 100 + t)
        }
        vi.advanceTimersByTime(FRAME_MS)
      })
      unmount()
      return renders - before
    }

    expect(measure(10)).toBe(1)
    expect(measure(10_000)).toBe(1)
  })

  it('keeps only the newest price per symbol from a coalesced frame', () => {
    // Coalescing is only sound because a last-traded price is
    // latest-wins; assert that explicitly so nobody "optimises" it into
    // dropping the wrong end.
    const { result } = renderHook(() => useLiveQuotes(['A', 'B']))
    const ws = FakeWebSocket.instances[0]
    act(() => ws.serverOpen())
    act(() => {
      for (let i = 1; i <= 500; i++) {
        ws.tick('A', i)
        ws.tick('B', 1000 + i)
      }
      vi.advanceTimersByTime(FRAME_MS)
    })
    expect(result.current.quotes.A.ltp).toBe(500)
    expect(result.current.quotes.B.ltp).toBe(1500)
  })

  it('a frame with no ticks costs no renders', () => {
    let renders = 0
    renderHook(() => {
      renders++
      return useLiveQuotes(SYMBOLS_500)
    })
    const ws = FakeWebSocket.instances[0]
    act(() => ws.serverOpen())
    const before = renders
    act(() => vi.advanceTimersByTime(FRAME_MS * 100))
    // No rAF is scheduled when nothing arrived — an idle tape is free.
    expect(renders).toBe(before)
  })
})
