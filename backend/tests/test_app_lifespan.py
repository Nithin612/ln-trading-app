"""App lifespan must never auto-start the v1 tick consumer.

Regression for the 2026-07-10 soak incident (phase-03 ledger, §post-close
forensics): lifespan used to resume the v1 consumer whenever a valid
admin token existed, arming a second candle writer on every uvicorn
(re)start while the live worker owned the tables — it wrote off-canon
candles twice that day. On the pre-fix code this test FAILS: the seeded
valid token makes lifespan call start_consumer.

The only sanctioned start path is the explicit admin endpoint
POST /broker/kite/consumer/start.
"""

from datetime import UTC, datetime, timedelta

import app.broker.tick_consumer as tick_consumer
import pytest
from app.main import app
from app.models import BrokerToken

from tests.helpers import create_test_user


@pytest.mark.asyncio
async def test_lifespan_never_starts_v1_consumer(db, monkeypatch) -> None:
    user = await create_test_user(db, email="lifespan-admin@example.com", role="admin")
    db.add(
        BrokerToken(
            user_id=user.id,
            broker="kite",
            access_token="valid-token-abc",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=12),
            is_active=True,
        )
    )
    await db.commit()

    calls: list[int] = []

    async def _spy(user_id: int) -> bool:
        calls.append(user_id)
        return False

    monkeypatch.setattr(tick_consumer, "start_consumer", _spy)

    async with app.router.lifespan_context(app):
        pass  # startup + shutdown

    assert calls == [], (
        "lifespan auto-started the v1 consumer — the 2026-07-10 dual-writer "
        "hazard is back; only POST /broker/kite/consumer/start may start it"
    )
