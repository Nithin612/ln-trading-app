"""Integration tests for Phase 10 — Trading Journal.

Covers:
  - CRUD: create, read, update, delete journal entries
  - Full-text search in notes and lesson fields
  - Emotion validation (invalid values rejected)
  - Screenshot upload: size limit, unsupported type rejection
  - Screenshot delete
  - Analytics: emotion distribution endpoint
  - Auto-population: closing a position creates an auto entry
  - Idempotency: closing same position twice doesn't duplicate entry
  - Ownership: users cannot access each other's entries
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.models.stock import Stock
from app.models.trading import Position
from app.models.user import User
from tests.helpers import create_test_user, get_auth_headers, make_stock


# ── Factories ─────────────────────────────────────────────────────────────────

async def _make_user(
    db: AsyncSession,
    email: str = "jrnl@example.com",
) -> User:
    from app.core.security import hash_password

    user = User(
        email=email,
        password_hash=hash_password("Secret123"),
        full_name="Journal User",
        role="user",
        is_active=True,
        trading_mode="paper",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_signal(db: AsyncSession, stock_id: int) -> Signal:
    now = datetime.now(tz=UTC)
    sig = Signal(
        stock_id=stock_id,
        direction="BUY",
        classification="swing",
        timeframe="1d",
        entry_price="500.0000",
        stop_loss="480.0000",
        take_profit="540.0000",
        suggested_qty=100,
        confidence_pct=80,
        factor_scores={},
        headline="BUY TEST@500",
        status="active",
        validity_until=now + timedelta(days=5),
        created_at=now,
    )
    db.add(sig)
    await db.flush()
    return sig


async def _open_position(
    db: AsyncSession,
    user: User,
    stock: Stock,
    signal: Signal,
) -> Position:
    pos = Position(
        user_id=user.id,
        stock_id=stock.id,
        mode="paper",
        side="LONG",
        quantity=100,
        avg_entry_price=Decimal("500"),
        current_sl=Decimal("480"),
        current_tp=Decimal("540"),
        trail_state="none",
        unrealized_pnl=Decimal("0"),
        realized_pnl=Decimal("0"),
        opened_at=datetime.now(tz=UTC),
        signal_id=signal.id,
    )
    db.add(pos)
    await db.flush()
    return pos


# ── CRUD tests ─────────────────────────────────────────────────────────────────

class TestJournalCrud:
    async def test_create_manual_entry(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        r = await client.post(
            "/api/v1/journal/",
            json={
                "trade_date": "2026-05-20",
                "notes": "Entered on bullish engulfing candle",
                "emotion_before": "confident",
            },
            headers=headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["entry_type"] == "manual"
        assert data["trade_date"] == "2026-05-20"
        assert data["emotion_before"] == "confident"
        assert data["screenshot_paths"] == []
        assert data["tags"] == []

    async def test_get_entry(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.get(f"/api/v1/journal/{entry_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == entry_id

    async def test_update_entry(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.put(
            f"/api/v1/journal/{entry_id}",
            json={"lesson": "Always wait for confirmation candle", "emotion_after": "satisfied"},
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["lesson"] == "Always wait for confirmation candle"
        assert data["emotion_after"] == "satisfied"

    async def test_delete_entry(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.delete(f"/api/v1/journal/{entry_id}", headers=headers)
        assert r.status_code == 204

        r = await client.get(f"/api/v1/journal/{entry_id}", headers=headers)
        assert r.status_code == 404

    async def test_list_entries_paginates(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        for i in range(3):
            await client.post(
                "/api/v1/journal/",
                json={"trade_date": f"2026-05-{18 + i:02d}"},
                headers=headers,
            )

        r = await client.get("/api/v1/journal/?limit=2&offset=0", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["entries"]) == 2

    async def test_create_entry_requires_auth(self, client: AsyncClient) -> None:
        r = await client.post("/api/v1/journal/", json={"trade_date": "2026-05-20"})
        assert r.status_code == 401

    async def test_get_nonexistent_entry_404(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)
        r = await client.get(
            "/api/v1/journal/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert r.status_code == 404


# ── Validation tests ───────────────────────────────────────────────────────────

class TestJournalValidation:
    async def test_invalid_emotion_before_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20", "emotion_before": "euphoric"},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_invalid_emotion_after_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20", "emotion_after": "depressed"},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_invalid_side_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20", "side": "HOLD"},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_valid_all_emotions(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        for eb in ("fear", "neutral", "confident", "greed", "anxious"):
            r = await client.post(
                "/api/v1/journal/",
                json={"trade_date": "2026-05-20", "emotion_before": eb},
                headers=headers,
            )
            assert r.status_code == 201, f"emotion_before={eb!r} was rejected"


# ── Full-text search tests ─────────────────────────────────────────────────────

class TestJournalSearch:
    async def test_search_matches_notes(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20", "notes": "Entered on double bottom reversal"},
            headers=headers,
        )
        await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-19", "notes": "RSI divergence spotted"},
            headers=headers,
        )

        r = await client.get("/api/v1/journal/?q=double+bottom", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert "double bottom" in data["entries"][0]["notes"]

    async def test_search_matches_lesson(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        await client.post(
            "/api/v1/journal/",
            json={
                "trade_date": "2026-05-20",
                "lesson": "Never chase breakouts without volume confirmation",
            },
            headers=headers,
        )

        r = await client.get("/api/v1/journal/?q=breakout+volume", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_search_no_match_returns_empty(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20", "notes": "Swing trade on RELIANCE"},
            headers=headers,
        )

        r = await client.get("/api/v1/journal/?q=cryptocurrency", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_filter_by_emotion_before(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        for eb in ("confident", "fear", "neutral"):
            await client.post(
                "/api/v1/journal/",
                json={"trade_date": "2026-05-20", "emotion_before": eb},
                headers=headers,
            )

        r = await client.get("/api/v1/journal/?emotion_before=confident", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["entries"][0]["emotion_before"] == "confident"

    async def test_filter_by_date_range(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        for day in ("2026-05-10", "2026-05-15", "2026-05-20"):
            await client.post(
                "/api/v1/journal/",
                json={"trade_date": day},
                headers=headers,
            )

        r = await client.get(
            "/api/v1/journal/?start_date=2026-05-12&end_date=2026-05-18",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["entries"][0]["trade_date"] == "2026-05-15"


# ── Screenshot tests ───────────────────────────────────────────────────────────

class TestJournalScreenshots:
    def _png_bytes(self, size: int = 100) -> bytes:
        """Minimal valid PNG header + enough padding."""
        header = (
            b"\x89PNG\r\n\x1a\n"          # PNG signature
            b"\x00\x00\x00\rIHDR"          # IHDR chunk length + type
            + b"\x00" * 17                  # width/height/etc padding
        )
        return header + b"\x00" * max(0, size - len(header))

    async def test_upload_screenshot_success(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.post(
            f"/api/v1/journal/{entry_id}/screenshots",
            files={"file": ("chart.png", self._png_bytes(), "image/png")},
            headers=headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["screenshot_paths"]) == 1
        assert "/uploads/screenshots/" in data["screenshot_paths"][0]

    async def test_upload_unsupported_type_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.post(
            f"/api/v1/journal/{entry_id}/screenshots",
            files={"file": ("data.pdf", b"%PDF-1.4", "application/pdf")},
            headers=headers,
        )
        assert r.status_code == 422

    async def test_upload_oversized_file_rejected(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        big_file = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)  # 6 MB
        r = await client.post(
            f"/api/v1/journal/{entry_id}/screenshots",
            files={"file": ("big.png", big_file, "image/png")},
            headers=headers,
        )
        assert r.status_code == 413

    async def test_delete_screenshot(self, client: AsyncClient, db: AsyncSession) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=headers,
        )
        entry_id = create_r.json()["id"]

        upload_r = await client.post(
            f"/api/v1/journal/{entry_id}/screenshots",
            files={"file": ("chart.png", self._png_bytes(), "image/png")},
            headers=headers,
        )
        screenshot_path = upload_r.json()["screenshot_paths"][0]
        filename = screenshot_path.split("/")[-1]

        r = await client.delete(
            f"/api/v1/journal/{entry_id}/screenshots/{filename}",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["screenshot_paths"] == []


# ── Analytics tests ────────────────────────────────────────────────────────────

class TestJournalAnalytics:
    async def test_emotion_analytics_empty(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        r = await client.get("/api/v1/journal/analytics/emotions", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_entries"] == 0
        assert data["before"] == []
        assert data["after"] == []

    async def test_emotion_analytics_counts(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await create_test_user(db)
        headers = await get_auth_headers(client)

        emotions = [
            ("confident", "satisfied"),
            ("confident", "frustrated"),
            ("fear", "regret"),
        ]
        for eb, ea in emotions:
            await client.post(
                "/api/v1/journal/",
                json={
                    "trade_date": "2026-05-20",
                    "emotion_before": eb,
                    "emotion_after": ea,
                    "realized_pnl": "1000.00" if ea == "satisfied" else "-500.00",
                },
                headers=headers,
            )

        r = await client.get("/api/v1/journal/analytics/emotions", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total_entries"] == 3

        before_map = {e["emotion"]: e["count"] for e in data["before"]}
        assert before_map["confident"] == 2
        assert before_map["fear"] == 1

    async def test_emotion_analytics_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/journal/analytics/emotions")
        assert r.status_code == 401


# ── Auto-population tests ──────────────────────────────────────────────────────

class TestJournalAutoPopulation:
    async def test_closing_position_creates_auto_entry(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        await db.commit()

        r = await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={"exit_price": "540.0000"},
            headers=headers,
        )
        assert r.status_code == 200

        journal_r = await client.get(
            "/api/v1/journal/?entry_type=auto", headers=headers
        )
        assert journal_r.status_code == 200
        data = journal_r.json()
        assert data["total"] == 1
        entry = data["entries"][0]
        assert entry["entry_type"] == "auto"
        assert entry["position_id"] == pos.id
        assert Decimal(entry["realized_pnl"]) == Decimal("4000")

    async def test_auto_entry_has_exit_price(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        user = await create_test_user(db)
        headers = await get_auth_headers(client)
        stock = await make_stock(db)
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        await db.commit()

        await client.post(
            f"/api/v1/trading/positions/{pos.id}/close",
            json={"exit_price": "530.0000"},
            headers=headers,
        )

        journal_r = await client.get("/api/v1/journal/", headers=headers)
        entry = journal_r.json()["entries"][0]
        assert Decimal(entry["exit_price"]) == Decimal("530.0000")

    async def test_auto_entry_not_duplicated_on_double_close(
        self, db: AsyncSession
    ) -> None:
        from app.services.journal_service import auto_create_journal_entry

        user = await _make_user(db, email="dup@example.com")
        stock = await make_stock(db, symbol="DUPCO")
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        pos.realized_pnl = Decimal("1000")
        pos.closed_at = datetime.now(tz=UTC)
        await db.flush()

        e1 = await auto_create_journal_entry(db, pos)
        e2 = await auto_create_journal_entry(db, pos)
        await db.commit()

        assert e1 is not None
        assert e2 is None  # second call is idempotent

    async def test_auto_entry_not_created_for_open_position(
        self, db: AsyncSession
    ) -> None:
        from app.services.journal_service import auto_create_journal_entry

        user = await _make_user(db, email="open@example.com")
        stock = await make_stock(db, symbol="OPENCO")
        signal = await _make_signal(db, stock.id)
        pos = await _open_position(db, user, stock, signal)
        await db.commit()

        result = await auto_create_journal_entry(db, pos)
        assert result is None


# ── Ownership tests ────────────────────────────────────────────────────────────

class TestJournalOwnership:
    async def test_user_cannot_read_other_users_entry(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from app.core.security import hash_password

        await create_test_user(db, email="owner@example.com")
        User2 = User(
            email="other@example.com",
            password_hash=hash_password("Secret123"),
            full_name="Other",
            role="user",
            is_active=True,
            trading_mode="paper",
        )
        db.add(User2)
        await db.commit()

        owner_headers = await get_auth_headers(client, email="owner@example.com")
        other_headers = await get_auth_headers(client, email="other@example.com")

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=owner_headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.get(f"/api/v1/journal/{entry_id}", headers=other_headers)
        assert r.status_code == 404

    async def test_user_cannot_delete_other_users_entry(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        from app.core.security import hash_password

        await create_test_user(db, email="owner2@example.com")
        User2 = User(
            email="other2@example.com",
            password_hash=hash_password("Secret123"),
            full_name="Other2",
            role="user",
            is_active=True,
            trading_mode="paper",
        )
        db.add(User2)
        await db.commit()

        owner_headers = await get_auth_headers(client, email="owner2@example.com")
        other_headers = await get_auth_headers(client, email="other2@example.com")

        create_r = await client.post(
            "/api/v1/journal/",
            json={"trade_date": "2026-05-20"},
            headers=owner_headers,
        )
        entry_id = create_r.json()["id"]

        r = await client.delete(f"/api/v1/journal/{entry_id}", headers=other_headers)
        assert r.status_code == 404
