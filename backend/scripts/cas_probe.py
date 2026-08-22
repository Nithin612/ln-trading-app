"""CAS probe — capture Kite REST /quote during the Closing Auction Session to find where (if
anywhere) the exchange's indicative close + total imbalance quantity surface for us.

    uv run python scripts/cas_probe.py            # defaults: liquid F&O names, until 15:36 IST
    uv run python scripts/cas_probe.py --once     # single snapshot now (dry-run / auth check)
    uv run python scripts/cas_probe.py --symbols NSE:RELIANCE,NSE:HDFCBANK --interval 20

WHY: CAS is new (Aug 2026) and its fields are NOT in Kite's static /quote docs; the WebSocket ticker
(MODE_FULL) has a fixed binary struct with no imbalance field, so the imbalance can only come from
REST /quote. This polls /quote every `interval` s across the CAS window (3:15-3:35 IST), appends the
FULL raw JSON per poll to docs/analysis/cas-probe-<date>.jsonl, and prints any key NOT in the
documented set — where an indicative-close / imbalance field would appear. Read-only; no order path;
safe any time (off-hours just captures ordinary quotes as a dry-run).

Run it Monday during 3:15-3:35 IST with an active Kite admin token (scripts/kite_login.py first),
then share docs/analysis/cas-probe-<date>.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OUT_DIR = _REPO_ROOT / "docs" / "analysis"

_DEFAULT_SYMBOLS = ["NSE:RELIANCE", "NSE:HDFCBANK", "NSE:ICICIBANK", "NSE:INFY", "NSE:SBIN"]

# The documented full-quote keys (kite.trade/docs/connect/v3/market-quotes). Anything BEYOND these
# appearing during the CAS window is a candidate indicative/auction/imbalance field.
_DOCUMENTED = {
    "instrument_token", "timestamp", "last_trade_time", "last_price", "last_quantity",
    "last_traded_quantity", "buy_quantity", "sell_quantity", "volume", "volume_traded",
    "average_price", "oi", "oi_day_high", "oi_day_low", "net_change", "lower_circuit_limit",
    "upper_circuit_limit", "ohlc", "depth",
}
_OHLC_DOCUMENTED = {"open", "high", "low", "close"}
_INTERESTING = ("imbalance", "indicative", "auction", "cas", "equilibrium", "match")


def _flag(quote: dict[str, object]) -> dict[str, object]:
    """Keys in this quote beyond the documented set, plus any 'interesting'-named key anywhere."""
    extra = {k: v for k, v in quote.items() if k not in _DOCUMENTED}
    ohlc = quote.get("ohlc")
    if isinstance(ohlc, dict):
        extra_ohlc = {k: v for k, v in ohlc.items() if k not in _OHLC_DOCUMENTED}
        if extra_ohlc:
            extra["ohlc.extra"] = extra_ohlc
    interesting = {
        k: v for k, v in quote.items() if any(tok in k.lower() for tok in _INTERESTING)
    }
    return {"extra_keys": extra, "interesting": interesting}


async def _snapshot(kite: object, symbols: list[str], out_path: Path) -> None:
    now = datetime.now(UTC)
    quotes = await kite.quote(symbols)  # type: ignore[attr-defined]
    rec = {"ts_utc": now.isoformat(), "ts_ist": now.astimezone(_IST).strftime("%H:%M:%S"),
           "quotes": quotes}
    with out_path.open("a") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")
    ist = now.astimezone(_IST).strftime("%H:%M:%S")
    for sym, q in quotes.items():
        if not isinstance(q, dict):
            continue
        lp = q.get("last_price")
        close = q.get("ohlc", {}).get("close") if isinstance(q.get("ohlc"), dict) else None
        flags = _flag(q)
        note = ""
        if flags["extra_keys"] or flags["interesting"]:
            note = f"  ⚑ NEW: {json.dumps({k: v for k, v in flags.items() if v}, default=str)}"
        print(f"  {ist}  {sym:16} last={lp} close={close}{note}", flush=True)


async def _run(symbols: list[str], interval: int, until_ist: time, once: bool) -> int:
    from app.broker.kite_rest import ThrottledKite
    from app.services.chain_recorder import get_any_active_admin_token

    async with AsyncSessionFactory() as db:
        token = await get_any_active_admin_token(db)
    if token is None:
        print("no active Kite admin token — run scripts/kite_login.py first", flush=True)
        return 1

    kite = ThrottledKite(token)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(UTC).astimezone(_IST).date()
    out_path = _OUT_DIR / f"cas-probe-{day.isoformat()}.jsonl"
    print(f"CAS probe → {out_path.relative_to(_REPO_ROOT)} | symbols={symbols} "
          f"| until {until_ist.strftime('%H:%M')} IST | every {interval}s", flush=True)

    polls = 0
    while True:
        try:
            await _snapshot(kite, symbols, out_path)
        except Exception as exc:  # noqa: BLE001 - a probe must never die on one bad poll
            print(f"  poll failed: {exc!r}", flush=True)
        polls += 1
        if once:
            break
        now_ist = datetime.now(UTC).astimezone(_IST).timetz()
        if now_ist.replace(tzinfo=None) >= until_ist or polls > 400:  # 400 = runaway backstop
            break
        await asyncio.sleep(interval)
    print(f"done — {polls} polls written to {out_path.relative_to(_REPO_ROOT)}", flush=True)
    print("Share that file; grep it for 'imbalance'/'indicative' or the ⚑ NEW lines above.",
          flush=True)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe Kite /quote for CAS indicative/imbalance")
    ap.add_argument("--symbols", type=str, default=",".join(_DEFAULT_SYMBOLS),
                    help="comma list of EXCHANGE:SYMBOL (default: liquid F&O names)")
    ap.add_argument("--interval", type=int, default=20, help="seconds between polls (default 20)")
    ap.add_argument("--until", type=str, default="15:36", help="stop at this IST HH:MM")
    ap.add_argument("--once", action="store_true", help="single snapshot now (dry-run)")
    args = ap.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    hh, mm = (int(x) for x in args.until.split(":"))
    raise SystemExit(asyncio.run(_run(symbols, args.interval, time(hh, mm), args.once)))


if __name__ == "__main__":
    main()
