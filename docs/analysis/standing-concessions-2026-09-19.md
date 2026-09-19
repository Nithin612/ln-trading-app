# The three standing concessions, enumerated (item 23)

⛔ **Why this file exists.** §13.8 item 23 has said *"the three standing concessions,
enumerated"* for several rounds, and **M78 measured them at 0 / 0 / 0 — they appeared in no
queue section at all.** A concession nobody can name is not a concession, it is an
unexamined assumption with a reassuring label. The doc even carried the phrase *"concession
in PARTS 7–8"* with a falsifier attached, and the falsifier was never run against it.

Each is stated as: **what is conceded · why · what it costs, measured where it can be ·
what would close it.** A concession without a closing condition is a permanent excuse.

---

## 1. Portfolio-level evaluation — we have none

**Conceded:** every result in this programme is **per-trade**. Mean R, IC, the delete
treatment, the hazard curve, item 5's null — all of it evaluates trades one at a time.
Nothing evaluates the **book**.

**Why:** the corpus is a sampler of independent entries, and the live book (₹1 lakh, 1–2
positions) is not the book the sampler represents. Building a portfolio replay before knowing
whether any signal has edge would have been the wrong order.

**What it costs, measured:**
- The two portfolio rails that exist — the **6% heat cap** and the **max-3 position cap** —
  were chosen from *friction arithmetic* (M77: delivery friction crosses 30 bps between 5 and
  6 positions), **not** from any portfolio evaluation. They are cost-motivated rails wearing
  risk-control clothing.
- Every σ used anywhere is a **per-trade** σ. Portfolio σ needs average pairwise correlation,
  and round 7 measured ρ̄ ≈ **+0.19** long-only after finding the earlier ρ̄ ≈ 0 was a
  directional-cancellation artifact. Nothing downstream uses that number.
- The heat counterfactual came closest and stopped short: it replayed entries against a cap
  and reported **capped −₹13,303 vs full −₹19,093**, but per-trade **−₹1,478 vs −₹796** ⇒ a
  risk control, not a profitability fix. It answered "what does the cap do to totals", never
  "what is the book's risk".

**Closes when:** a replay evaluates concurrent positions jointly — correlation, overlapping
exposure, sequencing — rather than summing independent trades. ⚠ Not worth building until
there is a generator worth running a portfolio of.

---

## 2. `entry_diversity`'s incremental effect — the one gate we run is the one we never tested

**Conceded:** `entry_diversity` is the only ACTIVE order-path gate that selects on the
signal's own content. It is **explicitly exempt** from the t ≈ 3.6 promotion bar, on the
argument that it enforces a *stated hard rule* — SIGNAL_ENGINE.md's "≥2 factors, never a
single indicator" — rather than a claimed edge. **Its incremental effect has never been
measured.**

**Why:** the exemption is defensible. It is the same class of rule as the settlement
restriction shipped 2026-09-19: a constraint the system declares, not a bet on the tape.

**What it costs, measured on the live book (52 signals):**

| | refused |
|---|--:|
| fewer than 2 scoring factors | **7** |
| one factor > 90% of scoring weight | **0** |
| **total** | **7 of 52 (13.5%)** |

⭐ **Half the gate has never fired.** The dominance clause — the half aimed at the SRTL
archetype, a single 0.8 factor reading 80% and clearing the ≥70% gate — has refused **nothing**
on this book. The "<2 factors" clause does all the work.

⚠ **And the precedent is not comforting.** The R:R ≥ 1 floor was also promoted on an identity
argument needing no evidence, and was refuted within a week: it had been blocking the book's
only profitable cohort. `entry_diversity` may well be right — but "it enforces a rule" is what
was said about R:R too.

**Closes when:** the refused cohort's outcomes are compared with the admitted cohort's. That
needs the refused signals **minted and tracked rather than discarded** — i.e. running the gate
in shadow alongside active, which nothing currently does.

---

## 3. Live-vs-modelled fill calibration — the fill model has never met a real fill

**Conceded:** the paper fill model is elaborate — real half-spread from the depth book, a
`k × participation²` impact term calibrated to zipline, directional tick rounding on a dated
tick grid, marks routed through the same model as fills. **Not one component has been
compared against a fill from a real broker.**

**Why:** live trading does not exist. `place_order` is paper-only with no Kite order path, so
there has never been a real fill to compare against.

**What it costs, measured:**
- M92 attributed the four-short loss using `half_spread_bps` of **0.36–2.22** against
  displacement of **27–58 bps** — and concluded the mechanism was signal staleness, not
  spread. That conclusion rests on a **modelled** half-spread being roughly right. It is
  probably fine; it is not verified.
- 6.8.2 measured that **82% of live NSE books have a half-spread wider than the flat 2 bps**,
  which is why paper P&L before and after 2026-08-17 is non-comparable. That measurement is of
  the *book*, not of *our fills against it*.

⚠ **Distinct from item 21**, and the two get conflated. Item 21 reconciles **charges** — the
brokerage/STT/DP stack, a published schedule. This concession is about the **fill price**,
which no schedule can settle.

**Closes when:** Phase 7 produces real fills and they are compared, trade for trade, against
what the model would have predicted. ⚠ Until then every bps figure in this programme inherits
it, including item 5's break-even.

---

## What these three have in common

All three are places where **a number is used as though it were measured, when what was
measured is something adjacent.** Portfolio risk stands in for per-trade risk; a stated rule
stands in for a tested one; a modelled fill stands in for a real one. That is the same family
as the defects this project keeps finding in its own instruments — a measure that cannot
distinguish the thing it reports from something else — and it is why they are worth naming
rather than carrying silently.

⭐ **None of the three blocks anything today.** They are recorded so that a future result which
*depends* on one of them cannot be stated without it.
