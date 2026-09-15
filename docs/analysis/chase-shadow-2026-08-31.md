# Anti-chase shadow (live signals) — 2026-08-31

_Read-only. The anti-chase overlay recomputed over the tradeable signal cohort since 2026-07-19 (540 signals), each judged on how far past its entry the order actually filled (chase_r = R past entry; the gate's own stamp when present, else the broker's post-fill telemetry). Gate mode: **shadow**. 'chased' = chase_r above the 0.33R ceiling — the reward:risk you were shown is materially gone. A would-block set net-negative AND worse than the near-entry set is the evidence to flip the gate active._

| set | signals | resolved | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|--:|
| CHASED (> 0.33R past entry, would-block) | 4 | 4 | ₹-12,755 | ₹-3,189 | 0% |
| near entry (eligible) | 66 | 42 | ₹14,747 | ₹351 | 62% |
| no data (no chase stamp) | 470 | 36 | ₹-8,564 | ₹-238 | 47% |

**anti-chase flip readiness:** ⏳ NOT READY — 4/20 resolved chased trades (> 0.33R past entry) — keep accruing. Flipping the gate active is behaviour-changing → needs forward evidence + explicit user sign-off (reversible via `chase_gate_mode=shadow`).

## Per-entry context (each committed signal's chase)

| date | stock | side | chase_r | verdict | outcome |
|---|---|---|--:|---|--:|
| 2026-08-28 | PIDILITIND | SHORT | +0.081R | ✅ near entry | open/none |
| 2026-08-27 | BLIL | LONG | -0.071R | ✅ near entry | open/none |
| 2026-08-27 | VRLLOG | LONG | +0.111R | ✅ near entry | open/none |
| 2026-08-26 | IDBI | LONG | +0.023R | ✅ near entry | open/none |
| 2026-08-26 | GPPL | LONG | +0.133R | ✅ near entry | open/none |
| 2026-08-26 | RELTD | LONG | +0.513R | 🚫 chased | ₹-3,137 |
| 2026-08-26 | LOVABLE | LONG | +0.000R | ✅ near entry | open/none |
| 2026-08-26 | KIRIINDUS | LONG | -0.051R | ✅ near entry | open/none |
| 2026-08-26 | ORKLAINDIA | LONG | +0.031R | ✅ near entry | ₹1,303 |
| 2026-08-25 | CDSL | LONG | +0.088R | ✅ near entry | open/none |
| 2026-08-25 | MOSCHIP | SHORT | -0.112R | ✅ near entry | ₹-2,719 |
| 2026-08-25 | GLOBUSSPR | LONG | -0.078R | ✅ near entry | open/none |
| 2026-08-25 | GOKULAGRO | LONG | +0.068R | ✅ near entry | open/none |
| 2026-08-25 | BVCL | LONG | +0.144R | ✅ near entry | open/none |
| 2026-08-25 | PRIMESECU | LONG | -0.047R | ✅ near entry | open/none |
| 2026-08-25 | ENRIN | SHORT | +0.084R | ✅ near entry | open/none |
| 2026-08-25 | KSB | LONG | +0.114R | ✅ near entry | open/none |
| 2026-08-24 | 20MICRONS | LONG | -0.109R | ✅ near entry | ₹832 |
| 2026-08-24 | EMKAY | LONG | -0.065R | ✅ near entry | ₹1,511 |
| 2026-08-24 | CGPOWER | LONG | -0.081R | ✅ near entry | open/none |
| 2026-08-24 | ADROITINFO | LONG | +0.000R | ✅ near entry | open/none |
| 2026-08-24 | ALGOQUANT | LONG | +0.229R | ✅ near entry | ₹-2,193 |
| 2026-08-21 | BENGALASM | LONG | -0.036R | ✅ near entry | open/none |
| 2026-08-17 | SOUTHBANK | SHORT | -0.057R | ✅ near entry | open/none |
| 2026-08-14 | BPCL | LONG | +0.110R | ✅ near entry | open/none |
| 2026-08-14 | HATSUN | LONG | -0.038R | ✅ near entry | ₹6,017 |
| 2026-08-14 | RELIABLE | SHORT | +0.072R | ✅ near entry | open/none |
| 2026-08-14 | PREMIERENE | SHORT | -0.090R | ✅ near entry | ₹-2,257 |
| 2026-08-14 | LEMERITE | SHORT | +0.317R | ✅ near entry | ₹1,279 |
| 2026-08-14 | KSL | SHORT | +0.097R | ✅ near entry | ₹-2,278 |
| 2026-08-14 | CGCL | LONG | +0.079R | ✅ near entry | ₹2,850 |
| 2026-08-13 | GRSE | LONG | +0.102R | ✅ near entry | open/none |
| 2026-08-13 | SMARTWORKS | LONG | +0.088R | ✅ near entry | ₹163 |
| 2026-08-13 | BEL | LONG | +0.078R | ✅ near entry | open/none |
| 2026-08-13 | SRTL | LONG | +0.500R | 🚫 chased | ₹-3,565 |
| 2026-08-12 | PFIZER | LONG | -0.006R | ✅ near entry | ₹-2,097 |
| 2026-08-12 | BHARTIARTL | LONG | -0.102R | ✅ near entry | open/none |
| 2026-08-12 | PETRONET | LONG | +0.104R | ✅ near entry | ₹-4 |
| 2026-08-12 | UBL | SHORT | -0.075R | ✅ near entry | ₹663 |
| 2026-08-12 | AAVAS | LONG | +0.097R | ✅ near entry | ₹-1,048 |
| 2026-08-11 | ANURAS | SHORT | -0.067R | ✅ near entry | ₹416 |
| 2026-08-11 | AFFLE | LONG | -0.062R | ✅ near entry | ₹944 |
| 2026-08-11 | SPARC | LONG | -2.538R | ✅ near entry | ₹-4,022 |
| 2026-08-10 | GLOBAL | SHORT | +0.083R | ✅ near entry | ₹-247 |
| 2026-08-10 | CONCORDBIO | LONG | +0.112R | ✅ near entry | ₹2,338 |
| 2026-08-10 | ABSLAMC | SHORT | +0.286R | ✅ near entry | ₹-2,221 |
| 2026-08-10 | IDFCFIRSTB | LONG | -0.071R | ✅ near entry | ₹72 |
| 2026-08-10 | KFINTECH | SHORT | +0.090R | ✅ near entry | ₹-1,705 |
| 2026-08-10 | RAJMET | SHORT | -0.136R | ✅ near entry | ₹2,556 |
| 2026-08-10 | MANAKSIA | LONG | +0.086R | ✅ near entry | ₹367 |

_… 20 more assessable signals not shown._

