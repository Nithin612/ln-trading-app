# Signal generation, entry selection and P&L attribution — a technical review

**Audience:** a quantitative reviewer with no prior exposure to this codebase.
**Scope:** how a stock becomes a signal, how a signal becomes an entry, what the
system has produced so far, why it loses money, and what is actually left to try.
**Status of the numbers:** every figure below is either read from code at a cited
path, or measured from the project's own data by a rerunnable script. Where a
number comes from a historical report whose data no longer exists in the dev
database (destroyed 2026-09-07, partially restored), that is stated inline.

**Companion:** `docs/POSITIONAL_REVIEW_FOR_QUANT.md` covers the **positional** class
on its own terms — it is produced by a single bonus factor, is long-only, and its
stop rule is implemented three different ways, none of which this document's
figures isolate.

**Generated:** 2026-09-10 · branch `feature/pre-cycle2-hardening`
**Reproduction:** `cd backend && uv run python scripts/engine_selectivity_probe.py`
(SELECT-only; the frozen engine is imported and called, never modified).
**Not canonical.** Project status lives in the top block of `docs/PHASES.md`; this is a
standalone explanation written against the code and the data on the date above.

---

## 0. Executive summary — the five things that matter

1. **The system is a bottom-up, single-name, daily-bar confluence scorer.** It runs
   after the close, scores every active stock over its last 300 completed daily
   candles, and emits a signal when a weighted agreement score clears 70%. There is
   no cross-sectional ranking, no sector model in the tradeable path, and no
   fundamental input.

2. **"Confluence" is not being achieved in practice.** Measured over 4,511 real
   daily panels: the median panel has **3 of 15 factors scoring**, worth **30 of a
   possible 160 weight points**, and the confidence percentage normalises by *only
   the factors that scored*. A signal that reads "76% confidence" is typically three
   indicators agreeing, not eleven. **The heaviest factor in the specification —
   Dow trend structure, weight 20, described as "the macro context" — scores on
   3 of 4,511 daily windows (0.07%).** Its parameters make it mathematically
   unreachable on the daily timeframe (§4.2). The swing engine therefore carries no
   trend-structure input at all.

3. **There is no confirmation stage.** The entry price is literally the previous
   session's close (`signal_service.py:236`); the signal is tradeable at 09:15 the
   next morning with nothing having to happen first; and the live "entered the entry
   zone" alert is a **symmetric ±0.5% band**, so a long drifting *down* into its
   entry fires the same alert as a long breaking *up* through it. The obvious fix —
   require the market to trade through the prior bar's extreme before entering — was
   measured on two independent samples and **loses significantly** (§10.2). The gap
   is real; the textbook remedy is not the answer.

4. **The measured edge is approximately zero, and costs are the same order of
   magnitude as the edge.** On 1,975 resolved backtest trades (2023-07 → 2026-09,
   250 liquid names, zero costs applied) mean R is **−0.065**, t = −1.94. On the
   paper book, which does apply costs, expectancy is **−0.303R/trade** over 99
   resolved trades. Round-trip charges alone are **22–62 bps** depending on position
   size, and measured slippage adds **2–58 bps per leg**. Expressed in R — the only
   comparable unit — cost is a *hyperbola in stop width*, and stop width here is set
   by an unrelated mechanism (§12.5). At the 10th-percentile stop width the charge
   load alone is ~0.4R per round trip, and ~0.8R once measured slippage is added.

5. **The problem is upstream of everything that has been built to fix it.** Eight
   selection overlays were built; two were promoted and both were refuted by their
   own forward evidence; the best surviving candidate sits at t = 0.41 against a
   t ≈ 3.6 hurdle. Exit machinery was audited and is working (53% of closed trades
   never reached +0.5R — there was nothing to protect). Target geometry was tested
   and is not the lever. **Candidate generation is where the loss is made, and no
   generation lever currently in the queue has survived testing.**

---

## 1. What the system is

| | |
|---|---|
| Market | NSE / BSE cash equity, India |
| Mode | **Paper only.** There is no live order path — `place_order` is paper, and the Kite client deliberately has no `place_order` method |
| Account modelled | ₹1,00,000 capital · 2% risk per trade · 3% (₹3,000) daily-loss circuit breaker · 5 entries/day (a per-user setting; the model default is 2) |
| Decision cadence | Once nightly on completed daily bars (19:15 IST), plus an intraday layer that is measured but never tradeable |
| Who pulls the trigger | **A human.** `POST /trading/orders` is called from the UI. There is no auto-trader |
| Stack | Python 3.12 / FastAPI / SQLAlchemy async / Celery+Redis / Postgres 16 + TimescaleDB; a Rust parity engine (`tradecore`) that reproduces the Python scorer exactly; React frontend |
| Governance | The scoring engine is **frozen** at an adjudicated commit. Changes require explicit sign-off, a backtest regression, and regeneration of the Rust parity fixtures |

The freeze matters for reading everything below: several defects identified in this
document sit **inside** the frozen boundary, which is why they have been measured
read-only rather than fixed.

---

## 2. Data plane — what exists and what does not

| Table | State (measured 2026-09-10) | Notes |
|---|---|---|
| `stocks` | 3,392 rows, **1,322 active** | `sector` populated on 500; `is_fno` 212; `is_nifty50` 50 |
| `ohlcv_1d` | **2,080,305 bars, 2019-10-01 → 2026-09-09** | The only complete price history. **Corporate-action UNADJUSTED** |
| `ohlcv_5m / 15m / 1h` | **empty** | Lost 2026-09-07; only re-accrues in real time |
| `index_ohlcv_1d` | 48 rows | Broad-index history not restored |
| `india_vix_daily` | 16 rows | Was 784 sessions before 2026-09-07 |
| `cas_daily` | 43 rows | Closing-auction capture; was 1,664 rows / 8 sessions |
| `signals`, `positions`, `orders`, `signal_outcomes` | 30 / 0 / 0 / 0 | **The trading record was destroyed on 2026-09-07** and is not recoverable |

Three consequences a reviewer must hold onto:

- **The historical P&L quoted in §11 cannot be re-derived from the database today.**
  It survives only in the dated reports under `docs/analysis/`, which were generated
  from the data while it existed. Those reports are the primary sources cited.
- **`ohlcv_1d` is CA-unadjusted.** A 2026-09-10 audit found **49 unadjusted corporate
  actions in the top-250-liquid universe, 35 of them ≥40% price halvings**. Dropping
  4 of 1,979 trades from one study removed **~+49R of fake profit**. Any study over
  this table must filter |close-to-close| > 25% and say how many rows it dropped.
  Two already-closed studies assert a "CA-clean window" that does not exist and have
  not been re-run.
- **Every intraday and opening-range hypothesis is currently untestable**, and will
  stay so until intraday capture is restarted and left running.

### 2.1 The daily chain (IST)

```
18:30  FII/DII flows ingested from NSE
18:40  Equities bhavcopy  ->  ohlcv_1d           (self-heals up to 21 missed sessions)
19:15  nightly_signal_generation                 <- the tradeable signals are minted here
19:25  per-profile suggestion pipelines + pair minter   (all currently shadow)
--- next morning ---
09:15  market opens; signals are already `active` and carry a Buy button
09:15–15:30  position monitor every 60s (stops, trailing, exits)
             live tick worker: depth capture, entry-zone / SL / TP alerts
every 5 min  expiry sweeper
```

Source: `backend/app/celery_app.py`.

---

## 3. Stage-by-stage: how a stock becomes a signal

### 3.0 Universe

