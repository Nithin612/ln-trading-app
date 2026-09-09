# U1 detail/cohort cluster — API + layout proposal (for sign-off)

**Status:** APPROVED (A/B/C/D as recommended, user 2026-09-09) · branch `feature/pre-cycle2-hardening`
**Progress:** ✅ Trio (U10/U15/U17) BUILT · ✅ U11 BUILT (Decision B = backtest curve) · ✅ U20 BUILT
(Decision C = light SVG contact sheet) — all 2026-09-09. **U19 is the only remaining item.**
⚠ U11/U20 render empty against the current dev DB (index_ohlcv_1d + signals wiped 09-07); code is
fully test-backed (tests seed their own data), a browser smoke waits on a dev-DB backfill (user deferred).
**Scope:** U10 · U15 · U17 (signal-detail trio) · U20 (would-block cohort as charts) ·
U11 (benchmark on every curve) · U19 (horizon/lag). The U1 *page* already shipped
(`/analytics/registry` + `GET /analytics/gate-register`); this is the explorable half.

> Standing truth, unchanged: **none of this attacks profitability** (both levers spent — D5
> exit geometry, D1 generation/RVOL). It is a legibility + evidence surface that makes the
> next lever-hunt faster and promotion decisions harder to get wrong. Touches **no recorded
> number** → builds under cycle 2's clock, no reset.

---

## 0. What already exists (so we extend, not rebuild — W2)

| Need | Already on disk | Consequence |
|---|---|---|
| Per-factor weight/score/explanation | `Signal.factor_scores` JSONB = `{NAME:{weight,score,explanation}}`, **all factors incl. score-0 abstainers** (`signal_service.py:271`), already on `SignalOut` | **The trio needs NO new signal API.** All of U10/U15/U17's data is in the payload the detail modal already receives. |
| Named evidence | `triggering_patterns` / `triggering_indicators` arrays, already on `SignalOut` | U15 is a render of existing fields. |
| The exact arithmetic | `confluence.py:159-166` (frozen): `num = Σ w·s (all)` · `den = Σ w where s≠0` · `norm = num/den` · `conf = int(|norm|·100)` | U10 renders this; the SRTL surface is literally `den` excluding abstainers. |
| Existing detail UI | `SignalDetailModal.tsx` already plots a factor bar chart + pills | The trio is a **redesign of that one section**, not a new screen. |
| Benchmark data | `buy_and_hold.py` (NIFTY50 return over the paper window, scalar) · `benchmark.py` (per-signal RS) · `IndexOhlcvDaily` (daily index closes) | U11 needs a daily **series**, a small extension of existing data. |
| Equity curves | Only backtest runs: `/strategy/runs/{id}` → `equity_curve`, rendered by `EquityCurveChart.tsx` (already has a `ReferenceLine` at 100). **No paper-book curve endpoint.** | U11 attaches to the backtest curve now; a book curve is a separate (optional) build. |
| Cohort logic | shadow sidecars `chase_shadow` · `entry_quality_shadow` · `regime_gate_shadow` · `liquidity_shadow` · `circuit_gate_shadow` · `market_regime_shadow` · `sector_rs_shadow` compute flagged-vs-passed sets (markdown today) | U20/U19 reuse the flagged set + add OHLC / horizon derivation. |
| Excursion/horizon raw data | `SignalOutcome.mfe_r/mae_r + mfe_at/mae_at`, entry/sl/tp touch times | U19's per-day R separation is derivable; no new recorder. |

**Net:** the trio is ~90% frontend + one tiny backend helper; U11/U19 are one small endpoint
each; **U20 is the only heavy, design-sensitive piece.**

---

## 1. Information architecture (3 surfaces)

1. **Signal-detail surface** (`SignalDetailModal` + the detail page AlertBell opens) →
   **U10 + U15 + U17**. Replaces the current "Factor breakdown" bar with the trio.
2. **Gate drill-down** — new route `/analytics/registry/:gateKey`, reached by clicking a row on
   the shipped registry page → **U20 + U19**. This makes U6's "kept-visible failures" actually
   explorable (regime −8R, R:R+₹10,585 cohort become browsable, not prose).
3. **Strategy/backtest curves** (`StrategyLabPage` → `EquityCurveChart`) → **U11** (benchmark as
   a default second series).

---

## 2. API surface

### 2.1 Trio — `GET /signals/{id}` gains `confidence_breakdown` (one small field)

