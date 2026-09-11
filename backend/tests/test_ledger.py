"""B8 — the append-only ledger.

⛔ Why it exists: `positions` and `orders` are empty. The dev database was destroyed on
2026-09-07 with no backup, and that single fact made ten rounds of live-tape argument
unfalsifiable. These tests pin the two invariants that make the table worth having —
append-only, and mandatory provenance — because a ledger that can be edited or that admits
rows with no sample tag is not an audit trail.
"""

import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import ALL_NODE_TYPES, NODE_TYPES, LedgerEntry
from app.services import ledger as led

EXP = "test-experiment"
DV = "ohlcv_1d@2026-09-12"


async def _one(db: AsyncSession, chain: uuid.UUID, **kw: object) -> LedgerEntry:
    return await led.record(
        db, node_type=kw.pop("node_type", "decision_snapshot"),  # type: ignore[arg-type]
        chain_id=chain, as_of=date(2026, 9, 11), experiment_id=EXP, data_version=DV,
        **kw,  # type: ignore[arg-type]
    )


class TestProvenanceIsMandatory:
    async def test_a_row_cannot_omit_its_sample_tags(self, db: AsyncSession) -> None:
        """⭐ §16.1's rule has been violated eight times by five authors — twice by whoever
        was invoking it. Prose cannot carry it; a required argument can."""
        c = uuid.uuid4()
        with pytest.raises(led.LedgerError, match="mandatory"):
            await led.record(db, node_type="decision_snapshot", chain_id=c,
                             as_of=date(2026, 9, 11), experiment_id="", data_version=DV)
        with pytest.raises(led.LedgerError, match="mandatory"):
            await led.record(db, node_type="decision_snapshot", chain_id=c,
                             as_of=date(2026, 9, 11), experiment_id=EXP, data_version="")

    async def test_a_typod_node_type_is_refused(self, db: AsyncSession) -> None:
        """A row nobody will ever find is the same as a row that was not written."""
        with pytest.raises(led.LedgerError, match="unknown node_type"):
            await led.record(db, node_type="desicion_snapshot", chain_id=uuid.uuid4(),
                             as_of=date(2026, 9, 11), experiment_id=EXP, data_version=DV)

    async def test_the_code_commit_is_recorded(self, db: AsyncSession) -> None:
        """⭐ The scorer was verified untouched since its freeze ONLY because git said so."""
        row = await _one(db, uuid.uuid4())
        assert row.code_commit
        assert row.code_commit == led.current_commit()

    def test_current_commit_fails_to_unknown_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⚠ A ledger that refuses to record because git is unavailable is worse than one
        that records 'I don't know'. The point is that the row gets written."""
        led.current_commit.cache_clear()
        monkeypatch.setattr(
            led.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(OSError("no git")),
        )
        assert led.current_commit() == led.UNKNOWN
        led.current_commit.cache_clear()


class TestAppendOnly:
    async def test_a_correction_is_a_NEW_row_and_the_original_survives(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ THE CONTRACT. Editing in place would destroy exactly the information that
        makes an audit trail an audit trail: a reader must see both the wrong value and the
        right one, and be able to tell which came first."""
        c = uuid.uuid4()
        orig = await _one(db, c, payload={"qty": 100})
        await db.flush()
        fixed = await led.correct(db, orig, payload={"qty": 80}, label="requantified")
        await db.commit()

        rows = await led.chain(db, c)
        assert len(rows) == 2, "the original must still be there"
        assert {r.id for r in rows} == {orig.id, fixed.id}
        assert fixed.supersedes_id == orig.id
        assert orig.supersedes_id is None
        # the superseded row keeps its ORIGINAL value — it was not edited
        assert orig.payload == {"qty": 100}
        assert fixed.payload == {"qty": 80}
        # provenance rides along so the two remain comparable
        assert fixed.experiment_id == orig.experiment_id
        assert fixed.data_version == orig.data_version

    async def test_the_model_exposes_no_update_timestamp(self) -> None:
        """A column that invites mutation is an invitation to mutate."""
        assert "updated_at" not in LedgerEntry.__table__.columns

    async def test_the_chain_walks_in_order(self, db: AsyncSession) -> None:
        c = uuid.uuid4()
        made = []
        for nt in NODE_TYPES:
            made.append(await _one(db, c, node_type=nt))
            await db.flush()
        await db.commit()
        got = await led.chain(db, c)
        assert [r.node_type for r in got] == list(NODE_TYPES)
        assert len(ALL_NODE_TYPES) == len(NODE_TYPES) + 1  # + experiment_manifest

    async def test_chains_do_not_bleed_into_each_other(self, db: AsyncSession) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        await _one(db, a)
        await _one(db, b)
        await db.commit()
        assert len(await led.chain(db, a)) == 1
        assert len(await led.chain(db, b)) == 1


class TestExport:
    async def test_export_writes_ndjson_off_box(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """⚠ A ledger stored beside the database it describes protects against nothing —
        the 2026-09-07 loss would have taken both."""
        c = uuid.uuid4()
        await _one(db, c, payload={"a": 1}, label="first")
        await _one(db, c, node_type="execution", payload={"fill": "123.45"})
        await db.commit()

        path = await led.export_day(db, date(2026, 9, 11), tmp_path)
        assert path.exists()
        lines = [json.loads(x) for x in path.read_text().splitlines()]
        assert len(lines) == 2
        assert {x["node_type"] for x in lines} == {"decision_snapshot", "execution"}
        for x in lines:
            # every exported row carries its full provenance, or the export is useless
            for k in ("code_commit", "spec_version", "experiment_id", "data_version",
                      "as_of", "created_at", "chain_id"):
                assert x[k], f"{k} missing from the export"

    async def test_reexport_reproduces_rather_than_accumulates(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        """The ledger is the source of truth; the export is a projection of it."""
        await _one(db, uuid.uuid4())
        await db.commit()
        p1 = await led.export_day(db, date(2026, 9, 11), tmp_path)
        n1 = len(p1.read_text().splitlines())
        p2 = await led.export_day(db, date(2026, 9, 11), tmp_path)
        assert p1 == p2
        assert len(p2.read_text().splitlines()) == n1

    async def test_a_day_with_nothing_exports_an_empty_file_not_an_error(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        path = await led.export_day(db, date(1999, 1, 1), tmp_path)
        assert path.exists()
        assert path.read_text() == ""

    async def test_only_the_requested_day_is_exported(
        self, db: AsyncSession, tmp_path: Path
    ) -> None:
        c = uuid.uuid4()
        await _one(db, c)
        await led.record(db, node_type="execution", chain_id=c, as_of=date(2026, 9, 10),
                         experiment_id=EXP, data_version=DV)
        await db.commit()
        n = (await db.execute(select(func.count()).select_from(LedgerEntry))).scalar()
        assert n == 2
        path = await led.export_day(db, date(2026, 9, 11), tmp_path)
        assert len(path.read_text().splitlines()) == 1