`app/services/universe_service.py::resolve_universe`. Only `is_active` stocks resolve;
stocks quarantined for a recent corporate action (`ca_flagged_at`) are excluded; T2T
and `-BE` series names are excluded through the daily instrument sync. The nightly
tradeable run uses **all active stocks** — 1,322 names. There is **no liquidity floor,
no price floor, no market-cap floor and no index-membership requirement** on the
tradeable path. (A liquidity gate exists but is in shadow and has been ruled
*don't flip* — §11.3.)

### 3.1 The window

`_load_candles` takes the **last 300 completed daily candles** (`is_complete = true`).
Fewer than 50 → no signal. The no-look-ahead rule is structural: indicators are
computed on candle N and the signal is valid from N+1; forming candles never enter a
committed signal.

### 3.2 The factor set

`app/analysis/confluence.py::run_all_factors` — 14 factors plus a conditional bonus.
Each returns a score in [−1, +1], where **0.0 means "not applicable"**.

| Factor | Weight | What it tests |
|---|---:|---|
| Candlestick pattern (best of 8, not summed) | 15 | Marubozu / Hammer / Hanging Man / Shooting Star / Engulfing / Harami / Piercing–Dark Cloud / Morning–Evening Star. Hammer and Shooting Star are location-gated (within 1% of the 20-bar extreme) |
| **Dow trend structure** | **20** | Higher-highs+higher-lows vs lower-highs+lower-lows over 20 bars. **See §4.2 — this never fires on daily** |
| EMA cross (20/50) | 15 | Golden-cross-lite |
| Price vs EMA (close > EMA50 > EMA200) | 15 | Trend alignment |
| RSI level (14) | 10 | RSI in 30–50 and rising |
| RSI divergence (10) | 10 | Price lower low, RSI higher low |
| MACD cross (12,26,9) | 10 | Line crosses signal |
| MACD histogram | 10 | Histogram rising toward zero |
| Volume | 10 | ≥1.5× the 20-period average — **confirmer only, see below** |
| Bollinger Bands | 10 | Touch outside then close back inside |
| Support/resistance + demand/supply zones | 10 | Proximity to a tested level, or a body breakout on 1.5× volume |
| Fibonacci retracement | 5 | Bounce from 0.5 / 0.618 / 0.786 |
| ADX + DI | 5 | ADX > 25 with directional agreement |
| FII/DII institutional flow | 5 | 5-day cumulative market flows + stock block/bulk deals |
| Multibagger EMA setup (1d only) | +10 bonus | EMA20 within 2% of EMA200 with a breakout candle |

Two design details a reviewer should notice immediately:

- **Volume cannot vote, only second.** After all factors run, a positive volume
  score is rewritten to +0.5 or −0.5 to match the sign of everything else, or to 0
  if the rest nets to zero (`confluence.py:145-157`). It can never fire alone and
  never pushes against the other factors.
- **The FII/DII market-wide component is cross-sectionally constant.** On a given
  day every stock in the universe receives the *same* ±0.5 flow score
  (`structure/institutional.py`); only the block-deal term is name-specific. A
  constant cannot discriminate between candidates — it can only tilt the entire
  night's output in one direction. It nonetheless appears in signal headlines as if
  it were evidence about the stock.

### 3.3 The scorer

```python
total_weighted = Σ  weight_i · score_i                     # over ALL factors
total_weight   = Σ  weight_i  where score_i ≠ 0            # ONLY the factors that scored
normalized     = total_weighted / total_weight             # in [-1, +1]
confidence_pct = int(|normalized| × 100)                   # truncation, not rounding
```

`app/analysis/confluence.py:159-166`.

**This normalisation is the single most consequential design decision in the
system.** A factor that abstains is not a vote against — it is removed from the
denominator entirely. One factor scoring 0.8 with fourteen abstentions yields
80% confidence. That is not a hypothetical: it is how a single-indicator signal
entered the book and lost ₹3,500, and it is why a separate "at least 2 scoring
factors" overlay had to be bolted on downstream (§7).

### 3.4 The gate

Base threshold 70 (`min_signal_confidence`), adjusted by trend strength:

| ADX(14) | Effective threshold |
|---|---|
| < 20 (weak trend) | 75 |
| 20 – 40 | 70 |
| > 40 (strong trend) | 65 |

Measured over 4,511 panels: **39.9% weak** (threshold raised to 75), **8.9% strong**
(lowered to 65), 51.2% unchanged. The "weak trend" branch is not an edge case — it fires
on two panels in five.

### 3.5 Classification

`app/signals/classifier.py` — purely a function of timeframe:

| Timeframe | Class | Validity |
|---|---|---|
| 1m / 5m | scalp | 30 minutes |
| 15m / 1h | intraday | 15:15 IST same session |
| **1d** | **swing** | **5 trading days** |
| 1d + multibagger EMA setup | positional | 30 trading days |
| 1w | positional | 30 trading days |

The tradeable nightly run is 1d only, so **every tradeable signal is a swing or a
positional** — the classification carries no information beyond "the multibagger
factor fired". Validity is computed in real NSE trading days via the holiday
calendar.

### 3.6 Idempotency

`_has_active_signal` blocks a second signal for the same (stock, timeframe,
direction) while one is unexpired. Profiles additionally supersede an existing
signal of the *opposite* direction. There is no "supersede on a stronger score".

---

## 4. What the ≥70% gate actually selects — measured

Method: the frozen engine run over **4,511 daily panels** — 239 stocks (the most
liquid by median daily traded value with sufficient history) × 30 decision dates
spaced 25 sessions apart, each scoring the trailing 300 completed bars. Script:
`backend/scripts/engine_selectivity_probe.py`.

### 4.1 Factor participation

| Factor | Weight | Fires |
|---|---:|---:|
| PRICE_VS_EMA | 15 | 63.4% |
| MACD_HISTOGRAM | 10 | 46.9% |
| ADX | 5 | 38.9% |
| RSI_LEVEL | 10 | 35.7% |
| SR_ZONE | 10 | 25.5% |
| VOLUME | 10 | 15.0% |
| MACD_CROSS | 10 | 8.7% |
| RSI_DIVERGENCE | 10 | 7.0% |
| FIBONACCI | 5 | 6.3% |
| BBANDS | 10 | 5.8% |
| EMA_CROSS | 15 | 1.9% |
| MULTIBAGGER_EMA | +10 | 1.4% |
| any candlestick pattern (the 8 summed) | 15 | ~28% — of which bearish engulfing 7.3%, bearish harami 4.9%, bullish harami 4.6%, bullish engulfing 3.6%, and the remaining nine under 2.5% each |
| **DOW_TREND** | **20** | **0.07%** |
| FII_DII_FLOW | 5 | not measurable in this probe (flows are a per-day constant supplied by the caller; the probe passes zero) |

**Number of factors scoring per panel:** 0 → 4.1% · 1 → 14.3% · 2 → 23.7% ·
3 → 26.7% · 4 → 18.3% · 5 → 8.7% · ≥6 → 4.3%.

**Denominator** (Σ weight of scoring factors, out of a possible 160):
p50 = **30**, p90 = 55, mean 30.9.

**Confidence, pre-gate:** p50 = 40, p90 = 62.

### 4.2 ⚠ The Dow-trend factor cannot fire on the daily timeframe

This is a finding, not a restatement. `run_all_factors` calls
`dow_trend_factor(candles, lookback=20, swing_n=5)` for every non-intraday
timeframe. Inside that function:

- the window is the **last 20 bars**;
- a swing high at pivot width `n=5` must be the maximum of an 11-bar window, so it
  can only sit at index 5…14 — ten candidate positions;
- any two of those indices differ by at most 9, which is **less than 11**, so their
  pivot windows overlap and both can be the maximum only on an exact float tie;
- the function requires **two swing highs AND two swing lows** before it will score.

Therefore at most one high and one low can be found, and the factor returns
`0.0 — "Not enough swing points"` on essentially every daily window. Two independent
demonstrations, both in the probe script:

- **Synthetic:** a textbook staircase uptrend with higher highs and higher lows by
  construction returns `score 0.0, "Not enough swing points: 1 highs, 0 lows"`.
- **Empirical:** 3 non-zero results in 4,511 real daily windows (0.07%), consistent
  with exact-tie edge cases.

The intraday call (`swing_n=3`) is reachable in principle; the daily one is not.

**Why this matters more than a missing 20 points of weight.** Because the
denominator only counts scoring factors, the absence is *silent*: no confidence
number is depressed, nothing is logged, and the specification's own worked example
(§7 of `docs/SIGNAL_ENGINE.md`) happens to be a case where Dow trend also abstained,
so it reconciles. The practical effect is that **the tradeable engine has no
trend-structure input whatsoever** — every swing signal is decided by oscillators,
moving-average position, a candle pattern, and proximity to a level.

Two independent observations corroborate the consequence:

- A Minervini trend-template test on 91 paper entries found **0 of 91 passed all
  seven trend conditions**, with the binding constraints being exactly the
  trend-structure ones (SMA150 > SMA200: 25/91; SMA200 rising: 29/91). The report's
  own conclusion: *"our selection is not a weaker version of this template; it is
  close to its opposite."*
- The closed paper book has **beta +0.92 with per-trade alpha +0.0010 and IR
  +0.017** — the cohort's outcome is explained by market exposure, not by selection.

⚠ **This is a specification defect, not an implementation bug.** `SIGNAL_ENGINE.md`
§2.4 specifies both the 20-bar lookback and N=5 for daily, and the code implements
exactly that. The two parameters are mutually inconsistent. `SIGNAL_ENGINE.md` is
hook-protected and changing it requires explicit instruction plus a backtest
regression, so **nothing has been changed**; this document records the finding.

### 4.3 Selectivity

**189 of 4,511 panels (4.19%) clear the gate**, split 108 SELL / 81 BUY,
176 swing / 13 positional.

Extrapolating to the real universe (1,322 active names) that is roughly 25–55 new
signals a night, which over a 5-trading-day swing validity accumulates to a live
pool in the low hundreds — consistent with the 190–545 active signals the daily
reports observed.

**What a passing signal actually rests on:**

| | p10 | p50 | p90 |
|---|---:|---:|---:|
| scoring factors | **1** | **3** | 4 |
| denominator (of 160) | 10 | **30** | 45 |
| confidence | — | 76 | 88 |

| Factor | Present in passing signals |
|---|---:|
| SR_ZONE | **69.8%** |
| BEARISH_ENGULFING | 39.2% |
| ADX | 25.4% |
| VOLUME | 20.1% |
| PRICE_VS_EMA | 17.5% |
| BULLISH_ENGULFING | 15.9% |
| RSI_DIVERGENCE | 12.2% |
| MACD_CROSS | 11.6% |

**Read plainly: the system is a "candle pattern at a support/resistance zone"
detector.** The advertised 14-factor confluence is, at the decision point, a median
of three factors worth 30 of 160 weight points — and a tenth of passing signals rest
on a single factor. That last cohort is the reason the diversity overlay exists and
is the only overlay currently active.

---

## 5. Levels: stop, target and R:R

`app/analysis/risk.py::compute_levels`, wrapped by
`app/signals/risk_guards.py::safe_levels`.

| Class | Stop loss | Max stop | Take profit |
|---|---|---|---|
| scalp | 0.30% from entry | 0.50% | ±0.45% (1:1.5) |
| intraday | last pivot swing low/high | 0.50% | 2× the risk distance (1:2) |
| **swing** | **last pivot swing low/high** | **8.00%** | **entry ± 6% (flat)** |
| positional | EMA20 daily | none | entry ± 15% (flat) |

Entry price = `Decimal(str(candles["close"].iloc[-1]))` — **the previous session's
closing price** (`signal_service.py:236`).

**Reject, never clamp.** If the structural stop is beyond the class cap, the signal
is discarded rather than tightened. `safe_levels` additionally discards a stop that
sits on the wrong side of, or exactly at, the entry.

### 5.1 The structural consequence: R:R is an accident

A **structural** stop (wherever the last pivot happens to be) is paired with an
**absolute-percentage** target (a flat 6% for swing). Nothing reconciles the two,
and **there is no minimum-R:R requirement anywhere in the tradeable path.**

Measured on the **91 of the 189 gate-passing signals that survive the level stage**
(the other 98 are rejected there — see §5.2):

| | value |
|---|---|
| stop width, % of price | p10 **0.65%** · p50 **5.00%** · p90 7.11% |
| stops under 2% of price | 17.6% |
| R:R | p10 0.84 · p50 **1.58** · p90 9.16 |
| **R:R below 1.0** | **27.5%** |
| R:R ≥ 3 | 31.9% (almost entirely the tiny-stop artifact) |
| notional at ₹1L / 2% risk | p50 ₹38,965 · p90 ₹252,990 · max ₹1,345,436 |
| notional above the 1.0× cap | 15.4% (rejected at order time) |

A 2026-09-02 audit of the live signal table found the same shape independently:
**94 of 295 swing signals had a target closer than their stop**, and 213 of 295 were
below 2R.

### 5.2 The pivot is not "the last swing low of the current structure"

`swing_levels(candles, n=5)` scans the **entire 300-bar window** and returns the most
recent pivot. Measured over the same 4,511 windows:

| entry → last swing low, % of price | |
|---|---|
| p10 | **−2.76%** (the pivot is *above* the entry) |
| p50 | 4.91% |
| p90 | **16.17%** |
| pivot at or above the entry close | **18.2%** |
| pivot beyond the 8% swing cap | **34.4%** |

**Only 47.4% of daily windows produce a usable BUY-swing stop**: 38.1% are rejected
by the 8% cap and 14.5% are wrong-side or degenerate. Among gate-passing signals the
attrition is worse — **98 of 189 (51.9%) die at the level stage**.

This is a selection effect on geometry, not on edge. The signals that survive to the
book are disproportionately those whose *nearest pivot happened to be close* — and
near stops are the losing cohort (§12.5).

---

## 6. Position sizing

```
qty = floor(capital × risk_pct / 100 / |entry − stop_loss|)
if ATR(14) > 3% of price:  qty = qty × 3 // 4          # volatility regime
if qty == 0: reject
```

`app/analysis/risk.py`. `risk_pct` is a whole percent (2.0 = 2%) — the function does
its own division; pre-dividing was a real 100× undersizing bug.

Two scales coexist and they are easy to confuse:

- **Signal generation sizes against ₹5,00,000** (hardcoded in
  `tasks/signal_tasks.py::_default_risk_params`). `signals.suggested_qty` is
  therefore a display number at the sampling scale.
- **The order path re-sizes from the actual fill at the user's own capital**
  (`paper_broker.size_for_fill`): `qty = floor(budget / (fill − stop))`, direction-aware,
  and when adding to an existing position it sizes against the *remaining* budget so
  repeat entries cannot stack past the per-trade risk budget.

Risk-first sizing bounds a trade's **risk** but not its **size**. A four-paise stop
once produced 50,000 shares — ₹1.19 crore of notional on ₹1 lakh of capital — and
returned HTTP 201. That is what the per-position notional cap (1.0× capital, reject
not clamp) now prevents.

---

## 7. From signal to order: the gate stack

`POST /api/v1/trading/orders` → `app/trading/risk_engine.py::check_pre_trade` →
`app/signals/restrictions.py` (an ordered registry, walked by both the order path
and the display path so the two cannot drift) → `paper_broker.place_paper_order` →
`check_sizing`.

Rules in execution order, with **live modes read from the running configuration on
2026-09-10**:

| # | Rule | Mode | What it does |
|---|---|---|---|
| 1 | kill switch | always | Human stop. Deliberately does **not** block exits |
| 2 | daily-loss circuit breaker | always, not disableable | ₹3,000/day realised loss, and max 5 entries/day |
| 3 | signal exists / status is `active` | always | Shadow and expired signals are untradeable |
| 4 | off-market entry | broker, always | Rejects outside 09:15–15:30 IST unless opted in |
| 5 | regime gate (skip ADX 20–25) | **shadow** | Promoted 2026-08-14, **reverted 2026-09-02** |
| 6 | circuit-band proximity (1.5%) | shadow | Don't enter within 1.5% of the adverse daily band |
| 7 | **entry diversity (≥2 scoring factors, no factor >90%)** | **ACTIVE** | The only active selection gate |
| 7b | stop-too-tight (`abs(entry − SL) < k·ATR`) | shadow | k = 1.0 |
| 8 | R:R floor (≥1.0) | **shadow** | Shipped active 2026-09-02, **reverted 2026-09-03** |
| 9 | sector relative strength | shadow | Untestable — see §9 |
| 10 | market regime (200-DMA + VIX) | shadow | Would block 74% of the book; do-not-flip |
| 11 | liquidity floor (₹1 Cr median traded value) | shadow | Ruled do-not-flip |
| 12 | anti-chase (live price > 0.33R past entry) | shadow | Blocks when the reward has already been consumed before the fill |
| 13 | through-stop | broker, always | Rejects an order already through its own stop |
| 14 | per-position notional cap (1.0× capital) | **active** | Reject, never clamp |
| 15 | max concurrent positions (3) | **off** | Flips at the cycle-2 reset |
| 16 | portfolio heat cap (6%) | **off** | Fails *closed*; flips at the cycle-2 reset |

**Exactly one selection gate is active**, and it enforces a stated hard rule
("never a single indicator") rather than a measured edge. That is deliberate: gating
has been formally closed as a programme (§11.3).

The display path runs the same registry through `eligibility.preview` so a signal
that would be refused is listed with a disabled Buy button and the *verbatim*
refusal reason. Before that was built, 41 of 204 listed signals offered a Buy button
that could only fail.

---

## 8. Execution model — fills, slippage, charges

**Fills are market orders at the live traded price**, haircut by a model that fails
open at every step (`paper_broker.simulate_fill`):

```
adverse_bps = clamp( half_spread + top_of_book_impact + participation ,
                     floor   = 2.0 bps ,
                     ceiling = 500 bps )
participation_bps = 0.1 × (order_value / median_daily_traded_value)² × 10,000
```

- `half_spread` is the real half-spread from the live depth book. **82% of live NSE
  books are wider than the flat 2 bps floor** — which is why paper P&L before and
  after 2026-08-17 is not comparable and the paper clock was reset.
- The top-of-book term is linear in `qty / resting size at the touch`, capped at
  50 bps.
- The participation term is quadratic, calibrated to zipline's `VolumeShareSlippage`:
  2.5% of a day's volume ≈ 0.6 bps, 10% ≈ 10 bps, 20% ≈ 40 bps.
- Tick rounding is **directional** — a buy ceils, a sell floors — because 27.2% of
  real closes are off the ₹0.05 grid and nearest-tick rounding would hand back a
  better-than-market fill 4.9% of the time.
- Unrealised marks route through the *same* model on the exit side, so a long marks
  toward the bid.

**A real day's fills** (2026-09-04, 9 fills, all priced off a live book): half-spreads
1.08–9.75 bps; impact 0.17 bps up to the 50 bps cap on four of them; totals 2.0–57.8
bps per leg. The honest model charged **₹664 more than the flat model would have** on
that one day.

**Charges** (`app/trading/fees.py`, Zerodha equity delivery):

| Component | Rate |
|---|---|
| Brokerage (delivery) | 0 |
| STT | 0.100% **both legs** |
| Stamp duty | 0.015% buy leg |
| Exchange transaction | 0.00297% both legs |
| SEBI | ₹10 per crore |
| GST | 18% on brokerage + exchange + SEBI |
| **DP charge** | **₹15.34 flat, delivery sell leg only** |

Round trip by position size:

| Position | Notional | Charges | bps |
|---|---:|---:|---:|
| 100 × ₹39 | ₹3,900 | ₹24.01 | **61.6** |
| 1,000 × ₹39 | ₹39,000 | ₹102.01 | 26.2 |
| 400 × ₹2,500 | ₹10,00,000 | ₹2,237.80 | 22.4 |

The DP charge is the only cost that is not neutral to position size. When it was
added (2026-09-05) it turned out **all 105 closed positions were delivery, so
₹1,610.70 had never been levied — 15.8% of the book's entire loss.**

### 8.1 ⚠ The backtest applies no costs at all

`app/backtest/engine.py::_simulate_trade` fills at the **open of candle N+1** and
applies **no slippage, no brokerage, no STT, no DP charge**. Gap-throughs exit at the
open rather than the level, and the stop is checked before the target on both-hit
bars, so the fill logic is conservative — but the cost load is simply absent.

**Therefore backtest expectancy and paper expectancy are not comparable**, and the
difference between them is roughly the entire charge load. Any comparison in §11 that
crosses this boundary is labelled.

---

## 9. Sector, index and market context

Asked directly — is there any sector or top-down analysis in the decision? **Not in
anything tradeable.**

- `app/signals/sector_rs.py` computes relative strength as *(stock return over N
  sessions) − (benchmark return over the same window)*. It is an eligibility
  overlay, **shadow**, and has never been active.
- `app/signals/market_regime.py` gates on the broad index's 200-DMA with India VIX as
  an informational companion. **Shadow.** Its sidecar has read "ready" — and the
  standing instruction is **do not act on it**: it would block 405 of 545 signals,
  and its blocked set has a *higher* win rate than the eligible set (52% vs 45%),
  which is the signature of a few large losers moving a mean.
- **Neither is currently testable at all**: `index_ohlcv_1d` holds 48 rows and
  `india_vix_daily` 16, and only three broad indices were ever ingested — so
  "sector" relative strength has no sector benchmark to compute against.
- `stocks.sector` is populated on **500 rows overall, but on only 165 of the 1,322
  active names** (12.5% of the tradeable universe) — corrected 2026-09-10; an earlier
  revision of this line read "500 of 1,322 active", which conflated the two counts.

Fundamentals: none. `market_cap_cr` has no writer (a free source was identified in a
2026-09-08 spike but the build was deferred for want of a consumer). News: an
ingestion path exists; the news veto was deferred because none of its three
preconditions holds — 0 of 322 rating rows carry a direction, there is no forward
earnings calendar, and the existing guard has never fired on any of 559 signals.

---

## 10. Validation, confirmation and promotion

This section answers the question directly: **do we validate a previous-day EOD
signal against the next trading day before treating it as tradeable?**

### 10.1 Next-day validation of a signal: **no**

A signal minted at 19:15 IST is `status = 'active'` immediately. At 09:15 the next
morning it is listed, it carries a Buy button, and the order path will fill it. No
price action is required to occur first. The entry price on which the stop, target,
quantity and R:R were all computed is *yesterday's close*, which by definition will
not be available again.

What exists instead is an **alert layer** (`app/broker/live_levels.py`), fed by the
live tick worker:

| Alert | Definition |
|---|---|
| entry zone | live price enters `entry × (1 ± 0.5%)` — **a symmetric band** |
| SL / TP near | within 25 bps of the level |
| SL / TP touch | a direction-aware cross at the exact level |
| PDH / PDL | direction-aware crosses of the previous day's extremes |

⚠ **The entry-zone alert is direction-blind.** A long whose price is *falling* into
the entry band fires the same "entered zone" alert as one *rising* through it — the
setup failing reads identically to the setup triggering. The direction-aware
`cross_up`/`cross_down` machinery already exists in the same file for PDH/PDL and is
simply not wired to the entry zone. **This is the one open correctness fix. It is
not built, and it is explicitly not a P&L claim.**

There is also a **provisional / shadow layer**: intraday profiles run on their real
schedules and are measured to outcome, but the order path admits `status == 'active'`
only, so they can never be traded. Provenance is carried on a durable `is_shadow`
column because `status` is a lifecycle field the expiry sweeper overwrites.

### 10.2 Should a confirmation trigger be added? Measured: **no**

The natural fix — don't buy the close, buy only when the market trades through the
prior bar's high — was pre-registered and tested on two independent samples in
September 2026.

**Sample A — market-wide base rate, 108,506 stock-days** (250 liquid names,
2023-07-03 →; 841 observations dropped for an unadjusted corporate action inside the
forward window). Selection is real: days that trade through the prior high return
**+1.018%** to the next close against **−0.915%** for days that do not (entering at
the open in both cases). But it is **fully priced into the trigger** — entering at the
trigger price instead returns **−0.176%** at +1d.

The hypothesis is a *difference*, so it is decided on the daily series
`mean(confirmed: enter at trigger) − mean(all: enter at open)`, with a Newey–West t at
lag k−1 over 628 days:

| horizon | mean difference | t (Newey–West) |
|---|---:|---:|
| +1d | −0.107% | **−3.46** |
| +3d | −0.107% | **−2.94** |
| +5d | −0.153% | **−3.51** |
| +10d | −0.165% | **−3.00** |

Weinstein's 2% chase ceiling does not rescue it (−2.55 … −3.35 over the same
horizons).

