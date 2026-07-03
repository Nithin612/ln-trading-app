//! `tradecore` — the Python face of engine-core, built by maturin.
//!
//! Conventions (see .claude/rules/rust.md):
//! - one call per BATCH of data, never per tick (GIL churn dominates);
//! - the GIL is released around anything non-trivial (`py.detach`);
//! - errors cross the FFI as typed Python exceptions, never panics.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

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
    if length == 0 {
        return Err(PyValueError::new_err("length must be >= 1"));
    }
    Ok(py.detach(|| engine_core::indicators::ema(&values, length)))
}

/// RSI, pandas-ta 0.4.71b0 Wilder semantics. NaN at index 0.
#[pyfunction]
fn rsi(py: Python<'_>, values: Vec<f64>, length: usize) -> PyResult<Vec<f64>> {
    if length == 0 {
        return Err(PyValueError::new_err("length must be >= 1"));
    }
    Ok(py.detach(|| engine_core::indicators::rsi(&values, length)))
}

#[pymodule]
fn tradecore(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(ema, m)?)?;
    m.add_function(wrap_pyfunction!(rsi, m)?)?;
    Ok(())
}
