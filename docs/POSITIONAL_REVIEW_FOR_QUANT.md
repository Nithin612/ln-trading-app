# Positional signals: selection, entry, levels and outcomes — a technical review

**Audience:** a quantitative reviewer with no prior exposure to this codebase.
**Scope:** the **positional** class only — how a stock becomes a positional signal,
how its entry, stop and target are set, whether anything is checked on the next
trading day, what the class has actually produced, why it loses, and what is left
to try. The swing class and the system-wide view are covered separately in
`docs/SYSTEM_REVIEW_FOR_QUANT.md`; this document assumes none of it and repeats
what it must.

**Status of the numbers.** Every figure is one of three things, and each is
labelled inline:

| Tag | Meaning |
|---|---|
| **[code]** | read directly from the cited source file — a rule, not a result |
| **[corpus]** | measured by `backend/scripts/positional_probe.py` over 238 liquid names, 2019-10-01 → 2026-09-09, by importing and calling the frozen engine |
| **[tape]** | measured from the 40 positional trades preserved in the dated reports under `docs/analysis/` — the live paper record (the database itself was destroyed 2026-09-07, see §2) |

**Generated:** 2026-09-10 · branch `feature/pre-cycle2-hardening`
**Reproduction:** `cd backend && uv run python scripts/positional_probe.py`
(SELECT-only; the frozen engine and the frozen backtest walker are imported and
called, never edited, subclassed or reimplemented).

---

## 0. Executive summary — seven things that decide how to read the rest

1. **"Positional" is not a horizon decision. It is one factor's footprint.**
   A daily-bar signal is classified positional **if and only if** a single bonus
   factor — `MULTIBAGGER_EMA` — scores; otherwise the identical machinery labels it
   swing **[code]**. That one factor then changes the stop rule, the target rule and
   the validity from 5 to 30 trading days. Nothing about the trade's *intended
   holding period* enters the decision.

2. **That factor can only ever vote bullish, and it alone can carry a signal.**
   It is appended to the factor list *only when it fires*, and when it fires it
   always scores exactly **+0.9** **[code]**. Because the confidence denominator
   counts only factors that scored, a panel on which nothing else scores reads
   `0.9 / 0.9 = 90%` confidence. That is not hypothetical: `BUY AFFLE — Multibagger
   Ema, 90% confidence` was minted, filled and held **[tape]**. Consistently,
   **430 of 430** gate-passing positional panels in the corpus are BUY **[corpus]** —
   the class is structurally long-only.

3. **The positional stop has no cap, and three code paths compute it three
   different ways.** `compute_levels` assigns `max_sl_pct = 15.00` for positional
   and then **skips the cap check for exactly that class** **[code]**, so a
   positional stop is never rejected for width — **11.9% of positional stops exceed
   8% of price**, a width no other multi-day class will accept **[corpus]**. Worse,
   `signal_service` passes `ema20_daily`, while `profiles/pipeline.py` and
   `backtest/engine.py` do not and silently fall back to a flat 5% **[code]**. In
   the live record **26 of 40 positional trades carried the flat 5% stop and 14
   carried the real EMA20** **[tape]**.

4. **The real (EMA20) stop is structurally tight, and tight stops are the losing
   cohort.** The factor requires a large green breakout candle, which leaves the
   close just above EMA20: median stop **3.23% of price, 30.1% under 2%**
   **[corpus]**. Sorted by stop width the outcome is monotone — mean R **−0.306**
   under 2% versus **+0.153** at 4–6% **[corpus]** — and that gradient is measured
   *before any cost*. Costs then compound it: round-trip friction in risk units is
   a hyperbola — **cost in R = round-trip bps ÷ (100 × stop-width %)**, an identity
   that follows from risk-first sizing plus the published charge schedule (§8.1) —
   so a 1% stop pays ~0.23R in charges alone before slippage.

5. **Nothing is validated against the next trading day.** The entry price *is*
   the previous session's close; the signal is `active` at 19:15 and tradeable at
   09:15 with no precondition; the "entered the entry zone" alert is a symmetric
   ±0.5% band, so a long falling into its entry fires the same alert as one rising
   through it **[code]**. The obvious remedy — wait for confirmation — was
   pre-registered and measured on two independent samples and **loses
   significantly** (§7.2).

6. **Measured honestly, positional expectancy is indistinguishable from zero.**
   Under the live rule with the stated 30-day horizon: **n=362, mean R −0.102, win
   28.5%**, median R −1.000 **[corpus]**, *gross of all costs*. No block-bootstrap
   interval excludes zero. Enforcing the stated 30-day horizon makes the class
   **worse**, not better (−0.032R → −0.102R), so the horizon label is not carrying
   the returns. On the live book **63% of positional trades never reached +0.5R**
   **[tape]**.

7. **The relabelling itself has never been tested, and the test does not support
   it.** Scoring the identical panels under swing rules instead — pivot stop, 8%
   cap, +6% target, 5-day validity — gives **−0.213R at a 37.4% win rate against
   the positional rules' −0.292R at 16.1%** on the same 155 signals; the paired
   difference is **−0.079R at t = −0.53, not significant** **[corpus]**. The relabel
   changes the stop reference, removes the stop cap and multiplies validity by six,
   on no evidence in either direction.

> **The one-line version.** Positional is a *bullish breakout-from-a-flat-moving-
> average-stack* detector that has been given a 30-day label, an uncapped stop
> computed three different ways, and a target that knows nothing about either. Its
> expectancy is zero within noise, and the largest identified defects are
> correctness defects, not tuning opportunities.

⚠ **One finding here is about the measuring instrument rather than the strategy, and
it travels beyond this class:** the frozen backtest walker records a fill that has
already gapped *through* its stop as an exit **at** the stop — i.e. a loss scored as
roughly **+1R**. It is reproducible in three bars, the live order path is immune to
it, and it flatters exactly the tight-stop cohort this document is about. See
Appendix C #4.

---

## 1. What the system is (the minimum context)

| | |
|---|---|
| Market | NSE / BSE cash equity, India |
| Mode | **Paper only.** There is no live order path — `place_order` is paper, and the Kite client deliberately has no order-placement method |
| Account modelled | ₹1,00,000 capital · 2% risk per trade · ₹3,000 daily-loss circuit breaker |
| Decision cadence | Once nightly on completed daily bars (19:15 IST) |
| Who pulls the trigger | **A human**, from the UI. There is no auto-trader |
| Stack | Python 3.12 / FastAPI / SQLAlchemy async / Celery + Redis / Postgres 16 + TimescaleDB; a Rust parity engine reproducing the Python scorer exactly |
| Governance | `backend/app/analysis/` and `app/backtest/engine.py` are **frozen** at an adjudicated commit. Changes need explicit sign-off, a backtest regression, and regeneration of the Rust parity fixtures |

The freeze matters throughout: several defects below sit **inside** the frozen
boundary, which is why they are measured read-only here rather than fixed.

---

## 2. Data, and what a reviewer must not assume

| Table | State (2026-09-10) | Note |
|---|---|---|
| `ohlcv_1d` | **2,081,473 bars, 2019-10-01 → 2026-09-10** | the only complete price history. **Corporate-action UNADJUSTED** |
| `ohlcv_5m / 15m / 1h` | **empty** | lost 2026-09-07; re-accrues only in real time |
| `signals` / `positions` | **30 / 0** | **the trading record was destroyed on 2026-09-07** and is not recoverable |
| `strategy_profiles` | **0** | same event — the profile definitions are gone from the database |
| `index_ohlcv_1d` · `india_vix_daily` | 48 · 16 rows | broad-index and VIX history not restored |

Three consequences that shape this document:

- **The live positional record cannot be re-derived from the database.** It
  survives only in the dated reports under `docs/analysis/`, which were generated
  while the data existed. Everything tagged **[tape]** is parsed from those
  reports: 40 unique positional trades, each with its plan, its fill, its chase in
  R, and its maximum favourable/adverse excursion in R.
- **`ohlcv_1d` is CA-unadjusted.** A 2026-09-10 audit found 49 unadjusted
  corporate actions in the top-250-liquid universe, 35 of them ≥40% price
  halvings. Every **[corpus]** measurement here therefore **drops any trade whose
  holding span contains a close-to-close move > 25%**; 4 trades were dropped and
  the count is printed by the probe.
- **Any intraday or opening-range hypothesis is currently untestable.**

---

## 3. How a positional signal is generated from the previous day's EOD

### 3.1 The chain (IST)

```
18:40  equities bhavcopy       ->  ohlcv_1d          (self-heals <=21 missed sessions)
19:15  nightly_signal_generation                     <- every tradeable signal is minted here
--- next morning ---
09:15  market opens; the signal is already `active` and carries a Buy button
09:15-15:30  position monitor every 60s; live tick worker raises level alerts
every 5 min  expiry sweeper flips lapsed signals to `expired`
```

