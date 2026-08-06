import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useVirtualRows } from '@/hooks/useVirtualRows'

const ROW_H = 36
const VIEWPORT_H = 360 // 10 rows visible

/**
 * jsdom does no layout, so clientHeight/scrollTop are defined explicitly.
 * scrollTop stays writable so tests can drive scrolling.
 */
function makeViewport(height = VIEWPORT_H) {
  const el = document.createElement('div')
  Object.defineProperty(el, 'clientHeight', { value: height, configurable: true })
  Object.defineProperty(el, 'scrollTop', { value: 0, writable: true, configurable: true })
  return el
}

function scrollTo(el: HTMLElement, top: number) {
  ;(el as unknown as { scrollTop: number }).scrollTop = top
  el.dispatchEvent(new Event('scroll'))
}

describe('useVirtualRows', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', (cb: () => void) => setTimeout(cb, 16) as unknown as number)
    vi.stubGlobal('cancelAnimationFrame', (id: number) => clearTimeout(id))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('renders every row below the virtualization threshold', () => {
    // .claude/rules/ui.md: virtualize at >=200 rows. Under that, small tables
    // (and their existing tests) must behave exactly as before.
    const ref = { current: makeViewport() }
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 50, rowHeight: ROW_H }),
    )
    expect(result.current).toEqual({
      virtualized: false, startIndex: 0, endIndex: 50, padTop: 0, padBottom: 0,
    })
  })

  it('windows a large dataset to the viewport plus overscan', () => {
    const ref = { current: makeViewport() }
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 1000, rowHeight: ROW_H, overscan: 8 }),
    )
    // at scrollTop 0: first = 0, visible = 360/36 = 10, last = 0 + 10 + 2*8
    expect(result.current.virtualized).toBe(true)
    expect(result.current.startIndex).toBe(0)
    expect(result.current.endIndex).toBe(26)
    expect(result.current.padTop).toBe(0)
    expect(result.current.padBottom).toBe((1000 - 26) * ROW_H)
  })

  it('reserves the full dataset height across window + spacers', () => {
    const ref = { current: makeViewport() }
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 1000, rowHeight: ROW_H }),
    )
    const { startIndex, endIndex, padTop, padBottom } = result.current
    const rendered = (endIndex - startIndex) * ROW_H
    // Total scroll geometry must equal the un-virtualized table's height,
    // or the scrollbar lies about the dataset.
    expect(padTop + rendered + padBottom).toBe(1000 * ROW_H)
  })

  it('moves the window on scroll and keeps the geometry exact', () => {
    const ref = { current: makeViewport() }
    const el = ref.current
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 1000, rowHeight: ROW_H, overscan: 8 }),
    )

    act(() => {
      scrollTo(el, 100 * ROW_H) // row 100 at the top
      vi.advanceTimersByTime(16)
    })

    // first = floor(3600/36) - 8 = 92; last = 92 + 10 + 16 = 118
    expect(result.current.startIndex).toBe(92)
    expect(result.current.endIndex).toBe(118)
    expect(result.current.padTop).toBe(92 * ROW_H)
    expect(result.current.padBottom).toBe((1000 - 118) * ROW_H)
    const rendered = (118 - 92) * ROW_H
    expect(result.current.padTop + rendered + result.current.padBottom).toBe(1000 * ROW_H)
  })

  it('coalesces a burst of scroll events into one recompute per frame', () => {
    const ref = { current: makeViewport() }
    const el = ref.current
    let renders = 0
    const { result } = renderHook(() => {
      renders++
      return useVirtualRows(ref, { count: 1000, rowHeight: ROW_H })
    })

    const before = renders
    act(() => {
      for (let i = 1; i <= 20; i++) scrollTo(el, i * ROW_H)
    })
    expect(renders).toBe(before) // nothing applied until the frame runs

    act(() => vi.advanceTimersByTime(16))
    expect(renders).toBe(before + 1)
    expect(result.current.startIndex).toBe(12) // floor(20) - 8, from the LAST scroll
  })

  it('does not re-render per scroll event while inside the same window', () => {
    const ref = { current: makeViewport() }
    const el = ref.current
    let renders = 0
    const { result } = renderHook(() => {
      renders++
      return useVirtualRows(ref, { count: 1000, rowHeight: ROW_H })
    })
    act(() => vi.advanceTimersByTime(16)) // let mount measurement settle
    const before = renders
    const windowBefore = { s: result.current.startIndex, e: result.current.endIndex }

    // Sub-row scrolling floors to the same row, so the window is unchanged.
    // React may still render ONCE when a reducer returns an identical value
    // (documented eager-bailout), but never once per scroll event.
    act(() => {
      for (let px = 1; px <= 10; px++) scrollTo(el, px)
      vi.advanceTimersByTime(16)
    })
    expect(result.current.startIndex).toBe(windowBefore.s)
    expect(result.current.endIndex).toBe(windowBefore.e)
    expect(renders - before).toBeLessThanOrEqual(1)
  })

  it('clamps when the dataset shrinks under the current window', () => {
    // A filter change can shrink `count` before the scroll effect reruns —
    // the window must never slice past the end or emit a negative spacer.
    const ref = { current: makeViewport() }
    const el = ref.current
    const { result, rerender } = renderHook(
      ({ count }) => useVirtualRows(ref, { count, rowHeight: ROW_H }),
      { initialProps: { count: 1000 } },
    )
    act(() => {
      scrollTo(el, 900 * ROW_H)
      vi.advanceTimersByTime(16)
    })
    expect(result.current.startIndex).toBeGreaterThan(300)

    rerender({ count: 300 })
    expect(result.current.startIndex).toBeLessThanOrEqual(299)
    expect(result.current.endIndex).toBeLessThanOrEqual(300)
    expect(result.current.padBottom).toBeGreaterThanOrEqual(0)
  })

  it('works without ResizeObserver and with a null viewport', () => {
    // Older browsers lack ResizeObserver; the hook must still window.
    vi.stubGlobal('ResizeObserver', undefined)
    const nullRef = { current: null }
    const { result } = renderHook(() =>
      useVirtualRows(nullRef, { count: 1000, rowHeight: ROW_H }),
    )
    // Unmeasured viewport falls back to an assumed height rather than
    // rendering a near-blank table for a frame.
    expect(result.current.virtualized).toBe(true)
    expect(result.current.startIndex).toBe(0)
    expect(result.current.endIndex).toBeGreaterThan(10)
  })

  it('recomputes when the observed container resizes', () => {
    class FakeResizeObserver {
      static last: FakeResizeObserver | null = null
      cb: () => void
      constructor(cb: () => void) {
        this.cb = cb
        FakeResizeObserver.last = this
      }
      observe() {}
      disconnect() {}
      fire() {
        this.cb()
      }
    }
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)

    const el = makeViewport(360)
    const ref = { current: el }
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 1000, rowHeight: ROW_H, overscan: 8 }),
    )
    expect(result.current.endIndex).toBe(26)

    // Container grows to 20 visible rows → the window widens.
    Object.defineProperty(el, 'clientHeight', { value: 720, configurable: true })
    act(() => FakeResizeObserver.last!.fire())
    expect(result.current.endIndex).toBe(36) // 0 + 20 + 2*8
  })

  it('treats a zero rowHeight as un-virtualizable instead of dividing by zero', () => {
    const ref = { current: makeViewport() }
    const { result } = renderHook(() =>
      useVirtualRows(ref, { count: 1000, rowHeight: 0 }),
    )
    expect(result.current.virtualized).toBe(false)
    expect(result.current.endIndex).toBe(1000)
  })
})
