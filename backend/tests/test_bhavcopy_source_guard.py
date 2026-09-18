"""Queue item 15 — the A10 guard on the bhavcopy downloader.

⭐ **The measured fact this file is built on.** On 2026-09-18 the 2022-08-08 URL still answers:

    HTTP 200 · 233,582 bytes · first four bytes `PK\\x03\\x04` · **858 newline bytes**

That is a ZIP served at a `.csv` URL, and it is the one session the 2021-22 backfill could not
ingest. The 858 "lines" matter: **a row-count floor would have passed it**. Real files carry
2,059-3,484 lines, so any floor low enough to be safe is far above 858 — the binary check and the
line floor catch different failures and neither subsumes the other.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.services.bhavcopy_service import (
    MIN_BHAVCOPY_LINES,
    BhavcopySourceError,
    _assert_plausible_bhavcopy,
)

D = date(2022, 8, 8)
_HEADER = b"SYMBOL,SERIES,DATE1,PREV_CLOSE,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE\n"


def _good(lines: int = MIN_BHAVCOPY_LINES + 500) -> bytes:
    body = b"RELIANCE,EQ,15-Jun-2021,2000,2010,2050,1990,2040\n" * lines
    return _HEADER + body


def test_a_real_looking_file_passes() -> None:
    """The canary. A guard that rejects everything 'fixes' ingestion by stopping it."""
    _assert_plausible_bhavcopy(_good(), D)


def test_the_2022_08_08_zip_is_refused() -> None:
    """⛔⛔ The actual failure, reproduced from its real signature."""
    zipped = b"PK\x03\x04" + (b"\x00\x01\n\x02" * 300)  # ~300 newlines, like the real body

    with pytest.raises(BhavcopySourceError, match="a ZIP/XLSX workbook"):
        _assert_plausible_bhavcopy(zipped, D)


def test_a_line_floor_alone_would_have_passed_the_zip() -> None:
    """⭐ Why both checks exist. The real ZIP carries 858 newline bytes — comfortably above any
    floor that is safe for real files, which start at 2,059 lines. If this ever fails, the two
    checks have stopped being independent and one of them can be removed."""
    real_zip_newlines = 858

    assert real_zip_newlines < MIN_BHAVCOPY_LINES, (
        "the measured ZIP would now be caught by the line floor alone"
    )


@pytest.mark.parametrize(
    ("magic", "expected"),
    [
        (b"\xd0\xcf\x11\xe0", "a legacy XLS workbook"),
        (b"%PDF", "served a PDF"),
        (b"\x1f\x8b", "a gzip stream"),
    ],
)
def test_other_binary_bodies_are_refused(magic: bytes, expected: str) -> None:
    """⚠ `match` is the point, not decoration. Without it these passed even with the
    magic-byte check removed — they were being caught by the SCHEMA assertion instead, so they
    asserted a failure without asserting the mechanism they are named for. Mutation testing
    found that; the match pins each case to the binary path.

    ⚠ And the match must be the CLASSIFICATION PHRASE, not a substring of the body.
    `match="PDF"` still passed under the mutation, because the schema error echoes the
    offending first line back — `got b'%PDF...'` — so the assertion was satisfied by
    the wrong code path. An error message that quotes its input can validate a test
    against a failure it did not cause."""
    with pytest.raises(BhavcopySourceError, match=expected):
        _assert_plausible_bhavcopy(magic + b"\n" * 2000, D)


def test_an_html_interstitial_is_refused() -> None:
    body = b"<!DOCTYPE html>\n<html><body>Access Denied</body></html>\n" * 400

    with pytest.raises(BhavcopySourceError, match="HTML"):
        _assert_plausible_bhavcopy(body, D)


def test_an_empty_body_is_refused() -> None:
    with pytest.raises(BhavcopySourceError, match="EMPTY"):
        _assert_plausible_bhavcopy(b"   \n  ", D)


def test_a_truncated_file_is_refused() -> None:
    with pytest.raises(BhavcopySourceError, match="below the"):
        _assert_plausible_bhavcopy(_good(lines=50), D)


def test_a_changed_schema_is_refused() -> None:
    """A header that no longer names SYMBOL and SERIES is not a bhavcopy, whatever its size."""
    body = b"COL_A,COL_B,COL_C\n" + (b"1,2,3\n" * 3000)

    with pytest.raises(BhavcopySourceError, match="SYMBOL and SERIES"):
        _assert_plausible_bhavcopy(body, D)


def test_the_error_names_the_date() -> None:
    """A failure that does not say WHICH session is a failure you cannot act on."""
    with pytest.raises(BhavcopySourceError, match="2022-08-08"):
        _assert_plausible_bhavcopy(b"PK\x03\x04" + b"\n" * 900, D)
