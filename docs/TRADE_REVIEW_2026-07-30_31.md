# Two-Day Trade Review & Decision Log — 2026-07-30 / 07-31

**Purpose.** A clinical, evidence-based record of every paper trade taken on
2026-07-30 and 2026-07-31 (the first two days on the *fixed* stop-loss / monitor
system), all findings (good and bad), the options we weighed, and what we chose.
This is the **baseline**. After we fix today's issues and merge, we trade
**Mon 2026-08-03 and Tue 2026-08-04**, run the *same* analysis, and compare
against this document to decide what worked, what didn't, and what to improve.

Written 2026-07-31 ~17:30 IST (post-close). Author: review with Claude.

---

## 0. Data-integrity caveats (read first — the numbers depend on these)

1. **The app's stored `unrealized_pnl` was STALE.** The Kite tick feed died ~09:48
   IST on 07-31 (laptop suspend + network change) and the monitor stopped updating
   marks, so the Positions screen froze on morning values. Several "green"
   positions there were actually **red** at the close. **All P&L below is
   recomputed from the real 15:29 tape, not the stored field.**
2. **07-31 intraday had holes** (302 / 247 of ~375 one-minute bars for the sampled
   names) from the tick outage. So **MFE/MAE are lower bounds** — true adverse
   excursions could be slightly worse. The **15:29 CLOSE prices are reliable.**
3. **07-31 daily (1d) EOD bar not yet ingested** (EOD ~18:40). The 07-31 "close"
   used here is the 15:29 one-minute close.
4. Some *earlier* trades (e.g., 07-27 LENSKART) were **corrupt** (closed on a
   stale/pre-open price that never traded) — the pre-open monitor bug, now fixed
   and flagged by the shadow comparator's off-tape detection. None of the 07-30/31
   trades are off-tape.

---

## 1. The trades (9 total: 5 opened 07-30, 4 opened 07-31; 1 closed)

All P&L **gross**, at the 07-31 15:29 close, unless marked realised.

| Stock | Side | Qty | Fill | 07-31 close | **P&L** | MFE | MAE | Peak (R) | Entry vs signal | State |
|---|---|---|---|---|---|---|---|---|---|---|
| PNCINFRA | LONG | 167 | 239.75 | 246.47 | **+1,122** | +₹1,471 | −₹244 | 0.66R | −1.54 (chased) | OPEN |
| GRPLTD | LONG | 16 | 2054.70 | 2118.00 | **+1,013** | +₹1,013 | −₹171 | 0.54R | +5.70 (good) | OPEN |
| FMGOETZE | SHORT | 69 | 476.55 | 472.50 | **+279** | +₹279 | −₹169 | 0.15R | +1.70 (good) | OPEN |
| JKPAPER | LONG | 83 | 388.05 | 390.00 | **+162** | +₹328 | −₹876 | 0.17R | +1.25 (good) | OPEN |
| SCHAEFFLER | SHORT | 11 | 4060.20 | 4078.90 | **−206** | +₹365 | −₹438 | 0.21R | +20.10 (good) | OPEN |
| FOSECOIND | SHORT | 5 | 5010.00 | 5110.50 | **−502** | +₹240 | −₹1,598 | 0.12R | −22.00 (chased) | OPEN |
| HINDCOPPER | SHORT | 87 | 486.10 | 492.90 | **−592** | +₹748 | −₹1,122 | 0.33R | −3.15 (chased) | OPEN |
| COLPAL | LONG | 13 | 2120.00 | 2073.00 | **−611** | −₹16 | −₹926 | −0.01R | −12.90 (chased) | OPEN |
| LENSKART | SHORT | 547 | 562.10 | *closed 07-30 09:58* | **−683** (realised) | +₹1,942 → gave it all back | — | ~0R | +2.75 | closed |

**Net: open gross MTM ≈ +₹666; incl. LENSKART realised −₹683 → ~flat (≈ −₹20 MTM;
≈ −₹270 if everything were closed now, after exit charges).**
Two days, nine trades, **breakeven.**

*Entry-vs-signal:* +ve = entered better than the signal level; −ve = chased worse.
*Peak (R):* best favourable excursion in initial-risk multiples.

### The signals behind them (why / when / conviction)

| Stock | Signal (factors) | Class | Conf | Generated | Valid until | Age at entry |
|---|---|---|---|---|---|---|
| PNCINFRA | Morning Star, Multibagger EMA, Sr Zone | positional | 75% | 07-24 19:25 | 09-04 | 7d |
| GRPLTD | Bullish Engulfing, Sr Zone, Multibagger EMA | positional | 71% | 07-30 19:15 | 09-10 | fresh (next am) |
| FMGOETZE | Bearish Engulfing, Sr Zone, MACD Cross | swing | 72% | 07-29 19:33 | 08-05 | 2d |
| JKPAPER | Sr Zone, Multibagger EMA, ADX | positional | 74% | 07-23 12:04 | 09-03 | 7d |
| SCHAEFFLER | Bearish Engulfing, Sr Zone, MACD Cross | swing | 75% | 07-30 19:16 | 08-06 | fresh (next am) |
| FOSECOIND | Bearish Engulfing, Sr Zone, FII/DII | swing | 76% | 07-23 19:15 | **07-30 EXPIRED** | **day 5/5** |
| HINDCOPPER | Sr Zone, Dark Cloud Cover | swing | 76% | 07-23 12:03 | **07-30 EXPIRED** | **day 5/5** |
| COLPAL | Sr Zone, Piercing Pattern | swing | 76% | 07-23 12:04 | **07-30 EXPIRED** | **day 5/5** |
| LENSKART | RSI Divergence | swing | 80% | 07-23 12:03 | **07-30 EXPIRED** | **day 5/5** |

