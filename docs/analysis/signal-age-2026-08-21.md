# Signal age at entry — 2026-08-21

_Read-only. For every resolved paper trade since 2026-07-19 (78 trades), how far into the signal's validity window we ENTERED. A positional signal stays `active` for 30 trading days and keeps surfacing the whole time, so a stale signal is one click away and looks as fresh in the list as a new one — this quantifies whether we are entering late and what it costs. `%elapsed = (entry − commit) / (validity − commit)`; 100% = at expiry._

**Median entry: 23% of validity elapsed (2 calendar days after the signal was generated).**

| entry timing (% of validity elapsed) | trades | net ₹ | avg ₹ | win% |
|---|--:|--:|--:|--:|
| 0–20% (fresh) | 32 | ₹474 | ₹15 | 59% |
| 20–40% | 15 | ₹7,182 | ₹479 | 67% |
| 40–60% | 9 | ₹-4,058 | ₹-451 | 44% |
| 60–80% | 10 | ₹-4,390 | ₹-439 | 40% |
| 80–100% (stale) | 12 | ₹-2,610 | ₹-217 | 42% |
| > 100% (after expiry) | 0 | — | — | — |

**Headline: STALE ENTRIES ARE WORSE.** Fresh (≤40% elapsed): 47 trades, avg ₹163, win 62%. Stale (>80%): 12 trades, avg ₹-217, win 42%.

_Why late entries happen: a committed signal is `active` (and shown) until its validity lapses, and the dedup overlay keeps the OLDEST source of a (stock, direction) — so a long-lived positional signal re-surfaces for weeks. The AlertBell / Live-Signals `best by <date>` + `⚠ stale` flags mark the decayed ones at the point of decision._

## Per-trade (most-elapsed first)

| traded | stock | class | signal age | %elapsed | outcome |
|---|---|---|--:|--:|--:|
| 2026-07-30 | LENSKART | swing | 6d | 99% | ₹-683 |
| 2026-07-30 | COLPAL | swing | 6d | 99% | ₹-672 |
| 2026-07-30 | HINDCOPPER | swing | 6d | 98% | ₹-686 |
| 2026-07-30 | FOSECOIND | swing | 6d | 94% | ₹-559 |
| 2026-08-14 | INDIACEM | positional | 38d | 91% | ₹-819 |
| 2026-08-14 | ORIENTCER | positional | 38d | 91% | ₹2,875 |
| 2026-08-10 | WINDLAS | swing | 6d | 86% | ₹1,933 |
| 2026-08-10 | JSWDULUX | swing | 6d | 86% | ₹1,780 |
| 2026-07-29 | TATASTEEL | swing | 5d | 84% | ₹-1,819 |
| 2026-07-29 | BIKAJI | swing | 5d | 84% | ₹16 |
| 2026-07-29 | LENSKART | swing | 5d | 84% | ₹1,021 |
| 2026-07-29 | SANOFI | swing | 5d | 84% | ₹-4,996 |
| 2026-08-06 | JBMA | swing | 5d | 80% | ₹1,506 |
| 2026-08-03 | DHAMPURSUG | swing | 5d | 80% | ₹-2,521 |
| 2026-08-06 | NATCOPHARM | swing | 5d | 80% | ₹-2,583 |
| 2026-07-28 | KOTHARIPRO | swing | 4d | 71% | ₹515 |
| 2026-07-28 | PCBL | swing | 4d | 71% | ₹-2,737 |
| 2026-07-28 | JSWDULUX | swing | 4d | 67% | ₹-255 |
| 2026-08-18 | SRTL | swing | 4d | 66% | ₹-3,565 |
| 2026-08-05 | DECNGOLD | swing | 4d | 65% | ₹-264 |
| 2026-08-10 | SHALBY | swing | 4d | 64% | ₹2,702 |
| 2026-08-10 | EASEMYTRIP | swing | 4d | 63% | ₹2,812 |
| 2026-07-27 | LENSKART | swing | 3d | 56% | ₹2,712 |
| 2026-07-27 | FORTIS | swing | 3d | 56% | ₹525 |
| 2026-07-27 | ABREL | swing | 3d | 56% | ₹-362 |
| 2026-08-18 | KSL | swing | 3d | 51% | ₹-2,278 |
| 2026-08-18 | PREMIERENE | swing | 3d | 51% | ₹-2,257 |
| 2026-08-14 | GLOBAL | swing | 3d | 51% | ₹-2,131 |
| 2026-07-28 | ORIENTCER | positional | 21d | 51% | ₹156 |
| 2026-07-27 | INDIGOPNTS | positional | 20d | 49% | ₹1,134 |
| 2026-08-12 | SANATHAN | positional | 19d | 47% | ₹-1,557 |
| 2026-08-13 | KFINTECH | swing | 2d | 37% | ₹-1,705 |
| 2026-08-03 | GEOJITFSL | swing | 2d | 37% | ₹1,117 |
| 2026-08-14 | ANURAS | swing | 2d | 37% | ₹416 |
| 2026-08-03 | RKDL | swing | 2d | 37% | ₹-1,880 |
| 2026-08-03 | STEELXIND | swing | 2d | 37% | ₹1,870 |
| 2026-08-03 | HAL | swing | 2d | 37% | ₹3,729 |
| 2026-08-06 | SREEL | swing | 2d | 29% | ₹2,576 |
| 2026-08-13 | SPARC | swing | 1d | 23% | ₹-4,022 |
| 2026-08-10 | DMCC | positional | 9d | 23% | ₹1,205 |
| 2026-08-12 | MANAKSIA | swing | 1d | 23% | ₹367 |
| 2026-07-31 | FMGOETZE | swing | 1d | 23% | ₹207 |
| 2026-08-07 | FRONTSP | swing | 1d | 21% | ₹1,441 |
| 2026-08-07 | AIROLAM | swing | 1d | 21% | ₹-305 |
| 2026-08-07 | ONGC | swing | 1d | 21% | ₹-30 |
| 2026-08-07 | LUPIN | swing | 1d | 21% | ₹2,198 |
| 2026-08-12 | TNPL | positional | 8d | 19% | ₹-3,037 |
| 2026-07-30 | JKPAPER | positional | 6d | 16% | ₹90 |
| 2026-07-31 | PNCINFRA | positional | 6d | 16% | ₹1,029 |
| 2026-08-05 | MSUMI | swing | 1d | 15% | ₹-1,080 |

_… 28 more not shown._

