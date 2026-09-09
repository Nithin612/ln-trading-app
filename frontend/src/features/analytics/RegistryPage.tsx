import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { analyticsApi, type GateHypothesis } from '@/lib/api/analytics'
import { PageHeader } from '@/components/layout/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { cn } from '@/lib/utils'
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table'

// U1 — the gate/hypothesis register (H4) rendered from GET /analytics/gate-register.
// Every partition we searched, decided or shipped — including the reverted and decided-no
// ones, kept VISIBLE on purpose (U6), because a register that hides its failures is the
// selection bias the deflated-Sharpe bar exists to correct.

type Status = GateHypothesis['status']

const STATUS_LABEL: Record<Status, string> = {
  active: 'Active',
  shadow: 'Shadow',
  reverted: 'Reverted',
  decided_no: 'Decided — no',
  research: 'Research',
}

// Token-backed pills (the StatusPill pattern), NOT the generic `destructive` Badge variant:
// that maps to --color-error (red-600), which fails WCAG AA in the daybreak/carbon themes on
// its own tint. `reverted` uses --color-loss, hardened to red-700 for exactly this contrast
// reason (tokens.css daybreak block). Every colour here is a token, so all 5 themes resolve.
const STATUS_CLASS: Record<Status, string> = {
  active: 'text-(--color-info) bg-(--color-info-bg) border-(--color-info)/20',
  shadow: 'text-(--color-warning) bg-(--color-warning-bg) border-(--color-warning)/20',
  reverted: 'text-(--color-loss) bg-(--color-loss-bg) border-(--color-loss)/20',
  decided_no: 'text-(--color-text-muted) bg-(--color-surface-3) border-(--color-border)',
  research: 'text-(--color-text-muted) bg-(--color-surface-3) border-(--color-border)',
}

// Active/shadow first (live evidence), the closed ones (reverted/decided) below — visible,
// never hidden. Research last. Stable within a status (the API preserves register order).
const STATUS_ORDER: Record<Status, number> = {
  active: 0,
  shadow: 1,
  reverted: 2,
  decided_no: 3,
  research: 4,
}

function StatusPill({ status, suffix }: { status: Status; suffix?: string }) {
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium',
        STATUS_CLASS[status],
      )}
    >
      {STATUS_LABEL[status]}
      {suffix}
    </span>
  )
}

export function RegistryPage() {
  const { accessToken } = useAuth()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['gate-register'],
    queryFn: () => analyticsApi.getGateRegister(accessToken!),
    enabled: !!accessToken,
    staleTime: 60_000,
  })

  const rows = data
    ? [...data.hypotheses].sort(
        (a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status],
      )
    : []

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Gate register"
        subtitle="Every partition of the book we've searched, decided or shipped — the evidence behind the deflated-Sharpe bar. Read-only; failures are kept visible on purpose."
      />

      {isLoading && (
        <div className="flex flex-col gap-3" aria-label="loading gate register">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {isError && (
        <div className="p-4 text-sm text-(--color-text-muted) bg-(--color-surface-2) border border-(--color-border) rounded-lg">
          Could not load the gate register.{' '}
          <Button variant="link" size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      )}

      {data && (
        <>
          {/* U4 — observed vs assumed trials, framed honestly (A24). */}
          <div className="bg-(--color-surface-2) border border-(--color-border) rounded-lg p-4">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
              <div>
                <span className="text-xl font-bold font-mono tabular-nums text-(--color-text)">
                  {data.trials_attempted}
                </span>
                <span className="ml-2 text-[11px] text-(--color-text-muted) uppercase tracking-wide">
                  trials observed
                </span>
              </div>
              <div>
                <span className="text-xl font-bold font-mono tabular-nums text-(--color-text)">
                  {data.assumed_trials}
                </span>
                <span className="ml-2 text-[11px] text-(--color-text-muted) uppercase tracking-wide">
                  assumed in the bar
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.counts)
                  .filter(([, n]) => n > 0)
                  .map(([status, n]) => (
                    <StatusPill key={status} status={status as Status} suffix={`: ${n}`} />
                  ))}
              </div>
            </div>
            <p className="mt-2 text-[11px] text-(--color-text-muted)">
              Observed is a <strong>lower bound</strong> — threshold variants aren't counted yet,
              so observed &lt; assumed does <strong>not</strong> make the bar conservative.
              As of {data.as_of}.
            </p>
          </div>

          {/* U1/U6 — the register as rows. */}
          {rows.length === 0 ? (
            <EmptyState
              title="No hypotheses recorded"
              description="The gate register is empty — nothing has been searched, shipped or reverted yet."
            />
          ) : (
            <div className="rounded-lg border border-(--color-border)">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Hypothesis</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Trial</TableHead>
                    <TableHead>Verdict</TableHead>
                    <TableHead>Review due</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((h) => (
                    <TableRow key={h.key}>
                      <TableCell>
                        {h.has_cohort ? (
                          // U20 — drill into the would-block cohort (only gates that have one).
                          <Link
                            to={`/analytics/registry/${h.key}`}
                            className="font-medium text-(--color-info) hover:underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--color-bg)"
                            title="View the would-block cohort"
                          >
                            {h.name}
                          </Link>
                        ) : (
                          <div className="font-medium text-(--color-text)">{h.name}</div>
                        )}
                        <div className="text-[11px] text-(--color-text-muted) font-mono">
                          {h.key}
                        </div>
                      </TableCell>
                      <TableCell>
                        <StatusPill status={h.status} />
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-(--color-text-muted)">
                          {h.counts_as_trial ? 'yes' : 'rule / rail'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-(--color-text) whitespace-normal">
                          {h.verdict}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-(--color-text-muted)">
                          {h.review_due ?? '—'}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
