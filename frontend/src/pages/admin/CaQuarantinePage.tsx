import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Label } from '@/components/ui/label'
import { SkeletonTable } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError } from '@/lib/api/client'
import { type CaQuarantineOut, corporateActionsApi } from '@/lib/api/corporateActions'
import { formatIstDateTime } from '@/lib/format'
import { useAuthStore } from '@/store/authStore'

/**
 * V7 / A9 — the CA quarantine review queue.
 *
 * ⭐ **Why this page could not exist until now.** A9 refused it outright while the
 * quarantine had no clearer: *"a monotonic accumulator with no clearer should not get a
 * surface that invites an unflag request nobody can grant."* The mechanism shipped first
 * (`ca_quarantine.py` + the admin endpoints); this is the surface it unblocked.
 *
 * ⚠ **What clearing actually asserts.** It does NOT adjust anything. It records a human
 * judgement that the unadjusted price history is safe to score again — because the gap was
 * a real move, the series has since been adjusted, or the bad bars have aged out of every
 * indicator window. A name that genuinely split needs a VERIFIED RATIO recorded as a
 * corporate action instead, and a reviewer who clears it instead has re-admitted poisoned
 * bars to every indicator window. That sentence therefore appears in the dialog itself,
 * not only in the page banner the reviewer already scrolled past (ui-reviewer #5).
 */
const STALE_MS = 30_000

export function CaQuarantinePage() {
  const token = useAuthStore((s) => s.accessToken) ?? ''
  const qc = useQueryClient()
  const [clearing, setClearing] = useState<CaQuarantineOut | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['ca-quarantine'],
    queryFn: () => corporateActionsApi.getQuarantine(token),
    enabled: Boolean(token),
    staleTime: STALE_MS,
  })

  const rows = data ?? []

  return (
    <div className="h-full flex flex-col gap-4">
      <PageHeader
        title="CA Quarantine"
        subtitle="Names the corporate-action detector is holding out of every suggestion universe"
      />

      <div
        className="rounded-lg border border-(--color-border) bg-(--color-surface-2) px-4 py-3 text-sm"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        The detector quarantines a stock when a session&apos;s open gaps more than 20% from
        the previous close, which usually means an unadjusted split or bonus. Quarantined
        names are excluded from every suggestion universe until a human reviews them.{' '}
        <strong style={{ color: 'var(--color-text)' }}>Clearing adjusts nothing</strong> —
        it records that the unadjusted history is safe to score again. If a name really
        split, record a verified ratio as a corporate action instead.
      </div>

      {isLoading ? (
        <SkeletonTable rows={6} cols={4} />
      ) : error ? (
        <div
          role="alert"
          className="rounded-lg border px-4 py-3 text-sm"
          style={{
            borderColor: 'var(--color-loss)',
            background: 'var(--color-loss-bg)',
            color: 'var(--color-text)',
          }}
        >
          {error instanceof ApiError
            ? error.message
            : 'Could not load the quarantine queue.'}{' '}
          <Button
            variant="outline"
            size="sm"
            className="ml-2"
            onClick={() => void qc.invalidateQueries({ queryKey: ['ca-quarantine'] })}
          >
            Retry
          </Button>
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck size={28} />}
          title="Nothing is quarantined"
          description="The detector runs with each EOD ingest. Names appear here when a session's open gaps more than 20% from the previous close."
        />
      ) : (
        <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-(--color-border)">
            {/*
              ⛔ NOT `--color-text-muted`: measured 3.52 (slate, the DEFAULT theme) and
              2.34 (daybreak) on this surface — sub-AA in four of five themes, and the
              contrast ratchet cannot see it because it only checks pairs it lists, not
              pairs assembled in a component (ui-reviewer #3).
            */}
            <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-secondary)">
              Quarantined — {rows.length} name{rows.length !== 1 ? 's' : ''}
            </span>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Symbol</TableHead>
                <TableHead>Flagged</TableHead>
                <TableHead>Detector&apos;s reason</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.stock_id}>
                  <TableCell className="font-mono font-bold">
                    {r.symbol}
                    {/*
                      ⚠ The queue deliberately includes names outside the tradeable
                      universe — the flag and the universe rule are independent. Saying so
                      per row stops a reviewer wondering why a name they cannot trade is
                      asking for a decision.
                    */}
                    {!r.is_active && (
                      <span
                        className="ml-2 inline-block rounded px-1 py-px text-[10px] font-sans font-normal"
                        style={{
                          background: 'var(--color-warning-bg)',
                          color: 'var(--color-warning)',
                        }}
                      >
                        not in universe
                      </span>
                    )}
                  </TableCell>
                  {/*
                    ⚠ `formatIstDateTime`, not a string slice of the ISO value: storage is
                    UTC and market logic is IST, so slicing renders the PREVIOUS calendar
                    day for any flag written after 18:30 IST — which is exactly when the
                    EOD ingest runs (ui-reviewer #8).
                  */}
                  <TableCell className="text-(--color-text-secondary)">
                    {formatIstDateTime(r.flagged_at)}
                  </TableCell>
                  <TableCell className="text-(--color-text-secondary)">
                    {r.reason ?? '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="secondary" size="sm" onClick={() => setClearing(r)}>
                      Review…
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {clearing && (
        <ClearDialog
          row={clearing}
          token={token}
          onClose={() => setClearing(null)}
          onDone={() => {
            setClearing(null)
            void qc.invalidateQueries({ queryKey: ['ca-quarantine'] })
          }}
        />
      )}
    </div>
  )
}

