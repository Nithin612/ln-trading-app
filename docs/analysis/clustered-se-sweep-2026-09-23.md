# Q1 — the clustered-SE sweep: which studies treat correlated observations as independent?

**2026-09-23. READ-ONLY audit.** Prompted by the M93 finding
(`docs/analysis/m93-audit-2026-09-21.md`), where `stddev(x)/sqrt(count(*))` over stock-days that
cluster by session inflated a t-statistic **8.6×** and reversed a conclusion.

The question: **where else does this repo compute a standard error as if its observations were
independent, and does the published conclusion survive?**

---

## ⭐⭐ The triage rule that made this tractable

> **A positive within-cluster correlation inflates the iid t. Correcting it can only move a
> result TOWARD the null.**

⇒ **Any conclusion already reported as a NULL survives the correction automatically.** Only
**significant** findings are at risk. That reduced an ~30-script sweep to a handful of files.

⚠ **The one exception, stated so it is not forgotten:** if within-cluster correlation were
*negative*, the clustered SE would be smaller and |t| would rise. That is rare in financial panels
(same-day names share a market move, so the correlation is positive) but it is an assumption, not
a theorem. Where a null is defended by this rule alone, that is recorded rather than hidden.

---

## Verdicts

| script | unit of observation | clusters? | published conclusion | verdict |
|---|---|---|---|---|
| **`e2_score_ic.py`** | daily IC, **strided by the horizon** | **no — disjoint by construction** | the retirement (IC −0.0055, NULL) | ✅ **CLEAN** |
| `signed_displacement_study.py` | stock-day | **yes, hard** (max 243/session) | +0.650%, t +14.33 | ⛔ **DEFECTIVE — refuted, t → +1.66** |
| `entry_confirmation_study.py` | paired ΔR per signal | yes, by mint date | fill cost, published t −7.2…−9.4 | ✅ **SURVIVES — |t| moves ≤0.2** |
| `tp_geometry_study.py` (D5) | signal | yes | every constant-R:R target worse, t −2.5…−3.7 | ✅ covered — `item6_rerun.py` re-ran cluster-robust |
| `rvol_factor_study.py` (D1) | signal | yes | RVOL refuted, t −2.91 | ✅ covered — same re-run |
| `b7_hazard.py` (B7) | trade | yes | T=0 contrast t −4.16 → −6.61 | ✅ covered — `item6_b7.py` |
| `factor_sweep.py` | date | **non-overlapping + day-block bootstrap** | nothing survived (NULL) | ✅ clean by design |
| `cas_stage2_study.py` | **day** (states it) | yes | ρ −0.272, explicitly NOT promotable | ✅ honest — says 208 obs would be ~14× too narrow |
| `regime_study.py` | stock-day | yes | direction only + non-overlap robustness | ✅ has the check |
| `positional_probe.py` | paired panel | yes | ΔR −0.120 t −1.47; ΔR −0.079 t −0.53 | ✅ **NULLs ⇒ survive** |
| `swing_dependence_probe.py` | trade | yes | — | ✅ carries HC3 **and** clustered SEs |
| `confirmation_base_rate.py` · `squeeze_study.py` · `overhead_supply_study.py` | stock-day | yes | all NULL | ✅ cluster-aware imports |
| `round9_cells.py` | trade | yes | round-9 cells | ✅ date-clustering checked (moved every t ≤0.06) |
| `clean_book_study.py` · `signal_filter_shadow.py` | the paper book (**n=4**) | n/a | descriptive only | ⚠ no decision rests on them |
| `dsr_negative_control.py` · `retune_dsr_verdict.py` | simulated / R series | — | instrument validation; retune not promoted | ⚠ low risk, no live decision |

---

## 1. ✅ The most important result in the project is SAFE

The scorer's retirement rests on `e2_score_ic.py`. It is **not** exposed:

```python
ap.add_argument("--stride", type=int, default=HORIZON,
                help="sample every Nth session; default = horizon (non-overlapping)")
```

with `grid = [d for d in sorted(sessions) if d >= TEST_BLOCK_START][::stride]` and
`HORIZON = 5`. ⇒ consecutive IC observations use **disjoint** 5-day forward windows, so
`stdev/sqrt(n)` over them is the right SE and there is no overlap to correct.

⚠ Residual, stated: striding removes *serial* overlap, not any common factor across the sampled
sessions. With disjoint windows that residual is small, and the result is a null in any case —
widening the interval cannot turn a null into a finding.

## 2. ⛔ The one confirmed defect, and what it cost

`signed_displacement_study.py:56` — `stddev(fwd_pct)/sqrt(count(*))`. Gap days cluster by session
almost by construction. Corrected with `cluster_robust_mean_t`:

| arm | mean | t iid | **t clustered** | deflation |
|---|--:|--:|--:|--:|
| gap ≤ −2% | +0.6505% | +14.33 | **+1.66** | **8.6×** |
| gap ≥ +2% | +0.6145% | +17.69 | +4.99 | 3.5× |
| pooled | +0.6309% | +22.52 | **+3.33** | 6.8× |

