import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import * as strategyApiModule from '@/lib/api/strategy'
import { StrategyLabPage } from '@/features/strategy/StrategyLabPage'

const mockUser = {
  id: 1, email: 'lab@example.com', full_name: 'Lab User', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token', user: mockUser })
})

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

function makeRun(overrides: Partial<strategyApiModule.StrategyRunOut> = {}): strategyApiModule.StrategyRunOut {
  return {
    id: 1,
    name: 'Test Run',
    description: null,
    timeframe: '1d',
    universe: 'NIFTY50',
    period_start: '2024-01-01T00:00:00',
    period_end: '2024-12-31T23:59:59',
    status: 'done',
    factor_weights: {},
    capital: '100000',
    risk_pct: '2.00',
    min_confidence: 70,
    total_trades: 42,
    winning_trades: 25,
    losing_trades: 17,
    win_rate_pct: '59.52',
    total_pnl_pct: '12.340',
    avg_pnl_pct: '0.294',
    avg_rr: '2.10',
    sharpe: '1.250',
    sortino: '1.800',
    max_drawdown_pct: '8.500',
    avg_holding_days: '4.20',
    ranking: 1,
    equity_curve: [100, 101, 103, 102, 105, 108],
    trades_json: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('StrategyLabPage — config form', () => {
  it('renders the run name input', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    expect(screen.getByPlaceholderText(/e.g. Momentum-heavy/i)).toBeInTheDocument()
  })

  it('renders factor weight sliders for all groups', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    expect(screen.getByText('Pattern')).toBeInTheDocument()
    expect(screen.getByText('Trend')).toBeInTheDocument()
    expect(screen.getByText('Momentum')).toBeInTheDocument()
    expect(screen.getByText('Volume')).toBeInTheDocument()
    expect(screen.getByText('Structure')).toBeInTheDocument()
    expect(screen.getByText('Institutional')).toBeInTheDocument()
  })

  it('renders quick-range buttons', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    expect(screen.getByText('1W')).toBeInTheDocument()
    expect(screen.getByText('2Y')).toBeInTheDocument()
  })

  it('shows Run Backtest button', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    expect(screen.getByText(/Run Backtest/i)).toBeInTheDocument()
  })

  it('shows Quick Preset Scan button', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    expect(screen.getByText(/Quick Preset Scan/i)).toBeInTheDocument()
  })
})

describe('StrategyLabPage — saved runs', () => {
  it('shows empty state when no runs', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    await waitFor(() => {
      expect(screen.getByText(/No saved runs/i)).toBeInTheDocument()
    })
  })

  it('renders a run row with metrics', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({
      total: 1,
      runs: [makeRun()],
    })
    wrap(<StrategyLabPage />)
    await waitFor(() => {
      expect(screen.getByText('Test Run')).toBeInTheDocument()
    })
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('59.52%')).toBeInTheDocument()
  })

  it('expands a run row to show equity curve section', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({
      total: 1,
      runs: [makeRun()],
    })
    wrap(<StrategyLabPage />)
    await waitFor(() => screen.getByText('Test Run'))
    // Click the row to expand
    fireEvent.click(screen.getByText('Test Run').closest('tr')!)
    await waitFor(() => {
      expect(screen.getByText(/Equity curve/i)).toBeInTheDocument()
    })
  })

  it('shows delete button on each row', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({
      total: 1,
      runs: [makeRun()],
    })
    wrap(<StrategyLabPage />)
    await waitFor(() => screen.getByText('Test Run'))
    expect(screen.getByTitle('Delete run')).toBeInTheDocument()
  })

  it('calls delete API when delete button clicked', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({
      total: 1,
      runs: [makeRun()],
    })
    const deleteSpy = vi.spyOn(strategyApiModule.strategyApi, 'deleteRun').mockResolvedValue(undefined)
    wrap(<StrategyLabPage />)
    await waitFor(() => screen.getByTitle('Delete run'))
    fireEvent.click(screen.getByTitle('Delete run'))
    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(1, 'test-token')
    })
  })
})

describe('StrategyLabPage — preset scan tab', () => {
  it('shows empty state on scan tab before scan', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    wrap(<StrategyLabPage />)
    // Click the tab button (exact "Preset Scan", not "Quick Preset Scan")
    const tabs = screen.getAllByText(/Preset Scan/i)
    const tabBtn = tabs.find((el) => el.textContent?.trim() === 'Preset Scan')!
    fireEvent.click(tabBtn)
    await waitFor(() => {
      expect(screen.getByText(/No scan results yet/i)).toBeInTheDocument()
    })
  })

  it('shows scan results after preset scan completes', async () => {
    vi.spyOn(strategyApiModule.strategyApi, 'listRuns').mockResolvedValue({ total: 0, runs: [] })
    vi.spyOn(strategyApiModule.strategyApi, 'presetScan').mockResolvedValue({
      entries: [
        {
          preset_name: 'momentum_heavy',
          weight_multipliers: { momentum: 1.5 },
          total_trades: 35,
          win_rate_pct: 57.1,
          sharpe: 1.4,
          sortino: 2.1,
          max_drawdown_pct: 9.2,
          avg_rr: 2.0,
          avg_holding_days: 3.5,
          equity_curve: [100, 102, 104, 103, 107],
        },
      ],
    })
    wrap(<StrategyLabPage />)
    fireEvent.click(screen.getByText(/Quick Preset Scan/i))
    await waitFor(() => {
      expect(screen.getByText(/momentum heavy/i)).toBeInTheDocument()
    })
  })
})
