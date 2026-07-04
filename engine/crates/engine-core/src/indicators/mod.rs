//! Incremental indicators with batch wrappers.
//!
//! Every indicator ships two forms:
//! - a `*State` struct with `update(&mut self, ...) -> Option<...>` — O(1)
//!   per tick, used by the live engine;
//! - a batch fn producing vectors (NaN during warmup) — used by backtests
//!   and parity tests, implemented ON TOP of the incremental state so live
//!   and batch can never drift apart.
//!
//! Reference semantics: pandas-ta 0.4.71b0 (the frozen Python engine).
//! Decoded quirks are documented per module; the committed fixture
//! `tests/fixtures/pandas_ta_reference.json` is the acceptance oracle.

mod adx;
mod atr;
mod bbands;
mod ema;
mod macd;
mod rsi;
mod sma;

pub use adx::{adx, AdxPoint, AdxState};
pub use atr::{atr, AtrState};
pub use bbands::{bbands, BbandsPoint, BbandsState};
pub use ema::{ema, EmaState};
pub use macd::{macd, MacdPoint, MacdState};
pub use rsi::{rsi, RsiState};
pub use sma::{sma, SmaState};
