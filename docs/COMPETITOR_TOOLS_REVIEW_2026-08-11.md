# Competitor / reference-tool review — 2026-08-11

**What this is.** On 2026-08-11 the user captured 66 screenshots (in
`~/zerodha money control/`) from four products and asked whether anything in
them is useful to us. This is the review + the resulting build plan. It is
**descriptive and advisory**, not a commitment; the actionable items are folded
into the phase-mapped backlog in `docs/PHASES.md` (Architecture-review backlog)
and point back here for detail.

**The one caveat.** These are screenshots of *other people's products*, not data
feeds. None of it is ingestible — Tijori / MoneyControl / Streak / Sensibull
have no open API and we only integrate Kite. So the value is (a) a **feature
benchmark** for our own screener/scans surfaces and (b) a **shopping-list of
derived metrics** we would have to compute ourselves. Every "build" below is
therefore *our* computation over *our* data, gated by whether the input data
exists (most of the fundamentals do not — see §4).

**The invariant that governs all of it.** Our screener is a **sieve**, the
confluence engine is the **judge** (`STOCK_SELECTION_AND_ALERTS.md` §A.2). Any
scan/filter/score below is **discovery** — it narrows the universe that feeds
the pipeline (`universe_service.resolve_universe`) and **never emits a signal**.
Signals exist only when candidates clear the ≥70% confluence gate
(`backend/app/analysis/confluence.py:168`, `score_from_factors`). The
single-number "technical ratings", analyst targets, and mSCOREs these tools sell
as buy/sell calls are exactly the single-indicator trap our confluence-only rule
forbids; they may inform *discovery* or act as a *gate/modifier*, never as an
additive factor. This is not a new rule to add — it already exists and is
enforced by code structure.

---

## 1. Verdict by source

| Source (screenshots) | What it shows | Verdict for us |
|---|---|---|
| **Zerodha Kite + Streak** (`technicals.zerodha.com`) | Technical summary scoring (bull/neutral/bear counts), S/R pivots, candlestick "technical events", SMA crossovers, RSI, dashboard scanners (top gainers/losers, ORB, volume breakout, adv/decline), sector/index heatmaps | Mostly **already ours or trivially derivable**. Heatmaps/adv-decline = low-value UI. The single-number technical rating is **invariant-risky** (discovery only). |
| **Tijori Finance** | Per-stock fundamentals: PE/PB/ROE/ROCE/EPS/div-yield/sector-PE, P&L·BS·CF (yr+qtr), revenue mix, quarterly shareholding (promoter/FII/DII/retail), peer table, **Forensics** accounting-quality checklist | **Real gap.** This is the fundamentals depth our screener lacks. Blocked on a data source (§4). |
| **Sensibull** (Kite option chain) | OI, Call/Put LTP, per-strike Greeks (Δ/Γ/Θ/V/IV), **PCR 0.42 · Max Pain 240 · ATM IV 20.40 · IV-percentile 47 "Medium"** | **Already ours** — `fo_analytics.py` computes PCR/MaxPain/IV-rank; `daily_report.py` §7 surfaces it; IV-rank gates option-selling. Confirmation, not gap. Ties to the 2 open F&O rulings ([[fo_open_calibration_rulings]]). |
| **MoneyControl** (Adani Enterprises page) | mSCORE, SWOT, MC Technicals (Classic/Fib/Camarilla pivots, MA table, daily/weekly/monthly), **Stock Vitals** (Altman Z / DuPont / Graham / Ohlson), Forecast (analyst targets/consensus/estimates), Price&Volume (returns, delivery%), **Seasonality**, and a **Scans library** (technical + fundamental, with explicit formulas) | The **richest source.** Scans library → §3; quality scores → §5; seasonality → §6. Forecast/mSCORE = **invariant-risky** (opinion data, gate/modifier only, ~0 directional alpha per [[market_context_engine_deferred]]). |

---

## 2. What we already have (do not rebuild)

- **Option-chain analytics** — PCR (`fo_analytics.put_call_ratio:123`), Max Pain
  (`:138`), IV-rank/percentile (`:714`, `GET /fo/iv-rank`), VIX + regime
  (`vix_service`, `fo_analytics.vix_regime`), all surfaced in the daily report §7
  (`daily_report.build_fo_health:1170`, `_render_fo_section:1437`). The Sensibull
  shots match this one-for-one.
- **Pivots / MAs / RSI math** — the frozen engine computes these; the Streak/MC
  pivot tables and MA ladders are re-presentations of numbers we already own.
- **Saved screens** — `SavedScreen` (JSONB `filter_spec`) + `STARTER_SCREENS`
  already exist (`app/screener/`, `ScreenerPage.tsx`). The "scan library" concept
  is *partially built*; §3 is about filling it, not inventing it.
- **The competitive framing** — `STOCK_SELECTION_AND_ALERTS.md` §C already argues
  why we beat Chartink / screener.in / TradingView scans (no repaint, durable
  levels, confluence-gated). This review does not change that thesis.