---

## 2. Forward/regime read (per open position, from the daily tape)

| Stock | Side | 20d% | 10d% | 5d% | Range pos | ER10 | ER20 | Trend | Trade vs trend | Reward:Risk left |
|---|---|---|---|---|---|---|---|---|---|---|
| PNCINFRA | LONG | +4.4 | +0.5 | +3.5 | 60% | 0.03 | 0.15 | up | **WITH** | 1.36x |
| GRPLTD | LONG | +15.2 | +12.6 | +5.5 | **100%** | **0.53** | 0.38 | up | **WITH** | 1.40x |
| JKPAPER | LONG | +11.8 | +5.5 | −2.9 | 54% | 0.22 | 0.30 | up | WITH (stalling) | 2.35x |
| FMGOETZE | SHORT | +2.7 | −3.1 | −1.3 | 56% | 0.56 | 0.12 | up | **VS** (fighting) | 0.84x |
| SCHAEFFLER | SHORT | −2.0 | −1.6 | −0.7 | 48% | 0.14 | 0.12 | flat | flat | 2.01x |
| HINDCOPPER | SHORT | −1.3 | +1.4 | +2.0 | 56% | 0.10 | 0.06 | flat | flat | 1.73x |
| FOSECOIND | SHORT | −1.9 | +1.0 | +1.2 | 45% | 0.10 | 0.10 | flat | flat | 1.21x |
| COLPAL | LONG | +1.3 | +1.5 | −0.6 | 38% | 0.10 | 0.05 | flat | flat | 1.39x |

