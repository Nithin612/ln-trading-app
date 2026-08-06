# Stock Selection Engine & Alert Generation — Complete Reference

**Status:** current as of 2026-08-01 · **Audience:** you (solo dev) — a full,
no-detail-omitted walkthrough of *how the platform decides what to trade and
how it tells you about it*, plus *why the design beats the tools retail
traders normally use* and *exactly how it is wired to Zerodha Kite*.

This document is descriptive, not normative. The **authoritative spec** for the
scoring math is `docs/SIGNAL_ENGINE.md` (protected). Where the two disagree,
SIGNAL_ENGINE.md wins and this file has a bug. File paths are given so you can
jump straight to the code.

---

## 0. The one-paragraph version

The platform never fires a trade idea off a single indicator. A stock is
"selected" only when **5–7 independent factors agree at the same price level**
(confluence), the weighted agreement clears a **≥70 % confidence gate**, the
setup survives a set of **safety guards** (news blackout, degenerate stop,
duplicate suppression, corporate-action quarantine), and a **position size +
stop-loss + target + expiry** can be computed within the risk caps for its
class. That produces a **committed signal**. Separately, a **live tick-trigger
layer** watches a handful of price/volume *levels* derived from those signals
(entry zone, stop/target proximity and touch, previous-day high/low, support/
resistance, volume bursts) and emits **alerts** the instant price interacts
with them — through a Rust state machine that fires **once** and re-arms only
after price genuinely retreats, so a choppy tape can't spam you. Everything
that touches live ticks is labelled **provisional** and is walled off from
scoring, sizing, and backtests, which is what keeps the engine free of
look-ahead bias. All market data — ticks, candles, historical backfill,
instrument master — comes from **Zerodha Kite Connect**, through a WebSocket
tick consumer and a shared rate-limited REST client, with the daily 6 AM token
death treated as a normal lifecycle event.

---

## 1. Two engines, one firewall (read this first)

The system has **two distinct decision layers**. Confusing them is the single
biggest source of bugs in systems like this, so the codebase keeps them
physically separated.

| | **Committed signal engine** (selection) | **Live tick-trigger engine** (alerts) |
|---|---|---|
| Question it answers | "Is this a trade worth taking?" | "Is price *doing the thing* right now?" |
| Input data | **Completed** candles only (`is_complete = true`) | Every live tick (forming candle) |
| Cadence | Nightly batch + on candle-close | Per tick (sub-10 ms target) |
| Output | A `Signal` row (direction, class, entry/SL/TP/qty, confidence, factors) | An `alert` stream entry (a level was crossed/entered/approached) |
| Look-ahead safe? | **Yes** — computes on candle N, valid from N+1 | N/A — it is *reaction*, not prediction |
| Enters backtests / P&L? | Yes | **Never** — labelled `provisional` end-to-end |
| Where | `app/analysis/`, `app/services/signal_service.py`, `app/signals/` | `engine/crates/engine-core/src/triggers.rs`, `app/broker/live_levels.py`, `app/broker/live_worker.py` |

