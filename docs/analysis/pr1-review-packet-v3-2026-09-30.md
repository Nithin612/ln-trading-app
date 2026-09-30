
I'm asking you for ONE careful, critical **verification** of a revised, pre-registered research
design. The design document (draft v3) follows this message or is attached. **This message is
self-contained:** you have no earlier rounds to recall, and everything you need is here. Please read
all of it before answering.

WHO AND WHAT
I'm a solo retail trader-developer building a research and paper-trading system for Indian
equities (NSE). The document describes a study (PR-1) that has NOT been run. It tests one idea:
stocks pushed down hardest in the last minutes of the trading day, relative to their peers,
rebound afterwards. The proposed reason is liquidity provision: index funds, derivative
settlement and fund NAVs force some traders to trade at the closing price, and whoever takes the
other side is paid when that pressure reverses.

WHY THIS ROUND EXISTS
- About 20 earlier strategy ideas were tested and rejected, so the bar is deliberately strict: a
  deflated-Sharpe hurdle of t ≈ 3.6.
- The design is pre-registered. Its text is frozen and committed BEFORE any analysis code is
  written; the study then runs exactly once, and its PASS/KILL/NULL rule is applied mechanically.
- A first outside review (five reviewers) and an internal quantitative review found **three
  defects that would each have decided the result on their own**. Draft v3 fixes them and about a
  dozen smaller items. Section 0 of the document lists every change.
- **This is the LAST external round.** After it, only arithmetic corrections are made, then the
  text is frozen. A flaw you find now can still be fixed; later it cannot.

ALREADY ESTABLISHED — do not re-derive these; attack one only if you bring a number
Everything below was measured on our data or recomputed in code. "Measured" means from
same-session prices, session dates or synthetic series; no return or outcome from the test window
has been computed by anyone.

A. The three defects in v2, now fixed (document §0, rows 1, 2 and 4)
- **Price basis (row 1).** The 5-minute history is back-adjusted for later splits, bonuses,
  demergers, rights and some dividends; the exchange's daily file holds traded prices.
  - The same-session official open ÷ the 09:15 bar's open is more than 2% away from 1 on **22.5%
    of 153,097 name-days**. Where the two bases agree, the opens are exactly equal on **98.7%**.
  - v2's intraday return divided one source by the other. **v3 computes every return inside the
    5-minute table**, and uses the daily file only for sizing and fees.
  - No outside reviewer saw this defect. It shows only in the data.
- **VWAP-close drag (row 2).** Before 3 Aug 2026 the official close was the 15:00–15:30 VWAP,
  while the signal ends at the last trade. Measured: κ = 0.712 (p10–p90 0.62–0.79), and the book's
  built-in drag averages **−64 bps** against ~35 bps of costs. v3 measures the overnight return
  from the last trade.
- **A kill that could not be passed (row 4).** "> 50% of net P&L from ≤ 5% of sessions": noise
  alone puts 83.8% of net P&L in the best 5% of sessions at the bar. v2 passed a genuine
  effect at the bar **0.4%** of the time (an effective bar of t ≈ 6.3); v3 passes it **45–51%**.

B. Arithmetic
- **v2's cost examples and bar were reproduced exactly by all five earlier reviewers.**
- The new v3 figures are the ones to check:
  - per-trade delivery fee, mean **30.41 bps**;
  - the book's own half-spread bracket **[1.76, 2.68] bps**;
  - delivery cost **[33.93, 35.77] bps**, intraday **[14.12, 15.96] bps**;
  - N = 22, n = 754 → **t 3.5953**;
  - at other skew/kurtosis the bar is 3.552–3.728.

C. Design facts (same-session data only)
- **Calendar:** 754 usable pairs on the exchange calendar, which has five special sessions. A
  calendar built only from the 5-minute table gives 756 and silently spans two muhurat sessions.
- **Cohort:** 191–209 names per session (median 204).
- **Book (the 5 most negative late moves):**
  - 206 distinct names; the top 3 hold 7.0% of slots; effective number of names 103.6;
  - median late move −77 bps;
  - median traded price ₹1,161 (cohort ₹1,110); 2.33% of slots cannot be bought at ₹20,000.
