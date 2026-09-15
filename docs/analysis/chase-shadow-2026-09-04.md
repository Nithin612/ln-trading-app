# Anti-chase shadow (live signals) — 2026-09-04

_Read-only. The anti-chase overlay recomputed over the tradeable signal cohort since 2026-07-19 (559 signals), each judged on how far past its entry the order actually filled (chase_r = R past entry; the gate's own stamp when present, else the broker's post-fill telemetry). Gate mode: **shadow**. 'chased' = chase_r above the 0.33R ceiling — the reward:risk you were shown is materially gone. A would-block set net-negative AND worse than the near-entry set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| CHASED (> 0.33R past entry, would-block) | 4 | 4 | ₹-12,755 | ₹-3,189 | 0% |
| near entry (eligible) | 87 | 55 | ₹9,567 | ₹174 | 55% |
| no data (no chase stamp) | 468 | 36 | ₹-8,564 | ₹-238 | 47% |

**anti-chase flip readiness:** ⏳ NOT READY — 4/20 resolved chased trades (> 0.33R past entry) — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + explicit user sign-off (reversible via `chase_gate_mode=shadow`).


### Evidence of record — anti-chase gate

_The numbers behind the verdict, so it can be re-judged later. `trimmed mean` drops the worst 10% of outcomes: if the sign changes there, the signal is tail-driven._

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 4 | 4 | ₹-3,189 | ₹-3,304 | ₹-3,064 | 0% |
| eligible (kept) | 87 | 55 | ₹174 | ₹237 | ₹616 | 55% |

**Shared guards:**
- ✅ `side_proxy` — the partition is not explained by side alone
- ✅ `tail` — the would-block set stays net-negative after trimming the tail
- ✅ `win_rate` — would-block win rate 0% ≤ eligible 55%

- **eligible set (the book a flip would leave you holding) — deflated Sharpe bar:** ⏳ does NOT clear — observed Sharpe +0.075 does not exceed the 20-trial benchmark +0.256 — more data cannot rescue it; the candidate is not ahead
  - n=55 · mean +173.9525 · sd 2323.3034 · **Sharpe +0.075** · skew +0.24 · kurtosis 3.23
  - P(true Sharpe > 0) = 71.0% · **after deflating for 20 trials: 9.0%** (bar 95%)
  - ⚠ trials are treated as INDEPENDENT; ours overlap (same book, shared cohorts), so the true deflation is WORSE than shown — this number is optimistic.

## Per-entry context (each committed signal's chase)

