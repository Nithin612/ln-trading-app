# PR-1 outside pass + internal review — adjudication (2026-09-30)

**What was reviewed:** `pr1-preregistration-extract-2026-09-30.md` (the two-page extract of draft
v2), sent by the user to ChatGPT, Gemini, DeepSeek, Grok, Kimi and a Claude chat.

**Five independent reviews, not six:** the reply pasted as Gemini's is ChatGPT's text, word for
word.

**Method:**
- Every point was checked against the full draft (`nemotron_review.md` §8.4 + §10.4), the code,
  or a measurement **before** it was adopted or rejected.
- The fixes were then reviewed by `quant-verifier`, which returned **FAIL** with one
  decision-changing defect. Every one of its findings was re-measured here before adoption.
- Nothing from the test window's outcomes was read. Every probe used same-session prices,
  session dates, or synthetic series.

**Result:** draft **v3** = `pr1-preregistration-extract-v3-2026-09-30.md`; the prompt for one
final verification round = `pr1-review-prompt-v3-2026-09-30.md`.

## Headline — v2 would have decided PR-1 by construction, three ways

1. ⛔⛔ **The two price tables are on different bases.** Found by the internal review, not by any
   outside reviewer.
   - `ohlcv_5m` (the Kite backfill) is **back-adjusted** for later splits, bonuses, demergers,
     rights and some dividends. `ohlcv_1d` (the bhavcopy) holds **traded** prices.
   - Re-measured on 153,097 name-days: the official open ÷ the 09:15 bar's open is > 2% from 1 on
     **22.5%** of them, and exactly equal on **98.7%** where the bases agree.
   - The step lands at corporate-action dates: KOTAKBANK 5.0000 until its split; NESTLEIND
     20 → 2 → 1; RELIANCE 2.0981 (the JFS demerger × a bonus); BANKBARODA stepping each June
     (dividends).
   - ⇒ **v2's intraday outcome** (5-minute 15:10 price ÷ daily open) and **v3's first-draft
     overnight outcome** (daily open ÷ 5-minute 15:30 price) both measured the adjustment factor,
     not the market.
2. **The overnight outcome carried a built-in drag toward KILL** (Claude chat 1.1; Kimi 1.1;
   DeepSeek 2).
   - R_on started from the official close, which before 3 Aug 2026 was the 15:00–15:30 VWAP; the
     signal ends at the last trade.
   - Measured on one basis: **κ = 0.712** (p10–p90 0.62–0.79), and the book's demeaned drag is
     **−64 bps**, against ~35 bps of costs.
3. **K3 fired on almost every genuine pass** (Claude chat 1.2).
   - At the bar, the best 5% of sessions carry 83.8% of net P&L by noise alone.
   - Simulated: P(PASS | true t 3.6) = **0.4%** under v2 (0.0% with fat tails), against **47.4%**
     under v3. v2's effective bar was **t ≈ 6.3**.

## Outside-pass issue ledger

