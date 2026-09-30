# PR-1 — pre-registration extract for external review (2026-09-30)

**Self-contained.** You do not need our code or data. **Nothing below has been run.** This is the
design we intend to commit *before* writing the analysis code; your review is the last check.

## What we ask of you — three questions, nothing else

1. **What would make the result biased or uninterpretable?** Name the mechanism, and say how you
   would detect or fix it within this design.
2. **Recompute** the cost intervals in §5 and the statistical bar in §6 from the stated inputs, and
   show your working. Say MATCH or MISMATCH.
3. **Is one kill criterion or one confound missing?** One is enough; "none" is a valid answer.

Please **don't** judge whether the strategy will be profitable. No one can know that before the
data, which is the point of pre-registering. Please don't propose unrelated strategies either.
Mark anything you are unsure of as unsure, and don't cite a source you have not read.

## 1. The idea — liquidity provision at the close

Some participants must trade **at the closing price**: passive funds tracking the index, derivative
settlement, and mutual-fund NAV. They pay for immediacy. Whoever takes the other side is paid when
the price pressure reverses. We test whether, on NSE, a stock pushed **down** into the close (against
its peers) rebounds afterwards, and by enough to pay retail costs.

Predictions, stated before any data:

- **P1:** the reversal is concentrated **overnight** (close → next open).
- **P2:** it scales with the size of the late move.
- **P3:** it is larger on high-volume closes.
- **P4:** it is larger when VIX is high (Nagel, *RFS* 2012).
- **P5:** it is not the overnight-gap reversal effect, which we already tested and rejected.

**Prior evidence:**

- US closing-auction deviations reverse by about 85% by the next morning (Bogousslavsky & Muravyev,
  *J. Financial Markets* 66, 2023).
- Our own 7-session sample from NSE's new closing auction (Aug–Sep 2026): cross-sectional Spearman
  ρ = −0.272 (day-block 90% CI [−0.478, −0.088]); bottom-minus-top quintile next-day return +1.27%.
- ⚠ Half of that effect came from **one** session, and the 7 sessions' data was later lost. It is a
  lead, not evidence.

## 2. Market facts the design relies on (primary sources)

| fact | source |
|---|---|
| Before 3 Aug 2026 the NSE close was the **VWAP of the last 30 minutes** of continuous trading | SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 (16 Jan 2026) §1 |
| Since 3 Aug 2026, F&O stocks close by a **call auction 15:15–15:35** (orders 15:20–15:30, random close 15:28–15:30); one equilibrium price is the official close; band ±3% of the 15:00–15:15 VWAP | same circular §4.2, §4.4.1; NSE circular NSE/CMTR/73362 |
| A **post-close session trades at the closing price**: 15:50–16:00 now (SEBI §4.2.4), 15:40–16:00 before the auction. Retail can buy there with **market orders, delivery (CNC) product** | Zerodha support "pre-market & post-market sessions" (current page, and a 2025-05-30 archive) |
| Intraday (MIS) positions in auction stocks are squared off at **15:12** | Zerodha support "What is SEBI's CAS" |
| Stock and Nifty derivatives expire on **Thursday up to 31 Aug 2025, Tuesday from 1 Sep 2025** | NSE circular NSE/FAOP/68747 (25 Jun 2025) |

## 3. PR-1 in one paragraph

We use **historical, pre-auction data** (the old closing mechanism) as a *mechanism test*. Does a
late-session move against peers predict the opposite move afterwards? If it passes, a second study
(PR-2) tests the live auction regime forward, on sessions collected since August 2026 that have not
yet been looked at.

## 4. The pre-registered design (draft v2)

