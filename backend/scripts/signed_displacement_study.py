"""SIGNED-DISPLACEMENT STUDY (Claude's point 2), run structurally.

The live book is n=4 — the 99-trade audit died with the dev DB on 2026-09-07. But the geometry
is reproducible from prices alone: the engine's signal entry IS the prior close
(`signal_service.py:246`) and the backtest fill IS the next bar's open
(`engine.py:212`). So the displacement a click experiences has the same shape as the
overnight gap, and the question "does a favourable fill predict a better outcome?" becomes
"does a gap CONTINUE or REVERT over the swing horizon?"

For a BUY the favourable displacement is a gap DOWN (you buy cheaper); for a SELL, a gap UP.
If gaps REVERT, favourable fills are genuinely good and a one-sided limit is right.
If gaps CONTINUE, a favourable fill means you entered against momentum.

Forward return is measured FROM THE FILL (the open), which is where the money actually is.
READ-ONLY. Strictly-PIT annual top-250 cohort. |gap| > 25% dropped as corporate actions.
"""
import asyncio
import sys

sys.path.insert(0, "/home/nithin/code/agent/Claude/trading-platform/backend")
from app.db.session import AsyncSessionFactory
from sqlalchemy import text

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
         lead(o.open, 1) OVER w AS fill,
         lead(o.close, {H}) OVER w AS exit_close
  FROM ohlcv_1d o
  JOIN coh ON coh.stock_id=o.stock_id AND coh.y=EXTRACT(YEAR FROM o.time)::int
  WINDOW w AS (PARTITION BY o.stock_id ORDER BY o.time)),
x AS (
  SELECT (fill-close)/close*100 AS gap_pct,
         (exit_close-fill)/fill*100 AS fwd_pct
  FROM g WHERE close>0 AND fill>0 AND exit_close IS NOT NULL
    AND abs((fill-close)/close) <= 0.25)
SELECT CASE
    WHEN gap_pct < -2 THEN 'a. gap < -2%'
    WHEN gap_pct < -1 THEN 'b. -2 to -1%'
    WHEN gap_pct < -0.5 THEN 'c. -1 to -0.5%'
    WHEN gap_pct < 0 THEN 'd. -0.5 to 0%'
    WHEN gap_pct < 0.5 THEN 'e. 0 to +0.5%'
    WHEN gap_pct < 1 THEN 'f. +0.5 to +1%'
    WHEN gap_pct < 2 THEN 'g. +1 to +2%'
    ELSE 'h. gap > +2%' END AS bucket,
  count(*) n, avg(gap_pct) mean_gap, avg(fwd_pct) mean_fwd,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY fwd_pct) med_fwd,
  stddev(fwd_pct)/sqrt(count(*)) se
FROM x GROUP BY 1 ORDER BY 1
"""

async def main() -> None:
    async with AsyncSessionFactory() as db:
        horizons = (
            (5, "SWING h=5: fill at open, exit 5 sessions later"),
            (1, "h=1: fill at open, exit next close"),
        )
        for h, label in horizons:
            print(f"\n== {label} ==")
            rows = (await db.execute(text(SQL.format(H=h)))).all()
            print(f"  {'gap bucket':<16}{'n':>9}{'mean gap':>10}{'mean fwd':>10}"
                  f"{'median':>9}{'SE':>8}{'t':>8}")
            for r in rows:
                mg, mf = float(r.mean_gap), float(r.mean_fwd)
                md, se = float(r.med_fwd), float(r.se or 0)
                t = mf / se if se else 0
                print(f"  {r.bucket:<16}{r.n:>9,}{mg:>+10.2f}{mf:>+10.3f}"
                      f"{md:>+9.3f}{se:>8.3f}{t:>+8.1f}")
asyncio.run(main())