| date | stock | side | chase_r | verdict | outcome |
|---|---|---|--:|---|--:|
| 2026-09-03 | TCS | SHORT | -0.063R | ✅ near entry | open/none |
| 2026-09-01 | FUSION | SHORT | -0.136R | ✅ near entry | open/none |
| 2026-09-01 | MUKANDLTD | SHORT | +0.148R | ✅ near entry | open/none |
| 2026-09-01 | MAHLOG | SHORT | -0.013R | ✅ near entry | open/none |
| 2026-08-31 | NOCIL | LONG | -0.063R | ✅ near entry | open/none |
| 2026-08-31 | SUPREMEIND | SHORT | +0.147R | ✅ near entry | open/none |
| 2026-08-31 | SHRINGARMS | SHORT | +0.015R | ✅ near entry | open/none |
| 2026-08-31 | NOCIL | LONG | +0.164R | ✅ near entry | open/none |
| 2026-08-28 | PIDILITIND | SHORT | +0.081R | ✅ near entry | open/none |
| 2026-08-27 | BLIL | LONG | -0.071R | ✅ near entry | open/none |
| 2026-08-27 | VRLLOG | LONG | +0.111R | ✅ near entry | open/none |
| 2026-08-27 | PREMIERENE | LONG | +0.181R | ✅ near entry | open/none |
| 2026-08-26 | IDBI | LONG | +0.023R | ✅ near entry | ₹-2,331 |
| 2026-08-26 | KIRIINDUS | LONG | -0.099R | ✅ near entry | open/none |
| 2026-08-26 | GPPL | LONG | +0.133R | ✅ near entry | open/none |
| 2026-08-26 | BOSCH-HCIL | LONG | +0.092R | ✅ near entry | ₹1,751 |
| 2026-08-26 | RELTD | LONG | +0.513R | 🚫 chased | ₹-3,137 |
| 2026-08-26 | LOVABLE | LONG | +0.000R | ✅ near entry | open/none |
| 2026-08-26 | KIRIINDUS | LONG | -0.051R | ✅ near entry | ₹6,621 |
| 2026-08-26 | ORKLAINDIA | LONG | +0.031R | ✅ near entry | ₹1,303 |
| 2026-08-25 | BAJAJHLDNG | LONG | -0.089R | ✅ near entry | open/none |
| 2026-08-25 | CDSL | LONG | +0.088R | ✅ near entry | open/none |
| 2026-08-25 | MOSCHIP | SHORT | -0.112R | ✅ near entry | ₹-2,719 |
| 2026-08-25 | GLOBUSSPR | LONG | -0.078R | ✅ near entry | open/none |
| 2026-08-25 | GOKULAGRO | LONG | +0.068R | ✅ near entry | ₹-2,239 |
| 2026-08-25 | BVCL | LONG | +0.144R | ✅ near entry | open/none |
| 2026-08-25 | PRIMESECU | LONG | -0.047R | ✅ near entry | ₹2,440 |
| 2026-08-25 | ENRIN | SHORT | +0.084R | ✅ near entry | ₹1,199 |
| 2026-08-25 | KSB | LONG | +0.114R | ✅ near entry | ₹-409 |
| 2026-08-24 | AJAXENGG | LONG | +0.100R | ✅ near entry | open/none |
| 2026-08-24 | 20MICRONS | LONG | -0.109R | ✅ near entry | ₹832 |
| 2026-08-24 | DVL | LONG | -0.036R | ✅ near entry | open/none |
| 2026-08-24 | EMKAY | LONG | -0.065R | ✅ near entry | ₹1,511 |
| 2026-08-24 | AJAXENGG | LONG | -0.436R | ✅ near entry | ₹-3,451 |
| 2026-08-24 | CGPOWER | LONG | -0.081R | ✅ near entry | open/none |
| 2026-08-24 | ADROITINFO | LONG | +0.000R | ✅ near entry | open/none |
| 2026-08-24 | ALGOQUANT | LONG | +0.229R | ✅ near entry | ₹-2,193 |
| 2026-08-21 | BENGALASM | LONG | -0.036R | ✅ near entry | ₹2,775 |
| 2026-08-17 | SOUTHBANK | SHORT | -0.057R | ✅ near entry | open/none |
| 2026-08-14 | BPCL | LONG | +0.110R | ✅ near entry | ₹-5,076 |
| 2026-08-14 | HATSUN | LONG | -0.038R | ✅ near entry | ₹6,017 |
| 2026-08-14 | RELIABLE | SHORT | +0.072R | ✅ near entry | open/none |
| 2026-08-14 | PREMIERENE | SHORT | -0.090R | ✅ near entry | ₹-2,257 |
| 2026-08-14 | LEMERITE | SHORT | +0.317R | ✅ near entry | ₹1,279 |
| 2026-08-14 | KSL | SHORT | +0.097R | ✅ near entry | ₹-2,278 |
| 2026-08-14 | BPCL | LONG | -0.590R | ✅ near entry | open/none |
| 2026-08-14 | CGCL | LONG | +0.079R | ✅ near entry | ₹2,850 |
| 2026-08-13 | TEJASNET | LONG | +0.091R | ✅ near entry | open/none |
| 2026-08-13 | GRSE | LONG | +0.102R | ✅ near entry | ₹-1,996 |
| 2026-08-13 | SMARTWORKS | LONG | +0.088R | ✅ near entry | ₹163 |

_… 41 more assessable signals not shown._

