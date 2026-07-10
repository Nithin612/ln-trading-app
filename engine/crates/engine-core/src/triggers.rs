//! Tick-trigger layer (Phase 3, slice 3.5): host-configured price/volume
//! watches evaluated inside the live tick path.
//!
//! Discipline is the same as `live.rs`: pure and deterministic. Levels are
//! DATA — the host loads them (active-signal zones, PDH/PDL, S/R, volume
//! baselines) and records every `set_levels` call in the replay stream, so
//! trigger events are as replayable as candles. The engine never knows
//! what a level *means*; `id` and `tag` round-trip to the host untouched.
//!
//! ## Re-arm semantics (the anti-spam contract)
//!
//! Every watch is a two-state machine: ARMED → fires once on its condition
//! → DISARMED → re-arms only when the re-arm condition holds. A choppy
//! tape sitting on a level cannot re-fire per tick. Duplicate delivery is
//! still possible across process restarts (fresh state) — the alert layer
//! is at-least-once by design; consumers dedupe by (id, day).
//!
//! * `Zone`: fires when price is first observed inside `[low, high]`
//!   (including on the very first tick — a live touch must not be lost to
//!   restart timing); re-arms when price leaves the zone.
//! * `CrossUp`/`CrossDown`: strictly transition-based (never fires on the
//!   first observation); re-arms once price retreats past the level by
//!   `rearm_bp` basis points on the origin side.
//! * `Near`: fires when |price − level| first comes within `within_bp` of
//!   the level; re-arms when price leaves the band.
//! * `VolumeBurst`: fires when the forming candle's volume on `tf_idx`
//!   reaches `baseline × mult_bp/10_000`; re-arms on the next bucket.

/// Basis-point denominator (1 bp = 0.01%).
const BP: i64 = 10_000;

/// What a watch looks for. Prices are money (i64·1e-4), like all of live.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LevelKind {
    /// Price inside `[low, high]` (entry zones). `low <= high` validated.
    Zone { low: i64, high: i64 },
    /// Upward cross of `price` (prev below-or-at, now above).
    CrossUp { price: i64, rearm_bp: u32 },
    /// Downward cross of `price` (prev above-or-at, now below).
    CrossDown { price: i64, rearm_bp: u32 },
    /// Within `within_bp` basis points of `price` (SL/TP proximity).
    Near { price: i64, within_bp: u32 },
    /// Forming-candle volume on `tf_idx` ≥ baseline · mult_bp/10⁴.
    VolumeBurst {
        tf_idx: usize,
        baseline: u64,
        mult_bp: u32,
    },
}

/// One host-configured watch. `id` is host-assigned, unique per
/// instrument, and round-trips through [`crate::live::LiveEvent::Trigger`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WatchLevel {
    pub id: u64,
    pub kind: LevelKind,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum TriggerError {
    #[error("duplicate watch id {id} for one instrument")]
    DuplicateId { id: u64 },
    #[error("watch id {id}: zone low {low} must be <= high {high}")]
    BadZone { id: u64, low: i64, high: i64 },
    #[error("watch id {id}: price/baseline must be > 0")]
    BadLevel { id: u64 },
    #[error("watch id {id}: tf_idx {tf_idx} out of range ({tf_count} timeframes)")]
    BadTfIdx {
        id: u64,
        tf_idx: usize,
        tf_count: usize,
    },
}

/// Trigger firing, as carried by [`crate::live::LiveEvent::Trigger`].
/// `tag` names the condition so downstream consumers are self-describing
/// without holding the level registry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TriggerTag {
    ZoneEnter,
    CrossUp,
    CrossDown,
    Near,
    VolumeBurst,
}

impl TriggerTag {
    pub fn as_str(self) -> &'static str {
        match self {
            TriggerTag::ZoneEnter => "zone_enter",
            TriggerTag::CrossUp => "cross_up",
            TriggerTag::CrossDown => "cross_down",
            TriggerTag::Near => "near",
            TriggerTag::VolumeBurst => "volume_burst",
        }
    }
}

