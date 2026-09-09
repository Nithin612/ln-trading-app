import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as analyticsApiModule from '@/lib/api/analytics'
import type { GateHypothesis, GateRegisterResponse } from '@/lib/api/analytics'
import { RegistryPage } from '@/features/analytics/RegistryPage'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

function hyp(o: Partial<GateHypothesis> & { key: string; name: string }): GateHypothesis {
  return {
    status: 'shadow', prediction: 'p', bar: 'b', stands_at: 's', verdict: 'v',
    counts_as_trial: true, review_due: null, has_cohort: false, ...o,
  }
}

function makeResponse(o: Partial<GateRegisterResponse> = {}): GateRegisterResponse {
  return {
    as_of: '2026-09-05',
    trials_attempted: 15,
    assumed_trials: 20,
    counts: { active: 1, shadow: 3, reverted: 2 },
    due_for_review: ['spread_width_r2'],
    hypotheses: [
      hyp({ key: 'regime_adx', name: 'Regime gate', status: 'reverted', verdict: 'blocked the only profitable cohort', has_cohort: true }),
      hyp({ key: 'entry_diversity', name: 'Entry diversity', status: 'active', counts_as_trial: false }),
    ],
    ...o,
  }
}

beforeEach(() => { useAuthStore.setState({ accessToken: 'tok', user: mockUser }) })

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><RegistryPage /></MemoryRouter></QueryClientProvider>,
  )
}

describe('RegistryPage', () => {
  it('renders trials (observed vs assumed) and the hypothesis rows', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockResolvedValue(makeResponse())
    setup()
    await waitFor(() => expect(screen.getByText('Regime gate')).toBeInTheDocument())
    expect(screen.getByText('15')).toBeInTheDocument() // trials observed
    expect(screen.getByText('20')).toBeInTheDocument() // assumed
    expect(screen.getByText(/lower bound/i)).toBeInTheDocument() // A24 uncertainty framing
  })

  it('keeps reverted/decided candidates visible (U6)', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockResolvedValue(makeResponse())
    setup()
    await waitFor(() => expect(screen.getByText('Regime gate')).toBeInTheDocument())
    expect(screen.getByText('Reverted')).toBeInTheDocument()
    expect(screen.getByText(/blocked the only profitable cohort/)).toBeInTheDocument()
    // a hard rule shows as not consuming a trial
    expect(screen.getByText('rule / rail')).toBeInTheDocument()
  })

  it('links a gate with a would-block cohort to its drill-down (U20), plain otherwise', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockResolvedValue(makeResponse())
    setup()
    await waitFor(() => expect(screen.getByText('Regime gate')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: 'Regime gate' })
    expect(link).toHaveAttribute('href', '/analytics/registry/regime_adx')
    // entry_diversity has no cohort in this mock → not a link
    expect(screen.queryByRole('link', { name: 'Entry diversity' })).not.toBeInTheDocument()
  })

  it('shows an empty state when the register has no hypotheses', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockResolvedValue(
      makeResponse({ hypotheses: [], counts: {} }),
    )
    setup()
    await waitFor(() => expect(screen.getByText(/No hypotheses recorded/i)).toBeInTheDocument())
  })

  it('shows loading skeletons', () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockReturnValue(new Promise(() => {}))
    setup()
    expect(screen.getByLabelText('loading gate register')).toBeInTheDocument()
  })

  it('shows an error state with retry', async () => {
    vi.spyOn(analyticsApiModule.analyticsApi, 'getGateRegister').mockRejectedValue(new Error('boom'))
    setup()
    await waitFor(() => expect(screen.getByText(/Could not load the gate register/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
