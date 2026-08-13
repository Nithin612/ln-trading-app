"""Corpus attribution — Phase 6 slice 6.2b.

Unit-tests the trade→Row reconstruction (status mapping, regime from the ADX
level, MFE/MAE via the shared tape_excursion, RR, and the guard paths) — the
risky part. The full tradecore.run_universe path is validated by a real corpus
run and by the parity suite; here the empty-corpus path is also covered.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.services.corpus_attribution import compute_corpus_attribution, trade_to_row


def _bars():
    times = [datetime(2020, 1, d, tzinfo=UTC) for d in range(1, 6)]  # idx 0..4
    high = [100.0, 105.0, 103.0, 101.0, 100.0]
    low = [100.0, 99.0, 97.0, 100.0, 100.0]
    close = [100.0, 104.0, 98.0, 100.0, 100.0]
    adx = [float("nan"), 27.0, 22.0, 15.0, 15.0]
    return times, high, low, close, adx


def _trade(**kw):
    t = dict(
        direction="BUY", fill_idx=1, exit_idx=3, entry=100.0, sl=98.0, tp=106.0,
        confidence=82, hit_target=True, hit_sl=False,
    )
    t.update(kw)
    return t


def test_trade_to_row_long_reconstruction() -> None:
    """LONG: RR from entry/sl/tp, regime = ADX at the DECISION bar (fill−1),
    MFE/MAE via tape_excursion over [fill_idx, exit_idx] anchored at the entry."""
    r = trade_to_row(_trade(fill_idx=2, exit_idx=3), *_bars())
    assert r is not None
    assert r.status == "tp_first" and r.confidence == 82 and r.direction == "BUY"
    assert r.rr == pytest.approx(3.0)          # |106-100| / |100-98|
    assert r.adx == pytest.approx(27.0)        # adx at decision bar = fill(2)−1 = idx1
    # bars[2:4] anchored at 100: max high 103 → +1.5R; min low 97 → −1.5R
    assert r.mfe_r == pytest.approx(1.5)
    assert r.mae_r == pytest.approx(-1.5)


def test_status_mapping() -> None:
    assert trade_to_row(_trade(hit_target=True, hit_sl=False), *_bars()).status == "tp_first"
    assert trade_to_row(_trade(hit_target=False, hit_sl=True), *_bars()).status == "sl_first"
    assert trade_to_row(_trade(hit_target=False, hit_sl=False), *_bars()).status == "expired_open"


def test_short_direction_is_mapped() -> None:
    """SELL: favourable extreme is the LOW (min low 97 → +1.5R for a short)."""
    r = trade_to_row(_trade(direction="SELL", sl=102.0, tp=94.0), *_bars())
    assert r is not None
    assert r.rr == pytest.approx(3.0)          # |94-100| / |100-102|
    assert r.mfe_r == pytest.approx(1.5)       # (100-97)/2


def test_out_of_range_and_unmappable_return_none() -> None:
    assert trade_to_row(_trade(exit_idx=99), *_bars()) is None       # exit past bars
    assert trade_to_row(_trade(fill_idx=3, exit_idx=1), *_bars()) is None  # fill after exit
    assert trade_to_row(_trade(direction="HOLD"), *_bars()) is None  # unmappable


def test_adx_nan_is_regime_na() -> None:
    """A decision bar inside the ADX warmup (NaN) → adx None → 'regime n/a', not a
    wrong bucket. fill_idx=1 → decision bar idx0, whose adx is NaN."""
    r = trade_to_row(_trade(fill_idx=1, exit_idx=2), *_bars())
    assert r is not None and r.adx is None


def test_rr_zero_risk_is_none() -> None:
    r = trade_to_row(_trade(entry=100.0, sl=100.0), *_bars())
    assert r is not None and r.rr is None


def test_trade_factors_extracted() -> None:
    """trade['factors'] {name: [weight, score]} → Row.factors {name: score}."""
    r = trade_to_row(_trade(factors={"RSI_LEVEL": [10.0, 0.6], "ADX": [5.0, 0.0]}), *_bars())
    assert r is not None and r.factors == {"RSI_LEVEL": 0.6, "ADX": 0.0}


async def test_empty_corpus_returns_zero(db) -> None:
    """No Nifty50 bars (fresh test DB) → total 0, cohort 'corpus', no tradecore call."""
    rep = await compute_corpus_attribution(db)
    assert rep.total == 0 and rep.cohort == "corpus"