const MIN_REASON = 10

function ClearDialog({
  row,
  token,
  onClose,
  onDone,
}: {
  row: CaQuarantineOut
  token: string
  onClose: () => void
  onDone: () => void
}) {
  const [reason, setReason] = useState('')

  /*
    ⭐ The prior history, and it is not decoration. A name flagged for the FIRST time and a
    name flagged-and-cleared three times are different decisions: the second says either
    the detector keeps mis-reading this stock, or somebody keeps waving it through.
    ⚠ Wired the moment it was written — the V6 lint failed this page's first commit for
    exactly this client function having no caller.
  */
  const history = useQuery({
    queryKey: ['ca-quarantine-history', row.stock_id],
    queryFn: () => corporateActionsApi.getQuarantineHistory(row.stock_id, token),
    enabled: Boolean(token),
    staleTime: STALE_MS,
  })
  const priorClears = (history.data ?? []).filter((e) => e.event === 'cleared').length

  const mut = useMutation({
    mutationFn: () => corporateActionsApi.clearQuarantine(row.stock_id, reason, token),
    onSuccess: onDone,
  })

  const short = MIN_REASON - reason.trim().length
  // ⚠ The submit waits for the history too. Without it a reviewer can clear a fourth-time
  // offender before the warning has loaded — the race ui-reviewer #6 measured.
  const blocked = short > 0 || mut.isPending || history.isPending

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clear {row.symbol} from quarantine</DialogTitle>
          <DialogDescription>
            {row.reason ?? 'No detector reason recorded.'}
          </DialogDescription>
        </DialogHeader>

        <p className="text-sm">
          This records that the unadjusted price history is safe to score again — because
          the gap was a real move, the series has since been adjusted, or the bad bars have
          aged out of every indicator window. <strong>It does not adjust anything.</strong>
        </p>
        {/*
          ⭐ The sentence that must not live only in the page banner. A reviewer is IN the
          dialog when they make an irreversible judgement, and "what do I do instead" is
          the half that keeps them from clearing a genuine split (ui-reviewer #5).
        */}
        <p className="text-sm">
          <strong>If {row.symbol} really split or issued a bonus, do not clear it</strong> —
          record a verified ratio as a corporate action instead, or its unadjusted bars go
          straight back into every indicator window.
        </p>

        {/* A24 — "we do not know" must not render as a verified zero (ui-reviewer #6). */}
        {history.isPending && (
          <p className="text-sm text-(--color-text-secondary)">Checking prior clears…</p>
        )}
        {history.isError && (
          <p
            className="rounded px-2 py-1.5 text-sm"
            style={{ background: 'var(--color-warning-bg)', color: 'var(--color-warning)' }}
          >
            Prior-clear history unavailable — decide without it.
          </p>
        )}
        {!history.isPending && !history.isError && priorClears > 0 && (
          <p
            className="rounded px-2 py-1.5 text-sm"
            style={{ background: 'var(--color-warning-bg)', color: 'var(--color-warning)' }}
          >
            Cleared {priorClears} time{priorClears !== 1 ? 's' : ''} before. A name that
            keeps returning is either mis-read by the detector or waved through too easily —
            read the earlier reasons before adding another.
          </p>
        )}

        <div className="grid gap-1.5">
          <Label htmlFor="ca-clear-reason">
            Why is it safe? (recorded permanently, with your name)
          </Label>
          <textarea
            id="ca-clear-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            aria-describedby="ca-clear-hint"
            className="w-full rounded border border-(--color-border) bg-(--color-surface-2) px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--color-bg)"
            placeholder="e.g. Verified against NSE: a genuine 22% circuit move, no corporate action."
          />
          {/*
            ⚠ The reason the button cannot be pressed, VISIBLE and announced — not parked
            in a `title` that never renders on the keyboard path. `tradeBlock` gets this
            right by changing the label; this is the same idea for a form (ui-reviewer #7).
          */}
          <p id="ca-clear-hint" className="text-xs text-(--color-text-secondary)">
            {short > 0
              ? `${short} more character${short !== 1 ? 's' : ''} needed — say what you checked.`
              : 'Recorded in the append-only quarantine log against your user.'}
          </p>
        </div>

        {mut.isError && (
          /*
            ⛔ The previous copy hardcoded "the reason must be at least 10 characters" —
            the ONE cause this path cannot produce, since the submit is already guarded.
            Every error a user actually sees here (403, a 404 "not currently quarantined",
            500, offline) was being reported as a false cause (ui-reviewer #4).
          */
          <p role="alert" className="text-sm" style={{ color: 'var(--color-loss)' }}>
            {mut.error instanceof ApiError
              ? mut.error.message
              : 'Could not clear it — the request failed. Nothing was changed.'}
          </p>
        )}

        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={mut.isPending}>
            Cancel
          </Button>
          {/*
            ⚠ `aria-disabled` + a click guard, never the native attribute: a native
            disabled control drops out of tab order and kills its own tooltip, so the
            reason becomes unreadable. The visible hint above carries the reason; this
            recedes with a TOKEN variant, never with opacity (the 2026-09-02 ruling).
          */}
          <Button
            size="sm"
            variant={blocked ? 'secondary' : 'default'}
            aria-disabled={blocked}
            aria-describedby="ca-clear-hint"
            onClick={() => {
              if (blocked) return
              mut.mutate()
            }}
          >
            {mut.isPending ? 'Clearing…' : 'Clear quarantine'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
