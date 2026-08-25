# NSE Closing Auction Session (CAS) — analysis & execution plan (2026-08-21)

_A 20-yr-quant read on the new NSE CAS: what it actually is, why it exists, how closing auctions are
exploited globally, what edge (if any) WE can realistically capture given our platform, and a staged,
paper-first, evidence-first plan. Written to correct the (self-contradictory) popular explanations and
ground the decision in the real spec + the academic literature._

## 1. What CAS actually is (corrected facts, sourced)

The popular write-ups disagree with each other on the timing. The verified facts:

- **CAS is a 20-minute call auction, 3:15 PM → 3:35 PM**, on all trading days. Continuous trading in
  the covered stocks now ends at **3:15**, not 3:30.
- **Live from 3 Aug 2026**, and **only for Category-I stocks** (those with active F&O contracts);
  every other stock (Category II) still closes the old way for now.
- **Reference price = VWAP of trades 3:00–3:15 PM** (fallback: LTP, then prior close).
- The auction discovers a single **equilibrium closing price = the price that maximises matchable
  volume**, replacing the old "weighted-average of the last-30-min trades" method. Order entry /
  matching happens inside the 3:15–3:35 window (with a random end to deter gaming).
- **Equity derivatives now close at 3:40 PM** (extended from 3:30) — so cash and F&O close on
  *different* mechanics and clocks now.
- Basis: SEBI circular HO/.../2026 dated 16 Jan 2026; NSE SOP circular. SEBI has said CAS is "here to
  stay" (open to feedback on implementation).

**Implication for our platform's data model:** the **3:15 LTP is the last continuous-market price**;
the **official close is an auction print that can differ materially** from it. So "3:15 price" and
"official close" are now two distinct, both-meaningful numbers — and any EOD logic that assumed the
last tick == the close is now subtly wrong for Category-I names.

## 2. Why NSE/SEBI introduced it

- **Better price discovery at the close** — a single auction price where max volume clears beats an
  average-of-last-trades that a few late prints can nudge.
- **Passive-fund / ETF tracking** — index funds must trade AT the close to track their benchmark; a
  proper auction gives them a real venue and cuts tracking error. (Reuters reported MF participation
  jumped after rollout.)
- **International convergence** — NYSE/Nasdaq closing cross, LSE/Euronext closing auctions all work
  this way; India was an outlier.

## 3. How closing auctions are actually exploited (the literature)

This is the important part, and it corrects the naive "predict the closing price and trade it" pitch:

- **Auction order-imbalance predicts the clearing price** — but only if you have the *live imbalance
  feed during the auction* (Jegadeesh & Wu 2021, on Nasdaq Finland, which disseminates imbalance). This
  is an **institutional, low-latency, feed-dependent** game — colocation + the official imbalance feed.
  **Retail does not win this race**, and every other algo is running the same supply/demand-curve
  reconstruction ChatGPT described. After costs, "buy quantity > sell quantity → BUY" is a loser.
- **The accessible, lower-frequency edge: the overnight REVERSAL of the auction move.** Multiple studies
  find **closing-auction returns are systematically reversed overnight (~14% of the auction return
  reverses, persisting >2h into the next session)** — i.e. part of the auction move is transient
  order-pressure, not information, and it gives back. **This is exactly our timeframe** (buy near close,
  sell next day). It says: a stock *pushed up* into the CAS close tends to open softer; one *pushed
  down* tends to bounce.
- **Auctions concentrate volume** (up to ~⅓ of daily volume in some markets) and can *raise* costs +
  impair intraday price discovery — relevant to our execution-cost realism, and a reason the close is
  NOT a free fill.

**Net:** the institutional edge (predict-and-trade the auction) is closed to us; the **behavioural edge
(overnight reversal of the auction move) is open to us and fits our style** — IF it holds on NSE.

## 4. Can WE profit? Honest assessment vs our platform

