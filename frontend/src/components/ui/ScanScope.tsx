import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import { signalsApi, type FunnelOut } from '@/lib/api/signals'
import { formatInt, formatIstDate, formatWholePct } from '@/lib/format'

/**
 * V1 — what the scan looked at, rendered under an empty signal list.
 *
 * ⭐ THE PROBLEM IT SOLVES: "Nothing meets the confluence gate right now" is
 * indistinguishable from "the scan covered 12 stocks because the universe collapsed".
 * The universe outage of 2026-09-07 produced exactly the second and displayed exactly
 * the first for days. An empty state has no stock in context, so it cannot name a
 * per-stock cause — the honest alternative is to state the SCOPE.
 *
 * ⭐⭐ It doubles as a breadth detector. `priced_today` against its own 30-day median
 * surfaces a coverage collapse the 6.8.6 feed alarm structurally cannot see, because
 * that alarm asserts RECENCY (are the newest bars fresh) and not COVERAGE (how many
 * names have them).
 *
 * A24: every count here is a MEASUREMENT, not a projection, so exact integers are the
 * honest precision. The one derived figure — the breadth shortfall — is rendered with
 * the median it is a shortfall against, in the same element, and rounded to whole
 * percent because a 30-day median of daily counts supports no more than that.
 *
 * ⛔ NOT rendered on the live-alert empty state. An absent alert means no level was
 * touched; the funnel says nothing about that and would be a confident-looking
 * non-answer. It belongs only where the question is "why is the SIGNAL list empty".
 */

/*
 * ⚠ No `role="status"` on the alarm line, deliberately. The component returns null until
 * its query resolves, so a live region would be inserted ALREADY POPULATED — which screen
 * readers do not reliably announce. A live region that silently never fires is worse than
 * none, because we would believe the announcement happens. The ⚠ glyph and the prose are
 * reachable by ordinary navigation, and this sits inside an empty state the user is
 * already reading.
 *
 * ⚠ The stranded-position banner keeps `role="alert"` on a DIFFERENT ground — not mount
 * timing (an earlier version of this comment claimed that, and it is false: that banner
 * also renders only after its positions query resolves). The real distinction is that
 * `alert` is assertive and IS announced on insertion by the major screen readers, whereas
 * polite `status` insertion is the unreliable case — and the banner is an actionable
 * safety condition, while this is supporting context.
 */

/*
 * A shortfall smaller than this is ordinary day-to-day variation, not a collapse.
 *
 * ⚠ WHERE 20 COMES FROM, since this file's whole thesis is that a figure without its
 * reference is decoration: it is a CHOSEN operating point, not a measured one. Observed
 * day-to-day coverage sits within a couple of percent of the median (measured 2026-09-14:
 * 2,286 priced against a 2,250 median = −1.6%, i.e. ABOVE it), while the failure this
 * exists to catch took coverage to a small fraction of normal. 20% is an order of
 * magnitude above the noise and an order of magnitude below the event, so nothing
 * currently distinguishes 15 from 25 and no evidence is claimed for the exact number.
 * ⛔ Do not present it as a validated threshold.
 */
const SHORTFALL_ALARM_PCT = 20

function Rung({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="font-mono tabular-nums text-(--color-text)">{value}</span>
      {/*
        ⛔ NOT `--color-text-muted`: measured against `--color-surface-2` it is 2.34:1 in
        daybreak, 3.30 midnight, 3.52 slate, 3.89 carbon — below the 4.5 AA floor in FOUR
        of five themes. And the label is not decoration: without it "3,395 → 2,291" says
        nothing. `--color-text-secondary` measures 6.13–8.89 across all five.
        (The → separators keep the muted token — they are `aria-hidden` decoration.)
      */}
      <span className="text-(--color-text-secondary)">{label}</span>
    </span>
  )
}

