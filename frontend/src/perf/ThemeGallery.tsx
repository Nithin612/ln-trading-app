/**
 * Theme gallery (Phase 5) — renders the phase's presentational components with
 * fixture data so every theme can be eyeballed without a logged-in session.
 *
 * Why this exists: the new screens colour themselves entirely from CSS custom
 * properties, which resolve differently in each of the five themes. A token can
 * compute correctly and still render unreadable, and slate is the only theme
 * anything gets seen in by accident. Contrast maths caught one real WCAG
 * failure (daybreak `--color-warning` at 2.91:1); this catches what maths
 * cannot.
 *
 * The components here take plain props — no queries, no auth — so the gallery
 * needs neither a backend nor a session. Page-level data plumbing is covered by
 * the 344 unit tests; what is under inspection here is purely appearance.
 *
 * Served at /perf/theme-gallery.html?theme=daybreak and screenshotted by
 * perf/shoot-themes.mjs.
 */

import type { FoAnalytics, IvRank, OptionChain, SpreadCandidate } from '@/lib/api/fo'
import type { OutcomeStyleStats } from '@/lib/api/analytics'
import type { SuggestionOut } from '@/lib/api/suggestions'
import { ChainLadder } from '@/features/fo/ChainLadder'
import { FoAnalyticsHeader } from '@/features/fo/FoAnalyticsHeader'
import { StrategyCards } from '@/features/fo/StrategyCards'
import { StyleStatsHeader } from '@/features/styles/StyleStatsHeader'

const CHAIN: OptionChain = {
  symbol: 'NIFTY',
  expiry: '2026-08-11',
  source: 'eod',
  spot: '24600.00',
  atm_strike: '24600.00',
  as_of: '2026-08-06',
  fut_price: '24631.4200',
  forward_source: 'fut_carry_implied',
  dte: 5,
  legs: [24400, 24500, 24600, 24700, 24800].flatMap((strike, i) => [
    {
      strike: `${strike}.00`, option_type: 'CE' as const,
      oi: 120000 + i * 90000, volume: 4200 + i * 900,
      ltp: `${(320 - i * 48).toFixed(2)}`,
      iv: 0.182 - i * 0.004, delta: 0.71 - i * 0.11,
      gamma: 0.00021, vega: 12.4 - i * 0.6, theta: -8.25 - i * 0.4,
    },
    {
      strike: `${strike}.00`, option_type: 'PE' as const,
      oi: 300000 - i * 52000, volume: 5100 - i * 700,
      ltp: `${(130 + i * 47).toFixed(2)}`,
      iv: 0.176 + i * 0.005, delta: -0.29 - i * 0.11,
      gamma: 0.00019, vega: 11.8 - i * 0.5, theta: -7.9 - i * 0.3,
    },
  ]),
}

const ANALYTICS: FoAnalytics = {
  symbol: 'NIFTY', expiry: '2026-08-11', source: 'eod',
  spot: '24600.00', atm_strike: '24600.00',
  pcr: { pcr_oi: 1.25, pcr_volume: 0.98, total_ce_oi: 4_000_000, total_pe_oi: 5_000_000 },
  max_pain: '24500.00',
  basis: { fut_close: '24631.42', underlying_close: '24600.00', basis: '31.42', basis_pct: 0.128 },
  vix: { current: '13.40', percentile: 42, band: 'normal', sample: 252 },
}

const IV_RANK: IvRank = {
  symbol: 'NIFTY', as_of: '2026-08-06', current_iv: 0.18,
  rank: 63, percentile: 61, min_iv: 0.1, max_iv: 0.3, sample: 252,
}

