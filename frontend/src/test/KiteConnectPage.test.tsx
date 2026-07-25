import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/store/authStore'
import { brokerApi, type TokenStatus } from '@/lib/api/broker'
import KiteConnectPage from '@/features/broker/KiteConnectPage'

const mockUser = {
  id: 1, email: 'admin@trading.com', full_name: 'Admin', role: 'admin',
  capital_inr: '100000', risk_per_trade_pct: '2', daily_loss_limit_pct: '3',
  max_trades_per_day: 2, allow_offmarket_entry: false, is_active: true,
  trading_mode: 'paper', created_at: '', updated_at: '',
}

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ accessToken: 'tok', user: mockUser })
})

function status(o: Partial<TokenStatus> = {}): TokenStatus {
  return { connected: false, expires_at: null, consumer_running: false, ...o }
}

function setup(path = '/broker/kite') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}><KiteConnectPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('KiteConnectPage', () => {
  it('shows a loading skeleton while the status query is pending', () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockReturnValue(new Promise(() => {}))
    const { container } = setup()
    expect(screen.getByText('Zerodha Kite Connect')).toBeInTheDocument()
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('renders the not-connected state with a Connect button', async () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockResolvedValue(status({ connected: false }))
    setup()
    await waitFor(() => expect(screen.getByText('Not connected')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /connect to zerodha/i })).toBeInTheDocument()
  })

  it('renders connected + consumer-running with Stop and Sync actions', async () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockResolvedValue(
      status({ connected: true, expires_at: '2099-01-01T00:00:00Z', consumer_running: true }),
    )
    setup()
    await waitFor(() => expect(screen.getByText('Connected')).toBeInTheDocument())
    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /stop tick consumer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sync instruments/i })).toBeInTheDocument()
    // the primary Connect CTA is replaced by Re-authenticate once connected
    expect(screen.queryByRole('button', { name: /connect to zerodha/i })).toBeNull()
  })

  it('offers Start Tick Consumer when connected but the consumer is stopped', async () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockResolvedValue(
      status({ connected: true, expires_at: '2099-01-01T00:00:00Z', consumer_running: false }),
    )
    setup()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /start tick consumer/i })).toBeInTheDocument(),
    )
  })

  it('calls syncKiteInstruments with the access token when Sync is clicked', async () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockResolvedValue(
      status({ connected: true, expires_at: '2099-01-01T00:00:00Z', consumer_running: true }),
    )
    const sync = vi.spyOn(brokerApi, 'syncKiteInstruments').mockResolvedValue({ synced: 1582 })
    setup()
    await waitFor(() => expect(screen.getByRole('button', { name: /sync instruments/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /sync instruments/i }))
    await waitFor(() => expect(sync).toHaveBeenCalledWith('tok'))
  })

  it('auto-exchanges a request_token carried in the Kite callback URL', async () => {
    vi.spyOn(brokerApi, 'getKiteStatus').mockResolvedValue(status())
    const exchange = vi
      .spyOn(brokerApi, 'exchangeKiteToken')
      .mockResolvedValue({ detail: 'ok', expires_at: '2099-01-01T00:00:00Z' })
    setup('/broker/kite?request_token=REQ123')
    await waitFor(() => expect(exchange).toHaveBeenCalledWith('REQ123', 'tok'))
  })
})
