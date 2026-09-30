"""PR-1 decision rule — operating characteristics, v2 vs v3, on SYNTHETIC series.

    uv run python scripts/pr1_decision_oc.py [--sims 20000]

**Reads no market data.** It asks one question of each version of the pre-registered rule: *if
the net book return had true t = 0, 2, 3.6 or 5, how often would the rule say PASS?* A rule
should pass about half the time at a true t equal to its own bar and almost always well above
it. The first outside pass (2026-09-30) claimed v2's session-concentration kill fires on almost
every genuine pass; this measures that claim instead of arguing it
(`docs/analysis/pr1-outside-pass-2026-09-30.md`, §7 of the v3 extract).

- v2: NW t ≥ 3.5749 · K3 = "> 50% of net P&L from ≤ 5% of sessions" (literal: also fires when
  the total is ≤ 0) · K4 = the halves disagree in sign.
- v3: NW t ≥ 3.5953 (N = 22) **and** DSR ≥ 0.95 at the REALIZED skew and kurtosis · K3′ = mean
  net ≤ 0 after removing the best 15 sessions · K4 unchanged · robustness kills evaluated only
  on a would-be pass.
- K6 (names) is simulated on the MEASURED book slot distribution (`pr1_design_facts.py`,
  session-t data only), because a guessed concentration would decide the answer.
- K2 (the IC sign) is not simulated: it needs a cross-section model, not a book series.

The vectorised t and PSR are checked against the house `newey_west_t` and `deflated_sharpe` on
real draws before anything is reported (W2: one implementation, proven equal, not a second one).
Seeded; Monte Carlo error is about ±0.7 pp at a 50% rate with 20,000 runs.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.block_bootstrap import newey_west_t  # noqa: E402
from app.services.deflated_sharpe import deflated_sharpe, expected_max_sharpe  # noqa: E402

N_PAIRS = 754  # the exchange calendar's pairs (756 silently spanned two muhurat sessions)
LAG = 10  # block_length(754)
BAR_V2 = 3.5749  # N = 21, n = 763, Gaussian moments (the v2 extract's number)
TRIALS_V3 = 22
Z95 = 1.6448536269514722
F64 = NDArray[np.float64]

#: Book slot counts per name, measured by `pr1_design_facts.py` on 2023-07-03 → 2026-07-31
#: (754 pairs × 5 = 3,770 slots; 206 names; top-3 = 7.0%; effective names 103.6).
SLOT_COUNTS: tuple[int, ...] = (
    90, 88, 86, 72, 70, 65, 60, 59, 59, 59, 58, 54, 53, 52, 50, 50, 49, 49, 48, 47, 47, 47,
    47, 46, 45, 45, 45, 44, 42, 40, 39, 38, 36, 35, 33, 32, 32, 31, 31, 31, 30, 30, 30, 29,
    29, 28, 27, 27, 25, 25, 24, 24, 24, 23, 23, 22, 22, 21, 20, 20, 20, 20, 19, 19, 18, 18,
    18, 18, 18, 18, 17, 17, 17, 16, 16, 16, 16, 16, 16, 16, 15, 15, 15, 15, 15, 14, 14, 14,
    14, 14, 14, 14, 14, 13, 13, 13, 13, 13, 13, 13, 12, 12, 12, 12, 12, 12, 12, 11, 11, 11,
    11, 11, 11, 11, 10, 10, 10, 10, 10, 10, 10, 9, 9, 9, 9, 9, 9, 9, 8, 8, 8, 8, 8, 8, 8, 7,
    7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2,
    2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1,
)


def bar_t(trials: int, n: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Smallest t = SR·√n whose PSR against E[max SR] reaches 0.95 at these moments."""
    bench = expected_max_sharpe(trials, 1.0 / math.sqrt(n))
    sr = bench
    for _ in range(200):
        sr = bench + Z95 * math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr * sr) / math.sqrt(n - 1)
    return sr * math.sqrt(n)


def nw_t(x: F64, lag: int = LAG) -> F64:
    """Row-wise Newey–West (Bartlett) t of the mean — the house formula, vectorised."""
    n = x.shape[1]
    d = x - x.mean(axis=1, keepdims=True)
    v = (d * d).mean(axis=1)
    for lg in range(1, lag + 1):
        v = v + 2.0 * (1.0 - lg / (lag + 1.0)) * (d[:, lg:] * d[:, :-lg]).sum(axis=1) / n
    t: F64 = x.mean(axis=1) / np.sqrt(v / n)
    return t


