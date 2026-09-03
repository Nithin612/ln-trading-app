import { describe, expect, it } from 'vitest'

import { convictionScore, rankSignals, TOP_N } from '@/features/alerts/conviction'
import type { SignalOut } from '@/lib/api/signals'

const NOW = new Date('2026-08-21T00:00:00Z').getTime()

function sig(o: Partial<SignalOut> = {}): SignalOut {
  return {
    id: 'sig',
    stock_id: 1,
    symbol: 'ACME',
    direction: 'BUY',
    classification: 'positional',
    timeframe: '1d',
    entry_price: '100',
    stop_loss: '96',
    take_profit: '112',
    suggested_qty: 10,
    confidence_pct: 80,
    factor_scores: { A: { weight: 20, score: 0.8, explanation: '' }, B: { weight: 10, score: 0.5, explanation: '' } },
    triggering_patterns: [],
    triggering_indicators: [],
    headline: '',
    status: 'active',
    // 30-day window; created 20 days ago ⇒ ~67% elapsed unless overridden.
    created_at: '2026-08-01T00:00:00Z',
    validity_until: '2026-08-31T00:00:00Z',
    sources_count: 1,
    near_expiry: false,
    days_valid_remaining: 10,
    regime_er: 0.5,
    choppy: false,
    blocked: false, blocked_by: null, block_reason: null, unassessed: [],
    ...o,
  } as SignalOut
}

describe('convictionScore', () => {
  it('is confidence + a small factor bonus for a fresh signal', () => {
    // fresh: created today ⇒ 0% elapsed, no age penalty. 80 conf + min(2 factors,4)=2 → 82.
    const s = sig({ created_at: '2026-08-21T00:00:00Z', validity_until: '2026-09-20T00:00:00Z' })
    expect(convictionScore(s, NOW)).toBe(82)
  })

  it('docks age decay only past 40% elapsed', () => {
    // 20% elapsed ⇒ no age penalty; 80 + 2 = 82.
    const fresh = sig({ created_at: '2026-08-17T00:00:00Z', validity_until: '2026-09-06T00:00:00Z' })
    expect(convictionScore(fresh, NOW)).toBe(82)
    // ~90% elapsed ⇒ heavy penalty → well below the fresh score.
    const stale = sig({ created_at: '2026-07-24T00:00:00Z', validity_until: '2026-08-23T00:00:00Z' })
    expect(convictionScore(stale, NOW)).toBeLessThan(70)
  })

  it('penalises a choppy regime', () => {
    const base = sig({ created_at: '2026-08-21T00:00:00Z', validity_until: '2026-09-20T00:00:00Z' })
    const choppy = sig({ created_at: '2026-08-21T00:00:00Z', validity_until: '2026-09-20T00:00:00Z', choppy: true })
    expect(convictionScore(base, NOW) - convictionScore(choppy, NOW)).toBe(10)
  })
})

describe('rankSignals', () => {
  it('puts the top-N by conviction first (flagged), rest by recency', () => {
    const fresh = '2026-08-21T00:00:00Z'
    const win = '2026-09-20T00:00:00Z'
    const signals = [
      sig({ id: 'low', confidence_pct: 72, created_at: fresh, validity_until: win }),
      sig({ id: 'high', confidence_pct: 95, created_at: fresh, validity_until: win }),
      sig({ id: 'mid', confidence_pct: 84, created_at: fresh, validity_until: win }),
    ]
    const ranked = rankSignals(signals, NOW)
    expect(ranked.map((r) => r.signal.id)).toEqual(['high', 'mid', 'low']) // by score desc
    expect(ranked.every((r) => r.isTop)).toBe(true) // 3 ≤ TOP_N
  })

  it('flags only the first TOP_N as top and orders the rest by recency', () => {
    // TOP_N+2 signals: give the freshest-but-lower-conf ones LATER created_at so the top set is
    // conviction-picked, and the leftover pair sorts by recency (newest first).
    const mk = (i: number, conf: number, created: string) =>
      sig({ id: `s${i}`, confidence_pct: conf, created_at: created, validity_until: '2026-09-20T00:00:00Z' })
    const signals = [
      mk(1, 99, '2026-08-10T00:00:00Z'),
      mk(2, 98, '2026-08-10T00:00:00Z'),
      mk(3, 97, '2026-08-10T00:00:00Z'),
      mk(4, 96, '2026-08-10T00:00:00Z'),
      mk(5, 95, '2026-08-10T00:00:00Z'),
      mk(6, 60, '2026-08-20T00:00:00Z'), // newest of the leftovers
      mk(7, 60, '2026-08-15T00:00:00Z'),
    ]
    const ranked = rankSignals(signals, NOW)
    expect(ranked.filter((r) => r.isTop)).toHaveLength(TOP_N)
    const tail = ranked.slice(TOP_N)
    expect(tail.map((r) => r.signal.id)).toEqual(['s6', 's7']) // leftover, newest-first
    expect(tail.every((r) => !r.isTop)).toBe(true)
  })
})
