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
| 2 | Strategy profiles — 4 style engines, offline | planned | — | profiles table + seeds (DC1/DC2, PDH/PDL/ORB, RRBO, multibagger…), NSE holiday calendar, per-style suggestions API, walk-forward backtests |
| 3 | Realtime v2 — tick-to-tick | planned | — | live-worker + Rust LiveEngine, committed vs forming layers, record/replay harness, p99 < 10 ms tick→publish. **Kite subscription required here.** Pre-shadow-week: rust-path signal envelope (patterns/indicators via FFI) + intraday parity goldens (then drop the off-1d python fallback) — see phase-01 §Exit gate |
| 4 | F&O analytics | planned | — | chain builder, Rust IV/Greeks, IV-rank/PCR/max-pain from recorded history, option-selling suggestions (calibrated with user) |
| 5 | UI overhaul | planned | — | new sidebar IA, slate theme default, 4 style pages, chain ladder, virtualized live tables @60fps |
| 6 | Outcome tracking + strategy lab v2 | planned | — | per-style hit-rate/expectancy dashboards, factor attribution, Rayon weight tuning + promotion workflow |
| 7 | Live-trading hardening | planned | — | Kite orders behind trading_mode + 30-day gate, kill switch, reconciliation, VPS runbook |

**▶ CONTINUE HERE (next session, any account):** Phase 2 kickoff — strategy
profiles (UPGRADE_PLAN.md §Phase 2): profiles table + seeds (DC1/DC2,
PDH/PDL/ORB, RRBO, multibagger…), NSE holiday calendar, per-style
suggestions API, walk-forward backtests. At kickoff, put the three
spec-vs-code drifts found at the Phase-1 gate to the user for adjudication
(F: §4 ATR>3% size reduction unimplemented · G: star patterns missing the
gap condition · H: sub-factor weight semantics vs §3's table — **evidence
already measured**, table in phases/phase-01-rust-engine.md §Exit gate:
G strongly positive, H1/H2 strongly negative, F = risk-preference call);
any change follows
SIGNAL_ENGINE.md §8: both engines + regenerated fixtures in one commit,
backtest regression. Session state is all in-repo: this file,
docs/phases/phase-01-rust-engine.md, docs/ARCHITECTURE.md §Adjudicated
canon, docs/PERFORMANCE.md.

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
