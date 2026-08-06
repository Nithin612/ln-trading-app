import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { LiveAlert } from '@/hooks/useAlertStream'
import { BURST_CAP, useBrowserNotifications } from '@/hooks/useBrowserNotifications'

function alert(id: string, o: Partial<LiveAlert> = {}): LiveAlert {
  return {
    id, sid: 42, levelId: '1', tag: 'zone_enter', price: '2850.5000',
    ts: 1752212345, day: '2026-08-06', source: 'entry_zone', style: 'swing',
    signalId: 'sig-1',
    ...o,
  }
}

/** Records constructions so tests can assert what the user would see. */
function stubNotification(permission: NotificationPermission, requested = 'granted') {
  const ctor = vi.fn()
  const requestPermission = vi.fn().mockResolvedValue(requested)
  vi.stubGlobal(
    'Notification',
    Object.assign(ctor, { permission, requestPermission }),
  )
  return { ctor, requestPermission }
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('useBrowserNotifications', () => {
  it('reports unsupported when the Notification API is absent', () => {
    vi.stubGlobal('Notification', undefined)
    const { result } = renderHook(() => useBrowserNotifications([]))
    expect(result.current.supported).toBe(false)
    expect(result.current.permission).toBe('unsupported')
    expect(result.current.enabled).toBe(false)
  })

  it('never requests permission without a user action', () => {
    const { requestPermission } = stubNotification('default')
    renderHook(() => useBrowserNotifications([alert('a1')]))
    expect(requestPermission).not.toHaveBeenCalled()
  })

  it('requests permission on opt-in and persists the choice', async () => {
    const { requestPermission } = stubNotification('default')
    const { result } = renderHook(() => useBrowserNotifications([]))
    await act(async () => { await result.current.setEnabled(true) })
    expect(requestPermission).toHaveBeenCalledTimes(1)
    expect(result.current.enabled).toBe(true)
    expect(localStorage.getItem('alerts:notify')).toBe('1')
  })

  it('stays disabled when the user denies permission', async () => {
    stubNotification('default', 'denied')
    const { result } = renderHook(() => useBrowserNotifications([]))
    await act(async () => { await result.current.setEnabled(true) })
    expect(result.current.enabled).toBe(false)
    expect(result.current.permission).toBe('denied')
    expect(localStorage.getItem('alerts:notify')).toBe('0')
  })

  it('stays silent for the batch already present at mount', () => {
    // Otherwise a page load with a full buffer would dump 100 popups.
    localStorage.setItem('alerts:notify', '1')
    const { ctor } = stubNotification('granted')
    renderHook(() => useBrowserNotifications([alert('a1'), alert('a2')]))
    expect(ctor).not.toHaveBeenCalled()
  })

  it('notifies for alerts that arrive after mount', () => {
    localStorage.setItem('alerts:notify', '1')
    const { ctor } = stubNotification('granted')
    const { rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('a1')] },
    })
    expect(ctor).not.toHaveBeenCalled()

    rerender({ alerts: [alert('a2'), alert('a1')] })   // newest-first
    expect(ctor).toHaveBeenCalledTimes(1)
    expect(ctor.mock.calls[0][0]).toContain('Entered zone')
    expect(ctor.mock.calls[0][1]).toMatchObject({ tag: 'alert-a2' })
  })

  it('collapses a burst into ONE summary notification', () => {
    // The open-auction XADD batch fans out dozens of alerts at once; one popup
    // each would be unusable.
    localStorage.setItem('alerts:notify', '1')
    const { ctor } = stubNotification('granted')
    const { rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('seed')] },
    })

    const burst = Array.from({ length: BURST_CAP + 4 }, (_, i) => alert(`b${i}`))
    rerender({ alerts: [...burst, alert('seed')] })

    expect(ctor).toHaveBeenCalledTimes(1)
    expect(ctor.mock.calls[0][0]).toBe(`${BURST_CAP + 4} new alerts`)
  })

  it('notifies individually at the burst boundary', () => {
    localStorage.setItem('alerts:notify', '1')
    const { ctor } = stubNotification('granted')
    const { rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('seed')] },
    })
    const batch = Array.from({ length: BURST_CAP }, (_, i) => alert(`c${i}`))
    rerender({ alerts: [...batch, alert('seed')] })
    expect(ctor).toHaveBeenCalledTimes(BURST_CAP)
  })

  it('does not notify while disabled, and does not backfill on enable', async () => {
    // Switching the toggle on must not dump everything that already arrived.
    const { ctor } = stubNotification('granted')
    const { result, rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('a1')] },
    })
    rerender({ alerts: [alert('a2'), alert('a1')] })
    expect(ctor).not.toHaveBeenCalled()

    await act(async () => { await result.current.setEnabled(true) })
    expect(ctor).not.toHaveBeenCalled()     // no backlog dump

    rerender({ alerts: [alert('a3'), alert('a2'), alert('a1')] })
    expect(ctor).toHaveBeenCalledTimes(1)   // only the genuinely new one
  })

  it('never notifies the same alert twice', () => {
    localStorage.setItem('alerts:notify', '1')
    const { ctor } = stubNotification('granted')
    const { rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('a1')] },
    })
    rerender({ alerts: [alert('a2'), alert('a1')] })
    rerender({ alerts: [alert('a2'), alert('a1')] })   // same list again
    expect(ctor).toHaveBeenCalledTimes(1)
  })

  it('survives a Notification constructor that throws', () => {
    localStorage.setItem('alerts:notify', '1')
    const throwing = vi.fn(() => { throw new Error('service worker required') })
    vi.stubGlobal('Notification', Object.assign(throwing, {
      permission: 'granted', requestPermission: vi.fn(),
    }))
    const { rerender } = renderHook(({ alerts }) => useBrowserNotifications(alerts), {
      initialProps: { alerts: [alert('a1')] },
    })
    expect(() => rerender({ alerts: [alert('a2'), alert('a1')] })).not.toThrow()
  })
})
