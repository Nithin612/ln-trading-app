//! `tradecore` — the Python face of engine-core, built by maturin.
//!
//! Conventions (see .claude/rules/rust.md):
//! - one call per BATCH of data, never per tick (GIL churn dominates);
//! - the GIL is released around anything non-trivial (`py.detach`);
//! - errors cross the FFI as typed Python exceptions, never panics.

use engine_core::options::{Bsm, OptionType};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::sync::{Mutex, MutexGuard};

fn check_length(length: usize) -> PyResult<()> {
    if length == 0 {
        return Err(PyValueError::new_err("length must be >= 1"));
    }
    Ok(())
}

/// (delta, gamma, vega, theta, rho) — one option's Greeks across the FFI.
type GreekTuple = (f64, f64, f64, f64, f64);

fn parse_kind(kind: &str) -> PyResult<OptionType> {
    match kind.to_ascii_lowercase().as_str() {
        "call" | "c" | "ce" => Ok(OptionType::Call),
        "put" | "p" | "pe" => Ok(OptionType::Put),
        _ => Err(PyValueError::new_err(
            "option kind must be 'call'/'CE'/'c' or 'put'/'PE'/'p'",
        )),
    }
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
    if [high.len(), low.len(), close.len(), volume.len()]
        .iter()
        .any(|&l| l != n)
    {
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

/// Parse the FFI (kind, value) TP rule; money-scaled strings, never f64.
fn parse_tp_rule(tp_rule: Option<(String, String)>) -> PyResult<Option<engine_core::risk::TpRule>> {
    let Some((kind, value)) = tp_rule else {
        return Ok(None);
    };
    let v = engine_core::risk::money_from_str(&value)
        .ok_or_else(|| PyValueError::new_err(format!("bad tp_rule value {value:?}")))?;
    match kind.as_str() {
        "rr" => Ok(Some(engine_core::risk::TpRule::Rr(v))),
        "flat_pct" => Ok(Some(engine_core::risk::TpRule::FlatPct(v))),
        other => Err(PyValueError::new_err(format!(
            "unknown tp_rule kind {other:?} (rr | flat_pct)"
        ))),
    }
}

fn build_params(
    capital: &str,
    risk_pct: &str,
    min_confidence: i32,
    weight_multipliers: Vec<(String, f64)>,
    tp_rule: Option<(String, String)>,
) -> PyResult<engine_core::backtest::BacktestParams> {
    Ok(engine_core::backtest::BacktestParams {
        capital: engine_core::risk::money_from_str(capital)
            .ok_or_else(|| PyValueError::new_err("bad capital"))?,
        risk_pct: engine_core::risk::money_from_str(risk_pct)
            .ok_or_else(|| PyValueError::new_err("bad risk_pct"))?,
        min_confidence,
        weight_multipliers,
        tp_rule: parse_tp_rule(tp_rule)?,
    })
}

fn trade_to_dict<'py>(
    py: Python<'py>,
    t: &engine_core::backtest::Trade,
) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("fill_idx", t.fill_idx)?;
    d.set_item("exit_idx", t.exit_idx)?;
    d.set_item(
        "direction",
        if t.side == engine_core::risk::Side::Buy {
            "BUY"
        } else {
            "SELL"
        },
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
    let f = PyDict::new(py);
    for (name, weight, score) in &t.factors {
        f.set_item(name, (*weight, *score))?;
    }
    d.set_item("factors", f)?;
    Ok(d)
}

/// Adjudicated-canon backtest for one stock. Trades as list of dicts.
/// session_last_bar (slice 8c): per-bar flags, len == bars; None = off.
#[pyfunction]
#[pyo3(signature = (open, high, low, close, volume, timeframe, capital, risk_pct, min_confidence, weight_multipliers=Vec::new(), tp_rule=None, session_last_bar=None))]
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
    weight_multipliers: Vec<(String, f64)>,
    tp_rule: Option<(String, String)>,
    session_last_bar: Option<Vec<bool>>,
) -> PyResult<Py<PyList>> {
    let bars = bars_from(&open, &high, &low, &close, &volume)?;
    if let Some(flags) = &session_last_bar {
        if flags.len() != bars.len() {
            return Err(PyValueError::new_err(format!(
                "session_last_bar length {} != bars length {}",
                flags.len(),
                bars.len()
            )));
        }
    }
    let params = build_params(
        &capital,
        &risk_pct,
        min_confidence,
        weight_multipliers,
        tp_rule,
    )?;
    let trades = py.detach(|| {
        engine_core::backtest::run_single_stock(
            &bars,
            &timeframe,
            &params,
            session_last_bar.as_deref(),
        )
    });
    let out = PyList::empty(py);
    for t in &trades {
        out.append(trade_to_dict(py, t)?)?;
    }
    Ok(out.into())
}