def dsr(x: F64, trials: int) -> F64:
    """Row-wise house DSR: PSR against E[max SR], sample skew and Pearson kurtosis."""
    n = x.shape[1]
    m = x.mean(axis=1)
    sd = x.std(axis=1, ddof=1)
    pop = x.std(axis=1)
    c = x - m[:, None]
    sk = (c**3).mean(axis=1) / pop**3
    ku = (c**4).mean(axis=1) / pop**4
    sr = m / sd
    den = np.sqrt(np.maximum(1 - sk * sr + (ku - 1) / 4 * sr * sr, 1e-12))
    z = (sr - expected_max_sharpe(trials, 1.0 / math.sqrt(n))) * math.sqrt(n - 1) / den
    out: F64 = 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))
    return out


def noise(rng: np.random.Generator, kind: str, size: tuple[int, int]) -> F64:
    """Unit-variance, zero-mean noise of the named shape."""
    if kind == "normal":
        out: F64 = rng.standard_normal(size)
    elif kind == "t4":
        out = rng.standard_t(4, size) / math.sqrt(2.0)
    elif kind == "t3":
        out = rng.standard_t(3, size) / math.sqrt(3.0)
    else:  # skew-normal, alpha = -5 (skew ≈ -0.85), standardised analytically
        dl = -5.0 / math.sqrt(26.0)
        raw = dl * np.abs(rng.standard_normal(size)) + math.sqrt(1 - dl * dl) * rng.standard_normal(
            size
        )
        mu = dl * math.sqrt(2.0 / math.pi)
        out = (raw - mu) / math.sqrt(1.0 - 2.0 * dl * dl / math.pi)
    return out


def parity_check(rng: np.random.Generator) -> None:
    x = noise(rng, "t4", (5, N_PAIRS)) + 0.12
    ours_t, ours_d = nw_t(x), dsr(x, TRIALS_V3)
    for i in range(5):
        row = [float(v) for v in x[i]]
        house_t = newey_west_t(row, lag=LAG)
        house = deflated_sharpe(row, trials=TRIALS_V3)
        assert house_t is not None and house is not None
        assert abs(house_t - float(ours_t[i])) < 1e-9, (house_t, ours_t[i])
        assert abs(house.dsr - float(ours_d[i])) < 1e-9, (house.dsr, ours_d[i])
    print("parity: vectorised t and DSR equal the house functions to 1e-9 on 5 draws")


def session_oc(rng: np.random.Generator, sims: int) -> None:
    bar = bar_t(TRIALS_V3, N_PAIRS)
    half = N_PAIRS // 2  # the halves split by index here; the design dates them (≈ equal)
    print("\n| noise | true t | PASS v2 | PASS v3 | v2 K3 fires when t ≥ bar |")
    print("|---|--:|--:|--:|--:|")
    for kind in ("normal", "t4", "t3", "negskew"):
        for tt in (0.0, 2.0, 3.6, 5.0):
            x = noise(rng, kind, (sims, N_PAIRS)) + tt / math.sqrt(N_PAIRS)
            t = nw_t(x)
            p = dsr(x, TRIALS_V3)
            tot = x.sum(axis=1)
            best = -np.sort(-x, axis=1)
            k3_v2 = (tot <= 0) | (best[:, :38].sum(axis=1) > 0.5 * tot)
            k3_v3 = (tot - best[:, :15].sum(axis=1)) <= 0
            k4 = np.sign(x[:, :half].mean(axis=1)) != np.sign(x[:, half:].mean(axis=1))
            pass_v2 = (t >= BAR_V2) & ~k3_v2 & ~k4
            would = (t >= bar) & (p >= 0.95)
            pass_v3 = would & ~k3_v3 & ~k4
            over = t >= BAR_V2
            k3_share = float(k3_v2[over].mean()) if over.any() else float("nan")
            print(f"| {kind} | {tt:.1f} | {pass_v2.mean():.1%} | {pass_v3.mean():.1%} | "
                  f"{k3_share:.1%} |")
    sr = bar / math.sqrt(N_PAIRS)
    phi = math.exp(-Z95 * Z95 / 2) / math.sqrt(2 * math.pi)
    print(f"\nclosed form (Gaussian): at SR {sr:.4f} the best 5% of sessions carry "
          f"{0.05 + phi / sr:.1%} of net P&L; the share reaches 50% only at t "
          f"{phi / 0.45 * math.sqrt(N_PAIRS):.2f}")


