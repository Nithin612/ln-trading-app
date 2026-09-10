# `docs/reading/security_analysis/` — what 14 books say about our entry problem

_Read 2026-09-09. 14 PDFs, ~1.5M words. Written against a specific question from the user:_

> _"check whether we can find a solution for our entry or stock selection, or how we can
> validate our previous day EOD signal with current day live market and only if it
> confirms/double confirms we can show in alerts … or alert the user only on the correct time
> to trade, not sooner or later, by checking it with changing live price."_

This is the right question to be asking. As of 2026-09-08 **both** queued profitability levers
are spent: D5 showed exit geometry is not the lever, D1 showed the RVOL generation lever is not
either. No queued item attacks profitability. So: is there a new lever in these books?

**Short answer: no — but the reading was still worth it, and not for the reason expected.**

The folder points unanimously at one architectural gap in our pipeline, and the gap is real.
Its remedy is not: tested against 108,506 stock-days and again against 1,979 of our own minted
signals, it does not pay. Four more levers extracted from the same books are refuted or fail the
proxy check. §6 is the evidence; §8 is what the reading actually yielded.

---

## 0. The gap the books identify — real, and worth fixing for its own sake

Every trading author in this folder builds an entry in **three** stages:

```
   SETUP                    TRIGGER                        MANAGE
   "this is a candidate" →  "the market has now proved it" →  "size, stop, target"
   (evening homework)       (next session, on live price)      (after the fill)
```

**We have no TRIGGER stage.** Our pipeline is SETUP → MANAGE. The confluence engine finds a
candidate at the close, stamps `entry = yesterday's close`
(`backend/app/services/signal_service.py:236` — verified, not quoted from docs), derives SL and
TP from that number (`app/analysis/risk.py:56 compute_levels`), and the live layer then fires an
alert when price merely *touches* a **symmetric ±0.5% band** around it
(`app/broker/live_levels.py:217`, `settings.live_entry_zone_pct`). Nothing in that chain ever
asks the market to demonstrate anything. A BUY drifting *down* into the band fires the same
"Entered zone" alert as a BUY breaking *up* through it.

That is not a small omission — it is the one stage all fourteen books consider *the* entry, and
the missing direction check is a plain defect worth fixing on its own terms.

**But "we lack the stage they all have" is an argument, and an argument is exactly what hard
constraint #8 forbids acting on.** So §6 measures the stage instead of installing it. The result
is that adding it does not improve outcomes: the trades that confirm really are better trades,
and the price of the confirmation consumes the difference. Fix the alert because it is wrong;
do not expect it to make money.

---

## 1. The folder, honestly

Not all 14 bear on the question. Recording which do — and which do not — so a future session
doesn't re-read the whole shelf.

| # | Book | What it is | Bears on our question? |
|---|---|---|---|
| 1 | **Carter — Mastering the Trade** (654pp) | Working intraday/swing playbook with explicit rules | **Yes, heavily.** Ch7 opening gap · Ch5 day-type classification from the first six 5-min bars · Ch11 the squeeze (a real compression lever) · Ch8 floor pivots |
| 2 | **Elder — Come Into My Trading Room** (322pp) | Method + money management | **Yes.** Screen 3 IS the answer to the user's question. Impulse System = a veto. Market Thermometer = a volatility-scaled entry-zone width we can actually compute |
| 3 | **Brooks — Trading Price Action: Ranges** (617pp) | Bar-by-bar, deepest treatment of entry mechanics | **Yes.** "Need Two Reasons to Take a Trade" · Entering on Stops vs Limits (regime-conditional) · the trader's equation, which *explains our own R:R reversal* |
| 4 | **Weinstein — Secrets for Profiting…** (430pp) | Stage analysis + relative strength | **Yes.** The buy-stop-with-a-limit is the single most directly implementable idea in the folder. Stage 2 filter + RS veto + "minimum resistance overhead" |
| 5 | **Damir — Price Action Breakdown** (83pp, image-only scan) | Market-profile-derived: value area, control price, excess, initiative vs responsive | **Yes.** Gives the *regime* axis that reconciles the contradiction in §3, plus a principled overhead-supply test |
| 6 | **Murphy — Technical Analysis of the Financial Markets** (494pp) | The reference text | **Partly.** Corrects Carter for single stocks: "gaps are always filled" is a myth; gap type is structural. Dow's confirmation/volume tenets |
| 7 | **Teo — Price Action Trading Secrets** (137pp) | Practical retail-facing framework | **Partly.** MAEE (Market structure → Area of value → **Entry trigger** → Exits) names our missing stage cleanly |
| 8 | **Lefèvre — Reminiscences of a Stock Operator** (690pp) | Livermore, narrative | **Partly.** "Line of least resistance" is the same rule, stated best. Also the source of the "pay up" idea that needs bounding — see §3 |
| 9 | **Johnson — Day Trading** / **…Day Trading King** (234pp total) | Lead-magnet tier; mostly derivative | **One useful thing:** the full-gap vs partial-gap taxonomy, and an explicit "wait for the first hour, then trigger off its extreme" rule. Its claim that "fills always happen because the market prefers a stable state" is simply wrong — Murphy debunks it directly |
| 10 | **Graham & Dodd — Security Analysis** (818pp) | The book the folder is named after | **No — and it says so.** See §4.5. It is about paying less than intrinsic value over years; it explicitly rejects confirmation-buying as *speculation*. Useful later for MCE fundamentals, not for this |
| 11–13 | **DEFIN576 / FMG_304 / IARE SAPM** (627pp) | University lecture notes: CAPM, Markowitz, EMH, Dow theory summaries | **No.** Nothing operational we don't already have. Profiled and set aside |

