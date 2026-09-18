"""Queue item 6 — re-run D5 and D1 under item 4's delete treatment, with the estimator the
dependence actually calls for.

⭐⭐ **THE ORDER OF OPERATIONS IS THE POINT.** The queue's wording is
*"characterise the dependence first, then choose the estimator — not 'apply Newey-West'"*.
So this script MEASURES the dependence structure and prints it before any corrected number
appears, and the estimator it then uses is the one that measurement implies. Reaching for
Newey-West here would be wrong on its own terms: it corrects SERIAL correlation along one
axis, and what these studies have is a GROUPING — many trades sharing one session.

⭐ **ONE THING CHANGES AT A TIME.** The cohort is left exactly as each published study drew
it, look-ahead and all (`tp_geometry_study._load_frames` ranks liquidity across the whole
window and filters on today's `is_active`). That defect is real and is NOT fixed here: the
question item 6 asks is *"does the headline survive the delete treatment and an honest
SE"*, and changing the cohort in the same pass would confound the answer beyond reading.
The cohort belongs to item 14's consumers. **It is recorded in the output so nobody reads
these numbers as clean.**

⛔ **The falsifier, from item 4 (F9), applied here rather than left in prose:** a headline
is invalid if it CHANGES SIGN, or crosses |t| = 1.96, *under the same estimator the re-run
uses*. And M85 predicts the delete shift by stop width — +0.0282R at the 2% order-path
floor, +0.0052R at the median 5% — so the measured shift is checked against a number
published before the run.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from app.backtest.entry_gap import is_unfillable, partition  # noqa: E402
from app.services.block_bootstrap import (  # noqa: E402
    cluster_robust_mean_t,
    design_effect,
    intraclass_correlation,
)

OUT = Path(__file__).resolve().parents[2] / "docs" / "analysis"


def _naive_t(xs: list[float]) -> tuple[float, float, float]:
    """mean, iid SE, t — the number every published headline used."""
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else 0.0), 0.0, 0.0
    mean = statistics.mean(xs)
    sd = statistics.stdev(xs)
    se = sd / n**0.5
    return mean, se, (mean / se if se > 0 else 0.0)


def characterise(values: list[float], dates: list[Any], label: str) -> list[str]:
    """Print the dependence BEFORE any corrected statistic. Returns report lines."""
    icc, m0, n_groups = intraclass_correlation(values, dates)
    deff = design_effect(values, dates)
    mean, se_iid, t_iid = _naive_t(values)
    rob = cluster_robust_mean_t(values, dates)
    lines = [
        f"### Dependence — {label}",
        "",
        f"- observations **{len(values)}** across **{n_groups}** sessions "
        f"(effective cluster size m0 = {m0:.2f})",
        f"- intraclass correlation by session **{icc:+.4f}**",
        f"- design effect **{deff:.2f}x** on the VARIANCE ⇒ effective n "
        f"**{len(values) / deff:.0f}**, SE understated **{deff**0.5:.2f}x** if ignored",
    ]
    if rob is None:
        lines.append("- ⛔ cluster-robust SE **not assessable** (fewer than two sessions)")
        return lines
    _m, se_c, t_c, g = rob
    lines += [
        f"- iid SE {se_iid:.4f} (t {t_iid:+.2f}) vs cluster-robust SE {se_c:.4f} "
        f"(t {t_c:+.2f}) over {g} clusters",
        "",
        f"⇒ **estimator: cluster-robust by entry session.** The dependence is a GROUPING "
        f"({len(values) / max(n_groups, 1):.1f} trades per session sharing that session's "
        f"market move), not a lag, so a serial-correlation correction would be the wrong "
        f"instrument.",
        "",
    ]
    return lines


def _stat_block(values: list[float], dates: list[Any], label: str) -> tuple[str, float, float]:
    """One line comparing naive and clustered inference. Returns (line, mean, t_clustered)."""
    mean, se_iid, t_iid = _naive_t(values)
    rob = cluster_robust_mean_t(values, dates)
    if rob is None:
        return f"| {label} | {len(values)} | {mean:+.4f} | {t_iid:+.2f} | — | — |", mean, 0.0
    _m, se_c, t_c, g = rob
    return (
        f"| {label} | {len(values)} | {mean:+.4f} | {t_iid:+.2f} | {t_c:+.2f} | {g} |",
        mean,
        t_c,
    )


def _verdict(name: str, t_before: float, t_after: float, m_before: float, m_after: float) -> str:
    """F9, applied rather than described."""
    flipped = (m_before > 0) != (m_after > 0)
    crossed = (abs(t_before) >= 1.96) != (abs(t_after) >= 1.96)
    if flipped:
        return (
            f"⛔⛔ **{name}: SIGN CHANGED** ({m_before:+.4f} → {m_after:+.4f}) "
            "— headline INVALID"
        )
    if crossed:
        return (
            f"⛔ **{name}: crossed |t| = 1.96** ({t_before:+.2f} → {t_after:+.2f}) — "
            "headline INVALID"
        )
    return (
        f"✅ **{name}: survives** (mean {m_before:+.4f} → {m_after:+.4f}, "
        f"t {t_before:+.2f} → {t_after:+.2f})"
    )


# ── D5 ───────────────────────────────────────────────────────────────────────

def run_d5(frames: dict[str, Any]) -> list[str]:
    import tp_geometry_study as d5

    print(f"D5: {len(frames)} stocks", flush=True)

    records: dict[tuple[str, pd.Timestamp], Any] = {}
    variants = d5._collect(frames, records=records)
    base = variants["baseline_frozen"]
    print(f"D5: {len(base)} baseline signals", flush=True)

    # ⛔ THE PUBLISHED STATISTIC IS SWING+POSITIONAL ONLY (`_TARGET_CLASSES`, applied in the
    # study's own `main`). A re-run over all classes would be a different quantity wearing the
    # same name — the error that withdrew §16.1b's t = −2.19 as "the WRONG COHORT's number".
    keys = sorted(
        (k for k, r in base.items() if r.classification in d5._TARGET_CLASSES),
        key=lambda k: (k[1], k[0]),
    )
    dates = [k[1] for k in keys]
    r_base = [d5._r_of(base[k]) for k in keys]

    lines = ["## D5 — target geometry (`tp_geometry_study`)", ""]
    lines += characterise(r_base, dates, "D5 baseline R")

    tradeable, refused = partition([records[k] for k in keys])
    lines += [
        f"**Delete treatment:** {len(refused)} of {len(keys)} baseline signals "
        f"({100 * len(refused) / max(len(keys), 1):.3f}%) are trades the live engine would "
        f"have refused at their own fill price.",
        "",
        "| variant | n | paired ΔR | t iid | t clustered | sessions |",
        "|---|--:|--:|--:|--:|--:|",
    ]

    verdicts: list[str] = []
    for name in d5._ALL_NAMES[1:]:
        var = variants[name]
        shared = [k for k in keys if k in var]
        d_all = [d5._r_of(var[k]) - d5._r_of(base[k]) for k in shared]
        dt_all = [k[1] for k in shared]
        line_b, m_b, t_b = _stat_block(d_all, dt_all, f"{name} — all")
        lines.append(line_b)

        kept = [k for k in shared if not is_unfillable(records[k])]
        d_keep = [d5._r_of(var[k]) - d5._r_of(base[k]) for k in kept]
        dt_keep = [k[1] for k in kept]
        line_a, m_a, t_a = _stat_block(d_keep, dt_keep, f"{name} — delete-treated")
        lines.append(line_a)
        verdicts.append(_verdict(name, t_b, t_a, m_b, m_a))

    # the baseline's own mean R, which is the other published number
    kept_keys = [k for k in keys if not is_unfillable(records[k])]
    r_keep = [d5._r_of(base[k]) for k in kept_keys]
    lb, mb, tb = _stat_block(r_base, dates, "baseline mean R — all")
    la, ma, ta = _stat_block(r_keep, [k[1] for k in kept_keys], "baseline mean R — delete-treated")
    lines += [lb, la, ""]
    lines += [
        f"**Delete shift on the baseline mean: {ma - mb:+.4f}R** "
        f"(M85 predicted +0.0052R at the median 5% stop, +0.0282R at the 2% floor — "
        f"⚠ note M85's sign convention is the magnitude; a delete can only pull the mean "
        f"DOWN, since every removed trade booked exactly +1.000R).",
        "",
        "**F9 falsifier:**",
        "",
    ]
    lines += [f"- {v}" for v in verdicts]
    lines.append(f"- {_verdict('baseline mean R', tb, ta, mb, ma)}")
    lines.append("")
    return lines


# ── D1 ───────────────────────────────────────────────────────────────────────

def run_d1(frames: dict[str, Any]) -> list[str]:
    """⛔⛔ The statistic here was WRONG in the first draft and the smoke run caught it.

    I computed a PAIRED contrast on keys present in both runs. It came back **exactly
    +0.0000**, and that is structural rather than lucky: for a key in both books the trade
    is identical — same entry, stop and target — because RVOL changes only whether a signal
    clears the 70% gate, never the levels once it does. A paired-on-shared contrast for this
    intervention is degenerate BY CONSTRUCTION and can only ever report zero.

    D1's real statistics are the published two: **§1** RVOL buckets on baseline signals (the
    design-free test — if RVOL carries no outcome information here, no factor design can
    extract any) and **§2** the four COHORT means, where the headline `−0.291R` lives in the
    set RVOL newly admitted (A∖B).
    """
    import rvol_factor_study as d1
    from app.backtest import engine as engine_mod

    print(f"D1: {len(frames)} stocks", flush=True)
    rec_b: dict[tuple[str, pd.Timestamp], Any] = {}
    baseline = d1._run(frames, records=rec_b)
    print(f"D1: baseline {len(baseline)} signals", flush=True)

    orig = engine_mod.__dict__["run_all_factors"]
    engine_mod.__dict__["run_all_factors"] = d1._augmented_run_all_factors
    try:
        rec_a: dict[tuple[str, pd.Timestamp], Any] = {}
        augmented = d1._run(frames, records=rec_a)
    finally:
        engine_mod.__dict__["run_all_factors"] = orig
    print(f"D1: augmented {len(augmented)} signals", flush=True)

    def keys_of(book: dict[Any, Any], subset: set[Any]) -> list[Any]:
        return sorted(
            (k for k in subset if book[k].classification in d1._TARGET_CLASSES),
            key=lambda k: (k[1], k[0]),
        )

    b_keys, a_keys = set(baseline), set(augmented)
    added, dropped, shared = a_keys - b_keys, b_keys - a_keys, a_keys & b_keys

    lines = ["## D1 — RVOL as a graded factor (`rvol_factor_study`)", ""]
    kb = keys_of(baseline, b_keys)
    lines += characterise([d1._r(baseline[k]) for k in kb], [k[1] for k in kb], "D1 baseline R")

    n_ref = sum(1 for k in kb if is_unfillable(rec_b[k]))
    lines += [
        f"**Delete treatment on the baseline book:** {n_ref} of {len(kb)} "
        f"({100 * n_ref / max(len(kb), 1):.3f}%) refused by the live predicate.",
        "",
        "⚠ Adding a factor is NOT additive — the scorer normalises by the weight of SCORING "
        f"factors — so the books are not nested: **added {len(added)}** (a weak signal lifted "
        f"over 70), **dropped {len(dropped)}** (a strong one diluted under it), shared "
        f"{len(shared)}.",
        "",
        "### §2 — the four cohorts (the published headline is *RVOL added*)",
        "",
        "| set | n | mean R | t iid | t clustered | sessions |",
        "|---|--:|--:|--:|--:|--:|",
    ]

    head: dict[str, tuple[float, float]] = {}
    for label, book, subset, recs in (
        ("baseline book B", baseline, b_keys, rec_b),
        ("augmented book A", augmented, a_keys, rec_a),
        ("RVOL added (A∖B)", augmented, added, rec_a),
        ("RVOL dropped (B∖A)", baseline, dropped, rec_b),
    ):
        ks = keys_of(book, subset)
        if not ks:
            lines.append(f"| {label} | 0 | — | — | — | — |")
            continue
        vals = [d1._r(book[k]) for k in ks]
        line, m, t = _stat_block(vals, [k[1] for k in ks], label)
        lines.append(line)
        kept = [k for k in ks if not is_unfillable(recs[k])]
        vk = [d1._r(book[k]) for k in kept]
        line2, m2, t2 = _stat_block(vk, [k[1] for k in kept], f"{label} — delete-treated")
        lines.append(line2)
        head[label] = (m, t)
        head[label + "|after"] = (m2, t2)

    lines += [
        "",
        "### §1 — does RVOL-at-entry predict outcome at all? (baseline, design-free)",
        "",
        "⭐ The decisive half: if RVOL carries no outcome information among signals we already "
        "mint, no factor design can extract edge from it.",
        "",
        "| RVOL bucket | n | mean R | t iid | t clustered | sessions |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    kept_b = [k for k in kb if not is_unfillable(rec_b[k])]
    for label, lo, hi in (("<1.0x", 0.0, 1.0), ("1.0-1.5x", 1.0, 1.5),
                          ("1.5-2.0x", 1.5, 2.0), (">=2.0x", 2.0, 1e9)):
        ks = [k for k in kept_b if lo <= baseline[k].rvol < hi]
        if len(ks) < 3:
            lines.append(f"| {label} | {len(ks)} | — | — | — | — |")
            continue
        line, _m, _t = _stat_block(
            [d1._r(baseline[k]) for k in ks], [k[1] for k in ks], label
        )
        lines.append(line)

    lines += ["", "**F9 falsifier** (on the published headline, the *added* set):", ""]
    if "RVOL added (A∖B)" in head:
        mb, tb = head["RVOL added (A∖B)"]
        ma, ta = head["RVOL added (A∖B)|after"]
        lines.append(f"- {_verdict('D1 RVOL-added mean R', tb, ta, mb, ma)}")
    else:
        lines.append("- ⛔ the added set is empty on this cohort — not assessable")
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", choices=["d5", "d1", "both"], default="both")
    ap.add_argument("--max-stocks", type=int, default=None,
                    help="override for a smoke run; default = each study's published value")
    ap.add_argument("--min-rows", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    today = datetime.now(tz=UTC).date().isoformat()
    lines = [
        f"# Queue item 6 — D5 / D1 re-run under the delete treatment ({today})",
        "",
        "**What changed vs the published runs: TWO things, and only two.** (1) item 4's "
        "delete treatment removes trades whose fill was already through its own stop — "
        "trades the live engine refuses and every study silently counted as +1.000R (M64). "
        "(2) inference is cluster-robust by entry session instead of iid.",
        "",
        "⛔ **What did NOT change, deliberately: the cohort.** Both studies still draw it the "
        "way they published it — `_load_frames` ranks liquidity across the WHOLE window and "
        "filters on today's `is_active`, so it is look-ahead-selected and survivorship-"
        "filtered. Changing it in the same pass would confound the answer to the question "
        "item 6 actually asks. **These numbers are therefore corrected for the delete "
        "treatment and the SE, and remain contaminated by the cohort.**",
        "",
    ]
    dest = Path(args.out) if args.out else OUT / f"item6-rerun-{today}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    def flush() -> None:
        """⛔ Write after EVERY study. The first version of this script wrote once at the
        end, so a crash in D1 threw away 1h48m of completed D5 work. A long job that
        reports nothing until it finishes has no partial-failure mode, only total loss."""
        dest.write_text("\n".join(lines) + "\n")

    # ⛔⛔ ONE `asyncio.run` FOR EVERY DB TOUCH, and this is not style.
    # `AsyncSessionFactory`'s pool binds its connections to the loop that created them, so a
    # SECOND `asyncio.run` — which builds a NEW loop — fails with "Future attached to a
    # different loop" the moment it reuses a pooled connection. That is exactly how the
    # 1h48m run died, at D1's frame load, after D5 had already finished.
    d5_n = args.max_stocks if args.max_stocks is not None else 250
    d1_n = args.max_stocks if args.max_stocks is not None else 150

    async def _load_all() -> tuple[dict[str, Any], dict[str, Any]]:
        import tp_geometry_study as d5

        f5 = (
            await d5._load_frames("liquid", args.min_rows, d5_n)
            if args.study in ("d5", "both")
            else {}
        )
        f1 = (
            await d5._load_frames("liquid", args.min_rows, d1_n)
            if args.study in ("d1", "both")
            else {}
        )
        return f5, f1

    frames_d5, frames_d1 = asyncio.run(_load_all())
    print(f"frames loaded — D5 {len(frames_d5)} · D1 {len(frames_d1)}", flush=True)

    if args.study in ("d5", "both"):
        lines += run_d5(frames_d5)
        flush()
        print(f"→ D5 section written to {dest}", flush=True)
    if args.study in ("d1", "both"):
        lines += run_d1(frames_d1)
        flush()

    print("\n" + "\n".join(lines))
    print(f"→ {dest}")


if __name__ == "__main__":
    main()
