"""Queue item 6, third study — B7's excursion surface and T=0 contrast, re-run.

⭐ **Why B7 is the one in item 6 most likely to move.** Its headline contrast is
`T = 0` (same-session exit) against `T ≥ 1`, published at **t = −4.16** with the caveat
*"but it is the tight-stop cohort the order path refuses"*. That caveat IS the delete
treatment, stated in prose and never applied. A same-session exit is exactly what a fill
that gapped through its own stop produces, so the two populations overlap by construction.

⭐⭐ **And its dependence is not the mean's.** The contrast has both arms on the SAME days,
so combining each arm's standard error with `hypot` — what `b7_hazard._report` does —
assumes the day shock is independent across arms when it is the *same day*. Run as one
regression with a group indicator, clustered on the entry session, the covariance cancels
where it should. `test_an_unbalanced_contrast_is_where_clustering_actually_bites` is the
canary for that, and it is the relevant regime here: same-session exits concentrate on
volatile days, so whole days lean one way.

⚠ **Cohort held fixed** (`swing_dependence_probe.load_frames`, i.e. the M62 `now() - 180
days` ranking). Known look-ahead, deliberately NOT repaired here — item 6 asks whether the
headline survives the delete treatment and an honest SE, and changing two things at once
would make the answer unreadable.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.block_bootstrap import (  # noqa: E402
    cluster_robust_mean_t,
    cluster_robust_slope_t,
    design_effect,
    intraclass_correlation,
)
from app.signals.restrictions import through_stop_reason  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "analysis"


def refused(t: dict[str, Any]) -> bool:
    """Item 4's predicate, applied to a probe row.

    ⚠ `w` cannot serve: the probe computes it from the FILL, so a fill through its stop still
    reports a positive risk distance (M64). That is why `stop_px` was added to the dump.
    """
    stop = t.get("stop_px")
    if stop is None or stop != stop or not t.get("entry_px"):  # noqa: PLR0124  (NaN check)
        return False
    return (
        through_stop_reason(
            side="BUY" if t["dir"] == "BUY" else "SELL",
            price=Decimal(str(t["entry_px"])),
            stop_loss=Decimal(str(stop)),
        )
        is not None
    )


def _naive(xs: list[float]) -> tuple[float, float, float]:
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else 0.0), 0.0, 0.0
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / n**0.5
    return m, se, (m / se if se > 0 else 0.0)


def _contrast(recs: list[dict[str, Any]], label: str) -> tuple[list[str], float, float]:
    """T=0 vs T>=1 on winsorized R, naive and clustered. Returns (lines, mean, t_clustered)."""
    y = [float(r["Rw"]) for r in recs]
    x = [1.0 if float(r["T"]) == 0 else 0.0 for r in recs]
    g = [r["entry"] for r in recs]
    z = [v for v, xi in zip(y, x, strict=True) if xi == 1.0]
    nz = [v for v, xi in zip(y, x, strict=True) if xi == 0.0]
    if len(z) < 3 or len(nz) < 3:
        return ([f"| {label} | too few in one arm | | | | |"], 0.0, 0.0)

    m1, s1, _ = _naive(z)
    m0, s0, _ = _naive(nz)
    diff = m1 - m0
    se_naive = (s1 * s1 + s0 * s0) ** 0.5
    t_naive = diff / se_naive if se_naive > 0 else 0.0

    res = cluster_robust_slope_t(y, x, g)
    if res is None:
        return ([f"| {label} | not assessable | | | | |"], diff, 0.0)
    b, se_c, t_c, n_groups = res
    lines = [
        f"| {label} | {len(z)} / {len(nz)} | {b:+.4f} | {t_naive:+.2f} | {t_c:+.2f} | {n_groups} |"
    ]
    return lines, b, t_c


def _surface(recs: list[dict[str, Any]], label: str) -> list[str]:
    """MFE / |MAE| — the 'is there information the geometry hands back' question."""
    g = [r["entry"] for r in recs]
    out = []
    for field, name in (("mfe_r", "MFE"), ("mae_r", "MAE"), ("Rw", "realised R")):
        vals = [float(r[field]) for r in recs]
        m, _se, t_n = _naive(vals)
        rob = cluster_robust_mean_t(vals, g)
        t_c = rob[2] if rob else float("nan")
        out.append(f"| {label} · {name} | {len(vals)} | {m:+.4f} | {t_n:+.2f} | {t_c:+.2f} |")
    mfe = statistics.mean([float(r["mfe_r"]) for r in recs])
    mae = abs(statistics.mean([float(r["mae_r"]) for r in recs]))
    ratio = mfe / mae if mae else float("nan")
    out.append(f"| {label} · **MFE / \\|MAE\\|** | {len(recs)} | **{ratio:.3f}** | | |")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="swing_dependence_probe --dump-trades output (needs stop_px)")
    ap.add_argument("--stocks", type=int, default=250)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import b7_hazard as b7
    from swing_dependence_probe import load_frames

    trades = b7._load(args.csv)
    if trades and "stop_px" not in trades[0]:
        raise SystemExit(
            "this dump has no `stop_px` column — re-run swing_dependence_probe with the "
            "current code, or the delete treatment cannot be applied (M64: `w` is computed "
            "from the fill and is blind to a through-stop entry)"
        )
    frames = asyncio.run(load_frames(args.stocks))
    recs, missing = b7.walk_excursions(trades, frames)
    print(f"trades {len(trades)} · frames {len(frames)} · excursions {len(recs)} "
          f"(unmatched {missing})", flush=True)

    kept = [r for r in recs if not refused(r)]
    dropped = len(recs) - len(kept)

    today = datetime.now(tz=UTC).date().isoformat()
    vals = [float(r["Rw"]) for r in recs]
    dates = [r["entry"] for r in recs]
    icc, m0, n_groups = intraclass_correlation(vals, dates)

    lines = [
        f"## B7 — excursion surface and the T=0 contrast, re-run ({today})",
        "",
        f"- {len(recs)} trades across {n_groups} entry sessions (effective cluster size "
        f"{m0:.2f}); ICC {icc:+.4f}; design effect **{design_effect(vals, dates):.2f}x** "
        f"on the variance",
        f"- **delete treatment: {dropped} of {len(recs)} "
        f"({100 * dropped / max(len(recs), 1):.3f}%) refused by the live predicate**",
        "",
        "⇒ **estimator: cluster-robust by entry session**, and for the contrast a single "
        "regression on a group indicator rather than two separate SEs — both arms appear on "
        "the same days, so `hypot` would treat one day's shock as two independent draws.",
        "",
        "### The T=0 contrast (published: t = −4.16, naive)",
        "",
        "| cohort | n T=0 / T≥1 | contrast (R) | t naive | t clustered | sessions |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    l_all, m_all, t_all = _contrast(recs, "all")
    l_keep, m_keep, t_keep = _contrast(kept, "delete-treated")
    lines += l_all + l_keep
    lines += [
        "",
        "### The excursion surface (published: MFE/|MAE| 0.83 / 1.12 ⇒ no geometry repair)",
        "",
        "| cohort | n | mean | t naive | t clustered |",
        "|---|--:|--:|--:|--:|",
    ]
    lines += _surface(recs, "all")
    lines += _surface(kept, "delete-treated")

    flipped = (m_all > 0) != (m_keep > 0)
    crossed = (abs(t_all) >= 1.96) != (abs(t_keep) >= 1.96)
    verdict = (
        f"⛔⛔ **T=0 contrast SIGN CHANGED** ({m_all:+.4f} → {m_keep:+.4f}) — headline INVALID"
        if flipped
        else f"⛔ **T=0 contrast crossed |t| = 1.96** ({t_all:+.2f} → {t_keep:+.2f}) — "
        "headline INVALID"
        if crossed
        else f"✅ **T=0 contrast survives** ({m_all:+.4f} → {m_keep:+.4f}, "
        f"t {t_all:+.2f} → {t_keep:+.2f})"
    )
    lines += ["", "**F9 falsifier:**", "", f"- {verdict}", ""]

    text = "\n".join(lines) + "\n"
    print("\n" + text)
    dest = Path(args.out) if args.out else OUT / f"item6-b7-{today}.md"
    dest.write_text(text)
    print(f"→ {dest}")


if __name__ == "__main__":
    main()
