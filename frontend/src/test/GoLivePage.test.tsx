import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import { useTradingHaltStore } from '@/store/tradingHaltStore'
import * as tradingApiModule from '@/lib/api/trading'
import type { PaperRecordOut } from '@/lib/api/trading'
import { GoLivePage } from '@/features/golive/GoLivePage'

const mockUser = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, profit_lock_enabled: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

function makeRecord(o: Partial<PaperRecordOut> = {}): PaperRecordOut {
  return {
    days: [], total_days_traded: 3, profitable_days: 3, losing_days: 0,
    current_streak: 3, best_streak: 3, total_realized_pnl: '1500', total_charges: '120',
    total_trades: 5, win_rate_pct: '100.0', target_days: 30,
    start_date: '2026-07-20', last_date: '2026-07-24', clock_started_at: null, ...o,
  }
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
  useTradingHaltStore.setState({ halted: false })
  localStorage.clear()
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><GoLivePage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('GoLivePage', () => {
  it('shows in-progress gate with days remaining', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makeRecord({ profitable_days: 3 }))
    setup()
    await waitFor(() => expect(screen.getByText('3/30')).toBeInTheDocument())
    expect(screen.getByText('IN PROGRESS')).toBeInTheDocument()
    expect(screen.getByText(/27 more profitable days/i)).toBeInTheDocument()
  })

  it('shows criteria-met at 30 profitable days', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makeRecord({ profitable_days: 30 }))
    setup()
    await waitFor(() => expect(screen.getByText('CRITERIA MET')).toBeInTheDocument())
  })

  it('kill switch halts, then releases with a two-step confirm', async () => {
    vi.spyOn(tradingApiModule.tradingApi, 'getPaperRecord').mockResolvedValue(makeRecord())
    setup()
    await waitFor(() => screen.getByText('Trading active'))

    fireEvent.click(screen.getByRole('button', { name: /Halt trading/i }))
    expect(useTradingHaltStore.getState().halted).toBe(true)
    expect(screen.getByText('TRADING HALTED')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Release halt/i }))
    expect(useTradingHaltStore.getState().halted).toBe(true) // first click only arms

    fireEvent.click(screen.getByRole('button', { name: /confirm release/i }))
    expect(useTradingHaltStore.getState().halted).toBe(false)
    expect(screen.getByText('Trading active')).toBeInTheDocument()
  })
})

describe('tradingHaltStore', () => {
  beforeEach(() => { useTradingHaltStore.setState({ halted: false }); localStorage.clear() })

  it('toggles and persists', () => {
    useTradingHaltStore.getState().toggle()
    expect(useTradingHaltStore.getState().halted).toBe(true)
    expect(localStorage.getItem('trading-halted')).toBe('true')
    useTradingHaltStore.getState().setHalted(false)
    expect(useTradingHaltStore.getState().halted).toBe(false)
    expect(localStorage.getItem('trading-halted')).toBe('false')
  })
})
