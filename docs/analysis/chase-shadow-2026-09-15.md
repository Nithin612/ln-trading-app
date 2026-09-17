# Anti-chase shadow (live signals) — 2026-09-15

_Read-only. The anti-chase overlay recomputed over the tradeable signal cohort since 2026-07-19 (38 signals), each judged on how far past its entry the order actually filled (chase_r = R past entry; the gate's own stamp when present, else the broker's post-fill telemetry). Gate mode: **shadow**. 'chased' = chase_r above the 0.33R ceiling — the reward:risk you were shown is materially gone. A would-block set net-negative AND worse than the near-entry set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| CHASED (> 0.33R past entry, would-block) | 0 | 0 | — | — | — |
| near entry (eligible) | 0 | 0 | — | — | — |
| no data (no chase stamp) | 38 | 0 | — | — | — |

**anti-chase flip readiness:** ⏳ NOT READY — 0/20 resolved chased trades (> 0.33R past entry) — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + explicit user sign-off (reversible via `chase_gate_mode=shadow`).

_No tradeable signals carried a chase stamp yet._