`backend/app/celery_app.py`. The nightly job runs **`timeframe="1d"` over all
`is_active` stocks** — 1,322 names, selected by `select(Stock).where(is_active)`
with no liquidity, price, market-cap or index-membership filter **[code]**.

The `1w` timeframe is the *only other* route to a positional classification, and it
**is never run**: the nightly job is 1d-only, and the sole other generation entry
point (`live_signal_generation`) is dispatched from `tick_consumer` — the dormant v1
tick path, gated off by default behind `LIVE_SIGNAL_DISPATCH_ENABLED` — and carries
intraday candle timeframes **[code]**. Therefore:

> **Positional ⇔ the multibagger factor fired on a daily bar.** There is no other
> way to produce one.

### 3.2 The window and the no-look-ahead rule

`_load_candles` takes the **last 300 completed daily candles** (`is_complete =
true`); fewer than 50 → no signal **[code]**. Indicators are computed on candle N
and the signal is valid from N+1. Forming candles never enter a committed signal.
This is structural, and it is respected on the positional path.

### 3.3 The factor that defines the class

`app/analysis/indicators/ema.py::multibagger_ema_factor` — weight **10**, a
*bonus* factor evaluated only on `1d`:

```python
proximity_pct = abs(ema20 - ema200) / ema200 * 100
if proximity_pct > 2.0:            -> 0.0   "20 EMA not close to 200 EMA"
body_now  = abs(close - open)
avg_body  = mean(|close-open|) over the last 20 bars
breakout  = close > open and body_now >= 1.5 * avg_body
if breakout:                       -> +0.9  "Multibagger setup"
else:                              -> 0.0   "EMAs converging but no breakout candle"
```

Two properties decide almost everything downstream:

- **It is appended only when it fires.** `confluence.py` evaluates it and adds it
  to the factor list *only if* `score > 0` **[code]**. So it is never a zero in the
  confidence denominator — it can only ever *add*.
- **Its score is a constant +0.9.** There is no gradation, and there is no
  negative branch. A bearish equivalent does not exist.

Together these mean the factor is a pure, one-directional, fixed-size bullish
bonus that additionally relabels the trade's class, stop rule, target rule and
validity.

### 3.4 Classification

`app/signals/classifier.py` **[code]** — classification is a pure function of
timeframe plus that one flag:

| Timeframe | Class | Validity |
|---|---|---|
| 1m / 5m | scalp | 30 minutes |
| 15m / 1h | intraday | 15:15 IST same session |
| **1d, multibagger did NOT fire** | **swing** | **5 trading days** |
| **1d, multibagger fired** | **positional** | **30 trading days** |
| 1w (never run) | positional | 30 trading days |

Validity is computed in real NSE trading days through the holiday calendar
(`market_calendar.validity_offset_days`) — calendar-day arithmetic would be a bug
and is not used **[code]**.

---

## 4. How marks are given — the scoring model

### 4.1 The factor set

`app/analysis/confluence.py::run_all_factors` runs 14 factors plus the
conditional bonus. Each returns a score in **[−1, +1]**, where **0.0 means "not
applicable"** — an abstention, not a vote against.

| Factor | Weight | What it tests |
|---|---:|---|
| Candlestick pattern (best of 8, not summed) | 15 | Marubozu / Hammer / Hanging Man / Shooting Star / Engulfing / Harami / Piercing–Dark Cloud / Morning–Evening Star |
| **Dow trend structure** | **20** | higher-highs+higher-lows over 20 bars — **see §5.3, it cannot fire on daily** |
| EMA cross (20/50) | 15 | golden-cross-lite |
| Price vs EMA (close > EMA50 > EMA200) | 15 | trend alignment |
| RSI level (14) | 10 | RSI 30–50 and rising |
| RSI divergence | 10 | price lower low, RSI higher low |
| MACD cross (12,26,9) | 10 | line crosses signal |
| MACD histogram | 10 | histogram rising toward zero |
| Volume | 10 | ≥1.5× the 20-period average — **confirmer only** |
| Bollinger Bands | 10 | touch outside then close back inside |
| Support/resistance + demand/supply zones | 10 | proximity to a tested level, or a body breakout on 1.5× volume |
| Fibonacci retracement | 5 | bounce from 0.5 / 0.618 / 0.786 |
| ADX + DI | 5 | ADX > 25 with directional agreement |
| FII/DII institutional flow | 5 | 5-day cumulative market flows + stock block/bulk deals |
| **Multibagger EMA setup (1d only)** | **+10 bonus** | **the factor that makes a signal positional** |

Two design details worth flagging before the arithmetic:

- **Volume cannot vote, only second.** After all factors run, a positive volume
  score is rewritten to ±0.5 to match the sign of everything else, or to 0 if the
  rest nets to zero **[code]**. It can never fire alone and never pushes against
  the others.
- **The FII/DII market-wide component is cross-sectionally constant.** On a given
  night every stock receives the *same* ±0.5 flow score; only the block-deal term
  is name-specific **[code]**. A constant cannot discriminate between candidates —
  it can only tilt the whole night in one direction. It nonetheless appears in
  signal headlines as though it were evidence about the stock, and it does so on
  **22% of positional trades** **[tape]**.

### 4.2 The scorer, and the decision that matters most

```python
total_weighted = Σ  weight_i · score_i                 # over ALL factors
total_weight   = Σ  weight_i  where score_i ≠ 0        # ONLY the factors that scored
normalized     = total_weighted / total_weight         # in [-1, +1]
confidence_pct = int(|normalized| × 100)               # truncation, not rounding
```

`app/analysis/confluence.py:159-166` **[code]**.

**Abstention is free.** A factor that does not apply is removed from the
denominator rather than counted as a zero. One factor scoring 0.8 with fourteen
abstentions yields 80% confidence.

For the positional class this is not a subtlety, it is the mechanism:

> `MULTIBAGGER_EMA` contributes `10 × 0.9 = 9` to the numerator and `10` to the
> denominator. **Alone, it produces exactly `9/10 = 90%` confidence.**

That is the highest confidence bucket the system has, produced by a single
indicator — and it is reached in practice. The signal
**`BUY AFFLE — Multibagger Ema, 90% confidence. Entry ₹1677.3, SL ₹1594.71,
TP ₹1928.90, Qty 90`** was minted, filled at ₹1,672.15 and held **[tape]**. Note
what the headline shows and does not show: the factor list is the **top three
scoring factors**, and only one is printed, so exactly one factor scored; the
`Qty 90` is the display quantity at the ₹5,00,000 *sampling* scale (§6.4), while
the order path independently sized the real position at ~25 shares — ₹41,800 of
notional carrying ₹1,936 of risk, 0.97× the ₹2,000 budget. Across the corpus the
multibagger factor is the **entire** confluence at the 90th percentile of
positional panels, and its median share is 39% **[corpus]**.

### 4.3 The gate

Base threshold 70, adjusted by trend strength **[code]**:

| ADX(14) | Effective threshold |
|---|---|
| < 20 (weak trend) | **75** |
| 20 – 40 | 70 |
| > 40 (strong trend) | **65** |

The lowered branch is visible in the live record: `BUY KOTHARIPET — Multibagger
Ema, Fii Dii Flow, Adx, **68% confidence**` was minted and traded **[tape]** — a
sub-70 signal, legitimately, via the strong-ADX branch.

### 4.4 Idempotency

`_has_active_signal` blocks a second signal for the same (stock, timeframe,
direction) while one is unexpired **[code]**. There is no "supersede on a stronger
score". Because positional validity is 30 trading days, **one positional signal
suppresses re-entry in that name and direction for six calendar weeks.**

---

## 5. What the positional gate actually selects — measured

Method **[corpus]**: 238 liquid names with ≥340 daily bars, 2019-10-01 →
2026-09-09. The multibagger breakout condition is screened vectorised (it depends
only on the last 20 bars, so it is exact), then every candidate bar is scored by
the real frozen engine on its own trailing 300-bar window. This finds **every**
positional panel in the corpus, not a sample.

### 5.1 Population

| | |
|---|---:|
| bars meeting the full multibagger condition | **1,654** |
| of those, clearing the ≥70% gate | **430 (26.0%)** |
| direction split | **430 BUY / 0 SELL** |
| confidence | p10 71 · **median 77** · p90 90 |
| scoring factors per signal | p10 **1** · **median 3** · p90 5 |

**The class is long-only in practice.** Not by rule — a SELL positional is
representable — but the +0.9 bonus has to be outweighed by the rest of the panel
*and* the panel still has to clear the gate, and in 1,654 opportunities that never
happened. A positional book is therefore an unhedged long book.

