"""Market-regime study runner — loads ~3y of index + VIX history and writes the regime report.

    uv run python scripts/regime_study.py [--date YYYY-MM-DD]

Reads index_ohlcv_1d (NIFTY50 + Bank/Fin Nifty) + india_vix_daily, classifies every day into a
level×breadth quadrant, measures forward returns, and writes docs/analysis/regime-study-<date>.md.
Read-only; touches no signal/live path. The analytical core lives in app.services.regime_study.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services import regime_study as rs  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ANALYSIS_DIR = _REPO_ROOT / "docs" / "analysis"
_INDICES = ["NIFTY50", "BANKNIFTY", "FINNIFTY"]


async def _run(day: date) -> int:
    from sqlalchemy import text

    async with AsyncSessionFactory() as db:
        id_by_sym = {
            sym: iid
            for iid, sym in (await db.execute(text("SELECT id, symbol FROM indices"))).all()
        }
        # date → close, per index
        closes_by_sym: dict[str, dict[date, float]] = {}
        for sym in _INDICES:
            iid = id_by_sym.get(sym)
            if iid is None:
                closes_by_sym[sym] = {}
                continue
            rows = (
                await db.execute(
                    text(
                        "SELECT trade_date, close FROM index_ohlcv_1d "
                        "WHERE index_id = :iid ORDER BY trade_date"
                    ),
                    {"iid": iid},
                )
            ).all()
            closes_by_sym[sym] = {r.trade_date: float(r.close) for r in rows}
        vix_by_date = {
            r.trade_date: float(r.close)
            for r in (
                await db.execute(
                    text(
                        "SELECT trade_date, close FROM india_vix_daily "
                        "WHERE close IS NOT NULL ORDER BY trade_date"
                    )
                )
            ).all()
        }
        fii_cov = (
            await db.execute(
                text("SELECT count(*), min(trade_date), max(trade_date) FROM fii_dii_daily")
            )
        ).one()

    nifty = closes_by_sym.get("NIFTY50", {})
    if not nifty:
        print("no NIFTY50 index history — run scripts/backfill_indices.py first", flush=True)
        return 1
    # common date axis: NIFTY dates present in every index we have data for, ≤ the report day.
    nifty_own = sorted(d for d in nifty if d <= day)
    dates = sorted(
        d
        for d in nifty_own
        if all(d in closes_by_sym[s] for s in _INDICES if closes_by_sym[s])
    )
    # The intersection axis is used for NIFTY's OWN 200-DMA window + forward horizons, so a gap in
    # Bank/FinNifty would silently drop interior NIFTY sessions and distort them. Today all three
    # share an identical 774-date axis; warn loudly if that stops being true (quant-verifier #5).
    dropped = len(nifty_own) - len(dates)
    if dropped:
        print(
            f"⚠ WARNING: {dropped} NIFTY sessions dropped by the multi-index intersection — the "
            "200-DMA window/forward horizons are distorted. Align Bank/FinNifty history before "
            "trusting this run.",
            flush=True,
        )
    nifty_closes = [nifty[d] for d in dates]
    vix = [vix_by_date.get(d) for d in dates]
    closes_by_index = {
        s: [closes_by_sym[s][d] for d in dates] for s in _INDICES if closes_by_sym[s]
    }

    days = rs.classify_days(dates, nifty_closes, vix)
    if not days:
        print("not enough index history to classify (need ≥200 sessions)", flush=True)
        return 1
    qstats = rs.quadrant_stats(days)
    episodes = rs.below_episodes(days)
    disp = rs.dispersion(days, closes_by_index)
    robust = rs.robustness(days)

    fii_n, fii_min, fii_max = fii_cov
    fii_note = (
        f"FII/DII recorder holds only {fii_n} sessions ({fii_min} → {fii_max}) — far too little "
        "for a multi-year regime-flow study. Backfill FII/DII history to unlock the flow angle."
        if fii_n and fii_n < 200
        else f"FII/DII coverage: {fii_n} sessions ({fii_min} → {fii_max})."
    )

    md = rs.render_markdown(
        day=day,
        span=(days[0].d, days[-1].d),
        n_days=len(days),
        qstats=qstats,
        episodes=episodes,
        disp=disp,
        indices=list(closes_by_index.keys()),
        fii_dii_note=fii_note,
        robust=robust,
    )
    _ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = _ANALYSIS_DIR / f"regime-study-{day.isoformat()}.md"
    out.write_text(md)
    print(f"wrote {out.relative_to(_REPO_ROOT)} — {len(days)} classified sessions", flush=True)
    bs, bw = qstats["below+strong"], qstats["below+weak"]
    print(
        f"[thesis] below+strong fwd-20 {bs.avg_fwd(20)} (n={bs.fwd_n(20)}) vs "
        f"below+weak {bw.avg_fwd(20)} (n={bw.fwd_n(20)}) — direction only; windows overlap",
        flush=True,
    )
    print(
        f"[robustness] non-overlap gap {robust.no_gap} (weak n={robust.no_n_weak}, "
        f"strong n={robust.no_n_strong}); bootstrap P(weak>strong) {robust.boot_p_positive}",
        flush=True,
    )
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Market-regime study (~3y)")
    ap.add_argument("--date", type=str, default=None, help="report day YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    raise SystemExit(asyncio.run(_run(day)))


if __name__ == "__main__":
    main()
