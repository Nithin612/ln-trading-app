# Exit / giveback study — in R, not ₹ (2026-09-07)

**95 closed paper positions** with a recoverable commit stop and a
peak-excursion mark. Everything below is normalised by **R = |entry − commit_SL| ×
qty**, because the ₹ version of this analysis gives the opposite answer.

## ⚠ The correction this study exists to record

It was commissioned on the reading that *25 of 30 stop-outs had been in profit and
gave it all back, for −₹59,785* — an apparent exit defect.

**In ₹ that is what it looks like. In R it evaporates.** The `sl_hit` group's average
peak of +₹1,229 is, against the risk actually taken, approximately **zero**. Those
trades were never meaningfully in profit — they wobbled a few hundred rupees above
entry on positions whose 1R was thousands.

This is the project's own standing rule, broken by the person who wrote it: *measure
in R, never ₹, because risk-first sizing makes ₹ incomparable across trades.*

## Where the money actually is

| peak bucket | n | avg peak R | avg realised R | total R | total ₹ | capture |
|---|--:|--:|--:|--:|--:|--:|
| **peak < 0.25R — never worked** | 35 | 0.02 | -0.72 | -25.3R | ₹-56,472 | — (no peak) |
| **peak 0.25–0.5R** | 15 | 0.37 | -0.35 | -5.3R | ₹-10,037 | — (no peak) |
| **peak 0.5–1R** | 18 | 0.73 | +0.33 | +5.9R | ₹13,856 | 45% |
| **peak 1–2R** | 24 | 1.31 | +0.86 | +20.7R | ₹47,771 | 66% |
| **peak ≥ 2R** | 3 | 2.60 | +1.69 | +5.1R | ₹9,997 | 65% |

## Verdict

⭐ **50 of 95 trades (53%) never reached 0.5R**, and they account for **₹-66,509** (-30.6R). **No exit rule can touch these** — there was never a profit to protect.

⭐ **The 45 trades that DID work kept most of their move**: 31.7R realised of a 52.4R combined peak = **60% capture**, and capture is roughly flat across buckets rather than collapsing on the big winners.

⭐ **The entire addressable pool for a better exit is 20.8R** — the total giveback on trades that got into profit, most of which is irreducible (nothing exits at the exact peak). Set that against the 30.6R lost by trades that never worked.

**⇒ This is NOT an exit problem. The exit machinery is working.** It is the same
diagnosis CLAUDE.md recorded months ago on 15 trades — *"the exit machinery was
correct but had nothing to protect"* — now confirmed on 95.

**The loss is made at ENTRY.**

## ⚠ And the ratchet does NOT explain the difference

An earlier pass split on *did the stop move* and found +₹43,395 versus −₹42,301,
which looks like proof the ratchet works. **It is a proxy.** The profit-lock ladder
only arms once a trade is up, so `stop moved` ≈ `trade went into profit`. Peak R
confirms it: 1.63R average peak for moved versus 0.41R for unchanged.

Controlling for peak R, the difference disappears:

| peak bucket | stop moved | n | avg realised R |
|---|---|--:|--:|
| peak < 0.25R — never worked | no | 34 | -0.738 |
| peak 0.25–0.5R | no | 15 | -0.350 |
| peak 0.5–1R | no | 17 | +0.306 |
| peak 1–2R | no | 7 | +0.941 |
| peak 1–2R | yes | 17 | +0.830 |
| peak ≥ 2R | yes | 3 | +1.690 |

Within a peak bucket, moving the stop made **no measurable difference**. That is the
partition-is-a-proxy trap the market-regime gate already taught, where the partition
turned out to be a proxy for *side*.

## ⚠ Limits

- **n = 95**, one broad regime, ~2 months of entries.
- **1 position(s) excluded** for a non-positive risk distance (a  stop on the wrong side of the fill). Excluded and counted, never `abs()`-ed  into a plausible-looking tiny R — that is how a −3.09R artefact was born.
- **`peak_pnl` is updated on live monitor ticks**, so it is only as complete as the
  monitor's uptime — a peak reached while the worker was down is not recorded, which
  biases peaks DOWNWARD and would, if anything, understate giveback.
- **Capture is undefined for a ~zero peak** and is reported as `—` rather than as the
  large negative artefact that dividing by a near-zero peak produces.
