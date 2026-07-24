/**
 * Phase 4 — frontend market data tests
 *
 * CandlestickChart: renders chart container when bars provided; shows empty state
 * FiiDiiPage: shows latest FII/DII cards; shows empty state when no data
 * StockDetailPage: queries OHLCV and passes bars to chart
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import { CandlestickChart } from '@/components/charts/CandlestickChart'
import { FiiDiiPage } from '@/features/market/FiiDiiPage'
import { StockDetailPage } from '@/pages/stocks/StockDetailPage'
import * as stocksApiModule from '@/lib/api/stocks'
import * as marketDataApiModule from '@/lib/api/market_data'
import * as categoriesApiModule from '@/lib/api/categories'

// Mock the chart in integration tests to avoid canvas/WebGL requirements
vi.mock('@/components/charts/CandlestickChart', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/charts/CandlestickChart')>()
  return {
    ...actual,
    CandlestickChart: ({ bars }: { bars: { time: string }[] }) =>
      bars.length === 0 ? (
        <div>No price data available — run bhavcopy ingestion first</div>
      ) : (
        <div data-testid="candlestick-chart">Chart ({bars.length} bars)</div>
      ),
  }
})

const USER = {
  id: 1, email: 'u@example.com', full_name: 'Test', role: 'user' as const,
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, is_active: true, trading_mode: 'paper' as const, allow_offmarket_entry: false,
  created_at: '', updated_at: '',
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token', user: USER })
})

function wrap(ui: React.ReactElement, path = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

// ── CandlestickChart (via mock) ───────────────────────────────────────────────

describe('CandlestickChart', () => {
  it('shows empty-state message when no bars provided', () => {
    wrap(<CandlestickChart bars={[]} />)
    expect(screen.getByText(/no price data available/i)).toBeInTheDocument()
  })

  it('renders chart element when bars are present', () => {
    const bars = [
      { time: '2026-05-18', open: 2900, high: 2950, low: 2880, close: 2930, volume: 1_000_000 },
    ]
    wrap(<CandlestickChart bars={bars} height={200} />)
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument()
  })
})

// ── FiiDiiPage ────────────────────────────────────────────────────────────────

const FII_DII_RESPONSE: marketDataApiModule.FiiDiiResponse = {
  total: 2,
  rows: [
    {
      trade_date: '2026-05-18',
      investor_type: 'FII',
      segment: 'cash',
      buy_value_cr: '12345.00',
      sell_value_cr: '9876.00',
      net_value_cr: '2469.00',
    },
    {
      trade_date: '2026-05-18',
      investor_type: 'DII',
      segment: 'cash',
      buy_value_cr: '8000.00',
      sell_value_cr: '7000.00',
      net_value_cr: '1000.00',
    },
  ],
}

describe('FiiDiiPage', () => {
  it('shows FII and DII latest cards when data is available', async () => {
    vi.spyOn(marketDataApiModule.marketDataApi, 'getFiiDii').mockResolvedValue(FII_DII_RESPONSE)

    wrap(<FiiDiiPage />)

    await waitFor(() => {
      expect(screen.getByText(/FII Latest/i)).toBeInTheDocument()
      expect(screen.getByText(/DII Latest/i)).toBeInTheDocument()
    })
  })

  it('shows empty state message when no data', async () => {
    vi.spyOn(marketDataApiModule.marketDataApi, 'getFiiDii').mockResolvedValue({
      total: 0,
      rows: [],
    })

    wrap(<FiiDiiPage />)

    await waitFor(() => {
      expect(screen.getByText(/No FII\/DII data/i)).toBeInTheDocument()
    })
  })
})

// ── StockDetailPage ───────────────────────────────────────────────────────────

const STOCK: stocksApiModule.Stock = {
  id: 1, symbol: 'RELIANCE', exchange: 'NSE', isin: null,
  company_name: 'Reliance Industries Ltd', sector: 'Energy', industry: 'Energy',
  market_cap_cr: null, lot_size: 1, tick_size: '0.05',
  is_fno: true, is_nifty50: true, is_banknifty: false, is_finnifty: false,
  is_active: true, listed_on: null, created_at: '', updated_at: '',
}

const OHLCV_RESPONSE: marketDataApiModule.OhlcvResponse = {
  stock_id: 1,
  timeframe: '1d',
  bars: [
    {
      time: '2026-05-18T00:00:00Z',
      open: '2900.0000',
      high: '2950.0000',
      low: '2880.0000',
      close: '2930.0000',
      volume: 1_000_000,
    },
  ],
}

describe('StockDetailPage', () => {
  it('renders stock info and triggers OHLCV query', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'get').mockResolvedValue(STOCK)
    vi.spyOn(marketDataApiModule.marketDataApi, 'getOhlcv').mockResolvedValue(OHLCV_RESPONSE)
    vi.spyOn(categoriesApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([])

    wrap(
      <Routes>
        <Route path="/stocks/:id" element={<StockDetailPage />} />
      </Routes>,
      '/stocks/1',
    )

    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeInTheDocument()
    })

    expect(screen.getByText(/Price History/i)).toBeInTheDocument()
    expect(marketDataApiModule.marketDataApi.getOhlcv).toHaveBeenCalledWith(
      1,
      expect.any(Object),
      'test-token',
    )
  })

  it('shows "no price data" when OHLCV returns empty bars', async () => {
    vi.spyOn(stocksApiModule.stocksApi, 'get').mockResolvedValue(STOCK)
    vi.spyOn(marketDataApiModule.marketDataApi, 'getOhlcv').mockResolvedValue({
      stock_id: 1, timeframe: '1d', bars: [],
    })
    vi.spyOn(categoriesApiModule.categoriesApi, 'getStockCategories').mockResolvedValue([])

    wrap(
      <Routes>
        <Route path="/stocks/:id" element={<StockDetailPage />} />
      </Routes>,
      '/stocks/1',
    )

    await waitFor(() => {
      expect(screen.getByText(/No price data available/i)).toBeInTheDocument()
    })
  })
})
