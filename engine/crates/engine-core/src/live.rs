//! LiveEngine core (Phase 3, slice 3.1): session-aligned tick→candle
//! state machine.
//!
//! Replaces the v1 Python `CandleAggregator`, fixing its three structural
//! defects: UTC-clock period floors (a 1h candle landed at 08:30 IST),
//! no session guard (pre-open ticks minted candles), and close-only-on-
//! next-tick (the 15:25–15:30 candle never committed until the next
//! session's first tick).
//!
//! Discipline (rules/rust.md): pure and deterministic — the NSE calendar,
//! wall clocks, and timezones stay HOST-side. A session enters as
//! `SessionSpec { open_ts, close_ts }` (epoch seconds), and every bucket
//! is an offset from `open_ts`, so there is no timezone math in core at
//! all. Half-days and muhurat sessions are just different parameters.
//!
//! ## Bucket canon (pinned here, mirrored by the slice-3.2 `ohlcv_1h`
//! rebuild; documented in docs/ARCHITECTURE.md)
//!
//! For timeframe N minutes, bucket k spans
//! `[open + k·N·60, min(open + (k+1)·N·60, close))`.
//! On the standard 09:15–15:30 IST session this makes 1h candles start at
//! 09:15, 10:15, …, 15:15 — the last being the 15:15–15:30 stub — and
//! leaves 1m/5m/15m identical to the Kite/backfill bucket times.
//!
//! ## Two output layers, distinct at the type level
//!
//! `LiveEvent::Forming` is the provisional layer (never persisted as
//! complete, never enters backtests); `LiveEvent::Committed` is the
//! candle-close layer (persisted `is_complete`, scoreable). A committed
//! (tf, period_start) can be emitted at most once per engine lifetime —
//! the no-repaint invariant, enforced by `committed_until`.
//!
//! ## Determinism for record/replay
//!
//! Output is a pure function of the (tick, time-pulse) input sequence.
//! `on_time` exists because the last candle of a session has no "next
//! tick" — the HOST drives it from its clock and MUST record those pulses
//! in the replay stream alongside ticks (slice 3.4).

use std::collections::HashMap;

use crate::triggers::{Firing, TriggerError, TriggerTag, WatchLevel, WatchSet};

/// One trading session in epoch seconds: `open_ts` inclusive,
/// `close_ts` exclusive.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionSpec {
    pub open_ts: i64,
    pub close_ts: i64,
}

/// One tick, converted at the FFI boundary: `price` is money (i64·1e-4),
/// `day_volume` the cumulative session volume counter (Kite MODE_FULL),
/// `qty` the last-traded-quantity fallback used only when `day_volume`
/// is absent.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Tick {
    pub ts: i64,
    pub price: i64,
    pub day_volume: Option<u64>,
    pub qty: u64,
}

/// One in-progress or committed candle. Prices are money (i64·1e-4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LiveCandle {
    pub period_start: i64,
    pub open: i64,
    pub high: i64,
    pub low: i64,
    pub close: i64,
    pub volume: u64,
}

impl LiveCandle {
    fn update(&mut self, price: i64, volume: u64) {
        if price > self.high {
            self.high = price;
        }
        if price < self.low {
            self.low = price;
        }
        self.close = price;
        self.volume += volume;
    }
}

/// Engine output. `tf_idx` indexes the constructor's timeframe list.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LiveEvent {
    /// Provisional layer: the forming candle changed. Never `is_complete`.
    Forming { tf_idx: usize, candle: LiveCandle },
    /// Committed layer: a candle closed. At most once per (tf, period).
    Committed { tf_idx: usize, candle: LiveCandle },
    /// Trigger layer (slice 3.5): a host-configured watch fired on this
    /// tick. `id` round-trips to the host's level registry untouched.
    /// Emitted after the tick's candle events, only for accepted
    /// in-session ticks — a recording with no `set_levels` calls replays
    /// to a stream with no `Trigger` events (golden compatibility).
    Trigger {
        id: u64,
        tag: TriggerTag,
        price: i64,
        ts: i64,
    },
}

/// Observability for everything the session guard refuses — rejected
/// input must be countable, not silent (record/replay fidelity).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct RejectCounters {
    pub pre_open: u64,
    pub post_close: u64,
    /// Out-of-order ticks older than the forming bucket (per-timeframe:
    /// one tick can be late for 5m yet in-bucket for 1h).
    pub late: u64,
    pub bad_price: u64,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum LiveError {
    #[error("session open_ts {open_ts} must precede close_ts {close_ts}")]
    BadSession { open_ts: i64, close_ts: i64 },
    #[error("timeframe list must be non-empty, minutes all > 0")]
    BadTimeframes,
}

