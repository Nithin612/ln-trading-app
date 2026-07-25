import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { journalApi, type JournalEntry } from '@/lib/api/journal'
import { JournalPage } from '@/features/journal/JournalPage'

function makeEntry(o: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: 'je-1', user_id: 1, position_id: null, stock_id: 5, symbol: 'TCS',
    trade_date: '2026-07-20', side: 'LONG', entry_price: '3800.0000', exit_price: '3900.0000',
    quantity: 10, realized_pnl: '1000.00', notes: 'clean breakout', lesson: null,
    emotion_before: 'confident', emotion_after: 'satisfied', screenshot_paths: [], tags: [],
    entry_type: 'manual', created_at: '', updated_at: '', ...o,
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  // the sidebar analytics panel fires its own query — keep it quiet
  vi.spyOn(journalApi, 'analytics').mockResolvedValue({ before: [], after: [], total_entries: 0 })
})

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><JournalPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('JournalPage', () => {
  it('shows loading skeleton rows while the list query is pending', () => {
    vi.spyOn(journalApi, 'list').mockReturnValue(new Promise(() => {}))
    const { container } = setup()
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('shows the empty state when there are no entries', async () => {
    vi.spyOn(journalApi, 'list').mockResolvedValue({ total: 0, entries: [] })
    setup()
    await waitFor(() => expect(screen.getByText(/No journal entries yet/i)).toBeInTheDocument())
  })

  it('renders an entry row with symbol, P&L and emotion', async () => {
    vi.spyOn(journalApi, 'list').mockResolvedValue({ total: 1, entries: [makeEntry()] })
    setup()
    await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument())
    expect(screen.getByText(/\+₹1,000/)).toBeInTheDocument()  // realized_pnl, Indian grouping
    expect(screen.getByText('confident')).toBeInTheDocument()
    expect(screen.getByText('satisfied')).toBeInTheDocument()
  })

  it('deletes an entry through journalApi.delete when the row trash button is clicked', async () => {
    vi.spyOn(journalApi, 'list').mockResolvedValue({ total: 1, entries: [makeEntry()] })
    const del = vi.spyOn(journalApi, 'delete').mockResolvedValue(undefined)
    setup()
    await waitFor(() => expect(screen.getByText('TCS')).toBeInTheDocument())
    fireEvent.click(screen.getByTitle('Delete'))
    await waitFor(() => expect(del).toHaveBeenCalledWith('je-1'))
  })
})