**Sample B — 1,975 of our own minted signals**, with the study's walker asserted
trade-for-trade against the frozen backtest engine on 400 trades:

| Entry rule | n | kept | mean R (winsorized) | win | t |
|---|---:|---:|---:|---:|---:|
| baseline: fill at next open (frozen) | 1975 | 100% | −0.065 | 36% | −1.94 |
| stop at prior-bar extreme, 1d | 1182 | 60% | −0.044 | 44% | −1.27 |
| … + 0.33R chase ceiling, 1d | 1151 | 58% | −0.047 | 45% | −1.34 |
| … + dead if the stop was touched in the same bar, 1d | 1083 | 55% | +0.013 | 47% | +0.37 |
| … same, 3d window | 1298 | 66% | −0.006 | 48% | −0.20 |
| … same, 5d window | 1363 | 69% | −0.011 | 48% | −0.34 |

Decomposed on the intersection (the same trades under both rules), the two effects
point in opposite directions and only one of them is significant:

| window | selection benefit | fill cost (paired ΔR) | t(ΔR) |
|---|---:|---:|---:|
| 1d | +0.239 | **−0.226** | **−10.62** |
| 3d | +0.248 | **−0.254** | **−12.46** |
| 5d | +0.253 | **−0.264** | **−12.84** |