- **Half-spread:** median 1.76 bps for book slots vs 1.74 for all names.
- **Data mismatch:** on 3 sessions, 13–26 names each have a 09:15 open that is 0.3–2% off the
  official open, reverting next session. This is disclosed, with a robustness rerun.

D. Claims already examined and REFUTED — don't re-raise without a new number
- **"The names kill (K6) has the same defect."** No: it fires on 0.0–3.1% of genuine passes, and
  on 100% of books where 3 names carry the edge.
- **"The book tilts to wide-spread or low-priced names."** No: see the numbers in C.
- **"Add a stricter concentration kill."** Backwards: the old one was already far too strict.
- **"Check survivorship on the sealed holdouts."** No: that spends them.
- **"Measure post-close fill quality from history."** Impossible: no post-close history exists. A
  forward capture starts 2026-10-01.
- **Considered and not adopted**, with reasons in §0: decide on raw returns · choose the branch
  from theory · split the sample · volatility-scale the signal · rescale prices instead of
  computing returns in one table.

E. External facts (sources in §2 of the document)
- **Verified:**
  - the close was a 30-minute VWAP until 3 Aug 2026, and a call auction since;
  - retail CNC market orders fill at the official close in a post-close session;
  - intraday positions in auction stocks are squared off at 15:12;
  - derivative expiry moved from Thursday to Tuesday on 1 Sep 2025.
- **Not verified:** that MIS entries and delivery sells can be placed in the pre-open auction. So
  both next-open legs are charged a half-spread.

WHERE TO SPEND YOUR EFFORT — highest value first
1. **The row-1 fix.** Every return now comes from the BACK-ADJUSTED 5-minute table. Could that
   create a bias of its own? For example:
   - dividends are adjusted for some names and not others;
   - the adjustment is a single snapshot;
   - the three one-day open-mismatch sessions.
   More generally: **is there another way the DATA could quietly contradict the TEXT?** That was
   the most serious class of defect last round.
2. **The row-2 fix.** The overnight entry at the last trade is hypothetical in the old regime.
   Is "it is the old-regime analog of the auction regime's post-close fill" a sound argument, or
   does it smuggle in something?
3. **The decision rule's calibration (§7).** Is the synthetic model adequate? K2 (the IC-sign
   kill) is not simulated: can it misfire?
4. **§9 governance** (optional).

WHAT I NEED FROM YOU — the four questions at the top of the document
1. For EACH row of §0: ACCEPT, AMEND or REJECT, with one line of reason for anything but ACCEPT.
   Does the fix work? Does it introduce a new problem?
2. Recompute the NEW figures in §5 (costs) and §6 (the bar), and check the logic of §7 (the code
   is in Appendix B — run it if you can). Show your arithmetic and say MATCH or MISMATCH. The fee
   model rounds each leg to the paisa, so a ₹0.01 difference is not a mismatch.
3. ONE remaining flaw that would change PASS, KILL or NULL and is NOT already in §0 or §10. One
   well-argued item is better than a list. "None" is a valid answer.
4. (Optional) §9: is the proposed forward bar sound, given that PR-1 selected the hypothesis? If
   not, what bar, and why?

CONTEXT NOT IN THE DOCUMENT
- **Account:** about ₹1 lakh at Zerodha, 3–5 positions. A cash-market short cannot be held
  overnight, so the overnight version is long-only; intraday (MIS) shorts are allowed.
- **Market structure:** since 3 Aug 2026, NSE sets the close of F&O stocks by a call auction.
  PR-1 uses the OLD regime as mechanism evidence only.
- **The follow-up:** a separate forward study (PR-2) will test the auction regime on sessions
  after 2026-09-29, which nobody has looked at. Some earlier August–September sessions were partly
  read, so they are excluded.

WHAT NOT TO DO
- Don't predict whether this will be profitable, and don't propose different strategies.
- Don't restate the document back to me, and don't re-derive anything in ALREADY ESTABLISHED.
- **Never imply you ran code or opened a source that you didn't.** If you could not run Appendix
  B, write "NOT RUN". Quote a paper or circular only if you read it, and give the title and the
  section or table. If unsure, say "unsure".
