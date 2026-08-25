# Horizon & recovery study — "it failed for the day, then it came back" (2026-08-25)

_Read-only, retrospective. Motivated by an observation from the desk: **several names that were
stopped out looked wrong on the day and then recovered over the following sessions** — i.e. they
behaved like the swing/positional trades they were labelled as, while the book judged them on a
one-day clock. This study asks whether that is real, how much it costs, and what (if anything)
should change._

**Nothing here authorises a money-path change.** It is a study on a small, benign, retrospective
sample — not a §8 walk-forward. What it does do is (a) explain a live losing streak, (b) independently
corroborate the already-built `sl_atr` shadow gate from a different angle, and (c) identify one
*reporting* change that is safe to make immediately.

---

## 1. Method

- **Cohort:** every closed paper position with a parent signal (`mode='paper'`, `closed_at IS NOT
  NULL`) — **82 trades**, 2026-07-07 → 2026-08-25. Plus the 13 positions open at the 08-25 close.
- **Forward tape:** `ohlcv_1d` bars strictly after the exit date (recovery test) or from the entry
  date (horizon replay). Daily bars only — this study never reads intraday data, so it cannot see
  the order of events inside a bar.
- **Volatility yardstick:** `avg_daily_range` = mean of `high − low` over the ~14 sessions *before*
  entry. Used as an ATR proxy so the study is independent of the engine's own ATR call.
- **Unit:** **R** — the trade's own risk, `|entry − SL| × qty`. R is the only honest unit here,
  because the platform sizes risk-first (`qty = floor(capital × risk% / |entry − SL|)`), so a wider
  stop automatically buys a *smaller* position. Comparing rupees across stop widths compares
  position sizes, not stop placement. **A first pass of this study held qty constant and concluded
  wider stops were catastrophic; that was a sizing artifact, not a finding.**
- **Conservatism:** when a daily bar contains both the stop and the +1R, the **stop is assumed
  first**. Every counterfactual below is therefore a lower bound.

---

## 2. The observation is real — but it is a bounce, not a vindication

Of the **17 stop-out losers**, 16 have forward bars. **11 of 16 (69%) traded back through their own
entry price**, and the median time to do so was **1 trading day**.

| Symbol | Side | Class | Net | Stop ÷ daily range | Days to recover to entry |
|---|---|---|--:|--:|--:|
| PNCINFRA | LONG | positional | −₹6,800 | 0.33× | 1 |
| ASPINWALL | LONG | positional | −₹3,471 | 0.53× | 1 |
| SPARC | LONG | swing | −₹4,022 | 0.05× | 1 |
| SRTL | LONG | swing | −₹3,565 | 0.65× | 1 |
| LENSKART | SHORT | swing | −₹683 | 0.06× | 1 |
| NDRAUTO | LONG | positional | −₹14,970 | 1.27× | 1 |
| PCBL | SHORT | swing | −₹2,737 | 0.67× | 2 |
| NATCOPHARM | LONG | swing | −₹2,583 | 0.47× | 2 |
| PREMIERENE | SHORT | swing | −₹2,257 | 1.65× | 2 |
| ABSLAMC | SHORT | swing | −₹2,221 | 0.64× | 3 |
| RKDL | LONG | swing | −₹1,880 | 1.43× | 3 |
| DHAMPURSUG | SHORT | swing | −₹2,521 | 1.97× | never |
| TNPL | LONG | positional | −₹3,037 | 1.30× | never |
| GLOBAL | SHORT | swing | −₹2,131 | 1.14× | never |
| KOTHARIPET | LONG | positional | −₹2,580 | 1.56× | never |
| KSL | SHORT | swing | −₹2,278 | 2.37× | never |
| PFIZER | LONG | positional | −₹2,097 | 2.25× | _no forward bars yet_ |

**The important caveat, stated up front: "just hold" is much worse, not better.** Marking the same
names to the latest available bar instead of honouring the stop gives NDRAUTO −₹54,701 and
PNCINFRA −₹77,464. The recovery is a **transient bounce inside a few sessions**, not the thesis
eventually paying. Any reading of this study as "our stops are too tight, loosen them" is wrong.

---

## 3. The real split: is the stop inside the noise, or outside it?

Sorting the same 17 losers by **stop width ÷ average daily range** separates them almost perfectly:

| Group | n | Recovered to entry | As-traded expectancy |
|---|--:|--:|--:|
| **A · stop < 1.0× one average daily range** | 8 | **8 / 8 (100%)** | **−1.45R** |
| **B · stop ≥ 1.0× one average daily range** | 9 (8 with data) | 3 / 8 (38%) | −1.17R |

