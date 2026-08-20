# Market Context Engine (MCE) — design capture

**Status: IN PROGRESS — slices 1 + 2 + 3 built 2026-08-20.** Slice 1 = the pure RS overlay
(`sector_rs.py`); slice 2 = index price store (`index_ohlcv_1d`, migration `b8c9d0e1f2a3`) +
benchmark provider + order-path wiring; slice 3 = the shadow sidecar (`sector_rs_shadow.py` →
`sector-rs-shadow-<date>.md` with a per-entry context table + flip-readiness banner) + the flip to
**mode `shadow`** (measures + stamps, never blocks). All agent-reviewed (quant-verifier PASS ×3 +
bug-hunter, findings actioned). **NEXT = let forward evidence accrue** (needs `index_ohlcv_1d`
backfilled — next `make worker` self-heals it); a shadow→active flip later needs the R-track
ceremony (§8-on-≥2y + sign-off). Slice 4+ = the other MCE components (fundamentals, news veto). The
named phase **after Phase 6.8, before Phase-7 (live)**. This doc captures the *entry-context* design agreed 2026-08-18 (the SRTL /
entry-selection discussion). Full prior context: the `market_context_engine_deferred` memory
+ `docs/Market_Context_Engine_Spec.docx` (spec on disk). **The sliced plan is now at the
bottom of this doc ("Sliced plan (started 2026-08-20)"), including one OPEN decision the
build is blocked on — the benchmark source.**

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
   single-name signal by whether its sector/index is leading. **Premise correction
   (2026-08-20, verified against the live DB):** there is **no index price series stored** —
   `ohlcv_1d` holds ~2360 equities and no Nifty/BankNifty/FinNifty/sector *index* instrument
   (only the `is_nifty50`/`is_banknifty`/`is_finnifty` membership flags: 50/14/25 members),
   and the RS benchmark input (`eval_relative_strength`'s `ctx.benchmark_closes`) is
   **unwired everywhere** ("benchmark series unavailable" / walkforward.py:69). So RS needs a
   **benchmark series that does not exist yet** — this is the keystone, and its SOURCE is an
   open decision (see the Sliced plan). Also: only **500 of 2380 stocks carry a `sector`**,
   so the sector gate necessarily fails open for the rest. Start as an overlay (shadow),
   promote to a confluence factor only via the R-track.
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

## Sliced plan (started 2026-08-20)

Component 1 (sector/index relative-strength), overlay lane, sequenced so the risk lands
in the right order. Each slice is shadow-first, frozen engine untouched, fully reversible.

**✅ DECIDED 2026-08-20 — the benchmark source = Option B (ingest real Kite index OHLC).** The
user's call: build the actual top-down series rather than a synthesized proxy. RS needs a
benchmark close series that does not exist yet. The two options that were on the table:
- **A — synthesize from constituents we already have.** Build an equal-weight daily-return
  index from the membership-flagged baskets (Nifty50 = 50 stocks; BankNifty = 14; FinNifty
  = 25) and per-sector baskets (the ~500 sectored stocks). No new data, buildable today, but
  it is a PROXY — an equal-weight 50-stock basket is not the real cap-weighted Nifty 50, and
  cap-weighting is impossible because `market_cap_cr` has no writer (the F1 blocker).
- **B — ingest the real index OHLC.** Kite exposes index instruments (`NSE:NIFTY 50`,
  `NSE:NIFTY BANK`, `NSE:NIFTY FIN SERVICE`, sector indices) with historical data. A small
  EOD-ingestion addition gives the ACTUAL index series (strictly better RS, and the honest
  top-down series the user's Bank-Nifty-leadership idea wants), at the cost of a new
  instrument set + EOD pull + storage. Arguably the right long-term answer.

**Decision (2026-08-20): B** — ingest the real Kite index OHLC for the market/sector indices
Kite publishes; A stays only as a possible fallback for any sector with no published index.
Slice 2 is now unblocked.

- **Slice 1 — RS overlay module. DONE 2026-08-20.** `app/signals/sector_rs.py` — pure,
  moded (off/shadow/active, default **off**), fail-open; reuses `eval_relative_strength`'s
  definition (excess = stock_ret − bench_ret over `lookback`; BUY wants out-performance, SELL
  under-performance). Benchmark-source-agnostic (takes closes as input), so it is correct
  under either A or B. UNWIRED — not in the order path, no config key yet, so it changes no
  behaviour. Tests: `tests/test_sector_rs.py` (16, values + both sides + every fail-open
  branch + all modes). **quant-verifier PASS-WITH-NOTES:** formula matches the
  `eval_relative_strength` reference term-for-term; two MEDIUM notes actioned in-slice — a
  gap/None element now fails open (was: would raise), and the caller alignment contract
  (session-aligned, completed candle N, no look-ahead) is documented for slice 2 to enforce;
  SELL-boundary + `bench_then==0` tests added.
- **Slice 2 — index price store + benchmark provider + order-path wiring. DONE 2026-08-20.**
  Source = **Option B** (the NSE indices bhavcopy CSV `vix_service` already downloads — every
  NSE index sits in that one file, so **no Kite token/historical API**; tokenless + testable +
  self-healing via the EOD catch-up). Built: `index_ohlcv_1d` table (migration `b8c9d0e1f2a3`,
  reversible; FK'd to the existing `indices` registry — indices stay OUT of the tradeable
  universe) · `app/services/index_ohlcv_service.py` (CSV parse keyed on the registry + idempotent
  upsert, wired into `eod_catchup.catchup_fo_eod`) · `app/services/benchmark.py` (membership
  mapping Bank ⊃ Fin ⊃ NIFTY 50 + **date-aligned** stock/benchmark closes, anchored to
  `signal.created_at` — no look-ahead) · `sector_rs` wired into the paper order path
  (`settings.sector_rs_gate_mode`, **default `off`** — wired-but-dormant until data backfills +
  the slice-3 sidecar reads the stamps; fail-OPEN in a savepoint so a DB fault never suppresses).
  16 tests. **quant-verifier PASS-WITH-NOTES** (look-ahead/alignment truly prevented — closes the
  slice-1 #4 note; anchored to commit time in-slice). **bug-hunter BUGS-FOUND** → 1 MEDIUM
  (RS path wasn't fail-open on a DB exception — fixed with a `begin_nested` savepoint + regression
  test) + 1 LOW (docstring over-promised catch-up backfill for a newly-added index — corrected).
  NOTE: the query runs synchronously on the order path (2 indexed reads/order — fine at
  order frequency, unlike the tick path); a Redis-cache front (the `circuit_bands` shape) is a
  possible optimization only if order volume ever makes it matter. Per-sector index mapping
  (NIFTY IT/AUTO/…) deferred — data can accrue by adding registry rows.
- **Slice 3 — shadow sidecar + per-entry context + flip off→shadow. DONE 2026-08-20.**
  `app/services/sector_rs_shadow.py` recomputes the RS verdict over the tradeable cohort
  (`is_shadow` FALSE, since OUTCOME_EPOCH), anchored to each signal's `created_at` (no
  look-ahead), partitioned **would-block / eligible / no-benchmark-data** with resolved
  outcomes + a flip-readiness banner, mirroring `regime_gate_shadow` / `entry_quality_shadow`;
  written by `make analysis` as `sector-rs-shadow-<date>.md` (wired into `daily_analysis.py`).
  It carries a **per-entry table** (each committed signal's benchmark + excess% + RS verdict +
  outcome) — the §69 REQUIREMENT to SHOW context, so we never trade blind to sector leadership.
  **Gate flipped `off`→`shadow`** (`sector_rs_gate_mode` default) — measures + stamps, never
  blocks. quant-verifier PASS (no look-ahead, buckets correct, flip-bar conservative; 2 INFO — a
  label made side-neutral, a `p.avg None` edge left identical to the reviewed sibling). 18 tests
  in `test_index_ohlcv.py` (2 new for the sidecar). **The would-block set net-negative AND worse
  than eligible, over ≥20 resolved, is the evidence for a later shadow→active flip (R-track:
  §8-on-≥2y + sign-off).** Evidence starts accruing once `index_ohlcv_1d` backfills (next
  `make worker` self-heals it ≤21d); on the smoke it correctly showed all 414 cohort signals as
  "no benchmark data (still backfilling)".
- **Slice 4+ — the other MCE components** (fundamentals gate — blocked on `market_cap`/F1;
  news/sentiment veto extending `event_guard`; 200-DMA/VIX regime; earnings blackout;
  seasonality), each its own overlay slice.

Flip to `active` for any gate = R-track ceremony: forward shadow evidence + §8-on-≥2y +
explicit sign-off. Never a silent flip.

## Cross-references
- The entry-selection discussion + verdict ("single factor is not an entry"): the
  **entry-quality overlay** (`app/signals/entry_quality.py`) is the *breadth* fix shipped now;
  the MCE is the *context* layer. See `docs/analysis/exit-ladder-research-2026-08-18.md`.
- Positioning: PHASES.md (MCE = the phase after 6.8, before Phase-7 live).
- Prior scope + decisions: the `market_context_engine_deferred` memory; spec docx on disk.
