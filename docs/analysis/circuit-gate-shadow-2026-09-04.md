# Circuit-gate shadow (live paper entries) — 2026-09-04

_Read-only. What the circuit overlay WOULD suppress on the live paper-entry cohort since 2026-07-19: entries within the proximity threshold of the ADVERSE circuit band (long→lower, short→upper). SHADOW: nothing is suppressed. (Mode as of report time, effective 2026-08-17 — the cohort below may span an earlier period under a DIFFERENT mode; check the changelog before reading a suppressed-set number as counterfactual.) A net-POSITIVE blocked set means the heuristic is killing good trades — do not flip to active._

- entries evaluated: **63** (with a live band: 63; no band / fail-open: 0)
- would-block entries: **0** across **0** blocked signal(s) · resolved trades: 0
- blocked set realized P&L: — (none resolved yet)

**Flip readiness:** ⏳ NOT READY — 0/20 resolved blocked trades — keep accruing. Flipping to active also requires explicit user sign-off (behaviour-changing, reversible via `circuit_gate_mode=shadow`).


### Evidence of record — circuit-band gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 0 | 0 | — | — | — | — |
| eligible (kept) | 0 | 0 | — | — | — | — |

**Shared guards:**
- ✅ `side_proxy` — one side of the partition is empty — not assessable
- ✅ `tail` — only 0 resolved would-block trades — not assessable
- ✅ `win_rate` — a side of the partition has no resolved trades

- **deflated Sharpe:** no resolved eligible trades yet