/// One watch plus its armed-state. The state survives `set_levels`
/// refreshes for unchanged (id, kind) pairs — a periodic host refresh
/// must not re-fire everything sitting inside a zone.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WatchState {
    pub level: WatchLevel,
    state: ArmState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ArmState {
    /// Armed; for cross watches, `prev_side` tracks which side of the
    /// level the last observation was on (None until first observation).
    Armed { prev_side: Option<Side> },
    /// Fired; waiting for the re-arm condition. For `VolumeBurst` the
    /// payload is the bucket that fired (re-arm = new bucket).
    Fired { fired_bucket: i64 },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Side {
    Below,
    AboveOrAt,
}

fn side_of(price: i64, level: i64) -> Side {
    if price < level {
        Side::Below
    } else {
        Side::AboveOrAt
    }
}

/// |a − b| without overflow surprises (prices are ≥ 0 in practice).
fn abs_diff(a: i64, b: i64) -> i64 {
    (a - b).abs()
}

/// Price is within `within_bp` basis points of `level`.
fn within_band(price: i64, level: i64, within_bp: u32) -> bool {
    // band = level · within_bp / 10⁴, computed in i128 — no overflow for
    // any representable money value.
    let band = (i128::from(level) * i128::from(within_bp)) / i128::from(BP);
    i128::from(abs_diff(price, level)) <= band
}

fn validate(levels: &[WatchLevel], tf_count: usize) -> Result<(), TriggerError> {
    for (i, w) in levels.iter().enumerate() {
        if levels.iter().skip(i + 1).any(|other| other.id == w.id) {
            return Err(TriggerError::DuplicateId { id: w.id });
        }
        match w.kind {
            LevelKind::Zone { low, high } => {
                if low <= 0 || high <= 0 {
                    return Err(TriggerError::BadLevel { id: w.id });
                }
                if low > high {
                    return Err(TriggerError::BadZone {
                        id: w.id,
                        low,
                        high,
                    });
                }
            }
            LevelKind::CrossUp { price, rearm_bp } | LevelKind::CrossDown { price, rearm_bp } => {
                // rearm_bp >= 100% would need a retreat past zero — a
                // permanently-disarmed watch is a host bug, fail loud.
                if price <= 0 || rearm_bp >= 10_000 {
                    return Err(TriggerError::BadLevel { id: w.id });
                }
            }
            LevelKind::Near { price, within_bp } => {
                if price <= 0 || within_bp == 0 {
                    return Err(TriggerError::BadLevel { id: w.id });
                }
            }
            LevelKind::VolumeBurst {
                tf_idx,
                baseline,
                mult_bp,
            } => {
                // baseline·mult_bp < 10⁴ truncates the threshold to 0 —
                // a watch that can never fire is a host bug, fail loud.
                if baseline == 0
                    || mult_bp == 0
                    || u128::from(baseline) * u128::from(mult_bp) < BP as u128
                {
                    return Err(TriggerError::BadLevel { id: w.id });
                }
                if tf_idx >= tf_count {
                    return Err(TriggerError::BadTfIdx {
                        id: w.id,
                        tf_idx,
                        tf_count,
                    });
                }
            }
        }
    }
    Ok(())
}

/// Per-instrument watch set. Owned by `live::InstrumentLive`; evaluation
/// is a linear scan over a handful of watches — no allocation.
#[derive(Debug, Clone, Default)]
pub struct WatchSet {
    watches: Vec<WatchState>,
}

/// A firing produced by evaluation, before the live layer wraps it with
/// stock id and event plumbing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Firing {
    pub id: u64,
    pub tag: TriggerTag,
}

