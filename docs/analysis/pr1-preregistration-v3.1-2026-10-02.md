# PR-1 — pre-registration, DRAFT v3.1 — the FREEZE CANDIDATE (2026-10-02)

**Self-contained.** **Nothing has been run:** no return, IC or other outcome from the test
window has been computed. The design facts in §8 read session-t data, plus outcome-free
same-session basis ratios on the neighbouring sessions t−1, t+1 and t+2 (cl. 3).

**Status.** v3.1 is draft v3 plus the fixes verified in the final verification round
(`docs/analysis/pr1-outside-pass-2026-09-30.md`, Round 2). **No further external rounds.** What
remains before the freeze:
1. one internal `quant-verifier` pass on the v3 → v3.1 diff (this text + the two probe scripts);
2. **the author's four decisions in §11** — each has a recommendation, and none is taken here;
3. commit this text together with PR-2's translation (§9a) → write the code → review it → run
   it **once** (cl. 15).

Every v3 clause is kept in full; the v3.1 changes are listed in §0a and marked **[v3.1]** where
they land.

## 0a. What changed from v3 (v3.1), and why

Row 16 would have decided the result by construction.

| # | v3 clause | the defect (found by) | the v3.1 fix |
|--:|---|---|---|
| 16 | 12 (K2) | **K2's whole-cohort IC lets the side the book never trades decide.** The reversal lives in the 5-name book, but the IC ranks all ~204 names, so a mild continuation of late UP-moves pushes the mean IC to ≥ 0 and kills a genuine pass. v3 §7 disclosed "K2 is not simulated", and that is where the defect was *(Claude chat, simulated; ChatGPT; Kimi — three sources)* | **K2 is computed on the bottom quintile of s.** Round 2 verified the lower half; the committed model (§7) measures the lower half at **2–5%** false kills on genuine passes (round 2's scratch model: 0.0%) and the bottom quintile at **0.0–0.6%**, both firing ~50% under the null. After the like-for-like fix (row 29) the bottom quintile fires on **0.0–1.3%** of genuine passes in every cell. The tighter set is adopted |
| 17 | 3 | **An adjusted corporate action other than a split or bonus can still cross a night.** Demergers, rights and adjusted dividends step the 5-minute table's basis too. RELIANCE's JFS demerger factor is **1.0491 = 1/0.9532**, the company's *tax cost-apportionment ratio*, not the market's price change, so the adjusted return across that night is **wrong**, not merely unrealizable *(DeepSeek, Claude; Kimi on dividends)* | **Drop every name-night whose same-session basis steps overnight and stays stepped** (cl. 3; row 27 adds the persistence test): A_d = official open ÷ 09:15-bar open. Measured: **187** strict steps dropped, **5** of them v3 book slots; 188 transient/mirror steps kept and counted; 9 not checkable (kept, counted) |
| 18 | §5 | **The spread top 2.68 was not shown to bound the MEAN half-spread** — the bounce cost is a mean, the bracket was built from medians *(ChatGPT)* | Measured: book-slot **mean 2.17 bps**, window-cluster 90% CI **[1.88, 2.47]** (CR1, t₃₆; clamped windows as 0; 2,882 of 3,740 slots covered; mean 2.17). 2.68 > 2.47, so the top is conservative. Stated in §5 |
| 19 | 9 (PR-2) | **PR-2's "same book rule" cannot run in the auction era.** On 2026-08-10, bars stamped 15:15–15:25 exist for **3 of 209** names (2026-07-10: 209 of 209), so P1530 is undefined and "all 75 bars" fails. Left open, PR-1's result could shape the translation *(Claude chat)* | **PR-2's translation is written out (§9a) and committed WITH this text** — rebuilt in row 28 |
| 20 | §9 | **"1.4 years" is 50% power, not a plan** *(Claude chat, ChatGPT)* | §9 states 80% power: **2.51 y** at annual Sharpe 2, **4.46 y** at 1.5 (one-sided 1%); plan on a SHRUNK effect (winner's curse) |
| 21 | 3, 7 | A suspended MIS slot: cl. 3 said "R_day = 0", cl. 7 "never entered" *(Claude chat)* | cl. 3 now defers to cl. 7: an MIS slot with no trade on t+1 is never entered |
| 22 | §6 | N_prior = 20 was a convention with no source *(Claude chat)* | Pinned to the agreement ledger, `nemotron_review.md` row **A3**: N = 20 for the programme, +1 per pre-registered estimand |
| 23 | §2, §8 | "The bases agree" was undefined; the facts script mislabelled 809 dividend-adjustment offsets as one-day mismatches *(internal)* | Defined as \|A − 1\| < 2%; label fixed |
| 24 | §7 | The simulation split K4 by index, not the dated halves; the two-branch max and the expiry-concentrated edge were not simulated *(ChatGPT, DeepSeek)* | K4 uses the **dated halves (382 / 366 pairs)**; both added to §7 |
| 26 | 5 | **The whole-cohort demeaning base lets the side the book never trades decide** (round 2 noted only a power drag, "≈ 25·m"). Measured (§7, like for like): when late up-movers REVERT it **manufactures a PASS on a zero-edge book — 9.3% at m −0.10, 35.5% at m −0.15, after K2**; when they continue it cuts power (13.6% at m +0.04) *(internal + quant-verifier, 2026-10-02)* | Demeaning against the **middle tercile**: false PASS ≤ 0.2%, power 32.7–42.4% across m ≥ 0, at a cost of ~3 pp at m = 0. Proposed as the decision base; **it is decision #1** (§11) |
| 25 | cl. 4 note, §3 | P1530 was called "the old-regime analog" of the auction price *(Kimi, ChatGPT)* | Renamed **"a synthetic signal-completion price"**; a descriptive variant with s ending at P1525 (so s and R_on share no print) is added (cl. 14). Whether to decide on it or on the VWAP is **decision #4** (§11) |

**Internal quant-verifier pass on v3.1 (2026-10-02) — verdict FAIL, all findings taken:**

| # | v3.1 clause | the defect | the fix |
|--:|---|---|---|
| 27 | 3 | **The name-level basis-step drop partly selected on the outcome's measurement error.** Of the first 558 drops, ~185 were TRANSIENT (A reverts by t+2), mostly on the three §10j sessions; on such a night A_{t+1} − 1 ≈ the gap between two measurements of the very open R_on ends on, so dropping on it selects on how far the outcome is mis-measured | A step must **persist into t+2**, and (second pass, row 31) A_t must be clean against t−1, to be dropped (187 drops; 188 transient/mirror kept, counted, rerun-without in cl. 14). The §10j sessions are excluded **whole**, both adjoining pairs, by a dated list: **754 → 748 pairs**; N, the bar and the lag are restated (§6: t 3.5954; lag 10) |
| 28 | 9a | **PR-2 could not run as written.** It imported cl. 3's 75-bar cohort, empty in the auction era; it read `ohlcv_5m` in that era, which ledger A3 forbids (two writers, an off-grid 15:11 bar, the auction print in a 15:25 bar); its basis-step detector is blind on traded-basis data, while `corporate_actions` holds splits/bonuses only; it imported cl. 10–11's N-deflated bar alongside a6's alpha-spending bar, and K4's halves dated inside PR-1's window; a missing post-close capture read as "unfilled" | **§9a rebuilt:** the CNC branch reads `cas_daily.pre_auction_price` (valid when first polled before 15:28) and the daily file only — no 5-minute bar; every ex-date of ANY corporate action is dropped from NSE's calendar as published by t (a stated build prerequisite); the bar is a8 alone; K4 re-dated by the read schedule; a session without a valid capture is excluded and counted |
| 29 | §7 | **Like-for-like and the cost wedge.** The middle-tercile PASS column required t only, the whole-cohort one t and DSR; and the planted edge had no cost wedge, though K2 reads the GROSS outcome and a real net pass needs a gross edge ~4× larger — so the false-kill figures were upper bounds | Both bases now require t, DSR and the K2 clear; a gross ×4 cell less a flat cost is added; b is calibrated against a book-free benchmark |
| 30 | §5, §7, §9, cl. 3 | Small: K6's range and the "3 names" t had moved (final run: 0.0–2.3%, 86.7%); four looks at 2.326 give 2.74%, not 2.8%; the quintile/tercile cuts were undefined; the spread CI used z with 37 clusters and did not state its coverage | Restated; the cuts are ranks after the cl. 3 drops, before any outcome filter, at ⌊n/5⌋, ⌊n/3⌋, ⌊2n/3⌋; CI with t₃₆ and coverage stated |
| 31 | 3, 9a, §7, §8 | **Second quant-verifier pass (FAIL):** a1's guard read `captured_at`, which is the LAST poll time (the cohort would be empty); a6 dropped a name with no 15:05 bar, re-opening v3 row 7's t+1 selection; a2 said "t" where a4 says "t+1"; 89 of the 278 "persistent" drops were mirrors of a day-t outlier, not corporate actions; t+2 could be a special or mismatch session; a5 read `volume_latest` from a capture that may have died early; a6's "never re-backfilled" was uncheckable; the §7 calibration label; "388"; the §10j list had no rule | a1 reads a new `first_polled_at` (built 2026-10-02, migration `9b4d2f7a1c3e`); a6 carries the latest earlier bar and excludes a thin session, from a hashed snapshot; a2 → t+1; the strict rule adds "A_t clean against t−1" (**187** drops, 5 book slots); neighbours skip special and mismatch sessions; a5 requires a last poll ≥ 16:00; §10j is a stated rule (≥ 10 one-day outliers); labels fixed; a beta descriptive line added (cl. 14) |
| 32 | 9a | **Final §9a check (FAIL):** a8 left PR-2 with no runnable rule — cl. 11's kills applied at every read would KILL a genuine edge 11–15% of the time (0.5–1.1% at one read); cl. 11 was deleted without restating PASS/NULL, h or a schedule; K3/K4/K6 were calibrated to n = 748; k_t = 0 undefined; the fill instrument unvalidated (`cas_postclose_daily` = 0 rows); a1's window trusted `last_price` up to 15:28; auction eligibility unchecked; validity per session not per row, with a stale-volume hole; no carry or demeaning rule in a5; the a6 snapshot untimed; the horizon to be planned from PR-1's estimate; `ohlcv_1d` rewrite risk; the label used 5-minute prices | a8 is now a complete sequential rule, **simulated before the freeze**; K3 scaled ⌈0.02·n⌉, K4 on the halves in hand, K6 descriptive; kills only at a crossing or the last read; k_t = 0 excluded; prerequisites 4–6; a1 window [15:15, 15:20); auction evidence in a2; per-row validity; a5 carry + demeaning; a6 15:20 snapshot as a bounded A3 exception; horizon fixed now (a0, a8); hashed evening snapshot; label translated |
| 33 | 9a | **Confirmation pass (PASS-WITH-NOTES):** K2 checked only at the last read gave the same evidence different verdicts by read; size was calibrated on normal noise (skew −0.85 → 1.3%); the "NULL" column counted no-crossings; no calendar cap; no lower bound on the post-close first poll; prereq 4 vs the 10× threshold; a0's "nothing" ignored the branch; the snapshot ÷ daily-file ratio unexplained | K2 at the crossing too; boundary recalibrated on a skewed null (frozen t 7.17 → 2.53; size 0.7–1.1%); column relabelled; cap 2031-12-31 or a CAS design change ⇒ NULL; first poll ∈ [15:35, 15:50); prereq 4 pass/fail only; a0 reworded and KILL → new trial; a6 basis note |

**Re-raised in round 2 and still NOT ADOPTED:** "decide on raw" (no new argument; it stays
decision #1 — 4 of 6 reviewers accept demeaned) · "K3 kills an expiry-concentrated edge"
(measured in §7: it does not) · "decide the overnight branch on the VWAP entry" (its premise
was wrong: a post-close order is placed after the close is set in BOTH regimes; the real
question, which old-regime price stands for the auction price, is decision #4).

## 0. What changed from v2 (v3), and why

Rows 1–2 and 4 would each have decided the result by construction.

| # | v2 clause | the defect (found by) | the v3 fix |
|--:|---|---|---|
| 1 | 2, 5 | **The two price sources are on different bases.** The 5-minute history is **back-adjusted** for later splits, bonuses, demergers, rights and some dividends; the exchange's daily file holds **traded** prices. On **22.5%** of name-days the official open differs from the 09:15 bar's open by more than 2%, and the step lands exactly at corporate-action dates (e.g. 5.0 until a 1:5 split). Any return that divides one source by the other measures that factor, not the market. **v2's intraday outcome did this** (5-minute 15:10 price ÷ daily-file open), and so did the first v3 draft's overnight outcome. *(internal review; re-measured)* | **Every return is computed inside the 5-minute table**, whose adjustment is consistent. Where the two sources share a basis, its **09:15 open equals the official open exactly on 98.7% of name-days**. The daily file is used only for **sizing and fees**, which need the traded price |
| 2 | 5 | **R_on started from the official close.** Before 3 Aug 2026 that close was the 15:00–15:30 VWAP, while s ends at the last trade before 15:30. Under a random walk, E[R_on \| s] ≈ κ·s. Measured on one basis: **κ = 0.71** (p10–p90 0.62–0.79), and the book's built-in drag averages **−64 bps**, against ~35 bps of costs. It pushes toward KILL. *(three reviewers; measured)* | **R_on is measured from the last trade that completes the signal**, the old-regime analog of the auction regime's post-close fill at the auction price. The official-close version and the gap G are reported but never decide |
| 3 | 3 | **The pair calendar silently spanned sessions.** The daily file has 764 sessions, one more than the 5-minute table (the 2024-11-01 muhurat). The 2023-11-12 muhurat is in neither table. Two of v2's "756 pairs" spanned a muhurat session. *(internal review)* | Pairs are consecutive in the **exchange calendar**, with five listed special sessions: **754 pairs** (748 in v3.1, row 28) |
| 4 | 10 | **The session-concentration kill fired on genuine passes.** "> 50% of net P&L from ≤ 5% of sessions": noise alone puts 0.05 + φ(1.645)/SR ≈ **84%** of net P&L in the best 5% of sessions at the bar. It fired on **99%** of genuine passes and quietly raised the bar to **t ≈ 6.3** (§7). v2 also said this kill caught monthly-expiry concentration, yet expiry settlement is one of the three named mechanisms | **K3:** KILL only if removing the best **15 sessions (2%)** leaves the mean net ≤ 0; checked only on a would-be PASS |
| 5 | 8 | **The branch was chosen on the test data**, an extra trial the bar did not count. Choosing on *gross* can pick the branch with the lower *net* (the costs differ by ~20 bps) *(all five reviewers)* | Choose the branch with the **higher Newey–West t of its NET series**; charge PR-1 as **two trials: N = 20 + 2 = 22** |
| 6 | 10 | **K2 used IC(s, R_on) even when the intraday branch decides** *(two)* | K2 uses the **chosen branch's** outcome |
| 7 | 3 | **"All 75 bars on t and on t+1" looks ahead.** Halts and no-trade bars on t+1 go with extreme moves *(two)* | Completeness is required **on t only**. A book name with missing t+1 data is **carried, not dropped**, and counted (cl. 3) |
| 8 | §5 | **Spread legs were inconsistent.** Intraday paid two half-spreads while its entry is the pre-open auction open; delivery paid none at that same open. The bracket was also the whole cohort's, while the bid-ask bounce is bounded by the *book's* half-spread *(three + internal)* | **Every leg in both branches pays one half-spread**, for reasons in §5. The bracket is rebuilt **on the book's own names** by the same construction: **[1.76, 2.68]** bps (cohort [1.74, 2.28]) |
| 9 | 6, §5 | **The notional was implicit.** Costs depend on size, and a name priced above ₹20,000 cannot be bought *(two)* | **₹20,000 per name, whole shares, sized on the traded price** (the official close). qty 0 ⇒ skipped: **2.33%** of slots |
| 10 | §6 | **N and n disagreed** *(two)* | **N = 22; n = 754** everywhere (748 in v3.1) |
| 11 | 9 | **3.575 assumes skew 0 and kurtosis 3.** A liquidity-provision book is plausibly negatively skewed *(one)* | PASS also needs **DSR ≥ 0.95 at the realized skew and kurtosis** (§6) |
| 12 | — | **Four clauses were fixed in the full draft but dropped from the v2 extract:** net = gross − top of the cost interval; NW lag 10; dated halves; "price at 15:10" = the bar stamped 15:05 *(one)* | Every clause is written out in full below |
| 13 | 5, 9 | **Demeaned or raw was ambiguous** *(four)* | The decision uses **demeaned** (relative) returns; **raw is reported**. **NOT ADOPTED: "decide on raw"** — the cohort mean is market beta, which the signal does not produce |
| 14 | — | **Which reversal is it?** A PASS could be generic reversal of the day's move, or the overnight-gap effect already rejected *(two)* | A pre-registered **label** (cl. 13) that the follow-up must inherit. **NOT ADOPTED as a kill:** it asks *which* reversal, not *whether* the signal pays |
| 15 | — | **What a PR-1 outcome means for the auction regime was unstated** *(two)* | Proposed in §9 |

**Considered and NOT ADOPTED, with the measurement:**

- **"The book tilts to wide-spread, low-priced names."** Measured:
  - the median half-spread is **1.76 bps for book slots vs 1.74** for all name-windows;
  - the median traded price is **₹1,161 for book slots vs ₹1,110** for the cohort;
  - the upper spread quantiles are 7–20% wider, and row 8's book-specific bracket prices that.
- **"The names kill (K6) fires on almost every pass."** On the measured slot distribution (top-3
  names = 7.0% of slots) it fired on **0.0–3.1%** of genuine passes (v3.1 re-run: 0.0–2.3%), with or without a flat cost.
  It caught a "3 names carry it, the rest lose" book **100%** of the time (§7). Kept as written.
- **"Add a stricter concentration kill."** The v2 kill was already far too strict (row 4).
- **"Check survivorship on the sealed holdouts."** That would spend the holdouts.
- **"Pick the branch from P1, or split the sample."**
  - Charging the second trial costs 0.02 in t.
  - P1-only would discard the only branch that was executable in the old regime.
  - A split halves the power.
- **"Volatility-scale s."** That changes a signal agreed earlier. The book is not concentrated
  (effective number of names 103.6).
- **"Rescale the 5-minute prices to the traded basis."** A rescale factor needs a same-day
  reference price, and it inherits that price's own mismatches (§10j). Computing every return
  inside one consistently adjusted table needs no factor at all.

## 1. The idea — liquidity provision at the close (unchanged)

Some participants must trade **at the closing price**: passive funds tracking the index,
derivative settlement, and mutual-fund NAV. They pay for immediacy, and whoever takes the other
side is paid when the price pressure reverses. We test whether, on NSE, a stock pushed **down**
into the close (against its peers) rebounds afterwards, by enough to pay retail costs.

**Predictions, stated before any data:**
- **P1:** concentrated overnight (close → next open).
- **P2:** scales with the size of the late move.
- **P3:** larger on high-volume closes.
- **P4:** larger when VIX is high (Nagel, *RFS* 2012).
- **P5:** not the overnight-gap reversal effect, which we already tested and rejected.
- **P6 (new, descriptive):** if derivative settlement is a channel, the effect is larger on
  expiry sessions, and its peak weekday moves from Thursday to Tuesday after 2025-09-01.

**Prior evidence:**
- US closing-auction deviations reverse about 85% by the next morning (Bogousslavsky & Muravyev,
  *J. Financial Markets* 66, 2023).
- Our own 7-session auction sample: ρ = −0.272, day-block 90% CI [−0.478, −0.088]. Half of it came
  from one session, and that data was later lost, so it is a lead, not evidence.

## 2. Market and data facts the design relies on

| fact | source / status |
|---|---|
| Before 3 Aug 2026 the NSE close was the **VWAP of the last 30 minutes** of continuous trading | SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 (16 Jan 2026) §1 |
| Since 3 Aug 2026, F&O stocks close by a **call auction 15:15–15:35** (orders 15:20–15:30, random close 15:28–15:30); one equilibrium price becomes the official close | same circular §4.2; NSE circular NSE/CMTR/73362 |
| A **post-close session trades at the closing price**, market orders only, CNC (delivery) product: 15:50–16:00 now, 15:40–16:00 before the auction | Zerodha support, "pre-market & post-market sessions" (current page re-read 2026-09-30; a 2025-05-30 archive for the old times) |
| The **pre-open session is a call auction** (09:00–09:08 during the window), and its equilibrium price is the official open | standard NSE pre-open rule; not re-verified this round |
| **MIS entry in the pre-open, and a BTST sell in the pre-open, are NOT stated on any primary broker page.** A Zerodha staff reply in the Z-Connect comments (2023) says intraday orders can be placed pre-market; that is secondary | ⇒ every next-open leg is charged a half-spread (§5) |
| MIS positions in auction stocks are squared off at **15:12** | Zerodha support, "What is SEBI's CAS" |
| Stock and Nifty derivatives expire on **Thursday up to 31 Aug 2025, Tuesday from 1 Sep 2025** | NSE circular NSE/FAOP/68747 (25 Jun 2025) |
| **Our 5-minute history is back-adjusted; our daily file is not** (row 1). **"The bases agree"** on a name-day ⇔ \|A − 1\| < 2%, A = official open ÷ 09:15-bar open **[v3.1]** | measured on 153,097 name-days (§8) |

## 3. PR-1 in one paragraph

We use **historical, pre-auction data** as a *mechanism test* for the auction regime. The question:
does a late-session move against peers predict the opposite move afterwards, by enough to pay
retail costs, **if the entry is made at the price that completes the late move**?
- **That is the entry the auction regime provides:** a post-close fill at the auction price.
  In the old regime P1530 is **a synthetic signal-completion price** **[v3.1]**: the print that
  completes s, carrying the late flow at one print, not a price anyone could fill at.
- **The old regime did not provide it:** its post-close fill was at a 30-minute VWAP. So the
  old-regime executable version is reported and never decides.
- **A PASS certifies a pattern at a hypothetical price, not a harvestable premium.** Post-close
  fills may be adversely selected, and no historical data can measure that (§10).
- **If PR-1 passes,** a second study (PR-2) tests the auction regime forward, on sessions not yet
  read.

## 4. The pre-registered design (draft v3 — every clause, in full)

**Notation.** All prices below are taken from the **5-minute table** unless marked otherwise.
Bars are stamped by start time:
- **O_d** = the open of the bar stamped 09:15 on session d, i.e. the official open.
- **P1510_d**, **P1515_d**, **P1530_d** = the closes of the bars stamped 15:05, 15:10 and 15:25,
  i.e. the last trades before 15:10, 15:15 and 15:30.
- **C_d** = the official close, from the exchange's **daily file**, on the traded basis.

| # | clause |
|---|---|
| 1 | **Question** as §3. |
| 2 | **Data.** 5-minute bars (75 a session) for a fixed ~205-name F&O capture set. **Every return in this design is a ratio of two 5-minute-table prices**: that table is consistently back-adjusted, and the exchange's daily file is not (§0 row 1). The daily file supplies only C (for sizing, fees and the descriptive versions) and the session calendar. **Window 2023-07-03 → 2026-07-31**, pinned by date. The last pair is (2026-07-30, 2026-07-31), so **no auction-regime session is read**. Earlier blocks (2019-10 → 2023-07) are sealed holdouts and are not read. |
| 3 | **Calendar and cohort.** The **exchange calendar** is the daily file's sessions plus the 2023-11-12 muhurat session, which is absent from both tables. The five **special sessions** are 2023-11-12, 2024-03-02, 2024-05-18, 2024-11-01 and 2025-10-21 (DR drills and muhurat; exchange-announced). A pair (t, t+1) is used when t+1 is the next exchange session, neither is special, **[v3.1] neither is a source-mismatch session: one on which ≥ 10 names have a one-day basis outlier** (A steps in from the previous session and back out to the next, which agree). The rule yields exactly **2024-02-05 (30 names), 2024-05-14 (18), 2025-01-20 (31)**; no other session has more than 7. Both adjoining pairs go, and t qualifies: **748 pairs**. **The cohort on t** is the names with all 75 bars on t and a daily bar on t (**t only**). A session qualifies with ≥ 150 such names. Drop a name on t if t+1 is its split or bonus ex-date (announced in advance). **[v3.1] Also drop a name on t whose adjustment factor changes overnight — a STRICT basis step:** \|A_{t+1} ÷ A_t − 1\| > 0.3%, **and** \|A_{t+2} ÷ A_{t+1} − 1\| ≤ 0.3% (it stays stepped), **and** \|A_t ÷ A_{t−1} − 1\| ≤ 0.3% (A_t is not itself a one-day outlier). A_d = official open ÷ 09:15-bar open; t−1 and t+2 are the neighbouring sessions that are **neither special nor a mismatch session**; a missing A on t−1 or t+2, or a neighbour outside the window, counts as no evidence of an outlier, so the step is dropped and nothing beyond the window is read. A strict step is a change in the 5-minute table's adjustment factor, i.e. a corporate action. A **transient** step (the t+1 open is a one-day outlier) or a **mirror** (A_t is) is **kept and counted** — dropping on it would select on how far an open is mis-measured, and a mirror night's R_on is clean. A name with no 09:15 bar on t or t+1 cannot be checked and is kept (counted). **Cut points:** the quintile and tercile sets of cl. 5 and 12 are ranks of s over the cohort on t **after these drops and before any outcome-defined filter**, as 0-based half-open rank intervals — bottom quintile [0, ⌊n/5⌋), middle tercile [⌊n/3⌋, ⌊2n/3⌋) — with ties in s broken by ascending symbol, as in cl. 6. Both drops act before ranking, so the name leaves the cohort and the book alike. **A book name with missing t+1 data is carried, not dropped**, and every carried slot is counted: no bar on t+1 at all (suspended) ⇒ R_on = 0 for a CNC slot, and an MIS slot is never entered (cl. 7) **[v3.1]**; no bar stamped 09:15 ⇒ the open of the first bar of t+1; no bar stamped 15:05 ⇒ the close of the latest earlier bar. **Demeaning** uses the cohort names whose outcome is defined; a carried book name enters at its carried raw value minus that mean. |
| 4 | **Signal (unchanged):** **s = (P1530_t − P1515_t) ÷ P1515_t, demeaned** across the session's cohort. |
| 5 | **Outcomes.** **R_on = (O_{t+1} − P1530_t) ÷ P1530_t**: from the last trade, *not* the official close. **R_day = (P1510_{t+1} − O_{t+1}) ÷ O_{t+1}**: before the 15:12 square-off. Both are **demeaned within session**, and **the decision uses the demeaned (relative) return**. **[v3.1] The demeaning base is decision #1 (§11): proposed = the mean of the cohort names in the session's MIDDLE TERCILE of s**, so a response of the names the book never trades leaks far less into the decision series: about a quarter as much as through the whole cohort for a one-sided response, and nothing for a linear one (§7). Against the whole cohort, an up-side-only REVERSAL manufactures a PASS on a zero-edge book (§7); the whole-cohort-demeaned version is then reported. The cohort mean is market beta: the signal does not produce it, and a long-only holder carries it as a separate, unhedged exposure. **Reported, never decisive:** raw returns; the old-regime executable R_on from C_t, computed within the daily file; and **G = P1530_t ÷ C_t − 1**, both on the traded basis. |
| 6 | **Book:** each session, the **5 names with the most negative s** (ties at the fifth place: ascending symbol), long only. **₹20,000 per name; qty = floor(20,000 ÷ C_t)**, on the traded price. A name with qty 0 is skipped and not replaced. The session return is the equal-weight mean over the names bought (k_t of them). |
| 7 | **Costs per slot.** fee_i = the fee model of §5 with qty from cl. 6 and both legs priced at C_t, the traded price, each leg dated on its own day. Pricing each leg at its own traded price instead moves a fee by ≈ 0.1 bps per 1% of price move, typically < 0.2 bps. Add **two half-spreads h** (one per leg), with **h ∈ [1.76, 2.68] bps**. **net_i(h) = R_i − fee_i − 2h**, and the session net is the mean over the names bought. A carried CNC slot pays the full round trip. An MIS slot with no trade on t+1 is never entered: no return, no fee. |
| 8 | **E1 (information, reported for both outcomes):** mean over sessions of Spearman IC(s, outcome) across the cohort, with its t and 90% CI as in cl. 10. |
| 9 | **Branch:** compute both branches' net series at h = 2.68. **The branch with the higher t decides; charged as two trials, N = 22.** The other branch is reported and never promoted. **Delivery (CNC):** outcome R_on. **Intraday (MIS):** outcome R_day. |
| 10 | **Statistics:** t = Newey–West (Bartlett kernel) with **lag 10** = ⌈748^(1/3)⌉. 90% CI = mean ± 1.645·SE. **DSR:** the formula in §6 at the series' **realized** skew and kurtosis, N = 22, n = 748. |
| 11 | **Decision** (chosen branch). **PASS** ⇔ net(h = 2.68) has **t ≥ 3.5954** and **DSR ≥ 0.95**, and no kill fires. (This implies v2's "gross CI lower bound > top of the cost interval".) **KILL** ⇔ K2 fires, **or** the 90% CI upper bound of net(h = 1.76) is below 0, **or** a would-be PASS fails K3, K4 or K6. **NULL** ⇔ anything else: we stop, and do not re-specify. |
| 12 | **Kills.** **K2 [v3.1]:** mean over sessions of IC(s, chosen outcome) **across the cohort names in the bottom quintile of s** (the fifth with the most negative s, which contains the book) ≥ 0. *Robustness kills, checked only on a would-be PASS (they can turn a PASS into a KILL, never a NULL into a KILL):* **K3:** removing the 15 sessions with the largest net leaves the mean net ≤ 0. **K4:** mean net over 2023-07-03 → 2025-01-31 and over 2025-02-01 → 2026-07-31 differ in sign (382 / 366 pairs). **K6:** the 3 names with the largest total net contribution carry > 50% of the total net. A name's contribution is Σ over its slots of net_i ÷ k_t. |
| 13 | **Mechanism label** — reported with the decision, never changes it. Each session, cross-sectional OLS of the chosen outcome on s, **r_pre = (P1515_t − O_t) ÷ O_t** and **gap = (O_t − P1530_{t−1}) ÷ P1530_{t−1}**, all demeaned, with t−1 the previous non-special session. Slopes are averaged over sessions, with the cl.-10 CI. The first session is skipped: its t−1 lies in a sealed block. **close-specific** ⇔ CI(β_s) < 0 **and** CI(β_s − β_pre) < 0. **generic reversal** ⇔ CI(β_s) < 0 only. **none** otherwise. PR-2 must state which label it inherits. |
| 14 | **Descriptive only, never decisive:** E1 for both outcomes · weekday × expiry type (P6) · VIX terciles (P4) · late-volume terciles (P3) · the long-short intraday variant · raw returns · the executable R_on from C_t, and G · a concentration panel (best-5% share; tagged expiry and index-event days) · a balanced-subsample rerun (names present in every session) · a rerun that also drops the transient basis-step name-nights (cl. 3) · counts of carried and skipped slots · **[v3.1]** the whole-cohort IC (v3's K2) · the **other demeaning base** (whole cohort if decision #1 picks the middle tercile, and vice versa) · the CNC branch with **s ending at P1525** (s = (P1525 − P1515) ÷ P1515 and R_on from P1530, so the two share no print) · counts of persistent and transient basis steps. If decision #1 picks raw, both demeaned bases are reported. · The decision series regressed on the overnight (CNC) or same-day (MIS) equal-weight cohort return: middle-tercile demeaning removes a beta of 1, not the book's beta relative to the middle tercile, and the book is high-beta mid-caps. |
| 15 | **Order:** this text is committed → the code is written → the code is reviewed → it runs **once** → the report is written. |

## 5. Costs — please recompute

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
  - stamp 0.003% on the buy;
  - exchange, SEBI and GST as for delivery;
  - no depository charge.

**Each leg's total is rounded half-up to the paisa** before the legs are added, so a hand
calculation can differ by ₹0.01. At price ₹500, entry = exit:

| round trip | ours |
|---|---|
| delivery, 40 shares (₹20,000) | ₹59.78 = **29.89 bps** |
| delivery, 66 shares (₹33,000) | ₹88.69 = **26.88 bps** |
| intraday, 40 shares | ₹21.20 = **10.60 bps** |
| intraday, 100 shares | ₹53.02 = **10.60 bps** |

**Per trade in the real book.** At ₹20,000 per name with whole shares on traded prices, delivery
fees come to: median **30.07**, mean **30.41**, p90 31.14, max 37.53 bps (§8). ₹500 × 40 = exactly
₹20,000 is the floor: whole-share rounding leaves most slots slightly below ₹20,000, so the flat DP
charge weighs more.

**Spread.** An Abdi–Ranaldo estimator on 5-minute bars, 2023-07-03 → 2026-08-20, 6,748
name-windows of 21 sessions on the same capture set:
- **the whole cohort:** median **1.74 bps**, 90% CI [1.58, 1.93]. Windows below the estimator's
  resolution read 0, so 1.74 is a lower bound; without them the median is **2.28**.
- **the book's own slots, by the same construction:** **[1.76, 2.68]**. The decision uses this
  bracket (h = 2.68 for PASS, h = 1.76 for the cost KILL), because the bid-ask bounce is bounded
  by the *book's* half-spread, not the cohort's.
- **[v3.1] the book's MEAN half-spread** (the bounce cost is a mean): **2.17 bps**, window-cluster
  90% CI **[1.88, 2.47]** (CR1, t with 36 df) over 37 windows, clamped windows counted as 0. The
  top 2.68 lies above the CI's upper bound, so it is conservative for the mean too. Under the
  v3.1 cohort the book's own bracket top measures **2.67**; **h = 2.68 is retained** (the larger,
  so the conservative one). ⚠ Coverage: **2,882 of the 3,740** book slots have a spread window;
  the 858 without one may be the less liquid, so the mean is measured on the slots that can be.

**Every leg pays one half-spread, in both branches:**
- **The CNC entry reference P1530 is a continuous-market print, and the book is selected ON that
  print.** Selection enriches bid-side prints, so bid-ask bounce flatters by up to one half-spread.
- **The next-open leg** (the CNC exit, the MIS entry) is a pre-open auction fill only if the broker
  accepts that order there. That is not verified from a primary page (§2).
- **The MIS exit at 15:10** is in continuous trading.

**Hence the intervals:**
- **delivery ≈ 30.41 + 2 × [1.76, 2.68] = [33.93, 35.77] bps** at the mean per-trade fee
  ([33.41, 35.25] at the ₹500 × 40 floor);
- **intraday 10.60 + 2 × [1.76, 2.68] = [14.12, 15.96] bps**.

## 6. The statistical bar — please recompute

N = 20 prior strategy trials in this programme (pinned to the agreement ledger, `nemotron_review.md`
row A3: "N = 20 for the programme, +1 per pre-registered estimand" **[v3.1]**) + 2 for PR-1's
two candidate branches = **N = 22**;
n = **748** **[v3.1]** (754 in v3). A Deflated Sharpe ratio of 95% (Bailey & López de Prado):

- E[max SR] = σ_SR · ((1 − γ) Φ⁻¹(1 − 1/N) + γ Φ⁻¹(1 − 1/(N e))), with γ = 0.5772 and
  σ_SR = 1/√n.
- PSR = Φ( (SR − SR\*) √(n − 1) / √(1 − skew · SR + (kurt − 1)/4 · SR²) ), where kurtosis is
  Pearson (normal = 3).

Ours, at skew 0 and kurtosis 3:
- σ_SR = 0.036564;
- Φ⁻¹(1 − 1/22) = 1.69062;
- Φ⁻¹(1 − 1/(22e)) = 2.12672;
- **E[max SR] = 0.071019** (≈ 1.13 annualised: the Sharpe that the best of 22 zero-edge trials
  shows by luck);
- the smallest per-session Sharpe with PSR ≥ 0.95 is **0.131461**, so **t = 3.5954**, and
  annualised ≈ 2.09.
- At other moments the bar moves: skew −0.5, kurtosis 6 → **t 3.660** · skew −1, kurtosis 10 →
  **3.729** · skew +0.5, kurtosis 6 → 3.552 · skew 0, kurtosis 11.46 → 3.626.
- **Sensitivity to N:** N = 30 → t 3.727 · N = 44 → 3.881 · N = 60 → 4.000. N = 20 is the
  ledger's count, and it may undercount.
- The trials overlap in data, which makes the effective count smaller. On that count the bar is
  conservative.

## 7. Operating characteristics of the decision rule — synthetic, no market data

**Set-up:**
- Net series of n = 748 with a planted true t; 20,000 runs per cell; seeded; code in Appendix B.
- Noise: normal · t₄ · t₃ · skew-normal (skew ≈ −0.85).
- v2 = its t, its K3 and K4. v3 = cl. 11–12 (t, DSR, K3, K4).
- K6 is run separately, on the **measured** book slot distribution. **[v3.1]** K2 runs on a
  cross-section model; the two-branch max and expiry-concentrated edges are added; K4 uses the
  **dated halves (382 / 366)**.
- Reproduce: `cd backend && uv run python scripts/pr1_decision_oc.py --sims 20000` (seed 42;
  the vectorised t and DSR are asserted equal to the house functions before anything prints).

| noise | true t | PASS v2 | PASS v3.1 | v2's K3 fires when t ≥ bar |
|---|--:|--:|--:|--:|
| normal | 0.0 | 0.0% | 0.0% | — |
| normal | 2.0 | 0.0% | 5.1% | 100% |
| normal | 3.6 | **0.3%** | **47.5%** | 99.4% |
| normal | 5.0 | 10.1% | 90.5% | 89.0% |
| t₄ | 3.6 | 0.0% | 47.8% | 100% |
| t₃ | 3.6 | 0.0% | 50.5% | 100% |
| t₃ | 5.0 | 2.4% | 87.7% | 97.4% |
| skew −0.85 | 3.6 | 17.0% | 45.2% | 67.6% |
| skew −0.85 | 5.0 | 64.2% | 88.2% | 29.5% |

(Re-run at n = 748 with the dated K4 halves; v3's figures at n = 754 differed by ≤ 1 pp.)

**Reading the table:**
- A rule should pass about half the time at a true t equal to its own bar. v3 does (45–51%); v2
  did not (0–18%).
- Closed form: at the bar the best 5% of sessions carry 0.05 + φ(1.645)/SR = **83.5%** of net P&L.
  That share falls to 50% only at t ≈ **6.27**.
- The v3 kills K3 and K4 almost never fire on a would-be pass in these iid cells. K4 targets
  regime change, which iid noise does not contain.

**What the robustness kills catch, on the measured slot distribution:**
- **K6 (names):** a name's volatility rises with its slot count (exponent 0.256 measured; 0.5 as a
  stress), and a flat cost eats 0% or 80% of the gross. On genuine broad edges at t 3.6 and 5.0,
  **K6 fires on 0.0–2.3%** of passes. When 3 names carry the whole edge and the rest lose, the t
  passes in 86.7% of runs, and **K6 fires on 100% of those**.
- **K3 (sessions):** when 15 random sessions carry the whole edge, the t itself passes only 12.2%
  (3.3% if ordinary days lose 0.04 sd), and K3 fires on ≤ 0.2% of those that pass. Outlier
  sessions inflate the variance, so the t does this work, and K3 is a backstop that seldom binds.
  We keep it because it costs < 1 pp of power, not because it has power.

**[v3.1] K3 on an expiry-concentrated edge** (overall true t 3.6, evenly spaced sessions; the
round-2 claim that K3 kills the expiry mechanism, P6):

| edge carried by | ordinary-day mean | t ≥ bar | K3 fires on those |
|---|--:|--:|--:|
| 36 expiry sessions | 0 / −0.02 / −0.04 sd | 40.2% / 35.5% / 31.0% | **0.0%** in each |
| 150 expiry sessions | 0 / −0.02 / −0.04 sd | 51.2% / 46.6% / 42.4% | **0.0%** in each |

**[v3.1] The two-branch maximum** (cl. 9; independent net series, the higher NW t decides, N = 22):

| true t (CNC, MIS) | PASS | the stronger branch decides, given PASS |
|---|--:|--:|
| (0, 0) | **0.02%** | — |
| (2, 2) | 9.4% | — |
| (3.6, 0) | 48.0% | 100.0% |
| (3.6, 2) | 49.7% | 93.6% |
| (3.6, 3.6) | 71.6% | — |

The double null stays far below 5%, so charging the branch choice as one extra trial is enough.

**[v3.1] K2 and the demeaning base, on a cross-section** (2,000 runs per cell). Each session:
204 names, s ~ N(0, 1), R = ε + m·max(s, 0) + w·b·[book], ε ~ N(0, 1); the book is the 5 lowest s.
b gives the book's NET return a true t of 3.6 against a noise-free benchmark (≈ 3.56 against a
199-name book-free one, ≈ 3.47 against the middle tercile — which is the ~3 pp gap below); w is a cost wedge
(gross edge w·b, flat cost (w − 1)·b — K2 reads the gross outcome). m is a response of late
UP-movers, the side the book never trades: m > 0 continuation, m < 0 reversal of the up side
only. **PASS** = net t ≥ bar, DSR ≥ 0.95 and the bottom-quintile K2 clear, under each demeaning
base (the K2 IC ignores the demeaning constant, so it is the same K2 under both). The K2 columns
give how often each variant fires on a middle-tercile t-and-DSR pass (on a no-edge row: on all
runs, where a kill should fire about half the time).

| book | m | PASS, whole-cohort base | **PASS, middle-tercile base** | K2 whole cohort | K2 lower half | **K2 bottom quintile** |
|---|--:|--:|--:|--:|--:|--:|
| no edge | 0 | 0.0% | 0.0% | 50.4% | 50.9% | 51.5% |
| no edge | −0.10 | **9.3%** | **0.1%** | 0.0% | 48.1% | 50.7% |
| no edge | −0.15 | **35.5%** | **0.2%** | 0.0% | 44.0% | 50.2% |
| net t 3.6 | 0 | 45.5% | 42.4% | 14.1% | 2.9% | **0.5%** |
| net t 3.6 | +0.02 | 27.8% | 38.2% | 99.2% | 3.4% | **0.4%** |
| net t 3.6 | +0.04 | 13.6% | 32.7% | 100% | 2.3% | **0.3%** |
| net t 3.6 | −0.10 | 96.0% | 67.2% | 0.0% | 5.1% | **1.3%** |
| net t 3.6, gross ×4 less a flat cost | 0 | 36.2% | 43.1% | 0.0% | 0.0% | 0.0% |
| net t 3.6, gross ×4 less a flat cost | +0.02 | 17.9% | 35.8% | 41.5% | 0.0% | 0.0% |

- **The whole-cohort base fails on SIZE, not only power.** When late up-movers revert (m < 0),
  the cohort mean falls, the demeaned book rises, and a **zero-edge book PASSES 9.3% (m −0.10)
  to 35.5% (m −0.15) of the time — after K2**, which cannot help: its IC lives in the bottom
  quintile, where the up side is absent. The middle tercile holds the false PASS to ≤ 0.2%.
- **On power, the middle tercile costs ~3 pp at m = 0** (a 68-name benchmark is noisier: 42.4% vs
  45.5%) and **wins whenever the up side moves** (32.7% vs 13.6% at m +0.04). It is not leak-free:
  for a one-sided response it leaks about a quarter as much as the whole cohort (67.2% at m −0.10
  against a nominal ~42%).
- **With a realistic cost wedge** the whole-cohort base also pays the book's own gross edge inside
  its benchmark (36.2% vs 43.1% at m = 0).
- **K2:** v3's whole-cohort IC false-kills 14% of genuine passes at m = 0 and ~100% at m +0.02; with
  a cost wedge that falls to 0% / 41.5%, so the zero-wedge rows are upper bounds. The **bottom
  quintile fires on 0.0–1.3% of genuine passes in every cell** and ~50% under the null.
- The figures differ from round 2's scratch model (not kept). The committed model is the
  reference: `backend/scripts/pr1_decision_oc.py`, output reproduced by the command above.

## 8. Design-level facts — SESSION-t data, plus outcome-free basis ratios on t−1, t+1, t+2 (no return read)

Re-run 2026-10-02 under the v3.1 cohort rule (`backend/scripts/pr1_design_facts.py`, window
pinned 2023-07-03 → 2026-07-31). Figures that moved from v3 are marked.

- **Calendar:** the 5-minute table has 763 sessions and the daily file 764 (+ the 2024-11-01
  muhurat). 760 sessions have ≥ 150 complete names (per session: min 191, median 204, max 209).
  That gives 754 pairs, and **748** once the three §10j sessions are excluded **[v3.1]**; a
  5-minute-only calendar gives 756.
- **Price basis:** on 153,097 name-days, the official open ÷ the 09:15 bar's open is more than 2%
  away from 1 on **22.5%**. Where the bases agree, the two are exactly equal on **98.7%**. The 809
  name-days at 0.3–2% are dividend-adjustment offsets and one-day source mismatches **[v3.1 label]**:
  **167 one-day basis outliers on 37 sessions**; 79 on the three mismatch sessions (30 / 18 / 31
  names), the rest at most 7 per session (a cluster 2023-12-21 → 2024-02-21, 7 on 2024-02-02).
- **Basis steps overnight [v3.1]:** **187** STRICT steps dropped (cl. 3), **5** of them v3 book
  slots; **188** transient or mirror steps kept and counted; **9** cohort name-nights cannot be
  checked (no 09:15 bar on one side) and are kept. (A first, looser rule dropped 558, then 278.)
- **K4's dated halves [v3.1]:** **382** pairs with t before 2025-02-01, **366** after.
- **Book:**
  - 3,740 slots over the 748 pairs;
  - **206 distinct names**;
  - the top 1 / 3 / 10 / 20 names hold 2.4% / **7.0%** / 18.8% / 32.4% of slots;
  - **effective number of names (1/HHI) = 103.6**;
  - the most frequent names are high-beta mid-caps.
- **The book's demeaned late move s:** median **−77 bps** (p10 −139, p90 −53).
- **The same-session gap G = P1530 ÷ C_t − 1** (one basis): κ median 0.71; the book's demeaned G
  averages **−64 bps**. This is the drag that v2's outcome base carried.
- **Traded price:** book median ₹1,160 (p90 ₹5,590, max ₹49,440); cohort median ₹1,109. **87 slots
  (2.33%)** are priced above ₹20,000.
- **Delivery fee** at ₹20,000 per name, whole shares, traded prices: median 30.07, mean 30.41, p90
  31.14, max 37.53 bps.
- **Half-spread of book slots vs all name-windows** (unconditional quantiles; both lie above
  their clamp shares of 33.0% and 28.6%):

  | | q50 | q70 | q90 | median of non-clamped |
  |---|--:|--:|--:|--:|
  | book slots | 1.76 | 2.87 | 4.45 | **2.68** |
  | all name-windows | 1.74 | 2.52 | 3.71 | 2.28 |

  **[v3.1] Book-slot MEAN:** 2.17 bps, window-cluster 90% CI [1.88, 2.47] (37 windows, t with 36 df;
  clamped as 0; 2,882 of 3,740 slots covered). The book's bracket top re-measures 2.67 (h = 2.68
  kept).

## 9. What each outcome means for the follow-up — PROPOSED; the author decides before the freeze

- **PASS** → PR-2 is pre-registered and committed before any auction-regime outcome is read:
  same branch, and the book rule as translated in **§9a** (committed with this text).
  - **Sessions:** its sessions start **after 2026-09-29 and after its own commit date**. Earlier
    August–September sessions were partly read: a spread study used 5-minute bars to 2026-08-20,
    and an earlier auction study read 7 sessions' outcomes. They are excluded.
  - **Bar:** a **single-test bar with an alpha-spending boundary** (e.g. O'Brien–Fleming, overall
    one-sided α = 1%) over a pre-registered read schedule. That controls repeated looks: four naive
    looks at t ≥ 2.33 would give 2.74%, not 1%.
  - **Why not the full deflation again:** the current agreement demands a second N-deflated t ≥
    3.575. At a true annual Sharpe of 2 that needs **~3.2 years** of forward sessions to reach it
    even half the time.
  - **[v3.1] Power, stated as power:** a one-sided 1% single-test bar is reached with **50%**
    power after ((2.326 ÷ SR)²) ≈ **1.35 y** at SR 2, and with **80%** power after
    ((2.326 + 0.842) ÷ SR)² ≈ **2.51 y** at SR 2 and **4.46 y** at SR 1.5. A PR-1 PASS is a
    selected result, so its point estimate is biased up (winner's curse). **The horizon is
    therefore fixed NOW (§9a a8: 8 reads × 126 sessions), never planned from PR-1's estimate**;
    its simulated power is in §9a.
  - **[v3.1] PR-2 decides on a pre-registered FILL rule** from the post-close capture
    (`cas_postclose_daily`, first capture day 2026-10-05): a slot counts as filled only if the
    post-close session traded enough volume at the close to absorb it. The rule is part of §9a.
- **NULL** → PR-1 stops and nothing is re-specified. PR-2 may still run under its own
  pre-registration, counted as a new trial.
- **KILL** → the old-regime claim is refuted. Whether it also ends the auction thread is the
  author's call; a PR-2 run after a PR-1 KILL is counted as a **new trial**, as after a NULL. The old close spread the forced flow over 30 minutes, while the auction
  concentrates it in one print. So a PR-1 KILL is weaker evidence against the auction effect than
  against the old one.

## 9a. PR-2's translation to the auction regime — committed WITH this text [v3.1]

**Why now:** in the auction era the continuous market ends at 15:15. On 2026-08-10 the bars
stamped 15:15–15:25 exist for 3 of 209 names, so P1530 is undefined and cl. 3's "all 75 bars"
cohort is empty. And the ledger (`nemotron_review.md` A3) records that auction-era 5-minute bars
are inconsistent: written by two writers (the live aggregator on the traded basis, the backfill
on the adjusted one), with the auction print in a 15:25 bar on some days and an off-grid 15:11
bar on 2026-09-22 — *"Any CAS-era estimand must read `cas_daily`, not `ohlcv_5m`."* If the
translation were written after PR-1's result, the result could shape it.

**⇒ The CNC branch reads no 5-minute bar.** Every price comes from `cas_daily` (the auction
capture, polled live from the exchange quote) or the exchange's daily file, both on the traded
basis.

| # | clause (auction era) |
|---|---|
| a0 | **Sessions.** PR-2 reads only sessions **after 2026-09-29 and after the commit that freezes this pre-registration** (PR-1 + this §9a together). Beyond the branch fixed by PR-1's cl. 9 (which also decides whether a6 applies), nothing PR-1 produces can move any clause below. **Cap:** if read 8 is not reached by **2031-12-31**, or SEBI changes the closing-auction design for these stocks before it, PR-2 ends **NULL** at that point. |
| a1 | **Prices.** P_pre,t = `cas_daily.pre_auction_price`, the last traded price at the first poll inside the auction window, frozen on insert. Category-I stocks print no continuous trade after 15:15; auction order entry opens at 15:20, closes at random between 15:28 and 15:30, and matching runs 15:30–15:35. **Valid only if `cas_daily.first_polled_at` ∈ [15:15:00, 15:20:00) IST** — before order entry opens, so no indicative or auction value can stand in for the last trade (this is stricter than "before 15:28": it costs only uptime and reads no outcome). Otherwise the name is out of the cohort (counted). `first_polled_at` was added 2026-10-02 (migration `9b4d2f7a1c3e`) because `captured_at` is rewritten on every poll; rows from before it are NULL ⇒ invalid. C_t = the official close in the daily file (not `cas_daily.official_close`, which can be a pre-match value at a 15:33 last poll). Open_t, Open_{t+1} = the official opens in the daily file. |
| a2 | **Cohort on t:** the names with a valid P_pre,t, a daily bar carrying C_t, **evidence that the name was in the auction on t** (non-null `reference_price`, `indicative_close` > 0 and a non-zero `total_imbalance_qty` on the row — met by 210 of 210 names on every session 09-15 → 09-29), and **t+1 not an ex-date for them** (a4). A name whose close fell back to a non-auction price (no price discovered) fails the evidence test when detectable, and is counted. A session qualifies with ≥ 150 names. Pairs are consecutive in the exchange calendar; special sessions are excluded as in cl. 3. Quintile/tercile cuts as in cl. 3. |
| a3 | **Signal:** s = (C_t − P_pre,t) ÷ P_pre,t, demeaned across the cohort (cl. 4). One basis (traded), one session. |
| a4 | **Corporate actions.** The A-ratio detector of cl. 3 sees nothing here (both sources are traded-basis), so **every name-night whose t+1 is an ex-date of ANY corporate action** (split, bonus, dividend, demerger, rights, …) **is dropped before ranking**, using NSE's corporate-action calendar **as published by the close of t** (ex-dates are announced in advance; prerequisite 2). |
| a5 | **CNC outcome:** R_on = (Open_{t+1} − C_t) ÷ C_t, both from the daily file, **demeaned per cl. 5 on the decision-#1 base**, over the cohort names with a defined outcome. A book name with no daily bar on t+1 (suspended) is **carried at R_on = 0 and counted** (cl. 3). The entry is the post-close fill at C_t. **Fill rule:** a slot is filled only if its name's post-close volume (`cas_postclose_daily.volume_latest − volume_after_auction`) is at least **10×** its quantity. **Validity is per name-night:** the row must be first polled in [15:35:00, 15:50:00) IST (after the auction match, so no auction volume enters the difference; before the post-close session opens), and its volume must have been observed at or after 16:00:00 IST (prerequisite 5) — an invalid row is **excluded and counted, never read as "unfilled"**. A session with **k_t = 0** filled slots is excluded from the decision series and counted. The 10× is a proposal; decision #3 sets it. |
| a6 | **MIS outcome** (only if PR-1 chooses MIS): R_day = (P1510_{t+1} − Open_{t+1}) ÷ Open_{t+1}, demeaned as a5. P1510 = the close of the complete (`is_complete`) 5-minute bar stamped 15:05 in a **snapshot taken at 15:20 IST on t+1 by a scheduled task, stored with its timestamp and a hash** (prerequisite 3). This is a stated, bounded **exception to ledger A3**: only bars ≤ 15:10, which precede the auction-era inconsistency, and only as frozen at 15:20 — the snapshot freezes same-session (traded-basis) state; it cannot prove the writer (`ohlcv_5m` has no provenance column), and a later gap-fill or an adjusted backfill cannot reach it. Off-grid bars are ignored. R_day divides a snapshot (5-minute) price by the daily-file open — the house rule forbids mixing the two tables inside a return, and it is safe HERE only because both are same-session traded prices: no later corporate action can back-adjust the snapshot (frozen at 15:20 on t+1), and a4 drops every t+1 ex-date. A name with snapshot bars but none stamped 15:05 takes **the close of the latest earlier bar** (cl. 3's carry rule); a name that traded on t+1 (daily bar) but has **no snapshot bar at all** is excluded and counted. A session whose snapshot is missing, late, or covers < 90% of the cohort is **excluded and counted**. |
| a7 | **Book, sizing, costs, branch:** cl. 6, 7 and 9 (the branch is PR-1's chosen branch; it is not re-chosen). **Mechanism label** (cl. 13), translated: r_pre = (P_pre,t − Open_t) ÷ Open_t and gap = (Open_t − C_{t−1}) ÷ C_{t−1}, from `cas_daily` and the daily file; PR-2 inherits PR-1's label definitions and reports its own. |
| a8 | **The decision rule (replaces cl. 10–12 for PR-2; decision #3 may change any number here, before the freeze):** reads after every **126** decision-series sessions, at most **8** reads (1,008 sessions ≈ 4 years) — **fixed now, not planned from PR-1's estimate**. At read l with n_l sessions: NW t with lag ⌈n_l^(1/3)⌉ of net(h = 2.68). **Boundary** c·√(1008 ÷ n_l), c set so that P(any crossing) = 1% one-sided under the null (O'Brien–Fleming shape). c is calibrated on a **negatively skewed** null (skew ≈ −0.85), the realistic shape for a liquidity-provision book. **Frozen values** (20,000 null paths, seed 2042): **t ≥ 7.17 · 5.07 · 4.14 · 3.58 · 3.21 · 2.93 · 2.71 · 2.53** at n = 126 … 1,008. Size at these values: 0.73% (normal) · 0.71% (t₃) · 1.03% (skew −0.85). A re-draw moves the values by up to ~0.13; the frozen numbers, not a re-draw, decide. **PASS** = the first crossing, provided **K2, K3 and K4 do not fire at that read** (K2 = bottom-quintile IC ≥ 0, as in PR-1; checked once at the crossing it costs 0.0–1.3% of power, §7): K3 = mean net ≤ 0 after removing the best ⌈0.02·n_l⌉ sessions; K4 = the two halves of the sessions in hand differ in sign. **KILL** = K2, K3 or K4 firing at a crossing, **or, at the LAST read only** (no crossing), K2 or the 90% CI upper bound of net(h = 1.76) below 0. **Interim reads without a crossing can only continue** — a kill evaluated at every read would KILL a genuine edge 11–15% of the time (quant-verifier, 2026-10-02). **NULL** = no crossing by the last read and no final-read KILL. **K6 is descriptive in PR-2** (proposed): PR-1 tests name concentration at n = 748; at PR-2's n it would kill 7–16% of genuine crossings in the high-cost cell (below). DSR is not re-applied (§9). |

**Operating characteristics of a8, simulated before the freeze** (`pr1_decision_oc.py`, the PR-2
section; slots drawn from the measured book distribution; "annual Sharpe" of the net session
series):

Reproduce: `cd backend && uv run python scripts/pr1_decision_oc.py --only pr2 --sims 20000` (seed
2042; 2,000 paths per cell). K2 and the cost-KILL are not simulated here (they need the
cross-section; §7 calibrates them), so "no crossing" is NULL or a final-read KILL.

**High-cost cell** (vol ∝ slot count^0.5, a flat cost eating 80% of gross — the realistic case
for a ~35 bps delivery round trip):

| annual Sharpe (net) | PASS, K6 descriptive (a8) | PASS if K6 were a kill | median read of the PASS (sessions) | K3 / K4 / K6 fire on a crossing | no crossing |
|--:|--:|--:|--:|--:|--:|
| 0 | **1.1%** | 1.1% | 1,008 | 0.0 / 0.0 / 0.0% | 99.0% |
| 1.0 | 31.8% | 26.8% | 882 | 0.0 / 0.2 / 15.9% | 68.2% |
| 1.5 | 68.7% | 58.7% | 756 | 0.0 / 0.1 / 14.5% | 31.2% |
| 2.0 | **93.1%** | 78.8% | 630 | 0.0 / 0.2 / 15.4% | 6.7% |
| 3.0 | 100.0% | 92.6% | 504 | 0.0 / 0.0 / 7.4% | 0.0% |

**Mild cell** (vol ∝ count^0.256, no cost): 0.8% on the null · 29.8% / 68.0% / 93.6% / 100% at
Sharpe 1 / 1.5 / 2 / 3; K6 fires on ≤ 0.3% of genuine crossings there, so it matters only when
costs eat most of the gross.

- **Size holds across shapes:** 0.7–1.1% (normal, t₃, skew −0.85, and the slot structure),
  against a 1% design.
- **K3 and K4 almost never fire on a genuine edge** at a crossing (≤ 0.2%); K6 fires on 7–16% of
  genuine crossings in the high-cost cell — the reason it is descriptive here (a8).
- At a true Sharpe of 2 the rule decides at a median of **630 sessions (≈ 2.5 years)**; at 1.5 it
  needs ≈ 3 years and passes ~69% of the time. These horizons are why a8's schedule is fixed now.

**Build prerequisites — PR-2 cannot read a session until each exists:**
1. ✅ **BUILT 2026-10-02:** `cas_daily.first_polled_at`, frozen on insert at the quote-arrival
   instant. Migration `9b4d2f7a1c3e` is applied to dev; the capture task picks it up at the next
   `make worker` start, so the first stamped session is 2026-10-05 at the earliest.
2. NSE's corporate-action calendar (all action types), archived as published by each t (a4).
3. The 15:20-IST snapshot task for the 09:15–15:10 bars, with timestamp and hash (a6, MIS only),
   and an evening snapshot (after EOD ingest) of each session's `cas_daily` rows, daily bars for t
   and t+1, and `cas_postclose_daily` rows, also hashed — so a later rewrite of `ohlcv_1d` (for
   example a corporate-action adjustment) cannot change a ratio already in the series.
4. **A validation of the fill instrument, outcome-free, before the 10× threshold is frozen:** on
   ≥ 10 sessions, `volume_latest − volume_after_auction > 0` for at least half the cohort. It is
   **pass/fail only and cannot change the 10× threshold** (those sessions precede a0's start anyway). If it
   fails, Kite's quote volume does not see post-close trades, the CNC fill rule is undefined, and
   PR-2's CNC branch does not run (a re-specification is a new trial).
5. `cas_postclose_daily.volume_latest_at`, stamped only when a poll returned a non-null volume —
   `captured_at` advances even when the volume is NULL (it is COALESCEd), so today a row can "see
   the whole session" with a stale volume. Needs a migration (author's approval).
6. Reporting: every excluded session (a5, a6) is listed with that day's equal-weight daily-file
   cohort return, so a feed outage that clusters on stress days stays visible.

## 10. Known weaknesses — disclosed; please go beyond them

- **(a) The CNC entry is hypothetical in the old regime** (§3). The old-regime executable version
  is reported.
- **(b) Post-close fills may be adversely selected**: a holder expecting the bounce won't sell at
  the close.
  - The counterfactual (orders that would not have filled) leaves no trace in any historical
    data. So **no historical study can size this discount**, and a PASS is an upper bound.
  - A forward capture of post-close volume and pending quantity is built; its first capture day
    is **2026-10-05** (2026-10-01 was lost to a worker outage, 10-02 was a holiday).
- **(c) Corporate actions are mostly neutralised, and [v3.1] a night whose adjustment factor steps
  is dropped outright (cl. 3)**, so a demerger factor that is a tax ratio cannot enter a return. Returns come from the back-adjusted table,
  which removes split, bonus, demerger and rights jumps, and some dividends. For example, one
  bank's ~3% dividends are adjusted, while a large IT name's dividends are not. Dividends the
  adjustment skips still depress R_on slightly, so the bias is **conservative**, estimated at
  < 0.5 bps.
- **(d) The ~205-name set is fixed, not point-in-time.** Names that left F&O are absent, which
  plausibly **flatters** a long loser-reversal book. A balanced-subsample rerun is reported.
- **(e) One ≈2025 fee schedule is applied to 2023–2026.** The exchange charge was slightly higher
  before Oct 2024; the effect is < 0.1 bps (exact figure unsure).
- **(f) Pre-open eligibility is unverified** for MIS entries and BTST sells (§2), so every
  next-open leg is charged a half-spread.
- **(g) The spread is a daily-average estimate.** Half-spreads at 15:29 and at the open are
  unmeasured, which is why the bracket is the book's own and the decision uses its top.
- **(h) The mechanism label is the only attribution test.** A PASS licenses "late-session
  relative pressure reverses", not "because of liquidity provision".
- **(i) A PR-1 NULL or KILL may reflect dilution**: the old close spread the forced flow over 30
  minutes (§9).
- **(j) On three sessions (2024-02-05, 2024-05-14, 2025-01-20), 13–26 names each have a 09:15-bar
  open 0.3–2% away from the official open**, reverting the next session — a one-day source
  mismatch, not a basis step. **[v3.1] Those sessions are excluded whole (cl. 3: 754 → 748 pairs)**
  by a stated rule (≥ 10 one-day basis outliers), which reproduces the list exactly. ⚠ The rule was
  written after the counts were seen; it reads basis ratios only, never a return, and the
  separation is wide (18–31 names against at most 7 elsewhere). The smaller one-day outliers —
  a Dec-2023 → Feb-2024 cluster, at most 7 names a session — stay in, and the transient/mirror
  rerun (cl. 14) shows their effect.
- **(k) The adjustment is one snapshot.**
  - The basis step lands exactly on 44 split/bonus ex-dates.
  - cl. 3 drops every name on the night before its split/bonus ex-date regardless, so an event the
    snapshot missed cannot enter R_on.
  - A corporate action after the window rescales the whole window by a constant, which leaves
    every return unchanged.

## Appendix B — the §7 simulation (numpy; swap the noise line for t₃ or skewed noise)

It reproduces §7's session table within Monte Carlo error; its random stream differs from our
script's. The K2, branch and expiry cells are in `backend/scripts/pr1_decision_oc.py`.

```python
import math, numpy as np
from statistics import NormalDist
Z, n, rng, G = NormalDist(), 748, np.random.default_rng(42), 0.5772156649
def emax(N): return ((1-G)*Z.inv_cdf(1-1/N) + G*Z.inv_cdf(1-1/(N*math.e))) / math.sqrt(n)
def nw_t(x, L=10):
    d = x - x.mean(1, keepdims=True); v = (d*d).mean(1)
    for l in range(1, L+1): v = v + 2*(1-l/(L+1))*(d[:, l:]*d[:, :-l]).sum(1)/n
    return x.mean(1) / np.sqrt(v/n)
def dsr(x, N=22):
    c = x - x.mean(1, keepdims=True); p = x.std(1); sr = x.mean(1)/x.std(1, ddof=1)
    sk, ku = (c**3).mean(1)/p**3, (c**4).mean(1)/p**4
    z = (sr - emax(N))*math.sqrt(n-1)/np.sqrt(1 - sk*sr + (ku-1)/4*sr*sr)
    return np.array([Z.cdf(v) for v in z])
for tt in (0, 2, 3.6, 5):
    x = rng.standard_normal((20000, n)) + tt/math.sqrt(n)
    t, best, tot = nw_t(x), -np.sort(-x, 1), x.sum(1)
    k4 = np.sign(x[:, :382].mean(1)) != np.sign(x[:, 382:].mean(1))  # dated halves
    v2 = (t >= 3.5749) & ~((tot <= 0) | (best[:, :38].sum(1) > .5*tot)) & ~k4
    v3 = (t >= 3.5954) & (dsr(x) >= .95) & ~((tot - best[:, :15].sum(1)) <= 0) & ~k4
    print(tt, f"PASS v2 {v2.mean():.1%}  PASS v3 {v3.mean():.1%}")
```

## 11. The author's four decisions — open; each must be taken before the freeze

| # | decision | options | recommendation, and why |
|--:|---|---|---|
| 1 | The **decision series** (cl. 5): demeaned against which base, or raw | middle tercile · whole cohort · raw | **Demeaned against the middle tercile.** The cohort mean is market beta, which the signal does not produce (4 of 6 round-2 reviewers accept demeaning). The whole-cohort base fails on SIZE: if late up-movers revert, a zero-edge book PASSES 9–36% of the time even after K2; the middle tercile holds that to ≤ 0.2% and keeps power at 33–42%, for ~3 pp less power when nothing on the up side moves (§7). Raw has no benchmark at all, so it carries the market's drift. Whole-cohort and raw are reported |
| 2 | The mechanism (cl. 13) as a **label** or a **kill** | label · kill | **Label.** It asks *which* reversal, not *whether* the signal pays; a kill would make PR-1 a joint test of two claims |
| 3 | **§9 / §9a:** what a PR-1 KILL means for PR-2; PR-2's read schedule, boundary, kills and fill threshold | as §9a a8 proposes · something else | **As a8:** reads every 126 sessions, at most 8 (≈ 4 years, fixed now), an O'Brien–Fleming-shape boundary at one-sided 1% overall; K2/K3/K4 at a crossing, K2 and the cost-KILL also at the last read, **K6 descriptive** (it would kill 7–16% of genuine crossings at PR-2's n in the high-cost cell); the 10× fill rule, subject to prerequisite 4. A PR-1 KILL ends the old-regime claim but not automatically the auction thread (§9, §10i). Simulated operating characteristics are in §9a |
| 4 | **The CNC entry base:** the last trade P1530 or the 15:00–15:30 VWAP | last trade · VWAP | **Last trade (P1530).** The auction price carries the forced flow's full impact at one print and is executable post-close; the old regime's full-impact print is P1530, while the VWAP averages the impact away (κ 0.71, a −64 bps built-in drag). Disclosed: P1530 is a thin print, and the P1525 variant (cl. 14) separates s from R_on |

**After the four decisions:** this text + §9a are committed as the pre-registration, then the code
is written, reviewed, and run once (cl. 15).