| # | clause |
|---|---|
| 1 | **Question** as §3. |
| 2 | **Data:** 5-minute bars (signal) and daily official open/close. **2023-07-03 → 2026-07-31 = 763 sessions.** Two earlier blocks (2019-10 → 2023-07) are sealed as holdouts and are **not** read. |
| 3 | **Cohort per session t:** a fixed set of ~205 F&O stocks (the names we capture 5-minute bars for; *not* point-in-time). Keep names with all 75 five-minute bars on t and on t+1. Skip sessions with fewer than 150 names. Drop names with a split or bonus ex-date on t+1. **Usable (t, t+1) pairs: 756.** 3 special short sessions fall out. |
| 4 | **Signal s:** (last trade before 15:30 − last trade before 15:15) ÷ last trade before 15:15, **demeaned across names** within the session. |
| 5 | **Outcomes**, demeaned within session: **R_on** = (open t+1 − official close t) ÷ close t · **R_day** = (price at 15:10 on t+1 − open t+1) ÷ open t+1. The exit is 15:10 because of the 15:12 MIS square-off. |
| 6 | **Book:** each session, the **5 names with the most negative s**, equal weight, long only. |
| 7 | **E1 (information):** mean over sessions of Spearman IC(s, R_on). Newey–West t with lag 10; 90% CI. |
| 8 | **Branch, fixed in advance:** if the book's mean R_on ≥ mean R_day ⇒ **delivery** version (buy at the close in the post-close session, sell at the next open); cost interval **[29.89, 32.17] bps**. Otherwise ⇒ **intraday** version (next open → 15:10); cost interval **[14.08, 15.16] bps**. |
| 9 | **Decision:** **PASS** only if the branch's gross 90% CI **lower** bound > the **top** of its cost interval **and** the net t ≥ **3.575** **and** no kill fires. **KILL** if any kill fires or the gross CI **upper** bound < the **bottom** of the cost interval. **Anything else is a NULL:** we stop, and do not re-specify. |
| 10 | **Kills:** mean IC ≥ 0 · > 50% of net P&L from ≤ 5% of sessions · the two halves disagree in sign · > 50% of net P&L from ≤ 3 names. |
| 11 | **Descriptive only, never used to decide:** weekday × expiry-day breakdown · VIX terciles (P4) · late-volume terciles (P3) · a long-short intraday variant. |
| 12 | **Known weaknesses:** (a) the old close is not an auction — this is mechanism evidence only. (b) The backtest assumes every post-close buy fills at the close; **real fills may be adversely selected** (holders expecting a bounce won't sell), so this result is an **upper bound**. A forward capture of post-close volume and pending quantity is now running to measure it. (c) **Dividend ex-dates are not excluded** (our corporate-action data holds splits and bonuses only); estimated bias ~0.5 bps, conservative. (d) The fixed ~205-name set is not point-in-time. |
| 13 | **Order:** this text is committed → the code is written → it runs **once** → the report is written. |

## 5. Cost inputs — please recompute

A retail discount-broker schedule (Zerodha, ≈2025). All percentages are of turnover.

- **Delivery (CNC):**
  - brokerage 0;
  - STT 0.1% on **both** legs;
  - stamp duty 0.015% on the buy;
  - exchange transaction 0.00297% on both legs;
  - SEBI fee ₹10 per crore on both legs;
  - GST 18% on (brokerage + exchange + SEBI);
  - a depository charge of **₹15.34 per sell, flat** (GST-inclusive, added after GST).
- **Intraday (MIS):**
  - brokerage min(0.03%, ₹20) per order;
  - STT 0.025% on the **sell**;
  - stamp duty 0.003% on the buy;
  - exchange, SEBI and GST as for delivery;
  - no depository charge.

Our results, at price ₹500 with entry = exit. **Each leg's total is rounded half-up to the paisa**
before the two legs are added, so a hand calculation can differ by ₹0.01:

| round trip | ours |
|---|---|
| delivery, 40 shares (₹20,000) | ₹59.78 = **29.89 bps** |
| delivery, 66 shares (₹33,000) | ₹88.69 = **26.88 bps** |
| intraday, 40 shares | ₹21.20 = **10.60 bps** |
| intraday, 100 shares | ₹53.02 = **10.60 bps** |

**Spread:** estimated half-spread 1.74 bps (90% CI 1.58–1.93; bracket up to 2.28), from an
Abdi–Ranaldo estimator on the same stocks. A continuous-market leg pays one half-spread; auction
and fixed-price legs pay none.

Hence **delivery [29.89, 32.17]** (post-close entry, or a continuous-market entry paying up to one
half-spread) and **intraday 10.60 + 2 × [1.74, 2.28] = [14.08, 15.16]**.

## 6. The statistical bar — please recompute

We count about **21 strategy trials** in this programme, all previously tested and rejected, plus
this one. The bar is a **Deflated Sharpe ratio of 95%** (Bailey & López de Prado):

- E[max SR] = σ_SR · ((1 − γ) Φ⁻¹(1 − 1/N) + γ Φ⁻¹(1 − 1/(N e))), with γ = 0.5772 and
  σ_SR = 1/√n.
- PSR = Φ( (SR − SR\*) √(n − 1) / √(1 − skew · SR + (kurt − 1)/4 · SR²) ).

With N = 21, n = 763, skew 0 and kurtosis 3: E[max SR] = 0.069585; the smallest per-session Sharpe
reaching PSR ≥ 0.95 is 0.129421, so the **required t = 3.5749**. (It barely changes at n = 756; the
bar is set by N, not n.) That equals a **net annualised Sharpe of about 2.05** (0.1294 × √252) on this
three-year window.

## Reply format

Number your answers 1–3. Show calculations for 2. For 1 and 3, give the mechanism, the direction of
the bias if you can, and how this design would detect it.
