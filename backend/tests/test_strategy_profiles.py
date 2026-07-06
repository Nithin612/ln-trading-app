"""strategy_profiles schema + signal linkage (Phase 2 slice 4).

Pins the invariants the design review demanded be DB-enforced, not
service discipline: immutable version rows (one non-superseded per key),
config-hash determinism, reject-don't-clamp JSONB validation, and the
partial-unique active-suggestion idempotency index on signals.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models.profile import StrategyProfile
from app.models.signal import Signal
from app.schemas.profile import (
    StrategyProfileConfig,
    compute_config_hash,
)
from app.services.universe_service import resolve_legacy, resolve_universe
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _config(**overrides) -> StrategyProfileConfig:
    base = {
        "key": "dc1",
        "name": "Double Confirmation 1",
        "style": "swing",
        "timeframe": "1d",
        "schedule": "eod",
        "universe_spec": {"kind": "index", "value": "NIFTY50"},
        "setup_conditions": [{"type": "dc1", "params": {}}],
        "weight_multipliers": {},
        "min_confidence": 70,
        "risk_template": {"kind": "rr", "ratio": "2"},
    }
    base.update(overrides)
    return StrategyProfileConfig(**base)


def _row(
    cfg: StrategyProfileConfig, *, version: int = 1, status: str = "active"
) -> StrategyProfile:
    return StrategyProfile(
        key=cfg.key,
        version=version,
        name=cfg.name,
        style=cfg.style,
        timeframe=cfg.timeframe,
        schedule=cfg.schedule,
        universe_spec=cfg.universe_spec.model_dump(mode="json"),
        setup_conditions=[c.model_dump(mode="json") for c in cfg.setup_conditions],
        weight_multipliers=cfg.weight_multipliers,
        min_confidence=cfg.min_confidence,
        risk_template=cfg.risk_template.model_dump(mode="json"),
        validity_spec=None,
        status=status,
        config_hash=compute_config_hash(cfg),
    )


class TestConfigValidation:
    def test_unknown_setup_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown setup type"):
            _config(setup_conditions=[{"type": "moon_phase", "params": {}}])

    def test_unknown_weight_group_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown weight groups"):
            _config(weight_multipliers={"vibes": 1.5})

    def test_multiplier_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _config(weight_multipliers={"trend": 0.0})
        with pytest.raises(ValidationError):
            _config(weight_multipliers={"trend": 3.5})
        assert _config(weight_multipliers={"trend": 3.0}).weight_multipliers["trend"] == 3.0

    def test_min_confidence_cannot_undercut_the_gate(self) -> None:
        """Profiles may RAISE the frozen ≥70% gate, never lower it."""
        with pytest.raises(ValidationError):
            _config(min_confidence=65)
        assert _config(min_confidence=85).min_confidence == 85

    def test_risk_template_decimal_strings(self) -> None:
        with pytest.raises(ValidationError):
            _config(risk_template={"kind": "rr", "ratio": "not-a-number"})
        with pytest.raises(ValidationError):
            _config(risk_template={"kind": "rr", "ratio": "-2"})
        with pytest.raises(ValidationError):
            _config(risk_template={"kind": "teleport"})

    def test_config_hash_deterministic_and_order_insensitive(self) -> None:
        a = _config(weight_multipliers={"trend": 1.5, "volume": 0.5})
        b = _config(weight_multipliers={"volume": 0.5, "trend": 1.5})
        assert compute_config_hash(a) == compute_config_hash(b)
        c = _config(weight_multipliers={"trend": 1.6, "volume": 0.5})
        assert compute_config_hash(a) != compute_config_hash(c)


class TestVersioningInvariant:
    async def test_one_non_superseded_row_per_key(self, db: AsyncSession) -> None:
        cfg = _config()
        db.add(_row(cfg, version=1, status="active"))
        await db.commit()

        # a second live row for the same key must violate the partial unique
        db.add(_row(cfg, version=2, status="active"))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

        # the sanctioned path: supersede v1, then insert v2
        from sqlalchemy import update

        await db.execute(
            update(StrategyProfile)
            .where(StrategyProfile.key == "dc1", StrategyProfile.version == 1)
            .values(status="superseded")
        )
        db.add(_row(cfg, version=2, status="active"))
        await db.commit()

    async def test_key_version_unique(self, db: AsyncSession) -> None:
        cfg = _config(key="rrbo_basic", setup_conditions=[], name="RRBO")
        db.add(_row(cfg, version=1, status="active"))
        await db.commit()
        db.add(_row(cfg, version=1, status="superseded"))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_db_rejects_gate_undercut(self, db: AsyncSession) -> None:
        """CHECK constraint backs the pydantic floor at the DB layer."""
        cfg = _config(key="sneaky")
        row = _row(cfg)
        row.min_confidence = 60
        db.add(row)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


class TestSignalProfileIdempotency:
    async def _signal(self, stock_id: int, profile: StrategyProfile | None) -> Signal:
        now = datetime.now(tz=UTC)
        return Signal(
            stock_id=stock_id,
            direction="BUY",
            classification="swing",
            timeframe="1d",
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            suggested_qty=10,
            confidence_pct=75,
            factor_scores={},
            headline="t",
            status="active",
            validity_until=now + timedelta(days=5),
            profile_id=profile.id if profile else None,
            profile_key=profile.key if profile else None,
            volatility_reduced=False,
        )

    async def test_one_active_suggestion_per_stock_and_profile(
        self, db: AsyncSession
    ) -> None:
        stock = await make_stock(db, symbol="PROF1")
        profile = _row(_config(key="dc2", name="DC2"))
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        db.add(await self._signal(stock.id, profile))
        await db.commit()

        db.add(await self._signal(stock.id, profile))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_legacy_null_profile_rows_unconstrained(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="PROF2")
        db.add(await self._signal(stock.id, None))
        db.add(await self._signal(stock.id, None))
        await db.commit()  # two active legacy signals: fine

    async def test_referenced_profile_version_cannot_be_deleted(
        self, db: AsyncSession
    ) -> None:
        stock = await make_stock(db, symbol="PROF3")
        profile = _row(_config(key="multibagger", name="MB", style="investment"))
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        db.add(await self._signal(stock.id, profile))
        await db.commit()

        await db.delete(profile)
        with pytest.raises(IntegrityError):
            await db.commit()  # ON DELETE RESTRICT
        await db.rollback()


class TestUniverseService:
    async def test_kinds_resolve(self, db: AsyncSession) -> None:
        n50 = await make_stock(db, symbol="UNIV1", is_nifty50=True)
        fno = await make_stock(db, symbol="UNIV2", is_fno=True)
        plain = await make_stock(db, symbol="UNIV3")
        await db.commit()

        ids, _ = await resolve_universe(db, {"kind": "index", "value": "NIFTY50"})
        assert n50.id in ids and fno.id not in ids

        ids, _ = await resolve_universe(db, {"kind": "flag", "value": "fno"})
        assert fno.id in ids and plain.id not in ids

        ids, sym_map = await resolve_universe(db, {"kind": "symbols", "value": ["UNIV3"]})
        assert ids == [plain.id]
        assert sym_map[plain.id] == "UNIV3"

        ids, _ = await resolve_universe(db, {"kind": "all_active"})
        assert {n50.id, fno.id, plain.id} <= set(ids)

    async def test_unknown_kind_rejected(self, db: AsyncSession) -> None:
        with pytest.raises(ValidationError):
            await resolve_universe(db, {"kind": "dartboard"})

    async def test_legacy_adapter_matches_old_semantics(self, db: AsyncSession) -> None:
        n50 = await make_stock(db, symbol="UNIV4", is_nifty50=True)
        await db.commit()
        ids, _ = await resolve_legacy(db, "NIFTY50", None)
        assert n50.id in ids
        ids, _ = await resolve_legacy(db, "ignored", ["UNIV4"])
        assert ids == [n50.id]