/// Tick→candle state machine for ONE instrument and one session.
#[derive(Debug, Clone)]
pub struct InstrumentLive {
    session: SessionSpec,
    tf_minutes: Vec<u32>,
    forming: Vec<Option<LiveCandle>>,
    /// period_start of the last committed candle per tf (no-repaint guard).
    committed_until: Vec<i64>,
    last_day_volume: Option<u64>,
    rejects: RejectCounters,
    /// Host-configured tick triggers (slice 3.5); empty by default.
    watches: WatchSet,
    /// Newest accepted tick ts — triggers only evaluate on ticks that do
    /// not regress in time (an out-of-order price must not fire a cross).
    newest_tick_ts: i64,
}

impl InstrumentLive {
    pub fn new(session: SessionSpec, tf_minutes: &[u32]) -> Result<Self, LiveError> {
        if session.open_ts >= session.close_ts {
            return Err(LiveError::BadSession {
                open_ts: session.open_ts,
                close_ts: session.close_ts,
            });
        }
        if tf_minutes.is_empty() || tf_minutes.contains(&0) {
            return Err(LiveError::BadTimeframes);
        }
        Ok(Self {
            session,
            tf_minutes: tf_minutes.to_vec(),
            forming: vec![None; tf_minutes.len()],
            committed_until: vec![i64::MIN; tf_minutes.len()],
            last_day_volume: None,
            rejects: RejectCounters::default(),
            watches: WatchSet::default(),
            newest_tick_ts: i64::MIN,
        })
    }

    /// Replace this instrument's watch list (slice 3.5). Armed-state is
    /// preserved for unchanged (id, kind) pairs; validation is
    /// all-or-nothing. The HOST records every accepted call in the replay
    /// stream — levels are input, exactly like ticks.
    pub fn set_levels(&mut self, levels: &[WatchLevel]) -> Result<(), TriggerError> {
        self.watches.set_levels(levels, self.tf_minutes.len())
    }

    pub fn rejects(&self) -> RejectCounters {
        self.rejects
    }

    pub fn forming_candle(&self, tf_idx: usize) -> Option<LiveCandle> {
        self.forming.get(tf_idx).copied().flatten()
    }

    /// Traded volume represented by this tick: the cumulative day-volume
    /// counter diffed against the previous tick (v1 semantics preserved —
    /// summing per-tick quantities double-counts throttled snapshots).
    /// First tick / counter reset ⇒ 0, never the whole day.
    fn volume_delta(&mut self, tick: &Tick) -> u64 {
        let Some(day_vol) = tick.day_volume else {
            return tick.qty;
        };
        let delta = match self.last_day_volume {
            Some(prev) if day_vol >= prev => day_vol - prev,
            _ => 0,
        };
        self.last_day_volume = Some(day_vol);
        delta
    }