**The benefit never reaches t = 0.4; the cost sits at t ≈ −10 to −13.** Re-anchoring
the target to the actual fill (to rule out target truncation) moves ΔR from −0.262 to
−0.268 — the cost is the risk side, not the reward side.

### 10.3 When does confirmation arrive anyway? (the alert-timing number)

Of 1,975 baseline signals, measured from the bar the engine fills on:

| Confirms on day | count | cumulative |
|---|---:|---:|
| +1 | 1,182 | **60%** |
| +2 | 194 | 70% |
| +3 | 93 | 74% |
| +4 | 63 | 78% |
| +5 | 46 | **80%** |
| never within 5 sessions | 397 | — |

A one-day alert window and a five-day alert window are different products. **20% of
signals never confirm at all**, and the swing validity is exactly 5 trading days.

### 10.4 How a *rule* gets promoted (the governance answer)

Distinct from validating a signal: how does a shadow gate or a retune become live?

- Every candidate runs in **shadow** on the real schedule, its verdicts stamped on
  orders and accrued in a per-day sidecar report.
- Promotion requires the **deflated-Sharpe bar** (`app/services/deflated_sharpe.py`),
  which corrects for the number of hypotheses tried. It was itself validated against
  a known null and a planted edge: it rejects noise (1.10% false-positive on
  best-of-20 zero-edge selections against a 5% design allowance) and detects real
  edges (80% power at a true per-trade Sharpe of 0.52).
