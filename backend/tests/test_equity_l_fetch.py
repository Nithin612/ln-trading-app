"""A10 — the materialiser's fetch refuses a 200 OK that is not the file we asked for.

⛔ **`raise_for_status` covers only the status code, and the failures that actually happen
here return 200.** Measured against `parse_eq_listed` before this guard existed, FOUR
bodies parsed to an empty set and reported success:

    good CSV                       ->    1 symbols   ok
    EMPTY body                     ->    0 symbols   ⛔ SILENT EMPTY
    whitespace only                ->    0 symbols   ⛔ SILENT EMPTY
    HTML 200 interstitial          ->    0 symbols   ⛔ SILENT EMPTY
    header only, zero data rows    ->    0 symbols   ⛔ SILENT EMPTY
    shifted header (the EQ=0 bug)  -> RAISED ValueError
    all rows are BE series         ->    0 symbols   ⛔ SILENT EMPTY

⭐ The parser's own schema guard cannot catch them: it fires only when rows EXIST and the
header is wrong. This is §42d's shape through a different door, and the project has been
bitten by the identical thing twice — the `EQ=0` header bug, and a 200-OK login
interstitial in `sync_instruments` that "parsed to zero records and reported success".
"""
from __future__ import annotations

import httpx
import pytest
from app.services.universe_materialiser import (
    MIN_EQUITY_L_ROWS,
    _assert_plausible_equity_l,
    download_equity_l,
)

HEADER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,"
    " MARKET LOT, ISIN NUMBER, FACE VALUE\n"
)


def _real_sized_csv(rows: int = MIN_EQUITY_L_ROWS + 500) -> bytes:
    body = HEADER + "".join(
        f"SYM{i:05d},Co {i} Ltd,EQ,01-JAN-2000,10,1,INE{i:09d},10\n" for i in range(rows)
    )
    return body.encode()


class TestTheFetchRefusesA200ThatIsNotTheFile:
    @pytest.mark.parametrize(
        ("label", "body", "match"),
        [
            ("empty", b"", "EMPTY body"),
            ("whitespace", b"   \n  \n", "EMPTY body"),
            ("html interstitial", b"<html><body>Access Denied</body></html>", "HTML"),
            ("doctype interstitial", b"<!DOCTYPE html>\n<html>...", "HTML"),
            ("header only", HEADER.encode(), "below the"),
            ("truncated to a handful", (HEADER + "A,A,EQ,x,1,1,I,1\n" * 5).encode(), "below the"),
        ],
    )
    def test_each_silent_empty_now_raises(
        self, label: str, body: bytes, match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            _assert_plausible_equity_l(body)

    def test_a_real_sized_file_passes(self) -> None:
        """The canary. Without it, a guard that rejects EVERYTHING passes every test
        above — and this project has shipped a guard that could not fail before."""
        _assert_plausible_equity_l(_real_sized_csv())  # must not raise

    def test_the_floor_sits_far_below_the_real_file(self) -> None:
        """⚠ Measured, not chosen: the live file carries ~2,292 EQ names in ~2,568 rows,
        so a 1,000-line floor has >2x headroom — while every failure mode above yields
        ZERO lines of data. A floor that could plausibly be reached on a normal day would
        be a tripwire nobody leaves armed."""
        assert MIN_EQUITY_L_ROWS == 1000
        assert MIN_EQUITY_L_ROWS * 2 < 2568


class TestThroughTheRealClient:
    async def test_an_html_interstitial_is_refused_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Through `download_equity_l` itself, not just the helper — the guard has to be
        WIRED, and 'built but not wired' is the defect class V6 exists for."""
        transport = httpx.MockTransport(
            lambda _req: httpx.Response(200, text="<html>Access Denied</html>")
        )
        _patch_client(monkeypatch, transport)
        with pytest.raises(ValueError, match="HTML"):
            await download_equity_l()

    async def test_a_500_still_raises_for_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The half that already worked, pinned so a refactor cannot drop it."""
        transport = httpx.MockTransport(lambda _req: httpx.Response(500, text="boom"))
        _patch_client(monkeypatch, transport)
        with pytest.raises(httpx.HTTPStatusError):
            await download_equity_l()

    async def test_a_good_response_returns_the_bytes_verbatim(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = _real_sized_csv()
        transport = httpx.MockTransport(lambda _req: httpx.Response(200, content=body))
        _patch_client(monkeypatch, transport)
        assert await download_equity_l() == body  # bytes, not a re-encoded str


def _patch_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Route `httpx.AsyncClient` through a mock transport. ⚠ Patched at the module the
    materialiser imports it from, so the test exercises the real call site — including the
    landing-page warm-up request it makes before the archive fetch."""
    real = httpx.AsyncClient

    def factory(*a: object, **kw: object) -> httpx.AsyncClient:
        kw["transport"] = transport
        return real(*a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr("app.services.universe_materialiser.httpx.AsyncClient", factory)
