# Provisional-layer health watch — LIVING DOC (open task)

**Status: OPEN — awaiting live-session evidence. Started 2026-08-19.**
**This watch has no scheduler behind it.** It was armed with an in-session cron
that is session-only and dies with the Claude session that created it. If you
are a new session: **nobody is watching this but you.** Run the check yourself
(command below) and fill in the table.

---

## Why this exists

`live-worker` logged two warnings on nearly every provisional cycle:

```
provisional: hot set clipped 466 → 150 (dropped 316: [128, 133, 137, ...])
provisional: cycle overran the cadence: 4039 ms > 3000 ms ({'hot': 150, ...})
```

Both were by-design log lines, but the numbers behind the design had drifted.

**Warning 1 (FIXED 2026-08-19).** `_recent_trigger_sids` admitted EVERY
alert-stream entry as "near-trigger". Market-BREADTH levels — vburst / PDH /
PDL / S&R, stamped `style="market"` by `live_levels` — carried **1271–1659
distinct stocks inside one 15-minute window** against a 150-stock cap. With 117
active-signal stocks only ~33 trigger slots remained, and the clip orders by
`(priority, stock_id)`, so the *same lowest stock_ids* won every cycle and
**watchlist stocks were never scored at all.** Near-trigger now means
SIGNAL-BOUND only; breadth returns via `live_provisional_trigger_market_max`.

**Warning 2 (OPEN — this is what the watch decides).** Arithmetic, not a fault:
`run_all_factors` re-measured at **35.6 ms/window** (module docstring says 45.7)
× ~50 engine calls ≈ 1.8–2.4 s, plus 150 window loads, against a **3.0 s**
cadence. Live cycles ran 3.1–4.2 s. Overruns self-throttle
(`delay = max(0, cadence − elapsed)`) and never queue, so they are not harmful
in themselves — the question is the RATE.

---

## The daily check

```bash
cd /home/nithin/code/agent/Claude/trading-platform/backend
uv run python scripts/provisional_health.py --days 7
```

Read-only. Prints two independent sides: the worker's own per-day counters from
`provisional:health:{day}`, and the hot-set input recomputed from Postgres +
the alert stream (so a filter that silently stopped working stays visible).

**⚠ The evidence expires.** `provisional:health:{day}` has a **7-day TTL**
(`live_provisional_health_ttl_s`). Read it within a week of each session day or
that day's numbers are gone — there is no file backup, because
`make live-worker` writes no log at all (only `make soak` tees one).

---

## Interpretation rules

| Observation | Conclusion |
|---|---|
| `clip% == 0` | The breadth filter settled it. |
| `clip% > 0` **and** `src_signal` near 150 | Cause is **signal COUNT**, not breadth. Fix is `live_provisional_hotset_max` (or a fair clip — within a rank it still picks lowest `stock_id`), **NOT** the cadence. Headroom is thin: 103–117 of 150 slots were already signal stocks. |
| `overrun% >= 20` or `mean cycle > cadence` | **Option 2 warranted** — raise `live_provisional_refresh_s` (3.0 → 5.0; pinned range 1–5 s). |
| `overrun%` small and non-zero | Option 2 optional. Overruns self-throttle. |
| `NO DATA` on a weekday | The live worker did not run (the Kite token needs interactive `scripts/kite_login.py` each ~6 AM IST). **Not** a failure of the fix. |
| `⚠ SEED FAILED` on a row | That day's counters UNDERCOUNT — a Redis read failed at thread start. |

Baseline to compare against (pre-fix, 2026-08-18): `hot_raw` ~466 clipped to
150, a clip on ~100% of cycles, cycles 3100–4200 ms vs a 3000 ms cadence.

---

## Session-day log

| Session day | cycles | overrun% | clip% | mean ms | max ms | hot_raw / clipped | src sig/trig/wl/mkt | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-08-18 (pre-fix) | — | ~100 | ~100 | 3100–4200 | 5047¹ | 466 / 316 | 117/~33/0/n-a | Baseline, from terminal logs only |
| **2026-08-20 (FIX LIVE, day 1)** | **624** | **9.6** | **0.0** | **2075** | **6339** | **106 / 0** | **103/18/3/0** | **First live session on the merged fix (`c1b4752`). CLIP RESOLVED — cap no longer binds; watchlist scored (wl=3); breadth excluded (mkt=0/597 admitted, ~30 idle slots). Worker stopped ~13:11 for the phase gate, restarted 14:20, clean session-over shutdown 15:40.** |
| _(fill in)_ | | | | | | | | |

¹ Not a real p99 — see the trap below.

**Verdict after ≥3 session days:** _(1/3 recorded — day 1 clean: clip 0%, overrun 9.6% self-throttling)_

---

## Two decisions parked on this evidence

1. **Cadence (option 2).** Raise `live_provisional_refresh_s` 3.0 → 5.0?
   Decide from `overrun%`, not from the single-day snapshot. **User asked to be
   TOLD whether it is required — do not change it unilaterally.**
   → **Day-1 evidence (2026-08-20): NOT required.** overrun=9.6% (well under the
   20% "Option 2 warranted" threshold) and mean cycle 2075 ms < 3000 ms cadence;
   the health script's own verdict was "OPTION 2 OPTIONAL". Keep accruing to ≥3
   days before calling it final, but on day 1 no cadence change is needed.
2. **Breadth discovery tier.** `live_provisional_trigger_market_max` is **0**,
   so the third hot-set source now adds almost nothing: measured 2026-08-19,
   **38 of 45** signal-bound alert stocks already carried an active signal, so
   the hot set is effectively `active signals ∪ watchlist` (~106–113 of 150 →
   **~37 slots idle**) while **~1569 breadth-movers can never reach a board**.
   quant-verifier recommends `market_max=20` paired with `refresh_s=5.0`
   (modelled 4.73 s/cycle at raw 133). Deliberately NOT taken — it bundles in
   the cadence decision above. The health script prints the
   idle-slots-vs-declined-movers line so the cost stays visible.

---

## Measurement traps found here (reusable)

- **`lat_p99` in the live-worker heartbeat is NOT a p99.**
  `LatencyHistogram.BOUNDS_MS` tops out at 100 ms, so `quantile_bound` falls
  through and returns `max_ms`. `lat_p99=5047` means ">1% of batches exceeded
  100 ms, worst 5.0 s".
- **The provisional thread holds the GIL.** It runs the *Python* frozen engine
  inside the consumer's process (`tradecore` is 266× faster but cannot take
  FII/DII flows yet), at ~100% duty cycle all session. Measured: a
  consumer-like 1 ms wake loop degrades from p50 1.08 ms / max 2.14 ms (idle)
  to **p50 6.16 ms / max 33.3 ms** with one scorer thread. The live heartbeat
  moved the same way (2026-07-16 soak, no provisional thread: `lat_p50=7.5` →
  2026-08-18: `lat_p50=50`), **but tick volume is also 8× higher**, so the shift
  is NOT attributable to provisional alone. The clean A/B is one session with
  `LIVE_PROVISIONAL_ENABLED=false`, comparing heartbeat `lat_p50`. Durable fix
  if the tick path needs the headroom: run the refresher in its own PROCESS.
- **`make live-worker` writes no log file.** Only `make soak` tees one. Any
  "just read the logs" plan for this thread is a dead end.
