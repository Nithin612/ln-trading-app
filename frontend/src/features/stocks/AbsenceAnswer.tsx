import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { SkeletonTable } from '@/components/ui/skeleton'
import { stocksApi } from '@/lib/api/stocks'
import { useAuthStore } from '@/store/authStore'

/**
 * V4 / A2 — the answer to an absence, shown exactly where the user hits it.
 *
 * ⭐ **§45/S2: an absence is not askable.** Everywhere else a name the universe rule
 * excluded simply is not there, and "No stocks found" is indistinguishable from "no such
 * company". Measured 2026-09-15: **1,104 of 3,395 stocks** are invisible to the list,
 * which defaults `is_active=true`.
 *
 * ⚠ This renders ONLY on the empty result of a real query — the same discipline V1's
 * funnel uses. A diagnostic attached to a question the user did not ask is noise.
 */
export function AbsenceAnswer({ query }: { query: string }) {
  const token = useAuthStore((s) => s.accessToken) ?? ''
  const { data, isError, isFetching, refetch } = useQuery({
    queryKey: ['stock-absence', query],
    queryFn: () => stocksApi.search(query, token),
    enabled: Boolean(token && query.trim()),
    staleTime: 30_000,
  })

  /*
    ⚠ `isFetching`, not `isPending`. With `enabled: false` — no token, or a blank query —
    TanStack v5 keeps `isPending` true FOREVER, so a loading state branched on it becomes
    the permanent render in that case (ui-reviewer #7).
  */
  if (isFetching) {
    return (
      <div className="py-6" aria-busy="true">
        <SkeletonTable rows={2} cols={1} />
      </div>
    )
  }

  /*
    ⛔⛔ THE ERROR BRANCH, and its absence was the worst defect in this component. Without
    it a failed request fell through to the terminal answer below, so a NETWORK ERROR
    rendered as a definitive claim about the master list — verbatim: "not in the tradeable
    universe, and not anywhere else in the master list either". In the one component whose
    entire purpose is answering absence honestly (ui-reviewer #6). A24: "not assessable"
    is a legitimate rendering and beats a plausible-looking default.
  */
  if (isError) {
    return (
      <div role="alert" className="py-6 text-center text-sm">
        <p className="text-(--color-text)">
          Couldn’t check the master list — so this says nothing about whether “{query}”
          exists.
        </p>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  const hits = data?.hits ?? []
  if (hits.length === 0) {
    // ⚠ The honest terminal answer, and it is DIFFERENT from "excluded": we looked at the
    // whole master, not just the tradeable subset, and there is no such company.
    return (
      <p className="py-6 text-center text-sm text-(--color-text-secondary)">
        No stock matches “{query}” — not in the tradeable universe, and not anywhere else
        in the master list either.
      </p>
    )
  }

  return (
    <div className="px-4 py-5 text-sm">
      <p className="font-semibold">
        {hits.length} name{hits.length !== 1 ? 's' : ''} match “{query}”, but{' '}
        {hits.length !== 1 ? 'none are' : 'it is not'} available to trade or suggest:
      </p>
      {data?.matched_former_symbol && (
        <p
          className="mt-2 rounded px-2 py-1.5"
          style={{ background: 'var(--color-warning-bg)', color: 'var(--color-warning)' }}
        >
          “{data.matched_former_symbol}” is a former ticker — the company still exists
          under a new symbol, and its history, signals and positions moved with it.
        </p>
      )}
      <ul className="mt-3 space-y-3">
        {hits.map((h) => (
          <li key={h.stock_id} className="border-l-2 border-(--color-border-strong) pl-3">
            <Link
              to={`/stocks/${h.stock_id}`}
              className="font-mono font-bold text-(--color-accent) hover:text-(--color-accent-hover) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--color-bg)"
            >
              {h.symbol}
            </Link>
            <span className="ml-2 text-(--color-text-secondary)">{h.company_name}</span>
            {h.former_symbols.length > 0 && (
              <span className="ml-2 text-(--color-text-secondary)">
                (formerly {h.former_symbols.join(', ')})
              </span>
            )}
            <ul className="mt-1 space-y-0.5">
              {h.exclusion_reasons.map((r) => (
                <li key={r} className="text-(--color-text-secondary)">
                  — {r}
                </li>
              ))}
            </ul>
            {/*
              ⚠ A24 — a reason derived from a recorded evaluation carries ITS DATE, so it
              is never read as a timeless fact about the company. When the rule term could
              not be justified from a record, no date is shown and none is implied.
            */}
            {h.reason_as_of && (
              <p className="mt-0.5 text-xs text-(--color-text-secondary)">
                as evaluated {h.reason_as_of}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