**The firewall:** the trigger engine only ever *watches levels that the signal
engine produced* (plus a few static market levels). It never scores, never
sizes, never writes a signal. A tick can make an alert light up on your screen;
it can **never** create or alter a committed trade idea. This is enforced by
code structure (`analysis/` is frozen and has no tick imports) and stated in
every relevant docstring (`live_levels.py`: *"Levels are alert thresholds,
never signal inputs"*).

```
                         ┌─────────────────────────────────────────────┐
   Zerodha Kite          │              COMMITTED ENGINE                │
   ─ EOD bhavcopy ──────►│  completed candles → 14-factor confluence →  │
   ─ REST history        │  ≥70% gate → classify → size → SL/TP →       │
                         │  guards → Signal row                          │
                         └───────────────┬─────────────────────────────┘
                                         │ active signals' prices
                                         ▼  (entry/SL/TP levels)
   Zerodha Kite          ┌─────────────────────────────────────────────┐
   ─ WebSocket ticks ───►│              LIVE TRIGGER ENGINE             │──► alerts:live
                         │  ticks → Rust LiveBook → level crossings →   │    (Redis Stream)
                         │  arm/disarm state machine → Firing            │──► WebSocket ─► AlertBell
                         └─────────────────────────────────────────────┘
```

---

# PART A — THE STOCK SELECTION ENGINE

Selection is a funnel. Each stage removes candidates; only what survives all
of them becomes a signal.

```
 ~all NSE/BSE equities
      │  (A.1) Universe: is_active, not T2T, not CA-quarantined
      ▼
 tradable universe (~ hundreds)
      │  (A.2) Screener — OPTIONAL manual pre-filter (index/sector/mcap/…)
      ▼
 candidate set
      │  (A.3) 14-factor confluence run per stock, per timeframe
      ▼  (A.4) weighted score → normalize → ≥70% gate (ADX-adjusted)
 stocks whose factors AGREE ≥70%
      │  (A.5) classify (scalp/intraday/swing/positional) + volatility regime
      │  (A.6) position size + SL/TP; REJECT if SL exceeds class cap
      │  (A.7) validity window; (A.8) guards (news, degenerate SL, dup, CA)
      ▼
 SIGNAL  ── persisted, surfaced on dashboard, drives live alert levels
```

## A.1 The universe — what is even eligible

Before any scoring, a stock must be *tradable*. Resolution lives in
`app/services/universe_service.py::resolve_universe`.

- Only `Stock.is_active = true` rows ever resolve.
- **CA-quarantined stocks are excluded** (`Stock.ca_flagged_at IS NULL`): a
  stock that just had a split/bonus/dividend has unadjusted history that would
  be scored *across* the corporate action — garbage. It's held out until
  adjusted (`services/ca_detector.py`).
- **T2T / trade-to-trade / `-BE` series stocks are live-excluded** via the
  daily instrument sync (self-healing, not a hand-maintained blacklist). These
  are surveillance-list names where intraday leverage is disallowed; they also
  receive no EOD bars (the bhavcopy parser is EQ-only), so they are naturally
  dark in both universes.
- Universe *kinds* the engine can target (typed, discriminated — unknown kinds
  are rejected, never silently widened): `index` (NIFTY50 / BANKNIFTY),
  `flag` (F&O-enabled), `symbols` (explicit list), `category` (a saved
  category slug), or `all_active`.

The nightly batch runs over **all active stocks**; strategy profiles and the
backtester can scope to any of the above.

## A.2 The screener — the optional manual pre-filter

The screener (`app/screener/`, `app/api/v1/screener.py`) is a **user-driven
structural filter**, distinct from the automatic signal engine. It answers
"show me stocks matching these hard criteria" and is how you narrow a universe
before (or instead of) leaning on signals.

- **Whitelist-driven, injection-proof.** Only fields in
  `app/screener/catalog.py::CATALOG` are filterable; unknown fields raise
  `ValueError` before any SQL is built. Each field declares its type and the
  operators that make sense for it (`bool → eq`; `str → eq/neq/like/in`;
  numeric/date → `eq/neq/gt/gte/lt/lte/between`).
- **Available today:** index membership flags (`is_nifty50`, `is_banknifty`,
  `is_finnifty`, `is_fno`, `is_active`), `symbol`, `exchange`, `sector`,
  `industry`, `isin`, `lot_size`, `listed_on`, `market_cap_cr`.
- **Declared but "coming soon" (rejected server-side with a clear message, not
  a silent empty result):** `indicator.rsi_14`, `indicator.price_vs_ema50`,
  `flow.fii_net_5d_cr` — these light up once their Phase-4 data exists.
- `AND`/`OR` combination, category membership AND-filter, sortable, paginated
  (limit 1–200), and **saved screens** (`SavedScreen`) per user.

The screener is a *sieve*; the confluence engine is the *judge*. You can screen
to a shortlist and let signals rank within it, or ignore the screener entirely
and let nightly signals surface across the whole universe.

## A.3 The factor universe — the 14 (+1) inputs

This is the heart. Every factor is a pure function returning a
`FactorResult(name, weight, score, explanation, tags)` where **score ∈ [−1.0,
+1.0]** (−1 strongly bearish, +1 strongly bullish, **0.0 = neutral / not
applicable**). Implemented under `app/analysis/`; assembled in
`app/analysis/confluence.py::run_all_factors`.

**Candlestick patterns** (`analysis/patterns/`) — the engine evaluates *all*
patterns and takes the **single highest-magnitude** one as one factor (weight
15), *not* the sum (`_best_pattern_factor`):

- *Single-candle* (`single.py`): Marubozu ±0.8, Doji 0, Spinning Top 0, Hammer
  +0.7, Hanging Man −0.6, Shooting Star −0.7, Paper Umbrella +0.4.
- *Multi-candle* (`multi.py`): Bullish/Bearish Engulfing ±0.9, Harami ±0.5,
  Piercing / Dark Cloud ±0.7, Morning / Evening Star ±0.95.
- **Context-aware:** a hammer mid-trend scores nothing; a hammer *at a swing
  low* (within 1 % of the 20-bar low) gets full credit. Location is passed in
  (`at_swing_low` / `at_swing_high`).

**Indicators** (`analysis/indicators/`) — each is its own independent factor:

| Factor (name) | Weight | Bullish condition | Bull score |
|---|---|---|---|
| Dow trend (`structure/dow.py`) | 20 | Higher-highs **and** higher-lows over 20 bars (pivot N=3 intraday / 5 daily) | +0.7 |
| EMA cross (`ema.py`) | 15 | 20 EMA crosses above 50 EMA | +0.6 |
| Price vs EMA (`ema.py`) | 15 | Close > 50 EMA and 50 EMA > 200 EMA | +0.5 |
| RSI level (`rsi.py`) | 10 | RSI 30–50 and rising | +0.6 |
| RSI divergence (`rsi.py`) | 10 | Price lower-low, RSI higher-low | +0.8 |
| MACD cross (`macd.py`) | 10 | MACD line crosses above signal (12,26,9) | +0.7 |
| MACD histogram (`macd.py`) | 10 | Histogram rising from negative toward 0 | +0.4 |
| Volume (`volume.py`) | 10 | Current vol ≥ 1.5× 20-period avg | +0.5 *(confirm-only, see A.4)* |
| Bollinger Bands (`bbands.py`) | 10 | Touches lower band, closes back inside next bar | +0.5 |
| ADX + DI (`adx.py`) | 5 | ADX > 25 and +DI > −DI | +0.6 |
| Support/Resistance + Zones (`structure/levels.py`) | 10 | At support with bullish pattern; demand-zone reversal; range-breakout-with-volume | +0.8 … +0.9 |
| Fibonacci (`structure/fibonacci.py`) | 5 | Bounce from 0.5 / 0.618 / 0.786 retrace | +0.4 … +0.6 |
| FII/DII flow (`structure/institutional.py`) | 5 | 5-day cumulative FII/DII net buying; block/bulk deals ±0.4 | +0.3 … +0.7 |
| **Multibagger EMA (1d only, BONUS)** | **+10** | 20 EMA within 2 % of 200 EMA + breakout candle | +0.9 |

Bearish counterparts are mirrored (negative scores). The **maximum applicable
weight is 150** (+10 multibagger bonus). See SIGNAL_ENGINE.md §2 for exact
trigger definitions and the masterclass provenance of each.

## A.4 The confluence scorer — how factors become a decision

`app/analysis/confluence.py::score_from_factors`. The algorithm, exactly:

```
total_weighted = Σ (weight × score)            over all factors
total_weight   = Σ  weight                      over factors whose score ≠ 0
if total_weight == 0: return None               (nothing applicable → no signal)
normalized     = total_weighted / total_weight  ∈ [−1, +1]
confidence_pct = int(|normalized| × 100)        (truncation = Python int())
```

Four rules make this more than a naïve weighted average:

1. **Only factors that actually fired count toward the denominator.** A factor
   scoring 0.0 is "not applicable" and is *excluded* from `total_weight`. So
   **four factors firing decisively beats fourteen firing weakly** — a window
   where many factors are middling *dilutes* the average and correctly stays
   below the gate. Each indicator carries its listed weight independently
   (they are separate factors, not shares of a group budget — adjudicated
   2026-07-05 item H; the group-budget alternative added ≈400 weak trades and
   crushed total P&L in the 2y × Nifty50 test).

2. **Volume is a confirmation multiplier, never a driver.** A volume surge is
   re-scored to `+0.5` if the *rest* of the factors are net-bullish, `−0.5` if
   net-bearish, `0` if flat. It confirms whatever else fired and **can never
   push against the other factors or fire alone** (SIGNAL_ENGINE.md §3;
   adjudicated 2026-07-04).

3. **The ≥70 % gate is ADX-regime-adjusted** (SIGNAL_ENGINE.md §4, implemented
   in `score_from_factors`):
   - ADX weak (< 20) → require **+5 %** extra (effective min 75) — weak trends
     need more agreement.
   - ADX strong (> 40) → threshold **drops to 65** — in strong trends, simpler
     setups work.
   - Otherwise the `.env` `MIN_SIGNAL_CONFIDENCE = 70` applies.

4. **Conflict resolution is automatic.** If a pattern says BUY but the (heavy,
   weight-20) Dow trend says down, the negative contribution drags the
   normalized score toward zero. A 65 % buy pattern against an 80 % down-trend
   nets to ~−14 % → below gate → **no signal**. Counter-trend trades are *hard*
   to surface, by design.

Below the gate the result is `None`: the signal is *logged for backtest
learning* but never shown. Above it, direction = sign of `normalized`, and the
result carries the full factor breakdown for the justification.

**Engine implementation dispatch.** Scoring runs through the frozen **Python
reference engine** or the **Rust `tradecore` engine** (`ENGINE_IMPL` setting,
default `python`). The Rust path is parity-gated: factor scores, confidence
integers, and decisions are **exact-equal by test** on the 2y × Nifty50 corpus.
The Python analysis code is *frozen* (bugfix-only) and its golden fixtures are
the Rust oracle (`app/services/signal_service.py::score_signal` handles the
dispatch, refusing rather than silently mis-scoring where Rust lacks a feature
like FII/DII flows or weight multipliers).

## A.5 Classification & volatility regime

`app/signals/classifier.py` maps the **timeframe that produced the setup** to a
class, and `app/analysis/risk.py` applies the volatility regime:

| Timeframe | Class | Typical hold |
|---|---|---|
| 1m / 5m | `scalp` | 5–30 min |
| 15m / 1h | `intraday` | hours, exit by 3:15 PM IST |
| 1d | `swing` (or `positional` if the multibagger EMA setup fired) | 3–10 trading days / weeks–months |
| 1w | `positional` | months |

- **ATR(14) > 3 % of price → volatile → position size cut 25 %** (`risk.py::
  volatility_adjusted_qty`, integer `qty*3//4` = exact `floor(qty×0.75)`,
  matching Rust). If that reduction takes qty to 0, the signal is rejected.

## A.6 Position sizing, stops, targets — risk-first, reject-don't-clamp

**Mandatory on every signal** (`app/analysis/risk.py`). This is what separates
a *trade idea* from a *tip*.

```
risk_amount    = capital × (risk_pct / 100)        # risk_pct is a WHOLE % (2.0 = 2%)
risk_per_share = |entry − stop_loss|
quantity       = floor(risk_amount / risk_per_share)
```

`risk_pct` is a whole percent — `compute_quantity` divides by 100 itself.
(Pre-dividing was the historic 100× undersizing bug; it's called out in every
relevant docstring.)

**Stop-loss placement & class caps** (`compute_levels`):

| Class | Default SL | **Max SL** | Target (RR) |
|---|---|---|---|
| Scalp | 0.30 % from entry | **0.50 %** | 1:1.5 |
| Intraday | below last swing low | **0.50 %** | 1:2 |
| Swing | below last swing low | **8.00 %** | flat 6 % (RRBO) |
| Positional | trailing 20 EMA (daily) | 15 % soft (trailing) | 15 % min |

**Reject, never clamp.** If the natural stop (e.g. the actual swing low)
exceeds the class cap, the signal is **rejected** — the SL is *never* tightened
to fit. "If the swing low is too far, avoid the trade" (masterclass). A live
guard (`app/signals/risk_guards.py::safe_levels`) additionally rejects a
degenerate stop that equals entry or sits on the wrong side (which would crash
`compute_quantity`), giving the live path reject-don't-crash semantics.

## A.7 Validity (expiry)

`app/signals/expiry.py` + the every-5-minute sweeper (`tasks/expiry_tasks.py`).
Validity is measured in **real NSE trading days** (the calendar, not
calendar-day arithmetic — `services/market_calendar.py`):

| Class | Validity |
|---|---|
| Scalp | 30 minutes |
| Intraday | until 3:15 PM IST same trading day |
| Swing | 5 trading days (or SL/TP/EMA exit) |
| Positional | 30 trading days (or 20-EMA exit) |

On expiry the status flips to `EXPIRED`, it drops off the dashboard, and the
row is retained for backtest analysis.

## A.8 The guards — why a >=70 % score still might not become a signal

Even a gate-passing setup is dropped if:

- **News blackout** (`app/signals/event_guard.py`): a high-impact corporate
  filing (earnings/merger/rating) within the last **60 minutes** suppresses new
  signals — technical structure is meaningless while price is news-driven.
- **Degenerate / wrong-side stop** (`risk_guards.py`) → reject.
- **Duplicate suppression / idempotency** (`signal_service.py::
  _has_active_signal`): if an *unexpired active* signal already exists for the
  same (stock, timeframe, direction), no near-identical duplicate is minted on
  the next candle-close or nightly rerun. This is the **no-repaint** guarantee:
  a committed signal's factors are frozen at commit time.
- **CA quarantine** (A.1) and **T2T exclusion** — removed at the universe stage.
- **Too little history**: fewer than 50 completed candles → skip (the scorer
  needs a real window; the canon is the **last 300 completed candles**).

## A.9 How signals actually get produced

Two production paths, **same scoring code**:

1. **Nightly batch** — `tasks/signal_tasks.py::nightly_signal_generation`
   (Celery beat, weekdays ~19:15 IST / 13:45 UTC, *after* the EOD bhavcopy
   lands). Skips market holidays (`is_trading_day`). Runs
   `run_nightly_signal_generation` over every active stock on the daily
   timeframe: loads market-wide FII/DII once, per-stock block-deal net inside
   the loop, generates and persists new signals.

2. **Live, per candle-close** — when a live candle closes, the tick consumer
   enqueues a `(stock_id, timeframe)` trigger; after the batch commits it fires
   `live_signal_generation`, which re-runs the **exact same confluence engine**
   on the intraday timeframe's completed candles (`signal_service.py::
   run_live_signal_generation`). This is **gated off by default**
   (`LIVE_SIGNAL_DISPATCH_ENABLED`) because `send_task` enqueues even with no
   worker running (that once OOM'd Redis).

Both paths: load ≤300 completed candles → `score_signal` → `_has_active_signal`
dedup → classify → `safe_levels` → `compute_quantity` → volatility adjust →
validity → build headline → persist.

## A.10 Worked example (from the live engine — SIGNAL_ENGINE.md §7)

POWERGRID, 1d, last 300 completed candles. Ten of fourteen factors scored 0.0
(excluded from the denominator). The four that fired:

| Factor | weight | score | contribution |
|---|---|---|---|
| Bullish Engulfing | 15 | +0.90 | +13.50 |
| RSI 30–50 rising | 10 | +0.60 | +6.00 |
| At support + bullish pattern | 10 | +0.85 | +8.50 |
| Fib bounce 0.5 | 5 | +0.40 | +2.00 |

`total_weighted = 30.00`, `applicable_weight = 40` → `normalized = 0.75` →
**confidence = 75 % → BUY** (clears the 70 % gate; ADX neutral). Sizer: entry
₹288.20, swing class, SL = swing low ₹278.40 (3.4 % — inside the 8 % cap), TP
₹305.49 (flat 6 %). Capital ₹5,00,000 @ 2 % risk → `qty = floor(10,000 / 9.80)
= 1020`. ATR 1.96 % (< 3 %) so no size cut.

> **"Buy POWERGRID — Bullish Engulfing at support, RSI rising, 75 % confidence.
> Entry ₹288.20, SL ₹278.40, TP ₹305.49, Qty 1020."**

---

# PART B — ALERT GENERATION

Alerts tell you *price is interacting with something you care about, right
now*. They are **reactions to live ticks**, produced by a Rust state machine,
and delivered over a WebSocket. They never create trades.

## B.1 What a "level" is, and where levels come from

`app/broker/live_levels.py` builds the watch-list of price/volume **levels**
per stock. Two sources:

**Static (built once at session start, from the previous day):**
- **PDH / PDL** — previous-day high / low → `cross_up` / `cross_down` watches
  (ids 1 / 2). The classic "10 AM strategy" / breakout reference levels.
- **Volume-burst baseline** — average completed-5m volume over ~20 sessions
  (id 3). The forming candle's *partial* volume is compared to
  `live_vburst_mult × baseline`, so firing early means genuinely bursty, not
  merely "on pace".

**Signal-derived (refreshed every `live_level_refresh_s` = 30 s, for stocks
with an active signal):**
- **Entry zone** — a band `entry ± live_entry_zone_pct` (±0.5 %) → `zone` watch.
- **SL proximity** and **TP proximity** — `near` watches within
  `live_sltp_within_bp` (0.25 %) of the stop / target.
- **SL touch** and **TP touch** — direction-aware `cross` watches at the *exact*
  SL/TP price (a BUY's TP is a cross-up, its SL a cross-down; SELL mirrored).
  These feed the outcome recorder (B.7).
- **Support/Resistance crosses** — from the *frozen* S/R detector over the last
  300 completed candles (`analysis/structure/levels.py::detect_sr_levels`),
  top 8 zones by strength → `cross_up` (resistance) / `cross_down` (support).

**Level ids are identity-derived, not rank-derived** (SHA-256 of the
signal-UUID / of `timeframe:zone_type:price`), and **stable across refreshes**,
so a strength reshuffle never reassigns an id — which would reset armed-state,
bypass the re-arm band, and break consumer dedupe. The `LevelDirectory`
tracks changes and re-sends only stocks whose merged level list changed since
the *consumer acknowledged* it (eviction- and rejection-proof).

## B.2 The Rust trigger engine — the anti-spam state machine

`engine/crates/engine-core/src/triggers.rs`. Pure, deterministic, allocation-
free, and **replayable** (every `set_levels` call is recorded into the tick
stream, so trigger events replay byte-identically). The engine never knows what
a level *means* — `id` and `tag` round-trip to the host untouched.

Five level kinds (`LevelKind`), each a **two-state machine: ARMED → fires once
→ DISARMED → re-arms only when its re-arm condition holds.**

| Kind | Fires when | Re-arms when | Tag emitted |
|---|---|---|---|
| `Zone {low,high}` | price first observed inside band (incl. first tick) | price leaves the band | `zone_enter` |
| `CrossUp {price, rearm_bp}` | strict transition below→above (never on first tick) | price retreats **below** by `rearm_bp` bps | `cross_up` |
| `CrossDown {price, rearm_bp}` | strict transition above→below | price retreats **above** by `rearm_bp` bps | `cross_down` |
| `Near {price, within_bp}` | \|price−level\| first within `within_bp` bps | price leaves the band | `near` |
| `VolumeBurst {tf,baseline,mult_bp}` | forming-candle volume ≥ `baseline × mult_bp/10⁴` | a new candle bucket starts | `volume_burst` |

**Why this matters (the anti-spam contract):** a naïve alert ("price > PDH!")
re-fires on *every tick* while price sits above the level — hundreds of
useless notifications during a consolidation. Here a cross fires **once**, then
stays silent until price genuinely retreats past a **re-arm band**
(`live_cross_rearm_bp` = 10 bps = 0.1 %). Chop *inside* the band cannot
re-fire it. All-or-nothing validation, and armed-state is **preserved across
level refreshes** for unchanged (id, kind) pairs — a periodic host refresh
never re-fires everything sitting inside a zone. Duplicate delivery is only
possible across a process *restart* (fresh state); the alert stream is
at-least-once by design and consumers dedupe by **(id, day)**.

## B.3 The tick → alert pipeline

`app/broker/live_worker.py` is the host that drives the Rust `LiveBook`:

```
Kite WebSocket tick
   │  (tick_consumer marshals off the ticker thread → asyncio queue)
   ▼
live_worker.process_item(batch)
   │  book.on_ticks(batch)         # Rust: updates forming candles + evaluates watches
   ▼
events = [committed candles, triggers, …]
   ├─ _enqueue_committed(...)      # durable candle writes (never dropped while writer lives)
   ├─ _publish_alerts(triggers) ──► XADD alerts:live  (Redis STREAM, at-least-once)
   ├─ _publish_ltp(batch) ───────► SET ltp:{sid} + PUBLISH ltp:{token}
   └─ _publish_events(candles) ──► PUBLISH candle:{table}:{sid}
```

**Alert enrichment** (`_publish_alerts`): the Rust firing carries only `id` +
`tag`. The host looks up the level's **meta** (`source`, `style`, `signal_id`)
from the registry and writes one stream entry per firing:

```json
{ "sid", "level_id", "tag", "price", "ts", "day",
  "source": "entry_zone|sl_near|tp_near|sl_touch|tp_touch|pdh|pdl|sr_support|sr_resistance|vburst",
  "style":  "market|scalp|intraday|swing|positional",
  "signal_id": "<uuid, if signal-derived>" }
```

Ordering discipline: engine accepts a batch **first**, durable writer **second**,
lossy Redis **last** — a Redis blip can never starve the engine or drop a
committed candle. The alerts XADD gets **one pipeline round-trip per batch**
plus one retry (an open-auction burst of hundreds of firings must not serialize
hundreds of RTTs inside the latency-measured window).

## B.4 Delivery to the browser

`app/api/v1/ws.py` — one authenticated WebSocket (`/ws/live?token=<JWT>`) fans
out four message types: `ltp`, `candle`, `alert`, `provisional`. The client
subscribes explicitly:

- `{"subscribe_alerts": true}` — all tick-trigger alerts
- `{"subscribe_alerts": {"styles": ["intraday","swing"]}}` — filtered by style
- `{"subscribe_alerts": {"watchlist": 3}}` — only that watchlist's stocks
  (ownership-checked; snapshot at subscribe — re-send to refresh)

Alerts are tailed from the `alerts:live` **Redis Stream** from `"$"` (new
entries only). Reconnect reconciliation is deliberate: on reconnect the
frontend re-reads committed state over REST rather than replaying the stream.
Redis is the fan-out bus so a slow client can't block a fast one; the worker
even gates candle/LTP *publishes* on whether anyone is actually subscribed.

## B.5 Alert presentation & the anti-chase guardrail (frontend)

`frontend/src/features/alerts/` (`AlertBell.tsx`, `alertPresentation.ts`).

- **Tag → human vocabulary** (`TAG_META`): `cross_up` ▲ "Crossed above"
  (profit tone), `cross_down` ▼ "Crossed below" (loss), `zone_enter` ◆
  "Entered zone", `near` ≈ "Approaching", `volume_burst` ⚡ "Volume burst".
  Direction is **always glyph + colour**, never colour alone (UI rule).
  Unknown backend vocabulary renders as a raw string so new tags degrade
  *visibly* rather than hiding alerts.
- **"Entry signals only" filter** — the bell defaults to showing only
  `source == 'entry_zone'` alerts (persisted in `localStorage`), so the actual
  *actionable* "price is at your entry" alert isn't buried under proximity
  noise.
- **Anti-chase guardrail** (`chaseGuidance`) — the differentiator. A signal is
  meant to be *entered at its `entry_price`*. Once price runs past entry by
  **0.33 R** (a third of the trade's own entry→SL risk), the reward:risk you
  were shown is materially gone and buying there is **chasing**. The bell
  computes a don't-chase ceiling (`entry ± 0.33·R`), shows it next to the
  ideal entry, and **flags when the trigger price already blew through it**
  ("chasing 1.4 % past entry"). The system actively discourages the single
  most common way retail traders turn a good signal into a bad trade.

## B.6 Provisional confidence — the live leaderboards

`app/broker/provisional.py`. A separate worker thread rescoring a **bounded hot
set** (active-signal stocks + near-trigger stocks + watchlist stocks, capped at
`live_provisional_hotset_max` = 150, clipping *logged*) through the **same
frozen scorer** on the same 300-bar window canon **with the forming bar
appended** — so the provisional score *converges* to the committed score at
candle close.

- Published as per-style leaderboards (`intraday`, `swing`, `fno`,
  `investment`, `scalp`, `positional`) over `provisional:{style}` channels,
  top-N=20, refreshed every ~3 s.
- **Provisional-labelled end to end** (`"provisional": true` on every payload):
  never an engine event, never recorded, never replayed, never in backtests or
  P&L. It is a *derived observability view* — a preview of "what would score if
  this candle closed now" — and nothing more. This is the look-ahead firewall
  applied to the UI: you get a live feel without live data ever contaminating
  the record.

## B.7 Signal-outcome recorder — the honesty layer

`app/services/signal_outcomes.py` + the durable alerts-stream consumer. It
watches the `entry_zone`, `sl_touch`, and `tp_touch` alerts and records, per
signal, whether price **entered the zone**, then hit **SL first** or **TP
first** — building an honest hit-rate.

- Idempotent single-statement UPDATEs (the stream is at-least-once); first-touch
  stamps only go NULL→value; terminal statuses never reopen (a monotonic
  ladder: `open → entry_touched → sl_first/tp_first`, or
  `expired_untouched/expired_open`).
- **Resolution requires a prior entry touch** inside validity — a TP cross on a
  never-entered setup is a *missed trade*, not a win. Ordering is pinned so a
  redelivered pre-entry touch can't resolve after entry.
- Observation started at a fixed epoch (2026-07-19); pre-epoch signals are
  never fabricated as outcomes, and hit-rate reporting cohorts on
  `created_at >= epoch`. This is the anti-vanity-metric discipline: the system
  refuses to claim it observed something it didn't.

## B.8 Downstream: position-health & trailing exits (advisory + real)

Once you're *in* a trade, three more mechanisms fire (these manage positions,
not selection, but they share the alert philosophy):

- **Emergency-exit / position-health watcher** (`app/trading/position_health.py`)
  — pure, advisory verdict `HOLD / WATCH / CUT` surfaced on the Positions page.
  Reasons: `thesis_break` (price through stop), `deep_mae` (≥0.8 R underwater),
  `rr_inverted` (more left to lose than gain), `trend_dead` (daily Kaufman
  Efficiency Ratio < 0.30 = choppy), `stale` (past validity). Soft conditions
  escalate to CUT **only when also underwater** — a green trade in chop is a
  hold. It **never executes**; it cuts a losing thesis on evidence instead of
  hope. Born from the 2026-07-30/31 review where week-old choppy swings bled
  out one small loss at a time.
- **Trailing stop-loss** (`app/trading/trail_sl.py`) — governs live PAPER exits
  **when the profit-lock is OFF (the default)**: `none → breakeven` (price +1 R
  → SL to entry) `→ trailing_1` (+1.5 R → SL to entry+0.5 R) `→ trailing_2`
  (+2 R → SL trails at price−1 R). Monotonic; never moves against the position.
- **Layered Ratchet Stop / profit-lock** (`app/trading/profit_lock.py`) — the
  dynamic stop that governs live PAPER exits **when a user opts in**
  (`User.profit_lock_enabled`, Profile → Trading Settings): the tightest of
  {initial risk SL, ATR chandelier `peak ∓ k·ATR`, tapering giveback cap},
  ratcheted one way, per-classification params. Shadow-first (paper-only, gates
  nothing real until Phase 7); the per-class params are still being calibrated
  on the shadow/tape evidence. **Note:** it only *arms* after +`arm_r`·R of
  favourable move (1 R for swing/positional), so below +1 R the stop stays at
  the signal SL — a sub-1 R pop that reverses gives it all back. See
  `docs/analysis/FIX_PLAN.md` (P2).
- **The position monitor** (`app/tasks/position_monitor.py`, every minute,
  **session-guarded** 9:15–15:30 IST) reads the live LTP (Redis, **no stale
  fallback** — evaluating SL/TP against yesterday's close once corrupted the
  paper record), auto-closes on SL/TP, advances the trail, refreshes P&L.

## B.9 Delivery guarantees per channel (the contract)

`.claude/rules/trading-domain.md` §Redis contracts — chosen per data criticality:

| Data | Redis primitive | Guarantee | Rationale |
|---|---|---|---|
| Latest price `ltp:{stock_id}` | KEY, TTL 600 s | last-write-wins | paper_broker reads it for fills; staleness bounded at 10 min |
| LTP / candle fan-out `ltp:{token}`, `candle:{table}:{sid}` | pub/sub | at-most-once (OK to drop) | UI reconciles over REST on reconnect |
| **Alerts** `alerts:live` | **Stream** (MAXLEN ~10k) | **at-least-once** | an alert must not silently vanish; consumers dedupe by (id, day) |
| Signal outcomes | DB rows | durable | the honest record; idempotent writes |
| Leaderboards `provisional:{style}` | pub/sub + TTL'd key | at-most-once | derived view; never load-bearing |

Every cache key gets a TTL (eviction is `volatile-lru`; a TTL-less key is
treated as broker-critical and never evicted).

---

# PART C — WHY THIS IS BETTER THAN WHAT RETAIL TRADERS USE

The benchmark is the toolset a typical Indian retail trader actually reaches
for: **Chartink / screener.in** (SQL-ish scans), **TradingView alerts**
(single-indicator crossovers), **broker scanners** (Kite/Groww built-in), and
**tip / Telegram services**. What this platform does differently:

**1. Confluence gate, not single-indicator triggers.**
Every one of those tools fires on *one* condition ("RSI < 30", "price crosses
20 EMA", "52-week high"). That is exactly the noise that makes 90 % of retail
lose. Here **nothing surfaces unless 5–7 independent factors agree at the same
level and clear a weighted ≥70 % bar** — and the gate *tightens* in weak trends
and *loosens* only in strong ones (ADX regime). Conflicting factors cancel;
counter-trend setups are structurally hard to surface.

**2. A signal is a complete, risk-first trade plan — not an idea.**
Chartink hands you a symbol. This hands you **direction + class + entry + stop
+ target + position size + validity + the exact factors that fired and their
scores**. Sizing is mandatory and derived from *your* capital and risk %. If
the honest stop exceeds the class cap, the trade is **rejected, not fudged** —
no other retail tool refuses a setup for being un-riskable.

**3. Rigorous look-ahead / no-repaint discipline → backtest = live.**
TradingView indicators famously *repaint*; scan tools evaluate on the current,
still-forming bar. Here committed signals compute on candle N and are valid
from N+1, only ever from `is_complete` candles, with a frozen idempotency
guard so history is never rewritten. Everything tick-level is **quarantined as
`provisional`** and can never enter a backtest or the P&L. That's why a
recorded tick session **replays byte-identically** and why the numbers you
backtest are the numbers you'd have traded.

**4. Deterministic Rust compute core with a parity oracle.**
The scoring and trigger logic is a pure, allocation-free Rust engine, gated by
golden fixtures at 1e-9 / 1e-6 tolerances with **exact** equality on factor
scores, confidence integers, and decisions. Retail tools are opaque black boxes
you cannot verify; here every number is reproducible and test-pinned.

**5. Alerts that respect your attention (and your entry).**
Broker/TradingView alerts re-fire every tick a condition holds — unusable in
consolidation. This engine's **arm/disarm state machine with re-arm bands**
fires once and stays quiet until price genuinely retreats. And the
**anti-chase guardrail** actively warns when a trigger has already run past the
point where the trade's reward:risk still holds — no other retail tool tells
you *"don't take this alert, the edge is gone."*

**6. Honest outcome accounting, no vanity stats.**
The outcome recorder only counts a win if the entry was actually touched first,
inside validity, and cohorts hit-rates on a fixed observation epoch — it
refuses to claim results it never observed. Tip services show cherry-picked
wins; this shows the real ledger.

**7. Built for the Indian market specifically.**
IST session alignment (candles anchor 09:15 IST, not naïve UTC hours), the NSE
holiday calendar for trading-day validity, FII/DII institutional-flow factor,
T2T/`-BE`-series exclusion, corporate-action quarantine, sub-paise Decimal
money throughout. Generic global tools get the half-hour IST offset and NSE
microstructure wrong.

**8. Paper-first safety with a hard circuit breaker.**
Live trading requires explicit opt-in **and** a 30-day profitable paper record,
enforced in code. The daily-loss circuit breaker is **never** disableable. This
isn't a scanner that shrugs when you blow up — the platform structurally
prevents it.

The one honest caveat: those tools are broad discovery nets over *thousands* of
stocks with zero setup. This platform is a **precision instrument** — deeper,
verifiable, risk-managed, and Indian-market-native — over a curated universe.
It optimizes for *fewer, better, fully-planned* trades, which is the opposite of
what causes retail losses.

---

# PART D — HOW IT'S CONFIGURED WITH ZERODHA (KITE CONNECT)

Every byte of market data — live ticks, historical candles, the instrument
master — comes from **Zerodha Kite Connect**. There is no other data vendor.

## D.1 Auth & the daily token lifecycle

`app/broker/kite_client.py`.

- **OAuth flow:** `get_login_url()` → user logs in at Zerodha → callback
  returns a `request_token` → `exchange_token()` calls `generate_session` with
  the API secret to get an `access_token`, invalidates any prior active token
  for the user, and persists a `BrokerToken` row.
- **Kite tokens die at ~6:00 AM IST daily** (stored as expiry `0:30 UTC`,
  rolled forward). This is treated as a **normal lifecycle event, not an
  error**: long-running consumers restart, warm up, and gap-fill rather than
  loop on errors. Daily re-login ritual: `scripts/kite_login.py`.
- `get_active_token()` returns the current active, non-expired token.

## D.2 Instrument master sync

`sync_instruments()` downloads Kite's full instruments CSV (~80k rows with NFO)
and upserts `kite_instruments` (NSE/BSE cash + NFO derivatives). The heavy
download+parse+map runs off the event loop (`asyncio.to_thread`). A **two-tier
stale sweep** removes carcasses (delisted / expired / moved) so dead rows stop
JOINing into the subscription universe and drawing `invalid token` errors:

- Rows absent ≥ 7 days → hard-deleted unconditionally.
- A **partial-dump tripwire**: if a dump has < 50 % of the table's rows, the
  younger-absence sweep is skipped with a warning (a truncated download must
  never mass-delete good rows). The watermark is derived from the data itself,
  so it's safe across clock steps.

The stock↔instrument join is on `tradingsymbol + exchange`, filtered to
`instrument_type = 'EQ'` for the equity tick universe.

## D.3 Live ticks — the WebSocket consumer

`app/broker/tick_consumer.py`. `KiteTicker` (kiteconnect's threaded Twisted
client) → asyncio queue → processing coroutine.

- **Subscription:** on connect, subscribe to all mapped instrument tokens in
  **`MODE_FULL`** (full market depth incl. cumulative `volume_traded`),
  `reconnect=True`, `reconnect_max_tries=50`.
- **Thread-safety (critical):** KiteTicker callbacks run on the *ticker's own
  thread*, where `asyncio.get_event_loop()` *raises* on Python 3.12. So the
  loop is captured once in the async context and every hop crosses via
  `loop.call_soon_threadsafe(...)`. Foreign threads never touch asyncio state
  directly (`.claude/rules/python.md`).
- **Bounded queue, drop-oldest** (`maxsize = 10_000`): if the consumer falls
  behind, the *oldest* LTP batch is dropped — losing a stale price beats
  crashing the callback chain. (Candle-closing events are never dropped
  downstream.)
- **Honest volume** (`candle_aggregator.py::_volume_delta`): Kite ticks are
  throttled snapshots, so per-tick `last_traded_quantity` both double-counts
  and misses trades. The aggregator instead **diffs the cumulative
  `volume_traded` counter** and handles the session reset (counter goes
  backwards → new session → count zero, don't count the whole day).
- **Timestamps:** Kite's `exchange_timestamp` is a *naïve* datetime in the
  host's local zone; the aggregator uses `.astimezone(UTC)` (not `.replace`)
  so an IST host isn't mislabelled by +5:30.
- **Session-anchored candles:** buckets anchor at **09:15 IST**, not a naïve
  UTC-hour floor (that half-hour offset is a classic bug source). This matches
  Kite's own 60-minute history.
- On candle close → publish the candle, upsert the row, and (if
  `LIVE_SIGNAL_DISPATCH_ENABLED`) fire the live signal-regeneration Celery task.
- A dead consumer is **loud** (`log.critical`) — silence here once cost a full
  trading day.

The production live path is the Rust-backed `live_worker.py` (the
`LiveBook`/`LiveEngine`), which supersedes the pure-Python aggregator for the
tick-to-trigger hot loop; the Python aggregator remains the reference and the
test seam.

## D.4 Historical data — the throttled REST client

`app/broker/kite_rest.py::ThrottledKite`. **All** Kite REST goes through this;
never raw `requests`/`httpx`/bare `KiteConnect` (`.claude/rules/trading-domain.md`).

- **~3 req/s ceiling** enforced by a monotonic-clock spacing gate
  (`min_interval 0.34 s`), serialized through an `asyncio.Lock`. kiteconnect is
  sync, so every call runs in a worker thread.
- **Backoff sleeps *inside* the gate** on purpose: when Kite pushes back, every
  caller sharing the client pauses, not just one. Retries: 3 attempts, backoff
  1 / 3 / 9 s. Transient set includes the *raw `requests` exceptions* Kite
  re-raises (ReadTimeout/ConnectionError) — not just Kite's own wrapper (this
  was a real production crash). Every attempt consumes rate budget, even
  non-transient failures, so the next caller can't fire unspaced.
- **One `ThrottledKite` per token, shared** — the throttle only spaces calls
  that share the instance. The unthrottled path was the 2026-07-13 rebuild's
  failure root (intermittent `invalid token` at full-universe scale).

## D.5 Reconnect gap-fill

`app/broker/gap_fill.py`. After a disconnect, backfill the missed candles:
find the latest complete candle per (stock, timeframe), request from Kite REST
via the shared `ThrottledKite`, upsert. Two Kite gotchas handled:

- **Naïve-IST datetimes:** kiteconnect strftimes wall-time and Kite reads it as
  IST, so the from/to are passed as *naïve IST* (`.astimezone(IST).replace(
  tzinfo=None)`). Passing UTC-aware datetimes shifts the window 5.5 h into the
  past and silently backfills nothing.
- **`TokenException` aborts the whole run** (the session token is dead — every
  further call is doomed) vs. a per-instrument `InputException` which is
  skipped. Prevents grinding ~6k paced calls after a token death.

EOD daily bars come from the **NSE bhavcopy** (equities bhavcopy task ~18:40
IST / 13:10 UTC), which lands *before* nightly signal generation so both
consume the same fresh data.

## D.6 Configuration knobs (`app/core/config.py`)

| Setting | Default | What it controls |
|---|---|---|
| `kite_api_key` / `kite_api_secret` | — | Kite app credentials |
| `kite_redirect_url` | `.../broker/kite/callback` | OAuth callback |
| `redis_url` | `redis://localhost:6379/0` | fan-out bus + cache + streams |
| `engine_impl` | `python` | `python` reference vs `rust` tradecore scorer |
| `min_signal_confidence` | `70` | the confluence gate (%) |
| `default_risk_per_trade_pct` | `2.0` | whole-percent risk for system signals |
| `live_signal_dispatch_enabled` | `false` | fire per-candle-close signal regen (needs a worker) |
| `live_level_refresh_s` | `30` | signal-level refresh cadence |
| `live_entry_zone_pct` | `0.5` | entry-zone half-width (% of entry) |
| `live_sltp_within_bp` | `25` | SL/TP proximity band (0.25 %) |
| `live_cross_rearm_bp` | `10` | PDH/PDL/S&R cross re-arm band (0.1 %) |
| `live_vburst_mult` | `3.0` | forming-5m volume ≥ mult × 20-day avg |
| `live_alert_stream` | `alerts:live` | the at-least-once alerts Redis Stream |
| `live_alert_maxlen` | `10_000` | stream MAXLEN cap |
| `live_provisional_enabled` | `true` | leaderboard worker thread on/off |
| `live_provisional_refresh_s` | `3.0` | leaderboard cycle cadence |
| `live_provisional_hotset_max` | `150` | bounded rescore hot-set cap |
| `live_provisional_top_n` | `20` | rows per style leaderboard |
| `live_outcome_recorder_enabled` | `true` | durable entry/SL/TP-touch recorder |

## D.7 Scheduling (Celery beat — `app/celery_app.py`, times in UTC / IST)

| Task | Cadence | Purpose |
|---|---|---|
| Equities bhavcopy ingest | 13:10 UTC / 18:40 IST, weekdays | EOD daily candles from NSE |
| Nightly signal generation | 13:45 UTC / 19:15 IST, weekdays | full-universe confluence run (after bhavcopy) |
| Position monitor | every minute, session-guarded 9:15–15:30 IST | SL/TP auto-close, trail advance, P&L refresh |
| Signal expiry sweeper | every 5 min, weekdays | expire lapsed signals, finalize outcomes |

## D.8 Safety posture with real money

- **Paper mode is default.** Live requires explicit opt-in **and** a 30-day
  profitable paper record, enforced in code (not by promise).
- **Daily-loss circuit breaker** (`app/trading/circuit_breaker.py`) — rejects
  new orders once realized loss for the IST day ≤ the user's limit, or the
  max-trades-per-day cap is hit. **Never disableable.**
- **Money is Decimal / Numeric(12,4) / i64·1e-4** end-to-end; floats only
  inside indicator math and display. Storage UTC, market logic IST, tz-aware
  everywhere.

---

# PART E — END-TO-END, ONE PICTURE

```
                          ZERODHA KITE CONNECT
        ┌──────────────┬──────────────────────┬──────────────────┐
        │ instruments  │  REST history        │  WebSocket ticks │
        │ CSV (sync +  │  (ThrottledKite      │  (KiteTicker,    │
        │  stale sweep)│   ~3 req/s, backoff) │   MODE_FULL)     │
        └──────┬───────┴───────────┬──────────┴────────┬─────────┘
               │                   │                    │
        kite_instruments     gap_fill / bhavcopy   tick_consumer /
        (stock↔token)        → ohlcv_* tables      live_worker (Rust LiveBook)
               │                   │                    │
               │                   ▼                    ├─► SET ltp:{sid}, PUBLISH ltp/candle
               │        ┌──────────────────────┐        │
               │        │  COMMITTED ENGINE     │        │  book.on_ticks →
               │        │  (completed candles)  │        │  level crossings
               │        │  run_all_factors →    │        ▼
               │        │  score (≥70% gate,    │   triggers (arm/disarm state machine)
               │        │  ADX regime) →        │        │
               │        │  classify → size →    │        ▼
               │        │  SL/TP (reject caps)→ │   XADD alerts:live (Stream, at-least-once)
               │        │  guards → Signal row  │        │
               │        └─────────┬─────────────┘        ▼
               │                  │ active-signal      WebSocket /ws/live
               │                  │ prices  ───────►   ─ alert  ─► AlertBell
               │                  ▼  (entry/SL/TP)     ─ provisional ─► leaderboards
               │        live_levels.build_directory    ─ ltp/candle ─► charts/tables
               │        (PDH/PDL, vburst, entry zone,        ▲
               │         SL/TP near+touch, S/R) ─────────────┘  (levels set on the LiveBook)
               │
               ▼
        signal_outcomes  ◄──── entry_zone / sl_touch / tp_touch alerts (honest hit-rate)
        position_monitor ◄──── ltp:{sid} (SL/TP auto-close, trail_sl, position_health)
```

---

# Appendix — file map & glossary

**Selection engine**
- `docs/SIGNAL_ENGINE.md` — the protected spec (source of truth)
- `app/analysis/confluence.py` — the scorer (`run_all_factors`, `score_from_factors`)
- `app/analysis/patterns/`, `indicators/`, `structure/` — the 14 factors
- `app/analysis/risk.py` — sizing, SL/TP, volatility reduction, reject-don't-clamp
- `app/signals/classifier.py` · `expiry.py` · `event_guard.py` · `risk_guards.py` · `headline.py`
- `app/services/signal_service.py` — nightly + live generation, engine dispatch
- `app/services/universe_service.py` — eligible-stock resolution
- `app/screener/catalog.py` · `compiler.py` — the manual pre-filter
- `engine/crates/engine-core/` — the parity-gated Rust scorer (`tradecore`)

**Alert engine**
- `app/broker/live_levels.py` — level construction & directory
- `engine/crates/engine-core/src/triggers.rs` — the arm/disarm state machine
- `app/broker/live_worker.py` — tick host, alert publishing (`_publish_alerts`)
- `app/broker/provisional.py` — live leaderboards
- `app/services/signal_outcomes.py` — outcome recorder
- `app/api/v1/ws.py` — WebSocket fan-out
- `frontend/src/features/alerts/` — AlertBell, anti-chase, presentation

**Zerodha integration**
- `app/broker/kite_client.py` — auth, token lifecycle, instrument sync
- `app/broker/kite_rest.py` — the shared throttled REST client
- `app/broker/tick_consumer.py` · `candle_aggregator.py` — WebSocket → candles
- `app/broker/gap_fill.py` — reconnect backfill
- `app/core/config.py` · `app/celery_app.py` — knobs & schedules

**Glossary**
- **Confluence** — multiple independent factors agreeing at one price level.
- **Committed vs provisional** — decided from completed candles (real) vs a
  live preview from the forming candle (never recorded / backtested).
- **R** — one unit of risk = \|entry − stop\|. Targets and trails are in R.
- **RRBO** — Risk-Reward Breakout (the swing 6 %-target setup).
- **Re-arm band** — how far price must retreat before a fired cross can fire
  again (the anti-spam mechanism).
- **PDH / PDL** — previous-day high / low.
- **ER** — Kaufman Efficiency Ratio; the trend-vs-chop regime gauge.
- **CA quarantine** — holding a stock out while a corporate action makes its
  unadjusted history unscoreable.
```
