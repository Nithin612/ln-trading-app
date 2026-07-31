# NautilusTrader — deep analysis & what to borrow for our platform

> **Purpose.** A clinically accurate study of [`nautechsystems/nautilus_trader`](https://github.com/nautechsystems/nautilus_trader)
> as an *architectural reference* for this platform (Indian NSE/BSE, retail,
> Zerodha Kite). It records what is genuinely worth adopting, what to adapt for
> India, what to explicitly **not** copy, and where we already align. Every
> claim here was verified against the actual source, not summarised from
> secondhand write-ups — the "Claim vs reality" table (§3) exists precisely
> because the popular AI-generated briefs contain embellishments that would be
> expensive to believe.
>
> **Provenance.** Analysed at tag/commit `3f71cbc` (version **0.61.0**), a
> shallow clone read file-by-file. Scale for context: **2,562 Rust source
> files** across ~24 core crates + **19 venue adapters**, **28 concept docs**.
> Source-of-truth for the "what it is" sections is the project's own
> `docs/concepts/*.md` plus the Rust crates under `crates/`.
>
> **⚠️ License — read before copying anything.** NautilusTrader is
> **LGPL-3.0-or-later**. Architecture, patterns, and ideas are not
> copyrightable and are free to learn from. **Source code is copyleft.** Given
> we may productise later (CLAUDE.md), do **not** paste NautilusTrader `.rs`/
> `.py`/`.pyx` files into our tree. Re-implement the *pattern* from scratch, or
> keep any real LGPL dependency as a cleanly isolated, separately-licensed
> module. When in doubt, learn the idea and write our own.

---

## 1. One-paragraph verdict

NautilusTrader is, on the merits, one of the best open-source trading-engine
architectures in existence — a Rust-native, single-threaded, event-driven
kernel with strict backtest↔live parity, fixed-point money, and a clean
ports-and-adapters boundary. **For us the value is the architecture, not the
code, and not the whole architecture.** We should adopt its *core discipline*
(event bus, in-memory cache, independent risk gate, unified execution +
broker-adapter port, rich order state machine, crash-only/fail-fast), **adapt**
a well-defined slice for Indian market structure (broker-centric OMS/RMS,
product types, sessions, circuit bands, corporate actions, F&O/margins), and
**ignore** the institutional-HFT layer that the "for India" briefs over-index
on (FIX gateways, colocation, leased lines, OTR penalty engines). Crucially, we
have **already** independently arrived at several of its best ideas in
`engine/` — so this is gap-closing, not a rewrite.

---

## 2. What NautilusTrader actually is (accurate baseline)

- **A framework + default node implementations**, not a strategy library. You
  can assemble a system from `Cache` + `MessageBus` + engines, or use the
  batteries-included `BacktestNode` / `LiveNode`.
- **Two-language design, done right.** The performance-critical core (domain
  model, engines, matching, risk, book maintenance) is **Rust**; **Python is
  the control plane** for strategy logic, config, and orchestration. This is
  their answer to the "two-language problem": research and live run the *same*
  compiled engine.
- **Mid-migration, v1→v2.** The current runtime is **Rust-native (v2) exposed
  via PyO3**. A **legacy Cython (v1)** core is still supported during the v2
  release-candidate phase. (Important nuance: the popular briefs say Nautilus
  "embeds the Python interpreter inside the Rust binary" — that is misleading.
  Python is the host; the Rust core is a compiled extension, either through
  Cython C-extensions statically linked to the Rust libs (v1) or PyO3 bindings
  (v2). Prebuilt wheels need no Rust toolchain at runtime.)
- **Single-threaded kernel** per node (LMAX-disruptor-inspired) for
  deterministic event ordering; network I/O, persistence, and adapters run on
  separate threads / a shared Tokio runtime and hand results back to the kernel
  through channels. The message bus is **thread-local**.
- **Environment contexts** are first-class: `backtest` (historical data +
  simulated venue), `sandbox` (real-time data + simulated venue), `live` (real
  time + real/paper venue). All three share one `NautilusKernel`.
- **Asset-class agnostic, multi-venue** — CEX/DEX crypto, FX, equities,
  futures, options, betting. 19 adapters ship in-tree (Binance, Bybit, OKX,
  Interactive Brokers, Databento, …).

---

## 3. Claim vs reality — corrections to the AI briefs

The two AI-generated documents (the "Institutional Blueprint" PDF and the
"Engineering Decisions" DOCX) are directionally good but contain several
inaccuracies. Believing them literally would cost us. Corrected against source:

| Popular claim | Reality (verified) | Why it matters to us |
|---|---|---|
| "Pins execution loops to dedicated CPU cores; lock-free **SPMC ring buffers**." | **Single-threaded kernel**; cross-thread hand-off is via **MPSC channels**; the bus is **thread-local**. No core-pinning in the codebase. (`docs/concepts/architecture.md` §Threading model) | Don't build a core-pinning/ring-buffer layer expecting parity. The real lesson is *single-writer determinism*, which is far cheaper to copy. |
| "Two precision types named `Decimal9` / `Decimal16`." | Types are **`Price`, `Quantity`, `Money`**, immutable fixed-point. Precision is a **compile-time feature flag**: standard = 9 dp on `i64`/`u64`; `high-precision` = 16 dp on `i128`/`u128`. (`crates/model/src/types/fixed.rs`, `docs/concepts/value_types.md`) | Our `i64·1e-4` is the same *idea* at lower precision — correct for paise. See §4. |
| "Embeds the Python interpreter inside the Rust binary." | Python is the **host**; Rust is a linked **extension** (Cython static-link v1 / **PyO3** v2). | Mirrors our `tradecore` wheel exactly. No exotic embedding needed. |
| "mimalloc allocator." | **True.** Wheels + `nautilus` CLI use **mimalloc**; benches run **3%–44% faster**, order-flow paths gain most. Crates stay allocator-neutral. (`docs/concepts/architecture.md` §Memory allocation) | A near-free win for our `engine-cli`/backtest binaries (§7). |
| "Risk is a post-trade/external concern in crypto adapters." | Risk is an **in-process pre-trade gate**: `RiskEngine` can emit **`OrderDenied`** and the order **never reaches the venue**. (`docs/concepts/architecture.md` §Execution flow) | This is the model we want for live (§6). |
| "Nanosecond timestamps everywhere are essential." | Timestamps are `UnixNanos` (UTC, RFC-3339, 9 fractional digits) — cheap `u64`, not a latency feature. | Fine to keep our tz-aware UTC / epoch-seconds `SessionSpec`; ns is not a requirement for retail. |
| "Colocation / FIX / leased lines / OTR penalty engine are required." | Those are **institutional-HFT** concerns the briefs imported from a different market tier. Nothing in Nautilus *requires* them; its default adapters are REST/WebSocket. | **Explicitly not for us** — see §8. Kite is REST (~3 req/s) + WS; our latency floor is the broker, not the engine. |

**Net:** the briefs are trustworthy on *philosophy* (event-driven, parity,
adapters, risk-gate, domain model, cache) and unreliable on *mechanism* and on
*which market tier we are in*.

---

## 4. The parts worth studying (engine design)

### 4.1 Core components (`NautilusKernel` orchestrates)

| Component | Responsibility | Our nearest equivalent |
|---|---|---|
| `MessageBus` | Pub/Sub + Req/Rep + point-to-point; optional Redis persistence | **none** — we use Redis pub/sub for *fan-out only*; no internal typed bus |
| `Cache` | In-memory hot state: instruments, accounts, orders, positions, quotes | **partial** — `ltp:{stock_id}` in Redis; orders/positions read from Postgres |
| `DataEngine` | Route market data to subscribers | `broker/tick_consumer.py` + `/ws/live` fan-out |
| `ExecutionEngine` | Own order lifecycle, route to clients, reconcile | **none unified** — `broker/paper_broker.py` (functions), Kite path separate |
| `RiskEngine` | Pre-trade checks → allow / `OrderDenied` | **partial** — `trading/circuit_breaker.py`, sizing in the signal path |
| `Portfolio` | Positions/PnL aggregated from fills | `services/portfolio_service.py` |

### 4.2 The two flows to internalise

**Data flow — "cache-then-publish."** `DataEngine` writes the quote into the
`Cache` **before** publishing it on the bus, so any handler can synchronously
read the latest value from cache the instant it fires. (Order-book deltas are
the exception — published directly, book state maintained separately.) This
ordering is a small, high-value discipline.

```
Adapter → MPSC channel → DataEngine → Cache.add_quote() → MessageBus.publish() → Strategy.on_quote_tick()
```

**Execution flow — risk is the gate.** A strategy emits *intent only*; it never
touches the venue.

```
Strategy.submit_order → RiskEngine (pre-trade) ─┬─ pass → ExecutionEngine → ExecutionClient(adapter) → Venue
                                                └─ fail → OrderDenied (never leaves the process)
events (Accepted/Filled/Canceled/Rejected/Expired) flow back through ExecutionEngine → Cache → Strategy handler → Portfolio
```

### 4.3 Domain model & value types (the money discipline)

- **`Price` (signed) / `Quantity` (unsigned) / `Money` (signed + currency)** —
  immutable, fixed-point integers with **dimensional type-algebra**:
  `Price + Price → Price`, but `Price × Price → Decimal` (units change, so the
  type changes). This makes whole classes of unit-confusion bugs
  *uncompilable*.
- **Precision is display metadata, not identity** — `Price(1.23, p=2) ==
  Price(1.230, p=3)` because the raw scaled integer is equal.

  | Mode | Backing | Max precision | Applies to |
  |---|---|---|---|
  | standard | `i64`/`u64` | 9 dp | Windows wheels, default Rust builds |
  | `high-precision` | `i128`/`u128` | 16 dp | Linux/macOS wheels, DeFi (18-dp wei) |

- **A real cautionary tale we should heed.** Their own fixed-point module
  documents a historical bug: catalog writers used `int(value * FIXED_SCALAR)`
  and introduced floating-point error; the fix is
  `round(value * 10^precision) * scale`. This is *exactly* our rule "construct
  money from `str`, never through `float`" — living proof it bites even careful
  teams. (`crates/model/src/types/fixed.rs`)

### 4.4 Order lifecycle FSM (`OrderStatus`, 15 states)

`Initialized → Denied | Emulated → Released → Submitted → Accepted →
{Triggered, PendingUpdate, PendingCancel, PartiallyFilled} → Filled | Canceled
| Expired | Rejected | Voided`, with predicates `is_open()`, `is_closed()`,
`is_cancellable()`. (`crates/model/src/enums.rs`)

The single most useful distinction for us:

- **`Denied`** = rejected **internally** by our own risk engine (never sent).
- **`Rejected`** = rejected **by the venue**.

That two-word split is precisely the OMS-reject vs RMS-reject vs
exchange-reject layering the India briefs ask for — we get it for free by
copying the state names. `Emulated`/`Released` (local synthetic orders held by
an `OrderEmulator` until a trigger) is conceptually our *provisional/forming*
layer applied to orders.

### 4.5 Ports & adapters (the broker boundary)

Venue-specific code lives **only** in an adapter that implements two ports:
`DataClient` (market data) and `ExecutionClient` (orders). The rest of the
system speaks one internal domain model. The **Interactive Brokers** adapter is
the closest in-tree template for a broker-with-an-OMS (as opposed to a raw
exchange), and its layout is a good skeleton for a future `ZerodhaAdapter`:

```
crates/adapters/interactive_brokers/src/
  common/  config.rs  data/  execution/  gateway/  historical/  providers/  python/
```

### 4.6 Reliability posture (adopt the mindset)

- **Crash-only design** for *unrecoverable* faults: startup and crash-recovery
  share one code path (so recovery is actually tested); `panic = abort` in
  release; state is externalised (Redis/Postgres) so restart is clean. Graceful
  `stop`/`dispose` still exists for normal shutdown.
- **Fail-fast on corrupt data** — "in trading systems, corrupt data is worse
  than no data." NaN/Inf/out-of-range/overflow → immediate error or panic
  rather than silent propagation.
- **Component lifecycle FSM** (`PRE_INITIALIZED → READY → RUNNING → STOPPED →
  DEGRADED/FAULTED → DISPOSED`) gives every long-lived component a uniform,
  observable state — directly applicable to our `live-worker`.
- **One node per process** (global singletons: force-stop flag, logger, Tokio
  runtime). Parallelism = separate processes. (We already run one worker.)

---

## 5. Where we already align (don't rebuild these)

Credit where due — `engine/` independently landed several of Nautilus's best
ideas, so a chunk of the "adopt" column is **already done**:

| Nautilus idea | Our implementation |
|---|---|
| Pure, deterministic, I/O-free compute core | `engine-core` (no I/O, no clocks — `.claude/rules/rust.md`) |
| **Time enters as parameters** (engine has no clock/calendar/tz) | `SessionSpec{open_ts, close_ts}` in `engine-core/src/live.rs` (ARCHITECTURE.md §Live bucket canon) |
| Backtest↔live parity, enforced | golden oracle fixtures + cross-language parity suite (`backend/tests/parity/`), EXACT decision agreement |
| PyO3 boundary, GIL released, **one call per batch** | `engine-py` (`tradecore`), batch tick calls |
| Fixed-point money, no float for money | `Decimal` / `Numeric(12,4)` / `i64·1e-4` (trading-domain rules) |
| Provisional vs committed, distinct at the type level | `Forming` vs `Committed` in `engine-core/src/live.rs` — committed at most once per (tf, period), no repaint by construction |
| Fail-fast / no-panic library discipline | `panic = "deny"` workspace lint; `Result`/`Option` on malformed data |
| Massive sim throughput as the enabler | Phase-1 result: 2y×49 backtest **883.8s → 0.143s (~6,180×)** |

The gap is **not** the compute core. The gap is the **runtime plumbing around
it**: bus, cache, unified execution, and an independent risk gate.

---

## 6. Gap analysis & concrete adoption plan

Ranked by value-to-effort, mapped to our files and phases. "Effort" is relative.

| # | Idea to adopt | Our state today | Recommendation | Where it lands | Effort |
|---|---|---|---|---|---|
| 1 | **Internal typed event bus** (Pub/Sub + Req/Rep) | Redis pub/sub for WS fan-out only; components call each other / go through Redis contracts | Introduce an in-process `EventBus` with typed events (`TickEvent`, `CandleClosed`, `SignalCommitted`, `OrderIntent`, `OrderEvent`, `PositionChanged`). Start by routing the tick→signal→alert path through it; keep Redis pub/sub as the *external* transport for WS. | Phase 3 tail / Phase 7 | M |
| 2 | **Unified `ExecutionEngine` + broker-adapter port** | `paper_broker.py` (functions) + separate Kite path; `if paper/live` risk | Define one `BrokerAdapter` port (`submit`, `cancel`, `modify`, event stream). Implement `PaperBroker` and `KiteBroker` behind it. Strategy/engine emit `OrderIntent` and never branch on mode. | **Phase 7** (live hardening) | M–L |
| 3 | **Independent `RiskEngine` gate** with `OrderDenied` | circuit breaker + sizing scattered in signal path | Every `OrderIntent` passes one pre-trade gate: daily-loss breaker (never disableable), position size, SL-cap reject, duplicate-order, freeze qty, price-band, exposure, market-status. Denied ⇒ never sent. | **Phase 7** | M |
| 4 | **Rich order state machine** (`Denied` vs `Rejected`, 15 states) | minimal order status | Adopt the state names + predicates; map Indian OMS-accept / RMS-accept / exchange-accept / freeze-reject / band-reject onto them. | **Phase 7** | S–M |
| 5 | **In-memory `Cache` for hot state** | `ltp:` in Redis; orders/positions from Postgres | Keep authoritative open orders/positions/quotes/instruments in RAM inside the worker; DB/Redis become durability + history. Cache-then-publish ordering. | Phase 3/7 | M |
| 6 | **Execution reconciliation** on restart | daily restart + warmup + gap-fill (data side only) | On worker boot, pull open orders/positions from the broker and reconcile against our cache before trading — the token-expiry restart is a *normal lifecycle event*. Nautilus's `reconciliation.md` is the reference. | **Phase 7** (already in the plan) | M |
| 7 | **mimalloc** on native binaries | not set (`engine/Cargo.toml` release = thin-LTO, cgu=1, `panic=deny`) | Add mimalloc as the global allocator for `engine-cli` and any bench/replay binary. Keep `engine-core` allocator-neutral. Measure via `/perf-bench`. | any time | **S (near-free)** |
| 8 | **Component lifecycle FSM** for the worker | ad-hoc | Give `live-worker` explicit `READY/RUNNING/DEGRADED/FAULTED` states + transitions; makes soaks and health checks legible. | Phase 3/7 | S |
| 9 | **Event sourcing for orders/positions** (optional) | rows mutated in place | Consider positions as *aggregations of immutable fill events* (Nautilus `event_store` crate / `event_sourcing.md`) for a perfect audit trail. Nice-to-have, not urgent. | Phase 6/7 | L |

**Sequencing note.** Items 1–5 are mutually reinforcing and are best done as
one coherent "runtime plumbing" slice **at Phase 7**, when live orders arrive —
that is the moment the paper/live branch actually hurts. Item 7 is independent
and can be picked up immediately.

### 6.1 Minimal event-bus sketch (so #1 is concrete, not hand-wavy)

```python
# app/runtime/bus.py  — in-process, typed, synchronous, single-writer
class EventBus:
    def subscribe(self, topic: str, handler: Callable[[Event], None]) -> None: ...
    def publish(self, topic: str, event: Event) -> None: ...   # cache first, then dispatch

# producers publish intent/facts; they never call consumers directly
bus.publish("candle.closed.5m.NSE.SBIN", CandleClosed(...))
bus.publish("order.intent", OrderIntent(stock_id=..., side=..., qty=..., sl=...))
# RiskEngine subscribes to order.intent, emits order.denied or forwards to ExecutionEngine
# UI/alerts/analytics/persistence subscribe with zero changes to producers
```

Keep it **synchronous and single-threaded inside the worker** (Nautilus's
determinism lesson); use the existing Redis Streams only for things that must
survive a crash (alerts, queued work) — never bare pub/sub for those.

---

## 7. Performance: is it "faster than ours", and does it matter?

**In absolute engine terms, yes** — single-threaded determinism, fixed-point,
mimalloc, zero per-tick allocation, and a compiled core make Nautilus very
fast. **But we have already captured the win that matters for us** (the Rust
core: ~6,180× on backtests), and **our real latency floor is the broker**
(Kite REST ~3 req/s, round-trips of tens-to-hundreds of ms), not our engine.
So the performance lessons to actually apply are the cheap, high-leverage ones:

- **mimalloc on native binaries** — 3–44% on their order-flow benches; free for
  `engine-cli`/replay/backtest (item 7).
- **In-memory cache** on the hot path — avoid Postgres/Redis round-trips per
  tick (item 5); this is a bigger real win for us than any micro-optimisation.
- **Cache-then-publish + single-writer** — determinism and no locks.
- **Batch the PyO3 boundary** — already done; keep it that way (never one call
  per tick).
- **Preallocated ring buffers, borrow-don't-clone in hot loops** — already our
  `rust.md` rule; Nautilus is a good exemplar to read.

What we should **not** chase: nanosecond timestamps, core-pinning, kernel-bypass
networking, FIX — none move the needle for a retail Kite platform (§8).

---

## 8. What NOT to copy (anti-patterns *for us*)

1. **The institutional-HFT layer.** Colocation, bare-metal `ap-south-1`, leased
   lines, FIX gateways, kernel-bypass NICs, and real-time **OTR penalty
   engines** are written for proprietary HFT desks. We are a **retail personal
   platform on Kite**. Adopting any of it is pure cost with zero payoff at our
   latency tier. (The "Institutional Blueprint" PDF is aimed at a different
   audience; read it as background, not as our spec.)
2. **Don't go Rust-first / rewrite the platform.** We already have the right
   split — Python control plane + Rust compute core. Keep FastAPI/Celery/
   Postgres for everything that isn't hot-path math.
3. **Don't chase 16-digit precision.** `i64·1e-4` / `Numeric(12,4)` matches
   Indian tick sizes (₹0.05) and paise. Their `high-precision` mode exists for
   crypto/DeFi (18-dp wei). **Do** copy the *discipline* (raw = exact multiple
   of scale; construct from `str`, never `int(float * scalar)`).
4. **Don't build multi-asset / multi-venue genericity up front.** Nautilus pays
   a real complexity tax to be asset-class-agnostic. We are NSE/BSE
   equities + F&O; a broker-centric model (not exchange-centric) is simpler and
   more correct for us.
5. **Don't copy source (LGPL).** Re-implement patterns; don't vendor files.
6. **Don't run multiple nodes in one process** (their explicit warning; we
   already run a single worker).