Two are pirated OceanofPDF rips, consistent with the earlier `~/Documents/e-books/` review. Same
note applies: read them, don't build a dependency on the source.

⚠ **On the quotations.** Weinstein's PDF is a low-quality OCR and Damir's is an image-only scan
read page by page, so fractions and symbols in those two are normalised from OCR artifacts (the
Weinstein stop-limit line reads `"Buy 1,000 XY Z at IZVB stop—l23/s limit"` in the raw text; the
surrounding paragraph fixes the prices as 12⅛ and 12⅜). Quotes from the other twelve are verbatim
from `pdftotext -layout` output. The two load-bearing ones — Brooks' trader's equation (§4.1) and
Weinstein's bracket (§2) — were re-checked against the source text after being written.

---

## 2. The convergent rule — five authors, five vocabularies, one mechanism

This is not one author's opinion. It is the closest thing to consensus in the folder, and it
answers the user's question directly.

**Elder** (Screen 3, p137) — the cleanest statement of exactly what was asked:

> "When the first two screens give you a buy signal … **place a buy order at the high of the
> previous day or a tick higher.** We expect the major uptrend to reassert itself and catch a
> breakout in its direction. **Place a buy order, good for one day only.** … You do not have to
> watch prices intraday."
>
> And with live data: "follow a breakout from the **opening range**, when prices rally above the
> high of the first 15 to 30 minutes of trading."

**Weinstein** (p65–67) — and he adds the half Elder leaves out:

> "What a buy-stop order does is tell the specialist that you want to buy stock XYZ. But — and
> this is an incredibly important but — **only if the stock breaks out above a certain level.**"
>
> Then the failure mode: "right before the market opens good news is announced and it opens much
> higher at 15. Instead of getting in at your perfect entry price of 12⅛, you are now the proud
> owner of XYZ at 15. … **the reward/risk ratio is now far less favorable than it was at 12⅛.**"
>
> And the fix — one order carrying both halves:
> **"Buy 1,000 XYZ at 12⅛ stop — 12⅜ limit — GTC."**

**Brooks** (Ch27, p491):

> "One of the best ways to trade using price action is to **enter on a stop, because you are
> being carried into the trade by the market's momentum** and therefore are trading in the
> direction of at least a tiny trend (at least one tick long). **This is the single most reliable
> entry approach**, and beginners should restrict themselves to it until they become consistently
> profitable."

**Livermore** (via Lefèvre, ch10):

> "The thing to do is … make up your mind that **you will not take an interest until the price
> breaks through the limit** in either direction."
>
> — "Why not buy it now, at $1.14?"
> — **"Because I don't know yet that it is going up at all."**

**Johnson** (gap chapter) — the same rule with an explicit clock:

> "look to the short timeframe charts **post 10 am** before setting a long stop that is roughly
> **2 ticks over the high that was achieved during the first hour** of the day."

So: **the trigger is a level the market has not yet traded through, in the signal's direction,
with a ceiling on how much you'll pay for it, alive for a bounded time.** Four of the five
authors put that level at the prior bar's extreme or the opening range's extreme.

---

## 3. The apparent contradiction, and its resolution (this part matters)

Damir says the *opposite* of Livermore, in plain terms (p52):

> "**As a rule, seek to buy in excess below value or in the bottom value area**, between the
> value area low and the control. … **Definitely do not buy when price is in excess territory
> above value.**"

And Brooks says both, explicitly conditioned (Ch28, p493):

> "When the market is in a **strong trend**, entering on **stops** is a reasonable approach. When
> it is in more of a **channel**, they will be more inclined to look to enter on **limit
> orders**. … after the channel has gone on for a while, many experienced traders will switch to
> entering on limit orders at and below the low of the prior bar instead of on stop orders above
> the high of the prior bar."

**Resolution: the entry MECHANISM is regime-conditional, not universal.**

| regime | entry mechanism | why |
|---|---|---|
| trend / imbalance (initiative move) | **STOP** above the prior extreme — pay up for proof | the move is real and continuation is the base rate |
| range / balance (inside a value area) | **LIMIT** at the lower half of value — buy the dip toward control | price is *attracted* to the control price; a breakout is probably false |

And the worst option is the one we currently run: **a market-style fill at yesterday's close,
which is an arbitrary point inside whichever regime happens to hold.** In a trend it under-pays
for a fill that never comes on our terms; in a range it buys mid-value where Damir's "control
price gravity" pulls price nowhere.