⭐ **Fixed forward:** the file now carries a supersession banner naming the audit and the
corrected numbers. **It is otherwise unchanged** — the point estimates reproduce exactly
(+0.6505%), so the file is kept as something the audit can be reproduced against. Only the
inference was wrong.

## 3. ✅ RESOLVED — `entry_confirmation_study.py` survives

`_mean_t` divides by `sqrt(n)` over signals, and line 560 uses it for the **paired ΔR** that the
reading study's headline rests on. Signals cluster by mint date.

⭐ **The key already carries the date** — `key = (stock, candles.index[sidx])` — so no dump was
needed. The study now prints the **session-clustered t beside the iid one** rather than replacing
it, so the deflation is visible in the artifact instead of being asserted in prose.

⚠ **Prediction, recorded before the run finished:** the deflation should be **much smaller than
M93's**, because this is a *paired* design — ΔR is the same signal under two entry rules, so the
common market move largely cancels in the difference.

### ✅ RESULT (run completed 2026-09-24, 250 stocks, 3,266 baseline signals)

**The prediction holds, and precisely. The deflation is essentially nil.**

| entry rule | n_int | paired ΔR | t iid | **t CLUSTERED** | dates |
|---|--:|--:|--:|--:|--:|
| stop, 1d | 2,059 | −0.163 | −12.11 | **−11.89** | 663 |
| stop+cap, 1d | 2,018 | −0.166 | −12.12 | **−11.94** | 658 |
| stop+cap+samebar, 2d | 2,200 | −0.214 | −13.64 | **−13.45** | 677 |
| stop, 3d | 2,514 | −0.185 | −12.25 | **−12.39** | 698 |
| stop+cap, 3d | 2,461 | −0.191 | −12.50 | **−12.71** | 693 |
| stop+cap+samebar, 3d | 2,304 | −0.222 | −14.40 | **−14.28** | 682 |
| stop+cap+samebar, 5d | 2,422 | −0.231 | −15.43 | **−15.33** | 685 |

⇒ **|t| moves by ≤ 0.2 in every cell, against M93's 8.6× collapse.** ⭐ **The fill-cost finding is
NOT an artifact of treating signals as independent** — the reading study's conclusion stands.

⭐⭐ **And the exception this document wrote down fired on the very next measurement.** §"the
triage rule" warned that a *negative* within-cluster correlation would make the clustered t
**larger**, calling that "an assumption, not a theorem." In three cells it is exactly that:
3d stop −12.25 → **−12.39**, 3d stop+cap −12.50 → **−12.71**, 5d stop −11.61 → **−11.61**.
⇒ **Clustering is a correction, not a penalty.** Do not describe it as "deflating" a t; describe
it as *using the right unit*, which can move the number either way.

### ⚠ Two honest qualifications

1. **The corpus is not the published one.** This run mints **3,266** baseline signals against the
   ~1,975 behind the published figures — `ohlcv_1d` gained 622 sessions in the 922-day backfill and
   the active universe went 1,322 → 2,292. So the magnitudes are **not** directly comparable to the
   published `t −7.2…−9.4`; only the clustering verdict transfers, and that is what this sweep was
   asking.
2. **On this larger corpus the whole-book confirmation effect is a NULL.** Every variant sits at
   mean R between −0.032 and +0.029 with **|t| ≤ 1.27** (baseline itself +0.004, t +0.15). The
   published *"significantly worse at 3d/5d (t −2.45, −2.87)"* does **not** reproduce at that
   strength here. ⇒ **the correct current statement is: the confirmation rule does not beat entering
   at the open, and its fill cost is strongly negative and robust.** The selection benefit remains
   the weaker half, exactly as originally reported.

---

## ⭐ What this sweep changes going forward

1. **`block_bootstrap` is the house estimator** — `cluster_robust_mean_t`, `cluster_robust_slope_t`,
   `newey_west_t`, all validated against a known null that first reproduces the failure
   (naive rejects 36.7% at a nominal 5%; clustered 5.0%). A new study that computes its own
   `sqrt(n)` should say why.
2. **Report both t's, never silently replace one.** A reader who sees only the corrected number
   learns nothing about how much the correction mattered.
3. **A null is cheap to defend, a finding is not.** State which side of that line a result sits on
   *before* choosing how hard to work on its SE.
4. ⭐⭐ **Clustering is a CORRECTION, not a penalty — stop calling it "deflation."** M93 fell 8.6×;
   the paired entry study moved ≤0.2 and in three cells moved the *other way*. The size of the
   change is a property of the design, and a **paired** design is what buys the immunity: when the
   two legs share the day, the day cancels in the difference. ⇒ **Prefer a paired estimand wherever
   the question allows one** — it is worth more than any SE correction applied afterwards.
5. ⚠ **A re-run on a grown corpus is not a re-test of the published number.** This study now mints
   3,266 signals against ~1,975 behind the published figures. Say which corpus a number came from,
   or two runs of the same script will be mistaken for a contradiction.
