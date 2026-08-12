# Zerodha Varsity — study & platform assessment (2026-08-12)

**What this is.** The user asked whether Zerodha Varsity
(`https://zerodha.com/varsity/modules/`, 17 modules) is useful for our platform.
Varsity is the authoritative, free, broad Indian-markets curriculum — unlike the
masterclass ([[trading_masterclass_origin]]) it is measured, hedged-risk-first,
and statistically literate. This is a module-level assessment mapping it to our
build; deeper per-chapter reads can follow on any specific topic on request.

> **Depth caveat.** I read each module's chapter list + Varsity's own framing
> (the full chapter bodies render behind the page). That is enough for a
> usefulness/mapping verdict; it is NOT a transcription of formulas. Where a doc
> says "informs X," the detailed chapter is the follow-up read.

> **Two headline uses.** Varsity is the authoritative **corrective** to the two
> riskiest masterclass ideas, and it surfaces **two new strategy families** that
> directly address our current pain (directional entries dying in choppy tape).

---

## 1. The high-value takeaways (read this first)

1. **Varsity corrects the masterclass's valuation.** Fundamental Analysis teaches
   real ratio analysis (profitability / leverage / valuation) + **DCF / free-cash-
   flow** valuation — the authoritative method vs the masterclass's arbitrary
   `FV = BookValue × 10`. When we build the fundamentals layer
   ([[competitor_tools_review_2026-08]]), Varsity's Module 3 (+ Integrated
   Financial Modelling, Module 13) is the reference, not the class.

2. **Varsity corrects the masterclass's option selling.** Option Strategies
   (Module 6) teaches **defined-risk, hedged** structures — bull/bear spreads,
   and the **Iron Condor**, which is precisely the *defined-risk version of a
   short strangle* (sell ATM CE+PE, but BUY protective wings). The masterclass's
   naked intraday short strangle has the same premium-collection profile with
   uncapped tail risk. **If we ever model that "passive income" idea, build it as
   an Iron Condor, not naked** — same theta harvest, bounded max loss. This is the
   single most actionable cross-reference in this review.

3. **Two new strategy families we don't have (Trading Systems, Module 10):**
   - **Pair trading / statistical arbitrage** — correlation → linear regression →
     **ADF cointegration test** → market-neutral entries. **Market-neutral
     sidesteps our exact problem**: it doesn't need a directional regime, so it
     can earn in the choppy tape where our directional profiles give back profit.
     Strong Phase-6+ candidate (needs a §8 backtest; not a factor — a new profile).
   - **Momentum portfolios** — systematic cross-sectional momentum ranking. A
     discovery/ranking lever for selection.

4. **Risk layer — a reference, NOT a new adoption (Risk Management, Module 9):**
   it teaches **position sizing (3 chapters), Kelly's Criterion, Value at Risk, and
   portfolio variance/covariance/correlation**. We already size per-trade (`qty =
   capital×risk% / SL`) and track a crude "portfolio heat." Varsity's
   correlation-aware variance/VaR *would* refine the heat sum (which currently
   treats positions as independent) — **but the Phase-7 backlog already made the
   opposite call on purpose: "simple caps, NOT VaR/ES, NOT a rolling correlation
   matrix" (review P2.2).** So this is a documented *possible reconsideration if
   simple caps prove insufficient*, not an adopted item. Do not build VaR/Kelly as
   a first pass.

---

## 2. Module-by-module verdict

