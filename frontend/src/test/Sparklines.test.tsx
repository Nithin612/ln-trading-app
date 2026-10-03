/**
 * Sparklines are REAL recent closes, never invented (2026-10-03).
 *
 * The canary: three tables drew a per-row sparkline from `seededSpark(stock.id)` (a PRNG seeded
 * by the row id) or `generateFakeSpark(entry, sl, tp)`, coloured green/red by the invented path —
 * a random number decided which names looked like they were rising. The four non-line/line
 * states (loading · unavailable · no history · measured) must stay distinct (A24).
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useLiveQuotes', () => ({
  useLiveQuotes: () => ({ quotes: {}, candles: {}, signals: [], connected: false }),
}))
import { Sparkline } from '@/components/ui/sparkline'
import { StocksPage } from '@/features/stocks/StocksPage'
import { MAX_IDS_PER_REQUEST, useSparklines } from '@/hooks/useSparklines'
import { useAuthStore } from '@/store/authStore'
import * as stocksApiModule from '@/lib/api/stocks'
import { renderHook } from '@testing-library/react'

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({
    accessToken: 'test-token',
    user: { id: 1, email: 'u@example.com', full_name: 'Test', role: 'user',
            capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
            max_trades_per_day: 2, is_active: true, trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
            created_at: '', updated_at: '' },
  })
})

const stock = (id: number, symbol: string): stocksApiModule.Stock => ({
  id, symbol, exchange: 'NSE', isin: null, company_name: `${symbol} Ltd`, sector: 'IT',
  industry: 'IT', market_cap_cr: null, lot_size: 1, tick_size: '0.05', is_fno: false,
  is_nifty50: false, is_banknifty: false, is_finnifty: false, is_active: true, listed_on: null,
  created_at: '', updated_at: '',
})

function qcWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>
  )
}

describe('Sparkline states', () => {
  it('no history, unavailable and loading are three distinct renderings', () => {
    const { rerender } = render(<Sparkline data={undefined} />)
    expect(screen.getByRole('img', { name: 'No recent price history' })).toHaveTextContent('—')
    rerender(<Sparkline data={[101]} />)
    expect(screen.getByRole('img', { name: 'No recent price history' })).toBeInTheDocument()
    rerender(<Sparkline data={undefined} status="error" />)
    expect(screen.getByRole('img', { name: 'Price history unavailable' })).toHaveTextContent('—')
    rerender(<Sparkline data={undefined} status="pending" />)
    expect(screen.getByRole('img', { name: 'Loading price history' })).not.toHaveTextContent('—')
  })

  it('names its own direction and size, and calls a flat line flat', () => {
    const { rerender } = render(<Sparkline data={[100, 104, 110]} />)
    expect(screen.getByRole('img', { name: '3-session close up 10.00%' })).toBeInTheDocument()
    rerender(<Sparkline data={[100, 130, 100]} />)
    expect(screen.getByRole('img', { name: '3-session close flat' })).toBeInTheDocument()
  })

  it('adds no focusable application role per row (recharts accessibility layer off)', () => {
    const { container } = render(<Sparkline data={[1, 2, 3]} width={60} height={24} />)
    expect(container.querySelector('svg')).not.toBeNull()
    expect(container.querySelector('[role="application"]')).toBeNull()
    // recharts keeps internal tabindex="-1" layers (programmatic only); none may be a tab stop.
    const stops = [...container.querySelectorAll('[tabindex]')].filter(
      (e) => Number(e.getAttribute('tabindex')) >= 0,
    )
    expect(stops).toHaveLength(0)
  })
})

describe('useSparklines', () => {
  it('chunks above the endpoint cap into disjoint sorted requests', async () => {
    const spy = vi.spyOn(stocksApiModule.stocksApi, 'sparklines').mockResolvedValue({ points: 20, series: {} })
    const ids = Array.from({ length: MAX_IDS_PER_REQUEST + 1 }, (_, i) => MAX_IDS_PER_REQUEST + 1 - i)
    const { result } = renderHook(() => useSparklines(ids), { wrapper: qcWrapper() })
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(spy).toHaveBeenCalledTimes(2)
    const [a, b] = spy.mock.calls.map((c) => c[0])
    expect(a).toHaveLength(MAX_IDS_PER_REQUEST)
    expect(b).toEqual([MAX_IDS_PER_REQUEST + 1])
    expect(a[0]).toBe(1)
  })

  it('a failed request reads as error, never as "no history"', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'sparklines').mockRejectedValue(new Error('down'))
    const { result } = renderHook(() => useSparklines([1]), { wrapper: qcWrapper() })
    await waitFor(() => expect(result.current.status).toBe('error'))
  })
})

describe('StocksPage sparkline column', () => {
  it('draws the backend closes per row in ONE batch and marks rows without history', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'list').mockResolvedValue({
      items: [stock(1, 'AAA'), stock(2, 'BBB')], total: 2, page: 1, page_size: 50, pages: 1,
    })
    const spark = vi.spyOn(stocksApiModule.stocksApi, 'sparklines').mockResolvedValue({
      points: 20, series: { '1': [200, 190] },
    })
    const Wrapper = qcWrapper()
    render(<Wrapper><StocksPage /></Wrapper>)
    await waitFor(() =>
      expect(screen.getByRole('img', { name: '2-session close down 5.00%' })).toBeInTheDocument(),
    )
    expect(screen.getByRole('img', { name: 'No recent price history' })).toBeInTheDocument()
    expect(spark).toHaveBeenCalledTimes(1)
    expect(spark).toHaveBeenCalledWith([1, 2], 'test-token')
  })
})