- No generic advice ("use more data", "beware overfitting") unless it is tied to a specific
  clause and a specific failure.

IF YOU NEED MORE INFORMATION
List your requests at the TOP of your reply, then answer everything you can without them. I can
supply design-level facts: per-session counts, coverage statistics, the fee-model code, the exact
statistical code, how the half-spread was estimated, and exchange rules with sources. I will NOT
share outcome data (returns, or any signal-versus-return statistic from the test window), because
that would break the pre-registration.

REPLY FORMAT — keep it sharp
- **At most ~900 words**, plus your arithmetic and the table. Rank every point by its effect on
  the PASS/KILL/NULL decision, most serious first.
- **Tag each point:** [NEW] (not in §0 or §10) · [AMEND row N] · [ARITH] · [CONFIRM].
- **Mark each claim** VERIFIED (you computed or derived it here) or ASSUMED.
- Number your answers 1–4:
  - **1:** a table with columns row # · ACCEPT/AMEND/REJECT · one line;
  - **2:** the full arithmetic;
  - **3 and 4**, per point: the issue in one line · the clause (section 4 numbers) · the mechanism
    · the direction of the bias (flatters or hurts) · how to detect or fix it within this design ·
    severity (does it change PASS, KILL or NULL, or is it cosmetic?) · your confidence.
- End with one line: **your single most important finding**, or "no decision-changing flaw
  found".
# PR-1 — pre-registration extract, DRAFT v3, for a verification review (2026-09-30)

**Self-contained.** You do not need our code or data. **Nothing has been run:** no return, IC or
other outcome from the test window has been computed.

v3 is draft v2 plus fixes from two sources:
- **one outside review pass** (five independent reviews);
- **an internal quantitative review of the fixes.** It found a third defect: the price tables are
  on different bases (§0, row 1).

Every point was checked against our code and data before it was adopted or rejected. **This is
the last external round.** After it, only arithmetic corrections are made, the text is committed,
and then the analysis code is written.

## What we ask of you — four questions

1. **§0 lists every change from v2.** For each row, answer **ACCEPT**, **AMEND** or **REJECT**.
   Give one line of reason for anything but ACCEPT. Does the fix work? Does it create a new
   problem?
2. **Recompute** §5 (costs) and §6 (the bar), and check the logic of §7 (a simulation of the
   decision rule; code in Appendix B). Say MATCH or MISMATCH, with your arithmetic.
3. **One remaining flaw** that would change PASS, KILL or NULL and is not already in §0 or §10.
   One well-argued item beats a list. "None" is a valid answer.
4. *(Optional)* **§9, governance:** is the proposed bar for the forward follow-up study sound,
   given that PR-1 selected the hypothesis?

Please **don't** judge whether the strategy will be profitable, and don't propose other
strategies. Mark anything you are unsure of as unsure, and don't cite a source you have not read.
**Items marked NOT ADOPTED in §0 were considered and measured.** Re-raise one only with a new
argument or a number.

## 0. What changed from v2, and why

Rows 1–2 and 4 would each have decided the result by construction.