def names_oc(rng: np.random.Generator, sims: int) -> None:
    """K6 on the MEASURED slot distribution. A name's volatility rises with its slot count
    (volatile names post extreme late moves more often): the exponent is 0.256 as measured by
    the review, and 0.5 as a stress. A flat cost per slot (rho = the share of the gross it eats)
    is what makes low-volatility names net-negative, so top-3 concentration is tested WITH it.
    The planted mean is scaled so the SESSION net t equals the stated t exactly."""
    names = np.repeat(np.arange(len(SLOT_COUNTS)), SLOT_COUNTS)
    counts = np.asarray(SLOT_COUNTS, dtype=np.float64)
    bar = bar_t(TRIALS_V3, N_PAIRS)
    top3 = np.argsort(counts)[-3:]
    print("\n| names scenario | vol ∝ count^γ | cost / gross | t ≥ bar | K6 fires on those |")
    print("|---|--:|--:|--:|--:|")
    cases: list[tuple[str, float, float, float, bool]] = []
    for gamma in (0.256, 0.5):
        for rho in (0.0, 0.8):
            for tt in (3.6, 5.0):
                cases.append((f"broad edge, true t {tt}", gamma, rho, tt, False))
    cases.append(("3 names carry it, the rest lose", 0.5, 0.0, 0.0, True))
    for label, gamma, rho, tt, rescue in cases:
        sig = (counts / np.median(counts)) ** gamma
        sig = sig / math.sqrt(float(np.mean(sig[names] ** 2)))
        mean_sig = float(np.mean(sig[names]))
        g = tt / ((1.0 - rho) * mean_sig * math.sqrt(5 * N_PAIRS)) if not rescue else 0.0
        c = rho * mean_sig * g
        n_pass = n_k6 = 0
        for _ in range(sims):
            nm = names[rng.permutation(len(names))]
            e = rng.standard_normal(len(names))
            if rescue:
                r = sig[nm] * (e + np.where(np.isin(nm, top3), 0.9, -0.02))
            else:
                r = sig[nm] * (e + g) - c
            sess = r.reshape(N_PAIRS, 5).mean(axis=1)
            if float(nw_t(sess[None, :])[0]) < bar:
                continue
            n_pass += 1
            byname = np.bincount(nm, weights=r, minlength=len(SLOT_COUNTS))
            n_k6 += int(float(np.sort(byname)[-3:].sum()) > 0.5 * float(r.sum()))
        rate = n_k6 / n_pass if n_pass else float("nan")
        cost = "—" if rescue else f"{rho:.0%}"
        print(f"| {label} | {gamma:g} | {cost} | {n_pass / sims:.1%} | {rate:.1%} |")


def fragile_sessions_oc(rng: np.random.Generator, sims: int) -> None:
    """The pattern K3 exists for: the whole edge sits in 15 random sessions (overall true t
    3.6), optionally with ordinary sessions losing slightly. Outlier sessions inflate the
    variance, so the t itself rejects most of these; K3 is the backstop for the rest."""
    bar = bar_t(TRIALS_V3, N_PAIRS)
    print("\n| 15 sessions carry the edge; ordinary-day mean | t ≥ bar | K3 fires on those |")
    print("|---|--:|--:|")
    for bleed in (0.0, -0.02, -0.04):
        x = noise(rng, "normal", (sims, N_PAIRS)) + bleed
        idx = np.argsort(rng.random((sims, N_PAIRS)), axis=1)[:, :15]
        lift = (3.6 / math.sqrt(N_PAIRS) - bleed * (N_PAIRS - 15) / N_PAIRS) * N_PAIRS / 15
        np.put_along_axis(x, idx, np.take_along_axis(x, idx, axis=1) + lift, axis=1)
        ok = nw_t(x) >= bar
        best = -np.sort(-x, axis=1)
        k3 = (x.sum(axis=1) - best[:, :15].sum(axis=1)) <= 0
        rate = float(k3[ok].mean()) if ok.any() else float("nan")
        print(f"| {bleed:+.2f} sd | {ok.mean():.1%} | {rate:.1%} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=20000)
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    parity_check(rng)
    print("\nbar (Gaussian moments): "
          + " · ".join(f"N={n} n={k}: t {bar_t(n, k):.4f}"
                       for n, k in ((21, 763), (21, 756), (22, 756), (22, N_PAIRS), (23, N_PAIRS))))
    print(f"bar at N=22, n={N_PAIRS} and other moments: "
          + " · ".join(f"skew {s:+.1f} kurt {k:g}: t {bar_t(22, N_PAIRS, s, k):.3f}"
                       for s, k in ((-0.5, 6.0), (-1.0, 10.0), (0.5, 6.0), (0.0, 11.46))))
    print("bar sensitivity to the trial count: "
          + " · ".join(f"N={n}: t {bar_t(n, N_PAIRS):.3f}" for n in (30, 44, 60)))
    print(f"luck alone: E[max SR] at N=22 = "
          f"{expected_max_sharpe(22, 1 / math.sqrt(N_PAIRS)) * math.sqrt(252):.2f} annualised")
    session_oc(rng, a.sims)
    names_oc(rng, max(1, a.sims // 10))
    fragile_sessions_oc(rng, a.sims)


if __name__ == "__main__":
    main()
