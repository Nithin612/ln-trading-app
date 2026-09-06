"""Phase 7.2 — the READ-ONLY Kite spike that validates the BrokerAdapter interface.

    uv run python scripts/kite_readonly_spike.py          # shape report
    uv run python scripts/kite_readonly_spike.py --raw    # also dump one raw sample each

**Why this exists.** `docs/phases/phase-07-live-trading-plan.md` §3 names the risk plainly:
designing the `BrokerAdapter` interface purely from the Kite docs, *having never called
Kite*, risks getting its shape wrong and discovering that on live day 1. The mitigation is
this spike — order-status, positions and margins endpoints, validated against reality
cheaply, before `KiteBrokerAdapter` is written.

⚠ **READ-ONLY. IT PLACES NO ORDERS, AND CANNOT.** `ThrottledKite` deliberately has no
`place_order` method at all (Phase 7.2) — order placement is post-cycle-2 work because only
reality validates it. The absence of the method is the safeguard, not a flag on this script.

**What it checks** is the *shape* of what Kite returns against what
`app/broker/adapter.py` declares — every field the adapter's `BrokerOrder`,
`BrokerPosition` and `Funds` need, and anything Kite sends that we have not modelled. A
missing field is an interface bug found now instead of on day 1; an unmodelled field is a
question, not necessarily a problem.

Prints a report and writes it to `docs/analysis/kite-readonly-spike-<date>.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import AsyncSessionFactory  # noqa: E402

_IST = ZoneInfo("Asia/Kolkata")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OUT_DIR = _REPO_ROOT / "docs" / "analysis"

#: What `BrokerOrder` needs from a Kite order row. If one of these is absent the adapter
#: cannot be written as designed — that is the finding this spike exists to surface.
_ORDER_FIELDS_NEEDED = {
    "order_id",       # → broker_order_id
    "tag",            # → client_order_id (Kite's 20-char user tag; see the WARNING below)
    "tradingsymbol",  # → symbol
    "transaction_type",  # → side
    "quantity",
    "filled_quantity",
    "status",
    "average_price",
}

#: What `BrokerPosition` needs from a Kite net-position row.
_POSITION_FIELDS_NEEDED = {"tradingsymbol", "quantity", "average_price"}

#: What `Funds` needs from `margins()["equity"]`.
_FUNDS_PATHS_NEEDED = {"available.live_balance", "utilised.debits"}


def _shape(value: Any, depth: int = 0) -> str:
    """A type sketch, never the value — this report is committed to the repo."""
    if isinstance(value, dict):
        if depth >= 1:
            return f"dict[{len(value)} keys]"
        inner = ", ".join(f"{k}: {_shape(v, depth + 1)}" for k, v in list(value.items())[:40])
        return "{" + inner + "}"
    if isinstance(value, list):
        return f"list[{len(value)}]" + (f" of {_shape(value[0], depth + 1)}" if value else "")
    return type(value).__name__


def _dig(d: dict[str, Any], dotted: str) -> tuple[bool, Any]:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


async def _run(dump_raw: bool) -> int:  # noqa: C901 — three independent endpoint
    # probes plus a report writer. Each block is a flat try/except that must name its
    # OWN failure and keep going, because a token that can read margins but not orders
    # is exactly the partial-permission case the spike exists to surface. Splitting
    # them into helpers would scatter the shared `lines`/`failures` accumulation.
    from app.broker.kite_rest import KiteException, ThrottledKite
    from app.services.chain_recorder import get_any_active_admin_token

    async with AsyncSessionFactory() as db:
        token = await get_any_active_admin_token(db)
    if token is None:
        print("no active Kite admin token — run scripts/kite_login.py first", flush=True)
        return 1

    kite = ThrottledKite(token)
    now = datetime.now(UTC).astimezone(_IST)
    lines: list[str] = [
        f"# Kite read-only spike — {now.date().isoformat()}",
        "",
        f"Run {now.isoformat(timespec='seconds')} IST. **Read-only — no order was placed;**",
        "`ThrottledKite` has no `place_order` method (Phase 7.2, deliberate).",
        "",
        "Validates the `app/broker/adapter.py` interface (A35) against what Kite actually",
        "returns, so its shape is not being guessed from the docs alone.",
        "",
    ]
    failures = 0

    # ── orders ────────────────────────────────────────────────────────────────
    lines += ["## `orders()` → `BrokerOrder`", ""]
    try:
        orders = await kite.orders()
        lines.append(f"- rows today: **{len(orders)}**")
        if orders:
            present = set(orders[0].keys())
            missing = _ORDER_FIELDS_NEEDED - present
            extra = present - _ORDER_FIELDS_NEEDED
            lines.append(f"- shape: `{_shape(orders[0])}`")
            if missing:
                failures += 1
                lines.append(f"- ⛔ **MISSING what the adapter needs: {sorted(missing)}**")
            else:
                lines.append("- ✅ every field `BrokerOrder` needs is present")
            lines.append(f"- unmodelled fields Kite also sends: {sorted(extra)}")
        else:
            lines.append(
                "- ⚠ **no orders today, so the shape is UNVERIFIED.** This is the expected "
                "result on an account that has never traded, and it means the spike has "
                "NOT yet done its job — re-run it on a day with at least one order "
                "(a cancelled one is enough)."
            )
    except KiteException as exc:  # pragma: no cover — network path
        failures += 1
        lines.append(f"- ⛔ call failed: `{type(exc).__name__}: {exc}`")

    # ── positions ─────────────────────────────────────────────────────────────
    lines += ["", "## `positions()` → `BrokerPosition`", ""]
    try:
        positions = await kite.positions()
        net = positions.get("net", [])
        day_rows = len(positions.get("day", []))
        lines.append(f"- `net` rows: **{len(net)}**, `day` rows: **{day_rows}**")
        if net:
            present = set(net[0].keys())
            missing = _POSITION_FIELDS_NEEDED - present
            lines.append(f"- shape: `{_shape(net[0])}`")
            if missing:
                failures += 1
                lines.append(f"- ⛔ **MISSING: {sorted(missing)}**")
            else:
                lines.append("- ✅ every field `BrokerPosition` needs is present")
        else:
            lines.append("- ⚠ no open positions, so the shape is UNVERIFIED.")
    except KiteException as exc:  # pragma: no cover
        failures += 1
        lines.append(f"- ⛔ call failed: `{type(exc).__name__}: {exc}`")

    # ── margins ───────────────────────────────────────────────────────────────
    lines += ["", "## `margins()` → `Funds` (A42's ground truth)", ""]
    try:
        margins = await kite.margins()
        equity = margins.get("equity", {})
        lines.append(f"- segments: {sorted(margins.keys())}")
        lines.append(f"- equity shape: `{_shape(equity)}`")
        for path in sorted(_FUNDS_PATHS_NEEDED):
            ok, _ = _dig(equity, path)
            if ok:
                lines.append(f"- ✅ `equity.{path}` present")
            else:
                failures += 1
                lines.append(f"- ⛔ **`equity.{path}` MISSING**")
    except KiteException as exc:  # pragma: no cover
        failures += 1
        lines.append(f"- ⛔ call failed: `{type(exc).__name__}: {exc}`")

    # ── the finding that matters most ─────────────────────────────────────────
    lines += [
        "",
        "## ⚠ The interface question this spike is really asking",
        "",
        "`BrokerOrder.client_order_id` is how reconciliation matches a broker row back to",
        "**our** order. Kite has no client-order-id field — the nearest thing is **`tag`,",
        "capped at 20 characters** and not guaranteed unique by the broker. Our namespaced",
        "ids (`paper:<uuid>`) do **not** fit in 20 characters.",
        "",
        "So one of these has to be true before `KiteBrokerAdapter` is written, and the",
        "choice is a decision, not a detail:",
        "",
        "1. our live ids are short enough to be a `tag` (a compact counter, not a uuid); or",
        "2. reconciliation matches on `(symbol, side, quantity, timestamp)` — weaker, and",
        "   ambiguous exactly when two identical orders are placed close together; or",
        "3. we keep a local `broker_order_id → client_order_id` map written at ack time,",
        "   and accept that an order lost *before* its ack is unmatchable.",
        "",
        "**(3) plus a short tag is the likely answer**, but it needs the user's call and it",
        "is precisely the kind of thing that would otherwise be discovered on live day 1.",
        "",
    ]

    if dump_raw:
        lines += ["## Raw samples (one row each)", "", "```json"]
        try:
            sample = {
                "order": (await kite.orders())[:1],
                "position_net": (await kite.positions()).get("net", [])[:1],
                "margins_equity": (await kite.margins()).get("equity", {}),
            }
            lines.append(json.dumps(sample, indent=2, default=str))
        except KiteException as exc:  # pragma: no cover
            lines.append(f"raw dump failed: {exc}")
        lines.append("```")

    lines += [
        "",
        "---",
        "",
        f"**Verdict: {'⛔ interface gaps found — see above' if failures else '✅ no gaps found'}**"
        f" ({failures} problem(s)).",
        "",
        "⚠ A clean run on an account with **no orders and no positions** verifies almost",
        "nothing. Read the ⚠ markers above before treating this as a pass.",
    ]

    report = "\n".join(lines)
    print(report, flush=True)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = _OUT_DIR / f"kite-readonly-spike-{now.date().isoformat()}.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\nwritten: {out}", flush=True)
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--raw", action="store_true", help="also dump one raw sample row per endpoint"
    )
    args = ap.parse_args()
    return asyncio.run(_run(args.raw))


if __name__ == "__main__":
    raise SystemExit(main())
