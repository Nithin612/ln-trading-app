"""§73 — the universe rule's INPUTS are recorded, not just its verdict.

⭐ The decision this file pins is **contents, not a fingerprint**. The plan originally
priced the artifact as "one CSV + one instruments hash per day"; five of six reviewers
independently said a hash cannot serve the purpose, because every consumer needs
`input` and a hash only gives `H(input)` — and `kite_instruments` is UPSERTED IN PLACE,
so yesterday's instrument state is already gone by the time anyone asks.

The sharpest consumer is the collapse rail: `apply_to_stocks` refuses a snapshot below
`universe_apply_min_fraction`, but it fires on a property of the INPUT while
`universe_snapshot` records the rule's OUTPUT. Before this table a refusal could be seen
and never explained, so the 0.5 threshold could never be tuned.
"""
from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.models.broker import KiteInstrument
from app.services.universe_materialiser import (
    load_inputs,
    load_recorded_csv,
    load_recorded_inputs,
    materialise,
    parse_eq_listed,
    record_inputs,
    record_parsed,
    record_source,
)
from app.services.universe_rule import RULE_VERSION, UniverseInputs, evaluate_all
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

AS_OF = date(2026, 9, 14)
HEADER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
    " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
)


def _csv(*symbols: str, series: str = "EQ") -> str:
    return HEADER + "".join(
        f"{s},{s} Ltd,{series},01-JAN-2000,10,1,INE000A0{i:04d},10\n"
        for i, s in enumerate(symbols)
    )


async def _instrument(db: AsyncSession, token: int, symbol: str) -> None:
    db.add(
        KiteInstrument(
            instrument_token=token, exchange_token=token >> 8, tradingsymbol=symbol,
            exchange="NSE", instrument_type="EQ", name=symbol,
            last_price=Decimal("100"), tick_size=Decimal("0.05"), lot_size=1,
            segment="NSE", expiry="", strike=Decimal("0"),
            synced_at=datetime.now(tz=UTC),
        )
    )


class TestTheRecordIsContentsNotAFingerprint:
    async def test_a_recorded_day_replays_to_the_same_verdicts(
        self, db: AsyncSession
    ) -> None:
        """⭐⭐ THE POINT OF THE WHOLE ITEM. Re-evaluating the rule against the RECORDED
        inputs must reproduce the day's verdicts exactly — that is what a hash could
        never support, and what makes "rule v2 behaves better than v1" falsifiable."""
        for i, sym in enumerate(("AAA", "BBB", "CCC")):
            await make_stock(db, symbol=sym)
            await _instrument(db, 1000 + i, sym)
        csv_text = _csv("AAA", "BBB")  # CCC is listed nowhere
        await db.commit()

        live_inputs = await load_inputs(db, csv_text=csv_text)
        original = evaluate_all(["AAA", "BBB", "CCC"], live_inputs)
        await record_inputs(db, as_of=AS_OF, csv_text=csv_text, inputs=live_inputs)

        replayed_inputs = await load_recorded_inputs(db, as_of=AS_OF)
        assert replayed_inputs is not None
        assert evaluate_all(["AAA", "BBB", "CCC"], replayed_inputs) == original
        # …and the verdicts are not vacuously all-equal
        assert original["AAA"][0] is True and original["CCC"][0] is False

    async def test_the_raw_source_round_trips_byte_for_byte(
        self, db: AsyncSession
    ) -> None:
        """Re-PARSING the stored bytes is what separates a source change from a parser
        change — the `EQ=0` header bug (a shifted column silently yielding an empty set)
        is exactly the case where the parsed set lies and the raw text does not."""
        csv_text = _csv("AAA", "BBB")
        await record_inputs(
            db, as_of=AS_OF, csv_text=csv_text,
            inputs=UniverseInputs(eq_listed=frozenset({"AAA"}), kite_tradable=frozenset()),
        )
        assert await load_recorded_csv(db, as_of=AS_OF) == csv_text
        # The stored parse and a fresh parse of the stored bytes are separable — here
        # they deliberately DISAGREE, which is the condition the artifact exists to expose.
        stored = await load_recorded_inputs(db, as_of=AS_OF)
        assert stored is not None
        assert stored.eq_listed == frozenset({"AAA"})
        assert parse_eq_listed(csv_text) == frozenset({"AAA", "BBB"})

    async def test_kite_tradable_is_recorded_because_it_is_upserted_in_place(
        self, db: AsyncSession
    ) -> None:
        """⚠ `kite_instruments` is upserted in place — the sync logs "57595 rows
        upserted, 0 stale swept" — so this set is unrecoverable after the fact by any
        route other than storing it. Here the table is emptied after recording, and the
        recorded inputs must survive that."""
        await make_stock(db, symbol="AAA")
        await _instrument(db, 1001, "AAA")
        await db.commit()
        inputs = await load_inputs(db, csv_text=_csv("AAA"))
        assert inputs.kite_tradable == frozenset({"AAA"})
        await record_inputs(db, as_of=AS_OF, csv_text=_csv("AAA"), inputs=inputs)

        await db.execute(text("DELETE FROM kite_instruments"))
        await db.commit()
        assert (await load_inputs(db, csv_text=_csv("AAA"))).kite_tradable == frozenset()
        recovered = await load_recorded_inputs(db, as_of=AS_OF)
        assert recovered is not None
        assert recovered.kite_tradable == frozenset({"AAA"})

    async def test_the_stored_bytes_are_compressed_and_digested(
        self, db: AsyncSession
    ) -> None:
        csv_text = _csv(*[f"SYM{i:04d}" for i in range(500)])
        digest = await record_inputs(
            db, as_of=AS_OF, csv_text=csv_text,
            inputs=UniverseInputs(eq_listed=frozenset(), kite_tradable=frozenset()),
        )
        row = (
            await db.execute(
                text(
                    "SELECT csv_gz, csv_sha256, rule_version, source_url"
                    " FROM universe_rule_inputs WHERE as_of = :d"
                ),
                {"d": AS_OF},
            )
        ).one()
        assert gzip.decompress(row.csv_gz).decode() == csv_text
        assert len(row.csv_gz) < len(csv_text.encode())  # compression actually applied
        assert row.csv_sha256 == digest and len(digest) == 64
        assert row.rule_version == RULE_VERSION
        assert "EQUITY_L.csv" in row.source_url


