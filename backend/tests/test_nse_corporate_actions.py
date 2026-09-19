"""Item 16 — corporate actions cached from the authority, and the two conventions that bite.

⭐⭐ The rule: **a predicate encoding an external authority must be a CACHE of its answers, not
a RULE you evaluate.** What we had instead was a rule — flag any `|gap| > 25%` — which M70
measured at **62.5% false-positive** (5 of 8 flagged events were genuine price moves).

⛔ Every subject string below is **verbatim from the live NSE feed**, captured 2026-09-19 for
January 2024. Invented fixtures would test the parser against my idea of the format rather than
the format.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.models.corporate_action import CorporateAction
from app.services.nse_corporate_actions import (
    ParsedAction,
    ingest_corporate_actions,
    parse_subject,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

# ── Verbatim from the feed ───────────────────────────────────────────────────
NESTLE = "Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share"
PGIL = "Face Value Split (Sub-Division) - From Rs10/- Per Share To Rs 5/- Per Share"
COCHIN = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"
BONUS_1_1 = "Bonus 1:1"
BONUS_3_1 = "Bonus 3:1"
RIGHTS = "Rights 6:179 @ Premium Rs 1810/-"
DIVIDEND = "Interim Dividend - Re 0.01 Per Share"
AGM = "Annual General Meeting"
EGM = "Extra Ordinary General Meeting"


# ── Convention 1: NSE publishes the BONUS ratio, the model stores the TOTAL ──

def test_a_one_for_one_bonus_doubles_the_holding() -> None:
    """The model's own docstring: a 1:1 bonus is 1→2, 'a holder ends with 2 shares per 1
    held'. NSE writes that as `Bonus 1:1` — one NEW share per one held."""
    assert parse_subject(BONUS_1_1) == ("bonus", 1, 2)


def test_a_three_for_one_bonus_quadruples_the_holding() -> None:
    """⛔⛔ THE CONVENTION THAT SILENTLY CORRUPTS AN ADJUSTMENT. `Bonus 3:1` is three NEW
    shares per one held, so the holder ends with FOUR. Storing 3:1 verbatim would apply a ×3
    where ×4 is correct — a 25% error in every adjusted price and quantity."""
    assert parse_subject(BONUS_3_1) == ("bonus", 1, 4)


# ── Convention 2: face value moves OPPOSITE to the share count ───────────────

def test_a_face_value_split_from_ten_to_one_is_a_ten_times_share_increase() -> None:
    """⛔⛔ NESTLEIND 2024-01-05 — the same event the 25% gap screen flagged (27,116 → 2,754).
    The authority states it as face value ₹10 → ₹1; that is a TENTH of the face value and
    therefore TEN TIMES the shares. Reading the direction backwards inverts the adjustment."""
    assert parse_subject(NESTLE) == ("split", 1, 10)


def test_ten_to_five_is_a_doubling_not_a_halving() -> None:
    assert parse_subject(PGIL) == ("split", 1, 2)


def test_the_parser_survives_the_whitespace_variants_the_feed_actually_emits() -> None:
    """`Rs10/-` and `Rs 10/-` both occur in the SAME fifteen-record response."""
    assert parse_subject(COCHIN) == parse_subject(PGIL) == ("split", 1, 2)


def test_a_non_integer_ratio_is_kept_exact_rather_than_rounded() -> None:
    """Face value 10 → 4 is ×2.5 shares, i.e. 2→5. Rounding to 1→2 or 1→3 would silently
    misprice every holding."""
    subject = "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 4/- Per Share"
    assert parse_subject(subject) == ("split", 2, 5)


def test_a_consolidation_is_not_read_as_a_split() -> None:
    """Face value going UP is a reverse split — the model has no type for it, so the honest
    answer is None rather than an inverted split."""
    subject = "Face Value Split (Sub-Division) - From Rs 1/- Per Share To Rs 10/- Per Share"
    assert parse_subject(subject) is None


# ── What must NOT be parsed ──────────────────────────────────────────────────

@pytest.mark.parametrize("subject", [RIGHTS, DIVIDEND, AGM, EGM, "", "Scheme of Arrangement"])
def test_non_split_non_bonus_events_return_none_never_a_guess(subject: str) -> None:
    """⚠ Rights genuinely dilute and do move the price, but `action_type` admits only
    split|bonus — so they are reported as `unsupported` by the ingest rather than forced into
    a type that would misprice them."""
    assert parse_subject(subject) is None


def test_a_rights_ratio_is_not_mistaken_for_a_bonus() -> None:
    """`Rights 6:179` contains a ratio and the word order is similar. Matching it as a bonus
    would invent a 30x share increase out of a rights issue."""
    assert parse_subject(RIGHTS) is None


# ── The ingest ───────────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload: list[dict[str, str]]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, str]]:
        return self._payload


class _FakeClient:
    """Stands in for the NSE client. The network is not under test; the mapping is."""

    def __init__(self, payload: list[dict[str, str]]) -> None:
        self._payload = payload

    async def get(self, _url: str, params: dict[str, str] | None = None) -> _FakeResponse:
        return _FakeResponse(self._payload)


