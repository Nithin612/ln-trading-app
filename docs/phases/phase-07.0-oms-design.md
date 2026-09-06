# Phase 7.0 — the OMS design pass (A33 + A42 + A35)

**Status: DESIGN COMPLETE 2026-09-06.** No code. Branch `feature/pre-cycle2-hardening`.
Parent: [`phase-07-live-trading-plan.md`](phase-07-live-trading-plan.md).

> **Why these three together.** The external review's finding was that A33 (order state),
> A42 (cash accounting) and A35 (the broker interface) *look* like three tasks and are one:
> **A42's "available cash" is a function of A33's active-order set, and A35's interface shape
> is decided by whether order state is synchronous or not.** Designing them apart produces an
> interface that fits paper's synchronous fill and breaks on the first real broker ack.

---

## 1. What exists today, precisely

`place_order` (`api/v1/trading.py:317`) → `place_paper_order` (`broker/paper_broker.py:490`):

```
check_circuit_breaker  ─┐
signal lookup + status  │  api/v1/trading.py
restrictions.check()    │  (A38 registry, OVERLAY only)
                       ─┤
offmarket check         │
price resolve           │  broker/paper_broker.py
through-stop check      │  (BROKER rules — unconditional)
size_for_fill           │
_check_notional_cap     │
simulate_fill           │
                       ─┘
Order(status="filled") + Position   ← one transaction, fill is synchronous
```

**Three properties of this that Phase 7 must change, and one it must preserve.**

### 1.1 ⚠ A refused order is not a row — it is an exception

Every refusal above raises `HTTPException` (409/422) or `PaperOrderError`. **No `Order` row is
ever written.** `Order.status` has exactly two values in the codebase — the `"pending"` column
default and `"filled"`, set by the paper broker. There is no `rejected`, no `cancelled`, no
`denied`.

So **the orders table records only successes.** What we refused, and why, survives today in:

- a log line, and
- the `broker_payload` stamps — but those are written *after* a successful fill, so a
  **blocked** order stamps nothing;
- ⚠ and the shadow sidecars do **not** read those stamps. They **recompute** the verdict from
  `Signal` rows using *today's* thresholds (the A38 correction of 2026-09-05). Only
  `circuit_gate` and `chase_gate` stamps have readers at all.

**Consequence:** we cannot currently answer *"what did the risk layer refuse last Tuesday, and
under which thresholds?"* from data. That is the audit-trail hole 7.4 is meant to close, and it
starts here, in 7.0, because it is a state-model problem before it is a logging problem.

### 1.2 The fill is synchronous, and that is a paper artefact

`place_paper_order` resolves a price and fills inside the same transaction. A real broker
returns an **acknowledgement**, and the fill arrives later on a different channel — possibly
partially, possibly never. If `BrokerAdapter.submit()` is designed against the paper behaviour
it will return a fill, and every caller will be written assuming one.

### 1.3 There is no concept of cash committed to an un-filled order

`size_for_fill` and `_check_notional_cap` reason about `user.capital_inr` and the value of
*existing positions*. Nothing accounts for an order that has been sent and not yet filled.
**Harmless today precisely because of 1.2** — there is no interval during which an order is
outstanding. It becomes a real over-commitment bug the moment there is.

### 1.4 What must be preserved: the verdicts, exactly

A38 proved the current chain's behaviour unchanged under differential fuzz (30,000 order-path
cases, 0 block diffs). **7.1 must clear the same bar**: identical verdicts before any refactor.
The registry in `app/signals/restrictions.py` is already the single declaration — 7.1 *consumes*
it, and must not start a second sequence (**W2**).

---

## 2. A33 — the OMS as a projection of an event stream

### 2.1 The decision

**An append-only `order_events` table becomes the source of truth; the `orders` row becomes a
projection of it.** Not the other way round, and not both.

The alternative — keep mutating `orders` and add an audit log beside it — was rejected: two
writers to the same truth drift, and the drift is discovered during reconciliation, which is the
one moment you need the record to be trustworthy. This is the same argument that made
`app/signals/restrictions.py` one registry instead of two sequences.

### 2.2 The event set

Every event carries `(order_id, seq, at, kind, payload)`; `seq` is per-order and monotonic, so
replay is deterministic and a gap is detectable.

