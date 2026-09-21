"""M93 cluster-SE audit — re-measures the overnight-gap result with the correct standard error.

⛔⛔ `signed_displacement_study.py` computes `stddev/sqrt(count)` over STOCK-DAYS treated as
independent. Gap days cluster by session almost by construction — an index-wide move produces
hundreds of same-direction gaps on one morning (measured: max 243 in a single session). This
rebuilds the identical event set and reports the iid t beside the session-clustered one.

Measured 2026-09-21: the long arm deflates **+14.33 -> +1.66 (8.6x)** and stops being
significant; pooled goes +22.52 -> +3.33, below this project's t = 3.6 bar. Record:
`docs/analysis/m93-audit-2026-09-21.md`.

⭐ The reconstruction reproduces the published figures exactly (+0.6505% / t +14.33 against
+0.650% / +14.3), so this is the same measurement with only the SE corrected.

READ-ONLY. SELECTs only.
"""

import asyncio
import logging
import statistics
import sys
from collections.abc import Callable

sys.path.insert(0, "/home/nithin/code/agent/Claude/trading-platform/backend")
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.services.block_bootstrap import cluster_robust_mean_t  # noqa: E402
from sqlalchemy import text  # noqa: E402

# M93's own construction, but returning ROWS so the SE can be rebuilt properly.
SQL = """
WITH coh AS (
  SELECT y, stock_id FROM (
    SELECT y.y, o.stock_id,
      row_number() OVER (PARTITION BY y.y ORDER BY
        percentile_cont(0.5) WITHIN GROUP (ORDER BY o.close*o.volume) DESC) rn
    FROM (SELECT generate_series(2020,2026) AS y) y
    JOIN ohlcv_1d o ON o.time >= make_date(y.y-1,1,1) AND o.time < make_date(y.y,1,1)
    GROUP BY y.y, o.stock_id HAVING count(*) >= 40) t WHERE rn <= 250),
g AS (
  SELECT o.stock_id, o.time::date d, o.close,
         lead(o.open,1) OVER w AS fill,
         lead(o.close,1) OVER w AS exit_close,
         lead(o.time,1) OVER w AS event_time
  FROM ohlcv_1d o
  JOIN coh ON coh.stock_id=o.stock_id AND coh.y=EXTRACT(YEAR FROM o.time)::int
  WINDOW w AS (PARTITION BY o.stock_id ORDER BY o.time))
SELECT stock_id, event_time::date AS session,
       (fill-close)/close*100 AS gap_pct,
       (exit_close-fill)/fill*100 AS fwd_pct
FROM g
WHERE close>0 AND fill>0 AND exit_close IS NOT NULL
  AND abs((fill-close)/close) <= 0.25
"""

async def main() -> None:
    async with AsyncSessionFactory() as db:
        rows = (await db.execute(text(SQL))).all()
    print(f"total stock-days: {len(rows):,}")

    def report(
        label: str,
        sel: Callable[[float], bool],
        sign: Callable[[float], int],
    ) -> None:
        cell = [(r[1], float(sign(float(r[2]))) * float(r[3])) for r in rows if sel(float(r[2]))]
        if not cell:
            return
        sessions = sorted({s for s, _ in cell})
        vals = [v for _, v in cell]
        n, mean = len(vals), statistics.mean(vals)
        sd = statistics.stdev(vals)
        iid_t = mean / (sd / (n ** 0.5))
        res = cluster_robust_mean_t([v for _, v in cell], [s for s, _ in cell])
        ct = res[2] if res else None
        n_clusters = res[3] if res else 0
        # session-level cross-sectional means
        per: dict[object, list[float]] = {}
        for s, v in cell:
            per.setdefault(s, []).append(v)
        sess_means = [statistics.mean(v) for v in per.values()]
        sig_sess = statistics.stdev(sess_means)
        sess_t = statistics.mean(sess_means) / (sig_sess / (len(sess_means) ** 0.5))
        print(f"\n--- {label} ---")
        print(f"  events {n:,}   sessions {len(sessions):,}   events/session "
              f"median {statistics.median([len(v) for v in per.values()]):.0f} "
              f"max {max(len(v) for v in per.values())}")
        print(f"  mean {mean:+.4f}%   sd {sd:.3f}")
        print(f"  t  IID (M93's method)      = {iid_t:+.2f}")
        print(f"  t  CLUSTERED by session    = {ct:+.2f}   ({n_clusters:,} clusters)"
              if ct is not None else "  clustered t: n/a")
        print(f"  t  session-mean series     = {sess_t:+.2f}   (sigma_session {sig_sess:.3f}%)")
        if ct:
            print(f"  DEFLATION                  = {abs(iid_t)/abs(ct):.1f}x   "
                  f"(vs t=3.6 bar: {'CLEARS' if abs(ct) >= 3.6 else 'FAILS'})")

    report("gap <= -2%  (LONG arm, raw fwd)", lambda g: g < -2, lambda g: +1)
    report("gap >= +2%  (SHORT arm, sign-adj)", lambda g: g > 2, lambda g: -1)
    report("POOLED sign-adjusted |gap| >= 2%",
           lambda g: abs(g) > 2, lambda g: -1 if g > 0 else +1)

asyncio.run(main())
