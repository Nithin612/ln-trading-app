# Trading masterclass — documentation & platform assessment (2026-08-12)

**What this is.** The user attended an 11-class trading masterclass (an
individual instructor, **not SEBI-registered** — treat as educational opinion,
not advice). The class videos are Tanglish (Tamil + English), 40 min–1.2 hr
each. The user fed the videos + handwritten notes to Google NotebookLM and
pasted NotebookLM's English synthesis here. **This document records that
synthesis and my assessment of it against our platform.**

> **Provenance / trust level.** Everything in §2 (the class digest) is
> **NotebookLM's summary of the videos+notes — UNVERIFIED against the source.**
> LLM summaries embellish and mis-transcribe. The raw videos + note photos are
> to be uploaded later; §5 is the cross-verify checklist for when they arrive.
> Nothing here changes any engine behaviour — it is reference + planning only.

> **The headline finding.** This masterclass is almost certainly the **design
> origin of our existing strategy profiles.** Our `backend/app/profiles/setups.py`
> implements `pdh_breakout`, `pdl_breakdown`, `dc1`, `dc2`, `orb_breakout`,
> `top_gainer_925`; walk-forward goldens exist for `rrbo_basic`, `rrbo_trailing`,
> `multibagger`, `gainer_925`, `orb_15m`, `pdh_pdl`, `dc1`, `dc2`. The class's
> strategies map ~1:1 to profiles we already **built and back-tested.** So the
> value of this material is (a) confirming coverage, (b) the few pieces we have
> NOT built, and (c) an honest reality-check: our own walk-forward already found
> the intraday set **negative risk-adjusted** (they run in SHADOW, not tradeable).

---

## 1. Assessment against the user's questions

**Does it help stock selection / entry / exit / F&O income?** Yes — but mostly
by confirming what we already encode, and it needs the same evidence discipline
we apply everywhere.

| Area | Masterclass teaches | Our status | Verdict |
|---|---|---|---|
| **Stock selection** | Sectoral-index breakout → pick stock in a hot sector; scanner filter (<8% moved, no circuits, no >2.5% gap); F&O-186 universe for intraday | Universe service + screener (sieve); sector metadata (500/2365); F&O universe exists | **Already ours as discovery.** The <8%/gap/circuit filters are good SavedScreen candidates (Phase 6 scan-catalog). |
| **Entry** | RRBO (1D), DC1/DC2 zones, PDH/PDL retest, 9:25 gainer, ORB, 10 AM options | **Implemented** as setup evaluators; swing family tradeable, **intraday trio in SHADOW** | **Built.** Confidence claims unproven for intraday — see risk flags §4. |
| **Exit** | 6% flat / TSL (50% at T1, trail rest) / EMA-close exit; SL caps (intraday 0.4–0.5%, swing 8%, option 10%); RR 1:1.5–1:2 | Our exit governors (profit-lock ladder, trail-SL), SL caps in risk rules (scalp/intraday 0.5%, swing 8%) | **Strong overlap.** SL caps nearly identical to our hard rules. TSL matches `rrbo_trailing`. |
| **F&O passive income** | Intraday **short strangle** (sell ATM CE+PE) at 9:20 & 1:00, 25% premium SL, target 4–5%/mo | **NOT built** (we are paper-only, no live order path; no option-selling profile) | **Genuinely new — but high tail risk. Do NOT treat as "passive."** See §4. |
| **Fundamentals for investing** | FV = BV×10; CMP vs BV vs FV; promoter >35%, pledge <10%; growth sectors | Fundamentals layer not built (blocked on `market_cap` source) | Promoter/pledge rules = clean scans once fundamentals exist. FV=BV×10 is **not** a real valuation — see §4. |
| **Risk / psychology** | 1:2 RR, position sizing `qty = risk / SL_points`, journal, max 2 trades/day, treat losses as cost, don't revenge-trade, "execute don't predict" | Position sizing is a hard invariant; circuit breaker; daily report is the journal | **Fully aligned** — this half is sound and matches our design. |

---

## 2. Class-by-class digest (per NotebookLM synthesis — unverified)

**Class 1 — Basics & investing.** Four trade types by risk (Investment < Swing <
Intraday < Options). Fundamental screen: **Valuation** (Under = CMP<BV, Attractive
= BV<CMP<FV, Over = CMP>FV, with FV = BV×10; avoid negative BV); **Promoter
holding >35%**; **pledged <10%**; **growth sectors** (AI/IT, EV). Data from
MoneyControl. Rakesh Jhunjhunwala / Titan hold-for-21-years anecdote.