| # | v2 clause | the defect (found by) | the v3 fix |
|--:|---|---|---|
| 1 | 2, 5 | **The two price sources are on different bases.** The 5-minute history is **back-adjusted** for later splits, bonuses, demergers, rights and some dividends; the exchange's daily file holds **traded** prices. On **22.5%** of name-days the official open differs from the 09:15 bar's open by more than 2%, and the step lands exactly at corporate-action dates (e.g. 5.0 until a 1:5 split). Any return that divides one source by the other measures that factor, not the market. **v2's intraday outcome did this** (5-minute 15:10 price ÷ daily-file open), and so did the first v3 draft's overnight outcome. *(internal review; re-measured)* | **Every return is computed inside the 5-minute table**, whose adjustment is consistent. Where the two sources share a basis, its **09:15 open equals the official open exactly on 98.7% of name-days**. The daily file is used only for **sizing and fees**, which need the traded price |
| 2 | 5 | **R_on started from the official close.** Before 3 Aug 2026 that close was the 15:00–15:30 VWAP, while s ends at the last trade before 15:30. Under a random walk, E[R_on \| s] ≈ κ·s. Measured on one basis: **κ = 0.71** (p10–p90 0.62–0.79), and the book's built-in drag averages **−64 bps**, against ~35 bps of costs. It pushes toward KILL. *(three reviewers; measured)* | **R_on is measured from the last trade that completes the signal**, the old-regime analog of the auction regime's post-close fill at the auction price. The official-close version and the gap G are reported but never decide |
| 3 | 3 | **The pair calendar silently spanned sessions.** The daily file has 764 sessions, one more than the 5-minute table (the 2024-11-01 muhurat). The 2023-11-12 muhurat is in neither table. Two of v2's "756 pairs" spanned a muhurat session. *(internal review)* | Pairs are consecutive in the **exchange calendar**, with five listed special sessions: **754 pairs** |
| 4 | 10 | **The session-concentration kill fired on genuine passes.** "> 50% of net P&L from ≤ 5% of sessions": noise alone puts 0.05 + φ(1.645)/SR ≈ **84%** of net P&L in the best 5% of sessions at the bar. It fired on **99%** of genuine passes and quietly raised the bar to **t ≈ 6.3** (§7). v2 also said this kill caught monthly-expiry concentration, yet expiry settlement is one of the three named mechanisms | **K3:** KILL only if removing the best **15 sessions (2%)** leaves the mean net ≤ 0; checked only on a would-be PASS |
| 5 | 8 | **The branch was chosen on the test data**, an extra trial the bar did not count. Choosing on *gross* can pick the branch with the lower *net* (the costs differ by ~20 bps) *(all five reviewers)* | Choose the branch with the **higher Newey–West t of its NET series**; charge PR-1 as **two trials: N = 20 + 2 = 22** |
| 6 | 10 | **K2 used IC(s, R_on) even when the intraday branch decides** *(two)* | K2 uses the **chosen branch's** outcome |
| 7 | 3 | **"All 75 bars on t and on t+1" looks ahead.** Halts and no-trade bars on t+1 go with extreme moves *(two)* | Completeness is required **on t only**. A book name with missing t+1 data is **carried, not dropped**, and counted (cl. 3) |
| 8 | §5 | **Spread legs were inconsistent.** Intraday paid two half-spreads while its entry is the pre-open auction open; delivery paid none at that same open. The bracket was also the whole cohort's, while the bid-ask bounce is bounded by the *book's* half-spread *(three + internal)* | **Every leg in both branches pays one half-spread**, for reasons in §5. The bracket is rebuilt **on the book's own names** by the same construction: **[1.76, 2.68]** bps (cohort [1.74, 2.28]) |
| 9 | 6, §5 | **The notional was implicit.** Costs depend on size, and a name priced above ₹20,000 cannot be bought *(two)* | **₹20,000 per name, whole shares, sized on the traded price** (the official close). qty 0 ⇒ skipped: **2.33%** of slots |
| 10 | §6 | **N and n disagreed** *(two)* | **N = 22; n = 754** everywhere |
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
  names = 7.0% of slots) it fired on **0.0–3.1%** of genuine passes, with or without a flat cost.
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
| **Our 5-minute history is back-adjusted; our daily file is not** (row 1) | measured on 153,097 name-days (§8) |

## 3. PR-1 in one paragraph

