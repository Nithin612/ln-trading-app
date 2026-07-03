//! Incremental indicators with batch wrappers.
//!
//! Every indicator ships two forms:
//! - a `*State` struct with `update(&mut self, x) -> Option<f64>` — O(1) per
//!   tick, used by the live engine;
//! - a batch fn producing `Vec<f64>` (NaN during warmup) — used by backtests
//!   and parity tests, implemented ON TOP of the incremental state so live
//!   and batch can never drift apart.
//!
//! Reference semantics: pandas-ta 0.4.71b0 (the frozen Python engine).

mod ema;
mod rsi;

pub use ema::{ema, EmaState};
pub use rsi::{rsi, RsiState};