/// Rayon-parallel universe backtest → [(symbol, [trade dicts])].
/// stocks: [(symbol, open, high, low, close, volume)]; money as strings.
/// session_last_bars (slice 8c): parallel to stocks, inner len == bars.
#[pyfunction]
#[pyo3(signature = (stocks, timeframe, capital, risk_pct, min_confidence, weight_multipliers=Vec::new(), tp_rule=None, session_last_bars=None))]
#[allow(clippy::type_complexity, clippy::too_many_arguments)]
fn run_universe(
    py: Python<'_>,
    stocks: Vec<(String, Vec<f64>, Vec<f64>, Vec<f64>, Vec<f64>, Vec<f64>)>,
    timeframe: String,
    capital: String,
    risk_pct: String,
    min_confidence: i32,
    weight_multipliers: Vec<(String, f64)>,
    tp_rule: Option<(String, String)>,
    session_last_bars: Option<Vec<Vec<bool>>>,
) -> PyResult<Py<PyList>> {
    let params = build_params(
        &capital,
        &risk_pct,
        min_confidence,
        weight_multipliers,
        tp_rule,
    )?;
    let mut universe: Vec<(String, Vec<engine_core::types::Bar>)> =
        Vec::with_capacity(stocks.len());
    for (sym, open, high, low, close, volume) in &stocks {
        universe.push((sym.clone(), bars_from(open, high, low, close, volume)?));
    }
    if let Some(flags) = &session_last_bars {
        if flags.len() != universe.len() {
            return Err(PyValueError::new_err(format!(
                "session_last_bars outer length {} != stocks length {}",
                flags.len(),
                universe.len()
            )));
        }
        for (i, ((sym, bars), f)) in universe.iter().zip(flags.iter()).enumerate() {
            if f.len() != bars.len() {
                return Err(PyValueError::new_err(format!(
                    "session_last_bars[{i}] ({sym}) length {} != bars length {}",
                    f.len(),
                    bars.len()
                )));
            }
        }
    }
    let results = py.detach(|| {
        engine_core::backtest::run_universe(
            &universe,
            &timeframe,
            &params,
            session_last_bars.as_deref(),
        )
    });
    let out = PyList::empty(py);
    for (sym, trades) in &results {
        let trade_list = PyList::empty(py);
        for t in trades {
            trade_list.append(trade_to_dict(py, t)?)?;
        }
        out.append((sym.as_str(), trade_list))?;
    }
    Ok(out.into())
}

/// Live tick→candle book (Phase 3 slice 3.3). One instance per session;
/// the host builds a fresh one at each daily restart with that day's
/// SessionSpec (epoch seconds, close exclusive — NSE calendar stays
/// host-side).
///
/// Money crosses this boundary as STRINGS in (Decimal-parseable, per
/// rules/rust.md) and raw i64·1e-4 OUT (host converts exactly via
/// `Decimal(raw) / 10**4` — never through f64).
///
/// Threading contract (slice 3.5-deferred, provisional confidence): the
/// consumer thread mutates via on_ticks/on_time/set_levels while the
/// provisional refresher thread reads via forming_snapshot — so the
/// pyclass is FROZEN and the book lives behind a Mutex. Every lock is
/// scoped entirely inside a `py.detach` closure or entirely under the
/// GIL — never across a GIL reacquisition — which makes a GIL↔lock
/// deadlock structurally impossible. Uncontended cost on the tick path
/// is one atomic lock/unlock per batch (~tens of ns); worst-case block
/// is the snapshot's copy window (µs-scale, every few seconds).
#[pyclass(frozen)]
struct LiveBook {
    inner: Mutex<engine_core::live::LiveBook>,
    tf_minutes: Vec<u32>,
}