We use **historical, pre-auction data** as a *mechanism test* for the auction regime. The question:
does a late-session move against peers predict the opposite move afterwards, by enough to pay
retail costs, **if the entry is made at the price that completes the late move**?
- **That is the entry the auction regime provides:** a post-close fill at the auction price.
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
| 3 | **Calendar and cohort.** The **exchange calendar** is the daily file's sessions plus the 2023-11-12 muhurat session, which is absent from both tables. The five **special sessions** are 2023-11-12, 2024-03-02, 2024-05-18, 2024-11-01 and 2025-10-21 (DR drills and muhurat; exchange-announced). A pair (t, t+1) is used when t+1 is the next exchange session, neither is special, and t qualifies: **754 pairs**. **The cohort on t** is the names with all 75 bars on t and a daily bar on t (**t only**). A session qualifies with ≥ 150 such names. Drop a name on t if t+1 is its split or bonus ex-date (announced in advance). **A book name with missing t+1 data is carried, not dropped**, and every carried slot is counted: no bar on t+1 at all (suspended) ⇒ R_on = 0 and R_day = 0; no bar stamped 09:15 ⇒ the open of the first bar of t+1; no bar stamped 15:05 ⇒ the close of the latest earlier bar. **Demeaning** uses the cohort names whose outcome is defined; a carried book name enters at its carried raw value minus that mean. |
| 4 | **Signal (unchanged):** **s = (P1530_t − P1515_t) ÷ P1515_t, demeaned** across the session's cohort. |
| 5 | **Outcomes.** **R_on = (O_{t+1} − P1530_t) ÷ P1530_t**: from the last trade, *not* the official close. **R_day = (P1510_{t+1} − O_{t+1}) ÷ O_{t+1}**: before the 15:12 square-off. Both are **demeaned within session**, and **the decision uses the demeaned (relative) return**. The cohort mean is market beta: the signal does not produce it, and a long-only holder carries it as a separate, unhedged exposure. **Reported, never decisive:** raw returns; the old-regime executable R_on from C_t, computed within the daily file; and **G = P1530_t ÷ C_t − 1**, both on the traded basis. |
| 6 | **Book:** each session, the **5 names with the most negative s** (ties at the fifth place: ascending symbol), long only. **₹20,000 per name; qty = floor(20,000 ÷ C_t)**, on the traded price. A name with qty 0 is skipped and not replaced. The session return is the equal-weight mean over the names bought (k_t of them). |
| 7 | **Costs per slot.** fee_i = the fee model of §5 with qty from cl. 6 and both legs priced at C_t, the traded price, each leg dated on its own day. Pricing each leg at its own traded price instead moves a fee by ≈ 0.1 bps per 1% of price move, typically < 0.2 bps. Add **two half-spreads h** (one per leg), with **h ∈ [1.76, 2.68] bps**. **net_i(h) = R_i − fee_i − 2h**, and the session net is the mean over the names bought. A carried CNC slot pays the full round trip. An MIS slot with no trade on t+1 is never entered: no return, no fee. |
| 8 | **E1 (information, reported for both outcomes):** mean over sessions of Spearman IC(s, outcome) across the cohort, with its t and 90% CI as in cl. 10. |
| 9 | **Branch:** compute both branches' net series at h = 2.68. **The branch with the higher t decides; charged as two trials, N = 22.** The other branch is reported and never promoted. **Delivery (CNC):** outcome R_on. **Intraday (MIS):** outcome R_day. |
| 10 | **Statistics:** t = Newey–West (Bartlett kernel) with **lag 10** = ⌈754^(1/3)⌉. 90% CI = mean ± 1.645·SE. **DSR:** the formula in §6 at the series' **realized** skew and kurtosis, N = 22, n = 754. |
| 11 | **Decision** (chosen branch). **PASS** ⇔ net(h = 2.68) has **t ≥ 3.595** and **DSR ≥ 0.95**, and no kill fires. (This implies v2's "gross CI lower bound > top of the cost interval".) **KILL** ⇔ K2 fires, **or** the 90% CI upper bound of net(h = 1.76) is below 0, **or** a would-be PASS fails K3, K4 or K6. **NULL** ⇔ anything else: we stop, and do not re-specify. |
| 12 | **Kills.** **K2:** mean IC(s, chosen outcome) ≥ 0. *Robustness kills, checked only on a would-be PASS (they can turn a PASS into a KILL, never a NULL into a KILL):* **K3:** removing the 15 sessions with the largest net leaves the mean net ≤ 0. **K4:** mean net over 2023-07-03 → 2025-01-31 and over 2025-02-01 → 2026-07-31 differ in sign. **K6:** the 3 names with the largest total net contribution carry > 50% of the total net. A name's contribution is Σ over its slots of net_i ÷ k_t. |
| 13 | **Mechanism label** — reported with the decision, never changes it. Each session, cross-sectional OLS of the chosen outcome on s, **r_pre = (P1515_t − O_t) ÷ O_t** and **gap = (O_t − P1530_{t−1}) ÷ P1530_{t−1}**, all demeaned, with t−1 the previous non-special session. Slopes are averaged over sessions, with the cl.-10 CI. The first session is skipped: its t−1 lies in a sealed block. **close-specific** ⇔ CI(β_s) < 0 **and** CI(β_s − β_pre) < 0. **generic reversal** ⇔ CI(β_s) < 0 only. **none** otherwise. PR-2 must state which label it inherits. |
| 14 | **Descriptive only, never decisive:** E1 for both outcomes · weekday × expiry type (P6) · VIX terciles (P4) · late-volume terciles (P3) · the long-short intraday variant · raw returns · the executable R_on from C_t, and G · a concentration panel (best-5% share; tagged expiry and index-event days) · a balanced-subsample rerun (names present in every session) · a rerun without the three one-day open-mismatch sessions (§10j) · counts of carried and skipped slots. |
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
fees come to: median **30.07**, mean **30.41**, p90 31.15, max 37.53 bps (§8). ₹500 × 40 = exactly
₹20,000 is the floor: whole-share rounding leaves most slots slightly below ₹20,000, so the flat DP
charge weighs more.

**Spread.** An Abdi–Ranaldo estimator on 5-minute bars, 2023-07-03 → 2026-08-20, 6,748
name-windows of 21 sessions on the same capture set:
- **the whole cohort:** median **1.74 bps**, 90% CI [1.58, 1.93]. Windows below the estimator's
  resolution read 0, so 1.74 is a lower bound; without them the median is **2.28**.
- **the book's own slots, by the same construction:** **[1.76, 2.68]**. The decision uses this
  bracket (h = 2.68 for PASS, h = 1.76 for the cost KILL), because the bid-ask bounce is bounded
  by the *book's* half-spread, not the cohort's.

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

N = 20 prior strategy trials in this programme + 2 for PR-1's two candidate branches = **N = 22**;
n = **754**. A Deflated Sharpe ratio of 95% (Bailey & López de Prado):

- E[max SR] = σ_SR · ((1 − γ) Φ⁻¹(1 − 1/N) + γ Φ⁻¹(1 − 1/(N e))), with γ = 0.5772 and
  σ_SR = 1/√n.
- PSR = Φ( (SR − SR\*) √(n − 1) / √(1 − skew · SR + (kurt − 1)/4 · SR²) ), where kurtosis is
  Pearson (normal = 3).

Ours, at skew 0 and kurtosis 3:
- σ_SR = 0.036418;
- Φ⁻¹(1 − 1/22) = 1.69062;
- Φ⁻¹(1 − 1/(22e)) = 2.12672;
- **E[max SR] = 0.070736** (≈ 1.12 annualised: the Sharpe that the best of 22 zero-edge trials
  shows by luck);
- the smallest per-session Sharpe with PSR ≥ 0.95 is **0.130934**, so **t = 3.5953**, and
  annualised ≈ 2.08.
- At other moments the bar moves: skew −0.5, kurtosis 6 → **t 3.660** · skew −1, kurtosis 10 →
  **3.728** · skew +0.5, kurtosis 6 → 3.552 · skew 0, kurtosis 11.46 → 3.625.
- **Sensitivity to N:** N = 30 → t 3.727 · N = 44 → 3.881 · N = 60 → 4.000. N = 20 is a programme
  convention, and it may undercount.
- The trials overlap in data, which makes the effective count smaller. On that count the bar is
  conservative.

## 7. Operating characteristics of the decision rule — synthetic, no market data

**Set-up:**
- Net series of n = 754 with a planted true t; 20,000 runs per cell; seeded; code in Appendix B.
- Noise: normal · t₄ · t₃ · skew-normal (skew ≈ −0.85).
- v2 = its t, its K3 and K4. v3 = cl. 11–12 (t, DSR, K3, K4).
- K6 is run separately, on the **measured** book slot distribution. K2 is not simulated: it needs
  a cross-section model.

| noise | true t | PASS v2 | PASS v3 | v2's K3 fires when t ≥ bar |
|---|--:|--:|--:|--:|
| normal | 0.0 | 0.0% | 0.0% | — |
| normal | 2.0 | 0.0% | 5.0% | 100% |
| normal | 3.6 | **0.4%** | **47.4%** | 99.2% |
| normal | 5.0 | 10.4% | 90.5% | 88.7% |
| t₄ | 3.6 | 0.0% | 48.2% | 100% |
| t₃ | 3.6 | 0.0% | 50.6% | 100% |
| t₃ | 5.0 | 2.4% | 87.7% | 97.4% |
| skew −0.85 | 3.6 | 18.0% | 45.2% | 65.5% |
| skew −0.85 | 5.0 | 64.5% | 88.5% | 29.2% |

**Reading the table:**
- A rule should pass about half the time at a true t equal to its own bar. v3 does (45–51%); v2
  did not (0–18%).
- Closed form: at the bar the best 5% of sessions carry 0.05 + φ(1.645)/SR = **83.8%** of net P&L.
  That share falls to 50% only at t ≈ **6.29**.
- The v3 kills K3 and K4 almost never fire on a would-be pass in these iid cells. K4 targets
  regime change, which iid noise does not contain.

**What the robustness kills catch, on the measured slot distribution:**
- **K6 (names):** a name's volatility rises with its slot count (exponent 0.256 measured; 0.5 as a
  stress), and a flat cost eats 0% or 80% of the gross. On genuine broad edges at t 3.6 and 5.0,
  **K6 fires on 0.0–3.1%** of passes. When 3 names carry the whole edge and the rest lose, the t
  passes in 86.5% of runs, and **K6 fires on 100% of those**.
