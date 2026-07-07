# Phase plan & status

Two eras: the **v1 build-out** (2025 → mid-2026, complete) and the **v2
upgrade** (current — approved 2026-07-03). The v2 plan's full rationale,
architecture decisions, and risks live in `docs/UPGRADE_PLAN.md`; each
completed phase writes a detailed report to `docs/phases/`.

Rule unchanged since v1: one phase at a time, vertical slices, green tests +
working demo + agent reviews before the next phase starts (`/phase-gate`).

---

## v2 upgrade phases (current)

| # | Phase | Status | Report | Key deliverable |
|---|-------|--------|--------|-----------------|
| 0 | Claude workbench · repo hygiene · triage · F&O recorders | **✅ done 2026-07-03** | [phase-00](phases/phase-00-workbench.md) | git + hooks/agents/rules/skills · 9 defects fixed (incl. dead live pipeline, 100× sizing) · F&O bhavcopy/VIX/chain recorders live |
| 1 | Rust engine core + parity + benchmarks | **✅ done 2026-07-05** (gate: `make check` green + quant-verifier signoff) | [phase-01](phases/phase-01-rust-engine.md) | tradecore wheel · 4 oracle fixtures · cross-language parity EXACT (96 windows + 125 trades) · 5 adjudicated canon decisions · **2y×49 backtest 883.8s → 0.143s (~6,180×)** |
| 2 | Strategy profiles — 4 style engines, offline | **✅ done 2026-07-07** (gate: suites 616/131/35 green · smoke · reviews; 8c trails by approved plan) | [phase-02](phases/phase-02-strategy-profiles.md) | versioned profiles + 8 seeds · NSE calendar · FII/DII + EOD chain wired · suggestions API · **walk-forward evidence: rrbo +41.3%/+1.97 sharpe POSITIVE; dc1/dc2/multibagger FLAGGED** · §8 golden harness in make check · Kite login + throttled REST + intraday backfill |
| 3 | Realtime v2 — tick-to-tick | planned | — | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, p99 < 10 ms tick→publish. **Kite subscription required here.** Pre-shadow-week: rust-path signal envelope (patterns/indicators via FFI) + intraday parity goldens (then drop the off-1d python fallback) — see phase-01 §Exit gate |
| 4 | F&O analytics | planned | — | chain builder, Rust IV/Greeks, IV-rank/PCR/max-pain from recorded history, option-selling suggestions (calibrated with user) |
| 5 | UI overhaul | planned | — | new sidebar IA, slate theme default, 4 style pages, chain ladder, virtualized live tables @60fps |
| 6 | Outcome tracking + strategy lab v2 | planned | — | per-style hit-rate/expectancy dashboards, factor attribution, Rayon weight tuning + promotion workflow |
| 7 | Live-trading hardening | planned | — | Kite orders behind trading_mode + 30-day gate, kill switch, reconciliation, VPS runbook |

**▶ CONTINUE HERE (next session, any account):** Phase 2 CLOSED
2026-07-07, **8c COMPLETE same day** (commits `8fa1263`→`a3b1927`;
report: `phases/phase-02-strategy-profiles.md`). 8c delivered: backfill
(15.3M rows, manifest 416/420 admitted) · session_last_bar axis in both
engines (default-off, fixture-proven) · 102-trade intraday parity oracle
(cargo + DB-free pytest replay it EXACTLY) · intraday walk-forwards —
**pdh_pdl −0.3%/sharpe −1.06 · orb_15m +10.4%/−0.60 · gainer_925 +116.3%
(≈0/trade)/−0.67 — all three FLAGGED; none earns Phase-3 activation
as-specced.** All 8 goldens replay green in `make walkforward`.

Open threads, in order:
1. **quant-verifier full pass owed on 8b+8c** (two gate runs died on
   account session limits; partials in the report: digest stability 200k
   clean, freeze diff = sanctioned groups only). Run before Phase-3 work
   starts; scope: walkforward.py, session_last_bar axis, intraday
   fixtures/goldens, kite_rest/backfill ingest.
2. **Final full `make check`** on the 8c tree if not run this session
   (suites were green per-slice; the walkforward target now replays 8
   goldens, ~7 min).
3. **Before any multiplier-carrying profile activates:** wire
   profile.weight_multipliers into pipeline.py scoring (all seeds `{}`);
   latent LOW calendar items in the report backlog.
4. **Profile tuning** (dc1/dc2/multibagger negative; intraday trio
   flagged) — Phase 6 workflow; verdicts pinned in goldens.
5. `git push` remains manual (credential-free remote by design).

Daily ops: Kite token dies ~6:00 AM IST; ritual =
`cd backend && uv run python scripts/kite_login.py` (terminal-only).
Chain recorder auto-activates while a token is live.

Next phase: **Phase 3 — Realtime v2** (plan §Phase 3): live-worker +
Rust LiveEngine, committed-vs-forming layers, record/replay harness,
p99 < 10 ms tick→publish. The rust-path signal envelope + intraday
goldens pre-work from phase-01 §Exit gate is now DONE (8c).

Phase-1 state (closed): F/G/H applied 2026-07-05, canon table in
ARCHITECTURE.md; standing baseline 599 trades / +52.1% / sharpe +0.13 on
the pinned 2y×49 corpus.

**Decision gates (unchanged in spirit from v1):**
- End Phase 1: parity green or no cutover.
- End Phase 2: every profile shows documented expectancy (or is flagged) before realtime work.
- End Phase 3: full-session soak clean before F&O/UI build on top. 30-day paper clock starts here.
- Before Phase 7 live pilot: 30 profitable paper days with discipline, static IP, kill-switch tested.

**Zerodha API:** not needed for Phases 0–2 (NSE public data + existing DB).
Nice-to-have from Phase 2 (historical intraday backfill). **Required at
Phase 3 start.** The chain-snapshot recorder (built in Phase 0) activates
automatically once a token exists.

---

## v1 build-out (complete — kept for history)

| # | Phase | Status |
|---|-------|--------|
| 0 | Infrastructure (docker compose: Timescale+Redis) | ✅ |
| 1 | Auth & user master (JWT, rotation, admin-only creation) | ✅ |
| 2 | Stock master + 50-filter screener + saved screens | ✅ |
| 3 | Categories master (M2M tagging) | ✅ |
| 4 | EOD ingestion (5y OHLCV, FII/DII, bulk/block deals) | ✅ |
| 5 | Signal engine offline (14 factors, confluence ≥70%, backtest harness) | ✅ |
| 6 | Dashboard v1 + corporate filings feed + event guard | ✅ |
| 7 | Live data via Kite WS (unit-tested; end-to-end defects repaired in v2 Phase 0) | ✅* |
| 8 | Paper trading (positions, trail SL, circuit breaker) | ✅ |
| 9 | Strategy lab (grid search, presets, equity curves) | ✅ |
| 10 | Trading journal (auto-populate, emotions, screenshots) | ✅ |
| 11 | External portfolio (CAMS CAS import, net worth) | ✅ |
| 12 | Live trading | → became v2 Phase 7 |

\* v1 Phase 7 shipped with four integration defects that made the live path
inoperable end-to-end (documented in UPGRADE_PLAN.md and repaired, with
regression tests, in v2 Phase 0 — see `docs/phases/phase-00-workbench.md`).

## Consciously deferred (unchanged)

Mobile native app · Account Aggregator integration · AI/ML signal
generation (only after the rule-based engine proves out) · multi-tenancy /
SaaS hardening · MCX commodities. FinBERT sentiment stays deferred
(column exists, never populated).
