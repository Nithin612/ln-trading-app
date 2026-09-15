import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CaQuarantinePage } from '@/pages/admin/CaQuarantinePage'
import { ApiError } from '@/lib/api/client'
import * as caApi from '@/lib/api/corporateActions'

vi.mock('@/store/authStore', () => ({
  useAuthStore: (sel: (s: { accessToken: string }) => unknown) =>
    sel({ accessToken: 'tok' }),
}))

/**
 * V7 / A9 — the CA quarantine review queue.
 *
 * ⭐ A9 refused this page outright while the quarantine had no clearer: *"a monotonic
 * accumulator with no clearer should not get a surface that invites an unflag request
 * nobody can grant."* The mechanism shipped first; these tests pin the two things the
 * surface must not get wrong — that clearing is a RECORDED JUDGEMENT with a reason, and
 * that it is not confused with ADJUSTING.
 */
function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const ROW: caApi.CaQuarantineOut = {
  stock_id: 7,
  symbol: 'DUCON',
  flagged_at: '2026-08-25T13:31:14Z',
  reason: '2026-08-25: open 2.26 vs prev close 3.08 (-26.6%) — possible corporate action',
  is_active: true,
}

describe('CaQuarantinePage', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('lists the queue with the detector’s own reason', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    expect(screen.getByText(/-26\.6%/)).toBeInTheDocument()
    expect(screen.getByText(/Quarantined — 1 name/)).toBeInTheDocument()
  })

  it('says clearing adjusts NOTHING, and says what to do INSTEAD, in the dialog', async () => {
    // ⛔ The failure this guards is the one that matters: a reviewer under time pressure
    // reading "clear" as "fix the split". Clearing asserts the history is USABLE; a name
    // that really split still needs a verified ratio recorded separately, and a reviewer
    // who clears instead has re-admitted poisoned bars to every indicator window.
    //
    // ⚠ THE FIXTURE DELIBERATELY OMITS THE PHRASE THIS ASSERTS. The first version matched
    // /verified ratio|corporate action/ against the whole dialog — and the DETECTOR's own
    // reason string ends "— possible corporate action", which the dialog echoes. So it
    // passed on the fixture's text rather than on the copy, and would have kept passing
    // with the sentence deleted (ui-reviewer #5). `reason: null` removes that escape.
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([
      { ...ROW, reason: null },
    ])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    expect(screen.getByText(/Clearing adjusts nothing/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/does not adjust anything/i)
    // The REMEDY, in the dialog where the irreversible judgement is entered — not only in
    // the page banner the reviewer already scrolled past.
    expect(dialog).toHaveTextContent(/record a verified ratio as a corporate action/i)
    expect(dialog).toHaveTextContent(/do not clear it/i)
  })

  it('will not submit a thin reason, and says why without hiding it', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    const clear = vi.spyOn(caApi.corporateActionsApi, 'clearQuarantine')
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))

    const submit = screen.getByRole('button', { name: /clear quarantine/i })
    // ⚠ `aria-disabled`, never the native attribute: a native disabled control drops out
    // of tab order and kills its own tooltip, so the reason it cannot be pressed becomes
    // unreadable. This project learned that from the ⊘ Blocked buttons.
    expect(submit).toHaveAttribute('aria-disabled', 'true')
    expect(submit).not.toHaveAttribute('disabled')
    await userEvent.click(submit)
    expect(clear).not.toHaveBeenCalled()

    await userEvent.type(
      screen.getByLabelText(/why is it safe/i),
      'Verified against NSE: a genuine circuit move.',
    )
    expect(submit).toHaveAttribute('aria-disabled', 'false')
  })

  it('sends the reason and refreshes the queue', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    const clear = vi
      .spyOn(caApi.corporateActionsApi, 'clearQuarantine')
      .mockResolvedValue(ROW)
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    await userEvent.type(
      screen.getByLabelText(/why is it safe/i),
      'Verified against NSE: a genuine circuit move, no corporate action.',
    )
    await userEvent.click(screen.getByRole('button', { name: /clear quarantine/i }))
    await waitFor(() =>
      expect(clear).toHaveBeenCalledWith(
        7,
        'Verified against NSE: a genuine circuit move, no corporate action.',
        'tok',
      ),
    )
  })

  it('closes on Escape — measured as BROKEN in the hand-rolled version', async () => {
    // ⛔ ui-reviewer MEASURED that the hand-rolled dialog did not close on Escape: focus
    // stayed on the "Review…" trigger, outside the dialog subtree, so the keydown never
    // reached the overlay's handler. It worked only after clicking inside. The fix was to
    // stop hand-rolling and use the portalled Dialog primitive four other surfaces already
    // use; this pins the BEHAVIOUR so a future hand-roll fails here.
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    await screen.findByRole('dialog')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('never renders UNKNOWN prior-clear history as a verified zero', async () => {
    // A24 — "we could not check" and "it has never been cleared" are different claims and
    // only one of them is reassuring. The count rendered identically for both, and the
    // submit was reachable before the history resolved (ui-reviewer #6).
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockRejectedValue(
      new Error('boom'),
    )
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    const dialog = await screen.findByRole('dialog')
    await waitFor(() =>
      expect(dialog).toHaveTextContent(/prior-clear history unavailable/i),
    )
  })

  it('warns when the name has been cleared before', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([
      { id: 1, stock_id: 7, event: 'flagged', at: '2026-07-01T00:00:00Z',
        reason: 'gap', actor_user_id: null },
      { id: 2, stock_id: 7, event: 'cleared', at: '2026-07-02T00:00:00Z',
        reason: 'checked against NSE', actor_user_id: 3 },
    ])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    expect(await screen.findByText(/Cleared 1 time before/i)).toBeInTheDocument()
  })

  it('shows the real error, not the one cause the submit already prevents', async () => {
    // ⛔ The old copy hardcoded "the reason must be at least 10 characters" — the ONE cause
    // this path cannot produce, since the submit is guarded. Every error a user actually
    // sees (403, a 404 "not currently quarantined", 500, offline) was reported as a false
    // cause (ui-reviewer #4).
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([ROW])
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantineHistory').mockResolvedValue([])
    vi.spyOn(caApi.corporateActionsApi, 'clearQuarantine').mockRejectedValue(
      new ApiError(404, 'stock 7 is not in CA quarantine'),
    )
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    await userEvent.click(screen.getByRole('button', { name: /review/i }))
    await userEvent.type(
      screen.getByLabelText(/why is it safe/i),
      'Verified against NSE: a genuine circuit move.',
    )
    await userEvent.click(screen.getByRole('button', { name: /clear quarantine/i }))
    expect(await screen.findByText(/not in CA quarantine/i)).toBeInTheDocument()
    expect(screen.queryByText(/at least 10 characters/i)).not.toBeInTheDocument()
  })

  it('marks a quarantined name that is outside the tradeable universe', async () => {
    // ⚠ The queue includes them on purpose — the flag and the universe rule are
    // independent — so the row has to say why it is asking for a decision on a name the
    // reviewer cannot trade.
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([
      { ...ROW, is_active: false },
    ])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText('DUCON'))
    expect(screen.getByText('not in universe')).toBeInTheDocument()
  })

  it('shows an empty state that explains when names appear', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockResolvedValue([])
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByText(/Nothing is quarantined/i))
    // ⚠ Scoped to copy unique to the EMPTY STATE. The intro banner renders in every state
    // (deliberately — it explains what the page is before there is anything on it), so it
    // also contains "gaps more than 20%" and a loose match now finds two elements.
    expect(screen.getByText(/Names appear here/i)).toBeInTheDocument()
  })

  it('shows an error state with a retry', async () => {
    vi.spyOn(caApi.corporateActionsApi, 'getQuarantine').mockRejectedValue(
      new Error('boom'),
    )
    wrap(<CaQuarantinePage />)
    await waitFor(() => screen.getByRole('alert'))
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