- **Restated as a plain t-statistic the bar demands t ≈ 3.6, and the hurdle is flat
  in n** (3.76 at n=30, 3.55 at n=1000). Two consequences: accruing more data never
  lowers the bar, so "keep waiting" is only ever right when the point estimate is
  already ahead; and power is near zero between t ≈ 2.6 and 3.5, so *failing is not
  evidence of no edge* — the t is recorded, not just the verdict.
- Standing rule after two reversals in two days: **no flip on an argument.** Check
  the count, check that the sign survives trimming the tail, and check the partition
  is not a proxy for something else (the regime gate turned out to be a proxy for
  side).

---

## 11. What the system has produced

### 11.1 Backtest, frozen engine, **zero costs applied**

| Corpus | n | Result |
|---|---:|---|
| 250 liquid names, 2023-07-03 → 2026-09, resolved trades | **1,975** | mean R **−0.065** (winsorized at 10R) · median R −1.000 · total **−128.4R** · win **36%** · target hit 35% · **t = −1.94** |
| Nifty50 daily, weight-retune baseline | 811 | Sharpe +0.025 · **t = +0.71** · expectancy **+0.038R** |
| Terminal signal outcomes since 2023-09 (attribution corpus) | 816 | expectancy **+0.05R** · 40% hit · reach-1R 44% |

Read these together rather than separately. The engine's *uncosted* expectancy is
somewhere around zero — slightly positive on one corpus, slightly negative on
another, **statistically indistinguishable from zero on both**. That is the honest
headline: there is no demonstrated edge to erode, and the sign flips with the sample.

Sub-cohorts from the 816-trade attribution (these are what the gating programme was
built on):

| Cell | n | expectancy R |
|---|---:|---:|
| confidence 80–89 | 307 | +0.20 |
| confidence 90–100 | 62 | +0.11 |
| confidence 70–79 | 434 | **−0.07** |
| ADX trending (≥25) | 140 | +0.24 |
| ADX choppy (<20) | 337 | +0.12 |
| ADX transitional (20–25) | 339 | **−0.10** |
| 70–79 × transitional | 250 | **−0.23** |

### 11.2 Paper trading, costs applied

Cycle 1 is a deliberately wide sampler: ~5 entries/day, ~5-day holds, ~25–29
concurrent positions, whose 30-day clock is **informational**, not the go-live gate.