The mechanism is simple and it is not about conviction:

> **A stop narrower than one average session's range is not a stop — it is a coin flip with a fee.**
> A perfectly ordinary day's noise reaches it, so the exit carries no information about whether the
> setup was right. When the stop sits *outside* the noise band, being hit means something: only 38%
> of those names came back.

### 3a. Tight stops don't even deliver their −1R

The intended loss on a stop-out is −1.00R. What the book actually realises, bucketed by stop width:

| Stop ÷ daily range | n | Mean realised loss on losers |
|---|--:|--:|
| < 0.25× | 3 | **−1.70R** |
| 0.25 – 0.5× | 4 | −1.25R |
| 0.5 – 1.0× | 7 | −1.43R |
| 1.0 – 1.5× | 13 | −0.99R |
| ≥ 1.5× | 55 | −0.50R |

This is the **cost-overshoot** half of the leak, and it is a direct consequence of the honest fill
model shipped in 6.8.2: half-spread + size impact is a roughly *fixed price* cost, so it is a much
larger fraction of a narrow stop. A tight stop is therefore penalised twice — hit by noise, and then
charged more than 1R for the privilege. (The ≥1.5× row's −0.50R is flattered by the 2026-08-17
clean-slate flatten, which closed 28 positions `manual` before their stops were reached.)

### 3b. Widening the stop rescues group A — and does not cost the winners

Replaying the **whole 82-trade cohort** (winners included) at a volatility-scaled stop, risk-normalised
so every variant risks the same rupees:

| Variant | Total R | Expectancy | Win % | Trades ≥ +1R |
|---|--:|--:|--:|--:|
| replay @ planned SL | −4.19R | −0.05R | 43% | 12 |
| replay @ 1.0× daily range | +6.89R | +0.08R | 39% | 23 |
| **replay @ 1.5× daily range** | **+8.79R** | **+0.11R** | 48% | 19 |
| replay @ 2.0× daily range | +3.62R | +0.04R | 49% | 10 |

Restricted to the 14 trades whose planned stop was inside the noise band, the same replay moves
**−0.87R → −0.11R** per trade. Restricted to the other 68, it barely moves. **The gain is entirely
concentrated in the group the study predicts it should be.**

> ⚠️ **Replay-vs-replay only.** The daily-bar replay cannot see the intraday ratchet or the profit-lock,
> so its absolute level (−0.05R at the planned SL) is *not* comparable to the book's actual +0.13R.
> Only the differences between replay variants are meaningful.

### 3c. This reproduces a gate we already built

`app/signals/entry_quality.py` already carries a **stop-too-tight** check —
`entry_sl_atr_gate_mode`, currently **shadow**, threshold `entry_min_sl_atr_mult = 1.0`. It flags
`|entry − SL| < 1.0 × ATR`. This study arrived at the **same 1.0× threshold from a different
yardstick** (average daily range, not ATR) and a different unit (R, not ₹), and it agrees with the
sidecar's own live numbers:

| Source | Flagged set | Passed set |
|---|--:|--:|
| `entry-quality-shadow-2026-08-25.md` | −₹13,937 over 12 resolved · 42% win | +₹4,472 over 62 · 53% win |
| this study (group A vs B, as traded) | −1.45R expectancy | −1.17R (B) / +0.09R (all wide) |

Two independent measurements agreeing is the strongest argument this gate has. It is **still not
enough to flip it**: the flip-readiness banner requires 20 resolved flagged trades and stands at
12, and a flip needs explicit sign-off. **Recommendation: keep accruing, and treat 1.0× as the
supported threshold when the flip is considered.**

---

## 4. The other half: we grade a 20-day trade on a 1-day clock

The desk's instinct was that these names were "behaving like swing/positional". The tape agrees —
the trades need **days**, and the daily report scores them in **hours**.

| Class | n | Touched +1R on the entry day | by day+1 | **within its own horizon** | Median best excursion |
|---|--:|--:|--:|--:|--:|
| swing (5 trading days) | 58 | 7 (12%) | 13 (22%) | **21 (36%)** | 0.85R |
| positional (20 trading days) | 24 | 3 (12%) | 5 (21%) | **13 (54%)** | **1.29R** |

**12% on the entry day versus 54% over a positional horizon is the same trades, measured on two
different clocks.** The "0/5 reached ≥1R" line that has led every daily report for three weeks is
an entry-day statistic being read as a verdict on the strategy.

And the race that decides whether we actually collect it:

| Cohort | +1R arrives first | Stop arrives first | Neither, in horizon | Median day of +1R |
|---|--:|--:|--:|--:|
| swing | 31% | 24% | 45% | d+1 |
| positional | **46%** | 42% | 12% | **d+3** |
| stop inside the noise band | 57% | **43%** | 0% | — |
| stop outside the noise band | 31% | 26% | 43% | — |

So for positional trades it is close to a coin flip between the target and the stop — and the tighter
the stop relative to the stock's own noise, the more often the stop wins that race.

---

## 5. Why this matters right now

The live book since the 2026-08-17 clean-slate cut is **6 closed trades, 1 winner, −₹10,817**. Four
of the five losers are in the recovery set above:

| Symbol | Net | Stop ÷ range | Recovered |
|---|--:|--:|---|
| SRTL | −₹3,565 | 0.65× | day+1 |
| ASPINWALL | −₹3,471 | 0.53× | day+1 |
| PREMIERENE | −₹2,257 | 1.65× | day+2 |
| KSL | −₹2,278 | 2.37× | never |
| PFIZER | −₹2,097 | 2.25× | no data yet |
| CGCL | **+₹2,850** | 0.86× | — (TP hit) |

Two of the three worst are group-A noise stop-outs. The current losing run is **not** evidence that
selection has degraded — it is consistent with the same mechanism this study describes, and with the
earlier two-window autopsy that attributed the "streak" to n=4 plus a down-drifting tape.

---

## 6. What should change (and what should not)

**Do now — reporting only, zero money-path risk:**

1. **Score entries on their own horizon.** The daily report's "reached ≥1R" line should read as
   `0/5 today · 4/13 within horizon so far` for the open book, not a bare entry-day count. A
   positional trade at day 5 of 20 is *unresolved*, not *failed*.
2. **Surface stop-width-in-ATRs at entry.** The number already exists — `sl_atr_mult` is stamped on
   every order's `broker_payload.entry_quality` (BHARTIARTL 08-25 carried `2.6147`). It should be a
   column in §2 of the daily report and a field on the Opportunities list, so a 0.05× stop is
   visible *before* the fill rather than in a post-mortem.

**Keep accruing — do not flip yet:**

3. `entry_sl_atr_gate_mode` stays **shadow**. This study supports the 1.0× threshold and adds the
   mechanism, but the readiness bar (20 resolved flagged trades) is unmet at 12, and this is a
   retrospective sample, not a walk-forward.

**Explicitly rejected:**

4. **Do not widen stops on the money path.** §3b's improvement is real but it is a retrospective
   replay on 82 trades, it cannot see intraday ordering, and the sample straddles a fill-model
   change. The platform's rule is *reject, don't clamp* — the correct response to a stop that is too
   tight for the stock is to **not take the trade**, which is exactly what the shadow gate does.
5. **Do not hold through stops.** §2 prices this at −₹54,701 on one name. The bounce is transient.

---

## 7. Honest limitations

- **n is small**: 82 closed trades, 24 positional, 17 stop-out losers. Every group-level number here
  has wide error bars, and one trade (LENSKART at a 0.03× stop, +11.02R) single-handedly flips
  group A's as-traded expectancy from −0.47R to +0.35R. That trade is the tiny-SL artifact the
  Phase-6 attribution already flagged.
- **The sample straddles a fill-model change.** Paper P&L before and after 2026-08-17 is not
  comparable (spread-aware slippage). Pooling them, as §3b does, is a known compromise.
- **Daily bars only.** No intraday ordering; stop-before-target assumed throughout.
- **The 08-17 clean-slate flatten** closed 28 positions `manual`, truncating their natural horizons
  and flattering the wide-stop bucket in §3a.
- **Benign tape.** The window contains no sustained trending regime, so nothing here says how a
  volatility-scaled stop behaves in one.

## 8. Reproduce

```
docker exec -i tp_postgres psql -U tpuser -d trading_platform     # cohort + forward bars
# study scripts are ad-hoc (this is a one-off read-only study, not a wired report):
#   recovery test      — days-to-recover-to-entry per stop-out loser
#   risk-normalised    — replay each trade at k x avg-daily-range, in R
#   horizon/race       — first-to-arrive: +1R vs stop, within class horizon
```

Related: `entry-quality-shadow-<date>.md` (the wired sidecar this corroborates) ·
`exit-ladder-research-2026-08-18.md` (the SRTL post-mortem that started the entry-side work) ·
`signal-age-2026-08-21.md` (the *other* entry-timing axis: trade fresh, ≤40% of validity).
