import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { EligibilityPanel } from '@/features/stocks/EligibilityPanel'
import type { StockEligibility } from '@/lib/api/stocks'

/**
 * V5 / A2 tier 3 — why this stock does or does not produce signals.
 *
 * THREE independent reasons exist and only the first was visible anywhere: the universe
 * rule did not admit it · the CA detector quarantined it (which drops it from every
 * suggestion EVEN WHEN TRADEABLE — measured, 5 of the 7 quarantined names are active) ·
 * or it has too few daily bars, so the scan never SCORES it rather than scoring it and
 * declining (V1 measured 184 of 2,286 priced names dying there).
 */
vi.mock('@/hooks/useAuth', () => ({ useAuth: () => ({ isAdmin: true }) }))

const HEALTHY: StockEligibility = {
  in_universe: true,
  ca_quarantined: false,
  suggestible: true,
  exclusion_reasons: [],
  reason_as_of: null,
  coverage: { daily_bars: 1100, min_bars_to_score: 50, enough_history: true, shortfall: 0, latest_bar: '2026-09-15' },
  scannable: true,
}

const wrap = (el: StockEligibility) =>
  render(
    <MemoryRouter>
      <EligibilityPanel eligibility={el} />
    </MemoryRouter>,
  )

describe('EligibilityPanel', () => {
  it('says a healthy stock IS scanned, with no reasons', () => {
    wrap(HEALTHY)
    expect(screen.getByText(/Scanned for signals/i)).toBeInTheDocument()
    expect(screen.queryByText(/Not scanned/i)).not.toBeInTheDocument()
  })

  it('explains a thin name as NEVER SCORED, not as declined', () => {
    // ⭐ The sentence that had no home before. "No signals" on a thin name means the scan
    // skipped it entirely — which says nothing about the setup, only about the history.
    wrap({
      ...HEALTHY,
      scannable: false,
      coverage: { daily_bars: 12, min_bars_to_score: 50, enough_history: false, shortfall: 38, latest_bar: '2026-09-15' },
    })
    expect(screen.getByText(/Not scanned/i)).toBeInTheDocument()
    expect(screen.getByText(/38 more needed/i)).toBeInTheDocument()
    expect(screen.getByText(/before scoring it/i)).toBeInTheDocument()
    expect(screen.getByText(/says nothing about the setup/i)).toBeInTheDocument()
  })

  it('shows the bar count WITH its threshold, never alone', () => {
    // A24 / H11 — a sample size travels with the number it qualifies. "12 bars" means
    // nothing without the 50 it is measured against.
    wrap({
      ...HEALTHY,
      scannable: false,
      coverage: { daily_bars: 12, min_bars_to_score: 50, enough_history: false, shortfall: 38, latest_bar: null },
    })
    expect(screen.getByText(/12 \/ 50 bars/)).toBeInTheDocument()
  })

  it('dates the bar count too — "more needed" must not assert sessions will arrive', () => {
    // A24 — without an as-of, "38 more needed" quietly claims 38 more sessions WILL
    // come, which is false for a stale or delisted name whose count is frozen.
    // `latest_bar` was in the payload and rendered nowhere (ui-reviewer #5).
    wrap({
      ...HEALTHY,
      scannable: false,
      coverage: { daily_bars: 12, min_bars_to_score: 50, enough_history: false, shortfall: 38, latest_bar: '2026-09-15' },
    })
    expect(screen.getByText(/latest/i)).toBeInTheDocument()
  })

  it('renders a QUARANTINED stock as quarantined, not as "no"', () => {
    // ⛔⛔ THE BUG THIS TEST MISSED THE FIRST TIME. `Row` took one label for the true
    // branch and hardcoded "⊘ no" for the false one, so a quarantined stock rendered
    // "CA quarantine ⊘ no" — which reads as NOT quarantined, the exact opposite of the
    // truth, in the one case this panel exists to explain. The old test asserted only the
    // PROSE below the rows, so it passed throughout (ui-reviewer #1).
    wrap({
      ...HEALTHY,
      ca_quarantined: true,
      suggestible: false,
      scannable: false,
      exclusion_reasons: [
        'Quarantined by the corporate-action detector, so it is excluded from suggestions even when tradeable — review it under CA Quarantine.',
      ],
    })
    expect(screen.getByText('⊘ quarantined')).toBeInTheDocument()
    expect(screen.queryByText('⊘ no')).not.toBeInTheDocument()
    expect(screen.getByText(/even when tradeable/i)).toBeInTheDocument()
  })

  it('offers the review queue to an admin, gated on the FLAG not on prose', () => {
    // ⚠ The link used to be shown by substring-matching the backend's sentence while the
    // authoritative boolean was in scope — a server copy edit would have removed it
    // silently. Here the reason text deliberately omits the phrase.
    wrap({
      ...HEALTHY,
      ca_quarantined: true,
      suggestible: false,
      scannable: false,
      exclusion_reasons: ['Some other wording entirely.'],
    })
    expect(screen.getByRole('link', { name: /review the ca quarantine queue/i })).toHaveAttribute(
      'href',
      '/admin/ca-quarantine',
    )
  })

  it('offers no link when the stock is not quarantined', () => {
    wrap(HEALTHY)
    expect(screen.queryByRole('link', { name: /quarantine/i })).not.toBeInTheDocument()
  })

  it('dates a derived verdict, and claims no date when it has none', () => {
    // A24 — a reason from a recorded evaluation carries ITS date so it is not read as a
    // timeless fact; when no record justified it, no date is shown and none is implied.
    wrap({ ...HEALTHY, in_universe: false, suggestible: false, scannable: false,
           exclusion_reasons: ['Not in the tradeable universe.'], reason_as_of: '2026-09-15' })
    // ⚠ Formatted through lib/format, not the raw ISO string (ui-reviewer #11).
    expect(screen.getByText(/as evaluated/i)).toBeInTheDocument()
    expect(screen.queryByText(/2026-09-15/)).not.toBeInTheDocument()

    wrap({ ...HEALTHY, in_universe: false, suggestible: false, scannable: false,
           exclusion_reasons: ['Not in the tradeable universe.'], reason_as_of: null })
    expect(screen.queryAllByText(/as evaluated/i)).toHaveLength(1) // only the first render's
  })

  it('never carries meaning by colour alone', () => {
    // ui.md — direction and state are glyph + text, never colour alone.
    wrap({ ...HEALTHY, in_universe: false, suggestible: false, scannable: false,
           exclusion_reasons: ['Not in the tradeable universe.'] })
    expect(screen.getByText('⊘ excluded')).toBeInTheDocument()
  })
})
