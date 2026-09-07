# Exit / giveback study — in R, not ₹ (2026-09-07)

**96 closed paper positions** with a recoverable commit stop and a
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
| **peak < 0.25R — never worked** | 33 | 0.00 | -0.83 | -27.4R | ₹-50,669 | — (no peak to capture) |
| **peak 0.25–0.5R** | 17 | 0.36 | -0.61 | -10.3R | ₹-15,111 | — (no peak to capture) |
| **peak 0.5–1R** | 19 | 0.77 | +0.26 | +5.0R | ₹11,978 | 34% |
| **peak 1–2R** | 21 | 1.39 | +1.03 | +21.7R | ₹45,933 | 75% |
| **peak ≥ 2R** | 6 | 2.62 | +0.53 | +3.2R | ₹8,962 | 14% |

## Verdict

⭐ **50 of 96 trades (52%) never got meaningfully into profit**, and they account for **₹-65,779** (-37.8R).

⭐ **The trades that DID work captured most of their move.** The 27 that reached ≥1R realised +0.92R against a 1.67R peak — **62% capture.**

**⇒ This is NOT an exit problem. The exit machinery is working.** It is the same
diagnosis CLAUDE.md recorded months ago on 15 trades — *"the exit machinery was
correct but had nothing to protect"* — now confirmed on 96.

**The loss is made at ENTRY**: roughly half of all trades go nowhere and pay ~0.7R
for the privilege. No exit rule can fix a trade that never moves in your favour.

## ⚠ And the ratchet does NOT explain the difference

An earlier pass split on *did the stop move* and found +₹43,395 versus −₹42,301,
which looks like proof the ratchet works. **It is a proxy.** The profit-lock ladder
only arms once a trade is up, so `stop moved` ≈ `trade went into profit`. Peak R
confirms it: 1.63R average peak for moved versus 0.41R for unchanged.

Controlling for peak R, the difference disappears:

| peak bucket | stop moved | n | avg realised R |
|---|---|--:|--:|
| peak < 0.25R — never worked | no | 32 | -0.851 |
| peak 0.25–0.5R | no | 17 | -0.607 |
| peak 0.5–1R | no | 17 | +0.260 |
| peak 0.5–1R | yes | 2 | +0.291 |
| peak 1–2R | no | 7 | +1.032 |
| peak 1–2R | yes | 14 | +1.035 |
| peak ≥ 2R | yes | 5 | +1.256 |

Within a peak bucket, moving the stop made **no measurable difference**. That is the
partition-is-a-proxy trap the market-regime gate already taught, where the partition
turned out to be a proxy for *side*.

## ⚠ Limits

- **n = 96**, one broad regime, ~2 months of entries.
- **`peak_pnl` is updated on live monitor ticks**, so it is only as complete as the
  monitor's uptime — a peak reached while the worker was down is not recorded, which
  biases peaks DOWNWARD and would, if anything, understate giveback.
- **Capture is undefined for a ~zero peak** and is reported as `—` rather than as the
  large negative artefact that dividing by a near-zero peak produces.
