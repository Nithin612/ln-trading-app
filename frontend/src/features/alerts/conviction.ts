/**
 * Conviction ranking for the Live-Signals "Opportunities" list.
 *
 * A v1 HEURISTIC — not a probability. It ranks active signals by how likely they are to work,
 * from what we can measure TODAY: the confluence confidence, a mild multi-factor bonus, and
 * penalties that encode the evidence we already have —
 *   • age decay: conviction is docked as a signal ages past 40% of its validity (up to −25 near
 *     expiry). ⚠ CORRECTED 2026-09-02 — this was documented as "the single most evidence-backed
 *     term", citing the signal-age study. It is NOT: `docs/analysis/signal-age-<date>.md`
 *     headlines "no stale-entry penalty visible yet" (fresh ≤40% = 61 trades at −₹58 avg / 57%
 *     win; stale >80% = 13 trades at +₹13 avg / 46% win). Age predicts WIN RATE mildly and ₹ not
 *     at all. The term is kept on its MECHANICAL rationale — a signal near expiry has less runway
 *     left to reach its target — not on a measured ₹ effect, and it is deliberately mild.
 *     The measured discriminator is DISPLACEMENT from entry, not age: at-entry fills (−0.02…
 *     +0.33R) = +₹9,830 / 55% win vs chased 0.33–1R = −₹12,789 / 22% (99 trades since 07-19).
 *     Displacement is surfaced per-row as the live chase guidance, and enforced by `chase_guard`
 *     on the order path — not folded into this score (ranking must not re-jitter every tick).
 *   • choppy regime: low Kaufman efficiency (`choppy`) → −10.
 * As the MCE slices mature (sector-RS, market-regime, liquidity, news) they become additional
 * terms here. Deliberately NOT a function of the live price — ranking must not re-jitter every
 * tick; live chase is shown per-row separately.
 */

import type { SignalOut } from "@/lib/api/signals";

import { pctElapsed } from "./alertPresentation";

const AGE_FREE_PCT = 40; // edge intact up to here (signal-age evidence)
const AGE_MAX_PENALTY = 25;
const CHOPPY_PENALTY = 10;
const FACTOR_BONUS_CAP = 4;
export const TOP_N = 5;

export interface Ranked {
  signal: SignalOut;
  score: number;
  isTop: boolean; // among the top-N conviction picks
}

function scoringFactorCount(signal: SignalOut): number {
  return Object.values(signal.factor_scores ?? {}).filter((f) => f.score !== 0).length;
}

/** v1 conviction score (higher = better). `now` injectable for deterministic tests. */
export function convictionScore(signal: SignalOut, now: number = Date.now()): number {
  let s = signal.confidence_pct; // 0..100 confluence base
  const pct = pctElapsed(signal, now);
  if (pct !== null && pct > AGE_FREE_PCT) {
    s -= Math.min(((pct - AGE_FREE_PCT) / (100 - AGE_FREE_PCT)) * AGE_MAX_PENALTY, AGE_MAX_PENALTY);
  }
  if (signal.choppy) s -= CHOPPY_PENALTY;
  s += Math.min(scoringFactorCount(signal), FACTOR_BONUS_CAP); // mild multi-factor reward
  return s;
}

function recencyThenConfidence(a: SignalOut, b: SignalOut): number {
  const ta = new Date(a.created_at).getTime();
  const tb = new Date(b.created_at).getTime();
  const byRecency = (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0);
  if (byRecency !== 0) return byRecency;
  if (b.confidence_pct !== a.confidence_pct) return b.confidence_pct - a.confidence_pct;
  return scoringFactorCount(b) - scoringFactorCount(a);
}

/**
 * The top-N by conviction (highlighted), then the REST ordered by recency → confidence → factor
 * count (the user's "recently generated + multi-factor confidence" rule). Returns one ordered
 * list with an `isTop` flag + the score, so the view renders top picks first then the rest.
 */
export function rankSignals(signals: SignalOut[], now: number = Date.now()): Ranked[] {
  const byScore = [...signals].sort((a, b) => {
    const d = convictionScore(b, now) - convictionScore(a, now);
    return d !== 0 ? d : recencyThenConfidence(a, b);
  });
  const top = byScore.slice(0, TOP_N);
  const topIds = new Set(top.map((s) => s.id));
  const rest = signals.filter((s) => !topIds.has(s.id)).sort(recencyThenConfidence);
  return [...top, ...rest].map((signal) => ({
    signal,
    score: convictionScore(signal, now),
    isTop: topIds.has(signal.id),
  }));
}
