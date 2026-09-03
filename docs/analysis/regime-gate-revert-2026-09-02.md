# Regime gate — REVERT to shadow (decision record, 2026-09-02)

_Decision: **revert `regime_gate_mode` from `active` to `shadow`.** User sign-off given 2026-09-02.
Reversible. The frozen confluence engine is untouched either way — this is an overlay mode flip._

## What was decided on 2026-08-14, and on what evidence

The §8 walk-forward established that committed entries in the **transitional ADX band (20–25)** were
net-negative, and that skipping them improved win rate, Sharpe and max drawdown out-of-sample. The
gate was flipped **shadow → active** on 2026-08-14 with the live banner reading **✅ READY on 44
resolved suppressed trades**, all three §8 metrics improving.

The flip shipped with a **pre-registered revert condition** (`phases/phase-06-plan.md`, follow-up 1):

> _"…watch the daily shadow banner (`regime-gate-shadow-<date>.md`) — if it diverges (⏳ NOT READY), revert."_

## That condition has fired, and stayed fired

The banner turned **NOT READY** by 2026-08-21 and has stayed NOT READY on every report day since.
The suppressed set — the cohort the gate removes from the book — is **net-POSITIVE on the live tape**:

| report | suppressed signals | decided | win% | Sharpe | mean expR |
|---|--:|--:|--:|--:|--:|
| 2026-08-21 | 147 | 54 | 35% | +0.064 | **+0.150** |
| 2026-08-24 | 148 | 55 | 35% | +0.055 | **+0.130** |
| 2026-08-25 | 152 | 58 | 34% | +0.047 | **+0.108** |
| 2026-08-26 | 156 | 61 | 36% | +0.059 | **+0.134** |
| 2026-08-27 | 157 | 62 | 37% | +0.070 | **+0.156** |
| 2026-08-31 | 187 | 84 | 36% | +0.043 | **+0.088** |
| 2026-09-01 | 192 | 88 | 36% | +0.044 | **+0.090** |

**Seven consecutive observations, sign never once negative, sample grown 54 → 88.** This is not a
one-day wobble.

## All three §8 metrics that justified the flip have inverted

From `regime-gate-shadow-2026-09-01.md`:

| variant | signals | decided | win% | Sharpe | maxDD R | total-R | mean expR |
|---|--:|--:|--:|--:|--:|--:|--:|
| baseline (ungated) | 449 | 234 | 32% | −0.005 | 21.4 | **−2.0** | −0.009 |
| **gated (kept — what we trade)** | 257 | 146 | **30%** | **−0.041** | **34.5** | **−10.0** | **−0.068** |
| **killed (suppressed)** | 192 | 88 | **36%** | **+0.044** | **11.2** | **+7.9** | **+0.090** |

Win rate, Sharpe and max drawdown are each **better in the set the gate throws away**. Gating moves
total-R from −2.0R (ungated) to −10.0R: the gate **subtracts ~8R** by removing a +7.9R cohort. The
backtest finding is not reproducing forward.

## The bar was not marginal — it was cleared 4.4×

The project's pre-registered promotion/revert bar is **20 resolved trades** in the would-block set
(printed in every sidecar banner). We are at **88**. The banner's own words: _"the real trigger is
the count, not the date"_ — so the 2026-09-15 calendar checkpoint was a convenience, not the gate.

## The gate was genuinely enforcing (this is not a phantom finding)

Verified against the dev DB, not the config (`.env` is hook-protected):

```sql
SELECT count(*) FROM positions p JOIN signals sg ON sg.id = p.signal_id
WHERE sg.regime LIKE 'transitional%' AND p.opened_at >= '2026-08-14';
-- 0 rows
```

**Zero transitional-regime positions opened since the flip.** The gate was blocking as designed, and
`settings.regime_gate_mode` read `'active'` at runtime.

Evidence continued to accrue while the gate was active because the **signal-outcome recorder tracks
every committed signal against the tape whether or not we traded it** — suppression removes the
trade, not the measurement. That is why `decided` kept growing 54 → 88 post-flip.

## Cost while it was on

Beyond the R arithmetic above, the gate was suppressing **37 of the 204** currently-active,
non-shadow, ≥70%-confidence signals — about a fifth of the visible inventory, and per this evidence
the better-performing fifth. This compounded a separate display defect: the overlays gate the
**order path** (`api/v1/trading.py`) and not the **display path** (`api/v1/signals.py`), so those 37
rows still render with a Buy button that 409s on click.

## Why this happened (the methodological lesson)

A gate promoted on **44** observations was refuted by **88**. This is exactly the failure mode the
2026-08-29 reading flagged — Aronson's data-mining bias and López de Prado's deflated Sharpe: an
in-sample walk-forward result plus a thin forward window is not enough to move the money path.

**Standing rule reinforced:** a shadow→active flip needs its pre-registered count met *and* a
multiple-testing-aware bar (the #1 item in the post-watch-mode research queue), not just a
favourable sign at the moment someone looks.

## Actions

1. **`REGIME_GATE_MODE=shadow`** in `.env` + backend & worker restart. (User-run: the file is
   hook-protected.) Revert path is the same flip in reverse.
2. Gate-mode variables are now documented in `.env.example` (they were undocumented).
3. **Follow-up doc bug:** `regime-gate-shadow-*.md` still opens with _"SHADOW: nothing is
   suppressed"_ — untrue from 2026-08-14 to 2026-09-02. The preamble in
   `app/services/regime_gate_shadow.py` must state the live mode instead of hardcoding "shadow".
4. The transitional band stays **measured, not traded-against**. Re-promotion requires a fresh
   forward window under the deflated-Sharpe bar, not a re-reading of the same §8 backtest.

## What this does NOT change

- The **diversity gate stays ACTIVE** — its evidence is intact (flagged −₹6,093 over 9 vs passed
  +₹3,880 over 60; zero single-factor signals in the current open book).
- No other gate mode moves. `chase` (4/20), `sl_atr` (17/20), `liquidity` (19/20, already ruled
  don't-flip), `circuit` (0/20), `sector_rs` (do-not-flip) all stay shadow.
- The frozen engine, the §8 corpus, and the paper clock are untouched. Reverting a gate to shadow
  restores the ungated population; it does not reset the clock.
