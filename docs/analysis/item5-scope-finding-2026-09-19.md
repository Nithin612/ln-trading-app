# Item 5's CA scope is ~75× larger than the queue records (2026-09-19)

Measured while preparing the E2 re-run. Three blockers dissolved under measurement tonight;
this is the fourth measurement and it goes the other way.

## What §13.8 says

> **5** — Re-run E2. Needs **14** and **21**. ⭐ **No longer blocked on 16 (Grok):** exclude
> the three named corporate actions **by dated list** — IRCTC 1:5, BAJAJFINSV 1:1 bonus +
> 1:5, PEL demerger. Window **797, DECIDED**.

## ⛔⛔ What is actually true

**The three named CAs are all in HOLDOUT-1, and none is in the test block.** Detected the way
the docs detect them — `open` against the previous `close`, not close-to-close, which is why an
earlier pass found none:

| symbol | date | prev close | open | gap | block |
|---|---|--:|--:|--:|---|
| IRCTC | 2021-10-28 | 4,130.15 | 817.00 | −80.2% | **holdout-1** |
| PEL | 2022-08-30 | 1,926.50 | 1,055.05 | −45.2% | **holdout-1** |
| BAJAJFINSV | 2022-09-13 | 17,138.05 | 1,755.00 | −89.8% | **holdout-1** |

⇒ **the dated list the queue specifies is EMPTY for the window item 5 runs on.**

**And the test block's own liquid pool holds 225 such events, not 3.** Restricting to names with
≥200 sessions and median daily traded value ≥ ₹5cr — the pool the top-250 cohort is drawn from
— there are **225** `|open ÷ prev close − 1| > 25%` events in 2023-07-03 → today. Many are
unmistakable splits on the largest names in the book:

| symbol | date | prev close | open | gap |
|---|---|--:|--:|--:|
| NESTLEIND | 2024-01-05 | 27,116.40 | 2,754.00 | −89.8% (1:10) |
| BAJFINANCE | 2025-06-16 | 9,331.00 | 956.00 | −89.8% (1:10) |
| TATAINVEST | 2025-10-14 | 9,922.00 | 1,042.00 | −89.5% |
| ANGELONE | 2026-02-26 | 2,489.90 | 251.00 | −89.9% |

**The queue's "exclude three by dated list" is not a workable plan for this window.** It was
scoped from M70's *"of 8 flagged events, 3 are corporate actions"* — but those 8 were counted
over a span that includes the holdouts, not over the test block alone.

## ⭐ The one thing that makes this tractable — and it is estimand-specific

**3a is a SPEARMAN rank correlation.** A split-induced −90% return only makes a name rank LAST
on its session; the magnitude never enters. One corrupted rank out of ~250 names, on 225 of
~160 decision sessions, is a bounded and small distortion. **3a is largely robust to this.**

**3b is a MEAN forward-return contrast, and is not.** A single −89.8% in either arm moves the
mean by roughly `0.9 / n`, which on a few hundred matched pairs is enormous. **3b cannot be run
credibly until these are handled.**

⇒ **The estimands have DIFFERENT CA requirements, and the queue treats them as one item.**

## What I recommend

1. **Run 3a now.** It is the estimand the decision reads (§13.8 item 19 keys off the point
   estimate), it is rank-based, and the contamination is bounded. Report the 225 events as a
   stated limitation with the robustness check: re-run 3a with those name-days dropped and show
   the IC barely moves. If it moves, that is itself the finding.
2. **Hold 3b** until the CA set is resolved — which is **item 16** (CA policy via the external
   NSE source), currently in Tier B. ⇒ **item 16 is a real precondition for 3b, and the queue's
   claim that item 5 is "no longer blocked on 16" is only true of 3a.**
3. **Do NOT blanket-drop all 225.** M70 measured the 25% screen at **62.5% false-positive** (5 of
   8 flagged events were genuine moves — ZEEL ×2, IDEA, ADANIENT ×2). Dropping real moves
   deletes the most informative sessions. The screen is a *candidate generator*, not a detector
   — the standing rule is that a predicate encoding an external authority must be a **cache of
   its answers**, not a rule you evaluate.