| Angle | Feasible for us? | Why |
|---|---|---|
| Intraday CAS clearing-price prediction | **No** | No live imbalance feed (retail Kite almost certainly doesn't expose CAS imbalance/indicative price), no colocation/latency, institutions dominate. |
| MOC / at-the-close participation | **No (yet)** | Needs live trading (our Phase 7, unbuilt), a close-auction order type, and the feed. |
| **Overnight reversal of the CAS move** | **Plausibly yes** | Lower-frequency, uses only the 3:15 price + official close + next-day open — data we can capture. Fits our near-close→next-day style. Must be *measured on NSE*, not assumed. |
| **Using the CAS move / official close as CONTEXT** | **Yes** | Feature for our existing next-day decisions; and a data-correctness fix (3:15 ≠ close for Cat-I). |

**Our observation ("stocks recovered from losses into the close recently") — reframed + a confound.**
Two things changed at once: (a) CAS went live 3 Aug, and (b) the market is in a below-200-DMA **oversold
regime** where our own 3-yr study just found dips mean-revert (bounce). So a "loss → recovery into the
close" could be CAS order-pressure, OR the oversold-bounce regime, OR both. **We must not attribute it to
CAS by eye — that's the exact n=4 trap the regime study just warned against.** Measure it.

## 5. Execution plan (staged, paper-first, evidence-first)

### Stage 0 — ✅ CONFIRMED LIVE 2026-08-25

**The probe ran through the live CAS window on 2026-08-25 and it works.** Kite `/quote` carries, on every
quote, five non-documented fields — **`indicative_close_price`**, **`total_imbalance_qty`**,
`reference_limit_price`, `high_limit_price_protection`, `low_limit_price_protection`. So we capture the
auction from our existing Kite feed — **no Global Datafeeds.** Learned:
- **Micro-timing:** `indicative_close_price` + `total_imbalance_qty` are **0 until ~15:21**, then
  populate/swing 15:21→15:28, and the auction **EXECUTES ~15:29** (`last_price` jumps to the clearing
  price, imbalance → 0, static after). So sample **15:15–15:32**; the useful signal is 15:21–15:29.
- **Data gotcha:** `ohlc.close` is the **PRIOR day's** close during the session — the true close is
  `last_price` / `indicative_close_price` after ~15:29, NOT `ohlc.close`.
- **Sample (08-25):** RELIANCE 1312.7 (15:15) → auction close **1317** (+0.33%); HDFCBANK 724 → **727.5**
  (+0.48%). Both closed UP in the auction. Imbalance sign convention still TBD (RELIANCE showed negative
  imbalance yet closed higher — confirm over more days).
- **Run it right:** launch `scripts/cas_probe.py` any time after `kite_login`; it now **idles until 15:10
  then captures only 15:10–15:33** (fixes the "killed it before 3:15 / 4 MB all-day file" problem from the
  first two runs). Raw dumps: `docs/analysis/cas-probe-<date>.jsonl` (kept local — large, not committed).

_Original plan (2026-08-22), now largely satisfied:_
- **Feed question answered (as far as the code + docs allow):** Kite's **WebSocket ticker (`MODE_FULL`,
  what `live_worker`/`tick_consumer` consume) has a fixed binary struct — LTP/OHLC/volume/5-level depth/
  OI/timestamps — with NO imbalance field.** So the **Total Imbalance Quantity cannot come from the
  WebSocket**; it can only be on the **REST `/quote`** (forum evidence says the indicative close +
  imbalance are broadcast there during the pre-open/CAS window, even though Kite's *static* /quote docs
  don't list them — the docs lag the Aug-2026 rollout). **⇒ our capture path is REST `/quote` polling
  during 3:15–3:35, the exact pattern we already run for 6.8.3 circuit bands** (`kite_rest.quote()` →
  a market-hours task). No commercial vendor (Global Datafeeds etc.) needed — decided 2026-08-22.
- **The remaining unknown is only the exact field name/location**, which the static docs don't give.
  So the probe **dumps the RAW `/quote` JSON** during CAS and flags any key beyond the documented set.
- **Run the probe LIVE on the next trading day (Mon 2026-08-25) during 3:15–3:35 IST** (market-closed
  weekends can't test it) — with an active Kite admin token (`scripts/kite_login.py` first):

  ```
  cd backend && uv run python scripts/cas_probe.py            # polls liquid F&O names to 15:36 IST
  ```

  It appends every raw `/quote` poll to `docs/analysis/cas-probe-<date>.jsonl` and prints `⚑ NEW` lines
  whenever a non-documented / `imbalance`/`indicative`-named key appears. **Share that JSONL** →
  we read exactly where (and whether) Kite surfaces the indicative close + imbalance, then design
  Stage-1 capture accordingly. (Runs from ANY session/account — it's a script, not tied to a chat;
  a dry `--once` off-hours just confirms auth/plumbing.)
- Mark Category-I stocks (we already know `is_fno`) — CAS applies to them.
- **If the fields prove out:** productionize the probe into a market-hours Celery beat task (the
  circuit-band task pattern) so the worker auto-captures CAS every day regardless of session — that
  becomes Stage 1.

### Stage 1 — Capture (forward, from existing feeds; no new vendor)
For each Category-I stock, per day, record: **3:15 LTP** (last continuous price), **official close**,
the **CAS move = (close − 3:15)/3:15**, next-day **open** and **first-hour / full-day return**. We
already have the tick LTP + EOD close + the `live_worker`/depth plumbing — this is a small capture
add, not a new data source. Store in a new daily table (shadow/observability, never a trade trigger).

### Stage 2 — Study (read-only, like the regime study)
- **Does the CAS move reverse overnight on NSE?** Regress next-day return on the CAS move; bucket by CAS-move
  size + direction; measure the reversal fraction (the literature's ~14% is the prior to test).
- **Control for the regime** (oversold-bounce) and for size/liquidity — is any "recovery into close" CAS,
  or just the mean-reversion we already found? Block-bootstrap it (same discipline as the regime study).
- Deliverable: a `cas-study-<date>.md` with the reversal estimate + a go/no-go on an edge.

### Stage 3 — Use it (ONLY if Stage 2 shows a real, robust edge)
- Fold the **CAS move** as a **feature/modifier** into our near-close→next-day (swing/overnight)
  decisions — e.g. down-weight buying a name that closed on a strong *upward* auction push (likely to
  give back); shadow-first, moded, §8-validated before it ever gates. **Not** an intraday auction trader.
- Independently: fix the data-correctness issue — treat 3:15 vs official close as distinct for Cat-I in
  any EOD logic.

### Stage 4 — Participation (far off, gated on live trading)
MOC/at-close order participation only makes sense after Phase 7 (live) + a close-auction order type +
(if it ever exists for us) an imbalance feed. Not now.

## 6. Honest caveats
- **Don't build an intraday CAS predictor.** No feed, no latency, crowded, institution-dominated — a
  retail loss after costs. The literature's imbalance-predicts-price result *requires* the live feed.
- **The overnight-reversal edge must be measured on NSE**, not imported from US/EU studies — magnitude
  and even sign can differ; and it's small (~single-digit % of a small auction move) → costs can eat it.
- **Confound with the current oversold regime is real** — our own study says dips are bouncing now;
  separate CAS from regime before believing anything.
- Everything paper-first; the 30-day live gate + circuit breaker still bind.

## 7. Recommendation
**Do Stage 0 + Stage 1–2** (spike the feed feasibility, capture the CAS move, study the overnight
reversal) — cheap, safe, and it either finds a real overnight-reversal edge that fits our exact style or
kills the idea with evidence. **Do NOT chase intraday auction prediction.** This is a natural companion
to the MCE (market context) and the anti-chase work: the close is now an auction, and how a name got to
its close is new, usable context — *if* the data shows it.

---
_Sources: NSE CAS product page + SOP circular (nseindia.com); Reuters (2026-08-12, CAS price discovery
& MF participation); Times of India (2026, SEBI "here to stay"); Business Standard (F&O to 3:40).
Literature: Jegadeesh & Wu (2021) "Who trades at the close?"; JFQA "Price impact in closing/opening
auctions"; EFMA 2023 & arXiv work on closing-auction price discovery + overnight reversal._