Note also what "pay up" actually means for Livermore: his trigger was $1.20 and he bought at
**$1.20½** — a 0.4% premium for confirmation. Not a 5% chase. That reconciles the folder with our
own hardest-won finding (displacement, not age, is the discriminator: at-entry +₹9,830/55% vs
chased 0.33–1R −₹12,789/22%). **Confirmation and anti-chase are not in tension — the ceiling is
what separates them**, and Weinstein's stop-limit is precisely that ceiling.

Two more converging statements of "don't take the first poke":

- **Brooks:** "the only other time only one reason is needed … is when there is a **second
  entry**. By definition there was a first entry, so the second entry is the second reason."
- **Weinstein:** "after a stock breaks out … there is usually at least one profit-taking
  correction that brings the price back close to the initial breakout point. **This is an ideal
  second chance** to do further buying."
- **Damir:** "We do not enter a trade when the initiative move breaks the value limit because
  there are many false breakouts. … **We trade if the initiative move is confirmed by a
  responsive move back to value followed by a subsequent initiative move in the same
  direction.**"

Three vocabularies, one rule: **take the second push, not the first.**

---

## 4. What the books say about decisions we have already made

### 4.1 ⭐ Brooks explains our R:R reversal — theoretically, not just empirically

This is the most valuable single paragraph in the folder for us (Ch25, p438):

> "Edges are rarely large, so **whenever one of the three variables is unusually good, it will be
> offset by one or both of the other variables being bad.** For example, if the potential reward
> is much larger than the risk, meaning that the risk is relatively small, the probability is
> usually small. If the probability is high, the reward is small and the risk is often high."

We reverted the R:R≥1 gate on 2026-09-03 because the blocked cohort was the book's *only*
profitable one (24 trades, +₹10,585, 63% win, 33% tp_hit vs 77 trades, −₹26,792, 48% win, 16%
tp_hit). We recorded that as an empirical surprise. **It was not a surprise; it is the structural
trade-off.** R:R and win-rate are priced against each other by the market. Our gate tried to buy
a better R:R for free and got charged in win rate.

Consequences worth writing down:

- The R:R floor must **never** be re-promoted on the identity argument. The identity ("R:R<1
  needs >50% win to break even") is true and irrelevant, because the market supplies the >50%.
- It independently explains **D5**: no constant-R:R target beat the frozen absolute-% target
  because moving the target trades probability for reward at roughly fair odds. Every paired ΔR
  was negative and |t| ≤ 0.65 — that is what "fair odds" looks like in data.
- **Corollary, and it is the whole reason this document exists:** expectancy can only be improved
  by moving the **probability** curve — i.e. by *when and whether* you enter — not by re-cutting
  risk and reward. Which is exactly the stage we don't have.

### 4.2 Carter corroborates the horizon/stop-width finding, from the other side

> "**In general, wider stops produce more winning trades.** … one of the reasons many traders fail
> to make it in this business is that they are using **stops that are too tight**. … Note that one
> of the best signs of an amateur trader is a person who uses only tight stops **or a 3:1
> risk/reward ratio on every trade**."

Our own numbers (2026-08-25): 14 trades with stops <2% of price lost ₹25,951 at 29% win; stop
width ÷ average daily range <1.0× → 8/8 recovered *after* being stopped at −1.45R. And D5 tested
the fixed-ratio target and refuted it. Carter names both failure modes in one paragraph, written
in 2005. Our `sl_atr` shadow gate measures exactly this and sits at t ≈ 0.41 against a 3.6 bar —
**the mechanism is real and our sample cannot prove it.** That is a sample problem, not a
disagreement.

### 4.3 Brooks corroborates `entry_diversity` — our only ACTIVE gate

> "One of the most important rules is that **you need two reasons to take a trade**, and any two
> reasons are good enough."

Our diversity gate enforces "≥2 scoring factors, and no single factor >90% of the confluence".
Same rule, arrived at independently, and it is the one gate we exempted from the DSR bar because
it encodes a stated hard rule rather than a measured edge. Brooks agrees that is the right
category for it.

### 4.4 Weinstein corroborates the MCE gate-not-additive design

> "As long as this [relative-strength] line is in a downtrend, **don't consider buying the stock
> even if it breaks out** on the price chart."

That is a veto over a price signal, never a term added to a score — which is the MCE's founding
design constraint ("top-down as GATES/MODIFIERS, never additive"). Elder puts the same
architectural point in general terms: the Impulse System is used as a *negative* rule, and
"**such 'negative rules', designed to keep you out of trouble, are among the most useful for
serious traders.**" Our whole overlay pattern is that idea. Good.

### 4.5 Graham & Dodd dissent — and it should be recorded, not hidden

The book the folder is named after argues *against* the central rule above:

> "we cannot avoid the conclusion that **the most generally accepted principle of timing — viz.,
> that purchases should be made only after an upswing has definitely announced itself — is
> basically opposed to the essential nature of investment.** … If the investor is now to hold back
> until the market itself encourages him, how will he distinguish himself from the speculator?"

He is right, and he is answering a different question. Graham's holding period is years and his
edge is price-vs-intrinsic-value. Our system holds 5 trading days (swing) to 30 (positional) and
has no intrinsic-value input at all — in Graham's taxonomy it is speculation, and confirmation is
the correct discipline *for speculation*. Worth stating plainly rather than quietly siding with
the technicians. Where Graham *will* matter is the MCE's fundamentals slice, if it is ever built.

---

## 5. Every lever extracted from the folder, with its verdict

Everything testable here is computable from data we already hold — **2,080,305 daily bars** in
`ohlcv_1d` across 3,392 stocks; nothing needed a vendor. Verdicts are from §6; the table is the
index into it.

| # | Lever | Mechanism | Verdict (§6) |
|---|---|---|---|
| **L1** | **Next-day confirmation trigger** (Elder/Weinstein/Brooks/Livermore) | enter only on a stop through the prior bar's extreme, with a ceiling, alive N days | **⛔ REFUTED on BOTH samples (§6.1 market-wide, §6.5 on our own 1,979 signals).** Selection is real; the trigger price consumes it. Fill cost t ≈ −8; every benefit t ≤ 1.2 |
| **L2** | Directional entry zone | replace the symmetric ±0.5% band with a one-sided trigger | ✅ **Still worth doing — as a CORRECTNESS fix, not a P&L lever.** A BUY drifting *down* firing "Entered zone" is wrong whatever §6.1 says |
| **L3** | Elder **Market Thermometer** | quiet-bar entry, hot-bar exit | **⛔ REFUTED (§6.2).** No forward edge; the apparent 1.8pp effect was same-day mechanics |
| **L4** | Weinstein **Stage 2 / 30-week MA** filter | never buy below a flat-or-falling 150-day MA | **⛔ REFUTED (§6.2).** t ≤ 2.54, horizon-dependent, vs a 3.6 bar |
| **L5** | **Overhead supply** ("minimum resistance overhead") | trapped volume between price and the target | **⛔ REFUTED AS A PROXY (§6.4).** Monotone whole-sample gradient (t 9) that inverts under low volatility and collapses in mid-momentum |
| **L6** | Carter **squeeze** (BB(20,2) inside KC(20,1.5)) | compression precedes expansion | **⛔ NO EDGE (§6.3).** 3,610 fires, \|t\| < 1 at every horizon, market-neutral |
| **L7** | Damir **value area / control price** | buy lower value, never in excess above value | ⏸ **Untested.** Its two components — a volume-by-price histogram and a distance-from-value measure — are exactly the two that failed the proxy check as L5, so the prior is now poor |
| **L8** | Carter **day-type classifier** | first six 5-min bars' volume ⇒ choppy vs trending day by ~09:45 IST | 🚫 **Untestable today** — needs intraday history destroyed on 2026-09-07 (§7.3) |
| **L9** | Gap taxonomy (Murphy's types, Johnson's full/partial) | classify the open vs (prior close, prior high) | ⏸ censused inside §6.5's report; descriptive only |
| **L10** | Carter/Elder higher-timeframe alignment | never trade against the weekly | ⚠ **Weak support (§6.3).** Firing *against* the weekly is mildly harmful (t −1.7 to −2.1); aligning removes a negative rather than adding a positive |
| **L11** | **12-month price momentum** — *not from the books* | rank candidates by trailing 12m return | 🔬 **The most promising thread here**, and it arrived as a *control variable* in §6.4: momentum was strong enough to absorb an apparent effect with t = 9. D1 refuted *volume* (RVOL); price momentum has never been tested |

Explicitly **not** on this list: Carter's $TICK/$TRIN/$VOLSPD internals and the AUDJPY carry
proxy (no Indian equivalents wired, and the ones that exist are index-level, which MCE already
covers), his 3:52 play and tick fades (intraday, and we have no intraday history), Elder's
SafeZone (an exit tool — and exits are not the leak), and anything requiring options-flow.

---

## 6. The measured answer — four pre-registered tests, on our own data

Hard constraint #8 is "NEVER flip a gate/knob on an argument — check the accruing data first",
and the corollary the R:R reversal taught us: **an identity about arithmetic still rests on an
empirical premise; test the premise.** So none of §2's consensus was taken on the authors'
authority. Four tests, each pre-registered to a named claim, all read-only, all on the CA-clean
window (2023-07-03 →) of the 250 most liquid active stocks.

⚠ **The paper book is not the corpus.** The 2026-09-07 dev-DB destruction took all 138 paper
positions, all signal outcomes and all intraday bars. What survived is `ohlcv_1d` (2,080,305
bars) and `fo_bhavcopy`. Every test below therefore runs on daily bars — a **larger** sample than
the lost 99-trade book, but see §7.3 for what that costs.

⚠ **Two corrections applied 2026-09-10 after a quant-verifier review; both are in the numbers
below.** (1) The window is **not** "CA-clean" — `ohlcv_1d` is CA-unadjusted and **49 unadjusted
corporate actions, 35 of them ≥40% halvings, sit inside this exact 250-stock universe**
(SHRIRAMFIN −81.1%, COFORGE −79.7%, ANGELONE −90.1%). I inherited that claim from an existing
script and repeated it without checking. Observations whose forward window contains a
|close-to-close| jump > 25% are now dropped and the count is printed. (2) **The t-statistics were
inflated.** Averaging each day's cross-section removes same-day dependence but *not* the overlap
between day t and day t+1, which share k−1 sessions of the same future; under H0 that inflates
the naive t by ~√k (sd 3.32 at k=10, 4.45 at k=20). Every t below is now **Newey-West at lag
k−1** (`app.services.block_bootstrap.newey_west_t`, added with its own H0 canary test), with the
naive t printed beside it. **Both corrections made the negatives stronger, not weaker.**

### 6.1 Does breaking yesterday's high pay? — `confirmation-base-rate-2026-09-09.md`

108,506 stock-days; 45.2% trade through the prior session's high. 841 stock-day/horizon
observations dropped for an unadjusted corporate action in the forward window.

| cohort | +1d | +3d | +5d | +10d |
|---|---|---|---|---|
| all: enter at open *(implementable)* | -0.070% | +0.087% | +0.236% | +0.591% |
| **confirmed: enter at trigger** *(implementable)* | -0.176% | -0.020% | +0.083% | +0.426% |
| confirmed + under a 2% ceiling — *Weinstein's stop-limit* | -0.172% | -0.010% | +0.086% | +0.419% |
| confirmed: enter at open — *decomposition only, not a strategy* | +1.018% | +1.177% | +1.284% | +1.632% |
| not confirmed: enter at open — *decomposition only* | -0.915% | -0.744% | -0.586% | -0.238% |

**And now the hypotheses are actually tested.** My first pass reported only the *level* t of each
cohort and then compared two levels by eye — which is not a test of anything. Each hypothesis is
a **difference**, so the report now builds the daily series `mean(A) − mean(B)` over the days both
cohorts occupy and reports the Newey-West t of that one series:

| hypothesis | difference | +1d | +3d | +5d | +10d |
|---|---|---|---|---|---|
| **H-A** (Elder/Brooks/Livermore) | confirmed@trigger − all@open | **−3.46** | **−2.94** | **−3.51** | **−3.00** |
| **H-A2** (Weinstein's ceiling) | capped@trigger − all@open | **−3.24** | −2.55 | **−3.35** | **−3.06** |

**H-A is not merely un-helpful — it is significantly WORSE, at every horizon**, by −0.107% to
−0.165% per trade. The selection signal is real and enormous (confirming days average +1.018% next
session against −0.915% for days that don't, naive t 13.8) and it is **completely priced into the
trigger**.

Two things my first pass got wrong here, both now fixed:

- **It never tested Weinstein.** The rule as originally coded bought *any* gap, however large —
  precisely the failure his stop-limit exists to prevent. H-A2 adds his 2% ceiling and it changes
  nothing: −3.24 to −3.06. The ceiling does not rescue the trigger.
- The two middle rows are *not* strategies. They use the fact that the day *would* confirm, which
  does not exist at the open. They are there to split the rule into selection and fill cost, and
  the split is the finding: **confirmation's edge is entirely same-day and already realised by
  the time you can act on it.**

This is Brooks' trader's equation (§4.1) measured on 108k Indian stock-days. You cannot buy the
information for free; the trigger price *is* where the market charges you for it.

### 6.2 Weinstein's 30-week MA and Elder's Thermometer — both refuted, now as differences

| hypothesis | difference | +1d | +3d | +5d | +10d |
|---|---|---|---|---|---|
| **H-B** (Weinstein 150-DMA) | above-rising − not-above, from close | −0.35 | +0.68 | +1.15 | +2.20 |
| **H-C** (Elder Thermometer) | quiet − hot, from close | −1.44 | +2.70 | +1.35 | +1.06 |

Neither clears anything like the t ≈ 3.6 bar, and both flip sign across horizons — the signature
of noise rather than a horizon effect.

⚠ **H-C nearly became a false lever, and it is worth recording how.** Measured from the *trigger*
price — the intuitive thing to do — the split reads **QUIET −1.028% vs HOT +0.775%**, a 1.8pp
spread at t = −17.8 / +10.1, which looks like a spectacular discovery *pointing the opposite way
to Elder*. It is an artifact: a return measured from the trigger spans the remainder of the entry
day, so a bar that has already run far past the trigger books that run as "forward" return.
Measured from the entry day's close the effect vanishes. **Both bases are printed in the report
so this cannot be quietly re-discovered.**

### 6.3 Carter's squeeze as a generation lever — no edge — `squeeze-study-2026-09-09.md`

Generation is the open problem (D5 and D1 both spent), and the squeeze is the only fully
mechanical *generation* idea in the folder. BB(20,2) inside KC(20,1.5), fire when compression
ends, direction from 12-period momentum, entry at the next session's open. **3,609 fires.**
Returns are excess over that day's cross-sectional universe mean, signed so a short earns the
negative of drift — the window is a strong Indian bull market and a long-biased rule would
otherwise look free.

| cohort | +1d | +5d | +10d | +20d |
|---|---|---|---|---|
| squeeze fire (all) | −0.023% (t −0.49) | +0.051% (t +0.44) | +0.163% (t +0.90) | +0.108% (t +0.41) |
| + weekly aligned (Carter's own filter) | +0.007% (t +0.12) | +0.128% (t +0.94) | +0.207% (t +1.09) | −0.041% (t −0.16) |

**No edge.** |t| ≤ 1.09 at every horizon. This study's cohorts are sparse (~5.5 fires/day), so
the overlap correction barely moved it (+1.05 → +0.90 at +10d) — its t's were honest to begin
with, unlike §6.4's.

### 6.4 Overhead supply — the apparent lever, and why it is not one — `overhead-supply-study-2026-09-09.md`

`overhead` = the share of the trailing 250 sessions' volume that traded between today's close and
+6% above it (where the frozen swing target sits). 81,567 stock-days, quintiled (645 dropped for an unadjusted corporate action in the forward window).

**My first pass reported this as "a monotone gradient at t +9.2" and rejected it on the proxy
check. Two of those three things were wrong.** The numbers I quoted came from an earlier run than
the report I cited (a W1 violation of my own making), and the t was never significant in the
first place. Corrected:

| overhead quintile | P(+6% touched ≤10d) | P(−8% touched ≤10d) | spread | fwd excess +10d, NW t | naive t |
|---|---|---|---|---|---|
| Q0 (least overhead) | 49.1% | 31.3% | +17.8pp | +0.386% (**t +3.92**) | +6.38 |
| Q1 | 45.9% | 30.1% | +15.8pp | +0.084% (t +1.07) | +1.43 |
| Q2 | 43.9% | 27.7% | +16.2pp | -0.021% (t -0.27) | -0.38 |
| Q3 | 39.8% | 25.7% | +14.0pp | -0.261% (t -3.25) | -4.55 |
| Q4 (most overhead) | 35.3% | 21.4% | +13.9pp | -0.312% (t -2.32) | -4.51 |

Three corrections, each of which weakens the finding:

1. **The t was inflated.** Naive +6.38 → Newey-West **+3.92** at +10d for Q0; Q4's −4.51 → −2.32. An independent
   Monte-Carlo of the naive statistic's own H0 distribution on this panel shape puts it lower
   still (~1.9σ). Either way, **"a whole-sample t of 9" was never true** — the gradient did not
   need a proxy check to fail.
2. **A reachability gradient is not an opportunity gradient.** The same volatility that makes
   +6% easier to touch makes the −8% stop easier to touch too. Adding the missing downside twin:
   the up/down spread only moves +17.8pp → +13.9pp across the whole quintile range, against a
   raw reachability move of 49.1% → 35.3%. **Roughly three-quarters of the apparent edge is
   matched by more stop-outs.**
3. **The proxy check, now run on reachability too.** The Q0−Q4 reachability spread collapses from
   **+13.8pp whole-sample to +4.2pp inside the low-volatility tercile** (and +6.8pp in
   mid-momentum). On the return side the spread inverts under low volatility (−0.153%) and
   collapses in mid-momentum (−0.029%).

**Not promotable, and for a simpler reason than I first gave: it was never significant.**

Two things worth keeping anyway:

- **The reachability result is real even if mostly mechanical.** A flat +6% target is touched
  within 10 sessions 49% of the time in the low-overhead quintile and 35% in the high — the
  frozen target's reachability varies ~1.4× across the universe and is predictable in advance.
  That is a genuine critique of an *absolute-%* target. It is **not** an invitation to re-open
  `compute_levels`: D5 tested constant-R:R targets and every paired ΔR was negative, and §4.1
  explains why a volatility-scaled target is unlikely to pay either.
- **We have never tested price momentum as a selection filter.** D1 refuted *volume* (RVOL); 12m
  price momentum is a different and far better-documented factor, and it was strong enough here
  to absorb an apparent effect. That remains the most promising thread this reading produced —
  though note it is now a thread suggested by a *control variable that killed something*, which
  is weaker evidence than it first appeared.

### 6.5 The rule applied to our own signals — refuted again, harder — `entry-confirmation-study-2026-09-09.md`

The one channel §6.1 cannot see: the base-rate test has no stops, so confirmation might pay by
avoiding immediate stop-outs rather than by adding drift. The frozen `run_single_stock` minted
**1,975 resolved trades** with real SL/TP geometry (4 dropped for a corporate action inside the
holding span); the exit walk is a replica of the frozen `_simulate_trade`, **asserted
trade-for-trade against the original on 400 trades** before any number was read.

| entry rule | n | kept | mean R | total R | win | t |
|---|---|---|---|---|---|---|
| baseline: fill at next open (frozen) | 1975 | 100% | −0.065 | −128.4 | 36% | −1.94 |
| stop @ prior-bar extreme, 1d | 1182 | 60% | −0.044 | −52.4 | 44% | −1.27 |
| … + 0.33R ceiling (Weinstein's stop-limit), 1d | 1151 | 58% | −0.047 | −53.6 | 45% | −1.34 |
| … + 0.33R ceiling, 3d | 1431 | 72% | −0.074 | −106.5 | 45% | **−2.45** |
| … + 0.33R ceiling, 5d | 1537 | 78% | −0.084 | −128.4 | 45% | **−2.87** |
| … + dead if the stop was touched in the SAME BAR, 1d | 1083 | 55% | +0.013 | +14.4 | 47% | +0.37 |
| … + same-bar rule, 5d | 1363 | 69% | −0.011 | −14.6 | 48% | −0.34 |

**Same structure as §6.1, independent sample.** Section 2 separates the two effects:

| | value | t |
|---|---|---|
| SELECTION — baseline R on just the trades that confirm | **+0.109 to +0.255** (vs −0.065 for the whole book) | — |
| FILL COST — paired ΔR on that same intersection | **−0.192 to −0.264** | **−9.6 to −12.8** |

Confirmation genuinely picks the better trades; paying the trigger costs about a quarter of an R
and cancels it. **Note which of the two is statistically solid: the cost is t ≈ −10 to −13; every
benefit figure is t ≤ 0.4.** And at the 3- and 5-day windows the rule is now *significantly worse*
than the baseline (t −2.45, −2.87).

All figures above are **winsorized at `ratios.WINSOR_R` = 10R**, the project's convention for
averaging R. Winsorizing moved *only the baseline* (mean −0.045 → −0.065, t −1.20 → −1.94) —
every variant row is unchanged, because the tiny-stop outliers are trades the confirmation rule
either skips or enters at a wider risk. It made the paired fill cost **more** significant
(t −7.2…−9.4 → **−9.6…−12.8**), so bounding the tails strengthens the finding rather than
rescuing it.

Three things the correction pass changed here, all in the same direction:

- **The corporate-action filter removed only 4 trades but ~49R of fake profit** — those four
  _(the "before" figures in this and the next bullet are from the pre-correction run, preserved
  only in git history at `b143a4f`; everything else here is from the cited report)_
  unadjusted split gaps were worth more than the study's entire original loss (baseline went
  −40.3R → −89.7R, mean −0.020 → −0.045). Exactly the failure mode the reviewer predicted.
- **The one positive column collapsed to nothing.** With CA gaps excluded, the same-bar variant
  goes +0.046 → **+0.013** at 1d and +0.015 → **−0.011** at 5d. The last trace of a positive
  result was a data artifact.
- **The fill cost is NOT target truncation.** The variants keep the frozen target anchored to the
  planned entry while the fill moves toward it, which charges the premium twice. Re-anchoring the
  target to the actual fill (§2b) barely moves the paired ΔR: **−0.262 → −0.268** at 1d. The
  conclusion survives its own strongest methodological objection.

⚠ **And the study's own disclosure table found a hazard nobody was looking for.** Its ten largest
|R| trades **all** have stops between **0.23% and 0.86%** of price, all are positive, and together
they contribute **+128.4R against an unwinsorized total of −89.7R**. That is the documented
tiny-SL artifact (`ratios.MAX_RR`'s reason for existing) dominating an R-based average. R is
therefore winsorized at the project's owned `WINSOR_R = 10R` wherever averaged — the convention
`entry_attribution.py` already follows and this study should have used from the start (W5). **The
robust summaries are the median (−1.000 — the modal outcome is a full stop-out) and the paired
ΔR, which is computed on identical signals and does not depend on the tails.**

Three things worth keeping regardless:

- **The alert-timing answer, directly.** Of all 1,975 signals: **60% confirm on day 1, 70% by day
  2, 80% by day 5 — and 20% never confirm within five sessions.** Any "wait for confirmation"
  alert design has to decide what to do with that last fifth, and a 1-day window is a materially
  different product from a 5-day one.
- **It is not a cohort-mix artifact.** The effect holds inside tight (+0.068) and mid (+0.075)
  stop-width cohorts and is flat-to-negative in the wide cohort (−0.008) — unlike the R:R≥1 gate
  it is not merely re-sorting the stop-width mix. It is simply too small and too uncertain.
- **BUY signals are net-negative (−0.103 mean R, n=1115) and SELL net-positive (+0.030, n=860)**
  over a bull-market window. The reviewer predicted this might be a CA artifact; with CA gaps now
  excluded it persists, though the SELL side shrank (+0.087 → +0.030). Worth its own look, and
  note that a cash-equity delivery short is not actually executable for us.

## 7. What is worth building, and what is not

### 7.1 One correctness fix, and it is not a P&L claim

**Make the entry zone directional.** `live_levels._signal_levels` emits one symmetric `zone`
level per signal, so a BUY drifting *down* into the band raises the same "Entered zone" alert as
a BUY breaking *up* through it. That is wrong on its own terms — the alert claims something about
the signal's direction that it has not checked — and it is worth fixing whether or not §6.1 holds.

What §6.1 changes is the **framing**: this is a correctness fix to an alert, not an entry
improvement. Do not ship it as "we now confirm before alerting, which should improve results",
because the measured answer is that a trigger entry is *worse* than entering at the open at every
horizon out to +10 sessions. Ship it as: the alert now says what it means.

The machinery already exists — `live_levels.py` already computes direction-aware PDH/PDL
`cross_up`/`cross_down` levels per stock (ids 1 and 2) with a re-arm band; they are simply not
wired to signals. Alerting is measure-only by construction, so no recorded number moves.

**Do not promote the bracket to the order path.** §6.5 came back negative on our own 1,979
signals in every unambiguous variant, reproducing §6.1's structure on an independent sample. The
only positive column depends on an intrabar ordering that daily bars cannot resolve and that is
biased in its own favour. If intraday capture is ever restored (§7.3), that one column is worth
re-measuring properly — it is the single open question this reading leaves — but it is a
shadow-first, t ≈ 3.6 proposition, not a build.

### 7.2 Nothing else in the folder is buildable on this evidence

L3, L4, L5 and L6 are refuted or fail the proxy check. L7's two ingredients are the two that
failed as L5. L1 is refuted unconditionally. That leaves:

1. **L11 — 12-month price momentum as a candidate-selection filter.** Not a book idea; it showed
   up as the control that absorbed L5. Cheap to test with the same harness (`overhead_supply_study.py`
   already computes it). Test it market-neutral and inside volatility terciles, exactly as L5 was
   tested, before believing anything.
2. **L10 as a veto only** — "do not take a signal firing against the weekly" — noting the evidence
   is t ≈ −2, i.e. suggestive of harm avoided, not of edge added.
3. **The BUY/SELL asymmetry surfaced by §6.5** — BUY −0.103 mean R over 1,115 trades, SELL +0.087
   over 864, in a bull-market window. Not a book idea and not yet explained; worth its own look
   before it is worth a build.

Everything else here is a negative result, and negatives are the point: four builds that would
have been undertaken on the authority of four respected authors do not survive our own data. That
is the same lesson as the regime gate (promoted on 44 observations, refuted by 88) and the R:R
floor (promoted on an identity, refuted in a week) — arrived at *before* the build rather than
after.

### 7.3 The honest blocker: we have no intraday history any more

The 2026-09-07 dev-DB destruction took `ohlcv_5m` / `ohlcv_15m` / `ohlcv_1h` (only two forensic
day-snapshots from 2026-07-10 and 07-13 survive), along with all 138 paper positions and every
signal outcome. `ohlcv_1d` (2.08M bars) and `fo_bhavcopy` (494k) survived.

So **L8 and everything keyed to the opening range cannot be tested at all right now.** Carter's
day-type classifier, Elder's "high of the first 15–30 minutes", Johnson's "post-10am off the first
hour's extreme" — all need bars we do not have. Two consequences:

- §6's tests deliberately use the **prior daily bar's extreme** as the trigger, not the opening
  range. That is Elder's own no-real-time-data variant, which he presents as primary, so the test
  is faithful — but it is the coarser of the two, and a finer intraday trigger is not ruled out by
  it. It is merely unmeasurable.
- Re-accumulating intraday bars is a **prerequisite** for the finer version of this work, and it
  accrues only in real time. Worth starting the capture before cycle 2 rather than after.

### 7.4 What NOT to do

- **Do not build any of L1/L3/L4/L5/L6 on the strength of §2.** That is the whole point of §6.
- **Do not add a new factor to the confluence engine.** `docs/SIGNAL_ENGINE.md` is protected, the
  engine is frozen, and every idea above is an eligibility/timing judgement, not a score term.
  Weinstein and Elder both insist these are vetoes; adding them additively is the one design error
  the MCE exists to avoid.
- **Do not re-open `compute_levels` on §6.4's reachability result.** It is real, but D5 already
  tested the obvious remedy and §4.1 explains why the non-obvious one is unlikely to pay either.
- **Do not widen stops on Carter's authority.** Already rejected (2026-08-25); "reject, don't
  clamp" means don't take the trade instead.
- **Do not re-promote the R:R floor.** §4.1 makes the case against it stronger, not weaker.
- **Do not chase Carter's internals** ($TICK/$TRIN/$VOLSPD, the AUDJPY carry proxy). No Indian
  equivalents wired; the index-level information is the MCE's job.
- **Do not trust Johnson's "gaps always fill."** Murphy debunks it in the same folder, and for
  single stocks he is right.
- **Do not re-run H-C from the trigger price and get excited.** §6.2 is the record of why that
  reads as a spectacular discovery and is an artifact.

## 8. Verdict

The folder identifies a real architectural gap — **we never ask the market to confirm a setup
before acting on it** — and one real defect that follows from it (the symmetric entry zone).
Fix the defect, as a correctness fix.

Its headline remedy does **not** survive contact with our data, tested twice on independent
samples: market-wide over 108,506 stock-days, and on 1,979 of our own minted signals with real
stops. Both times the same structure — the selection signal is real and large, and the price of
the trigger consumes it. Three of the four other levers extracted from the folder are refuted
too, and the fourth fails the proxy check.

The reading's real yield is not its recommendations. It is:

1. **Brooks' trader's equation**, which explains our own R:R reversal structurally rather than as
   bad luck, and warns that *any* re-cutting of risk against reward is priced at roughly fair
   odds — which is also why D5 found what it found.
2. **Five negative results** that pre-empt five faith-based builds, arrived at before the build
   rather than after. That is the same lesson as the regime gate and the R:R floor, learned
   cheaply for once.
3. **One measured operational number** for the question that was actually asked: 60% of signals
   confirm on day 1, 80% within five sessions, and 20% never do.
4. **A momentum thread** that came from a control variable rather than from any of the fourteen
   books — the only untested idea here with a decent prior.