/// Lock the book, mapping poisoning (an engine panic mid-call — "can't
/// happen" per the no-panic rules, but never silently ignored) to a loud
/// typed exception instead of unwrap.
fn lock_book(
    inner: &Mutex<engine_core::live::LiveBook>,
) -> PyResult<MutexGuard<'_, engine_core::live::LiveBook>> {
    inner
        .lock()
        .map_err(|_| PyRuntimeError::new_err("LiveBook mutex poisoned — engine panicked"))
}

fn live_events_to_list(
    py: Python<'_>,
    tf_minutes: &[u32],
    events: &[(u32, engine_core::live::LiveEvent)],
) -> PyResult<Py<PyList>> {
    use engine_core::live::LiveEvent;
    let out = PyList::empty(py);
    for (sid, event) in events {
        let d = PyDict::new(py);
        d.set_item("stock_id", sid)?;
        match event {
            LiveEvent::Forming { tf_idx, candle } | LiveEvent::Committed { tf_idx, candle } => {
                let c = candle;
                d.set_item(
                    "kind",
                    if matches!(event, LiveEvent::Forming { .. }) {
                        "forming"
                    } else {
                        "committed"
                    },
                )?;
                d.set_item(
                    "tf_minutes",
                    tf_minutes.get(*tf_idx).copied().ok_or_else(|| {
                        PyValueError::new_err(format!("tf_idx {tf_idx} out of range"))
                    })?,
                )?;
                d.set_item("time", c.period_start)?;
                d.set_item("open", c.open)?;
                d.set_item("high", c.high)?;
                d.set_item("low", c.low)?;
                d.set_item("close", c.close)?;
                d.set_item("volume", c.volume)?;
            }
            LiveEvent::Trigger { id, tag, price, ts } => {
                // Trigger layer (3.5): id/tag round-trip to the host's
                // level registry; price stays raw i64·1e-4 like candles.
                d.set_item("kind", "trigger")?;
                d.set_item("id", id)?;
                d.set_item("tag", tag.as_str())?;
                d.set_item("price", price)?;
                d.set_item("ts", ts)?;
            }
        }
        out.append(d)?;
    }
    Ok(out.into())
}

/// One host-supplied level dict → engine WatchLevel. Money crosses as
/// Decimal-parseable STRINGS (never f64); `vburst` names its timeframe in
/// MINUTES and is mapped to the book's tf index here, fail-loud.
fn extract_level(
    tf_minutes: &[u32],
    d: &Bound<'_, PyDict>,
) -> PyResult<engine_core::triggers::WatchLevel> {
    use engine_core::triggers::{LevelKind, WatchLevel};

    fn req<'py, T: for<'a> FromPyObject<'a, 'py>>(
        d: &Bound<'py, PyDict>,
        key: &str,
    ) -> PyResult<T> {
        let value = d
            .get_item(key)?
            .ok_or_else(|| PyValueError::new_err(format!("level missing {key:?}")))?;
        value
            .extract()
            .map_err(|_| PyValueError::new_err(format!("level field {key:?} has a bad type")))
    }
    fn money(d: &Bound<'_, PyDict>, key: &str) -> PyResult<i64> {
        let s: String = req(d, key)?;
        engine_core::risk::money_from_str(&s)
            .ok_or_else(|| PyValueError::new_err(format!("level field {key:?}: bad money {s:?}")))
    }

    let id: u64 = req(d, "id")?;
    let kind: String = req(d, "kind")?;
    let kind = match kind.as_str() {
        "zone" => LevelKind::Zone {
            low: money(d, "low")?,
            high: money(d, "high")?,
        },
        "cross_up" => LevelKind::CrossUp {
            price: money(d, "price")?,
            rearm_bp: req(d, "rearm_bp")?,
        },
        "cross_down" => LevelKind::CrossDown {
            price: money(d, "price")?,
            rearm_bp: req(d, "rearm_bp")?,
        },
        "near" => LevelKind::Near {
            price: money(d, "price")?,
            within_bp: req(d, "within_bp")?,
        },
        "vburst" => {
            let minutes: u32 = req(d, "tf_minutes")?;
            let tf_idx = tf_minutes
                .iter()
                .position(|&m| m == minutes)
                .ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "level {id}: tf_minutes {minutes} not in book timeframes {tf_minutes:?}"
                    ))
                })?;
            LevelKind::VolumeBurst {
                tf_idx,
                baseline: req(d, "baseline")?,
                mult_bp: req(d, "mult_bp")?,
            }
        }
        other => {
            return Err(PyValueError::new_err(format!(
                "level {id}: unknown kind {other:?} (zone|cross_up|cross_down|near|vburst)"
            )))
        }
    };
    Ok(WatchLevel { id, kind })
}

