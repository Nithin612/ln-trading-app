# External libraries review — 2026-08-02

Companion to `docs/NAUTILUS_TRADER_ANALYSIS.md`. Records a code-grounded
verdict on six GitHub projects that were pitched (via Gemini, ChatGPT, and
Claude-chat, each reasoning **without seeing our codebase**) as things we
should adopt for an Indian trading platform. Written at **v2 Phase 3**.

The purpose of this doc is durability: so a future session — or a future
"you must adopt X" pitch from an external AI — can see what was evaluated,
against what code, and why it was accepted, deferred, or declined.

---

## 1. One-paragraph verdict

**Adopt none of the six as a dependency.** Every architectural idea they
surface is already built, already scheduled (mostly Phase 7, and we are
learning it from a better-fit reference — NautilusTrader), or already
consciously deferred (AI/ML signal generation). Two of them (VectorBT,
NSEPython) would actively *regress* invariants we have already secured
(no-look-ahead discipline; durable data sourcing). The net action is a
conscious **"no"** on the roadmap plus this record. Three genuine
idea-harvests are routed into existing phases as notes, not work.

The common flaw in all three chatbot answers: they assumed a green-field
"building from scratch today." We are at Phase 3 with a frozen deterministic
confluence engine, a Rust compute core, a live tick pipeline, a paper broker,
and a screener — and we had already written `docs/NAUTILUS_TRADER_ANALYSIS.md`
covering the exact event-bus / broker-adapter / RiskEngine / order-FSM ground
LEAN and IndiaFenix re-pitch, from a stronger reference.

---

## 2. Verdict table

| Repo | What it pitches | Our reality (code) | Verdict | Phase |
|---|---|---|---|---|
| **IndiaFenix** | Broker-adapter seam, throttled REST, paper matching engine | Kite-only, but `ThrottledKite` (rate-limit) + `paper_broker.py` (matching engine: slippage, fees, gap-through-stop) exist; broker-adapter port already planned | Don't vendor — seam already planned via Nautilus | Phase 7 (learn, not adopt) |
| **QuantConnect LEAN** | Event-driven engine, order FSM, risk/exec separation, fill model | Realtime layer already event-driven; FSM + RiskEngine + reconciliation already in PHASES.md P7 + Nautilus §6 | Don't vendor — wrong tier/language, ideas already captured | Phase 7 (via Nautilus) |
| **VectorBT** | Fast vectorized parameter sweeps | `backtest/engine.py` + `grid_search.py` + `walkforward.py` exist; Rust core does 2y×49 in **0.143s (~6,180×)** | Not needed — reintroduces look-ahead bias we forbid | Never |
| **PKScreener** | NSE scan catalog, universe→shortlist | `screener/` DSL + `profiles/` + 14-factor confluence + watchlists + AlertBell already do this | Don't vendor — harvest its setup *ideas* only | Phase 6 (factor candidates) |
| **NSEPython** | Unofficial NSE JSON scraper (option chain, quotes) | Chain snapshots recorded from **Kite quotes**; VIX/bhavcopy from NSE **archive CSVs** — `vix_service.py` explicitly prefers the archive over "the fragile JSON API" NSEPython wraps | Not needed, contraindicated — durable version already built | Skip |
| **Kronos** | OHLCV foundation-model direction forecaster | Deterministic engine is the edge; AI/ML signal-gen already deferred "only after the rule engine proves out" (PHASES.md) | Not needed — already deferred by policy | Post-Phase-6 research-track only, if ever |

---

## 3. Per-repo detail

### IndiaFenix — broker-abstraction pitch
The broker-adapter seam is real and valid, but we do not adopt it by
vendoring an LGPL library of unknown quality while we run exactly one broker.
The two concrete things it advertises are already built:
- shared throttled REST client (`app/broker/kite_rest.py` → `ThrottledKite`;
  rate-limiting is a hard constraint in `.claude/rules/trading-domain.md`),
- paper matching engine (`app/broker/paper_broker.py` — adverse slippage,
  gap-through-stop, Zerodha round-trip fees).

The broker-adapter *port* itself is on the Phase-7 slate, modelled on
NautilusTrader's ports-and-adapters design (`NAUTILUS_TRADER_ANALYSIS.md`
§4.5/§6). Multi-broker (Upstox/Angel) is a genuine post-Phase-7 "someday" —
building the abstraction before a second broker exists is speculative
generality. The one nugget worth naming — centralizing symbol/instrument-token
normalization — we already handle in the `kite_instruments` sync + T2T mapping.

