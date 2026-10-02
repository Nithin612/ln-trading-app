"""PR-1 decision rule — operating characteristics, v2 vs v3/v3.1, on SYNTHETIC series.

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
- K2 (the IC sign) is simulated on a cross-section model (v3.1, after round 2 showed the
  whole-cohort IC lets the side the book never trades decide). The two-branch max and the
  expiry-concentrated edge are simulated too, and K4 uses the dated halves (382 / 366).

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

#: The exchange calendar's pairs under v3.1: 756 on a 5-minute-only calendar silently spanned two
#: muhurat sessions (754 in v3), and the three §10j mismatch sessions remove 6 more.
N_PAIRS = 748
LAG = 10  # ⌈748^(1/3)⌉
BAR_V2 = 3.5749  # N = 21, n = 763, Gaussian moments (the v2 extract's number)
TRIALS_V3 = 22
Z95 = 1.6448536269514722
F64 = NDArray[np.float64]

#: Book slot counts per name, measured by `pr1_design_facts.py` on 2023-07-03 → 2026-07-31 under
#: the v3.1 cohort rule (split/bonus and STRICT basis-step nights dropped; the three §10j
#: sessions excluded): 748 pairs × 5 = 3,740 slots; 206 names; top-3 = 7.0%; effective 103.6.
SLOT_COUNTS: tuple[int, ...] = (
    88, 88, 86, 71, 70, 63, 59, 59, 59, 59, 58, 53, 53, 52, 51, 50, 50, 49, 48, 47, 47, 47,
    46, 46, 45, 45, 43, 43, 41, 39, 38, 37, 36, 34, 33, 32, 32, 31, 31, 30, 30, 30, 30, 29,
    29, 28, 27, 26, 25, 24, 24, 24, 23, 23, 22, 22, 21, 21, 20, 20, 20, 19, 19, 19, 18, 18,
    18, 18, 17, 17, 17, 17, 17, 16, 16, 16, 16, 16, 16, 16, 15, 15, 15, 15, 14, 14, 14, 14,
    14, 14, 14, 14, 13, 13, 13, 13, 13, 13, 13, 12, 12, 12, 12, 12, 12, 12, 12, 12, 11, 11,
    11, 11, 11, 10, 10, 10, 10, 10, 10, 10, 9, 9, 9, 9, 9, 9, 8, 8, 8, 8, 8, 8, 8, 8, 7, 7,
    7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1,
)
#: K4's dated halves: pairs with t before 2025-02-01 (measured by `pr1_design_facts.py`).
K4_FIRST_HALF = 382
#: The K2 cross-section: names per session (median of the measured 191–209).
N_NAMES = 204


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


def k3_fires(x: F64) -> NDArray[np.bool_]:
    """v3 K3: the mean net is ≤ 0 once the 15 best sessions are removed."""
    best = -np.sort(-x, axis=1)
    out: NDArray[np.bool_] = (x.sum(axis=1) - best[:, :15].sum(axis=1)) <= 0
    return out


def k4_fires(x: F64) -> NDArray[np.bool_]:
    """K4: the mean net of the two DATED halves differs in sign."""
    a, b = x[:, :K4_FIRST_HALF].mean(axis=1), x[:, K4_FIRST_HALF:].mean(axis=1)
    out: NDArray[np.bool_] = np.sign(a) != np.sign(b)
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
            k3_v3 = k3_fires(x)
            k4 = k4_fires(x)
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


def concentrated_sessions_oc(rng: np.random.Generator, sims: int) -> None:
    """The edge sits in a few sessions (overall true t 3.6), optionally with ordinary sessions
    losing slightly. Two shapes: 15 RANDOM sessions (the pattern K3 exists for), and the EXPIRY
    sessions, evenly spaced (36 monthly, or 150 if every weekly expiry counted) — the round-2
    claim that K3 kills an expiry-concentrated edge, which is one of the named mechanisms (P6).
    Outlier sessions inflate the variance, so the t itself rejects most random-15 books."""
    bar = bar_t(TRIALS_V3, N_PAIRS)
    print("\n| edge carried by | ordinary-day mean | t ≥ bar | K3 fires on those |")
    print("|---|--:|--:|--:|")
    for shape, k in (("15 random sessions", 15), ("36 expiry sessions", 36),
                     ("150 expiry sessions", 150)):
        for bleed in (0.0, -0.02, -0.04):
            x = noise(rng, "normal", (sims, N_PAIRS)) + bleed
            if shape.endswith("random sessions"):
                idx = np.argsort(rng.random((sims, N_PAIRS)), axis=1)[:, :k]
            else:
                idx = np.tile(np.linspace(0, N_PAIRS - 1, k).round().astype(int), (sims, 1))
            lift = (3.6 / math.sqrt(N_PAIRS) - bleed * (N_PAIRS - k) / N_PAIRS) * N_PAIRS / k
            np.put_along_axis(x, idx, np.take_along_axis(x, idx, axis=1) + lift, axis=1)
            ok = nw_t(x) >= bar
            k3 = k3_fires(x)
            rate = float(k3[ok].mean()) if ok.any() else float("nan")
            print(f"| {shape} | {bleed:+.2f} sd | {ok.mean():.1%} | {rate:.1%} |")


def branch_oc(rng: np.random.Generator, sims: int) -> None:
    """cl. 9: two branches, the one with the higher NW t decides, charged as N = 22. The two
    net series are independent here (overnight vs the next day's session). Reports P(PASS) and,
    when the true t differ, how often the branch that decides is the one carrying more edge."""
    bar = bar_t(TRIALS_V3, N_PAIRS)
    print("\n| true t (CNC, MIS) | PASS | the stronger branch decides, given PASS |")
    print("|---|--:|--:|")
    for ta, tb in ((0.0, 0.0), (2.0, 2.0), (3.6, 0.0), (3.6, 2.0), (3.6, 3.6)):
        xa = noise(rng, "normal", (sims, N_PAIRS)) + ta / math.sqrt(N_PAIRS)
        xb = noise(rng, "normal", (sims, N_PAIRS)) + tb / math.sqrt(N_PAIRS)
        t_a, t_b = nw_t(xa), nw_t(xb)
        pick_a = t_a >= t_b
        x = np.where(pick_a[:, None], xa, xb)
        t = np.maximum(t_a, t_b)
        ok = (t >= bar) & (dsr(x, TRIALS_V3) >= 0.95) & ~k3_fires(x) & ~k4_fires(x)
        right = "—" if ta == tb else f"{float(pick_a[ok].mean()):.1%}" if ok.any() else "n/a"
        print(f"| ({ta:.1f}, {tb:.1f}) | {ok.mean():.2%} | {right} |")


def _session_ic(s: F64, r: F64) -> F64:
    """Per-session Spearman IC across the columns of (sessions, names) arrays (no ties)."""
    rs = np.argsort(np.argsort(s, axis=1), axis=1).astype(np.float64)
    rr = np.argsort(np.argsort(r, axis=1), axis=1).astype(np.float64)
    rs -= rs.mean(axis=1, keepdims=True)
    rr -= rr.mean(axis=1, keepdims=True)
    out: F64 = (rs * rr).sum(axis=1) / np.sqrt((rs * rs).sum(axis=1) * (rr * rr).sum(axis=1))
    return out


def k2_oc(rng: np.random.Generator, sims: int) -> None:
    """K2 and the demeaning base, on a CROSS-SECTION (round 2, then quant-verifier 2026-10-02).

    Each session: N_NAMES names, s ~ N(0, 1); R = ε + m·max(s, 0) + w·b·[in the book], ε ~ N(0,
    1). The book is the 5 most negative s; b gives the book's NET return a true t of 3.6 against a
    benchmark that excludes the book (the whole-cohort base then pays the book's own w·b·5/n
    inside its benchmark — a real property of that base, not a calibration error); w is a cost
    wedge (the GROSS edge is w·b and a flat cost (w − 1)·b comes off the net series, so the
    net t stays 3.6 — K2 reads the gross outcome, as in the design). m is a response of late
    UP-movers, in σ of R per σ of s, on the side the book never trades: m > 0 continuation,
    m < 0 reversal of the up-side only.

    Two decision series (cl. 5, decision #1): the book demeaned against the WHOLE cohort, and
    against the MIDDLE TERCILE of s (ranks ⌊n/3⌋ … ⌊2n/3⌋ − 1). PASS = net t ≥ bar AND DSR ≥ 0.95
    AND the bottom-quintile K2 clear (ranks 0 … ⌊n/5⌋ − 1); a within-session rank IC ignores the
    demeaning constant, so K2 is the same under both bases. The K2 columns report how often each
    K2 variant fires on a middle-tercile t-and-DSR pass (on a null row: on all runs)."""
    bar = bar_t(TRIALS_V3, N_PAIRS)
    half, quint = N_NAMES // 2, N_NAMES // 5
    lo3, hi3 = N_NAMES // 3, 2 * N_NAMES // 3
    b_edge = 3.6 / math.sqrt(5 * N_PAIRS)
    print("\n| book | m | PASS, whole-cohort base | PASS, middle-tercile base | K2 whole "
          "cohort fires | K2 lower half fires | K2 bottom quintile fires |")
    print("|---|--:|--:|--:|--:|--:|--:|")
    cells = [
        ("no edge", 0.0, 0.0, 1.0), ("no edge", -0.10, 0.0, 1.0), ("no edge", -0.15, 0.0, 1.0),
        ("net t 3.6", 0.0, 1.0, 1.0), ("net t 3.6", 0.02, 1.0, 1.0),
        ("net t 3.6", 0.04, 1.0, 1.0), ("net t 3.6", -0.10, 1.0, 1.0),
        ("net t 3.6, gross ×4 less a flat cost", 0.0, 1.0, 4.0),
        ("net t 3.6, gross ×4 less a flat cost", 0.02, 1.0, 4.0),
    ]
    for label, m, edge, wedge in cells:
        b = b_edge * edge
        cost = (wedge - 1.0) * b
        pass_whole = pass_mid = n_mid = 0
        f_whole = f_lower = f_quin = 0
        for _ in range(sims):
            s = np.sort(rng.standard_normal((N_PAIRS, N_NAMES)), axis=1)  # column = rank of s
            r = rng.standard_normal((N_PAIRS, N_NAMES)) + m * np.maximum(s, 0.0)
            r[:, :5] += wedge * b
            book = r[:, :5].mean(axis=1)
            whole = (book - r.mean(axis=1) - cost)[None, :]
            mid = (book - r[:, lo3:hi3].mean(axis=1) - cost)[None, :]
            k2_quin = float(_session_ic(s[:, :quint], r[:, :quint]).mean()) >= 0
            ok_whole = float(nw_t(whole)[0]) >= bar and float(dsr(whole, TRIALS_V3)[0]) >= 0.95
            ok_mid = float(nw_t(mid)[0]) >= bar and float(dsr(mid, TRIALS_V3)[0]) >= 0.95
            pass_whole += ok_whole and not k2_quin
            pass_mid += ok_mid and not k2_quin
            if ok_mid or not edge:
                n_mid += 1
                f_whole += float(_session_ic(s, r).mean()) >= 0
                f_lower += float(_session_ic(s[:, :half], r[:, :half]).mean()) >= 0
                f_quin += k2_quin

        def rate(k: int, n: int = n_mid) -> str:
            return f"{k / n:.1%}" if n else "n/a"

        print(f"| {label} | {m:+.2f} | {pass_whole / sims:.1%} | {pass_mid / sims:.1%} | "
              f"{rate(f_whole)} | {rate(f_lower)} | {rate(f_quin)} |")


#: PR-2's proposed read schedule (§9a a8, decision #3): a read every 126 sessions (~6 months),
#: at most 8 reads (~4 years). Fixed now, independent of PR-1's estimate.
PR2_READ_EVERY = 126
PR2_MAX_READS = 8
PR2_ALPHA = 0.01


def _sequential_t(x: F64, looks: list[int]) -> F64:
    """NW t of the running mean at each look: (runs, looks)."""
    return np.stack([nw_t(x[:, :n], lag=math.ceil(n ** (1 / 3))) for n in looks], axis=1)


def pr2_sequential_oc(
    rng: np.random.Generator, sims: int, gamma: float = 0.5, cost: float = 0.8
) -> None:
    """PR-2's decision rule, simulated BEFORE its freeze (§7's rule, quant-verifier 2026-10-02).

    Boundary: c_l = c·√(n_max / n_l) (O'Brien–Fleming shape), c set on the null so that P(any
    crossing) = 1% one-sided. PASS = the first crossing, then the robustness kills at THAT read
    only (they can turn a PASS into a KILL, never stop the study early): K3 = the mean is ≤ 0
    after removing the best ⌈0.02·n⌉ sessions; K4 = the two halves of the sessions in hand differ
    in sign; K6 = the top 3 names carry > 50% of net (slots drawn from the measured distribution,
    vol ∝ count^gamma and a flat cost eating `cost` of gross; the default is §7's hardest K6
    cell, γ 0.5 with 80%, and main() also runs the mildest, γ 0.256 with 0%). NULL = no
    crossing by the last read. Edges are stated as annual Sharpe, per session SR/√252."""
    looks = [PR2_READ_EVERY * k for k in range(1, PR2_MAX_READS + 1)]
    n_max = looks[-1]
    scale = np.sqrt(n_max / np.asarray(looks, dtype=np.float64))
    z0 = _sequential_t(rng.standard_normal((sims, n_max)), looks)
    c = float(np.quantile((z0 / scale).max(axis=1), 1 - PR2_ALPHA))
    bound = c * scale
    print(f"\nPR-2 boundary (one-sided {PR2_ALPHA:.0%} over {PR2_MAX_READS} reads of "
          f"{PR2_READ_EVERY}): " + " · ".join(f"n={n}: t {b:.2f}" for n, b in zip(looks, bound,
                                                                                 strict=True)))
    counts = np.asarray(SLOT_COUNTS, dtype=np.float64)
    prob = counts / counts.sum()
    sig = (counts / np.median(counts)) ** gamma
    sig = sig / math.sqrt(float(np.sum(prob * sig**2)))
    print(f"\nvol ∝ count^{gamma:g}, flat cost = {cost:.0%} of gross")
    print("| annual Sharpe | PASS (K6 descriptive, a8) | PASS if K6 were a kill | median read "
          "of the PASS | K3 / K4 / K6 fire on a crossing | NULL |")
    print("|--:|--:|--:|--:|--:|--:|")
    for sr in (0.0, 1.0, 1.5, 2.0, 3.0):
        # the SESSION series (mean of 5 unit-variance slots) has sd ≈ 1/√5, so its per-session
        # Sharpe is mu·√5: scale so that it equals sr/√252
        mu = sr / math.sqrt(252) / math.sqrt(5)
        n_pass = n_pass6 = n_null = k3 = k4 = k6 = 0
        reads: list[int] = []
        for _ in range(max(1, sims // 10)):
            nm = rng.choice(len(counts), size=(n_max, 5), p=prob)
            e = rng.standard_normal((n_max, 5))
            # a flat cost eats `cost` of each slot's gross, so the NET session mean is mu
            g = mu / (1.0 - cost) / float(np.sum(prob * sig))
            r = sig[nm] * (e + g) - cost * g * sig[nm].mean()
            sess = r.mean(axis=1)
            tt = _sequential_t(sess[None, :], looks)[0]
            hit = np.nonzero(tt >= bound)[0]
            if not len(hit):
                n_null += 1
                continue
            n = looks[int(hit[0])]
            x = sess[:n]
            best = np.sort(x)[::-1]
            f3 = (x.sum() - best[: math.ceil(0.02 * n)].sum()) <= 0
            f4 = np.sign(x[: n // 2].mean()) != np.sign(x[n // 2 :].mean())
            byname = np.bincount(nm[:n].ravel(), weights=r[:n].ravel(), minlength=len(counts))
            f6 = float(np.sort(byname)[-3:].sum()) > 0.5 * float(r[:n].sum())
            k3, k4, k6 = k3 + f3, k4 + f4, k6 + f6
            if not (f3 or f4):
                n_pass += 1
                reads.append(n)
                n_pass6 += not f6
        runs = max(1, sims // 10)
        crossed = runs - n_null
        med = f"{int(np.median(reads))}" if reads else "—"
        fires = (f"{k3 / crossed:.1%} / {k4 / crossed:.1%} / {k6 / crossed:.1%}"
                 if crossed else "—")
        print(f"| {sr:.1f} | {n_pass / runs:.1%} | {n_pass6 / runs:.1%} | {med} | {fires} | "
              f"{n_null / runs:.1%} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=20000)
    ap.add_argument("--only", choices=("pr2",), default=None,
                    help="run only the PR-2 sequential section (its own seed, 2042)")
    a = ap.parse_args()
    if a.only == "pr2":
        rng2 = np.random.default_rng(2042)
        pr2_sequential_oc(rng2, a.sims)
        pr2_sequential_oc(rng2, a.sims, gamma=0.256, cost=0.0)
        return
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
    concentrated_sessions_oc(rng, a.sims)
    branch_oc(rng, a.sims)
    k2_oc(rng, max(1, a.sims // 10))
    pr2_sequential_oc(rng, a.sims)
    pr2_sequential_oc(rng, a.sims, gamma=0.256, cost=0.0)


if __name__ == "__main__":
    main()
