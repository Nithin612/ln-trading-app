"""Round 9 — every cell the round-8 reviewers asked for, off ONE per-trade artifact.

Read-only. Consumes the CSV written by `swing_dependence_probe.py --dump-trades`; it
touches no database, no frozen code and no money path. The expensive pass runs once;
this is a cheap read, which is the shape Kimi's R4 asked for and the reason five
separate adjudications can be settled without five separate walks.

What it answers, and who asked:

  E3   `clean x BUY x w>=2% x net-per-trade` in FIVE units, in one pass, with four SE
       flavours.  ChatGPT §33.1 / Claude G2 / the document's own plan item 2''''.
       The single cell every conclusion in the adjudication is a corner of.

  PART B  is `t = -2.19` (12.18g) an artifact of dividing by a small number?  The same
       net question in raw %, ATR units and net Rs.  Claude Part B / §12.10b's own rule.

  G1/C2  the stop-width family with a THIRD mechanical term isolated: R = (a + drift*T)/w.
       Re-reporting in raw % removes 1/w; it does NOT remove drift*T, because T rises
       with w and the universe drifted. Only the matched-window basket removes it.
       Emits mean/median T and E[1/w] per bucket so the mechanism is visible, not inferred.

  G5   the drift null, PAIRED per trade over its own entry-to-exit window, instead of
       12.20's unpaired fixed-horizon scalar. The book is beta +0.92 against a basket
       that IS the market, so pairing removes the market factor and cuts SE.

  G6/F the rupee-day table -- plan item 22, open since round 1 -- at the MEASURED mean
       hold rather than an assumed one, beside the basket's own drift.

  G4   the `choppy` filter (Kaufman ER < 0.30) tested as a SELECTOR. It is one of two
       undeclared display-path filters (12.21b) that the order path and the corpus both
       ignore; it was filed as a governance item and never measured.

  C3   the confidence NORMALIZER, decomposed. `confluence.py:160` divides by the weight
       of factors that SCORED, so sparse conviction outranks broad agreement. Three rival
       ranking keys on the same panels distinguish "the factors carry nothing" from
       "the normalizer destroyed what they carry".

  D4   the posterior, against three hurdles, with ONE SE used consistently (the round-8
       document used 0.1287 in one section and 0.1490 in another for the same cell).

Every printed statistic carries n, the SE flavour and the cohort. Nothing here combines
two quantities whose samples differ (the 16.1 rule).
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from swing_dependence_probe import perm_p, spearman  # noqa: E402  (W2: one implementation)

# Charges. 25.5 bps round trip is the measured explicit stack at Rs1L on a 5% stop
# (16.1, `roundtrip_charges`, 2026-09-05). The slippage arm can NEVER be measured
# retrospectively -- `orders` = 0 rows -- so it is reported at a ladder, never folded in.
EXPLICIT_BPS = 25.5
SLIP_LADDER = (0.0, 10.0, 15.0, 20.0, 30.0)
TRADING_DAYS = 252


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def clustered_se(vals: list[float], groups: list[Any]) -> float:
    """Cluster-robust SE of a MEAN, clustered on entry date.

    Trades minted on the same session share that session's market move, so the iid SE
    understates. This is the mean-only case of the CR0 estimator; it is the flavour
    round 8 established for RVOL (where iid +3.67 collapsed to clustered +0.98) and
    then did not apply to its own headline.
    """
    n = len(vals)
    if n < 2:
        return float("nan")
    m = statistics.mean(vals)
    by: dict[Any, float] = collections.defaultdict(float)
    for v, g in zip(vals, groups, strict=True):
        by[g] += v - m
    return math.sqrt(sum(s * s for s in by.values())) / n


def cell(label: str, vals: list[float], groups: list[Any] | None = None,
         unit: str = "R", quiet: bool = False) -> dict[str, float]:
    if len(vals) < 2:
        if not quiet:
            print(f"  {label:<44} n={len(vals):>4}   (too few)")
        return {}
    n = len(vals)
    m, sd = statistics.mean(vals), statistics.stdev(vals)
    se = sd / math.sqrt(n)
    cse = clustered_se(vals, groups) if groups else float("nan")
    out = {"n": n, "mean": m, "sd": sd, "se": se, "t": m / se if se else float("nan"),
           "cse": cse, "ct": (m / cse) if cse and cse == cse else float("nan")}
    if not quiet:
        extra = f"  clust SE {cse:7.4f} t {out['ct']:+6.2f}" if groups else ""
        print(f"  {label:<44} n={n:>4}  mean {m:+9.4f}  sd {sd:7.4f}  "
              f"SE {se:7.4f}  t {out['t']:+6.2f}{extra}   [{unit}]")
    return out


def contrast(label: str, a: list[float], b: list[float], na: str, nb: str) -> None:
    """The statistic round 8 named and then omitted six times: the DIFFERENCE, with its SE."""
    if len(a) < 2 or len(b) < 2:
        print(f"  {label:<44} (too few)")
        return
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa = statistics.stdev(a) / math.sqrt(len(a))
    sb = statistics.stdev(b) / math.sqrt(len(b))
    d, sd_ = ma - mb, math.hypot(sa, sb)
    t = d / sd_ if sd_ else float("nan")
    print(f"  {label:<44} {na} {ma:+8.4f} (n{len(a)})  {nb} {mb:+8.4f} (n{len(b)})  "
          f"diff {d:+8.4f}  SE {sd_:.4f}  t {t:+6.2f}  p {2*(1-phi(abs(t))):.3f}  "
          f"MDE@80% {2.8016*sd_:+.4f}")


def load(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            d: dict[str, Any] = {}
            for k, v in r.items():
                if k in ("sym", "entry", "exit", "dir"):
                    d[k] = v
                elif k == "straddle":
                    d[k] = v == "True"
                else:
                    try:
                        d[k] = float(v)
                    except (TypeError, ValueError):
                        d[k] = float("nan")
            rows.append(d)
    return rows


def net_units(t: dict[str, Any], slip_bps: float) -> dict[str, float]:
    """One trade, costed ONCE, expressed in five units.

    The cost is a fixed number of basis points of notional. Its expression in R is
    `bps/(100*w)` -- so the SAME charge is 0.05R on a 5% stop and 0.51R on a 0.5% stop.
    That amplification is real economics for a risk-first sized book, and it is also
    exactly why the R-space net test up-weights the tight-stop cohort the live order
    path refuses. Reporting all five units is the only way to tell those apart.
    """
    bps = EXPLICIT_BPS + 2.0 * slip_bps
    cost_pct = bps / 100.0
    w = t["w"]
    return {
        "R": t["Rw"] - cost_pct / w,
        "pct": t["ret_pct"] - cost_pct,
        "excess": t["excess"] - cost_pct,          # paired vs the basket, then costed
        "atr": t["ret_atr"] - (cost_pct / t["atr_pct"] if t["atr_pct"] == t["atr_pct"]
                               and t["atr_pct"] else float("nan")),
        "cash": t["cash"] - cost_pct / 100.0 * t["entry_px"] * t["qty"],
        "cost_R": cost_pct / w,
    }


def cohorts(tr: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clean = [t for t in tr if not t["straddle"]]
    return {
        "ALL": tr,
        "BUY": [t for t in tr if t["dir"] == "BUY"],
        "clean": clean,
        "clean x BUY": [t for t in clean if t["dir"] == "BUY"],
        "clean x BUY x w>=2%  <- E3": [t for t in clean if t["dir"] == "BUY" and t["w"] >= 2.0],
    }


def main(path: str) -> None:
    tr = load(path)
    print(f"loaded {len(tr)} trades from {path}\n")
    co = cohorts(tr)

    print("=" * 108)
    print("0.  COHORT SIZES, and the holding period T that every per-day statement needs")
    print("=" * 108)
    print("  T = sessions from entry to exit. The probe CAPS at 5 but trades exit early at a")
    print("  barrier; mean T has never been emitted, so 12.20's 5-session null and every")
    print("  'per day' number in the record are conditional on a number nobody measured.")
    for k, v in co.items():
        if not v:
            continue
        Ts = [t["T"] for t in v]
        print(f"  {k:<30} n={len(v):>4}  mean T {statistics.mean(Ts):5.2f}  median {statistics.median(Ts):4.1f}"
              f"  T=0 (same-session exit) {100*sum(1 for x in Ts if x == 0)/len(Ts):5.1f}%"
              f"  mean w {statistics.mean([t['w'] for t in v]):5.2f}%"
              f"  E[1/w] {statistics.mean([1/t['w'] for t in v]):6.3f}")

    print("\n" + "=" * 108)
    print("1.  E3 + PART B — the net question in FIVE units x FIVE cohorts (explicit charges only)")
    print("=" * 108)
    print("  If the R row and the raw-% row disagree in SIGNIFICANCE, the R row is the 1/w")
    print("  estimator up-weighting tight stops -- the cohort the notional cap refuses.")
    for ck, cv in co.items():
        if len(cv) < 3:
            continue
        print(f"\n  --- {ck}  (n={len(cv)}) ---")
        g = [t["entry"] for t in cv]
        n0 = [net_units(t, 0.0) for t in cv]
        cell("gross R", [t["Rw"] for t in cv], g, "R")
        cell("NET R (explicit)", [x["R"] for x in n0], g, "R")
        cell("gross raw return %", [t["ret_pct"] for t in cv], g, "%")
        cell("NET raw return % (explicit)", [x["pct"] for x in n0], g, "%")
        cell("gross excess over matched basket %", [t["excess"] for t in cv], g, "%")
        cell("NET excess over matched basket %", [x["excess"] for x in n0], g, "%")
        cell("NET return / ATR20", [x["atr"] for x in n0 if x["atr"] == x["atr"]], None, "ATR")
        cell("NET cash Rs", [x["cash"] for x in n0], g, "Rs")
        cell("cost in R (the Jensen term)", [x["cost_R"] for x in n0], None, "R")

    print("\n" + "=" * 108)
    print("2.  THE SLIPPAGE LADDER on the E3 cell — the assumed half, never folded in")
    print("=" * 108)
    e3 = co["clean x BUY x w>=2%  <- E3"]
    if len(e3) > 2:
        g = [t["entry"] for t in e3]
        for s in SLIP_LADDER:
            n_ = [net_units(t, s) for t in e3]
            cell(f"NET R  @ {s:.0f} bps/leg slippage", [x["R"] for x in n_], g, "R")
            cell(f"NET raw %  @ {s:.0f} bps/leg", [x["pct"] for x in n_], g, "%")

    print("\n" + "=" * 108)
    print("3.  G1/C2 — the stop-width family with drift x T ISOLATED")
    print("=" * 108)
    print("  R = (alpha + drift*T)/w. Re-reporting in raw % removes 1/w and NOT drift*T,")
    print("  because T rises with w and the universe rose. Only the matched-window basket")
    print("  (the `excess` column) removes both. Read the three rows against each other.")
    buckets = [(0, 2), (2, 4), (4, 6), (6, 10), (10, 1e9)]
    for ck in ("ALL", "clean x BUY"):
        cv = co[ck]
        print(f"\n  --- {ck} ---")
        print(f"  {'bucket':<12} {'n':>4} {'meanT':>6} {'E[1/w]':>7} "
              f"{'R':>9} {'raw %':>9} {'excess %':>9} {'ret/ATR':>9}")
        for lo, hi in buckets:
            b = [t for t in cv if lo <= t["w"] < hi]
            if len(b) < 2:
                continue
            at = [t["ret_atr"] for t in b if t["ret_atr"] == t["ret_atr"]]
            print(f"  {f'{lo}-{hi if hi<1e8 else 999}%':<12} {len(b):>4} "
                  f"{statistics.mean([t['T'] for t in b]):>6.2f} "
                  f"{statistics.mean([1/t['w'] for t in b]):>7.3f} "
                  f"{statistics.mean([t['Rw'] for t in b]):>+9.4f} "
                  f"{statistics.mean([t['ret_pct'] for t in b]):>+9.4f} "
                  f"{statistics.mean([t['excess'] for t in b]):>+9.4f} "
                  f"{statistics.mean(at) if at else float('nan'):>+9.4f}")
        lo_, hi_ = [t for t in cv if t["w"] < 2], [t for t in cv if t["w"] >= 2]
        for key, nm in (("Rw", "R"), ("ret_pct", "raw %"), ("excess", "excess vs basket %")):
            contrast(f"  tight vs wide in {nm}", [t[key] for t in lo_], [t[key] for t in hi_],
                     "tight", "wide")

    print("\n" + "=" * 108)
    print("4.  Is `ret ⟂ w` really independence, or is it the drift x T slope?")
    print("=" * 108)
    print("  12.18f read `ret_pct ~ w` t = +1.07 as 'independence is MEASURED'. A")
    print("  non-rejection is not an affirmation, and drift x T predicts a POSITIVE slope")
    print("  of a specific size. Compare the measured slope against that prediction.")
    for ck in ("ALL", "clean x BUY"):
        cv = co[ck]
        if len(cv) < 10:
            continue
        ws = [t["w"] for t in cv]
        for yk, nm in (("ret_pct", "ret %"), ("T", "T (sessions)"), ("excess", "excess %")):
            ys = [t[yk] for t in cv]
            mx, my = statistics.mean(ws), statistics.mean(ys)
            sxx = sum((x - mx) ** 2 for x in ws)
            if sxx <= 0:
                continue
            b1 = sum((x - mx) * (y - my) for x, y in zip(ws, ys, strict=True)) / sxx
            resid = [y - (my + b1 * (x - mx)) for x, y in zip(ws, ys, strict=True)]
            s2 = sum(r * r for r in resid) / (len(cv) - 2)
            se = math.sqrt(s2 / sxx)
            print(f"  {ck:<14} d({nm})/dw = {b1:+8.5f}  SE {se:.5f}  t {b1/se:+6.2f}")

    print("\n" + "=" * 108)
    print("5.  G5 — the PAIRED drift null (12.20 computed it unpaired)")
    print("=" * 108)
    for ck, cv in co.items():
        if len(cv) < 3:
            continue
        g = [t["entry"] for t in cv]
        cell(f"{ck}: basket over the trade's own window", [t["bench"] for t in cv], g, "%",
             quiet=False)
        cell(f"{ck}: PAIRED excess (trade - basket)", [t["excess"] for t in cv], g, "%")

    print("\n" + "=" * 108)
    print("6.  G6 / plan item 22 — the account earns Rs/day, not R (at the MEASURED hold)")
    print("=" * 108)
    allT = [max(t["T"], 1) for t in tr]
    print(f"  basket drift, full span of this artifact: see the probe log (regime-dependent;")
    print(f"  12.20's +0.0816%/day is the POST-GAP block only -- do not reuse it as a constant)")
    for ck, cv in co.items():
        if len(cv) < 3:
            continue
        mt = statistics.mean([max(t["T"], 1) for t in cv])
        bday = statistics.mean([t["bench"] / max(t["T"], 1) for t in cv])
        for s in (0.0, 15.0):
            n_ = [net_units(t, s) for t in cv]
            perday = statistics.mean([x["pct"] / max(t["T"], 1)
                                      for x, t in zip(n_, cv, strict=True)])
            print(f"  {ck:<30} slip {s:>4.0f} bps  mean T {mt:4.2f}  "
                  f"net {statistics.mean([x['pct'] for x in n_]):+7.3f}%/trade  "
                  f"{perday:+7.4f}%/day   basket {bday:+7.4f}%/day   "
                  f"gap {(perday-bday)*TRADING_DAYS:+7.1f} pp/yr")
    _ = allT

    print("\n" + "=" * 108)
    print("7.  G4 — the `choppy` display filter (ER < 0.30) tested as a SELECTOR")
    print("=" * 108)
    print("  Default-ON in `signals.py`, absent from `restrictions.py`, not applied by the")
    print("  order path, never applied by the corpus. Filed as governance; never measured.")
    for ck in ("ALL", "clean x BUY"):
        cv = [t for t in co[ck] if t["er"] == t["er"]]
        if len(cv) < 6:
            continue
        lo_ = [t for t in cv if t["er"] < 0.30]
        hi_ = [t for t in cv if t["er"] >= 0.30]
        print(f"\n  --- {ck} (n={len(cv)} with an ER) ---")
        for key, nm in (("Rw", "R"), ("ret_pct", "raw %"), ("excess", "excess vs basket %")):
            contrast(f"  ER<0.30 (HIDDEN) vs >=0.30 in {nm}",
                     [t[key] for t in lo_], [t[key] for t in hi_], "hidden", "shown")

    print("\n" + "=" * 108)
    print("8.  C3 — the confidence NORMALIZER: four rival ranking keys, same panels")
    print("=" * 108)
    print("  confluence.py:160 divides by the weight of SCORING factors. The deployed UI")
    print("  sorts DESCENDING on the result. If a rival key ranks better, the information")
    print("  was destroyed by the normalizer rather than absent from the factors.")
    random.seed(11)
    for ck in ("ALL", "clean x BUY"):
        cv = co[ck]
        if len(cv) < 15:
            continue
        ys = [t["Rw"] for t in cv]
        yp = [t["ret_pct"] for t in cv]
        print(f"\n  --- {ck} (n={len(cv)}) ---")
        for key, nm in (("conf", "confidence_pct  <- DEPLOYED"), ("wsum", "raw weighted sum"),
                        ("nsc", "breadth (# scoring factors)"), ("wsc", "weight that scored"),
                        ("top", "concentration (top share)")):
            xs = [abs(t[key]) if key == "wsum" else t[key] for t in cv]
            if len({x for x in xs if x == x}) < 3:
                continue
            r1 = spearman(xs, ys)
            r2 = spearman(xs, yp)
            print(f"  rho({nm:<28}, R) {r1:+.4f}  p {perm_p(xs, ys, r1):.3f}"
                  f"   |  vs raw % {r2:+.4f}  p {perm_p(xs, yp, r2):.3f}")
        nb: dict[int, list[float]] = collections.defaultdict(list)
        for t in cv:
            nb[int(t["nsc"])].append(t["Rw"])
        print("    breadth buckets:  " + "  ".join(
            f"{k} factors n={len(v)} R {statistics.mean(v):+.3f}" for k, v in sorted(nb.items())
            if len(v) >= 3))

    print("=" * 108)
    print("9.  D4 — the posterior, done correctly: the prior belongs on the GROSS mean")
    print("=" * 108)
    print("  A prior of the form 'an unfitted TA scorer has no edge' is a statement about the")
    print("  GROSS mean. Costs are KNOWN, not estimated, so they must not be shrunk toward 0.")
    print("  12.18h D4 had this right; shrinking a NET mean and comparing to 0 does not.")
    print("  The hurdle is E[cost in R] + E[basket in R] over the SAME trades, paired.")
    for ck in ("clean x BUY", "clean x BUY x w>=2%  <- E3"):
        cv = co[ck]
        if len(cv) < 3:
            continue
        g = [t["entry"] for t in cv]
        gross = [t["Rw"] for t in cv]
        m = statistics.mean(gross)
        se_i = statistics.stdev(gross) / math.sqrt(len(gross))
        se_c = clustered_se(gross, g)
        cost = statistics.mean([net_units(t, 0.0)["cost_R"] for t in cv])
        cost15 = statistics.mean([net_units(t, 15.0)["cost_R"] for t in cv])
        bask = statistics.mean([t["bench"] / t["w"] for t in cv])
        print(f"\n  --- {ck} (n={len(cv)}) ---")
        print(f"  gross mean {m:+.4f}R   iid SE {se_i:.4f}   clustered SE {se_c:.4f}")
        print(f"  hurdles: cost(explicit) {cost:+.4f}R   cost(+15bps/leg) {cost15:+.4f}R   "
              f"PAIRED basket {bask:+.4f}R")
        print(f"           break-even {cost:+.4f}   BE+basket {cost+bask:+.4f}   "
              f"BE+basket @15bps {cost15+bask:+.4f}")
        for se_lbl, se in (("iid", se_i), ("date-clustered", se_c)):
            if not (se == se and se > 0):
                continue
            print(f"  SE = {se_lbl} {se:.4f}")
            for tau in (0.03, 0.05, 0.10, 0.20):
                pm = m * tau ** 2 / (tau ** 2 + se ** 2)
                ps = math.sqrt(tau ** 2 * se ** 2 / (tau ** 2 + se ** 2))
                cells = [f"{hl} {100*(1-phi((h-pm)/ps)):6.2f}%" for h, hl in
                         ((0.0, "P(>0)"), (cost, "P(>BE)"), (cost + bask, "P(>BE+basket)"),
                          (cost15 + bask, "P(>BE+basket@15bps)"))]
                print(f"    prior sd {tau:.2f}: post {pm:+.4f}+-{ps:.4f}  " + "  ".join(cells))

    print("\n" + "=" * 108)
    print("10. Rs/day, BOTH aggregations — the choice moves the answer by ~2x")
    print("=" * 108)
    print("  mean-of-ratios counts a same-session exit as a full day; ratio-of-means is what")
    print("  the ACCOUNT experiences (total return over total days deployed). Report both.")
    for ck, cv in co.items():
        if len(cv) < 3:
            continue
        for s_ in (0.0, 15.0):
            n_ = [net_units(t, s_) for t in cv]
            Ts = [max(t["T"], 1) for t in cv]
            mor = statistics.mean([x["pct"] / T for x, T in zip(n_, Ts, strict=True)])
            rom = sum(x["pct"] for x in n_) / sum(Ts)
            bmor = statistics.mean([t["bench"] / T for t, T in zip(cv, Ts, strict=True)])
            brom = sum(t["bench"] for t in cv) / sum(Ts)
            print(f"  {ck:<30} slip {s_:>4.0f}  mean-of-ratios {mor:+7.4f}%/d vs "
                  f"{bmor:+7.4f} = {(mor-bmor)*TRADING_DAYS:+7.1f} pp/yr  |  "
                  f"ratio-of-means {rom:+7.4f}%/d vs {brom:+7.4f} = "
                  f"{(rom-brom)*TRADING_DAYS:+7.1f} pp/yr")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    main(ap.parse_args().csv)
