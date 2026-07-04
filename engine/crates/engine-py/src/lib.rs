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
    Ok(())
}