7. **Don't over-abstract before Phase 7.** The event-bus/execution/risk/adapter
   refactor has the most value exactly when live orders exist. Doing it earlier
   is speculative plumbing.

---

## 9. Adapting the good parts for India (the ~20% redesign)

These map onto work we already have scaffolding for — this is *extension*, not
green-field:

| Concern | Nautilus baseline | India adaptation | Our anchor |
|---|---|---|---|
| Broker vs exchange | exchange/venue adapter | **broker**-centric port (Zerodha, then Dhan/Angel/Upstox/Fyers/Flattrade) | new `BrokerAdapter` (Phase 7) |
| Order states | generic 15-state FSM | map OMS-accept / RMS-accept / exchange-accept / freeze-reject / band-reject | `Denied` vs `Rejected` split |
| Product types | cash/margin/betting accounts | MIS / CNC / NRML / MTF / AMO / BO / CO normalised into one internal model | new `ProductType` enum |
| Sessions | continuous / venue calendars | pre-open / normal / closing / post-close / muhurat / half-day / holiday | `services/market_calendar.py`, `trading/market_hours.py` |
| Circuit logic | per-instrument price bands | dynamic 10/15/20% bands, upper/lower circuit, auction | extend `trading/circuit_breaker.py` + a price-band check |
| Corporate actions | external DB adjustments | split/bonus/dividend/rights/merger/series-change; **raw stays canonical** | `services/ca_detector.py` (already quarantines) |
| F&O | continuous futures, generic options | weekly/monthly expiries, Nifty/BankNifty/FinNifty/Sensex, chain/OI/PCR/IV/Greeks | `services/fo_bhavcopy_service.py`, `chain_recorder.py`, Phase 4 |
| Margins | SPAN/exposure account engine | SPAN + exposure + peak margin + haircut/pledge, netted per portfolio | Phase 4/7 (new margin service) |
| Data types | `OptionGreeks` is first-class | reuse the idea — Greeks as a first-class data type on the bus | Phase 4 Rust IV/Greeks |

