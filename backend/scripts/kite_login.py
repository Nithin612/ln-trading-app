"""Terminal Kite Connect login — the daily 6:30 AM ritual, no servers needed.

Flow (only postgres must be up — `make up`):
  1. Prints the Zerodha login URL. Open it in any browser, log in with
     client ID + password + TOTP.
  2. Zerodha redirects to the app callback (localhost:8000). If the
     backend isn't running the page FAILS TO LOAD — that is EXPECTED and
     fine: the request_token is in the ADDRESS BAR. Copy the full URL.
  3. Paste it here. The script exchanges it for an access token (valid
     until ~6:00 AM IST tomorrow), stores it, and syncs the instrument
     master so the backfill/recorders can map symbols → tokens.

Usage:
  uv run python scripts/kite_login.py              # login + instrument sync
  uv run python scripts/kite_login.py --no-sync    # login only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broker.kite_client import exchange_token, get_login_url, sync_instruments  # noqa: E402
from app.db.session import AsyncSessionFactory  # noqa: E402
from app.models.user import User  # noqa: E402
from sqlalchemy import select  # noqa: E402


def parse_request_token(pasted: str) -> str:
    """Accept the full redirect URL or a bare request_token.

    Zerodha redirects to
    .../callback?...&request_token=XYZ&action=login&status=success —
    users paste whatever their address bar holds; be liberal.
    """
    s = pasted.strip().strip("'\"")
    if not s:
        raise ValueError("empty input")
    if "request_token=" in s:
        qs = parse_qs(urlsplit(s).query)
        tokens = qs.get("request_token", [])
        if not tokens or not tokens[0]:
            raise ValueError("URL has no usable request_token param")
        return tokens[0]
    if "/" in s or "?" in s or "=" in s or " " in s:
        raise ValueError("that looks like a URL without a request_token param")
    return s


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-sync", action="store_true", help="skip instrument master sync")
    ap.add_argument("--user-id", type=int, default=0, help="app user to own the token")
    args = ap.parse_args()

    print("\n1) Open this URL and log in (client ID + password + TOTP):\n")
    print(f"   {get_login_url()}\n")
    print("2) After login the browser lands on a localhost:8000 URL.")
    print("   If that page fails to load, IGNORE IT — copy the full URL")
    print("   from the address bar anyway.\n")
    pasted = input("3) Paste the full redirect URL (or just the request_token): ")
    try:
        request_token = parse_request_token(pasted)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1

    async with AsyncSessionFactory() as db:
        user_id = args.user_id
        if not user_id:
            first = (
                await db.execute(select(User.id).order_by(User.id).limit(1))
            ).scalar_one_or_none()
            if first is None:
                print("✗ no users in DB — run make create-admin first")
                return 1
            user_id = int(first)

        try:
            token = await exchange_token(db, user_id, request_token)
        except Exception as exc:  # kiteconnect raises several concrete types
            print(f"✗ token exchange failed: {exc}")
            print("  Usual causes: request_token already used (they are single-use —")
            print("  log in again for a fresh one), or KITE_API_KEY/KITE_API_SECRET in")
            print("  backend/.env don't belong to the app whose login URL you opened.")
            return 2
        await db.commit()
        expires_ist = token.expires_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")
        print(f"✓ connected — token valid until {expires_ist} (~6:00 AM IST)")

        if not args.no_sync:
            print("syncing instrument master (~80k rows)…")
            n = await sync_instruments(db, token.access_token)
            await db.commit()
            print(f"✓ {n} instruments synced")

    print("\nNext: uv run python scripts/backfill_intraday.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
