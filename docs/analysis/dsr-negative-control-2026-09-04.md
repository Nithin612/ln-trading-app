# H8 — negative control on the deflated-Sharpe bar — 2026-09-04

_Generated 2026-09-04 22:56 IST · read-only · seed 20260904 · 2,000 simulations per specificity arm._

> **What this is.** A test of the test. `deflated_sharpe.py` currently rejects every
> gate we have, and that verdict is about to justify closing the gating programme.
> Before acting on an instrument that says no to everything, check that it can say
> yes to something. **H8 as written in `quant-agent-findings.md` asks only whether the
> bar rejects noise — a bar that rejects everything passes that trivially**, so a
> power arm was added. Both arms, or the result is not interpretable.

## Verdict: ✅ THE BAR IS SOUND

It rejects noise **and** accepts real edges. Its verdicts on our gates can be
acted on. The gates are not being failed by a broken instrument.

## The book the control is calibrated on

- **n = 105** closed paper trades · mean **₹-97** · sd ₹2,945
- skew **-0.39** · kurtosis **11.46** (normal = 3.0) — heavily fat-tailed, which PSR charges for
- per-trade Sharpe **-0.033** ⇒ **t = -0.34**

Synthetic series are bootstrapped from these trades and shifted, never drawn from a
normal — PSR penalises skew and fat tails, so a Gaussian control would flatter it.

## Arm 1 — specificity: does the bar reject what it should?

| control | simulations | cleared the bar | expected | verdict |
|---|--:|--:|--:|---|
| random, content-free partitions of the real book | 2,000 | **0.00%** | ≤ 5% | ✅ |
| **best of 20 zero-edge candidates** (the selection we actually do) | 2,000 | **1.10%** | ≤ 5% | ✅ |

The second row is the one that matters. Running eight shadow gates and getting
interested in the best-looking banner is *exactly* how two gates were promoted and
then refuted. Under a true-zero-edge null that procedure fools the bar **1.10%** of the time — at or inside the 5% it is designed to allow.

## Arm 2 — power: can the bar say yes at all?

Planted edges of known size at n = 78, our actual cohort size.

| true per-trade Sharpe | equivalent t | bar accepts |
|--:|--:|--:|
| 0.10 | 0.88 | **0.0%** |
| 0.20 | 1.77 | **0.0%** |
| 0.30 | 2.65 | **0.0%** |
| 0.40 | 3.53 | **28.8%** |
| 0.50 | 4.42 | **77.8%** |
| 0.60 | 5.30 | **99.8%** |
| 0.70 | 6.18 | **100.0%** |
| 1.00 | 8.83 | **100.0%** |

**Minimum detectable edge**, by bisection rather than off the grid above:

- **50% power** — true per-trade Sharpe 0.43 (t ≈ 3.83)
- **80% power** — true per-trade Sharpe 0.52 (t ≈ 4.55)

**The bar is not blind.** But note the cliff: power is ~0% below t ≈ 3.5 and near-total above t ≈ 4.4. It is an instrument for large edges, by design.

## What the bar is actually demanding, in one number

The probability language hides the hurdle. Solved back to a plain t-statistic on the
trade series (Gaussian case — real fat tails make it *stricter*):

| n | implied hurdle |
|--:|--:|
| 30 | t ≥ **3.76** |
| 50 | t ≥ **3.67** |
| 78 | t ≥ **3.62** |
| 105 | t ≥ **3.60** |
| 200 | t ≥ **3.58** |
| 400 | t ≥ **3.56** |
| 1,000 | t ≥ **3.55** |

**The hurdle is ≈3.6 and barely moves with sample size.** That is the single most
useful output here: it converts an opaque probability into a number the literature
already argues about. Harvey, Liu & Zhu (2016) recommend **t > 3.0** for accepting a
new factor precisely because of multiple testing. **Our bar sits just above that
recommendation — it is defensibly calibrated, not arbitrary, and not broken.**

It also explains why MinTRL keeps returning `None`: the benchmark falls as `1/√n`
while the required t stays flat, so **more observations do not lower the bar** — they
only shrink the error on an estimate that has to be large in the first place.

## Consequences — stated before anyone reads a banner again

1. **`sl_atr` is decided, and the answer is NO.** Its eligible set stands at Sharpe
   **+0.046 over n=78 ⇒ t ≈ 0.41**, against a hurdle of ≈3.6. That is not marginal;
   it is short by roughly 9×, and it sits far below even the low-power region where
   the bar might be accused of missing something. **Stop waiting for its 20th resolved
   trade** — the count was never the constraint. It passes all three readiness guards
   and still has no measurable edge in the book it would leave behind.
2. **Failing this bar is not proof of no edge — except when it is this far short.**
   The bar has almost no power between t ≈ 2.6 and t ≈ 3.5, so a genuine but modest
   edge would be invisible. That is the price of multiple-testing correction and it is
   the right trade for a promote-to-money decision. **Future gates failing at t ≈ 2–3
   deserve a different conversation from `sl_atr` at t = 0.41.** Record the t, not just
   the pass/fail.
3. **The leak is upstream of gating.** Three months of shadow accrual, eight gates, two
   promotions both refuted, and the best surviving candidate is at t = 0.41. No
   partition of these trades is going to clear a t of 3.6, because the trades
   themselves carry no edge to partition. Selection has been optimised; what generates
   the candidates has not.

## Limits of this control

- Bootstrap resampling assumes trades are **i.i.d.**; ours overlap in time and cluster
  by regime, so the true dispersion of a cohort Sharpe is wider than modelled and the
  specificity arm is, if anything, optimistic.
- `trials = 20` is still an assumption. **U4** (the trials counter)
  replaces it with an observed count; until then the deflation is understated.
- The power arm plants a *constant* edge. A real edge that is regime-dependent would be
  harder to see than these curves suggest.

