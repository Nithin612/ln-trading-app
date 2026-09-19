# Tier B plan · and exactly what is needed from the user (2026-09-19)

Written overnight while Tier A's last two unblocked rows were built. Two parts: **what I
need from you** (items 21, 13 and 12's unfinished half), and **the Tier B plan**.

⛔ **First, the correction that prompted this.** Tier A has **ten** rows, not five. A
previous session wrote *"TIER A IS BUILT — five items"* into `PHASES.md`, which redefined
the term to mean whatever had been finished, and a later session read that sentence back as
verification. State as of this document: **7 of 10 built, 1 half (item 12's sign), 2 blocked on the user (5 and 13).** Everything not needing you is done.

| # | Item | State |
|---|---|---|
| 4 | entry-bar gap delete treatment | ✅ built |
| 2 | ledger wiring + backend lint | ✅ built · 4 real production rows in dev |
| 3 | idempotent re-seed + census ratchet | ✅ built · run · 10 profiles present |
| 14 | `liquid_as_of` PIT cohort | ✅ built |
| 15 | bhavcopy A10 guard | ✅ built |
| 11 / 11b | **the two holdout seals** | ✅ **built 2026-09-19** |
| 6 | **re-run D5 + D1 + B7** | ✅ **DONE 2026-09-19** — all three re-run; every headline survives. Biggest finding: the published cohorts are **not reproducible** (`is_active` moved 1,322 → 2,292 under them) |
| 12 | push **and sign** | ⚠ **half** — pushed; `fe5d508` still returns `N` |
| 5 | re-run E2 | ⛔ needs item 21 |
| 13 | Celery beats off `day_of_week="1-5"` | ⛔ your call |

---

## PART 1 — What I need from you

### Item 21 — one real contract note ⛔ **CORRECTED: it is NOT a blocker**

⛔⛔ **I called this "the only thing between here and item 5". Measured 2026-09-19, that is
WRONG.** `e2_score_ic.py` does not read `fees.py` at all — it **hardcodes 25.5 bps**. So a
contract note can only reach item 5 through that single number, and the arithmetic settles it:

| | bps |
|---|--:|
| modelled delivery round trip (₹1L) | 23.76 |
| — of which **STT alone**, statutory | **20.00** (84%) |
| **statutory floor** (DP charge zeroed entirely) | **22.22** |
| needed to flip E2's verdict (upper bound 0.0119 vs break-even 0.0310) | **9.79** |

The only non-statutory line in the whole stack is the ₹15.34 DP charge. **Zero it completely
— the most extreme error a contract note could possibly correct — and costs are still 22.22
bps, which is 2.27× the 9.79 bps needed to change the answer.** ⇒ **item 5 is unblocked.**

⚠ Still worth sending eventually: `fees.py` has never been checked against reality (M74 — M27
regressed it against its own output), and it prices every P&L number in the system, not just
E2's break-even. That is correctness hygiene, not a gate. ⭐ Also noted: the script's hardcoded
25.5 bps is 7% ABOVE the modelled 23.76 — conservative, which is the safe direction. M74: `fees.py` has never been reconciled against a real note — M27
regressed it **against its own output**, which tests arithmetic and not correctness.

**What to send:** one Zerodha contract note (the PDF, or the trade-wise charge breakdown
from Console). Ideally two — one **delivery/CNC** trade and one **intraday/MIS** — but one
delivery note unblocks item 5 on its own, since that is the product you are trading.

**What I actually read from it:** trade value, quantity, buy/sell legs, and the itemised
charge lines — brokerage · STT · exchange transaction charge · SEBI turnover fee · GST ·
stamp duty · **DP charge**. That last one is the one most likely to be wrong in our model:
`fees.py` carries `₹15.34` flat per delivery sell, taken from a published schedule rather
than a note we have seen.

⚠ **Redact your client ID and PAN.** I need the numbers and the legs, nothing that
identifies the account. It stays local — never leaves this machine (project rule).

### Item 13 — a yes/no on weekend beats

⛔⛔ **CORRECTED 2026-09-19 — my earlier split recommendation was a trap, and the fact base
was wrong too.**

**There are 8 weekend sessions in the archive, not 4** (the docs still say 4): 2019-10-27
**Sun**, 2020-02-01, 2020-11-14, 2024-01-20, 2024-03-02, 2024-05-18, 2025-02-01, 2026-02-01
**Sun**. That is 0.46% of 1,728 sessions, ≈1.1/year.

⛔ **Flipping the 22 beats would change NOTHING.** `market_hours.is_market_session` returns
False on any weekend independently (`if now_ist.weekday() > 4: return False`), and
`position_monitor` — the only thing in the system that closes a position on a stop — checks
it. You would ship the change, believe weekend monitoring worked, and still be unguarded.
**A fix that looks done and isn't is worse than no fix.**

⛔ **And the real fix is not a scheduling change.** The weekday assumption sits in **seven**
places, the worst being inside **`is_trading_day` itself** — the function whose entire job is
answering that question returns False for a weekend *before* it consults the holiday table.
`nse_holidays` is a table of days NOT traded; there is no table of days traded, so the
calendar **structurally cannot express "this Saturday is a session"**.

**My recommendation, split by risk rather than all-or-nothing:**

| beats | change to | why |
|---|---|---|
| `ingest-equities-eod` · `fo-eod-ingestion` · `ingest-fii-dii` · `apply-corporate-actions` | `"*"` | idempotent and self-healing; on a non-session day the source 404s and they exit. This is the half that loses data permanently. |
| `check-feed-coverage` · `check-calendar-coverage` · `check-universe-health` · `check-report-health` · `check-starved-tables` | `"*"` | a detector that sleeps through the event it detects is not a detector |
| `nightly-signal-generation` · `mint-pair-signals` · `nightly-profile-suggestions` · the two intraday ones | **leave at `1-5`** | these MINT things. Weekend signals on a session nobody expects is a behaviour change, not a repair |
| `monitor-positions` · `capture-cas-window` · `record-option-chains` · `refresh-circuit-bands` · `sweep-expired-signals` | **leave at `1-5`** | live-session machinery; a weekend session is rare enough that I would rather you opt in deliberately |

**RECOMMENDATION: do not do item 13 now. Defer it to Phase 7.**

The exposure today is **zero real money**. Data is already safe — the backfill enumerator
offers every calendar day and lets the archive's 404 decide, which is exactly how all 8 of
those sessions were found. The only remaining gap is live position monitoring on an
announced session roughly once a year — and **you are paper trading**, so an unwatched paper
stop costs nothing. It becomes real the day live trading starts, which is precisely when the
session-calendar work belongs (it gates the SL monitor, so it is money-path and deserves the
care Phase 7 gives it).

**Until then, handle it by hand:** weekend sessions are announced weeks ahead. Either avoid
carrying positions over one, or run the monitor manually that day.

**What I need from you: nothing.** This is a recommendation to defer, not a question.

### Item 12 — the sign half (≈ 2 minutes, and it reuses the key you already made)

The row was never "push", it was **push and sign**. The push is done. `git log
--format='%G?' fe5d508` still returns **N**, and the branch carries **zero** signed commits,
so the E2 pre-registration remains *operator-attested* rather than provable — which was
M72's entire point.

SSH signing reuses the key we set up for pushing:

```
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

then on GitHub add that same public key a second time, with key type **Signing Key**
(it is a separate entry from the authentication key).

⚠ **This cannot retroactively sign `fe5d508`.** Rewriting history to sign it would defeat
the purpose — a pre-registration you can re-date is not a pre-registration. What signing
buys is that **the item-5 run, and everything after it, is attestable**. That is also why
the queue moved item 12 above item 5.

---

## PART 2 — The Tier B plan

Tier B is *"measured, but each came from one source"* — your own entry rule admits them
(**converged across sources OR settled by our own measurement — never consensus alone**),
and each has a measurement behind it. Ordered by **value ÷ cost**, not by number.

### Tranche 1 — correctness, hours not days, nothing to decide

| # | Item | Measurement behind it | Why first |
|---|---|---|---|
| **27** | `StockDetailPage` paints the LTP `--color-bull` regardless of direction | code fact; had **no queue row** until §13.8 | **A falling price renders green.** Money-correctness on the surface you look at most, frontend-only, and the smallest change in the whole queue |
| **28** | the FII/DII consumer states "flows neutral" from zero rows | `fii_dii_daily` ≈ 4–10 rows | a *positive claim from absent data* — the same class as the feed alarm reading ✅ through the outage. "Not assessable" is the correct rendering |
| **23** | the three standing concessions, enumerated | **M78: 0 / 0 / 0** across all four queue sections | pure documentation, but they are currently invisible: portfolio-level evaluation · `entry_diversity`'s incremental effect · live-vs-modelled fill calibration |

### Tranche 2 — instruments that make later work attributable

| # | Item | Measurement | Note |
|---|---|---|---|
| **22** | version the gate configuration | **M80**: no table matching `%config%`/`%setting%`/`%gate%` exists | a past signal **cannot currently be attributed to the config that produced it**. Every future flip is unattributable until this exists — and we have already reverted two flips |
| **24** | position-count cap, conditionally worded | **M77**: friction crosses 30 bps between 5 and 6 positions; the built cap of 3 sits at 26.88 bps | the cap is already BUILT and `off`. This is a wording fix so it does not read as a universal law — it is conditional on ₹1 lakh and the current modelled costs |
| **20** | tax in the cost model | **M73**: absent everywhere | ⚠ **significance corrected in round 11: it raises every TARGET, not the break-even** (tax is levied on profit, so it is zero at break-even). Parameterise by product and holding period; do **not** add a flat bps |

### Tranche 3 — data, and the one real dependency

| # | Item | Measurement | Note |
|---|---|---|---|
| **18** | index/VIX for 2021–22 | **M2**: 792 sessions ≈ 3.2 years, not 7 | integrity ingest, whitelist-class. Without it every market-regime and sector-RS overlay is unevaluable across the **holdout-1 era**, which is exactly the block we just sealed |
| **16** | CA policy via the external NSE source | **M66** `PREV_CLOSE` is the same unadjusted series (8/8) · **M70** the 25% screen fires on 0.068% and leaves 76.24% untouched; 3 of 8 flagged events are real CAs | ⭐ **no longer blocks item 5** — the three named CAs are excluded by dated list. So this is quality, not a gate. Build it as a **cache of the authority's answers, never a rule you evaluate** |
| **21** | reconcile `fees.py` to a real note | **M74** | ⛔ in Tier B only by origin; it is **Tier A's blocker**. See Part 1 |

### What I would NOT do next, and why

- **Do not start anything that needs a new measurement to justify it.** Both named
  profitability levers are spent (D5 exit geometry, D1 generation/RVOL, both refuted
  2026-09-08). Finding a new lever is an open research problem, not a queue item, and
  dressing one up as a build is how the last three months went.
- **Do not promote any gate.** Gating is closed as a programme; the bar is t ≈ 3.6 and the
  best surviving candidate sat at 0.41.
- **Item 5 is the only thing that changes direction**, and it is one contract note away.

---

## Suggested order

**You, and only one of these is urgent:**

1. ⭐ **Item 12 — sign, 2 minutes. Do this FIRST and before item 5 runs.** It is the only one
   of the three that is time-sensitive: once item 5 runs unsigned, that run is permanently
   operator-attested and signing afterwards cannot fix it. The queue's own H27 ruling puts
   item 12 above item 5 for exactly this reason.
2. **Item 21 — send when convenient.** Measured NOT to be a blocker (above). Worth having for
   `fees.py` correctness, which prices every P&L number in the system.
3. **Item 13 — nothing to decide. Recommended: defer to Phase 7.**

**Me, needing nothing:** item **5** (now unblocked — waits only on your signature, not on the
contract note), then Tier B 27 → 28 → 23 → 22 → 24 → 20 → 18 → 16.