    /// Process one tick; events are appended to `out` (host-owned buffer,
    /// reused across calls — no per-tick allocation here).
    pub fn on_tick(&mut self, tick: &Tick, out: &mut Vec<LiveEvent>) {
        if tick.price <= 0 {
            self.rejects.bad_price += 1;
            return;
        }
        if tick.ts < self.session.open_ts {
            self.rejects.pre_open += 1;
            return;
        }
        if tick.ts >= self.session.close_ts {
            self.rejects.post_close += 1;
            return;
        }
        let volume = self.volume_delta(tick);
        let open_ts = self.session.open_ts;
        let rejects = &mut self.rejects;

        for (tf_idx, ((&minutes, forming), committed_until)) in self
            .tf_minutes
            .iter()
            .zip(self.forming.iter_mut())
            .zip(self.committed_until.iter_mut())
            .enumerate()
        {
            let start = bucket_start_from(open_ts, tick.ts, minutes);
            let fresh = LiveCandle {
                period_start: start,
                open: tick.price,
                high: tick.price,
                low: tick.price,
                close: tick.price,
                volume,
            };
            match forming {
                None => {
                    if start <= *committed_until {
                        // Tick for an already-committed bucket (arrived
                        // after an on_time flush) — re-minting would emit
                        // a duplicate Committed for the same period.
                        rejects.late += 1;
                        continue;
                    }
                    *forming = Some(fresh);
                    out.push(LiveEvent::Forming {
                        tf_idx,
                        candle: fresh,
                    });
                }
                Some(current) if start > current.period_start => {
                    *committed_until = current.period_start;
                    out.push(LiveEvent::Committed {
                        tf_idx,
                        candle: *current,
                    });
                    *forming = Some(fresh);
                    out.push(LiveEvent::Forming {
                        tf_idx,
                        candle: fresh,
                    });
                }
                Some(current) if start < current.period_start => {
                    // Older than the forming bucket for THIS timeframe;
                    // dropped rather than smeared into the wrong candle
                    // (v1 updated in place, corrupting close/high/low).
                    rejects.late += 1;
                }
                Some(current) => {
                    current.update(tick.price, volume);
                    out.push(LiveEvent::Forming {
                        tf_idx,
                        candle: *current,
                    });
                }
            }
        }

        // Trigger layer (3.5): evaluated AFTER the candle pass so volume
        // watches see this tick's forming state; only for ticks that do
        // not regress in time (a late tick's stale price must not flip
        // cross-state).
        if tick.ts >= self.newest_tick_ts {
            self.newest_tick_ts = tick.ts;
            if !self.watches.is_empty() {
                let forming = &self.forming;
                self.watches.on_price(
                    tick.price,
                    |tf_idx| {
                        forming
                            .get(tf_idx)
                            .copied()
                            .flatten()
                            .map(|c| (c.period_start, c.volume))
                    },
                    |f: Firing| {
                        out.push(LiveEvent::Trigger {
                            id: f.id,
                            tag: f.tag,
                            price: tick.price,
                            ts: tick.ts,
                        });
                    },
                );
            }
        }
    }

    /// Host-driven time pulse: commit every forming candle whose bucket
    /// has ended by `now_ts`. This is how the last candle of a session
    /// (and any idle instrument's candle) closes without a next tick.
    /// Idempotent — a committed slot is cleared and cannot re-commit.
    pub fn on_time(&mut self, now_ts: i64, out: &mut Vec<LiveEvent>) {
        let close_ts = self.session.close_ts;
        for (tf_idx, ((&minutes, forming), committed_until)) in self
            .tf_minutes
            .iter()
            .zip(self.forming.iter_mut())
            .zip(self.committed_until.iter_mut())
            .enumerate()
        {
            if let Some(current) = *forming {
                if bucket_end_from(current.period_start, minutes, close_ts) <= now_ts {
                    *committed_until = current.period_start;
                    *forming = None;
                    out.push(LiveEvent::Committed {
                        tf_idx,
                        candle: current,
                    });
                }
            }
        }
    }
}

#[inline]
fn bucket_start_from(open_ts: i64, ts: i64, minutes: u32) -> i64 {
    let span = i64::from(minutes) * 60;
    open_ts + ((ts - open_ts) / span) * span
}

#[inline]
fn bucket_end_from(period_start: i64, minutes: u32, close_ts: i64) -> i64 {
    (period_start + i64::from(minutes) * 60).min(close_ts)
}

/// All subscribed instruments for one session. Keys are stock ids.
#[derive(Debug)]
pub struct LiveBook {
    /// Validated blank-state engine, cloned per instrument — no fallible
    /// construction (and so no panic path) inside the hot loop.
    template: InstrumentLive,
    instruments: HashMap<u32, InstrumentLive>,
    /// Reusable per-tick event buffer — the hot path must not allocate
    /// per tick (rules/rust.md; perf-audit finding 9, 2026-07-10).
    scratch: Vec<LiveEvent>,
}

impl LiveBook {
    pub fn new(session: SessionSpec, tf_minutes: &[u32]) -> Result<Self, LiveError> {
        Ok(Self {
            template: InstrumentLive::new(session, tf_minutes)?,
            instruments: HashMap::new(),
            scratch: Vec::with_capacity(tf_minutes.len() * 2 + 8),
        })
    }

    /// Pre-create state for the subscription list so the hot path never
    /// allocates instrument entries mid-session.
    pub fn ensure_instruments(&mut self, stock_ids: &[u32]) {
        for &sid in stock_ids {
            self.entry(sid);
        }
    }

    fn entry(&mut self, stock_id: u32) -> &mut InstrumentLive {
        self.instruments
            .entry(stock_id)
            .or_insert_with(|| self.template.clone())
    }