### QuantConnect LEAN — event-driven-architecture pitch
The single biggest redundancy. Event bus, 15-state order FSM (`Denied` ≠
`Rejected`), RiskEngine/ExecutionEngine separation, realistic fill model —
all already in the Nautilus analysis and Phase-7 plan (PHASES.md line 24),
sourced from a library that fits retail-on-Kite better than global-multi-asset
enterprise C#. Our realtime layer is already event-driven (tick → Rust
LiveEngine → publish). The only durable takeaway is LEAN's *fill-model
catalog* as a reference when building Phase-7 execution — and Nautilus §4
already covers that.

### VectorBT — the speed pitch, which is moot
We already have a research/backtest track, and Phase 1's win was moving the
hot path to Rust: **883.8s → 0.143s on 2y×49 (~6,180×)** (PHASES.md line 18).
VectorBT's reason to exist (numpy-vectorized sweep speed) is beaten by
tradecore + Rayon, which is *native* fast, not vectorized-fast. More
important: vectorized backtesting **hides look-ahead and intrabar-path bias**.
`backtest/engine.py` is deliberately candle-by-candle N→N+1 to enforce the
no-look-ahead invariant; adopting VectorBT would reintroduce the exact bias
class our hard constraints forbid. Skip permanently. If Phase-6 weight-tuning
needs bigger sweeps, that is Rayon on tradecore.

### PKScreener — the only one with a real idea to harvest
Not as a dependency (it scrapes for its data; we have Kite + bhavcopy
archives), but its *catalog of Indian setups* (VCP, NR7, momentum, delivery
filters) is a useful menu of candidate factors. The hard constraint governs
entry: **no factor bypasses the confluence scorer** — each becomes a new
weighted factor joining the framework, gated ≥70%, only after a §8 backtest
regression. That is a **Phase 6** activity (outcome tracking + strategy-lab-v2
/ factor expansion), not a now-fix. Its "compute indicators once, reuse across
scans" idea we already do — the Rust engine computes the factor set once per
window.

### NSEPython — we already made the call it recommends against itself
`app/services/vix_service.py` documents choosing NSE's archive CSV over "the
fragile JSON API" — precisely what NSEPython wraps. Option chains already come
from Kite quotes into the `option_chain_snapshots` hypertable
(`app/services/chain_recorder.py`). Adopting NSEPython as a primary feed would
regress from a durable design to a scraper that breaks when NSE rotates
cookies. The only conceivable use is a low-value Kite-independent cross-check
behind our existing data abstraction at Phase 4 — realistically, skip it.

---

## 4. Kronos — separate call, clear answer

All three chatbots converged correctly ("never let it generate trades,
isolate to research, fine-tune on NSE"), but missed that the project already
made this decision at the policy level: PHASES.md line ~469 —
*"AI/ML signal generation (only after the rule-based engine proves out)"* —
and we deliberately pushed even news/sentiment to "calibration, not
adaptation" to dodge overfitting.

Kronos is a black-box **direction forecaster** — the ML signal-generation we
deferred. It collides with two things that matter most right now:
1. **Explainability** — signals must read *"Bullish engulfing at 50-EMA
   support, RSI 32, 78% confidence, SL ₹482."* Kronos says "up," which breaks
   the confluence design's auditability.
2. **Timing** — Phase 3 → 7 is about determinism and pre-live safety
   (no-repaint, reject-don't-clamp, backtest/live parity). An unaudited
   predictor now is backwards.

Practical disqualifiers for now: 512-token context ≈ 1.3 NSE sessions of 1m
candles; global pretraining is blind to circuit filters / T2T / ASM-GSM; it
would need heavy fine-tuning on our TimescaleDB history to say anything about
Indian names.

**Verdict:** Not needed. The most it could ever be is a **gated confidence
input in the isolated research track** — the identical call already made for
the Market Context Engine — and only *after* Phase-6 outcome tracking gives a
calibration baseline to measure it against. Never a direction generator, never
in the live path. Park as "interesting, revisit post-Phase-6."

---

## 5. Where the real idea-harvests land (notes, not work)

- **PKScreener's Indian setup catalog** → candidate-factor list in the
  **Phase 6** backlog. Through the confluence scorer, after a §8 backtest.
- **LEAN's fill-model catalog** → pointer in **Phase 7** execution notes;
  reference alongside Nautilus §4 when building the execution handler.
- **Kronos's confidence-as-input** → **post-Phase-6** research-track
  experiment, gated-input-only, measured against the outcome baseline.

---

## 6. Bottom line

We were pitched an architecture we had largely already designed. The layered
stack all three chatbots drew (data → screening → alpha → portfolio/risk →
execution, with broker + data-source seams) is *our* architecture — and the
two seams they emphasize are already built (data-source: archive CSV + Kite;
option chain) or already scheduled and referenced to a better mentor
(broker adapter → Phase 7 via Nautilus). **Adopt none of the six as
dependencies.** This review is a no-op on the roadmap plus three phase-tagged
notes.
