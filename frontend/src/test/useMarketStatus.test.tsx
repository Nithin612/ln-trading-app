/**
 * The top-bar session pill, from the calendar (A4, Bucket C #4). The canary: it used to read
 * OPEN on a weekday holiday (a browser-clock weekday rule) and CLOSED through a weekend session.
 */
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { SessionNow } from '@/lib/api/calendar'
import { deriveMarketStatus, useMarketStatus } from '@/hooks/useMarketStatus'

vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ accessToken: 'test-token' }) }))
vi.mock('@/lib/api/calendar', () => ({ calendarApi: { constraints: vi.fn() } }))

/** An IST wall-clock moment. */
const ist = (day: string, hhmm: string) => new Date(`${day}T${hhmm}:00+05:30`)

const regularWed: SessionNow = {
  as_of: '2027-03-03T05:30:00Z', today_ist: '2027-03-03', is_trading_day: true,
  is_regular_session: true, open_ist: '09:15:00', close_ist: '15:30:00', in_session: false,
  next_open: '2027-03-03T03:45:00Z', session_close: '2027-03-03T10:00:00Z',
}

describe('deriveMarketStatus', () => {
  it('walks a regular day: closed → pre-market → open → closed', () => {
    expect(deriveMarketStatus(regularWed, ist('2027-03-03', '08:00')).status).toBe('CLOSED')
    const pre = deriveMarketStatus(regularWed, ist('2027-03-03', '09:05'))
    expect(pre).toEqual({ status: 'PRE-MARKET', nextEvent: 'opens in 0h 10m' })
    expect(deriveMarketStatus(regularWed, ist('2027-03-03', '11:00')))
      .toEqual({ status: 'OPEN', nextEvent: 'closes in 4h 30m' })
    const after = { ...regularWed, next_open: '2027-03-04T03:45:00Z', session_close: null }
    const closed = deriveMarketStatus(after, ist('2027-03-03', '16:00'))
    expect(closed.status).toBe('CLOSED')
    // exact: Intl's own format() renders "Thu, 09:15" on some ICU builds
    expect(closed.nextEvent).toBe('opens Thu 09:15')
  })

  it('reads a weekday HOLIDAY as closed, not open', () => {
    const holiday: SessionNow = {
      ...regularWed, is_trading_day: false, is_regular_session: false, open_ist: null,
      close_ist: null, next_open: '2027-03-04T03:45:00Z', session_close: null,
    }
    expect(deriveMarketStatus(holiday, ist('2027-03-03', '11:00')).status).toBe('CLOSED')
  })

  it('reads a weekend special session as open in its own hours, with no pre-market', () => {
    const muhurat: SessionNow = {
      ...regularWed, today_ist: '2027-03-06', is_regular_session: false,
      open_ist: '18:00:00', close_ist: '19:00:00',
    }
    expect(deriveMarketStatus(muhurat, ist('2027-03-06', '18:30')).status).toBe('OPEN')
    expect(deriveMarketStatus(muhurat, ist('2027-03-06', '17:50')).status).toBe('CLOSED')
  })

  it('says nothing about a next open that is already in the past (a stale answer)', () => {
    // fetched before the open (next_open = today 09:15), still cached after the close
    const stale = deriveMarketStatus(regularWed, ist('2027-03-03', '16:00'))
    expect(stale).toEqual({ status: 'CLOSED', nextEvent: '' })
  })

  it('is UNKNOWN with no answer, or with an answer for another IST day', () => {
    expect(deriveMarketStatus(undefined, ist('2027-03-03', '11:00')).status).toBe('UNKNOWN')
    expect(deriveMarketStatus(regularWed, ist('2027-03-04', '00:05')).status).toBe('UNKNOWN')
  })
})

describe('useMarketStatus', () => {
  it('starts UNKNOWN and follows the backend once it answers', async () => {
    const { calendarApi } = await import('@/lib/api/calendar')
    const today = new Date(Date.now() + 5.5 * 3600_000).toISOString().slice(0, 10)
    vi.mocked(calendarApi.constraints).mockResolvedValue({
      session: { ...regularWed, today_ist: today, is_trading_day: false, open_ist: null,
                 close_ist: null, next_open: null, session_close: null },
      validity: [], offmarket_entry_allowed: false, offmarket_rule: '', data_limits: [],
    })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useMarketStatus(), { wrapper })
    expect(result.current.status).toBe('UNKNOWN')
    await waitFor(() => expect(result.current.status).toBe('CLOSED'))
    expect(calendarApi.constraints).toHaveBeenCalledWith('test-token', { dataLimits: false })
    expect(result.current.timeIST).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })
})


describe('MarketStatusChip', () => {
  it('stays UNKNOWN on an error, drawn distinctly from CLOSED and saying why', async () => {
    const { calendarApi } = await import('@/lib/api/calendar')
    vi.mocked(calendarApi.constraints).mockRejectedValue(new Error('down'))
    const { MarketStatusChip } = await import('@/components/layout/MarketStatusChip')
    const { render, screen } = await import('@testing-library/react')
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><MarketStatusChip /></QueryClientProvider>)
    await waitFor(() => expect(calendarApi.constraints).toHaveBeenCalled())
    const pill = screen.getByLabelText(/Market status unknown/i)
    expect(pill).toHaveTextContent('UNKNOWN')
    expect(pill.className).toContain('border-dashed')
    expect(pill).toHaveAttribute('title', expect.stringMatching(/not reachable/))
  })
})