    pub fn on_tick(&mut self, stock_id: u32, tick: &Tick, out: &mut Vec<(u32, LiveEvent)>) {
        let mut buf = std::mem::take(&mut self.scratch);
        buf.clear();
        self.entry(stock_id).on_tick(tick, &mut buf);
        out.extend(buf.iter().map(|e| (stock_id, *e)));
        self.scratch = buf; // hand the (possibly grown) buffer back
    }

    /// Batched tick entry point — one FFI call per Kite batch.
    pub fn on_ticks(&mut self, ticks: &[(u32, Tick)], out: &mut Vec<(u32, LiveEvent)>) {
        for (sid, tick) in ticks {
            self.on_tick(*sid, tick, out);
        }
    }

    pub fn on_time(&mut self, now_ts: i64, out: &mut Vec<(u32, LiveEvent)>) {
        let mut buf: Vec<LiveEvent> = Vec::new();
        // Deterministic order for replay: sorted by stock id.
        let mut ids: Vec<u32> = self.instruments.keys().copied().collect();
        ids.sort_unstable();
        for sid in ids {
            if let Some(inst) = self.instruments.get_mut(&sid) {
                buf.clear();
                inst.on_time(now_ts, &mut buf);
                out.extend(buf.iter().map(|e| (sid, *e)));
            }
        }
    }

    /// Route a level replacement to one instrument (created if unseen —
    /// levels can arrive before the first tick).
    pub fn set_levels(&mut self, stock_id: u32, levels: &[WatchLevel]) -> Result<(), TriggerError> {
        self.entry(stock_id).set_levels(levels)
    }

    pub fn rejects(&self, stock_id: u32) -> Option<RejectCounters> {
        self.instruments.get(&stock_id).map(|i| i.rejects())
    }

    pub fn forming_candle(&self, stock_id: u32, tf_idx: usize) -> Option<LiveCandle> {
        self.instruments
            .get(&stock_id)
            .and_then(|i| i.forming_candle(tf_idx))
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::indexing_slicing, clippy::panic)]
mod tests {
    use super::*;

    // A synthetic 09:15–15:30 session (epoch-anchored at an arbitrary
    // multiple-of-nothing to prove alignment comes from open_ts, not from
    // clock-hour floors): open at t=1_000_000, 6h15m long.
    const OPEN: i64 = 1_000_000;
    const CLOSE: i64 = OPEN + 6 * 3600 + 15 * 60;
    const SESSION: SessionSpec = SessionSpec {
        open_ts: OPEN,
        close_ts: CLOSE,
    };
    const TFS: [u32; 4] = [1, 5, 15, 60];
    const TF_1M: usize = 0;
    const TF_5M: usize = 1;

    fn tick(ts: i64, price: i64) -> Tick {
        Tick {
            ts,
            price,
            day_volume: None,
            qty: 10,
        }
    }

    fn committed(events: &[LiveEvent]) -> Vec<(usize, LiveCandle)> {
        events
            .iter()
            .filter_map(|e| match e {
                LiveEvent::Committed { tf_idx, candle } => Some((*tf_idx, *candle)),
                LiveEvent::Forming { .. } | LiveEvent::Trigger { .. } => None,
            })
            .collect()
    }

    #[test]
    fn hourly_bucket_canon_is_session_anchored() {
        // The canon table: 1h buckets start at open+0h..open+6h; the last
        // is the 15-minute stub [open+6h, close).
        for k in 0..6 {
            let ts = OPEN + k * 3600 + 1234;
            assert_eq!(bucket_start_from(OPEN, ts, 60), OPEN + k * 3600);
            assert_eq!(
                bucket_end_from(OPEN + k * 3600, 60, CLOSE),
                OPEN + (k + 1) * 3600
            );
        }
        let stub_start = OPEN + 6 * 3600;
        assert_eq!(bucket_start_from(OPEN, CLOSE - 1, 60), stub_start);
        assert_eq!(bucket_end_from(stub_start, 60, CLOSE), CLOSE); // 15-min stub
    }

    #[test]
    fn five_minute_buckets_partition_the_session() {
        assert_eq!(bucket_start_from(OPEN, OPEN, 5), OPEN);
        assert_eq!(bucket_start_from(OPEN, OPEN + 299, 5), OPEN);
        assert_eq!(bucket_start_from(OPEN, OPEN + 300, 5), OPEN + 300);
        // 6h15m = 75 five-minute buckets exactly; final bucket unclamped.
        let last_start = OPEN + 74 * 300;
        assert_eq!(bucket_start_from(OPEN, CLOSE - 1, 5), last_start);
        assert_eq!(bucket_end_from(last_start, 5, CLOSE), CLOSE);
    }

