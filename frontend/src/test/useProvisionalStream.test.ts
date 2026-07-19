import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { parseLeaderboard, useProvisionalStream } from '@/hooks/useProvisionalStream'
import { useAuthStore } from '@/store/authStore'

/** Minimal WebSocket double (same shape as useAlertStream.test.ts). */
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

const BOARD = {
  provisional: true,
  style: 'intraday',
  as_of: '2026-07-16T06:03:00+00:00',
  rows: [
    {
      provisional: true, stock_id: 1, symbol: 'RELIANCE', profile_key: 'rrbo',
      style: 'intraday', tf: '5m', confidence: 78, direction: 'BUY',
      gate: true, sources: ['signal'],
    },
  ],
}

describe('useProvisionalStream', () => {
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

  it('connects with the token and subscribes to the requested styles', () => {
    renderHook(() => useProvisionalStream(['intraday', 'swing']))
    const ws = lastSocket()
    expect(ws.url).toContain('token=test-token')
    act(() => ws.serverOpen())
    expect(ws.sent).toEqual([
      JSON.stringify({ subscribe_provisional: ['intraday', 'swing'] }),
    ])
  })

  it('subscribes to everything when no styles are given', () => {
    renderHook(() => useProvisionalStream([]))
    const ws = lastSocket()
    act(() => ws.serverOpen())
    expect(ws.sent).toEqual([JSON.stringify({ subscribe_provisional: true })])
  })

  it('keeps the latest snapshot per style and ignores other frame types', () => {
    const { result } = renderHook(() => useProvisionalStream(['intraday']))
    const ws = lastSocket()
    act(() => ws.serverOpen())

    act(() => {
      ws.serverMessage({ type: 'ltp', data: { symbol: 'X' } }) // ignored
      ws.serverMessage({ type: 'provisional', data: BOARD })
      ws.serverMessage({
        type: 'provisional',
        data: { ...BOARD, as_of: '2026-07-16T06:03:03+00:00', rows: [] },
      })
    })

    expect(result.current.boards.intraday.as_of).toBe('2026-07-16T06:03:03+00:00')
    expect(result.current.boards.intraday.rows).toEqual([])
    expect(result.current.connected).toBe(true)
  })

  it('refuses frames without the provisional label', () => {
    expect(parseLeaderboard({ style: 'intraday', rows: [] })).toBeNull()
    expect(parseLeaderboard({ provisional: true, style: 'intraday', rows: [] })).not.toBeNull()
  })

  it('marks authFailed on 4401 and does not reconnect', () => {
    const { result } = renderHook(() => useProvisionalStream(['intraday']))
    act(() => lastSocket().serverOpen())
    act(() => lastSocket().serverClose(4401))
    expect(result.current.authFailed).toBe(true)
    const count = FakeWebSocket.instances.length
    act(() => vi.advanceTimersByTime(10_000))
    expect(FakeWebSocket.instances.length).toBe(count)
  })

  it('reconnects after a non-auth close', () => {
    renderHook(() => useProvisionalStream(['intraday']))
    act(() => lastSocket().serverOpen())
    const before = FakeWebSocket.instances.length
    act(() => lastSocket().serverClose(1006))
    act(() => vi.advanceTimersByTime(3000))
    expect(FakeWebSocket.instances.length).toBe(before + 1)
  })
})
