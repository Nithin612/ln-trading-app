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

### ⭐⭐ CAPTURED 2026-09-20 — the ordering on GITHUB'S OWN CLOCK

The table above is our clock. This is theirs, from `/repos/.../events`, and it does not depend
on any timestamp we control:

| push | GitHub `created_at` (UTC) | |
|---|---|---|
| head `3a0d73c` — **carried the criterion** `c117969` | **2026-09-18 18:52:34** | |
| head `94a11de` — carried **3a** `8e7e4fa` | 2026-09-19 07:16:06 | **+12.4 h** |
| head `812389e` — **3b** | 2026-09-19 17:07:19 | **+22.2 h** |

Ancestry verified locally: `c117969` is an ancestor of `3a0d73c`, `8e7e4fa` of `94a11de`.

⚠ **This evidence had a 90-day clock and no longer does.** GitHub's Events API retains events
for roughly 90 days, so by March this query would have returned nothing. The raw response is
therefore committed at `docs/analysis/provenance/github-events-raw-2026-09-20.json` — and
because *that commit* is itself pushed to GitHub with its own push event, the evidence is now
part of immutable history rather than a lookup that expires.

⭐ If a stronger artifact is ever wanted, a **GitHub release or tag on `c117969`** carries a
`created_at` on GitHub's clock and is retained indefinitely. Not created here: it is a visible
repository artifact and that is the user's call.

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
2. ⛔ **CORRECTED — the direction was wrong as first written.** "Record the commit hash in the
   criterion itself" **cannot work**: a commit cannot contain its own hash. **Invert it — the
   MEASUREMENT commit names the CRITERION's hash.** That direction is well-formed, and it is
   also stronger: the measurement artifact then points back at a fixed prior commitment,
   instead of the record having to vouch for both ends. (Applied retroactively here: `8e7e4fa`
   and `812389e` measure against criterion **`c117969`**.)
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

⭐ **Internal consistency check, worth having:** both flip thresholds back out to the same
implied current cost — `6.76 ÷ (0.0083/0.0313) = 25.49` and `16.14 ÷ (0.1614/0.255) = 25.50`
— which is the 25.5 bps the script hardcodes. The two estimands agree about what they are
priced against. Against the 22.22 floor, the **largest cost error available is a 12.9%
reduction**, versus the **73%** and **37%** the two flips require.

⭐⭐ **AND 3a IS STRONGER THAN THE FLOOR ARGUMENT MAKES IT LOOK.** Those are
interval-upper-bound thresholds, and **3a's POINT ESTIMATE IS NEGATIVE (−0.0055)**. Costs can
drive break-even toward zero; they can never drive it **below** zero. So no cost reduction, of
any magnitude, makes a negative IC clear a non-negative break-even. **Under the three-branch
table 3a is cost-proof outright, with nothing riding on the statutory floor at all.** The floor
argument is only load-bearing for 3b.

⛔⛔ **DO NOT GENERALISE THE 22.22 bps FLOOR. It is a DELIVERY round trip.** STT at 10 bps a
side is most of it. **Intraday STT is sell-side only at 2.5 bps**, so the floor collapses to a
few bps — and every conclusion resting on it collapses with it. **If a successor ever runs
intraday, this must be RECOMPUTED, never inherited.**

### ⚠ The two halves of this question cost very different amounts to close

They are usually spoken of as one thing. They are not, and a successor reading this should not
take its numbers as cleaner than they are:

| half | what closes it | cost |
|---|---|---|
| **`fees.py` reconciliation** | ONE real contract note — and Zerodha's **published charges breakdown gets most of the way with no trading at all** | **cheap, closeable now** |
| **fill / slippage calibration** | real broker fills compared trade-for-trade against what the model predicted | **cannot be closed without live orders — open until deployment** |

⇒ A successor can have a **verified charge model** early and will carry an **unverified fill
model** until it actually trades. Any pre-deployment cost figure it quotes is therefore part
measured and part modelled, and should say which is which.

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
