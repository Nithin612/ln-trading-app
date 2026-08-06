import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useLiveQuotes } from '@/hooks/useLiveQuotes'
import { useAuthStore } from '@/store/authStore'

/** Minimal WebSocket double: the hook drives it via the standard events. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  url: string
  readyState = FakeWebSocket.CONNECTING
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    if (this.readyState === FakeWebSocket.CLOSED) return
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code: 1000 })
  }

  // test drivers
  serverOpen() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  serverMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }

  serverClose(code: number) {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.({ code })
  }
}

function lastSocket(): FakeWebSocket {
  const ws = FakeWebSocket.instances.at(-1)
  if (!ws) throw new Error('no socket created')
  return ws
}

function tick(symbol: string, ltp: number) {
  return { type: 'ltp', data: { symbol, ltp, ts: '2026-08-06T10:00:00Z' } }
}

/** One animation frame under fake timers (rAF is stubbed onto setTimeout). */
const FRAME_MS = 16

describe('useLiveQuotes v2', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    // Drive rAF off the fake timer clock so batching is deterministic.
    vi.stubGlobal('requestAnimationFrame', (cb: () => void) =>
      setTimeout(cb, FRAME_MS) as unknown as number,
    )
    vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))
    useAuthStore.setState({ accessToken: 'test-token' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('connects with the token and subscribes to the initial symbols on open', () => {
    renderHook(() => useLiveQuotes(['RELIANCE', 'TCS']))
    const ws = lastSocket()
    expect(ws.url).toContain('token=test-token')
    expect(ws.url).toMatch(/^ws:\/\//) // ws under http, wss under https

    act(() => ws.serverOpen())
    expect(ws.sent).toEqual([JSON.stringify({ subscribe: ['RELIANCE', 'TCS'] })])
  })

  it('coalesces a burst of ticks into ONE render per frame, newest price winning', () => {
    let renders = 0
    const { result } = renderHook(() => {
      renders++
      return useLiveQuotes(['RELIANCE'])
    })
    const ws = lastSocket()
    act(() => ws.serverOpen())

    const before = renders
    act(() => {
      ws.serverMessage(tick('RELIANCE', 2800))
      ws.serverMessage(tick('RELIANCE', 2810))
      ws.serverMessage(tick('RELIANCE', 2820))
    })
    // buffered in a ref — nothing applied, nothing re-rendered yet
    expect(result.current.quotes).toEqual({})
    expect(renders).toBe(before)

    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.RELIANCE.ltp).toBe(2820) // latest wins
    expect(renders).toBe(before + 1) // exactly one render for the whole burst
  })

  it('applies quotes for many symbols in a single frame', () => {
    const { result } = renderHook(() => useLiveQuotes(['A', 'B', 'C']))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.serverMessage(tick('A', 10))
      ws.serverMessage(tick('B', 20))
      ws.serverMessage(tick('C', 30))
      ws.serverMessage(tick('A', 11))
    })
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.A.ltp).toBe(11)
    expect(result.current.quotes.B.ltp).toBe(20)
    expect(result.current.quotes.C.ltp).toBe(30)
  })

  it('does NOT resubscribe when re-rendered with an equal symbol set', () => {
    // Regression: v1 keyed an effect on the `symbols` ARRAY, and callers pass
    // a fresh literal every render — so every render re-sent `subscribe`, and
    // the connect effect tore the socket down on any list change.
    const { rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['RELIANCE', 'TCS'] },
    })
    const ws = lastSocket()
    act(() => ws.serverOpen())
    expect(ws.sent).toHaveLength(1)

    rerender({ syms: ['RELIANCE', 'TCS'] }) // new array, same set
    rerender({ syms: ['TCS', 'RELIANCE'] }) // same set, different order
    expect(ws.sent).toHaveLength(1)
    expect(FakeWebSocket.instances).toHaveLength(1) // socket never churned
  })

  it('sends only the delta when the symbol set changes, and prunes dropped quotes', () => {
    const { result, rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['A', 'B'] },
    })
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.serverMessage(tick('A', 10))
      ws.serverMessage(tick('B', 20))
    })
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(Object.keys(result.current.quotes).sort()).toEqual(['A', 'B'])

    act(() => rerender({ syms: ['B', 'C'] }))
    expect(JSON.parse(ws.sent[1])).toEqual({ subscribe: ['C'] })
    expect(JSON.parse(ws.sent[2])).toEqual({ unsubscribe: ['A'] })
    // A's stale price must not linger — a price under an untracked symbol
    // is a money-UI hazard.
    expect(result.current.quotes.A).toBeUndefined()
    expect(result.current.quotes.B.ltp).toBe(20)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('re-sends the full symbol set after a reconnect', () => {
    const { rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['A'] },
    })
    const first = lastSocket()
    act(() => first.serverOpen())
    act(() => rerender({ syms: ['A', 'B'] }))

    act(() => first.serverClose(1006))
    act(() => vi.advanceTimersByTime(3000))
    const second = lastSocket()
    expect(second).not.toBe(first)

    act(() => second.serverOpen())
    // the server starts clean, so a delta would silently under-subscribe
    expect(JSON.parse(second.sent[0])).toEqual({ subscribe: ['A', 'B'] })
  })

  it('close code 4401 sets authFailed and never reconnect-loops', () => {
    const { result } = renderHook(() => useLiveQuotes(['A']))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => ws.serverClose(4401))
    expect(result.current.authFailed).toBe(true)
    expect(result.current.connected).toBe(false)
    act(() => vi.advanceTimersByTime(30_000))
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('keys candles by symbol:timeframe and caps the signal feed at 50 newest', () => {
    const { result } = renderHook(() => useLiveQuotes(['A']))
    const ws = lastSocket()
    act(() => ws.serverOpen())

    act(() => {
      ws.serverMessage({
        type: 'candle',
        data: {
          symbol: 'A', timeframe: '5m', time: 't', open: 1, high: 2, low: 0.5,
          close: 1.5, volume: 100, is_complete: false,
        },
      })
      for (let i = 0; i < 60; i++) ws.serverMessage({ type: 'signal', data: { n: i } })
    })
    act(() => vi.advanceTimersByTime(FRAME_MS))

    expect(result.current.candles['A:5m'].close).toBe(1.5)
    expect(result.current.signals).toHaveLength(50)
    expect(result.current.signals[0]).toEqual({ n: 59 }) // newest first
  })

  it('ignores malformed frames instead of killing the stream', () => {
    const { result } = renderHook(() => useLiveQuotes(['A']))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.onmessage?.({ data: 'not json' })
      ws.serverMessage(tick('A', 42))
    })
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.A.ltp).toBe(42)
  })

  it('still flushes where requestAnimationFrame is unavailable', () => {
    // Background tabs never fire rAF; the hook falls back to a macrotask.
    vi.stubGlobal('requestAnimationFrame', undefined)
    const { result } = renderHook(() => useLiveQuotes(['A']))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => ws.serverMessage(tick('A', 99)))
    expect(result.current.quotes).toEqual({})
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.A.ltp).toBe(99)
  })

  it('prunes a dropped symbol even while the socket is down', () => {
    // Regression: the prune diffed against `subscribedRef`, which a close
    // empties — so a symbol removed during a reconnect was never pruned and
    // its last price lingered as if live when it came back.
    const { result, rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['A', 'B'] },
    })
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.serverMessage(tick('A', 10))
      ws.serverMessage(tick('B', 20))
    })
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.A.ltp).toBe(10)

    act(() => ws.serverClose(1006)) // socket down; reconnect pending
    act(() => rerender({ syms: ['B'] }))
    expect(result.current.quotes.A).toBeUndefined()
    expect(result.current.quotes.B.ltp).toBe(20)
  })

  it('does not resurrect a dropped symbol from the pending buffer', () => {
    // A tick buffered before the drop must not be re-inserted by the next flush.
    const { result, rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['A', 'B'] },
    })
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.serverMessage(tick('A', 10))
      ws.serverMessage(tick('B', 20))
    })
    // Drop A while its tick is still buffered (no frame has run yet).
    act(() => rerender({ syms: ['B'] }))
    act(() => vi.advanceTimersByTime(FRAME_MS))
    expect(result.current.quotes.A).toBeUndefined()
    expect(result.current.quotes.B.ltp).toBe(20)
  })

  it('ignores a stale socket close after a newer socket is live', () => {
    // StrictMode double-mounts: an aborted socket's close landing after the
    // live one opened used to clear `connected` and empty the subscribed set,
    // permanently disabling unsubscribe for the session.
    const { result, rerender } = renderHook(({ syms }) => useLiveQuotes(syms), {
      initialProps: { syms: ['A', 'B'] },
    })
    const stale = lastSocket()
    act(() => stale.serverOpen())

    // Socket drops, a reconnect takes over and is live.
    act(() => stale.serverClose(1006))
    act(() => vi.advanceTimersByTime(3000))
    const live = lastSocket()
    expect(live).not.toBe(stale)
    act(() => live.serverOpen())
    expect(result.current.connected).toBe(true)

    // The superseded socket's close arrives LATE — it must be ignored, or it
    // clears `connected` and empties the subscribed set.
    act(() => stale.onclose?.({ code: 1006 }))
    expect(result.current.connected).toBe(true)

    // And unsubscribe still works afterwards (the set wasn't wiped).
    const sentBefore = live.sent.length
    act(() => rerender({ syms: ['B'] }))
    expect(JSON.parse(live.sent[sentBefore])).toEqual({ unsubscribe: ['A'] })
  })

  it('cancels a pending flush on unmount', () => {
    const { unmount } = renderHook(() => useLiveQuotes(['A']))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => ws.serverMessage(tick('A', 1)))
    unmount()
    // No "setState on an unmounted component" and no pending timer work.
    expect(() => vi.advanceTimersByTime(1000)).not.toThrow()
    expect(vi.getTimerCount()).toBe(0)
  })
})
