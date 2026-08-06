# Fix plan — from the 2026-08-03 → 08-05 paper week

Prioritised, reviewed backlog surfaced by the daily reports in this folder.
Everything here concerns **paper** behaviour (live trading is Phase 7); each
item names the invariants it touches and the review agents to run. Sequencing
is **evidence-first**: the reports/shadow quantify the leak before we change
exit or sizing behaviour on the book that gates go-live.

Order-of-operations: **P0 shipped → gather 1–2 more clean days → P1 → P2 (with
the shadow retune) → P3.** P3 (UX) is independent and can slot in any time.

---

## The evidence in one paragraph

15 trades over 3 days (5/day, the max-trades cap). Realised **+₹188** vs last
week's **−₹12,159**, but that's flattered: 11 positions are held open, the open
book's green is **entirely STEELXIND**, and **only 1/15 trades ever reached
+1R**. Because the profit-lock only *arms* at +1R, it had nothing to protect on
14/15 — so profit made (peak) then given back (~₹21k peak→final across the
week). Three entries were **chased** past the 0.33R ceiling; BAJAJFINSV filled
0.75R past entry → **3.37% risk on one trade, over the whole ₹3,000 daily cap**.
Portfolio heat hit **30.7% of capital** open-at-risk with no cross-day cap.
Root causes are structural, not bad luck.

---

## P0 — Correct the misleading docstrings ✅ DONE (this session)

Two docs claimed the profit-lock was "shadow-only / not wired to live exits."
It has been per-user live-wired for paper since the profit-lock-live-wiring
merge (`position_monitor` → `layered_ratchet_stop` when `profit_lock_enabled`).
That stale text is what made the exit governor's behaviour surprising.

- Fixed: `app/trading/profit_lock.py` module docstring;
  `docs/STOCK_SELECTION_AND_ALERTS.md` §B.8 (both trail-SL and profit-lock
  bullets); `app/broker/paper_broker._apply_slippage` ("default is 2 bps", not 0).

---

## P1 — Stop the silent oversize on chased / stacked entries  **— ✅ DONE 2026-08-06**

_Shipped as option (a) + anti-stacking: `paper_broker.size_for_fill` sizes from the
actual fill (risk capped at budget), repeat entries size against remaining budget,
entry orders record chase telemetry. Chose resize-not-block (the resize already caps
risk; the anti-chase warning flags degraded R:R). Option (c) portfolio-heat cap is
still open (see watch-list)._


**Problem.** `place_paper_order` sizes quantity from the *signal's* entry→SL
distance, then fills at **market (LTP)** and keeps the signal's SL. So the real
per-share risk is `|fill − SL|`, not `|entry − SL|`, and the position is
silently oversized whenever you don't fill at the signal entry. Repeated Buy
clicks compound it (each averages-in at a fresh full-2% size).

**Evidence (this week).** BAJAJFINSV 1.75×/₹3,366 (3.37% > daily cap),
GEOJITFSL 2.69×/5.4%, STEELXIND 1.44×, HAL 2.69× (qty stacked to 15 vs a
2%-sized ~5). Portfolio heat 30.7% of capital.

**Options** (need your sign-off — this is trading-safety behaviour):
- **(a) Resize qty to the actual fill** so `qty = floor(risk_budget / |fill − SL|)`
  → risk% stays capped no matter where you fill. Preserves the structural SL;
  R:R still honestly degrades. *Recommended.*
- **(b) Reject/soft-block a market order whose LTP is past the 0.33R chase
  ceiling** (`entry + 0.33R`), requiring an explicit override — mirrors the
  AlertBell guard on the *execution* side, not just the display. *Recommended,
  in addition to (a).*
- (c) Cap cumulative open risk (portfolio heat) and per-name stacking — the
  circuit breaker currently caps only *daily realised* loss, not open risk
  across days. Bigger change; likely its own item.