| # | Module (chapters) | Scope | Verdict for us |
|---|---|---|---|
| 3 | **Fundamental Analysis** (16) | Annual reports, P&L/BS/CF, ratio analysis (profitability/leverage/valuation P/S·P/B·P/E), due diligence, **DCF/FCF** | **HIGH.** Authoritative spec for the fundamentals-layer + quality-score build. Corrects FV=BV×10. Same data blocker (`market_cap`/statements). |
| 5 | **Options Theory** (25) | Full Greeks (Δ/Γ/Θ/V), historical vol + normal-dist, moneyness, buy vs **write** calls/puts, M2M/P&L | **HIGH.** The "why naked writing is dangerous" reference; underpins our F&O engine + IV-rank rulings ([[fo_open_calibration_rulings]]). |
| 6 | **Option Strategies** (14) | Spreads (bull/bear, ratio, ladder), long/short straddle & strangle, **Iron Condor**, Max Pain & PCR | **HIGH.** Defined-risk alternatives to naked selling. Iron Condor = the safe version of the masterclass "passive income." |
| 9 | **Risk Management** (16) | Variance/covariance/correlation, portfolio optimization, **VaR**, **position sizing ×3**, **Kelly**, biases | **HIGH.** Correlation-aware portfolio risk + Kelly/VaR upgrade our risk layer & "heat" metric. |
| 10 | **Trading Systems** (16) | **Pair trading** (regression + ADF cointegration), calendar spreads, **momentum portfolios** | **HIGH (new).** Market-neutral & momentum families — candidate profiles, not factors. |
| 15 | **Sector Analysis** (17) | Per-sector fundamental drivers (cement, IT, banking, steel, retail, RE…) | **MEDIUM.** Teaches sector *fundamentals depth*, NOT sector-rotation/RS. Our sector-RS selection (Market Context Engine) is still our own build; this informs the fundamentals side per sector. |
| 2 | Technical Analysis (22) | Patterns, indicators, Dow, multi-TF | **LOW marginal** — overlaps our frozen confluence engine; useful only to sanity-check factor definitions. |
| 4 | Futures Trading (13) | Margins, hedging, contango | **LOW marginal** — overlaps Options/our F&O; relevant at Phase-7 live. |
| 13 | Integrated Financial Modelling (18) | Build a full financial model, valuation | **MEDIUM** — deeper companion to Module 3 for the fundamentals build. |
| 1,7,8,11,12,14,16,17 | Intro / Taxation / Currency-Commodity-GSec / MF / Innerworth / Insurance / SSE / NPS | — | **Out of scope** for the trading platform (personal-finance / tax / psychology-only). |

---

## 3. How it answers the original questions

- **Stock selection:** Fundamental Analysis + Sector Analysis give the
  authoritative fundamental screen (real ratios, per-sector drivers) for the
  fundamentals layer; **Momentum portfolios** (Module 10) is a systematic
  ranking lever. Sector *relative-strength* selection remains our own build.
- **Entry/exit:** Technical Analysis overlaps what we already encode; the genuine
  add is **pair-trading entries** (market-neutral, regime-agnostic).
- **F&O / "passive income":** Options Theory + Strategies say the same thing our
  invariants do — **defined-risk (Iron Condor) over naked short strangle.** This
  is the concrete safety upgrade to the masterclass idea.
- **Risk:** Kelly, VaR, and correlation-aware portfolio variance are real upgrades
  to our per-trade sizing and portfolio-heat metric.

---

## 4. Recommendation (dependency-ordered, mapped to phases)

1. **Now (reference, no build):** treat Varsity Module 3/13 as the spec for the
   fundamentals-layer + quality scores (still gated on the `market_cap` data
   decision). Treat Module 5/6 as the design authority for any future
   option-selling work — **Iron Condor, never naked.**
2. **Phase 6 candidate:** a **pair-trading / market-neutral profile** — the most
   promising *new* idea here because it's regime-agnostic (our directional
   profiles fail in choppy tape). Needs cointegration screening + a §8 backtest;
   it's a new profile in the confluence framework, never a bypass of the ≥70% gate.
3. **Phase 7 (live options):** if the masterclass option-selling idea is ever
   built, it is an **Iron Condor (defined-risk), never naked** — needs the live
   options order path, paper-first, §8 gap-through-SL backtest.
4. **Not adopting:** correlation-aware VaR/Kelly (§1.4) — the Phase-7 backlog
   deliberately chose simple exposure caps over VaR/correlation (review P2.2);
   kept only as a documented reconsideration.

**Not doing from Varsity:** taxation, currency/commodity/GSec, MF/insurance/NPS,
Innerworth (pure psychology). TA/Futures are confirmation-only (already ours).

---

## 5. Related
- [[trading_masterclass_origin]] · `docs/TRADING_MASTERCLASS_REVIEW_2026-08-12.md`
- `docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md` (fundamentals / seasonality plan)
- `docs/phases/phase-06-plan.md` (entry/regime selection — pair-trading candidate lands here)
- Deeper per-chapter reads (formulas) available on request for: Fundamental ratios/DCF, Option Greeks/vol, Iron Condor mechanics, Kelly/VaR, pair-trade ADF method.
