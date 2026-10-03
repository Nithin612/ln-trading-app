/**
 * useSparklines — REAL recent daily closes for a table's sparkline column, batched.
 *
 * Before this, three tables drew sparklines from invented data: `seededSpark(stock.id)` (a PRNG
 * seeded by the row id) on Stocks/Screener and `generateFakeSpark(entry, sl, tp)` on the
 * Dashboard — each coloured green/red by its invented path, so a random number decided which
 * names looked like they were rising.
 *
 * Three non-line states stay distinct (A24): still loading → `pending` (skeleton) · the request
 * failed → `error` ("unavailable") · answered without this id → no history. Saying "no recent
 * price history" while the answer is merely in flight would be a false claim (ui-reviewer
 * 2026-10-03), so a row reads its status through `sparkStatus`.
 */

import { keepPreviousData, useQueries } from '@tanstack/react-query'

import type { SparkStatus } from '@/components/ui/sparkline'
import { stocksApi } from '@/lib/api/stocks'
import { useAuth } from './useAuth'

/** The endpoint's per-request cap (`SPARKLINE_MAX_IDS`); larger tables are chunked. */
export const MAX_IDS_PER_REQUEST = 500

export interface Sparklines {
  series: Record<string, number[]>
  /** The table-level state; a row with a series is always 'ready' — use `sparkStatus`. */
  status: SparkStatus
}

export function sparkStatus(sparks: Sparklines, id: number): SparkStatus {
  return sparks.series[id] ? 'ready' : sparks.status
}

export function useSparklines(ids: number[]): Sparklines {
  const { accessToken } = useAuth()
  const unique = [...new Set(ids)].sort((a, b) => a - b)
  const chunks: number[][] = []
  for (let i = 0; i < unique.length; i += MAX_IDS_PER_REQUEST) {
    chunks.push(unique.slice(i, i + MAX_IDS_PER_REQUEST))
  }
  const results = useQueries({
    queries: chunks.map((chunk) => ({
      queryKey: ['sparklines', chunk.join(',')],
      queryFn: () => stocksApi.sparklines(chunk, accessToken!),
      enabled: !!accessToken,
      // Daily closes change once a day; a re-render or a filter toggle must not refetch.
      staleTime: 5 * 60_000,
      // A changed id set keeps the rows already drawn instead of blanking every row.
      placeholderData: keepPreviousData,
    })),
  })
  const series: Record<string, number[]> = {}
  for (const r of results) Object.assign(series, r.data?.series)
  const status: SparkStatus = results.some((r) => r.isError)
    ? 'error'
    : results.some((r) => r.isPending || r.isPlaceholderData)
      ? 'pending'
      : 'ready'
  return { series, status }
}