def _rec(symbol: str, ex: str, subject: str, series: str = "EQ") -> dict[str, str]:
    return {"symbol": symbol, "exDate": ex, "subject": subject, "series": series}


@pytest.mark.asyncio
async def test_an_authority_split_lands_in_corporate_actions(db: AsyncSession) -> None:
    stock = await make_stock(db, symbol="NESTLEIND")
    client = _FakeClient([_rec("NESTLEIND", "05-Jan-2024", NESTLE)])

    out = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31), client=client  # type: ignore[arg-type]
    )

    assert out["inserted"] == 1
    row = (await db.execute(CorporateAction.__table__.select())).one()
    assert row.stock_id == stock.id
    assert (row.action_type, row.ratio_from, row.ratio_to) == ("split", 1, 10)
    assert row.source == "nse"
    assert row.note == NESTLE, "the raw subject must be kept verbatim on every row"


@pytest.mark.asyncio
async def test_a_manual_row_is_never_overwritten_and_a_conflict_is_reported(
    db: AsyncSession,
) -> None:
    """⚠ An admin-verified ratio was checked by a person against the actual event; a prose
    parse has not been. Where they disagree the human wins AND the disagreement is surfaced —
    silently keeping either one would hide a parser bug."""
    stock = await make_stock(db, symbol="NESTLEIND")
    db.add(CorporateAction(
        stock_id=stock.id, action_type="split", ex_date=date(2024, 1, 5),
        ratio_from=1, ratio_to=5, source="manual", note="checked by hand",
    ))
    await db.flush()

    out = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31),
        client=_FakeClient([_rec("NESTLEIND", "05-Jan-2024", NESTLE)]),  # type: ignore[arg-type]
    )

    assert out["inserted"] == 0
    assert out["manual_conflicts"] == 1
    rows = (await db.execute(CorporateAction.__table__.select())).all()
    assert len(rows) == 1
    assert rows[0].ratio_to == 5, "the human's ratio must survive"
    assert rows[0].source == "manual"


@pytest.mark.asyncio
async def test_unparsed_actions_are_reported_not_silently_dropped(db: AsyncSession) -> None:
    """⛔ A dropped action is indistinguishable from 'there was no action' — the exact failure
    this item exists to end."""
    await make_stock(db, symbol="GRASIM")
    out = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31),
        client=_FakeClient([  # type: ignore[arg-type]
            _rec("GRASIM", "10-Jan-2024", RIGHTS),
            _rec("SPICEJET", "03-Jan-2024", AGM),
        ]),
    )

    assert out["inserted"] == 0
    assert out["unsupported"] == 2
    subjects = [u["subject"] for u in out["unsupported_sample"]]
    assert RIGHTS in subjects


@pytest.mark.asyncio
async def test_government_securities_are_excluded(db: AsyncSession) -> None:
    """The feed carries GS interest payments; one was the FIRST record of the probe."""
    out = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31),
        client=_FakeClient([  # type: ignore[arg-type]
            _rec("83GS2040", "01-Jan-2024", "Interest Payment", series="GS"),
        ]),
    )
    assert out["parsed"] == 0 and out["unsupported"] == 0


@pytest.mark.asyncio
async def test_an_unknown_symbol_is_counted_not_crashed_on(db: AsyncSession) -> None:
    """A CA for a name not in our universe is normal — the feed covers all of NSE."""
    out = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31),
        client=_FakeClient([_rec("NOTOURS", "05-Jan-2024", BONUS_1_1)]),  # type: ignore[arg-type]
    )
    assert out["unknown_symbol"] == 1 and out["inserted"] == 0


@pytest.mark.asyncio
async def test_re_ingesting_the_same_window_is_idempotent(db: AsyncSession) -> None:
    await make_stock(db, symbol="NESTLEIND")
    client = _FakeClient([_rec("NESTLEIND", "05-Jan-2024", NESTLE)])
    first = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31), client=client)  # type: ignore[arg-type]
    second = await ingest_corporate_actions(
        db, date(2024, 1, 1), date(2024, 1, 31), client=client)  # type: ignore[arg-type]

    assert first["inserted"] == 1
    assert second["inserted"] == 0 and second["already_present"] == 1


def test_the_parsed_action_keeps_its_raw_subject() -> None:
    a = ParsedAction("X", date(2024, 1, 5), "split", 1, 10, NESTLE)
    assert a.raw == NESTLE


def test_the_factor_matches_the_models_own_arithmetic() -> None:
    """⭐ Cross-check against `CorporateAction.factor`, which the adjuster uses: qty × factor,
    price ÷ factor. A 1→10 split must yield exactly 10."""
    kind, rf, rt = parse_subject(NESTLE)  # type: ignore[misc]
    assert kind == "split"
    ca = CorporateAction(stock_id=1, action_type=kind, ex_date=date(2024, 1, 5),
                         ratio_from=rf, ratio_to=rt)
    assert ca.factor == Decimal(10)