impl WatchSet {
    /// Replace the watch list, preserving armed-state for watches whose
    /// (id, kind) is unchanged. Validation is all-or-nothing: on error the
    /// existing set stays untouched.
    pub fn set_levels(
        &mut self,
        levels: &[WatchLevel],
        tf_count: usize,
    ) -> Result<(), TriggerError> {
        validate(levels, tf_count)?;
        let old = std::mem::take(&mut self.watches);
        self.watches = levels
            .iter()
            .map(|&level| {
                old.iter()
                    .find(|w| w.level == level)
                    .copied()
                    .unwrap_or(WatchState {
                        level,
                        state: ArmState::Armed { prev_side: None },
                    })
            })
            .collect();
        Ok(())
    }

    pub fn is_empty(&self) -> bool {
        self.watches.is_empty()
    }

    /// Evaluate all watches against an accepted in-session tick.
    /// `forming_volume(tf_idx)` and `forming_bucket(tf_idx)` expose the
    /// live layer's forming state for volume watches; `on_fire` receives
    /// each firing (append-to-buffer at the call site — no allocation
    /// here).
    pub fn on_price(
        &mut self,
        price: i64,
        forming_volume: impl Fn(usize) -> Option<(i64, u64)>,
        mut on_fire: impl FnMut(Firing),
    ) {
        for w in &mut self.watches {
            match w.level.kind {
                LevelKind::Zone { low, high } => {
                    let inside = price >= low && price <= high;
                    match w.state {
                        ArmState::Armed { .. } => {
                            if inside {
                                w.state = ArmState::Fired { fired_bucket: 0 };
                                on_fire(Firing {
                                    id: w.level.id,
                                    tag: TriggerTag::ZoneEnter,
                                });
                            }
                        }
                        ArmState::Fired { .. } => {
                            if !inside {
                                w.state = ArmState::Armed { prev_side: None };
                            }
                        }
                    }
                }
                LevelKind::CrossUp {
                    price: level,
                    rearm_bp,
                } => {
                    let side = side_of(price, level);
                    match w.state {
                        ArmState::Armed { prev_side } => {
                            if prev_side == Some(Side::Below) && side == Side::AboveOrAt {
                                w.state = ArmState::Fired { fired_bucket: 0 };
                                on_fire(Firing {
                                    id: w.level.id,
                                    tag: TriggerTag::CrossUp,
                                });
                            } else {
                                w.state = ArmState::Armed {
                                    prev_side: Some(side),
                                };
                            }
                        }
                        ArmState::Fired { .. } => {
                            // Re-arm once price retreats below the level by
                            // rearm_bp (0 bp ⇒ any tick strictly below).
                            let floor = level
                                - ((i128::from(level) * i128::from(rearm_bp)) / i128::from(BP))
                                    as i64;
                            if price < floor {
                                w.state = ArmState::Armed {
                                    prev_side: Some(Side::Below),
                                };
                            }
                        }
                    }
                }
                LevelKind::CrossDown {
                    price: level,
                    rearm_bp,
                } => {
                    let side = side_of(price, level);
                    match w.state {
                        ArmState::Armed { prev_side } => {
                            if prev_side == Some(Side::AboveOrAt) && side == Side::Below {
                                w.state = ArmState::Fired { fired_bucket: 0 };
                                on_fire(Firing {
                                    id: w.level.id,
                                    tag: TriggerTag::CrossDown,
                                });
                            } else {
                                w.state = ArmState::Armed {
                                    prev_side: Some(side),
                                };
                            }
                        }
                        ArmState::Fired { .. } => {
                            let ceil = level
                                + ((i128::from(level) * i128::from(rearm_bp)) / i128::from(BP))
                                    as i64;
                            if price > ceil {
                                w.state = ArmState::Armed {
                                    prev_side: Some(Side::AboveOrAt),
                                };
                            }
                        }
                    }
                }
                LevelKind::Near {
                    price: level,
                    within_bp,
                } => {
                    let near = within_band(price, level, within_bp);
                    match w.state {
                        ArmState::Armed { .. } => {
                            if near {
                                w.state = ArmState::Fired { fired_bucket: 0 };
                                on_fire(Firing {
                                    id: w.level.id,
                                    tag: TriggerTag::Near,
                                });
                            }
                        }
                        ArmState::Fired { .. } => {
                            if !near {
                                w.state = ArmState::Armed { prev_side: None };
                            }
                        }
                    }
                }
                LevelKind::VolumeBurst {
                    tf_idx,
                    baseline,
                    mult_bp,
                } => {
                    let Some((bucket, volume)) = forming_volume(tf_idx) else {
                        continue;
                    };
                    let threshold = (u128::from(baseline) * u128::from(mult_bp)) / (BP as u128);
                    let burst = u128::from(volume) >= threshold && threshold > 0;
                    match w.state {
                        ArmState::Armed { .. } => {
                            if burst {
                                w.state = ArmState::Fired {
                                    fired_bucket: bucket,
                                };
                                on_fire(Firing {
                                    id: w.level.id,
                                    tag: TriggerTag::VolumeBurst,
                                });
                            }
                        }
                        ArmState::Fired { fired_bucket } => {
                            if bucket != fired_bucket {
                                w.state = ArmState::Armed { prev_side: None };
                                if burst {
                                    w.state = ArmState::Fired {
                                        fired_bucket: bucket,
                                    };
                                    on_fire(Firing {
                                        id: w.level.id,
                                        tag: TriggerTag::VolumeBurst,
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::indexing_slicing, clippy::panic)]
mod tests {
    use super::*;

    fn no_volume(_: usize) -> Option<(i64, u64)> {
        None
    }

    fn fire_all(set: &mut WatchSet, price: i64) -> Vec<Firing> {
        let mut out = Vec::new();
        set.on_price(price, no_volume, |f| out.push(f));
        out
    }

    fn zone(id: u64, low: i64, high: i64) -> WatchLevel {
        WatchLevel {
            id,
            kind: LevelKind::Zone { low, high },
        }
    }

    #[test]
    fn zone_fires_on_first_observation_inside_and_rearms_on_exit() {
        let mut set = WatchSet::default();
        set.set_levels(&[zone(1, 100_0000, 101_0000)], 4).unwrap();
        // first tick already inside → a live touch, fires
        assert_eq!(fire_all(&mut set, 100_5000).len(), 1);
        // still inside → silent
        assert!(fire_all(&mut set, 100_9000).is_empty());
        // exit → re-arms, silently
        assert!(fire_all(&mut set, 102_0000).is_empty());
        // re-enter → fires again
        let f = fire_all(&mut set, 101_0000);
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].tag, TriggerTag::ZoneEnter);
        assert_eq!(f[0].id, 1);
    }

    #[test]
    fn zone_outside_first_then_enter_fires_once() {
        let mut set = WatchSet::default();
        set.set_levels(&[zone(9, 100_0000, 101_0000)], 4).unwrap();
        assert!(fire_all(&mut set, 99_0000).is_empty());
        assert_eq!(fire_all(&mut set, 100_0000).len(), 1); // boundary inclusive
        assert!(fire_all(&mut set, 100_0000).is_empty());
    }

    #[test]
    fn cross_up_needs_a_transition_never_first_tick() {
        let mut set = WatchSet::default();
        set.set_levels(
            &[WatchLevel {
                id: 2,
                kind: LevelKind::CrossUp {
                    price: 200_0000,
                    rearm_bp: 0,
                },
            }],
            4,
        )
        .unwrap();
        // first observation ABOVE the level: no fire (no known transition)
        assert!(fire_all(&mut set, 201_0000).is_empty());
        // drop below, then cross → fires
        assert!(fire_all(&mut set, 199_0000).is_empty());
        let f = fire_all(&mut set, 200_0000); // at-level counts as crossed
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].tag, TriggerTag::CrossUp);
        // sitting above → silent; dipping below re-arms (rearm_bp = 0)
        assert!(fire_all(&mut set, 205_0000).is_empty());
        assert!(fire_all(&mut set, 199_9999).is_empty());
        assert_eq!(fire_all(&mut set, 200_0001).len(), 1);
    }

    #[test]
    fn cross_up_rearm_band_blocks_chop() {
        // 100 bp re-arm band on a 200.0000 level → must retreat below
        // 198.0000 before the next fire.
        let mut set = WatchSet::default();
        set.set_levels(
            &[WatchLevel {
                id: 3,
                kind: LevelKind::CrossUp {
                    price: 200_0000,
                    rearm_bp: 100,
                },
            }],
            4,
        )
        .unwrap();
        fire_all(&mut set, 199_0000);
        assert_eq!(fire_all(&mut set, 200_5000).len(), 1);
        // chop just below the level: inside the re-arm band → still disarmed
        assert!(fire_all(&mut set, 199_5000).is_empty());
        assert!(fire_all(&mut set, 200_5000).is_empty());
        // full retreat past the band, then cross → fires again
        assert!(fire_all(&mut set, 197_9999).is_empty());
        assert_eq!(fire_all(&mut set, 200_0000).len(), 1);
    }

    #[test]
    fn cross_down_mirrors_cross_up() {
        let mut set = WatchSet::default();
        set.set_levels(
            &[WatchLevel {
                id: 4,
                kind: LevelKind::CrossDown {
                    price: 100_0000,
                    rearm_bp: 0,
                },
            }],
            4,
        )
        .unwrap();
        assert!(fire_all(&mut set, 99_0000).is_empty()); // first obs below: no fire
        assert!(fire_all(&mut set, 101_0000).is_empty());
        let f = fire_all(&mut set, 99_9999);
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].tag, TriggerTag::CrossDown);
    }

    #[test]
    fn near_band_fires_and_rearms_on_leave() {
        // 50 bp of 400.0000 = 2.0000 band
        let mut set = WatchSet::default();
        set.set_levels(
            &[WatchLevel {
                id: 5,
                kind: LevelKind::Near {
                    price: 400_0000,
                    within_bp: 50,
                },
            }],
            4,
        )
        .unwrap();
        assert!(fire_all(&mut set, 405_0000).is_empty());
        let f = fire_all(&mut set, 402_0000); // exactly at band edge
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].tag, TriggerTag::Near);
        assert!(fire_all(&mut set, 401_0000).is_empty()); // still in band
        assert!(fire_all(&mut set, 402_0001).is_empty()); // leaves → re-arms
        assert_eq!(fire_all(&mut set, 398_5000).len(), 1); // approach from below
    }

    #[test]
    fn volume_burst_fires_once_per_bucket_and_rearms_on_new_bucket() {
        let mut set = WatchSet::default();
        set.set_levels(
            &[WatchLevel {
                id: 6,
                kind: LevelKind::VolumeBurst {
                    tf_idx: 0,
                    baseline: 1_000,
                    mult_bp: 30_000, // 3×
                },
            }],
            1,
        )
        .unwrap();
        let mut fired = Vec::new();
        // below threshold (2999 < 3000)
        set.on_price(100_0000, |_| Some((0, 2_999)), |f| fired.push(f));
        assert!(fired.is_empty());
        // at threshold → fires
        set.on_price(100_0000, |_| Some((0, 3_000)), |f| fired.push(f));
        assert_eq!(fired.len(), 1);
        assert_eq!(fired[0].tag, TriggerTag::VolumeBurst);
        // same bucket keeps swelling → silent
        set.on_price(100_0000, |_| Some((0, 9_000)), |f| fired.push(f));
        assert_eq!(fired.len(), 1);
        // new bucket below threshold → re-armed, silent
        set.on_price(100_0000, |_| Some((60, 100)), |f| fired.push(f));
        assert_eq!(fired.len(), 1);
        // new bucket bursts → fires again
        set.on_price(100_0000, |_| Some((60, 3_000)), |f| fired.push(f));
        assert_eq!(fired.len(), 2);
        // bucket that ALREADY exceeds threshold on first sight fires even
        // if the previous bucket fired (bucket-to-bucket transition)
        set.on_price(100_0000, |_| Some((120, 5_000)), |f| fired.push(f));
        assert_eq!(fired.len(), 3);
    }

    #[test]
    fn set_levels_preserves_armed_state_for_unchanged_ids() {
        let mut set = WatchSet::default();
        set.set_levels(&[zone(1, 100_0000, 101_0000)], 4).unwrap();
        assert_eq!(fire_all(&mut set, 100_5000).len(), 1); // fired, now inside
                                                           // refresh with the SAME level + one new level → no re-fire
        set.set_levels(
            &[zone(1, 100_0000, 101_0000), zone(2, 200_0000, 201_0000)],
            4,
        )
        .unwrap();
        assert!(
            fire_all(&mut set, 100_5000).is_empty(),
            "refresh must not re-fire a zone the price is sitting in"
        );
        // but a CHANGED zone under the same id resets state
        set.set_levels(&[zone(1, 100_0000, 102_0000)], 4).unwrap();
        assert_eq!(fire_all(&mut set, 100_5000).len(), 1);
    }

    #[test]
    fn set_levels_validation_is_all_or_nothing() {
        let mut set = WatchSet::default();
        set.set_levels(&[zone(1, 100_0000, 101_0000)], 4).unwrap();
        let err = set
            .set_levels(&[zone(1, 100_0000, 101_0000), zone(1, 5_0000, 6_0000)], 4)
            .unwrap_err();
        assert_eq!(err, TriggerError::DuplicateId { id: 1 });
        // original set intact and still armed-preserving
        assert_eq!(fire_all(&mut set, 100_5000).len(), 1);
    }

    #[test]
    fn validation_rejects_bad_shapes() {
        let mut set = WatchSet::default();
        assert_eq!(
            set.set_levels(&[zone(1, 101_0000, 100_0000)], 4)
                .unwrap_err(),
            TriggerError::BadZone {
                id: 1,
                low: 101_0000,
                high: 100_0000
            }
        );
        assert_eq!(
            set.set_levels(
                &[WatchLevel {
                    id: 2,
                    kind: LevelKind::Near {
                        price: 100_0000,
                        within_bp: 0
                    }
                }],
                4
            )
            .unwrap_err(),
            TriggerError::BadLevel { id: 2 }
        );
        assert_eq!(
            set.set_levels(
                &[WatchLevel {
                    id: 3,
                    kind: LevelKind::VolumeBurst {
                        tf_idx: 4,
                        baseline: 10_000,
                        mult_bp: 10_000
                    }
                }],
                4
            )
            .unwrap_err(),
            TriggerError::BadTfIdx {
                id: 3,
                tf_idx: 4,
                tf_count: 4
            }
        );
        // baseline·mult_bp below one whole unit truncates the threshold
        // to 0 — a permanently-silent watch must be refused, not armed
        assert_eq!(
            set.set_levels(
                &[WatchLevel {
                    id: 4,
                    kind: LevelKind::VolumeBurst {
                        tf_idx: 0,
                        baseline: 9,
                        mult_bp: 999
                    }
                }],
                4
            )
            .unwrap_err(),
            TriggerError::BadLevel { id: 4 }
        );
        // a >= 100% re-arm band needs a retreat past zero — refused
        assert_eq!(
            set.set_levels(
                &[WatchLevel {
                    id: 5,
                    kind: LevelKind::CrossUp {
                        price: 100_0000,
                        rearm_bp: 10_000
                    }
                }],
                4
            )
            .unwrap_err(),
            TriggerError::BadLevel { id: 5 }
        );
    }
}