| # | issue | raised by | verdict | evidence | v3 |
|--:|---|---|---|---|---|
| 1 | R_on from the VWAP close; the signal ends at the last trade | Claude, Kimi, DeepSeek | ✅ **CONFIRMED, decision-changing** | κ 0.712; drag −64 bps (`kappa` probe, same-session prices only) | R_on from P1530, inside the 5-minute table |
| 2 | K3 fires on genuine passes | Claude | ✅ **CONFIRMED, decision-changing** | `scripts/pr1_decision_oc.py` | leave-15-out, only on a would-be PASS |
| 2b | K3's stated purpose (monthly-expiry concentration) contradicts the mechanism | found in adjudication | ✅ | round 8 §8.3 withdrew K7 for the same reason | covered by the new K3 |
| 3 | The branch is chosen on the test data | all five | ✅ | locked A3: "+1 per pre-registered estimand" | N = 22 |
| 3b | The branch compares gross, not net | Claude | ✅ | costs differ ~20 bps | choose on the net t |
| 4 | K2 keyed to R_on in the MIS branch | Kimi, Claude | ✅ | the v2 text | chosen outcome |
| 5 | t+1 completeness looks ahead | ChatGPT, Claude | ✅ | the v2 text | t only, plus a carry rule |
| 6 | Spread legs inconsistent | DeepSeek, Kimi, Claude | ✅ as an inconsistency | MIS in the pre-open is **not** stated on any primary Zerodha page (checked 09-30) | every leg pays h |
| 7 | Notional unstated; whole shares; names above ₹20k | ChatGPT, Claude | ✅ | traded-basis fee mean 30.41 bps; 2.33% of slots are qty 0 | ₹20k/name, sized on C_t |
| 8 | N vs "21 plus this one"; n 763 vs 756 | ChatGPT, Claude, Kimi | ✅ | A3 | N = 22; n = 754 (see internal #5) |
| 9 | The bar assumes Gaussian moments | Claude | ✅ | the house `deflated_sharpe()` uses REALIZED moments | DSR at realized moments, as well as t |
| 10 | "Five choices left to the code" | Claude | ◐ **4 of 5 were in the full draft** and dropped by the extract | `nemotron_review.md` §8.3–§10.4 | every clause in full |
| 11 | Demeaned vs raw | ChatGPT, DeepSeek, Kimi (raw); Claude (demeaned) | ◐ **explicit: decide on demeaned** | paired-benchmark canon; beta is not produced by the signal | raw reported |
| 12 | Generic reversal (r_pre) / gap effect (P5) | Claude Q3, Kimi Q3 | ✅ as a **label** | — | cl. 13 |
| 13 | A PR-1 KILL weakly refutes the auction effect | Claude Q4, Kimi Q4 | ✅ raised to the user | — | §9 PROPOSED |
| 14 | Bid-ask bounce in a last-trade signal | ChatGPT, Kimi | ✅ | bounded by the **book's** half-spread (internal #2) | h from the book's own bracket |
| 15 | Kill 4 (names) has the K3 defect | Claude | ⛔ **REFUTED** on the measured slots | 0.0–3.1% of passes; 100% of 3-name rescues | kept |
| 16 | The book tilts to wide-spread, low-priced names | Claude, DeepSeek | ⛔ **REFUTED at the median** | AR 1.76 vs 1.74 bps; traded price ₹1,161 vs ₹1,110 | upper tail priced via internal #2 |
| 17 | Stricter concentration kills | Grok | ⛔ **REFUTED** — backwards | row 2 | — |
| 18 | Survivorship check on the sealed holdouts | Grok | ⛔ **REJECTED** | it spends the holdouts | — |
| 19 | Post-close depth from the historical tape | Grok | ⛔ **impossible** | no post-close history exists | — |
| 20 | Adverse selection is not estimable from ANY historical data | Kimi | ✅ sharpened | — | 10b |
| 21 | The CA gap: demergers, rights | Claude | ✅ — now mostly neutralised by the adjusted table | internal #1 | 10c |
| 22 | Survivorship direction (flatters) | Kimi, DeepSeek, Grok | ✅ (already disclosed) | — | 10d + a balanced subsample |
| 23 | Expiry-weekday migration | Kimi | ✅ descriptive | NSE/FAOP/68747 | P6 |

**Arithmetic (Q2):** every reviewer reproduced §5 and §6 of v2.
- Kimi's n = 756 figure (3.569) is wrong; the correct value is 3.5750.
- Grok rounded per component and dropped the PSR moment term, yet still called it a MATCH.

## Internal review (quant-verifier) — FAIL → every finding re-measured → fixed

| # | finding | severity | re-measured here | v3 |
|--:|---|---|---|---|
| 1 | Price bases differ between the 5-minute and daily tables | **DECISION-CHANGING** | ✅ 22.5% of name-days > 2%; exact 98.7% where the bases agree; steps at CA dates | **every return inside the 5-minute table**; the daily file for sizing and fees only |
| 2 | The bounce bound is the book's half-spread, not the cohort's | MATERIAL | ✅ the book's median of non-clamped windows is **2.68** (cohort 2.28) | bracket **[1.76, 2.68]** for every leg. We did not adopt the reviewer's q70 (2.87), because 2.68 is the same construction as 2.28 |
| 3 | §9: repeated looks inflate 1%; "never searched" is false for Aug–Sep | MATERIAL | ✅ (the reviewer simulated 2.83% at 4 looks) | alpha-spending boundary; PR-2 starts after 2026-09-29 and after its commit |
| 4 | §8 used adjusted prices for the price level, qty and fees | cosmetic | ✅ traded basis: median ₹1,161; 88 qty-0 slots; fee 30.41 | fixed |
| 5 | Calendar: 764 daily vs 763 five-minute sessions; two pairs span a muhurat | cosmetic → the count | ✅ **754 pairs** | five listed special sessions |
| 6 | "(cl. 12)" should read "(cl. 13)" | cosmetic | ✅ | fixed |
| 7 | Demeaning of carried names, their fees, K6's weights unstated | cosmetic | — | specified |
| 8 | Facts script: an unbounded daily join; the CA drop skipped | cosmetic | ✅ | bounded; drop applied |
| 9 | OC names model: planted t 3.39 not 3.6; √count volatility; no cost | cosmetic | ✅ | fixed; K6 0.0–3.1%, so K6 stands |

**Also measured:**
- **One-day open mismatches.** On 2024-02-05, 2024-05-14 and 2025-01-20, 13–26 names each have a
  09:15 open 0.3–2% off the official open, reverting the next session. Disclosed, with a rerun
  without them.
- **Scope sweep.** Only PR-1's design mixed the two tables inside a return.
  `spread_impact_study.py` computes spreads within the 5-minute table and traded value from the
  daily file (correct), and `m93_cluster_audit.py` reads one table.

## Scorecard (outside reviewers)

| reviewer | decision-changing | valid | refuted / wrong | note |
|---|--:|--:|--:|---|
| **Claude chat** | **2** (κ drag, K3) | 9 | 2 (K6, spread tilt) | the only one to simulate |
| **Kimi** | 1 (κ drag, found but judged "economically correct" for the trade) | 8 | 1 | K2 keying, P5, "not estimable from data" |
| **DeepSeek** | 1 (the signal/entry mismatch; its fix — a signal from the official close — would not remove the drag) | 4 | 1 | the spread-leg MISMATCH is valid |
| **ChatGPT** | 0 | 7 | 0 | t+1 look-ahead, notional, N/n |
| **Grok** | 0 | 2 | 3 | Q3 backwards; would spend the holdouts |
| **Gemini** | — | — | — | not received: ChatGPT's text pasted twice |

⭐ **No outside reviewer found the price-basis defect, and it was the most serious of the three.**
It is invisible from a design text: seeing it takes the data.

## Also found while adjudicating (W1 — fixed)

- **The v2 extract was lossy.** Four settled clauses were missing. ⇒ v3 carries every clause.
- **`deflated_sharpe.py` stated the independence caveat backwards** (docstring + the rendered
  report line). Correlated trials make the bar **conservative**; serial dependence within a series
  is the optimistic part.
- ⛔ **My own process error.** I stopped the first verifier run as "stalled" by reading the mtime
  of its `.output` file, which is a **symlink**. Its real transcript was still being written. The
  relaunch cost ~37 minutes. ⇒ `stat -L` (or the symlink's target) before calling an agent hung.

## Probes (re-runnable; no outcome read)

```
cd backend && uv run python scripts/pr1_design_facts.py   # same-session prices + dates, READ ONLY
cd backend && uv run python scripts/pr1_decision_oc.py    # synthetic; parity-checked vs house NW t + DSR
```

## Recommendation

- **One more round, narrow and final.** Verify the v3 changes (ACCEPT/AMEND/REJECT per row),
  recompute, and ask for one remaining flaw. Send it to Claude chat, Kimi and ChatGPT. Optionally
  add DeepSeek and a real Gemini reply. Skip Grok.
- **Stop rule:** after this round, only arithmetic corrections; then commit.
- **Decisions only the user can take, before the freeze:**
  1. decide on demeaned (recommended) or raw;
  2. the mechanism label as a label (recommended) or a kill;
  3. §9 — what a PR-1 KILL means for PR-2, and PR-2's forward bar.

---

# Round 2 — verification of draft v3 (2026-09-30)

**Replies:** ChatGPT, DeepSeek, Grok, Claude chat, Gemini, Kimi.
- ⚠ **Kimi never received the document**: its words were "only your cover note reached me". It
  reviewed the prompt alone. For NIM, send the packet file, not the prompt.
- Every decision-relevant claim was re-checked by simulation or by an outcome-free query
  (scratchpad `r2_sim.py`, `r2_data.py`) before a verdict.

## The one decision-changing finding — K2 was the kill §7 said it had NOT simulated

⭐ **K2's whole-cohort IC lets the side the book never trades decide** (Claude chat, with a
simulation; ChatGPT row 6; Kimi §7 — three sources).
- **Mechanism:** the reversal lives in the 5-name book, but the IC ranks all ~204 names. A mild
  continuation of late UP-moves pushes the IC to ≥ 0.
- **Re-simulated:** 204 names, reversal confined to the book and calibrated to a net t of 3.6.
  Up-move continuation m = 0 / 0.02 / 0.03 / 0.04 (σ of R per σ of s) ⇒ the whole-cohort K2
  fires on **0.0% / 10.2% / 69.7% / 98.2%** of genuine passes. Claude's figures were 0 / 8.7 /
  62.9 / 98.7.
- **Fix, verified:** compute K2 on names with s **below the session median**. It fires on
  **0.0%** of passes in every cell, and on **49.7%** under the null, so it keeps its KILL role.
- **Same root, smaller:** the cohort mean the book is demeaned against also absorbs the up side's
  response (Claude: the book t falls by ≈ 25·m). ⇒ a middle-tercile-demeaned rerun, descriptive.
- ⭐ **LESSON:** v3's §7 said "K2 is not simulated". Every reviewer who took that disclosure
  seriously found the defect. A disclosed gap in the instrument validation is where the next
  defect lives: **simulate every kill, including the cross-sectional ones, before the freeze.**

## Material — verified

| # | point | source | verdict | evidence |
|--:|---|---|---|---|
| M1 | PR-2's "same book rule" cannot run in the auction era | Claude | ✅ **CONFIRMED** | 2026-08-10: bars stamped 15:15–15:25 exist for **3 of 209** names (pre-auction 2026-07-10: 209 of 209). So P1530 is undefined, and "all 75 bars" fails. ⇒ **commit PR-2's translation WITH PR-1's freeze**, or PR-1's result can shape it |
| M2 | Extend the night-drop to every ADJUSTED corporate action (demergers, rights, adjusted dividends) | DeepSeek, Claude; Kimi (dividends) | ✅ **CONFIRMED** | 554 name-nights on the 754 pairs have an overnight basis step, **18 of them book slots**. RELIANCE's JFS factor is **1.0491 = 1/0.9532**, the company's *tax cost-apportionment ratio*, not the market's split, so the adjusted return across a demerger night is wrong, not merely unrealizable. There is also no 09:15 bar on 2023-07-20 (special pre-open). ⇒ drop any name-night whose same-session basis steps overnight (> 0.3%), in addition to the split/bonus list |
| M3 | The spread top 2.68 is not shown to bound the MEAN half-spread | ChatGPT | ◐ **answered with a number** | Book-slot mean **2.18 bps** (clamped windows as 0), window-cluster 90% CI **[1.91, 2.48]**. 2.68 > 2.48, so it IS conservative; §5 must state this |
| M4 | §9 forward bar: 1.4 years is 50% power, not a plan; the alpha-spending looks must be exact | Claude, ChatGPT | ✅ | 80% power at one-sided 1% needs **2.51 y** at Sharpe 2 and 4.46 y at 1.5 (Claude, reproduced by formula). Plan on a SHRUNK effect (winner's curse), and decide PR-2 on a pre-registered fill rule from the post-close capture |
| M5 | §7 does not model the two-branch max | ChatGPT, DeepSeek | ✅, no change to the verdict | Re-simulated: double null P(PASS) **0.07%**; (3.6, 0) → 51.5% with the true branch chosen **99.4%**; (2, 2) → 12.8% |

## Refuted or answered

- **DeepSeek row 4 ("K3 kills an expiry-concentrated edge"): REFUTED.** Edge on 36 or 150 expiry
  sessions, with or without ordinary-day bleed ⇒ K3 fires on **0.0%** of passes.
- **DeepSeek row 13 ("decide on raw")**: re-raised without a new argument. It stays user decision
  #1; this round 4 of 6 accept demeaned.
- **Kimi's main finding ("decide the overnight branch on the VWAP entry")**:
  - Its premise is **factually wrong**. A post-close order is placed after the close is set, so
    the fill price is known before ordering in BOTH regimes.
  - The real question is which old-regime price stands for the auction price. The auction price
    carries the forced flow's full impact at one print and IS executable post-close. The old
    regime's full-impact print is P1530; the VWAP averages the impact.
  - ⇒ keep P1530 for the decision, with ChatGPT's wording ("a synthetic signal-completion price",
    not an "executable analog"). Keep Claude's thin-print disclosure and its descriptive variant:
    s ending at P1525, so s and R_on share no print.
  - **It remains a genuine judgment ⇒ user decision #4.**
- **Grok and Gemini:** all ACCEPT, "no decision-changing flaw". Both ran the arithmetic correctly;
  neither probed K2. Grok's "K2 cannot manufacture a false PASS" is true, and misses the false
  KILL.

## Cosmetic (to fix in v3.1)

- cl. 3 ("R_day = 0") vs cl. 7 ("never entered") for a suspended MIS slot (Claude).
- Pin N_prior = 20 to the programme ledger (A3) (Claude).
- Define "the bases agree" (|A−1| < 2%). The facts script's "one-day mismatches (0.3–2%): 809"
  label is wrong: most are dividend-adjustment offsets.
- The simulation splits K4 by index, not the dated halves.
- Add the K2 cross-section model, the two-branch rows and the expiry rows to
  `scripts/pr1_decision_oc.py`.

## Arithmetic

ChatGPT, DeepSeek, Grok, Gemini and Claude all reproduced §5 and §6 (MATCH). The four that ran
Appendix B got 0.5 / 47.5 and 10.2 / 90.7, the same as each other and consistent with §7.

## Scorecard (round 2)

| reviewer | decision-changing | material | wrong / refuted | note |
|---|--:|--:|--:|---|
| **Claude chat** | **1** (K2, simulated) | 3 (M1, M2, M4) | 0 | best again; ran code; sharp requests |
| **ChatGPT** | 1 (K2, row 6, unquantified) | 2 (M3, M4) | 0 | ran Appendix B |
| **DeepSeek** | 0 | 1 (M2) | 1 (K3-expiry) | re-raised row 13 |
| **Kimi** | 1 (K2, flagged blind) | — | 1 (its row-2 premise) | reviewed without the document |
| **Gemini** | 0 | 0 | 0 | arithmetic only |
| **Grok** | 0 | 0 | 0 | rubber stamp |

## Recommendation

**No further external rounds.**
- The remaining changes are specified fixes, each already verified by simulation or measurement.
- **Next:** v3.1 (the freeze candidate):
  - K2 on the lower half;
  - the basis-step night-drop;
  - the §5 mean-spread evidence;
  - the PR-2 translation committed with PR-1;
  - the §9 power wording;
  - the cosmetics.
- Then extend the OC script, run one internal `quant-verifier` pass on the diff, get the user's
  four decisions, and commit.
