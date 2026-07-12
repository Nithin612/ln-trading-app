import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAlertStream } from '@/hooks/useAlertStream'
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

const ALERT = {
  id: '1752212345678-0',
  sid: '42',
  level_id: '1001',
  tag: 'cross_up',
  price: '2850.5000',
  ts: '1752212345',
  day: '2026-07-13',
  source: 'pdh',
  style: 'market',
}

function lastSocket(): FakeWebSocket {
  const ws = FakeWebSocket.instances.at(-1)
  if (!ws) throw new Error('no socket created')
  return ws
}

describe('useAlertStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    useAuthStore.setState({ accessToken: 'test-token' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('connects with the token and subscribes to all alerts by default', () => {
    renderHook(() => useAlertStream())
    const ws = lastSocket()
    expect(ws.url).toContain('token=test-token')
    act(() => ws.serverOpen())
    expect(ws.sent).toEqual([JSON.stringify({ subscribe_alerts: true })])
  })

  it('parses alert frames (string fields → typed) and flushes bursts as one update', () => {
    const { result } = renderHook(() => useAlertStream())
    const ws = lastSocket()
    act(() => ws.serverOpen())

    act(() => {
      ws.serverMessage({ type: 'alert', data: ALERT })
      ws.serverMessage({ type: 'alert', data: { ...ALERT, id: '1752212345679-0', tag: 'near' } })
      ws.serverMessage({ type: 'ltp', data: { symbol: 'X' } }) // ignored
    })
    expect(result.current.alerts).toEqual([]) // buffered, not yet flushed

    act(() => vi.advanceTimersByTime(200))
    expect(result.current.alerts).toHaveLength(2)
    // newest first
    expect(result.current.alerts[0].id).toBe('1752212345679-0')
    expect(result.current.alerts[1]).toMatchObject({
      id: ALERT.id,
      sid: 42,
      ts: 1752212345,
      price: '2850.5000',
      tag: 'cross_up',
      source: 'pdh',
      style: 'market',
      signalId: null,
    })
  })

  it('drops malformed alert frames instead of crashing the stream', () => {
    const { result } = renderHook(() => useAlertStream())
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      ws.serverMessage({ type: 'alert', data: { ...ALERT, sid: 'not-a-number' } })
      ws.serverMessage({ type: 'alert', data: 'garbage' })
      ws.serverMessage({ type: 'alert', data: { ...ALERT, id: 'x-1', price: 'oops' } }) // would render ₹NaN
      ws.serverMessage({ type: 'alert', data: ALERT })
    })
    act(() => vi.advanceTimersByTime(200))
    expect(result.current.alerts).toHaveLength(1)
  })

  it('re-sends the style filter on setStyles and after reconnect', () => {
    const { result } = renderHook(() => useAlertStream())
    const first = lastSocket()
    act(() => first.serverOpen())

    act(() => result.current.setStyles(['swing', 'intraday']))
    expect(first.sent.at(-1)).toBe(
      JSON.stringify({ subscribe_alerts: { styles: ['swing', 'intraday'] } }),
    )
    expect(result.current.styles).toEqual(['swing', 'intraday'])

    // non-auth close → reconnect after 3s with the SAME filter
    act(() => first.serverClose(1006))
    expect(result.current.connected).toBe(false)
    act(() => vi.advanceTimersByTime(3000))
    const second = lastSocket()
    expect(second).not.toBe(first)
    act(() => second.serverOpen())
    expect(second.sent).toEqual([
      JSON.stringify({ subscribe_alerts: { styles: ['swing', 'intraday'] } }),
    ])
    expect(result.current.connected).toBe(true)
  })

  it('close code 4401 sets authFailed and never reconnect-loops', () => {
    const { result } = renderHook(() => useAlertStream())
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => ws.serverClose(4401))
    expect(result.current.authFailed).toBe(true)
    expect(result.current.connected).toBe(false)
    act(() => vi.advanceTimersByTime(30_000))
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('caps the retained list at 100 newest alerts', () => {
    const { result } = renderHook(() => useAlertStream())
    const ws = lastSocket()
    act(() => ws.serverOpen())
    act(() => {
      for (let i = 0; i < 120; i++) {
        ws.serverMessage({ type: 'alert', data: { ...ALERT, id: `175221234${5000 + i}-0` } })
      }
    })
    act(() => vi.advanceTimersByTime(200))
    expect(result.current.alerts).toHaveLength(100)
    expect(result.current.alerts[0].id).toBe('1752212345119-0') // newest kept
  })
})