#[pymethods]
impl LiveBook {
    #[new]
    fn new(session_open_ts: i64, session_close_ts: i64, tf_minutes: Vec<u32>) -> PyResult<Self> {
        let inner = engine_core::live::LiveBook::new(
            engine_core::live::SessionSpec {
                open_ts: session_open_ts,
                close_ts: session_close_ts,
            },
            &tf_minutes,
        )
        .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(Self {
            inner: Mutex::new(inner),
            tf_minutes,
        })
    }

    /// Pre-create per-instrument state for the subscription list.
    fn ensure_instruments(&self, stock_ids: Vec<u32>) -> PyResult<()> {
        lock_book(&self.inner)?.ensure_instruments(&stock_ids);
        Ok(())
    }

    /// Replace one instrument's tick-trigger watch list (slice 3.5).
    /// Levels are dicts: {"id", "kind": zone|cross_up|cross_down|near|
    /// vburst, ...} with money fields as Decimal-parseable strings.
    /// Armed-state survives for unchanged (id, kind) pairs; validation is
    /// all-or-nothing and fail-loud. The host records every accepted call
    /// as an "lv" line in the replay stream.
    fn set_levels(&self, stock_id: u32, levels: Vec<Bound<'_, PyDict>>) -> PyResult<()> {
        let parsed = levels
            .iter()
            .map(|d| extract_level(&self.tf_minutes, d))
            .collect::<PyResult<Vec<_>>>()?;
        lock_book(&self.inner)?
            .set_levels(stock_id, &parsed)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }

    /// ONE call per Kite batch: [(stock_id, ts_epoch_s, price_str,
    /// day_volume|None, qty)] → list of event dicts. Bad price strings
    /// fail loud (a silently skipped tick is a data hole).
    fn on_ticks(
        &self,
        py: Python<'_>,
        ticks: Vec<(u32, i64, String, Option<u64>, u64)>,
    ) -> PyResult<Py<PyList>> {
        let mut parsed: Vec<(u32, engine_core::live::Tick)> = Vec::with_capacity(ticks.len());
        for (sid, ts, price, day_volume, qty) in &ticks {
            let money = engine_core::risk::money_from_str(price)
                .ok_or_else(|| PyValueError::new_err(format!("bad price {price:?}")))?;
            parsed.push((
                *sid,
                engine_core::live::Tick {
                    ts: *ts,
                    price: money,
                    day_volume: *day_volume,
                    qty: *qty,
                },
            ));
        }
        // Lock scoped INSIDE the detach closure — dropped before the GIL
        // is reacquired (the deadlock rule in the struct docs).
        let events = py.detach(|| -> PyResult<Vec<(u32, engine_core::live::LiveEvent)>> {
            let mut inner = lock_book(&self.inner)?;
            let mut out = Vec::with_capacity(parsed.len() * 2);
            inner.on_ticks(&parsed, &mut out);
            Ok(out)
        })?;
        live_events_to_list(py, &self.tf_minutes, &events)
    }

    /// Host time pulse: commit every bucket ended by now_ts. The host
    /// records these pulses in the replay stream alongside ticks (3.4).
    fn on_time(&self, py: Python<'_>, now_ts: i64) -> PyResult<Py<PyList>> {
        let events = py.detach(|| -> PyResult<Vec<(u32, engine_core::live::LiveEvent)>> {
            let mut inner = lock_book(&self.inner)?;
            let mut out = Vec::new();
            inner.on_time(now_ts, &mut out);
            Ok(out)
        })?;
        live_events_to_list(py, &self.tf_minutes, &events)
    }

    /// (pre_open, post_close, late, bad_price) reject counters.
    fn rejects(&self, stock_id: u32) -> PyResult<Option<(u64, u64, u64, u64)>> {
        Ok(lock_book(&self.inner)?
            .rejects(stock_id)
            .map(|r| (r.pre_open, r.post_close, r.late, r.bad_price)))
    }