No new route. One new **reporting-only** pure module `app/signals/confidence_explain.py`
(NOT the frozen engine — it reads stored `factor_scores`, reproduces the frozen formula, and is
unit-pinned to equal the stored integer). Attached to the **detail** endpoint only (one signal
can afford it; the list stays lean).

```jsonc
"confidence_breakdown": {
  "numerator":   37.0,        // Σ weight×score over ALL factors
  "denominator": 45.0,        // Σ weight where score≠0  (abstainers excluded — the SRTL surface)
  "normalized":  0.822,       // numerator / denominator  ∈ [-1,1]
  "confidence_pct": 82,       // == signal.confidence_pct  (INVARIANT, tested for every signal)
  "direction": "BUY",
  "scoring":   [{"name":"MACD_CROSS","weight":20,"score":0.90,"contribution":18.0,"explanation":"…"}, …],
  "abstained": [{"name":"ADX","weight":15,"explanation":"…"}, …]
}
```

> **DECISION A —** compute the arithmetic in the **backend helper** (recommended) vs in JS.
> Backend avoids a JS reimplementation of a frozen formula silently drifting (W2/W5), and the
> `confidence_pct == stored` invariant is a real test. Cost: ~1 module + 1 test + 1 response field.
> Needs a quant-verifier pass (it mirrors frozen arithmetic, read-only).

### 2.2 U11 — `GET /analytics/benchmark-curve`

```
GET /analytics/benchmark-curve?run_id=<backtest run id>       # align to a backtest run's dates
GET /analytics/benchmark-curve?from=<date>&to=<date>          # generic window
→ { "symbol":"NIFTY50", "basis":100.0, "points":[{"date":"2026-07-03","idx":100.0}, …] }
```
NIFTY50 close-to-close from `IndexOhlcvDaily`, indexed to 100 at the window start, aligned on
common trading days. Frontend adds a second `<Line>` to `EquityCurveChart`.

> **DECISION B —** attach the benchmark to the **backtest curve only** (cheap, real, ships now)
> vs also build a **paper-book equity curve** (no endpoint exists → a separate small build:
> daily book equity = realised + open MTM over capital, indexed). Recommend: backtest now,
> book-curve as a fast-follow if you want the benchmark on the book itself (that is the H2 point).

### 2.3 U20 — `GET /analytics/cohort/{gate_key}`

`gate_key` is a register key (drives off the shipped `gate-register`). Returns the trades the gate
flagged/would-block, each with a small OHLC window for a contact sheet.

```jsonc
{
  "gate_key":"regime", "gate_status":"reverted",
  "would_block_count":44, "cohort_r_total":-8.0,
  "trades":[{
    "signal_id":"…","symbol":"SRTL","direction":"BUY","entry_date":"2026-08-14",
    "entry":39.0,"stop_loss":38.6,"take_profit":42.0,
    "outcome_status":"sl_first","realized_r":-1.21,
    "candles":[{"t":"…","o":..,"h":..,"l":..,"c":..}, …]   // ~30 bars around entry, ohlcv_1d
  }, …]
}
```
Reuses each sidecar's flagged-set predicate + an `ohlcv_1d` window. Read-only.

> **DECISION C —** rendering fidelity. Recommend a **light SVG/Recharts mini-panel** (OHLC window
> + entry/SL/TP lines + outcome glyph) over TradingView Lightweight Charts for v1 — the point is
> "see the set as one contact sheet", not tick fidelity. Upgrade later if it earns it.

### 2.4 U19 — `GET /analytics/cohort/{gate_key}/horizon`

```jsonc
{ "gate_key":"regime", "days":[0,1,2,3,4,5],
  "flagged_mean_r":[-0.18,-0.22,…], "passed_mean_r":[0.05,0.11,…],
  "flagged_hit_ge_1r":[0.08,0.10,…], "passed_hit_ge_1r":[0.12,0.30,…] }
```
Derived from `SignalOutcome` MFE-R timing per cohort. Reproduces the horizon finding
(entry-day ≥1R 12% vs swing 36% / positional 54%, +1R ≈ d+3) as a per-gate chart.

> **DECISION D —** the reading. Recommend **mean-R (and ≥1R-hit) by holding day, flagged vs
> passed** (directly answers "at what horizon does this gate separate winners from losers?").
> Alternative: a pure Pearson-corr-vs-lag bar. The former is more decision-useful here.

---

## 3. Chart layouts

