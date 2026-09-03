# "e-book suggested" — deep-read takeaways (2026-08-29)

Read of all 28 PDFs in `~/Documents/e-book suggested/`, mapped to **our** platform. This is a
curated, high-quality list (unlike the earlier academy-freebie folder). Depth here is
proportional to relevance to our open problems, but **no book is skipped**.

**How I read them:** extracted text from every file; deep-read the passages of the
highest-relevance titles (Aronson, López de Prado ×2, Tharp, Harris, Dalton) to ground the
specifics; covered the rest from their extracted text + established knowledge, always steering
to "what does this change for us."

## ⚠ File gotchas found first
- **`Option_Volatility_n_Pricing_-_Sheldon_Natenberg.pdf` is mislabeled** — the file is actually
  **Jay Kaeppel's *The Option Trader's Guide to Probability, Volatility, and Timing***, NOT
  Natenberg's *Option Volatility & Pricing*. Decent practical options book, but not the bible you
  think you have. If you want the real Natenberg, this file isn't it.
- **`9789814383134.pdf` (Kelly Capital Growth Criterion)** is only the **2-page catalog blurb**, not
  the 884-page book. Covered as "what Kelly is," since there's no content to read.
- **Two files are image-only scans with no text layer** — Taleb *Fooled by Randomness* and
  Steenbarger *The Psychology of Trading*. Covered from established knowledge; flag if you want an
  OCR pass.