---

## 3. The MoneyControl Scans library — transcribed, mapped to our seam

MoneyControl exposes ~20 named scans, each with the literal boolean formula.
These are a ready-made catalog for our `SavedScreen` / `STARTER_SCREENS`. **The
blocker is not the formula — it is the input data.** Our screener today filters
only the static `stocks` master; it has **no price/indicator join** (the
`rsi_14` / `price_vs_ema50` / `fii_net_5d_cr` catalog entries are `available=False`
stubs) and **no fundamentals** (§4). "Can express today?" reflects that.

### 3a. Technical scans (need a price/indicator join into the screener)

| Scan | Formula / meaning | Input needed | Can express today? |
|---|---|---|---|
| Ultra-Short Bearish Crossover | 5-DMA crosses below 13-DMA | 5/13 SMA of close | ⚠ have OHLCV; need SMA fields wired |
| VWAP Breakdown | close < 20-day VWAP | rolling VWAP | ⚠ derivable from OHLCV+vol |
| Above Average Volume | volume > N-day avg volume | volume + avg | ⚠ derivable |
| Open = High | day open == day high | daily OHLC | ⚠ derivable |
| Weekly Breakdown | breaks previous-week low | weekly aggregation | ⚠ derivable |
| Intraday SuperTrend Rider | price vs intraday SuperTrend | intraday ST | ⚠ intraday tape exists; ST not computed |

All ⚠ = **data we already ingest** (5y EOD + 1m/5m/15m tapes), but the screener
cannot *reach* it. Enabling technical scans = turning the `available=False`
stubs real by joining a latest-indicator snapshot into `compile_screener`. No
external data required — medium engineering lift.

### 3b. Fundamental scans (need the fundamentals layer of §4)

Verbatim formulas (MoneyControl uses `MarketCap` in cr; note **every one**
thresholds on MarketCap, which we cannot populate today — §4):

| Scan | Formula |
|---|---|
| Decreasing Debt/Equity | `D/E < D/E_1yrBack AND MarketCap > 250` |
| Double Dhamaka | `NetProfit > NetProfit1YrBack AND NPM > NPM1YrBack AND NetProfit1YrBack > 0 AND MarketCap > 250` |
| High Promoter Holding | `PromoterHolding > 70 AND MarketCap > 500 AND Pledged% < 1` |
| Promoter Increasing Holding | `PromoterHolding > PromoterHolding1QtrBack AND MarketCap > 500` |
| Low Public Holding | `PublicHolding < 10 AND MarketCap > 500` |
| Rising Book Value | `BookValue > BookValue1YrBack AND BookValue1YrBack > BookValue3YrsBack AND MarketCap > 500` |
| Price/Book Above Industry | `PBV > IndustryPBV AND MarketCap > 500` |
| Premium To Peers | `PE > IndustryPE AND MarketCap > 500` |
| FII Selling, DII Buying | `DIIHolding > DIIHolding1QtrBack AND FIIHolding < FIIHolding1QtrBack AND MarketCap > 250` |
| Decreasing Promoter Pledge | `PromoterPledge < PromoterPledge1QtrBack AND MarketCap > 250` |
| Profit To Loss | `NetProfit1YrBack > 0 AND NetProfit2YrBack > 0 AND QuarterlyNetProfit < 0 AND NetProfit1QtrBack > 0 AND MarketCap > 250` |
| Deteriorating Cash Conversion Cycle | `CCC > CCC_5YrAvg AND MarketCap > 250` |
| Operations Unsuccessful | `CFO < CFO_1YrBack < CFO_2YrBack < CFO_3YrBack AND MarketCap > 250` |
| Profit Pioneers | `NetProfit3yrCAGR > 25 AND NetProfitGrowth > 25 AND MarketCap > 500` |
| Falling Quarterly Profits | `QuarterlyNetProfit < NetProfit1QtrBack AND MarketCap > 500` |

These are a clean spec for a fundamentals-scan module once the data exists. They
are **discovery filters** — a `SavedScreen` result is a candidate list, not a
trade. Overlaps with the already-listed **PKScreener setup harvest** (Phase 6,
`EXTERNAL_LIBS_REVIEW_2026-08-02.md`): treat both as one scan-catalog effort.

---

## 4. Fundamentals — the real gap, and the honest blocker

Ground truth (verified 2026-08-11): the `Stock` model has `sector` /`industry`
(now ~500/2365 populated after the 08-07 interstitial slice, was 59) and an
**unpopulated `market_cap_cr` (no writer exists anywhere)**. There are **no**
PE / PB / ROE / ROCE / EPS / book-value / debt columns, **no** financial-statement
storage, and **no** per-stock shareholding-pattern table (`FiiDiiDaily` is
market-wide *flow*, not per-stock *holdings*).

