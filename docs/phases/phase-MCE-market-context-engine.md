# Market Context Engine (MCE) — design capture

**Status: DEFERRED / not started.** The named phase **after Phase 6.8, before Phase-7
(live)**. This doc captures the *entry-context* design agreed 2026-08-18 (the SRTL /
entry-selection discussion) so it's front-of-mind when we build it. Full prior context:
the `market_context_engine_deferred` memory + `docs/Market_Context_Engine_Spec.docx`
(spec on disk). This is a design capture, not yet a sliced plan.

## Why the MCE exists — the entry-context gap

The core confluence engine that mints tradeable single-name signals is **pure bottom-up
technical confluence** (~14 weighted factors: Dow trend, EMA cross, price-vs-EMA, S/R,
RSI, MACD, BBANDS, ADX, FII/DII, etc.). A serious process is **top-down AND bottom-up**;
we only have the middle step. Three context layers are **missing from the tradeable
engine** (confirmed against the code 2026-08-18):

1. **Sector / index relative-strength.** There is NO "Bank Nifty is leading today →
   prefer/boost its constituents" logic in the tradeable engine. What exists: a light
   **FII/DII flow** factor (weight 5, macro), a `sector` field + index flags
   (`is_nifty50`/`is_banknifty`/`is_finnifty`), and an `eval_relative_strength` — **but
   that RS lives in the intraday *profile* strategies, which are SHADOW-only** (walk-forward
   negative, never tradeable). The user's top-down instinct (index/sector leadership feeding
   stock selection) is genuinely absent.
2. **Fundamentals.** Not integrated. **Blocked on the `market_cap` data source** (no free
   NSE shares-outstanding writer — the keystone blocker; the 6.8 **F1 spike** de-risks it).
3. **News / sentiment.** Not integrated into entry selection. Only `event_guard` exists (it
   *suppresses* around scheduled events). ~40% of MCE plumbing exists: `event_guard`,
   fo_data (VIX / PCR / MaxPain), FII/DII flows.

## The load-bearing design principle — GATES/MODIFIERS, not additive factors

**Do NOT bolt context on as new additive confluence factors.** Rationale:
- **News/sentiment have ~0 directional alpha but high VETO value** — they belong as
  gates/vetoes (block/suppress), not as a ± score added to confidence.
- **Regime/sector context is a MODIFIER** — it scales or gates an existing technical signal
  (e.g., "long only if the stock's sector is leading"), it doesn't manufacture a signal.
- Naive additive factors overfit toward volume/context and dilute the ≥70% confluence gate.
  This is exactly why the intraday profiles (which *do* use relative strength) went
  walk-forward-negative and are stuck in shadow — a cautionary precedent.

**Two lanes, matching the Phase-6.8 discipline:**
- **Overlay lane (cheap, safe):** sector-RS / fundamental / news checks as downstream
  **eligibility gates or confidence modifiers** — the `regime_guard`/`circuit_guard`/
  `entry_quality` pattern (frozen engine untouched, shadow-first, flip on §8 + sign-off).
- **Factor lane (expensive, R-track):** a sector-relative-strength *factor* INSIDE the
  frozen confluence engine is a **frozen-engine change** → full ceremony: regenerate the
  Rust oracle fixtures + `§8` regression on 2y × Nifty50 + explicit user sign-off. Not a
  quick add.

**Every context signal is §8-backtested on ≥2y before it can go live.** No exceptions.

## Components (when built)

1. **Sector / index relative-strength gate/modifier.** Compute each index's (Nifty,
   BankNifty, FinNifty, sector) relative strength for the session; gate or boost a
   single-name signal by whether its sector/index is leading. Data available today (index
   OHLC + `sector` + index-membership flags) — this is the most buildable, and directly
   answers the user's Bank-Nifty-leadership idea. Start as an overlay (shadow), promote to a
   confluence factor only via the R-track.
2. **Fundamentals gate.** Quality/valuation thresholds (Varsity M3/M13; corrects FV=BV×10).
   **Gated on the F1 `market_cap` writer** — nothing fundamental unlocks until a data source
   is chosen (yfinance MVP vs XBRL). Use as a gate (exclude junk), not an additive score.
3. **News / sentiment veto.** Extend `event_guard` from scheduled-event suppression to a
   news/sentiment veto (earnings blackout, rating changes, adverse headlines). Veto value
   only — never a directional add.
4. Also in the MCE remit (from the review backlog): 200-DMA / VIX regime gate, earnings
   blackout, long/short-vol F&O toggle, seasonality.

## REQUIREMENT — the daily analysis report must surface context (post-MCE)

**When the MCE is built, extend `services/daily_report.py` so the daily report SHOWS the
context signals**, so we never again trade blind to them (the way we currently trade blind
to sector leadership). Concretely, add a report section covering, per entry:
- the stock's **sector / index relative-strength** that day (was its sector leading?),
- any **fundamental gate** flag (quality/valuation), and
- the **news/sentiment gate** status (event blackout, adverse news veto).
Mirror the existing gate-shadow sidecars (`regime-gate-shadow`, `circuit-gate-shadow`,
`entry-quality-shadow`): each context gate accrues a shadow report + a flip-readiness banner
before it goes active. This bullet is the reminder to wire that in — do not skip it.

## Cross-references
- The entry-selection discussion + verdict ("single factor is not an entry"): the
  **entry-quality overlay** (`app/signals/entry_quality.py`) is the *breadth* fix shipped now;
  the MCE is the *context* layer. See `docs/analysis/exit-ladder-research-2026-08-18.md`.
- Positioning: PHASES.md (MCE = the phase after 6.8, before Phase-7 live).
- Prior scope + decisions: the `market_context_engine_deferred` memory; spec docx on disk.
