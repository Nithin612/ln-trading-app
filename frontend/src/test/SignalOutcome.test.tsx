import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SignalDetailModal } from '@/features/dashboard/SignalDetailModal'
import { outcomeApi } from '@/lib/api/signals'
import type { SignalOut, SignalOutcome } from '@/lib/api/signals'

vi.mock('@/lib/api/signals', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/lib/api/signals')>()
  return { ...mod, outcomeApi: { getOutcome: vi.fn() } }
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
