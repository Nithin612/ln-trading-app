//! `tradecore` — the Python face of engine-core, built by maturin.
//!
//! Conventions (see .claude/rules/rust.md):
//! - one call per BATCH of data, never per tick (GIL churn dominates);
//! - the GIL is released around anything non-trivial (`py.detach`);
//! - errors cross the FFI as typed Python exceptions, never panics.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

fn check_length(length: usize) -> PyResult<()> {
    if length == 0 {
        return Err(PyValueError::new_err("length must be >= 1"));
    }
    Ok(())
}

/// Version banner: "tradecore x.y.z (engine-core x.y.z)".
#[pyfunction]
fn version() -> String {
    format!(
        "tradecore {} (engine-core {})",
        env!("CARGO_PKG_VERSION"),
        engine_core::VERSION
    )
}

/// EMA with pandas-ta `sma=True` seeding. NaN during warmup.
#[pyfunction]
fn ema(py: Python<'_>, values: Vec<f64>, length: usize) -> PyResult<Vec<f64>> {
    check_length(length)?;
    Ok(py.detach(|| engine_core::indicators::ema(&values, length)))
}

/// RSI, pandas-ta 0.4.71b0 Wilder semantics. NaN at index 0.
#[pyfunction]
fn rsi(py: Python<'_>, values: Vec<f64>, length: usize) -> PyResult<Vec<f64>> {
    check_length(length)?;
    Ok(py.detach(|| engine_core::indicators::rsi(&values, length)))
}

/// Rolling simple moving average. NaN during warmup.
#[pyfunction]
fn sma(py: Python<'_>, values: Vec<f64>, length: usize) -> PyResult<Vec<f64>> {
    check_length(length)?;
    Ok(py.detach(|| engine_core::indicators::sma(&values, length)))
}

/// MACD → (line, signal, histogram). pandas-ta seeding semantics.
#[pyfunction]
fn macd(
    py: Python<'_>,
    values: Vec<f64>,
    fast: usize,
    slow: usize,
    signal: usize,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    if fast == 0 || slow == 0 || signal == 0 || fast >= slow {
        return Err(PyValueError::new_err(
            "require 0 < fast < slow and signal >= 1",
        ));
    }
    Ok(py.detach(|| engine_core::indicators::macd(&values, fast, slow, signal)))
}

/// ATR (standalone flavor: TR[0]=high−low, SMA seed over `length`).
#[pyfunction]
fn atr(
    py: Python<'_>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    length: usize,
) -> PyResult<Vec<f64>> {
    check_length(length)?;
    Ok(py.detach(|| engine_core::indicators::atr(&high, &low, &close, length)))
}

/// ADX → (adx, plus_di, minus_di). pandas-ta pure-python semantics.
#[pyfunction]
fn adx(
    py: Python<'_>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    length: usize,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    if length < 2 {
        return Err(PyValueError::new_err("length must be >= 2"));
    }
    Ok(py.detach(|| engine_core::indicators::adx(&high, &low, &close, length)))
}

/// Bollinger Bands → (lower, middle, upper). Sample std (ddof=1).
#[pyfunction]
fn bbands(
    py: Python<'_>,
    values: Vec<f64>,
    length: usize,
    k: f64,
) -> PyResult<(Vec<f64>, Vec<f64>, Vec<f64>)> {
    if length < 2 {
        return Err(PyValueError::new_err("length must be >= 2"));
    }
    if !k.is_finite() || k <= 0.0 {
        return Err(PyValueError::new_err("k must be finite and > 0"));
    }
    Ok(py.detach(|| engine_core::indicators::bbands(&values, length, k)))
}


// ── Full-engine surface (Phase 1 task 22) ───────────────────────────────────

use pyo3::types::{PyDict, PyList};

fn bars_from(
    open: &[f64],
    high: &[f64],
    low: &[f64],
    close: &[f64],
    volume: &[f64],
) -> PyResult<Vec<engine_core::types::Bar>> {
    let n = open.len();
    if [high.len(), low.len(), close.len(), volume.len()].iter().any(|&l| l != n) {
        return Err(PyValueError::new_err("OHLCV arrays must have equal length"));
    }
    Ok(open
        .iter()
        .zip(high)
        .zip(low)
        .zip(close)
        .zip(volume)
        .map(|((((&o, &h), &l), &c), &v)| engine_core::types::Bar {
            open: o,
            high: h,
            low: l,
            close: c,
            volume: v,
        })
        .collect())
}