| Measure | Value | Source |
|---|---|---|
| Closed positions | **106** | clean-book study, 2026-09-07 |
| Realised, as recorded | **−₹12,369** | same |
| Expectancy | **−0.303R/trade** over 99 resolved | entry audit, 2026-09-02 |
| Win rate / avg win / avg loss | 37.5% · +1.14R · −1.17R | same — break-even needs a 1.67R payoff |
| vs NIFTY50, 2026-08-17 → 09-04 | book **−15.03%** vs index **−1.61%** — **lost to buy-and-hold by 13.42 pp** | daily report 2026-09-06 |
| Market exposure of the closed book | **beta +0.92** · per-trade alpha **+0.0010** · IR **+0.017** | same |
| Open portfolio heat at peak | **58.0% of ₹1L across 29 positions** | same |
| Under-costing found and fixed | ₹1,610.70 of DP charges never levied = **15.8% of the book's loss** | 2026-09-05 |

**The exit machinery is not the problem — this was tested.** On 95 closed positions
with a recoverable commit stop, normalised in R:

| Peak bucket | n | avg peak R | avg realised R | capture |
|---|---:|---:|---:|---:|
| < 0.25R — never worked | 35 | 0.02 | −0.72 | — |
| 0.25–0.5R | 15 | 0.37 | −0.35 | — |
| 0.5–1R | 18 | 0.73 | +0.33 | 45% |
| 1–2R | 24 | 1.31 | +0.86 | 66% |
| ≥ 2R | 3 | 2.60 | +1.69 | 65% |

**53% of trades never reached +0.5R** (−30.6R). The 45 that did work kept **60% of
their combined peak**. The entire addressable pool for a better exit is 20.8R, most
of it irreducible. ⚠ The same study records a correction worth repeating: in ₹ this
looked like a −₹59,785 exit defect; **in R it evaporates**, because risk-first sizing
makes ₹ incomparable across trades.

**Entry displacement split** (106 closed, threshold = the anti-chase ceiling 0.33R):

| Set | n | realised ₹ | total R | win |
|---|---:|---:|---:|---:|
| entered at or near the signal | 93 | **+₹13,262** | +18.8R | 55% |
| filled > 0.33R past the signal entry | 12 | **−₹21,609** | −9.1R | 25% |
| R not computable (stop wrong side of fill) | 1 | −₹4,022 | — | 0% |

⚠ The study that produced this immediately qualifies it: displacement is measured in
*units of the stop distance*, so a tight stop mechanically inflates it (avg stop
width 2.13% in the chased set vs 5.33% in the clean set). **Chasing and tight stops
are two entangled defects, not one measurement.**

### 11.3 Every hypothesis tested, and its verdict

This table exists so a reviewer does not re-propose something already refuted.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| 1 | Skip the transitional ADX 20–25 regime | **Promoted, then reverted** | Promoted on 44 observations; refuted by 88. Suppressed set net-positive; all three justifying metrics inverted; gating moved total-R from −2.0R to −10.0R |
| 2 | Require R:R ≥ 1 | **Promoted, then reverted in 24h** | The blocked cohort was the book's only profitable one: 24 trades, +₹10,585, 63% win. R:R<1 is a *proxy for a wide stop*, and wide stops are the good cohort |
| 3 | Stop-too-tight gate (`sl_atr`) | **Decided NO** | Best surviving candidate; **t = 0.41 against a 3.6 hurdle** |
| 4 | Liquidity floor | Do not flip | The illiquid set is net *positive*, the liquid set net negative, robust across floors |
| 5 | Market-regime (200-DMA) gate | Do not act | Would block 74% of the book; blocked set has the *higher* win rate |
| 6 | Weight retune (`momentum ×1.5`) | **Decided NO** | t = +1.00 vs 3.6; and **the winner moved** to `structure ×0.5` when the corpus grew — the ranking itself was the noise |
| 7 | Add RVOL / VWAP as confluence factors | **Declined** | RVOL at entry is mildly *inverse*; injecting a graded RVOL factor scores −0.291R at t = −2.91 on the 294 signals it newly admits |
| 8 | Change the take-profit geometry | **Closed** | No constant-R:R target (1.0–3.0R) beats the frozen absolute-% target on 1,152 signals; every paired ΔR negative, abs(t) ≤ 0.65 |
| 9 | Next-day confirmation trigger | **Refuted twice** | §10.2 |
| 10 | Weinstein 150-DMA stage filter · Elder Thermometer · Carter squeeze · Weinstein overhead supply | All refuted | Squeeze: 3,610 fires, abs(t) ≤ 1.09 market-neutral. Overhead supply: never significant once overlap-corrected |
| 11 | Minervini trend template as a gate | **Not a gate** | 0 of 91 entries pass — disjoint from our selection, so this book cannot test it. Needs a universe-level rerun |
| 12 | Feature sweep: 17 volume/SMA/price/52-week configurations | Nothing survives | 212,129 observations, day-block bootstrap; **no top-6 interval excludes zero** |
| 13 | Portfolio heat cap | **Risk control, not a fix** | Counterfactual: total loss smaller (−₹13,303 vs −₹19,093) but **per-trade worse** (−₹1,478 vs −₹796) |
| 14 | Closing-auction overnight reversal | **Real, not yet promotable** | Cross-sectional Spearman ρ = **−0.272**, 90% day-block interval [−0.478, −0.088] excludes zero, 6 of 7 days negative. But 7 days cannot clear t ≈ 3.6, and ~half the magnitude rests on one afternoon |

**Gating was formally closed as a programme on 2026-09-04.** Eight shadow gates, two
promotions both refuted, best survivor at t = 0.41. The conclusion drawn was not
"try a ninth gate" but "no partition of these trades will clear the bar, because the
trades carry no edge to partition".

### 11.4 ⚠ Four defects found in the measurement apparatus itself

Found 2026-09-10 (the fourth during the positional review the same day). They matter
to a reviewer because **all four made a negative result look better than it was**, and
every historical study is exposed to them.

1. **A daily cross-sectional t is not enough for overlapping forward windows.**
   Averaging the cross-section kills same-day dependence but not the overlap between
   day *t* and *t+1*, which share k−1 sessions of the same future. Under the null the
   naive t has standard deviation **0.98 at k=1, 3.32 at k=10, 4.45 at k=20** — so a
   naive "t = 9" on a 20-day horizon is ≈1.9σ. Fixed by
   `app/services/block_bootstrap.newey_west_t(series, lag=k−1)`, which ships with an
   H0 canary that first *reproduces* the inflation.
2. **The "CA-clean window" claim was false** (§2). Two already-closed studies
   (take-profit geometry, RVOL) assert it and have not been re-run.
3. **Averaging R without winsorizing lets ~10 trades own the answer.** In the entry
   study the ten largest |R| trades all had stops of 0.23%–0.86% and contributed
   **+128.4R against a −89.7R total**. Convention: winsorize at
   `app.core.ratios.WINSOR_R = 10.0` wherever R is averaged, and report the median
   and a paired ΔR beside it.

