/**
 * Option-chain ladder — calls left, strike centre, puts right (the layout
 * Indian brokers use, so muscle memory transfers).
 *
 * OI bars are scaled against the largest OI in the rendered window and drawn
 * with the neutral accent token, NOT the profit/loss tokens: open interest is
 * not a P&L, and reusing money colours for it would read as gain/loss. The
 * ATM row is marked with a text badge as well as a tint, so it survives a
 * colour-blind read (.claude/rules/ui.md: never colour alone).
 *
 * A null Greek renders as "—", never 0 — an unpriced leg must not look like a
 * zero-delta one.
 */

import { useMemo } from 'react'

import type { ChainLeg, OptionChain } from '@/lib/api/fo'
import { formatGreek, formatINR, formatInt, formatPct } from '@/lib/format'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'

interface LadderRow {
  strike: number
  strikeLabel: string
  ce: ChainLeg | undefined
  pe: ChainLeg | undefined
}

function buildRows(legs: ChainLeg[]): LadderRow[] {
  const byStrike = new Map<string, LadderRow>()
  for (const leg of legs) {
    const row = byStrike.get(leg.strike) ?? {
      strike: parseFloat(leg.strike),
      strikeLabel: leg.strike,
      ce: undefined,
      pe: undefined,
    }
    if (leg.option_type === 'CE') row.ce = leg
    else row.pe = leg
    byStrike.set(leg.strike, row)
  }
  return [...byStrike.values()].sort((a, b) => a.strike - b.strike)
}

function OiBar({ oi, maxOi, side }: { oi: number; maxOi: number; side: 'call' | 'put' }) {
  const pct = maxOi > 0 ? Math.max(2, Math.round((oi / maxOi) * 100)) : 0
  return (
    <span className="relative flex items-center justify-end gap-1" title={`OI ${formatInt(oi)}`}>
      <span
        aria-hidden="true"
        className="absolute inset-y-0.5 rounded-sm opacity-25"
        style={{
          width: `${pct}%`,
          background: 'var(--color-accent)',
          [side === 'call' ? 'right' : 'left']: 0,
        }}
      />
      <span className="relative tabular-nums">{formatInt(oi)}</span>
    </span>
  )
}

function GreekCells({ leg, showGreeks }: { leg: ChainLeg | undefined; showGreeks: boolean }) {
  if (!showGreeks) return null
  return (
    <>
      <TableCell numeric className="text-(--color-text-muted)">
        {leg?.gamma != null ? formatGreek(leg.gamma) : '—'}
      </TableCell>
      <TableCell numeric className="text-(--color-text-muted)">
        {leg?.vega != null ? formatGreek(leg.vega, 2) : '—'}
      </TableCell>
      <TableCell numeric className="text-(--color-text-muted)">
        {leg?.theta != null ? formatGreek(leg.theta, 2) : '—'}
      </TableCell>
    </>
  )
}

interface Props {
  chain: OptionChain
  showGreeks: boolean
}

export function ChainLadder({ chain, showGreeks }: Props) {
  const rows = useMemo(() => buildRows(chain.legs), [chain.legs])
  const maxOi = useMemo(
    () => rows.reduce((m, r) => Math.max(m, r.ce?.oi ?? 0, r.pe?.oi ?? 0), 0),
    [rows],
  )
  const atm = chain.atm_strike != null ? parseFloat(chain.atm_strike) : null
  // Greeks per side: OI, Vol, IV, Δ (+ Γ, V, Θ), LTP = 5 or 8 columns.
  const perSide = showGreeks ? 8 : 5

  return (
    <Table aria-label="Option chain ladder">
      <TableHeader>
        <TableRow>
          <TableHead numeric colSpan={perSide} className="text-center">
            Calls
          </TableHead>
          <TableHead className="text-center">Strike</TableHead>
          <TableHead numeric colSpan={perSide} className="text-center">
            Puts
          </TableHead>
        </TableRow>
        <TableRow>
          <TableHead numeric>OI</TableHead>
          <TableHead numeric>Vol</TableHead>
          <TableHead numeric>IV</TableHead>
          <TableHead numeric>Δ</TableHead>
          {showGreeks && (
            <>
              <TableHead numeric>Γ</TableHead>
              <TableHead numeric>V</TableHead>
              <TableHead numeric>Θ</TableHead>
            </>
          )}
          <TableHead numeric>LTP</TableHead>
          <TableHead className="text-center">—</TableHead>
          <TableHead numeric>LTP</TableHead>
          <TableHead numeric>Δ</TableHead>
          <TableHead numeric>IV</TableHead>
          {showGreeks && (
            <>
              <TableHead numeric>Γ</TableHead>
              <TableHead numeric>V</TableHead>
              <TableHead numeric>Θ</TableHead>
            </>
          )}
          <TableHead numeric>Vol</TableHead>
          <TableHead numeric>OI</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const isAtm = atm != null && r.strike === atm
          return (
            <TableRow
              key={r.strikeLabel}
              className={isAtm ? 'bg-(--color-surface-hover)' : undefined}
            >
              <TableCell numeric>
                {r.ce ? <OiBar oi={r.ce.oi} maxOi={maxOi} side="call" /> : '—'}
              </TableCell>
              <TableCell numeric className="text-(--color-text-muted)">
                {r.ce ? formatInt(r.ce.volume) : '—'}
              </TableCell>
              <TableCell numeric>
                {r.ce?.iv != null ? formatPct(r.ce.iv * 100, { signed: false }) : '—'}
              </TableCell>
              <TableCell numeric>
                {r.ce?.delta != null ? formatGreek(r.ce.delta) : '—'}
              </TableCell>
              <GreekCells leg={r.ce} showGreeks={showGreeks} />
              <TableCell numeric className="font-semibold">
                {r.ce?.ltp != null ? formatINR(parseFloat(r.ce.ltp)) : '—'}
              </TableCell>

              <TableCell className="text-center font-mono font-bold whitespace-nowrap">
                {formatINR(r.strike)}
                {isAtm && (
                  <span
                    className="ml-1 px-1 rounded text-[0.6rem] font-bold align-middle"
                    style={{
                      // Solid accent + its AA-tuned foreground (the same
                      // pairing buttons/avatars use across all 5 themes).
                      background: 'var(--color-accent)',
                      color: 'var(--color-primary-foreground)',
                    }}
                  >
                    ATM
                  </span>
                )}
              </TableCell>

              <TableCell numeric className="font-semibold">
                {r.pe?.ltp != null ? formatINR(parseFloat(r.pe.ltp)) : '—'}
              </TableCell>
              <TableCell numeric>
                {r.pe?.delta != null ? formatGreek(r.pe.delta) : '—'}
              </TableCell>
              <TableCell numeric>
                {r.pe?.iv != null ? formatPct(r.pe.iv * 100, { signed: false }) : '—'}
              </TableCell>
              <GreekCells leg={r.pe} showGreeks={showGreeks} />
              <TableCell numeric className="text-(--color-text-muted)">
                {r.pe ? formatInt(r.pe.volume) : '—'}
              </TableCell>
              <TableCell numeric>
                {r.pe ? <OiBar oi={r.pe.oi} maxOi={maxOi} side="put" /> : '—'}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