**U10 — "How this 82% was built" card** (replaces the raw bar):
```
factor            weight   score    contribution
MACD_CROSS          20   × +0.90  =   +18.0
RSI_DIVERGENCE      15   × +0.80  =   +12.0
VOLUME              10   × +0.70  =   + 7.0
ADX                 15   ×  0.00      — abstained —     ← greyed, NOT in divisor
EMA_STACK           12   ×  0.00      — abstained —
────────────────────────────────────────────────
Σ contribution (numerator)     =   +37.0
Σ weight of SCORING factors    =     45
37.0 ÷ 45 = 0.822  →  ×100  →  82% BUY   (truncated)
⚠ 3 of 5 factors scored — abstainers DROP OUT of the divisor (the SRTL surface).
```

**U17 — one stacked distribution bar** (shape of the vote, abstainers visible):
```
Confidence 82% BUY   ·   3 of 5 factors voted
[███ MACD +18 ███ RSI +12 ██ VOL +7 │ ░ ADX ░ EMA ░]
 └──────── scoring (in divisor) ──────┘ └ abstained ┘
```

**U15 — named-evidence line** (plain language + horizon):
```
Evidence: MACD bullish crossover · RSI divergence · volume spike
Horizon:  swing — graded over 5 trading days (+1R typically d+3)
```

**U11 — benchmark on the curve:**
```
110┤            ╭──── book
100┤━━━━━╮ ╭━━━━╯
 95┤     ╰━╯·····  NIFTY50 (buy & hold, same window)
   └──────────────────────────
⚠ book risks ~₹2k/trade — exposure 9% (not deployed alike; reader draws the line)
```

**U20 — would-block cohort contact sheet** (`/analytics/registry/regime`):
```
regime (reverted) — would have blocked 44 trades   ·   cohort −8.0R
┌──────┐┌──────┐┌──────┐┌──────┐
│SRTL  ││IDEA  ││YESBK ││ …    │   each panel: ~30-bar OHLC + entry▸SL▸TP + outcome glyph/R
│ ╱╲   ││  ╱   ││╲     ││      │
│╱  ╲_ ││_╱    ││ ╲__  ││      │   sorted by |R|.  "Statistics say whether; charts say what."
│▼-1.2R││▲+0.9 ││▼-1.0 ││      │
└──────┘└──────┘└──────┘└──────┘
```

**U19 — horizon separation** (same drill-down):
```
Mean R by holding day — flagged vs passed
+0.4┤              ╭─ passed
+0.2┤         ╭────╯
 0.0┼────╌╌╌╌╌┼╌╌╌╌╌╌╌╌  (zero ref)
-0.2┤ ╰──╮────╯ flagged
    └─d0─d1─d2─d3─d4─d5
```

---

## 4. Build order + effort (~4–6 d, matches findings-doc estimate)

1. **Trio (U10+U15+U17)** — ✅ DONE 2026-09-09. `app/signals/confidence_explain.py` (read-only) +
   `confidence_breakdown` on `GET /signals/{id}` + the redesigned `SignalDetailModal`. Tests green
   (backend 26 · Vitest 421); quant-verifier + ui-reviewer run at build.
2. **U11** — ✅ DONE 2026-09-09. `app/services/benchmark_curve.py` + `GET /analytics/benchmark-curve`
   + a dashed benchmark series on `EquityCurveChart` (lazy fetch on run-row expand). quant-verifier PASS;
   ui-reviewer fixed (`toFixed`→`formatPct`). Backtest curve only (book curve not built — Decision B).
3. **U19** — ~0.5–1 d (REMAINING). horizon endpoint + Recharts, on the gate drill-down.
4. **U20** — ✅ DONE 2026-09-09. `app/services/gate_cohort.py` (reuses `eligibility.preview`, W2) +
   `GET /analytics/cohort/{gate_key}` + `has_cohort` on the register + `CohortPage` light-SVG contact
   sheet at `/analytics/registry/:gateKey`. Supported for regime/diversity/rr (signal-only gates).

Each ships with tests + CHANGELOG + the doc-sync ritual; no recorded number moves.

## 5. Decisions summary (for sign-off)

- **A** — U10 arithmetic: backend helper (rec.) vs JS.
- **B** — U11: backtest curve only (rec.) vs + paper-book curve.
- **C** — U20 render: light SVG/Recharts (rec.) vs Lightweight Charts.
- **D** — U19: mean-R-by-day flagged-vs-passed (rec.) vs corr-vs-lag bar.
