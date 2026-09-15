# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Review round on §73 + §77 — nine findings, one HIGH, one of them mine (2026-09-15)

bug-hunter on `ef812eb` + `8318527`. The two that mattered were both instruments reporting
health they had not actually measured.

- ⛔⛔ **HIGH — `universe_health` measured the EVALUATION and never the APPLY, so it was
  silent in the dangerous direction.** `materialise()` commits the snapshot; `apply_to_stocks`
  may then REFUSE it (collapse rail or subscription ceiling), log an error and return
  `applied: False`. Recency alone reads that as perfect: the snapshot IS today's, so the
  report rendered **"✅ Universe current"** while `is_active` stayed frozen for as many days
  as the rail kept firing — and every consumer reads `is_active`, not the snapshot. Fixed with
  `apply_diverged` (decided members vs active count) folded into `is_alarming`, plus a
  **separate message**: "the beat stopped" sends you to the scheduler, "the verdict was
  refused" sends you to the rail and its threshold. The refusal now also **pushes from the
  task itself**, since it runs unattended and a log line nobody tails was the whole alarm.
- ⛔ **The input snapshot missed its own motivating case.** `record_inputs` ran AFTER
  `load_inputs`, which parses — and `parse_eq_listed` RAISES on an unrecognised header. So on
  the `EQ=0` header bug, the exact failure the artifact exists for, the task died before
  recording anything. Split into `record_source` (bytes, BEFORE the parse) and `record_parsed`
  (sets, after), with `eq_listed`/`kite_tradable` nullable (migration `f9e8d7c6b5a4`) so
  **"source captured, parse rejected" is representable** — the most informative row the table
  can hold. A replayed row with NULL sets reads as ABSENT, never as an empty universe.
- ⚠ **"The bytes as served" was true by luck, not construction.** `download_equity_l` returned
  `resp.text`; httpx decodes with `errors="replace"` and NSE declares no charset, so one
  Latin-1 byte would have become U+FFFD, unrecoverable, and `csv_sha256` would have stopped
  matching a `sha256sum` of an independent copy. Now returns `resp.content`; decoding happens
  at the parse boundary only. (Measured: the live file is 182,540 B, zero non-ASCII — so the
  two agreed today.) Pinned by a test with a real Latin-1 byte.
- ⚠ `universe_health`'s SQL correlated `max(as_of)` with `max(captured_at)` — **different
  rows** once a replay back-fills an older day — and asked "are the maxima equal" instead of
  "is there an inputs row FOR this snapshot", which false-alarmed on the normal sequence
  (source committed before the snapshot is written). Both fixed in the query.
- ⛔ **A claim of mine was wrong and is corrected in place (W1).** The conftest comment said
  migration-only tables leaked "16 of 56, including `corporate_filings`, `manual_assets`,
  `mf_holdings`, `mf_import_batches`" — measured against the DEV database and a partial import
  set. Re-measured against the TEST database: **47 tables, 45 modelled, 2 unmanaged**, and
  `universe_snapshot` was already cleared by CASCADE from `stocks`. **The only table that was
  actually leaking is `universe_rule_inputs`.** The mechanism still stands; the number did not.
- The cleanup now shares the existing connection instead of opening a second one on a NullPool
  engine — ~40 ms × 2,308 test functions ≈ **90 s off a full run** — which also removes the
  FK-ordering and id-drift hazards of a bare per-table loop.
- `ca_detector` now passes its own `now` into `record_flag`: the column's `server_default
  now()` is `transaction_timestamp()`, and `eod_catchup` scans up to 21 sessions in ONE
  transaction, so an event could be stamped minutes before the flag it records — in a log
  whose entire semantic is ordering.
- ⚠ **Left open, latent:** `actor_user_id` is `ON DELETE SET NULL` and NULL already means "a
  machine flagged this", so deleting a reviewing admin would make their clear look like a
  machine event. No user-delete path exists today.
- 20 new tests across the three suites; 100 green; ruff/mypy clean.

### §77 P1 batch — the universe's absences get instruments, and the CA quarantine gets a way out (2026-09-15)

Queue item 3. Four sub-items, and two of them changed what we believed.

- ⭐⭐ **"Does an Alembic migration bypass the `stocks.is_active` single-writer trigger?" —
  ANSWERED, and it is not the binary the question assumed.** Measured with a new re-runnable
  probe (`scripts/universe_writer_probe.py`): a plain `UPDATE` — what a naive migration does —
  is **REFUSED**, so the guard does cover migrations and §49's invariant is stronger than the
  "single-writer among application code" §76 settled for. ⛔ **But the probe found a bypass the
  question did not ask about:** the trigger was created `ENABLE`d (`tgenabled = 'O'`, origin
  only), so `SET LOCAL session_replication_role = 'replica'` disabled it wholesale — and the
  connecting role is a superuser. Migration `b0c1d2e3f4a5` sets `ENABLE ALWAYS`; re-running the
  probe confirms route 3 flips REFUSED and `tgenabled` `O` → `A`, with the legitimate writer
  still working. ⚠ Safe for `make backup-verify`'s real restore: the trigger is `BEFORE UPDATE`
  and a restore INSERTs.
- ⭐ **New `universe_health` instrument** — `max(as_of)` recency on `universe_snapshot` AND
  whether that evaluation's inputs were captured, in ONE surface because they are two facts
  about one nightly job. Rendered in the daily report; pushed by a **04:10 UTC beat**. The
  failure it catches has **no symptom of its own**: `materialise_universe` is the only writer of
  `is_active`, which gates ingestion breadth, the scan universe and the live subscription, so a
  beat that silently stopped leaves everything running on a decision nobody re-took. ⚠ Alarms at
  **2** trading days, not 1 — one day behind is the normal state for most of a trading day, and
  alarming on it would train the reader to ignore the channel. ⚠ `expected_latest_trading_day`
  gained a `due` parameter because the universe beat lands 08:35 IST, not the EOD feeds' 18:45;
  inheriting that cutoff would have declared the universe stale every morning.
- ⭐⭐ **The CA quarantine has a clearing path (Q-R3).** `stocks.ca_flagged_at` had one writer and
  **no clearer anywhere**, while `ca_detector`'s own docstring promised "unflag via admin after
  verifying". Measured 2026-09-14: **7 flagged, 5 active, 4 of the 7 flagged that same day** — a
  monotonic accumulator shrinking the tradeable universe by ~4 names a week, whose only symptom
  would have been suggestions quietly covering fewer stocks. Now
  `GET/POST /corporate-actions/quarantine…` (admin) with a **required, non-trivial reason**.
  ⛔ **An EXPIRY was considered and REJECTED:** the contamination is in the unadjusted price
  history and does not heal with time, so a timer would re-admit contaminated bars on a schedule.
  ⭐ **A LOG, not three columns on `stocks`** (`ca_flag_events`, append-only, migration
  `c1d2e3f4a5b6`, backfilled with the 7 existing flags): the detector re-flags a cleared name, so
  a single `ca_cleared_at/_by/_reason` triple would be overwritten by the next flag — §41's
  "the merge overwrites its own evidence" trap. A machine may quarantine; only a person may
  release, and the log keeps both sides.
- ⛔ **A HARNESS DEFECT FOUND WHILE DOING THIS, affecting the whole suite:** `conftest.clean_tables`
  walked `Base.metadata`, so every table created by a migration without an ORM model was **never
  cleared between tests** — measured **16 of 56**, including `universe_snapshot`,
  `corporate_filings`, `manual_assets`, `mf_holdings` and `mf_import_batches`. State leaked from
  one test into the next; the failure mode is a test that passes alone and fails in a suite, or
  passes in a suite for the wrong reason. The list is now DERIVED FROM THE DATABASE, so a future
  migration is covered the day it lands.
- 36 new tests (11 quarantine + 11 universe health + the rest); 161 green across the affected
  suites; ruff/mypy clean. Migrations applied to dev and test; reversibility verified by a real
  `downgrade -1` + re-`upgrade`.

### §73 — the universe rule's INPUTS are recorded, not just its verdict (2026-09-14)

Queue item 2. ⭐ **Contents, not a fingerprint.** The plan originally priced this as "one CSV +
one instruments hash per day"; a hash gives you `H(input)` while every consumer needs `input` —
and **`kite_instruments` is UPSERTED IN PLACE** ("57595 rows upserted, 0 stale swept"), so
yesterday's instrument state is already gone by the time anyone asks.

- **New table `universe_rule_inputs`** (migration `a9b0c1d2e3f4`, reversible — `downgrade -1`
  and re-`upgrade` both verified): `as_of` PK · `captured_at` · `source_url` · `csv_gz` (the raw
  bytes, gzipped, ~60 KB/day) · `csv_sha256` · `eq_listed` · `kite_tradable` · `rule_version`.
  Idempotent per day — a re-run REPLACES that date, the contract `materialise()` already keeps.
- ⭐⭐ **Recorded BEFORE the decision, which is the whole point.** `apply_to_stocks` refuses a
  snapshot below `universe_apply_min_fraction`, but the rail fires on a property of the **INPUT**
  while `universe_snapshot` records the rule's **OUTPUT**. A refusal could be seen and never
  explained, so 0.5 — picked by judgement — could never be tuned. A refusal is also exactly the
  path where the later steps do not run, so recording afterwards would miss the only firing
  anyone needs. ⭐ This also **corrects a stale comment** in `market_data_tasks.py` that claimed
  the snapshot alone made a refusal "inspectable" (W1).
- **Replay readers:** `load_recorded_inputs` (re-evaluate the rule against a past day's inputs —
  what makes "rule v2 behaves better than v1" falsifiable) and `load_recorded_csv` (re-parse the
  bytes as served — the half that separates a **source** change from a **parser** change, which
  is exactly what the `EQ=0` header bug would have needed).
- `_download_equity_l` became public `download_equity_l` so the caller owns the bytes;
  `load_inputs`'s signature is unchanged, leaving its 7 call sites untouched (W2).
- ⚠ `rule_version` is `String(16)`, matching `universe_snapshot` — `RULE_VERSION` is `"v1"`, not
  a number. Caught by the tests on first run.
- Migration applied to **dev** as well as test, so the 08:35 IST beat does not meet a missing
  table. ⚠ The running celery worker must be restarted to pick up this code AND U4′'s new beat
  entry. 7 new tests; 92 green across the universe suites; ruff/mypy clean.

### U4′ — the feed alarm learns to assert COVERAGE, not just recency (2026-09-14)

The 6.8.6 alarm asserts **recency** (`max(time)` vs the trading calendar) and read ✅ straight
through the 2026-09-07 outage, which froze daily bars for 1,278 names — every blue chip among
them — across five sessions. Recency is not health. Queue item 1 of the post-round-5 build.

- ⭐ **`feed_health.py` now answers two independent questions.** COVERAGE = distinct names on a
  feed's latest session vs the median over the trailing **30** sessions, alarming below
  `feed_coverage_min_fraction` (**0.90**). A feed can be current-and-thin, stale-and-broad, or
  both; each verdict is reported separately.
- ⛔⛔ **Counted RAW, never scoped to `stocks.is_active` — the single decision it turns on.**
  Scoping it makes the numerator and its own baseline share one mutable set: during the outage
  that set WAS what collapsed, so 1,322 active names against a median of 1,322 reads **100%
  healthy**. That is why `funnel.py`'s breadth stage cannot serve as this detector, and the
  acceptance test pins **both** silences on one fixture before asserting the new alarm fires.
  test-guardian confirmed by mutation that all three assertions are load-bearing.
- ⭐ **Threshold measured, then CORRECTED.** Worst BENIGN shortfall vs the trailing median:
  **2.21%** over the last 239 sessions · **3.21%** over the 791 post-gap · **8.17%** over all
  1,098 (2020-07-03, pre-gap ingestion era), against a ~50% failure. **0 firings across all
  1,098.** My first write-up quoted only the 239-session slice and claimed ~4.5× headroom; the
  honest worst-case margin is **~1.2×**. All three windows are recorded, and a test fails if a
  retune drops the threshold below the recorded floor.
- ⚠ **30 sessions, not the 5 the spec asked for.** A median is overtaken once half its window is
  collapsed, so a 5-session reference goes silent on the **4th session** of a persistent outage —
  it switches itself off inside the failure. One test runs the same fixture through both windows
  to opposite verdicts, so the choice is demonstrated rather than asserted.
- ⭐ **A daily beat at 13:40 UTC** (after both EOD ingests, before nightly generation) pushes
  through the A11 notifier. Before it, the check's only caller was `build_daily_report` — i.e.
  `make analysis`, run by hand — so a collapse on a day nobody ran the report was never seen.
  **A detector that waits to be asked is not a detector.**
- ⭐ **A health probe must not raise into its own report** (the rule `calendar_health` states):
  the probe now runs per-feed inside a `begin_nested` savepoint and degrades to "not assessable",
  never to green. Found by test-guardian as a CODE defect, not a test gap.
- ⛔ **And that guard immediately masked a real bug** — the first beat test returned `status: ok`
  with no numbers because the guard swallowed an `Event loop is closed` error. Caught ONLY
  because the test asserts measured VALUES rather than "did not raise". **A fail-open probe hides
  its own bugs.**
- ⚠ **KNOWN LIMIT, queued as U4″:** it is an UNWEIGHTED count, so the 10% floor is ~264 of ~2,637
  names. The 50 active Nifty-50 constituents are **1.90%** and all 210 active F&O underlyings
  **7.96%** — an ingestion bug that drops every blue chip fires nothing, and the funnel cannot
  see it either.
- Also fixed from review: healthy feeds vanishing from the header whenever any feed alarmed; a
  future-dated row silencing the alarm; `-0.0%` on an exactly-normal feed; copy claiming "today's
  session" when the check reads no clock; an off-by-one in the module's own justification.
- New knob `FEED_COVERAGE_MIN_FRACTION=0.90` (`.env.example`, W3). 25 new tests in
  `test_feed_coverage.py` + 2 beat-ordering invariants; ruff/mypy clean.

### Round-5 adjudication — both blocking questions answered against my own leaning (2026-09-14)

Six responses. ⭐ **Both were settled by a query, not by the argument**, and two items shipped.

- ⭐⭐⭐ **Q1: ship FIVE rungs, and the fifth is COMPUTABLE — which nobody predicted.** My framing
  ("a reader may assume the fifth stage is zero") was the weaker half: the real failure is that
  they assume **the fourth is complete**, so the whole drop from priced → signals is forced onto
  the confluence gate because it is the only mechanism left to explain it. ⭐ **The deciding
  query was named by a reviewer and its prediction confirmed:** `signal_service.py:217` refuses
  any name with `< 50` daily candles BEFORE scoring. **Measured: 184 of 2,286 priced names (8%)
  were being attributed to the gate having never been looked at.** ⭐⭐ And Q-R2's *"assessed
  does not exist as a counter"* was about the wrong quantity — the SCORER persists no panel
  count, but **ADMISSION is a property of the data** and is one `HAVING count(*) >= …` away. So
  the rung ships as a real number, not a placeholder. `MIN_CANDLES_TO_SCORE` extracted (it was a
  bare literal with no owner) and read by `funnel.py`, asserted **by identity** not by value (W5).
  Live: **3,395 → 2,291 → 2,286 → 2,102 → 0**. ⚠ `assessed_available` stays false and now means
  something narrower — the residual is part gate, part unknown, and the copy says so.
- ⭐⭐⭐ **Q2: YES, snapshot the inputs — and my own stated cost was wrong, unanimously.** Five of
  six sources independently said **a hash cannot serve the purpose**; my "one CSV + one
  instruments hash per day" would have had a future session build an artifact that cannot do its
  job. The mechanism I missed: **`kite_instruments` is upserted in place** (`57595 rows upserted,
  0 stale swept`) so yesterday's state is already gone. ⇒ the artifact is the raw CSV **plus the
  parsed EQ symbol set**. Four reasons that are not "history is unreconstructible": you cannot
  separate a rule change from a source change; **the collapse rail's refusals are unauditable**
  (it fires on the INPUT, the snapshot records the OUTPUT — so `UNIVERSE_APPLY_MIN_FRACTION=0.5`
  can never be tuned because a firing can never be reviewed, and §50's "inspectable" is wrong);
  rule v2 cannot be regression-tested against v1; and **the funnel is only a detector if it can
  tell a market event from an ingestion event** — which is the exact basis on which it was ranked P0.
- ⛔⛔ **SHIPPED: the collapse rail was one-sided, and growth is the dangerous direction.**
  `universe_materialiser.py:190` read "⚠ GROWTH is never refused." Severity is **composition**:
  U16's ceiling refuses the ENTIRE subscription past the per-connection cap (deliberately —
  truncating is a silent selection decision), so an over-including parse regression **— the exact
  mirror of the `EQ=0` header bug —** passes the rail, exceeds the cap, and the next worker start
  drops the feed for **every open position, including the held names U17 exists to protect**.
  Headroom measured **2,291 of 3,000**. `apply_to_stocks` now refuses above
  `settings.live_universe_max_count` — the worker's own knob (W5), enforced where it is still a
  refused write rather than at the worker where it is already an outage.
- ⛔ **CORRECTION to §42b, and it is mine.** The +1,121/−152 diff was called "independently
  derived … the strongest evidence in this document that the rule is right". **Measured: kite
  carries 10,110 distinct NSE EQ symbols against EQUITY_L's 2,292, and the universe is 2,291 — so
  `KITE_TRADABLE` excludes exactly ONE name.** The rule is ~99.96% single-source; two consumers of
  one CSV agreeing measures **consistency, not correctness**. The conclusion stands on §47's
  per-name review; the stated evidence was overclaimed.
- ⛔ **"1,847 with bars today" (§60/A1) was illustrative, not measured** — a made-up number inside
  the argument for a detector that exists to show real ones. Struck; the real figure is 2,286
  against a 2,250 median. ✅ **Measured and recorded:** `ca_flagged_at` = **7** (5 active), so the
  monotonic accumulator is a 7-row problem today, not §32's projected 1,768 — §38c's owed
  measurement is now taken.


### V1 + V2 — a price says where it came from, and an empty list says what it looked at (2026-09-14)

The first two items of the PART XXI §62 queue, backend **and** frontend in one change:
shipping the backend alone would have been the exact "built but unwired" defect §60/A5 is
about, and §44c had already found one instance of that pattern here.

- ⛔ **V2 — CORRECTION to PART XXI: the price fallback chain is THREE deep, not two.** Read
  from the code it is live tick → **last 1m close** → previous daily close → nothing; the
  middle rung was never documented and never surfaced. All four rendered **identically**, so a
  position whose feed had died showed a plausible number from a previous session — and
  `unrealized_pnl`, the daily P&L card and the paper record were all computed from it and
  looked equally real. `paper_broker` now exposes `PRICE_LIVE/MINUTE/DAILY/NONE` +
  `stored_price_with_source()`, with `get_current_price` **delegating** to it rather than
  carrying a second copy of the chain (W2).
- ⭐ **STRANDED is a different condition, not a worse staleness** — a held name with no
  tradable instrument cannot be priced *or exited* through the app at all. Page-level
  `role="alert"` naming every affected symbol plus the two real remedies, sourced from the
  same U17 `held_without_instrument()` query the live worker logs at ERROR, so the alert and
  the log cannot disagree.
- Positions API: the per-position `get_live_ltp` loop is **batched to `get_live_ltps`**,
  fixing an N+1 Redis round-trip the depth fetch had already been batched to avoid.
- ⭐⭐ **V1 — `GET /signals/funnel`**, and it doubles as the breadth detector the 6.8.6 feed
  alarm structurally cannot be: that alarm asserts **RECENCY**, never **COVERAGE**, and read ✅
  throughout the 2026-09-07 outage. Measured on dev: **3,395 known → 2,291 in universe → 2,286
  priced → 0 live signals**, 30-session median 2,250. ⇒ the zero is real.
- ⛔ **A stage nearly shipped wrong:** raw "stocks with a bar in the latest session" = **2,637**
  against an in-universe 2,291, because D3 ingests the whole bhavcopy deliberately. A funnel
  that *widens* is a bug that looks like data; the stage is now scoped to the universe and the
  nesting is asserted by test.
- ⛔ **The "scored" stage is genuinely ABSENT, not zero** — the scorer does not persist how many
  panels it evaluated. It renders as "not recorded"; a `0` would assert something we do not
  know (A24). Pinned by a test.
- ⚠ **Wired into two empty states, not the four the queue named.** `LiveSignalsPage` answers
  "was a level touched" and `StylePage` is per-style while the funnel is not — in both cases
  the counts would not correspond to the list beneath them. A diagnostic attached to a question
  it does not answer is worse than none, because it reads as an answer.
- Neither item moves a recorded number: `price_state` labels the price the code already used,
  and the funnel reads only.
- ⛔⛔ **ui-reviewer returned FAIL (16 findings, 3 HIGH) and the most important one INVERTED on
  measurement.** It observed the stranded banner claiming *"cannot be priced or exited here"*
  beside a fully enabled Close button, and proposed disabling the button. **Measured first:
  `close_position` takes no instrument** — `raw_price = exit_price or get_current_price(...)`,
  then `if raw_price is None: raw_price = position.avg_entry_price  # flat trade` — so a
  stranded position **closes fine**, and `held_without_instrument`'s own docstring says
  un-exitable *"through the **live path**"*, a qualifier the banner had dropped. **740 stocks
  have no EQ instrument and exactly 1 printed a bar in the latest session**, so the exit is
  booked against a stale close or a **fabricated flat trade**. ⇒ **disabling Close would have
  trapped the user in the one position they most need out of, to enforce a false claim.** Fixed
  the opposite way: banner copy corrected, and a `role="alert"` in `ClosePositionDialog` names
  what a blank price field will actually resolve to. ⭐ **When a UI and an action contradict,
  measure which one is lying before silencing either — disabling a control is not a neutral
  default, it is a claim that the action is impossible.**
- ⛔ **`--color-loss` failed AA in the DEFAULT theme** (slate 3.96:1, midnight 4.18:1; 3.36/3.66
  on hover) — the 2026-09-02 daybreak incident repeating in the dark themes — **and it was the
  wrong token regardless**: it means "losing money" on that same row, so stale data and a losing
  trade read identically. Both degraded states now use the `--color-warning` pill idiom;
  `--color-text-muted` (2.34:1 in daybreak at 11px) → `--color-text-secondary`.
  ⚠ **Recorded in `tokens.css`:** daybreak's `--color-warning`/`--color-warning-bg` pair clears
  AA by **0.01** — the tightest margin in the file, now load-bearing for two components.
- ⛔ Three A24 defects **inside the component built to enforce A24**: `Math.round` rendered a
  99.5% shortfall as **"100% below"** (asserting zero coverage) while printing 12 names priced
  two lines above ⇒ new `formatWholePct` **truncates**; `session` was fetched, typed and never
  rendered despite a backend docstring reading *"Without it the count means nothing"* **and a
  backend test asserting it**; a null median fell through both branches.
- ⛔ `DashboardPage`'s predicate tested the **post-filter** list, blaming the scan's scope for
  what a checkbox did — the exact mis-attribution written directly above it as forbidden.
- `PositionOut.price_state` is now `Literal["live","minute","daily","none"]` on the wire, with a
  test deriving the expectation from **both** declarations (W5).
- ⭐ **Re-review = PASS-WITH-NOTES, and it found nine defects IN THE FIXES.** The reviewer
  **withdrew its own #3 remedy** after reading `close_position`. The sharpest of the nine: my
  fix to the filter-vs-scan predicate **was the same error moved one layer up** — I called
  `signalData.signals` "the UNFILTERED response" in a comment while that query's key carries
  `direction`, `classification` and `minConfidence`, all server-side, so a min-confidence of 90
  would have blamed the scan's coverage for a slider. ⇒ **the decision MOVED** to `ScanScope`,
  which reads the funnel's genuinely unfiltered `signals_live`; `DashboardPage` now carries no
  predicate at all. Three attempts, three wrong predicates, one structural fix — each time the
  component that needed the answer was not the one that had it.
- ⛔ Copy corrections: **"a flat trade" overstated** (the `avg_entry_price` fallback still pays
  `simulate_fill` + `fees.py`, incl. the flat ₹15.34 DP charge ⇒ a small LOSS, never zero — and
  **`paper_broker`'s own `# fallback: flat trade` comment was stale** since 6.8.2/A29, now
  fixed, W1); the banner **was wrong for its own worst case** (no stored close ⇒ booked against
  the ENTRY price, and 740 instrument-less names have exactly 1 recent bar between them); and a
  **grammar bug in safety copy** — one stranded position read "This name **receive** no live
  price", because the plural branch covered every word except the verb.
- ⚠ **A principle applied to one of its two instances is not applied:** `PriceProvenance` was
  moved off `--color-loss` because a degraded state is not a negative value, while the banner
  thirty lines away kept the loss triplet. Now `--color-warning`. Plus a11y — the dialog warning
  said "see the warning **above**" (meaningless to a screen reader) and had no
  `aria-describedby`, so it was never announced on focus.
- ⛔⛔ **A PALETTE-WIDE AA DEFECT, found by a test written for something else.** `tokens.css`
  records contrast in prose comments and that convention has now failed three times, so
  `frontend/src/test/tokenContrast.test.ts` measures it instead — and **eight pairs are below
  the 4.5:1 floor on copy that carries money**: `--color-loss`/`--color-bear` at **4.29** on
  `--color-loss-bg` and **3.96/4.18** on the row surface in the three dark themes, and
  `--color-profit`/`--color-bull` at **3.32/3.44** in daybreak. ⭐⭐ **The structural finding:
  the 2026-09-02 fix was applied to a TOKEN, not a SEMANTIC GROUP** — it moved daybreak's
  `--color-loss` 3.95 → 5.30, and **`--color-bear` there still measures 3.95**, the very number
  that triggered it. ⛔ **NOT fixed — the user's call**, since changing the red or green moves
  every P&L figure in five themes; the test asserts the failing set EXACTLY, so it can only
  shrink deliberately. Recommendation (measured): dark `#ef4444` → `#f87171`, daybreak
  `--color-bear` → `#b91c1c`, daybreak green darker.
- ⚠ **The contrast test caught itself twice first:** `node:fs` did not typecheck under the app
  tsconfig (`make check` green while `pnpm build` failed — the documented build-gate gap), and
  Vite's `?raw` made it **silently vacuous** because vitest disables CSS processing, so the
  import was an empty string and every assertion would have passed while measuring nothing. The
  parse canary written for exactly that caught it — third instance of the repo's *guard test
  that cannot fail* pattern.


### Round-4 adjudication — the UI/UX round, and five corrections to our own PART XVIII (2026-09-14)

Five panel responses adjudicated in plan PART XXI. Every checkable claim measured first,
including the six questions asked with predictions stated.

- ⭐⭐ **S2 was about a third wrong, and the refutation dissolves Q1.** PART XVIII dismissed
  "a why-isn't-X-here lookup" as *"solves nothing, the user must already suspect"*. **Typing a
  symbol into search IS suspecting** — absence is not *notifiable* but it is *answerable* at
  two surfaces (search, direct navigation). Complementary correction: the unaskable set and the
  harmful set differ, since a user only feels absence when they hold a prior reference
  (searched / hold / held / watchlisted / saw it signal) — **all five already observable**.
- ⛔ **S3 understated it. `current_price` does NOT go null** — `update_position_pnl` falls back
  "live LTP → **last daily close**", so a stranded position renders a plausible price from a
  previous session. An em-dash at least signals absence; a stale close signals nothing.
- ⛔ **`ca_flagged_at` has NO clearing path** (measured). The only writer is the detector; the
  model docstring promises an admin unflag that does not exist. **A monotonic accumulator** —
  which retroactively strengthens §32's refusal to run the CA backward pass, since it would
  have permanently quarantined 1,768 of 3,395 stocks with no undo.
- ⛔ **The daily report has failed silently: 26 reports against 30 trading sessions.** Direct
  evidence for the panel's heartbeat requirement, and it refutes S4's *argument* while leaving
  its conclusion standing — 6.8.6 failed on **predicate**, not delivery.
- ✅ Predictions confirmed: `universe_snapshot` is **100% EQ (2,291/2,291)**, so the rule does
  what §42a claims; and only **1 of the 35** quarantined signals points at a stock the rule
  deactivated, confirming §52 from the other direction.
- ⭐ **Adopted, P0: the funnel counter** — an empty state has no stock in context, so naming a
  per-stock cause is a category error; show the scope searched instead. It ranks first not for
  the copy but because *"1,847 with bars today"* on a ~2,290 day **second-detects the breadth
  collapse 6.8.6 was blind to**, as a side effect of fixing a message.
- Eight-item queue in §62; three parked user items recorded in §64 (deep `ohlcv_1d` history,
  the other ~162 indices, and the market-regime/sector-RS limits).


### Index + VIX backfill — the market-regime overlay is evaluable again (2026-09-14)

`index_ohlcv_1d` and `india_vix_daily` were destroyed on 2026-09-07 and never redone: 54 and
18 rows, ~18 sessions. Every market-regime and sector-RS overlay has been unevaluable since.

| series | sessions | span |
|---|--:|---|
| NIFTY50 · BANKNIFTY · FINNIFTY | **789 each** | 2023-07-03 → 2026-09-11 |
| INDIA VIX | **789** | 2023-07-03 → 2026-09-11 |

- 789 sessions ingested, 46 skipped (weekends/holidays), from the NSE indices archive — one
  CSV per session feeding **both** tables, so half the requests of two separate backfills.
  No Kite dependency.
- ⭐ **Depth lands on 2023-07-03 again**, matching `ohlcv_1d`'s clean block and the intraday
  backfill from earlier today. All four archives — daily, 5m, 15m, index/VIX — now cover the
  **same period**, so no study can straddle a boundary present in one and absent in another.
- ✅ **Verified end-to-end, not just by row count:** `load_market_regime_context` now returns
  **200 closes** (the full DMA period) and **VIX 12.29**. Before this it had ~18 sessions and
  failed open silently.
- ⛔ **This restores the DATA. It does not license a flip.** `market_regime_gate_mode` stays
  `shadow` — §9/4 of the universe plan is explicit that restoring the index data is not
  evidence, and this project has promoted two gates on arguments and had both refuted within
  weeks. A promotion still needs the `t ≈ 3.6` bar.
- ⚠ **Sector-RS is still NOT unblocked.** The backfill scopes to `indices.is_active`, and the
  registry holds only **3** broad indices — the reason sector-RS has always been untested.
  Expanding it is U8. ⭐ The free win stands: the same CSV this downloads carries **165
  indices**, so U8 is a registry-population job, not a new data source.


### Intraday capture restored — 16.2M bars, back to the daily archive's clean block (2026-09-14)

`ohlcv_5m`/`15m`/`1h` have been **empty since the 2026-09-07 DB loss**, which made every
opening-range idea untestable and is a stated prerequisite before cycle 2.

- ⭐ **CLAUDE.md's "accrues only in real time" was imprecise, and checking rather than
  trusting it changed the plan.** Kite serves deep intraday history, and
  `scripts/backfill_intraday.py` already existed to fetch it — so the *history* was
  recoverable today rather than needing weeks of live accrual.

  | table | rows | stocks | span |
  |---|--:|--:|---|
  | `ohlcv_5m` | **12,189,732** | 210 | 2023-07-03 → 2026-09-11 |
  | `ohlcv_15m` | **4,051,153** | 210 | 2023-07-03 → 2026-09-11 |

- Depth lands exactly on **2023-07-03**, the first date of `ohlcv_1d`'s contiguous modern
  block, so the daily and intraday archives now cover the same period — no study can
  straddle a boundary that exists in one and not the other.
- **419 of 420 (symbol, timeframe) pairs admitted** at ≤5% gap. The exclusion is
  `FORCEMOT` 15m, **recorded and not patched** — the script's stated design.
- ⭐ **Sequencing mattered:** the backfill's universe is
  `is_active AND NOT ca_flagged AND (is_nifty50 OR is_fno)`. Run before D2′b it would have
  fetched microcaps; run after, it fetched the right 210 names with all 50 Nifty
  constituents inside them.
- ⛔ **`ohlcv_1h` remains EMPTY and has no backfill path** — the script's timeframe map
  covers 5m and 15m only. Hourly can accrue *only* from the live worker's `LiveBook`, so
  the 09-07 → now gap in it is **permanently unrecoverable**.
- ⚠ **Forward capture is ready but not running.** The persist path is sound (upsert with a
  monotone high/low/volume merge, so a restart re-mint cannot corrupt a bar) and the
  preflight now passes with **2,291 instruments** — the guard's baseline ratcheted
  1,178 → 2,291, growth accepted as designed. But no live-worker process is running, and
  `make live-worker` is a supervised ritual needing a fresh Kite token each morning.


### U11 — the 35 stale signals are withdrawn, not deleted (2026-09-14)

- ⭐ **Round 2's framing was wrong, and measuring first showed it.** These were queued as
  "the 35 microcap signals"; in fact **34 of 35 point at stocks the repaired rule says are
  tradeable** (ZYDUSLIFE, MAXHEALTH, DREAMFOLKS…), all were `status='active'`, and all were
  **still inside their validity window** — live and clickable. The real contamination is
  narrower: minted 09-09→09-11 by scanning 1,322 names with every blue chip excluded, **they
  won the wrong tournament.** Each signal's arithmetic is sound; the candidate SET was wrong.
- **Withdrawn, not deleted** — the rows are the forensic record of what the broken system
  emitted. ⚠ And deliberately **not** expressed through `status`: that is a lifecycle field
  the sweeper overwrites, so a verdict there could be silently undone and "expired by time"
  would be indistinguishable from "withdrawn as contaminated". New `quarantined_at` +
  `quarantine_reason`, mirroring `stocks.ca_flagged_at`.
- ⭐⭐ **Implemented as a `Restriction`, not a list filter.** A filtered signal vanishes —
  the invisibility PART XVIII objects to. As a restriction, the order path 409s and the
  display path returns `blocked=True, gate='signal_quarantine'` with the reason verbatim,
  so the existing `tradeBlock()` renders `⊘ Blocked` on all four Buy surfaces with **zero
  new UI**. Verified end-to-end against the live rows.
- ⛔ **New `Restriction.always_on`.** An OVERLAY rule with no mode KeyError'd 52 tests —
  the registry's coherence test doing its job. Giving the quarantine a mode would have
  created a `..._gate_mode = off` that **silently re-admits a signal a human removed**, so
  instead the concept "unconditional" is now explicit (it existed, conflated with "the
  broker rejects it"). A test asserts that with **every moded gate off**, a withdrawn signal
  is still blocked.
- Three registry-shape tests amended rather than silenced; `scripts/quarantine_signals.py`
  with `--list`/`--before`+`--reason`/`--release` (`--before` requires a reason — an
  unexplained withdrawal is not reviewable). Migration `f8a9b0c1d2e3`. 11 new tests.
  **Applied: 35 of 35.**


### D2′b — the universe rule owns `stocks.is_active`, enforced by the database (2026-09-14)

User approved the +1,121 / −152. **The 2026-09-07 outage is repaired.**

| | before | after |
|---|--:|--:|
| active stocks | 1,322 | **2,291** |
| **Nifty 50 constituents active** | **5** | **50** |
| subscription universe | 1,178 | **2,291** (76% of Kite's cap) |

- **The 152 were checked before flipping, not presented as a number:** **139 are `BE`
  series**, which the 2026-07-17 T2T ruling already excludes from live scanning — so
  deactivating them implements an existing ruling rather than deciding anything; the other
  **13 are junk**: `KNOWNCO` (a test fixture in the production stock master), `NIFTYNXT50`
  and `NIFTYFPI` (indices carried as stock rows), two rights entitlements, `QUINTEGRA`, and
  six delisted names. Two piles, nothing in between.
- ⭐⭐ **Enforced by a database trigger**, because a convention decays and this one already
  did. `is_active` may only change inside a transaction setting `app.universe_writer='on'`,
  and only `universe_materialiser.apply_to_stocks` does. Raw SQL and the ORM path are both
  refused. `SET LOCAL`, not `SET`, so a pooled connection cannot inherit the right to write.
- **Three writers gone:** `deactivate_dead_stocks.py` **retired** (its logic is the rule's
  `KITE_TRADABLE` term; left as a redirecting tombstone, and ⛔ **its documented reversal SQL
  was removed rather than preserved** — it joins on raw `stock_id`, and §20/2 proved every id
  was reassigned on 09-07, so running it would reactivate the wrong companies);
  `seed_stocks` now inserts `false` (seeding a symbol is not a tradeability verdict);
  `bhavcopy_service` already did. ⚠ INSERTs are deliberately not blocked — a row that does
  not exist cannot have been evaluated.
- ⛔ **A collapse rail §43 did not ask for.** The beat now applies nightly, unattended, from
  a CSV fetched over the internet, so `apply_to_stocks` refuses a snapshot below
  `UNIVERSE_APPLY_MIN_FRACTION` (0.5) of the active set. **This is exactly what my own
  `EQ=0` header bug would have done** had it reached this path instead of a `--diff`. Growth
  is never refused; a refusal logs at ERROR and leaves the universe alone.
- ⚠ **Deferred from §43 with reasons:** the four membership flags are NOT rule-derived —
  they self-heal on every reseed (which is why `is_active` alone got *stuck*), deriving them
  needs three more index CSVs in the job that now owns the money-path universe, and their
  real defect is point-in-time, which is U9's problem. And `forensic_stocks_deactivated` did
  not survive 09-07, so "the 15 July judgements as an acceptance test" was not possible.
- Migration `e7f8a9b0c1d2` (downgrade round-tripped on dev; it applies the *recorded*
  snapshot in pure SQL — a migration that fetches from the internet fails in a way nobody can
  reproduce). 14 tests.


### Calendar + UI/UX status for the panel (2026-09-14)

- **Added 2026-09-14 Ganesh Chaturthi to `nse_holidays`** (`source='manual'`, the model's
  documented value for an admin entry; the seed's `ON CONFLICT DO NOTHING` means later
  derivation cannot clobber it). ⭐ The calendar is 46/48 **derived** from bhavcopy gaps, which
  can only infer a holiday *after* the session passes — hence the gap. Verified:
  `_expected_latest_trading_day` now returns 2026-09-11, matching the latest bar, so **tonight's
  report will not raise a false staleness alarm**.
- ✅ **`sync-kite-instruments` fired unattended in production** at 02:30 UTC
  (`kite_instruments.synced_at` confirms) — first proof the token-free scheduled owner works.
  Worker restarted 10:19, so `materialise-universe` is now live too (fires tomorrow 03:05 UTC).
- **New plan PART XVIII — the UI/UX surface**, a *verified* inventory plus six statements and
  eight questions for the external panel. Headline: signal-level eligibility is fully plumbed
  (`blocked`/`blocked_by`/`block_reason`/`unassessed` → `tradeBlock()` on all four Buy
  surfaces), while **stock-level exclusion is invisible** — no UI for `is_active`, none for
  `ca_flagged_at` (which is not even in `StockRead`), no per-stock reason in any empty state,
  no ops/health page, and **a stranded position renders as a bare `—`, pixel-identical to a
  momentary gap**. ⭐ The hard part is that an absence is not askable: the 09-02 fix worked
  because the user was looking at a row and clicking a button that 409'd.
- ⚠ Two stale artifacts noted: `docs/STATUS.html` predates the 09-07 DB loss, and a **refuted
  claim in `SignalOut.choppy`'s comment** ("choppy tapes drove ~all the losses") is corrected —
  round 9 measured it at p = 0.999, which is why B1 deleted the filter. `choppy`/`near_expiry`
  survive as measured stamps, not eligibility.


### D2′a — the universe as a versioned rule, evaluated and recorded (2026-09-14) — SHADOW ONLY

`is_active` is a mutable boolean with three writers and no owner, and every one of the 3,392
`stocks` rows was minted during the 2026-09-07 rebuild, so there was never an original to
restore. The universe is now DERIVED and recorded rather than written. ⚠ **Nothing here writes
`is_active`** — the flip is D2′b, and this project has promoted exactly two rules on an
argument and had both refuted by data within weeks.

- **The rule, v1:** `EQ_LISTED ∧ KITE_TRADABLE`. ⛔ No bar-count term — bar coverage is a fact
  about our own data completeness, and a rule that reads its own completeness shrinks when
  ingestion breaks, which is 09-07 rebuilt inside the fix. Asserted **structurally**:
  `UniverseInputs` carries no coverage field, so no edit can add the term without changing a
  signature a test pins.
- ⭐⭐ **The diff: WOULD ACTIVATE 1,121 · WOULD DEACTIVATE 152 · resulting universe 2,291.**
  The 152 are all `not_eq_listed` — *exactly* the round-2 figure for "currently active but not
  in the EQ list", the QUINTEGRA class. Two independent routes to the same number, neither
  fitted to the other. Both directions are reported separately because the outage ran both
  ways and one "1,273 changed" would hide half the defect.
- ⭐ **Corrects U16 free:** §29f estimated the post-repair subscription at 2,655 (88% of Kite's
  cap) from a looser join. The rule's actual answer is **2,291 — 76%, headroom 709**. U16 still
  earns its place, but sharding is further off than reported.
- ⛔ **A bug I wrote, of the exact shape this rebuild is about.** The first run printed
  `EQUITY_L EQ=0` and "WOULD DEACTIVATE 1,322": the CSV header is
  `SYMBOL,NAME OF COMPANY, SERIES, …` — every column after the first has a **leading space** —
  so `row["SERIES"]` matched nothing and the parser returned empty **without raising**.
  `seed_stocks._csv_rows` already strips keys and says so in a comment, so this was a
  documented trap reintroduced by not reusing it. Had I trusted the output I would have
  "measured" that the rule condemns the whole universe. It now raises on a schema with no
  SERIES column, and the real header is pinned in a test.
- Ships migration `d6e7f8a9b0c1` (`universe_snapshot`, downgrade round-tripped),
  `universe_rule.py` (pure), `universe_materialiser.py`, `scripts/universe_snapshot.py`
  (`--diff` / `--materialise`), and a beat entry at 03:05 UTC — **after** the 02:30 instrument
  sync, since the rule reads `kite_instruments`; the ordering is pinned by test because nothing
  else enforces it. 15 tests + 2 schedule invariants.
- ⚠ `app/` must not import from `scripts/`; the first draft did, which also dragged that
  module's relaxed typing into a strict-checked file.


### D1′ — identity churn is recorded, and an ISIN is never silently rewritten (2026-09-14)

Two kinds of identity churn exist. **Rename** (ISIN keeps, symbol changes) was already handled
in place by `plan_renames` so the row keeps its id and its bars — but it left **no trace**, so
"what was this id called in July?" was unanswerable, which is half of why §20/2's reversal SQL
names the wrong companies. **Reuse** (symbol keeps, ISIN changes — NSE re-issuing a delisted
ticker) was not handled at all: `isin = COALESCE(EXCLUDED.isin, stocks.isin)` overwrote the
anchor and merged the new company into the dead one's row, inheriting its id and price history.

- ⭐ **The one-word fix: `COALESCE(stocks.isin, EXCLUDED.isin)`.** The anchor is filled once
  and never silently rewritten. A differing ISIN on a known symbol is either a reuse or a data
  correction and nothing in the feed distinguishes them — the old behaviour picked one
  silently, and it picked the one that merges two companies. It now keeps what it has and
  reports the conflict.
- New `symbol_history` table (migration `f2a3b4c5d6e7`, downgrade round-tripped on dev), model,
  and `app/services/symbol_history.py`. `seed_stocks` now seeds intervals, records renames, and
  reports ISIN conflicts. Verified on dev: 3,395 intervals, all open, 0 stocks with two open
  intervals; `valid_from` spans 09-07…09-13, the later dates being exactly the three rows U3's
  backfill created, so `first_seen` is honest rather than backdated.
- ⛔ **`uq_stocks_symbol_exchange` deliberately NOT dropped**, against §26's wording. 14 call
  sites assume one row per symbol and would silently resolve to an arbitrary row (the upserts
  lose their conflict target outright). And the hazard's rate is **unmeasurable
  retrospectively**: I measured 0 of 2,547 ISIN mismatches, and that number is worthless —
  our master was rebuilt from the very CSV it is compared against, and a merge overwrites its
  own evidence. Fourth instance of the estimand trap (§25f), caught before it was banked.
  Parked with an unblocking condition: **when `symbol_history` records a real `reuse` event**,
  the rate is measured and the migration has a reason.
- 14 tests.


### D0 — the stock-identity pin (2026-09-14)

Every `stocks.id` was reassigned during the 2026-09-07 emergency rebuild, which is why
`deactivate_dead_stocks.py`'s documented reversal SQL now names the wrong companies (§20/2):
July's `stock_id = 228` was QUINTEGRA, today's is BSE.

- **What it buys, stated precisely:** restoring from a `pg_dump` carries ids with it, so the
  pin adds nothing there. It matters in the case that actually happened — a rebuild **from
  source**, where bars re-attach by SYMBOL and stay internally consistent (which is why
  nobody noticed) while every artifact keyed on an id silently re-points at a different
  company.
- `backend/seed/stock_identity.csv` (3,395 rows, 116 KB), a pure `app/services/stock_identity.py`,
  and `scripts/stock_identity.py --export | --verify`. ⚠ `data/` is gitignored, hence
  `backend/seed/` — a pin file git never sees is not insurance.
- ⭐ **Only a CONFLICT fails.** New listings and delistings are reported as churn, because a
  guard that cries on ordinary turnover gets ignored within weeks — this project has already
  watched the 6.8.6 alarm read green through a five-day outage for asserting the wrong thing.
- ⭐ **The first test is a negative control**, not a happy path: it plants the exact 09-07
  scenario (QUINTEGRA 228→900, BSE 500→228) and asserts both are caught. A verifier that
  cannot detect the failure it exists for is decoration.
- ⛔ **Forensic detail found while building it:** 3,395 rows carry ids running to **2,178,609**.
  An `ON CONFLICT DO UPDATE` still consumes a sequence value per attempted insert, so that gap
  is a log of the reconstruction's insert attempts (~950 backfill days × ~2,300 symbols ≈
  2.18M) — an independent third confirmation of §3a's `backfill → seed → backfill` ordering,
  this time from the sequence rather than the id blocks.
- The restore procedure is written down in §40e, including the `setval` step that must follow
  an explicit-id insert or the next insert collides.
- 11 tests.


### U17 — the subscription is `universe ∪ held names` (2026-09-14)

`_build_token_stock_map` filtered `s.is_active = true`, and that map is the subscription
universe. `scan_positions` is correctly NOT universe-filtered, but it prices from
`get_live_ltp` and that key exists only for SUBSCRIBED instruments — so a held name that
left the active set stopped receiving ticks, its key expired at 600s, and the monitor
skipped it **permanently**, with SL and TP still on the row and nothing alive to evaluate
them. The skip is silent by design ("the monitor never acts on a stale price"), which is
correct in isolation and catastrophic in composition.

- Latent until now only because `is_active` moves when a human runs a script. **D2′ makes a
  rule re-evaluate it nightly**, so this is a precondition for that change, not a nicety.
- Mode-agnostic on purpose (`closed_at IS NULL`, any mode) — a Phase-7 live position needs
  its feed more than a paper one.
- ⭐ **The trace narrowed the scope.** The provisional alert hot set is deliberately NOT
  unioned: exits don't need it (`_publish_ltp` writes from the tick batch), and it is
  capacity-bounded with a recorded quant-verifier finding that a stale row "silently eats a
  slot" — so unioning it would re-introduce that bug on purpose. Four call sites mention
  `is_active`; exactly one was on the path that mattered.
- New `held_without_instrument()`: a held name with no EQ instrument has no token to
  subscribe to, so it is genuinely un-exitable through the live path. `_bootstrap` logs
  those at ERROR by symbol — reported, never raised, because one stranded name must not stop
  the worker serving every other position (the opposite call from U16's ceiling, where
  *every* subscription would be wrong).
- 9 tests, two stash-proven against the old query. Real data: 0 open positions, subscription
  universe 1,178, 0 stranded, within U16's 3,000 cap.


### D3 — the price archive no longer consults a trading decision (2026-09-14)

`upsert_bhavcopy_rows` appended `AND is_active = true` on the daily path. `is_active` is a
selection flag with three writers and no owner, so a selection mistake silently destroyed
price history — that is how 1,481 names lost five sessions between 2026-09-07 and 09-12.

- ⛔ **It also made U3's repair non-durable, which is what actually decided this.**
  `eod_catchup.py:102` calls the default path, so measured on 2026-09-11: of the **2,637**
  names that traded, the old path would write **1,166** and drop **1,471 — every single
  day.** That is the same per-session number U3 had to repair, so the next EOD run would
  have reopened the hole. Three rounds argued this on storage (~6 MB/year); the data flow
  settled it in one query.
- Both modes now attach bars to every KNOWN NSE symbol. They differ only on UNKNOWN ones:
  creating a stock row stays a `historical=True` behaviour, because recording a bar is
  bookkeeping while minting an instrument is a universe decision.
- ⚠ **The T2T ruling is not overturned.** It excludes BE/BZ/SM from live *scanning* and the
  scanner still enforces it (`resolve_universe` filters `is_active` itself). It was never
  implementable as a storage rule anyway — `parse_bhavcopy_csv` keeps `EQ` series only, so a
  name that *moves* to BE stops appearing in what we ingest regardless of any flag.
- **Downstream trace in §38b** — every `ohlcv_1d` consumer checked. Nothing defines a
  universe by "has bars" (the one hazard that would have silently widened a recorded
  number). Unaffected: signal minting, alerts, pair universe, the 6.8.6 feed alarm
  (measures recency, which is why it read ✅ through the outage), `deactivate_dead_stocks`
  (keys on `kite_instruments`, not bars), every benchmark service, liquidity, backtests.
  Affected and intended: U15's median threshold (self-adjusting by construction),
  `ca_detector` (§38c), and `load_frames` — where it is a restoration that closes the
  ~2026-10-06 clock permanently rather than pausing it.
- ⚠ **§38c, for whoever runs D2′:** D3 + D4a compose, so archive-only names will accrue
  `ca_flagged_at` over time and some returning names will already be quarantined on D2′ day.
  Correct behaviour, but measure the flag count before and after the first rule evaluation.
- `test_inactive_stock_gets_no_bars` is reversed to `test_an_inactive_stock_now_receives_bars`
  with the history kept in the class docstring. 13 tests.


### U16 — assert Kite's per-connection subscription cap (2026-09-13)

`live_worker` subscribes in one unchunked call and Kite carries at most 3,000 instruments
per WebSocket. Checked the SDK rather than assuming: `kiteconnect/ticker.py:567` serialises
the whole list into one frame and enforces nothing client-side, so the excess is dropped
server-side and nothing tells us — the same silent-partial shape as everything else here.

- Added as a third arm of the existing universe guard (`LIVE_UNIVERSE_MAX_COUNT=3000`), not
  a new mechanism. It **refuses rather than truncating**: subscribing "the first 3,000"
  silently picks which names the system stops watching, which is a selection decision made
  by list order with no evidence behind it.
- Needs no baseline and no Redis, so it fires on a first run; an over-cap universe is not
  recorded as a high-water mark, or a refused start would raise the baseline above what the
  connection can carry.
- Measured: today's subscription is 1,178 (39% of the cap); the post-universe-repair ceiling
  is **2,655 (88%)**, so the headroom before sharding is needed is 345. ⚠ This does not make
  a >3,000 universe work — it makes it impossible for one to fail quietly.


### D4a — the corporate-action detector is no longer gated on `is_active` (2026-09-13)

A corporate action is a fact about a price series, not about whether we currently trade the
name — and the quarantine's only consumer (`universe_service.resolve_universe`) already
filters `is_active` itself, so gating *detection* on it was redundant. It was also harmful:
through the 2026-09-07 → 09-12 outage the real universe was wrongly inactive, so the
detector was blind to exactly the names that mattered. Three flags in its lifetime, against
49 unadjusted actions known to sit in the top-250-liquid set alone. Three regression tests.

⛔ **The backward pass (D4b) is deliberately NOT shipped.** Measured first: replayed over the
1,098-session archive at the detector's own 20% threshold it would flag **1,768 of 3,395
stocks — including 386 of the 1,322 active**, i.e. 29% of the tradeable universe
quarantined permanently in one command, since the flag has no expiry. The docstring's
asymmetry ("false positives cost a review") holds at forward cadence, where the detector
fires a few times a day; it does not survive 2,923 events. Rescoped in §32 of the universe
plan as a review queue against `corporate_actions` with a split-ratio discriminator — which
makes it the front half of A3, not a half-day job.

### U15 — the backfill can repair a THIN session, not just a missing one (2026-09-13)

`backfill_ohlcv_history` judged a date complete by a fixed floor of 500 rows. The five
broken sessions held ~1,170 against a normal ~2,630 — all over 500 — so running the script
across that range would have printed "nothing to fetch — range already complete" and done
nothing; the U3 repair had to bypass it.

- Completeness is now measured against the range's own median session (80%), via a pure
  `complete_day_threshold()` so the rule is testable without a database; the old 500 is kept
  only as a backstop for degenerate ranges. Adds `--min-rows` and prints every session it
  intends to re-fetch. 8 tests, including a canary asserting the old floor would have passed
  every thin session.
- ⚠ Raising the constant would have reproduced the defect at a new threshold — no constant
  can be right for a quantity that grows with the listed universe.
- ⭐ Third instance of one shape: the 6.8.6 feed alarm asserted recency, `load_frames`
  asserted a bar count, this asserted a row floor — each an instrument asserting PRESENCE
  where the failure mode is COVERAGE.


### U1 — `kite_instruments` repopulated, and given a scheduled owner (2026-09-13)

The table had exactly one writer: an admin HTTP endpoint. Nothing scheduled had ever owned
it, which is why it stayed empty for five days after the 2026-09-07 DB loss while
`live_worker` logged `up: 0 instruments` every morning and ran dark.

- ⭐ **The dump is PUBLIC** — `https://api.kite.trade/instruments` returns HTTP 200 with
  110,290 rows and no `Authorization` header. That is what makes a scheduled owner
  possible at all: a Kite token dies ~06:00 IST daily and is renewable only through an
  interactive login, so a beat task needing one would go dark on exactly the mornings
  nobody logged in. `sync_instruments` now takes `access_token: str | None` and uses the
  public transport when given none; the SDK path is kept for the admin endpoint. A test
  asserts both paths map a row identically.
- **New beat task** `app.tasks.market_data_tasks.sync_kite_instruments`, 02:30 UTC
  (08:00 IST) weekdays — before the 09:15 session.
- **New startup guard** (`app/broker/universe_guard.py`): `live_worker` now exits
  `EXIT_NO_UNIVERSE = 5` rather than running dark, on an EMPTY subscription universe or
  one that has COLLAPSED below `LIVE_UNIVERSE_MIN_FRACTION` (0.5) of the previous
  session's. Growth is never refused; a refusal does not overwrite the baseline (or the
  guard would disarm itself after one bad morning); it fails open on Redis errors.
- ⛔ **Fixed a bug this change would otherwise have shipped:** `sync_instruments` never
  committed — it relied on its caller, and its only caller was the admin endpoint, whose
  `get_db` auto-commits. `run_db_task` does not, so the new beat task would have upserted
  57,595 rows and rolled them back **every morning while logging success**. The sync now
  owns its commit, matching `bhavcopy_service.upsert_bhavcopy_rows`. Both regression tests
  are stash-proven against the old code and assert from a **separate session**, since
  `flush()` makes rows visible to the current one.
- **Measured:** `kite_instruments` 0 → **57,595** rows (NFO CE 16,901 · NFO PE 16,844 ·
  BSE EQ 12,957 · NSE EQ 10,246 · NFO FUT 647); subscription universe **1,178**.
- ⭐ **Four subsystems un-darkened, not one:** the tick path, the frontend live-quote
  WebSocket (`api/v1/ws.py`), and the F&O option-chain recorder — whose "skipped" status
  in §7 of the daily report was correctly attributing its zero to this table all along.
- ⛔ **New finding, queued as U16:** `live_worker` subscribes in one unchunked call and
  Kite caps a connection at 3,000 instruments. Today that is 1,178 (39%); the post-repair
  ceiling is **2,655 (88%)**. The universe repair moves this to within 345 of a hard
  broker limit with no chunking and no guard — fix before D2′ lands.
- ⭐ **bug-hunter found five defects in the above, all fixed in the same commit** (§30):
  the supervisor was never taught `EXIT_NO_UNIVERSE`, so a refusal restart-looped every 5s
  instead of pausing; the check ran *after* `startup_gap_fill`, so a refusal first spent a
  ~35-minute throttled Kite pass; the baseline was re-recorded on every accepted start, so
  a staged collapse (2655 → 1460 → 803 → 441 → 242 → 133) passed a 50% ratio test at every
  step — and the real 09-07 event, 1,182 of 2,646 = 44.7%, cleared that bar by only 5.3
  points; an HTTP-200 login interstitial parsed to zero records and reported SUCCESS
  forever; and the refusal's remedy told the operator to use `redis-cli`, which is not
  installed here. The baseline now **ratchets up only**, a new absolute floor
  `LIVE_UNIVERSE_MIN_COUNT=500` covers what a ratio cannot, and both emptiness checks raise.
- New `backend/scripts/sync_instruments.py` — the token-free manual remedy the supervisor
  now prints.
- Also fixed two pre-existing `ruff` failures in `tests/test_ledger.py` (unmodified by
  this work) that had left the branch's lint gate red since the B8 commit.


### U3 executed — the 09-07 → 09-11 breadth hole is closed (2026-09-13)

The first write the universe-rebuild plan has made, on the user's explicit instruction.
`make backup` first (`trading_platform-20260913-215611.dump`).

- **+7,351 bars** across five sessions; `ohlcv_1d` 2,082,639 → 2,089,990. Per-session
  breadth 1,166–1,182 → **2,637–2,652**, matching the pre-hole 2,632–2,647 range.
- **Names with a bar on 09-04 and none after: 1,481 → 4.** The four residuals
  (`RNBDENIMS`, `DAICHI`, `MANAKSTEEL`, `HEG`) stopped appearing in the bhavcopy itself —
  a listing event, not an ingestion failure. Blue chips all current to 09-11.
- ⭐⭐ **`is_active` was 1,322 before and 1,322 after**, so the plan's `U1 → U2 → U3`
  dependency chain is disproven by execution, not just by reading
  `bhavcopy_service.py:255`. The `load_frames` ~2026-10-06 clock is stopped; no part of
  the universe redesign is on a deadline any more.
- ⚠ Scope was wrong in the plan two ways, both caught before running: the hole is five
  sessions (09-05/06 and 09-12/13 are weekends), and
  **`scripts/backfill_ohlcv_history.py` would have silently no-opped** — its
  `_already_done` guard skips any date with `>= _COMPLETE_DAY_ROWS = 500` rows, and the
  broken sessions held ~1,170. The run reused that script's own `_fetch_all` loop with an
  explicit date list rather than writing a second one.
- ⛔ **New defect queued as U15:** the backfill can repair a MISSING session but never a
  THIN one. Same blindness as the 6.8.6 feed alarm — an instrument asserting presence
  where the failure mode is coverage. Fix = a breadth-aware predicate (trailing median),
  not a higher constant.
- ⚠ The 7,351 new bars have **not** been scanned by `ca_detector.py` (it runs from
  `eod_catchup`, not from `ingest_bhavcopy_date`); CA flags stand at 3.
- 3 new `stocks` rows created inactive by `_ensure_historical_stocks` (`DEEPA`, `CRESTO`,
  `DOLLEX`); 3,392 → 3,395. Designed survivorship-safe behaviour.


### Universe rebuild plan — round 1 adjudicated; §3's root cause was wrong (2026-09-12)

Five external reviews (ChatGPT, Gemini, Perplexity, DeepSeek, and a Claude review delivered as
a separate document). Every claim adjudicated against the code and the database rather than
against our own docs, which confirmed two strong points and refuted three.

**⛔ §3's root cause is corrected (new §3a).** The round-1 review found by arithmetic on our
own published rows that 1,305 active stocks have bars, which sequential "bhavcopy first, then
seed" cannot produce. Verified three ways: 1,303 active stocks hold pre-09-05 bars (DMART,
AFFLE, NEOGEN carry 1,045 each back to 2019-10-01); the row-id blocks separate cleanly
(ids 1–1,700 = 0% active, created alphabetically by `_ensure_historical_stocks`, 1,415 of them
carrying a 2019-10-01 bar; ids 9,277–11,823 = 100% active, `seed_stocks.py`'s INSERT branch;
ids 11,750+ = 0% active again); and the five active Nifty 50 names (ETERNAL, JIOFIN, MAXHEALTH,
SHRIRAMFIN, TMPV) are all post-2019 listings. The restore was **interleaved**, so `is_active`
encodes which process created the row, not any property of the stock — and "seed first" is
therefore not a sufficient fix. The remedy becomes an invariant: the price archive must never
consult a trading flag (U6′).

**⭐ Two findings no reviewer had, both from verifying a review against the DB**
- **The research apparatus has a ~3-week deadline.** `load_frames` — the universe loader shared
  by `swing_dependence_probe.py` and `e2_score_ic.py` — admits a name only with >100 bars in the
  trailing 180 days. The frozen blue chips sit at **117**, a margin of 17 sessions that shrinks
  by one per trading day. On or about **2026-10-06** RELIANCE, TCS, HDFCBANK, INFY and ITC drop
  silently out of every probe built on it.
- **A documented reversal procedure is now actively dangerous.** `deactivate_dead_stocks.py`'s
  docstring ships reversal SQL joining `forensic_stocks_deactivated` on `stock_id`, and all 15
  ids now resolve to different companies (228 QUINTEGRA→BSE, 1213 JBCHEPHARM→SCHNEIDER). Running
  it would reactivate the wrong stocks.

**Refuted by measurement**
- "No scheduled backup exists" — a cron job has run `0 11 * * 1-5` since 2026-09-07; dumps for
  09-09/10/11 are present. Valid residue kept as U0.5′: all backups post-date the breakage and
  live on the same box.
- "E2 may be contaminated" — `load_frames` applies no `is_active` filter and the frozen names
  cleared its threshold at 117 bars on 09-12. E2 stands.
- "New listings are permanently invisible" — `_ensure_historical_stocks` runs only under
  `historical=True`; the daily path never creates a stock row.
- "Were the 15 July deactivations correct?" — verified correct; all are absent from today's
  `EQUITY_L.csv`.

**Also measured:** the active set is wrong by *inclusion* too (QUINTEGRA is active despite being
delisted), and all 35 live signals point at the microcap set — queued for quarantine (U11).

**Added** — PART V (§19 dispositions · §20 new findings · §21 revised queue with U0.5′, U6′,
U11–U14 and CAS/intraday promoted to P0 · §22 two blocking questions for round 2, including
whether the T2T ruling governs trading or storage, which U6′ collides with).


### Universe rebuild plan — the stock master has been silently wrong since 2026-09-07 (2026-09-12)

⛔ Diagnosis only; **nothing was executed** — no table written, no flag flipped, no migration run.
The symptom was `live-worker up: 0 instruments` and an empty AlertBell.

**Measured (dev DB, 2026-09-12)**
- `kite_instruments` = **0 rows** — the live path joins through it (`tick_consumer.py:463`), so
  there were no subscriptions. Its only caller is the admin endpoint `app/api/v1/broker.py:118`:
  **nothing scheduled has ever owned that table.**
- `stocks` = 3,392 / 1,322 active, but the active set is the wrong one: `RELIANCE`, `TCS`,
  `HDFCBANK` are `is_active = false`; **45 of 50 Nifty 50 and 14 of 14 Bank Nifty names inactive**.
  Only **751** active stocks carry the ≥300 bars the engine window needs; 1,683 inactive ones do.
- Daily EOD writes bars only for active names (`bhavcopy_service.py:255`), so **1,481 names have
  received no daily bar since 2026-09-04** and the hole grows one session per day.

**Root cause** — two individually-correct pieces composing. `_ensure_historical_stocks`
(`bhavcopy_service.py:191`) creates unseen bhavcopy symbols `is_active = false` for survivorship
safety; its stated invariant ("can only add, never deactivate") holds **only if `stocks` is
populated first**. On an empty table every symbol is unseen. `seed_stocks.py:354`'s
`ON CONFLICT DO UPDATE` then repaired every column **except `is_active`**. ⇒ the recovery order
`seed_stocks.py` → instruments sync → bhavcopy backfill → universe repair is **mandatory** and was
documented nowhere.

**⭐ Why nothing alarmed** — the 6.8.6 silent-feed-outage alarm asserts **recency**
(`max(time)`), never **coverage**, and printed "✅ Feeds current … Equity EOD 2026-09-11"
throughout. The A40 worker-liveness alarm fired correctly (celery and live_worker both down).

**⭐ Free capability found** — the NSE daily indices CSV `vix_service` already downloads carries
**165 indices** with OHLC + Volume + Turnover + P/E + P/B + Div Yield, including every sector
index and the size ladder. `indices` currently holds 3 rows.

**Added**
- `docs/UNIVERSE_REBUILD_PLAN.md` — measurement (PART I), an 11-item restoration queue in
  `BUILD_QUEUE.md` conventions (PART II), the universe-curation decision left explicitly open
  (PART III), and a **two-way review protocol** (PART IV). Splits every criterion into
  **structural** (no evidence bar) vs **empirical** (needs the `t ≈ 3.6` bar or a user ruling),
  and records that a liquidity floor at the universe layer would re-implement MCE slice 5a, which
  was measured and rejected.
- PART IV makes the review a loop rather than a verdict: **§12 THE WINDOW** (the book is empty, so
  structural change is free today and expensive after cycle 2's clock starts — while explicitly
  *not* lowering the evidence bar for selection changes); **§13** the six questions that block the
  plan; **⭐ §14 ten architecture questions** on building a standard security master (identity,
  point-in-time universe, corporate actions, ingestion invariants, universe-as-rule, multi-source
  reconciliation, sector taxonomy, calibration to a solo operator at ₹1 lakh, and the two
  time-sensitive captures — CAS and intraday); **§15** what reviewers may ask us, what we cannot
  answer at all (the destroyed book, CAS, intraday, 2021–22), and how to ask cheaply; **§16** the
  ADOPT / **PARK** / REJECT disposition rule — *parked never means wrong, and every parked row must
  carry its unblocking condition*; **§17–§18** the round ledger and parked register;
  **Appendix B** a five-point orientation for a reviewer new to the system.

**Fixed (docs, W1)**
- `CLAUDE.md`, `docs/PHASES.md` and the memory index claimed the ledger migration `e1f2a3b4c5d6`
  was **not** applied to dev. Measured: `alembic_version` = `e1f2a3b4c5d6` and `ledger_entries`
  exists. The warning was stale and is corrected in all three.


### B8 — the append-only ledger. The last item of the B-queue (2026-09-12)

⛔ It exists because `positions` and `orders` are EMPTY. The 2026-09-07 loss took the live tape
with no backup, and that made ten rounds of live-tape argument unfalsifiable: the offered sets,
the human's picks and every realised outcome are gone and unrecoverable. Whether the human adds
value over an uninformative sort key is, for all of history, unanswerable. ⭐ **Not for this
strategy -- E2 just closed the scorer as a ranker -- but for any successor.**

**Added**
- `app/models/ledger.py` + `app/services/ledger.py` + migration `e1f2a3b4c5d6`: **ONE**
  append-only table with the five node types as a discriminated column, not the eight-table
  schema the rounds proposed. ⭐ **Timeboxed deliberately**: the base rate is one item shipped
  as code in the fifty days before this queue, and the eight-table version is the one that does
  not ship. It can be normalised later, which is a far easier problem than resurrecting data
  nobody wrote.
- Mandatory provenance on every row -- `code_commit`, `spec_version`, `experiment_id`,
  `data_version`, `as_of` -- as REQUIRED arguments with no defaults. ⭐ **The sample-tag rule in
  software**: sec 16.1 has been violated eight times by five authors, twice by whoever was
  invoking it. Prose cannot carry that rule; a NOT NULL column can.
- `correct()` supersedes a row with a NEW one and leaves the original standing; `export_day()`
  writes newline-delimited JSON for an off-box destination.
- 12 tests covering both invariants, the export, and the empty-day case.

**⭐ A defect the tests caught immediately**
- The chain was ordered by `created_at`, and **Postgres `now()` is the TRANSACTION timestamp** --
  so every row written inside one transaction shares it to the microsecond, and a decision, its
  order, its fill and its outcome are exactly the rows written in one transaction. The first run
  put `position_lifecycle` before `order_intent` because the tiebreak fell through to a random
  UUID. **A ledger that cannot be ordered is not a chain.** Fixed with a database identity
  column (`seq`), which depends on no clock and cannot tie.

**⚠ The migration is NOT applied to the dev database**
- Verified against the test DB, upgrade **and** downgrade both clean (the downgrade was actually
  exercised, not merely written). Dev remains at `d0e1f2a3b4c5`. `make migrate` when ready --
  see RUNBOOK sec 8b.

`ruff` + `mypy` clean (303 files); `tests/test_ledger.py` 12 passed.


### B6 + B7 — E2 run against its pre-registration: 3a is a NULL (2026-09-12)

Pre-registered in `docs/analysis/E2-PREREGISTRATION-2026-09-12.md` and committed (`fe5d508`)
BEFORE the code existed, with two amendments both timestamped before any decision result.
Full output: `docs/analysis/e2-b7-results-2026-09-12.md`. New sec 12.35.

**Added**
- `scripts/e2_score_ic.py` — the three pre-registered estimands: 3a unconditional IC (the
  decision), 3b matched-tail contrast, 3c the gate-conditional collider (reported, never
  decided on). The frozen scorer is called with `min_confidence=0` so a score exists for
  every eligible name; `_spearman` comes from `factor_sweep` and the gap guard from
  `market_calendar` rather than being re-derived.
- `scripts/b7_hazard.py` — MFE/MAE per trade in R, raw % and ATR units; the hazard curve
  `P(+1R before -1R | day d)` for d = 0..20; time-to-excursion by stop-width bucket and
  direction; and the T=0 cohort separated out.

**⭐ THE RESULT — 17,748 panels, 96 sessions, median cross-section 190 names**
- **3a unconditional IC at h=5d: -0.0070, SE 0.0115, t -0.61, 90% [-0.0259, +0.0119] = NULL**
  on the pre-registered band (interval contains zero AND its upper bound sits below the
  measured break-even IC of 0.0310). The `confidence_pct` the deployed UI sorts by is flatter
  still (+0.0024).
- ⚠ **3b is INCONCLUSIVE and is reported as such.** Point estimate -0.3150% (passers
  UNDERPERFORM matched non-passers, so it is not evidence the gate adds value) but the upper
  bound +0.388% exceeds the +0.255% break-even. **The clean-closure branch does not fire
  cleanly: the RANKER is dead, the GATE is unproven in both directions.** Filling that gap
  with a prior is what the pre-registration forbids.

**⭐ Two assumed constants retired (these move sec 16.1)**
- `sd(IC_t)`: assumed 0.10, **measured 0.1126**.
- `E[z|selected]`: assumed **2.268**, **measured 1.8506** (SE 0.0238) -- a normal-tail
  approximation applied to a hard gate on a bounded score. 18% lower, so every break-even-IC
  figure rises ~23%. Break-even IC is now **0.0310**, near the middle of the published band.

**⭐⭐ B7**
- MFE/|MAE| is **0.83 (ALL) / 1.12 (clean x BUY)** -- roughly symmetric, so the "3a positive
  with MFE >> |MAE| means a geometry repair" branch does not fire on either leg.
- **The hazard curve is FLAT**: P(+1R before -1R | resolved by day d) = 0.559, 0.510, 0.500,
  0.520, 0.494, 0.489 over days 0-5 and unchanged through day 20. ⇒ **sec 13.11's
  hold-period-as-breadth-lever is RESOLVED AGAINST THE LEVER** -- shortening the hold does not
  raise mu, it only truncates unresolved trades.
- The **T=0 cohort** (27 of 185, exits on its entry bar) reads mean R **-0.7034** against
  -0.0541, contrast **t = -4.16** -- the first contrast in eleven rounds past t = 3.6. ⚠ It is
  the TIGHT-STOP cohort again: 53% of sub-2% trades are T=0 against 7% of the reachable book,
  and on w >= 2% removing it does not change the verdict. Recorded, not acted on.

**⛔ A new defect found en route, queued not fixed**
- `positional_probe.py` rejects a fill whose open has gapped past the stop and the live path
  refuses it unconditionally; **`swing_dependence_probe.py` has no such check**. Harness defect
  #4 runs at 2 of 185 so it drives nothing above, but the swing corpus admits fills the live
  order path would refuse and the positional corpus does not -- the two have never been
  measuring the same population.

`ruff` + `mypy` clean on both scripts.


### B5 — E1 re-specified: the positional family in FOUR units, with contrasts (2026-09-11)

E1 as originally written asked for R, raw % and net Rs. Re-reporting in raw % removes the
`1/w` amplification and does NOT remove the second mechanical term: `R = (alpha + drift*T)/w`,
and `T` rises with `w` at t = +6.69 while the universe drifted +0.0816%/day. Only a benchmark
PAIRED to each trade's own window removes it. On the swing book that sequence took the
tight-vs-wide contrast from -0.386 (t -1.55) to -0.262 (t -0.78) to **+0.069 (t +0.17)**.

**Added to `positional_probe.py`**
- `T`, `bench` and `excess` per trade, plus `ret_atr`, `cash`, `atr_pct` and the gap flag.
  ⭐ `basket_series`, `basket_window`, `atr20` and `_as_date` are IMPORTED from
  `swing_dependence_probe`, not re-derived (W2). Re-deriving an "equal-weight universe
  return" in a second file is exactly how two numbers that must agree stop agreeing -- and
  sec 16.1c's time-dimension rule exists because a benchmark measured on one sample was
  subtracted from another.
- B4's span-based gap guard, which this file never had at all.
- `_e1_report()`: per stop-width bucket, n / mean T / E[1/w] / R / raw % / excess vs the
  matched basket / ret-per-ATR20 / net Rs, for ALL windows and gap-clean separately, each
  followed by the tight-vs-wide **CONTRAST with its SE and its 80%-power MDE**.
  ⚠ Contrasts, never two levels: sec 12.27 found sec 12.1's published "the sign flips at
  w = 2%" was two point estimates each within 1.3 SE of zero, and the contrast is t = -1.47,
  p = 0.14 with an MDE of 0.74R. That is the family error this document has committed eight
  times.
- `--dump-trades`, the round-9 convention: one expensive pass writes the per-trade artifact,
  every contrast downstream is a cheap read.

⚠ The prior for positional is NOT the swing one and the report is built to show it: its
buckets carry OPPOSITE signs (which `E[ret]*E[1/w]` cannot produce at any mean) and its
reachable cohort is the BETTER one where swing's is worse.

**⭐⭐ RESULT — E1 is ANSWERED and positional closes the same way swing did.**
n = 390 positional trades (359 gap-clean), reproducing sec 12.1's 385 closely. The
tight-vs-wide contrast decays monotonically as each mechanical term is removed and is gone by
the third unit: **R -0.4879 (t -1.89) -> raw % -0.7870 (t -1.18) -> excess vs the matched
basket -0.1909 (t -0.29)**. Swing went -0.386 -> -0.262 -> +0.069. Different numbers, identical
shape, same verdict.
- ⛔ And sec 12.27's "opposite signs, so not the swing mechanism" argument is WITHDRAWN against
  itself. `E[1/w]` jumps **110x** at the first bucket boundary (43.4 against 0.352) -- a mean
  stop width of ~0.026% -- and net Rs in that bucket is **-25,808 per trade**. It is a LEVERAGE
  POINT, carried by a cohort the live order path refuses: the per-position notional cap is a 2%
  minimum-stop-width rule in disguise and B2's new cash rail refuses the rest.
- ⭐ The `drift x T` premise is confirmed a second time, on a different class: mean holding
  period rises **6.4 -> 16.3 -> 21.9 -> 29.0 -> 32.9 sessions** across the buckets.
- ⇒ sec 4.4, sec 12.1, sec 12.2, the cap sweep (plan item 18) and the sigma_R objective all
  close with it, which is exactly what sec 13.8 said would happen "on one afternoon".
- ⚠ The RELABEL question is untouched -- that rests on seven code branch points against a
  paired dR of -0.120, t -1.47, not on stop width. New fact bearing on it: mean T runs 6-33
  sessions against swing's 3.59, so the classes DO differ in realised holding period even
  though their rule sets are not separable by outcome.

Report: `docs/analysis/b5-positional-four-units-2026-09-11.md`, new sec 12.34.
`ruff` + `mypy` clean.


### B4 — the gap guard tests the SPAN, not two hardcoded endpoints (2026-09-11)

`GAP_LO, GAP_HI = date(2020, 12, 23), date(2023, 7, 3)` were constants describing ONE known
incident -- the 922-day hole in `ohlcv_1d` -- which is the shape W5 forbids. Worse, testing
only whether a window's two ENDPOINTS straddled that range said nothing about holes INSIDE
a window: measured, it missed 204 of 16,428 panels (1.2%), worst case 516 sessions inside a
300-row window, with 2,048 of 3,129 names below 95% coverage on the post-gap block.

**Added**
- `market_calendar.observed_session_index()` -- the dates the market actually produced bars
  on, from `ohlcv_1d` itself. ⚠ Deliberately NOT `trading_days_between`, which derives the
  calendar from `nse_holidays` -- measured incomplete for 2019-2020 (7 rows against >=17
  holidays that occurred). A missing holiday reads as a trading day and inflates every span.
  It also needs no holiday table at all, which makes it correct for any exchange later
  ingested.
- `session_span()` -- sessions between two dates inclusive, or **`None`** when either is not
  a session. Not 0, not an exception: 0 would read as "no gap" and silently pass a window
  the guard could not judge, which is the zero-sentinel mistake this codebase keeps finding.
- `window_has_holes()` -- does a `rows`-bar window span materially more than `rows`
  sessions. Fails OPEN on an unassessable span, matching every other overlay here.
- 8 tests, including the case the old guard structurally could not see: both endpoints well
  inside the modern contiguous block, 300 bars across 516 sessions.

**Changed**
- `swing_dependence_probe.py` now calls the guard and the two constants are **deleted**.
  `--clean-only` now means "no holes", a superset of its old meaning. Smoke run reads 1,098
  observed sessions.

**⛔ Fixed after the full-corpus run caught it — the guard shipped with a blind spot**
- The first version tested observed SESSIONS only and flagged **3** trades where the old
  endpoint guard flagged **38**. The reason is structural: during the 922-day hole NOBODY
  has bars, so those dates are absent from the observed calendar entirely and a window
  spanning the gap reads as ~300 sessions for 300 rows -- perfectly contiguous. Only the
  wall clock reveals it (~1,340 calendar days instead of ~440).
  ⭐ **A hole is invisible to exactly the instrument that defines "normal" using the same
  data the hole is missing from.** `window_has_holes` now runs BOTH a session-span and a
  calendar-day test, OR-ed, with a regression test for the blind spot.
- Re-verified on the full corpus: **40 straddling / 145 clean**, against the old guard's
  38 / 147 -- it catches everything the endpoint test caught PLUS two per-name holes it was
  blind to. The gap contrast is +0.1235, SE 0.1400, **t +0.88**: still not significant, so
  no conclusion moves. ⚠ `probe-147` is superseded by `probe-145` (sec 16.1d).
- ⚠ Two test fixtures had to be fixed too: they used consecutive CALENDAR days as a session
  calendar, which is not what one looks like.

**⚠ Blocked, and recorded rather than worked around**
- BUILD_QUEUE B4 also names `run_single_stock`'s bar-50 walk, which has no guard at all.
  That function lives in `app/backtest/engine.py`, which is **FROZEN**: wiring it needs
  explicit sign-off, a §8 regression and regenerated Rust oracle fixtures in the same
  commit. Left untouched.
- `positional_probe.py` has no gap guard to replace; it gets one as part of B5, which is
  already adding the paired-basket columns to the same file.


### B1 — the two undeclared display filters are removed, not declared (2026-09-11)

`GET /signals/active` dropped near-expiry and choppy-regime signals by default. Neither rule
was in `restrictions.py` -- the registry whose docstring calls itself the single source of
truth for tradability -- neither was applied by the order path, and neither was applied by
the research corpus. A signal the listing hid would still have been ACCEPTED by
`place_order`. That is display/order drift in the OPPOSITE direction from the one fixed on
2026-09-02 (display too permissive, 41 of 204 rows showing a Buy button that could only
409); this one was display too RESTRICTIVE, and it narrowed the offered set along two axes
no estimand accounted for.

**Removed**
- The `include_expiring` and `include_choppy` query params and the two filter applications.
  Deleted rather than declared because the choppy half was MEASURED first: splitting 185
  resolved trades at the deployed ER < 0.30 threshold gives a contrast of -0.0001R,
  **t = -0.00, p = 0.999**, while the filter was hiding **67%** of the offered set. On the
  clean tradeable cell its sign is wrong (the hidden cohort reads +0.18R better, ns). It
  was selecting nothing and costing two-thirds of the list.

**Unchanged, and this is why nothing is lost**
- `near_expiry`, `choppy` and `regime_er` still ride on every row, so the UI flags, sorts
  and styles on both exactly as before. Standing law: **flag, never hide** -- the same one
  that keeps eligibility-blocked rows listed with a disabled Buy instead of dropping them.

**Frontend**
- The Dashboard's two checkboxes became CLIENT-SIDE focus filters with the opposite sense
  ("Hide near-expiry", "Hide choppy", both default off). They were about to become dead
  controls, which is worse than removing them. Filtering on data already in the payload is
  also strictly better: toggling no longer refetches, so it dropped out of the query key.
- `signalsApi.getActive` lost the two dead params; `OpportunitiesTable` lost its now-
  redundant `includeExpiring: true`.

Backend: `ruff` + `mypy` clean; `test_signals.py` 18, `test_eligibility_preview.py` +
`test_confidence_explain.py` + `test_signal_task_sizing.py` 49 passed. Frontend: `tsc`
clean, `eslint` clean, **428 tests passed**.


### B3 — the tick grid becomes a dated schedule, not one constant (2026-09-11)

`paper_tick_size` was a single global 0.05 and the market has had two grids since mid-2024.
`_round_tick` snapped every simulated fill and mark to it, always adversely -- the correct
contract on the wrong grid. On a Rs39 share that is ~10 bps of round-trip rounding the
market does not levy: ~0.051R at a 2% stop, about 40% of the real 25.5 bps charge stack,
and concentrated on exactly the cheap tight-stop cohort the corpus is full of.

**Added**
- `app/broker/tick_schedule.py` -- the grid as a table of `(valid_from, price_lo, price_hi,
  tick, source)` rows, newest-first, each carrying the evidence for its own row. A schedule
  is externally owned and has already changed inside our data window, so hardcoding the
  current state as `0.01 if price < 250 else 0.05` is the shape W5 forbids.
- `paper_broker._tick_for()` -- owns only the override and the "what day is it" question;
  defaults `as_of` to today IST, which is right for every current call site.
- 15 tests including the stated acceptance criterion (Rs39 on 0.01, Rs2500 on 0.05, adverse
  contract preserved on both) and a canary that no >=Rs225 fill moves.

**Measured (the source for every schedule row, from `ohlcv_1d` itself)**
- Share of daily closes sitting exactly on a Rs0.05 multiple, sub-Rs250: 96-98% through
  2020, 84-88% mid-2023 to 2024-05, **38.98% in 2024-06**, then 20.8-23.3% from 2024-07
  onward. The >=Rs250 band never moved (94-97% throughout). A population fully on Rs0.01
  lands on Rs0.05 about 20% of the time by chance, so the post-change sub-Rs250 figure IS
  the chance rate. The change took effect during June 2024.
- ⚠ The boundary is a ZONE, not a cliff: post-transition the Rs225-250 band is 39.3% on
  Rs0.05, Rs250-275 is 66.5%, Rs275-300 is 84.0%, and only Rs300+ is fully Rs0.05. That is
  what you get when the tick is a property of the INSTRUMENT, assigned at a periodic review
  and sticky afterwards, rather than a function of the current price. **So the boundary is
  set at Rs225, the low end of the mixed zone** -- assuming the coarser grid there can
  over-charge a name that is really on Rs0.01 but can never under-charge one that is really
  on Rs0.05, which is the module's contract. A sharp Rs250 cut would hand out
  better-than-reality fills across roughly a third of that zone.

**Changed**
- `paper_tick_size` default 0.05 -> **0.0, which now means "use the schedule"**. A positive
  value forces a flat grid (tests, historical pinning); negative disables rounding, which
  nothing ships with. `.env.example` documented in the same commit.

⚠ Blast radius, stated because it was overstated once: `_round_tick` is called from
`paper_broker` and nowhere else -- not the research probes, not the backtest engine -- and
`positions` is empty, so this contaminated no published research number. It is a
before-cycle-2 correctness fix to the simulator, not a restatement of history.

⚠ The `valid_from` dates are DERIVED FROM OUR OWN DATA, correct to the month, not read off
a circular. If the published NSE/SEBI effective date is confirmed, replace the date and the
`source` string together.

`ruff` + `mypy` clean; `tests/test_tick_schedule.py` 15 passed; the money-path regression
(`-k "paper or fill or broker or order or trading or risk or fee or cost"`) **520 passed**.


### B2 — the aggregate cash rail, which did not exist (2026-09-11)

First item of the B-queue (`docs/BUILD_QUEUE.md`), and the only one where real money was at
stake. The per-position notional cap bounds ONE trade against capital; nothing bounded the
SUM. Three slots at the median 5% swing stop need ~120% of capital and all three returned
201. It enforces an identity -- a delivery account cannot deploy money it does not have --
so it carries no forward-evidence bar.

**Added**
- `risk_engine.cash_cap_reason()` and `RULE_CASH_CAP`, declared in `SIZING_RULES` between
  the per-position notional cap and the concentration/risk rails: both answer "can the
  account hold this" at two scales, and both must settle before rules that assume the
  money exists.
- `OpenHeat.notional` -- the cash actually deployed, computed from the same open-positions
  read rather than a second query. Notional accrues for every open position including
  those whose RISK is unmeasurable: a stopless position still consumes cash, so unlike the
  heat cap this rail has no fail-closed branch.
- `cash_cap_mode` (off/shadow/active, default **off**) and `cash_cap_leverage` (1.0 =
  strictly cash-and-carry), plus `.env.example` documentation in the same commit.
- Nine tests, including the stated acceptance criterion: three slots at the median 5% stop
  are refused at exactly the 120%-of-capital figure the finding reported.

**Changed**
- `check_sizing` now evaluates its three moded portfolio rails through one table rather
  than three copy-pasted deny-or-stamp blocks. Same order, same stamps, same behaviour;
  ruff's complexity limit is what forced the extraction and the result is shorter.

**Fixed (caught by its own test before shipping)**
- The first draft netted the position being topped up out of the held notional. `qty` at
  every call site is the INCREMENT, not the resulting size, so the netting double-
  discounted and would have let a repeat entry deploy cash the account did not have. The
  regression test is built so the per-position cap passes and only the aggregate rail can
  refuse, otherwise it would pass for the wrong reason.

Default is `off`: cycle 1 runs ~25 concurrent positions by design and an enforced rail
would truncate the evidence the programme is accruing. It flips `active` at the cycle-2
reset alongside the heat and position-count caps. `ruff`, `mypy` and
`tests/test_risk_engine.py` (50) green.


### Round 10 — a prediction hit to four decimals, and died the same session (2026-09-11)

The park-and-build ruling went to four sources; all four endorsed it. One made a falsifiable numeric
prediction from our own published rows, and testing what it implied killed the actionable version of
it within the hour. Zero new scoring walks: every number came off round 9's `--dump-trades` artifact
plus one basket rebuild. Adjudication sec 12.33, process sec 13.12, ledger sec 18.6.

**Added**
- `docs/BUILD_QUEUE.md` — the only operational document, created on ChatGPT's round-10 diagnosis that
  a 5,900-line adjudication is an excellent forensic archive and a dangerous specification. Per item:
  WHY / SCOPE / FILES / ACCEPTANCE / ARTIFACT / DO NOT, plus the parked register and five probe
  conventions. Its `CURRENT_SYSTEM_CONTRACT.md` was declined on W2 grounds -- CLAUDE.md plus
  .claude/rules/ already are that document.
- `docs/analysis/round10-cells-2026-09-11.md` — the measurement record.

**Measured**
- The BUY-SELL matched-basket contrast, predicted at -0.74% / SE 0.31 / t -2.4 and measured at
  **-0.7413% / SE 0.2914 / t -2.54 / p 0.011**, clustered -2.06, surviving the gap filter
  (clean -0.8556, t -2.59). First contrast in ten rounds with |t| > 2 on both samples.
- Decomposition: **88% of the BUY book's gross loss is tape, not alpha** (raw -0.1877% = tape
  -0.1659% + alpha -0.0218%); the SELL book rides a +0.58% tape and gives back -1.01% in alpha.
- The Wald check: on the full book `mean(bench) = drift x mean(T)` to ratio 1.00, and the deviation
  is entirely directional -- so the paired benchmark carries no exit-selection bias and sec 12.31c's
  alpha is confirmed as a genuine measurement.
- The counter-timing has **no observable antecedent**: BUY vs SELL trailing basket at entry gives
  t = +0.50 / -0.88 / +0.29 at 5/10/20 sessions, and the one bridging mechanism (basket mean
  reversion, t -2.14) explains 3% of the gap. Recorded, not acted on.
- The market-regime overlay was never gated on `index_ohlcv_1d`: the equal-weight basket is the
  better proxy, and conditioning BUY alpha on pre-entry tape does not separate (best cell t = +1.66).
  A parked item retired for free.

**Process**
- Queue entry rule: converged across sources OR settled by our own measurement, never consensus
  alone. Unanimous panel agreement has been wrong repeatedly; the best items each came from one
  source.
- B2 moves first (the only item where real money is at stake); B7 retires a parked row; B8 is
  timeboxed to one append-only table in one day.
- Rejected as forbidden, not parked: "deactivate the dead factors". `app/analysis/` is frozen and
  `docs/SIGNAL_ENGINE.md` is hook-protected; sec 12.32 is a finding to record, not a licence to edit.

Docs only. No code, no gate, no knob, no recorded number, no clock.


### Round 9 — E3 was run, the paired null refuted our own alpha, and the panel is closed (2026-09-11)

Five responses to §17b's standing invitation (*run one of E1/E2/E3, or refute a §16.1 row*),
adjudicated against code, queries and — for the first time — **a probe that shipped with the round**.
Seven of roughly seventy points changed a decision, and all seven came from a claim a probe could
test. Adjudication §12.24–§12.30, measurements §12.31, plan §13.9, ledger §13i, card §16.1c,
closure §17c of `docs/analysis/quant-panel-adjudication-2026-09-10.md`.

**Added**
- `backend/scripts/swing_dependence_probe.py` — four new per-trade column families, all read-only and
  all computed from the frozen scorer's own output: the **holding period `T`**; the **paired
  matched-window basket return** (`bench`/`excess`) over each trade's actual entry-to-exit window;
  the entry-day **Kaufman ER**; and the **confidence-normalizer decomposition** (`wsum`, `nsc`,
  `wsc`, `top`). Plus `--dump-trades <csv>`, which writes the per-trade table before the report
  sections so one expensive pass serves every downstream cell.
- `backend/scripts/round9_cells.py` — reads that artifact and emits E3 in five units with four SE
  flavours, the stop-width family with `drift x T` isolated, the paired drift null, the rupee-day
  table under both aggregations, the `choppy` filter as a selector, the four rival ranking keys, and
  the posterior against three hurdles.

**Measured (all new, all read-only)**
- **Mean holding period is 3.59 sessions**, median 5, with 14.6% of trades exiting in the same
  session. It had never been emitted, and every per-day and fixed-horizon statement in the record
  was conditional on it.
- **E3** — `clean x BUY x w >= 2%`, n=49: gross -0.1212R (t -1.26), net -0.1772R (t -1.84) on
  explicit charges, -0.2432R (t -2.52) at 15 bps/leg. Date-clustered SEs move every t by <= 0.06.
- **The paired basket over the tradeable book's own windows is NEGATIVE** (-0.166% BUY, -0.338% E3),
  so gross paired excess is -0.0218%, **t = -0.07** — the book's gross loss is when it trades plus
  cost, not what it picks.
- **Per rupee-day deployed the tradeable book underperforms holding the universe it selects from by
  19-56 pp/yr** (30-63 on the reachable cell) net of explicit charges; 39-90 with 15 bps/leg.
- The stop-width contrast decays and flips sign as each mechanical term is removed: R -0.386
  (t -1.55) -> raw % -0.262 (t -0.78) -> excess vs the matched basket +0.069 (t +0.17), with
  `d(T)/dw = +0.384, t = +6.69`.
- Two hypotheses refuted: the confidence normalizer (all four rival ranking keys rho ~ 0, every
  p > 0.46) and the undeclared `choppy` display filter as a selector (contrast -0.0001, p = 0.999,
  while hiding 67% of the offered set).

**Withdrawn / corrected in place**
- **Sec 12.20a's "the correct null roughly doubles the deficit" (alpha = -0.137R...-0.172R)** — it
  subtracted a drift measured on 789 post-gap sessions, at an assumed 5-session horizon, from trades
  occupying different sessions. New mechanical rule recorded: *a benchmark measured over one set of
  sessions may not be subtracted from a return measured over a different set.*
- **Sec 16.1b's net-cost row (`t = -2.19`)** — the right number for the wrong cohort; it includes
  sub-2% stops the live order path refuses. The verdict re-derives at -1.84 on the correct cell.
- **Sec 12.18f's "independence is measured"** — `t = +1.07` is a non-rejection, and about a quarter
  of that slope is the `drift x T` term.
- **Sec 12.19b's tick-bug blast radius** — `_round_tick` exists only in `paper_broker.py` (three call
  sites) and `positions` = 0, so the bug contaminates no number in the document; and the artifact is
  the 0.051R excess over the true grid, not the 0.064R total.
- Duplicate `12.18f` section headings disambiguated to `12.18f-C7` and `12.18f-C5`.

**Also measured — the factor inventory, read from the frozen scorer (487 real panels)**
- 26 registry entries, not the 15 every review document says: the candlestick detectors are separate
  `FactorResult`s and `_best_pattern_factor` selects at most one per panel. Declared weight 325; the
  mean weight that actually SCORES per panel is 30.6, or 9.4%.
- Three factors never score at all: `DOW_TREND` (weight 20, the heaviest — reconfirming the standing
  finding that it cannot score on a 20-bar lookback with swing_n=5), `MARUBOZU`, and `FII_DII_FLOW`
  (dead because `fii_dii_daily` holds 4 rows).
- That last one removes a blocker two reviewers built verification packages around: the only
  non-price term is already inert on live panels, so E2 can test the shipped scorer rather than a
  labelled "price-only variant".
- Four factors carry nearly every scoring event (PRICE_VS_EMA 70%, ADX 46%, MACD_HISTOGRAM 43%,
  RSI_LEVEL 36%) and two of the top three are EMA-derived, so effective dimensionality is plausibly
  2-3 rather than 15 — which downgrades the requested factor-correlation matrix to confirmatory.

**Documented**
- New sec 13.10: the decided build queue B1-B8 with acceptance criteria per item.
- New sec 13.11: what is parked, each row labelled BLOCKED / UNCONVERGED / SEQUENCED with the
  specific reason, so a parked item is distinguishable from a dropped one.
- New PART VI (sec 18.1-18.5): every question every panel source asked, answered per source, each
  answer pointing at a measured number or a numbered build.

No gate, no knob, no recorded number and no clock were touched. `mypy app/ scripts/` green.


### Round 8 — an external audit recomputed round 7 and withdrew five of its claims (2026-09-11)

Three round-8 responses to `docs/analysis/quant-panel-adjudication-2026-09-10.md`, adjudicated one at
a time against code, queries and arithmetic. One of them (`~/Downloads/round8-external-audit-2026-09-11.md`,
727 lines) is the first review in eight rounds to arrive as a reproducible recomputation rather than a
reading; every number in it was re-derived here before adjudication and 11 of 13 reproduce exactly.
Read-only throughout — no gate, no knob, no recorded number, no clock. `make typecheck` green.

**Five round-7 claims withdrawn, all five ours.** Both round-7 "inversions" were decompositions rather
than findings: the level in each half of a small sample was reported and the contrast was never
computed. BUY-vs-SELL is +0.0893, SE 0.1325, t = +0.67, p = 0.50; clean-vs-straddling is +0.0718,
SE 0.1420, t = +0.51. Neither partition separates, and 0.33 of the 0.52 t-drop from the gap filter is
power loss against only 0.20 from the mean. What survives is structural rather than statistical: a
cash-delivery account cannot hold an overnight short, so 55.7% of the trades are untradeable by
construction, and the reason for preferring the BUY cell was never statistical. The σ_R ladder
0.878 → 1.005 is noise at 0.62 SE by this document's own estimator, and t = 0.82 on a proper
two-sample test. "The evidence base is empty, not negative" is withdrawn: the posterior against the
0.111R net break-even gives P(positive net edge) = 0.4%–5.7% across prior sds from 0.03R to 0.20R,
which is economic closure without statistical closure. Every "MDE" in the document was 1.40× too
small — 2·SE is 50% power, so the honest cell's real MDE is +0.417R. And RVOL's t = +3.67, the only
coefficient in seven rounds to clear the t ≈ 3.6 bar, was an iid-standard-error artifact: under HC3 it
is +0.61 and date-clustered +0.98, because HC3 inflates its SE six-fold and 185 trades sit on only 92
entry dates while RVOL is a market-wide daily quantity.

**The one place round 8 made the picture sharper.** Friction is 1/w, so by Jensen the expected
cost-in-R is strictly greater than the cost at the median stop. Measured on the swing sample:
E[cost] = 0.1522R against the 0.0549R scalar, a 2.77× understatement on the unrestricted corpus — and
the scalar is correct for the live-reachable w ≥ 2% book at 0.0573R. Costed per trade instead of by a
scalar, the tradeable book reads −0.2435R at t = −2.19 on explicit charges alone and −0.4134R at
t = −3.31 with the slippage assumption. The gross question is underpowered; the net question is
answered.

**The stop-width family is closed on the swing sample.** Simulating the pure 1/w term with raw return
independent of stop width reproduces 116% of the measured tight-vs-wide spread (−0.4470 predicted
against −0.3864 observed), the independence is itself measured at t = +1.07, and the contrast was
never significant (t = −1.55). §4.4's wide-stop gradient, §12.1's reachable-cohort sign flip and
§12.2's dispersion lever are one artifact of dividing by a small number. The positional members remain
unmeasured and are now plan item E1.

**Three findings that were in no review, all from verifying the audit.** The equity-beta null is
computable from `ohlcv_1d` alone and had just been declared blocked on `index_ohlcv_1d`: an
equal-weight basket of the eligible universe gives 789 sessions at +0.0816%/day, t +2.06, +22.8%
annualised, so a 5-session hold's null is +0.088R and the honest cell reads α = −0.137R to −0.172R,
roughly double the raw deficit. `paper_tick_size` is a single global constant of ₹0.05 while NSE moved
sub-₹250 securities to a ₹0.01 tick — the on-₹0.05 fraction for those names fell from 0.98 in 2019 to
0.49 in 2024 and 0.22 in 2025 while nothing above ₹250 changed — so `_round_tick`, which always rounds
adversely, charges a ₹39 name about 10 bps of round-trip rounding the market does not, or 0.064R at a
2% stop, on exactly the cheap-tight-stop cohort the remaining results are built on. And the gap guard
shipped in round 7 tests two hardcoded endpoints rather than the span: there is a second, per-name
hole (790 post-gap sessions against a median 620 bars per name and a p10 of 67, with 2,048 of 3,129
names below 95% coverage), and the guard misses 1.2% of panels whose 300-row window spans up to 516
sessions.

**And the answer to the question that started the exercise, from the code.** `signals.py:267-289`
builds the offered set by deduping on confidence, filtering by two undeclared rules that default on
and appear neither in `restrictions.py` nor on the order path (`_near_expiry`, and `_choppy` at
Kaufman ER < 0.30), then sorting descending by `confidence_pct`. The deployed picker's ranking key is
therefore `confidence_pct`, which R7-B measures at Spearman ρ = −0.018 on a test powered to detect
0.147. The quantity the UI sorts by carries no measured information about outcome.

**Two structural reads adopted.** ρ̄ is flat in slot count under a one-factor model, which refutes the
round-7 question that asked whether it rises, and hold period is a bigger breadth lever than slot
count — nine slots at three-day holds gives 298 effective observations a year against 109 today — so
the 2021–2023 back-fill is dropped and the lever is turnover. And §4.5 applied `IR ≈ IC√BR`, a
portfolio law, to a gated tail selector; at the correct transfer an IC of 0.02 is roughly break-even
per trade and 0.04 comfortably positive, making §4.5's "not investable" a turnover diagnosis rather
than a signal-quality one. At the honest σ, validating on the live book is decade-scale again: 1,198
trades, about 9.6 years, for a Sharpe-1.0 net edge.

**Changed:** `backend/scripts/swing_dependence_probe.py` — HC3 and date-clustered sandwich estimators
in `ols_multi` (printed beside iid for every regression from now on), the two splits as interaction
tests, the per-trade cost-in-R distribution, the mechanical 1/w simulation, MDE at 80% power, and a
third outcome unit. `docs/analysis/quant-panel-adjudication-2026-09-10.md` → 4,500 lines with new
§12.18–§12.23, §13.8, §13h, §16.1b and §17b. `docs/PHASES.md` top block and CONTINUE HERE re-written.

### Round 7 of the quant panel — the headline inverts, and `ohlcv_1d` has a 922-day hole (2026-09-11)

Four external reviews (Claude · ChatGPT · Gemini · Kimi) of
`docs/analysis/quant-panel-adjudication-2026-09-10.md`, adjudicated point by point against code,
queries and arithmetic rather than taken on anyone's word. **37 points: 21 taken, 8 refined, 8
rejected on evidence.** Read-only throughout — the frozen engine, `SIGNAL_ENGINE.md`, every gate mode
and every knob are untouched, no recorded number moved, no clock reset.

**The headline, divided by direction — all four reviewers led with it and it had been an unrun plan
item since round 1.** Round 6's *"significantly negative gross edge, t = −2.31"* is carried by the
half a cash-delivery account cannot hold overnight: **BUY-only n=82, mean −0.0992R, t = −0.94** vs
SELL n=103, −0.1885R, t = −2.36. The tradeable book is not distinguishable from zero, negative in
expectation — a materially different verdict, and it changes what KILL LINE 3 firing would mean.

**`ohlcv_1d` has a 922-day hole: 2020-12-23 → 2023-07-03.** 1,097 sessions exist, not the ~1,730 a
2019-10 → 2026-09 span implies, and **33.2% of round 6's 16,428 panels were scored on a 300-bar
window straddling it** — EMA200, ATR, ADX and every pivot computed across a 2.5-year discontinuity.
It explains `_CLEAN_SINCE = 2023-07-03`, which three documents describe as a corporate-action choice
and which is simply the first date of the contiguous modern block. It **kills plan item #2**: the real
un-truncation yield is n ≈ 2,662 on the corpus's bar-50 walk and **exactly zero** at a 300-bar window,
against the 4,300 the plan's MDE rested on, and the blocker was never the CA source but **615 missing
sessions**. On gap-clean windows alone the headline falls to t = −1.79 — a second, independent reason
it is not robust. Standing rule earned: **a span is not a span until the session count is queried.**

**Three round-6 conclusions corrected by measurement.** ρ̄ ≈ 0 was a directional-cancellation
artifact — long-only, variance inflation is 1.19–1.23× (ρ̄ ≈ +0.19), so ₹3L buys ×1.63 effective
observations and Kimi's stress case turned out to be the real case. §12.10a's *"the corpus detects an
edge below friction, with room to spare"* is withdrawn: on the long-only book the MDE is +0.0714R,
above the 0.051R of explicit charges, and the margin against a Sharpe-1.0 edge is 1.3×, not 4×.
Δ_select, re-run as a continuous rank statistic on all 185 trades, gives ρ = −0.018 at permutation
p = 0.807 with power to detect ρ ≈ 0.147 — the same answer the decile contrast gave, now properly
powered, after Claude showed that contrast had an MDE of +0.31R.

**Two structural repairs.** KILL LINE 3 splits into **3a (strategy closure)** and **3b (feature-family
closure)**, because ChatGPT, Claude and Kimi converged from three unrelated directions on the same
defect: a line keyed to total strategy R cannot declare the death of the scorer when the classifier,
the level stage (−60.8%), the geometry, the horizon and the fill model sit between them. And
**`Σ notional ≤ available cash` does not exist anywhere in the code** — three slots at the median 5%
stop need 120% of capital and nothing notices. It is the first new risk rail any of 25 reviews has
produced, enforces an identity so it needs no forward-evidence bar, and is a precondition for cycle 2
rather than an enhancement.

**The best new finding is Claude's and it is the only breadth lever left.** The level stage discards
289 of 475 gate-passing swing panels and has never been evaluated as a selector. Re-simulated with
fallback stops on identical panels, the discarded cohort outperforms the kept cohort by **+0.16R**
(paired by entry date: t = +1.43 at a flat 5% stop, +1.54 at 2×ATR20, with the wider stops the
mechanism predicts). Not significant — the MDE is +0.22R, which is stated in the section rather than
buried — but it is +288 trades available today with no data blocker, larger in magnitude than the
entire deficit under investigation, and it is 3b's first test.

**Gemini's one control variable did more than any other point in the round.** Asked whether the
stop-width gradient is an ATR proxy: its own hypothesis was refuted (ATR% t = −0.43, gradient intact
at +0.063), one of our own findings was partially refuted (the gradient is t +2.30 in R and **+1.07
in raw %**, +1.06 long-only, so the 2026-08-25 stop-width result is substantially a denominator
effect), and it surfaced `RVOL-20` at **t = +3.67**, the only coefficient in seven rounds to clear
this project's own t ≈ 3.6 bar — which round 6's own rule then disqualified, because in raw return %
it is t = −0.28 and D1 refuted RVOL as a generator at t = −2.91. Recorded, not promoted.

**And then the honest cell, which corrected three of the above.** Crossing the gap guard with the
direction split — clean windows × long only — gives **n = 61, mean −0.0843R, t = −0.66, σ_R 1.0050,
MDE +0.29R: uninformative.** σ_R rises monotonically as the population is restricted to the honest
one (0.878 → 0.911 → 0.957 → 1.005), halfway back to the corpus's back-derived 1.489, and the
variance inflation rises with it to 1.24–1.43×. **Claude's Finding D does not survive the filter** —
the paired level-stage contrast falls from +0.16R (t 1.43) to +0.095R (t 0.69) and reverses on the
clean tradeable book — so the structural credit stands (the largest filter in the pipeline is now
measured, and the answer "not anti-selective" closes a suspect) while the effect does not, and plan
item 2′ is downgraded to a cheap sample-enlarger. **The Kelly interval claim is withdrawn**: on the
clean BUY book the interval includes zero, though `f* = 0.0000` exactly holds in every cell and
Claude's prediction about the upper end was right. **The stop-width gradient collapses and flips
sign** — t +2.30 all-windows, +1.06 clean, negative on clean × BUY — so the 2026-08-25 stop-width
finding survives neither the unit change nor the gap filter. What got stronger is `RVOL-20`, robust
to the filter at t +3.65 and +3.13 and still t −0.36 in raw %: only the unit kills it.

**The process lesson is recorded permanently in the ledger.** Four measurements were published before
the `--clean-only` variant of the guard built in the same round had been run, and it then corrected
three of them. **A guard is not adopted until every number in the same document has been re-run
through it.**

**Governance.** `§16.1` now carries a `sample` and a `verified` column per row with one mechanical
rule: **no formula may combine two quantities whose sample tags differ.** The document has committed
that error five times; Claude found the fifth and Kimi committed it in the same round while
diagnosing a different one. One regression table in this round was drafted from expectation before
its run finished — caught and deleted before it entered the document, and recorded permanently in the
round-7 ledger.

**Changed:** `backend/scripts/swing_dependence_probe.py` extended (read-only, SELECT-only, frozen
scorer and frozen `_simulate_trade` imported and called, not reimplemented) with the direction split,
a continuous Δ_select, the level-stage reject simulation, portfolio-space dependence, empirical
Kelly, the winsorization audit, a `--clean-only` gap guard and the multivariate regression.
`docs/analysis/quant-panel-adjudication-2026-09-10.md` → 3,320 lines. `docs/PHASES.md` top block and
CONTINUE HERE queue re-written.

### Per-question answer matrix + three gaps closed (2026-09-11)

An audit of the document against the reviewers' actual question lists found **three answers that had
been reported in conversation but never written into the file**: the full 10d/30d/60d bootstrap table
(now published including the 60-day anomaly at 0.62× on 19 blocks, labelled as under-blocked noise
rather than quietly dropped); the same-sector/cross-sector correlation split, recorded as **blocked**
because sector coverage is 165 of 1,322 and splitting would select on which names happened to get a
label; and whether the 1,975-trade corpus is all signals or gate-passers — **neither, it is three
stages downstream**, with the measured attrition (89 panels and 2.8 gate-passers per trade) given and
the honest note that the corpus's own upstream counts were never recorded.

The brief now carries a **per-question matrix covering all 32**: 24 answered, 4 partial, 3 impossible
or gated with reasons stated, 2 not attempted (Kite's adjustment policy and the end-to-end look-ahead
trace). Nothing is silently dropped.

### Adjudication document rebuilt clean (2026-09-11)

Restructured into five parts (system adjudicated · measurements · plan · round ledgers · governance
and reference) with a navigation map at the top. All round-number and date attribution was stripped
out of headings and left in the bodies where it belongs, the round-2 ledger was moved to sit beside
the round-3/4/5 ledgers, and §8 is marked superseded since the live plan is §13. **Two real defects
fixed:** §15.5/§15.6 had been duplicated by an earlier reorder, and §12.11a/b were out of order.
⚠ Section numbers are deliberately left stable, because several `§N` references point at the other
two review documents and renumbering would silently break them.

### Round-6 answer coverage (2026-09-11)

The adjudication document now opens with a **map** and an **honest answer-coverage matrix**: of round
6's 32 questions, 24 are answered with code, a query or a measurement; 4 partially; 2 are impossible
(the slippage regression, because `orders` and `positions` are empty, and the un-truncated-corpus
dependence, gated on 0a.6); and 2 are not yet attempted (Kite's adjustment policy, and an end-to-end
look-ahead trace). Stale round-N headings were fixed and sections predating §12.10 that lean on the
superseded σ_R = 1.489 or ρ̄ = 0.5 are marked rather than deleted.

**Newly answered:** the Sharpe→per-trade-R derivation (`μ_net = S·σ·√I/√N`, meaningless without N and
I stated — which is why the benchmark moved every round); cycle-2 calibration power (the test
functions to sd(ε) ≈ 0.35R and is dead at 0.5R, so estimating sd(ε) must precede testing the bias);
slippage sensitivity (the assumed 0.06R is 15 bps/leg — report friction-dependent conclusions at
10/15/20 bps until cycle 2 pins it); post-tax rows; and the capital ladder under both policies, which
resolves the §12.9 contradiction — fixed-2%-risk gives 3 slots at every capital, fixed-₹40k-position
gives 3/4/6/9 slots by cutting per-trade risk to 0.67%, **and the latter is available at ₹1L too**.
Fill accounting confirmed (`engine.py:212` fills at the next open; both probes take the R denominator
from the fill price). No ex-date handling exists in the backtest — stops are hit at the raw price.

**Gate provenance partly refutes the in-sample worry:** `confluence.py`, carrying the 70 threshold,
the weights and the ADX schedule, landed 2026-07-03; the first corpus analysis landed 2026-08-12, six
weeks later. The scorer was authored from the spec, not fitted to this data. What is in-sample is
everything after 08-12 — the eight shadow gates and the retune experiments.

### Round-6: the three assumptions measured (2026-09-11) — all three wrong, and the central question was the wrong one

Round 6's reviewers asked for evidence rather than opinion. **New read-only probe**
`backend/scripts/swing_dependence_probe.py` (SELECT-only; the frozen scorer and frozen
`_simulate_trade` imported and called, never reimplemented) walked **16,428 swing panels across 238
liquid names at stride 10** and measured the three inputs every conclusion in rounds 3–5 rested on.

**σ_R: assumed 1.489, measured 0.878** — the 1.489 was back-derived from a t and never measured;
required n falls 65%. **ρ̄: assumed 0.50, measured −0.013** on 263 overlapping pairs. **Variance
inflation: assumed 6.5× (corpus) and 1.75× (live), measured 1.00×** by calendar-block bootstrap at
both 10- and 30-day blocks, agreeing with §12.4's trade-block 1.046×. Three independent measurements
say dependence is nil, exactly as Claude's structural argument predicted — R is a barrier-truncated,
path-dependent transform and truncation compresses correlation. The `1+(m−1)ρ̄` formula appears
nowhere in the codebase; it was a document-level assumption throughout.

**The headline inverts a second time, and detectability stops being the constraint.** With measured
inputs the corpus detects a Sharpe-1.0 system at ×3.28 truncated and ×4.84 un-truncated, and the MDE
(+0.027R to +0.040R) now sits **below** the +0.051R friction floor — so anything that nets positive
is detectable with room to spare. Both "2.8–3.8× short" and "standing on the line" were artifacts of
unmeasured assumptions. ⚠ That makes the next figure worse rather than better: this sample's gross
mean is **−0.1489R, SE 0.0645, t = −2.31**.

**Claude's ratio-estimator finding is confirmed.** The same 185 trades show excess kurtosis **+8.19
in R, −0.25 in raw %, +0.02 in ATR units** — the fat tails are manufactured by our own denominator
(stop-width CV 0.51). Keep R for sizing; report in bps and ATR units.

**Δ_select = +0.045R, SE 0.153, t = +0.29**, and confidence is not monotone in outcome (the 80–84
bucket is the worst in the book). The score's top decile is statistically indistinguishable from the
average gate-passer — the measured answer to the original "I cannot select the right stock".

**Code answers to the reviewers' lists:** §12.4's bootstrap blocked on **8 trades, not days**, so it
could never have detected overlap; `orders.price` and `orders.filled_price` exist but both tables are
empty, so slippage is unmeasurable retrospectively and only cycle 2 can produce it; the three level
call sites share `compute_levels` with a divergent call contract; `backtest/engine.py` calls neither
`fees.py` nor `risk_engine`; there is no tax handling anywhere; and §12.9 contradicts itself on slot
count (3 at every capital versus a 3/4/6/9 ladder — two policies presented as one). Kimi's Kelly
point is confirmed: at p ≈ 0.25 and b ≈ 1, f\* ≈ −0.5, so the corpus's own numbers imply the
growth-optimal live risk is zero. **Nothing was built and no behaviour changed.**
### Reference card + reviewer notes, and two unmeasured inputs (2026-09-11)

**⛔ Two of the three inputs to the headline conclusion are assumptions, not measurements (§15.6).**
Rounds 3–5 all turn on σ_R, ρ̄ and friction. σ_R is measured. **ρ̄ = 0.5 was introduced in round 3 as an
illustrative figure and has been used unchallenged ever since** — it sets the variance inflation
`1 + (m−1)ρ̄`, which drives every effective-n figure, §12.5, §12.8 and the whole capital analysis. At
ρ̄ = 0.3 every MDE improves ~23%; at 0.7 they worsen ~16%. It is one query on the corpus. Friction is
half measured: explicit charges are 0.051R at the median stop against the 0.11R the document uses.
**Both added to the cut as items 10 and 11**, since they feed the two levers §12.5 names as able to
move the answer and are cheaper than anything else on the list.

**⭐ New §16 — reference card and per-reviewer notes** (user instruction; **all five sources stay** by
user ruling). §16.1 fixes the canonical constants with `[measured]` / `[ASSUMED]` marked on each,
because most of the dozen arithmetic disagreements across five rounds came from sources using
different values for the same quantity. §16.2 gives each reviewer an evidence-backed note on its
characteristic failure mode with the specific instances cited — including a narrow, actionable
prescription for the weakest source rather than a recommendation to drop it. §16.3 names the three
things worth attacking next, none of which is this document's internal consistency.

**⭐ §15.5 adds the round-5 rejections with their derivations** so they can be checked rather than
re-argued: ChatGPT's capital table applied the CAS daily-turnover DP figures to the swing book
(11.51%/3.83% against the correct 2.30%/0.77%); Kimi's +6% and Claude's +33% effective-breadth
figures against a measured +20% (75 → 90 effective observations a year); and our own self-rejected
gross-versus-net headline. Nothing was built and no behaviour changed.

### Round-5 adjudication (2026-09-11) — ⛔ the headline ratio was malformed and the conclusion inverts; capital question answered

**The most consequential correction of five rounds, and it is against our own headline.**
`required gross = friction + MDE` includes friction, while a Sharpe ratio is conventionally computed
**net** of costs — so §12.5 compared a gross requirement against a net benchmark, counting friction on
one side only. A second inconsistency was ours alone: N=250 trades/yr for the benchmark against N=125
for the live book's accrual. Consistent gross-vs-gross at ρ̄=0.5, a Sharpe-1.0 book **grosses
+0.189–0.286R against an MDE of +0.116–0.203R** ⇒ **detectable at ×1.11–×1.63.** *"Both classes need
2.8–3.8× a world-class edge"* is wrong; **we are standing on the line.** That changes what the plan is
for — un-truncation, σ_R and friction become decisive rather than merely surviving. The convention is
now stated explicitly (**net**), because a gross reading flips it back to failing by ~8×.

**⛔ Half the friction term is an unmeasured assumption.** Against `roundtrip_charges`, a 5% stop at
₹1L costs 25.5 bps = **0.051R**; §12.5 uses **0.11R**. The missing ~0.06R is a slippage assumption
driving every conclusion — **Week 0 #5 (fee/slippage reconciliation) is restored to the cut**, having
been dropped while friction was named one of only three levers that can move the answer.

**⭐ The CA blocker is an afternoon, not procurement.** Derive the adjustment factors from
**Kite-adjusted ÷ our unadjusted** series: the step in the ratio *is* the factor, on the exact
ex-date, as actually applied — ~1,300 names at 3 req/s ≈ 7 minutes, and strictly better than an event
feed because no reconciliation is needed. FII/DII is likewise a scraping afternoon, so #16 may run on
the shipped composite rather than a price-only variant. **The critical path is unblocked.**

**Sequencing and governance:** 0a.1 (freeze the holdout) is re-ordered to item #1 — it costs nothing,
depends on nothing, and freezing a date is a commitment device rather than a test run. A **programme
sunset** is added: if zero Week-0 items ship by **2026-10-31** the programme closes, with the ledger
archived as the deliverable. KILL LINE 1 is re-scoped from absolute to **comparative** (a gate known
to fire on everything is not a decision rule). A **holdout regime guard** is pre-committed.

**⭐ Capital sensitivity, computed (§12.9).** Slot count is **scale-free** — `slots = heat ÷ risk = 3`
at every capital level, so capital does not buy positions, the risk rules do. Swing friction barely
moves: 25.5 bps at ₹1L against 23.0 bps at ₹3L, about 0.005R/trade. The exception is turnover: DP drag
runs 2.30% → 0.77% of capital for a 5-day swing book but **11.51% → 3.83% for a daily-turnover CAS
book**, so capital helps the microstructure book enormously and the swing book almost not at all.
Power barely moves either: 75 → 90 effective observations a year, **+20%** (rejecting Kimi's +6% and
Claude's +33%). **Adding ₹2L is a friction-and-CAS decision, not a validation or edge decision** — and
if the paired-calibration test shows the corpus-to-live bias is real, more capital loses more at the
same rate. The one qualitative purchase is the F&O door, which at raised SEBI contract values may open
nearer ₹10L than ₹3L. In ₹/day terms, +0.09R/trade is ~₹22k/yr at ₹1L and ~₹67k/yr at ₹3L.

**Rejected:** ChatGPT's capital table (applied the CAS DP figures to the swing book), Kimi's +6%
breadth, Claude's +33% breadth. **Still open:** there is not one chart in 1,634 lines.
**Nothing was built and no behaviour changed.**
### Round-4 adjudication (2026-09-11) — plan cut to eight items, two blocked by empty tables; cycle 2 reframed

Four sources reviewed **one at a time** (user instruction, after ChatGPT was under-credited twice in
earlier rounds). Everything folded into `docs/analysis/quant-panel-adjudication-2026-09-10.md`:
§12.5 corrected, §12.7 and §13d added, and a new **§15 rebuttals-with-evidence**.

**⛔ §12.5's corpus rows used nominal n — the R2-11 failure, committed twice.** The research corpus is
*more* overlapped than the live book (~620 trades/yr at 5-day holds ⇒ m≈12 vs 2–3). Corrected at
ρ̄=0.5: corpus truncated +0.28R, corpus un-truncated +0.23R, live book +0.31R — **the corpus advantage
falls from 3.4× to 1.7×.** And the Sharpe-1.0 benchmark is itself an independence figure: +0.094R
becomes **+0.125R** under the same dependence, so the ratio is 2.52×, not 2.80×.

**⛔ Two plan-blocking data gaps, found by query.** `corporate_actions` holds **0 rows** — the CA
adjustment layer has no event source for any period, so un-truncation is gated behind sourcing one.
`fii_dii_daily` holds **4 rows across 3 days**, and the composite score consumes FII/DII flows
(`confluence.py:121`) plus sector (165/1,322), so **test #16 is infeasible on any window**; a
price-only variant frozen by commit hash is now mandatory and is a different estimand.

**⭐ Cycle 2 is a paired calibration measurement, not merely a rehearsal.** The corpus and the live
book estimate different quantities, so more n converges on the bias. Only the *pair* can measure that
bias: paired backtest-vs-realised R shares signal, name, window and geometry, so sd(ε) ≈ 0.2–0.3R and
SE ≈ 0.05R at n=25 — enough to detect a 0.10R corpus-to-live bias at t=2. Its acceptance criteria are
now recorded, having **dropped silently** from the round-3 ledger.

**⭐ The plan is cut from 29 items to eight**, driven by the four words written in round 3 and not
acted on — *"regardless of their outcome"*: only friction, σ_R and breadth can move the answer.
Plus two afternoons: the BTST/DP ticket (called the most decision-relevant item in the plan, and no
week owned it) and the F&O lot-size check.

**⭐ KILL LINE 3 re-keyed** from IC to cost-adjusted mean R with SESOI = friction, after all three
reviewers noticed it pointed at the estimand the plan itself had demoted four lines earlier. The
|IC| = 0.02 margin was below break-even (the transfer `IC × σ_cs × E[z]` gives 0.018–0.071);
Gemini's proposed replacement was rejected as dimensionally unsound and 4–100× too permissive.

**⭐ New §15 — rebuttals with evidence** (user instruction): every claim rejected across four rounds,
with the code line, query result or arithmetic that refutes it **and what would change my mind**, so
rejections can be checked rather than re-argued. Standing rule recorded: *a claim about the data
plane is a question, not a finding, until someone runs the SQL* — four rounds, four occasions.

**Credit corrections:** the σ_R lever and the capital-scaling question both originated with ChatGPT
in **round 1** and were rediscovered and credited elsewhere in rounds 3–4. Kimi's round-4 headline
was arithmetically wrong (bootstrap SE is 1.046× iid, not 2× — it compared an MDE to an SE) but its
**conclusion was right**, reached correctly by Claude via concurrency: *a conclusion can survive its
own broken derivation.* **Nothing was built and no behaviour changed.**
### Corpus un-truncation + round-4 brief (2026-09-11) — ⭐ two required-edge numbers, and the corpus is truncated for two dead reasons

Found while briefing round 4, and it corrects §12.5's own table. **§12.5 solved for the wrong n.**
It used the live book's accrual rate (~125 trades/yr ⇒ +0.264R required gross), but the research
corpus runs at **619 trades/yr** (1,975 trades over 3.19 years) ⇒ **+0.177R truncated, +0.155R
un-truncated**. ⭐ That distinction resolves the ₹1-lakh tension instead of restating it: **the corpus
can detect an edge the live book never can, so all validation belongs on the corpus and the live book
confirms operational correctness only** — §4.1's cycle-2 conclusion generalised to the programme.

⭐ **The swing corpus starts 2023-07-03 for two reasons that are both dead:** `ohlcv_1d` once began
there (a hard blocker **resolved 2026-09-08**, three days before the corpus was reported, when the
bhavcopy acquisition reached 2019-10-01), and it was described as "the CA-clean window", a claim
already recorded as **false**. Un-truncating takes the corpus from **1,975 to ~4,300 trades** using
data already in the table — new **Week 0a #6**, which must run *before* the holdout.

⚠ **It also defuses a collision between two round-3 recommendations that no reviewer could see:** a
2024-01 holdout against the truncated corpus leaves a **six-month** development set. Against the
un-truncated corpus: dev n≈2,631 (MDE +0.058R), holdout n≈1,665 (MDE +0.073R). Un-truncation spans
the COVID crash and the 2020–21 melt-up, so it must land with the CA layer and the regime split.

A **▶ BRIEF FOR ROUND 4** now heads the adjudication document: what is settled and must not be
re-opened, the four questions genuinely worth attacking, and a note that reviewers cannot inspect the
data plane from prose — three rounds have guessed at survivorship, CA coverage and universe
construction, and each time the answer required a query.

### Round-3 adjudication (2026-09-11) — ⛔ my own kill lines were broken three ways; stop reviewing, start shipping

Round 3 (Claude · Kimi · ChatGPT; Gemini returned nothing) audited **the adjudication's own
statistics** rather than the system's, and found the round-2 headline improvement — the kill lines —
unusable as written. All three defects verified by arithmetic; repairs and the round-3 ledger are in
`docs/analysis/quant-panel-adjudication-2026-09-10.md` §12.5, §12.6, §13a, §13b, §13c.

**The three broken lines.** **KILL LINE 4 was unpassable** — at n=271, σ_R=1.844 the MDE at t=2 is
+0.224R, so "gross > +0.15R *and* interval excluding zero" silently demanded ≥0.224R (a true +0.15R
yields t=1.34); on the deciding swing cells MDE is 0.149–0.211R, at or above the threshold under
test. Repair: publish the MDE per cell in the pre-registration and label sub-powered cells
decorative. **KILL LINE 3 had two defects** — it could not fire (80 intervals, `P(≥1 exclusion | all
null)` = 0.9998) and would have been unsound if it had (power ~0 at t 2.6–3.5). Repair: one primary
endpoint, commit-hash frozen, TOST equivalence against a pre-specified SESOI, and statistical
closure separated from economic closure. **DECISION LINE 6 optimised σ alone** when required n is
(σ/μ)² and a constant-R:R target lowers both. Repair: the criterion is σ/|μ| or n.

**⭐ The synthesis, and the best number of all three rounds:** required gross edge = friction(w) +
MDE over the wait ⇒ **swing +0.264R, positional +0.355R against +0.094R from a Sharpe-1.0 system**.
Both classes need 2.8×/3.8× a world-class edge merely for it to be visible within three years. It
supersedes KILL LINE 1 and reconciles the four thresholds the document had accumulated. And it is
optimistic: effective breadth was accepted in round 2 and never propagated — at 2.5 concurrent
positions with ρ̄ 0.5 the variance inflates 1.75× (7.1 → 12.4 years); at cycle-1's 23 positions, 12×
⇒ ~85 years.

**⭐ Survivorship — three reviewers named the disease and all three named the wrong organ.**
Measured: `stocks` holds **3,392** rows with **2,070 inactive retained** and **542** price series
that die mid-history, so the database can see the losers. **The bias is in our own universe
selector:** `positional_probe.py:92` and `engine_selectivity_probe.py:106` both require bars in the
last 180 days (excluding all 542 dead names) and then rank by *today's* liquidity, applying that
top-250 to 2019–2026 — survivorship plus look-ahead, in one query, in both probes.
`squeeze_study.py:65` is explicitly survivor-only. `factor_sweep.py` is clean on this axis. One query
to fix, not a data-acquisition project; bias direction upward, so every historical figure is
flattered.

**New Week 0a, to run before any Week-2 test is designed:** freeze a 2024-01+ **holdout** (deflation
cannot deflate a trial count nobody recorded, and three rounds of reviewers on one window is exactly
that) · repair harness **defect #4** as a `FROZEN-CONTRACT` fix and re-baseline (nine "decisive
tests" would otherwise run through an exit ledger wrong in the direction that biases the variable
under study) · fix the universe query · **backfill index/VIX** · commit hash on every ledger row ·
**readiness gating rather than calendar gating**.

**Also taken:** the `>25%` CA filter demoted to an ingestion alarm (it drops exactly the moves a
multibagger factor exists to catch); both nulls refined; **IC demoted from "the decisive test"** —
wrong question for a gated system and for a sparse event signal, so three estimands are reported and
conditional economic effect now outranks it; **capital-time economics added** (the account earns
₹/day, not R). **Answered rather than deferred:** the reachable-cohort flip is a domain restriction
not survivorship; **never compare a harness number to an analytic null** — run both arms through the
same harness so its biases cancel; "breadth from time" is not breadth (observations ≠ bets), so the
DP/BTST ticket becomes the most decision-relevant item in the plan; delete the positional relabel
rather than merging corpora (pooling different-σ populations lowers power). **"₹1L is not
validatable" softened** — the constraint is execution-economic, not statistical.

**⭐ §13c — the recommendation: stop the review cycle.** Three rounds, thirteen reviews, a
1,088-line document, **zero Week-0 items shipped.** Round 3 paid for itself only because it audited
the plan's own arithmetic; what remains unexamined is the data plane, which no reviewer can inspect
from prose. **Nothing was built and no behaviour changed** — the next artifact should be a shipped
Week-0a item.
### Round-2 adjudication + revised plan with kill lines (2026-09-11) — ⭐ the corpus contains trades live would refuse, and the sign flips

The 2026-09-10 adjudication was handed back to four reviewers together with the ten round-1
reviews. **Round 2 landed three direct hits on our own document**, all verified against code or a
read-only query, and they are stamped in place in
`docs/analysis/quant-panel-adjudication-2026-09-10.md` (§3.1, §4.2, §4.4, §7, §0) beside a
35-row taken/refined/rejected scoreboard (§10) and a revised plan (§13).

**The three hits.** (1) **§4.4's "three independent lines" was one variable measured twice** —
`risk.py:101,111` make the targets flat 6%/15%, so **R:R = 6/w and 15/w identically**; "R:R < 1"
and "wide stop" are the same variable, and the R:R-revert cohort's 7.29% average stop *was* the
wide-stop finding rather than corroboration of it. (2) **§3.1's counter-evidence is itself
CA-contaminated** — `scripts/factor_sweep.py` has **no corporate-action filter at all**, computing
features *and* labels on unadjusted prices, so ~5.8% of its 212,129 observations carry grossly
wrong values against a target IC of 0.02–0.04. It therefore does **not** license "no
cross-sectional IC exists"; **the ranker question is reopened.** (3) **§4.2 over-claimed "negative
alpha"** — +0.0010 on 40–105 observations will not exclude zero, and −13.42pp vs NIFTY needs a
time-in-market adjustment; under discrete daily monitoring the martingale null is negative anyway,
via `engine.py:257-261` checking `hit_sl` before `hit_tp`.

**⭐ New measurement — the corpus is not the live strategy.** The per-position notional cap is
**unconditional** in the paper broker and algebraically `w ≥ risk_pct/leverage` = 2%, while
`backtest/engine.py` applies **no cap**. Restricting the positional corpus to the live-reachable
set (a pre-specified identity, not a searched partition) **flips the sign**: ALL n=385 −0.032R ·
**REACHABLE (w≥2%) n=271 +0.084R** · REJECTED (w<2%) n=114 −0.306R. ⚠ **The bootstrap does NOT
exclude zero** (reachable Sharpe +0.045 [−0.061, +0.148], ≤0 in 25% of histories, against ALL at
−0.011 [−0.120, +0.076], ≤0 in 57%), so **this is a corrected measurement, not a discovered edge**:
the defect must be fixed regardless of what the corrected number is, and the corrected baseline is
**~0 rather than negative**. Net of ~0.05–0.11R friction it is ≈0, below the +0.15R kill line. The
rejected cohort also has the **highest dispersion** (2.566 vs 1.844), so one intervention improves
mean R by 0.116R *and* cuts required n by 22% (1,744 → 1,360 trades to detect +0.10R at t=2) — and
**that half is unaffected by the interval and is the durable result.**

**⭐ The dispersion lever.** Required n scales with σ_R², and nobody was treating σ_R as an
objective. Positional σ_R 1.84–2.09 against swing's 1.489 means **positional needs ~2× the trades
to validate** — an argument against the relabel independent of expectancy. The excess dispersion
*is* the R:R identity, and **D5 already proved a constant-R:R target costs ~nothing in expectancy
(every paired ΔR negative, |t| ≤ 0.65) — it was closed on the wrong objective.** Reopened as a
power decision.

**⭐ The CAS go/no-go.** `fees.py:228-231` charges the flat ₹15.34 DP on every delivery sell with
no BTST exemption, so a daily-turnover strategy pays **₹3,835 / ₹7,670 / ₹11,505 per year at 1/2/3
positions = 3.8 / 7.7 / 11.5% of ₹1 lakh.** Whether Zerodha exempts BTST is one support ticket and
it is the whole verdict on the closing-auction escape.

**The plan now has kill lines with dates** (the biggest gap in the previous version): CA adjustment
moves **above** the ledger because it invalidates every downstream test; three Week-0 items added
(offered-set snapshot, daily fee reconciliation, cost-feasibility table); the four Week-2 tests
become nine, all pre-registered; and six numbered kill/decision lines dated 2026-09-18 → 2026-10-16
close the programme, the class, the null question and the unit question rather than deferring them.
**Nothing was built and no behaviour changed.**
### External quant panel adjudicated (2026-09-10) — ⭐ cycle 2 cannot test expectancy; the null was never written down

Ten external reviews (Perplexity · Claude · ChatGPT · Gemini · Kimi, five each on
`docs/SYSTEM_REVIEW_FOR_QUANT.md` and `docs/POSITIONAL_REVIEW_FOR_QUANT.md`, plus two
companion documents) checked **claim by claim against the code and a read-only DB query**,
never on the reviewers' word and never on our own documents' word (W1). Deliverable:
**`docs/analysis/quant-panel-adjudication-2026-09-10.md`**.

**Confirmed (16)** — the confidence denominator (`confluence.py:160`), volume sign-forcing
(`:145-157`, a spec choice not a slip), the three-way positional level divergence and its root
cause (`risk.py:63` optional param with a plausible semantic default), **no stop cap on
positional at all** (`risk.py:117`), the zero-cost / no-horizon backtest, the notional cap as an
implicit 2%-minimum-stop-width filter, the symmetric entry-zone alert beside unused
`cross_up`/`cross_down` machinery, and the `_has_active_signal` latch. **New, ours:** the
divergence covers **targets** too, not just stops (`pipeline.py:379`, `engine.py:341`).

**Refuted (6)** — most importantly the panel's most unanimous claim, *"you have never computed
factor-level IC, do it first."* `scripts/factor_sweep.py` ran it 2026-09-07: 212,129 observations
on 156 non-overlapping dates with day-block bootstrap **and trial-count deflation** (a guard none
of the five proposed), and nothing survived — including the exact SMA/52-week family a
cross-sectional ranker is built from, which is a strong measured prior **against** the panel's
other unanimous recommendation. Also refuted: Gemini's injection script (computes a t-statistic on
`np.random.normal` placeholder data), its 44-bar pivot arithmetic, and "normalise confidence by the
full 160 weight" (would make the 70 gate unreachable — p90 scoring weight is 55/160).

**New and decisive (5)** — (1) **cycle 2 cannot test expectancy**: σ_R = 1.489, so at n ≈ 25 the
DSR bar demands +1.12R/trade and a plain t=2 demands +0.60R, against +0.094R from a Sharpe-1.0
system ⇒ re-scope it as an operational-correctness rehearsal; (2) **the null was never written
down** — E[R]=0 for any barrier config under a martingale, and the correct null for a 100%-long
beta-0.92 book in a rising market is strongly positive ⇒ **negative alpha, not zero alpha**;
(3) **57% of generator output is untradeable** (108 SELL / 81 BUY on a cash-delivery book that
cannot hold an overnight short, both sides simulated in the backtest); (4) the **8% swing stop cap
is anti-correlated with P&L** on three independent lines and is on no tier of the plan;
(5) **breadth** — `IR ≈ IC × √breadth` ⇒ at ~60 trades/yr a perfect version of this system is not
investable. Plus the tension nobody named: **at ₹1L cost economics pushes toward concentration
while validation pushes toward breadth, so single-name delivery swing trading at this capital is
not a validatable strategy class regardless of edge.**

**Tested and refuted — the panel's sharpest attack on our own numbers.** The positional
stop-width gradient is **not** a winsorizer artifact: re-running the probe with the raw mean and
clip count beside the winsorized mean shows only **3 of 119** tight-stop trades clipped, raw mean
**−0.222** against winsorized −0.251 — sign, ordering and conclusion all stand. The prediction
over-shot ~10× because `R at target = 15/w` only applies to trades that reach target, and that
bucket wins 13.4% of the time. Two unexpected results from the same run: the **accidental flat-5%
stop beats the live EMA20 stop** on 387 paired panels (+0.091R vs −0.016R; ΔR −0.116, t −1.41),
and applying the 8% cap to positional panels would reject **54.4%** of them.

**Corrected in the same change (W1) — two CLAUDE.md claims that reality had overtaken:** the index
backfill is **not** done (`index_ohlcv_1d` = 51 rows, VIX = 17), and CAS accrual is **not** healthy
(`cas_daily` = 43 rows across **1** session, not 1,664 across 8) — both destroyed with the dev DB on
2026-09-07. Also recorded: `positions` = **0 rows**, so every live-tape figure in both review
documents is currently unreproducible and the forward-evidence loops still listed as open in
`PHASES.md` are dead. **Nothing was built and no behaviour changed** — this is an adjudication plus
a proposed sequence awaiting the user's direction.

### Positional review doc + positional probe (2026-09-10) — ⚠ "positional" is one factor's footprint, and its stop rule has THREE implementations

User asked for a standalone technical/functional document explaining the **positional**
class to an external quant: how a stock becomes a positional signal from the previous day's
EOD, whether that signal is validated against the next trading day, how marks/patterns/
indicators/sector combine, how R:R and the stop and target are set, what the class has
produced, why it fails to enter the right stock at the right price, and what options remain.
Deliverable: **`docs/POSITIONAL_REVIEW_FOR_QUANT.md`** — the positional companion to the
swing-weighted `docs/SYSTEM_REVIEW_FOR_QUANT.md`. Every figure is tagged `[code]`,
`[corpus]` (reproducible by the new probe) or `[tape]` (parsed from the surviving daily
reports, since the trading record was destroyed 2026-09-07).

**New: `backend/scripts/positional_probe.py`** (SELECT-only; the FROZEN scorer AND the FROZEN
backtest walker `BacktestEngine._simulate_trade` are imported and CALLED, never edited,
subclassed or reimplemented — W2). It finds **every** positional panel in the corpus, not a
sample: the multibagger breakout half depends only on the last 20 bars, so it is screened
vectorized and exactly, then confirmed with the real factor on each 300-bar window.
238 liquid names, 2019-10-01 → 2026-09-09. Runs are deterministic (two executions produced
byte-identical statistics). CA-contaminated holding spans (>25% close-to-close) dropped;
R winsorized at `WINSOR_R`; dependence priced with `moving_block_bootstrap`.

**FINDINGS (all new, all positional-specific):**

- ⭐ **`positional` is not a horizon decision — it is `MULTIBAGGER_EMA`'s footprint.** A 1d
  signal is positional **iff** that one bonus factor scores; the `1w` route is never run.
  The factor is appended ONLY when it fires, always scores exactly **+0.9**, and has no
  bearish branch — so alone it yields confidence exactly `9/10 = 90%`, the system's top
  bucket. **430 of 430 gate-passing positional panels are BUY**: the class is structurally
  long-only. **18.6% rest on that single factor** (what the ACTIVE diversity gate now
  blocks); live example `BUY AFFLE — Multibagger Ema, 90% confidence`, filled and held.
- ⭐ **The positional stop has NO cap and THREE implementations.** `compute_levels` assigns
  `max_sl_pct = 15.00` for positional and then **skips the cap check for exactly that
  class** — the variable is dead (and set to 15%, which would barely bind: EMA20 stops run p90
  8.29%, max 15.93%), while **11.9% of positional stops exceed 8% of price**, a width no other
  multi-day class accepts. Worse, `signal_service.py:245/:434` pass
  `ema20_daily` while **`profiles/pipeline.py:367` and `backtest/engine.py:322` do not** and
  silently fall back to a flat 5%. In the live record **26 of 40 positional trades carried
  the flat 5% stop, 14 the real EMA20**. ⇒ **the backtest validates a stop rule the primary
  minting path never produces**, and `_simulate_trade` also walks to the END OF THE DATA, so
  the 30-trading-day validity is not tested either. Paired on identical panels the two stop
  rules are **not separable** (ΔR −0.120, t −1.47) — a correctness defect, not a proven P&L one.
- ⭐ **The class selects AGAINST trend structure and then trades a trend premise.**
  `PRICE_VS_EMA` fires on **9.1%** of positional panels vs **63.4%** of daily panels
  generally, because the defining condition `|EMA20 − EMA200| ≤ 2%` is a *converged* MA
  stack. `DOW_TREND` scored on **0 of 430**. A 30-trading-day trade is opened with no trend
  input at all — corroborating the 2026-09-10 DOW_TREND finding from a second direction.
- ⭐ **The notional cap is a `risk_pct ÷ leverage` minimum-stop-width rule in disguise.**
  `notional = capital × risk_pct ÷ stop_width%`, so the cap binds at `w < risk_pct/leverage`
  = **2%** — **the capital cancels**. It rejects **28.4%** of positional signals, was shipped
  as a blast-radius rail, and has never been measured or reported as selection. 2% is exactly
  where the corpus outcome flips sign, so any future stop-width rule must be measured
  AGAINST it, not in addition (W2).
- **Outcome, gross of costs:** live rule + stated 30-day horizon **n=362, mean R −0.102,
  median −1.000, win 28.5%**; flat-5% variant +0.033R. No bootstrap interval excludes zero.
  **Enforcing the 30-day horizon makes both rules WORSE** (−0.032 → −0.102; +0.089 → +0.033),
  so the horizon label is not carrying the returns.
- **Stop width is the strongest gradient in the class**, monotone and measured **before any
  cost**: <2% → **−0.306R at 9.6% win**; 2–4% → −0.036R; 4–6% → +0.153R; 6–10% → +0.103R;
  >10% → +0.543R at 62.5%. The live EMA20 rule produces a **median 3.24% stop with 30% under
  2%** — it manufactures the losing cohort. Costs compound it: **cost in R = round-trip bps ÷
  (100 × stop-width %)**, so a 1% stop pays 0.23R in charges alone before slippage.
- **Should the class exist?** The same 430 panels scored under SWING rules instead: on the 155
  where both produce a trade, swing −0.213R at 37.4% win vs positional −0.292R at 16.1%;
  paired **ΔR −0.079, t −0.53 — not significant**. No evidence the relabelling adds anything,
  and it had never been tested.
- ⭐ **A FOURTH measurement defect, found by this review and NOT positional-specific:
  `_simulate_trade` scores a GAP-THROUGH-STOP fill as a WINNER.** The gap check is skipped on the
  fill bar (correct — the entry IS that open), but the intrabar `low <= stop_loss` test still fires
  and exits **at `stop_loss`**, above the entry. Repro in 3 bars: close 100, stop 99, next open 95
  ⇒ exit 99, `hit_sl=True`, **+4.211% = +1.000R**. Live is immune (`paper_broker:544-554`). It
  flatters the **tight-stop** cohort; excluding the 6 affected trades moved the tightest bucket
  −0.257R → **−0.306R** (win 13.3% → 9.6%). ⚠ **Every study on `_simulate_trade` inherits it**
  (the 1,975-trade headline, the entry-confirmation study) — magnitude there unmeasured. Added to
  `SYSTEM_REVIEW_FOR_QUANT.md` §11.4 as defect #4.
- ⚠ **No realised per-trade positional record exists.** 39 of the 40 reconstructable trades
  are last seen `open`; closed trades drop out of the report tape entirely. Live evidence is
  excursion-only (**63% never reached +0.5R**, MFE median +0.261R vs MAE median −0.454R).
- No rule in the eligibility registry or the risk engine is classification-aware: a 30-day
  positional trade is gated exactly like a 5-day swing.

Nothing was changed on the money path, in the frozen engine, or in the protected spec.


### Review doc + engine-selectivity probe (2026-09-10) — ⚠ the weight-20 Dow-trend factor is UNREACHABLE on the daily timeframe

User asked for a standalone technical/functional document explaining the system to an
external quant: how a stock becomes a signal, how the entry is chosen for swing, whether an
EOD signal is validated against the next trading day, how marks/patterns/indicators/sector
combine, how R:R and the S&R stop and target are set, what the system has produced, why it
loses, and what options remain. Deliverable:
**`docs/SYSTEM_REVIEW_FOR_QUANT.md`** — mechanism, measured results, diagnosis, options,
every figure either cited to a code path or reproducible by a committed script.

**New: `backend/scripts/engine_selectivity_probe.py`** (SELECT-only; the FROZEN engine is
imported and called exactly as the nightly job calls it, never edited or subclassed). It
measures what the daily reports structurally cannot see — the panels that were scored and
**discarded**. 4,511 daily panels: 239 liquid names × 30 decision dates 25 sessions apart,
trailing 300 completed bars each.

⭐ **THE FINDING: `DOW_TREND` — weight 20, the heaviest factor in the spec, described there as
"the macro context" — scores on 3 of 4,511 daily windows (0.07%), and cannot score by
construction.** `run_all_factors` calls `dow_trend_factor(candles, lookback=20, swing_n=5)` for
every non-intraday timeframe. In a 20-bar window a pivot at width n=5 can only sit at index
5…14; any two of those differ by at most 9 < 11, so their pivot windows overlap and both can be
the maximum only on an exact float tie. The function needs **two** swing highs AND **two** swing
lows. A synthetic staircase uptrend with higher highs and higher lows *by construction* returns
`0.0 — "Not enough swing points: 1 highs, 0 lows"`. Both demonstrations ship inside the script.
⇒ **the tradeable swing engine has no trend-structure input at all.** Because the confidence
denominator counts only factors that scored, the absence is silent: no number is depressed and
nothing is logged. Two independent observations corroborate the consequence — **0 of 91 paper
entries pass Minervini's trend conditions** (binding constraints: SMA150>SMA200 25/91, SMA200
rising 29/91) and the closed book carries **beta +0.92 with per-trade alpha +0.0010**.
⚠ **This is a SPECIFICATION defect, not an implementation bug** — `SIGNAL_ENGINE.md` §2.4
specifies both the 20-bar lookback and N=5 for daily and the code implements exactly that; the
two parameters are mutually inconsistent. The file is hook-protected: **nothing was changed**,
and the fix (if any) needs explicit instruction + a §8 regression + regenerated Rust fixtures.
The cheap first move is the read-only injection test that refuted RVOL — no frozen edit needed
to get the answer.

**Also measured, and new:**
- **What "≥70% confidence" actually selects.** Median **3 of 15 factors score**, worth **30 of a
  possible 160 weight points**; 18.4% of panels have ≤1 scoring factor. Gate pass rate **4.19%**
  of stock-days (108 SELL / 81 BUY). Of *passing* signals the 10th percentile rests on a
  **single** factor, and `SR_ZONE` is present in **69.8%** with a candlestick pattern in most of
  the rest — the engine is, at the decision point, a "candle pattern at an S/R zone" detector.
- **The ADX branch is not an edge case:** 39.9% of panels take the weak-trend path (gate raised
  to 75), 8.9% the strong path (lowered to 65).
- **Pivot geometry.** The swing stop is the most recent n=5 pivot **anywhere in the 300-bar
  window**: distance entry→pivot p50 4.91%, **p90 16.17%**, and **18.2% of the time the pivot sits
  at or ABOVE the entry close**. Only **47.4%** of daily windows yield a usable BUY-swing stop
  (38.1% rejected by the 8% class cap, 14.5% wrong-side/degenerate); among gate-passing signals
  **98 of 189 (51.9%) die at the level stage**. ⇒ the book is selected on *pivot proximity*, and
  near stops are independently the losing cohort.
- **Level geometry of the survivors:** stop width p10 0.65% · p50 5.00% · p90 7.11% (17.6% under
  2%); R:R p50 1.58 with **27.5% below 1.0**; notional at ₹1L/2% p50 ₹38,965 (a single position
  is ~39% of the account) with 15.4% above the 1.0× notional cap.
- **Cost in R is a hyperbola in stop width** (derived from the measured charge schedule + the
  6.8.2 fill telemetry, not a new measurement): at the median 5% stop the round trip costs
  **0.05–0.11R**; at the p10 0.65% stop it costs **0.40–0.83R** (the span is charges-only vs
  charges plus the measured median slippage of 14.0 bps per leg). Stop width is set by pivot geography and
  cost is set by stop width, so neither is set by anything to do with the trade's merit. This
  links the tight-stop ₹ sink, the "chased" cohort (avg stop 2.13% vs 5.33%) and the −1.70R
  overshoot into one mechanism.

**Nothing was built, no gate flipped, no knob touched, no recorded number changed, no clock
reset.** `ruff` + `mypy --strict` clean on the new script.

### Reading study (2026-09-09) — `docs/reading/security_analysis/`: four pre-registered tests, five negative results

Read all 14 PDFs in `docs/reading/security_analysis/` against a user question: can the books
solve entry/stock selection, validate an EOD signal against the next day's live market before
alerting, and alert at the right moment? Synthesis with citations:
**`docs/reading/security-analysis-folder-takeaways-2026-09-09.md`**.

**The books agree on one architectural gap and it is real in our code (verified, not quoted):**
we have SETUP → MANAGE with no TRIGGER stage. `services/signal_service.py:236` sets
`entry = last completed close`, `analysis/risk.py compute_levels` derives SL and TP from it, and
`broker/live_levels.py:217` alerts on a **symmetric ±0.5% band** — so a BUY drifting *down* into
the band raises the same "Entered zone" as a BUY breaking *up*. Elder (Screen 3), Weinstein
(buy-stop + limit), Brooks (enter on stops), Livermore and Johnson all insert a directional
trigger there.

**Their remedy was measured, not adopted** (hard constraint #8 — an argument is not evidence).
Four NEW read-only study scripts, none touching the FROZEN engine, none writing to the DB:

- **`backend/scripts/confirmation_base_rate.py`** → `docs/analysis/confirmation-base-rate-2026-09-09.md`.
  108,506 stock-days. **H-A REFUTED:** the selection signal is real and large (days that trade
  through the prior high average +0.99% next session vs −0.92% for days that don't, t=13.4) but
  is **fully priced into the trigger** — entering at the trigger returns −0.208% vs −0.088% for
  entering at the open, and is worse at every horizon to +10d. **H-B (Weinstein 150-DMA stage
  filter) and H-C (Elder Market Thermometer) both refuted**, t ≤ 2.54 against a 3.6 bar.
  ⚠ **H-C nearly became a false lever:** measured from the trigger price the quiet/hot split reads
  −1.056% vs +0.736% (t −17.8/+9.5) — an artifact of spanning the rest of the entry day. Measured
  strictly forward it vanishes. Both bases are printed so it cannot be re-discovered.
- **`backend/scripts/entry_confirmation_study.py`** → `docs/analysis/entry-confirmation-study-2026-09-09.md`.
  The same rule against **1,979 of our own minted signals** with real SL/TP. Exit walk is a
  replica of the frozen `_simulate_trade`, **asserted trade-for-trade against the original on 400
  trades** before any number is read (the assert caught one real defect — a missing right-edge
  mark-to-last-close — during development). **Same structure, independent sample:** SELECTION is
  real (baseline R on the confirmed subset +0.16…+0.32 vs −0.020 for the book) and FILL COST
  cancels it (paired ΔR −0.22…−0.30, **t −7.3 to −9.5**). Every unambiguous variant is negative;
  the one positive column depends on an intrabar ordering daily bars cannot resolve and is biased
  in its own favour. ⚠ **The cost is t≈−8; every benefit is t≤1.2.**
  Also measured, and useful regardless: **60% of signals confirm on day 1, 70% by day 2, 80% by
  day 5, 20% never within five sessions** — the alert-timing answer.
- **`backend/scripts/squeeze_study.py`** → `docs/analysis/squeeze-study-2026-09-09.md`.
  Carter's squeeze (BB(20,2) inside KC(20,1.5)) as a *generation* lever — the open problem since
  D5/D1. 3,610 fires, market-demeaned and sign-corrected for shorts. **No edge, |t| < 1 at every
  horizon.** Firing *against* the weekly is mildly harmful (t −1.7…−2.1), which supports Carter's
  own alignment filter but only removes a negative.
- **`backend/scripts/overhead_supply_study.py`** → `docs/analysis/overhead-supply-study-2026-09-09.md`.
  Weinstein's "minimum resistance overhead". 82,431 stock-days. Produced the only positive result
  — a monotone gradient on both P(+6% target touched: 34.3% → 21.5% at 5d) and market-demeaned
  forward return (+0.86% → −0.68% at +20d, t +9.2/−6.2) — and then **FAILED THE MANDATORY PROXY
  CHECK**: the Q0−Q4 spread **inverts** inside the low-volatility tercile (−0.229%) and
  **collapses** in the mid-momentum tercile (+0.086%). A volatility-and-momentum compound, not a
  supply effect. **Not promotable.**

**Nothing was wired, flipped or promoted. No recorded number changed; no clock reset.** The
reading's yield is (1) Brooks' trader's equation, which explains the 2026-09-03 R:R reversal
*structurally* (whenever one of risk/reward/probability is unusually good the others are worse —
so the R:R floor blocked the high-probability cohort by construction, and it also explains D5),
(2) five negative results that pre-empt five faith-based builds, (3) the day-1/day-5 confirmation
timing numbers, and (4) one untested thread that came from a control variable rather than the
books: **12-month price momentum** (D1 refuted *volume*/RVOL; price momentum has never been
tested and was strong enough here to absorb an apparent t=9 effect).

⚠ **Blocked by the 2026-09-07 data loss:** `ohlcv_5m/15m/1h` are gone, so Carter's day-type
classifier, Elder's "high of the first 15–30 minutes" and Johnson's "post-10am off the first
hour's extreme" are **untestable** — the studies use the prior daily bar's extreme (Elder's own
no-real-time-data variant) instead. Restoring intraday capture is a prerequisite for the finer
version and accrues only in real time.


### Research-harness fixes (2026-09-10) — three measurement defects found by quant-verifier

Found while reviewing the reading study above; **they are about the instruments, so every analysis
script is exposed, and two of them touch decisions this project has already closed.** All three made
a *negative* result look better than it was.

- **`app/services/block_bootstrap.py` — NEW `newey_west_t(series, lag=k-1)`** (Bartlett kernel) +
  5 tests in `tests/test_block_bootstrap.py`, including an **H0 canary that first REPRODUCES the
  inflation** on a synthetic overlapping panel and then shows the correction removes it. A daily
  cross-sectional t removes SAME-DAY dependence but not the overlap between day t and t+1, which
  share k−1 sessions of the same forward return: under H0 the naive t has sd **0.98 at k=1, 2.08 at
  k=5, 3.32 at k=10, 4.45 at k=20**, so a naive "t = 9" at a 20-session horizon is ≈**1.9σ**. One
  gradient in the reading study looked decisive at t=9 and **was never significant at all.** Sits
  beside `moving_block_bootstrap` deliberately: that module is this project's overlap-aware
  inference instrument, and this is the *mean's* standard error where the bootstrap is the *Sharpe's*
  — complements, not a parallel implementation (W2).
- **⛔ "The CA-clean window from 2023-07-03" is a FALSE claim.** `ohlcv_1d` is CA-UNADJUSTED
  throughout; **49 unadjusted corporate actions sit inside the top-250-liquid universe, 35 of them
  ≥40% halvings** (SHRIRAMFIN −81.1% 2025-01-10, COFORGE −79.7% 2025-06-04, ANGELONE −90.1%,
  DIACABS +3118.6%). Measured cost: dropping **4 of 1,979 trades removed ~+49R of FAKE PROFIT** —
  more than that study's entire original loss (baseline mean R −0.020 → −0.045). All four new
  scripts now drop any observation whose forward window (or a trade's fill→exit span) contains a
  |close-to-close| jump > 25%, and print the count.
  ⚠ **`scripts/tp_geometry_study.py` (which closed D5, exit geometry) and
  `scripts/rvol_factor_study.py` (which closed D1, RVOL) assert the same false claim and have NOT
  been re-run.** The phrase originated in `tp_geometry_study.py` and was copied forward. Check
  before either is cited again; re-running restates two closed decisions, so it needs a ruling.
- **Averaged R must be winsorized.** The entry study's ten largest |R| trades **all** had stops of
  **0.23%–0.86%** of price, all positive, contributing **+128.4R against a −89.7R total**. That is
  the documented tiny-SL artifact dominating a mean. R is now winsorized at the project's owned
  `app.core.ratios.WINSOR_R` (10.0) via `clamp_ratio_f` wherever averaged — the convention
  `entry_attribution.py` already follows (W5: no hardcoded copy of a value that has an owner).
  It moved **only the baseline** (mean −0.045 → −0.065, t −1.20 → −1.94) and made the paired fill
  cost **more** significant (t −7.2…−9.4 → **−9.6…−12.8**), so bounding the tails strengthened the
  finding. Robust alternatives that need no winsor: the **median** R and a **paired** ΔR on
  identical signals.

⭐ **The generalisable rule: an instrument that has never been run against a known null, a
known-contaminated input and a known tail artifact has not been validated** — the
`instrument_self_validation` discipline applied to the measurement harness rather than to a metric.
The entry study's "largest surviving trades" disclosure table found the third defect on its own,
which nobody had gone looking for.

Also in this pass, from the same review: the hypotheses in `confirmation_base_rate.py` are now
tested as **differences** (`mean(A) − mean(B)` day by day, Newey-West) rather than by eyeballing two
level t's — which turned H-A from "nominally worse" into **significantly worse (t −2.94…−3.51)**;
a **2% ceiling cohort** was added because the rule as first coded bought any gap however large and
therefore never tested Weinstein at all (it changes nothing: t −2.55…−3.35); a **re-anchored-target
sensitivity** shows the fill cost is not target truncation (ΔR −0.262 → −0.268); the same-bar rule
is renamed with an honest label and now prints **exactly what it deletes** (68 fills of mean R
−1.000 at 1d — nothing but stop-outs, which is why it flipped the sign); a **stop-side twin**
`P(−8% touched)` was added to the overhead study; the proxy check now runs on **reachability** as
well as return; `risk_at_trigger` is **directional, not `abs()`** (the `size_for_fill` defect class);
and both synthesis tables that had drifted are now **generated from the report files** rather than
typed.

### U19 (2026-09-09) — the holding-day horizon: does a gate separate winners from losers? [Bucket C]

- **`backend/app/services/gate_horizon.py`** (NEW, read-only) + **`GET /api/v1/analytics/cohort/{gate_key}/horizon`**:
  for a gate, split the scanned signals into the set it would BLOCK (flagged) vs LET THROUGH (passed) —
  reusing the cohort's isolation split — then trace each signal's realized R forward day by day from
  entry: `R_d = direction·(close_{entry+d} − entry)/|entry−SL|` (winsorized ±`WINSOR_R`), and
  "reached +1R by day d" from the favourable excursion. Reports **mean R and %-reaching-+1R by holding
  day, flagged vs passed** (Decision D). Renders the horizon finding (we grade multi-day trades on a
  one-day clock — entry-day ≥1R 12% vs +1R typically d+3) as a per-gate chart.
- **`gate_cohort.py` refactor (W2):** the would-block predicate is now one function, `split_signals`
  (+ `SplitResult`), shared by U20's cohort and U19's horizon — so there is a single implementation of
  "which signals would this gate block". The cohort's honest-count/bounded-payload behaviour is
  preserved (verified: U20's 7 tests still green).
- **`frontend` `CohortPage`** gains a **horizon section** on the gate drill-down: two Recharts line
  charts (mean R by holding day; % reaching +1R by holding day), each **flagged vs passed** —
  distinguished by colour AND dash (passed is dashed) with a shared AA-neutral legend, and a zero
  reference line on the R chart. Sample sizes travel with the statistic (H11/A24).
- ⚠ **Renders empty against the current dev DB** (signals wiped 09-07) — points come back with `None`
  means; tests seed their own signals + forward OHLC.
- **quant-verifier PASS-WITH-NOTES, both MEDIUMs fixed:** the horizon now starts at the first
  **tradeable** session (N+1) — the entry candle was N and a nightly entry is its close, so day-0 R was
  structurally 0 and day-0 "+1R" peeked at the entry bar's own high/low (a same-bar artifact); and the
  OHLC load now filters `is_complete` so a forming daily bar can't enter the horizon (matching the
  excursion loader's no-repaint convention). R math / hit convention / read-only / the refactor all
  confirmed correct (REPL). Denominator conventions documented (`flagged_total` vs per-day `n`).
- **ui-reviewer PASS** — no diff-failing findings (tokens, color+dash+label distinction, contrast,
  formatters, states all clean); added `min-w-0` for narrow-viewport Recharts shrink. ⚠ Surfaced a
  SECOND pre-existing app-wide token gap (`--color-chart-text` axis ticks ~3.3–4.3:1, sub-AA) — like
  the daybreak `profit`/`bull` gap, a token-hardening pass, out of scope here.
- Tests: `tests/test_gate_horizon.py` (4 — a deterministic flagged-vs-passed R-by-day path from the
  first post-entry session incl. the +1R-hit day, unsupported gate, empty), Vitest `CohortPage.test.tsx`
  (+1 horizon-section test). **U19 completes the U1 detail/cohort cluster.**

### U20 (2026-09-09) — the would-block cohort as a contact sheet [Bucket C]

- **`backend/app/services/gate_cohort.py`** (NEW, read-only) + **`GET /api/v1/analytics/cohort/{gate_key}`**:
  the committed signals a gate WOULD block, each with its levels, realized outcome (status + R), and
  a daily OHLC window around entry. The would-block set is NOT a parallel predicate (W2) — it reuses
  the order path's single source of truth `eligibility.preview` with the target gate forced ACTIVE and
  every other moded gate OFF, so the cohort is exactly what the order path would 409 on that gate.
  Supported for the signal-only gates (**regime · diversity · R:R**); others (chase/circuit/liquidity/
  market-regime/sector-RS need live state, sl_atr needs an ATR) return `supported=False` + a reason,
  never a fabricated set. ⚠ subtlety handled: diversity's verdict returns under the combined
  `entry_quality` badge, so `_RETURNED_GATE` maps it. `realized_r = pnl% ÷ (|entry−SL|/entry·100)`.
- **`GET /analytics/gate-register`** gains a `has_cohort` flag (derived from `REGISTER_KEY_TO_GATE` —
  single owner, no duplicated list) so the registry links only the rows that have a cohort.
- **`frontend` `CohortPage` (`/analytics/registry/:gateKey`)** — a light-SVG (Decision C) candlestick
  contact sheet: each blocked trade is a mini price panel with entry/SL/TP levels, the outcome glyph,
  and its R; a cohort summary carries the count + Σ-R with its sample size (H11/A24). Registry rows now
  link to it. "Statistics say whether a gate separates winners from losers; a contact sheet says what."
- ⚠ **Renders empty against the current dev DB** (signals were wiped 09-07) — by design it returns an
  empty cohort, not an error; tests seed their own signals + OHLC + outcomes.
- **quant-verifier PASS-WITH-NOTES, fixed:** `scanned` now counts every signal EVALUATED (the loop no
  longer breaks early at the cohort limit — only the OHLC payload is capped, so `cohort_count/scanned`
  is an honest block rate); `SUPPORTED_GATES` now DERIVES from `REGISTER_KEY_TO_GATE` (single owner, so
  `has_cohort` can't disagree with `supported`). Isolation/realized-R/read-only all confirmed correct.
- **ui-reviewer PASS-WITH-NOTES, in-scope fixed:** the entry/SL/TP level lines were distinguished by
  colour alone (CVD-unsafe for the safety-critical SL-vs-TP) → now distinct **dash + text label** (E/SL/TP)
  + colour; direction text moved `bull/bear` → the AA-tuned `profit/loss` tokens; focus-visible rings on
  the new links; the loading-skeleton grid matches the content grid. ⚠ **Left as a noted follow-up
  (pre-existing, app-wide):** daybreak `--color-profit`/`--color-bull` were never hardened the way
  `--color-loss` was (→red-700), so gain-coloured TEXT is ~3.4:1 in daybreak — a token-hardening pass
  (→emerald-700) is the right fix, out of scope here.
- Tests: `tests/test_gate_cohort.py` (7 — R:R blocks low-R:R + excludes healthy, diversity blocks the
  single-factor SRTL archetype, honest count + bounded payload, unsupported gate → supported=False,
  empty when no signals, auth), Vitest `CohortPage.test.tsx` (3) + a RegistryPage link test. Backend
  49 (touched set) · full Vitest 427 green · mypy/ruff/eslint/tsc clean.

### U11 (2026-09-09) — NIFTY buy-and-hold benchmark on the backtest equity curve [Bucket C]

- **`backend/app/services/benchmark_curve.py`** (NEW, read-only) + **`GET /api/v1/analytics/benchmark-curve?run_id=`**:
  a NIFTY buy-and-hold series aligned to a run's equity curve. The curve is per-TRADE and the engine
  is FROZEN (no dates), so each equity point is dated at its trade's `exit_date` and the benchmark is
  `NIFTY_close(date_i)/NIFTY_close(window_start)·100` — the two series start together at 100 and the
  benchmark's endpoint is the full-window buy-and-hold return (the H2 comparison). **Fails closed**
  (`available=False` + reason) rather than substituting a nearby date; `strategy_return_pct` is still
  reported. **quant-verifier PASS** (alignment/no-look-ahead/fail-closed all confirmed via REPL).
- **`frontend` `EquityCurveChart`** gains an optional benchmark series — a dashed line in
  `--color-text-secondary` (distinguished by dash + `┄` glyph, not colour) with a legend; a new
  `RunEquityWithBenchmark` fetches it lazily when a run row is expanded and falls back to the bare
  curve when unavailable. **ui-reviewer FAIL→fixed:** a benchmark-return `toFixed(2)` now goes through
  `formatPct` (and two pre-existing `toFixed` on touched lines swept to `formatPct`/`formatScore`).
- ⚠ **`index_ohlcv_1d` is EMPTY in the dev DB** (09-07 wipe) so it renders "unavailable" until an
  index backfill; tests seed their own index data and prove the aligned series + the fail-closed path.
- Tests: `tests/test_benchmark_curve.py` (6 — aligned series + returns, non-trading-date as-of,
  fail-closed with no index data / window before first bar, 404), Vitest `EquityCurveChart.test.tsx` (2).

### U10/U15/U17 (2026-09-09) — the signal-detail trio: how a confidence was built [Bucket C]

- **`backend/app/signals/confidence_explain.py`** (NEW, read-only reporting) reconstructs a
  committed signal's confluence arithmetic from its STORED `factor_scores`: numerator
  `Σ weight·score` (all factors), divisor `Σ weight` over **scoring factors only** (score ≠ 0 —
  abstainers DROP OUT), `normalized = num/div`, `confidence = int(|normalized|·100)`. It mirrors
  the FROZEN `confluence.score_from_factors` (lines 159-166) but never scores, sizes, gates, or
  writes; the frozen engine is untouched. Fails OPEN (malformed/empty/all-abstained → `None`).
  The point it makes visible: a 0-score factor is *removed* from the divisor, which is exactly how
  SRTL entered on one 0.8 factor reading 80% and clearing the ≥70% gate.
- **`GET /api/v1/signals/{id}`** now returns `confidence_breakdown` (detail endpoint only — `None`
  on the list, which stays lean; `None` too on a malformed payload). New schemas
  `ConfidenceBreakdownOut` / `FactorContributionOut` / `FactorAbstentionOut`.
- **`frontend` signal-detail modal (`SignalDetailModal.tsx`)** replaces the single factor bar with
  the trio: **U10** an arithmetic card (weight × score = contribution, the Σ/Σ division → %, and an
  abstainer note), **U17** a one-bar vote distribution (each scoring factor's share; a single tall
  segment is flagged "a single indicator carries the entire score"), **U15** a named-evidence line
  ("MACD bullish crossover · RSI divergence · …") + a forecast-horizon label per classification.
  The breakdown is fetched lazily via `getById` (enrichment only — never blocks the modal). New
  `formatScore` helper in `lib/format.ts` (unit-less analytical values; keeps `toFixed` out of
  features per rules/ui.md).
- **ui-reviewer PASS-WITH-NOTES, actioned:** the load-bearing explanatory copy (abstainer note,
  vote caption, table header/Σ rows) moved `--color-text-muted` → `--color-text-secondary` (was
  2.08–3.48:1 on daybreak/etc, now AA in all 5 themes); `formatGreek` → `formatScore` for the
  unit-less score/normalized values; the bar's `aria-label` now names the direction. The
  direction-coloured contribution numbers keep the sanctioned `bull`/`bear` tokens (direction is
  redundantly carried by the +/− sign and the "N% BUY/SELL" line, so not colour-alone) — their
  sub-AA-on-surface is a known **app-wide** token weakness (the pre-existing metric cards are
  worse: accent 2.45:1) flagged for a separate token-hardening pass, not fixed locally.
- **W1 fix (pre-existing drift):** the U1 nav link added last night left `Sidebar.test.tsx` link
  counts stale (19/22 → 20/23) — corrected.
- **quant-verifier PASS (1 HIGH fixed same-day):** the reconstruction first accumulated the sums
  with a naive `+=` fold, but the frozen scorer uses `sum()` (Python 3.12 compensated/Neumaier
  summation) — the ~1e-14 disagreement flipped int()-truncated confidence by 1 on ~0.27% of panels
  (and direction at an exact-zero crossing). Now sums via `sum()` in the engine's factor order →
  bit-identical (verifier: 0 mismatches over a 1500-signal sweep). Also fixed: a non-finite stored
  score now fails open BEFORE the `int()` (LOW), and a randomized parity sweep was added (the
  regression canary the single hand-picked case couldn't be).
- Tests: `tests/test_confidence_explain.py` (11 — unit + a hand-picked parity test + a randomized
  800-panel sweep through `score_from_factors` asserting `confidence_pct`/`direction` match on
  every non-gated result + a non-finite fail-open case), `tests/test_signals.py` (3 new — detail
  returns the breakdown, list omits it, malformed → None), Vitest `SignalOutcome.test.tsx` (3 new —
  arithmetic/vote/abstainer render, the single-indicator SRTL tell, graceful fallback). Backend 28
  green · full Vitest 421 green · mypy/ruff/eslint/tsc clean.

### U1 (page) (2026-09-09) — "Gate Register" page [Bucket C]

- **`frontend/src/features/analytics/RegistryPage.tsx`** (route `/analytics/registry`, nav "Gate
  Register") renders `GET /analytics/gate-register`: a summary panel (observed vs assumed trials
  with the A24 "observed is a lower bound" caveat in the same element + status-count pills) and a
  table of every hypothesis (name/key · status · trial? · verdict · review-due), sorted
  active→shadow→reverted→decided→research so the **reverted/decided candidates stay visible** (U6).
  Loading/empty/error states; follows the `OutcomesPage` template.
- **ui-reviewer PASS-WITH-NOTES, all fixed:** status uses **token-backed pills (StatusPill
  pattern), not the generic `destructive` Badge** — that maps to `--color-error` (red-600) which
  fails WCAG AA in daybreak/carbon; `reverted` now uses `--color-loss` (hardened red-700, 5.30:1),
  the exact CLAUDE.md contrast trap. Added the empty state, gave `research` a real resting style
  (the `ghost` badge had hover-only styles), dropped a redundant `overflow-x-auto`. Zebra striping
  skipped to match the app's other tables (pre-existing primitive behaviour).
- 5 Vitest tests (`src/test/RegistryPage.test.tsx`): data + trials/A24, U6 visibility, empty,
  loading, error. typecheck + eslint clean.

### U1 (data layer) (2026-09-09) — gate/hypothesis register exposed as an API [Bucket C]

- **`GET /api/v1/analytics/gate-register`** exposes H4's gate register as data — today it is
  readable only inside the daily-report markdown. Returns every hypothesis (status · prediction ·
  bar · stands-at · verdict · `counts_as_trial` · `review_due`), the **observed vs assumed trial
  counts** (U4), per-status counts, and the `due_for_review` keys (constraint #8). Read-only, no DB
  (the register is static curated Python data), money-path untouched.
- **Rejected/reverted candidates stay visible** (U6): the regime gate (reverted, −8R) and R:R≥1
  (reverted) are in the response — a register that drops its failures is the selection bias the
  deflation corrects. This is the **data layer for the U1 registry page**; the page itself
  (folding in U2/U3/U5 DSR benchmarks) is design-sensitive and left for a review-together pass.
- 4 tests in `tests/test_analytics.py` (auth, shape + trial/count invariants, U6 visibility,
  `due_for_review` matches the service).

### T13/T14 (2026-09-09) — external hand-computed anchors for the Wilder family [Bucket C]

- **T13 does not apply as written here, and that is the finding (W1).** T13 asked for
  `incremental_equals_batch` across the Wilder family — but in this engine **every batch fn is
  the incremental state looped** (`sma`/`rsi`/`atr`/`adx` all `map(state.update)`), so batch ≡
  incremental *by construction* and such a test is tautological (the existing SMA/EMA ones are
  too). There is no second algorithm to diverge; T13 collapses into T14 here.
- **T14 — the anchor that was actually missing.** RSI/ATR carry in-module reference tests, but
  those values came **from pandas-ta**, so the chain (Rust ← Python ← pandas-ta) is
  self-referential — a pandas-ta convention bug would be encoded green forever. Added
  `hand_computed_reference_anchor` tests to `engine/crates/engine-core/src/indicators/{rsi,atr}.rs`
  pinning values derived **independently of pandas-ta** (the documented ewm-seeded-first-diff /
  SMA-seed recursions worked out from scratch in Python on a short n=3 series, with the
  hand-derivation shown in comments). Three independent implementations agree to 1e-9. Also added
  ATR's first-ever unit test module (warmup-NaN + non-negativity). ADX's multi-stage seeding is
  deferred as a follow-up. Test-only — no engine logic changed, so no fixture regeneration.
  `cargo test -p engine-core` 71 passed; fmt + clippy clean.

### T10 (2026-09-09) — negative-space assertions on the notifier [Bucket C]

- Two `ExplodingObject`-style tests (`tests/test_notifier.py::TestNegativeSpace`) assert what must
  NOT happen: a policy-suppressed (INFO) notification and a throttled repeat both short-circuit
  **before** the webhook — proven by an exploding/counting `_post_webhook` that the suppressed path
  never reaches (and the throttled repeat hits the wire exactly once, not twice).

### T9 + A15 (2026-09-09) — doc-sync ritual and a schedule invariant, as failing tests [Bucket C]

- **T9 (`backend/tests/test_doc_sync.py`)** promotes the mechanically-checkable half of the
  doc-sync ritual from "a procedure Claude must remember" to a test that fails — our own lesson
  ("a documented safety net is worth nothing without a test that fails when it lapses") applied to
  *process*. `collect_problems()` reports **every** violation in one pass (W3 config drift):
  a `.env.example` key with no `Settings` field (stale/renamed), and a new `Settings` field missing
  from `.env.example`. Carries a **monotonically-shrinking debt baseline** (T8-flavored): the 49
  currently-undocumented fields are frozen in `KNOWN_UNDOCUMENTED` — not a claim they're fine, a
  claim the debt cannot GROW; documenting one is free, adding an undocumented one fails. The 4
  docker-compose-only env keys are exempt. Also flags a missing/future PHASES `(updated …)` stamp.
  (The STATUS.html gate-mode check is deliberately deferred — matching modes out of hand-written
  prose is itself drift-prone; the durable fix is giving STATUS.html a data source.)
- **A15 (`backend/tests/test_schedule_invariants.py`)** pins that the CAS capture window (18 min)
  is ≥ its beat's tick interval (1 min) — a tick can fall outside a window narrower than the
  interval, and a missed closing-auction window is **unrecoverable**; a future edit coarsening the
  beat would otherwise silently never fire. Also pins that the coverage-check's close time equals
  the capture-window end (so the "window missed" alarm judges the same window it captured).

### A39 (2026-09-09) — cargo-deny supply-chain gate on the engine/ workspace [Bucket C]

- **`engine/deny.toml`** + **`make engine-audit`** add the missing supply-chain gate on the
  Rust engine: RustSec advisories, a permissive-license **allow-list** (a copyleft dep now
  fails the gate rather than sneaking in — a non-issue for personal use but a real problem at
  productization, per the external-libs review), and **crates.io-only** sources. The allow-list
  was derived from the real tree (`cargo metadata`): all 39 crates are MIT/Apache-2.0/
  Unicode-3.0/Unlicense; our own 3 crates (`UNLICENSED`, `publish=false`) are `private.ignore`.
- On-demand, not part of `make check`: `cargo-deny` is **not vendored** (needs
  `cargo install cargo-deny`); the make target prints that hint and exits if the tool is
  absent. Noted in `.claude/rules/rust.md` as a gate to run after any `Cargo.toml`/`.lock`
  change. `deny.toml` validated as well-formed; run-verification pends installing the tool.

### H7 (2026-09-09) — shadow-gate decay alarm [Bucket C]

- **`app/services/sharpe_decay.py`** alarms when a shadow gate's readiness banner **regresses**:
  the regime gate ran seven NOT-READY report days before it was reverted (net-positive suppressed
  set, ~8R subtracted), and the signal was on disk every day — nothing turned detection into an
  alarm. H7 is a **second reader** of the dated `<gate>-shadow-<date>.md` banners the sidecars
  already write.
- **The PUSH fires only for an ACTIVE gate that regressed** — the load-bearing distinction:
  `decaying ⟺ trailing NOT-READY run ≥ DECAY_STREAK_DAYS (5) AND the gate is ACTIVE per the
  gate_register`. That is the regime-gate incident exactly (a gate we adopted losing its edge). A
  perpetually-accruing gate never alarms; a **SHADOW** gate flipping READY→NOT-READY (criteria
  change or small-sample oscillation) is `shadow_regressed` — recorded in the durable table, never
  pushed (the notifier's "never train a human to mute the channel" rule). Leans on H4's register
  (`gate_register.get`) for adoption status. ⭐ **The shadow-vs-active distinction was a bug-hunter
  MEDIUM finding, fixed the same day** — the first cut pushed on any READY→NOT-READY flip and would
  have cried wolf daily for sector-RS/market-regime.
- **Wired into `make analysis`** as a diagnostics step (after the gate sidecars so today's banners
  are on disk): writes `gate-decay-<date>.md` (full status table, shadow regressions included) and
  pushes via the notifier only when an ACTIVE gate is decaying.
- 18 tests (`tests/test_sharpe_decay.py`): banner parsing precedence, accrual-vs-shadow-regression-
  vs-active-decay, streak recovery, file scan with gaps, and the "shadow regression records but
  never pushes" contract.

### A9/A10 (2026-09-09) — a progress envelope for long-running jobs [Bucket C]

- **`app/core/progress.py`** — a dependency-free, framework-agnostic progress protocol:
  `ProgressReporter.step()` emits `ProgressEvent`s carrying `{label, phase, step, total_steps,
  pct, message, elapsed_s, result, timestamp}` (A9), with a mid-flight `result()` for a running
  tally that updates between stage boundaries (A10). Renders a compact human line or one JSON
  object per line (`json_mode`) to any stream; emission failures are swallowed so a progress
  line can never break the job it reports on.
- **Wired into `make analysis`** (`scripts/daily_analysis.py`), which was opaque across its 11
  stages until it finished or wedged. Progress now goes to **stderr** — e.g.
  `[analysis 7/11 64% · 4.2s] shadow gates: market-regime shadow` — so stdout stays the clean,
  pipeable "wrote …" report lines. Backtests / walk-forward / EOD can adopt the same reporter.
- 14 tests (`tests/test_progress.py`): envelope arithmetic (percent, unknown-total, clamp),
  both renderings, stepping + elapsed via an injected clock, mid-flight result, and the
  broken-sink-never-breaks-the-job guarantee. Smoke-run confirmed clean stderr/stdout split.

### A36 (2026-09-09) — proactive NSE calendar-coverage expiry alarm [Bucket C]

- **`app/services/calendar_health.py`** turns the calendar's silent query-time warning into a
  proactive alarm. The `nse_holidays` table has a horizon (its last seeded circular); past it,
  trading-day arithmetic drops to **weekday-only** and silently miscounts every validity window
  (SIGNAL_ENGINE.md §5) around an unknown holiday. `read_calendar_status` (never raises, mirrors
  `token_health`) reports coverage state — **absent / expired / expiring-soon / healthy** — with
  the trading-days of runway remaining.
- **A daily beat task** (`health_tasks.check_calendar_coverage`, 09:30 IST weekdays) PUSHES via
  the notifier when runway is short (`< WARN_BELOW_TRADING_DAYS = 20`, WARNING) or gone (ERROR),
  and the **daily report** carries the same horizon as a human-read line beside worker/token
  health — so a quiet channel is never the only evidence.
- **Optional cheap second opinion:** cross-checks upcoming weekdays against `exchange_calendars`'
  XNSE *when that library is present* — never a dependency, never a hard failure (absent ⇒ silent).
- 15 tests (`tests/test_calendar_health.py`); the existing beat-schedule contract test confirms
  the new entry resolves to a registered task. No new settings, no migration.

### A28 (2026-09-09) — retryable delivery classification in the session notifier [Bucket C]

- **`app/services/notifier.py`** now classifies every webhook delivery outcome by whether
  **retrying can help** — repo 9's `ChannelAttemptResult.retryable`, applied to our transport.
  New `DeliveryOutcome` (`sent`/`attempts`/`retryable`/`status_code`/`error`) and a structured
  `DispatchResult` returned by a new `dispatch()`; `notify()` is now a thin bool wrapper over it,
  so callers and their `finally` blocks are unchanged.
- **Closes a real silent gap:** the POST did not check its response, so a webhook returning **404
  / 401 read as success** and a misconfigured channel looked healthy forever. A non-2xx is now a
  failure; a **permanent** one (4xx auth/not-found/bad-URL) is logged at **WARNING** naming the
  likely cause (a human must fix config), while a **retryable** one (429, 5xx, network/timeout) is
  retried up to `WEBHOOK_MAX_ATTEMPTS=2` and, if still failing, logged at debug — "a receiver
  outage must never affect trading". Still **never raises** into a caller.
- 14 new tests (`tests/test_notifier.py`, 34 total green): status + exception classification, the
  bounded retry (one backoff, exhausts budget, stops on success), permanent-vs-retryable log level,
  structured-result shape, and the backward-compat `notify()==True`-on-delivery-failure contract.

### D2 parked (2026-09-08) — R2 gate decision deferred to cycle-2 end

- User ruling: hold the final R2 (weekly spread-width gate) build-or-drop call until **cycle 2
  completes**, and decide it on cycle-2 forward evidence. R2 stays provisionally dropped (09-07); the
  decision does **not** block cycle-2 start. Recorded as a **review-calendar item** in the PHASES top
  block with trigger "WHEN CYCLE 2 COMPLETES" — Claude owns raising it unprompted at that point.
  Reconciled a prior doc inconsistency (Q2.3 read "DROPPED 2026-09-07 (user sign-off)" while Q0 still
  listed D2 open): both now read "provisionally dropped; final call parked to cycle-2 end."

### D3 resolved (2026-09-08) — free-source spike: the market-cap vendor question is moot, no vendor needed

- **Spike (`docs/analysis/market-cap-source-spike-2026-09-08.md`), read-only.** The "`market_cap`
  has no writer → pick a vendor" keystone is **retired**: no free *bulk* file carries per-stock market
  cap (bhavcopy = OHLCV+delivery; `ind_close_all` = per-index), but a **free per-symbol path exists on
  the NSE `/api/` surface the app already uses in production** (`fii_dii_service` → `fiidiiTradeReact`):
  `quote-equity` returns `issuedSize` (shares outstanding) and `trade_info` returns `totalMarketCap`/
  `ffmc`, so `market_cap = issuedSize × price` is computable daily from stored OHLCV after only a
  one-time + corporate-action-triggered shares fetch — far lighter than MCE 5b's XBRL scraper, and $0.
- ⚠ NSE `/api/` 403s from a datacenter IP, so the exact field names / rate limit must be confirmed from
  the app's own IP before building. **Build deferred:** nothing needs `market_cap` now (F1 dropped the
  size floor; cycle 2 doesn't use it; only the inert screener filter consumes it). No code changed.

### D4 decided (2026-09-08) — concentration/sizing: minimal rails; max-concurrent-position cap BUILT

- **Ruling:** keep the per-position notional cap (leverage 1.0) and the 6% portfolio heat cap
  unchanged; **add a max-concurrent-position cap** as the concentration rail that actually binds at
  cycle-2 scale; **defer** correlation/sector-aware heat (over-engineering for a 1–2 position book).
  Rationale: the 45–58% heat figures are a *cycle-1 sampler artifact* (~25–29 concurrent positions);
  cycle 2's ₹1L / 1–2-position book can't structurally over-concentrate, so a heat *percentage*
  barely binds while a *count* directly enforces the 1–2 design intent.
- **Built (`app/trading/risk_engine.py`):** `RULE_POSITION_COUNT` + `position_count_reason()`, wired
  into `check_sizing` alongside the heat cap (both portfolio-state rails now share one `open_heat`
  read). New settings `position_count_cap_mode` (off/shadow/active, default **off**) and
  `max_concurrent_positions` (default **3**) — `.env.example` updated (W3). A **hard design rail**
  (like `entry_diversity`), so no deflated-Sharpe bar; adding to an existing position is exempt (opens
  no new slot — the notional cap bounds per-name size); always measurable, so no fail-closed branch.
  `off` during the cycle-1 sampler, flips `active` at the cycle-2 reset alongside the heat cap. 42
  RiskEngine tests green (9 new); existing heat/notional tests unchanged (equivalence preserved).

### D1 declined (2026-09-08) — R1's RVOL half refuted, VWAP untestable; frozen engine untouched

- **Added `backend/scripts/rvol_factor_study.py`** — a read-only R1 counterfactual. It injects a
  research graded-RVOL confirmation factor through the frozen `score_from_factors` (monkeypatching the
  one `run_all_factors` seam), so it changes which signals mint **without editing frozen code or moving
  a recorded number**. Two analyses: §1 design-agnostic (does RVOL-at-entry predict outcome among
  signals already minted?) and §2 the injected-factor effect (with the dropped set, since normalization
  makes "add a factor" non-additive).
- **Result (`docs/analysis/rvol-factor-study-2026-09-08.md`, 1,152 baseline signals, 150 liquid names):**
  §1 — RVOL-at-entry is mildly **inverse** (elevated buckets worst: 1.5–2.0× −0.237R t=−1.71; ≥2.0×
  −0.157R), so no factor design can extract edge from it. §2 — injecting a graded RVOL factor makes the
  book significantly **worse** (augmented −0.095R vs baseline −0.026R; the 294 it newly admits average
  −0.291R at t=−2.91) via scorer dilution. VWAP is untestable (no intraday data). ⇒ **R1-RVOL dropped,
  D1 declined, no frozen change.** Notable: the existing binary VOLUME factor already encodes RVOL at
  1.5× and appears to over-capture it. **With selection, exit geometry (D5) and this generation lever
  (R1) all now refuted, no queued item attacks profitability** — the edge question is unresolved.

### D5 decided (2026-09-08) — take-profit geometry is NOT the profit lever; `compute_levels` stays frozen

- **Added `backend/scripts/tp_geometry_study.py`** — a read-only counterfactual for D5, riding the
  sanctioned `BacktestConfig.tp_rule` freeze-extension (`tp_rule=None` byte-identical to frozen), so
  it **touches no frozen code and moves no recorded number**. Holds every frozen entry+stop fixed,
  varies only the target across a constant-R:R family (1.0–3.0R), and does a **paired** per-signal
  comparison (`stock, entry_date`) measured in **R**, segmented by stop-width cohort. Factors are
  computed once per stock (baseline run) and the alternative targets re-simulated through the frozen
  `_simulate_trade` — verified byte-faithful to full re-runs.
- **Result (`docs/analysis/tp-geometry-study-2026-09-08.md`, 1,152 swing+positional signals, 150
  liquid names, CA-clean 2023-07-03+):** no constant-R:R geometry beats the frozen absolute-% target
  — every candidate's paired ΔR is negative (−0.012 to −0.025R, |t| ≤ 0.65), the baseline itself is
  −0.026R, and a higher R:R **damages the wide-stop majority** (547 trades: rr_3.0 −0.110R), the exact
  R:R-reversal mechanism. ⇒ **D5 closed as "keep the tourniquet"**; the leak is upstream in candidate
  generation (R1). Untested: a structural next-S/R target. Also surfaced: the post-wipe reseed left the
  stock membership/classification flags sparse (`is_fno` 45, `is_nifty50` 5, `sector` 165/1322,
  `market_cap_cr` 0) — a separate metadata-restore task; the study is unaffected (universe from
  `ohlcv_1d` traded value, not flags).

### ⛔ INCIDENT 2026-09-07 — the dev database was destroyed, and the guards that came out of it

**What happened.** A `pytest` run was invoked with `DATABASE_URL` pointed at
`trading_platform` instead of `trading_platform_test`. `tests/conftest.py` set that variable
with `os.environ.setdefault`, so the externally-supplied URL was taken as-is, and the autouse
`clean_tables` fixture ran `TRUNCATE ... RESTART IDENTITY CASCADE` against every table before
each of 11 tests. The variable was being passed by hand because a worktree carries no `.env`,
which is what made a normally-dormant trap live.

`archive_mode` was off, there was no PITR, and there was no backup of any kind on the machine.

**Cost — permanent, not recoverable:**

- **138 paper positions** (106 closed, 32 open) — the entire cycle-1 paper book, roughly
  seven weeks of accrual. Original observational data.
- `signals` and `signal_outcomes` — point-in-time levels, confidence, factor rationale, MFE/MAE.
- **`cas_daily` — 1,664 rows across 8 sessions.** Unrecoverable by design: the capture reads
  Kite `/quote` live during 15:15–15:33 IST and a missed window cannot be back-filled.
- `orders`, `order_events`, `watchlists`, `watchlist_items`, `journal_entries`,
  `saved_screens`, `mf_holdings`, `manual_assets`.

**Recovered:** `stocks` (2,886, via `seed_stocks.py` — public NSE CSVs, no auth required),
`ohlcv_1d` (1.63M bars re-ingested from the NSE bhavcopy archive), `users`.
`corporate_filings` survived untouched because its model is not registered in conftest's
`Base.metadata`. The schema was never damaged — `alembic_version` remained at head.

**Not reconstructed, by user ruling.** The 24 daily reports under `docs/analysis/` do carry
per-trade detail (plan, fill, chase, MFE/MAE), but exit coverage is only ~25% and realised
P&L would have to be recomputed under fee models that landed 2026-09-05. A half-real book
flowing into the paper clock and every future study is worse than the loss. The ledger stands
as written; accrual restarts from day 1.

**Mitigating context, stated without spin:** cycle 1's 30-day clock was already informational
and cycle 2's had not started, so no go-live milestone moved. The findings survive in
`docs/analysis/` because each report carries its numbers; the raw rows do not.

### fix: the test suite now refuses any database not named `*_test`

`tests/conftest.py` fails at import time — before any fixture, engine or migration — if
`DATABASE_URL` or `DATABASE_URL_SYNC` names a database whose name does not end in `_test`.
`setdefault` is still correct (CI and other harnesses legitimately inject a URL) but it must
not be able to aim the truncation at production-shaped data. The project already enforced
exactly this rule for Redis (*"never point them at dev db 0"*); for Postgres it was written
in a docstring and enforced nowhere. Verified in both directions.

### feat: daily database backups, with a restore that is actually proven

`scripts/backup_db.sh` + cron `0 11 * * 1-5` (11:00 IST, Mon–Fri) to
`/home/nithin/code/back_ups/trading_platform/{dev,test}/`, retaining the 3 most recent dumps
per database. `pg_dump -Fc` captures **the entire database** — all 52 tables: positions,
orders, holdings, filings, watchlists, journal, saved screens, signals and the hypertable bars.

Two properties are what make it a backup rather than a file:

- ⭐ **Pruning happens only after a dump that passes `pg_restore --list`.** Pruning first is
  how a backup system silently eats its own history: each failing run deletes one more good
  copy while writing nothing. A failed run leaves every existing backup untouched, exit 1.
- ⭐ **`make backup-verify` performs a REAL restore** into a scratch database and diffs every
  table's row count, rather than checksumming. Two stack-specific hazards would otherwise
  produce an unrestorable dump with no visible sign: TimescaleDB hypertables keep their rows
  in `_timescaledb_internal` chunks and need `timescaledb_pre_restore()`/`post_restore()`
  around the restore, and the host's pg_dump is 17.x against a 16.x server. Everything runs
  inside the container so client and server always match.

Verified on install: 52/52 tables restore, `pg_restore` clean, counts identical bar four rows
a scraper inserted during the check itself. Targets: `make backup`, `make backup-list`,
`make backup-verify`, `make install-backup`. Documented in `RUNBOOK.md` §9, including the full
restore procedure and the rule to restore into a NEW database and swap, never over a live one.

⚠ Redis is deliberately not covered — it is all TTL'd cache the live worker rebuilds.

### feat: survivorship-safe historical bar backfill

`app/services/bhavcopy_service.py` gains a `historical` mode and
`scripts/backfill_ohlcv_history.py` walks the NSE archive resumably. In historical mode a
symbol the bhavcopy names but `stocks` has never seen is CREATED as an **inactive** stock, so
a multi-year backfill reconstructs the point-in-time universe instead of a survivor-only one —
`stocks` is a today-snapshot from Kite instruments, and every company that delisted would
otherwise be silently absent. The default path is unchanged: unknown and inactive names still
get no bars, per the T2T ruling. Insert is chunked (a backfill is ~2,300 rows/day over ~950
days). 11 tests pin the contract. This is also what made the `ohlcv_1d` recovery possible.


### analysis: the book without the trades that were never really chosen

Asked to omit the positions that were "entered wildly without looking at the signal" or
mis-clicked, so the rest would show the real P&L. `backend/scripts/clean_book_study.py`
(+ `docs/analysis/clean-book-2026-09-07.md`). Three findings, in order of how much they
change the answer.

**1. No mis-click is recorded anywhere.** Nothing in `CHANGELOG.md`, `docs/`, the phase
docs or the memory files marks a position as unintended, and `positions` has no intent
field. The exclusion is therefore a forensic reconstruction from execution signatures,
not a record of what was meant.

**2. The "wrong button" class is empty.** 0 of 106 closed positions opened a LONG on a
SELL signal or the reverse. One entered through its own stop (SPARC — the side-blind
`size_for_fill` bug, fixed forward-only); 3 were off-market; 0 on a weekend. Nobody
bought a sell signal.

**3. What IS detectable is displacement from the signal's own entry, and the numbers are
large.** Excluding the 12 trades filled more than `settings.chase_max_r` (0.33R) past
their signal entry, plus the one broken row:

    as recorded   106 trades   -Rs 12,369
    clean          93 trades   +Rs 13,262   +18.8R   55% win
    excluded       13 trades   -Rs 25,631

**⚠ But "chased" is largely a PROXY for "tight stop", and that is a finding about the
instrument.** Displacement is measured in units of the stop distance, so a tight stop
mechanically inflates it: a stock that ran Rs 1 past its entry is 0.1R chased on a Rs 10
stop and 1.0R chased on a Rs 1 stop — same price action, opposite verdict. The chased set
averages a 2.13% stop against 5.33% for the rest, with 8 of 12 inside the already-known
tight-stop leak. The cross-tab is printed; chasing survives inside the wide-stop group
(4 trades, 0% win) but the cells are far too small to separate the two effects. This is
the third instance here of the partition-is-a-proxy trap (market-regime for *side*,
`stop moved` for *went into profit*).

**The exit verdict is robust to the exclusion.** On the clean set the exits still keep
63% of peak on the 43 trades that reached 0.5R, and 43 of 86 still never got there
(-Rs 47,751). Removing the badly-entered trades makes the entry problem smaller without
moving where it lives.

**What this does NOT license:** flipping `chase_gate_mode` active (n=12 against a t ~ 3.6
bar that is flat in n), or reading +Rs 13,262 as a P&L we could have had — removing the
worst 12% of any book improves it. The one thing that makes this cut legitimate rather
than hindsight is that displacement is knowable BEFORE the order: `chase_guard` computes
it from the live LTP at order time.

Also fixed while writing it: the bucket table silently dropped the 10 trades whose
`peak_pnl` is NEGATIVE (best mark never cleared entry) because the first bucket floored
at 0.0, so the rows added to 76 against a stated 86. Floor is now -inf and an assertion
pins the partition.

### feat: the exit/giveback study — commissioned on a wrong hypothesis, and that IS the finding

**The exit machinery is working. The loss is made at entry.** Confirmed on 96 closed
positions, in **R**, not ₹.

| peak bucket | n | avg peak R | avg realised R | total R | total ₹ | capture |
|---|--:|--:|--:|--:|--:|--:|
| **peak < 0.25R — never worked** | **33** | **0.00** | −0.83 | **−27.4R** | **−₹50,669** | — |
| peak 0.25–0.5R | 17 | 0.36 | −0.61 | −10.3R | −₹15,111 | — |
| peak 0.5–1R | 19 | 0.77 | +0.26 | +5.0R | +₹11,978 | 34% |
| **peak 1–2R** | 21 | 1.39 | **+1.03** | **+21.7R** | +₹45,933 | **75%** |
| peak ≥ 2R | 6 | 2.62 | +0.53 | +3.2R | +₹8,962 | 14% |

**50 of 96 trades (52%) never got meaningfully into profit** — they account for **−₹65,779
(−37.8R)**. The 27 that reached ≥1R realised **+0.92R of a 1.67R peak: 62% capture.**

**⇒ Not an exit problem.** This is the same diagnosis CLAUDE.md recorded months ago on 15
trades — *"the exit machinery was correct but had nothing to protect"* — now confirmed on 96.
**No exit rule can fix a trade that never moves in your favour.**

**⚠⚠ THE CORRECTION THIS STUDY EXISTS TO RECORD.** It was commissioned on the reading that
*25 of 30 stop-outs had been in profit and gave it all back, for −₹59,785* — an apparent exit
defect. **In ₹ that is what it looks like. In R it evaporates:** the `sl_hit` group's average
peak of +₹1,229 is, against the risk actually taken, approximately **zero**. Those trades
wobbled a few hundred rupees above entry on positions whose 1R was thousands.

**That is this project's own standing rule, broken by the agent that wrote it down** —
*"measure stop-width counterfactuals in R, never ₹… that error inverted the first pass"*.
Same class of error, one layer over.

**⚠ A second correction in the same pass: "the stop moved" is NOT evidence the ratchet
works.** Splitting on it showed +₹43,395 vs −₹42,301, which looks conclusive. It is a
**proxy** — the profit-lock ladder only arms once a trade is up, so `stop moved` ≈ `went
into profit` (peak 1.63R vs 0.41R). Controlling for peak R the difference **vanishes**:
1–2R bucket realises +1.035R moved vs +1.032R unchanged. The partition-is-a-proxy trap the
market-regime gate already taught, where it was a proxy for *side*.

**⚠ And a defect in the study's own first output:** the capture column printed **−610%** for
the dead buckets — dividing by a peak that never existed. The per-trade guard existed but
was not applied at bucket level, so the artefact reappeared one layer up. Now suppressed
with `— (no peak to capture)`.

⚠ `peak_pnl` updates on live monitor ticks, so it is only as complete as the monitor's
uptime — which biases peaks **downward** and would, if anything, *understate* giveback.

- `backend/scripts/exit_giveback_study.py` — new · `docs/analysis/exit-giveback-2026-09-07.md`


### feat(MCE 6 follow-up): the news-drift study — and it contradicts the shorting hypothesis

**The honest version of "check before scrapping".** The slice-6 feasibility check tested
`corporate_filings` against the *veto* design. This tests the question that actually
matters — **news as a directional signal**.

⭐ **And it needs no news feed.** A large abrupt move on heavy volume **is the footprint of
news**, so drift is measurable from bars we already hold. `scripts/news_drift_study.py`:
|1-day move| ≥ 6% on ≥1.5× average volume, in liquid names — **29,352 events across ~773
dates**, forward returns at t+1/3/5/10, split by direction and day-block bootstrapped.

**Drift IS detectable** — three cells' intervals exclude zero. But two things invert how it
reads:

**⚠⚠ 1. Every UP-jump cell is TAIL-DRIVEN.** Positive mean, *negative median*, under half
positive:

| cell | mean | median | % positive |
|---|---|---|---|
| UP t+1 | **+0.355%** | **−0.142%** | 48% |
| UP t+5 | +0.242% | **−0.608%** | 46% |
| UP t+10 | **+0.551%** | **−0.820%** | 47% |

**A positive mean with a negative median is a lottery-ticket distribution, not an edge.**
You lose on most trades and depend on rare large winners — which a ₹1 lakh book cannot
fund and **a stop-loss destroys**, because the stop cuts exactly the tail you are relying
on. This is the market-regime lesson repeating: that gate's would-block set had a −₹302 mean
and a **+₹200 trimmed mean**; mean alone would have recommended it. The script now computes
and prints this divergence itself.

**⭐ 2. DOWN jumps BOUNCE — they do not continue down.** Mean *and* median positive at
t+3/t+5/t+10 with >50% of events positive, the most internally consistent result in the
study (t+10: mean +1.846%, median +0.297%, interval [+0.008, +3.658]%).

**That is the opposite of the shorting hypothesis.** On 6,792 large adverse moves, **buying
the fall beat shorting it**. The TCS-style narrative (bad news → down for a week) is a real
*story*; it is not what the population does on average — and that gap between a vivid case
and the base rate is the entire reason to measure.

⚠ **Detectable ≠ tradeable**, and the report says why: costs (22–62 bps + ₹15.34 DP) can
exceed the drift · we could act only from the jump day's CLOSE, the intraday move gone ·
a DOWN-continuation short needs futures (cash delivery cannot short) · 8 cells were examined
and any survivor must be charged for that.

### feat: factor sweep at the 20-day horizon — same answer, stronger reversion

**Nothing survives** here either (17 configs, 52,830 non-overlapping observations). The
mean-reversion pattern is *stronger* at 20 days: `sma50_over_sma200` spreads **−1.369%**,
`close_over_sma200` **−1.139%**, all with 3/4 monotone steps — stocks further above their
long averages did worse over the following month.

⚠ **A limitation worth recording:** `close_over_vwap20` flips *positive* at 20 days
(+0.974%) and carries the **highest |IC| of either sweep (+0.0330)** — but it ranked 9th by
spread, and the harness only bootstraps the top 6, so it never got an interval. **Ranking by
spread rather than by IC is a design choice that can hide the strongest rank-correlation.**

- `backend/scripts/news_drift_study.py` — new · `docs/analysis/news-drift-2026-09-07.md`
- `docs/analysis/factor-sweep-h20-2026-09-07.md`


### feat: the factor sweep harness — and it REFUTES the R1 pre-screen's VWAP finding

**Built to the standing instruction** (*"always try different possibilities... what if we
change the period, how does it behave? Similarly 150 SMA > 200 SMA, 20 DMA > 200 DMA, or
in-betweens"*) — with the one thing that stops a sweep becoming an overfitting machine
**built in rather than bolted on**.

`scripts/factor_sweep.py` sweeps volume ratios at 4 lookbacks, every SMA pair, price against
3 references and 52-week position, against forward returns over the full daily history:
**212,129 observations on 156 non-overlapping dates, 17 configurations.**

**Three guards, each closing a specific way this could lie:**
1. **Non-overlapping dates** — a 5-day forward return on consecutive days overlaps 80% with
   its neighbour; ignoring that inflates significance ~√5×.
2. **Day-block bootstrap** — every stock on one date shares that date's market move, so the
   independent unit is the DATE, not the row (the CAS-2 lesson).
3. **Trial count reported and charged** — `momentum ×1.5` was best-of-12 and its ranking did
   not survive a larger corpus. That is the failure this exists to catch.

**⛔ Result: nothing survives.** All 17 intervals span zero; max |IC| = 0.0224; no
configuration is monotone 4/4. **The period choice in `volume_factor` is not where the
problem is, and neither is the SMA pair.** That is a real answer to a real question.

**⚠⚠ CORRECTION — this refutes the R1 pre-screen's headline, and the earlier enthusiasm was
wrong.** Two messages ago the pre-screen was reported as *"the cleanest gradient this project
has produced"* (win rate 43 → 71% as price rose above its 20-day anchored VWAP, n=21 per
quintile). On **212,129** observations with a day-block bootstrap, the same relationship runs
the **other way**:

| feature | Q5 − Q1 spread |
|---|---|
| `close_over_sma20` | **−0.313%** |
| `sma150_over_sma200` | **−0.309%** |
| `close_over_vwap20` | **−0.265%** |
| `close_over_sma200` | **−0.257%** |

Stocks further **above** their averages had **lower** 5-day forward returns — mean reversion,
not trend continuation. **The pre-screen finding should be treated as noise**, and the
enthusiasm for it as a lesson: n=21 per quintile is exactly the sample size that has
produced two refuted promotions in this project already.

⭐ **What is now the most interesting open question: on our trades, both signals run OPPOSITE
to the broad universe.** High RVOL did *worse* for us but ranks mildly *positive* in the
universe; price-above-average did *better* for us but ranks *negative* there. Either our 105
trades are too few to mean anything (most likely), or **our entry timing is systematically
late** — buying extended, high-volume names after the move. The Minervini result (we enter
structural downtrends) is a third observation in the same area.

⚠ **Forward return is not our P&L** — no costs, no stops, no sizing. A feature can rank
forward returns and still lose money once 22–62 bps round-trip and a stop are applied.

- `backend/scripts/factor_sweep.py` — new · `docs/analysis/factor-sweep-h5-2026-09-07.md`


### feat: entry-cohort (vintage) attribution — "were that day's PICKS any good?"

**The daily report has always grouped P&L by EXIT date.** That answers "what did today
realise" — what accounting needs — and it makes one question structurally unanswerable:
*we picked 5 names on Aug 26, were those picks good?* Under exit grouping those five
decisions land on five different report days, mixed with decisions from five other days.
Selection quality is smeared until invisible.

**Grouping by ENTRY day makes it legible immediately.** On the live book:

| entry day | picks | resolved | realised | win% |
|---|---|---|---|---|
| 2026-08-26 | 5 | 4 | **−₹8,835** | **25%** |
| 2026-08-27 | 5 | 4 | **−₹4,574** | **25%** |
| 2026-08-28 | 5 | 2 | **+₹5,215** | **100%** |

Two bad selection days next to a good one — **none of which the exit-date view can show.**
Given the entry leak is the demonstrated problem, this is the view that speaks to it.

**⭐ The one rule that keeps it honest: a cohort is not final until every pick resolves.**
A day whose five trades are all still open has realised ₹0, and printing that as "flat"
would be a lie about a cohort sitting at −₹4,593 unrealised. So realised and open are
**always separate columns**, in-flight rows carry `⏳`, and best/worst superlatives consider
**settled cohorts only** — an in-flight number is not final, so ranking on it would churn as
marks moved.

**A cohort with nothing resolved has NO win rate — `—`, not `0%`.** "No data" and
"everything lost" must not render identically; the same undefined-vs-measured distinction
`app/core/ratios.py` draws for degenerate ratios.

⚠ **No schema change.** `positions.opened_at` already exists — this is a grouping, not new
data. Nothing about how a trade is recorded or priced changes. It *does* change a recorded
number's **presentation**, so it lands before cycle 2's clock by the standing rule.

⚠ **A test bug caught on first run, worth recording:** the best/worst assertion used a
single settled cohort, where `best == worst` and the block is correctly suppressed — so it
would have passed without testing anything. Rewritten with two settled cohorts plus an
extreme in-flight one.

- `backend/app/services/entry_cohort.py` — new · `app/services/daily_report.py` (wiring)
- Tests: 13 new (`tests/test_entry_cohort.py`); report suite re-verified (31 passed)


### feat(R1 pre-screen): VWAP looks real, and the EXISTING volume factor appears mis-signed

**Run before the frozen-engine work, not after** — adding a confluence factor costs a Python
impl **plus a byte-identical Rust impl**, 7 regenerated golden fixtures, exact parity on
scores/confidence/decisions, an §8 regression and a hook-protected spec change. Days. So the
cheap question came first: on the 105 trades we actually took, does either quantity separate
winners from losers?

**Two findings reshaped R1 before a line was written:**

⭐ **RVOL already exists.** `volume_factor` computes `current / 20-day average` — that *is*
relative volume, merely **binarised** at `≥1.5 → +0.5`. "Add RVOL" is really "grade the
existing binary".
⭐ **VWAP is intraday.** Session VWAP does not exist on a daily bar; anchored VWAP does, and
**choosing the anchor is a spec decision**, not an implementation detail.

**⛔ The volume factor fires on the trades that do WORSE:**

| RVOL cohort | n | mean return | win | total |
|---|---|---|---|---|
| **≥ 1.5 — the factor FIRES, +0.5 confidence** | 18 | **−0.708%** | 50% | −₹2,821 |
| < 1.5 — silent | 87 | **+0.608%** | 52% | −₹7,397 |

The graded quintiles agree: Q5 (RVOL 3.64×) is **−1.384% at 43% win**; Q1 (0.35×) is +0.419%
at 57%. **So the engine adds confidence precisely where outcomes were worse.** That is a
finding about the *existing frozen engine*, not about a proposed factor — and it is the
opposite of R1's premise that more volume confirmation is better.

**✅ The VWAP gap is the cleanest gradient this project has produced:**

| price vs 20-day anchored VWAP | n | mean return | win |
|---|---|---|---|
| Q1 (−4.41%, price below) | 21 | +0.020% | 43% |
| Q2 (−1.67%) | 21 | +0.452% | 43% |
| Q3 (−0.26%) | 21 | +0.271% | 48% |
| Q4 (+2.31%) | 21 | +0.322% | 52% |
| **Q5 (+4.96%, price above)** | 21 | **+0.845%** | **71%** |

Win rate climbs monotonically 43 → 43 → 48 → 52 → **71%**, and the direction **agrees with an
independent finding**: Minervini showed we systematically enter names in structural
downtrends. Buying strength rather than weakness shows up twice, from two unrelated tests.

⚠ **n ≈ 21 per quintile — this is a SCREEN, not a test.** Nothing here approaches t ≈ 3.6.
It exists to decide whether the expensive engine change is worth starting.

⚠ **The pre-registered prediction was partly WRONG, recorded rather than quietly dropped.**
Before running I predicted t between 0.5 and 1.5 and **<5%** odds of anything clearing the
bar, on the reasoning that VWAP/RVOL are momentum/volume-family factors and that whole group
moves expectancy by ~±0.02R. The bar part still looks right. What I did not predict was a
**monotonic VWAP gradient** or that **RVOL would point the opposite way to how the engine
already uses it**.

- `backend/scripts/r1_factor_prescreen.py` — new · `docs/analysis/r1-factor-prescreen-2026-09-07.md`


### decision(D2): R2 weekly spread-width gate — DROPPED (user sign-off 2026-09-07)

**Dropped, and the reasoning is recorded rather than assumed** so a future session does not
re-propose it as a fresh idea.

**What R2 was:** a weekly spread-width eligibility gate, approved into the Phase-6.8 research
track on 2026-08-17 as one of three gated items (R1/R2/F1).

**Why it is dropped — three independent reasons, any one sufficient:**

**1. The reading says every gate is a TRIAL, and we now count them.** The e-book review's
centre of gravity was our own biggest risk — overfitting and self-deception. Aronson
(*Evidence-Based TA*: data-mining bias, out-of-sample discipline) and López de Prado (*AFML*:
**deflated Sharpe = discount by number of trials**) both make the same point: a ninth gate is
not free even if it looks promising, because **it raises the deflation bar for the other
eight**. The U4 trials counter makes that concrete — it already stands at **15 observed
trials, and calls that a LOWER BOUND** because threshold variants are not yet recorded.

**2. Our own data says there is nothing left to partition.** H1's moving-block bootstrap on
all 105 closed positions: **Sharpe −0.033, 90% interval [−0.223, +0.118]**. At n=105 *even the
loss is not statistically established* — so any gate slicing this series is slicing noise.
That is not an argument about R2 specifically; it is why gating was closed as a programme on
2026-09-04.

**3. The empirical record of this exact move is 0-for-2.** Both gates ever promoted were
refuted: the **regime gate** (promoted on 44 observations, refuted by 88, subtracted ~8R) and
the **R:R ≥ 1 floor** (promoted on an "identity, no evidence needed" argument, refuted within
a week — it blocked the book's only profitable cohort, +₹10,585 at 63% win). The best
surviving candidate, `sl_atr`, sits at **t ≈ 0.41 against a 3.6 hurdle**.

**⇒ Dropped.** ⚠ **The idea is not forbidden — its SHAPE is.** If spread width matters it
should return as a **position-sizing / slippage MODIFIER**, exactly the reframing already
ruled for the MCE 5a liquidity gate: a modifier claims no edge, so it needs no DSR bar and
costs no trial. A21/A37 already price spread and participation into fills, which is where a
spread-width insight naturally belongs.


### feat(Q5): pre-COVID backtest — the data-sourcing spike, and it reframes the request

**Calendar item discharged** (asked 2026-08-28, held until after watch mode). This is the
sourcing spike the hold specified, deliberately **not** the backtest.

⭐ **The archive starts around October 2019.** Probed to the boundary against NSE's public
archive — the same host `bhavcopy_service` already uses daily:

| date | `sec_bhavdata_full` |
|---|---|
| 2015-01-02 / 2018-01-02 | **404** |
| 2019-09-02 (a Monday — not a holiday artefact) | **404** |
| 2019-10-01 | **200** |
| 2020-03-23 (the COVID low) | **200** |

The older compact `.zip` format 404s throughout, so `sec_bhavdata_full` is the only path and
it does not reach the requested era.

**⇒ The request as asked (2015/2018) is a NO — but what IS available is arguably better.**
The purpose behind it was *does the edge survive a different regime, including a crash*. An
October-2019 start **contains the crash itself** — the fastest drawdown in NSE's modern
history — where 2018 would have offered a credit-cycle wobble. It takes us from **3.2 years
to ~7**.

⭐ **The survivorship fix turns out to be free.** Our `stocks` table is a *today* snapshot
(2,365 active), so every name that delisted between 2019 and now is simply absent —
backtesting against it would silently exclude the failures, biased in the flattering
direction. **But a bhavcopy is the day's trading record**: it lists what traded *that day*,
delisted names included. A point-in-time universe is not a second dataset to find — **it
falls out of ingesting the bhavcopies themselves.** That materially lowers the project's
cost versus the "data-acquisition project" the original hold assumed.

**Rough sizing:** ~1,480 trading days at the existing polite cadence ≈ **20 minutes of
downloading**, plus the real work — schema drift across eras, corporate-action adjustment on
names we hold no CA history for, and symbol-churn reconciliation. **Days, not weeks.**

**⇒ Recommendation: do not start the ingestion yet — sequencing, not doubt.** The most
likely outcome is *a wider confidence interval around approximately zero* (corpus base
expectancy is +0.05R; the live book's Sharpe is −0.033 with a 90% interval
[−0.223, +0.118]). Meanwhile the demonstrated leak is upstream and untouched: **the book
lost 15% while NIFTY fell 2%.** Settle the generation-side question (D1/D5) first — a regime
test is only meaningful against an engine somebody still believes in.

⚠ **Validation, not tuning.** The engine is FROZEN for the current regime. Older data may say
whether the edge survives another one; using it to search for parameters that fit 2020 would
be the largest overfitting surface this project has ever opened.

- `backend/scripts/historical_data_spike.py` — new (`--probe` for reachability)
- `docs/analysis/historical-data-spike-2026-09-07.md` — the report


### feat(MCE 6): the news veto is NOT buildable from the data we hold — checked, then deferred

**Checked before building, and the check is the deliverable.** The phase doc specifies slice
6 as *earnings-blackout + rating-**DOWNGRADE** veto + severity/decay*. Each clause assumes a
fact about `corporate_filings`. Against the live table (**23,174 filings**, ~6 weeks), none
of the three holds:

| precondition | result |
|---|---|
| rating **direction** recoverable | ⛔ **0 of 322** `rating_change` rows say "downgrade" (8 say upgrade); the headline is a bare `Credit Rating` and the `body` is a **PDF URL we never parse** |
| earnings timing known **in advance** | ⛔ `board_meeting` rows are *"Outcome of Board Meeting"* (post-facto); `earnings` rows are *"Clarification – Financial Results"* (administrative). **No forward earnings calendar** |
| filings and signals **coincide** | ⛔ **0 of 559** signals hit the existing 1-hour guard. A **3-day** window — 72× wider — reaches **4 (0.7%)** |

⭐ **The existing 60-minute `event_guard` has never fired.** Not once since the filings feed
started. That was invisible until counted, and it is the exact failure this check exists to
prevent: a veto built on an unsupported assumption does not fail loudly — it silently never
fires and then *looks like protection* wherever it is rendered.

**⇒ DEFER slice 6.** Two of its three clauses are **unimplementable** (a downgrade veto would
match zero rows; a blackout has no forward dates to anticipate) and the third has nothing to
act on. **Building severity/decay on a gate that fires zero times is decoration** — it would
add a knob, a shadow sidecar and a daily-report line, all reporting an event that does not
occur.

**What would change the answer:** a forward earnings calendar · parsed rating documents (or
a feed carrying direction as a field) · more history — re-run the script as it deepens, and
watch the coincidence rate.

⚠ **On the RSS + FinBERT alternative (review item A18) — this needs a DECISION, not a build.**
It is a different and much larger proposal than the phase doc's slice 6: `transformers` +
`torch` is a **locked-stack change** (~2 GB) against a standing "adopt no new deps" posture,
and it puts a live third-party feed on the signal path. **And precondition 3 still applies to
it** — if filings never coincide with our signals, whether *news* does is measurable far more
cheaply than by installing a language model. Answer the cheap question first.

- `backend/scripts/news_veto_feasibility.py` — new (re-runnable as history deepens)
- `docs/analysis/news-veto-feasibility-2026-09-07.md` — the report


### feat(Q3.6): the Minervini trend template — disjoint from our engine, and that is the finding

⭐ **NOT ONE of the 91 evaluable closed positions passes all seven conditions.**

That is not an uninformative split, it is a **disjoint** one — the template and our engine
select from effectively non-overlapping sets. This book therefore cannot test it: there is
no passing cohort to compare a failing one against.

**The conditions that bind hardest are the trend-structure ones:**

| condition | entries passing |
|---|---|
| `SMA150 > SMA200` | **25 of 91** |
| `SMA200 rising` | **29 of 91** |
| `≥30% above the 52-week low` | 45 of 91 |

⭐ **Read that as a finding about OUR engine, not about Minervini.** A large majority of the
names we entered were in a structural **downtrend** on his definition — trading below or
against their own long moving averages. Our selection is not a weaker version of this
template; it is close to its opposite. Those 91 positions made **−₹18,950**.

**⇒ Neither a clean drop nor a gate.** The template makes a claim about which names should
be *eligible*, and the only honest test is a **universe-level corpus rerun** — does applying
it change what the engine generates, and is that set better? That is real work, not a shadow
gate, and it is the correct next step for anyone pursuing it.

⚠ **It must NOT be shipped as a ninth selection gate.** On this book it would block **100%
of entries** — not a filter, but a different strategy wearing a filter's clothes. That is
also exactly the move closed as a programme on 2026-09-04.

⚠ **A verdict-logic bug caught on first output.** The script's first draft branched
"does not partition ⇒ DROP", which conflates *an uninformative split* with *an empty
cohort*. A 0-of-91 result says something far stronger than "tells us nothing", and reporting
it as a routine drop would have thrown away the most interesting thing in the run.

⚠ **No look-ahead:** every condition is computed from bars strictly BEFORE the entry date
(constraint #3). ⚠ **Condition 8 (relative strength) is approximated** within the traded set
and reported separately, since Minervini ranks against the whole market from a vendor.

- `backend/scripts/minervini_template.py` — new
- `docs/analysis/minervini-template-2026-09-07.md` — the report


### feat(Q2.4): the momentum ×1.5 retune — DECIDED NO, without waiting for forward evidence

**The forward route was dead.** The 6.4 shadow A/B has minted **7 signals per arm and
resolved 0 in 21 days** (worse than the "3 minted / 0 resolved in 6 days" on file). At that
rate the decision is years away — "wait for forward evidence" was a way of never deciding.

⚠ **The queued task was misframed and the correction matters:** it asked to *build* a
backtest path. One already existed — `scripts/weight_retune.py`, the 6.4 sweep. Building a
second would have been the parallel implementation W2 forbids. What was actually missing was
an **instrument**: the original picked best-of-12 on the full corpus and said so in its own
verdict, with `folds+` as its only guard against a lucky pick.

So `scripts/retune_dsr_verdict.py` runs the **existing** sweep through the deflated-Sharpe
bar — built 09-03, validated by H8 on 09-04, and made for exactly this shape of problem.
Two refinements over the original: the trial count is honest (**13** = baseline + 12), and
the trial dispersion is **measured** from the configs we actually ran rather than the bar's
conservative `1/√n` fallback.

**Result: not one config clears the bar.** `momentum ×1.5` stands at **t = +1.00 against a
≈3.6 hurdle** — DSR 74.8% vs a 95% bar, needing ≈4,453 observations against the 734 it has.

⭐ **And the sharper finding, which no single statistic gives you: THE WINNER MOVED.** August
put `momentum ×1.5` top on total-R (+50.4). Re-running the *same method* on a slightly larger
corpus puts **`structure ×0.5` first**, with the whole table separated by fractions of a t.
**A ranking that reshuffles when the sample nudges was never measuring an ordering** — which
shows the original pick *was* the selection, not an edge under it.

**⇒ DECIDE: NO.** The retune is not promotable and the forward A/B stops being carried as a
pending decision. Same shape as `sl_atr` (t ≈ 0.41, decided NO 09-04): **the instrument
working, not failing.** `gate_register` updated to `DECIDED_NO`.

⚠ **Limits kept in the report:** deflation prices the *selection*, not the missing holdout —
this is still in-sample, and a pass would have meant "worth a real out-of-sample test", never
"promote". And the lever is per-**GROUP** while the 6.2 leak is per-**FACTOR**, so a null here
argues for per-factor weights (a larger, frozen-engine change) rather than closing the
question.

**Also fixed:** the script stamped its report in **UTC** where every other analysis script
uses **IST** — which labelled an early-morning IST run with yesterday's date and would have
put it out of order beside its siblings.

- `backend/scripts/retune_dsr_verdict.py` — new · `app/services/gate_register.py`
- `docs/analysis/retune-dsr-verdict-2026-09-07.md` — the report


### feat(F1): would a market-cap size floor have helped? — the cheap cross-tab says no

**The half of F1 that needs no vendor**, and it changes what D3 is worth. MCE 5b proposes a
market-cap floor on the junk gate; building it means choosing a fundamentals vendor (D3) and
paying for an XBRL scraper. The standing instruction was to *cross-tab a cheap proxy first*,
because 5a already found the illiquid cohort net-**positive** and questioned 5b's premise.

We have no `market_cap` — that is what 5b would build — so the spike tests the two things
such a floor would be *proxying for*, across all 105 closed positions:

| by median daily traded value | mean return | win |
|---|---|---|
| Q1 (₹0.42 Cr — smallest) | **+1.517%** | 67% |
| Q5 (₹254 Cr — largest) | **−0.443%** | 48% |

| by entry price level | mean return | win |
|---|---|---|
| Q1 (₹67 — cheapest) | **−0.703%** | 52% |
| Q5 (₹3,518 — dearest) | **+0.210%** | 43% |

⭐ **The two proxies point in OPPOSITE directions.** By traded value the smallest names did
best; by price level the cheapest did worst. If a size effect were driving outcomes, two
measures of size would agree — two that disagree are not measuring it. Neither is monotonic
across its own quintiles either.

⭐ **And neither contrast survives its own bootstrap**: traded-value Q1−Q5 is
`[−0.083%, +3.957%]`, price-level Q1−Q5 is `[−3.220%, +1.473%]` — **both span zero**. So the
case is doubled: no agreement *and* no significance.

**⇒ Recommendation: DROP MCE 5b. D3 (the vendor decision) becomes moot** until someone
produces a reason to revisit the premise. Consistent with the 5a ruling, where the liquidity
floor would have cut a net-*winning* set and the already-ACTIVE diversity gate caught the
SRTL archetype anyway.

⚠ **What this cannot say:** a proxy result cannot *prove* a market-cap floor would fail. It
shows the free evidence declines to support one — which is decisive for **sequencing**,
since paying a vendor to test a hypothesis the cheap data already doubts is the expensive
way to learn it. Also: n=21 per bucket, traded value is not market cap, and these are the
names our engine chose rather than a cross-section of the market.

- `backend/scripts/size_proxy_spike.py` — new (deterministic, seeded)
- `docs/analysis/size-proxy-spike-2026-09-07.md` — the report


### feat(A3): broker-token status, and what its lapse silently costs

The Kite access token dies **~06:00 IST every day**. Across cycle 2's 45–50 trading days
that is 45–50 chances for it to lapse unnoticed, and the failure chain is quiet by
construction:

> token lapses → the tick feed stops → `depth:{stock_id}` expires at its 60 s TTL →
> 6.8.2's spread-aware fills fall back to the FLAT floor →
> **paper fills quietly CHEAPER than reality**

⭐ **That last step is why this is a data-QUALITY control, not an ops convenience.** A dead
feed does not merely *interrupt* the record — it **corrupts** it, in the direction that
flatters us, and 82% of live NSE books are wider than the flat 2 bps the fallback charges.
A cycle-2 window read off those fills would overstate the edge. The alarm says exactly that,
pinned by test, because "token expired" on its own reads as an annoyance and gets
deprioritised.

**`absent` and `expired` are kept distinct** even though both mean "no usable token now":
one is a token never obtained, the other one that worked and aged out. Same remedy,
different diagnosis — and a report that conflates them teaches people to ignore it. A test
asserts exactly one of {absent, expired, expiring_soon, healthy} holds at any moment, so a
render branch cannot pick the wrong message.

**A warning is one line; an alarm is a block quote.** Rendering a still-working token as a
full alarm would train the reader to skip alarm blocks — which is the failure mode that
makes every *other* alarm in the report worthless.

⚠ **Expiry is a NORMAL lifecycle event, never an error loop** (trading-domain rule), and
the alarm says so — Kite's login needs a human at a browser, so a retry loop would spin
forever. The remedy is named in the message.

⚠ **It never raises.** A health probe that can take down the report it appears in has
inverted its own purpose; a failed read degrades to `absent`. Same rule
`worker_health.read_statuses` already follows.

Shaped to match `worker_health`'s `render_lines` contract and rendered beside it, rather
than opening a second health surface (**W2**) — both answer the same question: *is the
machinery that produced these numbers actually alive?*

- `backend/app/services/token_health.py` — new · `app/services/daily_report.py` (wiring)
- Tests: 16 new (`tests/test_token_health.py`); report suites re-verified (63 passed)


### feat(A27): config dry-run — what does `.env` say, and which live process has heard it?

**`make config-check`.** `get_settings()` is an `@lru_cache` singleton, so a `.env` edit
reaches a running backend or worker only when that process re-imports `app.core.config`.
Editing the file and assuming it took effect has bitten this project repeatedly — it is why
CLAUDE.md carries a hand-run recipe for the same question. This is that recipe as a command.

**Why it earns being pulled out of Bucket C:** the **cycle-2 reset is itself a config
event** (heat cap → `active`, paper clock → restart). Getting that wrong silently does not
cost a day, it invalidates the *window* — 45–50 trading days.

**It never reads `.env` and never prints a credential.** Values arrive through pydantic's
own loader; the file is only ever `stat`-ed for its mtime. Masking is **name-based**, so a
conventionally named secret is covered without anyone remembering to add it — and the test
that matters runs over the **real** `Settings` model with a sentinel substituted for every
field, rather than over a handful of examples. A companion test asserts the rule actually
*matches* the known credentials, because an `_is_secret` that classified nothing would make
the leak test pass vacuously.

**It splits uvicorn's parent from its `--reload` child**, which is the specific error the
manual recipe warns about: the parent never re-imports config, so its start time says
nothing about which values are live.

**Three honesty fixes made after seeing its first real output:**
- it said *"Rails at their CODE DEFAULT (nothing in .env)"* — but the script deliberately
  does not open `.env`, so it cannot tell *absent* from *set to the same value*;
- it printed a green tick when there was **no `.env` at all** — the case where it knew
  *least*;
- ⭐ **exit `1` (could not check) is deliberately not exit `0` (checked and clean).**
  Sharing a code would let a CI check pass on a box with no `.env` — precisely the
  configuration most likely to be wrong.

⚠ **The staleness verdict is over-sensitive on purpose.** `.env` being newer than a process
start proves the process *may* hold old values, not that the knob you care about changed.
The failure it guards is silent, so a false alarm costs a re-read and a miss costs a window.

⚠ **The `.env`-present path is not yet exercised end to end** — this branch is an isolated
worktree, which has no `.env`, so only the "could not check" path ran for real.

- `backend/scripts/config_dryrun.py` — new · `Makefile` (`config-check`)
- Tests: 21 new (`tests/test_config_dryrun.py`)


### feat(CAS-2): the overnight-reversal study — a real signal, and its honest limits

**The auction move REVERSES overnight, cross-sectionally.** Spearman **ρ = −0.272**
(Pearson −0.320), 90% day-block interval **[−0.478, −0.088]** — **excludes zero** — 6 of 7
days negative, monotonic quintiles, **Q1−Q5 spread +1.27%**.

**This is the first clean directional signal the programme has produced** after eight
refuted gates, which is precisely why it gets the strictest reading available rather than
the friendliest.

**The control is cross-sectional, and that is what makes it worth anything.** Both series
are demeaned *within* each day, which removes the market factor exactly rather than
approximately — the standing *"control for the oversold regime"* warning. A naive
correlation on a market that sagged into the close and bounced next morning would measure
beta and call it an auction edge. ⚠ By construction it therefore says **nothing** about a
market-wide auction effect; it answers the relative question only.

**The independent unit is the DAY, not the row.** 1,664 rows looks like a lot and is not:
208 names on one afternoon share one market, so there are **7 usable blocks**. Every
interval resamples **whole days** — resampling rows would treat correlated observations as
independent and make the interval roughly **√208 ≈ 14× too narrow**. `block_bootstrap.py`
is deliberately not reused: it bootstraps a *Sharpe* from a return series, and this
statistic is a cross-sectional correlation over day-groups.

**⭐ The tail check (constraint #8) splits, and the split is the finding:**
- **SIGN survives every single-day removal** — all 7 leave-one-out values negative.
- **MAGNITUDE does not.** Dropping 2026-08-31 takes ρ from −0.272 to **−0.125**, about 46%
  of the full-sample estimate — so **roughly half the measured effect rests on one
  afternoon**, and that day carries ~5× the cross-sectional dispersion of every other.
  Direction is consistent; size is not. Anything sized off the full-sample number would be
  sized off that one day.

⚠ **NOT a promotion signal**, and the report says so itself. 7 independent days cannot
clear the t ≈ 3.6 hurdle however clean the sign looks, and **that hurdle is flat in n** —
more data does not lower the bar, it only moves the estimate. Keep the Stage-1 capture
running (it costs nothing) and re-run at ≥30 days.

- `backend/scripts/cas_stage2_study.py` — new (deterministic, seeded, rerunnable)
- `docs/analysis/cas-stage2-2026-09-07.md` — the report


### feat(7.4): kill switch, restart recovery, and reconciliation

**Phase 7.1–7.4 are now complete** — the cycle-2 runtime prerequisite.

**The kill switch is the first rule the RiskEngine runs**, ahead of even the daily-loss
breaker: someone who has hit stop should not have to reason about which *other* rule might
still let an order through.

⭐ **It deliberately does NOT block exits**, and that is the property that makes it safe to
use. A switch that halts new risk *and* traps you in what you already hold is a hazard
dressed as a safety feature — the moment you most want to stop trading is often the moment
you most need to close something. Asserted end-to-end (`test_it_does_not_block_exits`) so a
future refactor routing exits through the RiskEngine cannot silently make it a trap.

⚠ **It is a plain bool with no `shadow` mode**, pinned by test. A kill switch you can set
to measure-only is not a kill switch, and the three-valued gate vocabulary would invite
exactly that.

**Recovery and reconciliation are kept apart**, because conflating them hides which one
found something. *Recovery* rebuilds our view from our own durable record
(`load_events → project`) — deterministic, needs no broker, and **idempotent**, which is
what makes it safe to run unconditionally at startup rather than behind a "have we
recovered yet" flag that would itself need recovering. *Reconciliation* compares our view
against the broker's.

⭐ **Reconciliation reports what it could NOT check, even on a clean run.** Every paper
submit ends terminal inside one transaction, so `fetch_open_orders()` is structurally empty
and the order-matching half verifies **nothing**. A run saying "clean" without that caveat
would read as evidence that reconciliation works when it is evidence there was nothing to
reconcile — so `Reconciliation.caveats` travels with the result and `summary()` prints it.

**It reports; it never repairs.** A reconciler that "fixes" a disagreement it does not
understand can turn a reporting discrepancy into a real position, and the disagreements
worth having are the ones nobody anticipated. A16's durable repair queue is where a
human-approved fix belongs. `unknown_to_us` and `unknown_to_broker` stay separate and
neither is called an "error" — they mean opposite things and demand opposite responses.

**T2 lifecycle boundaries** cover the seams a restart actually lands on: first step on an
empty world, start mid-stream (between `accepted` and `filled` — the case that decides
whether a restart loses a fill), and stop early (a `submitted`-but-undecided order is still
ACTIVE and must surface, not be dropped).

- `backend/app/broker/reconcile.py` — new · `app/trading/risk_engine.py` (kill switch) ·
  `app/core/config.py` · `.env.example`
- Tests: 19 new (`tests/test_reconcile.py`)


### feat(7.3): the order-event stream, the FSM, the bus, and the live-path cutover

**COMPLETE.** (The first half below shipped as machinery; the cutover followed in the same
session — see the addendum at the end of this entry.)

**Machinery first.** `order_events` (migration applied to dev and verified
reversible) · `OrderEventRow` · `app/broker/order_fsm.py` · `app/broker/event_bus.py`.
**The durable event writer and the live-path cutover remain**, so `place_order` still calls
`place_paper_order` directly and no behaviour or recorded number changes.

**Why the table exists.** Today a refused order is not a row at all — every refusal raises,
and `Order.status` carries exactly two values in the codebase. So the orders table records
only successes, and *"what did the risk layer refuse last Tuesday, under which thresholds?"*
is unanswerable. Writing `submitted` **before** the gates run turns that from a logging gap
into a structural guarantee: the row exists before the decision is made.

**Two FSM rows worth reading.** `SUBMITTED → DENIED | REJECTED` — both refusals leave the
same state, which is exactly why they must be distinct *kinds*; the projection cannot
recover the distinction after the fold. And `CANCEL_REQUESTED → FILLED` is **legal**: a
cancel losing the race to a fill is a routine market outcome, and making the FSM raise on
it would invite someone to stop it raising at all.

**Fill quantities are CUMULATIVE, not deltas** — idempotent under replay, which is how the
projection survives a restart. With deltas, one duplicated event silently doubles a
position. **A sequence gap raises** rather than returning a state that looks fine.

**The bus does four things and refuses a fifth**: per-handler exception isolation (a
reporting bug must not fail a fill — errors are *counted and named*, so swallowed ≠
invisible) · snapshot iteration · a bounded queue with a *stated* policy (`REFUSE` for
order events, because losing one loses a fill; `DROP_OLDEST` still counts what it drops) ·
and **a dead bus is LOUD** — publishing to a stopped bus raises, because a bus that died
early must not look identical to a quiet market. Synchronous by design: the order path is
already in a transaction when events are emitted, and a handler that persists one must run
in *that* transaction.

**▶ Addendum — the cutover, same session.** `place_order` now writes `submitted` **before
the RiskEngine runs**, then `denied` (with the RULE that refused) or `rejected` (the paper
broker's own unconditional pre-fill refusals, `error_class=terminal`), or
`accepted` + `filled` on success.

⭐ **The defect this could easily have shipped with.** `get_db` rolls the session back when
a handler raises. Without an explicit commit **before** `raise HTTPException`, the denial
row is written and then discarded — the record vanishes in precisely the branch it exists
to capture, and every other test still passes. Both refusal branches now commit first, and
`test_denial_survives_the_exception` is the test that file exists for.

⚠ **CORRECTION to the 7.0 design, which said `orders` would become a list of intents.**
It does not, and the built version is safer: intents live in `order_events` only, `orders`
still gets a row exactly when a fill happens, so **no existing `orders` reader changed
meaning**. The design doc has been fixed on discovery (W1).

⚠ **`next_seq` is read-then-write and therefore NOT a lock.** Correct under the
single-writer order path we have; the `UNIQUE(client_order_id, seq)` constraint is what
catches the day that stops being true, which is why `append()` raises a named
`DuplicateSequenceError` rather than letting an opaque DB error surface.
⚠ **`append()` flushes but does not commit** — the caller owns the transaction, because
`submitted` and `denied` belong to the same unit of work as the decision itself.
⚠ **There is deliberately no DB `EventSink`**: a sink is synchronous and persisting needs
an await, so routing it through the bus would mean an orphan task writing *outside* the
caller's transaction.

- `backend/alembic/versions/d0e1f2a3b4c5_add_order_events.py` · `app/models/trading.py`
- `app/broker/order_fsm.py` · `event_bus.py` · `event_store.py` — new ·
  `app/api/v1/trading.py` (cutover)
- Tests: 42 new (`test_order_fsm.py` 32, `test_order_events_wiring.py` 10); order-path
  regression 212 passed; `mypy app/ scripts/` clean (265 files)


### feat(7.2): the BrokerAdapter port, and a read-only Kite spike to check its shape

**One rule the rest follows from: `submit()` returns an `Ack`, NEVER a `Fill`.**

Paper *can* fill synchronously — it does today, inside `place_paper_order`'s transaction —
and `PaperBrokerAdapter` still returns an `Ack` and then emits `FILLED` on the same event
channel a real broker will use. **The asynchrony is imposed on the paper side rather than
papered over on the Kite side**, because the alternative is that every caller gets written
against a synchronous world and the abstraction is discovered to be wrong on day 1 of
live — the exact failure the two-cycle plan exists to prevent. A structural test asserts
`Ack` carries no fill fields at all.

**A refusal is an `Ack`, not an exception.** A through-stop or notional-cap rejection comes
back as `AckStatus.REJECTED` with a reason and a `REJECTED` event, rather than as something
the caller must catch. That is the distinction 7.3's FSM is built on — and without it a
refusal leaves no trace, which is the hole 7.0 identified.

**`DENIED` and `REJECTED` stay separate**, pinned by test: *denied* is our own risk layer
and entirely within our control, so a rising denial rate is a finding about our thresholds;
*rejected* is the broker's. One "failed" bucket destroys the only signal separating "our
rules are too tight" from "the exchange said no".

**`is_active()` is declared once** with an exhaustiveness test that every `EventKind` is
active-or-terminal exactly once — the T7 shape, where a mis-filed state would make A42's
available-cash derivation quietly wrong rather than loud.

**The read-only Kite spike** (`scripts/kite_readonly_spike.py` + three read-only methods on
the existing `ThrottledKite`) validates the interface against reality before
`KiteBrokerAdapter` is written from the docs alone. ⚠ **`ThrottledKite` deliberately has no
`place_order` method** — placement is post-cycle-2, and the *absence of the method* is the
safeguard rather than a flag on the script.

**⭐ The spike already surfaced the interface question that matters**, without needing to
run: `BrokerOrder.client_order_id` is how reconciliation matches a broker row back to ours,
and **Kite has no client-order-id field** — the nearest thing is `tag`, **capped at 20
characters** and not broker-guaranteed unique. Our namespaced ids (`paper:<uuid>`) do not
fit. Three options, and the choice is the user's: short live ids that fit a tag · match on
`(symbol, side, quantity, timestamp)` (ambiguous exactly when two identical orders are
placed close together) · or a local `broker_order_id → client_order_id` map written at ack
time, accepting that an order lost *before* its ack is unmatchable. **(3) plus a short tag
is the likely answer.** This is precisely what would otherwise have been found on live day 1.

⚠ **Nothing is wired into the live order path.** `place_order` still calls
`place_paper_order` directly. No behaviour, no recorded number changes.
⚠ The spike's own report says so, but it bears repeating: **a clean run on an account with
no orders and no positions verifies almost nothing** — the shapes stay unverified until it
runs on a day with at least one order.

- `backend/app/broker/adapter.py` — new · `app/broker/paper_adapter.py` — new
- `backend/scripts/kite_readonly_spike.py` — new · `app/broker/kite_rest.py` (read-only)
- Tests: 27 new (`tests/test_broker_adapter.py`); full suite **2028 passed / 0 failed**


### feat(7.1 + A13): the RiskEngine single-gate, equivalence-pinned, and the heat cap

**Every pre-trade rule now runs in ONE place** — `app/trading/risk_engine.py`. They were
scattered across three files and two call sites, which matters because `place_order` is
not the only way an order can be born: the position monitor closes positions, and 7.2–7.4
add a broker adapter and a repair queue. A sequence typed out at one call site means every
new caller re-derives it, and the rules it forgets are the ones that never fire.

**It composes; it does not reimplement.** Each rule keeps exactly one definition and the
engine knows their ORDER. `restrictions.py` (A38) stays the single declaration of the
eligibility gates and is *walked*, not copied — a second sequence is what W2 forbids and
what the display/order drift of 2026-09-02 cost us. `_check_notional_cap` is now the
broker's *raising wrapper* around `risk_engine.notional_cap_reason`, and a test asserts
the two produce the same words.

**⭐ The equivalence pin is the point.** `tests/test_risk_engine.py` transcribes the
pre-7.1 chain literally and diffs the engine against it case by case — a pin that called
the thing it was pinning would prove nothing.

**⚠ It caught a real ordering inversion before it shipped.** The breaker runs BEFORE the
signal is looked up, so an unknown id while the breaker is tripped answers **409, not
404**. The natural refactor — hoist the lookup into the caller so `signal` is
non-optional — silently flips that. So "does the signal exist" is a RULE inside the engine
(`RULE_SIGNAL_MISSING`), the caller maps it to 404 and everything else to 409, and the
pair is pinned by `test_breaker_beats_missing_signal`.

**Two phases, and that is the shape of the problem rather than a compromise.**
`check_pre_trade()` needs only the signal; `check_sizing()` needs `qty` AND `fill_price`,
and `qty` does not exist until the fill price resolves — which after A37 itself depends on
`qty` (the participation term is quadratic, so `q → size(fill(q))` has no fixed point).

**The heat cap ships BUILT and `off`.** `heat = qty × max(0, entry − commit_SL)`, initial
risk (never mark-to-market — a from-the-mark definition *loosens* as the book
deteriorates), from the **commit** stop (never the trailed `current_sl`, which would let a
book gain budget merely by being right; pinned by test). Off is deliberate: a 6% cap cuts
cycle-1 entries ~74% and cycle 1 exists to accrue volume. It flips at the cycle-2 reset.

**⚠ Unlike the six selection overlays it FAILS CLOSED** — an open position whose risk
cannot be measured refuses the next entry rather than counting as zero. For a selection
gate the error to avoid is suppressing a good trade on uncertainty; for a risk rail it is
taking risk you cannot count.

**A13 — the breaker cannot be suppressed.** 7.1 refactors the daily-loss breaker *into*
the RiskEngine, which is exactly when a hard constraint can be quietly lost, so it is
pinned rather than left to whichever call site invokes it: it runs first, no `Settings`
field can disable it (the absence of a knob IS the guarantee, so the test asserts the
absence), and it still denies with **every** gate mode forced to `off`.

**A refactor that moved code, correctly.** `_load_restriction_context` was never
API-layer code — it loads the live state the gates judge, and the RiskEngine needs it
too. Leaving it in the router forced `app.trading` to import from `app.api`, which is a
cycle and the wrong direction. Now `app/signals/restriction_context.py`; behaviour
identical, five tests re-pointed at its new home.

**⚠ The heat cap STAYS a counted trial in the gate register.** Unlike `notional_cap`,
which never claimed an edge, this hypothesis did make one — "capping aggregate heat
improves outcomes" — and was tested against the counterfactual and answered no.
Re-labelling it a pure safety rail because that is how it ships would retroactively drop
an attempted, failed trial from the count, which is precisely the selection bias the
deflation corrects. `trials_attempted()` stays 15.

- `backend/app/trading/risk_engine.py` — new · `app/signals/restriction_context.py` — new
- `app/api/v1/trading.py` · `app/broker/paper_broker.py` · `app/core/config.py` ·
  `app/services/gate_register.py` · `.env.example`
- Tests: 33 new (`tests/test_risk_engine.py`); 5 re-pointed after the move
- `mypy app/ scripts/` clean (259 files); no recorded number moves (heat cap `off`)


### docs: the pre-cycle-2 queue, and a branch to carry it (2026-09-06)

**New working branch `feature/pre-cycle2-hardening`**, cut from
`feature/phase6-overlay-walkforward-retune` @ `518b84f` with user approval (branch creation
needs it — working rule W4). It carries everything still owed **before cycle 2's clock
starts**.

**The entry check was run against artifacts, not checkboxes** (W1), because the plan's own
Bucket-B table had gone stale against the harvest queue below it — four items showed no ✅
in one place and DONE in the other:

- **Bucket A — COMPLETE**, 8 items: A38 `restrictions.py` · A21 `exit_mark` · A37+T3
  `participation_bps` · A29 `dp_charge_per_sell` · A23 `SCHEDULE_HISTORY`/`schedule_for` ·
  A26 `apply_hotset_cap` · A25 `tick_mode.py` · H6 `ratios.py`. (A30/A31 subsumed by A38.)
- **Bucket B — COMPLETE**, 11 items: H8 · H1 `block_bootstrap.py` · H2 · H12 · T11 · H11 ·
  H4 + U4 `gate_register.py` · H3 · T7 · A24.
- **Bucket C — 7 of ~60**, deliberately: W1–W5 · A11 · A40. The rest builds *under* cycle
  2's clock, which is what the findings doc's sequence asks for — with **three slices
  proposed for pulling forward** on the same argument that already moved A11/A40
  (*"safe to ship mid-cycle" answers whether a change will disturb the record, not what
  protects the record while it is being made*): **A13** the breaker's un-suppressibility,
  which must ride in 7.1's own commit because 7.1 refactors the breaker into the RiskEngine;
  **A27** the config dry-run, because the cycle-2 reset is itself a config event and
  `settings` is an `@lru_cache` singleton; and **A3** broker-token status, because the Kite
  token dies daily and a silent lapse makes fills quietly cheaper than reality — corrupting
  the recorded numbers rather than merely interrupting them.

Every one of those 19 items was confirmed to have **code and tests on disk** — not a doc
claim. `docs/phases/pre-cycle2-queue.md` records the queue, the dependency order, and the
**five open decisions** (D1 frozen-engine sign-off for R1 · D2 R2 build-or-drop · D3 the MCE
market-cap vendor · D4 concentration/sizing · D5 `compute_levels` payoff geometry).

**Three things the ask did not include, now surfaced in the queue:**

1. **"The rest of Phase 6 / 6.8" has no unbuilt slices.** Both phases are GATE PASSED +
   CLOSED (2026-08-20). What remains is the shared gated research track `R1/R2/F1` plus
   three forward-evidence loops — one decided, one **stalled** (momentum ×1.5 at 3 minted /
   0 resolved in 6 days, so forward accrual cannot settle it), one accruing.
2. **R2 contradicts a standing ruling.** Gating was closed as a programme on 2026-09-04, and
   Bucket B then measured the book's Sharpe at −0.033 with a 90% interval **[−0.223,
   +0.118]** — at n=105 even the loss is not established, so any gate partitioning this
   series is partitioning noise. A ninth gate also adds a trial, raising the deflation bar
   for everything else. **Recommend drop, or re-scope as a sizing/slippage modifier** — the
   same reframing already ruled for MCE 5a liquidity.
3. **The demonstrated lever was not in the ask.** `compute_levels` pairs a structural stop
   with an absolute-% target, so **94 of 295 swing signals have R:R < 1 by construction**
   against a 1.67R break-even. It is on the cycle-2 entry checklist and it changes a
   recorded number.

- `docs/phases/pre-cycle2-queue.md` — new · `docs/PHASES.md` CONTINUE HERE rewritten
- No code changed; no recorded number moved.


### feat(A40): worker liveness and the absence alarm (2026-09-06)

**Bucket C, pulled forward with A11 as the other half of the same argument.** A11 pushes
from `finally` blocks, so it reports what **ran**. The failure that costs us is the opposite
shape — **the window passed and nothing ran** — and no `finally` fires for a task that never
started, so a silent worker produces a silent channel and a quiet channel gets read as
"fine". A11 could not close that by construction; this does.

Two standing human rituals were this failure in costume, and both are now alarms: CAS
capture (**a missed window cannot be back-filled**; the protocol was "check the row count
each morning") and provisional health (no scheduler at all).

**A staleness check, not a metrics stack** — the same ruling that kept 6.8.6 from becoming a
Prometheus deployment. Heartbeats are Redis keys with a TTL; **absence is the signal**, so
there is no counter to scrape.

**Three layers, and each one states what it cannot see:**

1. **Heartbeat** — `worker:heartbeat:{role}`, written by the Celery worker (a beat task) and
   by `live_worker`'s monitor loop, which is the thing that actually proves ticks are being
   processed. *Blind to:* a role that dies mid-window and restarts before anyone looks.
2. **CAS window coverage** — after 15:33 IST, did the day produce rows? This is the alarm
   A11 structurally could not give, because it fires on an absence. *Blind to:* a worker
   down continuously past the check, since it is itself a beat task and needs the worker
   back up to report. It catches "died during the window, returned later" — the common case.
3. **The daily-report section**, rendered **above** the scorecard because if the worker was
   down every number below it is suspect. This runs in a different process from the worker,
   which is what closes layer 2's blind spot.

**⚠ No layer is self-sufficient, on purpose.** A checker living inside the thing it checks
cannot report its own death. That asymmetry is why layer 3 exists and why `make analysis` is
the surface that must not be skipped.

**⚠ A real defect found while wiring it: `app.tasks.health_tasks` was missing from Celery's
`include`**, so the heartbeat beat entry named a task that would never register — the alarm
would have been **silently dead**, which is precisely the failure mode A40 exists to
prevent. A contract test now imports every module in `include` and asserts every beat entry
resolves to a registered task, so no future beat entry can point at nothing.

Verified against the real database: 2026-09-04 reads `trading=True, closed=True, rows=208 →
not missed`; the weekend days correctly read as non-trading; both roles render the loud
alarm because no worker is currently running.

Also, unlike A11, **this section speaks when everything is fine** — "✅ all roles current".
The opposite policy, deliberately: it is the only place an absence can be seen, so its
silence has to be a positive statement rather than nothing at all.

- `backend/app/services/worker_health.py` — new · `app/tasks/health_tasks.py` — new
- `backend/app/tasks/cas_tasks.py` · `app/celery_app.py` · `app/broker/live_worker.py` ·
  `app/services/daily_report.py`
- Tests: 16 new (`tests/test_worker_health.py`)

### feat(A11): session notifier with a noise policy (2026-09-06)

**Bucket C**, and the item the external review called *"the most actionable in this whole
document"*. We have standing **manual daily human checks that exist only because nothing
pushes**: CAS capture — the worker must be up 15:15–15:33 IST and **a missed window cannot
be back-filled** — and provisional health, which has no scheduler at all. Both are detected
today by someone remembering.

`app/services/notifier.py` is the policy plus a vendor-neutral transport. The policy is the
valuable part, so it is pure and tested separately from delivery:

- **Silence is the default for routine success.** The CAS task fires every minute of the
  market day and returns `skipped: outside CAS window` ~1,400 times; `INFO` never sends.
  Verified end-to-end against the real task: it returned `skipped` and produced nothing.
- **The artifact is the confirmation.** `make analysis` notifies on failure only — the
  written report is the evidence it ran, so a "completed" push would be pure noise.
- **Any exception ALWAYS notifies, bypassing every rule including the throttle.** A crash is
  the one thing no noise rule written for routine traffic may silence.
- **Repeats are throttled and the suppressed count rides the next message** — `(+37
  suppressed)`. Never a silent throttle: a growing count *is* the signal that something is
  worsening while being suppressed.
- **A missing channel is a silent no-op and delivery failure is swallowed.** Unset is the
  default and not a degraded mode — the policy still runs and still logs at the level it
  chose.

**⚠ A defect this found in itself, and the test that pins it.** The never-raises contract was
enforced inside `notify()` but **not in the wrappers callers actually use from a `finally`**.
Building the message is caller-supplied work — `str(exc)`, `str(value)` — and can raise
*before* `notify` is reached. An exception whose `__str__` raises escaped straight through a
`finally` and would have masked the original error: exactly the failure mode that gets
notifiers deleted. It now degrades to the exception's **type** and still sends, because the
type is the half that distinguishes a bug from an outage.

**⚠ What this cannot see: an ABSENCE.** Wiring into `finally` reports what *ran*. The CAS
alarm we actually want — the window passing with the worker down — is a thing that did not
happen, and no `finally` fires for it. That is A40's job. **A quiet channel must not be read
as "the capture worked"**, and the module, the setting and `.env.example` all say so.

Wired: CAS capture (`finally`, catching `BaseException` so a wrapper kill still pushes) ·
`make analysis` · provisional health, which now pushes the two conditions it was written to
find — no health key across the window (the worker did not run) and A26's protected hot-set
overflow.

Per **W3**, the new `NOTIFIER_WEBHOOK_URL` lands with its `.env.example` entry in this commit.

- `backend/app/services/notifier.py` — new · `app/core/config.py` · `.env.example`
- `backend/app/tasks/cas_tasks.py` · `scripts/daily_analysis.py` ·
  `scripts/provisional_health.py`
- Tests: 20 new (`tests/test_notifier.py`)

### docs(W1–W5): the five working rules, and Bucket C restored to the plan (2026-09-06)

**The gap first.** `docs/PHASES.md` summarised the execution plan as Bucket A → Bucket B →
P7/MCE/CAS-2, and **never mentioned Bucket C at all** — roughly 60 items, made invisible in
the one doc that is supposed to be canonical. Found only because the user asked. That is
working rule W1 in its own right: the findings doc and the status doc disagreed, and the
status doc was the wrong one.

Bucket C is now recorded in PHASES **with its sequencing intact**, because the omission
would otherwise invite doing it next, which the plan explicitly does not want: Bucket C runs
*underneath cycle 2's clock, continuously* — "build only what must be frozen, start the
clock, and let the remaining ~60 items land while the evidence accumulates."

**The W rules were the one part genuinely due now** — the plan's sequence puts them in
parallel with Buckets A and B, ~1.5 h total, and they were missed. All five are written into
CLAUDE.md as "Working rules", each anchored to an incident in this repo rather than borrowed
as a generic best practice:

- **W1 doc/code precedence** — the executable content wins and you fix the doc *in the same
  change*. A precedence rule, not the value "conflicts are bad": it says what to DO on
  finding one, and it applies on **discovery**, not only when you changed something. Two
  incidents behind it, including `market_regime.py` calling our VIX history "too shallow
  (~weeks)" when it held 784 sessions — which is exactly why that threshold went unexamined.
- **W2 no parallel implementations** — the rule with the most evidence here: five separate
  Buy surfaces, one unwired, eligibility gating retrofitted across all of them; and the gate
  vocabulary declared nine times and tied together nowhere.
- **W3 same-commit config hygiene** — a new config item updates `.env.example` and its docs
  in the same commit. The narrow checkable instance of the doc-sync ritual.
- **W4 the git boundary** — commit freely on the working branch, never push; branch creation
  needs approval. Stated rather than inferred, because "reserve push only" is a choice.
- **W5 no hardcoded copy of a value that has an owner** — including **gate modes**, the
  non-obvious clause: `STATUS.html` hardcodes them in prose, two tables, an ASCII diagram and
  the KPI tiles with no data source, and it has bitten twice.

- `CLAUDE.md` · `docs/PHASES.md` · `docs/quant-agent-findings.md`

### fix(H12): a market-driven GAIN and a market-driven LOSS are different findings (2026-09-06)

Found by running `make analysis` against the real book rather than by a test: the flag
printed **⚠ MARKET-DRIVEN** beside a **positive** per-trade alpha, which reads as "your edge
is fake" while the arithmetic said something else entirely — beta +0.92, alpha +0.0010, and
the market explaining **−0.0031** of the mean outcome. The market had sunk an
otherwise-positive alpha.

Both are real and they are opposite findings. A market-driven **gain** is the failure mode
H12 exists to catch: a directionally-biased cohort in a trending window looking like skill —
precisely how the market-regime gate's evidence became a proxy for SIDE. A market-driven
**loss** says the exposure sank the cohort, not that the signals were empty.

The flag now branches: `MARKET-DRIVEN GAIN` names the skill illusion, `MARKET-DRIVEN LOSS`
notes that the alpha is the opposite sign, and a market-neutral cohort gets no gloss at all.
The A24 rule applied to our own output — a caveat must branch on the data, because one
sentence covering both cases is wrong in one of them.

- `backend/app/services/beta_ir.py` — `market_helped`, branched render
- Tests: 3 new (`tests/test_beta_ir.py`)

### feat(H3): the VIX companion is a trailing percentile, not an inherited absolute (2026-09-05)

**Bucket B, item 10 — the last of the bucket.** `market_regime`'s VIX threshold was a flat
`20`, a US-derived number carried over without ever being checked against this market.

**⭐ Checked, and it does not describe India at all.** Across the 784 sessions in
`india_vix_daily` (2023-07-03 → 2026-09-04): median **13.35**, and VIX exceeds 20 on only
**5.1%** of days — so "20 = elevated" is really the **94.8th percentile**. It reads like a
"somewhat nervous" marker and behaves like an extreme. The 80th percentile sits at
**15.73**.

The threshold is now a **trailing percentile of our own history** — self-calibrating,
distribution-free, and requiring no view about what number is high in India. It keeps
meaning the same thing as the VIX regime drifts. The absolute remains the fallback when
history is too shallow to rank against (`MIN_VIX_HISTORY = 250` sessions), and
`vix_basis` always names which one produced the flag, so a `True` from one is never read as
a `True` from the other.

**⚠ A stale claim corrected in the same file.** The module said "our VIX history is too
shallow (~weeks) to §8-validate", which is why the absolute was never revisited. It holds
**784 sessions** — the backfill has happened, exactly as the index backfill had (corrected
2026-09-02). A doc that disagrees with the data is how a knob stays unexamined.

**Nothing about a gate decision changes.** VIX is informational and never blocks; this
changes what the shadow sidecar *reports* about market conditions. The market-regime gate
remains shadow and still owes its count, its DSR bar, and an answer to the side-proxy veto.

- `backend/app/signals/market_regime.py` — `vix_standing`, `vix_percentile`, `vix_basis`
- Tests: 8 new (`tests/test_market_regime.py`), including that VIX still never blocks

### feat(H4+U4): the gate register as data, and the trials counter it makes possible (2026-09-05)

**Bucket B, items 8 and 9.** Constraint #8 makes the review calendar Claude's to own and
requires raising each item *unprompted*. That calendar lived in `docs/PHASES.md` as a
markdown table — fine for a human, useless to code, with three consequences: **`N` in
`E[max SR]` was a guess** (`DEFAULT_TRIALS = 20`, hand-picked, and the deflation is the
entire point of the bar); the **failed-hypothesis archive had no home** (the regime gate's
−8R and R:R≥1's blocked +₹10,585 cohort existed only as prose in memory files); and nothing
could assert the calendar was complete.

`app/services/gate_register.py` is that table as data — deliberately a Python module rather
than YAML, so it is type-checked, imported by the code that reports it, and covered by
tests that fail when it drifts from the settings that actually exist.

**⭐ Observed trials: 15, against 20 assumed.** Seventeen hypotheses registered, of which 15
consumed a multiple-testing trial: 2 promoted-then-reverted, 3 decided against, 8 still in
shadow, 2 active.

**⚠ And the counter says out loud why "15 < 20, so the bar is conservative" does NOT
follow.** One entry is one *hypothesis*, but most were evaluated at several thresholds —
`sl_atr`'s k, anti-chase's 0.33R, circuit's 1.5%, liquidity's floor, the confidence gate's
level — and each variant we could have adopted is its own trial. The observed count is a
**lower bound**; the register does not record variants yet. A reassuring number with an
unstated caveat is exactly the failure A24 was written against.

**Two things deliberately excluded from the count**, each stating why in its own entry:
`entry_diversity` implements hard constraint #2 and could not have been rejected on
returns, and the notional cap bounds catastrophe while claiming nothing about edge. Neither
inflates a best-of-N Sharpe. Everything else counts **including the failures** — a trial
count that drops its failures is the precise selection bias the deflation corrects for, and
a reverted gate consumed a trial exactly *because* we adopted it.

**`DEFAULT_TRIALS` is untouched, on purpose.** Raising the assumed N makes the bar harder
for every candidate; that is a decision for a person looking at the discrepancy, not a side
effect of shipping the counter.

A contract test maps every `*_gate_mode` setting to a register entry and fails when a knob
is added or removed — which is precisely how a trial would otherwise escape the count.

- `backend/app/services/gate_register.py` — new · rendered in the daily report
- Tests: 12 new (`tests/test_gate_register.py`)

### docs(A24): never render a precise figure without its uncertainty (2026-09-05)

**Bucket B, item 7** — a standing rule, written into `.claude/rules/ui.md` where ui-reviewer
enforces it. A precise number reads as a confidence signal whether or not it is one: two
decimal places say "this was measured", a calendar date says "this will happen". We are
specifically exposed, because a 2–3%/day goal invites converting a wish into a timeline.

Six clauses, each anchored to something that actually went wrong somewhere: no bare point
estimate for anything predictive; **a projection must depend on what it projects** (the
review's worst example was a "probable exit date" with no volatility term that did not even
depend on the target price it was the date for — if changing the input does not move the
number, the number is decoration); round to the precision the evidence supports rather than
the float; **a sample size travels with its statistic** (H11); **"not assessable" is a
legitimate rendering** and beats a plausible-looking default, with H6's three cases
(undefined / off-scale / measured) staying visually distinct; and **a caveat must branch on
the data** — a fixed hedge that is wrong in some branch is worse than none, per
`buy_and_hold._deployment_note`.

- `.claude/rules/ui.md`

### feat(H11): the implied sample is the headline, not a footnote (2026-09-05)

**Bucket B, item 5.** We already compute MinTRL; the missing move was rendering it where it
cannot be missed. Required sample scales with the **inverse square of effect size**, so
halving an edge quadruples the evidence needed — on 4,843 published replications the median
strategy (Sharpe 0.37) needs **~28 years** of daily data to separate from zero. Our gates
are judged on **weeks**.

`deflated_sharpe.render_lines` now leads with `n=120 of ≈715 needed`, and when the observed
Sharpe does not exceed its benchmark the headline says **"MORE DATA CANNOT RESCUE IT"** —
the case where "keep accruing" is not merely unhelpful but actively wrong advice, since the
candidate is not ahead to begin with.

And the counterpart: every sidecar prints a `n/20 resolved — keep accruing` bar, which is a
**process convention, not a statistical requirement**. `flip_readiness.evidence_lines` now
says so explicitly beside it. `sl_atr` is the cautionary case — it passed all three
readiness guards and still sat at **t ≈ 0.41 against a 3.6 hurdle**, about 9× short, while
its `17/20` bar read like progress.

- Tests: 3 new (`tests/test_deflated_sharpe.py`)

### test(T7): exhaustive-enum mapping tests (2026-09-05)

**Bucket B, item 6.** We have been burned by precisely this: *"v1's `unassessed` tripwire
was IMAGINARY — 3 of 8 modes passed"* — an enumeration not exhaustively handled, with no
test that could notice.

**The gate-mode vocabulary was declared nine times and tied together nowhere.** Nine
`*_gate_mode` settings each say `Literal["off", "shadow", "active"]` independently, and
`_effective_mode` handles them with no link back. Add a fourth mode to one knob and it
falls through as `"off"` — silently, on the order path. `GATE_MODES` is now the single
declaration, and a contract test introspects the settings model against it, so extending
one without the other fails the suite.

Also pinned: `_effective_mode` over **every ordered pair** (the precedence lattice written
out longhand — this is where the `"off"`-is-truthy bug lived, and `div or sl` returning
`"off"` is exactly the case a spot-check misses); every `EnforcedBy` variant appearing in
the registry; and the registry's order as a **golden list**.

⚠ **One test was rewritten because it would have passed vacuously.** A
`test_broker_rules_come_last` written to the registry's own comment ("the broker's own
rejections come last, as they do in reality") is not true of the declaration — `offmarket`
is a BROKER rule declared **first**, deliberately, because the absence of a price is its
trigger. The draft passed only through an escape clause and asserted nothing. It is now a
pinned order list, which cannot.

- `backend/app/signals/restrictions.py` — `GATE_MODES` declared once
- Tests: 11 new (`tests/test_enum_exhaustiveness.py`)

### test(T11): pin PSR/DSR against independently-derived values (2026-09-05)

**Bucket B, item 4.** Cross-checking `deflated_sharpe.py` against QuantStats — the
best-known reference in the field — found **QuantStats wrong and us right**: its PSR feeds
pandas' **excess** kurtosis into a formula expecting **Pearson**, turning the `SR²`
coefficient from `+0.5` into `−0.25` and systematically **overstating** PSR. That check was
manual and one-off. It is now permanent, with every expectation written out from
Bailey & López de Prado rather than by calling the code under test (the T1 discipline:
anchor a test to a value you can derive independently).

**⭐ The bug is pinned as a VERDICT FLIP, not a rounding difference.** A test asserting
merely "excess kurtosis gives a bigger number" passes just as happily in the saturated
region where both conventions round to 1.0 and nothing is at stake — the first draft did
exactly that, and both sides printed 1.0000. Searched for the case that matters instead: at
**n=10, SR=0.585 the correct PSR is 0.9476 (fails a 95% bar) while the QuantStats
convention reports 0.9668 (clears it)**. Same data, opposite decision.

Also pinned: the `+0.5` vs `−0.25` coefficient longhand; the **seam** `moments → psr` (the
bug can only arrive through that handoff, and a unit test of either half alone would not
have caught QuantStats' version either); `expected_max_sharpe` against the
Euler–Mascheroni form; `min_track_record_length`; and the end-to-end DSR on a fixed
deterministic series.

- Tests: 6 new (`tests/test_deflated_sharpe.py`)

### feat(H2): the buy-and-hold benchmark — the honest denominator (2026-09-05)

**Bucket B, item 2.** We report P&L against zero. Zero is the wrong denominator: the
question a trading system has to answer is not "did it make money" but **"did it beat doing
nothing with the same money"**. The external review's most sobering number was a five-year
agent project that buy-and-hold quietly beat, invisible until someone opened a CSV. This
was genuinely absent rather than merely unreported — `benchmark.py` is per-signal relative
strength for the sector-RS overlay, not a portfolio baseline.

**⭐ First read, and it is not close.** Over the paper-clock window 2026-08-17 → 2026-09-04:
**NIFTY 50 −1.61%, the book −17.52%** (−₹17,522 realised + open MTM on ₹1L). The book **lost
to buy-and-hold by 15.92 percentage points.**

**The partial-deployment caveat is direction-aware, because here it makes things worse.**
Buy-and-hold is 100% invested and our sampler carries ~45% of capital at risk, so the
obvious sentence is "we were under-deployed, that explains some of the gap". It does not —
the index *fell* and the book fell ten times further, with **less** capital exposed. A fixed
caveat claiming otherwise would be exactly the misleading line this report exists to
prevent, so `_deployment_note` branches on the two signs: an under-deployed book that
trails a **rising** index is partly excused, one that loses more than a **falling** index is
not, and one that is **ahead** on less risk is stronger than its headline. This is the same
lesson `flip_readiness.tail_guard` learned when it announced "the negative mean is carried
by losses" for a cohort whose mean was positive.

Fails closed — `None` without a paper clock, a capital figure, or NIFTY bars at both ends —
and reaches BACK for the last bar on or before each edge (the clock can start on a weekend)
but never forward, which would be look-ahead. A window resolving to one bar at both ends is
refused: a 0.0% benchmark there is an artefact of the window, not a fact about the market.

- `backend/app/services/buy_and_hold.py` — new · wired into the scorecard
- Tests: 15 new (`tests/test_buy_and_hold.py`)

### feat(H12): beta to NIFTY and an information ratio (2026-09-05)

**Bucket B, item 3.** On 4,843 published replications the median strategy carries **beta
+0.17**, and stripping that exposure roughly halves the median edge. We computed **no beta
and no IR anywhere**, which left one specific blindness: a cohort that is directionally
biased in a trending market looks like skill. We have been bitten by exactly that — the
market-regime gate's evidence was a **proxy for side**. `side_proxy_guard` catches the
extreme version by counting sides; beta catches the graded version. Third robustness axis
beside **H1** (is it stable?) and **H8** (does the bar reject noise?): **is it just the
market?**

The market return per trade is taken over that trade's own holding window and **signed by
side** — a short profiting while the index falls is collecting exposure, not skill, and
unsigned it would read as negative beta and flatter the cohort.

**⭐ First read (105 closed positions):** beta **+0.638**, per-trade alpha **+0.607%**, IR
**+0.133**; LONG beta +0.342, **SHORT beta +1.492**. Our market exposure is far above the
+0.17 published median and the shorts carry most of it.

**⚠ A dimensional bug found while validating against the real book, now a regression test.**
Feeding **currency** returns against a fractional market move yields a beta carrying units —
measured at **−12,561** on the live book. Arithmetically fine, completely incomparable to
the +0.17 the finding is calibrated against. `Trade.ret` is now documented and tested as a
**fractional** return (`pnl ÷ notional`); a test asserts scaling the returns by 50,000
scales beta by 50,000, and that a fractional beta is a small number.

**⚠ And a discrepancy the instrument surfaced, reported rather than resolved.**
Equal-weighted return per trade is **+0.382%** while capital-weighted is **−0.118%**. The
tempting reading is "big positions pick worse" and it is **wrong** — Spearman(notional,
return%) is **−0.061**, essentially zero, and the largest quartile's *mean return is
positive* (+0.084%) while its rupee total is **−₹25,404**. The sign flip is
**concentration, not selection**. Worth noting the top quartile's median notional is
**₹122,566 on ₹100,000 of capital** — rows predating the per-position notional cap, which is
precisely the shape that cap exists to prevent.

**Scope:** rendered on the closed book and the LONG/SHORT split in the daily report.
Per-GATE-cohort beta is a follow-up: `flip_readiness` is contractually pure ("rows in,
verdicts out, no I/O") and `Row` carries no exit date or notional, so it would need four
more fields plumbed through six sidecars plus a DB read inside a pure module.

- `backend/app/services/beta_ir.py` — new · wired into the scorecard
- Tests: 17 new (`tests/test_beta_ir.py`)

### feat(H1): moving-block bootstrap beside the deflated-Sharpe bar (2026-09-05)

**Bucket B, item 1.** `deflated_sharpe.py` is parametric and **assumes the trades are
independent** — its own documented weakness. Ours are not: concurrent positions in one book
share the same market move, so a bad day is several correlated bad trades and an iid
instrument counts that as several independent pieces of evidence.

`app/services/block_bootstrap.py` is the non-parametric complement. Künsch's moving-block
bootstrap resamples runs of consecutive trades (`L = ceil(n^(1/3))`, the Hall–Horowitz–Jing
rate — 3–5 at our sample sizes) so short-range dependence survives the resampling, and
reports the Sharpe's 90% interval beside PSR/DSR/MinTRL. The two answer different
questions and must be read together: **DSR asks "better than luck given N trials", the
bootstrap asks "if the same process ran again, would the sign hold".** It also automates
by construction the tail-robustness check constraint #8 currently asks to be done by hand.

**⭐ First read on the live book — the loss is not statistically established either.** All
105 closed positions, chronological: observed Sharpe **−0.033**, 90% interval
**[−0.223, +0.118]**, sign fails to survive in ~30% of resampled histories. At n=105 the
book is indistinguishable from zero in **both** directions. That is sharper than the ₹
figure alone: it is not that we measured a small negative edge, it is that we have not yet
measured anything — and any gate partitioning this series is partitioning noise, which is
why no partition has ever cleared the bar.

**The blocks earn their keep, measured two ways.** On the real book the block interval is
**9% wider than iid** (0.342 vs 0.314) — small but in the expected direction, so the series
does carry dependence. On synthetic AR(1) data the effect is stark: with no autocorrelation
blocks cost nothing (interval ratio 0.99), at φ=0.8 they are **77% wider**, i.e. an
independence-assuming bootstrap would report a falsely tight bound. Both are pinned by test.

**Validated the way H8 validated the DSR bar** — an instrument that cannot come out badly
is not an instrument: at n=44 a zero-edge series' sign "survives" **6.2%** of the time
against a one-sided 5% design (percentile bootstraps under-cover slightly at small n; that
is recorded rather than hidden), and a true per-trade Sharpe of 0.5 survives **95%** of the
time.

**⚠ A defect found in this module while validating it, and fixed.** A near-constant series
with one outlier (43 trades of +0.2, one of −40) produced **76% zero-variance resamples**.
Dropping those silently left only the draws that *contained* the outlier, so the reported
interval described a filtered subpopulation and read as if the negative sign were robust —
when it was one trade. Exactly the failure this instrument exists to detect, occurring
inside the instrument. It now **refuses** above `MAX_DEGENERATE_SHARE` (10%) rather than
reporting a biased interval.

**⚠ Block order had to become a property of the data.** Blocks are runs of *consecutive*
trades, so they are meaningless unless the series is chronological — and sidecars sort their
rows for display (`market_regime_shadow` sorts newest-first). Rather than trust a convention
nothing can check, `flip_readiness.Row` gained an optional `at`, the bootstrap sorts by it,
and it **refuses when any row lacks one**. All six sidecars now pass it (`circuit_gate` and
`entry_quality` needed the timestamp plumbed onto their detail rows). A test asserts display
order cannot change the number.

Deterministic by construction (fixed seed) — a readiness figure that moves between two runs
on identical data would read as news. Costs ~190 ms at n=105, so under ~1.2 s across all six
sidecars in `make analysis`.

- `backend/app/services/block_bootstrap.py` — new
- `backend/app/services/flip_readiness.py` — `Row.at`, `_chronological`, one block in
  `evidence_lines`
- six `*_shadow.py` sidecars — pass `at=`
- Tests: 20 new (`tests/test_block_bootstrap.py` 17, `tests/test_flip_readiness.py` +3)

### fix(H6): a degenerate ratio is undefined, not zero, and off-scale is marked (2026-09-05)

**Bucket A, item 8** — it changes reported R:R values, so it lands before cycle 2's clock.

A ratio whose denominator goes to zero has three honest outcomes and the codebase conflated all
three. **UNDEFINED** (`entry == SL`: there is no reward:risk) was returned as `0.0` — *the same
number the code prints for the worst possible setup*, so "not assessable" and "terrible" became
indistinguishable. **OFF-SCALE** (a 4-paise stop against a ₹9 target) was returned raw, so a single
row could carry a cohort's mean, win a dedup sort, or overflow a `Numeric` column. **NORMAL** was
the number.

**The caps are read off the book, not argued for.** All 656 signals carrying levels, 2026-09-05:
planned R:R p50 **1.97**, p90 **3.67**, p99 **28.5**, max **228.06** — and **exactly one row
(0.15%) exceeds 50**, the known tiny-SL artifact whose stop is **2.6 bps** of its own price. So
`MAX_RR = 50` sits above the 99th percentile of genuine signals and below the artifact: it touches
the artifacts and nothing else. It is a reporting bound taken from the distribution, not a claim
that a 60:1 setup is impossible.

**⭐ THE RULE: clamp what you REPORT, never what you DECIDE.** Every gate computes its verdict from
the raw ratio and clamps only the value it stamps or prints. `MAX_RR` (50) is above every threshold
that reads it (`rr_guard.rr_min` 1.0, `position_health.rr_floor` 1.0), so the two can never
disagree — but it is the *ordering* that guarantees this, and a test pins both the ordering and the
constants' relative sizes.

**Four literals doing three jobs, in four modules, two of them disagreeing by 1000×** — now stated
once in `app/core/ratios.py`: `MAX_RR` (a reporting bound on R:R), `MAX_R = 9999.999` (a
*representability* bound from the `Numeric(7,3)` excursion columns, where an overflow aborts a batch
commit), `WINSOR_R = 10.0` (a *statistical* winsor bounding what one trade contributes to a mean).
Consolidating them deliberately did **not** collapse them into one number.

**Off-scale is marked, not silently truncated.** `format_ratio` renders `—` for undefined and `>50`
for a clamped value, because printing a truncated 228 as "50.00" would read as a real 50:1 setup —
worse than the artifact it replaced. `rr_guard` stamps `rr_capped` alongside `rr` for the same
reason.

Sites migrated: `rr_guard` (the stamped verdict) · `api/v1/signals._reward_risk` (a **dedup
tiebreaker** — an uncapped 228 let a 4-paise stop beat every genuine candidate for the shown row) ·
`entry_attribution._rr` + its `-1e9` sort sentinel (replaced by an explicit "no expectancy" sort
position) · `daily_report.chase_metrics` (five ratios; `rr_at_fill` blows up when a fill lands ON
the stop) · `position_health.rr_remaining` (reaches the API and the UI) · `signal_excursions` ·
`pair_outcome` · `pair_attribution`. Also fixed: `daily_report` divided by `capital_inr` unguarded
in one place and guarded in another **thirty lines apart, same expression**.

**Not touched, and named as follow-ups** (both need §8 + sign-off, `app/backtest/engine.py` is
FROZEN): `_compute_sortino` returns **`0.0` when there are no losing trades** — a genuinely infinite
Sortino reported as the worst possible score, and a §8 golden field; `_compute_sharpe` guards
`std == 0` by exact equality, so a `1e-16` float-noise stdev yields a Sharpe of ~`1e15` into a
`Numeric(6,3)` column; `metrics.avg_rr` is uncapped into `Numeric(5,2)`.

- `backend/app/core/ratios.py` — new: `MAX_RR`/`MAX_R`/`WINSOR_R`, `safe_ratio`, `safe_ratio_f`,
  `clamp_ratio`, `clamp_ratio_f`, `is_capped`, `format_ratio`
- Tests: 22 new (`tests/test_ratios.py`)

### feat(A25): assert the tick mode on the depth path (2026-09-05)

**Bucket A, item 7.** We subscribe `KiteTicker.MODE_FULL` and harvest 5-level depth out of the
ticks it returns (6.8.1), on both the live path (`live_worker`) and the dormant v1 path
(`tick_consumer`). **Neither ever checked the tick's `mode` field.** Kite is documented to deliver
quote-mode ticks on a full-mode subscription — the contrasting library (repo 8) detects exactly
this and reopens its socket.

**Why that matters here is the chain of fail-opens.** A quote-mode tick has no `depth` key →
`extract_top_of_book` returns `None` → `depth:{stock_id}` stops being refreshed → the key expires
after 60 s → 6.8.2's spread-aware fill model finds no book → paper fills fall back to the flat
`paper_slippage_bps` floor. Every step of that is deliberate, correct fail-open behaviour, which
is exactly what makes it dangerous: **the only symptom is paper fills getting quietly CHEAPER than
reality, on the book we use to judge whether a −0.303R expectancy is improving.** Note this is not
a bug we have observed — it is a documented broker behaviour we had no detector for.

**Detect, count, shout, name the remedy — deliberately not react.** `app/broker/tick_mode.py`
censuses each batch's `mode`, accumulates it, and raises a rate-limited (1/min, but immediate on
the first) warning naming the counts, the consequence and the fix. It does *not* reopen the socket:
we have never observed this against us, re-subscribing from the consumer thread reaches across into
the ticker's own thread, and a reconnect loop on a misread would cost more than the degradation.

**Two counters, cause and symptom, deliberately separate.** `degraded` = ticks whose mode is not
`full` (the broker downgrade). `depth_missing` = *tradable full-mode* ticks whose book was unusable
anyway — the symptom the mode counters cannot explain. Tradable-only because an index packet is
full mode and carries no book by design; counting those would park a permanent false number under
the alarm. A one-sided pre-open book is normal, so `depth_missing` counts but never alarms.

**A mode-less tick is NOT a degradation.** Recorded and replayed ticks legitimately carry no `mode`
field. Those count as `unknown` and ride the heartbeat — where a mode-less *live* feed would show
up — but they never raise the alarm and never write the durable key. Otherwise every replay run
would cry wolf, and the day hash would come to mean "we ran" rather than "the feed degraded".

**Three surfaces, cheapest first.** (1) `WorkerState.stats` → the existing live-worker heartbeat and
shutdown line, so a degradation is visible *as it happens*. (2) The rate-limited warning. (3) A
durable Redis day hash `tickmode:health:{day}` (7-day TTL) that the daily report reads and renders
as a loud header beside the 6.8.6 feed-staleness alarm. A log line alone is precisely how the
provisional hot-set flood hid for weeks (A26).

**The healthy path pays nothing.** `counters()` returns `{}` unless something actionable happened,
so a clean feed queues no Redis command at all; when there is something to record it rides the
tick loop's existing pipeline — never a round trip of its own. HSET-overwrite, not HINCRBY: the
counters are cumulative since worker start, so a restart must re-count, not double-count. The one
exception is the empty-batch early return, which never reaches `_publish_ltp` — it flushes on its
own pipeline, because a batch with nothing usable in it is the *worst* case and must not be the one
case that goes unrecorded.

The dormant v1 consumer got the same check (A31: a realism constraint added to one path that
produces a number must be added to every path that produces it, in the same change).

- `backend/app/broker/tick_mode.py` — new: `tally_tick_modes`, `TickModeMonitor`,
  `record_tick_mode_health`, `read_tick_mode_health`, `render_tick_mode_health`
- `backend/app/broker/live_worker.py` — census in `_ffi_batch`; `mode_degraded` / `mode_unknown` /
  `depth_missing` on the heartbeat stats; durable flush in `_publish_ltp` + `_flush_mode_health`
- `backend/app/broker/tick_consumer.py` — census in `_process_batch`; depth capture extracted to
  `_capture_depth` with the depth-miss counter
- `backend/app/services/daily_report.py` — `tick_mode_health` on the report, rendered next to 6.8.6
- Tests: 34 new (`tests/test_tick_mode.py` 25, `tests/test_live_worker.py` +7,
  `tests/test_tick_consumer.py` +2)

### feat(A26): the hot-set cap is hard for discovery, soft for committed work (2026-09-05)

**Bucket A, item 6.** The provisional hot set clipped at `live_provisional_hotset_max` by tier
priority and logged a warning. Two things were wrong with that, and we have already paid for one
of them: breadth alerts flooded the hot set, **watchlist stocks silently stopped being scored, and
it was found weeks later**.

**A stock carrying an active signal was clippable.** With more signal-bound stocks than the cap,
the surplus was dropped — and a signal-bound stock that is never scored is a signal that silently
does not exist. That makes a CPU budget a determinant of the trading record, which is precisely
why A26 sits in the bucket that must land before cycle 2's clock.

**The cap is now HARD for discovery tiers and SOFT for protected ones.** `signal` and `trigger`
stocks are never dropped: if they alone exceed the cap, all of them are admitted, the budget is
knowingly exceeded, and the overflow is escalated at ERROR with the actual numbers and a named
remedy. Discovery tiers (`watchlist`, `market`) still clip to whatever budget remains — and their
warning now names a remedy too, following the contrasting library (repo 8) that refuses at its
broker token ceiling with an error stating the numbers and two concrete fixes.

**Refusing to run was considered and rejected.** That library refuses because exceeding its
ceiling would fail at the broker anyway. Ours is a self-imposed CPU budget, and refusing would
score *nothing* — strictly worse than running over budget. Overflow-and-shout is the right shape
here; the point of A26 is not the refusal, it is that a capacity boundary must never be crossed
quietly.

**And it is durable now, not just a log line.** `protected_overflow` rides the cycle stats into
`provisional:health:{day}`, and `scripts/provisional_health.py` prints a `⛔ PROTECTED OVERFLOW`
marker plus the remedy. The original incident hid in a log line for weeks precisely because the
clip existed nowhere else — the same reasoning that put `clipped` on the stats in the first place.

The rule moved out of `load_hot_set` into a pure `apply_hotset_cap(hot, cap)`, so the boundary is
testable without a database. It previously could only be exercised through a full cycle, which is
part of why a real clip went unnoticed.

Tests: **1816 passed** (full suite, run exclusively); 9 new, covering the protection guarantee,
multi-source stocks taking their *strongest* tier (a watchlisted signal must not be demoted into
the clippable pool), the ERROR carrying both numbers and remedy, and `cap <= 0` being a no-op
rather than silently disabling the entire provisional layer. Reverting to the pre-A26 behaviour
fails **4** of them — checked by mutation.


### feat(A23): the effective-dated fee registry — each leg costed on its own date (2026-09-05)

**Bucket A, item 5.** `fees.py` has claimed since Phase 8 that costs are *"versioned by effective
date"*, and `ZERODHA_EQUITY` carried a note that *"a future effective-dated registry can replace
this constant"*. It was still a single constant. Indian statutory rates (STT above all) change
mid-year, so any record spanning a change was silently priced at today's rates.

`SCHEDULE_HISTORY` is now an ascending list of `DatedSchedule(effective_from, schedule, note)`, and
`schedule_for(on)` returns the entry in force on a date. **`roundtrip_charges` costs each leg on
its OWN date** — `entry_on` and `exit_on` — because a position opened before a rate change and
closed after it genuinely paid two schedules, and collapsing that to one is the error the registry
exists to prevent. The breakdown records `priced_on` per leg, so a cost can be re-derived from the
record alone.

**Wired to the three live call sites with real dates:** `close_position` (entry on the position's
open date, exit today), `_estimated_roundtrip_charges` (same, exit = "if it closed now"), and
`profit_lock_shadow`'s replay — which matters most, because it replays *real* positions opened weeks
ago and was costing every one of them at today's schedule.

**A date before the registry's coverage RAISES rather than falling back to the earliest schedule.**
Costing a trade with rates from outside their period produces a number that looks valid and is
fabricated; this project's repeated lesson is that unknown must be loud.

**⚠ The registry ships with ONE entry, and that is deliberate rather than a stub.** We hold no
researched history of Indian rate changes, and inventing effective dates would fabricate precision —
the same error as inventing a per-trade cost floor, which A29 declined for the same reason. Its
`effective_from` is documented as a **coverage floor** ("we model nothing earlier"), not a claim
that these rates began in 2000. To record a real change, *append* an entry — never edit an existing
one, exactly as with a migration: editing history re-prices every trade already costed under the old
rates.

**⚠ A bigger gap found while wiring this, and it is not A23's:** grepping for fee usage in
`app/backtest/` returns **nothing**. The backtest does not model costs *at all* — not undated fees,
zero fees. So **backtest P&L is GROSS while paper P&L is NET**, and any comparison between backtest
expectancy and paper expectancy is off by the entire charge load: 22–62 bps round-trip plus the flat
₹15.34 (A29). That is frozen-engine territory — the same blocker A38's and A37's backtest legs hit —
so it is recorded here and in PHASES rather than fixed. It is arguably the most consequential item
in the A21/A30/A31 "realism added here but not there" family, because it silently flatters every
backtest number we have ever compared against the live book.

Tests: **1807 passed** (full suite, run exclusively); `tests/test_fees.py` 14 → 20. The registry
tests use a synthetic two-entry history straddling a rate change and assert the entry leg pays 0.05%
STT while the exit pays 0.50% — a 10× difference the old single-constant model could not express —
plus the pre-coverage raise, the explicit-schedule override, and back-compat when no date is passed.
The A29 seam test now also asserts the entry leg was priced on **the position's own open date**.


### feat(A29): the flat depository charge — the one cost that is not neutral to size (2026-09-05)

**Bucket A, item 4.** Our `FeeSchedule` modelled delivery STT on both legs, intraday STT sell-only,
stamp on buy and GST on the right base — everything except the charge that does not scale. Zerodha
and CDSL levy a **flat ₹15.34 per delivery SELL, per scrip, irrespective of quantity**, and we
levied nothing.

**Measured on the real book: all 105 closed positions were delivery, so ₹1,610.70 of depository
charge was never levied — 15.8% of the book's entire loss.** Realised P&L should read
**−₹11,829, not −₹10,218**. We were under-costing the paper record in the direction that flatters
an already-negative expectancy, which is the one direction that matters for a record whose whole
job is gating live trading.

**Why a flat charge is different in kind.** Every other cost here is a percentage, and a percentage
is neutral to position size. A fixed cost is not:

| position | notional | round-trip charges | as bps |
|---|--:|--:|--:|
| 100 × ₹39 | ₹3,900 | ₹24.01 | **61.6 bps** |
| 1,000 × ₹39 | ₹39,000 | ₹102.01 | 26.2 bps |
| 400 × ₹2,500 | ₹10,00,000 | ₹2,237.80 | 22.4 bps |

Nearly **3× the relative cost** on the small position — and small is exactly the shape the
per-position notional cap produces today, and exactly the ₹1 lakh / 1–2 position shape live trading
will have. A test asserts that ratio rather than describing it.

Applied to the **delivery SELL leg only**: the charge is levied when shares leave the demat account,
so there is no buy-side and no intraday analogue. Added after the GST line because the published
₹15.34 is already GST-inclusive. It is itemised as `dp_charge` in the audit breakdown rather than
folded into the total — a charge you cannot see is one nobody notices going wrong.

**The per-trade cost floor ships as a mechanism, defaulting to zero, and that is deliberate.** The
Zerodha cash-equity schedule has no minimum per trade; inventing a rate would fabricate a cost
rather than model one, which is the same error as omitting the real one, only in the other
direction. `min_charge_per_leg` exists so a broker that *does* levy a minimum needs no call-site
change — the reason rates live in a schedule at all — and a test pins both that it is off by default
and that it applies when set.

⚠ **One caveat recorded in the code:** the charge is applied to whichever leg is the SELL, which for
a delivery SHORT means the *entry*. A cash-equity delivery short is not actually possible — you
cannot deliver stock you do not hold — so that combination is an artefact of the paper model, and
charging it consistently is closer to right than exempting it.

⚠ **Forward-only.** Closed positions keep their stored, under-costed `realized_pnl`; only new trades
and open positions' re-estimated `unrealized_pnl` reflect the charge. So the ₹1,610.70 above is what
history *should* have cost, not a restatement — and paper P&L before and after 2026-09-05 is not
comparable, on top of the A21/A37 fill changes the same day. Bucket A is where that is acceptable:
**cycle 2's clock has not started.**

Tests: **1800 passed** before this commit's own tests; `tests/test_fees.py` 8 → 14, including a
**seam test that closes a real position through the broker** and asserts the charge lands in both
`position.charges` and the order payload. Zeroing `dp_charge_per_sell` fails **7** of them — checked
by mutation, because A37 shipped a feature whose tests all passed while it could have been inert.
Two pre-existing hand-computed totals moved by exactly ₹15.34 and now say why.


### fix(A37): thirteen quant-verifier findings — a sizing loop with no fixed point (2026-09-05)

Review pass on `bac1bac`. The formula, units, money types, anchoring and fail-open behaviour all
verified correct, and the feature was confirmed live on the real book. Three HIGH findings against
it, all fixed.

**The sizing refinement had no fixed point.** Once the impact term became *quadratic*, the map
`q → size(fill(q))` stopped converging — it is a period-2 cycle (333 ↔ 1538), and one pass simply
landed on the low branch and stopped. The order then recorded `fill(q1)` while shipping `q2`:
measured, an entry **priced for an order 16.8× larger than the one placed — ₹1,537 of error on a
₹2,000 risk budget**. Pre-A37 the only size-dependent term was linear and capped at 50 bps, so the
gap was never material. Fixed by re-pricing once at the FINAL size and keeping that price. The
guarantee is now a bound rather than convergence: `q2` was sized against the strictly more adverse
`fill(q1)`, so realised risk `q2 × |fill(q2) − SL| ≤ budget` still holds. ⚠ **The consequence is
real and conservative: on thin names we now ship materially fewer shares** — 854 where the naive
size was 4,545, carrying ₹461 of risk against a ₹2,000 budget. That is the right direction (a name
where your own size moves the price that much is one to take less of) but it is a sizing change,
recorded below.

**The spread path never stamped what it charged.** `slippage_bps` included participation, but the
`FillModel` return omitted the two new fields, so `broker_payload["fill"]` reported
`participation_bps: "0.00"` and `half_spread + impact + participation ≠ slippage_bps` — a fill that
could not be re-derived from its own record, which is the single thing that record exists for.

**And the whole feature could be made inert with a green suite.** All 26 tests called the pure
functions directly and covered **none of the seven wiring sites**. quant-verifier proved it by
mutation: reverting the sizing gate, nulling the ADV in `place_paper_order`, and dropping
`adv_value` at all five mark surfaces each left the suite **fully green**. Six seam tests now go
through the real order path and the real mark path against a real database, and **each mutation was
re-run to confirm the new tests fail** — M3 and M2 each break two, M4 breaks one. (One of them
failed first time for an instructive reason: on a ₹39 stock a ₹0.05 tick is 12.8 bps, so a
participation impact smaller than that rounds to the same tick and the size does not move. The
fixture was too generous, not the code; it is now ₹1 lakh/day and the reason is in the test.)

**Also fixed:** all seven ADV loads now go through **one** `load_median_traded_values_safe` —
savepoint plus `except SQLAlchemyError`, matching the liquidity gate's house pattern. A DB fault on
the ADV query would previously have 500'd the order, and a fail-open written seven times is seven
chances to forget it. The daily EoD row is **now actually batched** (it was a per-row query — ~29
windowed scans per report day, ~145 per weekly summary — while the previous entry claimed it was
batched). `paper_participation_k` is clamped `ge=0.0` at the config edge, because a negative k drove
`slippage_bps` **negative** on the spread path, and the guard that looked like it prevented that was
dead code for every k ≥ 0; the baseline floor now applies on both paths. The "shared median" claim
is **made true** — `liquidity_guard` kept its own private `_median` and never imported the shared
one, so the definition now lives in the pure layer and the service re-exports it (the windows stay
deliberately different, and the docstring says so).

**⚠ The calibration is ours, not zipline's, above 2.5%.** Zipline pairs `price_impact=0.1` with
`volume_limit=0.025` — it never fills more than 2.5% of a bar, so 0.1 was only ever evaluated up to
≈0.6 bps. We apply the same quadratic at 20% (40 bps) and 50% (250 bps). The *form* is theirs; the
*extrapolation* is an unvalidated judgement call, now marked as one per T12, with what would falsify
it recorded: real fills on names where we take >5% of a session, which only Phase 7 can supply.

**⚠ Two further honesty notes.** The denominator is order ₹ ÷ median `close × volume` over 20
sessions, not zipline's shares ÷ that bar — they diverge when a name has trended inside the window
(a doubled stock's participation is overstated). And `conftest` now neutralises
`paper_participation_enabled` alongside `paper_slippage_bps`: the entire 1,789-test suite had been
running with participation LIVE, staying green only because fixtures seed fewer than 20 daily bars
and the model fails open. The first fixture to seed 20+ would have moved fill prices in unrelated
tests with no visible cause.

**⚠ Comparability, stated as the 2026-08-17 precedent requires:** this commit and `bac1bac` change
**every paper fill and every mark**. Paper P&L before and after 2026-09-05 is not comparable.
Landing inside Bucket A is what makes that acceptable — **cycle 2's clock has not started**, which
is the entire reason these items are sequenced ahead of it.

Tests: `tests/test_participation.py` 26 → 32. ruff + mypy clean across 248 files.


### feat(A37+T3): volume-participation impact — size priced against the stock, not just the book (2026-09-05)

**Bucket A, item 3.** The 6.8.2 model charged the real half-spread plus a size-vs-**top-of-book**
impact. Neither notices that an order is large relative to the stock's **daily volume**: the
notional cap bounds a position in rupees, not in liquidity. **SRTL is the named case** — a ₹39
micro-cap, 2,666 shares; ₹1 lakh in a name trading ₹5 lakh a day is a fifth of a session and is
not fillable at the quoted price, yet we modelled it free.

`participation_bps` charges **`k × participation²`**, participation = order value ÷ median daily
traded value. Quadratic, following zipline's `VolumeShareSlippage`
(`price × (1 + price_impact × volume_share²)`, `price_impact` 0.1), which is where the calibration
comes from: 2.5% ≈ 0.6 bps · 10% ≈ 10 bps · 20% ≈ 40 bps · 50% ≈ 250 bps. Small orders are
untouched; the cost bites exactly where the order stops being absorbable.

**On the real book right now — ADV resolved for all 29 open positions:**

| symbol | notional | participation | impact |
|---|--:|--:|--:|
| **ADROITINFO** | ₹32,832 | **16.95%** | **28.7 bps** |
| BVCL | ₹41,289 | 6.04% | 3.7 bps |
| LOVABLE | ₹31,748 | 5.69% | 3.2 bps |

**Only 3 of 29 positions are charged more than 1 bp** — it is surgical, not a blanket tax. And we
are holding the archetype today: a ₹33k position that is a sixth of its stock's daily volume, which
the old model priced at the 2 bps floor.

**Applied on BOTH fill paths, deliberately.** A thin stock usually has no live book at all, so
charging participation only on the spread path would exempt exactly the names the model exists for.

**The sizing refinement pass had to widen with it.** It re-priced only when
`fill.model == "spread"`, because top-of-book impact was previously the only size-dependent term.
Participation is size-dependent on the flat path too, so that gate would have sized SRTL off a
2 bps fill that should have been 45. It now re-prices whenever a size exists — a no-op where
nothing is size-dependent, since the second call returns the identical fill.

**Marks pay it too (A31).** Getting out of a fifth of a day's volume costs what getting in cost, so
`exit_mark` takes the same denominator and every mark surface batches it —
`list_open_positions`, the summary, `position_monitor`, `_open_book_mtm` and the daily EoD row.
Charging it on the fill and not on the mark would have re-opened precisely the optimism A21 closed,
which is the mistake this same commit sequence already made once.

New `load_median_traded_values` batches the denominator in one round trip, **and takes the median in
Python with `Decimal`** — Postgres `percentile_cont` returns double precision, and money through a
float is what the money rules forbid. It shares `median_traded_value` with the liquidity gate on
purpose: the gate and the fill model must not disagree about how liquid a name is. A stock with
fewer than `lookback` sessions is **absent, not zero** — too little history is *unknown*, and
unknown fails open to no impact. Zero would mean infinite participation and would make every order
in that name unfillable.

**Not a partial-fill cap.** Zipline also refuses to fill more than 2.5% of a bar and spills the
rest. That needs partial fills, which are explicitly Phase 7. This prices the trade honestly rather
than rejecting it — **no signal is suppressed by this knob**, which also keeps it out of
gate-promotion territory where this project has been burned twice.

⚠ **It overlaps the top-of-book term rather than being orthogonal to it** — one measures
instantaneous depth, the other daily capacity, and an illiquid name trips both. That is intended
(both being large *is* the signal the trade is unfillable) and the sum stays bounded by
`paper_slippage_max_bps`. ⚠ **The backtest is untouched**: its fill logic lives in the FROZEN
`app/backtest/engine.py`, the same blocker A38's backtest leg hit.

Tests: **1789 passed** (full suite, run exclusively). New `tests/test_participation.py` (26)
including **T3's parametrised `(participation → expected fill)` table**, and five DB tests for the
batched loader whose key assertion is the stock_id **mapping** — getting that wrong would price one
stock's order against another's liquidity, silently. ruff + mypy clean across 248 files.


### fix(A21): five quant-verifier findings — a missed surface, and rounding that paid us (2026-09-05)

Review pass on `873477a`. The A21 mechanism verified correct — direction, no double-counting,
reporting-only, no market look-ahead — but it **failed on scope and on rounding**.

**A surface was missed, and it is the exact failure A31 exists to prevent.**
`daily_report.py:352` computed the EoD open figure from the raw last close and printed it as
*"Open book mark-to-market (gross, EoD)"*, while the weekly series printed a **haircut** number
under the same label. Same book, same cutoff — provably identical (`report_end` and the weekly
`cutoff` are both `min(day_end, now)`) — two different models, shipped by the commit whose whole
purpose was making marks consistent. A31 names A21 as its first instance and it recurred inside
A21 itself. Fixed, with the invariant test that would have caught it:
`report.open_unrealized_eod == await _open_book_mtm(db, user_id, report.report_end)`.
The give-back leg deliberately stays **gross on both sides** — `exc.mfe_pnl` is a gross peak, and
haircutting one side of that subtraction would inflate every reported give-back.

**`_round_tick` could round a price back PAST its reference — in our favour.** It used
`ROUND_HALF_UP` to the *nearest* tick, so an off-grid reference could produce a fill or mark
**better than the last trade**, violating the module's own "can only make a fill worse" contract.
Measured over 20,000 real `ohlcv_1m` closes: **4.9% of long marks landed above their reference**
(mean phantom gain ₹0.0132/share), and **27.2% of our 1m closes are off the ₹0.05 grid** — not a
corner case. My test parametrised only grid-aligned prices (39 / 100 / 2500) and could not see it.
Rounding is now **directional**: a BUY ceils, a SELL floors. This is also the more truthful model —
an off-grid price is not transactable, so the achievable price is the next tick in the direction
that costs you.

**It applies to entry fills too, and there it was not latent.** Correcting the rounding turned
`test_sizing_is_risk_first_from_the_spread_aware_fill` red — and the test was asserting the bug.
On its fixture the model computes a raw adverse price of **502.5733** and the old rounding filled
the BUY at **502.55, below the price it had just computed**: we underpaid by ₹0.023/share on every
such entry while the module promised it "can only make a fill worse". The fill is now 502.60.
**So this is a recorded-number change on the money path, not only on the marks** — entry fills get
marginally worse, which is the honest direction and exactly why Bucket A lands before cycle 2.

**A side effect worth naming: this removed the limitation the previous entry documented.** The
"flat mark is a no-op below ~₹125" case existed only because a sub-half-tick haircut rounded away.
A floor always reaches the next tick down, so the cheap-stock mark now bites. That entry's
limitation 2 is **obsolete** and the test was renamed to assert the opposite.

**`exit_side_for` accepted an order side and would have inverted the sign.** It mapped
`BUY → SELL`, but `compute_pnl` and `roundtrip_charges` treat anything that is not `LONG` as a
SHORT — so a `side="BUY"` would have been marked DOWN and then valued with the SHORT formula,
turning the haircut into a phantom **gain**. Unreachable through `Position.side` today, but the
helper is public and **a test had pinned the loose mapping as intended contract**. It now accepts
`LONG`/`SHORT` only and raises otherwise.

**`get_live_depths` shipped with zero tests** while feeding three live call sites. Added, including
the assertion that actually matters — a three-id read with a gap in the middle, proving the
key→stock_id mapping holds. A mis-zip there would mark a position against **another stock's order
book**, which is silent and expensive.

**And three more assertions that could not fail** — in the commit where I had asked the reviewer to
hunt specifically for them. (a) The two `depth=None` cells of the fill-equivalence test: with
`conftest`'s `paper_slippage_bps=0` both sides returned the untouched reference, so **an inverted
`exit_side_for` still passed** (proven by mutation). (b) `assert m.slippage_bps == m.baseline_bps`
— the flat branch assigns both from the same local. (c) The short test's final assertion held from
`roundtrip_charges` alone, with no dependence on the mark. All three replaced with assertions on
values, and the equivalence test now takes the haircut fixture.

Left alone deliberately: `_week_giveback` marks its `final` raw, which is **correct** — its `peak`
leg is raw too, and haircutting one side would inflate give-back. Two point-in-time notes recorded
for later: the historical mark applies *today's* `paper_slippage_bps` to a past cutoff (same class
as A23, effective-dated fees), and it passes *today's* `pos.quantity` — inert now because the flat
branch only records quantity, but a real leak if depth is ever supplied on that path.

Tests: `test_exit_mark.py` 37 → 63 (off-grid references added), `test_depth.py` 24 → 27,
plus the daily-vs-weekly agreement test. ruff + mypy clean across 248 files.


### feat(A21): mark-to-exit — marks are priced by the same model as fills (2026-09-05)

**Bucket A, item 2.** Since 6.8.2 our *fills* pay the real half-spread, but our *marks* used
the untouched last trade. The same system charged the spread on the way in and out, then valued
the book as if it could be exited at a price nobody was offering. With **82% of live NSE books
wider than the flat 2 bps** across ~29 open positions, reported unrealized P&L was systematically
optimistic by roughly a half-spread per position. An internal inconsistency, not a modelling
preference.

**`exit_mark()` routes marks through `simulate_fill` with the EXIT side**, so the two halves
cannot drift apart again: a long marks toward the **bid**, a short toward the **ask**, and both
fail open to the flat `paper_slippage_bps` floor when no fresh book is available — the same
fallback the fill path takes. Passing the position quantity also charges the size-vs-top-of-book
impact, because a 5,000-share position cannot be exited at the touch either. The test that
matters asserts *equivalence to the closing order's fill*, not the arithmetic, so the property
A21 actually wants is the one pinned.

Wired into every unrealized-P&L surface: `update_position_pnl` (the API list, the summary and the
position monitor, each batching one `get_live_depths` MGET rather than opening a Redis connection
per position) and `_open_book_mtm` (the daily report + the weekly per-day series).

**Not double-counting:** `roundtrip_charges` is statutory/brokerage cost (STT, stamp, GST), a
different thing from the spread; and the entry half of the spread is already inside
`avg_entry_price`, so this adds only the exit half. `update_position_pnl` still **returns** the
raw reference price — callers show it as "current market price", and a haircut mark is not what
the tape says.

**⚠ This changes a recorded number and nothing else.** `unrealized_pnl` is purely reported:
every exit decision in `position_monitor` is taken on the live tick, and nothing branches on it.
Reported open-book MTM gets *worse*, which is the point — and it lands now precisely because
cycle 2's clock has not started.

**Two limitations found while testing, both pinned rather than papered over:**
1. **The historical mark cannot be a true mark-to-bid.** Depth lives in Redis under a 60-second
   TTL and is never persisted, so no book exists for a past cutoff — and `_open_book_mtm` is
   called for every day of a week. Reaching for *today's* book would price Monday's mark with
   Friday's spread, which is worse than a consistent floor, so the historical path always takes
   the flat-bps model. The live surface does mark to the real book. Both now pay a spread; they
   differ in precision, not in kind, bounded by `paper_slippage_bps`.
2. **The flat mark is a no-op on cheap stocks.** At 2 bps with a ₹0.05 tick, the haircut only
   clears half a tick above ~₹125 — below that it rounds away entirely, so a ₹39 micro-cap's
   *historical* mark does not move at all. Discovered because the first version of the test
   asserted "strictly worse" and failed; the true invariant is **never better**, and both halves
   (the invariant, and that a material spread does bite) are now separate tests.

Tests: **1728 passed** (full suite, run exclusively). New `tests/test_exit_mark.py` (37) plus
integration coverage for both directions in `test_trading.py` and the report path in
`test_daily_report.py`. ⚠ `conftest` zeroes `paper_slippage_bps` for the suite, so every
flat-path assertion sets it explicitly — otherwise it passes vacuously, which is the failure mode
this project keeps meeting. ruff + mypy clean across 248 files.


### fix(A38): seven bug-hunter findings — including two guard tests that could not fail (2026-09-05)

Second review pass on the A38 registry (`878b7ad`). quant-verifier had already proved block
decisions identical by differential fuzz; this pass looked for what a behaviour diff *cannot*
see. Seven confirmed findings, all fixed.

**The worst one is about the tests, not the code.** The two tests cited as pinning "the display
path's stand-in thresholds are unreachable" **could not fail**:
- `test_no_uncovered_restriction_is_satisfiable_from_a_list_row` asserted
  `not r.requires <= LIST_AVAILABLE` *guarded by* `if r.gate in UNCOVERED_GATES` — but
  `UNCOVERED_GATES` is **defined** by that predicate, so it was a tautology. bug-hunter proved it
  by replaying the verbatim body against all **2⁷ = 128** possible values of `LIST_AVAILABLE`:
  zero failures.
- `test_the_stand_ins_would_block_loudly_rather_than_pass_quietly` ran `preview` with **every mode
  `off`**, so every judge short-circuited before a threshold was read.

Widening `LIST_AVAILABLE` — the exact change the code comment warns about — left both green while
the preview began judging circuit against a fabricated `circuit_proximity_pct=100` and blocking
every listed row. The comment claimed *"`test_restrictions.py` pins the unreachability directly"*.
It did not. Replaced with tests that pin the **actual** reachable partition by name, and one that
runs every gate **ACTIVE**; both verified to fail on the widening, where the old form provably
cannot. This is the repo's own documented failure mode — *tests asserting what was INTENDED* —
and it landed in the tests written specifically to prevent it.

**A failed context load was recorded as "available", so an unjudgeable ACTIVE gate read as clear.**
`available` was meant to separate "looked, nothing there" (fail open — correct) from "never
looked" (unknown). A *failed* load is a third state and was filed under the first: no
`unassessed` entry, no WARNING, no `⚠ unchecked` badge — and the stamp written to
`broker_payload` recorded an infra fault as a **data-coverage gap**, which the shadow sidecars
then counted as evidence. Now a key joins `available` only when its load **succeeded**. Required a
new `get_circuit_band_checked() -> (band, ok)`, since `get_circuit_band` swallowed every exception
and could not distinguish Redis-down from no-band.

**The hand-maintained sequence A38 set out to delete had survived one level down.** The order
path's loads were keyed on gate *modes*, not on the registry's `requires`, so "a new rule lands
everywhere by construction" held for `check()` but not for `_load_restriction_context`: a new rule
requiring an **existing** key would be silently skipped whenever the unrelated gate that owned
that key was `off`. Now `_LOADABLE_CONTEXT` is checked against the registry at **import time** —
a rule with no loader fails at startup instead of quietly never running.

**`check()` no longer runs past the first block.** It had been judging every remaining rule; on
the display path an exception from a rule *after* the blocker escaped `preview`, and both callers
swallow that into a row byte-identical to "verified clear" — a blocked signal rendering a live Buy
button. The old preview `return`ed at the first block and was structurally immune. Restored.

**Also:** the sl_atr ATR requirement is now **declared** (`Restriction.sub_requires`) instead of a
hardcoded branch — the one gate whose assessability was not derived from data was the one that
most needed to be; and `LIST_AVAILABLE` now includes `CTX_FILL_PRICE`, with `preview` intersecting
against it, so the set that *derives* coverage and the set it *supplies* cannot diverge.

**⚠ A correction to the previous entry, and it matters more than the bug it corrects.** That entry
called the `entry_quality` stamp *"the entire forward-evidence mechanism for the sl_atr sidecar"*.
**That is false.** Nothing in the repo reads `broker_payload["entry_quality"]` — only `circuit_gate`
and `chase_gate` have readers. `entry_quality_shadow.py` **recomputes** `eq.evaluate` from `Signal`
rows using **today's** `entry_min_sl_atr_mult`. The truthiness fix was right; the reason given for
it was not, and it had been written into CLAUDE.md, the commit message and memory. **The real
consequence is worth more than the original claim: the sl_atr evidence is NOT point-in-time.**
Retuning `entry_min_sl_atr_mult` silently re-partitions the whole historical flagged/passed split
in every `entry-quality-shadow-<date>.md` — so a threshold tuned against that evidence is graded
by a yardstick that moved with it. Corrected in all four places.

**Confirmed sound by this pass** (verified with real Postgres faults, not by inspection): savepoint
discipline — an `UndefinedTable` inside each of the three nested blocks fails open, the order still
returns 201, and `in_nested_transaction()` is False on both the success and failure paths, no leaks;
no gate is silently skipped on the order path today; evaluation order byte-identical on both paths;
`_satisfied`/`requires_any` correct in all four price combinations; no mutable-default or aliasing
hazard; `RestrictionConfig.mode()`'s deliberate KeyError unreachable from any live caller; Decimal
money handling, tz-aware `as_of` threading, async boundaries, the frontend contract and both live
sidecar stamp readers all unchanged.

Tests: `tests/test_restrictions.py` now 32. ruff + mypy clean across 248 files.


### refactor(A38): one composable, point-in-time registry for every tradability rule (2026-09-05)

**Bucket A, item 1.** The eight eligibility gates were written out twice — once in
`api/v1/trading.py::_apply_eligibility_overlays` (with I/O, raising 409) and once in
`signals/eligibility.py::preview` (pure, for the list). Two hand-maintained sequences that had
to agree on which gates exist, in what order, and with what wording. The 2026-09-02 fix for the
display-path hole *was* the second sequence, kept in step by a contract test and a comment
reading *"⚠ flipping an uncovered gate ACTIVE means extending this module IN THE SAME COMMIT"* —
a synchronisation ritual, which is the thing that had just failed (41 of 204 listed signals
offering a Buy that could only 409, five Buy surfaces needing retrofit).

**Now each rule is declared once** in `app/signals/restrictions.py` and both paths walk the same
ordered registry. `eligibility.py` is a thin display-path adapter; `_apply_eligibility_overlays`
is replaced by `_load_restriction_context` + `restrictions.check(enforced_by=OVERLAY)`.

Three properties are now **data the composer reads** rather than rules a human remembers:
- **`requires`** — the context keys a rule needs. A rule whose context is unresolved is skipped
  and, if ACTIVE, NAMED in `unassessed`. `COVERED_GATES`/`UNCOVERED_GATES` are *derived* from
  this instead of typed out, so a new live-state rule becomes uncovered automatically.
- **`enforced_by`** — `OVERLAY` (settings-moded) vs `BROKER` (the paper broker's own
  unconditional pre-fill rejections). The order path runs only overlays, since the broker
  enforces its own and running them twice would double-reject; the preview runs both, because a
  user clicking Buy meets both.
- **`as_of`** — mandatory on the context. Every loader already accepted one; nothing could *pose*
  the composed question. A backtest can now ask "was this restricted **on that date**".

**Behaviour is preserved, and that was verified rather than asserted.** quant-verifier
transcribed the old order path and differentially fuzzed it against the new one: **30,000 cases
× 6 signals × 2 sides → 0 block diffs**, and 18,000 preview cases → 0 diffs under the live
callers' contract. Evaluation order is verbatim identical on both paths, `off` is still a true
no-op (no query, no verdict, no stamp), all four `as_of`/`before` anchors survive, the three
savepoint fail-opens are unchanged, and the frozen engine and protected spec are untouched.

**⚠ Two HIGH defects the first cut shipped, both found by that review, both now fixed and pinned
by canary tests proven to fail on the old code:**

1. **A truthiness bug silently stopped writing the `entry_quality` stamp.**
   `mode = "active" if "active" in (div, sl) else div or sl` — **`"off"` is a non-empty string
   and therefore truthy**, so `div or sl` returned `"off"` whenever diversity was off. The
   judgement was tagged off, `check` dropped it, and for `diversity=off, sl_atr=shadow` the gate
   ran and recorded nothing. The fuzz found exactly this: 1,885 stamp diffs, all in that one
   mode class. Replaced with an explicit `_effective_mode(active > shadow > off)`.
   ⚠ **This entry originally claimed the stamp is "the entire forward-evidence mechanism for the
   sl_atr sidecar". That is FALSE and is corrected below** — see the 2026-09-05 bug-hunter entry.
2. **`through_stop` could be skipped, reporting a void setup as CLEAR.** `requires` is an AND, so
   declaring `{market_price}` skipped the rule whenever only a modelled fill was supplied — and
   the preview judges the post-slippage fill by design. Added `requires_any`, so the rule needs
   *a usable price* and either will do. Latent (both live callers only build a fill when there is
   a price) but the dead `CTX_FILL_PRICE` constant was the tell.

Also from that review: `allow_offmarket` is now a **required** context field (a safety field
defaulting permissive is one refactor from being wrong, and `allow_offmarket_entry` defaults
FALSE); `stamp_key` is declared **once** on the `Restriction` and attached by `check` instead of
being repeated in every judge; the display path's stand-in thresholds for gates it cannot judge
now **block everything rather than pass everything**, so if `LIST_AVAILABLE` ever grows the
failure is loud instead of a plausible-looking verdict against fabricated numbers; and the
docstring no longer claims an I/O economy the code does not have — context is resolved **eagerly**
(the price of a pure composer), so a blocked order pays for the later gates' loads.

**Not done, and blocked rather than skipped:** A38 also wants the **backtest** consulting the
registry. The backtest currently consults no gate at all and `app/backtest/engine.py` is FROZEN,
so wiring it in changes recorded backtest numbers and needs explicit sign-off plus an §8
regression and regenerated Rust oracle fixtures. The interface can now pose the question; the
connection is a separate, sanctioned change.

Tests: **1684 passed** (full backend suite, run exclusively) · `tests/test_restrictions.py` adds
**28** covering the structural claims — including one that adds a rule to a copy of the registry
and asserts it lands on both paths untouched, a two-sided canary on the test fixture itself, and
the two regressions above. ruff + mypy clean across 248 files.

⚠ **Process note:** the first full-suite run was void — launched alongside the review agents, it
deadlocked on the shared test DB's per-test table reset and named an unrelated frozen-engine
test. Per the user's standing rule (2026-09-05), long tasks now run **strictly one at a time**.


### feat(evidence): H8 — the negative control on our own deflated-Sharpe bar (2026-09-04)

The bar was rejecting every gate we have, and that verdict was about to justify closing the
gating programme and redirecting months of work. Before acting on an instrument that says no
to everything, test the instrument.

**The specification in `quant-agent-findings.md` was insufficient, and that matters.** H8 as
written asks only *"does the bar reject pure noise?"* — modelled on an external repo's worked
example. But **a bar that rejects everything passes that check trivially**, and ours was in
exactly that state. A specificity-only suite would have gone green on a useless instrument:
hollow coverage of precisely the kind `.claude/rules/testing.md` warns about. So a **power arm**
was added — plant an edge of known size and require the bar to accept it. Only both arms
together distinguish *"our gates are not good enough"* from *"our bar cannot say yes"*, and
those two readings imply opposite next actions.

**Verdict: the bar is SOUND.**

| arm | result | expected |
|---|--:|---|
| specificity · random content-free partitions of the real book | **0.00%** cleared | ≤ 5% ✅ |
| specificity · **best of 20 zero-edge candidates** (the selection we actually perform) | **1.10%** cleared | ≤ 5% ✅ |
| power · min detectable true per-trade Sharpe @ 50% | **0.43** (t ≈ 3.83) | — |
| power · min detectable true per-trade Sharpe @ 80% | **0.52** (t ≈ 4.55) | — |

**⭐ The most useful output is a restatement: the bar is equivalent to demanding a t-statistic of
≈3.6 on the trade series, and that hurdle is flat in n** (3.76 at n=30 · 3.62 at n=78 · 3.55 at
n=1000). That turns an opaque probability into a number the literature already argues about —
Harvey, Liu & Zhu (2016) recommend **t > 3.0** for accepting a new factor, precisely because of
multiple testing. **Ours sits just above it: defensibly calibrated, not arbitrary.** It also
explains why MinTRL keeps returning `None` — the benchmark falls as `1/√n` while the required t
stays put, so more observations never lower the bar, they only sharpen an estimate that has to
be large to begin with.

**Consequences.** (1) **`sl_atr` is decided: NO, and its 20-trade trigger is withdrawn.** Its
eligible set is Sharpe **+0.046 over n=78 ⇒ t ≈ 0.41** against a ≈3.6 hurdle — short by ~9×, and
far below even the low-power band where the bar could be accused of missing something. It passes
all three readiness guards and still has no measurable edge in the book a flip would leave
behind; the count was never the constraint. (2) **"Fails the bar" is not "no edge" — except when
it is this far short.** Power is ~0 between t ≈ 2.6 and t ≈ 3.5, so a genuine but modest edge is
invisible; that is the price of multiple-testing correction and the right trade for a
promote-to-money decision. **Record the t, not just the pass/fail** — a future gate failing at
t ≈ 2–3 deserves a different conversation. (3) **The leak is upstream of gating, now demonstrated
rather than suspected:** eight gates, two promotions both refuted, best survivor at t = 0.41. No
partition of these trades clears t ≈ 3.6, because the trades carry no edge to partition.
Selection has been optimised; what *generates* the candidates has not.

**Shipped:** `app/services/dsr_control.py` (pure, stdlib, every entry point takes an explicit
seeded `random.Random` so findings reproduce) · `scripts/dsr_negative_control.py` → writes
`docs/analysis/dsr-negative-control-<date>.md` · `tests/test_dsr_control.py`, **14 tests** — the
standing guard, so the bar cannot silently drift into being permissive *or* impossible.

Synthetic series are **bootstrapped from the real book and shifted, never drawn from a normal**:
PSR explicitly penalises skew and fat tails, so a Gaussian control would flatter the one
distribution the bar has no complaint about. The real book's kurtosis is **11.46**. Shifting by a
constant moves the mean without touching sd, skew or kurtosis, which makes the planted Sharpe
exact by construction.

**Two things the work itself taught, both pinned by tests.** A canary asserting "10,000 trials
makes the bar impossible" **failed** — `E[max SR]` grows only as `√(2·ln N)`, so even a 500×
increase in trials leaves the benchmark at ≈0.44 and a true Sharpe of 0.90 still clears ~99% of
the time. The `confidence` threshold, not the trials count, is what makes a bar unreachable; both
facts now have tests so nobody "tightens" the wrong knob. And `minimum_detectable_sharpe` is
computed by bisection rather than read off the probe grid, which moved the reported 80%-power
figure from a coarse 0.60 to 0.52.

**Stated limits** (also in the report): the bootstrap assumes i.i.d. trades while ours overlap
and cluster by regime, so specificity is if anything optimistic; `trials = 20` remains an
assumption until **U4** counts them; and the power arm plants a *constant* edge, so a
regime-dependent one is harder to see than these curves suggest.


### fix(state): the R:R gate's live mode verified, and three records made to agree (2026-09-04)

Closes the one discrepancy the previous session flagged rather than guessed at. `config.py`
declared `rr_gate_mode = "active"`, CLAUDE.md described the R:R floor as ACTIVE, and the
2026-09-03 record said it had been reverted to shadow. **`.env` is hook-protected and cannot be
read**, so the question was whether the revert had actually reached the running processes.

**It had. Verified `shadow` in both, by evidence rather than by reading the file:**

| link | value |
|---|---|
| fresh settings load (`get_settings().rr_gate_mode`) | `shadow` — and since the *code* default was `"active"`, the mismatch is itself proof `.env` overrides |
| uvicorn `--reload` **child** start (the parent never restarts) | 2026-09-03 **12:28:21** |
| celery worker start | 2026-09-04 **08:37:49** |
| the revert commit (`git log -S` on the CHANGELOG heading) | 2026-09-03 **09:34:45** |

Both live processes re-imported `app.core.config` *after* the flip, so both hold `shadow`.
The generalised recipe — including the trap that the uvicorn PID you see in `ps` is the reloader
parent, whose start time is meaningless — is now written into **CLAUDE.md** as
*"HOW TO VERIFY A GATE'S LIVE MODE"*, so the next check costs minutes.

**`config.py`: default moved `"active"` → `"shadow"`.** A fresh checkout, a new dev box or CI had
no `.env` and would therefore have run the *refuted* configuration. The comment block was also
rewritten: it still argued the premise the tape falsified — that a >50% win rate is something "no
trend-following system sustains" — which is a disproven rationale sitting in the code that
implements it, worse than a merely stale comment. It now records why the premise was wrong
(the blocked cohort sustained 63%, and R:R<1 is a proxy for a *wide* stop). **No live behaviour
changed:** `.env` already said shadow, and shadow is what both processes were running.

**⚠ `STATUS.html` had drifted much further than the R:R line**, and the same pass corrected it.
It advertised **"2 live · 5 shadow"** gates and showed the **regime gate as ACTIVE in four separate
places** (KPI tile, the gate table, the Phase-6 status row, and the risk list, which still read
"the regime gate is live on one walk-forward … reverting is one environment variable") — three
weeks after the 2026-09-02 revert. Also corrected: the R:R overlay described as "queued" when it
had shipped *and* been reverted; `sl_atr` at 12/20 → **17/20**; CAS at "0 rows · starts 08-26" →
**1,664 rows / 8 sessions, complete**; MCE "2 inert pending backfill" → backfill verified done;
heat 25.6% → **58.0%**; the gate table given its missing 8th row and the "seven gates" headings
corrected; and the critical-path diagram re-pointed at the execution plan. Date stamps moved to
2026-09-04.

**Rendering the page caught what grepping did not.** A headless screenshot showed the header still
advertising *"CAS built → WATCH MODE to 09-04"*, an "Active work: CAS watch" tile, a **"2 sessions
to go"** counter and a callout written in the present tense about a window that had closed — plus
three more "seven gates" strings the earlier greps missed (the Part-I intro, the §01 paragraph and
the guiding-principle callout) and the ASCII gate diagram, which needed its 8th row. **Read the
rendered page, not just the source**; prose drift does not match the strings you think to grep for.

**Paper-book figures re-read from the database** (the page claims its numbers come from the dev DB,
so they were verified rather than trusted): all-time **−₹7,932 / 83 closed / ₹15,160 charges** →
**−₹10,218 / 105 closed / ₹18,539**; era 2 **−₹10,817 / 6 trades** → **−₹13,104 / 28 trades, 11
winners**; open book 13 → **29**; and 96 positions opened → **134** since 2026-07-07. The journal
reconciliation in §22 was re-verified rather than merely restated: **105 journal entries vs 105
closed positions, both summing to −₹10,218.30 exactly.** Era 1 still computes to +₹2,885, so the
two eras remain internally consistent. The era-2 *trade-by-trade* table was **not** regenerated —
it is the six trades §18's stop-width finding is argued from, and it is now labelled as the first
six rather than silently presented as "the whole record".

**The standing hazard, restated because this is its second bite:** `STATUS.html` hardcodes gate
modes AND figures in prose, in tables, in an ASCII diagram and in the KPI tiles, with no live data
source. A mode flip silently falsifies it. **Grep every gate name in it on every flip, and render
it before believing it.**

Tests: 169 green over the touched surface (`test_rr_guard` 14, plus `test_eligibility_preview`,
`test_trading`, `test_entry_quality`, `test_entry_quality_shadow` = 155). Every R:R test
monkeypatches the mode explicitly, so the default change moved no assertion.


### docs(state): watch mode closed, docs re-synced for the next session (2026-09-04)

Doc-sync ritual run at the close of the review series.

**✅ WATCH MODE COMPLETE (2026-08-26 → Fri 2026-09-04).** CAS Stage-1 accrual verified by query:
**`cas_daily` = 1,664 rows across 8 sessions, last captured 2026-09-04, no session missed.** Stage 2
(the overnight-reversal study) is unblocked, and the standing daily "check the row count each
morning" obligation is **discharged — explicitly marked not to carry forward**, since it was the
kind of manual ritual that outlives its purpose.

**`docs/PHASES.md`** — STATE block re-stamped 2026-09-02 → **2026-09-04** with the watch-mode close,
the 30-repo review, the six findings that were about *our own* code, and the calibration (median
published Sharpe 0.37). **CONTINUE HERE** rewritten: it still told the next session *"THIS WEEK IS A
WATCH, NOT A BUILD (to Fri 2026-09-04)"*, which would have read as still-active; it now points at
the execution plan with Buckets A and B named.

**`CLAUDE.md`** — the watch-mode bullet replaced with the completed state plus the next build.

**⚠ One unresolved discrepancy, flagged rather than guessed, in both docs.** `config.py` declares
`rr_gate_mode = "active"` (`rr_min = 1.0`) and CLAUDE.md describes the R:R floor as ACTIVE, but the
2026-09-03 record says it was **REVERTED to shadow** (it blocked the only profitable cohort — 24
trades, +₹10,585, 63% win — because R:R<1 is a proxy for a wide stop). **`.env` is hook-protected,
so the live mode could not be verified this session.** Per our own rule — *verify a gate from the
running process, never the file, because `settings` is an `@lru_cache` singleton* — this is now the
**first action item** in CONTINUE HERE. Nothing was flipped on the strength of a doc.

**Also recorded:** heat has drifted **45.3% → 58.0%** of capital (₹58,034, 29 open positions), still
with no portfolio-level cap; and the standing note that **the plan buys evaluation, not edge** — the
known lever remains `compute_levels` producing 94/295 swing signals with R:R < 1 by construction,
which is frozen-engine work and deliberately not in the 91 items.


### feat(evidence): the deflated-Sharpe bar, and every readiness banner now ships its data (2026-09-03)

Two gates were promoted on favourable-looking evidence in one week and both had to be
reverted. The missing instrument was a bar that accounts for **how many things we have
tried** — search enough variants and the best one looks good by luck alone.

**NEW `app/services/deflated_sharpe.py`** (stdlib only — `statistics.NormalDist` supplies
the normal CDF and its inverse, so no new dependency):
- **PSR** — P(true Sharpe > benchmark), adjusted for sample length, **skew and kurtosis**.
  That adjustment matters here specifically: our losses cluster in a few large trades, and
  a metric that ignored that would flatter us.
- **E[max SR]** — the Sharpe the best of N zero-skill trials would show anyway. The bar a
  candidate must clear *instead of zero*. `DEFAULT_TRIALS = 20` is a documented constant
  (8 gates + threshold variants + 4 exit policies + 2 breakeven rungs) — bump it when a new
  variant is tested, never lower it.
- **DSR** = PSR against E[max SR].
- **MinTRL** — the sample size at which a candidate *could* reach the bar if today's
  moments persisted. This turns "keep accruing" into "keep accruing until n ≈ X", which is
  what the review calendar needed. It returns `None` when the candidate is not ahead of the
  benchmark at all, because no amount of data rescues that.

**First read on the live book — every gate fails, and all for the same reason:**

| gate (eligible set = the book a flip leaves you holding) | n | Sharpe | 20-trial bar | DSR |
|---|--:|--:|--:|--:|
| market-regime | 33 | −0.004 | +0.331 | 2.9% |
| anti-chase | 51 | +0.032 | +0.266 | 4.9% |
| sector-RS | 59 | −0.105 | +0.247 | 0.3% |
| liquidity | 72 | −0.150 | +0.224 | 0.1% |

**Not one candidate's Sharpe even exceeds its benchmark**, so `MinTRL` is `None` for all
four: more data cannot rescue them because they are not ahead. Bar 95%; best result 4.9%.
**No gate currently on the board is promotable, and the constraint is not sample size** —
the book a flip would leave you holding has a Sharpe of ~zero either way, so the leak is
upstream of gating. 17 tests, including the PSR closed form checked against a
hand-computed value and that fat tails/negative skew reduce confidence.

**Evidence of record on every banner** (user request: *"along with ✅ READY or sign-off it
is best to have the data or record of the captured one — it helps better"*).
`flip_readiness.evidence_lines` now appends, under each readiness verdict: a
would-block-vs-eligible table (**n · resolved · mean · median · trimmed mean · win%**), all
three shared guards with their measured values, and the deflated-Sharpe block. A verdict
without its numbers cannot be re-judged later — and both reverted gates were caught
precisely because someone went back to the numbers.

**Completeness contract (`test_sidecar_readiness_contract.py`).** I reported the evidence
block as landing on "every readiness banner". It was **four of seven** — and the worst
omission was `entry_quality_shadow`, the one carrying `sl_atr`, the gate closest to a
decision: it aggregated its rows into Buckets and discarded them, so it *could not* run the
guards (aggregates are not recoverable into rows after the fact). A second audit then found
`circuit_gate_shadow` had the evidence block but **not the veto**, so its banner could still
print READY without the guards running. Both slipped through because nothing checked the set.
- All seven are now wired (`entry_quality_shadow` keeps a `SignalQuality` detail row;
  `circuit_gate_shadow` runs the veto on its blocked-only rows, where `side_proxy`/`win_rate`
  degrade to "not assessable" and `tail` does the work).
- The new test **auto-discovers** `app/services/*_shadow.py`, so a sidecar added later is
  covered without anyone remembering a list, and asserts each one that prints a readiness
  verdict calls **both** `fr.veto` and `evidence_lines`. Exemptions must carry a written
  reason (>80 chars) and are checked for staleness — `regime_gate_shadow` is the one
  exemption: it holds only aggregate `GateMetrics` and already prints a richer record
  (3 variants × 8 §8 metrics).
- It includes a "guard the guard" case (discovery must find ≥7 modules, or every other
  assertion would vacuously pass), and **I verified it fails when wiring is removed** —
  deleting `fr.veto` from one sidecar reproduces exactly the error message it should.

**And the contract immediately paid for itself on `sl_atr`** — the first gate whose evidence
is structurally sound:

| set | signals | resolved | mean | median | trimmed mean | win% |
|---|--:|--:|--:|--:|--:|--:|
| would-BLOCK | 123 | 17 | −₹1,118 | **−₹2,221** | −₹545 | 41% |
| eligible (kept) | 423 | 74 | +₹17 | +₹44 | +₹406 | 51% |

All three guards **pass**, and note the median is *worse* than the mean — the exact inverse
of market-regime, i.e. its losses are broad rather than tail-driven. **Yet it still fails the
deflated-Sharpe bar** (eligible Sharpe +0.009 vs a +0.221 benchmark). That contrast is the
most useful thing the two instruments produced together: **`sl_atr` correctly identifies a
genuinely bad cohort, and removing it still does not leave a book with measurable
risk-adjusted edge.** Concretely — it will likely hit 20/20 shortly and pass every
qualitative guard, and that alone will not justify a flip.

It immediately showed something the ₹ means had hidden: **market-regime's would-block
trimmed mean is +₹200**, from a −₹302 mean. Trimming the worst 10% does not merely weaken
that gate's case, it *reverses the sign*. The eligible set's trimmed mean is +₹346 — both
cohorts are profitable once the tails come off, which locates the whole book's negativity
in a handful of trades rather than in cohort selection.

### revert(R:R gate): ACTIVE → SHADOW — the "identity" premise was wrong (2026-09-03)

Shipped active on 2026-09-02 with the argument that it enforces an *identity* and therefore
needs no evidence bar. **Measured on the live tape the same week, it blocks the only
profitable cohort in the book.**

| cohort | n | net | avg | win% | avg stop | tight (<2%) | tp_hit% |
|---|--:|--:|--:|--:|--:|--:|--:|
| **R:R < 1 — was BLOCKED** | 24 | **+₹10,585** | +₹441 | **63%** | **7.29%** | **0** | **33%** |
| R:R ≥ 1 — allowed | 77 | **−₹26,792** | −₹348 | 48% | 4.38% | 11 | 16% |

**Where the reasoning failed.** The arithmetic was right: at planned R:R < 1 a trade needs a
>50% win rate to break even. The *premise* — "which no trend-following system sustains" —
was an assertion I never checked, and it is false for exactly this subset. Two mechanisms:
1. **A nearer target is mechanically easier to hit** — 33% tp_hit vs 16%. The cohort
   sustained **63%**, clearing the bar the identity sets.
2. **R:R < 1 is a proxy for a WIDE stop** — 7.29% average and **zero** tight stops, versus
   4.38% and 11 tight in the allowed set. Wide stops are independently the *good* cohort
   (>6%: 59% win, +₹6,880), so blocking R:R<1 blocks wide stops — backwards.

`RR_GATE_MODE=shadow` (user, 2026-09-03). n=24 is small, so shadow-and-measure is the
honest state. **Standing lesson: an identity about arithmetic still rests on an empirical
premise — check the premise against the tape before flipping, not after.**

### research(market-regime): the ✅ READY banner is measuring SIDE, not regime — do not flip (2026-09-03)

The market-regime sidecar has been printing **✅ READY for sign-off**. It should not be
acted on, and the banner itself cannot currently tell why.

- **NIFTY50 sat below its 200-DMA on 33 of 33 days** in the measurement window, so the
  gate never varied — it was "block longs" throughout. Per-entry: **39 LONG → all blocked,
  11 SHORT → all kept, zero exceptions.** "Would-block is net-negative (−₹302) vs eligible
  (−₹7)" therefore just restates *our longs lost and our shorts broke even* over one
  directional window. It is a **side proxy**, not a regime finding.
- **It would block the cohort with the better median AND the better win rate:** LONG 65
  trades, median **+₹156**, win **54%** (mean −₹246) vs SHORT 36, median −₹44, win 47%.
- **The mean is a tail.** Dropping the worst **3** longs takes the long book from
  **−₹15,986 to +₹10,861**; worst 5 → +₹19,879; worst 8 → +₹30,365. **NDRAUTO alone is
  −₹14,970 — 94% of the entire long-side loss**, and 6 of the 8 worst longs have stops
  under 2.3%.
- **The combination test settles it:** exclude tight stops (<2%) — the pathology `sl_atr`
  is actually designed for — and the long book is **+₹11,450 at 60% win over 57 trades**.
  The gate wants to block all of that and keep the −₹221/47% shorts. It subtracts the good
  half.
- **A 2-year test is not currently possible:** `signals` begins 2026-07-06 (636 rows, ~8
  weeks). Testing a gate over 2y means running the **backtest corpus** through it
  (`gate_walkforward`-shaped work, built for the ADX gate), not a query.

**Follow-up queued:** the readiness function cannot distinguish a gate from a side proxy.
It should refuse ✅ READY when the regime state never varied across the window, and require
the sign to survive trimming the tail.

### feat(evidence): the profit-lock breakeven knob is A/B-able for the first time (2026-09-03)

The 2026-08-18 research recommended moving `profit_lock_breakeven_inr` 2,000 → 800 and said
to "run it as a forward A/B (the `profit_lock_shadow` infra already A/Bs this)." **It did
not** — the comparator replayed `ladder`/`layered`/`giveback_33`, none of which is the
absolute-rupee ladder `position_monitor` actually runs, so that knob had never been
measurable there.

- Added `abs_live` + `abs_early_be` to the comparator: the same live ladder with **only**
  the breakeven rung varied (trail_start/giveback/atr_k stay put — the research was explicit
  that the wider "arm early AND trail wide" hybrid did not win). New setting
  `profit_lock_breakeven_early_inr` (default 800) names the candidate; nothing acts on it.
- **Result over 99 closed trades: 20 differ — 13 runners clipped vs 7 blow-ups prevented.**
  Live still-running gains of +₹361…+₹3,032 become −₹60…−₹140 flat exits; against that,
  −₹305…−₹2,737 blow-ups become −₹60…−₹233. Aggregate flips with censoring treatment
  (all 99: early ₹7,034 **worse**; both-actually-exited 35: early ₹7,766 **better**) — and
  13 of the 20 differing cases have `abs_live` censored, i.e. still holding an unrealised
  gain, so the "both exited" view flatters early-BE by excluding exactly the clipped
  runners.
- **Verdict: the retune was NOT shipped.** ₹800 = +0.4R at the ₹1L/2% budget, which is
  inside normal pullback noise. Three independent studies now agree a stop inside one
  session's range carries no information: the 08-25 horizon study (stops <1× daily range →
  **8/8 recovered**), the `sl_atr` threshold at 1.0× ATR, and this A/B.
- **The knob's UNITS are the problem, not its value.** `breakeven_inr` is flat rupees, so
  ₹800 is 0.4R for everything — including names whose daily range is 3R. A
  volatility-denominated rung (k × ADR) is the coherent shape, but searching over k on 20
  differing trades is the exact overfitting the deflated-Sharpe bar exists to prevent, so
  it is queued, not built.
- Tests: the exact-policy-set guard extended (kept exact, so an accidental addition still
  trips) + a one-variable A/B test proving the variants diverge only via the breakeven rung
  and are byte-identical when the rungs match. Deliberately **no** assertion on which
  variant earns more — that depends on what price does next, and pinning it in a unit test
  would be asserting a market opinion.

### feat(measurement) + governance: dual-denominator exposure, the heat counterfactual, and TWO paper cycles (2026-09-02)

**Governance (user ruling) — two paper cycles, not one.** Full plan:
`docs/phases/phase-07-live-trading-plan.md` (the Phase-7 doc, which did not exist before).
- **Cycle 1 = the wide sampler running now** (~5 entries/day, ~5-day holds ⇒ ~25 concurrent
  positions), deliberately broad to accrue entry/exit evidence fast. **Its 30-day clock is
  now INFORMATIONAL**, because a ~25-position book at 45.3% of the live capital figure is
  not the book that will ever be traded (live = ₹1 lakh, 1–2 positions) and the two can
  produce **opposite signs from identical signals**.
- **Cycle 2 = the rehearsal.** After CAS Stage 2 · MCE 5b + 6 · the tuning/promotions · the
  deflated-Sharpe bar · **Phase 7.1–7.4**, reset the clock and run **45–50 trading days
  targeting 30 profitable** on a heat-capped ₹1 lakh book. **That** is the binding go-live
  gate. Honest timeline: cycle 2 alone is ~9–10 weeks, so live is realistically 4–6 months
  out — the direct consequence of *"no point of going live without proper paper trading
  result with better strategy."*
- **Phase 7 is split by what paper can PROVE.** Before cycle 2: **7.1 RiskEngine
  single-gate** (test-first, equivalence-pinned; absorbs the circuit breaker + the six
  eligibility overlays + the notional cap + the R:R floor + the heat cap, which are
  currently scattered across `api/v1/trading.py` and `broker/paper_broker.py`) · **7.2
  BrokerAdapter port** · **7.3 order FSM** (Denied/Rejected/Filled) · **7.4
  reconciliation-on-restart + kill switch + audit trail**. After cycle 2: Kite placement,
  GTT, genuine partial fills/rejections, broker-book reconciliation, token lifecycle under
  live orders — only reality validates those, and simulating them is a modelling choice
  (6.8.2 showed how much modelling quality matters: 82% of live books were wider than the
  flat 2 bps we assumed). **Rationale:** `.claude/rules/testing.md` — *"453 green tests once
  coexisted with a dead live pipeline: test the SEAMS."* A 45-day rehearsal through the real
  ExecutionEngine gives the plumbing 45 days of runtime hours with fake money; the same
  rehearsal on today's `place_paper_order` leaves it at zero — and v1 Phase 7's four
  integration defects were exactly plumbing. **Risk noted:** designing the BrokerAdapter
  interface purely from the Kite docs risks meeting reality on live day 1 → mitigate with a
  **read-only** Kite spike in 7.2 (order-status/margins/positions; no placement).
- **The heat cap is DESIGNED but deliberately NOT BUILT.** It belongs inside 7.1's
  RiskEngine (building it now means retrofitting), and it must not throttle cycle 1 — a 6%
  cap cuts entries by ~74%.

**Dual-denominator exposure** (`paper_sampling_capital_inr`, **reporting only**).
- `capital_inr` is the LIVE figure and drives all sizing; it does not change. The declared
  sampling scale is used **only** as a reporting denominator — it never touches
  `compute_quantity`/`size_for_fill`, so no trade changes size and history stays comparable.
- The daily report now prints **both, labelled**: the same 23 positions are *45.3% of the
  ₹1,00,000 LIVE capital* and *9.1% of the ₹5,00,000 sampling scale*. Replacing one
  misleading denominator with a different one would have been no improvement. `0`/absent =
  previous behaviour exactly. 2 tests.

**Heat counterfactual** (`app/services/heat_counterfactual.py` + a
`heat-counterfactual-<date>.md` sidecar in `make analysis`). **Enforces nothing.**
- Replays every paper entry chronologically against a cap, releasing budget on close, and
  reports the admitted subset beside the full book — so cycle 2's book shape is measurable
  *during* cycle 1 with zero behaviour change.
- First read (since the clock epoch): **admitted 12 / skipped 35 · capped −₹13,303 vs full
  −₹19,093 (+₹5,790 total) · per-trade −₹1,478 vs −₹796** ⇒ **the cap is a RISK control,
  not a profitability fix** — it cuts total loss by taking fewer trades at an unchanged
  negative expectancy. Nothing here repairs −0.303R/trade.
- Heat definition: `qty × max(0, entry − commit_SL)` — clamped at zero (a stop past entry
  exposes nothing), **initial** risk not mark-to-market (a from-the-mark definition
  *loosens* as the book deteriorates, which is perverse for a risk cap), and from the
  **commit** stop never the trailed `current_sl` (that would leak price action the decision
  could not see).
- **Two self-corrections found by using it, both now pinned by tests:** (1) the first run
  defaulted to `OUTCOME_EPOCH` and silently spanned the **2026-08-17 cut**, where risk-first
  sizing moved from the signal entry to the actual fill AND the honest fill model started —
  the tell was admission risks of **₹5,663 against a ₹2,000 budget**; it now takes
  `user.paper_clock_started_at`, the clock's own epoch, so it answers the question about
  exactly the window the go-live gate measures. (2) the first verdict said *"the cap would
  have HELPED"* from TOTAL P&L alone, which is misleading because admission is
  **chronological** — it selects by arrival time, not quality, and one ₹6,000-risk entry can
  consume the whole budget and block three good ones behind it; it now reports per-trade
  alongside and names that limit in the report body. 10 tests, including one that pins the
  "risk control, not a profitability fix" wording.
- Why a retrospective ENTRY replay is legitimate at all (unlike an exit replay): declining
  to enter changes neither the market nor which other signals fire, so the admitted trades'
  outcomes are exactly the outcomes they really had.

### feat(safety): per-position notional cap + the reward:risk floor overlay (2026-09-02)

Both approved by the user after the 09-02 audit. Neither needs a spec change — that was
the point of splitting them out from the `paper_min_risk_pct` proposal.

**Per-position notional cap** (`paper_broker._check_notional_cap`,
`paper_max_notional_leverage = 1.0`).
- Risk-first sizing bounds a trade's **risk** but says nothing about its **size**:
  `qty = risk_budget / risk_per_share` has no ceiling on `qty × price`. A stop four paise
  wide sized **50,000 shares = ₹1,18,65,000 on ₹1,00,000 of capital** — 119× the account —
  and returned 201, so the row entered the paper book, the R statistics and the 30-day
  go-live clock. Both agent reviews reproduced it independently.
- Cap = `capital × leverage`, default **1.0** = NSE cash-delivery reality: you cannot buy
  more stock than you have money. Includes any existing position in the same name so a
  repeat entry cannot stack past it. **Reject, never clamp** — a clamped size would
  silently change the trade's risk, the one thing sizing exists to hold fixed.
- **Deliberately NOT the `paper_min_risk_pct` floor that was proposed.** A `%-of-price`
  minimum stop is the wrong instrument: 2% of price is comfortable on HDFC Bank and a
  knife-edge on a ₹39 micro-cap. Volatility is the right denominator, and the gate that
  uses it (`sl_atr`, in ATRs) already exists at 17/20 on its own bar, independently
  reproduced by the 08-25 horizon study at the same 1.0× threshold. So the spec stays
  untouched: cap the notional now, promote `sl_atr` when it clears 20.
- ⚠ **PER POSITION only.** Portfolio-wide exposure is the heat cap's job — still not
  built, and the book ran at **45.3% risk across 23 positions**.

**Reward:risk floor overlay** (`app/signals/rr_guard.py`, `rr_gate_mode = active`,
`rr_min = 1.0`).
- Rejects a signal whose planned **target is closer than its stop**. **11 of the 190
  currently-listed signals (5.8%)** are in that state, and 6 of the 23 open positions were.
- **Ships ACTIVE with no forward-evidence bar, and that is not an oversight.** Every other
  overlay asserts something *empirical* about the tape and therefore waits on its
  pre-registered count. This one enforces an **identity**: at planned R:R < 1 the trade
  needs a >50% win rate merely to break even, which no trend-following system sustains.
  There is no hypothesis to falsify. **Raising the floor above 1.0 IS empirical** — 1.67 is
  the break-even payoff at our observed 37.5% win rate, i.e. a number fitted to 99 trades —
  and must pass the deflated-Sharpe / multiple-testing bar first. The distinction is
  documented in the module, the settings and `.env.example` so a future reader does not
  "helpfully" tune it.
- **Complementary to `sl_atr`, not redundant — the two are structurally disjoint.** A
  too-tight stop mechanically produces a LARGE ratio (a fixed 6% target ÷ a 0.4% stop =
  15:1), while R:R < 1 only arises when the stop is WIDE. Measured on the live inventory:
  11 under R:R 1.0, 21 with stops under 2% of price, **zero in both**. A test pins this so
  nobody later "deduplicates" them.
- Root cause named in the module: `analysis/risk.py::compute_levels` (FROZEN) pairs a
  STRUCTURAL stop with an ABSOLUTE-% target, so the ratio is an accident of pivot
  placement. Intraday/scalp are ratio-based (1:2, 1:1.5) and unaffected. Making
  swing/positional ratio-based is a §6 spec change + §8 regression — deliberately not done
  here; this overlay is the tourniquet.
- Wired into **both** paths: the order path (`_apply_eligibility_overlays`, beside
  entry-quality since both judge the signal itself, ahead of every gate needing live market
  state) and the display path as a **COVERED** gate — it is decidable from the signal row
  alone, so the list and detail endpoints judge it exactly as the order path does, with a
  contract test asserting the two produce the identical string.
- No fixtures reddened: the suite's signals are 2.0 and 4.0 R:R, checked before flipping
  the default (the 08-19 lesson about active defaults and thin fixtures).
- Tests: 14 in `test_rr_guard.py` (pure, mode-gating, short-side symmetry, the exact-1.0
  boundary, zero-risk fail-open, the disjointness proof, order path ×3, display path ×2) +
  5 notional-cap cases including the ₹1.19cr canary and the leverage knob.
- **The cap reddened one existing test, and the FIXTURE was the unrealistic part:**
  `test_spread_fill.py::test_large_order_pays_impact_past_top_of_book` placed **3000 shares
  ≈ ₹15.2 lakh on a ₹1 lakh account** to exercise the impact term. The economics it tests
  are real and its assertions are unchanged; what was impossible was the account. `_make_user`
  now takes a `capital` override and that user is funded at ₹20 lakh. **I only pre-flighted
  fixtures for R:R<1 and never for large-notional ones — the same pre-flight gap as 08-19,
  one class over.** When flipping ANY order-path constraint on, grep the fixtures for what
  the NEW rule measures, not just the last rule's shape.

### fix(ui): ui-reviewer round — the blocked state was unreadable and unreachable (2026-09-02)

Verdict FAIL, on rendering rather than design. Token *choices* were right (zero raw hex,
zero palette classes, zero `dark:`, all grep gates clean) — but the state was measured
unreadable in every theme and, on two surfaces, had no path to the reason at all.

- **Contrast: I stacked `opacity: 0.55` on the blocked row on top of the Button
  primitive's own `disabled:opacity-50`** → 0.275 effective alpha. Measured: the word
  "Blocked" at **1.52–1.99:1** and the badge at **2.15–2.83:1**, against a **4.5:1** AA
  floor, in all five themes — I made the one row that most needs reading the least
  readable in the app, on the widest Buy surface. The dim is gone; a blocked row now
  carries a `border-l-2 border-l-(--color-loss)` accent, leaving foreground contrast
  intact (UI_GUIDELINES §12.6 / §13.2).
- **A11y: a native `disabled` made the reason unreachable.** Verified in jsdom that
  base-ui emits a real `disabled=""`, which drops the button out of the tab order AND —
  via `disabled:pointer-events-none` — kills its own `title` tooltip. So an `aria-label`
  carrying the block reason was attached to an element **no keyboard and no mouse user
  could reach**; on LiveSignalsPage and StylePage there was no path whatsoever. All five
  surfaces now use `aria-disabled` + an `inert` click guard: focusable, ring intact,
  tooltip works, still cannot fire an order. Tests assert `aria-disabled` AND
  `not.toBeDisabled()` so the contract is pinned.
- **`TradeBlock.unknown` was read by ZERO call sites** — the field was returned, its
  docstring promised it "must LOOK different", and nothing rendered it. Now a visible
  `⚠ unchecked` marker in the same warning-token idiom as the adjacent `⚠ stale` flag, on
  every surface, with a test asserting the marker is in the DOM (a title-only affordance
  is invisible on touch and to a scanning eye).
- **Hand-rolled pill replaced with `StatusPill kind="rejected"`** — which already shipped
  the exact `text-(--color-loss) bg-(--color-loss-bg) border-(--color-loss)/20` triplet,
  an `XCircle` and an on-scale `text-[10px]`. The first version duplicated it badly at
  `text-[9px]`, off the §2.3 type scale (§19.3: "never hand-rolled").
- **Five hand-built variants of one state consolidated.** OpportunitiesTable hardcoded
  `'Blocked'` with no glyph and no colour while `block.label` existed; AlertBell built its
  own fragment; the loss colour was applied on three surfaces and omitted on two. Label,
  glyph and the unknown marker now all come from the helper (§14).
- JSX comments wedged inside attribute lists and three column-0 opening tags cleaned up.

**Two PRE-EXISTING issues fixed because this work made them load-bearing:**

- **The Dashboard trade button had no `focus-visible` ring at all** (§10.1) — on the
  landing page's widest Buy surface, and it now carries the eligibility reason, so a
  keyboard user could neither see focus nor read the message. Ring added; the icon-only
  copy button beside it also got its missing `aria-label` (§19.4).
- **daybreak `--color-loss` was 3.95:1 on its own `-bg`** — below AA, affecting every
  existing `hit_sl` / `rejected` / `sell` StatusPill, not just the new badge. Darkened to
  red-700 following the file's own `--color-warning` amber-700 precedent, and **measured
  rather than assumed**: red-600 3.95:1 FAIL → red-700 **5.30:1** on `-bg`, 5.91:1 on
  `--color-surface-2`, 6.47:1 on white. (The first comment quoted 5.42/4.83 from memory;
  corrected to the measured values — a comment whose purpose is recording a measurement
  must not carry an approximation.)

**Left as recorded pre-existing:** raw `<button>` in four feature files (§8.1) and
`DashboardPage` bypassing `lib/format.ts` for prices (`₹{pctFmt(...)}` ×3, §1.3/§3.2).
Real violations in files this diff touches; neither is from this work.

Gate: frontend typecheck 0 · eslint clean · **`npm run build` passes** (the real build,
not just the app tsconfig — that is the documented `make check` gap) · **413 vitest**.
Backend unchanged: **1574 passed**.

**Review tally for the 2026-09-02 eligibility work: 21 defects found across three agent
reviews, in work that passed its own tests and was doc-synced twice.** The tests asserted
what was intended, not what the code did — the false-BLOCK direction, the off-market
default, the fifth Buy surface, an unreadable contrast ratio, and a dead field documented
as live all passed a green suite.

### fix(eligibility): quant-verifier round — the preview now AGREES with the order path (2026-09-02)

Verdict PASS-WITH-NOTES. Spec conformance held throughout (frozen engine and parity
fixtures untouched · no new look-ahead — the detail endpoint's `latest_atr(...,
before=signal.created_at)` anchoring is byte-identical to the order path · sizing formula
intact with `risk_pct` not re-divided · money Decimal end-to-end · shadow `measure`/
`gate_metrics`/`readiness_line` byte-identical · no signal generated differently). The
findings were all about the preview DISAGREEING with the order path:

- **The preview compared the raw LTP; the broker compares its POST-SLIPPAGE fill** — so
  they disagreed inside a half-spread/half-tick band **in both directions**. Reproduced:
  LTP 237.25 vs SL 237.26 previewed as blocked while the order path fills 237.30 and
  allows the trade. **That is a false BLOCK, which HIDES A TRADEABLE SIGNAL** — the worse
  of the two errors and the opposite of this feature's purpose. The preview is now judged
  on `simulate_fill(ltp, side).fill` (pure with `depth=None`, so list-safe), with a test
  pinning that the LTP-only and fill-based verdicts differ.
- **The broker has TWO unconditional pre-fill rejections; only one was previewed.** The
  off-market guard fires when there is no live tick and `allow_offmarket_entry` is False —
  **which is the default, and the list is usually read outside market hours**, so every
  row read `blocked=False` in the evening while the order path 422'd all of them. Now
  previewed via a shared `OFFMARKET_REASON`, with the user's real flag threaded through
  both endpoints. Probably the most common wasted click in the app.
- **A FIFTH Buy surface: `StylePage`.** It posts real `Signal` ids into the same order
  path and its `SuggestionOut` had no eligibility fields at all. The styles endpoint now
  stamps the same verdict (batched MGET, the shared `eligibility.gate_modes()`, the same
  fail-open containment) and the page renders it. **`gate_modes()` moved into
  `eligibility` so every surface shares ONE definition.**
- **The "all four share one helper" claim was FALSE** — `OpportunitiesTable` and
  `AlertBell` re-implemented the logic inline (behaviour right, claim wrong). All **five**
  surfaces now genuinely route through `tradeBlock()`.
- **`unassessed` never reached the client**, so "unknown, never a silent clear" lived only
  in a server log — at the exact place the wasted clicks happen. Now on both schemas and
  rendered as a distinct **enabled-but-marked** state (it is not blocked; we just do not
  know), with `tradeBlock().unknown`.
- **A non-finite LTP would 500 the detail endpoint.** `Decimal("nan")`/`Decimal("Infinity")`
  PARSE without raising and the suppressed exception set did not catch them, so
  `price <= stop_loss` threw `InvalidOperation`. Same bug class the same commit fixed in
  `entry_quality`, reintroduced one file over. Now rejected at the Redis boundary in BOTH
  `get_live_ltp` and `get_live_ltps` (non-finite or ≤ 0 ⇒ no price).
- **The NaN comment claimed "fail open" but mixed payloads fail CLOSED** — `{nan, 0.8}`
  reads as ONE scoring factor, so an ACTIVE diversity gate blocks it. Correct per
  SIGNAL_ENGINE §1/§2 (one readable factor IS a single indicator), but the wording was
  wrong. Reworded + the mixed-payload test.
- **`chase_gate` was listed uncovered although `chase_guard.evaluate` is pure** and needs
  only the price already in hand — it is now JUDGED rather than logged as unassessable.
- `status != "active"` previewed on the detail path with the order path's own sentence;
  `MODE_EFFECTIVE_FROM` generalised to `circuit_gate_shadow`; the superseded
  `known(bug): …unfixed` entry (fixed in the same diff) removed.
- Tests: 32 eligibility-preview cases (off-market ×3, fill-vs-LTP, chase ×3, tripwire per
  uncovered gate), 20 entry-quality, +2 frontend (StylePage blocked + the unknown state).
  Full gate: backend **1574 passed**, ruff + mypy (`app/` + `scripts/`) clean, frontend
  typecheck 0 / eslint clean / **411 vitest**.

**Still OPEN and now clearly a SPEC decision, not a patch:** quant-verifier independently
reproduced the ₹0.04/share → 50,000-share / ₹1.19cr case and confirmed the code is
**spec-faithful** — SIGNAL_ENGINE.md §6 defines no minimum risk distance. So adding a
`paper_min_risk_pct` floor is a spec change (§6 + §8 regression + sign-off), not a bugfix.
Same for the `used = abs(existing_entry - stop_loss)` sizing bug.

### fix(eligibility): bug-hunter round on the 09-02 diff — 9 findings fixed (2026-09-02)

The agent review of the same day's eligibility/wrong-side work found real defects in it.
Fixed here; two pre-existing ones are recorded as OPEN below.

- **`scripts/regime_gate_shadow.py` still called `render_markdown` without `mode`** — a
  missed caller that would have died with a `TypeError` when run by hand, which is
  exactly how the regime-gate forward-evidence protocol says to run it. **Root cause of
  the miss: `make typecheck` only ran `mypy app/`, so `scripts/` was NEVER type-checked.**
  Now `mypy app/ scripts/` (241 files). The nine pre-existing untyped scripts are
  GRANDFATHERED in `pyproject.toml` with an explicit comment — visibly exempt at the
  state they were in, not silently excluded; fix and delete an entry when you touch one.
- **The `unassessed` tripwire was imaginary.** `preview()` received only 3 of 8 gate
  modes, so flipping e.g. the liquidity gate ACTIVE produced `blocked=False` on a row the
  order path 409s — while this CHANGELOG, `docs/PHASES.md` and the module docstring all
  claimed the drift "cannot silently return". `preview()` now takes a COMPLETE mode map
  (`_gate_modes()` builds it from settings in one place), `COVERED_GATES`/`UNCOVERED_GATES`
  are explicit, and there is a **parametrized test per uncovered gate** asserting an
  ACTIVE one lands in `unassessed`. The rule is now enforced, not aspirational.
- **Only 2 of 4 Buy surfaces were wired.** `DashboardPage` (the landing page, and the
  widest Buy surface) and `LiveSignalsPage` still fired orders that could only 409. All
  four now render through one shared `tradeBlock()` helper in `alertPresentation.ts`, so
  a fifth surface cannot silently miss the rule. +2 tests.
- **The diff's own new rejection wasn't previewed.** The `through_stop` 422 is the most
  likely failing click for a stale swing signal (the PNCINFRA archetype). Now previewed,
  with the sentence owned by `eligibility.through_stop_reason` so the preview and
  `place_paper_order` cannot word it differently (only the PRICE differs by construction:
  the preview knows the live LTP, the broker knows the post-slippage fill).
- **New `get_live_ltps()`** — one Redis MGET for a whole page. `get_live_ltp` opens and
  closes a connection per call, so it must never run in a row loop.
- **A NaN in `factor_scores` could 500 the whole list.** `Decimal('nan') != 0` is True, so
  a NaN smuggled in as a JSON *string* (JSONB accepts `"nan"`) reached `total > 0` and
  raised `InvalidOperation`. Root-cause guard in `factor_diversity` (non-finite ⇒ not a
  scoring factor ⇒ fails open) **plus** per-row containment in the list, because a read
  path whose whole philosophy is fail-open must degrade one row, not 200. 4 tests.
- **`entry_quality_shadow` hardcoded its own mode** — and it is the ONLY gate currently
  blocking money, so it was the most consequential instance of the bug the same commit
  fixed elsewhere. Now prints both live modes.
- **The mode banner now states WHEN the mode took effect** (`MODE_EFFECTIVE_FROM`).
  Without it, the first report generated after the 09-02 revert would have printed
  "SHADOW: nothing is suppressed" about the 88 resolved suppressed trades from the
  08-14 → 09-02 ACTIVE window — the same false statement, inverted, in the report that
  feeds the keep/revert decision.
- **The `place_paper_order` through-stop guard shipped untested**; now has a regression
  test asserting the 422, its message, and that no position is opened (canary: the old
  code sized 44 shares and returned 201).
- `staleTime: Infinity` on the alert signal query is no longer valid — the eligibility
  verdict is live state, not immutable plan data. Bounded to 60s.
- `list_active_signals` crossed the complexity gate, so the per-row work is extracted to
  `_enrich_page`.

**Confirmed sound by the review:** the monotonicity argument behind checking only the
FIRST spread-only fill (the impact refinement can only move a fill adversely, i.e. away
from a valid stop, never across it) was property-checked over **20,000 randomized books
including crossed books and zero top-of-book size — 0 violations**. Repeat-entry,
explicit-quantity and off-market paths verified intact; the test-fixture corrections
verified not to weaken what those tests assert.

### known(bug): two PRE-EXISTING sizing holes, unfixed — need a decision (2026-09-02)

Both change sizing behaviour on the money path, so neither is a watch-mode change.

- **HIGH — no minimum risk-distance floor, and no notional/affordability cap.** A signal
  one tick from its stop (LTP ₹237.30 vs SL ₹237.26 ⇒ ₹0.04/share risk) is accepted:
  reproduced as **201 CREATED, 50,000 shares, ₹1,18,65,000 notional on ₹1,00,000 capital**.
  The 09-02 wrong-side fix closed the *negative*-distance half of this hole and left the
  *near-zero* half, which produces a worse position than the bug that was fixed — and
  that row would enter the paper book, the R statistics and the 30-day go-live clock.
  This is the same tiny-SL pathology as the known `RR≈228` artifacts. Fix = a
  `paper_min_risk_pct` floor (reject, never clamp) + a hard affordability check.
- **LOW-MED — `used = abs(existing_entry - stop_loss)` invents risk that does not exist.**
  For an open long whose stop has trailed above its entry, a repeat entry is refused with
  "already at your per-trade risk budget" — false: that position has locked-in profit and
  zero remaining risk. Fix = a DIRECTIONAL `used` **clamped at 0** (the naive directional
  fix is also wrong: it would hand out negative risk as free budget), or read
  `position.current_sl` instead of the new signal's stop.

### feat(eligibility): the signals list now shows what you can actually TRADE (2026-09-02)

Closes the display/order-path gap found in the same-day audit: `place_order` runs seven
eligibility overlays and 409s on the first ACTIVE rejection, while `GET /signals/active`
and `GET /signals/{id}` ran **none** of them — so **41 of 204 listed signals** rendered a
Buy button that could only fail. That is where the 409 toasts in the 08-26/08-31
screenshots came from.

- **New `app/signals/eligibility.py`** — one source of truth for "what would an ACTIVE
  gate do to this signal". `preview()` is pure (modes + thresholds are arguments, the
  `regime_guard`/`entry_quality` convention), evaluates gates **in the order the order
  path does** so the reason shown is the one actually hit first, and passes the reason
  through **verbatim** — the list and the failed click cannot word it differently.
- **Covered:** regime (reads the persisted `Signal.regime`) · entry-quality diversity
  (needs only `factor_scores`) · entry-quality sl_atr (when an ATR is supplied).
  **Not covered** (needs live state a list can't cheaply read): circuit bands, liquidity,
  anti-chase, market regime, sector RS — all SHADOW today, so nothing they'd block is
  missed. An ACTIVE gate the preview cannot judge is named in `unassessed` rather than
  reported as "clear", so the drift cannot silently return.
- **Both endpoints stamp it** via one shared `_apply_eligibility`: the list passes
  `atr=None` (no per-row I/O); `GET /signals/{id}` loads a real ATR, because one signal
  affords one query — and that is the endpoint **AlertBell** reads, so the bell is fixed
  too rather than half of the problem.
- **New `SignalOut` fields:** `blocked`, `blocked_by` (stable gate slug), `block_reason`.
- **UI:** blocked rows are still **LISTED** — flagged, never silently hidden, so what the
  gates are doing stays visible. `OpportunitiesTable` badges the symbol (`⊘ blocked`),
  dims the row and disables the Buy button with the reason as its title/aria-label;
  `AlertBell` does the same on its per-alert Buy. Tokens only (`--color-loss`,
  `--color-loss-bg`), glyph + colour, no raw hex.
- Tests: 12 backend (`test_eligibility_preview.py`) incl. **the contract test** — a
  signal the list marks blocked gets a 409 from the order path with the *same string* —
  plus 4 `OpportunitiesTable` and 2 `AlertBell` cases (listed-but-flagged, disabled,
  never fires an order, unblocked still tradeable).

### fix(paper broker): reject a stop on the WRONG SIDE of the fill (2026-09-02)

- `size_for_fill` computed `per_share = abs(fill - stop_loss)` and `compute_quantity`
  raises only on exact equality, so **a BUY whose fill landed BELOW its own stop was
  sized and opened** instead of rejected — a position already through its stop at birth.
  **One such row exists in the dev DB.** It happens when a signal's entry has gone stale
  and price has travelled past the stop (e.g. a BUY planned at ₹238.21 with SL ₹237.26,
  clicked while the stock trades ₹191 — exactly the PNCINFRA row in the 08-31 screenshot).
- `side` is now a **required** keyword and the risk distance is **directional**
  (`fill - stop_loss` for a long, `stop_loss - fill` for a short). Wrong side ⇒ 0 ⇒ the
  caller rejects. **Reject, never clamp** (`.claude/rules/trading-domain.md`).
- `place_paper_order` also fails fast with an accurate message ("Price has moved through
  this signal's stop loss … the setup is void") instead of falling through to the generic
  "size rounds to 0". Checking the FIRST spread-only fill is sufficient: the impact
  refinement only moves a fill adversely, which is *away* from a valid stop.
- Tests: 4 regression cases with canaries (the old code returns 43 shares where the fixed
  code returns 0), incl. the SHORT mirror and BUY/SELL-vs-LONG/SHORT wording equivalence;
  6 existing call sites updated.
- **It reddened 3 pre-existing tests, and they were the ones that were wrong.**
  `test_index_ohlcv.py` and `test_liquidity.py` built signals at entry ₹500 / SL ₹480 on
  stocks whose seeded candles were ₹100 and ₹39. With no Redis LTP in tests the paper fill
  falls back to the newest candle close, so those fixtures described a LONG filling
  ₹380–₹441 BELOW its own stop — impossible trades that only passed because `abs()` hid
  them. Fixtures fixed (levels anchored to each file's seeded price series; the ₹39
  micro-cap archetype kept, since it is the SRTL case the liquidity gate targets) with a
  docstring on each fixture explaining the coupling. Same lesson as 2026-08-19's
  diversity-gate reddening: **a new order-path check surfaces old inconsistent fixtures —
  read the fixture before "fixing" the check.**

### fix(reports): shadow reports state their REAL mode instead of hardcoding "SHADOW" (2026-09-02)

- `regime_gate_shadow` and `circuit_gate_shadow` both hardcoded
  *"SHADOW: nothing is suppressed."* in their preamble. That sentence was **false for the
  19 days the regime gate ran active** (2026-08-14 → 2026-09-02): every reader of those
  reports — including the readings used to justify keeping the gate on — was told nothing
  was being suppressed while the order path was rejecting transitional entries outright.
- `render_markdown` now takes the live `mode` and renders it via one shared
  `eligibility.mode_banner`: active prints **"⚠ THE GATE IS ACTIVE — these signals ARE
  being suppressed on the order path right now"**, off prints "GATE OFF", shadow keeps the
  old sentence. 3 regression tests, incl. a canary that the old string must NOT appear in
  active mode.

### fix(docs): `conviction.ts` age-decay rationale corrected (2026-09-02)

- The age-decay term was documented as *"the single most evidence-backed term"*, citing
  the signal-age study. The sidecar says the opposite — `signal-age-<date>.md` headlines
  **"no stale-entry penalty visible yet"** (fresh ≤40%: 61 trades, −₹58 avg, 57% win;
  stale >80%: 13 trades, +₹13 avg, 46% win). Age predicts win rate mildly and ₹ not at all.
- The term is **kept** on its mechanical rationale (a signal near expiry has less runway
  to reach its target) and re-documented as such. The comment now records that the
  measured discriminator is **displacement from entry**, not age, and that displacement is
  handled per-row (live chase guidance) and on the order path (`chase_guard`) rather than
  folded into a score that must not re-jitter every tick. **No behaviour change** — the
  ranking weights are untouched.

### revert(regime gate): ACTIVE → SHADOW — refuted by its own forward evidence (2026-09-02)

Config-only, reversible, frozen engine untouched. Decision record:
`docs/analysis/regime-gate-revert-2026-09-02.md`.

- **The regime gate (skip transitional ADX 20–25) is reverted to `shadow`.** It went ACTIVE on
  2026-08-14 with a ✅ READY banner at **44** resolved suppressed trades. Its pre-registered revert
  condition — *"if the banner diverges (⏳ NOT READY), revert"* — fired on 2026-08-21 and stayed
  fired for **7 consecutive report days**.
- **The suppressed set is net-POSITIVE on the live tape:** +0.150, +0.130, +0.108, +0.134, +0.156,
  +0.088, +0.090 expR across 08-21 → 09-01, sign never once negative, `decided` grown 54 → **88**
  (4.4× the 20-trade bar).
- **All three §8 metrics that justified the flip inverted:** win rate 30% (kept) vs 36%
  (suppressed) · Sharpe −0.041 vs +0.044 · maxDD 34.5R vs 11.2R. Gating moves total-R from −2.0R
  (ungated) to **−10.0R** — the gate subtracts ~8R by removing a +7.9R cohort.
- **Verified enforcing, not phantom:** zero transitional-regime positions opened since 08-14
  (DB-checked; `.env` is hook-protected so runtime `settings.regime_gate_mode` was read instead).
  Evidence kept accruing post-flip because the signal-outcome recorder tracks committed signals
  against the tape whether or not they are traded.
- It was suppressing **37 of 204** active, non-shadow, ≥70%-confidence signals — a fifth of the
  visible inventory, and per this evidence the better-performing fifth.
- **Gate modes are now documented in `.env.example`** (they were undocumented); the flip itself is
  user-run because the file guard treats `.env` as user-managed.
- **No other gate moved:** diversity stays ACTIVE (evidence intact); chase (4/20), sl_atr (17/20),
  liquidity (19/20, already ruled don't-flip), circuit (0/20) and sector-RS (do-not-flip) stay shadow.
- **Standing lesson recorded:** a gate promoted on 44 observations was refuted by 88. No
  shadow→active flip without its pre-registered count met AND a multiple-testing-aware bar
  (Aronson / López de Prado, per the 2026-08-29 reading).

### research(entry): entry/eligibility audit — the leak is arithmetic, not stock picking (2026-09-02)

Read-only; no code on any path. Triggered by a desk question (*"signals were already dead in live
market while the signals are previous-day EOD created"*). Evidence: 99 resolved paper trades since
2026-07-19 + the live signal inventory.

- **Expectancy is −0.303R/trade** (24 closed since the 08-17 cut: 37.5% win, avg win +1.14R, avg
  loss −1.17R). Break-even needs 1.67R payoff at that win rate, or a 46.7% win rate at that payoff.
- **Payoff is capped by construction.** `compute_levels` pairs a STRUCTURAL stop (swing pivot /
  EMA20) with an ABSOLUTE-% target (swing +6%, positional +15%), so R:R is an accident of pivot
  placement: **94 of 295 swing signals have R:R < 1**, 213 < 2; every swing `tp_hit` realised < 1R.
  **6 of the 23 open positions have targets closer than their stops.** There is no minimum-R:R gate
  anywhere in the codebase.
- **Tight stops are the ₹ sink:** 14 trades with stops < 2% of price lost **₹25,951** at 29% win,
  worst −2.01R — fill cost is a fixed price amount, so it is a large fraction of a narrow stop
  (6 of 10 fills on 09-01 pinned the 50 bps impact cap ⇒ order ≈ 10× top-of-book).
- **Cohort split:** 44 trades carrying ≥1 mechanical defect (chased > 0.33R · stop < 2% · < 2
  scoring factors · R:R < 1) = **−₹19,649**; the 55 clean trades = **+₹5,256 at 55% win.**
- **Displacement, not age, is the discriminator:** at-entry fills (−0.02…+0.33R) = +₹9,830/55% win;
  chased 0.33–1R = −₹12,789/22%; > 1R = −₹8,820. The signal-age sidecar separately reports **no**
  stale-entry penalty — so `conviction.ts`'s documented age-decay rationale is not evidence-backed.
- **Overlays gate the ORDER path, not the DISPLAY path:** 41 of 204 listed signals render a Buy
  button that 409s (37 regime-blocked + 16 diversity-blocked, overlapping).
- **Portfolio heat is 45.3%** of ₹1L across 23 open positions (18 underwater, oldest 15 days), with
  **no heat cap and no max-position limit in code**. Elder's rule is 6%; Tharp's 6–10%.
- **Entry semantics:** the entry price is literally yesterday's close (`signal_service.py:236`) and
  the live entry zone is **symmetric ±0.5%**, so a BUY drifting DOWN into entry fires "Entered zone" —
  a failing setup reads as a triggering one.

### fix(ops): duplicate Celery beat detected (2026-09-02)

- An orphan `celery worker -B` (reparented to `systemd --user`) was running alongside the
  `make worker` tree, so **every scheduled task fired twice** — including the 60-second
  `position_monitor`, which can close positions on the live open book. CAS capture and nightly
  generation are idempotent (208 rows/session, `_has_active_signal` guard) so no data damage was
  found. Remedy: kill the orphan PID, keep the `make worker` tree.


### research(horizon): stop-width vs recovery study + full `docs/STATUS.html` rebuild (2026-08-25)

Answers a desk observation — *"some names failed for the day and then recovered over the next
sessions, like the swing/positional trades they were labelled as"*. Read-only; no code on any path.

- **`docs/analysis/horizon-recovery-2026-08-25.md`** — the study. **The observation is real:** 11 of
  the 16 stop-out losers with forward daily bars traded back through their own entry price, median
  **1 trading day**. But **"just hold" is far worse** (NDRAUTO −₹54,701, PNCINFRA −₹77,464) — the
  recovery is a transient bounce, not the thesis paying.
- **The split that explains it — stop width ÷ average daily range.** Below 1.0×: **8/8 recovered**,
  realised expectancy **−1.45R**. At/above 1.0×: 3/8 recovered, −1.17R. *A stop narrower than one
  average session's range is not a stop; ordinary noise reaches it, so the exit carries no
  information.* Tight stops also **overshoot the intended −1R** (−1.70R under 0.25×, −1.43R at
  0.5–1.0×) because the honest 6.8.2 fill cost is a roughly fixed price amount and therefore a bigger
  fraction of a narrow stop.
- **Method correction worth recording:** the first counterfactual held qty constant and "showed"
  wider stops were catastrophic (−₹59,834 → −₹122,500). That was a **sizing artifact** — risk-first
  sizing means a wider stop buys a smaller position. Redone in **R** over all 82 closed trades
  (winners included): planned SL −0.05R → 1.0×range +0.08R → **1.5×range +0.11R** → 2.0× +0.04R, with
  the entire gain inside the tight-stop group (−0.87R → −0.11R) and no cost to the wide group.
- **This independently reproduces the already-built `sl_atr` shadow gate at its exact `1.0 × ATR`
  threshold**, from a different yardstick (daily range) and unit (R), and agrees with the sidecar's
  own live numbers. **It still stays shadow** — readiness is 12/20 resolved and a flip needs sign-off.
- **Horizon half:** ≥1R on the entry day is **12%** for both classes, but **within their own horizon
  swing 36% / positional 54%** (median best excursion 0.85R / 1.29R), with +1R typically arriving on
  **d+3** for positionals. The daily report's "0/5 reached ≥1R" is an entry-day statistic being read
  as a verdict. Within-horizon race: positional 46% reach +1R first vs 42% stopped first; for stops
  inside the noise band the stop wins 43% of the time.
- **Actions:** make the report's ≥1R line horizon-aware, and surface `sl_atr_mult` (already stamped on
  every order) at entry. **REJECTED:** widening stops on the money path (retrospective, daily-bar,
  straddles a fill-model change — and *reject, don't clamp* says don't take the trade instead), and
  holding through stops.
- **`docs/STATUS.html` rebuilt** — current through Phase 6.8, MCE slices 1–5a, the anti-chase gate,
  CAS, and the above. 29 sections across four parts; new sections for the multi-factor rule (§6, with
  the real AYE single-factor signal worked through), the seven eligibility gates (§7, with a real
  seven-stamp order payload), the horizon finding (§18), reports/journal (§22) and the CAS watch
  (§23). **Four charts, pre-rendered as static SVG** — no charting library, no CDN, no runtime JS for
  the marks; each carries an `aria-label`, per-mark `<title>` hover and a table view. Categorical
  palette validated against this page's own light and dark surfaces (all six checks pass both modes);
  the profit/loss pair is knowingly CVD-weak (ΔE 4.2 deutan) so every P&L mark carries a ▲/▼ glyph and
  a signed label per the project's own UI law. Adds a **Full/Overview detail toggle** (hides code and
  file paths for presenting) and a **light/dark/auto theme toggle**, both persisted with guarded
  `localStorage`. Verified by rendering: fixed a shattered worked-example step list (anonymous grid
  items), a clipped chart annotation, an axis-label collision, and scatter label overlaps.

### feat(CAS slice 1): daily Closing-Auction-Session capture (2026-08-25)

Stage 1 of the CAS work — now that Stage 0 confirmed Kite `/quote` exposes the auction fields, this
records them daily, hands-off, across the F&O universe so the overnight-reversal study (Stage 2) can
accrue data. Research/observability only — the order path never reads it.

- **`cas_daily` table** (migration `c9d0e1f2a3b4`, reversible): one row per (stock, trade_date) —
  `pre_auction_price` (3:15, frozen on first capture), `reference_price`, `indicative_close`,
  `official_close` (converges to the clearing price), `total_imbalance_qty`, `polls`, `captured_at`.
- **`app/services/cas_capture.py`** — `parse_cas` (pulls `indicative_close_price` /
  `total_imbalance_qty` / `reference_limit_price` from a /quote row) + `capture_cas` (batched
  `kite.quote()` over the F&O universe → Postgres upsert; **freezes `pre_auction_price` on the first
  poll, converges the rest**; fail-open per batch).
- **`app/tasks/cas_tasks.py`** — a market-hours Celery beat task (`capture_cas_window`, every minute
  over the UTC superset) that **self-guards to 15:15–15:33 IST**, skips holidays / missing token,
  builds the `is_active`+`is_fno` universe, and calls `capture_cas`. Same pattern as the 6.8.3
  circuit-band task. `cas_capture_enabled` flag (default on; self-skips without a Kite token).

`test_cas_capture.py 8 tests` (parse edge cases + upsert pre-auction-freeze/converge/idempotency +
window-guard bounds + the imbalance regression below); ruff + mypy clean; migration applied to dev.
**bug-hunter BUGS-FOUND → HIGH fixed:** the upsert took the *latest* `total_imbalance_qty`, but a
matched auction's final poll reports **0** residual imbalance — so every row was storing 0, silently
destroying the Stage-2 predictor (verified by replaying the real 53 HDFCBANK polls: peak −245,638,
stored 0). Fixed to **keep the last NON-ZERO imbalance** (post-match 0 can't clobber it); everything
else verified sound (pre-auction freeze, polls increment, batch fail-open, session/commit, tz guard).
**Next: Stage 2 — study the overnight reversal (read-only, control for the oversold regime,
block-bootstrap) once days accrue.**

### research(regime study): 3-year market-regime backtest → regime playbook (2026-08-21)

Item 3 of the anti-chase/regime arc. A read-only study (`scripts/regime_study.py` + pure core
`app/services/regime_study.py` → `docs/analysis/regime-study-<date>.md`) over 575 classified sessions
(NIFTY50 + Bank/Fin Nifty + VIX, 2024-04 → 2026-08). Each day is put in a level×breadth quadrant
as-of that day (reusing the reviewed `summarize_regime` — no classifier look-ahead), then the forward
5/10/20-session return that followed is measured; plus below-200-DMA drawdown episodes, index/cap
dispersion, and a data-driven playbook.

- **HEADLINE — the two-window hypothesis is REFUTED at scale.** Over 3y, **below-200-DMA + WEAK
  breadth had the BEST forward-20 return (+1.33%), beating below + STRONG breadth (+0.21%)** — the
  opposite of what the n=4 autopsy suggested (textbook mean-reversion). **But a block-bootstrap
  (added this pass) shows the "edge" is NOT statistically established:** the fwd-20 windows overlap
  heavily (the naive +1.33% rests on ~2 drawdown episodes, one still open); the moving-block bootstrap
  puts **P(below-weak > below-strong) at only 83%** (short of significance) and the non-overlapping
  subsample is too small (just 2 independent below-strong points) and **flips sign**. So the
  breadth→forward-return signal is **noise on this sample — don't build on it.** **Implication: do NOT
  add a breadth term to MCE slice 4 in EITHER direction from this — the naive "prefer strong breadth"
  is unsupported, and the mean-reversion reading isn't significant either.** Vindicates
  measure-before-rule, twice over.
- **Critical caveat (in the report):** 3y = one bull cycle where every dip recovered, so the playbook
  is really "buy oversold dips" — a bull-market prior that would be dangerous in a structural bear
  (falling knife). We can't distinguish bull-vs-bear meta-regime from 3y. And we're **currently in the
  deepest/longest episode** (below 200-DMA since 2026-02-27, −11.3%, still below) — exactly the
  "bull dip or regime change?" question the study can't resolve.
- **Dispersion:** BankNifty/FinNifty amplify the mean-reversion (~2–2.8% vs NIFTY 1.33% from oversold).
- **FII/DII money-flow: DATA GAP** — the recorder holds only 36 sessions (since 2026-07-17); the
  flow-causation angle needs a backfill (follow-up). News/fundamental causation remains unmeasurable
  (no history) — the study measures price/breadth/VIX behaviour + recovery, not *why*.

`test_regime_study.py 6 tests` (forward-return alignment, quadrant classification, episode detection,
dispersion, + block-bootstrap direction/determinism); ruff + mypy clean. **quant-verifier
PASS-WITH-NOTES** — math verified correct (forward returns match the raw series to 1e-9, no look-ahead,
no quadrant inversion, dispersion date-aligned); fixes applied: honest fwd-k sample size in labels
(`fwd_n`), a loud warning if the multi-index date-axis drops NIFTY sessions, and a **`robustness()`
block-bootstrap + non-overlapping subsample** (the reviewer's TODO) that quantifies the fragility in
the report — verdict: **direction not statistically established.**

### research(CAS): NSE Closing-Auction-Session analysis + execution plan (2026-08-21)

`docs/CAS_CLOSING_AUCTION_ANALYSIS_2026-08-21.md` — a grounded analysis of NSE's new CAS (3:15–3:35 PM
auction close, F&O-underlying stocks, from 3 Aug 2026; F&O now closes 3:40) with a staged, paper-first,
evidence-first plan. Key: the institutional "predict-the-auction" game is closed to us (no imbalance
feed, no latency), but the literature's **overnight reversal of the closing-auction move** (~14% in
US/EU studies) fits our near-close→next-day style and is testable from data we can capture. Confound
flagged: the recent "recovery into the close" could be CAS OR the current oversold regime (the same
study above) — must be measured, not eyeballed. Plan: Stage 0 feed-feasibility spike → Stage 1 capture
(3:15 price, official close, CAS move, next-day return) → Stage 2 study the overnight reversal
(read-only) → Stage 3 fold as a feature only if a robust edge survives.
- **Feed decision (2026-08-22): Kite, not a commercial vendor.** Kite's WebSocket `MODE_FULL` struct
  has no imbalance field → CAS indicative-close/imbalance can only come from REST `/quote`; Global
  Datafeeds (true-TBT/FIX vendor) is overkill for our paper/low-frequency use.
- **`scripts/cas_probe.py`** (shipped) — a read-only Stage-0 probe: polls `kite_rest.quote()`, dumps raw
  JSON to `docs/analysis/cas-probe-<date>.jsonl`, flags any non-documented / `imbalance`-named key.
  **✅ CONFIRMED LIVE 2026-08-25:** Kite `/quote` exposes `indicative_close_price` + `total_imbalance_qty`
  (+ reference/limit bands) — no vendor needed. Learned the auction executes ~15:29 and `ohlc.close` is
  the prior day's close mid-session. Probe now **idles until 15:10 then captures only 15:10–15:33**
  (fixes the manual-timing failures). No order path. NEXT = Stage 1 (auto-capture Celery task + shadow
  table).

### feat(Live Signals): persistent, live-priced, ranked "Opportunities" list (2026-08-21)

Item 2 of the anti-chase/entry-quality UX arc. The Live Signals menu was an ephemeral tick-alert
feed (session-only, 100-capped, trigger-price snapshots — why alerts "vanished" and the price was
frozen). This adds a durable **Opportunities** list stacked above that feed (the feed + desktop
notifications stay, unchanged):

- NEW `features/alerts/OpportunitiesTable.tsx` — sourced from `GET /signals/active` (server-side
  **deduped** into `sources_count`, only `active` + non-expired = intrinsic **keep-until-resolved**),
  **live-priced** via `useLiveQuotes` → `PriceCell`, refetched every 60s. The anti-chase guardrail
  now recomputes against the **LIVE** price (unlike the frozen feed). Columns: rank (top-N ★), symbol
  (+dedup ×N), direction, live price, live entry-discipline, Plan (SL/TP/R:R/conf), Window
  (age · best-by · validity · stale/choppy), Trade. Loading (Skeleton) / empty / error+retry states.
- NEW `features/alerts/conviction.ts` — pure v1 conviction ranking: `confidence − age-decay − choppy
  + small multi-factor bonus`. **The age-decay term folds in item 1's evidence** (edge lives ≤40%
  elapsed, decays past it). Top-N starred; the rest ordered by recency → confidence → factor count
  (the user's stated rule). Not a probability — a heuristic; MCE slices become future terms.
- `alertPresentation.ts` — new pure `pctElapsed` helper.
- `LiveSignalsPage.tsx` — renders the Opportunities list above the existing feed; subtitle updated.

`conviction 5 + OpportunitiesTable 7 tests` (+ feed tests updated for the stacked query); full
frontend suite **401 passed**, tsc + eslint clean. **ui-reviewer PASS-WITH-NOTES** — token-clean,
theme-safe across all 6 themes, all loading/empty/error states + a11y covered; one LOW applied (loading
now uses a column-structured `SkeletonTable` per §4.8); the rest are pre-existing (raw `<button>` chips
in the feed/bell, page §9.1 scaffold) outside this diff. Note: the Dashboard already lists active signals
live — this is the focused, ranked, decision-first view in the menu the user works from; plumbing is
reused, the ranked/entry-context view is new.

### feat(make analysis): signal-age-at-entry + market-regime (level-vs-breadth) diagnostics (2026-08-21)

Two read-only daily-report sidecars, motivated by the two-window autopsy + the user's day-25
stale-entry observation. Never gate/size/trade.

- `app/services/signal_age_report.py` → `signal-age-<date>.md`: per resolved paper trade, how far
  into the signal's validity window we ENTERED (`%elapsed = (entry − commit)/(validity − commit)`),
  bucketed, with P&L. **Real-data smoke proves the stale-entry leak: the edge lives ≤40% elapsed
  (20–40% band +₹7,182 / 67% win over 15) and flips net-negative past 40% (40–60% −₹4,058, 60–80%
  −₹4,390, 80–100% −₹2,610).** Cohort keyed on the TRADE (`opened_at`), not signal commit.
- `app/services/market_regime_report.py` → `market-regime-<date>.md`: NIFTY vs its 200-DMA AND its
  20-DMA + breadth (% up-days over last 10) + VIX, flagging when the LEVEL and BREADTH disagree (the
  Window-A/B tape a level-only regime gate would miss). Pure `summarize_regime` + a DB wrapper.
- Both wired into `scripts/daily_analysis.py` (each in its own try/except — never blocks the report)
  with a stdout summary line.

`test_analysis_diagnostics.py 8 tests`; ruff + mypy clean. **quant-verifier PASS-WITH-NOTES** — one
**HIGH fixed**: signal_age wrongly filtered signals by `created_at >= OUTCOME_EPOCH` (a shadow-report
floor), silently dropping the exact archetype (an old signal traded stale); now keyed on `opened_at`,
with a regression test. Follow-up noted (not this diff): `benchmark._MARKET_CLOSES_SQL` lacks an
`is_complete` filter — benign (the index store writes completed EOD bars), verify the writer later.
Report stays at 20% age bands: a one-off finer-bin dig (10%/5%) showed n=78 is too small to trust
individual bins (only the 0–5%-elapsed "enter promptly" sub-signal looked robust, +₹9,232/90%/n=10) —
recheck ~2026-09-20 when n grows.

### feat(Live Signals): entry-context columns + default Entry-only + "best by" window (2026-08-21)

Extends the AlertBell entry-context surfacing (below) to the full-width **Live Signals** page and
adds a trade-window suggestion to both surfaces. Frontend-only.

- **Live Signals default filter → "Entry signals only"** (was "All alerts") — the actionable
  buy/sell triggers first; level crosses / volume bursts are opt-in.
- **Two new columns** on the Live Signals feed, mirroring the bell: **Plan** (`SL · TP · R:R ·
  conf%`, SL loss-coloured / TP profit-coloured) and **Window** (`signal <age> · best by <date>`
  + `Nd left`/`till HH:MM` + `⚠ stale`/`choppy`).
- **`bestByLabel`** (new shared pure helper) — "best by 25 Jul" / "best by 14:03", the end of the
  useful window (the 80%-elapsed mark, `NEAR_EXPIRY_FRACTION`), shown on both the bell and Live
  Signals. Directly targets the stale-entry leak (a positional signal traded on ~day 25 of 30 now
  reads `⚠ stale` and shows it is past best-by).

`AlertBell 38 + LiveSignalsPage 17 = 55 tests`, tsc + eslint clean. **ui-reviewer PASS-WITH-NOTES**
(token-clean, theme-safe across all 5 themes incl. daybreak warning contrast; redundant scroll
wrapper removed; the raw `{conf}%` note left as-is — `formatPct` would force noisy 2-dp on an
integer, and it matches `SignalDetailModal`/`DashboardPage`). Note: both surfaces are still the
ephemeral `useAlertStream` feed (session, 100-cap, trigger-price snapshots) — a persistent,
live-priced, deduped signals *list* (keep-until-resolved + top-5 ranking) is the proposed next step.

### feat(anti-chase gate): server-side eligibility overlay — block orders chasing past entry (2026-08-21)

The server-side backstop to the AlertBell guardrail, and the second half of the anti-chase work
(the first being the AlertBell surfacing below). Blocks an order when the LIVE price has run more
than `chase_max_r` × the trade's risk (`|entry − SL|` = 1R) PAST the signal's entry — the point
where the reward:risk you were shown is materially gone. Motivated by the chase_r-vs-outcome
measurement (2026-08-21, 39 resolved trades): chase_r ≤ 0.33 → **+₹275 avg / 62% win** over 37
trades; the only 2 past 0.33R (incl. SRTL) were **both losers, −₹3,074 avg**. Same overlay-lane /
shadow-first / fail-open pattern as the MCE gates; frozen engine untouched; mode `shadow`.

- `app/signals/chase_guard.py` — pure overlay: signed `chase_r` (R past entry, direction-aware),
  `blocked` when `chase_r > chase_max_r`. Fail-open (`assessable=False`) on no live price
  (off-market) or a zero-risk signal; a negative chase (filled *better* than entry) never blocks.
- Wired into `_apply_eligibility_overlays` as the 6th overlay (last — a pre-fill execution check,
  distinct from the upstream selection gates). Reads the Redis LTP via `get_live_ltp` (the same
  reference the broker fills near); no DB savepoint needed (that read fails to None on its own).
  Verdict stamped as `broker_payload["chase_gate"]` — distinct from the broker's post-fill
  `chase` telemetry.
- `app/services/chase_shadow.py` — forward-evidence sidecar → `chase-shadow-<date>.md` (chased /
  near-entry / no-data partition + per-entry table + flip-readiness banner), wired into
  `make analysis`. Reads the gate's own stamp when present, else the broker's fill-based `chase_r`
  as the historical proxy.
- `chase_gate_mode` (off/shadow/active, default shadow) + `chase_max_r` (0.33) in config.

`test_chase_gate.py 17 tests` (pure both-sides/negative/fail-open/boundary + order-path
off/shadow/active/fail-open + sidecar partition). ruff + mypy clean; order-path regression green
(156 passed). **quant-verifier PASS-WITH-NOTES** + **bug-hunter CLEAN** (no CRITICAL/HIGH/MEDIUM;
no look-ahead, no float-money, no connection leak, tuple-arity consistent, fail-open can't 500);
two LOW notes applied — chase_r stamped at 4dp so the sidecar's would-block recompute is faithful
at the ceiling, and `_chase_by_signal` now `ORDER BY placed_at` so a repeat/average-in entry's
chase is deterministic. Real-data smoke: chased −₹3,074 avg / 0% win vs near-entry +₹241 / 61%
(38 assessable resolved), flip-readiness NOT READY (2/20). Shadow→active flip needs forward
evidence + sign-off.

### feat(AlertBell): surface trade-plan context per entry alert — SL/TP/R:R, confidence, age, validity (2026-08-21)

Direct answer to a live pain point: the bell was traded blind — no way to tell at a glance whether you
were at the signal's entry or chasing, when it was generated, or how long it stays valid. AlertBell
already carried the anti-chase guardrail (ideal entry + don't-chase ceiling); this adds the rest of the
plan, all from the committed signal (no backend change, no live-data dependency):

- **Trade-plan line** — `SL · TP · R:R` (SL loss-coloured, TP profit-coloured, each with a text label)
  + `conf N%`.
- **Timing line** — `⏱ signal <age>` (time since the confluence engine committed it) + validity runway
  (`Nd left` for multi-day plans, `till HH:MM` IST for intraday), with `⚠ stale` when ≥80% of the
  validity window has elapsed and `choppy` when the daily regime is low-efficiency.
- `features/alerts/alertPresentation.ts` — pure helpers `tradePlan` (reward:risk), `signalAgeLabel`,
  `validityLabel`.
- `lib/format.ts` — reusable `formatRatio` (keeps `toFixed` out of feature code).

Frontend-only. `AlertBell 35 tests` (2 new component + 7 new pure), `tsc` + eslint clean.
**ui-reviewer PASS-WITH-NOTES** (token-clean, number-safe, a11y-correct; two optional notes applied —
SL/TP via `text-(--color-loss/profit)` classes, `min-w-0` overflow guard). Motivated by the
chase_r-vs-outcome measurement (chase_r ≤ 0.33 → +₹275 avg / 62% win over 37 trades; the only 2 trades
past 0.33R were both losers). Deferred: recomputing the chase % against the live LTP (needs a per-alert
quote subscription — a separate slice).

### feat(MCE slice 5a): liquidity junk gate + shadow sidecar (2026-08-21)

The junk filter's core, and the direct fix for the SRTL archetype (a BUY on a ₹39 micro-cap that blew
up because it was **un-exitable — illiquid**, not merely small). Slice 5 was split: 5a = liquidity
(buildable now from `ohlcv_1d`, no new data); 5b = the XBRL market_cap writer (greenfield scraper, its
own spike). Same overlay-lane / shadow-first / fail-open pattern; frozen engine untouched; mode `shadow`.

- `app/signals/liquidity_guard.py` — pure overlay: block when the **median** daily traded value
  (₹ = close × volume) over `liquidity_lookback` sessions is below `liquidity_min_traded_value_inr`
  (default ₹1 crore/day). Median (not mean) so one block-deal spike can't fake liquidity.
  **Side-independent** — illiquidity traps a long and a short alike.
- `app/services/liquidity.py::load_traded_values` — the close×volume series, anchored to
  `signal.created_at` (no look-ahead).
- Wired into `_apply_eligibility_overlays` behind a `begin_nested` savepoint (DB fault → fail open);
  the 5 verdict stamps were extracted to a `_overlay_stamps` helper (place_order simplified).
- `app/services/liquidity_shadow.py` — forward-evidence sidecar → `liquidity-shadow-<date>.md`
  (illiquid / liquid / no-data + per-entry table + flip banner), wired into `make analysis`.

`18 tests`, ruff/mypy clean, order-path regression green (188). **quant-verifier PASS-WITH-NOTES**
(median/floor/side-independence/look-ahead/fail-open all correct; INFO: make the floor per-class before
flipping active). **bug-hunter CLEAN** (three sequential savepoints in one order confirmed sound with
real Postgres errors; the stamp refactor behaviour-identical). Runs on real data now (no backfill).
**Forward-evidence finding:** over the 414-signal cohort the illiquid set is so far net-*positive*
(+₹119 avg, 14 resolved) and the liquid set net-*negative* (−₹71 avg, 55 resolved) — the live tape
does not yet support "illiquid = worse"; the flip-bar correctly holds NOT READY. A shadow→active flip
needs the R-track (§8-on-≥2y + sign-off).

### feat(MCE slice 4): market-regime (200-DMA + VIX) overlay + shadow sidecar + deep index backfill (2026-08-20)

The broadest top-down filter, above sector-RS: block a fresh long when the broad market (NIFTY 50) is
below its 200-DMA (a short the mirror). Same overlay-lane / shadow-first / fail-open pattern as the
prior slices; frozen confluence engine untouched. Chosen as slice 4 because it's the only remaining
MCE candidate both buildable AND §8-validatable now (3y of daily history).

- `app/signals/market_regime.py` — pure overlay: 200-DMA trend gate (symmetric long/short + buffer
  band); **India VIX is informational only** (reported/stamped, never gates — history too shallow to
  §8-validate).
- `app/services/benchmark.py::load_market_regime_context` — market-WIDE context (last N NIFTY 50
  closes + latest VIX), anchored to `signal.created_at` (no look-ahead).
- Wired into `_apply_eligibility_overlays` with a `begin_nested` savepoint so a DB fault fails open;
  `settings.market_regime_*` (mode default **shadow**, dma_period 200, buffer 0, vix_threshold 20).
- `app/services/market_regime_shadow.py` — forward-evidence sidecar → `market-regime-shadow-<date>.md`
  (would-block / with-regime / no-data partition + per-entry context table + flip banner), wired into
  `make analysis`; context memoized per as-of date.
- `scripts/backfill_indices.py` — deep index + VIX backfill from the NSE indices archive; ONE download
  per session feeds both feeds, per-day error isolation (resumable), idempotent. Needed because the
  200-DMA wants ~200 sessions and §8 ~2 years — the ≤21d EOD catch-up can't reach that depth.

`22 tests`, ruff/mypy clean, order-path regression green (191). **quant-verifier PASS-WITH-NOTES**
(look-ahead prevented, 200-DMA math + symmetry correct, VIX never gates, fail-open every branch; one
cosmetic INFO actioned). **bug-hunter**: the two-savepoint interplay (sector-RS + market-regime in one
request) confirmed sound; 1 MEDIUM (backfill lacked per-day error isolation) FIXED + regression test;
1 LOW (sidecar N+1) FIXED via per-date memoization. No money-path change (shadow never blocks). The
200-DMA is inert until `scripts/backfill_indices.py` seeds history; a shadow→active flip needs the
R-track (§8-on-≥2y + sign-off).
### docs(research): execution plan sequenced to cycle 2 — all 91 items bucketed (2026-09-03)

Turns the review's 91 queue items into a sequenced plan in `docs/quant-agent-findings.md`.
**Nothing is authorised** — watch mode holds to Fri 2026-09-04.

**The rule that orders it:** *anything that changes a recorded number must land BEFORE cycle 2's
clock starts.* We have already paid this once — paper P&L before and after 2026-08-17 is **not
comparable** because the spread-aware fill model landed mid-window and the 30-day clock reset.
Cycle 2 is 45–50 trading days on ₹1L; a costing, fill or eligibility change mid-cycle costs the
whole window.

**The corollary makes it tractable:** work that touches no recorded number — notifiers, tests,
rules, UI — can be built **while the clock runs**, and that is most of the backlog. So the choice
was never "build everything first" vs "start accruing": it is **freeze the number-changing
surface, start the clock, build the rest underneath it.**

Buckets, with all 91 items assigned and none left unplaced (verified programmatically):

- **A — freeze the numbers (~7 d):** A38 (the point-in-time `Restrictions` interface, subsuming
  A30/A31) · A21 marks · A37+T3 participation cap · A29 DP charge · A23 effective-dated fees ·
  **A26** (hot-set capacity — it changes *which signals exist*) · A25 tick-mode assert · H6.
- **B — the instruments that read the cycle (~5 d):** H8 · H1 · H12 · H2 · H11 · T11 · H4 (absorbing
  A8) · U4 · H3 · T7 · A24.
- **P7 — the long pole (weeks):** A33 + A42 + A35 designed **together**, then A32 · A22 · A16 ·
  T2 · A34. Read vnpy's 145-line bus, PaperTrade-India's `orders/` and repo 4's CLAUDE.md first.
- **MCE — blocked on a decision, not code:** 5b needs a **vendor chosen**; T1's filing-anchored PIT
  test ships *with* it; MCE 6 = A18.
- **C — during accrual (~60 items):** the whole notifier stack (A11/A40/A27/A28/A3/A36/H7/A9/A10),
  every test item, all W rules, and the full UI queue led by U1 and the U10+U15+U17 trio.
- **PARKED:** H10 (an overfitting machine until H8 exists), H9, A19, A20, A6, W6.

**Honest sizing: three to four months to the start of cycle 2**, dominated by P7 and the MCE
vendor decision — consistent with the standing "live is 4–6 months out". Buckets A+B are ~2 weeks
of that. The discipline recorded: *every week building is a week not accruing, and cycle 2 needs
its 45–50 days regardless.*


### docs(research): repos 23–29 the .NET batch, and a closing summary at thirty repos (2026-09-03)

Seven C#/.NET repos, none sharing our stack, so lesson 17's filter applies: shared *stack* or
shared *discipline*, not shared subject. **One of seven earns the reading; two are rejected on
licence before any technical assessment.**

**⚠ StockSharp and StockSharp/AlgoTrading — the strongest licence rejection in the log.** A custom
notice stating the repo *"is not licensed under a general-purpose open source license"*, that
**"viewing, downloading, copying, building, modifying, using, distributing, or otherwise
accessing"** requires their EULA, and — decisively — that **"StockSharp may update its license terms
… Users are responsible for monitoring … and complying with the then-current terms."** The terms are
**unilaterally mutable with a monitoring duty on the user**, and even *viewing* is nominally gated,
so the "read for architecture, adopt nothing" posture used with vnpy/zipline/qlib is not clearly
available. StockSharp is essentially "vnpy for .NET" and **vnpy is MIT**, so the risk buys nothing.

**⭐ facioquo/stock-indicators-dotnet is the one worth reading** — Apache 2.0, active, 518 test
files, and **80 committed `.xlsx` hand-calculated oracles** (`Rsi.Calc.xlsx` beside
`RsiSeriesTests.cs`). Its tests pin total count, **non-null count**, the **exact warmup boundary**
(`sut[13]` null, `sut[14] = 62.0541`) and values across the series, plus property invariants — and
every indicator is tested through **batch / incremental / streaming**, which must agree. Two
findings about *our* code:

- **T13** — we already have that agreement test, on **two** indicators (`sma.rs`, `ema.rs`).
  **RSI/ADX/ATR do not have it**, and recursive smoothing makes the Wilder family both the most
  likely to diverge and the loosest in our parity tolerance (1e-6 vs 1e-9).
- **T14** — our oracle chain is **Rust ← Python ← pandas-ta** with **no external anchor**. If
  pandas-ta carried a convention bug — exactly the QuantStats failure of §22 — our fixtures would
  encode it and every parity test would pass forever, in green. ~20 hand-computed Wilder values,
  once, and the chain stops being self-referential. **Fourth independent arrival at "anchor the
  test to something the code did not produce"** (with T1, T11, H8).

**One contrast** from `mccaffers/backtesting-engine` (MIT, no longer actively developed): its
stated purpose is *horizontally scaling strategy permutations on AWS* for *"more comprehensive
strategy exploration"* — **which is precisely what the deflated-Sharpe bar defends against.** Every
permutation is a trial; `E[max SR]` grows with the trial count. Compute makes the overfitting
problem worse, not better.

The remaining four (Financial-Formulas — 12 files, superseded by FinanceToolkit; TradingStrategies;
quant-trading-toolkit) are too small or too covered to repay the reading, and are recorded as such.

**Added a closing "Where this leaves us" section** at the end of the first review series: the five
items to do first (**A11+A40**, **H8**, **A21**, **H2+U2**, **A25**), the six findings that were
about *our own code* rather than theirs, the three sentences worth remembering, and the calibration
from §20's 4,843 replications.


### docs(research): repo 22 FinanceToolkit — the counter-example to QuantStats, and T12 turned on ourselves (2026-09-03)

[JerBouma/FinanceToolkit](https://github.com/JerBouma/FinanceToolkit), **MIT**, ~131k LOC,
**1,486 tests**, 95 fundamental ratio formulas plus risk/performance/technicals/options modules.
Reviewed immediately after QuantStats on purpose: repo 21 failed a formula audit, and this
library's whole pitch is that its formulas are inspectable.

**★ It passes the exact audit QuantStats failed.** Where QuantStats silently fed pandas' *excess*
kurtosis into a formula expecting *Pearson*, FinanceToolkit makes the convention a named,
documented, defaulted parameter — `get_kurtosis(..., fisher: bool = True)` returning
`returns.kurtosis() if fisher else returns.kurtosis() + 3`, with the docstring spelling out both
definitions. **That is the difference between a library you can audit and one you must audit.** Its
formulas also carry real citations: the Cornish-Fisher VaR docstring names Zimmerman (Part 1, pp.
130-131), Gilli/Maringer/Schumann, Hull, and a thesis section — four sources for one quantile
adjustment, and the direct opposite of abu's underived `0.668` / `0.91`.

**It does NOT unblock MCE 5b, and saying otherwise would be manufacturing relevance.** Its 95
ratios compute *from statements you supply*, sourced from **FinancialModelingPrep** and yfinance,
with **no India/NSE support anywhere**. Our recorded blocker is the data half — *"`market_cap` has
no writer → nothing fundamental unlocks until a source is chosen"* — so it solves the half we do
not have a problem with.

**What it does contribute to 5b is a warning, in the author's own founding words:** *"I repeatedly
observed significant fluctuations in the same financial metric among different sources… the
reported financial statements often didn't line up."* **That is the argument for why 5b's source
decision is the whole problem rather than a detail**: whichever vendor we pick becomes *part of the
definition* of every ratio, a market-cap threshold calibrated on one vendor is not portable to
another, and T1's PIT test must be anchored to *that vendor's* published figures.

**T12 — and applied to ourselves, which is where it stings.** Only two files in our trading layer
cite a derivation: `atr.py` (Wilder) and `deflated_sharpe.py` (Bailey & López de Prado, plus the
`# Pearson (normal = 3.0), not excess` pin that saved us in §22). The frozen engine is covered by
`docs/SIGNAL_ENGINE.md`, which is *better* than inline citations — versioned and regression-gated.
**But the trading layer has no spec, and it is exactly where our churn is**: `profit_lock`'s ladder
(+₹2k breakeven, seal peak−₹1k above ₹3k) and the gate thresholds are fitted constants nobody can
re-derive — the same criticism levelled at abu, now applied to us. T12 asks each to record a
citation, a fitting procedure with its sample, **or an explicit "chosen by judgement on <date>,
never validated"** — the third option being the important one, because it makes unvalidated knobs
visible to the review calendar instead of indistinguishable from derived ones.

Synthesis extended to twenty-four repos with lesson 22: **a constant with no recorded origin can
only be defended by whoever remembers choosing it.**


### docs(research): repo 21 QuantStats — cross-checked our PSR, found two bugs in theirs (2026-09-03)

[ranaroussi/quantstats](https://github.com/ranaroussi/quantstats), **Apache 2.0**, ~12.3k LOC,
**79 metric functions** — the canonical tearsheet library, by the author of `yfinance`.

**★★ This one validated our own measurement stack.** We built PSR from Bailey & López de Prado on
2026-09-03; QuantStats implements the same formula, which made an independent check possible.
Algebraically the two agree exactly — collecting their `SR²` terms,
`0.5·SR² + ((γ₄−3)/4)·SR² = ((γ₄−1)/4)·SR²`, which is ours.

**But the agreement holds only if both feed the same kurtosis convention, and theirs does not.**
Their `kurtosis()` returns `returns.kurtosis()` — pandas, i.e. **excess** kurtosis (normal = 0) —
into a formula whose `(kurt − 3)/4` term expects **Pearson** (normal = 3). Demonstrated on 100k
normal draws: the `SR²` coefficient evaluates to **−0.2422** where it should be **+0.5078**. That
makes `sigma_sr` too small, the z too large, and **PSR systematically overstated — the library
reports more confidence than the data supports.** A second, separate defect in the same function:
`if annualize: return psr * (252 ** 0.5)` — **multiplying a probability by ≈15.87**, a unit error
hiding behind an optional flag.

**Ours is correct, with the trap explicitly pinned** — `kurtosis: float  # Pearson (normal = 3.0),
not excess`. That comment is the entire difference. **This is the strongest validation our
measurement code has received in this review: checked against the best-known reference in the
field, and the reference is the one that is wrong.**

**T11 — pin PSR/DSR against independently derived values in a regression test**, including a
normal-series case where the `SR²` coefficient must be `+0.5`, so the convention can never silently
flip. Same discipline as T1: anchor the test to a value you can derive independently.

**The metric battery is a checklist of what we do not compute**: `information_ratio` and `greeks`
(alpha/beta) — **a working implementation of H12**; `smart_sharpe` / `autocorr_penalty` — the
*parametric* cousin of **H1**'s block bootstrap, worth having alongside rather than instead;
`tail_ratio` / `outlier_win_ratio` / `remove_outliers` — named formalisations of the trimming check
we improvised when market-regime's cohort showed a *trimmed mean of +₹200 against a −₹302 raw
mean*; `risk_of_ruin`, which we do not compute and which matters against ₹1L and a negative
expectancy.

**Verdict: reference, not dependency.** Two structural reasons — the battery operates on a **daily
returns Series** while our evidence unit is the **per-trade R-multiple** (exactly why MinTRL exists
rather than a years formula), and it is float/pandas throughout where we are `Decimal` end to end.

Synthesis extended to twenty-three repos with lesson 21: **check every statistical instrument
against an independent implementation — the most-used implementation in a field is not a reference,
it is another sample.**


### docs(research): repo 20 vectorbt — prior rejection confirmed, with a decisive licence reason (2026-09-03)

[polakowo/vectorbt](https://github.com/polakowo/vectorbt), ~62.7k LOC. **A re-review of a decision
already made** — `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` concluded *adopt none as dependencies*
and singled out VectorBT as one that *"would REGRESS invariants"*. That stands, and this review
supplies **two sharper reasons, one of them decisive and absent from the original note.**

**★ The licence is not open source.** The README badges "Fair Code"; the licence is **Apache 2.0
with the Commons Clause**, which withholds the right to *"provide to third parties, for a fee or
other consideration (including … hosting or consulting/support services), a product or service
whose value derives, entirely or substantially, from the functionality of the Software."* Against
our own CLAUDE.md opening line — *"personal use first, **possible future productization**"* —
personal use today is fine and **any future productization becomes a live legal problem**. There is
a paid `vectorbt.pro`, which is why the free edition carries the restriction. **This is worse than
a plainly incompatible licence, because the trap springs only at commercialisation** — when the
dependency is most embedded and least removable. Recorded so a future session weighing it on
technical merit hits this first.

**The technical regression, now named.** It is **constraint #3** (*compute on candle N, valid from
N+1; fill at N+1 open*), and the regression is in **kind, not degree**. vectorbt's own docs are
candid: *"forward, for example, with `signals.vbt.fshift(1)`"* and *"otherwise you may expose
yourself to a look-ahead bias."* Signals are computed **vectorised over the whole array** and the
default fill is the same bar, so **a correct backtest depends on the caller remembering the
shift.** Our engine cannot make that mistake; adopting a framework where correctness is a
convention is a regression however fast it runs.

**★ This closes the log's look-ahead thread.** §21.3 now lays out the full spectrum across
twenty-two repos, and position on it predicted the outcome every time: Zipline (*not expressible*)
→ qlib and repo 9 (prevented, fails closed) → **vectorbt (the default unless you remember)** →
QuantHarness (a commented-out holdout) → QuantAgents-NSE (it simply happened, producing a +0.5pp
"edge" that isn't real). **Repo 5 is what the vectorbt row produces downstream**, and its author
almost certainly never saw it as a choice. That is the strongest available argument for **A38**
(accessors bound to an "as-of" time) and **T1** (a PIT test anchored to a real filing date): not
that convention is unreliable in the abstract, but that we have now watched it fail in this exact
way, twice, with a third project documenting the trap it declines to remove.

**No queue items.** The value is a rejection that now survives someone changing their mind about
the technical merits, plus the spectrum.


### docs(research): repo 19 awesome-systematic-trading — a replication record over 4,843 papers (2026-09-03)

[paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading),
**no LICENSE**, updated the day of review: 299 library rows, 61 showcased strategies, 55 books,
blogs and courses.

**Method note, stated honestly:** the brief was "dig deeply into each and every one", and I did
**not** individually review 299 libraries or 4,843 papers — claiming otherwise would be false.
Instead: inventoried the list programmatically, computed the statistics it does not compute,
cross-checked it against the eighteen repos already reviewed and against our own open gaps, and
kept only what changes something.

**★★ The replication record above the list is the most valuable thing in this whole review.** They
coded and ran **4,843 published papers over their full history**: median Sharpe **0.37**; **only
48% clear t > 1.96** (*"half the published record cannot be distinguished from zero on its own
sample"*); median beta **+0.17** to the S&P, and **stripping it takes the median information ratio
to 0.21** — roughly halving the apparent edge; and **no measurable post-publication decay** once
the market period is controlled for. This is population-level evidence on the entire literature,
produced by running it.

**H11 — the sample-size reality check.** `years ≈ (1.96/Sharpe)²` is our **MinTRL** arrived at
independently: a 0.37 Sharpe needs **~28 years** to separate from zero. Units do not transfer
(theirs is annualised-on-daily, ours is per-trade — which is why we built MinTRL), **but the shape
does: required sample grows with the inverse square of the edge.** Our gates are judged on 33–72
trades. We already compute MinTRL; the missing move is rendering it as the **headline** beside
every readiness banner so `n=44` is never read without `needs ≈N`.

**H12 — we compute no beta and no information ratio anywhere.** Cohorts are judged on raw
expectancy and per-trade Sharpe, so a would-block cohort that is long-biased in a rising market
looks like skill. This is H2/U2 generalised from portfolio to *cohort* level, and the inputs exist
(`index_ohlcv_1d` backfilled, `benchmark.py` for alignment). Third robustness axis beside **H1**
(is it stable?) and **H8** (does the bar reject noise?): **is it just the market?**

**A selection effect found in its own presentation.** Parsing the 61 showcased strategies gives a
median Sharpe of **1.06** (equities 1.51, derivatives 0.53) against the population's **0.37** — the
list shows roughly its best 1.3%, and a skimming reader anchors 3× high. **This is disclosed** in
plain language above the tables, which is more honesty than any other list here — but it is the
subtlest instance of this log's theme: the selection effect moved into the presentation layer,
where no code is wrong and the reader is still mis-calibrated. **Our exact equivalent is a
readiness banner showing the gates we are watching, a selected sample of the gates we have tried** —
which is why U4 exists.

Also noted: **27 of 299 library rows carry dated dormancy flags** inline (`dormant since 2024-02`),
which independently corroborates this review's zipline call; books largely overlap our e-book
review; and the blogs skew to **engineering blogs of real firms** (Jane Street, HRT, Two Sigma, Man
Group) rather than strategy blogs — by lesson 8, the more credible reading.

Synthesis extended to twenty-one repos with lessons 19 and 20. Calibration recorded plainly: **a
−0.303R book measured honestly is an early-stage position on this distribution, not an anomalous
one — and a 2–3%/day target is not on the distribution at all.**


### docs(research): repo 18 QUANTAXIS — QIFI's account model exposes our missing frozen-capital concept (2026-09-03)

[yutiansut/QUANTAXIS](https://github.com/yutiansut/QUANTAXIS), **MIT**, ~66.3k LOC, actively
maintained — a long-running Chinese full-stack quant framework. **No performance claim, the ninth
repo to decline.**

Most of its layers duplicate ground this log already covered in better implementations
(`QAEngine`/`QAPubSub` vs vnpy's event bus, `QAFetch` vs AKShare, `QAFactor`/`QAIndicator` vs qlib),
and those are not re-derived. **One module is distinctive and produces one queue item.**

**QIFI** is an account-state interoperability protocol, published as **`qifi.md` (spec) +
`qifi.sql` (DDL) + one implementation** — the contract as an artifact rather than an
implementation detail, which is the third independent appearance of that instinct here (after
AKShare's `interfaces.json` and qlib's PIT field syntax). Its account model separates four things
our code treats as roughly one: `pre_balance` (yesterday's close), `static_balance` (today's
settlement baseline), `balance` (static + floating P&L) and `money` (**available** cash = balance −
frozen − margin), with an explicit daily settlement roll. That vocabulary reinforces a rule repo 4
already taught us — *the circuit-breaker baseline is always `last_equity`, not last night's DB
snapshot* — expressed as a schema rather than a convention. Our breaker's IST calendar-day baseline
is sound, so no defect there; the value is the naming.

**★ A42 — the actionable finding: we have no concept of frozen capital.** Verified — every
`frozen` in our codebase is `@dataclass(frozen=True)`. Cash committed to a *pending, unfilled*
order is not reserved anywhere. Harmless today because paper fills are immediate, so no order is
ever outstanding — **but Phase 7 removes that property**, and two orders can then be sized against
the same cash. This is exactly the family of bug repo 4 documented from production: *a filter
pre-deducted **phantom cash**, letting BUYs quietly borrow margin (2026-04-19)*. Cheap to design
now while the account model is small and paper-only; expensive to retrofit once orders can sit
unfilled. Pairs with **A33** — the frozen amount is derivable from the active-order set, so both
belong in one design pass.

Lesson 8 promoted from observation to prior: across twenty repos, **nine decline to publish any
performance number, and they are without exception the ones whose code was worth reading.**


### docs(research): repo 17 QuantDinger — closest analogue to our platform; its MCP model and worker-liveness alert (2026-09-03)

[OpenByteInc/QuantDinger](https://github.com/OpenByteInc/QuantDinger), **Apache 2.0**, ~177.6k LOC,
803 files, **committed the day of review** — a commercially backed open-source "AI Trading OS".
**The closest product-shaped analogue to our platform in the log**, on nearly our stack (Python
3.12 / PostgreSQL / Redis / Docker Compose) with the same end-to-end scope. **No performance
claim** — the eighth repo to decline.

**★ W6 — its MCP server is the best "expose your platform to an agent" model here**, and directly
relevant because we already drive `make analysis` through skills. Seven decisions worth copying:
the MCP server is a **thin wrapper over a dedicated versioned `/api/agent/v1`** — *the agent gets
an API, never the internals*; **R vs R/W scopes tabulated per tool group**; trading tools
separately **safety-gated**; **two distinct tokens** with the docs stating the inbound MCP client
token *"must not be the Agent Gateway token"*; transport that **fails closed** (non-loopback
requires a token, authenticated non-loopback requires HTTPS) with two separately-named escape
hatches and *"never use either on a directly reachable public listener"*; explicit agent-specific
credential hygiene (*"never place an agent token in prompts, logs, screenshots…"*, responses redact
credentials); and **bounds on every long-running job** exposed to an agent — the fix for exactly
the unbounded-stream hang found in repo 8. Recorded, not queued: we have no such need today, but
the design should not be reinvented badly under pressure.

**A40 — export a worker-liveness metric and alert on it.** Their
`quantdinger_workers_healthy{role=~"trading|scheduler|celery"} < 1` for 2 minutes is precisely the
alarm that would catch **two of our standing manual rituals**: CAS capture (`make worker` up
15:15–15:33 IST, **a missed window cannot be back-filled**, protocol is "check the row count each
morning") and the provisional-health watch (no scheduler at all). Both are worker-liveness problems
dressed as human rituals. Strengthens A11 rather than replacing it.

**A41 (low priority) — split Redis by durability.** They run separate `redis-cache` and
`redis-jobs` instances. Our rule *"TTL-less keys are treated as broker-critical and never evicted"*
exists **because** volatile cache and durable data share one eviction policy; two instances remove
the conflict instead of documenting around it. Worth revisiting when Phase 7 adds a durable repair
queue.

Also recorded: a **multi-timeframe review lens** from their strategy guidance — use the
**completed** higher timeframe, never conflate a persistent **state** ("is bullish") with an
**event** ("just crossed"), and keep low-timeframe order conditions **idempotent** so a persistent
higher-timeframe state cannot cause repeated scale-ins. Useful for auditing our own overlays, since
both of our reverted gates failed on *what the partition actually meant*.

Synthesis extended to nineteen repos with lesson 18: **alerting splits cleanly into platform and
domain, and almost nobody has both.** Every one of their alerts is infrastructural and none is
about the market; we are the mirror image. A green Prometheus board says nothing about a feed
returning yesterday's prices, and a readiness banner says nothing about a worker that never
started.


### docs(research): repo 16 turbovec — domain rejected, but its supply-chain gate found the log's #1 defect (2026-09-03)

[RyanCodrai/turbovec](https://github.com/RyanCodrai/turbovec), MIT, ~39.6k LOC Rust + Python —
**not a trading repo**: a quantized vector-search index (Google Research's TurboQuant) for RAG.
User asked whether it was useful "by any chance".

**Domain answer: no, and recorded as considered-and-rejected without stretching for a use.** We
have no embedding corpus, no RAG and no similarity search. The only conceivable hook is "find
similar historical trades" — abu's Edge referee from §16 — where the bottleneck is **statistical
validity, not search speed**; at n≈99 trades you use numpy pairwise distances, as abu does. An ANN
index built to fit 10M vectors in 4 GB has nothing to offer a hundred rows.

**★ But it shares our Rust + PyO3 wheel shape, and that carried one finding across.** Its
`deny.toml` (cargo-deny, enforced by a `supply-chain.yml` workflow) documents, in a comment, the
most instructive instance yet of this log's #1 defect:

> *the workflow advertises a "yanked crates" gate, but cargo-deny **defaults `yanked` to Warn** and
> `cargo deny check` only exits non-zero on Deny-level findings — so **a yanked dependency produced
> a warning and a green run (#491)**.*

**A guard that could not fail, caught in the wild, issue number cited — and nothing in the code was
wrong: the *configuration default* was.** Lesson 2 extended accordingly: name the input that makes
a guard fail **and confirm the tool would actually fail on it**, because a gate can be disarmed by
a default you never chose. Their `ignore` list also carries the T8 ratchet discipline informally —
every entry names the advisory, the reason, the PR that accepted it and the revisit condition.

**A39 — we have no supply-chain gate on `engine/` at all.** Our Rust gate is `fmt` + `clippy -D
warnings` + `test`: no advisory scan, no licence audit. We ship a compiled wheel (`tradecore`)
running options math **on the money path** from a dependency graph nobody audits. ~2 hours, and
this repo hands us the two settings that make it real.

Synthesis extended to eighteen repos with lesson 17: **a repo outside our domain can still be worth
reviewing — the filter is shared *stack* or shared *discipline*, not shared subject.** The
corollary matters more: when a repo shares neither, **"no" is the correct and complete answer**.


### docs(research): repo 15 abu — meta-labeling in 2017, and why it is dangerous (2026-09-03)

[bbfamily/abu](https://github.com/bbfamily/abu), **GPL-3.0**, ~56k LOC — a Chinese quant framework
written as a book companion. **Licence settles adoption before quality enters the discussion**:
every other repo here is MIT or Apache, and copyleft would impose GPL obligations on our codebase.
Read-only review. It makes **no performance claim** — the seventh repo to decline.

**★ Its `UmpBu` "referees" (裁判) are meta-labeling, implemented years before the term was
standard, and structurally *our overlay pattern*.** A two-tier learned veto over a primary signal:
a **Main referee** clusters historical trades, finds the clusters with the highest failure
probability, vetoes new trades falling into them, **and saves candlestick snapshots of the worst
cluster so a human can see what the losing pattern looks like**; an **Edge referee** does
similarity/k-NN voting by surviving historical neighbours. Both across dimensions — trend angle,
gaps, price, volatility — and separately for buy and sell.

**Why it matters to us, and why it is queued as research not work.** Our overlays are all
**hypothesis-driven** — we posit that transitional ADX is bad, R:R<1 is bad, single-factor is bad,
then test the posit — and **two of the three we tested empirically were reverted, because the
partition turned out to be a proxy for something else** (market-regime → side; R:R<1 → wide stop).
abu inverts the direction: don't guess the partition, cluster the actual losers and let the
clusters define the veto. That attacks our exact failure mode.

**But it is unmistakably an overfitting machine.** Clustering your own losing trades and vetoing
those clusters always looks good in-sample; with 99 trades and a −0.303R book it would produce a
beautiful backtest that means nothing. Filed as **H10**, explicitly gated behind the bar we
already built — DSR with an honest trial count (every cluster configuration is a trial), MinTRL,
**and H8's noise negative control**, because a method this prone to fitting is precisely the case
the negative control exists to catch. Its magic constants (`0.668`, `0.91`, `100`) arrive with no
derivation, and each would become another hyperparameter multiplying the trial count.

**U20 — one idea we can take immediately.** abu renders the highest-failure cluster's trades as
charts. Our shadow sidecars report *"this gate would block these 44 trades"* as expectancy, win
rate and DSR — and **nobody has ever looked at those trades as a set of charts.** The regime gate
was refuted numerically; a contact sheet of the suppressed entries might have surfaced the
"proxy for side" problem visually and sooner. Statistics say *whether*; charts say *what*.

Also noted: three independent sources have now pointed at meta-labeling (our e-book review, repo
12's `mlfinlab` entry, this working implementation), so it earns a place on the post-watch-mode
research queue rather than continuing to surface accidentally.

Synthesis extended to seventeen repos with lesson 16: **licence is a first-class review criterion
and decides before merit** — one GPL-3, one LGPL, and **four repos with no LICENSE file at all**
(which is *more* restrictive than GPL, since no licence means no grant of rights). **vnpy being MIT
is the single most consequential licence fact in this document**, since it makes the repo we would
most plausibly borrow from for Phase 7 legally borrowable where NautilusTrader is not.


### docs(research): repo 14 Zipline — look-ahead made inexpressible; A38 supersedes A30 (2026-09-03)

[quantopian/zipline](https://github.com/quantopian/zipline), Apache 2.0, ~65k LOC, **archived
2020-10-14** (successor: `zipline-reloaded`). The ancestor of the modern Python backtesting
lineage — it spawned `trading_calendars` → `exchange_calendars`, `alphalens`, `pyfolio`,
`empyrical`. Read for architecture, not code.

**★ Its crown jewel: look-ahead is not forbidden, it is *not expressible*.** A strategy never
receives data — it receives a `BarData` constructed with a `simulation_dt_func`, and every
accessor (`current`, `history`, `can_trade`) resolves through the simulation clock and queries the
data portal *as of that instant*. **There is no API for a future bar.** Across sixteen repos I
found look-ahead four ways — a commented-out holdout, same-bar execution, a scaler fit over the
test window — each *a mistake someone could make*. This is the only one where the mistake has no
syntax. Its `before_trading_start` also sets "current" to the *previous* market minute, making it
the **second independent world-class implementation to conclude the current bar depends on the
session phase** (repo 9's resolver was the first).

**★★ A38 — a composable, point-in-time `Restrictions` interface. This supersedes A30.**
`asset_restrictions.py` ships `Restrictions` (ABC) with `Static`, **`Historical`** (time-varying),
`SecurityList` and **`_UnionRestrictions`** (composes sources), wired into `BarData` so
`can_trade()` — the question the *strategy* asks — already knows. I had recommended "enforce
circuit bands in the backtest"; that is the right goal and the wrong shape. The right shape is
**one composable interface consulted by the backtest, order path and display path**, with each of
our rules as a source (T2T/-BE, circuit-band proximity, liquidity, market hours /
`allow_offmarket_entry`, gate modes). `HistoricalRestrictions` answers *"was this restricted on
that date"* — the only correct backtest question and one ours cannot ask at all; `_UnionRestrictions`
is the structural fix for fragmentation that already cost us **41/204 rows offering a Buy that
could only 409** and five Buy surfaces needing retrofit. A new restriction then lands on every
path by construction (subsumes A31 for this class).

**★ A37 — fills capped by bar volume.** `VolumeShareSlippage` caps equity fills at **2.5% of the
bar's volume** with **quadratic** price impact, spilling or raising `LiquidityExceeded` beyond it.
**We have no participation cap** — 6.8.2 models half-spread and size-vs-top-of-book impact, and
the notional cap bounds *rupees*, not *liquidity*. **SRTL is the named case**: ₹39 micro-cap,
2,666 shares. A ₹1L position in a stock trading ₹5L/day is 20% of daily volume and is not
fillable at the quoted price.

**T10 — `ExplodingObject` negative-space assertions.** `zipline/testing/` ships as part of the
library, including an object that raises `UnexpectedAttributeAccess` on *any* attribute access:
inject it where a dependency must never be touched and the test fails if it is. It proves a path
does **not** use something — normally the hardest property to test. We hold three such claims by
convention alone: **"frozen engine untouched"** (every overlay), **`circuit_guard` only READS the
cache**, and overlays never seeing future data. Each is a documented safety net with no test that
fails when it lapses — the `unassessed` tripwire failure exactly. ~15 lines.

Synthesis extended to sixteen repos with lesson 15: **the strongest guarantee is the one that
removes the syntax for the mistake.** Rules and reviews catch mistakes; design prevents them —
and where we build new evaluation surfaces (MCE 5b above all), an accessor bound to an "as of"
timestamp is cheaper than a rule and cannot lapse.


### docs(research): repo 13 AKShare — adopt no data code; take its testing strategy (2026-09-03)

[akfamily/akshare](https://github.com/akfamily/akshare), MIT, **~103k LOC across 406 modules** —
the free China-market data library that repos 5 and 9 both lean on.

**The data layer is not for us, on three checks.** India coverage is **incidental** (global-index
and macro modules, a rich-list scraper — nothing resembling NSE equity, corporate actions or F&O).
**314 modules issue HTTP requests and only 13 mention retry, backoff or rate-limiting** — about
4%, so it is not a model for hardening our ingestion either. And
`docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` already settled the data-source question.

**But its answer to "how do you test 400 scrapers?" is the best process idea in the log.** You
cannot unit-test a thousand live public endpoints without a permanently red CI — so it tests the
**contract surface** instead: `interfaces.json` records every public function with its module,
example, limits and **full output schema**, and the suite pins reachability, export mapping and
documentation coverage against that registry.

**★ T8 — a self-cleaning debt baseline.** Five tests govern how known debt may exist:
`baseline_allows_known_gaps` (legacy debt does not redden CI), `baseline_rejects_new_orphan` /
`_new_undocumented` (new debt does), and — the sophisticated part —
`baseline_rejects_stale_entry` / `baseline_rejects_fixed_orphan`: **the build fails when a
baseline entry is no longer a problem.** Most known-failure allowlists rot into permanent
amnesties that eventually suppress real regressions; this one can only shrink. We have the shape
(typecheck coverage gaps, `STATUS.html` prose duplicating gate modes) and no mechanism.

**★ T9 — turn the doc-sync ritual into failing tests. The finding that matters most.** They test
release/doc consistency mechanically — missing changelog entry, missing `__init__` history, tag
vs version mismatch, and `reports_every_problem_at_once` so a sweep is one pass rather than N.
**Our doc-sync ritual is a procedure an agent must remember to run; theirs is a test that fails.**
Our own lesson — *"a documented safety net is worth nothing without a test that fails when it
lapses"*, drawn when the `unassessed` tripwire proved imaginary — was applied to our code and
never to our process. Three of the ritual's seven steps are mechanically checkable today: a new
`settings.*` without an `.env.example` line (promotes **W3**); a `docs/PHASES.md` `(updated …)`
stamp older than the newest `docs/phases/*.md` change; and a gate mode in `STATUS.html`
disagreeing with `settings` — the exact drift our memory warns about with *"grep the gate name on
every flip"*, **a human ritual standing in for a test.**

Its per-interface declared output schema is filed as a note against U8/A7 rather than a new item:
it is how a *returned-but-unrendered field* gets caught mechanically, which we found by review
instead (`unknown` had zero consumers).

Synthesis extended to fifteen repos with lesson 14: **our most repeated process risk has the same
fix as their most repeated code defect.** The commonest defect across the log is *a guard that
cannot fail*; our process equivalent is *a ritual nobody is forced to run*. Same fix — make it a
test.


### docs(research): repo 12 awesome-quant — a curated list, and the negative-control idea (2026-09-03)

[wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant) — a **curated list,
not a codebase**, so mined for candidates rather than audited, and cross-checked against our
existing `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` (which concluded *adopt none as dependencies*).
That conclusion stands. Three findings survive.

**★ H8 — the best idea in the repo, and it is a test of our own bar.** Its Factor Analysis section
lists purpose-built backtest-overfitting auditors — *Lacuna* ("leakage, overfitting, fragile
results, unrealistic costs, missing point-in-time evidence") and *Perception-XAlpha Lite* ("CSCV
probability of backtest overfitting, deflated Sharpe against the declared trial count, White's
Reality Check, point-in-time universe membership, disclosure-date alignment"). The second **ships
a worked example in which 24 pure-noise series produce a 1.11 Sharpe and the audit correctly
rejects them** — a negative control proving the detector fires.

**We should do exactly this to `deflated_sharpe.py`**: generate N content-free random partitions
of the real trade set, run them through the *same* path the real gates use, and assert the bar
rejects them. **If a noise gate clears our bar, the bar is broken and every readiness banner built
on it is worthless.** Cheap (the machinery exists), a genuine test rather than an argument, and
aimed squarely at what has bitten us twice — promoting on evidence that looked sufficient. Our own
rule says a metric that cannot come out badly is not a metric; a *bar* never shown to reject
anything is in the same position. **H9** records CSCV/PBO, White's Reality Check and `mlfinlab`'s
meta-labeling as research pointers, not queued work.

**A36 — our NSE calendar is better sourced than any library, and has the weakest alarm.**
`market_calendar.py` seeds past holidays from **observed bhavcopy session gaps** (ground truth —
a published list can be wrong and you would never know), so we should *not* adopt
`exchange_calendars`. But its expiry path is a **passive WARNING inside a query**, falling back to
weekday arithmetic — seen by nobody. Needs a proactive "calendar covers only to `<date>`, N
trading days remain" notification (A11) plus a cheap cross-check against XNSE. Same pattern as
A25/A30: a degradation technically announced and practically invisible. (Repo 6A solved it a third
way — a refresh script plus versioned JSON.)

**T7 — exhaustive-enum mapping test.** The list ships a test suite for its own markdown, including
`test_all_finding_kinds_are_mapped_and_sorted_deterministically`: adding an enum variant without
handling it fails the suite. **We have been burned by exactly this** — *"v1's `unassessed` tripwire
was IMAGINARY — 3 of 8 modes passed."* Gate modes, rejection reasons and sidecar readiness states
all want it. Its `test_api_error_fails_closed` is also the **third independent codebase** to name
and test "fails closed" as a principle.

Synthesis extended to fourteen repos with lesson 13, **"test the test"**, and lesson 10 reinforced
by its third independent instance.

Meta-observation recorded: we built the deflated-Sharpe bar from first principles on 2026-09-03,
and two libraries in this list already implement it alongside three tests we do not have. That does
**not** mean we should have used them — ours is stdlib-only and wired into our own evidence path —
but the design could have been informed for free, and the negative-control idea would have arrived
a week earlier. A curated list is the right *first* stop for "does a tool already exist for the bar
I am about to hand-build?"


### docs(research): repo 11 vnpy — the most Phase-7-relevant repo, and its 145-line event bus (2026-09-03)

[vnpy/vnpy](https://github.com/vnpy/vnpy), **MIT**, core ~12.8k LOC (gateways and strategy apps
ship as separate packages) — a decade old and the most battle-tested open-source live-trading
framework in Asian markets. Our NautilusTrader review named the Phase-7 gap as *"runtime plumbing
(event bus, ExecutionEngine + BrokerAdapter, RiskEngine, reconciliation)"*; **vnpy is a second,
independent implementation of exactly that — and unlike Nautilus's LGPL it is MIT, so it is
legally vendorable, not merely readable.**

**The headline: the event bus is 145 lines of stdlib Python** — a `Queue`, one consumer thread, a
`defaultdict` of handlers, and a timer thread. Three ideas worth taking: a **single consumer
thread** (handlers never run concurrently, so none needs a lock against another); **wildcard
`general_handlers`** so logging/recording/UI subscribe to everything without enumerating types;
and a **bus-generated `EVENT_TIMER`**, which makes *everything periodic an ordinary subscriber* —
one scheduling primitive instead of a scheduler plus a bus (**A34**). Our staleness alarm,
provisional-health watch and CAS capture window are three different solutions to that one problem.

**But I reproduced three robustness gaps.** `_run` catches only `queue.Empty`, so **a single
handler exception kills the consumer thread**: the healthy handler received *nothing* (the failing
one was registered first and aborted `_process`), `put()` kept succeeding afterwards, and the
process stayed up — **the system looks alive and is completely deaf.** Plus an **unbounded queue**
and **handler lists mutated while being iterated**. Queued as **A32**: isolate exceptions per
handler, bound the queue with a stated overflow policy, iterate a snapshot, and **make a dead bus
loud** — a silently deaf trading system is strictly worse than one that crashes.

**A33 — the OMS as a projection.** `OmsEngine` keeps one dict per entity, all rebuilt purely from
broker events, with `active_orders` maintained as a *side effect* of each order event under a
single `OrderData.is_active()` predicate, and gateway-namespaced ids. Derived state can be
rebuilt by replay, which is what makes reconciliation tractable — and we have been bitten by the
inverse (`signals.status` is a mutable lifecycle field doing double duty as durable fact).
**A35**: define `BrokerAdapter` as an interface a second broker *could* implement even while only
Kite does — vnpy's core ships no gateway, which is what forces the interface to be a real contract.

**A11 is now settled.** `MainEngine.send_notification` fans out to all configured channels as a
core engine method — making vnpy the **third independent mature system** to treat push
notification as a first-class primitive (after repo 4's noise-policy notifier and repo 9's
multi-channel dispatcher). By lesson 9, three independent hits makes it near-certain.

Synthesis extended to thirteen repos with a new lesson 12: **the scary part of Phase 7 is not the
part we thought.** The bus is small and well understood; what actually costs is the order
lifecycle and reconciliation — 82 defects across two audits in repo 4, 543 tests in 6A, and the
same partial-fill bug found independently by both. Budget accordingly: little for the bus, a lot
for the FSM.


### docs(research): repo 10 microsoft/qlib + two new review dimensions (testing, workbench) (2026-09-03)

Brief widened by the user: *"take any idea worthy that upgrades us... don't stick only with
analysis, architecture, ui/ux"* — including test cases and other repos' Claude Code tooling. The
log now carries **five** queues: **H** analysis · **U** UI/UX · **A** architecture · **T** testing ·
**W** workbench.

**[microsoft/qlib](https://github.com/microsoft/qlib)** (MIT, ~56k LOC) is a different tier from
everything reviewed so far — a maintained industrial research platform, the fifth of twelve repos
to make no performance claim, and **the first where nothing needed debunking**.

**★ T1 — the best test in the log.** Qlib treats point-in-time correctness as *syntax* (`$$`
fields, a `P()` operator, so non-PIT use is visible). `tests/test_pit.py` asserts that a
fundamental value **changes on the exact date the filing was published**, citing the real
disclosure URL in a comment — a regression test anchored to a verifiable external fact, which
cannot rot into tautology. Its sibling asserts `NaN` for a stock with no PIT record rather than
forward-filling: **fails closed**. **Our MCE slice 5b (`market_cap` writer) is the keystone
blocker for everything fundamental and inherits exactly this trap**; T1 says ship a
filing-date-anchored test with it, citing a real NSE/BSE announcement.

**Two costing/realism gaps it exposed in our code.** **A29** — our `FeeSchedule` has no
`dp_charge_per_sell`; Zerodha/CDSL levy a **flat ~₹13.5–20 per delivery sell scrip regardless of
size** (PaperTrade-India models it, we don't). A fixed cost disproportionately hits small
positions — exactly what the notional cap produces and exactly the ₹1L / 1–2 position shape live
will have, so **we are under-costing the paper book in the direction that flatters an already
negative expectancy.** **A30** — `circuit_guard.py` (6.8.3) stops the *paper order path* entering
a name pinned near its adverse band, but `app/backtest/` has no band handling at all, so the
backtest fills orders on days a stock was locked limit-up/down and untradeable. Qlib warns
explicitly when its `limit_threshold` is unset for this reason.

**A31 — and the pattern behind them, promoted to a standing rule:** a realism constraint added to
one execution path must be added to every path producing a comparable number, in the same change.
Three instances now — spread-aware fills vs last-close marks (A21), bands on the order path but
not the backtest (A30), `MODE_FULL` subscribed but never verified (A25). Individually minor;
together they mean backtest, paper and live silently stop being comparable.

**T2–T6** from its test suite: lifecycle-boundary tests for an execution simulator (start
mid-stream, stop early — directly Phase 7); parametrised fill tests under a participation limit;
explicit NaN/corner-case tests (earned — a non-finite Redis LTP once 500'd our detail endpoint);
crash-path tests; and ordered pipeline-stage integration tests, which our EOD ingestion chain
lacks. Its `workflow/` recorder (params / metrics / artifacts) also sharpens **H4** and **U1**:
record gate config as params, n/expectancy/DSR as metrics, the sidecar and its query as
artifacts — then the registry page is a *view* and the review calendar is a *query*.

**W1–W5, retro-mined from repo 9's `AGENTS.md`** (qlib ships no agent tooling; repo 4's CLAUDE.md
was already covered as A12): make **doc/code precedence** an explicit rule — the executable
content wins, fix the doc in the same change (W1); **"do not add parallel implementations"** as a
written rule — the one with the most evidence behind it for us, given we found **five separate Buy
surfaces** (W2); same-commit config hygiene (W3); decide the git boundary deliberately rather than
by inference (W4); and forbid hardcoded **model names** alongside secrets and paths — our analogue
being `STATUS.html`, which hardcodes gate modes a flip silently falsifies (W5). Their GitHub-triage
skills are recorded as *considered and rejected* (we are solo, no PR flow).


### docs(research): repo 9 daily_stock_analysis — 332k LOC in 27 days, and the log's best treatment of "which bar could this have acted on" (2026-09-03)

[ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis), MIT,
**~332,000 LOC · 5,782 test functions · 50 commits over 27 days** — multi-market (A/HK/US/JP/KR/TW)
AI daily analysis pushed to WeCom/Feishu/Telegram/Discord/Slack/email. By far the largest repo in
the log, at ~12k LOC/day, which is only reachable with heavy LLM generation (it ships `CLAUDE.md`,
`AGENTS.md`, `SKILL.md`, `.claude/skills/`). The audit question is whether the volume corresponds
to substance — and on the parts checked, unexpectedly, yes.

**★ Its backtest layer is the most methodologically careful in eleven repos.** It grades its own
past analyses against realised outcomes, and resolves the entry bar **from the market session
phase at analysis time** — the exact question that sank repo 5. `resolve_historical_daily_bar_date`
recognises six named phases (`premarket` / `intraday` / `lunch_break` / **`closing_auction`** /
`postmarket` / `non_trading`), uses a real per-market calendar library, treats a persisted
`effective_daily_bar_date` as the primary authority, and — decisively — **fails closed**: an
unknown or calendar-inconsistent phase returns `None`, excluding the record from scoring rather
than guessing. In every other repo here, ambiguity resolved in favour of the flattering answer.
`closing_auction` as a first-class phase is directly relevant to our own CAS work. **And the
README publishes no accuracy number** — it ships the instrument and lets you run it on your own
history.

**A27 / A28 extend A11.** A27: a notification **config dry-run** (`--check-notify`) plus a
`--no-notify` escape hatch — A11 runs unattended, so the first time it *should* fire is the worst
time to discover the credentials are wrong. A28: `ChannelAttemptResult.retryable` — classify a
delivery failure by whether retrying can help, and return a structured per-channel dispatch
result. Combined with repo 4's rule that a notifier outage must never affect trading, the design
is: try, classify, record, never raise into the caller.

**Cautions recorded:** the README's "recommended" LLM/data/search providers carry affiliate
parameters (`share_code=`, `?aff=`, `ref=`, `utm_source=`) — stated as fact, the code is not
compromised, but the provider comparisons are not disinterested. File sizes are a maintenance
risk (5,563 / 5,182 / 5,124-line source files; 4,841-line test files). And its decision layer is
an LLM producing scores and buy/sell points, which changes nothing about our position that the
money path stays deterministic.

Synthesis extended to eleven repos with a new lesson 10: **one line decides whether a system is
honest — what it does with the ambiguous case.** Repo 9 returns `None` and says "it fails closed";
every repo that failed this audit resolved ambiguity the other way (a missing holdout became the
full window, an unrecognised phase became "close enough", a `'NO'` string became `True`). Failing
closed is cheap and is the clearest separator in the whole document — and it is why our
shadow-first overlays and fail-open-with-an-alarm design are right *provided the alarm exists*
(A11, A25). Lesson 8 also refined: the four repos that survive audit all decline to publish a
performance number; three are pure infrastructure and the fourth ships the measuring instrument
instead of a result.


### docs(research): repo 8 express-option-chain — the only repo on our exact stack, and it found a gap in ours (2026-09-03)

[pramakrishn/express-option-chain](https://github.com/pramakrishn/express-option-chain), MIT,
**952 LOC, 3 commits, 2023, unmaintained** — a focused library streaming NSE/MCX/CDS/BCD option
chains over **Kite Connect WebSocket into Redis**. The only repo in the log built on our exact
stack, and infrastructure rather than strategy (no performance claim), which by lesson 8
predicted it would hold up. It largely does.

**★ A25 — it documents a Kite behaviour we are exposed to.** Their `on_ticks` guards:

```python
if ticks[0]['mode'] != ws.MODE_FULL:
    # bug: web socket sent ticks in quote mode even though we subscribed in full mode
    ws.stop(); return
```

**We subscribe `MODE_FULL` and harvest order-book depth from those ticks, and never check the
mode** — verified at `live_worker.py:979` / `:505` and `tick_consumer.py:256`, with no
`tick['mode']` validation on either path. If Kite downgrades against us, `depth:{stock_id}` goes
stale and **6.8.2's spread-aware fills silently fall back to the flat `paper_slippage_bps`
floor** — the fail-open path working exactly as designed, and therefore invisibly. The symptom
would be paper fills quietly getting cheaper than reality, on the book we use to judge whether
−0.303R expectancy is improving. Fix is ~2 hours: assert the mode, count degradations, surface
it. Pairs with A11 and the existing 6.8.6 staleness alarm. *(Not an observed bug — a documented
broker behaviour we have no detector for.)*

**A26 — refuse loudly at a capacity boundary.** They name Kite's limits as constants with
provenance (`MAX_TOKENS_PER_WEBSOCKET = 3000`, `MAX_WEBSOCKET_CONNECTIONS = 3`), shard across
processes, and **refuse to start** past the ceiling with an error stating the actual counts and
two concrete remedies. **The direct contrast with a failure we already had**: our `live-worker`
hot set was flooded by breadth alerts and watchlist stocks silently stopped being scored.

**Adopt no code.** Its Redis and threading patterns are things our rules explicitly forbid: one
`hset` round-trip **per tick** with no pipelining (the exact defect perf-auditor caught in our
6.8.1), a new `threading.Thread` on every tick callback with no queue or backpressure, **no TTL**
on the tick hash (harmful under our volatile-lru policy), and `ticks[0]` indexed without an
emptiness check. Operationally: **token expiry is unhandled** (`on_noreconnect` logs and stops;
the Kite token dies ~06:00 IST daily — our rules call this "a normal lifecycle event, not an
error loop"), and its process watchdog is a **startup check, not a supervisor** — it returns once
all processes are alive, after which a death is never repaired.

Synthesis extended to ten repos, with a new closing lesson: **the most useful findings came from
the repos closest to our own stack, and they were about *us*** — PaperTrade-India exposed A21
(fills spread-aware, marks not), this one exposed A25. Neither was a defect in their code; both
were gaps in ours, visible only because someone else solved the same problem and left the guard
in. **Prioritise repos sharing our exchange, broker or stack over those sharing our ambition.**


### docs(research): repo 7 Stock-market-prediction-and-screener — leaked scaler, missing baseline, disabled guard (2026-09-03)

[sumittttttt/Stock-market-prediction-and-screener](https://github.com/sumittttttt/Stock-market-prediction-and-screener),
MIT, ~3.9k LOC, **2022-04 → 2023-01, unmaintained**. A Streamlit multi-page app (fundamentals,
indicators, "screener", pattern recognition, next-day forecasting) plus a notebook that selects
the forecasting model. A competent student portfolio piece — and the ninth repo in the log,
repeating three established failure modes in unusually clean form.

**Model selection rests on two errors.** (1) *Leaked scaler*: the notebook defines
`train = dataset[0:990]` / `valid = dataset[990:]` and then calls
`scaler.fit_transform(dataset)` on the **whole series**, so the validation window's min/max are
baked into the normalisation the LSTM trains under. (2) *No persistence baseline*: for a
next-day **price** predictor the only benchmark that matters is "tomorrow = today", and it is
absent from the comparison table. A large cap in the low thousands at ~1.5% daily vol has a
persistence RMSE near ₹40–50; the selected LSTM scores **117.49** — plausibly two to three times
worse than predicting no change, while comfortably beating the three other elaborate models it
was measured against. (Order-of-magnitude estimate; the exact split isn't published. The point
is the omission, not the constant.)

**A guard that cannot return false — the third instance across nine repos.**
`is_consolidating` returns the **strings** `'YES'`/`'NO'`; `is_breaking_out` uses it in a boolean
context, and both strings are truthy (verified). The consolidation precondition is therefore
always satisfied and `is_breaking_out` degrades to a plain 15-day-high check with its defining
filter silently disabled.

**UI confirms:** the "Screener" page takes a single-ticker `selectbox` and screens nothing; and
every indicator is cast `.astype('int64')` **before** `round(..., 2)`, so RSI 67.83 renders as
`67.00` and MACD values between −5 and +5 truncate to 0 — fake precision with the signal
destroyed. Exactly why `lib/format.ts` is the single formatting path in our rules.

**Taken:** nothing adoptable. One pointer — a compact consolidation primitive (`min_close >
max_close × (1 − pct/100)` over N candles) for the already-queued **Minervini trend-template
shadow test**, with the obvious upgrades: return a real boolean, measure the range in ATRs
rather than raw percent, require a minimum base length.

Synthesis restructured to nine repos with a promoted lesson: **"a guard that cannot return
false" is now the single most repeated defect in the log (3 of 9)** — `generalization_gap ≡ 0`,
`risk_approved` always true, and now a truthy-string predicate. Three root causes, one symptom.
**The test is mechanical: for every guard, name the input that makes it fail; if you cannot, it
is not a guard** — our own `unassessed` tripwire failed exactly this. Lesson 1 sharpened to its
operational form: **when a repo picks a winner, look first at what it did not compare against.**


### docs(research): repos 6A–6C — a reference implementation, a mock demo, and a fabricated exit date (2026-09-03)

**6A [Mirzabaig313/PaperTrade-India](https://github.com/Mirzabaig313/PaperTrade-India)** —
MIT, **~24.8k LOC · 543 tests**, a standalone pip-installable **NSE/BSE paper broker**: the
same job as our `paper_broker`. Date-versioned statutory fee engine, T+1 settlement with
deliverable-qty enforcement, 15:15 intraday square-off, tick/lot/band snapping, bracket/OCO,
synthetic L2 book with queue position + Almgren impact, corporate actions, double-entry ledger,
pluggable data providers with per-provider circuit breakers. **Makes no performance claim** (it
is infrastructure) — the second repo after quant-agent to pass that test. **The one repo here
that is a reference implementation rather than a cautionary tale.**

**★ A21 — it exposed an inconsistency in our own system.** They mark unrealized P&L
**to bid**; our `_open_book_mtm` marks *"to the last 1m close ≤ cutoff"*. Since 6.8.2 our
**fills** pay the real half-spread but our **marks** do not — we charge the spread in and out,
then value the book as if we could exit at the untouched last price. With 82% of NSE books
wider than 2 bps across a ~25-position book, reported open-book MTM is systematically
optimistic. **The depth needed to fix it is already captured (6.8.1).** Also **A22** bracket
sibling-qty rebalance on partial fill (a named function here; repo 4 called the same failure
"the partial-fill mode that took several iterations to pin down" — two independent hits make it
near-certain for Phase 7) and **A23** an effective-dated fee registry (ours is *designed* for
versioning but is a single constant set today).

**Correction to §5.2, found via their `docs/FEES.md`:** an earlier draft said real round-trip
NSE delivery cost is ~0.12–0.13% because STT applies only to the sell leg. **Wrong — delivery
STT is 0.1% on both legs** (intraday 0.025%, sell only), so ~0.22% round trip. Our own
`app/trading/fees.py` already encodes this correctly, so no P&L is affected — but repo 5's 0.2%
commission was *accurate*, not conservative, and §5 now carries the correction inline.

**6B [artist-hks/SentimentStock](https://github.com/artist-hks/SentimentStock)** — 7 commits,
no LICENSE (despite an MIT badge). Advertises *"Hinglish NLP sentiment analysis"* and
*"LSTM-style stock predictions"*; there is no NLP and no model — `generateData.js` emits
deterministic pseudo-random series from `Math.sin(seed) * 10000`. Judged as the UI demo it
actually is, one idea is worth taking: **U19**, a lag/horizon correlation chart. We found *in
prose* that we grade multi-day trades on a one-day clock (entry-day ≥1R 12% vs swing 36% /
positional 54%, +1R typically d+3); this is that finding's natural rendering, and it
generalises to every shadow overlay — *at what horizon does this gate separate winners from
losers?*

**6C [madhusudhan-nikhil/InvestmentPrediction](https://github.com/madhusudhan-nikhil/InvestmentPrediction)**
— active FastAPI+React app for Indian retail, no LICENSE. **Hierarchical Risk Parity** for
portfolio construction is a genuine pointer (López de Prado; our heat sits at 45.3% with no
correlation-aware sizing). But its **"probable exit date"** is a specific calendar date computed
from deterministic drift with **zero volatility**, a hardcoded category fudge (×0.70–×1.45), and
— decisively — **no dependence on the target price at all**: ask for a 5% target or a 50% target
on the same stock and horizon and you get the same date. Queued as **A24, a standing rule: never
render a precise figure without its uncertainty.** Same failure as repo 3's vote-share-as-
confidence; we are specifically exposed because a 2–3%/day goal invites converting a wish into a
timeline.

Synthesis extended to eight repos, with two new lessons: **(7) the repos worth reading are the
ones with nothing to sell** — the only two that survive audit cleanly are both infrastructure,
and the presence of a headline performance number is empirically the best predictor that a
repo's claims will not survive its own source; **(8) two independent projects hitting the same
bug makes it near-certain for us** — which is why A22 is queued before Phase 7 starts.


### docs(research): repo 5 QuantAgents-NSE — the only NSE repo, and its claim fails on six counts (2026-09-03)

[PreethamSanji/QuantAgents-NSE](https://github.com/PreethamSanji/QuantAgents-NSE), ~7.9k LOC,
**no LICENSE file**. Four agents (news/technical/risk/manager) replicating arXiv:2501.04916 on
the Nifty 50, with FinBERT sentiment and a FinRL PPO model. **The first repo in the log on our
own exchange**, which makes it the easiest to check — and the claim (a commit headline, not the
README: *"improve backtester **to** Sharpe 0.237, CAGR 8.9% vs Nifty 8.4%"*) does not survive:

1. **Look-ahead in the live backtest path** — the Otto score for a date is computed from
   indicators including that date's close, and the trade fills at that same close. Our
   constraint #3 exists for exactly this. First repo here with look-ahead in the *executed*
   path rather than a commented-out holdout.
2. **Survivorship bias twice over** — the universe is "top 10 Nifty 50 stocks with longest
   yfinance history": current index membership *and* longest history, i.e. the ten blue chips
   that both survived and stayed in.
3. **Two of the four agents are wired to nothing** — `in_bull_market` (the 200-DMA regime
   filter, advertised as *"eliminates the worst drawdown periods (2008, 2011, 2020)"*) and
   `r_score_today` (Dave's Equation 3, weighted 30% in config) are both assigned and **never
   read**; `risk_multiplier` is hardcoded 1.0. The backtested system is not the diagrammed one.
4. **Tuning documented in the comments** — weekly-over-monthly rebalancing because monthly
   "hurt CAGR", Emily's ±0.5 cap set so Bob can overcome it, asymmetric ±0.15/−0.10 thresholds.
5. **Risk-free accrual added on idle cash** with the stated reason that it makes cash-holding
   Sharpe-neutral — justified by a regime filter that is dead code.
6. **No spread or impact** (commission only, ~0.2% round trip — actually conservative vs real
   NSE delivery cost, but our 6.8.2 finding is that 82% of NSE books are wider than a flat 2bps).

After all six the result is **+0.5pp CAGR at Sharpe 0.237** — inside the noise of a ten-stock
five-year sample before any of it.

Also **reproduced an NSE calendar bug**: `resample("W-FRI")` labels buckets with the calendar
Friday while the index holds trading days, so **any week whose Friday is an NSE holiday skips
rebalancing silently** (demonstrated against Good Friday 2025). Precisely the failure our
domain rules name.

Harvested: **A18** India news sourcing for the unbuilt **MCE news veto (slice 6)** — Google
News RSS with `hl=en-IN&gl=IN&ceid=IN:en` plus **FinBERT** (`ProsusAI/finbert`), and explicitly
**not** their MoneyControl/ET HTML scrapers (the repo ships three HTML-debug scripts — the
evidence it kept breaking); **A19** normalise components before summing a composite risk scalar
(their Equation 3 sums beta, inverse liquidity, sector concentration and vol at equal weights
with no normalisation, so the largest-scale term dominates and the weights are decorative);
**A20** a signed risk penalty that scales confidence rather than a boolean gate — closer to what
the reverted regime gate should have been.

Synthesis extended: lesson 0 is now four of five, and a new lesson 2 — **dead code advertised as
a feature appears in three of five repos**, so "does this path affect the output?" is a faster
audit than reading the logic, and `grep` answers it.


### docs(research): repo 4 quant-agent — the best-engineered of the four, and the only one whose claims survived audit (2026-09-03)

[yebof/quant-agent](https://github.com/yebof/quant-agent), MIT, **~63k LOC · 1,344 tests**,
solo author, US equities, live-capable via Alpaca. **The most relevant repo reviewed so far
by a wide margin** — the same *shape* as what we are building (scheduled sessions, real
broker, portfolio, risk gates, daily reflection), so the comparison is direct.

**Its claims check out** — a first. `risk_reward` really is a Python `@computed_field` over
entry/stop/target geometry returning `None` on malformed input "so PM/RM won't render a fake
ratio"; the schema-enforced CoT is real (**64** `min_length=1` fields — a skipped step is a
`ValidationError`); the "874 tests" claim *understates* the actual 1,344; and it makes **no
performance claim anywhere**. Synthesis lesson 0 revised accordingly: the rule is not "public
repos lie" but the narrower, more useful **"the claims that fail audit are almost always the
performance claims, and the repos that make none are the ones worth reading."**

**The gap, which the author states himself:** there is **no backtest, no walk-forward, no
evaluation harness** in the repo — *"prompt changes cannot be backtested here, so it is easy
to ship something merely because it sounds right."* His decision-replay harness diffs how a
prompt change alters decisions on real historical inputs, but outcome-aware scoring is
*"the layer above this, not yet built."* **The symmetric trade: he has the production machine
we have not built, and none of the validation we already have — and ours is the safer of the
two positions.**

Harvested (architecture queue, now 12 items): **★A11 session notifier with a noise policy** —
the most actionable item in the whole document. Silence for routine success, failures
classified by whether a human can act (SEC transient suppressed, analysis error not), **any
exception always notifies**, the artifact is its own confirmation, and a notifier outage can
never affect trading. **We have at least two standing manual daily human checks that exist
only because we have no notifier** — CAS capture (15:15–15:33 IST, *a missed window cannot be
back-filled*) and provisional health (no scheduler at all). Also **A13** a test pinning the
circuit breaker's un-suppressibility (theirs is exempt from both the dedup guard and the
session mutex, pinned by a named test — our `unassessed` tripwire taught us documentation
alone is worthless); **A15** assert scheduling window ≥ tick interval (a 25-min window on a
30-min timer missed the close two days running — **our CAS window is 18 minutes and its miss
is unrecoverable**); **A14** timeouts derived from measurement, layered, after a 13-hour hang;
**A12** invariants documented with the dated incident that produced them; **A16** the
order-protection lifecycle state machine — not actionable pre-live but the best available map
of what Phase 7's BrokerAdapter must handle; **A17** provider failover semantics + a pinned
cost table.

Recorded for balance in §4.5: we are ahead on validation, a freezable deterministic engine,
money types (they use floats for prices throughout), and a real UI — and self-modifying
prompts on a live trading system, however well guarded, changes behaviour on argument alone,
which is what our constraint #8 exists to prevent.


### docs(research): repo 3 ai-quant-agents reviewed — a 236-line SDK, not a quant system (2026-09-03)

[demandai/ai-quant-agents](https://github.com/demandai/ai-quant-agents), single commit,
Apache 2.0, **295 LOC total**. **Not a quant system: a marketing SDK for a closed paid
service** (`dream.hmyk.ai`) — no indicators, no backtest, no data layer, no evaluation. The
"12 AI agents" run server-side behind a PRO ONLY gate. Its most useful line names its
upstream, **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** (Tauric
Research, Apache 2.0) — **that is the artifact worth reviewing, and it is now queued.**

Four defects in 236 lines, all of a familiar kind: **`risk_approved` is hardcoded true**
(`"risk" not in decision.lower()` where decision ∈ {BUY,HOLD,SELL}) while the product is
marketed on a "Risk Manager with VETO POWER"; the README's example output advertises
`entry`/`stop_loss`/`target`/`position_size` but the code sets `suggested_action={}`
unconditionally — the only four fields a trader would act on are decorative; the decision is
a **substring match on free LLM text** (`if "BUY" in text`, tested before SELL, so *"I would
not BUY this"* → BUY); and **the stream has no correlation id**, connecting to a global
socket and consuming any analysis until the first `analysis_complete` — on a shared demo
server `analyze("NVDA")` can return a stranger's TSLA debate, stamped NVDA locally. Also
`key_reasons` is harvested only from bull/aggressive speakers, so it is structurally the
bull case even when the verdict is SELL.

Harvested despite the above: **A9** a progress envelope for long-running jobs
(`{phase, step, total_steps, message}` — LLM-agnostic, and several of our jobs run minutes
in silence, the walk-forward replay ~8 of them); **A10** emit running results mid-flight;
**U16** a phase/participant stage-tracker strip (~40px shows every phase and what has
completed); **U18** a streaming log with phase tags and per-entry expansion; and **U17**,
the most valuable — **confidence as a distribution bar rather than a scalar**, which
completes the trio with U10 (the arithmetic) and U15 (the named evidence): a 78% scalar
hides whether four factors agreed or one carried everything, which *is* the SRTL failure.

Synthesis section extended and re-titled. New lesson 0: **all three repos advertise numbers
or fields their own code cannot produce** — in this sample the base rate of a public quant
repo's headline claim surviving contact with its own source is **zero**. New lesson 4:
"confidence" is repeatedly a *share*, not a probability — theirs divides modal votes by
total across agents that share a model and prompt (correlated by construction), which is the
same shape as our own confluence normalising by the weight of factors that scored.


### docs(research): repo 2 QuantHarness reviewed + architecture becomes a standing review dimension (2026-09-03)

Per user instruction the review log now carries **three** numbered queues — analysis
(`H`), UI/UX (`U`) and **architecture (`A`: notifications, menus/IA, portfolio modelling,
credential lifecycle, agent topology, cost tiering, state schemas)**.

Repo 2 = [Y-Research-SBU/QuantHarness](https://github.com/Y-Research-SBU/QuantHarness)
(arXiv:2509.09995; Stony Brook/CMU/UBC/Yale/Fudan; MIT; ~3.6k LOC): four LLM agents
(Indicator → Pattern → Trend → Decision) in a LangGraph, two of them **vision** agents that
render candles to PNG and have a VLM read the picture. Far more serious than repo 1 — the
benchmark is real (1,600 CSVs) and the baselines are strong and honestly reported.

**But the headline table does not carry the claim.** n=300/cell (the .3/.7 decimals are
thirds); recomputing a two-proportion test the paper omits: **significant vs the naive
baseline 5/8, but vs LOGISTIC REGRESSION 1 of 8** — and that one (ES) rests on LR scoring
43.0%, below chance. Mean 55.8% vs LR 51.0%, inside the ±5.7pp CI on almost every asset.
**BTC — the flagship — is the weakest cell (50.7%, z=1.40).** Directional accuracy is also
not profitability: no costs, and the design forces a trade every window. Reproducibility
gaps: **the 1,600 benchmark CSVs ship but no eval script does**, and the only visible
look-ahead holdout is a **commented-out `.iloc[:-3]`** beside the live path, with no flag
and no test.

Two design choices rejected outright, both instructive: **`HOLD is prohibited`** (a
forced-trade architecture — the inverse of our thesis that entry *selectivity* is the edge:
44 defect trades −₹19,649 vs 55 clean +₹5,256), and an **LLM told to emit a risk-reward
"between 1.2 and 1.8"** with no stop or target computed. Its confluence is done in prose,
which is non-deterministic and un-backtestable — a case where our frozen numeric engine is
ahead of a published paper.

Harvested: **A3** a broker credential-status endpoint + banner (the Kite token dies ~06:00
IST daily and its state is only discoverable from a failed request — highest-value item
because the failure is known to recur); **A4** constraint pre-validation endpoints
(generalises the fix that removed 41/204 Buy rows that could only 409); **A1** two-tier
model routing for the research loop only; **A5** self-documenting `Annotated` state schemas;
**A6** independent analysts fan out, never chain (theirs pays 3× latency for a chain of
mutually independent agents); plus **U15**, a named-evidence line for the signal detail
view — the human-readable half of U10.

New closing section, **"What both repos independently confirm"**: a simple baseline matches
the elaborate system in both (buy-and-hold +102.4% vs +0.7%; LR ≈ four-agent GPT-4o on 7/8
assets) and neither leads with it though both ship the data; the guard that matters is the
structural one (a metric that could only return zero; a holdout that is a comment); and
published work stops where the hard part starts — neither models a position, and repo 2 is
titled "for High-Frequency Trading".


### docs(research): external quant/AI-agent repo review log — `docs/quant-agent-findings.md` (2026-09-03)

A running review log for external repos the user shares, starting with
[OnePunchMonk/AgentQuant](https://github.com/OnePunchMonk/AgentQuant) (~12.1k LOC, MIT, LLM
parameter-search agent over US ETFs). Every number was recomputed from the repo's own code and
committed CSVs rather than read off its README — and the two disagree. **Verified: the "6-epoch
harness evolution" runs identical code six times** (`harness_spec` is never passed to `run_agent`,
which takes no harness parameter); the published results JSON **cannot be that script's output**
(its `generalization_gap` is `max(avg − best, 0)` ≡ 0 yet stores 0.124; `claim_accuracy` is a
hardcoded `0.8  # Placeholder`); and the algorithm-comparison table comes from a **`_mock_fitness_
function` that never touches market data** and encodes its own conclusion (`+0.10 if use_tools`).
The repo's *committed* experiments refute its thesis: buy-and-hold SPY returned **+102.4%/0.896
Sharpe** vs the agent's converged golden cross at **+0.7%**, the LLM picked `(50,200)` in **8 of 9**
walk-forward windows, 8 of 9 rationales say the regime context was empty, and the ablation has
**No-Context 0.711 vs With-Context 0.277**.

Verdict: **adopt no code, reject the thesis, harvest four ideas.** Queue (unauthorised — watch mode
holds to 2026-09-04, and all four are measurement, not money path): **H1** moving-block bootstrap p5
Sharpe beside PSR/DSR/MinTRL — the non-parametric complement to a bar whose own weakness is the
independence assumption, and an automatic version of the tail-robustness check constraint #8 asks
for by hand; **H2** a buy-and-hold benchmark line in the daily report (we have none — `benchmark.py`
is per-signal RS, not a portfolio baseline — and the index bars are already backfilled); **H3**
re-frame the VIX companion as a trailing percentile, dissolving the "history too shallow to
§8-validate" blocker on an absolute, US-derived threshold of 20; **H4** the gate/hypothesis register
as data rather than prose.

**UI/UX pass — now a standing part of every repo review** (numbered `U1…`, separate from `H1…`).
Its stack is Streamlit + Plotly, one light theme, no tokens — behind ours on every axis — but
**its Research Workspace screen is better information design than anything we have for the same
job**: one Experiment Registry table (name · mode · metric · robustness · validation)
**default-sorted by a drawdown-penalised robustness score rather than the headline metric**, with
**benchmark rows inside that same sort order** so buy-and-hold's 0.896 cannot be skipped; a
worst-of-checks `Validation` column whose per-check *reasons* are one click away; a
`tried/accepted/watch/rejected` funnel strip; rejected candidates left on screen with their
damage; and an `Artifacts` panel naming the file each number came from. Our equivalent evidence
is **seven separate markdown sidecars** opened one at a time. Queued U1–U10, led by a Research/
Gate Registry page (U1) with benchmarks-as-rows (U2) and a trials-attempted counter (U4) — the
last makes `N` in `E[max SR]` an observed number instead of the 20 we assume, the soft spot in
the whole DSR bar. Its weak `dashboard*.png` screens are logged as *confirms*: wide dataframe
dumps clipped off-screen, `None` rendered raw, unformatted floats, no profit/loss colour — each
a defect `.claude/rules/ui.md` already forbids.

Also recorded as a cautionary case study: five mechanisms by which a
green, well-tested repo reports numbers its code cannot produce.

### feat(MCE slice 3): sector-RS shadow sidecar + per-entry context + flip off→shadow (2026-08-20)

The forward-evidence half of the sector-RS overlay, mirroring `regime_gate_shadow` /
`entry_quality_shadow`. `app/services/sector_rs_shadow.py` recomputes the RS verdict over the
tradeable signal cohort (`is_shadow` FALSE, since OUTCOME_EPOCH), each signal judged on benchmark
closes aligned to its own `created_at` (no look-ahead), partitioned **would-block / eligible /
no-benchmark-data** with resolved paper outcomes + a flip-readiness banner. Written by `make
analysis` as `sector-rs-shadow-<date>.md` (wired into `daily_analysis.py`), and it carries a
**per-entry table** — each committed signal's benchmark, excess-vs-benchmark %, RS verdict, and
outcome — the MCE's standing requirement to surface context so we never trade blind to sector
leadership.

The gate default is **flipped `off`→`shadow`** (`sector_rs_gate_mode`): the order path now computes
+ stamps the RS verdict but never blocks (fail-open). `18 tests`, ruff/mypy clean, order-path
regression green (138). **quant-verifier PASS** (no look-ahead, buckets correct — an unassessable
signal never biases the eligible set, flip-bar conservative; 2 INFO — a label made side-neutral, a
`p.avg None` edge left identical to the reviewed sibling). Evidence accrues once `index_ohlcv_1d`
backfills (next `make worker` self-heals it ≤21d); a later shadow→active flip needs the R-track
ceremony (§8-on-≥2y + sign-off).

### feat(MCE slice 2): index price store + benchmark provider + sector-RS wiring (2026-08-20)

The keystone the relative-strength overlay needed — a real index price series — plus the wiring
that puts `sector_rs` on the paper order path (mode `off` by default, so no behaviour change yet).

- **Data (Option B, no Kite dependency):** index EOD OHLC comes from the NSE indices bhavcopy CSV
  that `vix_service` already downloads (every NSE index is in that one file). New `index_ohlcv_1d`
  table (migration `b8c9d0e1f2a3`, reversible) FK'd to the existing `indices` registry, so indices
  stay OUT of the tradeable stock universe. `app/services/index_ohlcv_service.py` parses the CSV
  (keyed on the registry, idempotent upsert) and is wired into the EOD catch-up (`catchup_fo_eod`),
  so it self-heals ≤21d like the other feeds.
- **Provider:** `app/services/benchmark.py` maps a stock to its most specific benchmark index
  (Bank-Nifty ⊃ Fin-Nifty ⊃ NIFTY 50 via membership flags) and returns the stock's and that index's
  daily closes **aligned on common trading days**, anchored to the signal's decision time — closing
  the slice-1 alignment note, no look-ahead.
- **Wiring:** `sector_rs` runs in `_apply_eligibility_overlays` and stamps a verdict on the order;
  `settings.sector_rs_gate_mode` (off/shadow/active, **default off**), `sector_rs_lookback` (20),
  `sector_rs_min_excess_pct` (0.0). The benchmark read runs in a `begin_nested` savepoint and fails
  OPEN on any DB fault — a benchmark lookup can never suppress a trade.
- `16 tests` (CSV parse · idempotent ingest · provider mapping/alignment/gap-drop/as-of · wiring
  off/shadow/active-block/active-allow/fail-open-no-data/fail-open-on-DB-error), ruff/mypy clean.
  **quant-verifier PASS-WITH-NOTES** (look-ahead truly prevented) + **bug-hunter** 1 MEDIUM
  (fail-open on exception) + 1 LOW (docstring), both fixed. Per-sector index mapping deferred; slice
  3 = the shadow sidecar + daily-report context section.

### milestone: Phase 6 + Phase 6.8 GATED + CLOSED (2026-08-20)

Both phases passed `/phase-gate` and are on `main` (pushed). One full `make check` on the merged tree
(worker stopped for a quiescent dev DB) certifies both — the code tree was byte-identical across the two
gates: **backend 1477 · parity 16 · walkforward 9 (§8 drift gate — frozen engine untouched) · replay 19
· frontend 375 · cargo ok**; static clean; `make analysis` smoke green. **Phase 6** (outcome tracking +
entry-selection) closes build-complete with three forward-evidence loops continuing post-close (regime
keep/revert review ~09-15 · momentum-retune promotion · pair df-vs-adf) — none blocking. **Phase 6.8**
(execution realism) closes with paper day-1 still deferred until the user says "proceed" (the merge did
not start the clock). Close reports: `docs/phases/phase-06-plan.md` and
`docs/phases/phase-06.8-execution-realism-plan.md`.

### feat(MCE slice 1): sector/index relative-strength overlay module (2026-08-20)

First slice of the Market Context Engine (`docs/phases/phase-MCE-market-context-engine.md`) — the
*top-down* context the tradeable confluence engine lacks. `app/signals/sector_rs.py`: a downstream
eligibility overlay (NOT an additive confluence factor — that would dilute the ≥70% gate), the same
pure/moded/fail-open shape as `circuit_guard` / `regime_guard` / `entry_quality`. It reuses the
platform's own relative-strength definition (`profiles/setups.eval_relative_strength`: excess =
stock_return − benchmark_return over `lookback`; BUY wants out-performance, SELL under-performance) and
is agnostic to where the benchmark close series comes from. Modes off/shadow/active, **default off** —
the module is UNWIRED (no order-path call, no config key yet), so it changes no behaviour. `16 tests`
(values + both sides + every fail-open branch + all modes), ruff/mypy clean. **quant-verifier
PASS-WITH-NOTES** — formula matches the `eval_relative_strength` reference term-for-term; two MEDIUM
notes actioned in-slice: a gap/None element in the series now fails open (previously would raise), and
the caller alignment contract (session-aligned, completed candle N, no look-ahead) is documented for
the wiring slice to enforce; SELL-boundary + `bench_then==0` tests added. No migration.

Recorded a **premise correction** in the MCE plan: there is no index price series in the DB (only the
`is_nifty50`/`is_banknifty`/`is_finnifty` membership flags) and the RS benchmark input is unwired
everywhere, so the benchmark must be built — an OPEN decision (synthesize from constituents vs ingest
real Kite index OHLC) that blocks slice 2 (benchmark builder + cache + order-path shadow wiring).

### fix(provisional): breadth alerts no longer flood the hot set + per-day cycle health (2026-08-19)

`live-worker` logged two warnings on nearly every provisional cycle — `hot set clipped 466 → 150` and
`cycle overran the cadence: 4039 ms > 3000 ms`. Both were by-design log lines, but the numbers behind
the design had drifted, and the first was hiding a real loss of coverage.

**Root cause.** `_recent_trigger_sids` admitted EVERY alert-stream entry as "near-trigger", regardless
of tag. Measured on the live stream (2026-08-18): `volume_burst` alone carried **1271 distinct stocks**,
plus PDH/PDL crosses on ~880 more — market-BREADTH breadcrumbs, not near-trigger. Against a 150 cap
the trigger source alone was ~2.3× the cap, so with 117 active-signal stocks the remaining ~33 slots
went to the lowest stock_ids (the ordering is `(priority, stock_id)`, so the *same* 33 won every cycle)
and **watchlist stocks — a documented hot-set source — were never scored at all**.

- **Near-trigger now means SIGNAL-BOUND.** The producer already discriminates: `live_levels` stamps
  `style="market"` on vburst/PDH/PDL/S&R and the signal's classification on entry-zone/SL/TP alerts.
  Market-level entries are excluded; a style-less entry reads as market (**fail closed** — failing open
  would let the flood back silently). `live_provisional_trigger_market_max` (default 0) dials breadth
  back in as a bounded, recency-ordered **discovery tier ranked BELOW the watchlist** and deduped
  against everything already hot, so turning the dial on can never re-starve the watchlist.
  Observability only — the provisional layer is never tradeable.
- **Known trade-off at the default 0:** the third hot-set source then adds almost nothing new — 38 of 45
  signal-bound alert stocks already carried an active signal — so the hot set is effectively
  `active signals ∪ watchlist`, ~37 of 150 slots sit idle, and ~1569 breadth-movers can never reach a
  board. Deliberate (this thread holds the GIL); the dial is how you buy discovery back, and
  `scripts/provisional_health.py` now prints the idle-slots-vs-declined-movers line so the cost is
  visible rather than assumed.
- **The cadence overrun is arithmetic, not a fault.** Measured here at 35.6 ms per `run_all_factors`
  window (the module's own figure: 45.7 ms) × ~50 engine calls ≈ 1.8–2.4 s, plus 150 window loads —
  against a 3.0 s cadence. Overruns never queue (`delay = max(0, cadence − elapsed)`). Left alone
  pending forward evidence; raising `live_provisional_refresh_s` is the follow-up if it persists.
- **Cycle health is now durable.** New `provisional:health:{day}` key (TTL one week): cumulative
  cycles / overrun% / clip% / mean+max elapsed / last-cycle hot-set composition per IST session day,
  re-seeded across a mid-session worker restart. `make live-worker` writes no log file, so a day's
  cadence/clip record previously lived only in a terminal and died with it. `HotSetStats` rides the
  cycle stats so a clip is trendable, not log-only. Read it with `scripts/provisional_health.py`
  (read-only; also recomputes the hot-set input independently, so a filter that silently stopped
  working is still visible).

Also noted while measuring, not changed: the provisional thread runs the **Python** frozen engine in
the consumer's process, so it holds the GIL at ~100% duty cycle all session. A consumer-like 1 ms wake
loop degrades from p50 1.08 ms / max 2.14 ms (idle) to **p50 6.16 ms / max 33.3 ms** with one scorer
thread running. The live heartbeat moved the same way (2026-07-16 soak, no provisional thread:
`lat_p50=7.5`; 2026-08-18: `lat_p50=50`) — though tick volume is also 8× higher, so that shift is not
attributable to provisional alone. Note `lat_p99` in the heartbeat is **not a p99**: the histogram tops
out at 100 ms, so `quantile_bound` falls through and returns `max_ms`.

**22 new tests** (50 in `test_provisional.py`, up from 28, all green), no migration, reversible by
config.

**Reviews.** bug-hunter: BUGS-FOUND, 5 LOW, all in the new monitoring surface, all fixed — (1) the
restart re-seed ran outside the loop's `try`, so a non-numeric health key raised straight out of the
NON-JOINED daemon thread and took the provisional layer dark for a whole session (reproduced; now a
fail-safe `_seed_counters`, and `json.dumps` moved inside the publish guard); (2) both Redis failure
paths logged at DEBUG while `live_worker` configures the root logger at INFO, so a silently wiped day
was indistinguishable from a first run (now WARNING + a `seed_failed` flag on the key); (3) the health
script never printed `as_of`, the staleness signal the key documents; (4) the liveness INFO line was
throttled on the cumulative counter, delaying it up to 30 cycles after a restart; (5) a test-count
claim in this entry was wrong. It independently confirmed the 2026-07-19 paging fix survived the C901
refactor statement-for-statement and that page-boundary ordering is strict.
quant-verifier: PASS-WITH-NOTES, 2 MEDIUM + INFO — frozen engine untouched (no Rust fixture
regeneration), the convergence contract intact (scorer region and memo key byte-identical, hot-set
membership is not a scorer input), zero DB writes so no repainting, money discipline clean. Both
MEDIUMs actioned: the market dial was deduped only against signal-bound alert sids and trimmed before
the `is_active` filter, so a slot could be spent on an already-hot or inactive stock (fixed +
regression tests); and the pinned Phase-3 decision text, which still described near-trigger as an
unqualified third source, is now amended. Its recommendation to pair a non-zero `market_max` with
`live_provisional_refresh_s = 5.0` is deliberately NOT taken yet — that is the cadence decision under
forward measurement. mypy strict then caught a third defect the reviewers missed: the tuple split left
the alert-read failure path returning a bare `set()`, so the path meant to fail OPEN would have raised
on unpacking (fixed + regression test).

### feat(phase6.8 R-track): entry-quality overlay — the SRTL-class leak (2026-08-18)

The SRTL paper loss (−₹3,565 in 10 min) and the exit-ladder replay both pointed at the ENTRY, not
the exit: trades captured only 25–48% of their peak because most *peaked then reversed* — weak
entries. Two causes the ≥70% confidence gate misses, now caught by a downstream eligibility overlay
(`app/signals/entry_quality.py`, frozen engine untouched, the `regime_guard`/`circuit_guard` pattern),
as **two independently-moded checks**:

1. **Near-single-factor signals (`entry_diversity_gate_mode`, default ACTIVE — user sign-off, the
   stated "≥2 factors, never a single indicator" hard rule).** The confluence confidence normalizes
   by the weight of the factors that *scored*, so a single factor at 0.8 reads 80% (SRTL fired on
   RSI_DIVERGENCE alone). Flag/block when `< entry_min_scoring_factors` (2) scored, or one factor is
   `> entry_max_dominant_factor_share` (0.90) of the weighted confluence.
2. **Stops too tight for volatility (`entry_sl_atr_gate_mode`, default SHADOW — a tunable threshold).**
   Flag when `|entry − SL| < entry_min_sl_atr_mult` (1.0) × ATR — a stop tighter than the stock's
   noise guarantees a fast stop-out and amplifies slippage on the huge qty risk-first sizing buys.

Both computed on the committed signal (+ ATR as-of `signal.created_at`, no look-ahead); fail-open;
verdict stamped on the order. The order-path gates (regime · circuit · entry-quality) were extracted
to a behaviour-preserving `_apply_eligibility_overlays` helper. A **shadow-report sidecar**
(`app/services/entry_quality_shadow.py`, written by `make analysis` as `entry-quality-shadow-<date>.md`)
partitions the live signal cohort by each check and reports flagged-vs-passed outcomes + an sl_atr
**flip-readiness** banner — the forward evidence to eventually activate sl_atr, gated like the regime
gate. **Evidence (read-only, on history):** diversity-flagged signals that traded netted −₹6,093 (9
trades) vs the passed set +₹3,880 (60) — single-factor signals are net-losers, so the active block is
well-founded; catches SRTL on all axes. **24 tests**; no migration. Reviews of the mode-split +
sidecar delta: **quant-verifier PASS** (1 INFO — docstring — fixed) + **bug-hunter CLEAN** (no
behavioural defect; 3 LOW test-coverage gaps — reopen-sum, sl_atr DB partition, sl_atr-active
wiring — all closed with the 4 added tests).

### feat(phase6.8): 6.8.6 — silent-feed-outage alarm (2026-08-18)

The month-long v2-era EOD outage (ingestion frozen 07-02→07-17, found by accident) is the cautionary
tale. EOD tasks self-heal (≤21d) now, but nothing LOUDLY flagged a feed gone stale — we found out by
reading §7/§8 of the daily report. New `services/feed_health.py`: for each EOD feed (`ohlcv_1d`,
`fo_bhavcopy`, `fii_dii_daily`), how many **trading** days behind is its latest row vs the last
completed EOD cycle. Trading-calendar aware — a weekend/holiday is not an outage, and a pre-EOD morning
run (before 18:45 IST) doesn't yet expect today's row. `daily_report.py` renders a loud, un-missable
"⚠️ FEED STALENESS ALARM" header above §1 when any feed is behind (a quiet "Feeds current" line
otherwise), and `check_feed_staleness` logs a `warning` per stale feed so it's loud even without the
report. A staleness check, not a metrics stack (the review's Prometheus idea is over-engineering for a
solo platform); a notification channel is deferred (none exists yet).

Reviews: bug-hunter BUGS-FOUND, both fixed — (LOW) the days-behind count under-reported by 1 when a
feed's latest row fell on a non-trading date (holiday seeded after the row); fixed to count trading
days strictly after `latest`. (LOW) the header uses wall-clock `now`, so it's stamped "as of report
generation" to disambiguate historical `make analysis DATE=…` runs. test-guardian GAPS-FOUND, all
fixed — added weekend/holiday-in-gap calendar-awareness tests, the daily-report seam integration
(build → render), the 18:45 cutoff boundary, and the log-warning. **13 tests**; no migration.

### feat(phase6.8): 6.8.5 — CA-adjust of OPEN paper positions (2026-08-18)

CA detection was quarantine-only — it removed a flagged stock from the *selection* universe but did
NOTHING to a position held through an ex-date. After a 5:1 split, a held position's `avg_entry_price`,
`qty`, `current_sl`, `current_tp` were all off by 5×, so its P&L and its risk (R) were silently wrong —
and `position_monitor` seeing the old SL against the ex-adjusted tape could false-stop-out and book a
fake loss into the 30-day go-live clock.

New `corporate_actions` table (a VERIFIED split/bonus: `action_type`, `ex_date`, `ratio_from:ratio_to`)
+ `position_corporate_actions` idempotency ledger (UNIQUE per position+action). An ex-date Celery worker
(`apply_corporate_actions`, pre-market 08:15 IST) adjusts every OPEN paper position in the affected
stock, **preserving R and reward:risk EXACTLY**: entry/peak follow the nominal ex-date price scale;
SL/TP scale by their entry-relative distance × `old_qty/new_qty`, so `|entry−SL|×qty` is unchanged even
when a fractional entitlement floors the qty (the dropped fraction is logged). `peak_pnl`/
`unrealized_pnl` are ₹ amounts invariant under a split — untouched. **Idempotent** and **catch-up**
(matches `ex_date ≤ today`, commits per position) so a missed pre-market run or a late-entered CA is
picked up on the next run rather than leaving a position mis-priced.

The ratio comes ONLY from the admin-verified row — never guessed from a price gap or parsed from
headline text (a wrong ratio silently corrupts a held position). New admin API `POST/GET
/corporate-actions` (`require_admin`). Auto-population from an NSE CA feed is deferred (a data-source
decision). New: `models/corporate_action.py`, `services/ca_adjust.py`, `tasks/corporate_action_tasks.py`
+ beat, `api/v1/corporate_actions.py` + schema; reversible migration `a7b8c9d0e1f2`. **14 tests**
(R-preservation to the paisa incl. short + fractional-entitlement, idempotency, ex-date scope, catch-up,
admin auth/404/422/409). Run `make migrate`.

### feat(phase6.8): 6.8.4 — continuous open-book MTM (carried-position gap) (2026-08-17)

Pure-reporting slice (`services/daily_report.py` only). The rich per-trade excursion narrative
(rolling MFE/MAE, chase, timing) was centred on positions opened *that day* — a swing carried for a
week got an EoD mark + heat line but no rolling write-up, so a position quietly bleeding toward its
stop over three days wasn't narrated until it closed. Now `DailyReport.carried` collects still-open
positions opened on a PRIOR day, and §3 renders the full `_render_trade_block` for each (with the open
DATE), marked to **this day's cutoff** — the excursion is bounded at `min(now, end-of-day)`, so a
carried hold's rolling MFE on day D can never see D+1's bars (no look-ahead).

The weekly `open_mtm_latest` becomes a per-trading-day series (`WeekSummary.open_mtm_series`): one point
per trading day (holiday/future-day skipped), each the gross unrealized of all positions open at that
day's cutoff, marked to the last complete 1m close ≤ cutoff (new `_open_book_mtm` / `_last_1m_close_at`).
Read-only, temporally bounded — no future-bar leakage. The row-classification loop was extracted to a
behavior-preserving `_place_row` helper.

Reviews: quant-verifier PASS (no-look-ahead verified on every mark/excursion path; SHORT/LONG mark sign
correct; `_place_row` byte-identical; frozen engine untouched). test-guardian raised coverage gaps on
`_open_book_mtm`'s None-mark/closed-boundary branches and the render date — all fixed. **27
daily-report tests** (7 new: carried rolling MFE + no-look-ahead, weekly per-day series, no-future-bar
leakage, closed/no-tape boundary, SHORT carried sign, empty-carried header absence, holiday/future skip).

### feat(phase6.8): 6.8.3 — circuit-band eligibility overlay (2026-08-17)

A long whose stock is pinned near its **lower** circuit has no buyers — its stop cannot fill at any
price, software or exchange (a structurally un-exitable trade); a short near the **upper** band is the
mirror. New downstream eligibility overlay skips entering a name whose entry sits within
`circuit_proximity_pct` (default **1.5%**) of its ADVERSE band. Frozen confluence engine untouched
(same shape as the regime gate) — and **shadow-first**: `circuit_gate_mode` defaults to `shadow`
(measure-only), flipped to `active` later on forward evidence + explicit sign-off, fully reversible.

Bands aren't on the `MODE_FULL` tick wire, so a new market-hours Celery task
(`refresh_circuit_bands`, every 15 min) fetches `lower/upper_circuit_limit` for the active NSE EQ
universe in one batched `ThrottledKite.quote()` and caches them to Redis `circuit:{stock_id}` (TTL
`circuit_band_ttl_s`=1800). The order path only **reads** that cache (sub-ms) — no external call on the
money path. **Fail-open** throughout: no cached band (task not run, market closed, bands disabled) ⇒
the entry is eligible; a missing band never blocks an otherwise-valid signal.

Every paper entry is judged and the verdict stamped on `orders.broker_payload["circuit_gate"]`
(no migration). `make analysis` gains a `circuit-gate-shadow-<date>.md` sidecar + readiness banner
(mirrors the regime-gate one): what the gate would suppress and, for the resolved subset, whether the
blocked trades were net-losing — the forward evidence for the eventual flip. New:
`app/signals/circuit_guard.py`, `app/broker/circuit_bands.py`, `app/tasks/circuit_tasks.py`,
`app/services/circuit_gate_shadow.py`; knobs `circuit_gate_mode` / `circuit_proximity_pct` /
`circuit_bands_enabled` / `circuit_band_ttl_s`. 27 new tests (guard direction + fail-open, band
parse/cache round-trip, order-path shadow/active/fail-open, shadow-report aggregation).

### feat(phase6.8): 6.8.2 — spread-aware slippage & impact model (2026-08-17)

Paper fills stop pretending every stock trades like a Nifty large-cap. When 6.8.1's live
`depth:{stock_id}` book is fresh, the adverse haircut is priced off the REAL book instead of the flat
`paper_slippage_bps`:
`clamp(half_spread + impact, floor=paper_slippage_bps, ceiling=paper_slippage_max_bps)`, where
`impact = min(paper_impact_k_bps × qty/top_qty, paper_impact_cap_bps)` and `top_qty` is the size
resting on the side we TAKE (ask for a BUY, bid for a SELL). Applied at **both** fill sites — entry
(`place_paper_order`) and exit (`close_position`).

**Why this matters:** measuring all 1666 live books at 15:26 IST on 2026-08-17 — median spread
**11.85 bps**, p75 32.79, p90 **87.02**, p99 280.11, max 518.13 — **82.1% (1367/1666) have a
half-spread wider than the flat 2 bps we were charging.** The flat model was under-charging four
names in five (~3× at the median, ~22× at p90). The 30-day paper record is the Phase-7 go-live gate,
so that overstatement was flowing straight into the decision to risk real money.

Design notes: the flat bps is a **FLOOR**, so a tick-wide book can never make a fill *cheaper* than
before — the model only ever charges more, and "no depth ⇒ byte-identical to the old fill" is exact
(the slice's canary test). Sizing↔impact is circular (risk-first sizing needs the fill; impact needs
the size) and is resolved in **one refinement pass** whose residual error is conservative by
construction. The spread is applied **relative** to the reference price rather than by filling
literally at bid/ask, because the reference may be a stop level or a drifted LTP — it stays a model,
not the book-walking SOR we rejected. Exits deliberately layer the spread on top of the
gap-through-stop worse-of price. New knobs: `paper_spread_fill_enabled` (kill switch, on),
`paper_impact_k_bps` (5.0), `paper_impact_cap_bps` (50.0), `paper_slippage_max_bps` (500.0).

`daily_report.py` gains **§9 Fill realism**: per-fill model / ½-spread / impact / total bps and the
**₹ excess over the flat baseline** — how much the old record was overstating the day's edge. Fill
telemetry rides the existing `orders.broker_payload` JSONB (no migration); pre-6.8.2 orders carry
none and are skipped, not crashed on.

**Frozen engine untouched and backtests unaffected** — depth is live-only provisional data, and the
only callers of these fill paths are the trading API and the position monitor. **⚠ Paper P&L is
non-comparable across this change; the 30-day clock needs a reset.** +27 tests (bps model incl.
floor/caps/side-correct liquidity, fail-open branches, the entry refinement pass, exits, telemetry
JSON round-trip, and the §9 surface); 200 green across the touched modules; ruff + mypy strict clean.

### feat(phase6.8): 6.8.1 — order-book depth capture (2026-08-17)

First slice of the approved **Phase 6.8 (Execution Realism & Exchange-Safety)**. The Kite consumers
already subscribe `MODE_FULL`, so 5-level depth arrives on every tick and was discarded; this captures
**top-of-book** (best bid/ask + sizes) into a new Redis KEY `depth:{stock_id}` (JSON, prices as
Decimal-parseable strings, 60 s TTL), mirroring the `ltp:{stock_id}` contract. It is **PROVISIONAL
live data** — never written to a candle, backtest, or P&L (no-look-ahead) — and its only purpose is to
make 6.8.2's paper fills spread-aware and to feed liquidity/circuit gates. New `app/broker/depth.py`
(`Depth` dataclass with `spread`/`mid`/`spread_bps`, `extract_top_of_book`, serialize/parse,
`write_depth`, `get_live_depth` mirroring `get_live_ltp`); new `depth_capture_enabled` flag (default
on, a kill switch). Wired into **both** consumers: the dormant v1 `tick_consumer` (isolated
best-effort) and — the load-bearing correction from the perf review — the **soak-proven
`live_worker`**, where the depth SET is **folded into the existing per-batch LTP pipeline (one round
trip, never a per-tick set)** so the p99 ≤ 50 ms budget is untouched. Depth is harvested behind the
same accept/stale gate as the FFI tuple (a snapshot echo never overwrites fresh depth) and is a
Redis-only concern (no DB column, no migration).

Reviews: **bug-hunter** found one MEDIUM — `extract_top_of_book` was called outside the fail-open
try and could raise on a truthy-but-non-list `depth["buy"]` (a dict → `KeyError: 0`), which would
have dropped the whole tick batch and rolled back earlier candle upserts; fixed by guarding the
indexing at the source *and* wrapping the call, with a regression test. **perf-auditor** found a HIGH
correctness issue — the initial wiring lived only in the dormant v1 `tick_consumer`, so depth would
never populate in production; fixed by wiring the pipelined `live_worker` path (measured: the depth
CPU is +21% of the tiny per-tick cost, the extra SET is +17% of round-trips only on the non-budgeted
v1 path, and 0% on the budgeted worker path where it joins the existing pipeline). +26 tests
(extraction edge cases incl. crossed/one-sided/zero/non-list books, Decimal-exact serialize↔parse,
the Redis read-back seam + TTL, and consumer/live-worker integration proving a depth-less tick leaves
the `ltp:` contract byte-identical). `make check` legs green on the changed modules: 184 tests, ruff,
mypy strict.

### docs(status): rebuild STATUS.html as the all-in-one project Compendium (2026-08-15)

Folded the deep-dive "Complete Overview" artifact (how the system works — 19 sections) INTO
`docs/STATUS.html` and brought every status section current, so one self-contained page now holds
the whole project. Four parts: **(I) the system, end to end** (architecture, lifecycle, the signal
engine + 14 factors + POWERGRID worked example, Rust core + parity, realtime, data model, canon,
constraints, workbench); **(II) where the build stands** (the paper book, the Phase-6 leak/edge, the
gate experiment → the regime gate now ACTIVE, factor attribution → the momentum ×1.5 shadow retune,
and all forward-evidence shadow layers incl. pair-trading + F&O); **(III) what's next** (a detailed
Market Context Engine build plan with recommended sequencing, and Phase 7 live-trading in detail —
RiskEngine-gate-first, broker adapter, exchange stops, Iron Condor, pair tradeability); **(IV)
reference** (glossary, ops, and the full report + doc map). Updated facts: Phase 3 CLOSED
(1246/375/86), regime gate ACTIVE + reversible, first-class ADX, 6.5 pair-trading loop, main +30.
Supersedes the stale published deep-dive artifact. Self-contained (no CDN/scripts/fonts),
theme-aware (light/dark/system), scroll-spy TOC, ASCII diagrams (not mermaid) so it renders offline
via `file://`. Verified: 28 sections, TOC↔anchors matched, zero external references.

### feat(phase6): 6.5b slices 3+4 — spread-outcome tracker + pair attribution (2026-08-15)

Completes the market-neutral shadow loop — the "does it work, and which arm" measurement half.
**Slice 3 (`pair_outcome`):** for each open shadow PairSignal, `resolve_spread` walks the spread's
z forward from the daily tape (no look-ahead; bars in date order, bounded by the validity date) and
resolves tp_first (reverts to z_exit) / sl_first (hits z_stop) / expired (validity lapses first),
writing `outcome_r` in R comparable to the single-name attribution (the ACTUAL crossing z is used,
so a daily gap through the stop books worse than −1R). The nightly task now resolves opens from the
fresh tape THEN mints. **Slice 4 (`pair_attribution` + CLI):** resolved-signal expectancy (mean R,
win%, total R) split by ARM (the df-vs-adf verdict), sector, and half-life; R winsorized ±10; a cell
n<5 is shown-not-ranked → `pair-attribution-<date>.md`. Read-only, additive, shadow-only.

quant-verifier verified the R-sign convention + frozen-z reference exact at every boundary and caught
a **HIGH: the resolution loop had no upper bound** → a cross PAST validity booked as a win/loss
(and calendar-day validity can lapse on a weekend the Mon–Fri tracker skips), biasing the A/B. Fixed
(bound resolution to the validity date; such cases mark `expired`) + regression test. Finding 2
(calendar-day validity) documented as an intentional shadow-class choice made safe by the fix.
+13 tests. **6.5b COMPLETE** (slices 1–4): the shadow evidence now accrues nightly and the
attribution report answers df-vs-adf once it does.

### feat(phase6): 6.5b slice 2 — pair-signal shadow minter (df+adf dual arms, nightly) (2026-08-15)

The market-neutral shadow layer goes LIVE. `pair_minter.mint_pair_signals` screens the universe
under BOTH arms (`df` + `adf` — the A/B) and mints a shadow `PairSignal` for each candidate at an
entry extreme (entry_z ≤ |z| < |z_stop|): long the cheap leg / short the rich, exit toward z≈0,
stop at ±3.5. De-duped against open signals. Writes only to `pair_signals` (is_shadow) — never the
single-name path or an order. Wired nightly via `app.tasks.pair_tasks.mint_pair_signals` (Celery
beat 13:55 UTC / 19:25 IST, after EOD ingestion; skips holidays) + a CLI. First live run minted 2
sensible signals (MAXHEALTH–SUNPHARMA, df z=−2.31 + adf z=−2.20, both long_spread). `PairStat`
gained `spread_last`/`z_sigma` (the frozen entry-time z reference for slice 3); `PairCandidate`
carries the filtered stock ids so the minter never re-maps symbols. +4 tests. **bug-hunter
BUGS-FOUND → all fixed:** (MED) reject entries born past their own stop — else a favourable
reversion books as a stop-loss, corrupting the very A/B this slice measures; (LOW) thread the
filtered stock ids through the screen (dual-listed-symbol safe); (LOW) guard a sub-tick σ that
rounds to 0 (a slice-3 div-by-zero). Next: slice 3 = spread-outcome tracker, slice 4 = attribution.

### feat(phase6): 6.5b slice 1 — pair_signals model + migration (additive shadow table) (2026-08-15)

The Phase-6.5b foundation: a new `pair_signals` table + `PairSignal` model for 2-leg
market-neutral pair signals (spread mean-reversion). **PURELY ADDITIVE** — migration
`f4a5b6c7d8e9` is a `CREATE TABLE` that does not touch the single-name `signals` table, the
confluence engine, the paper broker, or the live order path; the running worker + paper trading
are insulated (proven: `test_signals` stays 14/14 green). **Shadow-only** (`is_shadow` default
true): measured to outcome, never tradeable (no spread order path; an overnight pair short needs
Phase-7 futures). Both screening arms (df/adf) mint here — the `method` column — so the forward
spread P&L resolves the df-vs-adf A/B. Fields: hedge (β/α), mean-reversion (half-life, df_tstat,
adf_pvalue), the trade (direction, entry/exit/stop z, spread_entry/sigma), nullable outcome fields
(resolved by slice 3). Reversible (drop table); applied to dev + test. +2 tests. Next: the shadow
minter (slice 2).

### feat(phase6): 6.5a.3 statsmodels ADF/Johansen A/B + notional guard (2026-08-15)

User approved adding **statsmodels + scipy** ("if it gives an edge"). Added a `method="adf"`
path to `pair_screen` — Augmented DF (`adfuller`, AIC lag selection + MacKinnon p-value, gate
p ≤ 0.05) + a **Johansen** hedge ratio (`coint_johansen`, order-independent) — alongside the
numpy `method="df"` default (OLS β + plain DF), plus a **notional-imbalance guard** on both
(reject leg dollar exposures beyond 5×). **A/B on the live Nifty50 universe (with the guard):
df = 8 candidates, adf = 23, and df is a clean SUBSET of adf.** So ADF is a *wider net*, not a
clean upgrade — its extra 15 pairs are unvalidated, and raw-level Johansen produced fragile
hedge ratios (β ≈ 132) the guard catches. **Decision: `df` stays the conservative default;
`adf` is an available cross-check; df-vs-adf is resolved by 6.5b FORWARD shadow P&L, not by
argument.** +8 tests (ADF sig/insig, Johansen β recovery, adf-gate canary, notional guard).
Report of record: `docs/analysis/pairs-2026-08-15.md` (df, 8 pairs). Net edge over numpy-only:
a more rigorous test on demand + a tradeability guard — modest and honest, exactly what the A/B
was meant to reveal.

### feat(phase6): 6.5a.2 pair-universe screen — run 6.5a over the live universe (2026-08-14)

`app/services/pair_universe.py` + `scripts/pair_universe.py` → `docs/analysis/pairs-<date>.md`.
Screens same-sector active-Nifty50 pairs (a prior against data-snooped false cointegration) over
~400 trading days and ranks by DF t-stat. Read-only, mints nothing. Pure `align_closes` /
`rank_pairs` (inner-join common trading days → screen → rank) + a thin DB loader; `now` is
injectable (no hidden clock). **First live run: 12 candidates, all economically sensible** —
IT-services peers (TCS–WIPRO, INFY–WIPRO, HCLTECH–WIPRO), metals (HINDALCO–JSWSTEEL), pharma
(DRREDDY–SUNPHARMA, CIPLA–MAXHEALTH), auto (M&M–MARUTI), financials (BAJAJFINSV–ICICIBANK);
half-lives 10–19 bars, DF t-stats −2.88…−3.96, n=432. The report's VR(2)≈1 on those real
mean-reverting pairs confirms empirically why VR is informational, not the gate. +8 tests (pure
align/rank, cross-sector exclusion, untagged skip, a DB planted-pair integration test, render).
Still read-only research — 6.5b signal-minting deferred (needs the pair-signal schema decision).

### feat(phase6): 6.5a pair-trading cointegration/mean-reversion screen (numpy-only) (2026-08-14)

Foundation for Phase 6.5 (market-neutral pair-trading — regime-agnostic, earns in the choppy
tape the directional book leaks in). `app/services/pair_screen.py`, pure numpy (no
scipy/statsmodels — the lean-deps decision): OLS hedge ratio; the **Dickey-Fuller stationarity
t-stat** (the gate, vs the −2.86 5% critical value) + OU half-life from the Δs=c+λ·s_{t-1}
regression; the Lo-MacKinlay variance ratio (informational); and a trailing-window z-score (the
entry signal). Every degenerate path returns None, never a fabricated number; no look-ahead
(stats only on the passed window). **Read-only research screen — mints NO tradeable signal**
(shadow-first; the frozen single-name engine is untouched). +13 tests (math validated against
known AR(1) / random-walk properties; an exact-value canary pins the DF standard-error formula).
quant-verifier PASS-WITH-NOTES (math independently recomputed to ~1e-14; notes addressed —
design doc reconciled to the DF gate, `adf_tstat`→`df_tstat`). Design + open questions
(pair-signal schema, formal ADF/Johansen, universe scope):
`docs/phases/phase-06-6.5-pairtrading-plan.md`. 6.5b (the shadow pair-profile that mints
signals) deferred — needs the pair-signal data-model decision.

### chore(phase3): gate closed — Realtime v2 GATED 2026-08-14 (PASS)

Phase 3 (realtime tick-to-tick) formally closed at the user's instruction, Fri 2026-08-14
EOD. Full quality gate **PASS**: static clean (ruff/mypy/eslint/tsc/cargo fmt/clippy); suites
green — backend **1246 passed / 1 skipped** (incl. all 44 parity+walkforward+replay marker
tests), frontend **375**, engine **cargo 86**; regression Δ0 (parity + walkforward goldens
byte-identical, `git diff main -- app/analysis app/backtest/engine.py` empty); reviews clean
(quant-verifier ×2, bug-hunter). Exit criteria re-verified: quiet-box soak MET ×2 (p99 ≤ 50 ms)
+ 14-day clean shadow week (diffs=0, extended through 08-14). Live-tick smoke deferred
(market-closed EOD) — the soak + shadow week are the stronger realtime proof. Full verdict:
`docs/phases/phase-03-realtime.md` §Gate closure.

### ops(phase6): activate the regime-eligibility gate — REGIME_GATE_MODE=active (2026-08-14)

User decision (reversible): flip the §8-validated regime gate from shadow to active via
`REGIME_GATE_MODE=active` in `.env` + a backend/worker restart. `place_order` reads
`settings.regime_gate_mode` live, so once restarted the paper order path REJECTS transitional-ADX
(20–25) entries (fail-open on unknown regime; the daily-loss circuit breaker and sizing are
unchanged). No code change — the code default stays `shadow`; this is a deployment/config toggle,
recorded here for traceability. Preconditions were met: the first-class ADX level is built, and the
accumulated live cohort cleared the forward-evidence bar (44 suppressed trades, all three §8 metrics
improve live — expR +0.027→+0.089, total-R +2.8→+5.5, maxDD 8.8→4.7R). Monitored by the daily Flip
readiness banner; revert = `REGIME_GATE_MODE=shadow` + restart. NB: live before/after P&L is a
confounded, sample-starved comparison — the shadow counterfactual remains the rigorous read.

### feat(phase6): regime-gate forward-evidence banner in the daily analysis run (2026-08-14)

`make analysis` (via `daily_analysis._run`) now also writes
`docs/analysis/regime-gate-shadow-<date>.md` and prints a one-line **Flip readiness** banner,
so the live forward evidence for the gate flip accrues and surfaces every session instead of
needing a manual script run. Guarded: a failure prints a visible skip line and never blocks
the primary daily report.

Readiness bar (`regime_gate_shadow.forward_evidence_ready`): ≥20 resolved suppressed
(transitional) trades AND the suppressed set net-negative AND gating lifting expectancy over
baseline (n=20 = the rank floor; the §8 backtest already powered the decision at killed n=223).
The first run surfaced that the accumulated live cohort since OUTCOME_EPOCH (2026-07-19) is
ALREADY ✅ READY: 44 decided suppressed trades, all three §8 metrics improve on live (expR
+0.027→+0.089, total-R +2.8→+5.5, maxDD 8.8→4.7R, suppressed −0.061R). Whether that
(accumulated, out-of-sample vs the 2y backtest corpus but mostly pre-dating the overlay build)
suffices, or strictly-forward-only evidence is wanted, is a user call. The flip still needs
explicit §8 sign-off and is NOT done; review checkpoint stored as `FORWARD_EVIDENCE_REVIEW_DATE`
= 2026-09-15. +4 tests.

### feat(phase6): align the regime-gate shadow measurement onto signals.regime (2026-08-14)

Closes the INFO follow-up from the first-class-ADX change below. The live regime-gate
shadow (`regime_gate_shadow.measure`) bucketed the kept/killed sets by re-deriving regime
from the parsed ADX number (`adx_regime(Row.adx)`), while the active gate reads the
persisted `signals.regime` — so at a band edge the forward evidence could mis-predict what
the gate would actually suppress. Now the attribution `Row` carries `regime` (selected as
`s.regime` in the loader, `= m["regime"] or regime_from_factor_scores(fs)` — byte-identical
to `regime_guard.signal_regime`), and `measure` partitions by it. The shadow now measures
exactly the set the active gate would suppress.

Read-only and §8-safe: `measure` runs only on the live cohort; the corpus/§8 path
(`corpus_attribution`, `gate_walkforward`) and the attribution report still bucket via the
unchanged `adx_regime(raw)` and never read `Row.regime`, so no banked number moves. Live
shadow and backtest agree except at raw ADX == 25.0 exactly (measure-zero). Backtest/legacy
rows (`regime=None`) fall back to the raw-level bucket, unchanged.

+3 tests (a shadow canary where two adx=30 rows split only under stored-regime bucketing; a
NULL-regime fallback; a DB seam test that the persisted field — not a re-derivation — flows
through the loader). quant-verifier PASS-WITH-NOTES (all INFO — no number moved).

### feat(phase6): first-class ADX regime on signals — the gate's active-flip precondition (2026-08-14)

The regime-eligibility overlay (`app/signals/regime_guard.py`) recovered a committed
signal's ADX regime by parsing the frozen ADX factor's `f"ADX={x:.1f}"` prose on the
order path. That 0.1-rounding misbucketed a raw-choppy [19.95, 20) signal as 20.0 →
transitional, which in `active` mode would have wrongly SUPPRESSED it (choppy is not in
the skip-set). A money-path gate must not hang off prose rounding — the documented
precondition for flipping the gate shadow→active.

Regime is now a first-class field. `Signal.regime` (migration `e3f4a5b6c7d8`, nullable,
reversible) is persisted at each of the three signal-commit sites (`signal_service.py`
×2, `profiles/pipeline.py`), recovered from the frozen factor's DECISION BRANCH
("…weak trend…" / "…moderate…" / "…trending…") rather than its rounded number — the
branch reflects the comparison the factor made at full precision before rounding the
display, so the band-edge misbucket is gone. The gate reads `signal.regime`; legacy NULL
rows fall back to on-the-fly recovery (fail-open preserved). The frozen engine is
untouched (`app/analysis/` diff empty) — a downstream filter, the `risk_guards.py`
pattern.

Branch-recovery agrees with the backtest's raw-number `adx_regime` bucketing everywhere
except raw ADX == 25.0 exactly — a measure-zero point where the branch calls it
transitional (the factor's own inclusive "moderate" branch, the conservative direction).
The §8 / corpus / shadow evidence path is unchanged.

+9 tests: two band-edge canaries (both mutation-verified — 19.97→choppy, 24.97→
transitional), stored-field preference, NULL fallback, and a pipeline seam assertion.
quant-verifier PASS-WITH-NOTES (one INFO: align the live shadow measurement onto
`signals.regime` before the flip so forward evidence and enforcement use the identical
partition — now done in the follow-up above), bug-hunter CLEAN. **Money-path
behaviour is UNCHANGED until the gate is flipped to `active` (default `shadow` = no-op);
this only makes the future flip safe.**

### perf(provisional): score each stock once per cycle, not once per profile (2026-08-14)

The live worker logged `cycle overran the cadence: ~15000 ms > 3000 ms` continuously
through the 2026-08-14 session. Measured on the live hot set: `run_all_factors` is
**45.7 ms/window and 92.6% of the cycle** — the window LOADS were only 8% (4.4 ms × 328).
The waste was structural, not algorithmic: all five active profiles are `1d` with
identical `min_confidence` (70) and no weight multipliers, differing only by universe, so
the frozen engine ran the *same* computation up to five times per stock and again every
cycle whether or not anything had moved.

`score_pair` now takes an optional per-cycle window map and a scoring memo on `_Cache`.
The memo is keyed **per slot** — `(stock_id, timeframe, min_confidence, multipliers)` —
holding the input fingerprint (committed-window identity, forming bar, flows, block net)
its answer came from. A hit means the frozen scorer would receive byte-identical inputs,
and it is pure (no clock, no randomness, no I/O), so the memoized answer IS the current
answer, not a stale one. Keyed per slot rather than per input so a ticking forming bar
replaces an entry instead of minting one, and pruned each cycle to the stocks in scope —
the map tracks the hot set instead of growing all session. Window loads are deduped
WITHIN a cycle only: across cycles a committed bar can close, and serving that from a TTL
cache would publish a score built on a window the engine has already moved past.

Measured on the real hot set (328 pairs, 150 hot, Redis stubbed, DB read-only):

| cycle | before | after | engine calls |
|---|---|---|---|
| cold  | ~15 000 ms | **9 560 ms** | 328 → **159** |
| warm (nothing moved) | ~15 000 ms | **897 ms** | **0** |

Cycle stats now report `engine_calls` / `memo_hits` / `windows`, because `pairs_scored`
no longer tracks work done — an overrun must be able to say whether it was real.

Not a fix for the ceiling: a cycle in which every one of ~160 stocks ticks still costs
~8 s on the Python engine, so ~45 moving stocks is the most a 3 s cadence can carry.
`tradecore` scores the same window in **0.17 ms (266×, 25/25 decision agreement)** and
would put a full cycle at ~56 ms, but `score_signal(impl="rust")` refuses non-zero
FII/DII flows (live today: +720.12 / +8929.23) — closing that gap needs FlowInputs
through the PyO3 boundary plus fixture regeneration, i.e. an engine change with sign-off.

Behaviour is unchanged: same frozen sequence entered through `score_signal`, same rows,
same gate verdicts. +6 tests — profiles sharing params score once; unchanged inputs reuse
the memo; **a moved forming bar rescores** (the canary: a slot keyed on the stock alone
would freeze the preview at the bar's first tick); differing gate and differing
multipliers never share a slot; the shared window is not mutated by scoring.

### feat(phase6): 6.4 shadow-promote momentum ×1.5 — the retune A/B, forward (2026-08-14)

Turns the 6.4 in-sample corpus finding into FORWARD out-of-sample evidence. Migration
`d2e3f4a5b6c7` seeds two 1d/eod **shadow** profiles over Nifty50 with no setup gating
(pure base engine + group weight multipliers): `retune_base` (no multipliers — the
control) and `retune_momentum_x15` (momentum ×1.5 — the experiment's lead). They run on
the same nightly `eod` path as the live profiles (`run_scheduled_profiles` runs active OR
shadow) and mint `is_shadow` signals — measured to outcome by 6.1/6.2 attribution
(bucketed by `profile_key` under the shadow cohort), never tradeable (the order path
admits `status=='active'` only). No new code — a data seed on the existing parity-pinned
profile/shadow machinery; nothing promoted to live.

A/B design: both arms run the SAME pipeline with the SAME exit (rr 2), so the comparison
isolates the ENTRY selection the momentum weights drive — the forward test of the finding.
(The exit is a fixed RR, not the corpus experiment's classification-canon TP — the profile
pipeline has no canon-TP template — so the entry SET matches the experiment but absolute R
is not directly comparable to the corpus numbers; the momentum-vs-base direction is what
matters.) Promotion to an active retune stays a separate forward-evidence + sign-off step.

Verified: seed config-hashes pinned (`tests/test_strategy_profiles.py`), end-to-end smoke
(both arms mint `is_shadow` signals with the right `profile_key`/`status`), 43 profile
tests green, migration applied to dev. Reversible (downgrade deletes the seeds by key;
once shadow signals reference a profile the FK correctly blocks deletion).

### feat(phase6): 6.4 weight-retune experiment — group-weight sweep (read-only) (2026-08-13)

The first slice of 6.4 (weight tuning): a coordinate sweep of the six confluence
weight-groups (each ×0.5 / ×1.5) over the parity-clean Nifty50 daily corpus, scored on
the §8 metrics + per-fold temporal consistency. `app/services/weight_retune.py` +
`scripts/weight_retune.py` → `docs/analysis/weight-retune-<date>.md`; `corpus_rows`
gained a `weight_multipliers` param (group-keyed scaling inside the frozen scorer —
byte-identical to frozen when empty; the parity-pinned profile mechanism). Read-only;
nothing promoted.

**Result — `momentum ×1.5` is the lead candidate** (cross-engine-consistent): mean
expectancy +0.052→+0.070, total-R +41.2→+50.4, Sharpe +0.034→+0.045, maxDD 36.5R→32.4R,
beats baseline in 4/5 time folds. Runners-up `structure ×0.5` and `pattern ×0.5`.
Counter to the a-priori (per-factor) guess — *up*weighting momentum *tightens* the
confluence (742 vs 818 trades) rather than adding noise. Not promoted: a candidate for a
shadow retune profile, forward-evidence + sign-off gated. Best-of-12 in-sample selection,
so treat as in-sample until shadow confirms.

**Key structural finding:** the 6.2 leak is per-FACTOR but the only weight lever is
per-GROUP, and groups mix helping and hurting factors (momentum = RSI_DIVERGENCE +
MACD_CROSS + RSI_LEVEL; pattern = MORNING_STAR + DARK_CLOUD_COVER + EVENING_STAR) — so
group tuning is coarse and a null result would argue for per-factor weights.

quant-verifier FAIL→resolved (an "OOS" mislabel → "temporal-consistency", plus dead code,
both fixed; the lead is unaffected).

**Correction (2026-08-14):** an earlier revision of this entry flagged a "DOW_TREND
grouping bug" (Rust `structure` vs Python `trend`). That was a MISREAD. A *scoring*
DOW_TREND is tagged `["structure"]` (analysis/structure/dow.py) and Python `_factor_group`
checks tags before names, so it groups `structure` — matching the Rust engine; the
`_GROUP_NAMES` "trend" entry is dead code for it. All six weight groups are cross-engine
consistent; there is no bug. An attempted "fix" (→trend) inverted parity and was reverted
(quant-verifier caught it). Do not change DOW_TREND's group — see `dow-trend-grouping-gotcha`.

### feat(phase6): regime-eligibility overlay — the §8 gate, shadow-first (2026-08-13)

Acts on the §8-validated finding (below) WITHOUT touching the frozen engine — a
downstream eligibility overlay, following the `risk_guards.py` precedent
("analysis/ is frozen, so the guard lives here"). It reads a committed signal's
own ADX regime and, in `active` mode, rejects a paper order in the transitional
(20–25) band. **Default `shadow` — it measures, it does not suppress.**

- `app/signals/regime.py` — canonical ADX regime taxonomy (one source of truth;
  the attribution/§8 code now delegates to it, so gate and measurement can't drift).
- `app/signals/regime_guard.py` — `SKIP_REGIMES={transitional}`, fail-open
  (unknown regime → eligible; a suppressing gate must never suppress on uncertainty),
  and `order_block_reason(signal, mode)` — a strict no-op unless `mode=="active"`.
- `app/api/v1/trading.py` — the guard call in `place_order`, after the circuit
  breaker + status checks. Inert in the default config; flipping to `active` is
  one setting (`settings.regime_gate_mode`) and fully reversible.
- `app/services/regime_gate_shadow.py` + `scripts/regime_gate_shadow.py` →
  `docs/analysis/regime-gate-shadow-<date>.md` — "measure before gating": what the
  gate WOULD do to the LIVE cohort. First read (210 live signals): the suppressed
  set is net-negative (−0.061 expR) and gating lifts live expectancy −0.034→−0.016
  — consistent with the backtest; keep accruing before flipping.

quant-verifier PASS + bug-hunter CLEAN. **Preconditions for the shadow→active flip
(both documented in-code): explicit user sign-off on the §8 metric moves, and a
first-class ADX level persisted on the signal** (the shadow gate recovers regime by
parsing the frozen ADX factor's prose — fine for measurement, not for a money-path
gate). Tests: `test_regime_guard.py` + order-path seam tests in `test_trading.py`.

### feat(phase6): regime-gate §8 walk-forward — the finding holds out-of-sample (2026-08-13)

Promotes the gate experiment into a §8-grade regression. The gate experiment showed
skip-transitional wins over the *whole* corpus, but (a) omitted the three metrics
`docs/SIGNAL_ENGINE.md` §8 actually gates a merge-approval on — win rate, Sharpe, max
drawdown — and (b) scored a rule that was *mined from the same corpus* (circular).
`app/services/gate_walkforward.py` (pure, unit-tested) + `scripts/gate_walkforward.py`
→ `docs/analysis/gate-walkforward-<date>.md` close both gaps, read-only over the
parity-pinned Nifty50 daily backtest at gate-70. DRY: a shared `realized_r(row)` helper
(the +winsor(RR)/−1R unit) now backs the attribution cells, the gate experiment, and
this — byte-identical output confirmed.

**§8 metrics — every gated axis improves, all moves > ±5% (⚠ needs sign-off):**

| metric | baseline (all regimes) | proposed (skip transitional) | change |
|---|--:|--:|--:|
| win rate | 40% | 43% | +7% ⚠ |
| Sharpe (per-trade) | +0.034 | +0.097 | +186% ⚠ |
| max drawdown | 36.5R | 20.4R | −44% ⚠ |
| total-R | +41.2 | +73.8 | +79% |

**Robustness — it is not one lucky stretch, and it is not circular:**
- **Consistency:** skip-transitional wins expectancy in **5/5** sequential time folds
  (2023-09 → 2026-08). Its biggest lift is in the *worst* fold (2025-06→12: baseline
  −28.3R / −0.170 expR → −2.0R / −0.018).
- **Anchored walk-forward (out-of-sample):** learning the negative-expectancy regime on
  each expanding *past* window and applying it forward — every window independently
  re-learns "transitional" — lifts OOS expectancy **+0.067 → +0.142** (Sharpe +0.044 →
  +0.091, maxDD 36.5R → 20.4R). The rule is chosen without seeing the fold it is scored on.

Verdict: **HOLDS out-of-sample.** quant-verifier PASS (refactor equivalence proven,
look-ahead structurally disproven, frozen engine untouched, R-multiples not a money
path). Read-only — changes nothing. The engine gate itself (skip ADX 20–25) is
behaviour-changing and stays **unbuilt pending explicit user sign-off** on those §8 moves.

### feat(phase6): gate experiment — the regime gate beats a higher confidence gate (2026-08-13)

Read-only backtest comparison over the Nifty50 corpus (Rust `run_universe`) that
TESTS the 6.2 verdict before any engine change is even proposed. `scripts/gate_experiment.py`
→ `docs/analysis/gate-experiment-<date>.md`; refactor: `corpus_rows(db, min_confidence)`
extracted from `compute_corpus_attribution` so the experiment varies the gate.

**Result — skipping the transitional ADX regime is the high-value lever, not raising
the confidence gate:**

| variant | trades | win% | mean expR | total-R |
|---|--:|--:|--:|--:|
| gate-70 (baseline) | 816 | 40% | +0.052 | +41.2 |
| gate-80 | 270 | 45% | +0.142 | +37.9 |
| **gate-70 + skip transitional** | **477** | **43%** | **+0.158** | **+73.8** |
| gate-80 + skip transitional | 181 | 44% | +0.090 | +16.3 |

Skipping transitional-ADX entries (keeping the 70 gate) **nearly doubles total
captured R (+73.8 vs +41.2) and triples per-trade expectancy**, while keeping far more
trades than gate-80. Raising the gate to 80 lifts per-trade quality but cuts volume
too hard (lower total-R); combining both over-filters. → a **regime gate** (Market
Context Engine) is the recommended §8 experiment, ahead of a confidence-gate bump.
Read-only; no engine change.

### feat(phase6): per-factor attribution — which confluence factors predict edge (2026-08-13)

Extends 6.2 with one table per confluence factor: expectancy when the factor was
**supportive / against / neutral** to the trade. A factor's raw score is directional,
so it's aligned to BUY/SELL — a SELL's supportive factors are its bearish ones.
Factors that rarely fire (< n=20 non-neutral — e.g. DOW_TREND is ≈always 0) are
skipped rather than shown as one dead cell. Live and corpus share it via
`attribute_rows` (factors from `factor_scores` live, from the trade's `factors`
tuples in the corpus). Read-only; no engine change.

- **Corpus finding (816 trades): RSI_DIVERGENCE +0.43R supportive vs +0.02R neutral
  (Δ+0.41), ADX Δ+0.22, MORNING_STAR Δ+0.21 are the real edge factors; while
  DARK_CLOUD_COVER −0.40R (Δ−0.47), EVENING_STAR (Δ−0.35), MACD_CROSS (Δ−0.28) and
  RSI_LEVEL (Δ−0.27) actively HURT** (outcomes worse when they fire) — a direct
  weight-tuning signal for 6.4.
- 4 tests (direction-align canary, inclusion threshold, live + corpus factor
  extraction), canaries mutation-verified.

### feat(phase6): corpus-scale entry attribution — slice 6.2b (2026-08-13)

The statistical-power half of 6.2: run the parity-clean Rust backtest
(`tradecore.run_universe`) over the Nifty50 daily corpus and attribute the trades
through the SAME `entry_attribution` aggregator. **The frozen engine is untouched**
— the backtest already exists and is parity-pinned (`test_backtest_ext_parity.py`).

- `app/services/corpus_attribution.py`: `load_nifty50_daily` → `run_universe` → per
  trade reconstruct **regime** (raw ADX level via `tradecore.adx`, len 14, sampled
  at the decision bar to match the live loader) + **MFE/MAE** (shared
  `tape_excursion` over fill→exit) + RR + win/loss → `attribute_rows`. CLI
  `scripts/corpus_attribution.py` → `docs/analysis/attribution-corpus-<date>.md`.
- **816 trades over the corpus in ~0.6s.** The leak, with real power:
  confidence **80–89 +0.20R (n=307)** vs **70–79 −0.07R (n=434, the bulk)**;
  regime trending +0.24R / choppy +0.12R / **transitional −0.10R (n=339)**; leakiest
  ranked cell **70–79 × transitional −0.14R (n=223)**. Corrects the noisy live read
  (transitional, not choppy, is the real drag) → raise the confidence gate toward
  80 / down-weight the 70–79 band.
- 7 tests (trade→row reconstruction, status/regime/RR/guards, empty corpus),
  canaries mutation-verified. Reviews: quant-verifier PASS (shared aggregator, its
  fixes applied), bug-hunter CLEAN (reconstruction / index alignment). Read-only.

### feat(phase6): entry-quality attribution — slice 6.2a (2026-08-12)

The Phase-6 payoff: a per-cell expectancy table that turns "1 of 15 reached +1R"
into "which cells are the leak." Read-only over the terminal `signal_outcomes` +
6.1's MFE/MAE; no engine change; never feeds scoring/sizing/gating/backtests.

- `app/services/entry_attribution.compute_attribution` + `render_attribution_markdown`
  + CLI `scripts/entry_attribution.py` → `docs/analysis/attribution-<date>.md`.
- Cells by confidence · regime (ADX) · direction · setup · time-of-day (marginals
  + a confidence×regime 2-D), tradeable and shadow cohorts separate. Metrics: n,
  entered, hit_rate, reached_1r_rate (mfe_r≥1), mean MFE/MAE, expectancy_r
  (mean over decided of +RR / −1R).
- Honesty affordances: cells with n<20 are computed but flagged **not ranked** (†);
  R-means are **winsorized at ±10R** (live signals reach RR≈228 on tiny SLs —
  artifacts, not edge); expectancy is **derived from status+RR** because
  `outcome_pnl_pct` is unpopulated for the whole live cohort; regime is parsed
  from the ADX factor's explanation (the factor *score* is a poor discriminator)
  with a graceful `regime n/a` fallback.
- **First read (171 tradeable outcomes): expectancy is monotonic in regime** —
  trending (ADX≥25) +0.20R, transitional −0.01R, choppy (ADX<20) −0.15R; the
  biggest ranked negative cell is 70–79 confidence × transitional (−0.30R, n=63).
  The entry-selection leak, quantified.
- 7 tests, canaries mutation-verified (winsor · n-floor · regime-parse). Reviews
  inline — quant-verifier/test-guardian subagents are spend-limited. Purely
  additive (new files only); no existing code touched.

### feat(phase6): signal-level MFE/MAE excursion recorder — slice 6.1 (2026-08-12)

The prerequisite for entry-quality attribution (6.2). Every *terminal*
`signal_outcome` now carries max-favourable / max-adverse excursion (price +
timing + R) over its observation window, so a bad **setup** can be told apart
from a bad **stop** — first-touch tp/sl ordering alone can't.

- Extracted the excursion math into a shared `app/services/excursion.py`
  (`Excursion`, `tape_excursion`, `load_1m_bars`) — one source of truth for the
  daily report (per-position) and the new recorder (per-signal); `daily_report`
  now imports it (behaviour byte-identical, parity-checked).
- `app/services/signal_excursions.compute_outcome_excursions`: tape-derived (1m),
  anchored at the signal's `entry_price`, direction-aware (BUY→LONG / SELL→SHORT).
  **No look-ahead** — `is_complete` bars only, window `[created_at,
  min(resolved_at, validity_until)]` (a swept row's `resolved_at` is the sweep
  time, so it never widens past validity). Idempotent; R winsorized at the
  ±9999.999 column bound; per-row commit so one row can't poison the batch;
  ordered by effective window-end so a same-day-deferred row can't starve ready ones.
- Migration `c5d6e7f8a9b0` (reversible): 7 nullable columns on `signal_outcomes`
  (mfe/mae price·at·r + `excursion_computed_at`).
- Wired into the 5-min expiry sweep (after `finalize_expired_outcomes`) + a
  one-off `scripts/backfill_signal_excursions.py`.
- **Pure observability** — never feeds scoring/sizing/gating/backtests; the
  frozen engine is untouched. 11 tests, every canary mutation-verified
  (direction-map, validity-cap, is_complete filter, same-day defer, poison-pill,
  effective-end ordering).
- Reviews: quant-verifier PASS; bug-hunter (starvation / poison-pill / count
  findings fixed + regression-tested); test-guardian was spend-limited, so its
  checks were run by hand (all canaries mutation-proven).

### feat(seasonality): per-stock monthly return-bias context statistic (2026-08-11)

First build off the 2026-08-11 competitor review
(`docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md` §6). For each stock, the
per-calendar-month return distribution (n years, % up, average / best / worst)
is computed **on-read** from the ingested daily OHLCV — no new table, no
migration (mirrors `fo_analytics`). Surfaced as a "Seasonality" tab on the stock
detail page.

- Service `app/services/seasonality.py` + `GET /seasonality/{stock_id}`
  (`app/api/v1/seasonality.py`, schemas `app/schemas/seasonality.py`).
- **Context / discovery only** — never a confluence factor, never emits a signal
  (sits nowhere near the ≥70% gate). **No look-ahead:** only completed months
  strictly before the current IST month are counted (IST, not UTC — the
  month is bucketed from `ts.astimezone(Asia/Kolkata)`), only `is_complete`
  candles feed it, and a monthly return is computed only between adjacent
  calendar months so a data gap can't fabricate one. Sample size (`n`,
  `years_covered`) is reported honestly and the UI **de-emphasises thin cells
  per-month**: months with fewer than 5 years of data drop the profit/loss
  colour (glyph still shows direction), carry a `*` marker, and trip a footnote —
  so a 1–4 year cell can't read as a reliable edge.
- Frontend: `SeasonalityPanel` + typed `lib/api/seasonality.ts`, wired as a tab
  on `StockDetailPage`. Table-shaped loading skeleton, themed `Button` retry
  (focus-visible ring), and ▲/▼ glyphs on Avg/Best/Worst.
- Tests: 12 backend (stats math incl. mixed up/down partition, gap handling,
  current-month exclusion + IST-boundary bucketing canary, incomplete-candle
  filter, last-trading-day month-end, zero-prior-close guard, auth / 404 /
  empty), 5 frontend (render, loading skeleton, empty, error, thin-cell flag).
- Review: quant-verifier PASS (look-ahead / money / isolation verified clean);
  test-guardian + ui-reviewer findings all fixed (hollow IST canary made real
  via mutation, untested guards covered, per-cell thin affordance implemented).

### docs: competitor/reference-tool review → screener-scans / fundamentals / seasonality plan (2026-08-11)

Reviewed 66 screenshots (Zerodha Kite+Streak · Tijori · Sensibull · MoneyControl)
the user captured in `~/zerodha money control/`. New
`docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md`: verdict per source, ~20 MoneyControl
scan formulas transcribed and mapped to our `SavedScreen` seam, the four
quality-score formulas (Altman Z / DuPont / Graham / Ohlson), and a seasonality
spec. F&O analytics (PCR/MaxPain/IV-rank/VIX §7) are already ours — confirmation,
not gap. Fundamentals + quality scores + seasonality are greenfield; only
seasonality needs no new data. Keystone blocker: `stocks.market_cap_cr` has no
writer (NSE publishes no free shares-outstanding source) and every fundamental
scan thresholds on MarketCap — a data-source decision is required first. Backlog
folded into `docs/PHASES.md` (Phase 6 scan-catalog harvest; Market Context Engine
fundamentals / quality-scores / seasonality). Docs + memory only; no code change.

### quant-verifier round on the shadow layer — one CRITICAL, three HIGH (2026-08-08)

The review of `e3003b9` returned **FAIL**, and every finding that mattered was
real. Recorded in full because the CRITICAL is a design lesson, not a typo.

- **CRITICAL — shadow results were counted as real performance.**
  `/analytics/outcomes` joins outcomes → signals → profiles and groups by style
  with no shadow filter, so every shadow outcome landed in the intraday
  hit-rate/entry-rate/avg-return that StylePage renders as "Tracked outcomes".
  Shadow profiles are *precisely* the ones that have not earned activation, so
  this dragged the headline numbers toward a strategy nobody trades — corrupting
  the evidence the shadow layer exists to produce. Proven by an executed probe
  returning `total=1, losses=1, hit_rate=0.0` for a single shadow signal.
- **The deeper half: `status` cannot carry provenance.** `status` is a LIFECYCLE
  field — the sweeper overwrites it with `'expired'`, and expiry is exactly when
  an outcome finalises. So filtering `status <> 'shadow'` would have excluded
  the handful still live and counted the *entire finalised history*. New
  immutable **`signals.is_shadow`** (migration `b4c5d6e7f8a9`), written once at
  mint, never rewritten; `analytics.py` filters `is_shadow IS FALSE`.
  `strategy_profiles.status` was no substitute either — it is mutable, so
  activating a profile later would retroactively relabel its whole shadow
  history as tradeable.
- **HIGH — the 09:16 IST beat scored the PREVIOUS session.** `crontab(hour="3-10")`
  fired at 03:46 UTC, which passes the session guard but precedes the day's
  first 15m close (09:30 IST). `_load_window` therefore returned yesterday's
  15:15 bar, the setups passed on it (a stale close sits far above yesterday's
  PDH), and the resulting signal took the one-per-(stock, profile) dedup slot —
  suppressing every genuine run for the rest of the day. Window narrowed to
  `hour="4-9"` (09:31–15:16 IST) **and** `stale_decision_bar_day()` now rejects
  any decision bar not from today's session, which also covers the case where
  the live worker never started because the Kite token wasn't refreshed.
- **HIGH — the 15:16 IST beat minted 24-hour "intraday" signals.**
  `compute_validity_until` rolls the deadline forward a calendar day past 09:45
  UTC (correct for the nightly EOD caller), so a late beat produced a signal
  spanning the overnight gap — on a Friday, expiring on a **Saturday** — that
  also held the dedup slot into the next session. `past_intraday_cutoff()`
  refuses it, leaving `expiry.py` untouched for the EOD path.
- **MEDIUM — the alert shadow stamp failed OPEN.** `sig.get("shadow", False)`
  defaulted a missing key to *tradeable*, drawing a Buy button — the one
  direction where being wrong is dangerous, and the opposite of
  `signal_status_for`'s fail-closed contract. Now `is not False`.
- **MEDIUM — positional row access.** `r[8]` for the shadow flag while eight
  siblings stayed positional: inserting a column anywhere in that SELECT would
  silently re-map it. Now named access throughout `_active_signals`.
- Both new guards are pure predicates (`stale_decision_bar_day`,
  `past_intraday_cutoff`) so they test without clock manipulation. **A first
  draft used a minutes-based age threshold and passed — only because it was 3am;
  the same tests would have failed at 10am**, since the fixtures stamp bars with
  today's date. Replaced with an IST trading-date comparison, which is the actual
  invariant.
- Migrations exercised down-twice-and-up for real; the previous commit's
  "downgrade-exercised" claim had no test behind it, which the review flagged.
- Tests: `+7` (shadow leak with a real profile row, tradeable evidence still
  counted, provenance surviving expiry, the stale-bar rejection with its
  still-mints counterpart, and four pure cutoff cases including the Friday →
  Saturday one).

### §8 — intraday shadow health in the daily report (2026-08-08)

Same reasoning as §7 F&O engine health, one step earlier in the funnel: the
shadow layer exists to replace a negative backtest verdict with forward
evidence, so **a silent layer is a failed layer** — "no evidence yet" and
"evidence says no" must never look the same. `make analysis` now reports, per
shadow profile, how many signals it minted, how many resolved, W/L, and when the
count is zero, WHY — distinguishing "not a trading day" from "NO bars for the
day, the live worker produced nothing (check the Kite token ritual)" from "ran
but nothing cleared the confidence gate". Attribution is checked in failure
order, because blaming the wrong gate is what turns a dead worker into an
apparent strategy failure.

### Intraday activation — shadow profiles, and the scheduler that never existed (2026-08-07)

Third slice of "Intraday activation + v1 surface uplift". The Intraday menu had
never produced a single signal, and could not have: the three profiles were
`inactive`, **and nothing scheduled them either way**.

- **The intraday schedules had no caller.** `nightly_suggestions` only ever ran
  the `'eod'` schedule; `on_close_suggestions` was still a Phase-3 stub
  (`return {"status": "stub"}`). So `intraday_15m` and `time_0925` profiles could
  never fire regardless of status — the menu was structurally unable to
  populate. New `intraday_suggestions` task + beat entries at **:01/:16/:31/:46**
  (one minute after each 15m bar closes, so the scored bar is COMPLETE — scoring
  a forming candle is the look-ahead violation the committed layer exists to
  avoid) and **03:56 UTC / 09:26 IST** for the single-shot 09:25 screen. The
  stub's design — one task per stock per candle-close event — was dropped
  deliberately: the profiles score completed bars and bar boundaries are known
  in advance, so a beat is the same computation without depending on the tick
  pipeline being healthy. The task carries its own `is_market_session` guard,
  authoritative over the necessarily-coarse crontab window (the same split that
  fixed the position monitor's 08:30 pre-open beat).
- **Shadow is the third profile state.** Walk-forward says the trio should NOT
  be activated — all three are negative risk-adjusted (pdh_pdl −1.06 Sharpe,
  orb_15m −0.60, gainer_925 −0.86 at 32% max drawdown; gainer_925's headline
  +56.2% is **+0.004% per trade** over 12,935 trades, i.e. noise before costs,
  and it was already flattered ~2× by a look-ahead fixed in 8c-4). But leaving
  them off produced no evidence either, so the backtest verdict was never going
  to be revisited. `status='shadow'` runs a profile on its **real** schedule and
  measures every suggestion to outcome, while keeping it untradeable.
  - **Untradeability is enforced by code that already existed:** the order path
    admits `status == "active"` only, so a shadow signal is rejected there
    (409, "Signal is shadow, not active") without a new flag anyone must
    remember. Asserted by a test that posts an order directly at a shadow
    signal — the UI merely declines to draw a button; this is the seam.
  - Shadow signals are likewise absent from `/suggestions/{style}` and
    `/signals/active`, both of which already filtered on `'active'`.
- **Three gates had to learn about shadow, and each was a real bug if missed:**
  - The **expiry sweeper** swept `'active'` only — shadow signals would have
    lived forever, their outcomes never finalising (so the forward evidence
    never closes out) and every 15-minute run stacking another undead row on the
    same (stock, profile).
  - **`live_levels`** tracked `'active'` only — but its entry/SL/TP touch levels
    are what drive `signal_outcomes`, so excluding shadow would have produced
    suggestions nobody ever scores, the exact opposite of the point. Shadow
    signals are now tracked and carry a `shadow` flag through alert metadata.
  - The **supersede guard** was unscoped: a shadow run could have superseded a
    live tradeable signal. Each layer now dedups only against its own status,
    with a canary asserting a shadow run leaves an active signal alone.
- **Alerts stay on the stream but are stamped.** Shadow alerts must still flow —
  that is how outcomes record — so `_publish_alerts` marks them `shadow="1"`
  (Redis hash fields are strings, never bools) and the UI drops the trade
  affordance for them, showing "shadow · not tradeable" instead of a button that
  would 409.
- Migrations (both reversible, downgrade exercised): `strategy_profiles.status`
  gains `'shadow'`; a partial unique index mirrors
  `uq_signals_active_per_profile` for the shadow layer (without it the
  one-live-suggestion-per-(stock, profile) rule simply would not exist in
  shadow); the three intraday profiles move `inactive → shadow`. `signals.status`
  needed no DDL — it carries no CHECK constraint.
- `signal_status_for()` **fails closed**: an unrecognised profile status mints a
  *shadow* signal, never a tradeable one, so a typo in a status column cannot
  become live suggestions.
- Tests: backend **+23** (`test_shadow_profiles.py`) weighted at the safety
  properties — order-path rejection, absence from both feeds, sweeper expiry,
  `live_levels` tracking, the two layers not colliding, fail-closed status
  mapping, and the scheduler picking up shadow profiles on intraday schedules
  while ignoring `inactive` ones and not bleeding `time_0925` into the 15-minute
  beat. Frontend **+6**: `parseAlert` string-flag handling (including the
  classic Redis trap where `"0"` and `"false"` are both truthy), and a shadow
  alert rendering no trade button while a normal one still does.

### v1 surface uplift — watchlist prices, screener honesty, an honest empty state (2026-08-07)

Second slice of "Intraday activation + v1 surface uplift". Three pages that
worked but under-delivered, each for a different reason.

- **Watchlists showed no prices.** The page rendered symbol + company name and
  nothing else — the only live surface in the app without quotes, while the
  backend had been fanning ticks out *per watchlist* since Phase 3. It is now a
  real table with live LTP, change % and previous close, on the standard live
  stack: `useLiveQuotes` (rAF-batched), `PriceCell` for the flash, memoised rows
  so a tick re-renders one row rather than the page, and `formatChange`'s glyph
  so direction is never carried by colour alone.
  - `WatchlistItemRead` gains **`prev_close`** — the last **completed** daily
    close, which is what a live LTP is a change *against*. `is_complete` is the
    load-bearing word: today's daily bar does not exist until EOD ingestion
    (~18:40 IST), so during a session this correctly resolves to yesterday's
    close. Scoring a live price against the bar that same tick is building would
    compare a price to itself and report every stock as flat.
  - One `DISTINCT ON` query for the whole list, not a lookup per row — a
    watchlist is a list, and per-item would be an N+1 on every page load.
  - Null-safe throughout: a stock with no daily bar (the ~268 series-moved names
    that receive no EOD bars) renders "—", never a fabricated 0.00%, and a zero
    previous close cannot divide.
- **The screener silently returned nothing on sparse columns.** A filter on a
  mostly-null field matches almost no rows, which reads as *"no stocks match
  your criteria"* when the truth is *"this data isn't loaded"* — sector sat at
  59 of 2,333 stocks for months behind exactly that ambiguity. New
  **`GET /screener/fields`** returns the catalog with a **counted** `populated`
  per field, and a filter row now says "Only 500 of 2,365 stocks have a sector —
  the rest cannot match this filter." Counted per request, never hardcoded: the
  number moves on every reseed. An `available=False` field reports `populated:
  null` rather than `0`, because "0 of N have this" implies data that merely
  hasn't loaded when the feature does not exist.
  - The CSV export **drops the market-cap column** rather than exporting an
    always-empty one: nothing populates `stocks.market_cap_cr`, so it was a
    promise the data cannot keep. The screener field itself stays listed and
    honestly reports `populated: 0`.
- **The Intraday page blamed the clock for being empty.** Every style showed
  "Fresh suggestions are generated nightly after EOD (~7:30 PM IST)" — true for
  the EOD-scheduled styles, false for intraday, whose three profiles are
  inactive because walk-forward returned **negative risk-adjusted** returns for
  all of them (pdh_pdl −1.06 Sharpe, orb_15m −0.60, gainer_925 −0.86). An empty
  table that blames the schedule reads as a broken pipeline; the real reason is
  a deliberate refusal to suggest trades from a profile that has not earned it,
  and the page now says so. F&O likewise explains the IV-rank gate rather than
  citing a nightly run it does not use.
- Tests: frontend 353 → **364** (watchlist live prices incl. null/zero
  prev_close and the missing-tick case; screener coverage warning present when
  sparse, absent at full coverage, and reflecting the live count; the intraday
  reason shown and the EOD text NOT shown); backend watchlists 10 → **14**
  (latest completed close, incomplete bar ignored with a canary, null when no
  bar, no cross-stock smearing) and screener **+5** (auth, measured counts,
  `available=False` → null, market cap reported empty, inactive rows excluded
  from both sides of the ratio).

### Fixed — the stock master had no real company names, and reseeding was broken (2026-08-07)

First slice of "Intraday activation + v1 surface uplift". Went in for sector
coverage; found two larger defects underneath it.

- **No stock had a correct company name.** `EQUITY_L.csv` carries a
  `NAME OF COMPANY` column that `fetch_equity_universe` never read, so
  `company_name` was the ticker itself for **2,274 of 2,333** active stocks —
  and for the 59 index members it was the **sector**, because the caller indexed
  a `{symbol: industry}` map as if it held names. ADANIENT was named
  "Metals & Mining". That string is what the screener, watchlist search, stock
  detail and CSV export have all been rendering. `company_name` was also missing
  from the upsert's `DO UPDATE SET`, so a reseed could never repair a name once
  written — both fixed.
- **The reseed had silently stopped working.** The upsert conflicts on
  `(symbol, exchange)`, but `uq_stocks_isin` must hold too; when NSE renames a
  ticker, the CSV brings the NEW symbol carrying the OLD row's ISIN, so the
  insert dies on the ISIN constraint and the **entire run rolls back**. Six real
  renames were blocking it: AMIRCHAND→AEROPLANE, ASHIKA→ASHIKAG,
  LYPSAGEMS→AURUS, GUJGASLTD→GUJENERGY, MIRCELECTR→ONIDA, VISASTEEL→VISACHROME.
  New `plan_renames()` resolves them **in place** — a rename is the same company,
  so the row keeps its id and with it every OHLCV bar, signal and position
  pointing at it (GUJENERGY kept 738 daily bars, ONIDA 376). Inserting a fresh
  row would have stranded that history under a ticker NSE no longer publishes.
  When BOTH tickers already exist, choosing the canonical history is not a seed
  script's call: that is reported as a collision, the incoming row is written
  without its ISIN, and nothing is merged. Renames and collisions both print in
  the run summary — they change what a ticker MEANS, so they are never silent.
- **Sector source widened to Nifty 500** (`ind_nifty500list.csv`), the widest
  free flat CSV NSE publishes. Coverage **59 → 500**; market cap stays unpopulated
  (NSE publishes no free shares-outstanding source, so the screener field remains
  honestly unavailable). An NSE outage narrows coverage instead of failing the run.
- Measured after reseed: sector 59 → **500**; `company_name` = ticker 2,274 → **2**;
  `company_name` = sector 59 → **0**; inactive rows **15 → 15**, so the 2026-07-17
  T2T deactivation ruling survived untouched (`is_active` is deliberately absent
  from the update list).
- Tests: new `tests/test_seed_stocks_renames.py` (15) against a pure
  `plan_renames()` — all six real renames pinned, new listings and ISIN-less
  symbols excluded, both-tickers-alive reported rather than merged, and
  determinism under row-order flips. One of them caught a bug in the first draft:
  two symbols claiming one ISIN planned two UPDATEs against the same row id, the
  second silently overwriting the first.

### Fixed — Journal and Portfolio were unreachable; the Filings page 422'd on its own default (2026-08-07)

Both were caught from a pasted server log, not from the suite. That is the story
of this entry: every one of these failures is at a seam the tests mock away.

- **Journal and Portfolio 401'd on every request — the features were entirely
  unusable against a live backend.** `lib/api/journal.ts` (8 calls) and
  `lib/api/portfolio.ts` (9 calls) never took a token parameter, so no request
  from either module carried an `Authorization` header. The access token lives
  in memory; `credentials: 'include'` only sends the refresh **cookie**, which
  `get_current_user` does not accept — so this was a hard 401 on list, create,
  update, delete, screenshot upload and net-worth alike. Page tests mock the API
  module, so 100% green tests coexisted with two dead features (the same lesson
  as the 453-green-tests / dead-live-pipeline incident).
  - **Fix is in the client, not the 17 call sites:** `request()` now falls back
    to the auth store's token when none is passed, making the token the API
    client's business. An explicit argument still wins, so every existing module
    is untouched. `api.anon.post` opts login and refresh out — they mint the
    token and must never send a stale one.
  - Tests: new `src/test/apiClient.test.ts` (8) exercises the module→client seam
    through a mocked `fetch` — store fallback, explicit-token precedence, no
    header when logged out, login/refresh staying anonymous, and the exact
    journal/portfolio calls from the log carrying the bearer. **5 of the 8 fail
    on the old client** (verified by reverting).
- **`GET /filings/recent` rejected the Filings page's own default view.** The
  page's date pickers default to 7 days, which spans **8 calendar days** once the
  end day is included → `hours=192`, over the endpoint's `le=168` cap → **422 on
  every load**, and the page rendered its empty state. The cap is now one year,
  matching the sibling `/by-stock` endpoint's `days` cap.
- **The same request was silently discarding the end date.** The from/to pickers
  were being flattened into a single look-back window, so a range ending last
  month returned everything since then. `/filings/recent` now accepts
  `start_date`/`end_date` as **inclusive IST calendar days** (resolved to UTC
  instants for the tz-aware column, end day inclusive through 23:59 IST); the
  page sends the range it actually shows. `hours` remains for the dashboard
  panel's 24h view.
- Riders in the same handler: the total count was pulling every matching row id
  into Python to call `len()` on it — now a database `COUNT`; and the page's
  default range was built with `toISOString()`, which yields the **UTC** day and
  so reads a day early before 05:30 IST.
- Tests: `tests/test_filings_api.py` 14 → **19** (the 192-hour default accepted,
  the year cap still enforced, both ends of a date range bounded, the end day
  inclusive for an evening IST filing, reversed ranges rejected);
  `src/test/FilingsPage.test.tsx` asserts the request carries dates and no
  `hours`. Backend regressions carry canaries that fail on the old handler.

### Daily analysis — §7 F&O option-selling engine (2026-08-07)

- **The daily report had zero F&O coverage**, so the two calibration decisions taken the same day (`docs/phases/phase-04-fo-suggestions.md` §9.3 weeklies-excluded, §9.7 stale-vol-gates-warn) could only be reviewed from recollection. Both were taken on an *argument*, not a measurement — reviewing them needs a day-by-day record. And since the engine returning `[]` was already the ambiguity that hid a month-long outage, "no suggestions today" must never again be the only artifact.
- `make analysis` now writes **§7** into `docs/analysis/<date>.md`: per allowed underlying, a verdict (produced / dark / no data), the expiry + DTE actually priced, the forward source, and **the reason** — attributed by re-walking the engine's own gates **in the engine's own order** via its own helpers. Plus explicit call-outs when the monthly-only policy is what went dark, when the vol gate ran on stale evidence, and when F&O bhavcopy is behind.
- Window logic is now shared rather than duplicated: new `fo_suggestions.in_window_expiries` backs both `_pick_expiry` and the report, so a report that audits the engine cannot drift from it. (`_pick_expiry` is otherwise unchanged.)
- **Gate ORDER turned out to matter, and a test caught it.** The VIX veto fires *before* expiry selection, so a vetoed day can still have a perfectly pickable expiry; attributing off "did we pick an expiry" reported a risk-off stand-down as "nothing qualified" — the exact misattribution the section exists to prevent. `_fo_blocked_reason` now returns `None` only when every gate genuinely passed.
- **First real reading (2026-08-05 / 08-07): all three indices dark on IV-rank 15–29 against the 50 sell gate.** Vol is cheap and the engine is correctly refusing to sell cheap premium — so *neither* open ruling is currently the binding constraint. It also correctly flagged F&O bhavcopy running 2 days behind.
- Tests: `tests/test_daily_report.py` 10 → **16** — the monthly-only policy named when it goes dark; the walk reaching the monthly when a weekly leads (no false policy flag); a VIX veto distinguished from a genuine no-trade; the stale-data flag; no-data reported rather than a silent row; and the seam proving §7 reaches the rendered Markdown on a day with no equity trades.

### v2 Phase 5 — UI overhaul (in progress, started 2026-08-06)

- **Review round + the 60 fps budget MEASURED — slice 5.5 (2026-08-06).** bug-hunter and ui-reviewer run against the phase diff; every finding in new code fixed with a regression test.
  - **The F&O page would have shipped with every Greek null.** `futures_basis` required a future with the SAME expiry as the option — but index options are **weekly** and index futures **monthly**. Verified against the live dev DB: on the latest recorded NIFTY day only **3 of 12** option expiries have a futures row, and the *nearest* expiry (which the page defaults to, 226 legs) has none. Spot keyed the same way, so `atm_strike` was null too and the ±N strike window silently degraded to the whole chain. New `fo_analytics.forward_for_expiry` uses an exact-expiry future where one exists, else implies the market's own carry from the nearest future expiring on/after the option (`b = ln(F_fut/S)/T_fut`, `F_opt = S·e^(b·T_opt)`), and reports which via a new `forward_source` field so the UI can never imply a future that isn't there; `spot_on_day` recovers spot from any contract's `underlying_close`.
  - **An intraday chain was priced against the previous day's futures close** (EOD bhavcopy only lands ~18:45 IST), skewing every IV and delta while the provenance line implied same-day inputs. The forward lookup is now pinned to the chain's own day and stands down instead of guessing.
  - **`chain_day` derived a trading day from a UTC instant** — anything after 18:30 UTC dated the ladder a day early, putting `dte` out by one. Now converted to IST.
  - **`hit_rate`/`entry_rate` are FRACTIONS from the API** but were rendered with `formatPct` and toned against `>= 50`, so a 60% hit rate displayed as **"0.60%"** and was painted loss-red for *every possible value*; the shipped test hid it by mocking percent-shaped data. Also the honest-sample gate used `sample` (which includes `no_entry`) while the hit-rate denominator is `wins+losses` — 2W/2L beside 30 no-entries passed a `>= 20` check. Both fixed, with canaries.
  - **`useLiveQuotes`:** a symbol dropped while the socket was down was never pruned (the diff ran against `subscribedRef`, which a close empties), a tick already buffered for a dropped symbol was re-inserted by the next flush, and a stale socket's late close could clobber the live one. Handlers now close over **their own** socket — the first fix used a shared `let` that reconnect reassigns, so the guard passed anyway; the regression test caught it.
  - **`StylePage` rows are memoised** — `quotes` is component state, so every rAF flush re-rendered all visible rows and all 11 cells; `PriceCell` isolates the flash, not the render.
  - **Accessibility/theme:** daybreak `--color-warning` was amber-600 = **2.91:1** (below WCAG AA) while carrying the safety copy ("chasing N% past entry") → amber-700, 4.58:1, contrast verified independently before touching a shared token. The ladder's two-row header repeated every label per side (a cell announced "OI 1,25,000" with no call/put) → `scope` + side-qualified `sr-only` names, and the em-dash that was serving as the Strike column's accessible name is gone. Plus skeletons instead of a sentence while candidates load, retry on candidate/analytics failures, an analytics error that no longer silently deletes the whole six-tile strip, `aria-label` on all four F&O pickers, `formatInt` for a share count (`formatINR` rendered "1,250.00", which reads as a price), and `formatCurrency` instead of hand-glued `₹`.
  - **The sticky table header did not stick — found only in the browser.** `Table` wraps itself in `overflow-x-auto`, and CSS promotes the other axis to `auto` too, so that wrapper became the containing block for `position: sticky`; being unbounded it never scrolls, so the `<thead>` travelled with the content. Measured in Chrome: scrolling the viewport 800 px moved the header to `top: -761` — off screen, losing the column headers on exactly the long tables that need them. `VirtualViewport` now neutralises the inner wrapper and owns both scroll axes; re-measured after the fix the header holds at the viewport top. The F&O ladder, which had no bounded scroll container at all, now uses one. Static review had cleared this — jsdom has no layout, so only a real browser could settle it.
  - **60 fps budget — MEASURED and MET.** New browser harness (`frontend/perf/run-bench.mjs` + `perf/live-table-bench.html` + `src/perf/`) drives the REAL hooks and components in **Chrome 151** over the DevTools Protocol with **zero new dependencies** (Node 22's built-in WebSocket — this box cannot install packages). React `<Profiler>` commit **p99 8.8 ms @ 50 rows/500 tps · 7.8 ms @ 300/2,000 · 7.6 ms @ 1,000/5,000**, against a 16.7 ms budget; frame cadence flat 60 Hz; **zero** jank frames in the realistic profile. Row count and tick rate barely move the cost, which is the windowing and rAF batching earning their place. Method, caveats (headless; stubbed socket) and reproduction in `docs/PERFORMANCE.md`.
  - Knowingly deferred and recorded in the phase report §8: the daybreak `--color-bull`/`--color-profit-bg` badge pairing (3.32:1) is what `StatusPill` prescribes app-wide, so it is a design-system decision; and `components/ui/drawer.tsx` (pre-existing) lacks a Portal and focus trap.
- **Live Signals feed + alert centre — slice 5.4 (2026-08-06).** New page at `/live-signals` (sidebar: Styles group): the full-width feed to leave open during a session, where the topbar bell is only a glanceable summary. Every tick-trigger alert with its trigger, level, style and price; server-side style and watchlist scoping; client-side lenses (entry signals / level crosses / stop-target proximity / volume bursts); the **anti-chase guardrail** (don't-chase price, and a warning once the trigger already ran past a third of the trade's risk beyond entry); and one-click paper trade on the alert's originating signal through the same order path (risk-first sizing from the actual fill + the non-disableable circuit breaker). Labelled **PROVISIONAL** — alerts are at-most-once and the stream tails new entries only; nothing here creates or gates a signal.
  - **Opt-in desktop notifications** (`useBrowserNotifications`): permission is **never** requested without a user action (browsers penalise unsolicited prompts and a denial is effectively permanent), the choice persists, a **blocked** permission renders as a disabled, explained control rather than a dead toggle, and a browser with no Notification API says so. **Bursts coalesce** — the open-auction batch can fan out dozens of alerts in one flush, so anything over 3 becomes ONE summary notification instead of dozens of popups. Alerts already seen never re-notify, and the batch present at mount (or when the toggle is switched on) is marked seen **without** notifying, so enabling it never dumps the backlog. Notifies regardless of tab visibility on purpose: the case that matters is the browser sitting behind an IDE or chart window, where `document.hidden` is false.
  - **`useAlertContext` extracted** from AlertBell (sid → symbol, signalId → signal, both `staleTime: Infinity` since neither changes for an alert's life) so the bell and the feed share one implementation rather than two copies of the same joins.
  - **`SimpleSelect` now accepts `aria-label`** — its trigger renders only the selected value, so an unlabelled select was an unnamed combobox to assistive tech. Both new selects on this page are labelled.
  - Rows are **memoised, not virtualised**, and the reason is recorded: `useAlertStream` caps retention at 100 alerts, so windowing would add machinery for a list that cannot reach the size where it pays off; the real live-update cost is re-rendering rows on every flush, which memoisation fixes.
  - One real robustness bug fixed while testing: `"Notification" in window` is true even when the property exists set to `undefined`, and reading `.permission` off that throws — the probe now checks the value's type.
  - Tests: `src/test/LiveSignalsPage.test.tsx` (13) — row contents, PROVISIONAL label, chase warning both sides of the limit, paper trade in the signal's own direction, kill-switch disables trading, source filtering, server-side style scoping, connected-vs-offline empty states, auth-failure state, and the three notification permission states. `src/test/useBrowserNotifications.test.ts` (11) — no auto-prompt, opt-in persistence, denial, silence at mount, notify-after-mount, burst collapse at the boundary and above it, no backlog dump on enable, no double-notify, and surviving a throwing constructor. Sidebar link counts updated for the new nav entry. Frontend **304 → 328**; eslint + tsc clean.
- **Style pages v2 — slice 5.3 (2026-08-06).** The style pages were a single flat table; they now carry the engine's own structure.
  - **Committed vs forming, visually separate.** The suggestions table is badged **COMMITTED** (scored on complete candles, valid from the next one — the tradeable layer, and what the one-click paper trade acts on); the **provisional** leaderboard sits below it in its own panel, labelled as converging at candle close. Conflating the two is a correctness problem, not a cosmetic one, so they can't share a table. `ProvisionalPanel` gained an optional `style` prop that locks it to one style and hides the tab strip — the dashboard keeps the full tabbed leaderboard, but a style page must not offer navigation to a style the page isn't about, and the locked panel subscribes to only the style it renders.
  - **Per-style stats header** (`StyleStatsHeader`) from the real `/analytics/outcomes` data — hit rate, entry rate, avg return — plus the live shape of the list on screen (count, buy/sell split, avg confidence). **Sample size sits next to every rate**, and a rate computed from fewer than 20 tracked outcomes renders greyed with "n=… — too small to read" instead of coloured as good or bad: the 08-03→05 evidence (1 of 15 trades reached +1R) is exactly the regime where a hit rate off a handful of outcomes looks like an edge and isn't. Entry rate is surfaced deliberately — a low one means entries are priced too far away, which is the current binding constraint.
  - **Factor-breakdown drawer** (`FactorDrawer`) — the confluence engine is the edge and deliberately not a black box: per-factor weight, score, **weighted contribution (weight × score, matching how the scorer aggregates)** and the engine's own explanation string, ordered by absolute contribution so what actually drove the decision is at the top rather than buried alphabetically. Plus the plan (entry/SL/TP/qty/**reward:risk**/profile version/validity) and the setup trigger. Opened from a **button on the symbol, not a clickable row**, so it is keyboard-reachable with a visible focus ring.
  - **Live LTP column** via `useLiveQuotes` v2 + the existing `PriceCell` flash (cell-level, so a tick doesn't re-render the row), and the table is **virtualized** through `useVirtualRows` — windowing engages above 200 rows and stays off below it.
  - Tests: `src/test/StylePage.test.tsx` 7 → 16 — committed/forming separation, locked provisional panel (no tablist), reward:risk from the plan, drawer contents incl. signed contributions and contribution ordering, stats header from tracked outcomes, the small-sample refusal, live LTP placeholder (never a stale 0), and **virtualization proven both ways** (300 rows → a window plus spacer rows, 12 rows → all 12 and no spacers). One pre-existing assertion was scoped: the page now has two independent error regions, so `/Could not load/` was ambiguous. Frontend **294 → 304**; eslint + tsc clean.
- **F&O page — slice 5.2 (2026-08-06).** The UI for the whole Phase-4 backend, which until now had no screen at all: analytics strip, option-selling candidate cards, and the chain ladder. Route `/styles/fno` (matched before the generic `styles/:style`), lazy-loaded like every other page.
  - **Backend, per-leg IV + Greeks (`fo_analytics.price_chain_greeks`, `GET /fo/chain?greeks=true`).** The chain endpoint returned only strike/OI/volume/LTP, so the planned "ladder with IV + Greeks" had nothing to render. The pricer inverts every quoted leg to an implied vol and prices its Greeks via two batched `tradecore` calls per side — **Black-76 on the future (carry = 0), the same convention `iv_rank` uses**, so a ladder IV is directly comparable to the IV-rank history instead of being a second, subtly different number for the same thing. The options math itself stays Rust-only; this is orchestration. Legs that cannot be priced (no quote, deep-ITM at intrinsic, negligible vega) are **absent, never zero-filled** — a 0.0 delta reads as a real tradeable value on screen.
  - **`fo_analytics.chain_day`** — Greeks need a time-to-expiry, and dating them off `today` would misprice every chain loaded on a Monday from Friday's close (and every holiday). The endpoint now reports `as_of`, `fut_price` and `dte`, so the UI can state exactly what the Greeks were priced off; any missing input (no futures close, expiry already settled) leaves every Greek `null` rather than guessing a forward.
  - **`GET /fo/underlyings` + `GET /fo/expiries`** — the chain UI could not render without knowing the valid underlyings and expiries, and hardcoding them in the client would bake market knowledge into the frontend. Both are scoped to the latest recorded day (so they offer what is currently tradeable and stay index-fast instead of DISTINCT-scanning years of bhavcopy), and expiries already settled are dropped — a settled contract has no tradeable chain.
  - **Frontend:** `lib/api/fo.ts` (typed client, money kept as Decimal strings); `FoAnalyticsHeader` (spot/ATM, PCR, max pain, basis, IV-rank against the engine's ≥ 50 sell gate, India-VIX band); `ChainLadder` (calls-left/strike-centre/puts-right as Indian brokers lay it out, OI bars scaled to the window and drawn in the **neutral accent** token rather than profit/loss — open interest is not a P&L — ATM marked by a text badge as well as a tint so it survives a colour-blind read, Γ/V/Θ behind a toggle); `StrategyCards` (legs, credit, max loss, breakevens, POP, return-on-margin, mechanical exit plan).
  - **Honesty carried into the UI** from `docs/phases/phase-04-fo-suggestions.md`: expectancy is labelled **report-only** (risk-neutral expectancy is ~0 by construction and the estimator is deliberately negative-biased, so a small negative number is EXPECTED, not a red flag), the panel says **forward-tested, not backtested**, an empty candidate list renders as a deliberate **no-trade** answer listing the gates, the India-VIX veto renders as a **stand-down when the regime is unknown** (fail-closed — blank would look OK), and there is **no order button** (F&O execution does not exist; live trading is Phase 7). The ladder always states its source and day so an EOD chain cannot read as live.
  - `formatGreek` added to `lib/format.ts` so feature code never reaches for `toFixed`.
  - Tests: `tests/test_fo_analytics.py` **+18** (49 in the file) — `chain_day` per source incl. as-of and the load_chain agreement, Greek sign/moneyness ordering, IV round-trip proving the Black-76 convention, unpriced-legs-absent, degenerate inputs, picker scoping/settled-expiry drops/empty states, and API paths for greeks-off/greeks-on/no-forward/expired. `src/test/FoPage.test.tsx` (16) — analytics tiles, nearest-expiry defaulting, ladder values, provenance line, "—" not 0, Greeks toggle refetch, candidate economics, report-only + forward-tested labels, no-trade empty state, VIX unknown/high stand-down, IV-rank 404-as-empty-state, loading/error/retry, and re-defaulting the expiry when the underlying changes. Frontend **278 → 294**; ruff/mypy/eslint/tsc clean.
- **Live-data infrastructure — slice 5.1 (2026-08-06).** The plumbing the style/F&O pages need before they can carry live tables.
  - **`useLiveQuotes` v2 (`src/hooks/useLiveQuotes.ts`)** — rewritten for full-universe tick rates. Ticks now buffer in a ref and apply in **one state update per animation frame** (repeated ticks for a symbol coalesce to the newest — for a last-traded price, latest wins), replacing v1's one-`setState`-plus-whole-map-clone *per tick*. Three real bugs fixed in the process: (a) the connect effect was keyed on the symbol list, so every watchlist edit **tore down and reopened the socket**; (b) a second effect re-sent `subscribe` on **every render**, because callers pass a fresh array literal each time — the subscription now keys off the symbol SET's content and sends only **deltas**; (c) `unsubscribe` was never sent, leaking a server-side Redis subscription for every symbol ever viewed — dropped symbols now unsubscribe and their **stale quotes are pruned** (a price shown under an untracked symbol is a money-UI hazard, not just waste). A reconnect re-sends the full want-set (the server starts clean, so a delta would silently under-subscribe). `authFailed` is now surfaced, matching the other two live hooks.
  - **`useVirtualRows` (`src/hooks/useVirtualRows.ts`) + `VirtualViewport`/`VirtualSpacer` (`src/components/ui/virtual-table.tsx`)** — fixed-height row windowing for the app's tables: one recompute per frame (rAF-coalesced, passive scroll listener), state updates only when the visible window moves, spacer rows preserving the full dataset's scroll geometry, and windowing **off** below 200 rows per `.claude/rules/ui.md` (so small tables and their tests are untouched). **Deviation from the plan, flagged:** the plan named `@tanstack/react-virtual`, but this box's pnpm store was pruned by a snap refresh — `node_modules` is hard-linked to a store that no longer exists, so no new dependency can be installed without a full ~900-package reinstall. The hook is deliberately library-shaped and behind one module, so swapping TanStack in later is a one-file change with no call-site churn.
  - **`src/lib/ws.ts`** — `buildWsUrl` (wss under https, ws under http), `WS_CLOSE_UNAUTHORIZED`, `WS_RECONNECT_DELAY_MS`, previously retyped in all three live hooks; `useAlertStream` and `useProvisionalStream` now import them.
  - Tests: `src/test/useLiveQuotes.test.ts` (11) and `src/test/useVirtualRows.test.ts` (10) — burst coalescing asserted as **exactly one render for the whole burst**, the resubscribe-per-render regression, delta subscribe/unsubscribe + stale-quote pruning, reconnect re-subscribe, 4401 no-loop, rAF-absent fallback, unmount cancellation; windowing math and scroll-geometry invariant (`padTop + rendered + padBottom == count × rowHeight`), per-frame scroll coalescing, dataset-shrink clamping, ResizeObserver present/absent. Frontend suite **257 → 278**; tsc + eslint clean.

### v2 Phase 4 — F&O analytics (in progress, started 2026-07-30)

- **FIXED: expiry selection dead-ended, and a CRITICAL look-ahead beside it (2026-08-07).** Full write-up in `docs/phases/phase-04-fo-suggestions.md` §9. No calibrated number moves.
  - **The engine had already gone silent, not "was about to".** Flagged as "imminent" at the Phase-5 gate (`phase-05-ui-overhaul.md` §8). `_pick_expiry` took the first option expiry with DTE in `[20,45]` and `suggest_option_sells` priced it with `futures_basis`, which requires an **exact** expiry match. Index options expire **weekly**, index futures only **monthly**, so a weekly sitting in FRONT of a perfectly good in-window monthly killed the run: `futures_basis` → `None` → `[]`, **indistinguishable from "no candidate cleared the gates"**, which the docs teach you to read as normal. On 2026-08-05 the monthly sat at DTE exactly 20 — the *floor* of the window — so that was the LAST day it would work, not a margin. Measured over the real NIFTY expiry calendar, 42 trading days 08-06 → 10-02: old logic produces on **7 days**, the fixed walk on **33**.
  - `_pick_expiry` now returns `(day, expiry, ChainForward)` and **walks** the in-window expiries, taking the first eligible one instead of dead-ending on the first entry. When nothing is eligible it logs that the empty result is a pricing/policy outcome, not a gate rejection — closing the ambiguity that made this invisible.
  - **CRITICAL look-ahead (found by the owed quant-verifier pass).** `suggest_option_sells` called `load_chain` with **no `as_of`**, so `_chain_from_bhavcopy` took `max(trade_date)` unbounded while the forward and `t` came from a bounded query — any historical `as_of` priced a **later** chain against an **earlier** forward. Demonstrated: with chains on 08-03 and 08-04 (spot gapped +5%, IV halved), `as_of=08-03` built from **08-04's** premia — net credit 38.51 instead of 21.94. Inert on the live endpoint (never passes `as_of`), but the Phase-6 realized-vs-POP dashboard is exactly a historical-`as_of` consumer, so it would have silently corrupted the engine's own validation evidence. The chain is now bound to the forward's own day.
  - **Weeklies stay EXCLUDED, and `min_oi` is not what excludes them.** A first draft of this fix let weeklies through, arguing the `min_oi=500` per-leg floor made them safe. Real data refutes that: on 2026-08-05 the 09-01 weekly's *entire chain* carried **921,960** OI against **95,937,855** on the 08-25 monthly (~1%), and the 09-08 weekly totalled **3,705** across 142 legs — three of which cleared the floor, on daily volumes of 43/39/14 contracts. A per-leg floor cannot tell a live chain from a dead one, and the fill haircut was fitted to monthly quotes, so a weekly's true half-spread would exceed `min_slippage` and **overstate credit**. §7.6's "weeklies excluded in v1" therefore stands and is now enforced in code by a new `SellRules.require_exact_expiry_future` (default `True`) rather than emerging by accident from which expiry owns a futures row. **Open user ruling:** flipping it takes the engine to 42/42 days but needs a chain-level liquidity gate and a weekly-calibrated fill model first.
  - **Calibration provably untouched.** With the flag on, the engine prices against exact-expiry futures only, and `forward_for_expiry` short-circuits to that future's close **verbatim**. Real dev DB, NIFTY 2026-08-05: monthly 08-25 → `24647.7000` from both old and new paths (`fut_exact`). (The withheld carry-implied path would give the 09-01 weekly `24695.8967`, hand-checked as `24624.65·e^(b·27/365)`, `b = ln(24770/24624.65)/(55/365)`.) One difference from the old code, and it is an improvement: `futures_basis` filtered `trade_date <= as_of` and could price today's option closes against an **earlier day's** futures close; the new path is pinned by equality and refuses instead.
  - **Robustness:** `forward_for_expiry` took the nearest future with `limit(1)` and returned `None` if that row had no settlement price — one bad recorder row killed the forward, and every Greek, for the whole front chain. It now takes the nearest **priced** future, exact-expiry short-circuit still first.
  - **Provenance:** a non-exact forward is disclosed in every candidate's `rationale`. §6c measured that forward's error as **consistently positive** ~0.12–0.19%, not zero-mean — worth ~1.1pp of POP, enough to cross the hard `min_pop=0.65` gate — so it must never read as a traded-future price.
  - **Stale vol gates are now audible (pre-existing).** `iv_rank` and `vix_regime` are bounded against look-ahead but were never *aligned* to the day the chain prices on, so an 8-week-old IV-rank could authorize a trade in silence — live condition, given EOD ingestion missed 2026-08-06. Logs a warning when `ivr.as_of != day`. Left as a warning rather than a hard reject because that changes gate semantics: **open for a user ruling** (phase-04 §9.7).
  - Also: the naive `datetime` in Gate 2 is now tz-aware, `_select_and_build`'s `forward_source` no longer defaults to the reassuring value, `limit(4)` became a named `_FUT_FALLBACK_DEPTH`, and spot is taken from the nearest futures row that carries it rather than whichever row supplied the price.
  - **Review record:** quant-verifier **FAIL → PASS-WITH-NOTES**. Round 1 caught the look-ahead and that the first draft overrode §7.6; round 2 verified every blocker by targeted revert and independently reproduced the 7/33/42 calendar numbers. It also caught that the calibration guard's stated *reason* was wrong (for a same-expiry future `t_fut == t_opt`, so the carry formula is an identity and the numbers match either way — `source` is what discriminates); corrected in both test and doc.
  - Tests: `tests/test_fo_suggestions.py` 23 → **33**. Fixture reproduces the real NSE topology with a **non-zero carry** (a zero-carry fixture lets a calibration guard pass even with the short-circuit deleted — the first draft had exactly that flaw). Three canaries are **targeted-revert-proven** to fail on the pre-fix code: the walk regression, the look-ahead (38.51 vs 21.94), and the unpriced-nearest-future fall-through. Plus: weeklies excluded by default and selectable only via the flag, carry provenance in/absent from the rationale, forward bounded strictly inside `(spot, F_fut)` matching a hand-computed 50098.07, no-priced-future → `None`, and a calibration guard asserting the `fut_exact` **branch** as well as Decimal equality.
- **F&O option-selling suggestion engine — slice 4.3 (v1 calibrated, 2026-08-06).** Defined-risk credit candidates (bull put / bear call / iron condor); suggestions only, never auto-trades. Design + decisions in `docs/phases/phase-04-fo-suggestions.md`.
  - `app/services/fo_suggestions.py`: settled payoff math (net credit, max profit/loss, width, breakevens); **breakeven-exact POP** = `N(d2)` under Black-76; expectancy `POP·credit − (1−POP)·max_loss` **reported not gated** (risk-neutral expectancy is ~0 by construction — the edge is the volatility risk premium, gated via IV-rank + forward-testing, not provable from prices); conservative per-leg fill haircut `max(0.5%·prem, 1pt)`; `ExitPlan` (TP 50% / SL 2× / 21-DTE). `SellRules` = user-approved v1 defaults (index-only universe, IV-rank ≥ 50, 0.16Δ short, 0.30 reward floor, POP ≥ 0.65, DTE 20–45, min OI 500). `suggest_option_sells` wires it to 4.1/4.2 + `tradecore` behind the gates; `passes_gates` = reward floor + POP floor; `rank_candidates` by RoM×POP.
  - Finance-safety: **defined-risk only**, **cash-settled index only** (no physical-settlement/assignment), and the VIX regime veto **fails closed** (stands down on high OR unknown regime). Default 0.16Δ+0.30-floor is deliberately selective ("often no trade").
  - `GET /fo/suggestions` (empty list = nothing clears the gates, a valid answer).
  - Tests: `tests/test_fo_suggestions.py` (23) — hand-computed spread economics + exit plan, breakeven-POP directions, gates (reward/POP/expectancy-not-gated), and a real-chain happy path + high-VIX + no-VIX-fail-closed through `tradecore`. quant-verifier PASS-WITH-NOTES (all 3 notes fixed: VIX fail-closed, expectancy wording, condor guard). ruff/mypy clean.
- **Options math over the FFI + IV-rank — slice 4.2b (2026-07-30).**
  - `engine-py` (`tradecore`): batch `option_price`, `option_greeks`, `implied_vol` — one call per batch (rows are tuples), GIL released around the compute (`py.detach`), `None` per row for degenerate/no-solution, `ValueError` on a bad `kind`. Rebuilt via `make engine-build`.
  - `app/services/fo_analytics.py`: `iv_rank` — ATM front-month implied-vol rank/percentile over the trailing lookback of futures sessions. IV is computed via Black-76 on the **future** (carry=0, dividend-free): three bhavcopy queries assemble the per-day ATM call inputs, then a single batched `tradecore.implied_vol` call inverts them; rank = (cur−min)/(max−min)·100, percentile = % of the window below current. `GET /fo/iv-rank`.
  - Tests: `tests/test_options_ffi.py` (8 — Hull values, Greek shape, Black-76 rho identity, batch IV round-trip, `None` propagation, bad-kind `ValueError`, put–call parity) and `TestIvRank` in `tests/test_fo_analytics.py` (4 — round-trips a known vol series through the DB + `tradecore`, empty→`None`, API 200/404). ruff/mypy clean.
- **Rust options math — slice 4.2a (2026-07-30).** `engine-core/src/options.rs`: generalized Black-Scholes–Merton pricing, the five Greeks, and implied volatility — pure, deterministic f64, no panics (every entry point returns `Option`; degenerate inputs collapse to discounted intrinsic).
  - One cost-of-carry `b` serves both F&O instruments: `b=rate` → Black-Scholes (equity/index spot), `b=0` → Black-76 (options on futures), `b=rate−q` → Merton (dividend).
  - Implied vol: Newton–Raphson (Manaster–Koehler seed) with a bisection fallback and no-arbitrage bound checks. Normal CDF = Abramowitz–Stegun 26.2.17 (|err| < 7.5e-8, proven at golden-gen time against `math.erf`).
  - Validation: hand-computed Hull textbook price+Greeks; property tests (put–call parity to 1e-9, IV round-trip, Greek signs/bounds, price monotone in vol, degenerate→intrinsic); rho identity checks (Black-76 = −T·price, equity vs finite-difference); and a 90-case parity golden (`tests/fixtures/options_reference.json`) generated by an independent Python reference (`backend/scripts/gen_options_goldens.py`). `cargo fmt`/`clippy -D warnings`/`test` green (engine-core 68 unit + parity).
  - quant-verifier review caught and fixed: `rho` is now per-instrument (Haug) — `carry=0` (Black-76, options on futures) → −T·price, else the equity form; and `implied_vol` rejects low-vega premia (deep-ITM/near-expiry at intrinsic → `None` rather than an ill-conditioned value).
  - Next (4.2b): PyO3 exposure (`tradecore`) + Python IV-rank/percentile over bhavcopy EOD history. Not yet wired to Python.

- **F&O analytics foundation — slice 4.1 (2026-07-30).** New arithmetic-only analytics computed from the Phase-0 recorders (`fo_bhavcopy`, `option_chain_snapshots`, `india_vix_daily`), read-only (no migration, no frontend):
  - `app/services/fo_analytics.py` — pure functions `put_call_ratio` (by OI and volume; None when the call side is zero), `max_pain` (writer-payout-minimising strike; ties → lower strike), `atm_strike`/`near_atm` (±N strike window); async loaders `load_chain` (EOD bhavcopy or intraday snapshot — latest at/before `as_of`), `latest_spot`, `futures_basis` (FUT − underlying, absolute + %), `vix_regime` (India VIX percentile within a trailing lookback → low/normal/high band). Money = Decimal, ratios/percentiles = float.
  - `GET /fo/chain`, `GET /fo/analytics`, `GET /fo/vix-regime` (`app/api/v1/fo.py` + `app/schemas/fo.py`), registered on the v1 router.
  - Scope boundary: implied vol, Greeks and IV-rank (needing Black-Scholes) are intentionally **not** here — that is Rust-only (`engine/`, slice 4.2). The option-selling suggestion engine (slice 4.3) is deferred pending rule calibration.
  - Tests: `tests/test_fo_analytics.py` — hand-computed PCR / max-pain / ATM / window, DB loaders (latest-day/-snapshot selection, basis, VIX percentile), and /fo API smoke incl. auth + empty-state 404. 23 tests.

### v2 Phase 3 — Realtime v2 (in progress, started 2026-07-09)

- **Status-doc refresh + one accuracy fix (2026-08-06).** The session-entry docs had drifted a month behind: `CLAUDE.md`'s "Current truth" still read *2026-07-03 · Phase 0 · 439 backend / 131 frontend tests* (actual: mid-Phase-3, **974 / 257**) — refreshed, with the live exit-governance + daily-analysis loop stated. `docs/PHASES.md` gained a **"STATE AT A GLANCE" top block** (the canonical Phase-3 remaining checklist, so a reader doesn't have to grep 484 lines of narrative). `RUNBOOK.md` updated for the ₹ ladder, fill-based sizing, trade-from-AlertBell, the evening `make analysis` step, and the current 5-session evaluation window. **Accuracy fix:** `docs/PROJECT_OVERVIEW.md` claimed Phase 3 had *"soaks pass · p99 ≤ 50 ms met"* — it has not; the 2026-07-10 soak was PARTIAL (a load spike starved the consumer) and the latency verdict is still OPEN. Corrected in both the phase table and the Phase-3 detail paragraph.
- **Test isolation — isolated, per-test-flushed Redis (2026-08-06).** `conftest` truncated Postgres before each test but never cleared Redis, and tests shared the **dev cache (db 0)** — so a leaked `ltp:{id}` key from one test poisoned a later one once `RESTART IDENTITY` recycled the stock id. A full-suite-only flake (invisible when a file runs alone): `test_place_and_close_position` filled `@ 24.0000` off a stale key instead of its ₹500 entry, and `test_get_current_price_prefers_latest_1m_over_daily` returned 24.0 not 105.50. Tests now use a **dedicated Redis logical DB (15)** via `REDIS_URL`, **flushed before each test** alongside the table truncation — guarded to only ever flush db 15, never dev db 0. Test-infra only; no product code. (Surfaced by the full-suite run of the profit-protection work below.)
- **Profit-protection follow-through — chase-safe sizing, the rupee profit ladder, trade-from-AlertBell (2026-08-06).** The three fixes from `docs/analysis/FIX_PLAN.md` (P1–P3), toward booking *and keeping* profit.
  - **P1 — risk-first sizing from the ACTUAL fill (`paper_broker`).** `place_paper_order` sized quantity from the *signal's* entry but filled at market, so a chased fill silently over-risked (BAJAJFINSV filled 0.75R past entry → ₹3,366 = 3.4% on one trade, over the ₹3,000 daily cap). New pure `size_for_fill` computes `floor(budget / |fill − SL|)` from the real fill, so a fill away from plan shrinks the quantity to hold risk at the per-trade budget instead of over-risking; a repeat entry is sized against the **remaining** budget (repeat Buy clicks can no longer stack risk — the HAL 2.7× case). Fill is computed before sizing; the entry order records `chase` telemetry in `broker_payload`. Rejects (never clamps) at zero size. +7 tests.
  - **P2 — the rupee profit ladder replaces the R-ratchet on the live paper exit (`profit_lock` + `position_monitor`).** When `profit_lock_enabled`, the monitor now governs paper exits with the trader's own model (`absolute_ladder_stop`): once peak profit ≥ ₹2,000 lock **breakeven** (kills the "went +₹2k then back to a loss" case); once ≥ ₹3,000 **seal `(peak − ₹1,000)`** — a fixed-₹ trailing giveback that tightens as a fraction as the trade runs; the giveback is at least `atr_k × ATR` in price so a volatile trend keeps room and isn't noise-stopped. Coherent across trades because P1 sizes each to the same risk budget (₹≈R). Thresholds are config knobs (`profit_lock_*_inr` / `_atr_k`) — calibration starting points to tune on the tape. One-way/monotonic; paper-only; gates nothing live until Phase 7. +7 pure ladder tests; the 3 governor tests re-pinned to the ladder (LONG seals 520 / SHORT 480). The daily report now leads in ₹: `exit governor: ON (₹ profit ladder)`, the live config, per-position **sealed-in ₹**, and a scorecard **"Profit sealed right now"** total. +1 report test.
  - **P3 — trade directly from AlertBell.** Each entry-zone alert (already carrying its originating signal for the anti-chase guardrail) gained a Buy/Sell button through the same paper order path + circuit breaker, so an alerted stock that isn't on the (deduped, choppy/near-expiry-hidden, paginated) dashboard list is still one click from a paper trade. Halt- and direction-aware (SELL opens a short); P1's risk cap applies. +4 AlertBell tests. **Deferred:** resting LIMIT orders (enter-at-price-and-wait) — an order-state-machine feature for its own slice; P1 already caps the risk of a market entry and the anti-chase warning flags overpayment.
- **Daily trading-analysis report generator (2026-08-05).** New `make analysis` / `/daily-analysis` / `scripts/daily_analysis.py` → `app/services/daily_report.py`: a read-only, reproducible Markdown report per IST trading day, written to `docs/analysis/`. Per traded stock it reconstructs what the engine predicted (entry/SL/TP/confidence/factors + `signal_outcomes` touches), what you did vs the plan — the **chase** (fill vs signal entry, in R), the resulting silent **oversize** (`risk vs 2% budget`), and the R:R collapse — plus a 1m-tape **MFE/MAE with timing**, whether the trade reached +1R (the profit-lock arm threshold), the `profit_lock_shadow` exit-policy replay, risk analysis (portfolio heat, single-trade cap breaches), and templated takeaways. A weekly roll-up (`WEEK-<monday>.md`) does week-over-week realised-P&L, and a running `LEDGER.md` tracks the trend. Money is temporally bounded (a past-day report never shows a future exit) and marks recompute from the day's last 1m close (not the mutable `unrealized_pnl`) so re-runs reproduce. Ran for 2026-08-03/04/05: surfaced that only **1/15** entries reached +1R (so the profit-lock had nothing to arm on), ~₹21k of peak profit given back, 3 chased entries (BAJAJFINSV 3.37% risk on one trade — over the ₹3,000 daily cap), and 30.7% open portfolio heat. Findings and the prioritised code fixes are in `docs/analysis/FIX_PLAN.md`. +9 tests (chase/oversize + tape MFE/MAE pure-fns, 3 DB-integration incl. a regression for the opened-D/closed-D+1 temporal look-ahead). Corrected two stale docstrings that claimed the profit-lock was "shadow-only / not wired" (it governs paper exits per-user since 2026-07-30) and `_apply_slippage`'s "default 0" (it's 2 bps).
- **Honest gap-through-stop fills in the paper monitor (2026-08-01).** The position monitor booked every SL exit at the *exact* stop price, even when the live tick had already gapped through it (an overnight gap surfaced at the 09:15 first tick, or a fast move between the 60-second polls) — flattering the paper record on precisely the moves that hurt most, and the paper record is what gates live trading. SL exits now fill at the **worse of {stop, live price}** via the new pure `app/trading/trail_sl.stop_fill_price` (TP unchanged — a favourable target-gap filled at the target is already conservative); slippage/tick rounding still apply on top in `paper_broker`. A clean touch (price == stop) is byte-identical to the old behaviour, so only genuine gaps change value. From the 2026-08-01 architecture-review fit-check (item P0.3, the one now-fix). +3 tests (LONG/SHORT pure-helper worse-of, and a scan-level gap-through regression asserting the fill lands at the gapped market, not the stop). Remaining review items are phase-mapped at the end of `docs/PHASES.md`.
- **Paper fills now model adverse slippage by default (2026-08-01).** `paper_slippage_bps` was `0.0` (off), so every simulated fill assumed the exact screen price — optimistic, since a real market order always crosses the spread. Default is now **2 bps** (BUY fills up, SELL down; ~₹0.10 on a ₹500 name each way), stacking on top of the gap-through-stop fix and the Zerodha fee model so paper P&L ≤ realistic live P&L. Applies to entries and exits via `paper_broker._simulated_fill`; tune per the names/size traded. Unrelated tests are pinned slippage-neutral (conftest `_neutral_paper_slippage`) so fill assertions aren't coupled to the knob; +5 dedicated tests exercise the 2-bps path (pure `_apply_slippage`/`_simulated_fill` both sides + zero-noop, and close-path/entry-path integration asserting fills land adverse and worse than the neutral baseline).
- **Paper-clock reset — restart the 30-day honest-fill window (2026-08-01).** Because the two fill-model changes above make the record stricter going forward, the 30-day profitable-paper count should be measured under one consistent model. New `users.paper_clock_started_at` (migration `y1z2a3b4c5d6`, nullable, reversible; NULL = count all history): when set, `GET /trading/paper-record` counts only trades closed on/after it, and `POST /trading/paper-clock/reset` stamps it to now (past trades stay in the DB, they just stop counting). Surfaced on `PaperRecordOut.clock_started_at`; the Paper Record card gained a two-step "Reset clock" confirm and a "counting since {date}" label. +3 backend tests (record filters by clock start · reset drops prior days · empty-record clock field) and +1 frontend test (two-step confirm calls the endpoint once and reflects the new start). The go-live gate stays display-only until Phase 7 (the authoritative promotion gate).

- **Layered Ratchet Stop wired into live paper exits, behind a per-user toggle (2026-07-30).** New `users.profit_lock_enabled` (default **False** = the unchanged `trail_sl` ladder). When on, the position monitor governs open **paper** positions with the Layered Ratchet Stop (`app/trading/profit_lock.py` — peak-anchored ATR chandelier + tapering giveback cap, one-way, no profit ceiling) instead of the fixed rung ladder. Entry-time ATR (`before=opened_at`) matches the shadow comparator, so the live path tracks the shadow evidence. The SL/TP-hit check still runs against the *pre-advance* stop (no intra-beat look-ahead) and the lock only ever tightens the stop; `trail_state` stays a ladder-only concept (frontend union unchanged). Paper exits only — never places live orders. Toggle lives in Profile → Trading Settings. Migration `x0y1z2a3b4c5` (reversible; `server_default false`). +3 backend governor tests (ON=layered / OFF=ladder regression canary / SHORT) and a frontend toggle test; bug-hunter review clean (all seven exit-seam risks verified). Default-off, so behaviour is unchanged until explicitly opted in.
- **Total unrealised P&L on the Today's-P&L card (2026-07-30).** The Positions/Trade-History "Today's P&L" widget now shows **Unreal. (open)** — the summed net unrealised P&L across all open positions. `GET /trading/daily-pnl` refreshes each open position's P&L (same path as the positions list) and sums it, so the card matches the table exactly. +2 tests.
- **Shadow comparison in Trade History (2026-07-30).** The Trade History table now shows **Peak** (max favourable excursion, gross), **Capture %** (realised ÷ peak), and **After-lock** — the ₹ the Layered Ratchet Stop would realistically have kept, replayed on the real 1m tape — per closed trade, from the read-only `GET /trading/shadow-compare` (cached, not re-fetched per page). Makes profit leakage and the profit-lock's potential visible at a glance; still shadow-only (drives no orders).
  - **Off-tape close detection (correctness).** When a trade's recorded exit is *better than anything that actually traded* (a short below the true low / a long above the true high) it closed on a stale/pre-open price — the fixed monitor bug — so its realised P&L is fictional (Peak < realised). Such rows are now flagged (`actual_exit_off_tape`, ⚠ marker) and no capture % is computed against the fake exit; Peak and After-lock stay real. Caught the 07-27 LENSKART (recorded +₹2,711 but real peak was only ₹218; the profit-lock's true-price outcome was −₹930). +2 tests (backend detection + frontend flag). The shadow report script also silences SQLAlchemy echo for readable output.
- **Stocks search — relevance ranking (BUG, 2026-07-30).** Search filtered by a too-permissive pg_trgm similarity (0.1) but ordered results by the table sort (market cap, NULL for most rows), so exact matches were buried — typing "STYRENIX" returned ~25 fuzzy rows with the exact match *last*. Search now also matches on substring (ILIKE) so every symbol/name containing the query is found, and **ranks by match quality** (exact symbol → symbol prefix → name prefix → substring → trigram), with the table sort as the in-tier tiebreak and a stable `symbol` final tiebreak for deterministic pagination. Trigram threshold tightened 0.1→0.3 (substring covers the obvious hits; 0.1 only added noise). "STYRENIX" now returns one row, first; "TATA" returns the 9 Tata-group stocks first instead of 57 noisy rows. +3 regression tests.
- **Frontend build fix (BUG, 2026-07-30).** `globals.css` `@import`ed `@fontsource-variable/inter` and `jetbrains-mono`, neither installed (only `geist` is), so `@tailwindcss/vite` 500'd the whole stylesheet and `make frontend` served an error page. Removed the two unresolvable imports and led `--font-ui` with the bundled Geist; Inter/JetBrains remain as `tokens.css` fallbacks.
- **Signal-intelligence overlay v1 + stale-P&L fix (2026-07-31).** Presentation-layer fixes from the 07-30/31 trade review (`docs/TRADE_REVIEW_2026-07-30_31.md`) — the signal engine stays FROZEN; these change only what's *shown*.
  - **Dedup (`GET /signals/active`).** The base engine and named profiles (e.g. `multibagger`) each emit a near-identical signal for the same setup (observed on 6 stocks incl. NILKAMAL — same entry/TP, different SL/qty). The list now collapses to one row per (stock, direction, classification), keeping the best (confidence → reward:risk → recency) and reporting `sources_count` (UI badges "×N"). Fixes the inflated active/buy/sell counts.
  - **Near-expiry suppression.** Signals with ≥80% of their validity window elapsed (`near_expiry`) are hidden by default (opt-in `include_expiring`), with `days_valid_remaining` shown per row and a "Near-expiry" toggle. Directly targets the review's biggest loss driver — entering week-old swing signals on their expiry day (4/4 losers).
  - **Regime (choppiness) filter.** Each signal is tagged with its stock's daily **Kaufman efficiency ratio** (`regime_er`); those below 0.30 (`choppy`) are hidden by default (opt-in `include_choppy`), muted + "· chop"-badged when shown, with a "Choppy" toggle. This is the highest-value filter from the `scripts/signal_filter_shadow.py` measurement: on the 25-trade reliable sample, keeping only trending (ER ≥ 0.30) tapes was **+₹1,035 (50% win)** vs the choppy bucket's **−₹26,023 (36% win)** — nearly all losses came from chop. Threshold provisional; confirm on the Mon/Tue forward run. **The R:R gate was measured and DROPPED** (counterproductive — big losers had artifact-high signal R:R). +4 tests.
  - **Anti-chase guardrail in the alert bell.** Each entry-zone alert now fetches its originating signal and shows the trade direction (▲ BUY / ▼ SELL), the ideal entry price, and a **"don't chase > ₹X"** ceiling (BUY) / **"< ₹X"** floor (SELL) set at entry ± 0.33·(entry→SL risk) — past which the reward:risk you were shown is materially gone. When the trigger price has already run past it, the row flips to **"⚠ chasing +N% past entry"** in the warning colour. Directly targets the review's chase-driven losers (COLPAL / FOSECOIND / HINDCOPPER). Frontend-only, engine untouched; +7 tests, ui-reviewer clean.
  - **Emergency-exit watcher (the downside twin of the profit-lock).** `GET /trading/positions` now carries an advisory **health verdict** per open position — **CUT** (structurally dead, exit) / **WATCH** / hold — computed by the new pure `app/trading/position_health.py` from five conditions: thesis break (price through the stop), deep MAE (≥0.8R underwater), remaining-R:R inversion (only when losing), trend death (daily Kaufman ER < 0.30), and stale (held past the signal's validity). Soft conditions escalate to CUT only when the trade is underwater. The Positions table shows a colour-coded badge with the primary reason inline (full reasons on hover) and a left-edge accent on flagged rows; the page already polls every 30 s, so it acts as a live watcher. It is **advisory only — it never auto-exits** (the trail-SL and circuit breaker own execution). Targets the review's slow bleeders — week-old choppy swings that never hit 1R. As part of this, the daily-regime ER logic used by both the signal overlay and the watcher was centralised into `app/trading/regime.py`. +14 tests.
  - **Stale unrealised-P&L (`get_current_price`).** When live ticks are cold, marks now use the freshest **1-minute** close instead of the daily close (which lags a full session until the evening EOD ingest) — so the Positions/Today's-P&L marks stop showing a day-old figure.
  - +7 tests (dedup keep-best + sources_count, near-expiry hide/show, 1m-close preference). *(This worktree used an isolated test DB — the shared `trading_platform_test` was migrated ahead by the parallel live-wiring branch; resolves on merge.)*
- **Profit-protection program + trade transparency (2026-07-29→, in progress).** Prompted by the LENSKART paper trade whose unrealised profit peaked ~₹5,388 (1.58R) but realised only ₹1,020.89 — the entry-anchored trail ladder froze between 1.5R and 2R. The program: fix the monitor price-feed, surface exit data, then build a Dynamic Profit Lock ("Layered Ratchet Stop") as a shadow comparator before it ever controls orders.
  - **Alert bell "Entry signals only" filter.** The live-alert bell now defaults to showing only entry-zone triggers (`source === "entry_zone"`) — the actionable buy/sell alerts (price re-entered a signal's entry band). Level crosses, S/R zone entries and volume bursts are hidden until the user turns the filter off; the choice persists in `localStorage` and constrains both the list and the unseen badge. Client-side only (no backend/WS change). +5 AlertBell tests.
  - **Trade transparency — exit price/reason + live position price.** `positions.exit_price` and `positions.exit_reason` (`sl_hit`/`tp_hit`/`manual`) are now denormalised onto the position at close (migration `v8w9x0y1z2a3`, nullable, reversible), and surfaced on `PositionOut`. Trade History gained **Exit** and **Reason** columns (reason renders as Stop loss/Target/Manual · auto/manual). The open-**Positions** table gained a **Current** market-price column: `update_position_pnl` now returns the price it used and the list endpoint carries it as `current_price`. `unrealized_pnl` is now reported NET of estimated round-trip costs, so open and closed rows read in the same units. +3 backend tests, +3 frontend tests.
  - **Position-monitor stale-price / pre-open exit fix (BUG).** The auto-close monitor no longer acts on stale prices. New `app/trading/market_hours.is_market_session` gates the scan to the exact NSE regular session (09:15–15:30 IST, weekdays) — the authoritative guard, with the Celery crontab widened to a coarse superset (`hour="3-10"`); the old `hour="3-9"` fired an 08:30 IST pre-open beat that auto-closed positions on the previous session's close. The exit/trail/P&L path now reads the **live** LTP only (`get_live_ltp`, Redis-only) and *skips* a position when no fresh tick exists, instead of falling back to the last daily close. The monitor body is refactored into a testable `scan_positions(db, *, now)`. +7 tests including a pre-open regression (breaching price must NOT close before the open) and an in-session no-live-price skip.
  - **Layered Ratchet Stop — Dynamic Profit Lock (shadow comparator, controls nothing).** The mechanism from the design discussion, built shadow-first for evidence: `app/trading/profit_lock.py` — a pure, deterministic `layered_ratchet_stop` taking the tightest of {initial risk SL, peak-anchored ATR chandelier `peak∓k·ATR`, tapering profit-lock cap} and ratcheting one way only, no profit ceiling; per-class tuning (`CLASS_PARAMS`) resolved from `signal.classification`. `app/trading/atr.py` computes a Wilder-seed ATR from stored candles (reads only — the analysis engine stays frozen). `app/services/profit_lock_shadow.py` replays candidate policies (current ladder vs layered vs a plain 33% giveback) over a position's committed 1m tape — offline, so it sees past the real exit — and reports each policy's exit, net P&L and **capture ratio** (realised ÷ MFE). Exposed read-only at `GET /trading/shadow-compare` and via `scripts/profit_lock_shadow.py`. Separately, the live monitor now tracks each position's **max favourable excursion** (`positions.peak_price`/`peak_pnl`, migration `w9x0y1z2a3b4`, nullable/reversible) to quantify leakage going forward. The current `trail_sl` ladder still governs real exits — nothing here is wired to live orders. +15 tests (pure stop/giveback, ATR, replay proving layered keeps more than the ladder on a spike-and-fade, peak tracking, endpoint).
- **UI overhaul + frontend hardening (weekend program, 2026-07-19→25) — the offline-buildable slices across Phases 5/6/7, done ahead of the Monday live run.** All frontend/token work that needs no live tick, landed so the app is tight before `make worker`/`--gap-fill` on 07-27. (1) **Slate is the new default theme** — a sixth `[data-theme]` block (bg `#0b1220`, accent `#2563eb`) added as the `:root` default, with per-theme `--color-primary-foreground` overrides (midnight `#041019`, carbon `#0a0a0a`, ocean `#04211d`) so accent-on-button text clears AA in every theme; `themeStore` default + daybreak→slate toggle updated. (2) **Repo-wide token/format sweep** — dashboard, StockDetail, Login, Stocks, Categories converted to `(--color-x)` tokens + `lib/format` helpers (no raw hex/`toFixed`/palette classes); dashboard duplicate-React-key + StatCard color-mix fixed; ui-reviewer PASS-WITH-NOTES → two diff-introduced color collisions fixed. (3) **Grouped sidebar IA** — `NAV_GROUPS` (Markets / Styles / Trading / Analysis / Admin) with `isNavActive`, split into `nav-items.tsx` (data) + `Sidebar.tsx` (components) to satisfy `react-refresh/only-export-components`; Kite banner + logo tokenized; page-title map extended for the new routes. (4) **Four trading-style pages** `/styles/:style` (intraday/swing/fno/investment) over a new `lib/api/suggestions` client, consuming `GET /suggestions/{style}`. (5) **Live signal rows memoized** for 60fps tick updates — `SignalRow = memo(...)` with stable `useCallback` handlers + primitive props, `PriceCell` for the flashing LTP (TanStack Virtual was intended but blocked by the snap-pnpm store-path quirk — documented; memoization shipped as the interim, virtualization tracked). (6) **Per-style outcome analytics** — backend `GET /analytics/outcomes` (joins `signal_outcomes`→`signals`→`strategy_profiles`, cohorted on `OUTCOME_EPOCH` 2026-07-19, `FILTER`-counted by status ladder) + `OutcomesPage` dashboard (hit-rate/entry-rate/avg-return per style, breakdown, skeleton/empty/error+retry). (7) **Go-live gate view + client-side kill switch** — `GoLivePage` renders the 30-day profitable-paper progress (read-only; the authoritative gate stays Phase 7), and a persisted `tradingHaltStore` drives an AppShell halt banner + a guard on the dashboard's Paper-Trade action (the daily-loss circuit breaker remains the non-disableable server-side stop; this is an additive client convenience, never a replacement). (8) **Trading dialogs re-themed** — Close-Position and Update-SL rebuilt on the themed base-ui `Dialog`/`Input`/`Label` primitives (Portal + solid `--color-surface` + `open`/`onOpenChange`), replacing raw `<input>` + rgba scrim. (9) **Route-level code-splitting** — every page is now a `React.lazy` chunk (defs in `routes/lazyPages.ts` so `router.tsx` stays a pure route table) behind an AppShell `<Suspense>` skeleton; the heavy chart deps (recharts `CartesianChart` ~293 kB, lightweight-charts `StockDetailPage` ~179 kB) no longer sit in the initial bundle — they load only on the pages that use them. Fixed a latent `pnpm build` break exposed along the way: `vite.config.ts` imported `defineConfig` from `vite` while carrying a Vitest `test` key (TS2769 under `tsc -b`, never caught because `make check` runs `typecheck` on the app config only) → now from `vitest/config`. Frontend suite **131 → 229 green** across the program (incl. first-ever tests for the Kite-connect, Journal, Portfolio, and Filings pages — states + primary interactions); eslint + tsc + `pnpm build` clean.

- **Paper-trading credibility pass — the 30-day paper record now reflects real returns.** Trace of the paper path (manual entry → auto exit → P&L → the profitable-day gate) surfaced four issues; all fixed so the record faithfully predicts live profitability. (1) **Position sizing now uses the trader's own capital**, not the signal's house-default `suggested_qty` (`place_paper_order` calls `compute_quantity(user.capital_inr, user.risk_per_trade_pct, …)` when no explicit quantity) — the ₹5L-vs-₹1L mismatch that made each suggested-qty trade risk 5× the intended amount is gone. A size that rounds to **0** (stop wider than the account's per-trade risk) is **rejected (422), never clamped** (`PaperOrderError`), per the reject-don't-clamp rule. (2) **Trading costs are modelled** (`app/trading/fees.py`): a configurable Zerodha cash-equity schedule (brokerage, STT, exchange txn, GST, SEBI, stamp), product-aware (swing/positional → delivery, scalp/intraday → intraday), applied on the round trip so `positions.realized_pnl` is **net of costs** everywhere (circuit breaker + record consistent); the charge breakdown is stashed in the closing order's `broker_payload` for audit, and the total in a new nullable `positions.charges` column (reversible migration `t6u7v8w9x0y1`, up→down→up proven; NULL = pre-cost history). Behavioural toggles `paper_costs_enabled` (default on), `paper_slippage_bps` (adverse fill slippage, default 0), `paper_tick_size` (0.05). Rates cross-checked against Zerodha's calculator (delivery ≈ ₹232.60 / intraday ≈ ₹85.30 on a 100-share ₹1000→₹1100 round trip). (3) **Dashboard "Paper Trade" is now direction-aware** — a SELL signal opens a SHORT (was hard-coded BUY, which opened a wrong-way long on bearish setups; the backend already supported SHORT end-to-end). (4) **New `GET /trading/paper-record`** + a **PaperRecordCard** on the Positions page: per-IST-day net P&L, cumulative, profitable-day count, current/best streak, win rate and total costs — the visible surface of the 30-day profitable-paper gate (the authoritative promotion gate stays Phase 7). Design informed by a user-supplied paper-broker execution spec; the fuller simulator (order state machine, immutable fill ledger, cash/margin ledger, LIMIT/STOP types, broker abstraction for the paper→live swap) is captured as the Phase-6/7 roadmap, deliberately out of scope here. (5) **Off-market entry guard** — paper entries are rejected (422, `PaperOrderError`) when there's no live tick price (market closed or the stock isn't trading), so a fill can't use a stale prior close; per-user toggle `users.allow_offmarket_entry` (default off = guard on; migration `u7v8w9x0y1z2`, reversible) editable in Trading Settings. `get_current_price` refactored to reuse a new `get_live_ltp` (Redis-only, no fallback). Motivated by a real 08:08 pre-open fill that used the prior close. Self-service **Trading Settings on the Profile page** — capital, risk %, daily-loss %, max trades/day, and the off-market toggle are user-editable (backend `PATCH /users/{id}` already allowed self-update) with a live risk-amount preview and schema-bound validation, since the user's capital varies. +8 backend cost tests (hand-computed), +7 backend trading tests (sizing-from-capital, zero-qty rejection, cost toggle, short net P&L, paper-record aggregation/empty), updated 4 gross→net assertions (tied to the fee module, not brittle constants); +7 frontend tests (BUY/SELL direction, profile edit/save/validation, record card data/empty/error). ruff + mypy(strict) + eslint + tsc clean.

- **Slice 3.7 live-run ops — shadow-week wrapper + both queued rulings resolved.** New `backend/scripts/shadow_day.sh`: thin wrapper over `shadow_week.py` that runs one or more days, extracts the report summary (matched/diffs/errors/both_emitted), appends a timestamped `PASS/FAIL` verdict to `backend/shadow/shadow_week.log`, and exits nonzero if any day disagrees — so a daily run fails loudly and the week's verdicts accumulate in one place. Timing note captured in PHASES/ledger: the wrapper must run AFTER the evening EOD beats land the committed close (~19:30 IST — equities EOD 18:40, nightly 19:15), not mid-afternoon. Both non-blocking rulings recorded RULED in the phase-03 ledger §Decisions (and cleared from the PHASES next-action): (1) **outcome-tick gap-through-SL fidelity → option (a) now + (c) Phase 6** — accept the live recorder as-is (`sl_first` is a documented FLOOR; zero code), defer an EOD candle-based reconciliation pass to Phase 6 where a second oracle exists; option (b) recorder-side synthesis rejected. (2) **the 4 CA quarantines (KRISHANA/MBAPL/MWL/GOLDIAM) → keep flagged** — verified true-positive splits/bonus on small-cap, non-index/F&O names; no ad-hoc adjusted refetch (would poison cross-sectional factors); re-inclusion folded into the Phase-4/6 universe-wide adjusted-history migration (noting `ca_flagged_at` is permanent-until-manually-cleared).

- **Slice 3.7 (offline harness) — shadow-compare: Rust vs frozen-Python 1d decision double-check** (UPGRADE_PLAN Phase-3 exit activity; ledger §Shadow compare). The tooling for "one shadow week, zero diffs required"; the week-long run is live. `app/services/shadow_compare.py` re-scores each committed 1d close under BOTH engine implementations through the ONE real `score_signal` entrypoint (a restored `engine_impl` toggle — no third reimplementation) and reports any decision/direction/confidence-integer diff; designed as an EOD SWEEP over the active universe (same order of work as nightly generation, never the tick path — Rust is parity-pinned only for the base 1d decision, so 1d closes at EOD are the meaningful domain). `scripts/shadow_week.py --day` writes a gitignored JSON report and exits nonzero on any diff or error (the gate). SCOPE (honest, per quant-verifier PASS-WITH-NOTES): the BASE flow-free decision, not the flow-inclusive committed nightly signal (tradecore raises on flows/multipliers — this is exactly the fixture-pinned parity domain); the day's excluded §2.7 flows are stamped in the report, and the frozen Python engine stays non-deletable until flows are plumbed through Rust. **Executed day-one against the real DB (07-17): 2,293/2,293 committed 1d closes matched exactly, 0 diffs; 73 were real emitted signals, all agreeing.** +11 tests (real DB + real tradecore: emitted-signal exact parity via a bearish-marubozu frame both engines score (SELL,66), injected-divergence detection, toggle restore, matched-count decomposition, flow stamp, as-of cutoff, non-1d refusal). quant-verifier PASS-WITH-NOTES → all fixed (flow-exclusion framing + stamp; signals_emitted/both_emitted counters; real-emit-parity test; raw is_active universe == nightly). bug-hunter BUGS-FOUND → all fixed (MEDIUM: report JSON omitted the errors list → now serialized; LOW latent: global engine_impl toggle could race the provisional thread → REMOVED by threading an explicit `impl=` param through score_signal, pure/thread-safe; LOW: _load_window outside the per-stock guard aborted the whole day → load now inside with rollback recovery). signal_service.score_signal gained an optional `impl=` override (additive, backward-compatible; not frozen code).

- **Slice 3.6 — signal-outcome tick evaluation ("did the entry zone touch before expiry?") recorded now; Phase 6 consumes** (UPGRADE_PLAN Phase-3 bullet; ledger §Outcome ticks). Trigger set extended: every active signal now carries direction-aware SL/TP **touch** cross levels at the exact prices (BUY: SL=cross_down/TP=cross_up; SELL mirrored) alongside the existing proximity alerts — outcome truth needs the touch, not the approach; `signal_level_ids` spacing ×4→×8 (slots 3/4; ids are session-ephemeral — armed-state lives within a day and recordings replay their own "lv" lines). `signal_outcomes` table REPLACED (reversible migration `s5t6u7v8w9x0`, up→down→up proven; old v1 EOD-reconciliation shape had zero writers/readers and 0 rows, guarded by a refuse-to-drop-nonempty check): one row per signal — first entry/SL/TP touch stamps+prices (Numeric(12,4)), validity snapshot, and a MONOTONIC status ladder (open → entry_touched → tp_first/sl_first; expired_untouched/expired_open; terminal never reopens). Semantics pinned: SL/TP touches WITHOUT a prior entry touch stamp but never resolve (a TP cross on a never-entered setup is a missed trade, not a win); only status transitions are validity-guarded — stamps record even late (Phase-6 honesty); first touch wins (idempotent COALESCE writes). New `app/broker/outcome_recorder.py` worker thread (behind `live_outcome_recorder_enabled`, default ON): durable alerts-stream CONSUMER GROUP (`outcome-recorder`; XACK strictly AFTER the DB commit → at-least-once with idempotent redelivery; PEL crash-recovery pass at startup; non-touch alerts acked immediately so the PEL can't pin); zero work on the consumer thread. Expiry sweeper finalizes: lapsed signals get terminal outcomes each 5-min beat, alert-less expired signals still get rows. Surfaces: REST `GET /signals/{id}/outcome` (404 = lazily not-yet-written) + an Outcome section in SignalDetailModal (status glyph+tone ladder, touch trail in IST; enrichment-only — never blocks the modal). +11 backend tests (real Redis consumer-group drain both sides, ack-after-commit, redelivery, ghost-signal skip; status-ladder matrix incl. first-touch-wins and late-touch honesty; expiry finalization idempotence; SELL mirror; REST roundtrip) + 4 frontend tests + updated live-levels pins (5-tuple ids, touch kinds). Reviews (ledger §Reviews outcome ticks): bug-hunter BUGS-FOUND → all fixed (2 MEDIUM w/ executed repros: finalizer classified on the raw stamp not the ladder — a post-expiry armed-lag touch flipped the verdict, now `CASE WHEN status='open'`; recorder PEL-recovery had no armor + a poison entry aborted its batch and killed the thread every restart, now retrying recovery + per-entry SAVEPOINT with poison acked as a drop; +3 LOW: OUTCOME_EPOCH seeding floor, updated_at stamped in raw SQL, crash-window monotonic-toward-truth upgrades). quant-verifier FAIL → fixed/dispositioned (HIGH: redelivered pre-entry TP/SL touch could resolve after entry landed — now `:ts >= entry_touched_at`, reorder regression; HIGH+MEDIUM gap-blind + at-level-asymmetry documented as known measurement limits with a user ruling QUEUED in §Decisions — recommend accept-as-floor now + Phase-6 candle cross-check; MEDIUM epoch cohorting requirement; dead OUTCOME_TERMINAL removed; prices via formatCurrency). Containment reconfirmed: zero outcome references in analysis/signals/backtest/profiles/engine.

- **Provisional confidence + per-style leaderboards (the last 3.5 deferred item) — implemented per the pinned design** (ledger §Decisions 2026-07-11: throttled batch rescore of a bounded hot set; O(1)-incremental stays rejected). New `app/broker/provisional.py` refresher thread (own loop/engine/redis, the `run_refresher` pattern; in-session gate 09:15–15:35 IST; cycle-START cadence `live_provisional_refresh_s`=3s, overruns log loudly and never queue): hot set = active-signal + near-trigger (alert-stream recency window) + watchlist stocks, bounded by `live_provisional_hotset_max` with signal>trigger>watchlist priority and LOGGED clipping → ONE `LiveBook.forming_snapshot` FFI read → each (stock, profile) pair rescored through the FROZEN sequence (`score_signal` with the profile's real min_confidence + multipliers) on the window canon (≤299 completed bars + forming bar; 1d pairs session-aggregate today's committed 5m + forming 5m per the 3.0 own-bars principle) → per-style leaderboards SET (TTL `live_provisional_key_ttl_s`) + PUBLISH on `provisional:{style}`; top-N clip never drops active-signal rows (they always publish — confidence=null = "your signal's setup no longer passes its gate"). CONVERGENCE BY CONSTRUCTION: the provisional score equals the committed score at candle close (pinned by test; intraday tfs — the 1d preview converges to the session-aggregate score, a documented data-source delta vs the bhavcopy VWAP close). Rust: `LiveBook` is now `#[pyclass(frozen)]` holding the book behind a Mutex (consumer mutates, provisional thread reads; every lock scoped entirely inside `py.detach` or entirely under the GIL — GIL↔lock deadlock structurally impossible; poisoning → typed RuntimeError, never unwrap); new `forming_snapshot(stock_ids)` getter (GIL released; DERIVED read — never an engine event, never recorded/replayed). Surfaces: `/ws/live` `subscribe_provisional` (true|[styles]|false, REPLACE semantics, validated against `ALL_PROVISIONAL_STYLES`, `{"type":"provisional"}` frames) + REST `GET /market/provisional/{style}` reconciliation (empty state ≠ error) + dashboard `ProvisionalPanel` (style tabs, ▲/▼ + profit/loss tokens, `formatPct`, tabular-nums, skeleton/empty/error+retry states, PROVISIONAL badge + "converges at candle close" labelling end-to-end) fed by `useProvisionalStream` (latest-snapshot-per-style over one socket; REST covers mount/reconnect; 4401 → authFailed, no reconnect loop). Worker: provisional thread joins `main()` behind `live_provisional_enabled` (default ON; the reversibility switch) — ZERO new work on the consumer thread. +21 backend tests (real DB + real Redis + real tradecore book: convergence exact-equality canary pinned to the frozen engine's (SELL, 43)/(SELL, 66) fixtures, window-canon cap/supersede, hot-set priority clipping, TTL/ordering/signal-row-survival, run_cycle end-to-end row == direct `score_signal` on the identical window, 1d aggregate path, WS fanout both sides, REST roundtrip) + 12 frontend tests (161→173 — panel states, tab switch, WS-snapshot preference, hook subscribe/parse/auth-fail/reconnect). Reviews (ledger §Reviews provisional confidence): quant-verifier PASS-WITH-NOTES — HIGH fixed (signal pairs bound to a deactivated profile silently dropped its multipliers/gate/style shelf; non-superseded profile rows now fetched for pair keys + regression test) + 3 LOW fixed (whole-cycle abort on one malformed stream entry; clipped signal stocks losing forming bar/symbol; no-data conflated with below-gate — `gate: null` + "no data" rendering now distinct end-to-end) + cadence made true start-to-start + deterministic sort tiebreak. bug-hunter BUGS-FOUND → all fixed (MEDIUM w/ executed repro: an emptied style was never re-published, stale board outlived the setup behind a Live badge — every style now publishes every cycle incl. empty, canary test; LOW: capped XREVRANGE shrank the trigger recency window under alert bursts — now pages past the cutoff, 551-entry regression; LOW: published scalp/positional boards had no UI tab — panel offers all six styles). Backend suites green (3-leg gate re-run on final code); eslint+tsc+ruff+mypy clean.

- **EOD-ingestion incident RESOLVED (2026-07-18): self-healing catch-up shipped, 07-03→07-17 backfilled** (ledger §EOD restart). Root cause was structural — no make target for Celery, soaks quiesce the box, and every EOD beat task ingested only `today`, so each missed evening was a permanent silent hole. New `app/services/eod_catchup.py`: EOD task bodies (`ingest_equities_eod`, `fo_eod_ingestion`, `ingest_fii_dii`) now heal every missing trading session in a 21-day lookback, per-session presence (interior holes included), CA-sweeping each healed equities session in order; `trading_days_between` added to market_calendar; `scripts/catchup_eod.py` manual runner shares the same functions; `make worker` (celery worker -B) joins the daily ritual (+10 real-DB tests incl. the outage regression canary). Backfill executed: ohlcv_1d, fo_bhavcopy, india_vix_daily all 11/11 sessions; CA sweep quarantined 4 gap-window corporate actions (KRISHANA/MBAPL ≈5:1 splits, MWL ≈10:1, GOLDIAM ≈4:3 bonus — pending review). **FII/DII parser fixed** (third latent bug): the live NSE endpoint serves only the LATEST day in a flat `buyValue/sellValue` shape the old parser didn't recognize — every fetch had parsed to zero records since the feature shipped; both shapes now parse (flat → segment='cash', the one §2.7's rollup reads; regression test with the verbatim live payload). 07-17 flows captured; 07-02→07-16 permanently unavailable from this source (historical fetcher = Phase 4; rollup scores missing days as zero by design). bug-hunter BUGS-FOUND → all five fixed + 6 regression tests (transport-error isolation per session/table — one bad download no longer forfeits the run and VIX survives an fo failure; CA sweep now covers every present session in the window each run, healing sweeps lost to crashes or backfill_eod.py; mixed-shape payloads prefer segmented cash over the flat total; presence/CA `time::date` casts tz-pinned via AT TIME ZONE 'UTC'; `_to_decimal` rejects NaN/Infinity before they poison the §2.7 SUM; +0.5s inter-day politeness pause on recovery bursts).

- **Universe ruling (a)+(c) executed (user, 2026-07-17): T2T stocks stay live-excluded (self-healing); 15 ghost master rows deactivated; EOD-ingestion outage discovered** (ledger §Decisions + §Universe deactivation). New committed `scripts/deactivate_dead_stocks.py` (+4 real-DB tests incl. the T2T canary: a `SYMBOL-BE`-only listing must NOT be deactivated — ruling (a) keeps surveillance-series stocks active in the master with live exclusion done naturally by the plain-symbol join, and the exclusion self-heals when NSE returns a stock to the EQ series). Executed after a dry-run diff that caught and corrected the earlier misclassification (the "16 stale tokens" were 15 T2T series-moves + 1 delisting): 14 `dead_no_listing` (gone from Kite under any symbol/series/exchange/name — recent corporate deaths like GUJGASLTD/JBCHEPHARM/RELINFRA plus v1 master noise like NIFTYNXT50/EFCIL-RE) + 1 `moved_bse_only` (AVAILFC); active master 2,348 → 2,333; cumulative `forensic_stocks_deactivated` + documented one-UPDATE reversal; idempotent re-run for future delistings. Future re-inclusion path recorded (§Decisions + memory): suffix-mapping scoped to the Investment engine if it graduates in Phase 6, with per-style ineligibility and the EOD watch-only rider. Bycatch incident (pre-existing): **EOD ingestion down since 2026-07-02** — Celery never ran in the v2 era; ohlcv_1d frozen; 07-15/16 soak prev-day levels used 07-02 dailies; restart + catch-up backfill queued as next action.
- **kite_instruments stale sweep (2026-07-17): `sync_instruments` now deletes rows absent from Kite's dump; EXECUTED — 1,582 carcasses swept, the "16 stale tokens" resolved.** The dump is Kite's complete tradable universe for the kept segments, but the upsert-only sync never removed rows that left it: 1,584 dead rows (expired CE/PE contracts + delisted/moved equities) accumulated over ten days of logins and kept JOINing into the live worker's subscription universe — the deterministic `invalid token` repair failures were 15 stocks moved to NSE's T2T series under rotated tokens + 1 delisted outright (split corrected 2026-07-17 during the (c) execution), not refreshable tokens. The sweep deletes rows whose `synced_at` predates the run's watermark, fenced by a partial-dump tripwire (`_SWEEP_MIN_FRACTION = 0.5`: a dump under half the table size skips the sweep with a WARNING instead of mass-deleting on a truncated CSV). Live run: 60,751 upserted / 1,582 swept (forensic snapshot `forensic_kite_instruments_stale_20260717` kept); table now equals the dump exactly; worker join 2,056 → 2,037. bug-hunter (no tier-A; atomicity/MVCC/watermark proven by executed repros) found two MEDIUMs, both fixed pre-commit: the fraction guard counted stale rows in its own denominator and could self-wedge permanently once stale ≥ live → two-tier sweep (`_HARD_SWEEP_DAYS = 7` hard tier deletes week-deep absences BEFORE the guard computes, mutation-proven wedge-recovery test); and the multi-MB download/parse/mapping ran on the event loop the tick consumer shares → `asyncio.to_thread`. Also: watermark now derived from the mapped data (backward-clock-step immune); `map_instrument_rows` skips `TypeError`/`InvalidOperation` rows instead of crashing the sync. New `tests/test_instrument_sync.py` (real DB, stubbed `build_kite`): token-rotation sweep, partial-dump tripwire, worker-join seam through the real `_build_token_stock_map`, surviving-row refresh, hard-sweep wedge recovery, exact-50% boundary, swept-count log honesty — sweep canaries stash-proven to fail on the old code. Audit bycatch pinned for user decision (ledger §Decisions): 296 active master stocks are trade-to-trade series (`SYMBOL-BE`) listings the equality join has NEVER covered; ~15 more are long-dead master rows.
- **Gap-fill routed through the shared `ThrottledKite` + three latent gap-fill bugs fixed (2026-07-17).** The unthrottled `kite_client.fetch_historical` (root of the 07-13 rebuild failures — ~6,165 raw REST calls at full universe) is DELETED; `detect_and_fill_gaps` takes the caller's `ThrottledKite` and `startup_gap_fill` shares ONE across the loop (~3 req/s ≈ 35 min full-universe, documented as post-outage repair — bulk rebuilds are `backfill_intraday.py`). bug-hunter passed the diff and confirmed three pre-existing latents in the same seam with executed repros, all fixed + stash-proven same session: (1) HIGH — gap-fill windows were sent as UTC wall time that Kite reads as IST, shifting every request 5.5 h into the past: mid-session outage fills silently returned nothing and overnight fills logged success while re-upserting yesterday (now naive IST per the repair-script convention, regression-tested); (2) HIGH — a mid-loop DB error poisoned the single long transaction and the final COMMIT silently became a server-side ROLLBACK, discarding every fetched row while the worker started normally (now commit-per-instrument + rollback-on-failure; the regression test shows `[]` — total loss — on the old code); (3) MEDIUM — a dead session token was swallowed per-timeframe and ground all remaining paced calls (~35 min futile startup delay); `TokenException` now aborts the fill with a CRITICAL log while stale-instrument `InputException`s stay isolated per-timeframe. test_gap_fill.py rebuilt around the real-DB seam (exact-Decimal assertions, failure isolation, dead-token abort, no-data skip; v1 tautology removed); +3 startup behavior tests; six canaries stash-proven to fail pre-fix.
- **Streaming replay digest (2026-07-17): `app/broker/replay.py` replays arbitrarily large recordings in constant memory; all four soak recordings pinned, replay ≡ live EXACT.** The buffering harness materialized every item, every event, and every canonical line — exit-137 OOM on any full-day recording (open since 07-13). Now streaming end-to-end: `iter_recording` (single-pass validated parse; torn-tail tolerance via one-line lookahead), `iter_events` (generator, FFI call pattern unchanged), `replay_stream(path, emit)` → `ReplaySummary(lines, events, committed, triggers, digest)` with ATOMIC emit (`.tmp`+rename on success, unlink on failure); old list APIs kept as thin wrappers over the same generators — pinned golden digest byte-identical through both paths (proven by executing old vs new). Measured ~38 MB flat RSS / ~3 min per 600 MB recording. Replay suite 11 → 19 (digest/emit equality, single-pass + laziness canaries, emit-clobber regressions); bug-hunter: no tier-A, MEDIUM emit-clobber (truncate-before-replay destroyed the `--emit` target on failed runs) fixed pre-commit, LOW error-precedence drift accepted (fail-faster, message-only), zero-event emit now an empty file (documented). Digest pins (ledger §Streaming replay digest): 07-13 `88da0c16…` (partial reconciliation — runs 1–3 logs lost), 07-14 `5bfdcd35…` (828,180 committed / 14,097 triggers — EXACT vs worker counters), 07-15 `3fba10ff…` (847,995 / 15,493 EXACT), 07-16 `cff17a55…` (848,693 / 14,654 EXACT).
- **Re-soak ×2 on the optimized worker (2026-07-15 + 2026-07-16): STABILITY PASS both days; latency budget p99 ≤ 50 ms MET; (10,20] tightening target NOT reached — gate stays 50 ms** (ledger §Fourth soak). 9.35 M / 9.54 M ticks, ~848 k committed candles each day, 0 skipped, queues ≤ 2/10,000 throughout; three more Kite 1006 drops (incl. the first back-to-back double drop, 07-16 14:42) recovered unattended in 8–17 s; both recordings lossless against worker counters. Optimization effect honest-recorded: processing p50 7.5 → 5.0 ms both days, processing p99 into (10,20] on 07-15's main segment, max 98 → 89 ms; total p99 bucket unchanged. The End-Phase-3 "full-session soak clean" gate criterion is now MET on both stability and latency. Ops: 07-15's 3.3-min-late start left a thin 09:15 open bucket — repaired same night via `repair_morning_window.py --day 2026-07-15 --until-ist 09:20` (1,872 bars; 5m 09:15 volume 40.6 M → 185.9 M; 15m/1h recomputed 2,039/2,041 rows; RELIANCE 15m == 5m agg exactly; the deterministic stale-token set grew 14 → 16, re-sync still the fix); 07-16 was the first soak started inside the pre-09:15 runbook window (its `stale=2042` counter = the session guard rejecting one pre-open snapshot tick per instrument, benign).
- **Latency budget restated + the soak-#3 optimization slate (user ruling 2026-07-14): unchanged-price SET dedupe + commit-burst batching.** The budget is now **p99 ≤ 50 ms tick→publish at full universe (~2,055 instruments)** — the original 10 ms was authored for 200–500; three independent full-scale soak measurements pinned steady-state p50 7.5 / p99 (20,50] (PERFORMANCE.md + PHASES.md + ledger §Decisions). The two audit-scoped optimizations target the (10,20] bucket; the next soak measures. (1) `_publish_ltp` skips the `ltp:{stock_id}` SET when the price equals the last successfully-SET value within `_LTP_RESET_S` (10 s — bounds the one new exposure: after a redis data loss the worker can't observe, an unchanged-price key stays absent ≤10 s with paper_broker on its daily-close fallback; observed execute() failures clear the whole dedupe cache so every stock re-SETs as it next ticks); SET still fires on first sight/change/keep-alive, intra-batch duplicates dedupe with A→B→A re-SETting in pipeline order, cache learns a SET only after execute() succeeds; the subscriber-gated PUBLISH leg keeps per-tick cadence. (2) Committed candles now reach the writer as ONE list per batch instead of one queue put per candle (a :30 close paid thousands of lock/notify cycles inline in the tick loop); the writer unwraps and persists per-candle with per-candle retry; sentinel/liveness/bounded-drain semantics unchanged; heartbeat `writer_q` depth now counts bursts. bug-hunter (executed repros): no tier-A; a MEDIUM (the unobservable-loss window at 60 s) and a LOW (buffer-time redis spy couldn't pin the queued/execute seam — proven by a mutant passing 65 tests) both fixed pre-commit. Live-worker suite 30→38 tests; targeted live suite 66 green; replay byte-exactness untouched.
- **`scripts/repair_morning_window.py` — scoped intraday morning repair from official Kite candles** (born from soak #3's late start, 2026-07-14): refetches official 5m for `[09:15, --until-ist)` on `--day` across the full active-EQ universe via `ThrottledKite`, upserting with ON CONFLICT **DO UPDATE** (deliberately unlike `backfill_intraday.py`'s never-replace: wrong live-minted partial rows must be overwritten), then recomputes the enclosing 15m/1h buckets as exact 5m aggregates. Dead-token tripwire (aborts if the first 20 calls all fail), isolated `invalid token` failures tolerated and counted, `--dry-run`. First production run repaired 2026-07-14: 5,758 5m bars, 15m/1h 09:15 buckets recomputed (2,030/2,041 rows), RELIANCE 15m == its 5m aggregate exactly. bug-hunter verified the executed run wrote ZERO wrong rows (re-derived all 2,030+2,041 bucket rows from their 5m children on the live DB — 0 mismatches) and found 5 latent/test issues, all fixed same session: recompute now loops EVERY 15m/1h bucket the window touches (was hardcoded to one — a wider `--until-ist` would have left stale buckets over repaired 5m); same-day runs refused before 15:40 IST (forming buckets must not be stamped complete); the forming-bar test canary was vacuous (PK-collision silently dropped it — proven by SQL mutation) and is now real; the dead-token tripwire fires on 20 consecutive failures ANYWHERE (was head-only); raw `requests` transport exceptions no longer crash the run. +8 tests total (window half-open bounds + IST/UTC canon, DO-UPDATE-replaces vs outside-window-preserved, failure tolerance, head + mid-run tripwire, aggregate exactness with a REAL forming-bar exclusion canary, wider-window bucket-loop regression).
- **Watchlists (3.5 deferred item) — user-owned named stock sets + watchlist-scoped alert fanout.** New `watchlists`/`watchlist_items` tables (reversible migration `r4s5t6u7v8w9`, up→down→up proven; CASCADE FKs; `stock_id` indexed because Postgres doesn't auto-index FK columns), ownership-scoped service (a foreign watchlist id is indistinguishable from an absent one — 404, existence never leaks) and CRUD API under `/api/v1/watchlists*` (create 201 / duplicate-name 409 / empty-name 422 / idempotent add+remove / items joined with symbol+company, sorted by symbol). `/ws/live` `subscribe_alerts` accepts `{"watchlist": id}`, combinable with `styles`: the id is validated BEFORE any subscription state mutates (fail closed — a foreign/absent watchlist gets an error frame and NO subscription, never a silent unscoped fall-back); the stock set SNAPSHOTS at subscribe time (re-send to refresh, documented in the protocol header); an empty watchlist scopes to NOTHING (the None-vs-empty distinction is pinned by tests on both the service and the WS seam). Frontend: a /watchlists manager page (create/delete, symbol-search-to-add, remove, with loading/empty/error+retry states) and a watchlist scope selector in the AlertBell panel; `useAlertStream` re-applies BOTH scopes after a reconnect. +13 backend tests (CRUD, ownership isolation, WS seam through both sides of the stream) and +10 frontend tests (157 total). Test-harness bycatch, fixed: the app's module-level POOLED engine poisoned successive TestClient event loops for any DB-touching WS path — "Task attached to a different loop" (the Celery pool-×-loop lesson, harness edition); test_ws_alerts.py now disposes the app engine per test. Caught by the end-to-end browser smoke (real stack, strict in-panel assertions — the first smoke pass was a FALSE POSITIVE that matched page text outside the panel): (1) choosing an option in a Select nested in the Popover CLOSED the panel and swallowed the selection — nested floating layers portal to document.body outside the panel ref; the Popover outside-mousedown handler now ignores select layers (+stash-proven regression test); (2) `SimpleSelect` rendered the raw VALUE in its trigger (invisible while every caller had value≡label; watchlists select by id → "4" instead of "Momo") and leaked the `__empty__` sentinel when no ''-option exists — the trigger now resolves the option label with placeholder fallback (+2 tests); (3) the backend q-search is fuzzy + alphabetically ordered, so an exact ticker ranked below dozens of substring cousins and never made a top-8 list ("RELIANCE" lost to -ANCE matches) — the add-stock search re-ranks client-side (exact symbol → symbol prefix → name prefix) over a 50-row fetch. Final smoke: watchlist created and populated through the real API, bell scoped via the selector, two alerts XADDed into the live stream — exactly ONE row rendered in-panel (in-list stock), the out-of-list alert filtered server-side, zero console errors.
- **Tailwind v4 token-class migration — the themes render again.** The v4 upgrade had silently dropped the `[--color-x]` arbitrary-value shorthand, so every token-driven utility class (898 occurrences across 46 files) computed to NOTHING — sidebar, topbar, cards, zebra rows, hover states, rings: all transparent; the app survived on body background, inherited text color, and inline styles, and 4 of the 5 themes were largely cosmetic fiction. All sites mechanically converted to the v4 `(--color-x)` form (the two comment references to the old syntax deliberately excluded). Verified in headless Chrome across ALL FIVE THEMES: sidebar/topbar/surface chips compute opaque theme-distinct colors; the opacity-modifier form `border-(--color-profit)/20` compiles to `oklab(… / 0.2)` per theme; daybreak renders as a true light theme for the first time; carbon's amber accent system correct; zero console errors. Riders: dashboard duplicate-React-key warning fixed (the static signals-table header array ends with two "" action columns, so label keys collided — positional keys now; warning verified gone in-browser), StocksPage filter-count badge moved to the accent-bg/accent AA pair (same fix as the AlertBell badge), Popover triggers now announce `aria-expanded`/`aria-haspopup`. Suite 147 green; eslint + tsc clean.
- **Alert UI (3.5 deferred item) — the live alert stream gets its surface.** Topbar `AlertBell` (unseen-count badge, index-math not length-math so the capped list can't drift it; panel via the shared Popover) fed by new `useAlertStream` speaking the `/ws/live` `subscribe_alerts` protocol: all-string stream frames parsed+validated (malformed dropped), bursts buffered and flushed as ONE state update per 200 ms window — never a render per frame, 100-alert cap, 3 s reconnect that re-applies the current style filter, close 4401 → "sign in again" (never a reconnect loop). Rows: sid→symbol via TanStack Query on `/stocks/{id}` (cached forever, `#sid` fallback while loading); tag glyph+tone from `TriggerTag::as_str` (▲ cross_up / ▼ cross_down / ◆ zone_enter / ≈ near / ⚡ volume_burst — never color-alone); source labels (PDH/PDL/entry zone/SL/TP/S-R/volume); `formatCurrency` price; style + IST time (Intl, Asia/Kolkata). Style-filter chips drive the server-side filter (replace semantics, `aria-pressed`). Shared Popover: Escape-close added (+test) and the panel moved to an INLINE solid `var(--color-surface)` + `--color-border-strong` per the floating-panel rule. Dev proxy fixed with `ws: true` — the string-shorthand proxy never forwarded WebSocket upgrades, so `/ws/live` could not connect through vite at all. +14 frontend tests; eslint+tsc clean. Manual smoke in headless Chrome against the REAL stack: XADD into `alerts:live` → badge → open → RELIANCE row with symbol resolved → chips → Escape; solid panel verified by computed-style probe. ui-reviewer: PASS-WITH-NOTES, no HIGH — taken same session: badge moved to the accent-bg/accent pill pair (white-on-accent failed AA in 3 of 5 themes), non-numeric price strings refused at parse (₹NaN guard), focus-visible rings on bell+chips, 10px type floor, +2 tests (unknown-tag degradation, 99+ cap) — frontend suite 147 green; pre-existing idiom items (raw-button topbar chrome/44px, Popover aria-expanded+focus, daybreak warning contrast) folded into the Tailwind-migration slice.
- **Found by the alert-UI smoke (recorded; own slices):** (1) **The Tailwind v4 upgrade silently broke the repo-wide `[--color-x]` class idiom** — v4 syntax is `(--color-x)`, so all 619 occurrences compute to NOTHING (sidebar/topbar/panel backgrounds are literally `rgba(0,0,0,0)`; the app looks right only via body background, inherited text color, and inline styles). New alert files use the working v4 syntax; dedicated migration slice recommended (mechanical rename + visual pass across the 5 themes; frontend-only, safe before the soak). (2) Dashboard emits a duplicate-React-key console warning with zero alerts involved (suspects: `key={d}` / `key={h}` at DashboardPage.tsx:275/337). (3) `make create-admin`'s default email `admin@trading.local` is rejected by the login endpoint's EmailStr validation (pydantic refuses `.local`) — the documented bootstrap admin could never log in; default is now `admin@trading.com`.
- **Publish-gating hardening — the two LOWs deferred from the perf-fix review, closed with the ledger recipes verbatim.** (a) `PUBSUB CHANNELS` cannot see `PSUBSCRIBE`, so a future pattern subscriber would have silently received nothing: `_refresh_watched` now checks `PUBSUB NUMPAT` first and holds `watched_channels = None` (publish-EVERYTHING sentinel) while any pattern subscriber exists; both publish gates are None-aware; the exact-SUBSCRIBE contract comment at the channel constants documents the fallback instead of a starvation footgun. (b) The watched-set refresh no longer rides the pulse branch — pulses are droppable under queue-full backpressure, so the refresh used to starve exactly when the box was saturated: it is now wall-clock inside `process_item` (any item kind, ≥ 1 s since last), which also closes a startup gap (the watched set began empty, so the first second of forming events published to nobody until the first pulse). +2 regression tests, both PROVEN to fail on the stashed pre-fix code; targeted live suite 50 green; bug-hunter re-review CLEAN with executed repros (fail-open keeps the previous watched value whole — no torn state; spy/None fallbacks; wrong-implementation catches). Separately: the previous session's deferred FULL three-leg gate ran green on the perf-fix commit exactly as shipped (731 backend / 131 frontend / 16 parity / 9 walkforward / 11 replay; `make check` exit 0).
- **Publish-path perf fixes (audit-driven; the p99 < 10 ms phase target vs the soak's p50 ≈ 20 ms/batch)** — the audit showed ~112 of ~127 ms per full 2,000-tick batch was the Redis leg, mostly payloads built + published to channels with ZERO subscribers. Applied: (1) subscriber-gated publishes — `watched_channels` refreshed once per pulse via `PUBSUB CHANNELS` (~0.3 ms); LTP/candle payloads neither serialized nor published for unwatched channels; the `ltp:{stock_id}` KEY is ALWAYS SET (paper-broker contract, test-pinned); observable change: a client subscribing mid-second may miss ≤1 s of pushes (REST-reconcile is the documented model); exact-SUBSCRIBE-only contract commented at the channel constants (PSUBSCRIBE is invisible to PUBSUB CHANNELS). (2) hiredis dependency (parser ~2× faster, confirmed active; zero behavior change). (3) Recorder block-buffered, ONE flush per queue item instead of a per-line flush syscall (~4 ms/batch back); crash-loss window one line → one item (≤1 s); SIGKILL repro proved the file stays line-aligned and replay loads it. (4) Measurement honesty: histogram split into end-to-end (the phase metric) + dwell (GIL queue wait) + processing, 7.5/15 ms buckets (a true 11 ms median used to report as "20"), avg batch size in the shutdown line, `sys.setswitchinterval(0.002)` in worker main (dwell p50 5.2→1.2 ms measured). (5) Rust: `LiveBook.on_tick`'s per-tick Vec replaced with a reusable scratch buffer (no-alloc discipline). Rejected: coalescing forming events in Rust — ~0 win at Kite's conflated cadence and it breaks replay byte-exactness. bug-hunter: LOW-only; two hardening items deferred with exact recipes in the ledger. +3 behavioral tests; 56 live-suite tests green; 55 cargo tests; synthetic golden byte-stable. **Full three-leg suite deliberately deferred to next session (budget) — run it before new work.**
- **v1 tick-consumer auto-start REMOVED** (next-soak pre-work; root cause of the 2026-07-10 dual-writer incident): `app/main.py` lifespan no longer resumes the v1 consumer when a valid token exists — that auto-start armed a second candle writer on every uvicorn (re)start and wrote off-canon candles TWICE during the first soak (zombie 09:56–11:06; drowning 13:01→close restart, 44 min behind real time — see phase-03 ledger §post-close forensics). The live worker owns the candle tables; the v1 consumer now starts only via the explicit admin endpoint `POST /broker/kite/consumer/start` (kept, with `/stop` and the shutdown cleanup). Regression canary `test_lifespan_never_starts_v1_consumer` proven to FAIL on the pre-fix code (seeded valid admin token → lifespan called start_consumer) and pass on the fix.
- **Tick triggers + alert stream (slice 3.5 core)** — the live layer's first alert surface: host-configured watch levels evaluated INSIDE the Rust live engine on every accepted tick (`engine-core/src/triggers.rs` + `LiveEvent::Trigger`), with strict armed/re-arm hysteresis so a choppy tape cannot spam (Zone fires on first observation inside and re-arms on exit; Cross is transition-only — never on first sight — with a basis-point re-arm band; Near is a proximity band; VolumeBurst compares the FORMING candle's partial volume against `mult ×` a 20-session per-bucket average and re-arms per bucket). Levels are INPUT exactly like ticks: the worker records every accepted `set_levels` as an `{"k":"lv"}` line, so replay reproduces trigger events deterministically — and recordings WITHOUT lv lines replay byte-identically (the 3.4 synthetic golden digest is untouched, proven by the existing test). Level sources (`app/broker/live_levels.py`): PDH/PDL crosses from the previous 1d candle (high/low are derivation-identical to session-aggregated bars; only close differs), entry zones (±0.5%, mirroring §2.5 proximity) + SL/TP proximity for ACTIVE signals, S/R crosses from the FROZEN detector for signal stocks, 5m volume-burst baselines — refreshed every 30s by a dedicated thread (own loop + own engine, the writer-thread pattern) that enqueues only CHANGED stocks; the engine preserves armed-state for unchanged (id, kind) pairs so refreshes never re-fire. Signal-level ids are stable 48-bit hashes of the signal UUID (JSON/JS-safe). Trigger firings are XADDed to the `alerts:live` Redis Stream (at-least-once class, MAXLEN~10k, retry + breadcrumb) enriched with source/style/signal_id from the host registry; `/ws/live` grew `{"subscribe_alerts": true | {"styles": [...]}}` — a per-connection XREAD tail pushing `{"type":"alert"}` frames, style-filtered. Alerts are provisional-layer OUTPUT only: nothing here gates, mints, or modifies signals, sizing, or backtests. Rust 55 tests (+15) · +23 backend tests (FFI contract, replay-with-levels determinism + golden compat, worker alert seam, level construction against the real DB incl. a payload-passes-real-FFI canary, WS fanout through both sides of the stream). Deferred to follow-up slices: forming-candle provisional confidence + per-style leaderboards (needs the O(1) incremental factor design per plan §2), watchlist-scoped fanout (watchlists have no model yet), alert UI.
- **Review fixes on slice 3.5** (quant-verifier FAIL→fixed + bug-hunter BUGS-FOUND, both 2026-07-10; the HIGH was independently confirmed by executed FFI repros on both sides): (1) HIGH — S/R level ids were rank-indexed from a fixed base, so a stock with TWO active signals produced duplicate ids, the engine's all-or-nothing validation rejected the stock's ENTIRE level list, and `mark_sent`-at-enqueue made it permanent — the most signal-active stocks would have run the whole session with a dead alert layer. S/R now computes once per (stock, timeframe) and ids are identity-derived (sha256 of timeframe:zone_type:price), which also stops rank reshuffles from resetting armed-state or breaking consumer (id, day) dedupe. (2) MEDIUM — levels could be lost silently two ways (drop-oldest eviction of a queued "levels" item; engine rejection after producer-side `mark_sent`): the ack now lives with the CONSUMER (`on_levels_applied` → `mark_sent` under a lock, fired only after engine accept), so evicted or rejected level sets re-send every refresh cycle — loud, never divergent. (3) MEDIUM — `_active_signals` gained `ORDER BY id` (order-sensitive change detection churned recordings on Postgres row-order flips). (4) LOW — statics restricted to the subscription set (`stock_id = ANY(:sids)` — no more per-tf engine state for never-ticking stocks); `_apply_levels` catches ANY per-stock exception (a malformed payload can't strand the chunk's other stocks); alert XADDs pipeline as one round trip per batch (an open-auction burst must not serialize hundreds of RTTs inside the latency window); vburst configs whose threshold truncates to zero and cross re-arm bands ≥ 100% are refused at validation (a permanently-silent watch is a host bug, fail loud). +Rust validation tests, +2 regression tests (two-signals-one-stock passes the real FFI; consumer-ack resend).
- **Found & fixed by the 3.4 gate run:** the Phase-0 chain-selection test fixtures hardcoded expiry `2026-07-09` — it expired overnight and flipped "nearest expiry" to the far one (first suite run after the date rollover). Fixtures are now wall-clock-relative (`today+20/41/69d`); the ingestion tests keep their fixed historical dates (correctly time-independent).
- **Review fixes on slice 3.4** (bug-hunter: 1 HIGH, 2 MEDIUM, 2 LOW — all addressed): recording is now FAIL-OPEN and written only AFTER the engine accepts a batch (a full disk can no longer starve candles/LTP for the day, and a raising batch is neither consumed nor recorded — symmetric with replay, which also kills the bad-price batch asymmetry); the recorder is line-buffered with a newline-prefixed header so a hard crash loses at most one line and the torn tail cannot fuse with the restart's header; `load_recording` shape-validates every line (typed ReplayError with file:line) and tolerates exactly one artifact shape — a torn line immediately before a session header. +5 regression tests.\n- **Record/replay harness + latency instrumentation (slice 3.4)** — live-worker recordings are now SELF-DESCRIBING (a session-header line with open/close/tfs precedes the tick/pulse stream; a crash-restart appends a new header, mirroring the fresh in-memory book a restart actually builds). `app/broker/replay.py` replays a recording through a fresh `tradecore.LiveBook` per header and emits a canonical sorted-key JSONL event stream + sha256 digest — byte-identical to live by construction, and the ONLY ground truth this layer has (no v1 baseline). Committed synthetic golden (61 events/22 committed: pre-open rejection, volume baseline + counter reset, cross-bucket commits, late tick dropped by 1m yet absorbed in-bucket by 5m/1h, pulse-driven closes) + a worker-seam fidelity test proving replay reproduces the writer-queue stream even when the live run skipped stale/unknown ticks (they are filtered BEFORE recording). `make replay` joins the `make check` chain (`-m replay`, ~4s; runs inside the standard pytest harness, so it needs the dev stack up and must never run concurrently with another pytest session on the shared test DB). Tick→publish latency: fixed-bucket `LatencyHistogram` (1/2/5/10/20/50/100ms), stamped at the WS-callback enqueue, observed after the redis pipeline, p50/p99/max logged at shutdown — the p99 < 10 ms phase target gets its verdict from the soak session, not CI. +11 tests.
- **Live-worker process + `tradecore.LiveBook` binding (slice 3.3)** — dedicated process (`python -m app.broker.live_worker`) replacing the v1 in-app asyncio consumer with the plan §2 topology: KiteTicker thread → bounded stdlib queue (drop-oldest for tick batches — stale LTP beats a crashed callback; time pulses share the queue so tick/pulse ordering is serialized and replayable) → consumer thread → ONE PyO3 batch call into the 3.1 LiveEngine → sync redis-py pipeline (`SET ltp:{stock_id}` TTL 600 + LTP/candle pub/sub, keys imported from tick_consumer — never retyped) → committed candles through a BLOCKING writer queue (a candle close is never dropped) → writer thread with its OWN event loop and engine (the Celery pool-×-loop lesson) → Decimal-exact upsert → Celery signal trigger after commit. Token expiry = exit-for-restart (codes 3/4 for the supervisor); `--gap-fill` opt-in startup REST backfill; `live_record_path` JSONL record hook captures the exact tick+pulse input stream (the 3.4 replay seed). PyO3 `LiveBook`: money strings in / raw i64·1e-4 out (`Decimal(raw)/10**4`, never f64), GIL released around engine compute, fail-loud on bad prices, reject counters exposed. +15 tests. First market-hours soak scheduled next trading session.
- **Session-aligned `ohlcv_1h` rebuild (slice 3.2)** — migration `q3r4s5t6u7v8` deletes the v1 UTC-hour-floored table body (8,180 rows, all at …09:30/10:30 IST anchors plus post-close pollution — a different time base from Kite's own 9:15-anchored 60minute history) and rolls up session-aligned 1h candles from the 11.5M complete 5m bars via ONE shared SQL definition (`app/services/ohlcv_rollup.py`, used by both the migration and the async service — cannot drift). Canon per slice 3.1: buckets 09:15…15:15 IST with the 15:15–15:30 stub; pre-open/post-close bars excluded (backfill guard); a bucket mints only once fully ended at an injected `as_of` cutoff (forming hours never land complete); `ON CONFLICT DO NOTHING` reruns. Applied on dev: **1,074,456 rows / 2,036 stocks, anchors exactly the canonical seven, zero incomplete**. Downgrade documented as empty-table (pre-rebuild rows were garbage; the 5m source re-derives). The interim v1 aggregator floor is patched to the 03:45-UTC session anchor (arithmetically identical for 1m/5m/15m; 1h moves to canon) so live minting stays consistent until the 3.3 LiveEngine replaces it — **restart the backend before the next session open** to load it. +6 tests.
- **Rust LiveEngine core (slice 3.1)** — `engine-core/src/live.rs`: session-aligned tick→candle state machine replacing the v1 `CandleAggregator`'s three structural defects (UTC-hour floors — 1h candles landed at 08:30 IST; no session guard — pre-open ticks minted candles; close-only-on-next-tick — the session-last candle never committed). Sessions enter as PARAMETERS (epoch open/close; the NSE calendar/clock/timezones stay host-side); bucket canon pinned: `[open + k·N·60, min(open+(k+1)·N·60, close))` ⇒ 1h at 09:15…15:15 + 15:15–15:30 stub, 1m/5m/15m identical to Kite/backfill times (ARCHITECTURE.md §Live bucket canon; the Phase-3.2 `ohlcv_1h` rebuild mirrors it). Forming vs Committed are distinct event types (provisional layer can't leak into committed persistence); commits happen on next-bucket ticks OR host `on_time` pulses; committed (tf, period) at most once per lifetime (no repaint by construction); session-guard/late/bad-price rejections counted, never silent; volume = cumulative day-counter diff with reset re-baselining. 15 cargo tests incl. a 5,000-tick LCG partition property (committed candles ≡ per-bucket fold of the tick stream, all four TFs). PyO3 `LiveBook` binding follows with the 3.3 live-worker.
- **Review fixes on slice 3.0** (quant-verifier PASS-WITH-NOTES; bug-hunter 4 LOW/latent, all addressed): explicit IST session-dating in setups (`_ist_date` — removes the NSE-hours UTC-date coincidence); **top_gainer_925 exact-tie ranking made deterministic** ((pct, symbol) key — was dict-insertion-order dependent, i.e. live planner order vs walk-forward alphabetical; gainer golden replayed byte-stable after the change); **rust-dispatch multiplier guard narrowed to the true tradecore 1d path** — the intraday python fallback now applies multipliers instead of raising (a rust deployment would have blacked out intraday multiplier profiles); loud warnings for dual-exchange duplicate symbols in the 9:25 pool and for 1m+prev-day-setup profiles (375-bar session > 300-bar window cap ⇒ permanently fail-closed conditions). +3 tests.
- **Phase-3 pre-work (slice 3.0)** — the 8c quant-verifier MEDIUMs, closed before any realtime slice: **(1) `_prev_day_hlc` fails closed on intraday windows** — the old `iloc[-2]` fallback served the previous BAR as "previous day", so a live PDH/PDL gate would have passed on a five-minute range (detection data-driven: min index gap ≤ 1h; daily windows keep the fallback and the 1d goldens replay through it). **(2) Live pipeline builds real intraday session context**: per-stock prev-day OHLC aggregated from the window's own sessions (fails closed under 3 present sessions — cap-truncation guard) and the 9:25 universe cross-section (consulted only for decision bars starting ≥ 09:20 IST — the 8c-4 look-ahead boundary now enforced live too). Per-symbol math EXTRACTED to `app/profiles/session_context.py`; the walk-forward delegates to it — one implementation on both sides, 9/9 goldens replay byte-stable. **(3) `weight_multipliers` reach live scoring** (slice-7 gap closed): services dispatch reproduces the exact BacktestEngine sequence (`run_all_factors → apply_weight_multipliers → score_from_factors`); `{}` is byte-identical to the frozen path (all seeds carry `{}` — zero live change today); ENGINE_IMPL=rust refuses multipliers loudly (no FFI input yet — flows-guard discipline). **(4) Found en route: `opening_gap` measured the gap at the decision bar's open** on intraday windows (mid-session price) — now the decision session's first-bar open; no seeded profile affected. +26 test functions (28 cases) incl. 4 behavioral canaries proven to FAIL on the stashed pre-fix tree (the drop-canary reproduces old code minting a suggestion off the previous bar's high). Intraday profiles remain INACTIVE — walk-forward verdicts unchanged; activation is a Phase-6 tuning decision.

### v2 Phase 2 — Strategy profiles (in progress, started 2026-07-05)

- **Look-ahead purged from the 9:25 gate** (8c-4, quant-verifier HIGH): session-first 5m decision bars (close 09:20, fill 09:20) were being gated by the 09:25 cross-section — data from 5 minutes after the fill. The screen now exists only for decision bars starting ≥ 09:20; earlier ones fail closed exactly like live pre-09:25. **gainer_925 regenerated: 13,497 → 12,935 trades and totPnL +116.3% → +56.2% (sharpe −0.86, maxDD 32.1) — half the apparent profit was the look-ahead.** Golden run-block gains `schedule_approximated: true` for time_0925 profiles (per-bar minting ≠ once-daily live schedule; never read golden-vs-live like-for-like); backfill `--until` clamps to yesterday IST (forming bars can never be stored complete). +1 regression test; findings 2/4 (live-pipeline intraday context wiring, top_gainer on 15m) recorded as Phase-3 pre-work in the report
- **Intraday walk-forwards — evidence for the Phase-3 profiles** (slice 8c-3): the walk-forward runner accepts every parity-pinned timeframe (`1d/5m/15m` whitelist; unpinned still refused), reconstructs session context offline — DatetimeIndex windows, per-session prev-day OHLC, and the 9:25 universe cross-section from the profiles' own 5m bars — and feeds `session_last_bars` to the engine off-1d (never on 1d: all five 1d goldens replay byte-identical through the whole changeset, regen prints "(unchanged)" ×5). Intraday digests carry bar timestamps (same-session trades can't collide; 1d digest format untouched). Goldens now allowed for explicitly-named INACTIVE profiles (evidence before Phase-3 activation; superseded never eligible). **Intraday verdicts (F&O 205/210, eval 2024Q4→2026Q2): pdh_pdl 1,224 trades · win 40.9% · −0.3% · sharpe −1.06 → FLAGGED; orb_15m 1,045 · 43.1% · +10.4% · sharpe −0.60 → FLAGGED (positive-sum, negative risk-adjusted); gainer_925 13,497 · 41.8% · +116.3% (≈+0.009%/trade) · sharpe −0.67 → FLAGGED. None earns activation as-specced.** Two hard-won correctness fixes: intraday loads chunk at 15 symbols/query (one 400-symbol fetch = >10M rows buffered = OOM on 16GB, observed twice) and cross-sectional context computes over the PINNED ran-set only — the generator originally ranked 9:25 gainers over all 210 resolved symbols while replays ranked over the 205 pinned ones, drifting gate outcomes +3.5% (harness caught it on first replay; §8 gate working exactly as designed). +8 unit tests (timeframe matrix, FFI seam sends timeframe+flags, digest timestamps)
- **Intraday parity fixtures — the off-1d oracle exists** (slice 8c-2): `python_backtest_intraday_reference.json` pins 5 cases of REAL backfilled bars (RELIANCE/TCS/HDFCBANK 15m × 31 sessions · RELIANCE/SBIN 5m × 15 sessions; QA-manifest-admitted, 2026-07-07) with data-driven session flags and **102 frozen-python oracle trades**. Both engines replay it EXACTLY: cargo (`python_backtest_intraday_parity.rs`, + an oracle self-consistency test that no trade spans a session) and a NEW dev-DB-free pytest leg (`tests/parity/test_intraday_parity.py` — python reproduces its own oracle; tradecore matches at 1e-12 pnl). `generate_engine_fixtures.py` gains the intraday job: bars bootstrap ONCE from the backfilled corpus at pinned windows, then live verbatim like every fixture. Engine 41 rust tests. **Intraday backfill completed (track T run 3): 15.3M 5m/15m rows, 210 stocks, full 739-session depth; QA manifest 416/420 admitted** (FORCEMOT gappy 10.1%, NIFTYNXT50 = index ticker, correctly no EQ data) — plan risk #6 (unverified Kite depth) closed
- **session_last_bar engine axis** (slice 8c-1, deferred from 8a): intraday trades must never span sessions — both engines gain per-bar session flags as a default-off freeze-extension (None = byte-identical to the frozen canon, proven by the untouched 1d oracle fixtures AND the 5 walk-forward goldens replaying digest-exact through the new wheel). Semantics, mirrored exactly: a flagged DECISION bar mints nothing (its fill would cross into the next session); an open trade force-exits at a flagged bar's CLOSE after that bar's SL-before-TP checks (a stop on the closing bar still exits at the stop). Flags are data-driven (`session_last_flags`: last bar of each IST session — half-days handled naturally, no clock math). FFI: `run_backtest_single(session_last_bar=)` / `run_universe(session_last_bars=)` with typed length validation at the boundary (no panics in core). Rust +4 axis tests against the committed oracle bars (all-false ≡ None; all-flagged mints nothing; close-out exit/price/pnl exact; SL-beats-session race) · python +8 (direct `_simulate_trade` semantics, helper, loud length rejection) · parity +3 (cross-language EXACT under synthetic 5-bar sessions on the live corpus; universe==single with flags; boundary rejection). Engine 39 rust tests **(1) HIGH — every recurring Celery DB task after a worker child's first died** with "Future attached to a different loop": task bodies ran `asyncio.run()` per invocation while the module-level engine POOLED asyncpg connections bound to the previous (closed) loop — the 5-min sweeper kept children warm, so the sweeper, FII/DII + equities-EOD chain, and nightly suggestions were all structurally broken in a real worker (invisible to the NullPool test suite; reproduced against the app's real factory). New `app/tasks/_runner.run_db_task` disposes the pool INSIDE each task's loop; all 10 task bodies converted (+2 regression tests driving the real pooled engine through back-to-back loops). **(2) Kite retry net never matched real transport errors** — kiteconnect re-raises raw `requests` exceptions, which subclass neither the builtins nor `NetworkException`; the first production backfill run died mid-universe on an uncaught `ReadTimeout` ~40 minutes after bug-hunter predicted exactly that. `_TRANSIENT` now covers `requests.exceptions.ConnectionError/Timeout`; the backfill catches `RequestException` (skip-and-continue) and aborts cleanly on `TokenException` (exit 4 — token death is a lifecycle event, not an error loop); every attempt now updates the rate-budget clock (no unspaced bursts after non-transient errors). **(3) Degenerate stop loss crashed the whole nightly**: a pivot swing-low exactly equal to the last close passes the class-cap check, then `compute_quantity` raises — one such stock killed the entire run (all profiles). New `app/signals/risk_guards.safe_levels` (reject-don't-crash, same semantics the backtest engines always had) wired into BOTH live paths + per-stock isolation in `run_profile` (+4 tests incl. the executed crash pair). **(4) Backfill resume-point poisoning**: unbounded `max(time)` would see the tick consumer's forming TODAY-rows, compute `start > until`, silently skip the entire historical fetch, and let the QA manifest blame "no data" — `_last_stored` is now `until`-bounded and `is_complete`-filtered (+1 regression test). Latent LOW finding recorded for backlog: trading-day walks use UTC dates (correct at all beat times; wrong only for ad-hoc runs 00:00–05:30 IST) and `same_day` validity ignores weekends (no seed uses it)
- **Shared throttled Kite REST client + intraday backfill** (track T): `app/broker/kite_rest.py` — `ThrottledKite`, the trading-domain-mandated single path for Kite REST (~3 req/s monotonic spacing, retry×3 with backoff held INSIDE the gate so every caller pauses when Kite pushes back). `scripts/backfill_intraday.py`: Nifty50+F&O 5m/15m history in ≤60-day chunks → `ohlcv_5m`/`ohlcv_15m` (`is_complete=true`, UTC via astimezone, 09:15–15:30 IST session guard drops pre-open artifacts); idempotent `ON CONFLICT DO NOTHING` — history is never replaced; reruns resume from each stock's last stored session; auto-syncs the instrument master when empty; aborts loudly (exit 3) if the historical add-on is missing. Session-completeness **QA manifest** (`tests/goldens/intraday_qa_manifest.json`): per (symbol, tf) depth/gap-ratio vs the NSE calendar over each stock's own available depth — gap > 5% ⇒ EXCLUDED, never patched (slice 8c pins intraday goldens only on admitted stocks). +20 tests (throttle spacing/retry/exhaustion, chunking, session-window bounds, IST→UTC exactness, never-replace on real PG, resume-point seam)
- **Walk-forward runner + §8 golden harness** (slice 8b): `app/backtest/walkforward.py` walks each ACTIVE 1d profile over pinned bounds in ONE `tradecore.run_universe` call — trade indices→IST dates, setup gates replayed as an exact python post-filter on the trade's factor snapshot (same evaluators as live; canary test pins the decision-window off-by-one), fills before `eval_start` dropped, survivors binned into calendar-quarter folds, metrics via the slice-8b ordering canon. Symbols with <300 completed bars before `eval_start` are EXCLUDED and recorded (window-canon invariance — results can't depend on `since`); `eval_start` pinned to **2024-10-01** (not the sketched 2024-07-01: the corpus starts 2023-07-03, giving only 245 prior sessions — 309 exist by October). TP mapping: rr/flat_pct direct; `flat_pct_trailing→flat_pct`, `ema_trail→flat_pct(min_target)` as documented approximations pinned per golden (`tp_approximated`). Goldens per profile (`tests/goldens/walkforward/`) embed config + config_hash + tradecore version + bounds + resolved symbols + row counts + exclusion manifest + per-fold & aggregate metrics + sha256 trade digest. Harness (`pytest -m walkforward`, `make walkforward`, wired into `make check`; dev-DB-skip like parity): config_hash match → replay → digest EXACT + every metric within max(5%, 0.05); failures print the Δ-table with **[§8 APPROVAL REQUIRED]** rows. `scripts/gen_walkforward_goldens.py` dry-runs by default; `--write` refuses out-of-tolerance moves without `--i-have-approval` (both refusal seams demonstrated). Golden schema lives in ONE place (`build_golden`/`spec_from_golden`/`compare_against_existing` in walkforward.py — generator and harness import it) after test-guardian mutation-tested the slice: its proven silent mutation (hardcoding `weight_multipliers=[]` at the FFI call passed everything — all seeds carry `{}`) is now killed by a stubbed-tradecore kwarg-seam test, plus stub-DB tests for the exclusion manifest/all-excluded/empty-universe refusal paths and a schema roundtrip + write-gate mode table. **First walk-forward evidence (2024Q4→2026Q2, ₹5L @ 2%): rrbo_basic/rrbo_trailing +41.3% · win 50.0% · sharpe +1.97 · maxDD 40.6% (58 trades) — the only positive profiles; dc1 −52.2% (289 trades) · dc2 −39.7% (218) · multibagger −1491.3% (1,425 trades, 1118-stock universe) flagged needs-tuning for the phase gate.** +37 unit tests + 6 golden-replay tests
- **Fixed a 100×-family sizing hazard on `POST /signals/generate`**: the admin endpoint defaulted `risk_pct=0.02` (fractional style) in a whole-percent convention — a default request risked 0.02% instead of 2%. Default is now 2.0 with a [0.1, 10] validation floor that rejects fractional-style values loudly (+3 regression tests)
- **NSE market calendar** (slice 1): `nse_holidays` table + `market_calendar` service (`is_trading_day`, `add_trading_days`, `last_n_trading_days`, `validity_offset_days`) + admin CRUD at `/api/v1/calendar/*`. Seeded with **46 holidays derived from bhavcopy session gaps** (2023-07→2026-07 — data is the authority for the past) + published future dates; the service warns when queried beyond coverage. Swing/positional signal validity now uses **real trading days** (5/30) instead of the 7/42 calendar-day approximation — a Diwali-week swing signal now correctly lives to the 5th session. Nightly generation, F&O EOD ingestion, and the chain recorder skip market holidays (+15 tests)
- **Signal expiry sweeper** (slice 2): spec §5's "runs every 5 minutes" sweeper now exists — lapsed active signals flip to `expired` + `expired_at` on the beat; previously NOTHING ever wrote expiry status (lazy query-filter only). Injected session/clock core, 3 tests
- **FII/DII flows finally reach signal generation** (slice 3): `get_market_flow_5d` (cash segment, last 5 TRADING days via the calendar) + `get_stock_block_deal_net_cr` wired into nightly, live, and admin generation — the ±5-weight §2.7 factor had scored zero on every signal ever generated. FII/DII ingestion is now on the beat (18:30 IST; was manual-POST only). +5 tests
- **EOD pipeline ordering fixed** (slice 3): there was NO daily equities-EOD ingestion task at all (`ohlcv_1d` only ever written by the Phase-1 backfill script) — nightly generation scored stale candles. New `ingest_equities_eod` beat task (18:40 IST) + nightly generation moved 18:00 → **19:15 IST** so it consumes same-day candles and flows
- **Corporate-action quarantine** (slice 6): raw bhavcopy stays canonical, never auto-adjusted; a discontinuity detector (|open÷prev_close−1| > 20%) runs after each equities-EOD ingest and quarantines the stock (`stocks.ca_flagged_at/_reason`) — quarantined stocks are excluded from every suggestion universe until reviewed. Policy + future adjusted-history path documented in ARCHITECTURE.md; goldens pin row counts/digests so any later adoption is an explicit regeneration. Reversible migration `p2q3r4s5t6u7`, +3 tests
- **Rust FFI extension + parity axes** (slice 8a): `tradecore.run_universe` exported (Rayon, input-order-preserving) and `weight_multipliers` + `tp_rule` (rr / flat_pct) plumbed through both backtest entry points (multipliers were hardcoded empty since Phase 1 — presets could never run on Rust); every trade dict now carries the post-adjustment factor snapshot for setup gating without rescoring. `TpRule` math is exact-Decimal-parity (one half-even round at 1e-4, i128 expanded scale); shared `app/backtest/tp_rules.py` feeds pipeline + both engines. Frozen `engine.py` gains `tp_rule` as a default-off freeze-extension — old oracle fixtures pass UNCHANGED; new `python_backtest_ext_reference.json` pins 3 axes × 6 stocks (bars joined from the base fixture, not duplicated). Rust 35 tests · parity suite +4 (axes exact on live corpus, universe==single, factor snapshot, unknown-kind rejection). `session_last_bar` deferred to 8c with the intraday data `app/profiles/pipeline.py` runs each ACTIVE profile — universe → frozen-python confluence scoring with real flows → setup gates → §6 risk-template TP (SL stays classification canon; reject-don't-clamp preserved) → Signal rows tagged with profile version, setup evidence, and volatility attribution. Supersede policy live (same-direction re-trigger skips; opposite direction supersedes; races resolve at the DB index under a per-stock savepoint). `GET /api/v1/suggestions/{style}` serves active suggestions with factor breakdown + setup evidence + profile identity; nightly per-profile Celery run at 19:25 IST (after the EOD data chain); on-close trigger stubbed for Phase 3. +11 seam tests (exact Decimal TP/SL/qty assertions)
- **Setup evaluators + seed profiles** (slice 5): `app/profiles/setups.py` — nine pure, direction-aware evaluators (`pdh_breakout` PDH/PDL momentum, `pdl_breakdown`, `opening_gap`, `relative_strength` vs NIFTY50, `dc1` (SR_ZONE sugar), `dc2` (prior-candle DC1 + confirmation), `orb_breakout`, `top_gainer_925`, `factor_score`) shared verbatim between the live pipeline and the walk-forward runner; fail closed on missing context; AND-combined with evidence persisted to `setup_trigger`. Import-time registry↔schema sync guard. Seed migration `o1p2q3r4s5t6`: 8 profiles with frozen config literals + hashes (dc1/dc2/rrbo_basic/rrbo_trailing/multibagger active; pdh_pdl/orb_15m/gainer_925 defined-but-inactive until Phase 3), seed-integrity test re-validates literals against the live schema. +24 tests
- **`strategy_profiles` schema** (slice 4): versioned, immutable profile rows (edits insert `(key, version+1)` and supersede — a DB partial-unique index enforces one live row per key); typed JSONB shapes (universe/setups/risk-template/validity discriminated unions, reject-don't-clamp) with `config_hash` for golden drift-detection; `min_confidence ≥ 70` CHECK — profiles may raise the gate, never lower it. `signals` gains `profile_id` (exact version, DELETE-RESTRICT) / `profile_key` / `setup_trigger` / `volatility_reduced` (§4 attribution now written by both generation paths) + a partial-unique index = DB-enforced one-active-suggestion-per-(stock, profile). Universe resolution lifted to `services/universe_service.py` (+ category-slug universes); strategy-lab API delegates. Reversible migration `n0p1q2r3s4t5`, +15 tests

### Adjudications F/G/H — star gap, volatility sizing, weight semantics (2026-07-05)

User rulings on the three spec-vs-code drifts found at the Phase-1 exit gate, applied per SIGNAL_ENGINE.md §8 (both engines in lockstep, oracles regenerated in the same commit; evidence: `scripts/adjudication_experiments_fgh.py`, table in the phase-01 report §Exit gate):

- **G — implemented in both engines**: Morning/Evening Star now require the star's real body to gap fully beyond the first candle's body (§2.2). 78% of previous detections were gap-false and their ±0.95 dominated best-pattern selection; the pinned 2y×49 corpus flips 807→599 trades, totPnL −78.7% → **+52.1%**, sharpe −0.27 → +0.13
- **F — implemented in both engines**: ATR(14) > 3% of price on the decision window → quantity reduced 25% (`volatility_adjusted_qty` / `volatility_reduced_qty`, exact `3·q // 4` integer arithmetic both sides; reduction to zero rejects). Applied in the backtest engine and BOTH live signal_service call sites
- **H — code semantics kept, spec amended**: per-sub-factor weights are canon (max applicable weight 150 + 10 multibagger). SIGNAL_ENGINE.md §3 table rewritten to match the code (+ Bollinger Bands 10 row + semantics note); §7 worked example regenerated from real engine output (POWERGRID, conf 75 — the old TATAMOTORS example never reconciled). Protected-spec guard lifted for exactly two edits on explicit user instruction, restored byte-identical
- **Fixture regeneration is now repeatable**: new `scripts/generate_engine_fixtures.py` recomputes all Python-oracle fixtures from the live engine while keeping the committed bars verbatim (backtest oracle 125→101 trades; 3 confluence windows re-scored; analysis fixture unchanged). Rust reproduces all three exactly
- **New standing baseline** (pinned corpus, anchor 2024-06-04): **599 trades · win% 40.1 · totPnL +52.1% · sharpe +0.13 · maxDD 96.2%** — the first positive corpus baseline; Rust `engine-cli` reproduces 599 in 172 ms. Star detections drop 1,778 → 394
- Tests: backend 453→**461** (8 new adjudication regressions) · Rust 30→**33** · parity 6 · quant-verifier signoff

### v2 Phase 1 — Rust engine core, adjudication, parity, 6,180× (2026-07-04)

Full report: `docs/phases/phase-01-rust-engine.md`.

- **3y EOD backfill** (ohlcv_1d was EMPTY despite v1 claims): 1.29M candles, 2,330 stocks + `scripts/backfill_eod.py`
- **engine/ Rust workspace** (rustc 1.96.1): engine-core (indicators/patterns/structure/factors/confluence/risk/backtest — incremental state + batch on top), engine-py → `tradecore` (PyO3 abi3), engine-cli (bench)
- **pandas-ta 0.4.71b0 semantics decoded** (SMA-seeded EMA, first-diff-seeded RSI, prenan ADX with first-DX seed, ddof=1 BBands) and locked by committed reference fixtures — machine-precision parity (≤1e-12 real-data error)
- **Five spec drifts adjudicated by the user with measured evidence** (see ARCHITECTURE.md): volume direction-match · RSI bands removed · pivot swing-SL shared live+backtest · last-300 window canon · HONEST fills (which revealed the old +1.8% totPnL as fill flattery — truthful baseline ≈ −108%; tuning is Phase 2/6 against reality). Applied to BOTH engines in lockstep + 8 regression tests
- **Cross-language parity suite** (`make parity`): exact factor scores/confidence/decisions on 96 real windows; exact 125-trade backtest lists; ENGINE_IMPL flag (python|rust) wired through signal_service with dispatch tests
- **Benchmark** (docs/PERFORMANCE.md): 2y×49 full backtest **883.8 s → 0.143 s (~6,180×, RAYON=6)**; 200-combo grid ≈50.5 h → ≈29 s
- Python engine frozen (bugfix-only; sunset after Phase-3 shadow week)
- **Exit gate passed 2026-07-05** (`/phase-gate`): full `make check` green — Rust 30 · backend 453 · frontend 131 · parity 6; quant-verifier signoff (adjudicated canon in both engines, look-ahead hygiene, money discipline, exact parity). Gate fixes: missed rustfmt pass committed (+ `backtest` added to the engine-cli usage hint); `ENGINE_IMPL=rust` dispatch now fails loud on FII/DII flows and answers off-1d timeframes with the python engine — only 1d is fixture-pinned (+2 regression tests); `parity` pytest mark registered; smoke reproduced the recorded bench to the trade (807 on the bench-day corpus). Three pre-existing spec-vs-code drifts recorded for user adjudication (§4 ATR>3% sizing · §2.2 star gap condition · sub-factor weight semantics) — see phase report §Exit gate


### v2 Phase 0 — Claude workbench, repo hygiene, triage, F&O recorders (2026-07-03)

The first phase of the approved v2 upgrade (`docs/UPGRADE_PLAN.md`). Full
report: `docs/phases/phase-00-workbench.md`.

#### Repo & tooling
- **Git initialized** (the 12-phase codebase was unversioned); pristine baseline commit, `.gitignore` hardened (fixed `lib/` pattern that would have ignored `frontend/src/lib/`)
- **Backend venv rebuilt** on a snap-proof Python 3.12 (previous interpreter was garbage-collected by a snap refresh — tests could not run)
- **Claude Code workbench**: `.claude/settings.json` permissions + 3 hooks (auto-format per language; destructive-command guard, 12 cases verified; protected-file guard for SIGNAL_ENGINE.md/applied migrations/.env, 7 cases verified) · 5 review agents with strict evidence contracts (quant-verifier, bug-hunter, ui-reviewer, perf-auditor, test-guardian) · 6 rules files · 4 skills (/vertical-slice, /phase-gate, /signal-audit, /perf-bench)
- **Ruff + mypy brought to zero** across the backend (48 + 18 baseline findings)

#### Critical fixes (each with regression tests)
- **100× position undersizing**: signal_tasks pre-divided risk% by 100 and compute_quantity divided again — every system-generated signal risked 0.02% instead of 2%. **Paper-trading history before this fix is invalid; the 30-day gate restarts.**
- **Live tick pipeline repaired** (it had never worked end-to-end): asyncio.get_event_loop on the KiteTicker thread (RuntimeError on 3.12); .format() on a TextClause (AttributeError on first candle); flush-without-commit (candles invisible all day); LTP published to a channel but never SET as the key paper_broker reads (intraday SL/TP silently ran on stale EOD closes)
- **From bug-hunter agent review** (3 confirmed by reproduction): batch failures no longer kill the tick loop (one Redis blip used to end live data for the day; task now supervised + loud); candle timestamps converted with astimezone (kiteconnect sends naive HOST-LOCAL datetimes in `exchange_timestamp` — every live candle was mislabelled +5:30 on an IST host); /ws/live pubsub reader anchored with a keepalive subscription (redis-py listen() exits on an unsubscribed pubsub — the stream was dead on arrival); candle volume now diffs cumulative `volume_traded` (snapshot-quantity summing fed garbage to the volume factor); Celery publishes batched off the event loop; `asyncio.run` replaces `get_event_loop().run_until_complete` in all Celery tasks
- **Signal idempotency**: active-signal dedup guard — candle-close regeneration no longer mints near-duplicate signals every period
- **/ws/live authenticates**: JWT required on the upgrade (close code 4401; refresh tokens rejected); useLiveQuotes sends the token, supports wss, stops reconnect-looping on auth failure
- **Redis eviction**: allkeys-lru → volatile-lru so Celery broker keys can never be silently evicted; stale container recreated (it predated the port mapping)
- **Backtests off the event loop** (asyncio.to_thread) — running a backtest no longer freezes the API and live WebSocket

#### F&O data recorders (recording starts now; analytics consume it in Phase 4)
- `fo_bhavcopy` — NSE UDiFF derivatives EOD (futures+options close/settle/OI/volume), idempotent, Celery beat 18:45 IST
- `india_vix_daily` — VIX EOD from the NSE indices bhavcopy (interim IV-regime proxy)
- `option_chain_snapshots` (Timescale hypertable) — 1-minute nearest-expiry chain snapshots via kite.quote for NIFTY/BANKNIFTY (2N+1 strikes around spot); idles without a Kite token
- `kite_instruments`: NFO segment synced with strikes; tokens widened to BIGINT; migration `k7l8m9n0p1q2` verified reversible

#### Docs
- Approved plan committed as `docs/UPGRADE_PLAN.md`; `docs/phases/` reports started; CLAUDE.md/README/PHASES rewritten to current truth; ARCHITECTURE.md + PERFORMANCE.md started; Rust rationale added to TECH_STACK_RATIONALE.md; CLAUDE_CODE_GUIDE.md updated for the workbench

#### Tests
- **+45 backend tests** (sizing 3, tick consumer 7 + loop survival 1, dedup 5, WS auth 9, aggregator regressions 4 + fixture truth-up, F&O recorders 16) — backend total 439, frontend 131

### UI Polish v2 — pre-Phase-12 sprint

#### Frontend
- **4-theme design system** (`src/styles/tokens.css`) — full CSS token rewrite; four named themes (midnight/carbon/ocean/daybreak) replacing the old dark/light binary; backward-compat mappings for old localStorage values; new tokens: `--color-border-strong`, `--color-warning-bg`, `--color-info-bg`, `--color-accent-bg`, `--font-ui`, `--font-num`
- **Theme switcher** (`src/pages/admin/SettingsPage.tsx`) — 2×2 card grid replacing the old radio list; each card shows bg swatch + accent dot + active badge; daybreak (light) card correctly previews light surface
- **Continuous font size** — slider (12–22 px, step 1) + five preset chips (Compact/Default/Comfortable/Large/X-Large) writing `--ui-font-size` CSS variable; replaces the old three-state discrete toggle
- **Split font system** — separate UI font selector (Inter/Geist/IBM Plex Sans/Roboto) and numeric font selector (JetBrains Mono/IBM Plex Mono/Roboto Mono/Inter tabular) stored in `uiPrefsStore`; applied via `data-ui-font` and `data-num-font` attributes on `<html>`
- **Profile dropdown** (`src/components/ui/profile-dropdown.tsx`) — ported to `createPortal` + `getBoundingClientRect` so it escapes `overflow: hidden` clipping; solid `--color-surface` background (no semi-transparent bleed)
- **Login page redesign** (`src/pages/LoginPage.tsx`) — glow-orb + subtle grid background layer; brand logo + monospace heading + tagline; shadcn `Input` for email; new `PasswordInput` component for password
- **PasswordInput component** (`src/components/ui/PasswordInput.tsx`) — show/hide toggle with Eye/EyeOff icons; aria-label `Show characters` / `Hide characters` avoids collision with `getByLabelText(/password/i)` in tests
- **KpiCard component** (`src/components/ui/KpiCard.tsx`) — card with 4 px left accent border, value in tabular-nums mono, optional sub-line with trend coloring; supports profit/loss/warning/info/accent variants
- **Action icon colors** — delete/trash hover color unified to `--color-loss` (was `--color-bear` in JournalPage)
- **Market status chip** (AppShell) — raw `text-green-400`/`bg-green-900` replaced with `--color-profit-bg`/`--color-profit`; yellow PRE-MARKET uses `--color-warning-bg`/`--color-warning`
- **Native `<select>` elimination** — replaced in `Pagination` (page-size picker), `UsersPage` (role and trading_mode), previously `DashboardPage`, `FilingsPage`, `TagPicker`; all now use `SimpleSelect` backed by base-ui portal
- **`themeStore`** — extended with `carbon` and `ocean` themes, `setTheme()` action, backward-compat toggle (daybreak ↔ midnight); old `'dark'`/`'light'` localStorage values auto-migrated
- **`uiPrefsStore`** — extended with `fontSizePx`, `uiFont`, `numFont` state and setters; `setFontSizePx` writes `--ui-font-size` inline; boot hydration in `main.tsx`
- **Select popup styling** (`src/components/ui/select.tsx`) — replaced shadcn defaults with `--color-surface`/`--color-border-strong` tokens; no semi-transparent backgrounds

### Phase 11 — External Portfolio

#### Backend
- **Alembic migration** `j1k2l3m4n5o6` — creates `mf_import_batches`, `mf_holdings`, `manual_assets` tables with UUID PKs, BigInteger FKs to users, and covering indexes; fully reversible
- **ORM models** (`app/models/portfolio.py`) — `MfImportBatch` (source PDF metadata, totals), `MfHolding` (amc, scheme, folio, isin, units/NAV/value as Numeric), `ManualAsset` (gold/FD/PPF/NPS/bonds/real_estate/other with cost basis and maturity fields)
- **CAS PDF parser** (`app/services/cas_parser.py`) — state-machine parser for CAMS Consolidated Account Statement PDFs via `pdfplumber`; extracts header (investor name, PAN, statement date) and holdings (AMC, scheme, folio, ISIN, units, NAV, current value, valuation date); flush-when-complete design avoids look-ahead bias
- **Portfolio service** (`app/services/portfolio_service.py`) — `import_cas_pdf` (parse + upsert batch + holdings in one transaction), `get_batch_with_holdings` (selectinload), `get_net_worth` (aggregates equity open positions + latest MF batch + manual assets into `NetWorthOut`)
- **Portfolio API** (`app/api/v1/portfolio.py`) — `POST /portfolio/cas/upload` (20 MB limit, PDF-only), `GET /portfolio/cas/batches`, `GET /portfolio/cas/batches/{id}`, `DELETE /portfolio/cas/batches/{id}`, `POST /portfolio/assets`, `GET /portfolio/assets`, `PUT /portfolio/assets/{id}`, `DELETE /portfolio/assets/{id}`, `GET /portfolio/net-worth`; all JWT-protected, ownership enforced
- **pdfplumber** added to backend dependencies

#### Frontend
- **Portfolio API client** (`src/lib/api/portfolio.ts`) — TypeScript interfaces and typed functions using the `api` fetch wrapper for all portfolio endpoints
- **PortfolioPage** (`/portfolio`) — three-tab layout (Net Worth, Mutual Funds, Other Assets)
  - *Net Worth tab*: total value card, stacked segment bar (equity/MF/manual), per-segment cards, manual asset type breakdown
  - *Mutual Funds tab*: drag-drop CAS upload zone (20 MB limit), batch history table with expandable holdings, delete batch
  - *Other Assets tab*: asset table with add/edit/delete, `AssetFormModal` with conditional fields per asset type
- **SimpleSelect** shared component (`src/components/ui/simple-select.tsx`) — thin wrapper around base-ui Select primitives accepting a flat `options` array; fixes Journal pages that used incorrect `options` prop on raw `SelectPrimitive.Root`
- **AppShell** — Portfolio nav item with Wallet icon added
- **Router** — `/portfolio` route registered

#### Bug fixes (Phase 10 Journal)
- `JournalPage` / `JournalEntryModal`: replaced `const { toast } = useToast()` with `const { success, error } = useToast()` (API mismatch)
- `JournalEntryModal`: fixed `<Dialog>` without `<DialogContent>` (no overlay rendered); now uses `<Dialog><DialogContent>` correctly
- `JournalPage`: fixed `Pagination` missing `pages` prop; fixed page state from 0-indexed to 1-indexed
- Removed invalid `variant="neutral"/"bull"/"bear"` Badge usage; replaced with themed inline spans

#### Tests (32 new passing — 327 total backend, 126 total frontend)
- `TestCasParser` (8) — header extraction, holding count, value parsing, multi-folio same AMC, missing closing balance, as-of-date from NAV line
- `TestCasUpload` (7) — upload creates batch, non-PDF rejected, auth required, list batches, get batch detail with holdings, 404 on missing, delete cascade
- `TestManualAssets` (10) — create gold/FD, invalid type 422, negative value 422, all 6 valid types, list, filter by type, update, delete, ownership isolation
- `TestNetWorth` (7) — empty state, manual assets aggregate, breakdown sorted by value, MF batch included, auth required

---

### Phase 8 — Paper Trading

#### Backend
- **Alembic migration** `g8h9i0j1k2l3` — creates `orders` and `positions` tables with partial indexes for open positions and time-based lookups; UUID PKs generated at Python level (no `server_default`)
- **ORM models** (`app/models/trading.py`) — `Order` (BUY/SELL, fill details, broker_payload JSONB) and `Position` (LONG/SHORT, avg_entry_price, trail_state, unrealized_pnl, realized_pnl, opened_at/closed_at)
- **Paper broker** (`app/broker/paper_broker.py`) — `place_paper_order` fills at Redis LTP → latest daily close fallback → signal entry_price; averages into existing open position for same stock/user/side; `close_position` creates closing order and computes realized P&L; `update_position_pnl` refreshes unrealized P&L
- **Circuit breaker** (`app/trading/circuit_breaker.py`) — blocks new orders when daily realized loss exceeds `capital_inr × daily_loss_limit_pct / 100` or `max_trades_per_day` is reached; uses IST calendar day window; never disableable
- **Trail SL state machine** (`app/trading/trail_sl.py`) — monotonic 4-state machine (none → breakeven → trailing_1 → trailing_2) based on R multiples; `advance_trail`, `is_sl_hit`, `is_tp_hit`, `compute_pnl`
- **Position monitor Celery task** (`app/tasks/position_monitor.py`) — runs every minute during market hours (9:15–15:30 IST = UTC 3:45–10:00, Mon–Fri); auto-closes on SL/TP hit; advances trail SL; refreshes unrealized P&L
- **Trading API** (`app/api/v1/trading.py`) — `POST /trading/orders` (circuit breaker enforced), `GET /trading/positions`, `POST /trading/positions/{id}/close`, `POST /trading/positions/{id}/update-sl`, `GET /trading/history` (paginated), `GET /trading/daily-pnl`

#### Frontend
- **Trading API client** (`src/lib/api/trading.ts`) — TypeScript interfaces and `tradingApi` with `placeOrder`, `getOpenPositions`, `closePosition`, `updateSl`, `getHistory`, `getDailyPnl`
- **DailyPnlCard** — shows realized P&L, loss limit progress bar, circuit breaker status; refetches every 60 s
- **PositionsPage** (`/trading/positions`) — open positions table with unrealized P&L, edit-SL and close buttons; `ClosePositionDialog` and `UpdateSlDialog` rendered via `createPortal` per floating-panel rules
- **TradeHistoryPage** (`/trading/history`) — paginated closed positions table with summary cards (page P&L, win rate, trade count)
- **Dashboard** — "Paper Buy" button added to each signal row; green-tinted with cart icon; shows loading state during mutation
- **AppShell** — Positions and Trade History nav links added

#### Tests (34 new passing, 302 total backend, 114 total frontend)
- `TestTrailSl` — 9 pure unit tests covering all state transitions (LONG/SHORT, breakeven, trailing_1, trailing_2, no-regression, zero-risk guard)
- `TestCircuitBreaker` — 3 async DB tests (loss-limit trigger, within-limit pass, max-trades trigger)
- `TestPaperBroker` — 5 integration tests (open+close full lifecycle, average-in, SL hit auto-close, TP hit auto-close, double-close raises)
- `TestTradingApi` — 17 API tests (auth, 404, circuit-breaker block, positions list, manual close, already-closed 409, SL update, invalid SL direction 422, history pagination, daily-pnl, cross-user isolation)
- Frontend: 12 tests across DailyPnlCard, PositionsPage, TradeHistoryPage

---

### Phase 7 — Live Data via Kite WebSocket

#### Backend
- **Kite OAuth flow** — `/broker/kite/login` returns Zerodha login URL; `/broker/kite/callback` exchanges `request_token` for `access_token`, persists `BrokerToken` (expires next 6 AM IST)
- **KiteInstrument sync** — `/broker/kite/instruments/sync` downloads Kite CSV and upserts into `kite_instruments` table; maps `exchange:symbol` → `instrument_token` for tick subscription
- **Candle aggregator** (`app/broker/candle_aggregator.py`) — stateful tick → OHLCV for 1m/5m/15m/1h; emits `CandleEvent` on new candle or close; look-ahead safe (compute N → signal valid from N+1)
- **Tick consumer** (`app/broker/tick_consumer.py`) — `KiteTicker` (thread) bridges to asyncio via `Queue`; publishes `ltp:{token}` and `candle:{table}:{stock_id}` to Redis pub/sub; upserts candles to DB; fires Celery task on candle close for signal regeneration
- **Gap fill** (`app/broker/gap_fill.py`) — on reconnect fetches Kite REST historical data for each missed timeframe and upserts
- **Live signal generation** — new Celery task `live_signal_generation` runs confluence engine on intraday candles (5m/15m/1h) for a single stock after each candle close
- **FastAPI WebSocket** (`/api/v1/ws/live`) — browser subscribes by symbol; server subscribes to Redis channels and fans out LTP + candle + signal events
- **Auto-resume** — FastAPI lifespan queries DB for active admin token and restarts tick consumer on server restart
- **Alembic migration** `f1g2h3i4j5k6` — creates `ohlcv_1m`, `ohlcv_5m`, `ohlcv_15m`, `ohlcv_1h` (TimescaleDB hypertables), `broker_tokens`, `kite_instruments`
- **Kite credentials** loaded from `.env` (`KITE_API_KEY`, `KITE_API_SECRET`, `KITE_REDIRECT_URL`)

#### Frontend
- **KiteConnectPage** (`/broker/kite`) — OAuth connect button, token status, sync instruments, start/stop consumer, setup checklist; admin-only route
- **`useLiveQuotes` hook** — WebSocket connection to `/api/v1/ws/live`; subscribes by symbol list; exposes `quotes` (LTP) and `candles` (latest per timeframe) maps; auto-reconnects every 3 s
- **Dashboard** — live LTP column in signals table; WebSocket connection indicator (green dot when connected)
- **AppShell** — "Kite" nav link for admin users

#### Tests (26 new passing)
- Candle aggregator: `_floor_to_period`, OHLC update, candle close event, 5m aggregation, zero-price guard, registry operations
- Gap fill: timeframe → Kite interval mapping, model mapping, gap calculation logic
- Broker API: login URL, auth guard, status endpoint, OAuth exchange (mocked Kite), bad token error, admin-only instrument sync

---

### Phase 5 — Signal Engine (Offline)

#### Backend — Analysis Engine
- **15 candlestick pattern detectors** — 6 single-candle (Marubozu ±0.8, Doji, Spinning Top, Hammer/Paper Umbrella +0.4/+0.7, Hanging Man −0.6, Shooting Star −0.7) and 4 multi-candle (Engulfing ±0.9, Harami ±0.5, Piercing/Dark Cloud ±0.7, Morning/Evening Star ±0.95) — scores match SIGNAL_ENGINE.md §2.1–2.2
- **10 indicator factors** — RSI level + divergence (wt 10), MACD cross + histogram (wt 10), EMA cross + price structure + multibagger bonus (wt 15/15/10), ADX regime (wt 5), BBands reversal (wt 10), Volume spike (wt 10)
- **Structural factors** — Dow Theory trend (wt 20), S/R zone + demand/supply detection (wt 10), Fibonacci retracement 0.5/0.618/0.786 levels (wt 5), FII/DII institutional flow (wt 5)
- **Confluence scorer** (`app/analysis/confluence.py`) — weighted average of all 14 factors, ADX regime adjustments (±5% threshold), min 70% confidence gate; returns `ConfluenceResult | None`
- **Risk sizer** (`app/analysis/risk.py`) — `compute_quantity = floor(capital × risk% / |entry − SL|)`; `compute_levels` per-classification SL/TP rules with max-SL guards (scalp 0.5%, intraday 0.5%, swing 8%)
- **Signal classifier** — maps timeframe → scalp/intraday/swing/positional
- **Expiry sweeper** — classification-correct validity (scalp +30 min, intraday 3:15 PM IST, swing +7 days, positional +42 days)
- **Signal generation service** — loads candles from DB, runs full pipeline, persists `Signal` ORM rows
- **Signal API** (`GET /signals/active`, `GET /signals/{id}`) — filterable by direction/classification/min_confidence, sorted by confidence desc; JWT-protected
- **Backtest harness** (`app/backtest/engine.py`) — anti-look-ahead (compute on N, fill at N+1 open); reports win_rate, avg_RR, max_drawdown, Sharpe, Sortino
- **Alembic migration** `d1e2f3a4b5c6` — creates `sr_levels`, `signals`, `signal_outcomes`, `strategy_runs`; fully reversible

#### Tests
- **219 total tests passing** — 189 new Phase 5 tests covering all pattern detectors, all indicators, Dow Theory, S/R/Fibonacci/institutional flow, confluence worked example from spec §3, risk sizer per-classification, signal API endpoints (auth, filters, pagination, 404)
- Anti-look-ahead bias verified in both fibonacci (uses `candles.iloc[:-1]` for prior swing) and backtest harness

---

### Phase 1 — Auth & User Master

#### Backend
- **JWT authentication** — access token (45 min, JS memory) + refresh token (7 d, httpOnly cookie)
- **Refresh token rotation** — each `/auth/refresh` call revokes the old session and issues a new one; JTI hash stored in `user_sessions` (raw token never persisted)
- **User CRUD API** (`/api/v1/users`) — admin-only list/create; self-service profile update; admin role-change gate; soft deactivation (no hard deletes)
- **Role-based deps** — `get_current_user` (Bearer + DB lookup) and `require_admin` FastAPI Depends
- **Alembic migration** `b4945c2d75aa` — creates `users` and `user_sessions` tables with `RESTART IDENTITY CASCADE` support
- **`scripts/create_admin.py`** — idempotent first-admin seed script
- **30 backend tests** — all passing; real Postgres test DB (`trading_platform_test`), `NullPool` isolation, no mocks

#### Frontend
- **Vite 8 + React 19 + TypeScript 6** scaffold with `@tailwindcss/vite` plugin
- **Design tokens** (`src/styles/tokens.css`) — trading-specific color palette: bull/bear/neutral, chart surface, brand dark theme
- **Global styles** (`src/styles/globals.css`) — base reset plus `card`, `btn`, `input`, `label`, `error-text` CSS primitives
- **API client** (`src/lib/api/client.ts`) — typed `fetch` wrapper with `ApiError` class
- **Auth & Users API modules** (`auth.ts`, `users.ts`)
- **Zustand auth store** — in-memory `accessToken` + `user`; survives re-renders, clears on logout
- **`useAuth` hook** — login, logout, refreshToken callbacks with 401 auto-clear
- **`AppShell`** — sticky header with brand logo, admin nav link, signed-in user email
- **`PageHeader`** — reusable title / subtitle / action-slot component
- **`LoginPage`** — email/password form with loading state and per-status error messages
- **`UsersPage`** (admin) — table with live TanStack Query fetch + "New user" modal
- **Protected routes** — `RequireAuth` and `RequireAdmin` guards in React Router v7
- **12 frontend tests** — Vitest + RTL; useAuth hook, LoginPage, UsersPage

#### Infrastructure
- Fixed postgres port mapping to 5433 (5432 was occupied by local Postgres)
- Added `make backend`, `make frontend`, `make migrate`, `make create-admin`, `make test`, `make lint`, `make typecheck`, `make check` targets
