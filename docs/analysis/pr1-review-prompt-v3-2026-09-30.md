# Prompt — PR-1 draft v3 verification round (the final external round)

**For you, the sender — not part of the prompt:**
- **Chat UIs (Claude, ChatGPT, Gemini, DeepSeek):** copy everything below the COPY line, then attach
  (or paste) `docs/analysis/pr1-preregistration-extract-v3-2026-09-30.md`.
- **API models with no memory (Kimi via NVIDIA NIM):** send ONE message containing the prompt and
  the full extract. The ready-made file is `docs/analysis/pr1-review-packet-v3-2026-09-30.md`.
  - Set max output tokens to ≥ 4,000 and a low temperature (≈ 0.2), or a careful reply gets cut
    off mid-table.
  - After editing either source, rebuild the packet:
    `sed '1,/^=== COPY EVERYTHING BELOW THIS LINE ===$/d' docs/analysis/pr1-review-prompt-v3-2026-09-30.md > docs/analysis/pr1-review-packet-v3-2026-09-30.md && cat docs/analysis/pr1-preregistration-extract-v3-2026-09-30.md >> docs/analysis/pr1-review-packet-v3-2026-09-30.md`
- **Send to:** a fresh Claude chat, Kimi and ChatGPT; DeepSeek optional; a fresh Gemini (round 1's
  "Gemini" reply was ChatGPT's text). Skip Grok.

=== COPY EVERYTHING BELOW THIS LINE ===

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
