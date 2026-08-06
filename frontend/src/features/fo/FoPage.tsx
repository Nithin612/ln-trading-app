/**
 * F&O page (Phase 5 slice 5.2) — the UI for the whole Phase-4 backend:
 * analytics strip, option-selling candidates, and the chain ladder.
 *
 * The pickers are driven by what has actually been RECORDED (/fo/underlyings,
 * /fo/expiries) rather than a hardcoded symbol list, and the provenance line
 * states the source and the day everything was computed from. That matters
 * here more than on most pages: an EOD chain rendered without a date reads as
 * live, and Greeks priced off a stale forward would look tradeable.
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Layers } from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import { foApi } from '@/lib/api/fo'
import { ApiError } from '@/lib/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { SimpleSelect } from '@/components/ui/simple-select'
import { formatINR } from '@/lib/format'
import { FoAnalyticsHeader } from './FoAnalyticsHeader'
import { ChainLadder } from './ChainLadder'
import { StrategyCards } from './StrategyCards'

/** ±N strikes around ATM. The ladder is ~2N rows, so it stays unvirtualized. */
const STRIKE_WINDOWS = ['10', '15', '20', '30'] as const
const DEFAULT_STRIKE_WINDOW = '15'

const SOURCE_OPTIONS = [
  { value: 'eod', label: 'EOD (bhavcopy close)' },
  { value: 'intraday', label: 'Intraday snapshot' },
]