4. **⚠ Added 2026-09-10 (found during the positional review): `_simulate_trade`
   scores a gap-through-stop fill as a WINNER.** The gap check is skipped on the fill
   bar (correctly — the entry is that bar's open), but the intrabar `low <= stop_loss`
   test still fires and exits **at `stop_loss`**, which for an already-gapped fill is
   *above* the entry. A three-bar reproduction: signal close 100, stop 99, next open
   **95** ⇒ recorded exit 99, `hit_sl = True`, **P&L +4.211% = +1.000R**. The live
   path is immune (`paper_broker:544-554` rejects an order already through its stop),
   so this is a *measurement* defect only — but it flatters the **tight-stop** cohort,
   which is where this document's cost analysis (§12.5) concentrates. **The
   1,975-trade headline in §11.1 and the entry-confirmation study in §10.2 both
   inherit it and the magnitude there is unmeasured.** On the positional corpus,
   excluding the affected trades moved the tightest stop bucket from −0.257R to
   −0.306R. Details and the reproduction: `docs/POSITIONAL_REVIEW_FOR_QUANT.md`
   Appendix C #4.

The generalisable rule adopted: *an instrument never run against a known null, a
known-contaminated input and a known tail artifact has not been validated.*

---

## 12. Diagnosis — why the right stock is not entered at the right price at the right time

Ordered by strength of evidence, not by ease of fixing.

### 12.1 The candidate generator has no demonstrated edge

1,975 resolved trades, mean R −0.065, t −1.94, **before any cost**. On a second
corpus expectancy is +0.038R at t = +0.71. Both are indistinguishable from zero. A
selection layer, an exit layer and an execution layer applied to a zero-edge
candidate set cannot produce a positive expectancy; they can only redistribute it.
Everything else in this section is downstream of this.

For calibration rather than comfort: across a 4,843-paper replication record, the
**median published Sharpe is 0.37 and half of published strategies are
indistinguishable from zero on their own sample**. A −0.303R book measured honestly
is an early-stage position on that distribution, not an anomaly. A 2–3%/day target is
not on that distribution at all.

### 12.2 The confluence premise is not being met, and the arithmetic hides it

Median 3 of 15 factors score; the denominator is 30 of 160; the tenth percentile of
*passing* signals rests on a single factor. Because abstention is free, a signal
built on three agreeing oscillators is arithmetically indistinguishable from one
built on eleven agreeing inputs. The stated edge — "5–7 conditions aligning" — is
not what the code produces.

### 12.3 The engine has no trend-structure input on the timeframe it trades

§4.2. The weight-20 Dow factor fires on 0.07% of daily windows and cannot fire by
construction. Corroborated by 0/91 entries passing Minervini's trend conditions and
by beta +0.92 with alpha ≈ 0. **The system is systematically entering names in
structural downtrends and its output is dominated by market beta.** Of the diagnoses
here this is the only one that is a *defect* rather than a *result*.

### 12.4 There is no trigger stage — and the textbook trigger loses

Setup → manage, with no confirm in between (§10). Entry is yesterday's close, the
alert is direction-blind, and 20% of signals never confirm within their entire
validity window. But the measured remedy is worse than the disease: the selection
benefit of waiting is real but small (t ≤ 0.4) and the fill cost of waiting is large
and significant (t ≈ −10 to −13). **A structural explanation exists** — Brooks'
trader's equation: whenever one of {risk, reward, probability} is unusually good, the
others are worse. Waiting for confirmation buys probability and pays for it in risk.
The same mechanism independently explains why the R:R ≥ 1 floor blocked the
high-probability cohort.

### 12.5 Stop geometry is arbitrary, and cost in R is a hyperbola in stop width

The stop is the most recent 5-bar pivot **anywhere in a 300-bar window** — p90 is
16% away, and 18% of the time it is above the current price. The target is a flat
percentage that knows nothing about it. Half of gate-passing signals die at the class
cap, and the survivors are selected on *pivot proximity*.

Now combine that with §8. Round-trip charges are 22–62 bps, plus 2–58 bps of
slippage per leg. Expressed against the trade's own risk unit:

| Stop width | Charges only (≈26 bps at the median ₹38,965 notional) | + measured slippage (≈28 bps round trip) |
|---|---:|---:|
| 5.00% (median) | 0.05R | **0.11R** |
| 2.00% | 0.13R | 0.27R |
| 0.65% (p10) | 0.40R | **0.83R** |

_Slippage basis: the only day with published fill telemetry (2026-09-04, 9 fills, all
priced off a live book) had a **median total of 14.0 bps per leg** — mean 25.2, range
2.0–57.8. One day of nine fills is a thin basis and the range spans an order of
magnitude, which is why the charges-only column is given beside it: that one needs no
assumption at all and is already enough to make the point._

**A trade whose structural stop happened to land close must overcome most of an R in
friction before it can win anything.** This is not a modelling artifact — it is why
14 trades with stops under 2% of price lost ₹25,951 at a 29% win rate, why tight
stops overshoot −1R (−1.70R realised under 0.25× the daily range), and why the
"chased" cohort is really the tight-stop cohort wearing a different label. The stop
width is set by pivot geography; the cost is set by the stop width; neither is set by
anything to do with the trade's merit.

### 12.6 Cost is the largest *measured* effect anywhere in the programme

Every candidate *edge* measured over three years sits at abs(t) ≤ 3.5, and most at
abs(t) ≤ 1. The fill-cost term sits at **t ≈ −10 to −13**. That asymmetry deserves emphasis: the
one thing this system can measure with confidence is what it pays to trade.

### 12.7 Execution is human, clustered, and unaided

All entries are placed by hand, almost all between 09:20 and 10:21 IST, as market
orders at whatever the price then is. There are no limit orders (deferred), and the
anti-chase guard is in shadow. 12 of 106 fills landed more than 0.33R past the signal
entry.

### 12.8 Portfolio construction was never sized for the account

Median signal notional at ₹1L/2% is ₹38,965 — a *single* position is ~39% of the
account. Heat reached 58% of capital across 29 positions. Both caps (6% heat, 3
concurrent positions) are built, both are `off`, and both are scheduled to flip at
the cycle-2 reset. Note this is a **cycle-1 sampling artifact** by design, not an
accident — but it means the recorded book is not the book that would be traded.

---

## 13. Options — what is actually left to try

Nothing here is a recommendation to trade. Each is scoped by what it would cost to
test and what evidence would settle it.

### Tier 1 — generation levers (the only tier that can change expectancy)

| # | Option | Mechanism | How to test | Prior |
|---|---|---|---|---|
| **1** | **Restore trend structure to the scorer** | The weight-20 factor is unreachable on daily (§4.2). Either the lookback or the pivot width is wrong; a 60–100 bar lookback at n=5, or n=3 at 20 bars, makes it reachable | Exactly the read-only method used to refute RVOL: inject a working trend factor through the frozen scorer, score the 2023-07→2026-09 corpus, compare paired ΔR. **No frozen edit needed to get the answer** | Guarded. It is the only *defect* on the list rather than a *hypothesis*, and two independent observations say trend structure is where our selection is anomalous. But the RVOL test showed injection can dilute through normalisation, so a negative is entirely possible. Requires a spec decision to ship |
| **2** | **Minervini as a universe filter, not a gate** | 0/91 entries pass — the sets are disjoint, so this cannot be tested on the book. It makes a claim about what should be *eligible* | Universe-level corpus rerun: restrict the scoring universe to trend-template names and regenerate signals from scratch. This is real work, not a shadow gate | Unknown — genuinely untested. Named by its own report as the correct next step |
| **3** | **12-month price momentum** | The single thread the September reading study surfaced and did not test. It appeared as the *control that killed* the overhead-supply effect, so the evidence for it is weaker than it looks | Cross-sectional factor test with the day-block bootstrap and Newey–West t, then a paired injection test | Weak-positive prior, cheap to run |
| **4** | **Closing-auction overnight reversal, to ≥30 sessions** | The only clean directional signal the programme has produced (ρ = −0.272, interval excludes zero) | Restart Stage-1 capture (currently 43 rows; the window cannot be back-filled) and re-run at ≥30 days | Best odds on the list, but ~6 weeks of wall-clock and it is a *different strategy*, not a fix to this one |

### Tier 2 — attack the cost term (does not create edge; moves −0.065R toward 0)

| # | Option | Expected effect |
|---|---|---|
| 5 | **Limit orders instead of market** (order type + price already scoped, deferred) | Directly attacks the only term measured at t ≈ −10. Cannot fix the charge floor, but removes the half-spread and the top-of-book impact on entry |
| 6 | **Refuse trades whose stop is too near to survive friction** | Not the ATR gate (refuted at t = 0.41) but a *cost-relative* rule: reject when round-trip friction exceeds some fraction of 1R. This is an identity about arithmetic — ⚠ and the R:R reversal is the standing warning that an identity still rests on an empirical premise. Test the premise before shipping |
| 7 | **Fewer, larger positions** | The flat DP charge is 61.6 bps at ₹3,900 and 22.4 bps at ₹10L. Cycle 2's 1–2 position shape makes this worse, not better, unless position size rises |

### Tier 3 — correctness and capability (no P&L claim)

| # | Option | Why |
|---|---|---|
| 8 | **Make the entry-zone alert directional** | A long falling into its entry currently fires "entered zone". Machinery already exists in the same file. Small, unambiguous |
| 9 | **Restart intraday capture before cycle 2 begins** | `ohlcv_5m/15m/1h` are empty and only accrue in real time. Every opening-range, VWAP and intraday-timing hypothesis is blocked until this runs |
| 10 | **Restore index and VIX history** | 48 and 16 rows. Until these are back, the market-regime and sector-RS overlays cannot be evaluated at all, and the benchmark comparison in the daily report is fragile |
| 11 | **Re-run the two studies that assert the false CA-clean window** | Take-profit geometry (closed D5) and RVOL (closed D1). Both conclusions may well stand — but they are currently uncitable |

### Tier 4 — risk control (reduces variance and ruin risk, not loss rate)

| # | Option | Effect |
|---|---|---|
| 12 | Flip the 6% heat cap and 3-position cap at the cycle-2 reset | Already built and `off`. Measured: smaller total loss, *worse* per-trade loss. This buys survivability, not profitability, and the distinction should be stated whenever it is reported |
| 13 | Keep the notional cap and the daily-loss breaker exactly as they are | Both prevented specific, documented failures |

### What should **not** be done

- **Do not add a ninth selection gate.** Gating is closed as a programme, with the
  reasoning recorded: the trades carry no edge to partition.
- **Do not re-promote the R:R floor on the identity argument.** It has now been
  refuted empirically *and* explained structurally.
- **Do not flip a shadow gate because its sidecar reads "ready".** Two of two such
  promotions were reverted. The bar is t ≈ 3.6 and it does not fall with more data.
- **Do not tune anything on the live paper book.** It is the go-live gate.

---

## 14. Open questions a reviewer is best placed to answer

1. Is the abstainer-normalising denominator defensible at all, or should a
   non-scoring factor count as a zero *in* the denominator? The alternative was
   measured once (sub-factors sharing a group budget) and was much worse — but the
   specific question "abstention free vs abstention penalised" has not been tested.
2. Given §4.2, is restoring the trend factor a *bug fix* (restore the specified
   intent) or a *new hypothesis* (which must then clear t ≈ 3.6)? The governance
   answer changes the amount of evidence required by an order of magnitude.
3. Is a structural stop paired with a *structural* target (next S/R level) worth
   testing, given that the constant-R:R family was refuted? The prior in-house is
   that re-slicing an edgeless set will not rescue it.
4. At an account size of ₹1 lakh where round-trip friction is 22–62 bps plus spread,
   is a daily-bar swing strategy on 1,300 Indian small- and mid-caps viable at all,
   or is the cost floor decisive?
5. Is the correct next move to keep searching for edge inside this framework, or to
   treat what has been built — the honest execution model, the deflated-Sharpe bar,
   the outcome recorder, the overlap-corrected statistics — as *evaluation
   infrastructure* and search for the edge elsewhere?

---

## Appendix A — file map

| Concern | Path |
|---|---|
| Specification (protected) | `docs/SIGNAL_ENGINE.md` |
| Factor implementations | `backend/app/analysis/{indicators,patterns,structure}/` |
| Confluence scorer | `backend/app/analysis/confluence.py` |
| Stops, targets, sizing | `backend/app/analysis/risk.py` · `backend/app/signals/risk_guards.py` |
| Signal generation | `backend/app/services/signal_service.py` |
| Strategy profiles | `backend/app/profiles/{pipeline,setups}.py` |
| Eligibility registry | `backend/app/signals/restrictions.py` |
| Pre-trade gate | `backend/app/trading/risk_engine.py` |
| Paper execution + fill model | `backend/app/broker/paper_broker.py` |
| Charges | `backend/app/trading/fees.py` |
| Live alerts | `backend/app/broker/live_levels.py` |
| Backtest (frozen) | `backend/app/backtest/engine.py` |
| Promotion bar | `backend/app/services/deflated_sharpe.py` · `dsr_control.py` |
| Overlap-corrected t | `backend/app/services/block_bootstrap.py` |
| Ratio conventions | `backend/app/core/ratios.py` |
| Daily report generator | `backend/app/services/daily_report.py` (`make analysis`) |
| This document's probe | `backend/scripts/engine_selectivity_probe.py` |

## Appendix B — conventions a reader must know

| Term | Meaning here |
|---|---|
| **R** | One unit of planned risk = \|entry − stop\| × qty. Every outcome is normalised by it. ₹ figures are not comparable across trades because sizing is risk-first |
| `WINSOR_R = 10.0` | Bound applied wherever R is *averaged* — a 0.23% stop produces a 26R trade that otherwise owns the mean |
| `MAX_RR = 50` | Reporting bound on displayed R:R. **Clamp what you report, never what you decide** — gates read the raw ratio |
| `MAX_R = 9999.999` | Representability bound from the `Numeric(7,3)` excursion columns |
| Undefined ratio | `None`, never `0.0` — "not assessable" and "worst possible" must not collide |
| `is_shadow` | Durable provenance. `status` is a lifecycle field the sweeper overwrites, so any tradeable statistic must filter `is_shadow IS FALSE` |
| Gate modes | `off` (no-op) · `shadow` (verdict computed and recorded, never acted on) · `active` (order path rejects). ⚠ `"off"` is a truthy string in Python — the codebase has a helper for this because it caused a silent bug |
| Cycle 1 / cycle 2 | Cycle 1 is the wide sampler running now; its 30-day clock is **informational**. Cycle 2 is a 45–50 session rehearsal on a heat-capped ₹1 lakh book and is the binding go-live gate |

## Appendix C — reproducing the measurements in this document

```bash
# §4 and §5: factor participation, gate selectivity, level and pivot geometry
cd backend && uv run python scripts/engine_selectivity_probe.py

# §10.2 and §10.3: the confirmation-trigger study
cd backend && uv run python scripts/entry_confirmation_study.py

# §11.1: the take-profit geometry counterfactual (see §11.4 caveat 2 first)
cd backend && uv run python scripts/tp_geometry_study.py

# §11.3 #14: the closing-auction overnight-reversal study
cd backend && uv run python scripts/cas_stage2_study.py

# the daily book report + all shadow sidecars
make analysis
```

⛔ **Never pass `DATABASE_URL` to `pytest`, `make test` or `make check`.** Doing so on
2026-09-07 truncated the development database. The test harness now refuses any
database not named `*_test`.