| kind | meaning | who emits |
|---|---|---|
| `submitted` | intent recorded — **written BEFORE any gate runs** | RiskEngine caller |
| `denied` | **we** refused it | RiskEngine (7.1) |
| `accepted` | the broker acknowledged it | BrokerAdapter (7.2) |
| `rejected` | **the broker** refused it | BrokerAdapter (7.2) |
| `partially_filled` | a partial fill arrived | BrokerAdapter (7.2) |
| `filled` | fully filled | BrokerAdapter (7.2) |
| `cancel_requested` / `cancelled` | cancellation intent, then confirmation | either |
| `expired` | validity elapsed unfilled | timer (A34) |

⭐ **`denied` and `rejected` are different events on purpose** (the Nautilus distinction, and
7.3's core). *Denied* is our own risk layer and is **entirely within our control** — a rising
denial rate is a finding about our thresholds. *Rejected* is the broker's and is a finding about
the market or our credentials. Collapsing them into one "failed" bucket destroys the only signal
that separates "our rules are too tight" from "the exchange said no", which is exactly the
question a 45-day cycle-2 rehearsal exists to answer.

### 2.3 `submitted` is written first, and that is the whole point

Writing the intent **before** the gates run is what turns 1.1 from a logging gap into a
structural guarantee: **a decision cannot fail to be recorded, because the row exists before the
decision is made.** A denial then appends `denied`; it does not "fail to create" anything.

⚠ **CORRECTION — 2026-09-07, as built.** This section originally said the `orders` table
would *become* a list of intents, and every reader would have to be re-checked. **That is
not what shipped, and the built version is safer.** The intent lives in `order_events`
only; `orders` still gets a row exactly when a fill happens, so **no existing `orders`
reader changed meaning at all** and the "grep before assuming" hazard never materialised.

The projection direction in §2.1 is unchanged — `order_events` is the source of truth for
what an order *did* — but the `orders` row remains the projection of the *filled* subset
rather than of every intent. Reconstructing the full intent history means reading
`order_events`, which is where `event_store.refusals_between()` points.

⚠ The original hazard returns the moment anyone *does* start writing `orders` rows for
non-fills. If that ever happens, every count, join and report reading `orders` must be
re-checked against a terminal-state filter — the `is_shadow IS FALSE` lesson from
`signals.status`, in a new table.

### 2.4 One `is_active()` predicate

```
ACTIVE   = {submitted, accepted, partially_filled, cancel_requested}
TERMINAL = {denied, rejected, filled, cancelled, expired}
```

**One function, one place** — `is_active(order) -> bool`. The rule that makes it useful:
*an order is active iff it can still consume capital.* That is why `partially_filled` is active
(the remainder can still fill) and why `denied` is terminal (it never can).

⚠ **Nothing may re-derive this inline.** The gate-vocabulary incident (T7) is the precedent: the
mode `Literal` was declared **nine times** and tied together nowhere, so a fourth value would
have silently fallen through as "off" *on the order path*. Same shape, same fix — declare once,
pin with an exhaustiveness test.

### 2.5 Gateway-namespaced ids

`paper:<uuid>` · `kite:<broker_order_id>`. Two reasons, and the second is the load-bearing one:

1. A broker id can never collide with one of ours.
2. **Reconciliation can tell "an order we do not know about" from "an order from a different
   gateway".** Without a namespace those look identical, and the safe response to each is the
   opposite — one is an alarm, the other is noise.

---

## 3. A42 — frozen and available cash

### 3.1 The decision: derive, never store

```
available(user) = capital
                − Σ  value of open positions
                − Σ  frozen(o)   for o in orders where is_active(o)

frozen(o)       = (o.quantity − o.filled_qty) × o.limit_price_or_estimate
```

**A stored cash balance is a fourth writer to a truth three other tables already own.** It drifts
on every missed event, and it drifts *silently* — the failure looks like a correct number.
Deriving it from A33's active set means the only way to get it wrong is to get `is_active()`
wrong, and `is_active()` is pinned by an exhaustiveness test.

⚠ Cost, stated rather than discovered: `available()` is a query, not a field. It must be
**batched** on any path that needs it per-position — the A21 precedent (one `get_live_depths`
MGET for the whole book, never a per-position Redis read).

### 3.2 It fails CLOSED

Consistent with the heat cap (7.1) and the daily-loss breaker, and **deliberately unlike the six
selection overlays**. For a *selection* gate the error to avoid is suppressing a good trade on
uncertainty. For a *capital* rail it is committing money you cannot account for. If the active
set cannot be read, the answer is zero available, not unlimited.

### 3.3 What it is not

**Not margin.** Cash-equity delivery only, matching what the paper model does today. Margin,
MTF and F&O span are Phase-7-after-cycle-2, and modelling them from the docs without having
called Kite is the exact risk 7.2's read-only spike exists to retire.

---

## 4. A35 — the BrokerAdapter interface

### 4.1 The shape, and the one rule that fixes it

```python
class BrokerAdapter(Protocol):
    gateway: str                      # "paper" | "kite" — the id namespace

    async def submit(self, req: OrderRequest) -> Ack        # NEVER a Fill
    async def cancel(self, order_id: str) -> Ack
    async def fetch_open_orders(self) -> list[BrokerOrder]  # reconciliation (7.4)
    async def fetch_positions(self) -> list[BrokerPosition] # reconciliation (7.4)
    async def fetch_funds(self) -> Funds                    # A42's ground truth
```

⭐ **`submit()` returns an `Ack`, never a `Fill`.** This is the single most important line in
the design. Paper *can* fill synchronously and will still return an `Ack`, then emit
`filled` on the same event channel a real broker uses. If paper were allowed to return a fill,
every caller would be written against a synchronous world and 7.2's abstraction would be met on
day 1 of live — which is precisely the failure the plan says cycle 2 exists to prevent.

**Fills arrive as events, not return values.** One channel for both adapters.

### 4.2 What the interface deliberately does NOT have

- **No `place_and_wait()`.** A convenience that re-synchronises the world would be used, and the
  asynchrony would leak back out.
- **No GTT.** Post-cycle-2; only reality validates it.
- **No Kite-specific fields** (`variety`, `validity`, `product`) on the shared type. They belong
  in `KiteBrokerAdapter`'s own translation layer, or the "interface" is just Kite's API with an
  extra indirection — which is the standard way a port stops being a port.

### 4.3 Errors are classified at the adapter boundary

`retryable` (network, 5xx, rate limit) vs `terminal` (rejected, insufficient funds, bad symbol)
vs `unknown`. **`unknown` is not retryable** — retrying an order whose fate you do not know is
how you get two positions. This is A28's classification, pulled to the boundary where the
broker's own vocabulary is still available and has not yet been flattened into a generic
exception.

⚠ **Kite specifics that shape this** (already on record, not new findings): the access token
dies **~06:00 IST daily** and expiry is a *normal lifecycle event*, never an error loop; and
**all REST goes through the shared throttled client** (~3 req/s historical) — never raw
`requests`/`httpx`.

---

## 5. Build order, and what each slice may assume

| slice | may assume | must not assume |
|---|---|---|
| **7.1** RiskEngine | the A38 registry; `is_active()` exists | any broker; any async fill |
| **7.2** BrokerAdapter | 7.0's event kinds; `Ack` ≠ `Fill` | that fills are synchronous |
| **7.3** Order FSM | every event kind is emitted by someone | a single-threaded bus |
| **7.4** Reconciliation | namespaced ids; the event stream is complete | that the local view is right |

**7.1 first because it is the only one that changes a *decision*.** 7.2–7.4 move state and
plumbing; 7.1 is where a rejection either matches today's chain or does not, and the
equivalence pin is cheapest to hold while the surrounding machinery is still the old one.

---

## 6. Open questions carried into 7.1 — flagged, not silently resolved

1. **Does `submitted`-before-gates change the recorded number? — CHECKED, and the answer is no.**
   Order *counts* change (denials become rows); no P&L, fill or position changes. Both readers
   were verified rather than assumed:
   - **`max_trades_per_day` counts `Position.id`, not orders** (`circuit_breaker.
     get_trades_taken_today`) ⇒ the breaker cannot be loosened or tightened by denial rows.
   - **The only `select(Order)` in the reporting layer** (`daily_report.py:605`, the fill-quality
     section) already filters `Order.status == "filled"` **and** `filled_at` within the window
     ⇒ denial rows are excluded twice over.

   ⚠ The rule still stands for anything added later: a denial row is an *intent*, not a trade,
   so **every new `orders` reader must filter on terminal state or `is_active()`**. This is the
   `signals.status` lesson in a new table — `status` there is a lifecycle field the sweeper
   overwrites, which is why tradeable statistics must filter `is_shadow IS FALSE` instead.
2. **Heat cap denominator** — `capital_inr` (₹1L live) or `paper_sampling_capital_inr`? The
   latter is declared **reporting-only and must never touch sizing**, so the cap uses
   `capital_inr`. Recorded here because the two-denominator split is new and easy to misapply.
3. **Backtest still consults no gate**, and `app/backtest/engine.py` is FROZEN. The RiskEngine
   does not change that. It stays the standing divergence between backtest and paper — alongside
   the larger one found while wiring A23: **the backtest models no trading costs at all.**