    #[test]
    fn session_guard_rejects_pre_open_and_post_close() {
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN - 1, 100_0000), &mut out);
        inst.on_tick(&tick(CLOSE, 100_0000), &mut out); // close is exclusive
        inst.on_tick(&tick(CLOSE + 60, 100_0000), &mut out);
        assert!(
            out.is_empty(),
            "no candle may be minted outside the session"
        );
        assert_eq!(inst.rejects().pre_open, 1);
        assert_eq!(inst.rejects().post_close, 2);
        assert_eq!(inst.forming_candle(TF_1M), None);
    }

    #[test]
    fn first_tick_mints_forming_on_every_timeframe() {
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 3, 123_4500), &mut out);
        assert_eq!(out.len(), TFS.len());
        for e in &out {
            match e {
                LiveEvent::Forming { candle, .. } => {
                    assert_eq!(candle.period_start, OPEN);
                    assert_eq!(candle.open, 123_4500);
                    assert_eq!(candle.close, 123_4500);
                    assert_eq!(candle.volume, 10);
                }
                LiveEvent::Committed { .. } => panic!("nothing to commit yet"),
                LiveEvent::Trigger { .. } => panic!("no levels configured"),
            }
        }
    }

    #[test]
    fn next_bucket_tick_commits_the_previous_candle() {
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 10, 100_0000), &mut out);
        inst.on_tick(&tick(OPEN + 30, 101_0000), &mut out);
        out.clear();
        // 90s later: a new 1m bucket — 1m commits, 5m/15m/1h still forming.
        inst.on_tick(&tick(OPEN + 90, 99_0000), &mut out);
        let done = committed(&out);
        assert_eq!(done.len(), 1);
        let (tf_idx, candle) = done[0];
        assert_eq!(tf_idx, TF_1M);
        assert_eq!(
            (
                candle.period_start,
                candle.open,
                candle.high,
                candle.low,
                candle.close
            ),
            (OPEN, 100_0000, 101_0000, 100_0000, 101_0000)
        );
        // the same tick opened the next 1m candle and updated the others
        assert_eq!(inst.forming_candle(TF_1M).unwrap().period_start, OPEN + 60);
        assert_eq!(inst.forming_candle(TF_5M).unwrap().low, 99_0000);
    }

    #[test]
    fn skipped_buckets_commit_once_without_phantom_candles() {
        // Illiquid stock: ticks in bucket 0 and bucket 3 — the bucket-0
        // candle commits once; buckets 1–2 never exist (matches Kite
        // historical, which omits empty buckets).
        let mut inst = InstrumentLive::new(SESSION, &[1]).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 5, 100_0000), &mut out);
        out.clear();
        inst.on_tick(&tick(OPEN + 3 * 60 + 5, 101_0000), &mut out);
        let done = committed(&out);
        assert_eq!(done.len(), 1);
        assert_eq!(done[0].1.period_start, OPEN);
        assert_eq!(inst.forming_candle(0).unwrap().period_start, OPEN + 180);
    }

    #[test]
    fn on_time_commits_the_session_last_candle_without_a_next_tick() {
        // The v1 flaw: the 15:25–15:30 candle only closed when the NEXT
        // session's first tick arrived.
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(CLOSE - 10, 100_5000), &mut out);
        out.clear();
        inst.on_time(CLOSE, &mut out);
        let done = committed(&out);
        assert_eq!(done.len(), TFS.len(), "every timeframe commits at close");
        for (_, c) in &done {
            assert_eq!(c.close, 100_5000);
        }
        // idempotent: nothing left to commit
        out.clear();
        inst.on_time(CLOSE + 3600, &mut out);
        assert!(out.is_empty());
    }

    #[test]
    fn on_time_mid_session_commits_only_ended_buckets() {
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 10, 100_0000), &mut out);
        out.clear();
        inst.on_time(OPEN + 60, &mut out); // 1m ended; 5m/15m/1h still open
        let done = committed(&out);
        assert_eq!(done.len(), 1);
        assert_eq!(done[0].0, TF_1M);
        assert!(inst.forming_candle(TF_5M).is_some());
        assert_eq!(inst.forming_candle(TF_1M), None);
    }

    #[test]
    fn tick_after_on_time_flush_for_same_bucket_is_late_not_repainted() {
        let mut inst = InstrumentLive::new(SESSION, &[1]).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 5, 100_0000), &mut out);
        inst.on_time(OPEN + 60, &mut out);
        out.clear();
        // straggler for the already-committed bucket
        inst.on_tick(&tick(OPEN + 59, 200_0000), &mut out);
        assert!(out.is_empty(), "must not re-mint a committed period");
        assert_eq!(inst.rejects().late, 1);
    }

    #[test]
    fn late_tick_is_per_timeframe() {
        // A tick older than the forming 1m bucket can still belong to the
        // forming 1h bucket: dropped for 1m, absorbed by 1h.
        let mut inst = InstrumentLive::new(SESSION, &[1, 60]).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 5, 100_0000), &mut out);
        inst.on_tick(&tick(OPEN + 130, 101_0000), &mut out); // 1m bucket 2
        out.clear();
        inst.on_tick(&tick(OPEN + 70, 99_0000), &mut out); // 1m bucket 1: late
        assert_eq!(inst.rejects().late, 1);
        let hourly = inst.forming_candle(1).unwrap();
        assert_eq!(hourly.low, 99_0000, "1h absorbed the in-bucket tick");
        let minute = inst.forming_candle(0).unwrap();
        assert_eq!(minute.period_start, OPEN + 120);
        assert_eq!(minute.low, 101_0000, "1m did not smear the late tick");
    }

    #[test]
    fn cumulative_day_volume_diff_with_reset_protection() {
        let mut inst = InstrumentLive::new(SESSION, &[5]).unwrap();
        let mut out = Vec::new();
        let t = |ts: i64, dv: u64| Tick {
            ts,
            price: 100_0000,
            day_volume: Some(dv),
            qty: 999, // must be ignored when day_volume is present
        };
        inst.on_tick(&t(OPEN + 1, 1_000), &mut out); // baseline → 0
        inst.on_tick(&t(OPEN + 2, 1_400), &mut out); // +400
        inst.on_tick(&t(OPEN + 3, 1_400), &mut out); // quote-only → +0
        assert_eq!(inst.forming_candle(0).unwrap().volume, 400);
        inst.on_tick(&t(OPEN + 4, 100), &mut out); // counter reset → 0, re-baseline
        assert_eq!(inst.forming_candle(0).unwrap().volume, 400);
        inst.on_tick(&t(OPEN + 5, 150), &mut out); // +50 from new baseline
        assert_eq!(inst.forming_candle(0).unwrap().volume, 450);
    }

    #[test]
    fn bad_price_rejected() {
        let mut inst = InstrumentLive::new(SESSION, &[1]).unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 1, 0), &mut out);
        inst.on_tick(&tick(OPEN + 1, -5), &mut out);
        assert!(out.is_empty());
        assert_eq!(inst.rejects().bad_price, 2);
    }

    #[test]
    fn constructor_rejects_bad_specs() {
        assert_eq!(
            InstrumentLive::new(
                SessionSpec {
                    open_ts: 10,
                    close_ts: 10
                },
                &[1]
            )
            .unwrap_err(),
            LiveError::BadSession {
                open_ts: 10,
                close_ts: 10
            }
        );
        assert!(InstrumentLive::new(SESSION, &[]).is_err());
        assert!(InstrumentLive::new(SESSION, &[5, 0]).is_err());
    }

    #[test]
    fn half_day_session_clamps_tails_data_driven() {
        // 09:15–13:00 half day (3h45m): the 1h set is 09:15..12:15 with a
        // 45-minute stub — parameters decide, never a calendar in core.
        // Proven through the engine itself: a tick in the stub commits at
        // the half-day close, not at a full hour.
        let close = OPEN + 3 * 3600 + 45 * 60;
        let mut inst = InstrumentLive::new(
            SessionSpec {
                open_ts: OPEN,
                close_ts: close,
            },
            &[60],
        )
        .unwrap();
        let stub_start = OPEN + 3 * 3600;
        assert_eq!(bucket_start_from(OPEN, close - 1, 60), stub_start);
        assert_eq!(bucket_end_from(stub_start, 60, close), close);
        let mut out = Vec::new();
        inst.on_tick(&tick(close - 10, 100_0000), &mut out);
        out.clear();
        inst.on_time(close, &mut out);
        let done = committed(&out);
        assert_eq!(done.len(), 1);
        assert_eq!(done[0].1.period_start, stub_start);
    }

    // ── Property-style invariants ────────────────────────────────────────────

    /// Deterministic pseudo-random stream (no rand dep, no real randomness:
    /// a fixed LCG — same input, same output, forever).
    fn lcg_stream(n: usize) -> Vec<Tick> {
        let mut state: u64 = 0x2545F4914F6CDD1D;
        let mut ticks = Vec::with_capacity(n);
        let span = (CLOSE - OPEN) as u64;
        for _ in 0..n {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let ts = OPEN + ((state >> 16) % span) as i64;
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let price = 90_0000 + ((state >> 16) % 20_0000) as i64;
            ticks.push(tick(ts, price));
        }
        ticks.sort_by_key(|t| t.ts);
        ticks
    }

    #[test]
    fn property_committed_candles_partition_ticks_exactly() {
        // For an in-session, time-ordered stream: after a final flush,
        // per timeframe the committed candles are exactly the non-empty
        // tick buckets, with OHLC = fold of that bucket's ticks, volume =
        // qty sum, and strictly increasing period_starts (no repaint).
        let ticks = lcg_stream(5_000);
        for minutes in [1u32, 5, 15, 60] {
            let mut inst = InstrumentLive::new(SESSION, &[minutes]).unwrap();
            let mut events = Vec::new();
            for t in &ticks {
                inst.on_tick(t, &mut events);
            }
            inst.on_time(CLOSE, &mut events);

            let span = i64::from(minutes) * 60;
            let mut expected: Vec<LiveCandle> = Vec::new();
            for t in &ticks {
                let start = OPEN + ((t.ts - OPEN) / span) * span;
                match expected.last_mut() {
                    Some(c) if c.period_start == start => c.update(t.price, t.qty),
                    _ => expected.push(LiveCandle {
                        period_start: start,
                        open: t.price,
                        high: t.price,
                        low: t.price,
                        close: t.price,
                        volume: t.qty,
                    }),
                }
            }
            let got: Vec<LiveCandle> = committed(&events).into_iter().map(|(_, c)| c).collect();
            assert_eq!(got, expected, "tf={minutes}m");
            assert!(
                got.windows(2)
                    .all(|w| w[0].period_start < w[1].period_start),
                "committed periods must be strictly increasing (tf={minutes}m)"
            );
            assert_eq!(inst.rejects(), RejectCounters::default());
        }
    }

    // ── Trigger layer (slice 3.5) ────────────────────────────────────────────

    use crate::triggers::{LevelKind, TriggerTag, WatchLevel};

    fn triggers(events: &[LiveEvent]) -> Vec<(u64, TriggerTag)> {
        events
            .iter()
            .filter_map(|e| match e {
                LiveEvent::Trigger { id, tag, .. } => Some((*id, *tag)),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn no_levels_means_no_trigger_events_stream_unchanged() {
        // The golden-compat guarantee: an instrument with no watches emits
        // exactly the pre-3.5 event stream.
        let ticks = lcg_stream(500);
        let mut plain = InstrumentLive::new(SESSION, &TFS).unwrap();
        let mut with_state = InstrumentLive::new(SESSION, &TFS).unwrap();
        with_state.set_levels(&[]).unwrap();
        let (mut a, mut b) = (Vec::new(), Vec::new());
        for t in &ticks {
            plain.on_tick(t, &mut a);
            with_state.on_tick(t, &mut b);
        }
        plain.on_time(CLOSE, &mut a);
        with_state.on_time(CLOSE, &mut b);
        assert_eq!(a, b);
        assert!(triggers(&a).is_empty());
    }

    #[test]
    fn trigger_events_follow_the_ticks_candle_events() {
        let mut inst = InstrumentLive::new(SESSION, &TFS).unwrap();
        inst.set_levels(&[WatchLevel {
            id: 42,
            kind: LevelKind::Zone {
                low: 100_0000,
                high: 101_0000,
            },
        }])
        .unwrap();
        let mut out = Vec::new();
        inst.on_tick(&tick(OPEN + 3, 100_5000), &mut out);
        // 4 forming events (one per tf) then the zone touch
        assert_eq!(out.len(), TFS.len() + 1);
        match out.last().unwrap() {
            LiveEvent::Trigger { id, tag, price, ts } => {
                assert_eq!(*id, 42);
                assert_eq!(*tag, TriggerTag::ZoneEnter);
                assert_eq!(*price, 100_5000);
                assert_eq!(*ts, OPEN + 3);
            }
            other => panic!("expected trigger last, got {other:?}"),
        }
    }

    #[test]
    fn rejected_and_time_regressing_ticks_never_touch_trigger_state() {
        let mut inst = InstrumentLive::new(SESSION, &[1]).unwrap();
        inst.set_levels(&[WatchLevel {
            id: 7,
            kind: LevelKind::CrossUp {
                price: 200_0000,
                rearm_bp: 0,
            },
        }])
        .unwrap();
        let mut out = Vec::new();
        // pre-open tick below the level must not seed cross-state
        inst.on_tick(&tick(OPEN - 5, 150_0000), &mut out);
        // first in-session observation above: no known transition, no fire
        inst.on_tick(&tick(OPEN + 10, 201_0000), &mut out);
        assert!(triggers(&out).is_empty());
        // an out-of-order tick BELOW the level must not arm the cross...
        out.clear();
        inst.on_tick(&tick(OPEN + 4, 150_0000), &mut out);
        // ...so a fresh tick above does not fire
        inst.on_tick(&tick(OPEN + 11, 202_0000), &mut out);
        assert!(
            triggers(&out).is_empty(),
            "time-regressing price must not flip cross-state"
        );
        // a genuine forward-in-time dip and cross fires
        out.clear();
        inst.on_tick(&tick(OPEN + 12, 199_0000), &mut out);
        inst.on_tick(&tick(OPEN + 13, 200_5000), &mut out);
        assert_eq!(triggers(&out), vec![(7, TriggerTag::CrossUp)]);
    }

    #[test]
    fn volume_burst_sees_the_current_ticks_forming_volume() {
        let mut inst = InstrumentLive::new(SESSION, &[1]).unwrap();
        inst.set_levels(&[WatchLevel {
            id: 9,
            kind: LevelKind::VolumeBurst {
                tf_idx: 0,
                baseline: 100,
                mult_bp: 20_000, // 2× ⇒ threshold 200
            },
        }])
        .unwrap();
        let mut out = Vec::new();
        let t = |ts: i64, qty: u64| Tick {
            ts,
            price: 100_0000,
            day_volume: None,
            qty,
        };
        inst.on_tick(&t(OPEN + 1, 150), &mut out); // 150 < 200
        assert!(triggers(&out).is_empty());
        inst.on_tick(&t(OPEN + 2, 60), &mut out); // 210 ≥ 200 — this tick tips it
        assert_eq!(triggers(&out), vec![(9, TriggerTag::VolumeBurst)]);
        out.clear();
        inst.on_tick(&t(OPEN + 61, 300), &mut out); // next bucket bursts on sight
        assert_eq!(triggers(&out), vec![(9, TriggerTag::VolumeBurst)]);
    }

    #[test]
    fn book_set_levels_routes_and_precedes_first_tick() {
        let mut book = LiveBook::new(SESSION, &[1]).unwrap();
        // levels arrive BEFORE the instrument's first tick (startup order)
        book.set_levels(
            5,
            &[WatchLevel {
                id: 1,
                kind: LevelKind::Zone {
                    low: 100_0000,
                    high: 101_0000,
                },
            }],
        )
        .unwrap();
        let mut out = Vec::new();
        book.on_ticks(&[(5, tick(OPEN + 1, 100_5000))], &mut out);
        let fired: Vec<(u32, u64)> = out
            .iter()
            .filter_map(|(sid, e)| match e {
                LiveEvent::Trigger { id, .. } => Some((*sid, *id)),
                _ => None,
            })
            .collect();
        assert_eq!(fired, vec![(5, 1)]);
        // other instruments are untouched
        out.clear();
        book.on_ticks(&[(6, tick(OPEN + 2, 100_5000))], &mut out);
        assert!(triggers(&out.iter().map(|(_, e)| *e).collect::<Vec<_>>()).is_empty());
    }

    #[test]
    fn book_routes_per_instrument_and_orders_on_time_deterministically() {
        let mut book = LiveBook::new(SESSION, &[1]).unwrap();
        book.ensure_instruments(&[7, 3]);
        let mut out = Vec::new();
        book.on_ticks(
            &[(7, tick(OPEN + 1, 100_0000)), (3, tick(OPEN + 2, 200_0000))],
            &mut out,
        );
        assert_eq!(out.len(), 2);
        out.clear();
        book.on_time(CLOSE, &mut out);
        let ids: Vec<u32> = out.iter().map(|(sid, _)| *sid).collect();
        assert_eq!(ids, vec![3, 7], "flush order is sorted by stock id");
        assert!(book.forming_candle(7, 0).is_none());
    }
}
