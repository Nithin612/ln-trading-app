import { Link } from 'react-router-dom'

import { useAuth } from '@/hooks/useAuth'
import type { StockEligibility } from '@/lib/api/stocks'
import { formatInt, formatIstDate } from '@/lib/format'

/**
 * V5 / A2 tier 3 — why this stock does or does not produce signals.
 *
 * ⭐ **Three independent reasons exist and only the first was visible anywhere:**
 *   1. the universe rule did not admit it;
 *   2. the CA detector quarantined it — which drops it from every suggestion **even when
 *      it is perfectly tradeable** (measured: 5 of the 7 quarantined names are ACTIVE);
 *   3. it has too few daily bars, so the scan never SCORES it rather than scoring it and
 *      declining. V1 measured **184 of 2,286 priced names** dying there, with the whole
 *      drop being attributed to the confluence gate.
 *
 * ⚠ Every verdict here comes from the backend (§28 — never let the frontend derive
 * universe state), computed by the same `stock_resolve` code the search surface uses.
 */
export function EligibilityPanel({ eligibility }: { eligibility: StockEligibility }) {
  const { isAdmin } = useAuth()
  const { coverage } = eligibility
  const ok = eligibility.scannable

  return (
    <section
      className="rounded-lg border border-(--color-border) bg-(--color-surface-2) px-4 py-3"
      aria-label="Signal eligibility"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-(--color-text-secondary)">
          Signal eligibility
        </h2>
        <span
          className="rounded px-2 py-0.5 text-xs font-semibold"
          /*
            ⛔ NOT `--color-bull` on `--color-profit-bg`. Two reasons, and the second is
            the one that matters. (a) Measured 3.32:1 in daybreak — already on the
            recorded-debt list, so adding a consumer of a known-failing pair is exactly
            what that list warns about. (b) SEMANTICS: those tokens mean *money gained*
            (§5.1 scopes them to `value >= 0`), and "this stock is scanned" is a
            CAPABILITY, not a gain — painted green directly beneath a live LTP that is
            also green, it tells a trader the stock is UP (ui-reviewer #4, #8).
            `--color-text` on the tint measures 12.15–15.74 in all five themes; the
            semantic colour survives on the border only.
          */
          style={
            ok
              ? {
                  background: 'var(--color-profit-bg)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-bull)',
                }
              : {
                  background: 'var(--color-warning-bg)',
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-warning)',
                }
          }
        >
          {ok ? '✓ Scanned for signals' : '⊘ Not scanned'}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
        <Row
          label="In tradeable universe"
          ok={eligibility.in_universe}
          okLabel="yes"
          badLabel="excluded"
        />
        <Row
          label="CA quarantine"
          ok={!eligibility.ca_quarantined}
          okLabel="clear"
          badLabel="quarantined"
        />
        {/*
          ⚠ The count travels with its THRESHOLD, never alone — a bare "12 bars" means
          nothing without the 50 it is being measured against (A24 / H11).
        */}
        <div>
          <dt className="text-(--color-text-secondary)">Daily history</dt>
          <dd className="font-mono tabular-nums">
            {formatInt(coverage.daily_bars)} / {formatInt(coverage.min_bars_to_score)} bars
            {!coverage.enough_history && (
              <span className="ml-1 text-(--color-warning)">
                — {formatInt(coverage.shortfall)} more needed
              </span>
            )}
            {/*
              ⚠ A24 — the count carries its AS-OF as well as its threshold. Without it,
              "38 more needed" quietly asserts that 38 more sessions WILL arrive, which is
              false for a stale or delisted name whose count is frozen. `latest_bar` was
              already in the payload and rendered nowhere (ui-reviewer #5).
            */}
            {coverage.latest_bar && (
              <span className="ml-1 font-sans text-xs text-(--color-text-secondary)">
                · latest {formatIstDate(coverage.latest_bar)}
              </span>
            )}
          </dd>
        </div>
      </dl>

      {!coverage.enough_history && (
        <p className="mt-3 text-sm text-(--color-text-secondary)">
          {/*
            ⭐ The sentence that had no home before. A thin name is not REJECTED by the
            confluence gate — it is never examined, so "no signals" here means something
            entirely different from "the engine looked and declined".
          */}
          With fewer than {coverage.min_bars_to_score} completed daily candles the scan
          skips this name <strong>before scoring it</strong> — so the absence of signals
          says nothing about the setup, only about the history.
        </p>
      )}

      {eligibility.exclusion_reasons.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-(--color-text-secondary)">
          {eligibility.exclusion_reasons.map((r) => (
            <li key={r}>— {r}</li>
          ))}
        </ul>
      )}

      {/*
        ⛔ Gated on the BOOLEAN, not on a substring of the backend's prose. The first
        version tested `r.includes('CA Quarantine')` while the authoritative
        `ca_quarantined` flag was in scope, so a copy edit on the server would have
        silently removed the link (ui-reviewer, closing note).
        ⚠ And only for an ADMIN: `/admin/ca-quarantine` is `RequireAdmin`, so showing it
        to everyone bounced a non-admin to `/` — offering a door that is locked.
        ⛔ NOT `--color-accent` for the link: measured 2.88:1 on this surface in SLATE,
        the DEFAULT theme. The underline carries "link"; the colour does not have to.
      */}
      {eligibility.ca_quarantined && isAdmin && (
        <p className="mt-2 text-sm">
          <Link
            to="/admin/ca-quarantine"
            className="text-(--color-text) underline underline-offset-2 hover:text-(--color-accent-hover) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--color-bg)"
          >
            Review the CA quarantine queue
          </Link>
        </p>
      )}

      {/*
        ⚠ A24 — a reason derived from a recorded evaluation carries ITS DATE, so it is
        never read as a timeless fact. When the rule term could not be justified from a
        record, no date is shown and none is implied.
      */}
      {eligibility.reason_as_of && (
        <p className="mt-2 text-xs text-(--color-text-secondary)">
          Universe verdict as evaluated {formatIstDate(eligibility.reason_as_of)}.
        </p>
      )}
    </section>
  )
}

function Row({
  label,
  ok,
  okLabel,
  badLabel,
}: {
  label: string
  ok: boolean
  okLabel: string
  badLabel: string
}) {
  return (
    <div>
      <dt className="text-(--color-text-secondary)">{label}</dt>
      {/*
        ⛔ BOTH labels are explicit, and that is the fix for a real bug. The first version
        took one `invertedLabel` for the true branch and hardcoded "⊘ no" for the false
        one — so a QUARANTINED stock rendered "CA quarantine ⊘ no", which reads as *not
        quarantined*: the exact opposite of the truth, in the one case this panel exists
        to explain. Only the amber tint hinted otherwise, and colour is never the carrier
        (ui-reviewer #1). The test missed it because it asserted the prose below, not the
        row.
        ⚠ Glyph + text, never colour alone (ui.md).
      */}
      <dd style={{ color: ok ? 'var(--color-text)' : 'var(--color-warning)' }}>
        {ok ? `✓ ${okLabel}` : `⊘ ${badLabel}`}
      </dd>
    </div>
  )
}