**Class 2 — Technicals & candlesticks.** Body vs wick; green/red; Hammer &
Bullish Engulfing (up), Shooting Star & Bearish Engulfing (down), Doji. Trend
via swing highs/lows. TradingView for charts, 1D to start. Psychology: not
get-rich-quick, no 100% strategy, discipline > talent.

**Class 3 — Chart patterns & S/R.** H&S / inverse H&S, W (double bottom) / M
(double top); pattern only valid **at** S/R; wait for the pattern to confirm the
level. S/R = recent swing highs/lows; focus on nearest to CMP.

**Class 4 — Swing (RRBO).** 1D timeframe; **Recent Resistance Breakout**; select
via sectoral index or scanner (<8% moved); enter 2:30–3:15 PM if candle **body**
closes above resistance (else next-day 9:15 if opens in range, no big gap); SL at
recent swing low, **cap 8%**; targets: flat 6% or TSL.

**Class 5 — Multibagger & hacks.** RRBO + **20 EMA & 200 EMA very close together**
at breakout; min target 15%, then exit only when daily body closes below 20 EMA.
3rd swing-exit = 6% then 3h/20-EMA trail. Hacks: Nifty BeES, IT BeES, "Tata group
pattern." Warren-Buffett 3–4/10 win-rate framing.

**Class 6 — Intraday & zones.** 5x leverage, both directions, close by ~3:10.
**Supply/Demand zones** = last opposite-colour candle before the breakout rally.
Trendlines. **DC1** (zone on 1h → confirm on 15/5m via pattern or TL break),
**DC2** (trendline-based). **TLBO** downside-only.

**Class 7 — Intraday selection & indicators.** Live: advance/decline → top
gainers/losers (**F&O-186 filter**); **9:25 strategy** (mark high/low of first two
5-min candles, enter running break of 3rd/4th; skip if no break by 10:15, gap
>2.5%, or already moved >4%). **PDH/PDL with mandatory retest.** EOD scan (2–3%
movers) + DC1 next day. Sensibull LTP alerts → WhatsApp. Indicators: EMA (20/200
swing, 50 intraday), Volume, Volume Profile/POC, PP Dynamics, CPR, **RSI(10)
divergence**. "Bus-stop" rule: wait for price to come to your zone.

**Class 8 — Options fundamentals.** Futures ≈ ₹1.2L margin → options with less
capital. Segments: indices, 186 F&O stocks, commodities (open to 11:30 PM).
5 rules: **Premium** (partial capture), **Time Decay**, **Strike** (OTM/ATM/ITM,
ATM recommended), **Expiry** (indices weekly, stocks monthly), **CE for up / PE
for down** (buy-only to avoid sell margin).

**Class 9 — Option buying.** **10 AM strategy** (mark 9:15–10:00 high on ATM CE &
PE, 1-min, enter first to break). RSI(10) divergence + confirmation. DC1/DC2 on
15m→5/1m. TLBO downside-only. **Data hack:** Bank Nifty ≈ 70% CNX Finance + 30%
CNX PSU Bank — analyse FinNifty first as a **lead indicator**.

**Class 10 — Option selling & risk.** **Hedging** (buy CE+PE, event days only —
one → 0, other flies). **Selling** (sell PE for up / CE for down; benefits from
time decay; ~₹1.2–2L capital; 4–5%/mo). Risk: Trader-A-vs-B (RR > win-rate), **1:2
RR**, **position sizing formula**, losses = business cost, journal, **max 2
trades/day**, Mark Douglas "execute don't predict."

**Class 11 — Exits & compounding.** Intraday SL **≤0.4%** (0.5% max); option
SL/target **on the strike chart, not the index** (time decay); option SL ≤10% of
premium; RR 1:1.5 (9:25 / 10 AM) or 1:2 (DC/PDH/TLBO). Pick **two** strategies and
write a fixed setup; demo first. **Compounding:** ₹2L at 15%/mo → ~₹57L in 2y
(claims ~₹27L even at 50–60% execution). "Downside faster than upside"; NSE > BSE.

**Passive-income (option selling) — detailed.** Sell ATM CE+PE at **9:20 AM**,
**25% premium SL each**, force-close 1:00 PM; if one SL hits, close the other.
Repeat at **1:00 PM**, close 3:00 PM. Claim: ~₹3k/week, ₹10–12k/mo on ₹2L
(4–5%/mo), automatable via algo/API.

---

## 3. Mapping to our platform (grounded in code)

