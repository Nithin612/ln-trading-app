/**
 * useMarketStatus — the top-bar session pill, from the CALENDAR (A4, Bucket C #4).
 *
 * It used to compute OPEN/CLOSED from the browser clock with a weekday rule, so it read OPEN on
 * a weekday holiday and CLOSED through a weekend session. Now the backend answers
 * (`GET /calendar/constraints`: holidays, weekend special sessions and their hours) and this hook
 * only ticks the clock against that answer. With no answer it says UNKNOWN — "not assessable"
 * beats a plausible-looking default (A24).
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { calendarApi, type SessionNow } from '@/lib/api/calendar'
import { formatIstClock, formatIstWeekdayTime } from '@/lib/format'
import { useAuth } from './useAuth'

export type MarketStatus = 'OPEN' | 'PRE-MARKET' | 'CLOSED' | 'UNKNOWN'

/** The pre-open call auction runs 15 minutes before a regular session's open. */
const PRE_OPEN_MS = 15 * 60_000

/** An IST wall-clock moment as epoch ms (IST is UTC+5:30, no DST). */
function istMs(day: string, hhmmss: string): number {
  const [y, mo, d] = day.split('-').map(Number)
  const [h, mi, s] = hhmmss.split(':').map(Number)
  return Date.UTC(y, mo - 1, d, h, mi, s ?? 0) - (5 * 60 + 30) * 60_000
}

function istDate(now: Date): string {
  return new Date(now.getTime() + (5 * 60 + 30) * 60_000).toISOString().slice(0, 10)
}

function span(ms: number): string {
  // Rounded UP: "0h 0m" while time remains reads as "now", which it is not.
  const mins = Math.max(0, Math.ceil(ms / 60_000))
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

export interface DerivedStatus {
  status: MarketStatus
  nextEvent: string
}

/** Pure: the pill for `now`, given the backend's answer (or none). */
export function deriveMarketStatus(session: SessionNow | undefined, now: Date): DerivedStatus {
  // No answer, or an answer for a different IST day (stale across midnight): not assessable.
  if (!session || session.today_ist !== istDate(now)) return { status: 'UNKNOWN', nextEvent: '' }
  const t = now.getTime()
  if (session.is_trading_day && session.open_ist && session.close_ist) {
    const open = istMs(session.today_ist, session.open_ist)
    const close = istMs(session.today_ist, session.close_ist)
    if (t >= open && t <= close) return { status: 'OPEN', nextEvent: `closes in ${span(close - t)}` }
    if (t < open) {
      const pre = session.is_regular_session && t >= open - PRE_OPEN_MS
      return { status: pre ? 'PRE-MARKET' : 'CLOSED', nextEvent: `opens in ${span(open - t)}` }
    }
  }
  if (session.next_open && new Date(session.next_open).getTime() > t) {
    // (a next_open already in the past is a stale answer — say nothing rather than "0h 0m")
    const next = new Date(session.next_open)
    const sameDay = istDate(next) === session.today_ist
    const label = formatIstWeekdayTime(session.next_open)
    return { status: 'CLOSED', nextEvent: sameDay ? `opens in ${span(next.getTime() - t)}` : `opens ${label}` }
  }
  return { status: 'CLOSED', nextEvent: '' }
}

export function useMarketStatus(): DerivedStatus & { timeIST: string } {
  const { accessToken, user } = useAuth()
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  const { data } = useQuery({
    // Scoped to the user (the payload carries a per-user flag) and to the IST day, so the
    // answer refetches the moment the date changes instead of reading UNKNOWN for minutes.
    queryKey: ['calendar-constraints', user?.id ?? null, istDate(now)],
    queryFn: () => calendarApi.constraints(accessToken!, { dataLimits: false }),
    enabled: !!accessToken,
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
  })
  const timeIST = formatIstClock(now)
  return { ...deriveMarketStatus(data?.session, now), timeIST }
}