/// Full confluence evaluation. Returns None below the gate, else a dict:
/// {direction, confidence, normalized, multibagger, factors: {name: [w, s]}}
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn score_signal(
    py: Python<'_>,
    open: Vec<f64>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: Vec<f64>,
    timeframe: String,
    min_confidence: i32,
) -> PyResult<Option<Py<PyDict>>> {
    let bars = bars_from(&open, &high, &low, &close, &volume)?;
    let outcome = py.detach(|| {
        engine_core::confluence::score_signal(
            &bars,
            &timeframe,
            min_confidence,
            engine_core::confluence::FlowInputs::default(),
        )
    });
    let Some(o) = outcome else { return Ok(None) };
    let d = PyDict::new(py);
    d.set_item(
        "direction",
        match o.direction {
            engine_core::confluence::Direction::Buy => "BUY",
            engine_core::confluence::Direction::Sell => "SELL",
        },
    )?;
    d.set_item("confidence", o.confidence_pct)?;
    d.set_item("normalized", o.normalized)?;
    d.set_item("multibagger", o.is_multibagger)?;
    let f = PyDict::new(py);
    for fac in &o.factors {
        f.set_item(fac.name, (fac.weight, fac.score))?;
    }
    d.set_item("factors", f)?;
    Ok(Some(d.into()))
}

/// Adjudicated-canon backtest for one stock. Trades as list of dicts.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn run_backtest_single(
    py: Python<'_>,
    open: Vec<f64>,
    high: Vec<f64>,
    low: Vec<f64>,
    close: Vec<f64>,
    volume: Vec<f64>,
    timeframe: String,
    capital: String,
    risk_pct: String,
    min_confidence: i32,
) -> PyResult<Py<PyList>> {
    let bars = bars_from(&open, &high, &low, &close, &volume)?;
    let params = engine_core::backtest::BacktestParams {
        capital: engine_core::risk::money_from_str(&capital)
            .ok_or_else(|| PyValueError::new_err("bad capital"))?,
        risk_pct: engine_core::risk::money_from_str(&risk_pct)
            .ok_or_else(|| PyValueError::new_err("bad risk_pct"))?,
        min_confidence,
        weight_multipliers: Vec::new(),
    };
    let trades = py.detach(|| engine_core::backtest::run_single_stock(&bars, &timeframe, &params));
    let out = PyList::empty(py);
    for t in trades {
        let d = PyDict::new(py);
        d.set_item("fill_idx", t.fill_idx)?;
        d.set_item("exit_idx", t.exit_idx)?;
        d.set_item(
            "direction",
            if t.side == engine_core::risk::Side::Buy { "BUY" } else { "SELL" },
        )?;
        d.set_item("confidence", t.confidence_pct)?;
        d.set_item("entry", t.entry)?;
        d.set_item("sl", t.stop_loss)?;
        d.set_item("tp", t.take_profit)?;
        d.set_item("qty", t.qty)?;
        d.set_item("exit_price", t.exit_price)?;
        d.set_item("pnl_pct", t.pnl_pct)?;
        d.set_item("hit_sl", t.hit_sl)?;
        d.set_item("hit_target", t.hit_target)?;
        out.append(d)?;
    }
    Ok(out.into())
}

#[pymodule]
fn tradecore(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(ema, m)?)?;
    m.add_function(wrap_pyfunction!(rsi, m)?)?;
    m.add_function(wrap_pyfunction!(sma, m)?)?;
    m.add_function(wrap_pyfunction!(macd, m)?)?;
    m.add_function(wrap_pyfunction!(atr, m)?)?;
    m.add_function(wrap_pyfunction!(adx, m)?)?;
    m.add_function(wrap_pyfunction!(bbands, m)?)?;
    m.add_function(wrap_pyfunction!(score_signal, m)?)?;
    m.add_function(wrap_pyfunction!(run_backtest_single, m)?)?;
    Ok(())
}