**Our differentiators (the ~10% we build that Nautilus deliberately doesn't):**
the confluence **signal engine** (our edge), the **news/market-context** gate
layer (deferred phase; see memory), the **adaptive/regime** decision layer
(`trading/regime.py`), and an **Indian paper broker** with realistic OMS/RMS/
fees semantics (`paper_broker.py` + `trading/fees.py`).

---

## 10. Learning resources (ranked)

**Read these first (their own docs — the single best resource):**
- `docs/concepts/architecture.md` — the whole design in one file (threading,
  flows, component FSM, crash-only, memory).
- `docs/concepts/message_bus.md`, `cache.md` — the two ideas we're missing.
- `docs/concepts/execution.md`, `orders/`, `reconciliation.md` — the Phase-7
  execution + reconciliation model.
- `docs/concepts/value_types.md` — the money/precision discipline.
- `docs/concepts/backtesting/`, `live.md`, `portfolio.md`, `accounting.md`,
  `greeks.md`, `options.md` — for Phases 4–7.
- `MIGRATION_V2.md`, `BENCHMARKING.md` — the Cython→Rust migration and the perf
  methodology.

**Then read this source (for the pattern, not to copy):**
- `crates/common/` — `MessageBus`, `Cache`, actor/component registries.
- `crates/execution/` — `ExecutionEngine`, `ExecutionClient`.
- `crates/risk/` — `RiskEngine` pre-trade checks.
- `crates/model/src/{enums.rs, types/fixed.rs, orders/}` — domain model.
- `crates/adapters/interactive_brokers/` — broker-adapter skeleton.
- `crates/backtest/` — the `SimulatedExchange` that gives parity.

**External references they cite (worth an hour):**
- Martin Fowler, *The LMAX Architecture* (single-thread determinism / disruptor).
- Candea & Fox, *Crash-Only Software* (HotOS 2003).
- *High Assurance Rust* (`highassurance.rs`).

---

## 11. Bottom line

Use NautilusTrader as an **architectural mentor**, not a dependency. We already
share its compute-core DNA; the concrete, high-value work is the **runtime
plumbing** — an internal event bus, an in-memory cache, and a unified
execution + broker-adapter + independent-risk stack — landed at **Phase 7**
where it pays off, plus a **free mimalloc** win now. Adapt a bounded slice for
Indian market structure, and firmly **skip** the institutional-HFT apparatus
that doesn't apply to a retail Kite platform. Learn the patterns; write our own
code; keep money in `Decimal`/fixed-point; and let the engine stay pure while
the world's messiness lives at the adapters.

---

*Appendix — verified facts (source paths at commit `3f71cbc`, v0.61.0):
license `LGPL-3.0-or-later` (`LICENSE`, `pyproject.toml`); precision constants
`crates/model/src/types/fixed.rs` (`FIXED_PRECISION` 9|16, `PRECISION_BYTES`
8|16); order/enum states `crates/model/src/enums.rs`; threading/allocator/flows
`docs/concepts/architecture.md`; value-type spec `docs/concepts/{overview,value_types}.md`;
mimalloc gain "3%–44%" from the same architecture doc; our numbers from
`docs/PHASES.md` and `docs/ARCHITECTURE.md`.*
