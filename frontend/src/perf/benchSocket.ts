/**
 * WebSocket stand-in for the live-table benchmark.
 *
 * Installed on `window` before the app mounts so `useLiveQuotes` exercises its
 * real message path unmodified — the hook is the thing under test, so it must
 * not know it is being benchmarked. Lives in its own module because a file that
 * exports both a component and a helper breaks react-refresh.
 */

export class BenchSocket {
  static current: BenchSocket | null = null
  static readonly OPEN = 1

  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null

  constructor() {
    BenchSocket.current = this
    setTimeout(() => {
      this.readyState = BenchSocket.OPEN
      this.onopen?.()
    }, 0)
  }

  send() {}

  close() {
    this.readyState = 3
  }
}

/** Must run before anything constructs a WebSocket. */
export function installBenchSocket() {
  ;(window as unknown as { WebSocket: unknown }).WebSocket = BenchSocket
}