So the Tijori/MoneyControl fundamentals are **greenfield**: a new
`stock_fundamentals` table (ratios + latest statements + quarterly shareholding)
+ an ingestion job.

**The blocker is data sourcing, and it needs a decision:**
- `market_cap` = price × shares-outstanding. **NSE publishes no free
  shares-outstanding feed** (this is why `market_cap_cr` was never populated).
  Yet MarketCap thresholds gate ~every fundamental scan and are the screener's
  headline numeric filter → **market_cap is the keystone unlock.**
- Candidate sources (a decision, not decided here): (a) **BSE/NSE XBRL** quarterly
  results — free, but heavy parsing; we already ingest filing *announcements*
  (`filings_consumer`) so extending to XBRL line-items is the natural path;
  (b) a **paid fundamentals API** — clean, costs money; (c) **screener.in-style
  scrape** — fragile + ToS risk, not recommended.

Recommendation: don't build the fundamentals table until (a)/(b) is chosen —
an empty table repeats the `market_cap_cr` mistake (a filter that silently
returns nothing). Feeds the deferred **Market Context Engine** fundamental gate.

---

## 5. Quality / forensic scores (MoneyControl Stock Vitals · Tijori Forensics)

All are closed-form off filed statements → **no look-ahead** (period-end data),
and **100% greenfield** (nothing exists). They belong as a **fundamental
quality gate/modifier** on the Investment/positional side, never as additive
confluence factors. All are **blocked on §4** (they consume the same statements).

- **Altman Z''-score** (emerging-market variant MC shows):
  `Z = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4`, where X1 = WorkingCapital/TotalAssets,
  X2 = RetainedEarnings/TotalAssets, X3 = EBIT/TotalAssets, X4 = BookEquity/TotalLiabilities.
  Zones: `>2.6` safe · `1.1–2.6` grey · `<1.1` distress. **Distress screen / veto.**
- **DuPont ROE** = NetProfitMargin × AssetTurnover × EquityMultiplier
  (the shown 11.98% = 9.65% × 0.38 × 3.23). Decomposes *why* ROE is high —
  margin vs turnover vs leverage. **Quality context, not a gate.**
- **Graham Number** = `√(22.5 × EPS × BVPS)` = a conservative fair value; price
  above ⇒ "overvalued". **Value-overreach flag** for positional entries.
- **Ohlson O-score** = 9-variable logistic bankruptcy model; probability
  = `e^O/(1+e^O)`, lower O ⇒ safer. **Bankruptcy-risk veto** (pairs with Altman).
- **Tijori "Forensics"** = a proprietary accounting-quality checklist (8 yes /
  7 no / 2 neutral). We can't replicate the exact checklist, but the *idea* — a
  panel of red-flag checks (receivables vs sales, CFO vs PAT, promoter pledge
  trend, auditor changes) — is a good Market-Context input.

---

## 6. Seasonality — the one cheap, genuinely-new win

MoneyControl's Seasonality ("11 of 18 years Adani gave negative returns in
August", with max/avg positive/negative change per month) is **greenfield for
us** — but unlike §4/§5 it needs **no new data**: it is a pure aggregation over
our existing 5y EOD OHLCV. Compute a per-stock (and per-index) monthly
return distribution → a **context flag / soft modifier** ("this name is
seasonally weak in August, n=18"). Cheap, honest (report n, refuse to rank thin
samples — the StyleStatsHeader precedent), and new. This is the item I'd pick up
first.

---

## 7. Priority (honest, dependency-ordered)

1. **Seasonality** — no new data, no engine change, genuinely new. Smallest lift,
   ships alone. → Market Context Engine bucket, but doable early.
2. **Technical-scan enablement** — wire indicator/price fields into the screener
   catalog (make the `available=False` stubs real) so §3a scans + the PKScreener
   setups can be saved-screens. Data we have; medium lift.
3. **`market_cap` sourcing decision** — the keystone. Unblocks the existing
   screener's main numeric filter *and* ~all §3b fundamental scans. Needs the
   user's call on source (§4).
4. **Fundamentals table + quality scores** — after (3). Biggest lift; feeds the
   Market Context fundamental gate. Any behaviour-change needs a §8 backtest.

**Explicitly not doing:** heatmaps/adv-decline (low value, derivable), analyst
targets / mSCORE / technical-rating single-numbers (opinion data — gate/modifier
only per [[market_context_engine_deferred]], never additive), any F&O rebuild
(already ours).

## 8. Related

- `docs/STOCK_SELECTION_AND_ALERTS.md` §A.2 (screener sieve), §C (vs retail tools)
- `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` (PKScreener setup harvest — same effort as §3)
- `docs/PHASES.md` → Architecture-review backlog (Phase 6 · Market Context Engine)
- Memory: [[menu_surface_audit_2026-08-07]], [[market_context_engine_deferred]],
  [[external_libs_review_2026-08]], [[fo_open_calibration_rulings]]
