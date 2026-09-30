# Prompt — PR-1 draft v3 verification round (paste this, then attach the v3 extract)

Attach: `docs/analysis/pr1-preregistration-extract-v3-2026-09-30.md`.
Send to: a fresh Claude chat, Kimi, ChatGPT (optionally DeepSeek). Skip Grok. For Gemini, send
fresh: the reply pasted for Gemini in round 1 was ChatGPT's text, word for word.

---

I'm asking you for ONE careful, critical **verification** of a revised pre-registered research
design. The design document (draft v3) is attached. Please read all of it before answering.

WHO AND WHAT
I'm a solo retail trader-developer building a research and paper-trading system for Indian
equities (NSE). The document describes a study (PR-1) that has NOT been run. It tests one idea:
stocks pushed down hardest in the last minutes of the trading day, relative to their peers,
rebound afterwards. The proposed reason is liquidity provision: index funds, derivative settlement
and fund NAVs force some traders to trade at the closing price, and whoever takes the other side
is paid when that pressure reverses.

WHY THIS ROUND EXISTS
- About 20 earlier strategy ideas were tested and rejected, so the bar is deliberately strict: a
  deflated-Sharpe hurdle of about t ≥ 3.6.
- The design is pre-registered. Its text is frozen and committed BEFORE any analysis code is
  written; the study then runs exactly once, and its PASS/KILL/NULL rule is applied mechanically.
- A first outside review (five reviewers) and an internal quantitative review found three
  defects that would each have decided the result on their own:
  - the 5-minute price history is back-adjusted for corporate actions, while the exchange's daily
    file is not. Two returns divided one source by the other, so they measured the adjustment
    factor, not the market. The two sources disagree by more than 2% on 22.5% of name-days;
  - the overnight return was measured from a 30-minute VWAP close, while the signal ends at the
    last trade. That built in a measured drag of about −64 bps against ~35 bps of costs;
  - a concentration kill fired on ~99% of genuine passes, which quietly raised the bar to t ≈ 6.3.
- Draft v3 fixes these and about a dozen smaller items. **Section 0 lists every change.** The
  price-basis defect was invisible from the design text. If you can think of another way the
  DATA could quietly contradict the text, that is the most useful thing you could find.
- **This is the LAST external round.** After it, only arithmetic corrections are made, then the
  text is frozen. A flaw you find now can still be fixed; later it cannot.

WHAT I NEED FROM YOU — the four questions at the top of the document
1. For EACH row of §0: ACCEPT, AMEND or REJECT, with one line of reason for anything but ACCEPT.
   Does the fix work? Does it introduce a new problem?
2. Recompute §5 (costs) and §6 (the bar), and check the logic of §7 (a simulation of the decision
   rule; the code is in Appendix B — run it if you can). Show your arithmetic and say MATCH or
   MISMATCH. The fee model rounds each leg to the paisa, so a ₹0.01 difference is not a mismatch.
3. ONE remaining flaw that would change PASS, KILL or NULL and is NOT already in §0 or §10. One
   well-argued item is better than a list. "None" is a valid answer.
4. (Optional) §9: is a single-test bar on fresh forward data sound for the follow-up study, given
   that PR-1 selected the hypothesis? If not, what bar, and why?

CONTEXT NOT IN THE DOCUMENT (curated, so you don't have to guess)
- Account: about ₹1 lakh at Zerodha, 3–5 positions. A cash-market short cannot be held overnight,
  so the overnight version is long-only; intraday (MIS) shorts are allowed. Intraday positions in
  auction stocks are squared off by the broker at 15:12 IST.
- Market-structure change: since 3 Aug 2026, NSE sets the close of F&O stocks by a call auction.
  Before that, the close was the VWAP of the last 30 minutes. PR-1 uses the OLD regime as
  mechanism evidence only. A separate forward study (PR-2) will test the auction regime on
  sessions collected since August 2026, which nobody has looked at.
- Everything in §8 was measured from same-session prices, session dates and synthetic series. No
  return, IC or outcome from the test window has been computed by anyone.

WHAT NOT TO DO
- Don't predict whether this will be profitable, and don't propose different strategies.
- Don't re-raise an item marked NOT ADOPTED in §0 unless you bring a new argument or a number.
- Don't cite papers, circulars or numbers you haven't actually read. If you cite something, give
  the title and section or table. If unsure, say "unsure".
- No generic advice ("use more data", "beware overfitting") unless it is tied to a specific
  clause and a specific failure.

IF YOU NEED MORE INFORMATION
List your requests at the TOP of your reply, then answer everything you can without them. I can
supply design-level facts: per-session cohort counts, coverage statistics, the fee-model code, the
exact statistical code, how the half-spread was estimated, and exchange rules with sources. I will
NOT share outcome data (returns, or any signal-versus-return statistic from the test window),
because that would break the pre-registration.

REPLY FORMAT
- Number your answers 1–4.
- For 1: a table with columns row # · ACCEPT/AMEND/REJECT · one line.
- For 2: the full arithmetic.
- For 3 and 4, per point: the issue in one line · the clause (section 4 numbers) · the mechanism ·
  the direction of the bias (flatters or hurts) · how to detect or fix it within this design ·
  severity (would it change PASS, KILL or NULL, or is it cosmetic?) · your confidence.