export function FoPage() {
  const { accessToken } = useAuth()
  const token = accessToken ?? ''
  const enabled = !!accessToken

  const [symbol, setSymbol] = useState('NIFTY')
  // The user's PICK, which may not exist for the current underlying. The
  // expiry actually queried is derived below — see `expiry`.
  const [pickedExpiry, setPickedExpiry] = useState('')
  const [source, setSource] = useState<'eod' | 'intraday'>('eod')
  const [strikes, setStrikes] = useState<string>(DEFAULT_STRIKE_WINDOW)
  const [showGreeks, setShowGreeks] = useState(true)

  const underlyings = useQuery({
    queryKey: ['fo-underlyings'],
    queryFn: () => foApi.getUnderlyings(token),
    enabled,
    staleTime: 5 * 60_000,
  })

  const expiries = useQuery({
    queryKey: ['fo-expiries', symbol],
    queryFn: () => foApi.getExpiries(symbol, token),
    enabled: enabled && !!symbol,
    staleTime: 5 * 60_000,
  })

  const expiryList = useMemo(() => expiries.data?.expiries ?? [], [expiries.data])

  // DERIVED, not synced: the nearest open expiry unless the user's pick is
  // still valid for this underlying. Deriving (rather than mirroring the list
  // into state via an effect) means changing the symbol can never leave a
  // stale expiry selected — which would query a chain that cannot exist — and
  // avoids the cascading render an effect+setState would cause.
  const expiry = useMemo(() => {
    if (pickedExpiry && expiryList.some((e) => e.expiry === pickedExpiry)) return pickedExpiry
    return expiryList[0]?.expiry ?? ''
  }, [pickedExpiry, expiryList])

  const chainReady = enabled && !!symbol && !!expiry

  const analytics = useQuery({
    queryKey: ['fo-analytics', symbol, expiry, source],
    queryFn: () => foApi.getAnalytics(symbol, expiry, token, { source }),
    enabled: chainReady,
    staleTime: 60_000,
  })

  const ivRank = useQuery({
    queryKey: ['fo-iv-rank', symbol],
    queryFn: () => foApi.getIvRank(symbol, token),
    enabled: enabled && !!symbol,
    staleTime: 5 * 60_000,
    // 404 = not enough recorded option history; that is an empty state, not a
    // failure worth retrying.
    retry: false,
  })

  const chain = useQuery({
    queryKey: ['fo-chain', symbol, expiry, source, strikes, showGreeks],
    queryFn: () =>
      foApi.getChain(symbol, expiry, token, {
        source,
        strikes: Number(strikes),
        greeks: showGreeks,
      }),
    enabled: chainReady,
    staleTime: 60_000,
  })

  const suggestions = useQuery({
    queryKey: ['fo-suggestions', symbol],
    queryFn: () => foApi.getSuggestions(symbol, token),
    enabled: enabled && !!symbol,
    staleTime: 60_000,
  })

  const symbolOptions = useMemo(
    () => (underlyings.data?.symbols ?? []).map((s) => ({ value: s, label: s })),
    [underlyings.data],
  )
  const expiryOptions = useMemo(
    () => expiryList.map((e) => ({ value: e.expiry, label: `${e.expiry} · ${e.dte}d` })),
    [expiryList],
  )

  const ivRankMissing = ivRank.isError && (ivRank.error as ApiError)?.status === 404
  const chainData = chain.data

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="F&O"
        subtitle="Chain analytics, per-strike IV & Greeks, and defined-risk option-selling candidates."
      />

      {/* Pickers */}
      <div className="flex flex-wrap items-end gap-3 p-3 rounded-lg bg-(--color-surface-2) border border-(--color-border)">
        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted)">
            Underlying
          </span>
          <SimpleSelect
            value={symbol}
            onChange={setSymbol}
            options={symbolOptions.length > 0 ? symbolOptions : [{ value: symbol, label: symbol }]}
            size="sm"
            className="min-w-36"
            aria-label="Underlying"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted)">
            Expiry
          </span>
          <SimpleSelect
            value={expiry}
            onChange={setPickedExpiry}
            options={expiryOptions}
            placeholder={expiries.isLoading ? 'Loading…' : 'No open expiry'}
            disabled={expiryOptions.length === 0}
            size="sm"
            className="min-w-44"
            aria-label="Expiry"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted)">
            Source
          </span>
          <SimpleSelect
            value={source}
            onChange={(v) => setSource(v as 'eod' | 'intraday')}
            options={SOURCE_OPTIONS}
            size="sm"
            className="min-w-48"
            aria-label="Chain source"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wider text-(--color-text-muted)">
            Strikes (±)
          </span>
          <SimpleSelect
            value={strikes}
            onChange={setStrikes}
            options={STRIKE_WINDOWS.map((n) => ({ value: n, label: `± ${n}` }))}
            size="sm"
            className="min-w-24"
            aria-label="Strike window"
          />
        </label>

        <div className="flex items-center gap-2 pb-1.5">
          <Checkbox id="fo-show-greeks" checked={showGreeks} onCheckedChange={setShowGreeks} />
          <label
            htmlFor="fo-show-greeks"
            className="text-xs text-(--color-text) select-none cursor-pointer"
          >
            Greeks (Γ V Θ)
          </label>
        </div>
      </div>

      <FoAnalyticsHeader
        analytics={analytics.data}
        ivRank={ivRank.data}
        ivRankMissing={ivRankMissing}
        isLoading={analytics.isLoading}
        isError={analytics.isError}
        onRetry={() => void analytics.refetch()}
      />

      {/* Option-selling candidates */}
      <section className="rounded-lg bg-(--color-surface-2) border border-(--color-border)">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center gap-2">
          <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            <Layers size={16} /> Option-selling candidates
          </span>
        </div>
        <div className="p-4">
          <StrategyCards
            symbol={symbol}
            candidates={suggestions.data?.candidates}
            isLoading={suggestions.isLoading}
            isError={suggestions.isError}
            onRetry={() => void suggestions.refetch()}
          />
        </div>
      </section>

      {/* Chain ladder */}
      <section className="rounded-lg bg-(--color-surface-2) border border-(--color-border)">
        <div className="px-4 py-3 border-b border-(--color-border) flex items-center justify-between gap-2 flex-wrap">
          <span className="text-xs font-semibold uppercase tracking-wide text-(--color-text-muted)">
            Chain ladder
          </span>
          {/* Provenance: never let an EOD chain read as live. */}
          <span className="text-[0.7rem] text-(--color-text-muted) tabular-nums">
            {chainData?.as_of
              ? `${source === 'eod' ? 'EOD close' : 'snapshot'} ${chainData.as_of}`
              : source === 'eod'
                ? 'EOD close'
                : 'intraday snapshot'}
            {chainData?.fut_price &&
              ` · Greeks off ${
                chainData.forward_source === 'fut_carry_implied'
                  ? 'implied forward'
                  : 'future'
              } ${formatINR(parseFloat(chainData.fut_price))}${
                chainData.dte != null ? ` · ${chainData.dte}d` : ''
              }`}
          </span>
        </div>

        {chain.isLoading && (
          <div className="p-4 space-y-2" aria-label="loading option chain">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
          </div>
        )}

        {chain.isError && (
          <div className="p-4 text-sm text-(--color-text-muted)">
            Could not load the {symbol} chain.{' '}
            <Button variant="link" size="sm" onClick={() => void chain.refetch()}>
              Retry
            </Button>
          </div>
        )}

        {!chain.isLoading && !chain.isError && chainData && chainData.legs.length === 0 && (
          <EmptyState
            title="No chain recorded"
            description={
              source === 'intraday'
                ? 'No intraday chain snapshot for this expiry yet — the recorder runs on a 1-minute beat during market hours. Try the EOD source.'
                : 'No F&O bhavcopy rows for this underlying and expiry.'
            }
          />
        )}

        {!chain.isLoading && !chain.isError && chainData && chainData.legs.length > 0 && (
          <>
            {showGreeks && chainData.fut_price == null && (
              <p className="px-4 pt-3 text-xs text-(--color-warning)">
                {source === 'intraday'
                  ? 'Greeks unavailable — the futures close for this snapshot’s day has not been recorded yet (EOD lands ~18:45 IST). Pricing live premiums against yesterday’s forward would skew every IV and delta, so it stands down. OI, volume and LTP are unaffected.'
                  : 'Greeks unavailable — no future expiring on or after this expiry was recorded for that day, so there is no Black-76 forward to price against. OI, volume and LTP are unaffected.'}
              </p>
            )}
            {showGreeks && chainData.forward_source === 'fut_carry_implied' && (
              <p className="px-4 pt-3 text-xs text-(--color-text-muted)">
                This expiry has no future of its own (index options are weekly, futures monthly),
                so the forward is spot grown by the carry implied by the nearest future.
              </p>
            )}
            <ChainLadder chain={chainData} showGreeks={showGreeks} />
          </>
        )}
      </section>
    </div>
  )
}
