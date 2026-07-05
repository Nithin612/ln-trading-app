"""ENGINE_IMPL wiring: the signal service dispatches to tradecore when
settings.engine_impl == "rust", and both paths agree on real data."""

import pytest
from app.core.config import settings
from app.services.signal_service import score_signal

from tests.parity.test_engine_parity import SYMBOLS, _load

pytestmark = pytest.mark.parity


@pytest.fixture(scope="module")
def corpus():
    import asyncio

    frames = asyncio.run(_load(SYMBOLS[:3], min_rows=450))
    if not frames:
        pytest.skip("ohlcv_1d empty — run scripts/backfill_eod.py")
    return frames


def test_rust_flag_dispatches_and_agrees(corpus, monkeypatch: pytest.MonkeyPatch) -> None:
    checked = 0
    for _sym, df in sorted(corpus.items()):
        for end in (320, 420, len(df)):
            w = df.iloc[end - 300 : end]
            monkeypatch.setattr(settings, "engine_impl", "python")
            py = score_signal(w, "1d", 70)
            monkeypatch.setattr(settings, "engine_impl", "rust")
            rs = score_signal(w, "1d", 70)
            assert (py is None) == (rs is None)
            if py is not None:
                assert rs.direction == py.direction
                assert rs.confidence_pct == py.confidence_pct
            checked += 1
    assert checked == 9


def test_rust_path_actually_calls_tradecore(corpus, monkeypatch: pytest.MonkeyPatch) -> None:
    import tradecore

    calls = []
    real = tradecore.score_signal

    def spy(*a, **kw):
        calls.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(tradecore, "score_signal", spy)
    monkeypatch.setattr(settings, "engine_impl", "rust")
    df = next(iter(corpus.values()))
    score_signal(df.iloc[-300:], "1d", 70)
    assert calls, "rust flag did not route through tradecore"