- **K3 (sessions):** when 15 random sessions carry the whole edge, the t itself passes only 11.7%
  (3.3% if ordinary days lose 0.04 sd), and K3 fires on ≤ 0.6% of those that pass. Outlier
  sessions inflate the variance, so the t does this work, and K3 is a backstop that seldom binds.
  We keep it because it costs < 1 pp of power, not because it has power.

## 8. Design-level facts, measured from SESSION-t DATA ONLY (no t+1 price, no return read)

- **Calendar:** the 5-minute table has 763 sessions and the daily file 764 (+ the 2024-11-01
  muhurat). 760 sessions have ≥ 150 complete names (per session: min 191, median 204, max 209).
  That gives **754 pairs**; a 5-minute-only calendar gives 756.
- **Price basis:** on 153,097 name-days, the official open ÷ the 09:15 bar's open is more than 2%
  away from 1 on **22.5%**. Where the bases agree, the two are exactly equal on **98.7%**.
- **Book:**
  - 3,770 slots over the 754 pairs;
  - **206 distinct names**;
  - the top 1 / 3 / 10 / 20 names hold 2.4% / **7.0%** / 18.8% / 32.3% of slots;
  - **effective number of names (1/HHI) = 103.6**;
  - the most frequent names are high-beta mid-caps.