### 5.2 Which factors are actually underneath a positional signal

The signal headline shows only the **top three factors by |score|**, so it cannot
answer this **[code]**; the probe counts every non-zero score. The right-hand
column is the same measurement over 4,511 *general* daily panels, from
`docs/SYSTEM_REVIEW_FOR_QUANT.md` §4.1.

| Factor | Fires on positional panels | Fires on all daily panels |
|---|---:|---:|
| MULTIBAGGER_EMA | **100.0%** | 1.4% |
| SR_ZONE | 55.8% | 25.5% |
| VOLUME | 37.7% | 15.0% |
| BULLISH_ENGULFING | 25.8% | 3.6% |
| MACD_CROSS | 18.8% | 8.7% |
| ADX | 18.4% | 38.9% |
| **PRICE_VS_EMA** | **9.1%** | **63.4%** |
| RSI_LEVEL | 8.4% | 35.7% |
| MACD_HISTOGRAM | 8.1% | 46.9% |
| MORNING_STAR | 7.0% | <2.5% |
| FIBONACCI | 4.7% | 6.3% |
| EMA_CROSS | 3.5% | 1.9% |
| BBANDS | 0.5% | 5.8% |
| RSI_DIVERGENCE | 0.2% | 7.0% |
| **DOW_TREND** | **0.0%** | 0.07% |

**The `PRICE_VS_EMA` collapse is the most informative number in this document.**
That factor tests `close > EMA50 > EMA200` — trend alignment. It fires on 63.4% of
all daily panels and on **9.1%** of positional panels. The reason is structural
rather than statistical: the multibagger condition *requires* `|EMA20 − EMA200| ≤
2% of EMA200`, i.e. a **converged, flat moving-average stack**, which is close to
the negation of a separated trend stack.

> The positional class systematically selects the names with the *least* trend
> structure, and then holds them for 30 trading days on a trend-following premise.

### 5.3 …and the one factor that was supposed to supply trend structure is dead

`run_all_factors` calls `dow_trend_factor(candles, lookback=20, swing_n=5)` for
every non-intraday timeframe. Inside a 20-bar window a pivot at width n=5 must be
the maximum of an 11-bar window, so it can only sit at index 5…14; any two such
indices differ by at most 9 < 11, so their windows overlap and both can be the
maximum only on an exact float tie. The function requires **two** swing highs
**and two** swing lows before it will score. It therefore returns
`0.0 — "Not enough swing points"` on essentially every daily window: **3 non-zero
results in 4,511 general panels, and 0 in 430 positional panels** **[corpus]**.

⚠ This is a **specification** defect, not an implementation bug: `SIGNAL_ENGINE.md`
§2.4 specifies both the 20-bar lookback and n=5, and the code implements exactly
that. The spec file is hook-protected; **nothing has been changed**.

**Net effect for positional:** the heaviest factor in the specification (weight 20,
described as "the macro context") contributes nothing, *and* the class's defining
condition actively selects against the only surviving trend factor. A 30-trading-day
trade is opened with no trend input at all.

### 5.4 What the one active gate does to this

Exactly one selection gate is `active` on the order path — `entry_diversity`,
which enforces the stated hard rule "never a single indicator" (≥2 scoring
factors, and no factor above 90% of the confluence) **[code, verified against the
running configuration 2026-09-10]**. Applied to the corpus:

| | |
|---|---:|
| positional signals with < 2 scoring factors | 80 (18.6%) |
| positional signals with one factor > 90% of the confluence | 80 (18.6%) — **the same 80** |
| **would be blocked at order time** | **80 (18.6%)** |

The two limbs coincide because a lone scoring factor is by definition 100% of the
confluence. So **roughly one positional signal in five is a single-indicator
signal**, and the AFFLE trade in §4.2 is what that looks like when it reaches the
book. The gate now blocks it; it was added after that trade.

### 5.5 Sector, index and macro context — none of it reaches the decision

The question "do you do sector analysis?" has a short answer for this class:
**no, and currently it could not be done even if it were wired.**

| Input | State |
|---|---|
| Sector relative strength (`app/signals/sector_rs.py`) | exists; **shadow**; never active |
| Market regime — index 200-DMA + India VIX (`app/signals/market_regime.py`) | exists; **shadow**; standing instruction is *do not act on it* (it would block 74% of the book and its blocked set has the **higher** win rate) |
| `stocks.sector` | populated on 500 rows overall, but on only **165 of the 1,322 active** names — 12.5% of the tradeable universe |
| `index_ohlcv_1d` | **48 rows across 3 indices, 2026-08-19 → 2026-09-09** — three weeks of three broad indices |
| `india_vix_daily` | **16 rows** (was 784 sessions before 2026-09-07) |
| Fundamentals (`market_cap_cr`) | **0 rows populated.** No writer exists; a free source was identified in a 2026-09-08 spike and the build deferred for want of a consumer |
| News veto | deferred — none of its three preconditions holds (0 of 322 rating rows carry a direction; no forward earnings calendar; the existing guard has never fired) |

Two consequences specific to positional:

- **There is no sector benchmark to compute relative strength against.** Only three
  *broad* indices were ever ingested, and only three weeks of them survive. Sector
  RS is not merely inactive — it is currently unmeasurable.
- **The class is the one that would benefit most from a market filter, and has
  none.** Positional is long-only (§5.1) and holds for six calendar weeks, so it is
  maximally exposed to a market downtrend and cannot express the opposite view. The
  overlay built for exactly this — the 200-DMA market-regime gate — is in shadow,
  carries a do-not-act instruction, and cannot presently be evaluated because the
  index history it needs is 48 rows.

So every claim about a positional signal is a claim about a **single name in
isolation**: no sector, no index, no breadth, no fundamentals, no earnings calendar,
no news.

---

## 6. Levels: entry, stop, target, R:R and size

### 6.1 The rules as written

`app/analysis/risk.py::compute_levels`, wrapped by
`app/signals/risk_guards.py::safe_levels` **[code]**:

| Class | Stop loss | Max stop | Take profit |
|---|---|---|---|
| scalp | 0.30% from entry | 0.50% | ±0.45% (1:1.5) |
| intraday | last pivot swing low/high | 0.50% | 2× the risk distance (1:2) |
| swing | last pivot swing low/high | **8.00%** | entry ± 6% (flat) |
| **positional** | **EMA20 (daily)** | **none — see 6.2** | **entry ± 15% (flat)** |

```python
elif classification == "positional":
    max_sl_pct = Decimal("15.00")            # trailing; no hard cap
    if direction == "BUY":
        sl = ema20_daily if ema20_daily is not None else entry - _pct(entry, 5)
        tp = entry + _pct(entry, 15)
    else:
        sl = ema20_daily if ema20_daily is not None else entry + _pct(entry, 5)
        tp = entry - _pct(entry, 15)
...
if classification != "positional":           # <-- the cap check, skipped for positional
    if abs(entry - sl) / entry * 100 > max_sl_pct:
        return None
```

**Entry price = the previous session's close**
(`signal_service.py:236`, `Decimal(str(candles["close"].iloc[-1]))`) **[code]**.
Stop, target, R:R and quantity are all computed from a price that, by definition,
will not be available again.

Three things a reviewer should register immediately:

- **Support/resistance never sets a level.** S/R enters only as a *scoring* factor
  (`SR_ZONE`, present on 56.1% of positional signals **[corpus]**). It influences
  *whether* the signal fires, never *where* the stop or the target goes. For
  positional, the pivot swing levels are passed into `compute_levels` and then
  **ignored** — only `ema20_daily` is read.
- **`max_sl_pct = 15.00` is assigned and never used.** The cap check is explicitly
  skipped for positional. The comment says "trailing; no hard cap"; there is no
  trailing mechanism at signal-generation time. The variable is dead.
- **The target is an absolute percentage that knows nothing about the stop.** So
  R:R is an accident of how far EMA20 happens to sit — the same structural defect
  documented system-wide, but with a different and much wider dispersion here.

`safe_levels` adds the only rejection positional gets: a stop on the **wrong side
of, or equal to,** the entry is discarded rather than clamped **[code]**. For a
long that means EMA20 above the close, which happens on **7.7%** of positional
panels **[corpus]**.

### 6.2 ⚠ Three code paths, three different positional stops

This is a correctness defect, and it is load-bearing for every number anyone has
ever quoted about this class.

| Call site | Passes `ema20_daily`? | Resulting stop | Resulting R:R |
|---|---|---|---|
| `services/signal_service.py:245` and `:434` (the nightly + live minters) | **yes** | **EMA20** | 15% ÷ (distance to EMA20) — variable |
| `profiles/pipeline.py:367` (strategy-profile minter) | **no** | **flat 5%** | **exactly 3.00** |
| `backtest/engine.py:322` (the frozen backtest) | **no** | **flat 5%** | **exactly 3.00** |

