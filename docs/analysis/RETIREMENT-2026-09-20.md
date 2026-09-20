# The daily-swing scorer is retired — item 19, accepted 2026-09-20

**Decision: the user accepted the retirement on 2026-09-20.** This document is the record.

## 1. What fired

| estimand | result | 90% CI | break-even | verdict |
|---|--:|---|--:|---|
| **3a** — unconditional IC, h=5d | **−0.0055** | [−0.0192, **+0.0083**] | 0.0313 | NULL |
| **3b** — matched-tail contrast | **−0.0885%** | [−0.3384, **+0.1614**] | +0.255% | NULL |

Both branches of item 19 fire independently:

- The **original** wording — *"if item 5 on 797, CA-screened and PIT-cohorted, returns a 90%
  upper bound below break-even, this daily-swing scorer is retired"* — fires on both estimands.
- The **Q30 third branch** — *point estimate < 0.0121 ⇒ retire* — fires at **−0.0055**, on the
  first branch rather than the ambiguous middle.

Measured on **31,378 panels across 156 sessions** (2023-07-03 → 2026-08-18), 403 distinct
names, a point-in-time cohort rebuilt monthly, corporate actions dropped by the **authority**
rather than by the 25% screen.

## 2. ⭐ Provenance — the criterion predates the measurement, and it is checkable

| event | commit | timestamp (IST) |
|---|---|---|
| Q30 third branch written | `c117969` | **2026-09-18 10:42:04** |
| 3a measured | `8e7e4fa` | 2026-09-19 12:26:46 — **+25.7 h** |
| 3b measured | `812389e` | 2026-09-19 18:10:46 — **+31.5 h** |

⭐⭐ **And `c117969` was already on GitHub before the measurement existed**: it is an ancestor
of `3a0d73c`, which was pushed in an earlier push. So the criterion was not merely written
first — it was **published** first, on a third-party server, before anyone could see the
result. Re-dating it now would require a force-push, which leaves traces.

### ⚠ The one gap, named rather than glossed

`c117969` is **unsigned** (`git log --format='%G?'` returns `N`). The ordering therefore rests
on git metadata plus the push, not on a cryptographic attestation.

⚠ **How much that actually matters: little, and it is worth being precise about why.** Signing
proves **WHO** authored a commit. The property under dispute in a pre-registration is **WHEN**.
A signed commit carrying a back-dated `--date` is still back-dated; signing does not fix
timing. What defends timing is publication to a third party, which happened.

**Process tightening for the next criterion** — the gap is real even if it did not bite here:

1. A kill criterion is **pushed in its own commit, before the run, and the push confirmed** —
   not batched with the work that follows it.
2. Record the pre-registration commit hash **in the criterion itself**, so the document names
   its own provenance rather than requiring archaeology.
3. If signing is ever set up (`--local` only — see the note in the Tier B plan), sign that one
   commit at minimum.

## 3. ⛔ The break-even assumption — logged as a SEPARATE open question, deliberately

**Dated 2026-09-20, AFTER the decision above, and explicitly excluded from it.**

The 0.0313 figure carries weight, and interrogating the cost and slippage model for NSE/BSE is
legitimate work. **Doing it now, after an unfavourable result, is precisely the move the
criterion exists to block.** So it is recorded here as an input to a successor's design, with
the sequence visible, and it is **not** a route back to the scorer.

**What the figure depends on:**

- `break-even IC = 25.5 bps ÷ (σ_cs 4.340% × E[z|selected] 1.8758)`
- ⚠ The **25.5 bps is HARDCODED** in `e2_score_ic.py` — it does not read `fees.py`.
- `fees.py` models **23.76 bps** round-trip on delivery, of which **22.22 bps is statutory**
  (STT alone is 20.00 bps = 84%).
- ⛔ `fees.py` has **never been reconciled against a real contract note** (M74 — M27 regressed
  it against its own output). That is item 21, still open.
- ⛔ The **fill model has never met a real fill** (standing concession 3). Half-spread,
  quadratic participation and directional tick rounding are all modelled.

**⭐ And the reason deferring it costs nothing — the retirement is ROBUST to it:**

| | costs would have to fall to | vs statutory floor |
|---|--:|---|
| flip 3a | **6.76 bps** | below 22.22 |
| flip 3b | **16.14 bps** | below 22.22 |

**Both thresholds sit below the statutory floor** — the STT, exchange transaction charge, SEBI
fee, GST and stamp duty that are published law and cannot be negotiated. **No error in our cost
model, of any size, can reach either verdict.** The only non-statutory line is the ₹15.34 DP
charge; zero it entirely and costs are still 22.22 bps.

⇒ The break-even question is **worth answering for the successor** and **cannot change this
decision**. Both things are true, and recording them together is the point.

## 4. What "retired" means, quoted not reinterpreted

> the scorer stops being a candidate · `entry_diversity` stays as the one hard rule · the 617-
> and 313-session blocks are preserved **unopened** for a successor generator · the harness stays

**Stops:** nightly signal generation on the frozen confluence engine as a strategy intended for
trading; the ≥70% gate as a filter worth keeping; any further tuning of this scorer.

**Continues, and was never about this scorer:** the append-only ledger · the two sealed
holdouts · `liquid_as_of` (point-in-time cohorts) · the authority corporate-action set · the
cluster-robust estimators · the delete treatment · the settlement restriction · the backup and
off-box machinery · `entry_diversity`, which enforces a stated rule rather than a measured edge.

**Stays shut:** both holdouts. They open only on the ≥0.0499 branch, which did not fire — and
the temptation to open them now, hoping for a kinder answer, is exactly what the third branch
was written to forbid.

## 5. Scope — what this is not

A verdict on **one generator**, on the 798-session test block, at **h = 5d**. It is not
evidence that no generator can work, and it is not a verdict on the platform. The holdouts were
preserved precisely so a successor can still be tested honestly — which is only possible
because they were never touched.

**The open problem is now a successor generator.** The apparatus to test one exists.