class TestIdempotence:
    async def test_re_running_a_day_replaces_it(self, db: AsyncSession) -> None:
        """Same contract `materialise()` keeps: a re-run after a fixed input must not
        leave two contradictory records for one date."""
        empty = UniverseInputs(eq_listed=frozenset(), kite_tradable=frozenset())
        first = await record_inputs(db, as_of=AS_OF, csv_text=_csv("AAA"), inputs=empty)
        second = await record_inputs(
            db, as_of=AS_OF, csv_text=_csv("AAA", "BBB"),
            inputs=UniverseInputs(eq_listed=frozenset({"BBB"}), kite_tradable=frozenset()),
        )
        assert first != second
        count = (
            await db.execute(
                text("SELECT count(*) FROM universe_rule_inputs WHERE as_of = :d"),
                {"d": AS_OF},
            )
        ).scalar()
        assert count == 1
        latest = await load_recorded_inputs(db, as_of=AS_OF)
        assert latest is not None and latest.eq_listed == frozenset({"BBB"})

    async def test_an_uncaptured_day_reads_as_absent_not_empty(
        self, db: AsyncSession
    ) -> None:
        """⚠ A24 — every day before 2026-09-14 has no record, and "we did not capture
        this" must never render as "the rule saw nothing that day"."""
        assert await load_recorded_inputs(db, as_of=date(2020, 1, 1)) is None
        assert await load_recorded_csv(db, as_of=date(2020, 1, 1)) is None


class TestTheRefusalIsNowAuditable:
    async def test_inputs_survive_a_refused_apply(self, db: AsyncSession) -> None:
        """⭐⭐ THE SHARPEST CONSUMER (§73/2). `apply_to_stocks` refuses a collapsed
        snapshot; the rail fires on a property of the INPUT while `universe_snapshot`
        holds the rule's OUTPUT. This asserts the input record is present and readable
        for a day whose apply was REFUSED — the only case anyone needs to inspect, and
        the reason the recording happens before the decision rather than after."""
        from app.services.universe_materialiser import apply_to_stocks

        for i, sym in enumerate(("AAA", "BBB", "CCC", "DDD")):
            await make_stock(db, symbol=sym, is_active=True)
            await _instrument(db, 2000 + i, sym)
        await db.commit()

        # A truncated feed: one EQ name out of four live ones.
        truncated = _csv("AAA")
        inputs = await load_inputs(db, csv_text=truncated)
        await record_inputs(db, as_of=AS_OF, csv_text=truncated, inputs=inputs)
        await materialise(db, as_of=AS_OF, inputs=inputs)

        try:
            await apply_to_stocks(db, as_of=AS_OF)
            refused = False
        except ValueError:
            refused = True
        assert refused, "a 1-of-4 snapshot must trip the collapse rail"

        # …and the INPUT that caused it is on record, so the threshold can be tuned.
        recorded = await load_recorded_inputs(db, as_of=AS_OF)
        assert recorded is not None
        assert recorded.eq_listed == frozenset({"AAA"})
        assert await load_recorded_csv(db, as_of=AS_OF) == truncated


