# MCE slice 6 — news-veto feasibility (2026-09-07)

**Checked before building.** The phase doc specifies slice 6 as *earnings-blackout +
rating-DOWNGRADE veto + severity/decay*. Each clause assumes something about
`corporate_filings`; this checks the assumptions against the live table.

⚠ **Why check first:** a veto built on an assumption the data does not support does
not fail loudly. It silently never fires, and then *looks like protection* wherever
it is rendered.

**23,175 filings** on record.

| type | rows | first | last |
|---|--:|---|---|
| other | 20,280 | 2026-07-23 | 2026-09-07 |
| board_meeting | 2,182 | 2026-07-23 | 2026-09-04 |
| rating_change | 322 | 2026-07-23 | 2026-09-04 |
| merger | 208 | 2026-07-23 | 2026-09-07 |
| earnings | 117 | 2026-07-23 | 2026-09-04 |
| dividend | 64 | 2026-07-24 | 2026-09-02 |
| split | 2 | 2026-08-11 | 2026-08-12 |

## Precondition 1 — is rating DIRECTION recoverable?

- `rating_change` rows: **322**
- mention *upgrade*: **8**
- mention *downgrade*: **0**
- rows whose `body` is just a **URL**, not text: **322** of 322

**⛔ NOT satisfied.** The headline is a bare label (`Credit Rating`) and the body is a link to a PDF we do not parse, so the direction lives in a document we never read. A downgrade veto here would match **zero** rows — a gate that cannot fire.

## Precondition 2 — is earnings timing known IN ADVANCE?

| type | rows | `Outcome of…` (post-facto) | administrative |
|---|--:|--:|--:|
| earnings | 117 | 0 | 117 |
| board_meeting | 2,182 | 2,182 | 0 |

**⛔ NOT satisfied.** `board_meeting` rows are *Outcome of Board Meeting* — they report a meeting that already happened. `earnings` rows are *Clarification / Delayed submission* — administrative notes ABOUT results, not the results. There is no forward earnings calendar here, so a **blackout** (which must anticipate) cannot be built; only a cooldown (which reacts) can.

## Precondition 3 — do filings and signals ever COINCIDE?

- signals minted since filings began: **511**
- would be suppressed by the existing **1-hour** guard: **0**
- would be suppressed by a **3-day** window (72× wider): **4** (0.8%)

**⛔ NOT satisfied.** ⭐ **The existing event guard has never fired.** Not once, across every signal minted since the filings feed started. Widening the window 72× still reaches under 1% of signals. Whatever is losing money on this book, it is not signals minted next to a corporate filing.

## Verdict

⛔ **NONE of the three preconditions holds. DEFER slice 6.**

This is not 'the gate would be weak' — it is that two of its three clauses are
**unimplementable** from data we hold, and the third has nothing to act on:

1. the downgrade veto would match **0** rows;
2. the blackout has no forward earnings dates to blackout *against*;
3. the guard it extends has **never fired**.

**Building severity/decay on top of a gate that fires zero times is decoration.**
It would add a knob, a shadow sidecar and a line in the daily report, all
reporting on an event that does not occur — and every one of those surfaces
would read as protection.

### What would change this answer

- **A forward earnings calendar** (dates announced ahead), which makes a real
  blackout possible. Not in `corporate_filings`; needs a source.
- **Parsed rating documents**, or a feed carrying direction as a field.
- **More history** — this is ~6 weeks. Re-run this script as it deepens; the
  coincidence rate is the number to watch.

### On the RSS + FinBERT alternative (review item A18)

The external review proposed Google News RSS + FinBERT instead. That is a
**different and much larger** proposal than the phase doc's slice 6, and it needs
a decision rather than a build:

- **`transformers` + `torch` is a locked-stack change** (~2 GB, GPU-adjacent). The
  project's standing posture is 'adopt no new deps, stay lean'.
- **It adds a live external dependency** on the signal path — a third-party feed
  that can rate-limit, change shape, or go down.
- ⚠ **Precondition 3 still applies to it.** If corporate filings never coincide
  with our signals, the open question is whether *news* does — and that is
  measurable far more cheaply than by installing a language model.

**Recommended sequence:** answer the cheap question first (does adverse news
coincide with our entries at all?), and only then decide whether it justifies the
stack change.