- **The book's demeaned late move s:** median **−77 bps** (p10 −139, p90 −53).
- **The same-session gap G = P1530 ÷ C_t − 1** (one basis): κ median 0.71; the book's demeaned G
  averages **−64 bps**. This is the drag that v2's outcome base carried.
- **Traded price:** book median ₹1,161 (p90 ₹5,605, max ₹49,440); cohort median ₹1,110. **88 slots
  (2.33%)** are priced above ₹20,000.
- **Delivery fee** at ₹20,000 per name, whole shares, traded prices: median 30.07, mean 30.41, p90
  31.15, max 37.53 bps.
- **Half-spread of book slots vs all name-windows** (unconditional quantiles; both lie above
  their clamp shares of 33.0% and 28.6%):

  | | q50 | q70 | q90 | median of non-clamped |
  |---|--:|--:|--:|--:|
  | book slots | 1.76 | 2.87 | 4.46 | **2.68** |
  | all name-windows | 1.74 | 2.52 | 3.71 | 2.28 |

## 9. What each outcome means for the follow-up — PROPOSED; the author decides before the freeze

- **PASS** → PR-2 is pre-registered and committed before any auction-regime outcome is read:
  same branch, same book rule.
  - **Sessions:** its sessions start **after 2026-09-29 and after its own commit date**. Earlier
    August–September sessions were partly read: a spread study used 5-minute bars to 2026-08-20,
    and an earlier auction study read 7 sessions' outcomes. They are excluded.
  - **Bar:** a **single-test bar with an alpha-spending boundary** (e.g. O'Brien–Fleming, overall
    one-sided α = 1%) over a pre-registered read schedule. That controls repeated looks: four naive
    looks at t ≥ 2.33 would give 2.8%, not 1%.
  - **Why not the full deflation again:** the current agreement demands a second N-deflated t ≥
    3.575. At a true annual Sharpe of 2 that needs **~3.2 years** of forward sessions; a 1%
    single-test bar needs ~1.4. At a Sharpe of 1.5 the figures are 5.7 and 2.4 years.
