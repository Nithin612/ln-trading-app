//! Pure trading-engine logic.
//!
//! Discipline (see `.claude/rules/rust.md` in the repo root):
//! - no I/O, no clocks, no randomness — time and data enter as parameters;
//! - no panics: `Result`/`Option` everywhere, `unwrap` is denied by lint;
//! - money is i64 scaled 1e-4, indicator math is f64;
//! - semantics replicate the frozen Python reference (pandas-ta 0.4.71b0)
//!   exactly — "better" behavior without a spec change is a bug.

pub mod indicators;
pub mod patterns;
pub mod pivots;
pub mod structure;
pub mod types;

/// Crate version, re-exported for the Python module banner.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