| Masterclass strategy | Our implementation | Tradeable? |
|---|---|---|
| RRBO swing (1D), 6% / TSL exits | `rrbo_basic`, `rrbo_trailing` (walk-forward goldens) | Swing base |
| Multibagger (20/200 EMA proximity) | `multibagger` (golden) | Positional |
| 9:25 top gainer/loser | `top_gainer_925` evaluator / `gainer_925` golden | **SHADOW** (neg. walk-forward) |
| ORB | `orb_breakout` / `orb_15m` golden | **SHADOW** |
| PDH/PDL retest | `pdh_breakout` / `pdl_breakdown` / `pdh_pdl` golden | **SHADOW** |
| DC1 / DC2 zones | `dc1`, `dc2` evaluators + goldens | verify status in `setups.py` |
| Candles / S-R / EMA / RSI / Volume | frozen confluence engine factors (`app/analysis/`) | factors, gated ≥70% |
| Seasonality (MoneyControl) | shipped 2026-08-11 (`app/services/seasonality.py`) | context only |
| Sector-index breakout selection | sector metadata + screener sieve | discovery |
| Sensibull LTP alerts | our AlertBell + LTP alerts | built |
| **Option selling passive income** | **not built** (paper-only, no order path) | **GAP** |
| **FinNifty→BankNifty lead-lag hack** | not built | **GAP (interesting)** |
| **Fundamental screen (promoter/pledge/FV)** | not built (blocked on `market_cap`) | **GAP** |

---

## 4. Honest risk flags (where the class conflicts with our invariants or reality)

1. **Option "passive income" is not passive — it's short-volatility with
   fat tails.** Selling ATM CE+PE (short strangle) intraday with a 25% premium
   SL collects small premiums most days and takes a large loss on gap/event days;
   a single bad day can erase weeks. The 4–5%/mo claim ignores tail risk and the
   "back-tested 2 years" claim is unverified. If ever built: paper-first, hard
   daily-loss breaker (never disableable), event-day blackout, and a §8 backtest
   incl. gap-through-SL — exactly our existing safeguards. **Do not live-trade
   this on the strength of the class.**
2. **"Enter on a running candle (don't wait for close)"** conflicts with our
   **no-look-ahead / commit-on-`is_complete`** rule. Fine as manual discretionary
   execution; our engine commits signals only on completed candles. Keep that line.
3. **FV = Book Value × 10 is not a valuation method** — it's an arbitrary
   multiple with no basis. The promoter>35% / pledge<10% rules ARE sound and map
   to real fundamental scans; the FV heuristic should not become a feature.
4. **15%/month compounding → ₹57L is arithmetic, not a forecast.** Sustained
   15%/mo is not realistic; our LEDGER shows the real difficulty (entries rarely
   reach 1R). Useful as motivation, dangerous as an expectation/position-sizing
   basis.
5. **Our own evidence already contradicts the intraday confidence.** gainer_925 /
   orb / pdh_pdl walk-forwarded **negative** → shadow. The class presents them as
   reliably profitable; our data says "not yet proven." This is the single most
   important cross-check.

---

## 5. Cross-verify checklist — when the real videos + notes arrive

**What I can ingest:** photos of handwritten notes (PNG/JPG) and PDFs — I can read
and translate Tanglish text in images. **What I cannot:** video or audio files —
I can't watch/transcribe them. To use a video, provide a transcript (NotebookLM,
YouTube captions, or any speech-to-text) and I'll work from that.

When sources arrive, verify against §2/§3:
- [ ] Do the numeric rules match (SL caps 0.4%/8%/10%, RR 1:1.5 vs 1:2 per strategy, <8% swing filter, 2.5% gap / 4% move skips, EMA lengths 20/200/50, RSI length 10)?
- [ ] The option-selling schedule exactly (9:20 & 1:00 entries, 25% SL, force-close 1:00/3:00, close-other-on-SL) — this is the one we'd model, so precision matters.
- [ ] The FinNifty→BankNifty 70/30 lead-lag claim — is it stated as tradeable or anecdotal?
- [ ] Any strategy detail NotebookLM dropped or invented (LLM summaries do both).
- [ ] Whether "DC1 §2.5" cited in the notes matches a numbering in our own spec (would confirm provenance).

**Then extract only what's useful and not already ours:** the option-selling
model (paper + backtest first), the lead-lag hack as a candidate confluence
input (§8-gated), and any fundamental-scan thresholds for the Phase-6 catalog.

---

## 6. Related
- `docs/COMPETITOR_TOOLS_REVIEW_2026-08-11.md` (screener / fundamentals / seasonality plan)
- `backend/app/profiles/setups.py` (the evaluators these strategies became)
- `docs/phases/phase-06-plan.md` (entry/regime selection — where scan-catalog work lands)
- Zerodha Varsity (`https://zerodha.com/varsity/modules/`) — the authoritative,
  broad free curriculum; study on request, module by module.