- **NULL** → PR-1 stops and nothing is re-specified. PR-2 may still run under its own
  pre-registration, counted as a new trial.
- **KILL** → the old-regime claim is refuted. Whether it also ends the auction thread is the
  author's call. The old close spread the forced flow over 30 minutes, while the auction
  concentrates it in one print. So a PR-1 KILL is weaker evidence against the auction effect than
  against the old one.

## 10. Known weaknesses — disclosed; please go beyond them

- **(a) The CNC entry is hypothetical in the old regime** (§3). The old-regime executable version
  is reported.
- **(b) Post-close fills may be adversely selected**: a holder expecting the bounce won't sell at
  the close.
  - The counterfactual (orders that would not have filled) leaves no trace in any historical
    data. So **no historical study can size this discount**, and a PASS is an upper bound.
  - A forward capture of post-close volume and pending quantity starts 2026-10-01.
- **(c) Corporate actions are mostly neutralised.** Returns come from the back-adjusted table,
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
  open 0.3–2% away from the official open**, reverting the next session. That is a one-day source
  mismatch, not a basis step. It is disclosed, and a rerun without those sessions is reported
  (cl. 14).
- **(k) The adjustment is one snapshot.**
  - The basis step lands exactly on 44 split/bonus ex-dates.
  - cl. 3 drops every name on the night before its split/bonus ex-date regardless, so an event the
    snapshot missed cannot enter R_on.
  - A corporate action after the window rescales the whole window by a constant, which leaves
    every return unchanged.

## Appendix B — the §7 simulation (numpy; swap the noise line for t₃ or skewed noise)

It reproduces §7 within Monte Carlo error; its random stream differs from our script's.

```python
import math, numpy as np
from statistics import NormalDist
Z, n, rng, G = NormalDist(), 754, np.random.default_rng(42), 0.5772156649
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
    k4 = np.sign(x[:, :n//2].mean(1)) != np.sign(x[:, n//2:].mean(1))
    v2 = (t >= 3.5749) & ~((tot <= 0) | (best[:, :38].sum(1) > .5*tot)) & ~k4
    v3 = (t >= 3.5953) & (dsr(x) >= .95) & ~((tot - best[:, :15].sum(1)) <= 0) & ~k4
    print(tt, f"PASS v2 {v2.mean():.1%}  PASS v3 {v3.mean():.1%}")
```

## Reply format

- **At most ~900 words**, plus your arithmetic and the table. Rank every point by its effect on the
  PASS/KILL/NULL decision, most serious first.
- **Tag each point:** [NEW] (not in §0 or §10) · [AMEND row N] · [ARITH] · [CONFIRM]. **Mark each
  claim** VERIFIED (you computed or derived it) or ASSUMED. If you could not run Appendix B, write
  "NOT RUN".
- Number your answers 1–4:
  - **1:** a table with columns row # · ACCEPT/AMEND/REJECT · one line;
  - **2:** the full arithmetic;
  - **3 and 4**, per point: the issue in one line · the clause · the mechanism · the direction of
    the bias · how this design would detect or fix it · whether it changes PASS/KILL/NULL · your
    confidence.
- End with one line: **your single most important finding**, or "no decision-changing flaw
  found".
