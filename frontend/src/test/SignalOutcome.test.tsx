import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SignalDetailModal } from '@/features/dashboard/SignalDetailModal'
import { outcomeApi, signalsApi } from '@/lib/api/signals'
import type { ConfidenceBreakdown, SignalOut, SignalOutcome } from '@/lib/api/signals'

vi.mock('@/lib/api/signals', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/lib/api/signals')>()
  return {
    ...mod,
    outcomeApi: { getOutcome: vi.fn() },
    signalsApi: { ...mod.signalsApi, getById: vi.fn() },
  }
})

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}))

const SIGNAL: SignalOut = {
  id: 'sig-1',
  stock_id: 1,
  symbol: 'RELIANCE',
  direction: 'BUY',
  classification: 'swing',
  timeframe: '1h',
  entry_price: '100.0000',
  stop_loss: '98.0000',
  take_profit: '104.0000',
  suggested_qty: 10,
  confidence_pct: 78,
  factor_scores: {},
  triggering_patterns: [],
  triggering_indicators: [],
  headline: 'test signal',
  status: 'active',
  validity_until: '2026-07-23T10:00:00+00:00',
  created_at: '2026-07-16T05:00:00+00:00',
  sources_count: 1,
  near_expiry: false,
  days_valid_remaining: 4,
  regime_er: 0.5,
  choppy: false,
  blocked: false, blocked_by: null, block_reason: null, unassessed: [],
}

function outcome(overrides: Partial<SignalOutcome> = {}): SignalOutcome {
  return {
    signal_id: 'sig-1',
    stock_id: 1,
    direction: 'BUY',
    classification: 'swing',
    timeframe: '1h',
    validity_until: '2026-07-23T10:00:00+00:00',
    status: 'tp_first',
    entry_touched_at: '2026-07-16T06:03:00+00:00',
    entry_touch_price: '100.1000',
    sl_touched_at: null,
    sl_touch_price: null,
    tp_touched_at: '2026-07-16T06:33:00+00:00',
    tp_touch_price: '104.0500',
    resolved_at: '2026-07-16T06:33:00+00:00',
    ...overrides,
  }
}

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SignalDetailModal signal={SIGNAL} onClose={() => {}} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(outcomeApi.getOutcome).mockReset()
  // Default: detail fetch returns the signal with no breakdown, so the outcome-section tests
  // never touch the network and the card degrades gracefully.
  vi.mocked(signalsApi.getById).mockReset()
  vi.mocked(signalsApi.getById).mockResolvedValue(SIGNAL)
})

describe('SignalDetailModal outcome section', () => {
  it('shows a resolved outcome with its touch trail', async () => {
    vi.mocked(outcomeApi.getOutcome).mockResolvedValue(outcome())
    renderModal()

    expect(await screen.findByText('▲ target hit')).toBeInTheDocument()
    expect(screen.getByText(/entry ₹100\.10/)).toBeInTheDocument()
    expect(screen.getByText(/TP ₹104\.05/)).toBeInTheDocument()
    expect(screen.getByText('Outcome')).toBeInTheDocument()
  })

  it('shows the stopped-out state', async () => {
    vi.mocked(outcomeApi.getOutcome).mockResolvedValue(
      outcome({
        status: 'sl_first',
        tp_touched_at: null,
        tp_touch_price: null,
        sl_touched_at: '2026-07-16T07:00:00+00:00',
        sl_touch_price: '97.9500',
      }),
    )
    renderModal()
    expect(await screen.findByText('▼ stopped out')).toBeInTheDocument()
    expect(screen.getByText(/SL ₹97\.95/)).toBeInTheDocument()
  })

  it('renders nothing when no outcome is recorded yet', async () => {
    vi.mocked(outcomeApi.getOutcome).mockResolvedValue(null)
    renderModal()
    await waitFor(() =>
      expect(vi.mocked(outcomeApi.getOutcome)).toHaveBeenCalledWith('sig-1', 'test-token'),
    )
    expect(screen.queryByText('Outcome')).not.toBeInTheDocument()
    expect(screen.getByText('RELIANCE')).toBeInTheDocument() // modal itself intact
  })

  it('never blocks the modal on an outcome fetch error', async () => {
    vi.mocked(outcomeApi.getOutcome).mockRejectedValue(new Error('boom'))
    renderModal()
    expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
    await waitFor(() =>
      expect(vi.mocked(outcomeApi.getOutcome)).toHaveBeenCalled(),
    )
    expect(screen.queryByText('Outcome')).not.toBeInTheDocument()
  })
})

function breakdown(overrides: Partial<ConfidenceBreakdown> = {}): ConfidenceBreakdown {
  return {
    numerator: 26,
    denominator: 30,
    normalized: 0.8667,
    confidence_pct: 86,
    direction: 'BUY',
    scoring: [
      { name: 'DOW_TREND', weight: 20, score: 0.9, contribution: 18, explanation: 'uptrend' },
      { name: 'RSI_DIVERGENCE', weight: 10, score: 0.8, contribution: 8, explanation: 'divergence' },
    ],
    abstained: [{ name: 'ADX', weight: 15, explanation: 'no trend' }],
    ...overrides,
  }
}

describe('SignalDetailModal confidence breakdown (U10/U15/U17)', () => {
  beforeEach(() => {
    vi.mocked(outcomeApi.getOutcome).mockResolvedValue(null)
  })

  it('renders the arithmetic, the vote distribution, and the abstainer note', async () => {
    vi.mocked(signalsApi.getById).mockResolvedValue({
      ...SIGNAL,
      confidence_pct: 86,
      confidence_breakdown: breakdown(),
    })
    renderModal()

    // U10 — the division is shown, and both scoring factors are named.
    expect(await screen.findByText('How this 86% was built')).toBeInTheDocument()
    expect(screen.getByText('dow trend')).toBeInTheDocument()
    expect(screen.getByText('rsi divergence')).toBeInTheDocument()
    // U17 — the vote caption counts scoring vs total.
    expect(screen.getByText(/2 of 3 factors voted/)).toBeInTheDocument()
    // The abstainer is called out as excluded from the divisor (the SRTL mechanism).
    expect(screen.getByText(/drops out of the divisor/i)).toBeInTheDocument()
    expect(screen.getByText(/adx/i)).toBeInTheDocument()
  })

  it('flags a single-indicator signal as carrying the whole score (the SRTL tell)', async () => {
    vi.mocked(signalsApi.getById).mockResolvedValue({
      ...SIGNAL,
      confidence_pct: 80,
      confidence_breakdown: breakdown({
        numerator: 12,
        denominator: 15,
        normalized: 0.8,
        confidence_pct: 80,
        scoring: [
          { name: 'RSI_DIVERGENCE', weight: 15, score: 0.8, contribution: 12, explanation: 'div' },
        ],
        abstained: [
          { name: 'ADX', weight: 15, explanation: 'flat' },
          { name: 'EMA_STACK', weight: 12, explanation: 'flat' },
        ],
      }),
    })
    renderModal()
    expect(
      await screen.findByText(/a single indicator carries the entire score/i),
    ).toBeInTheDocument()
  })

  it('falls back gracefully when the detail fetch has no breakdown', async () => {
    vi.mocked(signalsApi.getById).mockResolvedValue(SIGNAL) // no confidence_breakdown
    renderModal()
    expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
    // Wait for the detail query to settle out of its loading state.
    expect(await screen.findByText(/factor breakdown unavailable/i)).toBeInTheDocument()
  })
})