export function ScanScopeBody({ funnel }: { funnel: FunnelOut }) {
  const shortfall = funnel.breadth_shortfall_pct
  const median = funnel.breadth_median
  const alarm = median != null && shortfall != null && shortfall >= SHORTFALL_ALARM_PCT

  /*
    ⭐ F1 — THE ATTRIBUTION LIVES HERE, NOT IN THE CALLER. `signals_live` counts
    `status='active' AND quarantined_at IS NULL` with NO filter applied, so if it is
    positive while the caller is rendering an empty list, the engine DID commit signals
    and something in front of the user removed them. That is a filter, not a scan-scope
    problem, and saying "here is what the scan covered" would blame the wrong thing.

    ⚠ An earlier cut put this decision in `DashboardPage` and got it wrong: the predicate
    read the query response, whose key carries `direction`, `classification` and
    `minConfidence` — all SERVER-side. Setting min-confidence to 90 emptied the response
    and the page blamed the scan's coverage for a slider. Deciding from `signals_live`
    needs no knowledge of any caller's filter state and cannot drift as filters are added.
  */
  if (funnel.signals_live > 0) {
    return (
      <p className="text-xs text-(--color-text-secondary)">
        {`The engine has ${formatInt(funnel.signals_live)} active signal${funnel.signals_live === 1 ? '' : 's'} right now — `}
        the filters on this view are hiding {funnel.signals_live === 1 ? 'it' : 'them'}.
        Clear them to see the full list.
      </p>
    )
  }

  // A24: the priced count is meaningless without the session it refers to, and this is
  // the failure mode the component exists for — before the day's ingest runs, the latest
  // session IS the previous one, so an unlabelled "priced today" is wrong in exactly the
  // direction of the outage we are trying to catch.
  const pricedLabel = funnel.session
    ? `priced on ${formatIstDate(funnel.session)}`
    : 'priced (no session on record)'

  return (
    <div className="flex flex-col items-center gap-2 text-xs">
      <div className="flex flex-wrap items-baseline justify-center gap-x-2 gap-y-1">
        <Rung label="known" value={formatInt(funnel.known)} />
        <span aria-hidden="true" className="text-(--color-text-secondary)">→</span>
        <Rung label="in universe" value={formatInt(funnel.in_universe)} />
        <span aria-hidden="true" className="text-(--color-text-secondary)">→</span>
        <Rung label={pricedLabel} value={formatInt(funnel.priced_today)} />
        <span aria-hidden="true" className="text-(--color-text-secondary)">→</span>
        <Rung label="live signals" value={formatInt(funnel.signals_live)} />
      </div>

      {/*
        The scoring stage is ABSENT, not zero — the scorer does not persist how many
        panels it evaluated. Saying so is the A24 "not assessable" rendering; printing a
        0 would assert that nothing was scored, which we do not know.
      */}
      {!funnel.assessed_available && (
        <p className="text-(--color-text-secondary)">
          How many of those were scored is not recorded, so the drop from priced to
          signals cannot be attributed here.
        </p>
      )}

      {/*
        Three branches, not two. The `median == null` case used to fall through BOTH and
        render the count with no reference and no statement that the reference was
        missing — the same A24 rule this file applies correctly to the scored stage,
        omitted one element below it.
      */}
      {alarm ? (
        <p
          className="rounded border px-2 py-1"
          style={{
            background: 'var(--color-warning-bg)',
            borderColor: 'var(--color-warning)',
            color: 'var(--color-warning)',
          }}
        >
          {`⚠ Coverage is ${formatWholePct(shortfall!)} below the ${formatInt(median!)}-name `}
          median of the last 30 sessions — treat this empty list as a data problem until
          the gap is explained.
        </p>
      ) : median != null ? (
        <p className="text-(--color-text-secondary)">
          {`Typical coverage over the last 30 sessions is ${formatInt(median)} names.`}
        </p>
      ) : (
        <p className="text-(--color-text-secondary)">
          There is no 30-session coverage reference yet, so this count cannot be judged
          high or low.
        </p>
      )}
    </div>
  )
}

/**
 * Self-fetching wrapper for use inside an empty state. Renders NOTHING while loading or
 * on failure: this is supporting context under a message that already stands on its own,
 * and a spinner or an error box there would make a diagnostic aid look like the subject.
 */
export function ScanScope() {
  const token = useAuthStore((s) => s.accessToken)
  const { data } = useQuery({
    queryKey: ['signals', 'funnel'],
    queryFn: () => signalsApi.getFunnel(token!),
    enabled: !!token,
    staleTime: 60_000,
  })

  if (!data) return null
  return (
    <div className="mt-4 border-t border-(--color-border) pt-3 max-w-md">
      <ScanScopeBody funnel={data} />
    </div>
  )
}