    /// Read-only copy of the CURRENT forming candles for the given stocks
    /// (slice 3.5-deferred, provisional confidence). Called from the
    /// provisional refresher thread, never the consumer. Returns the same
    /// dict shape as "forming" events (money raw i64·1e-4); stocks or
    /// timeframes with no forming bucket are simply absent. This is a
    /// DERIVED OBSERVABILITY read: never an engine event, never recorded,
    /// never in replay.
    fn forming_snapshot(&self, py: Python<'_>, stock_ids: Vec<u32>) -> PyResult<Py<PyList>> {
        let tf_count = self.tf_minutes.len();
        let snap = py.detach(|| -> PyResult<Vec<(u32, engine_core::live::LiveEvent)>> {
            let inner = lock_book(&self.inner)?;
            let mut out = Vec::new();
            for &sid in &stock_ids {
                for tf_idx in 0..tf_count {
                    if let Some(candle) = inner.forming_candle(sid, tf_idx) {
                        out.push((
                            sid,
                            engine_core::live::LiveEvent::Forming { tf_idx, candle },
                        ));
                    }
                }
            }
            Ok(out)
        })?;
        live_events_to_list(py, &self.tf_minutes, &snap)
    }
}

/// Batch Black-Scholes–Merton prices. `kind` applies to the whole batch;
/// `rows` are (spot, strike, t, rate, carry, vol). Returns one price per row,
/// or `None` for a degenerate contract. `carry`: rate=BS, 0=Black-76, rate−q=Merton.
#[pyfunction]
fn option_price(
    py: Python<'_>,
    kind: &str,
    rows: Vec<(f64, f64, f64, f64, f64, f64)>,
) -> PyResult<Vec<Option<f64>>> {
    let k = parse_kind(kind)?;
    Ok(py.detach(|| {
        rows.iter()
            .map(|&(spot, strike, t, rate, carry, vol)| {
                engine_core::options::price(
                    k,
                    &Bsm {
                        spot,
                        strike,
                        t,
                        rate,
                        carry,
                        vol,
                    },
                )
            })
            .collect()
    }))
}

/// Batch Greeks. `rows` are (spot, strike, t, rate, carry, vol); each result is
/// (delta, gamma, vega, theta, rho) or `None` for a degenerate contract.
#[pyfunction]
fn option_greeks(
    py: Python<'_>,
    kind: &str,
    rows: Vec<(f64, f64, f64, f64, f64, f64)>,
) -> PyResult<Vec<Option<GreekTuple>>> {
    let k = parse_kind(kind)?;
    Ok(py.detach(|| {
        rows.iter()
            .map(|&(spot, strike, t, rate, carry, vol)| {
                engine_core::options::greeks(
                    k,
                    &Bsm {
                        spot,
                        strike,
                        t,
                        rate,
                        carry,
                        vol,
                    },
                )
                .map(|g| (g.delta, g.gamma, g.vega, g.theta, g.rho))
            })
            .collect()
    }))
}

/// Batch implied volatility. `rows` are (market_price, spot, strike, t, rate,
/// carry); each result is the annualized IV or `None` when the premium violates
/// the no-arbitrage bounds / carries no recoverable vol.
#[pyfunction]
fn implied_vol(
    py: Python<'_>,
    kind: &str,
    rows: Vec<(f64, f64, f64, f64, f64, f64)>,
) -> PyResult<Vec<Option<f64>>> {
    let k = parse_kind(kind)?;
    Ok(py.detach(|| {
        rows.iter()
            .map(|&(price, spot, strike, t, rate, carry)| {
                engine_core::options::implied_vol(k, price, spot, strike, t, rate, carry)
            })
            .collect()
    }))
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
    m.add_function(wrap_pyfunction!(option_price, m)?)?;
    m.add_function(wrap_pyfunction!(option_greeks, m)?)?;
    m.add_function(wrap_pyfunction!(implied_vol, m)?)?;
    m.add_function(wrap_pyfunction!(score_signal, m)?)?;
    m.add_function(wrap_pyfunction!(run_backtest_single, m)?)?;
    m.add_function(wrap_pyfunction!(run_universe, m)?)?;
    m.add_class::<LiveBook>()?;
    Ok(())
}
