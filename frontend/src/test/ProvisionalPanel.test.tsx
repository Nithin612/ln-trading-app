import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProvisionalPanel } from '@/features/dashboard/ProvisionalPanel'
import { provisionalApi } from '@/lib/api/market_data'
import type { ProvisionalLeaderboard } from '@/lib/api/market_data'

vi.mock('@/lib/api/market_data', () => ({
  provisionalApi: { getLeaderboard: vi.fn() },
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}))

// The stream hook owns the WebSocket lifecycle (covered by its own unit
// tests); the panel test drives its OUTPUT states directly.
const streamState = {
  boards: {} as Record<string, ProvisionalLeaderboard>,
  connected: true,
  authFailed: false,
}
vi.mock('@/hooks/useProvisionalStream', () => ({
  useProvisionalStream: () => streamState,
}))

function board(style: string, rows: ProvisionalLeaderboard['rows']): ProvisionalLeaderboard {
  return { provisional: true, style, as_of: '2026-07-16T06:03:00+00:00', rows }
}

function row(
  overrides: Partial<ProvisionalLeaderboard['rows'][number]> = {},
): ProvisionalLeaderboard['rows'][number] {
  return {
    provisional: true,
    stock_id: 1,
    symbol: 'RELIANCE',
    profile_key: 'rrbo',
    style: 'intraday',
    tf: '5m',
    confidence: 78,
    direction: 'BUY',
    gate: true,
    sources: ['watchlist'],
    ...overrides,
  }
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ProvisionalPanel />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(provisionalApi.getLeaderboard).mockReset()
  streamState.boards = {}
  streamState.connected = true
})

describe('ProvisionalPanel', () => {
  it('renders leaderboard rows from the REST snapshot, provisional-labelled', async () => {
    vi.mocked(provisionalApi.getLeaderboard).mockResolvedValue(
      board('intraday', [
        row(),
        row({ stock_id: 2, symbol: 'TCS', confidence: 71, direction: 'SELL' }),
      ]),
    )
    renderPanel()

    expect(await screen.findByText('RELIANCE')).toBeInTheDocument()
    expect(screen.getByText('TCS')).toBeInTheDocument()
    expect(screen.getByText('78.00%')).toBeInTheDocument()
    expect(screen.getByText('71.00%')).toBeInTheDocument()
    expect(screen.getByText(/▲ BUY/)).toBeInTheDocument()
    expect(screen.getByText(/▼ SELL/)).toBeInTheDocument()
    // provisional labelling is end-to-end — the panel must SAY it
    expect(screen.getByText('Provisional')).toBeInTheDocument()
    expect(screen.getByText(/converges at candle close/)).toBeInTheDocument()
  })

  it('shows the loading skeleton before data arrives', () => {
    vi.mocked(provisionalApi.getLeaderboard).mockReturnValue(new Promise(() => {}))
    renderPanel()
    expect(screen.getByLabelText('loading leaderboard')).toBeInTheDocument()
  })

  it('shows the empty state when nothing passes the gate', async () => {
    vi.mocked(provisionalApi.getLeaderboard).mockResolvedValue(board('intraday', []))
    renderPanel()
    expect(await screen.findByText('No provisional scores')).toBeInTheDocument()
  })

  it('shows the error state with a retry action', async () => {
    vi.mocked(provisionalApi.getLeaderboard).mockRejectedValue(new Error('boom'))
    renderPanel()
    expect(await screen.findByText('Leaderboard unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('switches styles via the tabs and fetches that leaderboard', async () => {
    vi.mocked(provisionalApi.getLeaderboard).mockImplementation((style: string) =>
      Promise.resolve(
        board(style, style === 'swing' ? [row({ symbol: 'INFY', style: 'swing' })] : []),
      ),
    )
    renderPanel()
    await screen.findByText('No provisional scores')

    await userEvent.click(screen.getByRole('tab', { name: 'swing' }))

    expect(await screen.findByText('INFY')).toBeInTheDocument()
    await waitFor(() =>
      expect(vi.mocked(provisionalApi.getLeaderboard)).toHaveBeenCalledWith(
        'swing',
        'test-token',
      ),
    )
  })

  it('prefers the live WS snapshot and flags below-gate signal rows', async () => {
    vi.mocked(provisionalApi.getLeaderboard).mockResolvedValue(board('intraday', [row()]))
    streamState.boards = {
      intraday: board('intraday', [
        row({ symbol: 'HDFCBANK', confidence: null, direction: null, gate: false, signal_id: '42' }),
        row({ stock_id: 9, symbol: 'WIPRO', confidence: null, direction: null, gate: null, signal_id: '43' }),
      ]),
    }
    renderPanel()

    expect(await screen.findByText('HDFCBANK')).toBeInTheDocument()
    expect(screen.queryByText('RELIANCE')).not.toBeInTheDocument()
    // gate=false → a real below-gate verdict; gate=null → no data (never conflated)
    expect(screen.getByText('— below gate')).toBeInTheDocument()
    expect(screen.getByText('— no data')).toBeInTheDocument()
    expect(screen.getAllByText('signal')).toHaveLength(2)
  })
})
