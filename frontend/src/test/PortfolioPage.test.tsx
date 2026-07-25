import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NetWorthOut } from '@/lib/api/portfolio'
import { getNetWorth, listBatches, listAssets } from '@/lib/api/portfolio'
import { PortfolioPage } from '@/features/portfolio/PortfolioPage'

// portfolio.ts exposes bare named function exports — mock the module.
vi.mock('@/lib/api/portfolio', () => ({
  getNetWorth: vi.fn(),
  listBatches: vi.fn(),
  getBatch: vi.fn(),
  deleteBatch: vi.fn(),
  uploadCas: vi.fn(),
  listAssets: vi.fn(),
  createAsset: vi.fn(),
  updateAsset: vi.fn(),
  deleteAsset: vi.fn(),
}))

function makeNetWorth(o: Partial<NetWorthOut> = {}): NetWorthOut {
  return {
    equity: { current_value: '500000', cost_basis: '450000', unrealized_pnl: '50000', position_count: 3 },
    mutual_funds: { current_value: '200000', holding_count: 5, last_imported: '2026-07-01' },
    manual_assets: { current_value: '100000', count: 2, breakdown: [] },
    total_net_worth: '800000',
    as_of: '2026-07-24T10:00:00Z',
    ...o,
  }
}

beforeEach(() => {
  vi.mocked(listBatches).mockResolvedValue([])
  vi.mocked(listAssets).mockResolvedValue([])
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PortfolioPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PortfolioPage', () => {
  it('shows a loading skeleton while net worth is pending', () => {
    vi.mocked(getNetWorth).mockReturnValue(new Promise(() => {}))
    const { container } = setup()
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('renders the net-worth total and segment breakdown', async () => {
    vi.mocked(getNetWorth).mockResolvedValue(makeNetWorth())
    setup()
    await waitFor(() => expect(screen.getByText('Total Net Worth')).toBeInTheDocument())
    expect(screen.getByText(/8,00,000/)).toBeInTheDocument()   // total, Indian grouping
    expect(screen.getByText('Equity')).toBeInTheDocument()      // segment card
    expect(screen.getByText(/5,00,000/)).toBeInTheDocument()    // equity value
  })

  it('exposes the three portfolio tabs', async () => {
    vi.mocked(getNetWorth).mockResolvedValue(makeNetWorth())
    setup()
    await waitFor(() => expect(screen.getByRole('tab', { name: /net worth/i })).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: /mutual funds/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /other assets/i })).toBeInTheDocument()
  })

  it('switches to the Mutual Funds tab and shows the CAS upload zone', async () => {
    vi.mocked(getNetWorth).mockResolvedValue(makeNetWorth())
    setup()
    await waitFor(() => expect(screen.getByRole('tab', { name: /mutual funds/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('tab', { name: /mutual funds/i }))
    expect(await screen.findByText(/Drop your CAMS CAS PDF here/i)).toBeInTheDocument()
  })
})