- **Harris *Trading and Exchanges*** is a **113-page 2002 draft**, not the full ~600pp book.
- **`The Strategic Options Day Trader` (subtitle "…Maximize 200% Profit Daily… Day Trader
  Millionaire")** is the one hype-titled outlier in an otherwise serious list — treat with the same
  skepticism as the academy freebies.

---

## GROUP A — Methodology & not fooling yourself (the most important group for us)

These four+ books are the intellectual backbone of *why our evidence discipline matters*, and they
sharpen it into concrete technique. This is where the collection most changes what we do.

### Evidence-Based Technical Analysis — David Aronson (528pp)
*The book on making TA falsifiable.* Two theses: (1) TA claims must be stated as **objective,
back-testable rules** (no subjective "it looks like a head-and-shoulders"); (2) the killer is
**data-mining bias** — when you search many rules, the best one's backtested return is inflated by
luck, and naïve significance tests overstate it badly. Prescribes proper hypothesis testing,
out-of-sample validation, and bias-correction (White's Reality Check / Monte-Carlo permutation).
**For us:** this is the academic form of the instinct we keep invoking. It *validates* our refusal
to combo-mine 14 factors, and gives the fix: when you test N variants, judge the winner against a
null that accounts for N. **Adopt:** (a) pre-register hypotheses (we said this); (b) a permutation /
multiple-testing correction before believing any shadow-gate or factor-combo result; (c) treat the
frozen engine + §8 walk-forward as our "objective rules + OOS" — which is exactly Aronson-compliant.

### Advances in Financial Machine Learning — Marcos López de Prado (481pp)
*The state-of-the-art on not overfitting financial backtests.* Key tools: **triple-barrier
labeling** (label a trade by which of {profit-target, stop, time-limit} hits first — this is
essentially our MFE/MAE + horizon framing); **meta-labeling** (a primary model picks direction, a
secondary ML model decides *bet size / whether to take it* — precisely the "overlay decides
eligibility, engine stays frozen" pattern we already use!); **purged & embargoed K-fold CV**
(remove train samples whose labels overlap the test window, then embargo a gap — prevents
leakage); **Combinatorial Purged CV** and the **Deflated Sharpe Ratio** (discount your Sharpe by
how many trials it took to find it). His blunt line: *"Each backtest is always overfit to some
extent… always ask in what way you may be overfitting."* **For us:** the single richest technical
source here. Our regime-gate/sl_atr/sector-RS shadow work is *meta-labeling* in spirit. **Adopt
when we do any ML/feature work:** purged+embargoed CV (our walk-forward already embargoes
conceptually — formalize it), and a deflated/number-of-trials-aware bar before promoting any gate.
This directly answers our recurring worry: "some time-bucket / factor-combo will look great by
chance."

### Machine Learning for Asset Managers — López de Prado (152pp)
*The compact companion to AFML.* Denoising covariance matrices, **distance/information-theoretic
feature importance (MDI/MDA/clustered)**, the **"p-hacking / backtest overfitting is the reason most
published factors fail out-of-sample"** argument, and why economic rationale must precede the data
mining. **For us:** reinforces AFML; the practical nugget is *feature clustering before importance*
(don't rank correlated factors independently — cluster them) — relevant if we ever revisit factor
attribution, since several of our factors are correlated (MACD_CROSS/MACD_HISTOGRAM, the pattern
factors).

### Thinking, Fast and Slow — Daniel Kahneman (595pp)
*The definitive account of cognitive bias.* System 1 (fast, intuitive, error-prone) vs System 2
(slow, effortful); anchoring, availability, **loss aversion** (losses hurt ~2× as much as equal
gains), the **narrative fallacy / seeing patterns in noise**, overconfidence, hindsight. **For us:**
the psychology under our own findings — loss aversion is *why* we give back gains and hold losers
(the exit-leak); the pattern-in-noise bias is *why* the ₹44L headline and combo-mining are so
seductive. It argues for exactly what our system externalizes: **mechanical rules that bypass System
1** at the moment of decision.

### Antifragile — Nassim Taleb (650pp)
*Things that gain from disorder.* Fragile = hurt by volatility/tails; robust = unaffected;
antifragile = benefits. The **barbell** (mostly ultra-safe + a little extreme-convex risk, avoid the
fragile middle); **via negativa** (improve by removing/avoiding ruin, not adding); **never blow up —
survival first, because you can't compound if you're out.** **For us:** the risk philosophy behind
the non-disableable circuit breaker and small position sizing on the ₹1L — protect against the tail
that ends the game. It also frames option-*buying* as a (small, defined-risk) convex bet — but only
if sized as the tiny barbell tail, never the core (the opposite of the CAS-lottery mistake).

### Fooled by Randomness — Nassim Taleb (image-only, ~111pp)
*(Text not extractable — from knowledge.)* Survivorship bias, mistaking luck for skill,
under-weighting rare events, the noise-vs-signal problem in track records. **For us:** the reason we
distrust a short winning streak (our paper edge is thin and could be luck), and a direct warning on
the **survivorship bias** in any deep-history backtest — exactly the caveat we already flagged for
the 2018 idea.

---

## GROUP B — Position sizing, expectancy, risk (our R-framework, formalized)

### Trade Your Way to Financial Freedom — Van K. Tharp (181pp)
*The book that popularized the language we already use.* Core ideas: **the "Holy Grail" is inside
you** — success is the *system + psychology + position sizing*, not a magic indicator (his opening
metaphor is a direct rebuke to the tip-group/₹44L fantasy). **Expectancy = average R per trade**
(mean of wins-in-R minus losses-in-R) — *our exact metric*. **R-multiples**: express every outcome as
a multiple of initial risk R (we do this — Tharp is the source of that convention). **Position
sizing is where the objective is actually met** — "how much" matters more than "what to buy," and
it's what turns a positive-expectancy system into a survivable one. He also warns on data-mining
seasonals ("computers will always find 13-of-14-years-on-April-13 — trade only with a cause"). **For
us:** near-total alignment — our risk-first sizing, R-normalized measurement (the horizon study), and
"binding constraint is entry/expectancy not exit" are pure Tharp. The one framing to adopt
explicitly: a system's real edge = **expectancy × opportunity (trade frequency)** — improve
expectancy first (our thin +0.05R is the problem), and size to survive the inevitable losing streak.

### The Kelly Capital Growth Criterion — MacLean/Thorp/Ziemba (blurb only)
*(Only the catalog page is in the folder.)* Kelly = the bet-fraction that maximizes long-run
log-wealth; over-betting Kelly guarantees eventual ruin, so practitioners use **fractional Kelly**
(¼–½). **For us:** the theoretical ceiling on position sizing. Our fixed 2%-risk rule is a
conservative, simpler cousin. Worth knowing as the "how much is mathematically optimal" bound — but
full Kelly is too aggressive for a ₹1L account; our fixed-fractional approach is the right call.

---

## GROUP C — Market structure, auctions, execution (CAS / stops / liquidity)

### Trading and Exchanges — Larry Harris (113pp draft)
*The practitioner's microstructure reference.* Order-driven vs quote-driven markets; **single-price
call auctions** (exactly the CAS mechanism — all orders pool, one clearing price); **order types**
and why **stop orders don't guarantee a price** and can be picked off; liquidity *suppliers* (limit
orders = free options they write) vs *demanders* (market orders pay the spread); **front-running**,
transaction-cost measurement, informed vs uninformed traders. **For us:** the academic grounding for
three things we've already lived: (1) our **CAS = single-price auction** understanding and why the
intraday window is manipulable/illiquid; (2) why **"a stop isn't a seatbelt"** — Harris explains
stops as market orders on trigger, subject to slippage/gaps (validates our honest gap-through-stop
fill model, 6.8.2); (3) liquidity as a written option — the theory behind our liquidity/spread
overlays. High-value reference; keep for Phase-7 execution + the CAS work.

### Mind Over Markets — James Dalton (370pp)
*The fuller, foundational Market-Profile text* (deeper than *Markets in Profile*, which we read
last session). Value area, **initial balance**, range extension, day types (normal, trend,
neutral), **"excess"** (the thin-volume rejection spike that ends an auction and tends to reverse),
other-timeframe activity, attempted-direction vs value. **For us:** reinforces the **CAS Stage-2
refinement already in memory** — classify CAS moves as *excess-type* (sharp, thin, rejected →
reverses) vs *acceptance/value-migration* (holds → continues) and test separately. Dalton is the
canonical source for that vocabulary; when we run Stage-2 after Sep 4, this is the reference.

### Inside the Black Box — Rishi Narang (431pp)
*What quant/algo trading actually is, demystified.* A quant system = **alpha model** (the edge) +
**risk model** (exposure limits) + **transaction-cost model** + **portfolio construction** +
**execution**, plus data + research infrastructure. Trend vs mean-reversion alphas; the danger of
**data mining without theory**; why risk and costs matter as much as alpha. **For us:** a clean
mirror of our own architecture — we already have analogs of every block (confluence engine = alpha;
risk_guards/circuit breaker = risk; the 6.8.2 spread-aware fills = cost model; sizing = portfolio
construction; paper_broker/live_worker = execution). Good vocabulary + sanity check that we're
building the right components in the right shape.

---

## GROUP D — Entry selection, trend, relative strength (our entry-leak, directly)

This group is the most *directly actionable* for our #1 problem (entry selection), because O'Neil
and Minervini are systematic about *which* stocks to buy and *when*.

### How to Make Money in Stocks — William O'Neil (529pp)
*The CANSLIM system.* C = current quarterly earnings, A = annual earnings, N = new
product/high, S = supply/demand, **L = leader (high relative strength vs market/peers)**, I =
institutional sponsorship, **M = market direction** (~3 of 4 stocks follow the general market, so
trade with it). Buy from proper **base patterns** (cup-with-handle etc.) on volume; cut every loss
at **–7–8%**. **For us:** two ideas map straight onto open work — **L (relative strength)** is our
sector-RS shadow, and **M (market direction)** is our market-regime gate. O'Neil's evidence that
most stocks follow the market *supports* having a regime filter (while our data warns it must
*discriminate*, not just gate on 200-DMA). The 7–8% hard stop is a fixed-% cousin of our
classification SL caps.

### Trade Like a Stock Market Wizard — Mark Minervini (432pp)
*SEPA — a tightened, modern CANSLIM.* The **Trend Template** is the gem: only buy when price is
above the 150- & 200-day MAs, the 200-day is *rising*, the 50-day > 150 > 200 (stacked), price is
well off its 52-week low and near its high, and the **RS line is at/near new highs**. Buy
volatility-contraction pivots; sell into strength; cut losses fast. **For us:** the Trend Template
is a **concrete, testable eligibility filter** — exactly the shape of an MCE shadow experiment.
**Candidate:** shadow-test a Minervini-style trend-template gate (stacked-MA + RS-new-high) on our
tradeable cohort, the same way we shadow the regime/sector-RS gates. It's a more discriminating
"trade with strength" rule than a single 200-DMA line — which is precisely the weakness we found in
our current regime gate.

### 24 Essential Lessons for Investment Success — William O'Neil (190pp)
*The pocket version of CANSLIM* — same rules as bite-size lessons (buy leaders in uptrends, cut
losses at 7–8%, buy on breakouts with volume, follow the market). **For us:** no new content beyond
the big O'Neil book; useful as a compact restatement of the RS + market-direction + loss-cutting
discipline.

### How to Make Money Selling Stocks Short — William O'Neil (264pp, chart-heavy)
*The short side of CANSLIM* — short late-stage broken leaders **only in a confirmed market
downtrend**, on breakdown from topping patterns (head-and-shoulders), with tight stops. **For us:**
short-selling needs the live futures/options path (Phase-7), so this is not near-term. But the
principle — **shorts require market-direction confirmation** — again supports a regime filter, and
matches our pair-trading/short-leg constraint (short leg needs futures, deferred).

---

## GROUP E — Trading psychology & discipline (the ₹44L / discipline thread)

### Trading in the Zone — Mark Douglas (143pp)
*The sequel to* The Disciplined Trader *(which we read last session) — his most refined statement.*
**Think in probabilities**: any single trade's outcome is random; edge shows up only over a large
sample, so you must be indifferent to the individual result. The **"5 fundamental truths"** (anything
can happen; you don't need to know what will happen next to make money; wins/losses are randomly
distributed around your edge; an edge is just a probability; every moment is unique). **For us:** the
direct antidote to the emotional pulls we've discussed — it's why we judge the system on *expectancy
over the cohort* (attribution, shadow readiness) rather than any one trade, and why a fixed
daily-profit quota is psychologically wrong. Pair with Kahneman as the "why discipline must be
mechanical."

### The New Trading for a Living — Alexander Elder (452pp)
*A complete retail framework.* The **"three M's"**: Mind (psychology/discipline), Method
(a tested edge + indicators like his Impulse system), Money (risk management — his **2% rule** per
trade and **6% monthly** portfolio stop). Markets as mass psychology; keeping a trading journal.
**For us:** Elder's **2% / 6% rules** are essentially our per-trade risk cap + a monthly circuit
breaker — validation of that design. The journal discipline ≈ our daily-analysis loop + LEDGER.

### Market Wizards: The Next Generation — Jack Schwager (339pp)
*Interviews with modern top traders* (Kullamägi, Breitstein, et al.).
Recurring themes across all of them: relentless **risk control / cutting losses**, asymmetric
payoffs (small losses, big wins), specialization, journaling, and psychological resilience — *not*
secret indicators. **For us:** the ensemble evidence that edge = process + risk discipline + big-R
winners, not a magic setup. Reinforces "let winners run / cut losers" (our exit + horizon work) and
"the edge is in the process."

### Reminiscences of a Stock Operator — Edwin Lefèvre / Jesse Livermore (690pp, illustrated)
*The classic trading memoir (1923).* Timeless lessons: the big money is in the **big move, sitting
tight** (being right *and* holding); don't fight the tape/trend; cut losses fast; markets repeat
because human nature does; beware tips and over-trading. **For us:** a narrative echo of trend-following
+ loss-cutting + patience; "sitting tight" is the psychological side of our let-winners-run / horizon
finding. Enrichment, not method.

### The Alchemy of Finance — George Soros (389pp)
*Reflexivity.* Prices don't just reflect fundamentals — participants' biased views *change* the
fundamentals, in feedback loops (boom/bust). Markets are not efficiently self-correcting. **For us:**
philosophically important (it's *why* trends over- and under-shoot, and why regimes shift — the
bracket→trend transition Dalton describes), but not a mechanical tool. Context for macro/regime
thinking, low direct implementation value.

### Mastering Trading Psychology — Andrew Aziz (345pp)
*Practical retail psychology* (with contributor stories) — process over outcome, handling
losses/tilt, routines, journaling. **For us:** solid but covers the same ground as Douglas/Elder at a
more anecdotal level; nothing new for our (automated) system, useful as human-side reinforcement.

### The Psychology of Trading — Brett Steenbarger (image-only, ~348pp)
*(Text not extractable — from knowledge.)* A clinical-psychologist trader on self-observation,
emotional pattern-breaking, and treating trading improvement like behavioral change. **For us:**
human-discipline reinforcement; not system-relevant. Flag if you want an OCR pass.

---

## GROUP F — Retail day-trading tactics (lower relevance to our EOD/swing system)

These are competent retail *manual day-trading* guides (Bear Bull Traders / Peak Capital). Our
platform is EOD/swing/positional and automated, so their tactical specifics (Level-2 tape reading,
1-minute scalps, hotkeys) don't port — but the **risk/discipline scaffolding does**.

### How to Day Trade for a Living — Andrew Aziz (228pp)
*The popular beginner's day-trading primer.* Tools, a few chart-pattern strategies (ABCD, VWAP,
reversals), money management, psychology; heavy emphasis on **risk per trade, daily max loss, and
trading only A+ setups**. **For us:** the money-management/discipline chapters echo our own rules;
the intraday tactics aren't applicable to our stack.

### Advanced Techniques in Day Trading — Andrew Aziz (410pp)
*The follow-up* — more on VWAP, moving-average strategies, float/catalysts, and detailed trade
management. **For us:** same verdict — the "trade with the trend / manage risk / few good setups"
skeleton aligns; tactics don't transfer.

### TradeBook: How to Build a Complete Trading System — Andrew Aziz (342pp, 2025)
*Framework for assembling a personal trading system* (watchlist → scan → setup → entry/exit rules →
risk → review). **For us:** conceptually the closest of the Aziz set to what we do; a decent checklist
for "what a complete system needs," though far less rigorous than Narang/Tharp on the same question.

### The Strategic Options Day Trader — Andrew Aziz (118pp)
*(Hype-titled — "200% profit daily / millionaire.")* Short options day-trading playbook. **For us:**
weakest/most-overhyped entry in the list; the intraday-options-scalping premise is exactly the
CAS-window risk we cautioned against. Skip.

### The Option Trader's Guide to Probability, Volatility, and Timing — Jay Kaeppel (288pp)
*(This is the file mislabeled "Natenberg.")* Practical options strategy selection by
volatility/time regime — using probability of profit, IV rank, and calendar/seasonal timing to pick
strategies. **For us:** reasonable practical options grounding relevant to our F&O engine + the CAS
options discussion (it's about *defined-risk, probability-based* option structures — the antithesis
of the 0-DTE lottery). Not the rigorous Natenberg, but useful. If you want true options-pricing depth
(greeks, vol surface), source the real Natenberg.

---

## GROUP G — Industry / other

### The Future of Investment Management — Ronald Kahn (138pp, CFA Research Foundation)
*Where active management is heading* — from a co-author of *Active Portfolio Management* (the Grinold-Kahn
"Fundamental Law": IR ≈ IC × √breadth). Themes: smart beta, big data / ML / alternative data, the
shrinking of traditional alpha, the information ratio and breadth. **For us:** the **Fundamental Law**
is a useful mental model — your edge scales with *skill × number of independent bets*. It nuances the
Tharp "expectancy × frequency" point and cautions that adding breadth only helps if the bets are
*independent* (our correlated factors/positions are not). Strategic context, not a build input.

---

## SYNTHESIS — what this collection means for us

**1. The collection's center of gravity is exactly our biggest risk: fooling ourselves with
overfit backtests.** Aronson + López de Prado (×2) + Kahneman + Taleb all converge on it. This is
strong outside confirmation of the discipline we keep invoking (rejecting combo-mining, walk-forward,
pre-registered hypotheses). **Concrete upgrades to adopt:** (a) a multiple-testing / deflated-Sharpe
correction before we ever promote a shadow gate or a factor combo; (b) purged + embargoed
cross-validation formalized for any future ML/feature; (c) meta-labeling is the *name* for our
overlay pattern (frozen engine picks direction, overlay decides eligibility/size) — we're already
doing the right thing, and can lean into it deliberately.

**2. Our measurement/sizing framework is already textbook.** Tharp (R-multiples, expectancy,
position-sizing-is-the-objective, "holy grail is inside you") and Elder (2%/6%) essentially describe
what we built. The reframe to keep: **edge = expectancy × frequency**, and our +0.05R expectancy is
the thing to raise — not the trade count, and never a daily-% quota.

**3. Two concrete, testable ideas for the entry-leak (our #1 problem):**
   - a **Minervini/O'Neil trend-template gate** (stacked MAs + RS-line-at-new-highs) as an MCE
     *shadow* experiment — a more *discriminating* "trade with strength" filter than the blunt
     200-DMA regime gate we found too coarse.
   - O'Neil's "M = market direction" evidence *supports* having a regime filter at all — the fix
     our data points to is making it discriminate, which the trend-template does.

**4. The CAS thread is well-served.** Dalton (*Mind Over Markets*) deepens the excess/value-area
vocabulary already feeding the CAS Stage-2 refinement; Harris (*Trading and Exchanges*) is the
microstructure grounding for why the CAS auction is manipulable and why stops aren't seatbelts —
supporting both the Stage-2 study and the 6.8 execution-realism work.

**5. Everything psychological (Douglas, Kahneman, Taleb, Schwager, Livermore, Elder) reinforces the
same thing our system mechanizes:** think in probabilities over a cohort, cut losses, let winners
run, size to survive the tail, and don't chase — the antidote to this week's CAS/₹44L temptations.

## Prioritized actions this collection suggests (all read-only research; none built)
1. **Adopt an explicit multiple-testing / deflated-Sharpe bar** (Aronson + López de Prado) before
   promoting *any* shadow gate — this directly hardens the sl_atr / sector-RS / regime flip decisions
   and the combo-hypothesis tests. **Highest value; cheap.**
2. **Shadow-test a Minervini trend-template gate** as a new MCE experiment — the most promising fresh
   idea for the entry-leak. Needs the deep index/MA history (the backfill already flagged).
3. **Formalize purged+embargoed CV** language for our §8 walk-forward (mostly documentation — we
   already embargo conceptually).
4. Keep **Dalton (MoM) + Harris** as the reference pair for the CAS Stage-2 study after Sep 4.
5. If we want real options-pricing depth for the F&O engine, **source the actual Natenberg** — the
   file we have is Kaeppel.

_Nothing above touches the money path or the frozen engine; these are research directions for after
watch mode (Fri 2026-09-04)._