class TestTheSourceSurvivesAParseFailure:
    """⛔ THE FIX FOR THE ARTIFACT'S OWN MOTIVATING CASE (bug-hunter, 2026-09-15).

    `record_inputs` originally ran AFTER `load_inputs`, which parses — and
    `parse_eq_listed` RAISES on an unrecognised header. So on the `EQ=0` header bug (a
    shifted column that makes the parse return nothing), the task died before recording
    anything, and the one artifact that separates a SOURCE change from a PARSER change was
    absent for the only day it was ever needed.
    """

    async def test_a_rejected_parse_still_leaves_the_bytes_on_record(
        self, db: AsyncSession
    ) -> None:
        shifted = _csv("AAA", "BBB").replace("SERIES", "SERIES_X", 1)
        # The parser refuses it — that is the guard working, and the whole problem.
        with pytest.raises(ValueError, match="no SERIES column"):
            parse_eq_listed(shifted)

        # The order path records the source BEFORE parsing, so the bytes survive.
        await record_source(db, as_of=AS_OF, raw=shifted.encode())
        assert await load_recorded_csv(db, as_of=AS_OF) == shifted

    async def test_an_unparsed_row_reads_as_absent_not_as_an_empty_universe(
        self, db: AsyncSession
    ) -> None:
        """⚠ The dangerous reading. NULL sets mean "captured, not understood"; returning
        an EMPTY UniverseInputs would replay as "the rule saw no listed equities", which
        is the same shape as the outage this whole rebuild is about."""
        await record_source(db, as_of=AS_OF, raw=_csv("AAA").encode())
        assert await load_recorded_inputs(db, as_of=AS_OF) is None
        # …and the raw half still answers, which is the point of keeping them separable.
        assert await load_recorded_csv(db, as_of=AS_OF) is not None

    async def test_parsed_sets_fill_in_afterwards(self, db: AsyncSession) -> None:
        await record_source(db, as_of=AS_OF, raw=_csv("AAA", "BBB").encode())
        await record_parsed(
            db,
            as_of=AS_OF,
            inputs=UniverseInputs(
                eq_listed=frozenset({"AAA", "BBB"}), kite_tradable=frozenset({"AAA"})
            ),
        )
        replayed = await load_recorded_inputs(db, as_of=AS_OF)
        assert replayed is not None
        assert replayed.eq_listed == frozenset({"AAA", "BBB"})

    async def test_a_new_source_invalidates_the_previous_parse(
        self, db: AsyncSession
    ) -> None:
        """⚠ Re-recording a day's SOURCE must not leave yesterday's parse attached to it —
        that would assert a set of symbols was derived from bytes it never came from."""
        await record_source(db, as_of=AS_OF, raw=_csv("AAA").encode())
        await record_parsed(
            db,
            as_of=AS_OF,
            inputs=UniverseInputs(eq_listed=frozenset({"AAA"}), kite_tradable=frozenset()),
        )
        assert await load_recorded_inputs(db, as_of=AS_OF) is not None

        await record_source(db, as_of=AS_OF, raw=_csv("ZZZ").encode())
        assert await load_recorded_inputs(db, as_of=AS_OF) is None
        assert await load_recorded_csv(db, as_of=AS_OF) == _csv("ZZZ")


class TestTheStoredBytesAreTheServedBytes:
    async def test_a_non_utf8_source_round_trips_exactly(
        self, db: AsyncSession
    ) -> None:
        """⚠ `download_equity_l` returns `resp.content`, not `resp.text`. httpx decodes
        with `errors="replace"` and NSE declares no charset, so a single Latin-1 byte
        would have become U+FFFD and been UNRECOVERABLE — while `csv_sha256` silently
        stopped matching a `sha256sum` of an independently fetched copy. Today's live file
        is pure ASCII, so the two agreed by luck; this pins it by construction."""
        served = "SYMBOL,NAME OF COMPANY, SERIES\nCAFé,Café Ltd,EQ\n".encode("latin-1")
        assert b"\xe9" in served  # the byte that a text round-trip destroys

        await record_source(db, as_of=AS_OF, raw=served)
        row = (
            await db.execute(
                text("SELECT csv_gz, csv_sha256 FROM universe_rule_inputs WHERE as_of = :d"),
                {"d": AS_OF},
            )
        ).one()
        assert gzip.decompress(row.csv_gz) == served  # byte for byte
        assert row.csv_sha256 == hashlib.sha256(served).hexdigest()
        # …and a lossy decode would NOT have produced that digest.
        lossy = served.decode("utf-8", errors="replace").encode("utf-8")
        assert lossy != served
        assert row.csv_sha256 != hashlib.sha256(lossy).hexdigest()