**Invariants touched.** Position-sizing (§ "position sizing mandatory";
reject-don't-clamp — a chase-block is a reject, never a clamp), circuit-breaker
semantics (add an open-risk view without weakening the daily-loss breaker —
which is never disableable). **Reviews:** quant-verifier (sizing math),
bug-hunter (order path / async), test-guardian. **Tests:** chased fill resizes
qty and caps risk%; a past-ceiling market order is rejected/flagged; repeated
Buy stacking is bounded; regression asserting old behaviour oversized.

---

## P2 — Profit-lock: protect earlier + retune on the tapes  **— ✅ DONE 2026-08-06 (rupee ladder)**

_Shipped as the trader's absolute-₹ ladder (`profit_lock.absolute_ladder_stop`), now
the live paper governor when `profit_lock_enabled`: breakeven at +₹2,000, seal
(peak − ₹1,000) above ₹3,000, ATR-room elasticity. Thresholds are config knobs to
**tune on the tape toward the ₹4–5k/day goal** — the retune is the ongoing work, not
a one-time change. Next: watch the daily report's "profit sealed" + give-back trend
and adjust `profit_lock_*_inr` / `_atr_k`._


**Problem.** The ratchet arms only after +`arm_r`·R (1.0R swing/positional). Below
that the SL sits at the original signal level, so a sub-1R pop that reverses
gives everything back. This week that's INDGN +₹1,540→−₹672, MSUMI
+₹729→−₹456, KRBL +₹533→−₹401, HAL, KOTHARIPET — the #1 leak. Even once armed,
`giveback_early` is 0.55–0.60 for swing/positional (over half the peak allowed
back). Chasing (P1) inflates R, delaying the arm further.

**Direction (agreed).** *Add earlier protection AND retune params on evidence.*
- **Earlier rung:** move the SL to breakeven (or +small R) once the trade is
  modestly green (e.g. +0.5R), before the full ratchet arms — so a fade after a
  small pop doesn't round-trip to the original stop. Keep it one-way/monotonic.
- **Retune, don't guess:** the `CLASS_PARAMS` are explicitly "starting points
  for backtest, not final." Use `profit_lock_shadow` over this week's real 1m
  tapes (the reports already load them) + the 2y backtest corpus to fit
  `arm_r` / `giveback_*` / `atr_k`. Add the candidate "breakeven-then-layered"
  policy to the shadow comparator so the report quantifies the upside
  per-trade before anything changes.

**Constraints.** Paper-only, shadow-first; changes here feed the Phase-7
go-live gate, so no hand-tuning on the live book. **Reviews:** quant-verifier
(the exit math is analysis-adjacent), test-guardian. **Tests:** the new rung is
monotonic and never moves against the position; per-class param changes have
golden expectations; a "sub-1R pop then reverse" case keeps more than the
current ladder.

---

## P3 — Let me trade the alerts (and at the shown price)  **— ✅ Buy/Sell from AlertBell DONE 2026-08-06; limit orders deferred**

_Shipped Problem A: every entry-zone alert has a Buy/Sell button through the paper
order path (halt- and direction-aware). Problem B (limit orders / order-source field)
is deferred — a resting-limit order-state-machine is its own slice, and P1's
fill-based sizing already caps the risk of a market entry._


**Problem A — can't act on an alert.** The only Buy button is on a *visible*
dashboard signal row (and StylePage). The dashboard `/signals/active` dedups to
one representative per (stock, direction, class), **hides choppy + near-expiry
by default**, filters by confidence, and paginates to 50. Alerts fire off the
*full* active-signal set — so alerted names (INTERARCH, ORKLAINDIA, TAINWALCHM…)
are absent from the table and have **no reachable trade affordance**, even at
Min-Conf 50%.

**Problem B — can't enter at the alert price.** The order path is market-only
(`PlaceOrderRequest` = signal_id + side + optional qty; fills at LTP). The
AlertBell shows `BUY @ 2096` but you fill at LTP 2103.70 with no limit field.

**Fixes.**
- Add a **Buy/Sell affordance directly on AlertBell entries** (each alert
  carries its `signal_id`), routing through the same order path + circuit
  breaker. Also surface a trade action on the Stocks page for any active signal.
- Add **limit-order support**: `order_type` + `price` on the order path so you
  can enter at the alert's entry (or the anti-chase ceiling), not just market.
  Pairs naturally with P1 (a limit at/under the ceiling can't chase).
- Add an **order-source field** (alert / dashboard / manual) so future reports
  can attribute "your picks vs alert picks" — today only manual *exits* are
  distinguishable. (This is what makes the "DECNGOLD was my pick" question
  answerable from data.)

**Invariants touched.** None in the engine; execution + UI only. **Reviews:**
ui-reviewer (tokens, portal, themed controls, number formatting per
`.claude/rules/ui.md`), bug-hunter (order path), test-guardian. **Tests:** an
alert's Buy places through the breaker; a limit order fills/rests correctly;
RTL coverage for the AlertBell action (loading/empty/error/primary).

---

## Watch-list (smaller, noted so they aren't lost)

- **Outcome vs fill divergence.** DHAMPURSUG's `signal_outcome` = `tp_first`
  while the *position* stopped out −₹2,521 — the known cross-trigger / gap
  measurement limit (SignalOutcome docstring). The report shows both; don't
  read the outcome ladder as the P&L.
- **Cross-day open-risk cap.** The breaker caps daily *realised* loss and
  trades/day, not the 30%+ open risk that accumulated across the week. Consider
  an advisory portfolio-heat gate (never weakening the daily breaker).
- **Alert-stream snapshot.** Persist a daily snapshot of `alerts:live` so the
  report's AlertBell recap is the real firings, not just the durable
  reconstruction.