Nothing about the *signal* differs — only which function minted it. The live
record shows both populations side by side **[tape]**:

| Stop rule | Trades | Stop width | Planned R:R |
|---|---:|---|---|
| flat 5% (profile path) | **26 of 40** | exactly 5.00% | exactly 3.00 |
| EMA20 (signal_service path) | **14 of 40** | 0.93% – 13.43%, median 4.61% | 1.12 – 16.07 |

Two consequences:

1. **The backtest does not test the live positional rule.** It tests a flat 5%
   stop that the primary minting path never produces. Any backtest statistic about
   positional describes a strategy that was not traded.
2. **It does not test the live positional *horizon* either.** `_simulate_trade`
   walks forward `for i in range(fill_idx, len(candles))` — **to the end of the
   data**, with no validity cap **[code]**. A "30-trading-day" positional trade is
   backtested as "hold until ±15% or the stop, forever". Separately, in live
   operation nothing force-closes a position at expiry either: the *signal* expires
   and `position_health` merely emits the advisory *"Held past the signal's validity
   window — the setup has expired"* **[code]**.

### 6.3 The geometry the live rule actually produces

**[corpus]**, 430 gate-passing positional signals, both rules evaluated on the
*same* panels:

| | EMA20 rule (live) | flat-5% rule (profiles + backtest) |
|---|---|---|
| rejected, stop wrong side of entry | 33 (7.7%) | 0 |
| stop width, % of price | p10 **0.88** · median **3.23** · p90 8.29 · max **15.93** | 5.00 exactly |
| stops under 2% of price | **30.1%** | 0% |
| stops wider than 8% of price (the *swing* class's cap) | **11.9%** | 0% |
| R:R | p10 1.80 · median **4.64** · p90 **16.95** | **3.00** exactly |
| R:R below 1.0 | 0.5% | 0% |
| notional at ₹1L / 2% risk | median ₹56,952 · p90 ₹222,584 | ₹40,000 |
| **over the 1.0× notional cap ⇒ rejected at order time** | **28.4%** | 0% |

Read that table as one mechanism. The factor demands a large green candle, which
leaves the close just above a flattened EMA20 — so the stop is *near*, the reported
R:R is *spectacular* (median 4.64, p90 16.95), and risk-first sizing turns the near
stop into a large position: quantity is `risk budget ÷ risk-per-share`, so

> **notional = ₹2,00,000 ÷ (stop width in %)** — independent of price.

A 0.88% stop is therefore a ₹2.27 lakh position on a ₹1 lakh account. That is why
**28.4% of positional signals now exceed the per-position notional cap and are
rejected at order time**, and why the four positional signals surviving in the
database today carry stops of 0.59%, 1.04%, 1.76% and 4.92% — the 0.59% one implies
₹3.39 lakh of notional **[code, live query 2026-09-10]**.

**A high reported R:R here is a symptom of a near stop, not of a good trade.** That
is the same reversal already established system-wide from the opposite direction
(the R:R ≥ 1 floor was promoted, then reverted within 24 hours because the blocked
cohort — wide stops — was the only profitable one).

### 6.4 Position sizing

```
qty = floor(capital × risk_pct / 100 / |entry − stop_loss|)
if ATR(14) > 3% of price:  qty = qty × 3 // 4        # volatility regime
if qty == 0: reject
```

`app/analysis/risk.py` **[code]**. `risk_pct` is a whole percent (2.0 = 2%) — the
function divides by 100 itself.

Two scales coexist and are easy to confuse:

- **Signal generation sizes against ₹5,00,000**, hardcoded in
  `tasks/signal_tasks.py::_default_risk_params` **[code]**. `signals.suggested_qty`
  is a display number at the sampling scale.
- **The order path re-sizes from the actual fill at the user's own capital**
  (`paper_broker.size_for_fill`), direction-aware, sizing against the *remaining*
  budget when adding to an existing position.

Risk-first sizing bounds a trade's **risk** but not its **size** — which is exactly
what the notional cap exists to catch, and what positional trips more than any
other class.

---

## 7. Is the signal validated against the next trading day?

This is the question the class is most often assumed to answer, so it is worth
stating flatly.

### 7.1 Next-day validation of a positional signal: **no**

A signal minted at 19:15 IST is `status = 'active'` immediately. At 09:15 the next
morning it is listed, it carries a Buy button, and the order path will fill it.
**No price action is required to occur first** **[code]**. There is no "confirm the
breakout held", no gap filter, no opening-range check, no re-scoring on the new
bar. The 30-trading-day clock starts from the signal, not from any trigger.

What exists instead is an **alert layer** (`app/broker/live_levels.py`), fed by the
live tick worker **[code]**:

| Alert | Definition |
|---|---|
| entry zone | live price enters `entry × (1 ± 0.5%)` — **a symmetric band** |
| SL / TP near | within 25 bps of the level |
| SL / TP touch | a direction-aware cross at the exact level |
| PDH / PDL | direction-aware crosses of the previous day's extremes |

⚠ **The entry-zone alert is direction-blind.** Since every positional signal is a
BUY (§5.1), a name *falling* into its entry band raises exactly the same "entered
zone" alert as one *rising* through it — the setup failing is indistinguishable
from the setup triggering. The direction-aware `cross_up` / `cross_down` machinery
already exists in the same file for PDH/PDL and is simply not wired to the entry
zone. This is the one unambiguous correctness fix on the list; it is **not built**,
and it is explicitly **not a P&L claim**.

### 7.2 Should a confirmation trigger be added? Measured: **no**

The natural remedy — do not buy yesterday's close, buy only when the market trades
through the prior bar's high — was pre-registered and tested on two independent
samples in September 2026. ⚠ Both samples are **all-class** (they are dominated by
swing); the study has **not** been re-run on the positional subset, and doing so is
listed as an option in §11.

**Sample A — market-wide base rate, 108,506 stock-days.** Selection is real
(signals average +1.018% next-day against −0.915% for non-signals) but it is
**fully priced into the trigger**: once the entry moves to the trigger price and
returns are differenced with an overlap-corrected t, the confirmed-entry rule is
**significantly worse at every horizon (t −2.94 … −3.51)**.

**Sample B — 1,975 of the system's own minted signals.** Decomposed on the
intersection, the two effects point in opposite directions and only one is
significant:

| window | selection benefit | fill cost (paired ΔR) | t(ΔR) |
|---|---:|---:|---:|
| 1d | +0.239 | **−0.226** | **−10.62** |
| 3d | +0.248 | **−0.254** | **−12.46** |
| 5d | +0.253 | **−0.264** | **−12.84** |

**The benefit never reaches t = 0.4; the cost sits at t ≈ −10 to −13.** A
structural explanation exists — Brooks' trader's equation: whenever one of {risk,
reward, probability} is unusually good, the others are worse. Waiting for
confirmation buys probability and pays for it in risk.

### 7.3 When does confirmation arrive anyway?

Of 1,975 signals, measured from the bar the engine fills on: **60% confirm on day
+1, 70% by +2, 80% by +5, and 20% never confirm within five sessions.** For a
5-day swing that is a hard constraint. For a 30-trading-day positional it means the
validity window is long enough that "never confirmed" is rarely the binding issue —
the position is simply opened before the question is asked.

### 7.4 How a *rule* gets promoted (the governance answer)

Distinct from validating a signal: how does a shadow gate or a retune go live?

- Every candidate runs in **shadow** on the real schedule, its verdicts stamped on
  orders and accrued in a per-day sidecar report.
- Promotion requires the **deflated-Sharpe bar** (`app/services/deflated_sharpe.py`),
  which corrects for the number of hypotheses tried. The instrument was itself
  validated against a known null *and* a planted edge: it rejects noise (1.10%
  false-positive on best-of-20 zero-edge selections against a 5% design allowance)
  and detects real edges (80% power at a true per-trade Sharpe of 0.52).
- **Restated as a plain t-statistic the bar demands t ≈ 3.6, and the hurdle is flat
  in n** (3.76 at n=30, 3.55 at n=1000). Two consequences: accruing more data never
  lowers the bar; and power is near zero between t ≈ 2.6 and 3.5, so **failing is
  not evidence of no edge** — the t is recorded, not just the verdict.
- Standing rule after two reversals in two days: **no flip on an argument.** Check
  the count, check the sign survives trimming the tail, and check the partition is
  not a proxy for something else.

### 7.5 What the order path checks (none of it is positional-aware)

`POST /api/v1/trading/orders` → `risk_engine.check_pre_trade` →
`signals/restrictions.py` (one ordered registry, walked by both the order path and
the display path so the two cannot drift) → `paper_broker.place_paper_order`.
Modes read from the running configuration on 2026-09-10 **[code]**:

| Rule | Mode | Note |
|---|---|---|
| kill switch · daily-loss circuit breaker (₹3,000, max 5 entries/day) | always on | breaker is not disableable |
| signal exists and `status = 'active'` | always | shadow and expired signals untradeable |
| off-market entry | always | rejects outside 09:15–15:30 IST |
| **entry diversity (≥2 factors, none > 90%)** | **ACTIVE** | the only active selection gate — blocks **18.6%** of positional (§5.4) |
| regime (ADX 20–25) · circuit-band · stop-too-tight · R:R floor · sector RS · market regime · liquidity · anti-chase | **shadow** | eight overlays, none acting |
| through-stop rejection | always | broker-level |
| **per-position notional cap (1.0× capital)** | **ACTIVE** | rejects **28.4%** of positional (§6.3) |
| max concurrent positions (3) · portfolio heat cap (6%) | **off** | built; flip at the cycle-2 reset |

> **No rule in the registry is classification-aware.** A 30-trading-day positional
> trade is gated exactly like a 5-day swing. The only two class-aware pieces of
> machinery in the system are the profit-lock ratchet preset
> (`profit_lock.CLASS_PARAMS`: positional arms at 1.0R with a wider giveback taper)
> and the ATR timeframe selector **[code]**.

---

## 8. Execution: fills, charges, and why the stop width sets the cost

**Fills are market orders at the live traded price**, haircut by a model that fails
open at every step (`paper_broker.simulate_fill`) **[code]**:

```
adverse_bps = clamp( half_spread + top_of_book_impact + participation ,
                     floor = 2.0 bps , ceiling = 500 bps )
participation_bps = 0.1 × (order_value / median_daily_traded_value)² × 10,000
```

**82% of live NSE books are wider than the flat 2 bps floor** — which is why paper
P&L before and after 2026-08-17 is not comparable and the paper clock was reset.
Tick rounding is directional (a buy ceils, a sell floors) because 27.2% of real
closes sit off the ₹0.05 grid. Unrealised marks route through the same model on the
exit side, so a long marks toward the bid.

**Charges** (`app/trading/fees.py`, Zerodha equity **delivery** — which is what
positional is, by `product_for_classification` **[code]**): STT 0.100% both legs ·
stamp duty 0.015% buy · exchange 0.00297% both legs · SEBI ₹10/crore · GST 18% on
the fee components · **DP charge ₹15.34 flat on the sell leg**.

### 8.1 Cost in R is a hyperbola in stop width — and positional sits at the wrong end

Because sizing is risk-first, `notional = risk budget ÷ (stop width %) × 100`, and
the algebra collapses to something independent of capital and of price:

> **cost in R = round-trip bps ÷ (100 × stop-width %)**

Computed with the real schedule at ₹1L capital / 2% risk (1R = ₹2,000) **[code]**:

| Stop width | Notional | Round-trip charges | bps | **Charges in R** | + measured slippage¹ | Notional cap |
|---:|---:|---:|---:|---:|---:|---|
| 0.59% | ₹3,38,500 | ₹768 | 22.7 | **0.384R** | ~0.86R | **rejected** |
| 1.00% | ₹2,00,000 | ₹460 | 23.0 | 0.230R | ~0.51R | **rejected** |
| **3.23%** (median EMA20) | ₹61,500 | ₹152 | 24.7 | **0.076R** | ~0.16R | ok |
| 5.00% (flat rule) | ₹40,000 | ₹104 | 26.1 | 0.052R | ~0.11R | ok |
| 8.29% (p90 EMA20) | ₹24,000 | ₹69 | 28.6 | 0.034R | ~0.07R | ok |

¹ Slippage basis: the only day with published fill telemetry (2026-09-04, 9 fills,
all priced off a live book) had a **median 14.0 bps per leg**, mean 25.2, range
2.0–57.8. One day of nine fills is a thin basis and the range spans an order of
magnitude — which is why the charges-only column is given beside it: that one needs
no assumption at all and already makes the point.

⚠ **The backtest applies none of this.** `_simulate_trade` fills at the open of
candle N+1 with **no slippage, no brokerage, no STT and no DP charge** **[code]**.
Every **[corpus]** outcome in §9 is therefore *gross*, and the honest cost load for
the tight-stop cohort is the left-hand end of that table.

---

## 9. What the positional class has actually produced

### 9.1 ⚠ Read this before any number in this section

The live trading record was destroyed on 2026-09-07 (§2). What survives in the
dated reports is the **per-trade tape for positions that were open on each report
day** — a closed trade drops out of that section entirely, and no per-trade exit
price is preserved anywhere. Of the 40 positional trades reconstructable from the
tape, **39 are last seen `open`** **[tape]**.

> **There is therefore no realised per-trade P&L record for the positional class.**
> Live evidence below is *excursion* evidence (how far each position ran in its
> favour and against it, in R, while it was observable), truncated at each trade's
> last appearance — which understates both MFE and MAE for the trades that lived
> longer. Outcome evidence comes from the corpus study, which is gross of costs.

Neither source is the same thing as a realised, cost-bearing track record. The
system does not have one for this class.

### 9.2 Corpus outcomes — the frozen walker, gross of costs

**[corpus]** 430 gate-passing positional signals, filled at the open of the next
bar by `BacktestEngine._simulate_trade` (imported and called, not reimplemented),
CA-contaminated holding spans dropped (4 trades), R winsorized at 10, and **6 trades
excluded whose fill had already gapped through the stop** — the live broker rejects
those outright and the frozen walker mis-scores them as winners (Appendix C #4):

| Variant | n | mean R | median R | win | total R |
|---|---:|---:|---:|---:|---:|
| **EMA20 stop (the live rule), 30-day horizon** | **362** | **−0.102** | −1.000 | **28.5%** | −37.0 |
| EMA20 stop, no horizon (frozen default) | 385 | −0.032 | −1.000 | 23.4% | −12.2 |
| flat-5% stop (profiles + backtest), 30-day horizon | 394 | +0.033 | −1.000 | 34.8% | +12.9 |
| flat-5% stop, no horizon | 424 | +0.089 | −1.000 | 28.8% | +37.9 |
| *swing baseline, same names, strided sample* | *85* | *+0.221* | *−1.000* | *44.7%* | *+18.8* |

Block bootstrap (2,000 resamples, moving blocks) — **no sign survives**:

| Series | observed Sharpe | 90% interval | Sharpe ≤ 0 in |
|---|---:|---|---:|
| positional, EMA20 | −0.011 | [−0.120, +0.076] | 57% |
| positional, flat-5% | +0.049 | [−0.053, +0.144] | 21% |
| swing baseline | +0.125 | [−0.064, +0.280] | 12% |

Four things follow.

- **Median R is −1.000 in every variant.** More than half of positional trades
  reach their stop. The distribution is a long left mass with a thin right tail —
  which is what a 15% target against a 3% stop must produce, and why the win rate
  (29–35%) and the mean can disagree in sign.
- **The class is indistinguishable from zero, gross.** Once §8.1's cost load is
  applied — 0.076R at the median stop, 0.23–0.38R at the tight end — the live-rule
  variant is clearly negative.
- **Positional underperforms swing on the same universe.** Treat the baseline row
  as indicative only — it is a strided sample (n=85) of *different* panels and its
  own interval straddles zero. The like-for-like comparison, the same panels under
  both rule sets, is §9.6; the larger authority for the swing/all-class side is the
  1,975-trade backtest in `SYSTEM_REVIEW_FOR_QUANT.md` §11.1 (mean R −0.065,
  t −1.94, also gross).
- **Enforcing the stated 30-day horizon makes both rules *worse*** (EMA20 −0.032 →
  −0.102; flat-5% +0.089 → +0.033). The uncapped variant is not a realistic
  product — it holds until ±15% or the stop, however many years that takes — but
  the comparison says plainly that the 30-day label is not carrying the returns.
  Whatever the class earns, it earns after its own validity window has closed.

### 9.3 The two stop rules, compared the right way (paired)

The two rules were evaluated on **identical panels**, so the comparison can be
paired rather than pooled **[corpus]**:

| | |
|---|---|
| paired signals | 380 |
| mean ΔR (EMA20 − flat-5%) | **−0.120** |
| median ΔR | **+0.000** |
| t | **−1.47** |

**Verdict: not significant.** The point estimate favours the flat 5% stop, and the
median difference is exactly zero — on half the panels the two rules produce the
same outcome. This is the honest reading: *the three-way divergence in §6.2 is a
correctness defect, not a demonstrated P&L defect.* It must be fixed because the
backtest currently validates a rule the live path does not use — not because one
rule has been shown to make money.

### 9.4 Stop width is the strongest gradient in the class

**[corpus]**, EMA20 rule, gross of costs:

| Stop width (% of price) | n | mean R | win |
|---|---:|---:|---:|
| 0 – 2% | 114 | **−0.306** | **9.6%** |
| 2 – 4% | 113 | −0.036 | 18.6% |
| 4 – 6% | 68 | +0.153 | 32.4% |
| 6 – 10% | 74 | +0.103 | 35.1% |
| 10%+ | 16 | **+0.543** | **62.5%** |

Monotone, and large: the tightest bucket loses **0.306R per trade at a 9.6% win
rate** while the widest gains half an R at 62.5%. ⚠ **This gradient is measured with zero costs applied**,
so it is not a cost artefact — it is geometry and probability. Costs then push the
same direction (§8.1), so the true spread is wider than the table shows.

This independently reproduces three findings the project already had, from three
different directions: the R:R ≥ 1 floor was reverted because the blocked cohort
(wide stops) was the only profitable one; the horizon study found stops narrower
than one average daily range recover 8/8 times but still realise −1.45R; and the
`sl_atr` shadow gate flags exactly this population. **Positional is the class most
exposed to it**, because its stop rule structurally produces near stops (30% under
2% of price).

### 9.5 Live behaviour — 40 positional trades, excursions only

**[tape]**, unique by symbol and open time, truncated at last appearance:

| | Positional (n=40) | Swing (n=67) |
|---|---:|---:|
| direction | **100% LONG** | mixed |
| confidence, median | 76% | 76% |
| planned R:R, median | **3.00** | 1.10 |
| planned stop width, median | 5.00% | 5.51% |
| stop width, max | **13.43%** | 7.67% (the 8% cap) |
| reached **+1R** | 8/38 = **21%** | 12% |
| **never reached +0.5R** | 24/38 = **63%** | 73% |
| MFE, median | +0.261R | +0.258R |
| MAE, median | −0.454R | −0.304R |
| chased > 0.33R past the signal entry | 4/40 = 10% | 10% |
| chase, median | +0.096R | +0.079R |

The headline R:R of 3.00 versus swing's 1.10 is the flat-5%-fallback population
(§6.2) — a number produced by a code path, not by a market judgement. What the
market actually delivered is the row below it: **63% of positional trades never ran
half an R in their favour**, and the median position spent more time under water
(−0.454R) than it ever spent in profit (+0.261R).

For context, the all-class paper book at its last clean measurement: **106 closed
positions, −₹12,369 realised, expectancy −0.303R over 99 resolved trades, 37.5%
win, beta +0.92 with per-trade alpha +0.0010**, and it lost to buy-and-hold on
NIFTY50 by 13.42 percentage points over 2026-08-17 → 09-04. Those figures are
**all-class** and no class split survives.

### 9.6 Should the class exist? The same panels scored under swing rules

Because positional is only a relabelling (§3.4), the counterfactual is directly
computable: take the identical 430 panels and apply the **swing** rule set — pivot
swing-low stop, 8% cap, +6% flat target, 5-trading-day validity — instead
**[corpus]**.

| | |
|---|---:|
| positional panels the swing rule set would **reject outright** | **234 of 430 (54.4%)** |
| …of which by the 8% stop cap or a wrong-side/degenerate pivot | all of them |

⚠ That attrition is **not** special to positional: the general daily population
loses 52.6% at the same stage (`SYSTEM_REVIEW_FOR_QUANT.md` §5.2). Positional
panels are ordinary in pivot geometry; what differs is that the positional branch
**ignores the pivot entirely** and substitutes EMA20, with no cap.

On the 155 panels where both rule sets produce a tradeable signal, each run under
its own validity window:

| Rule set | n | mean R | median R | win | total R |
|---|---:|---:|---:|---:|---:|
| **as POSITIONAL** (EMA20 stop, +15%, 30 days) | 155 | **−0.292** | −1.000 | **16.1%** | −45.3 |
| **as SWING** (pivot stop, +6%, 5 days) | 155 | **−0.213** | −0.184 | **37.4%** | −33.1 |
| paired difference (positional − swing) | 155 | **−0.079** | **−0.480** | — | t = **−0.53** |

**Not significant** — the relabelling is not *demonstrably* harmful. But the point
estimate is negative on the mean, sharply negative on the median (the typical panel
does about half an R worse as a positional), and the win rate more than halves. The
mean and median disagree because the +15% target produces a thin right tail that
lifts the average while the modal trade is stopped out.

> The honest summary: **there is no evidence that relabelling these signals as
> positional adds anything, and the decision to do so currently rests on no evidence
> at all.** The relabel is doing real work — it changes the stop reference, removes
> the stop cap, and multiplies validity by six — and none of it has ever been
> tested until now.

---

## 10. Diagnosis — why the right stock is not entered at the right price at the right time

Ordered by strength of evidence, not by ease of fixing. Each is positional-specific
unless stated.

### 10.1 The class is defined by a factor, not by a thesis

There is no answer in this codebase to "why is this a 30-day trade?" other than
"because `MULTIBAGGER_EMA` scored". The factor's own condition is about *moving
average convergence plus one big candle*; nothing in it concerns the holding
period, and the 30-day validity, the EMA20 stop and the 15% target were all
attached to that condition rather than derived from anything. A reviewer looking
for the economic hypothesis will not find one stated in code or spec — the closest
is the factor's name.

### 10.2 It selects against trend structure, then trades a trend premise

`PRICE_VS_EMA` fires on **9.1%** of positional panels versus **63.4%** of daily
panels generally, because the defining condition `|EMA20 − EMA200| ≤ 2%` is a
*converged* moving-average stack **[corpus]**. Meanwhile the specification's
heaviest factor, Dow trend structure (weight 20), **cannot fire on the daily
timeframe at all** and scored on 0 of 430 positional panels **[corpus]**.

> The class holds a name for six calendar weeks on the strength of a breakout
> candle, having selected for the absence of the trend the breakout is supposed to
> begin, with no trend input in the score.

This is corroborated system-wide: 0 of 91 paper entries passed Minervini's
seven trend conditions, and the closed book's outcome is explained by market
exposure (beta +0.92, per-trade alpha +0.0010).

### 10.3 The stop rule manufactures the losing cohort

A large green candle leaves the close just above the flattened EMA20, so the live
stop is near by construction: median **3.23%**, **30% under 2%** **[corpus]**. And
near stops are the losing cohort — mean R **−0.306** under 2% (9.6% win) against
**+0.153** at 4–6%, monotone across five buckets, **before costs** **[corpus]**. Costs then
compound it, because cost in R = bps ÷ (100 × stop-width %) — at a 1% stop, charges
alone are 0.23R and measured slippage roughly doubles that (§8.1).

The reported R:R inverts the picture: median **4.64**, p90 **16.95**. A quant
reading the signal list sees the best risk/reward in the system attached to its
worst-performing geometry.

### 10.4 ⭐ The notional cap is silently doing the selection, and nobody designed it to

Risk-first sizing gives `qty = capital × risk_pct ÷ (price × stop_width%)`, so

```
notional = qty × price = capital × risk_pct ÷ stop_width%
```

and the per-position cap rejects `notional > capital × leverage`. **The capital
cancels**:

```
capital × risk_pct / w  >  capital × leverage     ⟺     w  <  risk_pct / leverage
```

At the configured `risk_pct = 2.0` and `paper_max_notional_leverage = 1.0` that is
**`stop width < 2%`** — the same threshold at any account size, moving only if the
user changes their risk percentage or the leverage knob.

> **The 1.0× notional cap is a 2%-minimum-stop-width rule in disguise** — and 2% is
> precisely the boundary at which the corpus outcome flips sign (§9.4: −0.306R below
> 2%, −0.036R from 2–4%, positive above).

⚠ Two qualifications. The identity is exact only before the §4 volatility
adjustment, which cuts `qty` to 3/4 when ATR(14) > 3% of price and so lets some
volatile names through at a slightly tighter stop — which is why the measured
rejection rate (**28.4%**) sits just below the share of signals with stops under 2%
(**30.1%**) rather than equalling it **[corpus]**. And the rule is *not* symmetric
with intent: it was shipped as a blast-radius rail after a four-paise stop produced
₹1.19 crore of notional on ₹1 lakh — never designed as a selection rule, never
measured as one, and never reported as one.

Any future minimum-stop-width proposal must therefore be measured *against this
one*, not in addition to it — otherwise the project ships a second instrument for a
job that is already being done invisibly.

### 10.5 There is no trigger stage, and the entry price is unobtainable

Entry is the previous close; the signal is tradeable at 09:15 with nothing having
to happen; the entry-zone alert is direction-blind so a falling long reads as a
triggering long (§7.1). The textbook remedy is refuted at t ≈ −10 to −13 on
all-class samples (§7.2) — but it has **never been tested on positional**, whose
30-day window changes the trade-off materially.

### 10.6 The book is structurally long-only and unhedged

430 of 430 gate-passing positional signals are BUY **[corpus]**; 40 of 40 live
positional trades were LONG **[tape]**. The class cannot express a bearish view,
and cannot offset the swing book's shorts. Combined with beta +0.92 all-class, a
positional allocation is close to a levered long index position with extra costs.
The overlay built precisely for this exposure — the 200-DMA market-regime gate — is
in shadow, carries a do-not-act instruction, and **cannot currently be evaluated at
all** because the index history it reads is 48 rows (§5.5).

### 10.7 One in five positional signals is a single indicator

18.6% of gate-passing positional panels rest on `MULTIBAGGER_EMA` alone, which the
abstainer-normalising denominator renders as **90% confidence** — the highest
bucket the system reports **[corpus]**. `BUY AFFLE — Multibagger Ema, 90%
confidence` was filled and held as a real position **[tape]**. The
diversity gate now blocks this population; it was added after that trade, and it is
the only active selection gate in the system.

### 10.8 Nothing downstream knows the trade is a 30-day trade

No rule in the eligibility registry or the risk engine is classification-aware
(§7.5). The backtest neither uses the live stop rule nor respects the validity
window (§6.2). Position monitoring does not close at expiry — it emits an advisory.
The only class-aware machinery is the profit-lock preset. So "positional" changes
three numbers at mint time and is invisible everywhere else.

---

## 11. Options — what is actually available, and what each would cost to test

Nothing here is a recommendation to trade. Tier 1 is correctness work with **no
P&L claim**; only Tier 2 can change expectancy.

### Tier 1 — correctness (do these regardless; they are what make the rest measurable)

| # | Option | Why | Cost |
|---|---|---|---|
| **1** | **Pick one positional stop rule and make all three call sites use it** | `signal_service` uses EMA20; `profiles/pipeline.py` and `backtest/engine.py` silently use a flat 5%. 26 of 40 live trades were minted under the rule the primary path never produces. **Decide on reproducibility, not P&L** — the paired test cannot separate them (ΔR −0.120, t −1.47) | One argument at one call site, plus a decision. The backtest change is inside the freeze: sign-off + §8 regression + Rust fixture regeneration |
| **2** | **Make the backtest respect the positional validity window** | `_simulate_trade` walks to the end of the data. A 30-trading-day product is being backtested as an unbounded hold, and the two differ materially (−0.032R vs −0.102R). The `session_last` freeze-extension already provides the mechanism — this probe uses it | Frozen-engine change; the read-only measurement is already done here |
| **3** | **Make the entry-zone alert directional** | A falling long fires "entered zone". `cross_up`/`cross_down` already exist in the same file, unwired | Small, unambiguous, frontend-visible |
| **4** | **Resolve `max_sl_pct = 15.00`** | It is assigned for positional and never used; the cap check is explicitly skipped for that class alone. Note the threshold would barely bind if enforced — EMA20 stops run p90 **8.29%** with a maximum of **15.93%** **[corpus]** — so the dead variable is set to a number that would reject a negligible share, *and* the widest stops are the corpus's **best** cohort (§9.4). Either enforce it, or delete it and document "positional has no stop cap" explicitly | A decision plus one line |
| **5** | **Report the notional cap as a selection rule** | It is a 2%-minimum-stop-width filter that removes 28.4% of positional signals and was never measured as such (§10.4) | Reporting only; the counterfactual is a rerun of this probe with the cap applied |

**Also in this tier, and a prerequisite rather than an option:** restore
`index_ohlcv_1d` (48 rows) and `india_vix_daily` (16 rows), and backfill
`stocks.sector` beyond 165 of 1,322 active names. Until then the market-regime and
sector-RS overlays cannot be *evaluated at all* (§5.5) — which matters most for
this class, because it is long-only and holds for six weeks. Restarting intraday
capture (`ohlcv_5m/15m/1h`, currently empty) belongs here too: it accrues only in
real time, so it must be started before cycle 2, not when a question needs it.

### Tier 2 — generation levers (the only tier that can change expectancy)

| # | Option | Mechanism | How to test | Prior |
|---|---|---|---|---|
| **6** | **Require trend alignment on positional** | The class fires where `PRICE_VS_EMA` is absent 91% of the time. Requiring it — or a repaired trend factor — attacks the defect in §10.2 directly | Read-only injection through the frozen scorer, exactly the method that refuted RVOL: score the corpus with and without, compare **paired ΔR**. No frozen edit needed for the answer | **Guarded.** The class's defining condition works against trend alignment, so the intersection may be too small to trade. That is itself a finding |
| **7** | **Repair the Dow-trend factor** | Weight 20, unreachable on daily by construction (§5.3). A 60–100 bar lookback at n=5, or n=3 at 20 bars, makes it reachable | Same read-only injection. Shipping needs a **spec** decision — `SIGNAL_ENGINE.md` is protected | Guarded but it is the only *defect* on this list rather than a hypothesis. ⚠ Injection can dilute through the abstainer-normalising denominator, so a negative is entirely possible |
| **8** | **Re-run the confirmation study on the positional subset** | Refuted twice on all-class samples, never on positional, whose 30-day window changes the cost/benefit balance | The existing `entry_confirmation_study.py` restricted to positional signals | Low. The all-class result is strongly negative and the mechanism (Brooks' trader's equation) is general |
| **9** | **Ask whether the class should exist at all** | Positional is a relabelling of one factor. Removing the relabel would leave these as swing signals — 5-day validity, pivot stop, 8% cap, +6% target | **Already measured — see §9.6.** On the 155 panels where both rule sets produce a trade, the swing rules do better on the point estimate (−0.213R vs −0.292R) but the paired difference is **not significant (ΔR −0.079, t −0.53)** | Unresolved, but nothing supports the relabelling adding value. The decision currently rests on no evidence at all |

### Tier 3 — cost and geometry (moves the cost term toward zero; creates no edge)

| # | Option | Expected effect |
|---|---|---|
| 10 | **Limit orders instead of market** | Attacks the only term ever measured at t ≈ −10. Removes the half-spread and top-of-book impact on entry; cannot touch the charge floor |
| 11 | **A cost-relative minimum stop width** | Reject when round-trip friction exceeds a stated fraction of 1R. ⚠ Measure **against** the notional cap (§10.4), which already implements a 2% version — do not add a second instrument for the same job. ⚠ And the R:R reversal is the standing warning that an arithmetic identity still rests on an empirical premise |
| 12 | **Fewer, larger positions** | The flat ₹15.34 DP charge is 61.6 bps on a ₹3,900 position and 22.4 bps on a ₹10 lakh one. Cuts against the cycle-2 shape (1–2 positions on ₹1 lakh) unless position size rises |

### Tier 4 — risk control (reduces variance and ruin risk, not the loss rate)

| # | Option | Effect |
|---|---|---|
| 13 | Flip the 6% heat cap and the 3-position cap at the cycle-2 reset | Both built, both `off`. Measured all-class: smaller total loss, **worse per-trade** loss. Buys survivability, not profitability — and matters more here because the class is long-only and correlated |
| 14 | Keep the notional cap and the daily-loss breaker exactly as they are | Both prevented specific documented failures — but see §10.4: the notional cap is not only a rail |

### What should **not** be done

- **Do not add another selection gate.** Gating was formally closed as a programme
  on 2026-09-04: eight shadow gates, two promotions both refuted, best survivor at
  t = 0.41 against a t ≈ 3.6 bar.
- **Do not promote anything on a high reported R:R.** Positional's median planned
  R:R is 3.00–4.64 and the class still loses; the R:R ≥ 1 floor was promoted on an
  identity argument and reverted in 24 hours because it blocked the only profitable
  cohort.
- **Do not read the 30-day label as a horizon thesis.** Enforcing it *reduces* mean
  R in both stop rules (§9.2).
- **Do not tune on the live paper book.** It is the go-live gate.

---

## 12. Open questions a reviewer is best placed to answer

1. **Is the abstainer-normalising denominator defensible?** A factor that does not
   apply is removed from the denominator rather than counted as a zero, which is
   what lets one factor produce 90% confidence. The alternative ("abstention
   penalised") has never been tested. For positional it is not a corner case — it
   is 18.6% of the class.
2. **Is repairing the Dow-trend factor a bug fix or a new hypothesis?** If it is
   restoring the specified intent, it ships after a parity regression. If it is a
   new hypothesis it must clear t ≈ 3.6. The governance answer changes the required
   evidence by an order of magnitude, and it is the single largest unexplored lever
   for this class.
3. **Should a stop reference ever be chosen independently of the target?** The
   positional pair is EMA20 (structural, wherever it happens to be) against +15%
   (absolute). A constant-R:R target family was already tested system-wide and
   refuted; a *structural* target (next resistance) has not been.
4. **Is the notional cap acceptable as an implicit selection rule?** It is
   currently a 2%-minimum-stop-width filter — the threshold is `risk_pct ÷
   leverage`, so it silently changes the moment the user edits their risk
   percentage (§10.4). Should the selection intent be made explicit and separated
   from the blast-radius intent — and if so, does an explicit stop-width rule need
   to clear the t ≈ 3.6 promotion bar, given it is arithmetic about cost rather
   than a claim about the tape?
5. **At ₹1 lakh, with round-trip friction of 22–29 bps plus spread, and a stop rule
   that produces a 3.23% median stop, is this class viable at all** — or is the
   cost floor decisive before any selection question is reached?
6. **Should the class simply be deleted?** §9.6 says the relabelling is not
   demonstrably better or worse than leaving these as swing signals. Deleting it
   would remove a stop rule, a target rule, a validity rule and an uncapped-stop
   exception, at the cost of one factor's bonus weight.

---

## Appendix A — file map

| Concern | Path |
|---|---|
| Specification (hook-protected) | `docs/SIGNAL_ENGINE.md` |
| The factor that defines the class | `backend/app/analysis/indicators/ema.py::multibagger_ema_factor` |
| Confluence scorer and normalisation | `backend/app/analysis/confluence.py` |
| Classification | `backend/app/signals/classifier.py` |
| Stops, targets, sizing | `backend/app/analysis/risk.py::compute_levels` · `app/signals/risk_guards.py::safe_levels` |
| Signal generation (passes EMA20) | `backend/app/services/signal_service.py:245, :434` |
| Profile minter (**omits** EMA20) | `backend/app/profiles/pipeline.py:367` |
| Backtest (**omits** EMA20, no horizon) | `backend/app/backtest/engine.py:322` · `_simulate_trade` |
| Validity in trading days | `backend/app/signals/expiry.py` · `app/services/market_calendar.py` |
| Eligibility registry / pre-trade gate | `backend/app/signals/restrictions.py` · `app/trading/risk_engine.py` |
| Paper execution + fill model | `backend/app/broker/paper_broker.py` |
| Charges | `backend/app/trading/fees.py` |
| Live alerts (entry zone) | `backend/app/broker/live_levels.py` |
| Class-aware exit ratchet | `backend/app/trading/profit_lock.py::CLASS_PARAMS` |
| Promotion bar | `backend/app/services/deflated_sharpe.py` · `dsr_control.py` |
| Overlap-corrected t / block bootstrap | `backend/app/services/block_bootstrap.py` |
| **This document's probe** | `backend/scripts/positional_probe.py` |
| System-wide companion review | `docs/SYSTEM_REVIEW_FOR_QUANT.md` |

## Appendix B — conventions a reader must know

| Term | Meaning here |
|---|---|
| **R** | one unit of planned risk = \|entry − stop\| × qty. Every outcome is normalised by it. ₹ figures are **not** comparable across trades because sizing is risk-first |
| `WINSOR_R = 10.0` | bound applied wherever R is *averaged* — a 0.23% stop otherwise produces a 26R trade that owns the mean |
| `MAX_RR = 50` | reporting bound on displayed R:R. **Clamp what you report, never what you decide** |
| Undefined ratio | `None`, never `0.0` — "not assessable" and "worst possible" must not collide |
| `is_shadow` | durable provenance. `status` is a lifecycle field the sweeper overwrites, so any tradeable statistic must filter `is_shadow IS FALSE` |
| Gate modes | `off` (no-op) · `shadow` (verdict recorded, never acted on) · `active` (order path rejects) |
| MFE / MAE | maximum favourable / adverse excursion, in R, while the position was held |
| Cycle 1 / cycle 2 | cycle 1 is the wide sampler that produced the tape; its 30-day clock is **informational**. Cycle 2 is a 45–50 session rehearsal on a heat-capped ₹1 lakh book and is the binding go-live gate |

## Appendix C — measurement hygiene these numbers obey

Three defects were found in this project's own research harness on 2026-09-10, and
a fourth was found by this review; every measurement in this document is constructed
to avoid all four:

1. **Overlapping forward windows inflate a naive t.** Under the null a daily
   cross-sectional t has sd 0.98 at k=1 but 3.32 at k=10 and 4.45 at k=20. This
   document reports **trade-level** statistics and prices dependence with
   `moving_block_bootstrap`; the two paired t-statistics quoted (−1.47, −0.53) are
   on *differences between rules on identical signals*, where the common market
   factor cancels.
2. **The "CA-clean window" claim is false.** `ohlcv_1d` is CA-unadjusted
   throughout: 49 unadjusted corporate actions sit in the top-250-liquid universe,
   35 of them ≥40% halvings, and in one study 4 of 1,979 trades carried ~+49R of
   fake profit. Every corpus figure here **drops any holding span containing a
   close-to-close move > 25%** (4 trades dropped, printed by the probe).
3. **Averaging R without winsorizing lets ~10 trades own the answer.** All means
   here are winsorized at `WINSOR_R = 10.0`, and the **median is printed beside
   every mean** — which is why §9.2's "median R −1.000" appears next to means near
   zero, and why §9.6's mean and median disagree in size.

4. **⚠ NEW, found by this review: the frozen backtest walker scores a
   gap-through-stop fill as a WINNER.** `_simulate_trade` skips its gap check on the
   fill bar itself (correctly — the entry *is* that bar's open), but then still runs
   the intrabar test `low <= stop_loss` and exits **at `stop_loss`**. If the fill has
   already gapped below the stop, that exit price is *above* the entry, so an
   immediate loss is recorded as a gain of about **+1R**. Minimal reproduction, three
   bars:

   | | value |
   |---|---|
   | signal bar close / stop | 100.00 / 99.00 |
   | fill = next bar's open | **95.00** — already 4.04% *below* the stop |
   | recorded exit | 99.00, `hit_sl = True` |
   | recorded P&L | **+4.211% = +1.000R** |

   The live path is unaffected: `paper_broker` (`:544-554`) rejects an order already
   through its own stop, and `size_for_fill` refuses a non-positive risk distance.
   Only *measurement* is affected — and it flatters precisely the **tight-stop**
   cohort, because a near stop is the one an overnight gap clears. Excluding these 6
   trades moved this document's tightest bucket from −0.257R to **−0.306R** and its
   win rate from 13.3% to **9.6%**: the headline gradient in §9.4 was *understated*.
   ⚠ **Any study built on `_simulate_trade`, or on a walker validated against it,
   inherits this** — including the 1,975-trade backtest headline and the
   entry-confirmation study in `SYSTEM_REVIEW_FOR_QUANT.md`, where the magnitude is
   currently unmeasured.

The rule adopted from that episode, and applied here: *an instrument never run
against a known null, a known-contaminated input and a known tail artefact has not
been validated.*

## Appendix D — reproducing every [corpus] figure

```bash
# everything, including the strided swing baseline in 9.2 (slowest; ~17k extra panels)
cd backend && uv run python scripts/positional_probe.py --stocks 250 --swing-stride 25

# positional only — identical positional numbers, no swing baseline (fast)
cd backend && uv run python scripts/positional_probe.py --stocks 250 --swing-stride 0
```

The swing **baseline** row in §9.2 (n=85) comes from the first command; every other
`[corpus]` figure is produced by both and was cross-checked between them.

SELECT-only. The frozen confluence engine and the frozen backtest walker are
imported and called exactly as the nightly job and the backtest call them; nothing
under `app/analysis/` or `app/backtest/` is edited, subclassed or reimplemented.

⚠ **Determinism is conditional on the database state, and the corpus drifts.** Three
consecutive executions against an unchanged database produced byte-identical
statistics. But the universe is chosen by a **rolling 180-day** median-traded-value
ranking, so a new session's EOD bars change both the ranking and the available
decision bars. This happened during the preparation of this document — 2026-09-10's
bars landed mid-session and moved the gate-passing count by about 1%. **Every
`[corpus]` figure in this document is therefore taken from a single run against a
single snapshot** (`ohlcv_1d` complete through 2026-09-10); do not mix figures
across runs, and expect a rerun on a later day to differ slightly.

The **[tape]** figures are parsed from the per-trade blocks of
`docs/analysis/2026-*.md`; the parser keys each trade by (symbol, class, open date,
open time) so a position carried across report days is counted once.

⛔ **Never pass `DATABASE_URL` to `pytest`, `make test` or `make check`.** Doing so
on 2026-09-07 truncated the development database — which is why the live record
discussed in §9.1 no longer exists. The test harness now refuses any database not
named `*_test`.