**ER (Kaufman efficiency, 0–1):** >0.40 = clean trend (continuation evidence);
<0.30 = choppy / mean-reverting. **Only GRPLTD (and partly FMGOETZE's up-move)
show a real trend; everything else is chop.**

### Per-position verdict (hold / protect / cut)
- **GRPLTD** — only clean trend; but at 100% of range (extended). **Hold, trail to lock +1,013, don't add.**
- **PNCINFRA** — with-trend, best P&L, positional runway; choppy though. **Hold, trail; TP 11% away.**
- **JKPAPER** — with-trend but stalling (5d red). **Marginal — hold only above entry.**
- **FMGOETZE** — green but **fighting a clean uptrend** and **R:R < 1**. **Bank it / tighten hard.**
- **SCHAEFFLER** — choppy, small loss, but good entry and 2.0x R:R left. **Small hold, defined stop.**
- **HINDCOPPER** — flat/choppy, no downtrend behind the short. **Cut if it can't reclaim below entry.**
- **FOSECOIND** — got run over (+6% against), choppy, chased. **Thesis broken — cut candidate.**
- **COLPAL** — chased a long into chop in the lower third; **never traded green (−0.01R).** **Cut candidate.**

---

## 3. Findings

### What went RIGHT (good)
- The **fixed monitor ran clean** — no pre-open/stale-price closes; all 9 trades are on-tape (the off-tape detector confirms). The 07-27-class corruption did **not** recur.
- **Position sizing worked** — qty sized from capital/risk (e.g., HINDCOPPER 87 vs the signal's house default 439).
- The engine **did find two genuinely good, with-trend trades** — PNCINFRA (+1,122) and GRPLTD (+1,013), both positional, both aligned with a daily uptrend.
- The **analysis/shadow tooling** let us reconstruct truth precisely (real MFE/MAE, off-tape flags, capture, regime) despite the stale display.

### What went WRONG (bad)
1. **Stale expiry-day swing entries — the biggest single loss driver.** HINDCOPPER, LENSKART, COLPAL, FOSECOIND were all **07-23 signals entered on day 5/5** (their expiry). **All four lost/scratched** (−592, −683, −611, −502). No runway, week-old levels.
2. **Weak follow-through / wrong regime.** **No trade reached even 1R favourable** (best 0.66R); MAE > MFE on nearly all. The daily ER confirms most names were **choppy, not trending** — the engine fired directional signals into a range-bound tape (whipsaw).
3. **Chasing.** The three most-chased entries (COLPAL −12.90, FOSECOIND −22, HINDCOPPER −3.15) are among the worst losers.
4. **Charges eat scratches.** LENSKART's −683 was **pure delivery round-trip cost** on a breakeven exit (it peaked +₹1,942 then round-tripped to breakeven, then lost the fees).
5. **Duplicate signals.** 6 stocks (GRPLTD, JKPAPER, NILKAMAL, PNCINFRA, PNGJL, SANATHAN) have **two active signals each** — one from the **base** engine (`profile_key` NULL) and one from the **multibagger profile** — same entry/TP, different SL/qty. Confusing and a double-exposure risk. Three of these (GRPLTD, JKPAPER, PNCINFRA) were traded.
6. **Stale unrealized-P&L display** (tick outage; §0.1).
7. **Operational:** `make live-worker WORKER_ARGS=--gap-fill` was run **mid-session**; `--gap-fill` REST-backfills the whole universe *before* connecting the ticker, so ticks were blocked ~40 min. `--gap-fill` is a **pre-open** step only.

### Root cause (the unifier)
The **alert bell / dashboard is a dumb pipe** — it surfaces whatever the (frozen)
engine generated, with **no age, no validity-left, no regime, no dedup, no R:R,
no action/level**. The user acted reasonably on "Entered Zone"; the system never
told them what they were looking at.

---

## 4. Options weighed & decisions

| Question | Options | **Chosen** | Why |
|---|---|---|---|
| Where do filters live? | (i) inside the confluence engine; (ii) a presentation/eligibility **overlay** between engine and alerts | **(ii) overlay** | `docs/SIGNAL_ENGINE.md` is **frozen** — engine changes need a backtest regression + explicit sign-off. Overlay = no freeze violation, independently testable, shadow-able. |
| Fix stale P&L (a) vs build filters (b) first? | a, b, both | **b as the overlay's first slice; a as a quick side-fix** | b subsumes 4 asks at once (dedup + age + regime + R:R); a is a small correctness fix, done in parallel. |
| Gate signals immediately? | hard-gate now vs **shadow-measure first** | **shadow-first** | A 9-trade sample is too thin; a choppiness gate also kills pre-breakout setups. Measure the keep/kill P&L delta on real history *before* hiding anything. |
| Expiry-day → intraday/scalp? | couple them | **decouple** | Intraday/scalp profiles are **inactive/unvalidated (Phase 6)**. Suppress stale swings now; revisit intraday separately. |

### The agreed backlog (the "Signal-Intelligence / Eligibility overlay")
Built as an overlay, shadow-first, all respecting the engine freeze:
1. **Dedup** base + profile signals per stock (prefer profile / better-R:R; show "2 sources"); fix the active-count to unique stocks.
2. **Age / validity-left** on every signal + alert; **suppress/grey day-4/5 swings** ("don't show on expiry").
3. **Regime tag (ER)** per signal; shadow-measure, then optionally gate choppy names.
4. **R:R check** — flag/suppress signals whose reward:risk from the entry is poor.
5. **Anti-chase alert enrichment** — show **BUY/SELL + entry level + "don't chase past ₹X"** in the bell.
6. **Emergency-exit watcher** — a position-health service beside the monitor that alerts to **cut** when thesis level breaks / trend dies / R:R inverts / deep MAE (the downside twin of the profit-lock).
7. **(a) stale unrealized-P&L** — mark to the latest available close when live ticks are cold (quick side-fix).
8. **Op note:** `--gap-fill` pre-open only; mid-session use plain `make live-worker`.

**Still shadow-only / NOT wired to live:** the Layered Ratchet Stop (profit-lock)
still does not control real exits — the `trail_sl` ladder does. That stays true
through the Mon/Tue run unless we explicitly decide to wire it.

---

## 5. Plan → Monday/Tuesday comparison

1. **Fix today's issues** (backlog §4, at least: dedup, stale-P&L, age/expiry suppression, and — if the shadow report supports it — the regime/R:R flags + anti-chase alert).
2. **Merge** the profit-protection / eligibility work to `main` (note: most profit-protection slices are *already* on `main`; this merges the new overlay + today's fixes).
3. **Trade Mon 2026-08-03 & Tue 2026-08-04** on the fixed + overlaid system.
4. **Re-run this exact analysis** on those trades (§1–§3 format).
5. **Compare** vs this baseline and decide right/wrong/improve.

### Comparison scaffold (fill after 08-03/08-04)
| Metric | Baseline (07-30/31) | Post-fix (08-03/04) | Δ |
|---|---|---|---|
| Trades taken | 9 | | |
| Net P&L (real close basis) | ≈ −₹20 MTM / ~breakeven | | |
| % trades reaching ≥1R MFE | 0 / 9 | | |
| Avg MFE (R) | ~0.24R | | |
| Losers that were stale (day 4/5) | 4 / 4 losers | | |
| Losers that were chop (ER<0.3) | most | | |
| Chased entries | 4 | | |
| Duplicate signals shown | 6 stocks | | |
| Trades WITH the daily trend | 3 / 8 open | | |

**Hypotheses to test:** (H1) suppressing stale + chop signals lifts the % of
trades reaching ≥1R and cuts the loser count. (H2) anti-chase alerts reduce
entry slippage. (H3) the emergency-exit watcher cuts dead trades earlier than
the fixed SL. Confirm or reject each on the Mon/Tue data — do **not** conclude
from a 2-day, 9-trade sample alone.