const CANDIDATES: SpreadCandidate[] = [
  {
    structure: 'bull_put',
    legs: [
      { action: 'sell', option_type: 'PE', strike: '24000.00', premium: '95.00' },
      { action: 'buy', option_type: 'PE', strike: '23900.00', premium: '62.00' },
    ],
    net_credit: '33.00', max_profit: '33.00', max_loss: '67.00', width: '100.00',
    breakevens: ['23967.00'], pop: 0.71, expectancy: '-3.20',
    margin_est: '67.00', return_on_margin: 0.4925, short_delta: -0.16,
    dte: 28, expiry: '2026-09-01',
    exit_plan: { take_profit_credit: '16.50', stop_loss_amount: '66.00', time_stop_dte: 21 },
    rationale: 'IV-rank 63, 0.16Δ short, above max-pain',
  },
  {
    structure: 'iron_condor',
    legs: [
      { action: 'sell', option_type: 'PE', strike: '24000.00', premium: '95.00' },
      { action: 'buy', option_type: 'PE', strike: '23900.00', premium: '62.00' },
      { action: 'sell', option_type: 'CE', strike: '25200.00', premium: '88.00' },
      { action: 'buy', option_type: 'CE', strike: '25300.00', premium: '59.00' },
    ],
    net_credit: '62.00', max_profit: '62.00', max_loss: '38.00', width: '100.00',
    breakevens: ['23938.00', '25262.00'], pop: 0.68, expectancy: '-1.10',
    margin_est: '38.00', return_on_margin: 1.63, short_delta: -0.17,
    dte: 28, expiry: '2026-09-01',
    exit_plan: { take_profit_credit: '31.00', stop_loss_amount: '124.00', time_stop_dte: 21 },
    rationale: 'Neutral: IV-rank 63, both wings ~0.17Δ',
  },
]

const STATS: OutcomeStyleStats = {
  style: 'swing', total: 50, entered: 40, wins: 24, losses: 16,
  no_entry: 8, timed_out: 2, pending: 0, sample: 50,
  hit_rate: 0.6, entry_rate: 0.8, avg_return_pct: 1.4,
}

const SMALL_STATS: OutcomeStyleStats = {
  ...STATS, wins: 3, losses: 0, entered: 3, total: 4, no_entry: 1,
  sample: 4, hit_rate: 1.0, entry_rate: 0.75, avg_return_pct: 2.0,
}

function suggestion(o: Partial<SuggestionOut> = {}): SuggestionOut {
  return {
    id: 's1', symbol: 'RELIANCE', direction: 'BUY', classification: 'swing',
    timeframe: '1d', entry_price: '2850.0000', stop_loss: '2800.0000',
    take_profit: '2950.0000', suggested_qty: 1250, confidence_pct: 82,
    headline: 'BUY RELIANCE', factor_scores: {}, setup_trigger: null,
    volatility_reduced: false, profile_key: 'rrbo', profile_name: 'RRBO',
    profile_version: 1, style: 'swing',
    validity_until: '2026-08-12T10:00:00Z', created_at: '2026-08-06T04:00:00Z',
    blocked: false, blocked_by: null, block_reason: null, unassessed: [],
    ...o,
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xs font-bold uppercase tracking-wider text-(--color-text-secondary)">
        {title}
      </h2>
      {children}
    </section>
  )
}

export function ThemeGallery() {
  const theme = new URLSearchParams(window.location.search).get('theme') ?? 'slate'
  document.documentElement.setAttribute('data-theme', theme)

  return (
    <div className="min-h-screen bg-(--color-bg) text-(--color-text) p-6 flex flex-col gap-6">
      <h1 className="text-lg font-bold">
        Theme: <span className="text-(--color-accent)">{theme}</span>
      </h1>

      <Section title="Style stats header — healthy sample">
        <StyleStatsHeader
          stats={STATS}
          statsLoading={false}
          suggestions={[suggestion(), suggestion({ id: 's2', direction: 'SELL' })]}
        />
      </Section>

      <Section title="Style stats header — sample too small (must read muted, not endorsed)">
        <StyleStatsHeader stats={SMALL_STATS} statsLoading={false} suggestions={[suggestion()]} />
      </Section>

      <Section title="F&O analytics strip">
        <FoAnalyticsHeader
          analytics={ANALYTICS}
          ivRank={IV_RANK}
          ivRankMissing={false}
          isLoading={false}
        />
      </Section>

      <Section title="F&O analytics strip — VIX unknown (fail-closed stand-down, uses --color-warning)">
        <FoAnalyticsHeader
          analytics={{ ...ANALYTICS, vix: null }}
          ivRank={undefined}
          ivRankMissing
          isLoading={false}
        />
      </Section>

      <Section title="Option-selling candidates">
        <StrategyCards symbol="NIFTY" candidates={CANDIDATES} isLoading={false} isError={false} />
      </Section>

      <Section title="Option-selling candidates — no-trade empty state">
        <StrategyCards symbol="NIFTY" candidates={[]} isLoading={false} isError={false} />
      </Section>

      <Section title="Chain ladder (OI bars, IV, Greeks, ATM badge)">
        <div className="rounded-lg border border-(--color-border) bg-(--color-surface-2)">
          <ChainLadder chain={CHAIN} showGreeks />
        </div>
      </Section>
    </div>
  )
}
