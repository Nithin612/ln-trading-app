# Quant / AI-agent repo findings

A running review log. Each external repo the user shares gets one section: what it is,
what survives scrutiny, what we should harvest, and what we should refuse. The last
section is the consolidated **harvest queue** — the only part that should ever turn into
work.

**Every repo gets its own UI/UX pass too**, even when its stack is far
below ours. The bar is not "is their UI better than ours" — it is "**does any single
screen, table, tile or label do a job better than our equivalent**". A Streamlit page can
out-design a React page on *information architecture* while losing on everything else, and
that idea still transfers. Findings split three ways: **take** (better than ours),
**confirms** (their defect is something our rules already forbid — evidence the rule earns
its place), and **reject**.

**And an architecture pass** — system design rather than screen design:
notifications and alerting, navigation and menus, portfolio and position modelling,
credential/session lifecycle, agent topology, cost tiering, state schemas. Architecture
items are numbered `A1, A2, …`.

**And, from 2026-09-03, two more dimensions** — the brief widened to "take any idea worth
having, don't restrict to analysis/architecture/UI": **`T`** test patterns (cases and concepts
worth copying, not just code) and **`W`** workbench (Claude Code agents, skills, hooks, commands
and rules that other repos ship).

So five numbered queues, kept separate because they land in different places and have different
owners: **`H`** analysis/methodology · **`U`** UI/UX · **`A`** architecture · **`T`** testing ·
**`W`** workbench.

Ground rule for this document, and the reason it exists in this form: we have twice
promoted a gate on an argument and had to revert it (regime gate, R:R≥1 — see the
CLAUDE.md hard constraint #8). **A claim in someone else's README is exactly the class of
unchecked premise that rule was written about.** So every number quoted below was
recomputed from the repo's own code and committed data, not read off the README. Where
the README and the code disagree, that disagreement is itself reported as a finding.

| # | Repo | Reviewed | Verdict |
|---|---|---|---|
| 1 | [OnePunchMonk/AgentQuant](https://github.com/OnePunchMonk/AgentQuant) | 2026-09-03 | **Adopt no code, reject the thesis — harvest 4 analysis + 12 UI + 2 architecture ideas.** Its Research Workspace screen is better information design than anything we have for the same job. |
| 2 | [Y-Research-SBU/QuantHarness](https://github.com/Y-Research-SBU/QuantHarness) | 2026-09-03 | **Adopt no code, reject the trading thesis — harvest 5 architecture ideas.** A real paper with real baselines, honestly reported; but it beats logistic regression on **1 of 8 assets**, and its forced-trade design is the opposite of our whole thesis. |
| 3 | [demandai/ai-quant-agents](https://github.com/demandai/ai-quant-agents) | 2026-09-03 | **Not a quant system — a 236-line marketing SDK for a closed paid API.** No algorithm to review; `risk_approved` is hardcoded true. **Harvest 3 UI + 1 protocol idea.** ⭐ Its real value: it names its upstream, **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** — review that instead. |
| 4 | [yebof/quant-agent](https://github.com/yebof/quant-agent) | 2026-09-03 | ⭐ **The best-engineered repo here, and the only one whose claims survived audit.** 63k LOC, 1,344 tests, live-capable via Alpaca, **zero performance claims**. Ahead of us on production discipline; **has no backtest or validation at all**. **Harvest 7 architecture ideas — A11 (session notifier) is the most actionable item in this whole document.** |
| 5 | [PreethamSanji/QuantAgents-NSE](https://github.com/PreethamSanji/QuantAgents-NSE) | 2026-09-03 | **The only NSE agent repo — and its claim fails on six counts**, incl. **look-ahead (fills on the signal bar's close)**, a hindsight-picked survivor universe, and **2 of its 4 agents wired to nothing**. Result is +0.5pp CAGR at Sharpe 0.237. No LICENSE. **Harvest 2 ingredients for the MCE news veto.** |
| 6A | [Mirzabaig313/PaperTrade-India](https://github.com/Mirzabaig313/PaperTrade-India) | 2026-09-03 | ⭐ **A reference implementation, not a cautionary tale.** 24.8k LOC, 543 tests, MIT — a standalone NSE/BSE paper broker: statutory fees, T+1, bands, bracket/OCO, corporate actions, L2 book. **Makes no performance claim** (it is infrastructure). **Read `orders/` + `docs/FEES.md` before Phase 7; take A21 now.** |
| 6B | [artist-hks/SentimentStock](https://github.com/artist-hks/SentimentStock) | 2026-09-03 | **A synthetic-data UI demo** — "Hinglish NLP" and "LSTM-style predictions" are `Math.sin(seed)`. No LICENSE (despite the badge). **Harvest 1 UI idea** (U19, the lag-correlation chart). |
| 6C | [madhusudhan-nikhil/InvestmentPrediction](https://github.com/madhusudhan-nikhil/InvestmentPrediction) | 2026-09-03 | Real FastAPI+React app for Indian retail. **HRP portfolio construction is a genuine pointer**; its **"probable exit date" is arithmetic on the user's own input** — and doesn't even depend on the target price. No LICENSE. **Harvest A24 as a standing rule.** |
| 7 | [sumittttttt/Stock-market-prediction-and-screener](https://github.com/sumittttttt/Stock-market-prediction-and-screener) | 2026-09-03 | Unmaintained 2022–23 student project (MIT). **Picks its LSTM on a scaler fit over the full series and with no persistence baseline** — the winner is plausibly worse than "no change". Its breakout filter is **disabled by a truthy-string bug**. **Adopt nothing**; one pointer for the Minervini trend-template test. |
| 8 | [pramakrishn/express-option-chain](https://github.com/pramakrishn/express-option-chain) | 2026-09-03 | **The only repo on our exact stack** (Kite WS + Redis + Indian derivatives), 952 LOC, unmaintained since 2023. Adopt no code (per-tick Redis writes, no TTL, unbounded threads). ⭐ **But it documents a Kite quirk we are exposed to — quote-mode ticks on a full-mode subscription — and our depth path never checks. A25 + A26.** |
| 9 | [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | 2026-09-03 | **332k LOC in 27 days** (LLM-generated at scale), multi-market daily analysis + push. Adopt no code. ⭐ **But its phase-aware, fails-closed "which bar could this have acted on" resolver is the best treatment of that question in the log** — read `src/core/trading_calendar.py`. Makes no accuracy claim. **A27 + A28 extend A11**; its `AGENTS.md` seeds **W1–W5**. |
| 23–29 | **The .NET batch** — [stock-indicators-dotnet](https://github.com/facioquo/stock-indicators-dotnet) · [StockSharp](https://github.com/StockSharp/StockSharp) · [AlgoTrading](https://github.com/StockSharp/AlgoTrading) · [Financial-Formulas](https://github.com/srbrettle/Financial-Formulas-Library-.NET-Standard) · [backtesting-engine](https://github.com/mccaffers/backtesting-engine) · [TradingStrategies](https://github.com/SoftAlgoTrade/TradingStrategies) · [quant-trading-toolkit](https://github.com/Krexind/quant-trading-toolkit) | 2026-09-03 | **One of seven earns the reading.** ⭐ stock-indicators-dotnet commits **80 hand-calculated `.xlsx` oracles** and tests every indicator through batch/incremental/streaming — yielding **T13** and **T14** about *our* code. ⚠ **StockSharp + AlgoTrading rejected on licence**: proprietary, **unilaterally mutable, with a monitoring duty on the user** — the strongest rejection in the log. |
| 22 | [JerBouma/FinanceToolkit](https://github.com/JerBouma/FinanceToolkit) | 2026-09-03 | MIT, 131k LOC, **1,486 tests**, 95 cited ratio formulas. ⭐ **The counter-example to QuantStats** — it makes the kurtosis convention an explicit documented parameter and cites formulas to source + page. **Does NOT unblock MCE 5b** (FMP-based, no NSE coverage; our blocker is the data half) but is the right reference when 5b is built. **T12**, applied to our own uncited trading-layer constants. |
| 21 | [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | 2026-09-03 | ⭐⭐ **Used it to cross-check our own `deflated_sharpe.py` — found two bugs in QuantStats and confirmed ours is correct.** Its PSR feeds pandas **excess** kurtosis into a formula expecting **Pearson** (SR² coefficient −0.25 instead of +0.5 ⇒ **PSR systematically overstated**), and its `annualize` flag multiplies a probability by √252. **Reference, not dependency.** H12 has a working implementation here; **T11**. |
| 20 | [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | 2026-09-03 | **Re-review of a decision already made** (`EXTERNAL_LIBS_REVIEW_2026-08-02`: "would REGRESS invariants") — **confirmed, with two sharper reasons.** ⚠ **Licence is Apache-2 + Commons Clause: not open source, and it only bites at commercialisation** — incompatible with our stated "possible future productization". Technically it makes constraint #3 a matter of caller discipline (`fshift(1)`). **No queue items; closes the log's look-ahead spectrum.** |
| 19 | [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading) | 2026-09-03 | ⭐⭐ **The most useful source in this review — not for its links, for its replication record.** They ran **4,843 published papers**: median Sharpe **0.37**, **only 48% clear t>1.96**, median beta **+0.17** (stripping it halves the median edge). **H11** sample-size reality check · **H12** we compute no beta or IR anywhere. Also: its own showcase medians **1.06** vs a population **0.37** — a selection effect in the presentation layer. |
| 18 | [yutiansut/QUANTAXIS](https://github.com/yutiansut/QUANTAXIS) | 2026-09-03 | MIT, ~66k LOC, active. Most layers duplicate ground already covered better (vnpy, qlib, AKShare). **One distinctive module — QIFI, an account-state protocol published as spec + DDL + implementation** — and it exposed that **we have no frozen/committed-capital concept**, harmless while paper fills are immediate and a real hazard once Phase 7 has pending orders. **A42.** Ninth repo with no performance claim. |
| 17 | [OpenByteInc/QuantDinger](https://github.com/OpenByteInc/QuantDinger) | 2026-09-03 | ⭐ **The closest product-shaped analogue to our platform**, on nearly our stack (Py3.12/Postgres/Redis), same end-to-end scope, Apache-2, **no performance claim**, committed the day of review. **W6: its MCP server is the best "expose your platform to an agent" security model in the log** — the agent gets a versioned API, never the internals. Plus **A40**, **A41**. |
| 16 | [RyanCodrai/turbovec](https://github.com/RyanCodrai/turbovec) | 2026-09-03 | **Not a trading repo** (quantized vector search for RAG) — **domain rejected, no stretch made.** But it shares our Rust+PyO3 wheel shape, and its `deny.toml` documents **a guard that could not fail caught in its own CI** (`yanked` defaults to Warn ⇒ a yanked dep passed green). **A39: we have no supply-chain gate on `engine/` at all.** |
| 15 | [bbfamily/abu](https://github.com/bbfamily/abu) | 2026-09-03 | **GPL-3 — a hard adoption blocker**, and 2017-era code. But its `UmpBu` "referees" are **meta-labeling implemented years before the term was standard**, and structurally *our overlay pattern*: cluster your actual losers and let the clusters define the veto. **H10** (attacks our hypothesis-driven-partition failure mode; also an overfitting machine — gated behind DSR + H8) and **U20**. |
| 14 | [quantopian/zipline](https://github.com/quantopian/zipline) | 2026-09-03 | ⭐⭐ Archived 2020, but the ancestor of the modern Python backtesting lineage and **architecturally the best idea in the log: look-ahead is not forbidden, it is *not expressible*** (strategies get a `BarData` bound to the simulation clock). **A38 — a composable point-in-time `Restrictions` interface supersedes A30 and unifies our fragmented eligibility logic.** Plus A37, T10. |
| 13 | [akfamily/akshare](https://github.com/akfamily/akshare) | 2026-09-03 | 103k LOC of China data wrappers — **India coverage is incidental and only 13 of 314 HTTP modules mention retry**, so adopt nothing from the data layer. ⭐ **But its answer to "how do you test 400 scrapers" is the best process idea in the log: a self-cleaning debt baseline (T8) and doc/release consistency as failing tests rather than a ritual (T9).** |
| 12 | [wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant) | 2026-09-03 | A **curated list**, not a codebase — mined for candidates, confirms our existing external-libs review. ⭐ **Its best find: purpose-built anti-overfitting audit tools whose worked example feeds pure noise through the audit and shows it caught** — which becomes **H8, a negative control against our own deflated-Sharpe bar.** Plus A36, T7. |
| 11 | [vnpy/vnpy](https://github.com/vnpy/vnpy) | 2026-09-03 | ⭐ **The most Phase-7-relevant repo here** — a decade-proven live-trading framework, and **MIT, so vendorable where NautilusTrader (LGPL) is not.** Its event bus is **145 lines**; I reproduced **three robustness gaps in it** (a handler exception silently kills the bus). **A32 + A33**; third independent repo to make notification a core primitive, which settles A11. |
| 10 | [microsoft/qlib](https://github.com/microsoft/qlib) | 2026-09-03 | ⭐⭐ **A different tier — the only genuine methodology reference here, and nothing needed debunking.** Point-in-time fundamentals as *syntax*, with **the best test in the log** (a value that changes on a cited real filing date). Exposed **two costing/realism gaps in our code (A29, A30)** and the pattern behind them (**A31**). Seeds **T1–T6**. |

---

# 1. AgentQuant — `OnePunchMonk/AgentQuant`

Reviewed 2026-09-03 at `425132f` (last commit 2026-08-28; first commit 2025-08-12).
~12,100 LOC Python · 54 test functions · MIT (declared in `pyproject.toml`; **no `LICENSE`
file in the tree** — if we ever vendored code we would want that fixed at source).

## 1.1 What it is

An LLM-driven research agent over **US ETFs** (SPY/QQQ/IWM/TLT/GLD + `^VIX`), daily bars
from yfinance, 5-year window. The loop is a genuine ReAct cycle:

```
analyze     → load bars, compute features, detect regime (VIX percentile + momentum)
hypothesize → Claude tool-use proposes parameter sets; falls back to grid, then random
backtest    → tournament all proposals, parallel, with costs + warmup guards
reflect     → score vs a Sharpe threshold; retry up to max_iterations
store       → SQLite memory, keyed by regime, recalled on the next run
```

It is **a parameter-search agent**, not an alpha-discovery agent. It picks
`fast_window`/`slow_window` for a fixed family of five textbook strategies (momentum,
mean-reversion, volatility, trend-following, breakout) from a canonical grid in
`config.yaml`. The LLM's entire job is choosing grid cells with a rationale attached.

That distinction matters for us: **our engine is the frozen weighted-confluence scorer,
and our leak is entry/regime selection, not parameter tuning.** Nothing in this repo
attacks our binding constraint. Its value to us is methodological, and it is real, but it
is confined to *how you decide whether a result is true* — not to *what to trade*.

## 1.2 Integrity audit — the headline results are not produced by this code

This is the most important section, and it is uncomfortable. The README's flagship claims
are fabricated or tautological. I verified each one against the source.

### Finding A — the "6-epoch harness evolution" runs identical code six times

`scripts/harness_evolution_6_epochs.py:216`:

```python
state = run_agent(
    ohlcv_data=self.ohlcv_data,
    strategy_type=self.strategy,
    asset=self.asset,
    trace=trace,
)
```

`harness_spec` — the dict carrying `use_tools`, `prompt_template`, `grid_adaptation`,
`ensemble` — **is never passed in.** And `run_agent` (`src/agent/agent_graph.py:415`)
takes no harness parameter at all:

```python
def run_agent(ohlcv_data, strategy_type="momentum", asset=None,
              max_iterations=None, trace=None) -> AgentState:
```

`harness_spec` is consumed only by `_describe_harness_changes()`, which prints the dict
back out as ✓/- bullets. So epochs 1–6 are the same agent, same config, same data. The
"+37.4% Sharpe across 6 epochs" cannot have been measured, because there is only one
harness.

Corollary: `.harness/v6_research.json`, described as "**the production harness**", is
never read by any runtime code. `HarnessConfig` is imported in exactly one place —
`harness_evolution_algo.py`, which *writes* genomes into it. Nothing loads it.

### Finding B — `results/harness_evolution_6epochs_results.json` is not this script's output

Four independent proofs:

1. **`generalization_gap` is mathematically impossible.** The code computes
   `gap = max(avg_sharpe - best_sharpe, 0.0)`. Since `best` is the maximum of the same
   population, `avg − best ≤ 0` always, so the code emits **`0.0` for every epoch**. The
   JSON stores `0.124` for v1 — which is exactly `|0.328 − 0.452|`, i.e. the sign was
   dropped by hand. The README's headline "generalization gap reduced 61%" is the decay
   of a quantity the code can only ever emit as zero. There is no train/validation/test
   split behind it.
2. **`claim_accuracy` is a hardcoded placeholder.** Code: `claim_accuracy=0.8,  #
   Placeholder`. JSON: `0.0, 0.75, 0.78, 0.81, 0.83, 0.86`.
3. **A string the code cannot emit.** JSON contains `"- Prompt: grid_search_default"`.
   `_describe_harness_changes` only ever appends `f"✓ Prompt tuned: {…}"`, and only when
   the template is *not* `grid_search_default`.
4. **Shape.** `timestamp` is `"2026-08-28T12:30:00"` — no microseconds, unlike
   `datetime.now().isoformat()`. And every single metric is perfectly monotone across six
   epochs: Sharpe up, std down (0.089→0.068→0.062→0.055→0.051), drawdown down, win-rate
   up, trades up, tool-calls 0→3→4→5→6→8. Real backtests do not do this.

### Finding C — the algorithm comparison never touches market data

The README's "Manual 0.621 vs GA 0.594 vs DE 0.571 vs Random 0.465" comes from
`scripts/benchmark_harness_evolution.py:81`, `_mock_fitness_function`:

```python
base_sharpe = 0.40
if genome.use_tools:                            base_sharpe += 0.10
if genome.use_web_search and genome.use_tools:  base_sharpe += 0.05
if genome.use_ensemble:                         base_sharpe += 0.08
base_sharpe -= abs(genome.tool_weight - 0.6) * 0.1
base_sharpe -= abs(genome.temperature - 0.15) * 0.1
base_sharpe += random.gauss(0, 0.02)
```

Its maximum is `0.40+0.10+0.05+0.08 = 0.63` less small penalties — which is where the
"0.621 production Sharpe" comes from. The docstring is honest ("Mock fitness function…
In production, this would run actual backtests"); the README is not.

The deeper problem is circularity: **"tools improve Sharpe" is an assumption written into
the fitness function (+0.10), then reported as a discovery.** The GA did not find that
tools help; it found the `+0.10` the author typed. This is the purest example of the
failure mode our constraint #8 names — an unchecked premise dressed as a measurement.

### Finding D — "86% falsifiable claim accuracy" never compares prediction to outcome

`src/agent/tools/evals.py:187`:

```python
if predicted and actual_sharpe > 0.2:
    accurate += 1
total += 1
```

The predicted value is not read — only its *existence* is tested. A forecast of "Sharpe
will be −0.5" that realises +0.3 scores as accurate. The idea (§1.4) is excellent; the
implementation measures nothing.

### Finding E — smaller defects

- **Inverted overfitting warning** (`evals.py:_generate_recommendation`): reports
  `"High overfitting detected (gap={…})"` inside `if metrics.get("generalization_gap", 0)
  < 0.3:` — it fires when the gap is *low*.
- **HMM is computed and discarded.** `regime.py::_try_hmm_regime` fits a 3-state
  `GaussianHMM` (100 iterations) on every regime call; the result is written to a
  `logger.debug` line and never reaches the label. DESIGN.md advertises "Optional HMM for
  probabilistic regime switching". This is the same class of defect as our own "MCE slices
  3/4 INERT" note — a feature that exists, runs, costs time, and changes nothing.
- **Badges are static.** `CI/CD-passing` and `tests-63 passed` are hardcoded shields.io
  images, not workflow badges. The real CI neuters its own type gate twice:
  `continue-on-error: true` *and* `mypy … || true`.
- **Catch-all swallow** in `runner.py`: `except (SignalGenerationError, Exception)` logs
  and continues, so a failed leg silently yields a smaller portfolio rather than an error.
- Inconsistent metric keys: per-asset dicts carry `sharpe`, the combined dict carries
  `sharpe_ratio`; `run_backtests_parallel` sorts on the latter.

## 1.3 What the repo's *real* data actually shows — and it is damning

Credit where it is due: **the author committed the disconfirming experiments and left them
in the tree.** They are far more valuable than the README. Recomputed from the CSVs:

### The agent loses to buy-and-hold, badly

`experiments/static_baseline_results.csv`:

| Strategy | Sharpe | Total return | Max DD |
|---|--:|--:|--:|
| **Buy & Hold SPY** | **0.896** | **+102.4%** | −24.5% |
| Golden Cross (50/200) | 0.598 | **+0.7%** | 0.0% |
| *Agent's claimed best harness* | *0.621* | — | — |

Five years of SPY returned 102%. The crossover strategy the agent converges on returned
**0.7%**. The celebrated 0.621 Sharpe is below buy-and-hold's 0.896 — the project's
headline achievement underperforms doing nothing, and the file proving it ships in the
repo.

### The agent converges to a constant

`experiments/walk_forward_results.csv`, 9 walk-forward windows (2021-02 → 2025-07):

- The LLM chose **`(50, 200)` in 8 of 9 windows**; the ninth was `(21, 252)`.
- Mean window Sharpe 1.49, compounded +48.2% — but that is the Sharpe of *a hardcoded
  golden cross*, not of an agent. Remove the LLM and the result is unchanged.

### The regime context — the entire thesis — was never reaching the model

In **8 of 9 windows** the stored LLM rationale says some variant of *"Given an unknown
market regime and no technical data available for SPY…"*. The `RegimeContext` that the
whole architecture exists to build was arriving empty. Every recorded walk-forward result
is therefore a *context-free* result, which is also why the parameters never move.

### The ablation says context makes it worse

`experiments/ablation_results.csv`:

| Arm | n | Mean Sharpe | Median | Std |
|---|--:|--:|--:|--:|
| **No Context** | 5 | **0.7105** | 0.7105 | 0.000 |
| With Context | 5 | 0.2766 | 0.1717 | 0.429 |

Adding regime context **halves** mean Sharpe and injects large variance. The repo's
central claim — regime-aware LLM strategy selection — is refuted by the repo's own
ablation file, which is committed, and which the README does not mention.

### The honest experiment has no published results

`experiments/walk_forward_context_with_costs.py` writes
`experiments/walk_forward_context_costs_results.csv`. **That file does not exist in the
tree.** The two committed walk-forwards are the cost-free ones. Given the strategy trades
a 50/200 crossover, costs would be small — but the one experiment designed to be
pessimistic is the one with no committed output.

For scale, `random_baseline_results.csv` (n=100): mean Sharpe **0.037**, std **0.415**. A
±0.4 std on single-draw Sharpe is the noise floor every claim above should have been
measured against, and none were.

## 1.4 What is genuinely good — and worth taking

Strip the agent narrative and there is a competently built research library underneath. I
ran its core suite: `pytest tests/test_metrics.py tests/test_backtest.py` → **10 passed**.
The engineering is real; only the story on top is not.

### ★ 1 — Moving-block bootstrap Sharpe (`src/backtest/metrics.py`)

The single best thing in the repo, and it is directly complementary to the deflated-Sharpe
bar we built on 2026-09-03.

```python
@staticmethod
def bootstrap_sharpe(returns, n=200, pct=5, block_size=20) -> float:
    """5th percentile Sharpe from a moving-block bootstrap … uses overlapping
    blocks of `block_size` consecutive daily returns (rather than an IID
    resample) so autocorrelation/regime structure in the return series is
    preserved — an IID resample destroys the serial correlation present in
    trend/momentum strategies and understates the true uncertainty."""
```

**Why this matters to us specifically.** Our `app/services/deflated_sharpe.py` is
*parametric*: PSR from skew/kurtosis, `E[max SR]` for N trials, MinTRL. Its own recorded
weakness is that **trials are assumed independent, so the DSR is optimistic**. A block
bootstrap is the non-parametric complement — it needs no independence or normality
assumption, and it prices in *path* uncertainty rather than *selection* uncertainty. The
two answer different questions and should both be reported:

- DSR: "given we tried N things, is this one better than luck?"
- Block-bootstrap p5: "if the same trades had arrived in a different order, how bad could
  this Sharpe plausibly have been?"

And it directly attacks a hole we already found by hand. The evidence-of-record block
exposed that market-regime's would-block set has a **trimmed mean of +₹200 against a
−₹302 raw mean — trimming reverses the sign.** We caught that with an ad-hoc trim. A
bootstrap p5 catches that class of instability *automatically, on every gate, with no
hand-chosen trimming rule*, because a distribution whose sign depends on one trade
produces a p5 far below its mean. **This is the highest-value harvest in the repo.**

Note their block size (20) is tuned to daily returns; ours would run over a **per-trade R
series**, so block size should be small (2–5) and justified by measured autocorrelation,
not copied.

### ★ 2 — VIX as a *percentile*, not an absolute threshold (`src/features/regime.py`)

```
Crisis: >85th pct | HighVol: >65th | MidVol: >35th | LowVol: <35th   (trailing 252d)
```

Our `app/signals/market_regime.py` uses an **absolute** `vix_threshold = Decimal(20)`, and
its own docstring records why it is stuck:

> *"our VIX history is too shallow (~weeks) to §8-validate, so it stays a shadow-only
> companion until `india_vix_daily` is backfilled"*

A percentile reframing partially dissolves that blocker. An absolute 20 is a **fitted
constant** that must be validated against history we do not have — and worse, it is
borrowed from US-VIX intuition while India VIX has a different level distribution. A
percentile is a **distribution-free statement about where we are in our own recent
regime**, self-calibrating as history accrues, with a documented degradation path (their
code falls back to the 50th percentile below 10 observations). It does not make the gate
promotable — that still needs the count and the DSR bar — but it converts a knob we cannot
justify into one we can.

Their `regime_confidence` is also worth noting: a **continuous** score
(`2·|pct/100 − 0.5|` blended with momentum strength) rather than a binary label. Our
reverted regime gate was binary (skip ADX 20–25) and got refuted; a graded confidence that
*sizes* rather than *blocks* is a different instrument and would not have had the same
failure mode.

### ★ 3 — Warmup enforcement that raises (`src/features/lookback_guard.py`)

```python
class WarmupEnforcer:
    def check(self, df, eval_start, min_window=None):
        n_before = (df.index < eval_start).sum()
        if n_before < required:
            raise InsufficientWarmupError(...)
```

Plus an `@enforce_lookback(min_periods=…)` decorator that validates a feature function's
own output. We enforce no-look-ahead by convention and review (`.claude/rules/`); this
makes it a **runtime invariant that fails loudly**. The decorator form is the neat part —
the guard lives on the feature function itself, so it cannot be forgotten at a call site.

### ★ 4 — Small correctness hygiene worth copying

- **`MAX_RATIO = 1e6` sentinel instead of `inf`** for Calmar/Sortino when drawdown ≈ 0, so
  degenerate ratios can flow into sorting, ranking and persistence without poisoning them
  with `inf`/`NaN`. We have exactly this hazard on record — the `RR≈228` tiny-SL artifacts
  in the Phase-6 attribution.
- **One metrics module, imported everywhere** ("import this instead of computing inline").
- **A docstring that corrects its own config.** `config.yaml` calls the parameter
  `market_impact_bps: # square-root market impact`; the implementing function says plainly
  it is *"a flat linear market impact … (not a true square-root impact model)"*. That is
  the doc-sync discipline our CLAUDE.md ritual is about, applied at function scope.

### ★ 5 — The hypothesis register (`src/research/alpha_store.py`)

`AlphaCandidate` persists `thesis · status(watch/…) · regime · generation_method ·
confidence · alpha_score` alongside the metrics, indexed on
`(regime, strategy_type, status, alpha_score)`, with `to_prompt_context()` feeding prior
results back into the next run.

The *schema* is the idea, not the code. We have the same need and currently meet it with
prose spread across `docs/PHASES.md`, CLAUDE.md bullets and memory files: **a register of
every gate/knob we are carrying, its pre-registered prediction, its bar, its count, and
its verdict.** Constraint #8 makes me the owner of that review calendar; right now the
calendar is prose, and prose does not have a `WHERE due_count <= current_count` query.

### ★ 6 — Roadmap ideas that map onto real gaps of ours

Ignoring the agent-flavoured ones, three are pointed:

- **Real-time Sharpe decay monitoring** — alert when live Sharpe drifts >20% from
  backtest. This is precisely the regime-gate failure: it went `⏳ NOT READY` and stayed
  so for 7 report days before anyone acted. We detect drift; we do not *alarm* on it.
- **False-hypothesis archival** — keep failed hypotheses and mine the failure patterns.
  We have two rich failures (regime gate, R:R≥1) recorded as prose lessons. The
  generalisable pattern across both — *"a partition that looks predictive is often a proxy
  for something else"* (market-regime → side; R:R<1 → wide stop) — was found by hand, twice.
- **Hypothesis aging / half-life** — measure how fast an edge decays. Directly relevant to
  the momentum ×1.5 retune still awaiting forward evidence.

## 1.5 What to refuse

| Reject | Why |
|---|---|
| **The harness-evolution framing** | Not measured (Finding A/B), and the benchmark is circular (C). Nothing to learn from a result that was typed rather than run. |
| **LLM-proposes-parameters as an alpha source** | Refuted by their own data: converged to a textbook constant in 8/9 windows, and the context that was supposed to differentiate it *halved* Sharpe. |
| **Their cost model** | `trades × (commission + slippage + flat_bps)` on daily bars. We are strictly ahead — 6.8.2 gives real half-spread + size-vs-top-of-book impact from live depth, on the finding that **82% of NSE books are wider than a flat 2bps**. Adopting theirs is a regression. |
| **Selecting on Sharpe across epochs** | Six rounds of selection with no deflation, on 5 years of one asset. This is the exact bias our DSR bar exists to price. |
| **The stack** (Streamlit / yfinance / vectorbt / SQLite) | Redundant against FastAPI + React + Postgres/Timescale + our Rust core. |
| **Vendoring any code** | MIT is permissive, but there is no `LICENSE` file, and every idea worth having is ~30 lines. Reimplement against our types (`Decimal`, tz-aware, `Numeric(12,4)`) and our tests. |

## 1.6 UI/UX findings

Stack: **Streamlit + Plotly**, single light theme, no design tokens. On every axis our
React 19 / Tailwind-token / 5-theme frontend is ahead. **And yet its Research Workspace
screen is better information design than anything we have for the same job**, so the
findings below are worth more than the stack comparison suggests.

Assessed from the seven committed screenshots (I looked at them, rather than inferring
from code) plus `src/app/streamlit_app.py` and `src/research/workspace.py`.

### ★ TAKE — the Research Workspace screen is the UI our shadow-gate evidence deserves

This is the finding. **We have seven shadow sidecars and every one of them is a separate
markdown file** (`entry-quality-shadow-<date>.md`, `circuit-gate-shadow-<date>.md`,
`sector-rs-shadow-<date>.md`, …) that a human must open one at a time and hold in their
head. AgentQuant renders the same class of information — every experiment, its evidence,
its verdict — as **one screen**. Concretely, in one viewport it gives:

| Element | What it does | Our equivalent |
|---|---|---|
| **Experiment Registry** table | every run, one row: `Run ID · Name · Mode · Strategy · Source · Sharpe · Return · MaxDD · Robustness · Validation` | 7 separate `.md` files |
| **4 KPI tiles** | `Tracked Runs 6 · Best Sharpe 1.490 · Best Robustness 0.711 · Validation Pass Rate 50.0%` | — |
| **"Current leader" callout** | one sentence: *"Current leader: No Context ablation with robustness 0.711. Use this as the anchor run when comparing new agent or swarm experiments."* | — |
| **Robustness Map** | scatter, Sharpe (y) × MaxDD (x), coloured by Mode | — |
| **Run Inspector** | pick a run → result sentence, research notes, per-check validation with reasons, artifacts | — |

**U1 — the registry as a screen, sorted by robustness rather than by the headline metric.**
`load_research_workspace` sorts by `robustness_score`, defined as `sharpe − max_drawdown`
(and `mean_sharpe − sharpe_std − max_drawdown` for walk-forward runs). The leaderboard's
default order is a **dispersion- and drawdown-penalised** score, not the number everyone
quotes. Sorting by the thing you actually care about instead of the thing that is easiest
to game is a one-line decision with a large behavioural effect.

**U2 — benchmarks are ROWS IN THE SAME TABLE, not a separate report.** `base-1 Buy and
Hold · 0.896 · 102.4%` sits two rows above `wf-momentum · 1.49 · 42.4%`. You physically
cannot read that table and miss that buy-and-hold won. This is **H2 rendered as UI**, and
it is strictly stronger than H2 as a report line: a benchmark in its own section gets
skipped, a benchmark in the same sort order does not. If we do H2, do it this way.

**U3 — the "current leader" callout.** One highlighted sentence naming the champion *and
telling you what to do with it* ("use this as the anchor run"). It converts a table into a
decision. Our readiness banners say READY/NOT READY per gate but never say *which gate is
currently the best candidate and what it should be compared against*.

**U4 — a `Validation` column whose value is the WORST of its checks.**

```python
@property
def validation_status(self) -> str:
    statuses = {check.status for check in self.validation_checks}
    if FAIL in statuses:  return FAIL
    if WARN in statuses:  return WARN
    return PASS
```

We already enforce this logic in the readiness guards ("no sidecar can print READY on bad
evidence"). What they add is **rendering it as a scannable column**, with the individual
checks and their *reasons* one click away in the inspector — not a bare tick but
*"**Pass** Ablation coverage: 5 trials available for this ablation arm."* A green tick
tells you the answer; the sentence tells you whether to believe it.

**U5 — honest WARN labelling with the reason.** The Buy-and-Hold row shows `warn`, and the
check explains why: *"Useful benchmark, but not a leakage-safe validation protocol."* The
warning is not "this is bad", it is "this is not the kind of evidence you think it is".
That is precisely the distinction our two reverted gates needed.

**U6 — the funnel KPI strip.** `Stored Alphas 11 · Accepted 2 · Watchlist 0 · Rejected 9`.
This is a **visible trials counter**, and it is exactly the `N` that `E[max SR]` needs in
our deflated-Sharpe bar. Right now that N is a number I choose by hand when computing the
bar (we assumed 20). A UI that counts *how many things we have tried* makes the multiple-
testing denominator an observed quantity instead of an assumption — which is the single
biggest soft spot in H1/our DSR work.

**U7 — rejected candidates stay on screen, with their damage.** Nine rejected rows are
rendered with their real numbers (Sharpe −0.857, −0.718, −0.864 …, `Score −1.352`), not
filtered out. The failure archive is a first-class UI citizen. Ours is prose in
`FIX_PLAN.md` and memory files.

**U8 — an `Artifacts` panel naming the file that produced the number**
(`experiments/ablation_results.csv`, in a code block). This is the discipline I proposed in
§1.6 — *every reported number must name the code path that produced it* — already built as
UI. Cheap for us: each sidecar banner could name its own generating service and query.

**U9 — provenance as a column.** `Method`: `alpha_memory` / `random` / `grid_search`, plus
collapsible *"Alpha memory used for this run"* / *"NLA memory used for this run"* panels.
Every row says how it was generated and what prior knowledge fed it. Our signals carry
`generation_method`-like provenance in the DB but never surface it.

**U10 — regime stamped as a banner on the run** (`📊 Market Regime: MidVol-Bull`) and as a
column on every stored candidate. The context a result was produced in travels with the
result. We persist `Signal.regime` at commit but do not show it as run context.

**U11 — the Robustness Map.** Sharpe × MaxDD scatter, colour = Mode (Ablation / Benchmark /
Agent research). A risk-return frontier of every experiment on one pair of axes, where the
benchmark cluster is visually adjacent to the candidate cluster. We have no equivalent
view; our `dataviz` skill would render a better version of it.

**U12 — the "Strategy Formula" card: the rules rendered as readable math.** A boxed card
stating what the strategy *actually does*, generated from its parameters:

```
Historical Volatility = σ(34)
Volatility Threshold   = 0.34

Position = +1 if Volatility < Threshold
Position =  0 if Volatility > Threshold

Parameters: {'window': 34, 'vol_threshold': 0.34}
Allocation Weights: GLD 0.32 · QQQ 0.08 · SPY 0.60
```

**This is the strongest single idea for our signal detail view.** Our confluence engine is
opaque at the point of decision: a signal shows "78%" and the user cannot see how it got
there. The SRTL loss is exactly this failure — one factor scoring 0.8 normalises to 80% and
clears the ≥70% gate, and *nothing on screen made that visible*. A card that renders the
actual arithmetic — each factor that scored, its weight, the `Σ(score×weight) / Σ(weight of
factors that scored)` division, and the resulting confidence — would have made the
single-factor entry obvious at a glance rather than a post-mortem finding. We now block it
with the diversity gate, but the *explanation surface* is still missing, and it generalises
to every gate verdict we show.

(Take the idea, reject the execution: theirs is a **matplotlib-rendered image**, so the
text is unselectable, unthemeable and fixed-size. Ours would be DOM.)

**U13 — the equity curve has no benchmark overlay.** `Portfolio Performance` plots one
line, annotated `Total Return: 87.39%`, with nothing to compare against — the chart-level
form of the same blindness as §1.3. Any equity/P&L curve we draw should carry the
benchmark as a second series by default, not as an option.

**U14 — small things worth stealing.** The headline number annotated *onto* the equity
chart (`Total Return: 87.39%` pinned in-plot) rather than beside it. A free-text "Add
tickers" input beside the multiselect, for symbols not in the preset universe. An explicit
`☐ Refresh market data now` checkbox instead of an automatic refetch — the user decides
when a network call happens. A one-line plain-English run summary in a status box
(*"Generated 1 proposals, 1 backtested successfully, stored 1 alpha candidates…"*).

### CONFIRMS — their defects are things our rules already forbid

The `dashboard*.png` screens are the weak end, and every failure maps to a rule we already
have. Useful as evidence those rules earn their keep, not as anything to copy.

| Their defect (screenshot) | Our rule that prevents it |
|---|---|
| `Performance Metrics` is a raw wide dataframe dump — 19+ columns (`GLD_total_return … SPY_max_drawd…`) running off-screen, clipped | `ui.md`: wide content scrolls in its own `overflow-x` container; long format over wide |
| `sharpe_ratio: None` rendered raw as "None" | `format.ts` for all numbers; explicit empty states |
| Unformatted floats — `0.8739`, `-0.1282`, `0.9464`, mixed 2/3/4 decimals, no units | `lib/format.ts` exclusively; no `toFixed` in features |
| Negative Sharpes in plain black — no profit/loss colour, no direction glyph | `--color-profit` / `--color-loss` + glyph, never colour alone |
| Red chips for neutral asset tags (red = loss in a trading UI) | token semantics — red is reserved for loss |
| Asset Allocation table rendered twice on one screen, beside an empty chart region | — (plain redundancy) |
| A pandas index column rendering as a meaningless `0` | — |
| The **same number in two formats on one screen** — allocation table shows `0.316`, the pie beside it shows `31.6%` | `format.ts` as the single formatting path |
| A **pie chart** for allocation | `dataviz` skill discourages pies; a bar/stacked bar reads better |
| Static matplotlib images for charts — no hover, no tooltip, rotated date labels | Lightweight Charts / Recharts, interactive |
| *"Optimization complete!"* success banner whose "optimized" params are **identical to the inputs** (`window 34, vol_threshold 0.34`) | a success message must state what changed, or say "no change" |
| `Validation` column clipped at the right edge of the registry | sticky/opaque headers + overflow handling |
| Single light theme, no tokens | 5 themes via `data-theme`, tokens only |

### REJECT

The Streamlit stack itself, the sidebar-drives-everything layout (a global filter rail is
wrong for our per-page workflows), and Plotly as a chart dependency — we are on
Lightweight Charts + Recharts and that is the better pairing for candles + dashboards.

## 1.7 The most useful thing in the repo is a warning

AgentQuant is a well-engineered library wearing a research narrative that its own
committed data contradicts. The mechanism is worth naming, because **we are running the
same risk from the same position**:

1. A metric was defined so it could not fail (`gap = max(avg − best, 0)` ≡ 0).
2. A placeholder was reported as a measurement (`claim_accuracy = 0.8  # Placeholder`).
3. A benchmark encoded its conclusion as an input (`+0.10 if use_tools`).
4. A validator checked that a claim *existed* rather than that it was *right*.
5. The disconfirming files stayed in the repo, unread, while the README told the other story.

We have already produced items 1 and 4 in our own house. The regime gate was promoted on
44 observations and refuted by 88. The R:R≥1 gate was promoted on an "identity needs no
evidence" argument and refuted in a week. And on 2026-09-02, **three agent reviews found
21 defects in work that had passed its own green suite twice — because the tests asserted
what was intended, not what the code did.** That is item 4 exactly: a check that confirms
a claim exists rather than that it holds.

The cheapest defence is the one this repo skipped: **every reported number must name the
code path that produced it, and any metric that cannot come out badly is not a metric.**
Worth adding to `.claude/rules/testing.md` as a one-liner.

---

# 2. QuantHarness — `Y-Research-SBU/QuantHarness`

Reviewed 2026-09-03 at `2e64c7b` (last commit 2026-08-18; first 2025-08-26). ~3,630 LOC
Python · MIT (real `LICENSE` file) · **an actual peer-reviewable artifact**:
[arXiv:2509.09995](https://arxiv.org/abs/2509.09995), Stony Brook + CMU + UBC + Yale +
Fudan. Formerly "QuantAgent".

This is a much more serious repo than #1. The benchmark is real, the baselines are strong,
and the authors report numbers that do not flatter them. My criticisms below are about
**statistical strength and fitness for our platform**, not integrity.

## 2.1 What it is

Four LLM agents in a LangGraph, over crypto/futures/indices at 1h and 4h:

```
START → Indicator Agent → Pattern Agent → Trend Agent → Decision Maker → END
```

- **Indicator** computes RSI / MACD / Stochastic / ROC / Williams %R (TA-Lib) and writes a
  prose report.
- **Pattern** and **Trend** *render candlestick charts to PNG*, base64 them into the state,
  and have a **vision** LLM read the picture — trendline channels, double bottoms,
  support/resistance. ("Our model requires an LLM that can take images as input.")
- **Decision** synthesises the three prose reports into `LONG` or `SHORT` + JSON.

The whole system is **one stateless invocation over the last 45 candles**. There is no
memory, no portfolio, no position sizing, no capital, no stop computation — I grepped for
all of them and they do not exist. It answers "which way next?", nothing else.

## 2.2 The benchmark — the honest read

`benchmark/` ships **1,600 CSVs** (100 windows × 8 assets × 2 timeframes, 100 candles
each). The headline table (`assets/table1.png`) reports directional accuracy vs three
baselines. The `.3`/`.7` decimals put n at **300 per cell** (100 windows × 3 repeats).

Recomputing significance — a two-proportion test, which the paper does not report:

| asset | ours | naive base | z | **logistic regression** | **z vs LR** | XGBoost | beats LR? |
|---|--:|--:|--:|--:|--:|--:|:--|
| BTC | 50.7 | 45.0 | 1.40 | 46.0 | 1.15 | 45.3 | no |
| CL | 55.0 | 41.0 | 3.43 | 54.3 | 0.17 | 40.0 | no |
| DJI | 52.3 | 47.0 | 1.30 | 52.0 | 0.07 | 47.3 | no |
| ES | 55.0 | 51.0 | 0.98 | 43.0 | 2.94 | 52.0 | **YES** |
| VIX | 54.7 | 46.3 | 2.06 | 48.7 | 1.47 | 53.3 | no |
| NQ | 55.3 | 43.7 | 2.84 | 48.7 | 1.62 | 47.3 | no |
| QQQ | 59.7 | 47.3 | 3.04 | 56.0 | 0.91 | 52.7 | no |
| SPX | 63.7 | 47.3 | 4.02 | 59.7 | 0.98 | 60.0 | no |

**Significant vs the naive baseline: 5 of 8. Significant vs logistic regression: 1 of 8** —
and that one (ES) is carried by LR scoring an anomalous 43.0%, *below* chance. Mean
accuracy 55.8% vs LR's 51.0%, a +4.8pp edge that is inside the noise band on almost every
individual asset (95% CI on a single cell is ±5.7pp).

So the defensible claim is: **a four-agent GPT-4o vision pipeline roughly matches logistic
regression on the same features.** That is not nothing — matching LR while producing a
human-readable rationale has real value — but it is a much smaller claim than the table's
bolding implies. Three further caveats:

1. **Directional accuracy is not profitability.** No costs, no slippage, no spread. The
   architecture forces a trade every window (below), so at 1h resolution the cost drag
   would be severe, and a 55% hit rate with symmetric payoffs does not survive it. Our own
   book is the cautionary case: **37.5% win rate, +1.14R/−1.17R, −0.303R expectancy** —
   hit rate alone told us nothing.
2. **BTC — the flagship asset, the one in every chart — is the weakest result** (50.7%,
   z=1.40, not significant). A coin flip.
3. **Multiple comparisons.** 8 assets × 2 timeframes × 4 methods, no correction. Exactly
   what our deflated-Sharpe bar exists to price.

**Reproducibility gap:** the 1,600 benchmark CSVs ship, but **no evaluation script does** —
`grep -rln benchmark --include=*.py` returns nothing. The numbers live in the paper and in
PNGs; nothing in the repo regenerates them.

**And the look-ahead guard is a commented-out line.** `web_interface.py:311-317`:

```python
# if len(df) > 49:
#     df_slice = df.tail(49).iloc[:-3]     # holdout: drop the 3 candles being predicted
# else:
#     df_slice = df.tail(45)

df_slice = df.tail(45)                      # ← active: no holdout
```

For live use `tail(45)` is correct (the future does not exist yet). But the task is
"predict the next 3 candlesticks", the holdout variant that drops exactly 3 is commented
out directly above it, and **there is no separate evaluation path** — so benchmark mode was
selected by hand-editing the line that also serves live requests. I cannot prove the
published numbers used look-ahead, and I am not claiming they did. I am claiming this:
**the only visible holdout mechanism in the repo is a comment, in shared code, with no
flag and no test.** Our constraint #3 makes this structural for exactly this reason.

## 2.3 The architectural disagreement that matters most

**`HOLD is prohibited`** — the decision prompt, verbatim:

> *"Your task is to issue an **immediate execution order**: **LONG** or **SHORT**.
> ⚠️ HOLD is prohibited due to HFT constraints."*

This is the deepest incompatibility with our platform, and it is worth stating plainly
because it is the thing to *learn from*, not copy. Our entire architecture exists to be
able to say **no**: the ≥70% confluence gate, the reject-don't-clamp SL rule, the
eligibility overlays. Our diagnosis is that **the binding constraint on profit is entry
selection** — 44 defect trades cost −₹19,649 while 55 clean ones made +₹5,256. A system
that must take a position on every candle has, by construction, zero selectivity. It is
optimising the one variable we have evidence is *not* the lever.

Second: **the risk-reward ratio is invented, not computed.**

> *"Suggest a reasonable **risk-reward ratio** between **1.2 and 1.8**"*

The LLM is told to emit a number in a range — no stop, no target, no price levels. It is a
plausible-sounding string, not a measurement. We have just been through this: our R:R≥1
gate was reverted precisely because R:R turned out to be a **proxy for stop width** rather
than the quantity we thought. Theirs is worse — it is not a proxy for anything, because
nothing computed it.

Third: **the "multi-agent" graph is strictly sequential.** `graph_setup.py` wires
Indicator → Pattern → Trend as a chain, but the three agents are independent — each reads
the same `kline_data` and none consumes another's output. They could fan out and join.
As built, that is 3 serial LLM round-trips (two of them vision calls) where 1 wall-clock
round-trip would do. For a system whose selling point is *high-frequency*, that is a
notable miss.

## 2.4 Architecture findings — what to take

**A1 — two-tier model routing.** `agent_llm_model` (cheap: `gpt-4o-mini`) for leaf agents,
`graph_llm_model` (strong: `gpt-4o`) for synthesis and graph logic, each with its own
provider and temperature. Cheap model does the mechanical work; the expensive one only
adjudicates. We do not have an LLM in the money path and should not, but we *will* have one
in the research loop (daily analysis, the review calendar) — and the same split applies:
a cheap pass to extract, an expensive pass to judge.

**A2 — provider abstraction with per-provider default mapping.** `apply_provider_defaults()`
swaps the whole model set when the provider changes, so switching OpenAI → Anthropic →
Qwen → MiniMax → Gemini does not leave a stale model id behind. Community-contributed
providers landed as small PRs against that seam, which is the proof it is the right seam.

**A3 — a credential-status endpoint. This is the one with a live use for us today.**
`/api/get-api-key-status` + `validate_api_key()` make credential health a *first-class,
queryable state* rather than something you discover from a failed request. **Our Kite
access token dies at ~06:00 IST every single day** — the domain rules already call this "a
normal lifecycle event, not an error loop". A `GET /api/v1/broker/token-status` returning
`{valid, expires_at, hours_remaining}`, surfaced as a topbar banner, converts a daily
silent breakage into a visible one. Cheap, and it targets a failure we *know* recurs.

**A4 — constraint pre-validation, not error-after-submit.**
`get_timeframe_date_limits(timeframe)` and `validate_date_range()` tell the client what is
legal *before* it asks (1m data only goes back so far, etc.). We have the same shape of
constraint everywhere — the NSE calendar, per-classification validity (scalp 30min /
intraday 3:15 / swing 5 trading days / positional 30), market hours, the
`allow_offmarket_entry` rejection. Our display-path work already found the cost of *not*
doing this: **41 of 204 rows offered a Buy that could only 409**, and separately every row
read clear in the evening while the order path 422'd on off-market. Pushing the constraint
to a queryable endpoint is the generalisation of the fix we already shipped once.

**A5 — a self-documenting state schema.** Every field of the graph state is
`Annotated[type, "what this is"]`:

```python
pattern_image: Annotated[str, "Base64-encoded K-line chart for pattern recognition agent use"]
indicator_report: Annotated[str, "Final indicator agent summary report used by downstream agents"]
```

The schema carries its own contract, readable by both humans and tooling. Worth copying for
our sidecar/report payloads, where field meaning currently lives in a docstring far from the
type. (Their execution has a smell to copy *around*: the graph-wide state is still called
`IndicatorAgentState` — named after the first agent that used it.)

## 2.5 UI/UX findings

Flask + Jinja, hand-written HTML/CSS/JS (`index.html` 1353 · `demo_new.html` 1996 ·
`output.html` 754). Single-shot tool: pick asset → timeframe → date range → run → read.

**TAKE**

**U15 — per-agent result tabs, with the evidence named in plain language.** Results are
split into a tab per analyst (Indicator / Pattern / Trend / Decision), and the decision
card names its evidence rather than scoring it: *"Justification: MACD Bullish Crossover.
Rising Rate of Change. Double Bottom Pattern + Steep Breakout Resist Line."* Plus an
explicit **`forecast_horizon`** field — the prediction states what period it is about.

This is the **human-readable complement to U10**. U10 was the arithmetic (which factors
scored, their weights, the normalising division). This is the sentence. Our signal detail
view should carry both: the arithmetic proves the confidence is honest, the named-evidence
line makes it legible. Together they are what would have made SRTL's single-factor entry
obvious on screen — "RSI_DIVERGENCE" alone in an evidence list reads as thin instantly, in
a way that "78%" never does.

**CONFIRMS** — their notification and IA layers are behind ours, usefully so:

| Their approach | Ours |
|---|---|
| **20 raw `alert()` calls**, no toast/snackbar system — blocking, unstyleable, unthemeable | `AlertBell` + themed surfaces |
| `print()` for request logging inside Flask handlers | structured logging with context |
| API key pasted into a web form as the primary path | `.env` + hooks protecting it |
| No empty/error/loading states beyond a spinner and `Loading` | required per page by `.claude/rules/ui.md` |

**The absence worth naming: there is no portfolio, no position, no P&L, no risk layer at
all.** For a paper titled *"…for High-Frequency Trading"*, the system stops at "which
direction?" and never models what you own, how much, or what it cost. This is the reverse
of our situation — we have paper positions, sizing, heat, exits, a circuit breaker and a
30-day clock, and what we lack is the research surface (U1). Nothing to harvest here; it is
a useful reminder that **the published-research end of this field routinely stops exactly
where the hard part starts.**

## 2.6 What to refuse

| Reject | Why |
|---|---|
| **The forced-trade design** (`HOLD is prohibited`) | Inverts our central thesis. Selectivity *is* the edge we are trying to find. |
| **LLM-emitted risk-reward** | A number in a prompt-specified range with no stop or target behind it. |
| **Natural-language weighting** as the scoring mechanism | The decision prompt does confluence in prose ("give higher weight to…", "prioritise when all three align"). Non-deterministic, unauditable, un-backtestable, and it cannot be frozen for parity. Our numeric engine is strictly better here — and this is a case where **we are ahead of a published paper**. |
| Vision-LLM chart reading as a signal source | Interesting research; unreproducible, slow, and impossible to §8-validate. |
| The stack (Flask/Jinja/TA-Lib/yfinance) | Redundant against ours. |
| Sequential fan-out | If we ever build an agent graph, independent analysts run in parallel. |

---

# 3. AI Quant Agents — `demandai/ai-quant-agents`

Reviewed 2026-09-03 at `5aba01b` — **a single commit, 2026-03-24**. Apache 2.0.
**295 LOC total, of which `client.py` is 236.**

## 3.1 What it is — and what it is not

**It is not a quant system. It is a marketing SDK for a closed commercial service.**

There are no indicators, no backtest, no data layer, no evaluation, no strategy — none of
it is here. The package is an HTTP + WebSocket client that POSTs a ticker to
`https://dream.hmyk.ai/api/trigger_analysis` and streams back messages. The "12 AI agents"
run server-side, closed-source, behind a **PRO ONLY** gate.

The README is candid about the lineage, and this is the most useful line in the repo:

> *"Built on [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache 2.0)
> by Tauric Research."*

**So the artifact actually worth reviewing is upstream TradingAgents, not this wrapper.**
Recommend adding it to the queue of repos to look at.

(Minor provenance smell: the GitHub org is `demandai`, but `pyproject.toml` points
`Repository` at `github.com/nicekate/ai-quant-agents`.)

## 3.2 Code review — four defects in 236 lines

Small surface, but the defects are the *interesting kind* — they repeat patterns this
document has already named twice.

**D1 — `risk_approved` can never be False.** The README markets a "Risk Manager with
**VETO POWER** — can block any trade". In the client:

```python
risk_approved = "risk" not in decision.lower()
```

`decision` is only ever `"BUY"`, `"HOLD"` or `"SELL"`. The substring `"risk"` cannot
appear. **The safety flag is hardcoded true.** This is the same species as AgentQuant's
`generalization_gap` that could only return zero — *a metric that cannot come out badly* —
except here it is the risk check, which is worse. The veto the product is sold on is not
representable in the result object.

**D2 — the README's example output is not reachable from the code.** It advertises:

```json
"suggested_action": {"entry": "$142-145", "stop_loss": "$132",
                     "target": "$165", "position_size": "2-3% of portfolio"}
```

The code sets `suggested_action={}` unconditionally and never touches it again. Those are
the only four fields a trader would actually act on, and they are decorative. Mechanism #2
from §1.7 — a placeholder presented as a measurement.

**D3 — the decision is parsed by substring match on free LLM text.**

```python
text = msg.message.upper()
if "BUY" in text:    decision = "BUY"
elif "SELL" in text: decision = "SELL"
```

*"I would not BUY this here"* → **BUY**. And because `BUY` is tested first, any message
containing both words returns BUY. There is no structured output contract with the server.

**D4 — the stream has no correlation id, so it can return someone else's analysis.**
`stream()` POSTs the trigger, then connects to a **global** socket —
`wss://dream.hmyk.ai/ws/live` — and consumes every `agent_speak` message until the first
`analysis_complete`. Nothing filters by ticker or request id. On a shared demo server with
concurrent users, `client.analyze("NVDA")` can return a stranger's TSLA debate, labelled
NVDA, because the client stamps the ticker on locally. Two smaller bugs ride along: the
trigger fires *before* the socket connects, so early messages are lost; and
`while True: ws.recv()` has no timeout or reconnect, so a missing `analysis_complete`
hangs the caller forever.

Also: `key_reasons` are harvested only from speakers whose name contains `bull`/`aggressive`
and `risk_warnings` only from `bear`/`risk`, each truncated at 200 chars mid-word. So
`key_reasons` is **structurally the bull case regardless of the verdict** — a SELL still
lists bullish arguments as its reasons.

**And `confidence` is not a confidence.** `max(consensus.values()) / total` is the
plurality share of agent votes: 8 of 12 agreeing gives 0.67. These agents share a model
family and a prompt context, so they are not independent estimators — their agreement is
correlated by construction and is not evidence about the world. Calling the modal vote
share "confidence" is a category error, and a familiar one: it is the same shape as our own
confluence normalisation, where a share of *scoring* weight reads as a probability.

## 3.3 Architecture findings

**A9 — a progress envelope for long-running jobs. The one genuinely good idea here.**
Every streamed message carries:

```python
speaker · phase · progress · total_steps · action_type · timestamp · current_consensus
```

That is a well-designed protocol for a job that takes minutes: the client renders a phase
label, a progress bar and a running tally **without knowing anything about the pipeline**.

We have several long jobs with no progress protocol at all — `make analysis` (7 sidecars +
report sections), backtests, the walk-forward replay that takes ~8 minutes, EOD ingestion
with its ≤21-day self-heal. Today these are opaque until they finish or a log line appears.
A `{phase, step, total_steps, message}` envelope would serve all of them, and it is
independent of any LLM or agent framing.

**A10 — running consensus emitted mid-flight** (`current_consensus` on every message), so
the tally is visible while the job is still going rather than only at the end. Pairs with
A9; same idea applied to the *result* rather than the *progress*.

**Confirms, not take — the phased pipeline with an explicit veto stage.** Intelligence (4
analysts) → Debate (bull/bear/3 debaters) → Trading (proposes) → Risk (**veto**) → Judge.
Separating *propose* from *approve* is sound, and we already do it: the confluence engine
proposes, `risk_guards` / `eligibility.py` / the circuit breaker can reject. Worth noting
only because their framing makes the veto a named role, which is a clearer way to describe
what our overlay pattern already is.

## 3.4 UI/UX findings

The product is a "cyberpunk trading room": an AI-generated illustration of a trading floor
with agent names floating over it, occupying ~70% of the viewport and carrying **zero
data**. That part is theatre. The right-hand rail, though, has three ideas worth taking.

**U16 — a phase/participant stage-tracker strip.** A single row of chips grouped by stage:

```
INTELLIGENCE [NA][SA][FA][MA]   DEBATE [BUL][BER]   RISK [AGG][NEU][CON]   DECISION [R-M][R-J][TRD]
```

Phases, the participants inside each phase, and which have completed — in about 40px of
vertical space. This is the visual form of A9 and the best compact representation of a
multi-stage pipeline I have seen across these three repos. Directly applicable to a
`make analysis` run and to backtest/walk-forward progress.

**U17 — the consensus rendered as one stacked bar, not three numbers.**
`BUY 0% | HOLD 33% | SELL 67%` as a single horizontal bar with the verdict in large type
beside it. **This is the right shape for our confidence display.** A confluence score of
78% is currently a scalar; the *distribution* behind it — which factors voted, how strongly,
which abstained — is what actually tells you whether to trust it. Pair with U10 (the
arithmetic) and U15 (the named evidence) and the signal detail view finally explains itself.
Caveat to fix in ours: their bar renders a visible segment for a 0% category; zero-value
segments must collapse.

**U18 — a streaming log with per-entry phase tags and explicit expansion.** Each entry is
prefixed `[Layer 1: INTELLIGENCE]`, truncated, and followed by `View Full Report →`, with a
live `> reasoning...` cursor while a step is in flight. Summary inline, detail on demand,
progress visible. Good pattern for our sidecar output, which is currently all-or-nothing
markdown.

Also present: a compact **HISTORY rail** (ticker · verdict chip · timestamp, newest first)
and a top market-ticker strip using glyph + colour — the latter is a *confirms*, we already
require it.

**CONFIRMS**

| Their approach | Our rule |
|---|---|
| ~70% of the viewport is a decorative illustration with no data | information density; every surface earns its space |
| The primary input is disabled behind a **PRO ONLY** badge, so the demo cannot be driven | — |
| A 0% category still renders a visible bar segment | zero/empty states must be explicit, not misleading |
| "RISK MANAGER — VETO ARMED" is text baked into a static image, not a state indicator | state must come from state, not decoration |

## 3.5 Verdict

**Adopt no code — there is almost none, and what exists has a hardcoded-true risk flag, a
substring-matched decision, and a stream that can hand you another user's analysis.** Take
three UI ideas and one protocol idea, none of which depend on this repo existing.

The lasting value is as a third data point for §"What both repos independently confirm":
this is now the **third repo in a row** whose README advertises numbers or fields its own
code cannot produce.

---

# 4. quant-agent — `yebof/quant-agent`

Reviewed 2026-09-03 at `6fc3cf1` (first commit 2026-05-16, last 2026-07-16). MIT.
**~63,000 LOC · 1,344 test functions.** Solo author, US equities, live-capable via Alpaca.

**This is the most relevant repo of the four by a wide margin, and the best-engineered.**
It is the same *shape* of thing we are building — a personal, scheduled, risk-gated trading
agent with a real broker, a portfolio, notifications and a daily reflection loop — so the
comparison is direct rather than analogical. In several specific places it is ahead of us.

## 4.1 What it is

Six sessions per trading day on an OS-level timer (systemd user timers on Linux, launchd on
macOS), each ET-window-gated by a bash wrapper:

```
08:00-09:15  earnings_preprocess   only session that runs the earnings LLM; others read cache
09:30-12:00  morning               full team → PM → risk → execute
09:30-16:00  intra_check           every 30-min tick, NO LLM, ~5s: daily-loss breaker only
13:00-14:30  midday                sell-only, Position Reviewer "patient"
15:30-16:00  close                 sell-only, Position Reviewer "act-on-trigger"
20:00-22:00  evening               grade the day, set tomorrow's bias
```

Eight daily LLM agents (tech / news / macro / earnings / portfolio manager / risk manager /
position reviewer / evening) plus a quarterly **meta-reflector** that edits six of the eight
agents' prompt files under a 10-invariant safety system. Prompts live as versioned markdown
in `config/prompts/`.

## 4.2 The claims are true — the first repo in this log where that holds

I ran the same audit that caught the first three, and it came back clean:

| Claim | Verified |
|---|---|
| "R/R computed in Python, not trusted to the LLM" | **True.** `risk_reward` is a real `@computed_field` over entry/stop/target geometry, returning `None` on malformed geometry *"so PM / RM won't render a fake ratio"*. |
| "Schema-enforced reasoning chains — the LLM cannot skip steps" | **True.** 64 occurrences of `min_length=1` in `models.py`; a missing CoT step is a `ValidationError`, not a silent pass. |
| "874 tests" | **Understated.** 1,344 test functions actually present — the README is stale in the *conservative* direction. |
| Performance claims | **There are none.** No Sharpe, no returns, no "beats the market", anywhere in README or CLAUDE.md. |

That last row is the striking one. **This repo makes no performance claim at all** — the
only thing resembling one is a disclaimer stating that no backtest, simulation, paper or
live result in the repository predicts anything. After three repos whose headline numbers
their own code could not produce, one that simply declines to claim is a genuine
counterexample, and I have revised the synthesis section accordingly.

## 4.3 The gap, stated plainly: nothing validates any of it

There is **no backtest, no walk-forward, no evaluation harness** in the repository — I
searched. The author says so himself, in CLAUDE.md:

> *"prompt 改动这里没法回测,所以容易'听起来对就上'"* — prompt changes cannot be backtested
> here, so it is easy to ship something merely because it sounds right.

His mitigation is a **decision-replay harness** (`scripts/replay_decision.py`): feed a real
historical `input_message` from `agent_logs` back through the *current* prompt and model,
and structurally diff the old and new decisions — turning *"I think this version is better"*
into *"here is exactly how it changed decisions on N real inputs."* That is a good tool, and
he is equally clear about its ceiling:

> *"outcome-aware 评分（对比次日/5日真实走势判好坏）是它之上的下一层,**尚未建**"* —
> outcome-aware scoring, judging a change against the actual next-day/5-day move, is the
> layer above this, **not yet built**.

So the harness answers *what changed*, never *whether it was better*.

**This is the symmetric trade with our platform, and it is worth being precise about it:**

| | quant-agent | ours |
|---|---|---|
| Production/operational discipline | **ahead of us** — see §4.4 | catching up |
| Decision engine | LLM, non-deterministic, un-backtestable by construction | frozen numeric confluence, parity-tested, replayable |
| Validation apparatus | **none** | §8 walk-forward, golden fixtures, shadow overlays, outcome tracking, deflated-Sharpe bar |
| Evidence of edge | none claimed, none shown | negative so far (−0.303R) — but *measured* |

He has built an excellent machine with no instrument to tell him whether it works. We have
a mediocre-performing machine with good instruments telling us so. **Ours is the better
position to be in**, and it is worth saying that explicitly, because §4.4 is otherwise a
long list of things he does better.

One more honest note: `git log` shows 14 of 51 commits are fixes, including *"full-codebase
audit — 25 defects (1 critical: stops expired at the close, positions naked overnight)"* and
*"audit-r2: 57 verified defects"*. That is not sloppiness — it is a solo developer running
adversarial audits and reporting the count honestly, which is exactly our own practice
(three agent reviews, 21 defects, 2026-09-02). But 82 defects across two audits of a
live-capable trading system is also a fair measure of how much complexity an LLM-in-the-loop
design buys you.

## 4.4 Architecture findings — the richest section in this document

**★ A11 — a session notifier with a noise policy. The single most actionable item across
all four repos.**

Every session pushes a structured status message to Telegram. The design principles are all
correct, and each one is a decision we would otherwise have to discover:

- **Silence is the default for routine success.** The 14 daily `intra_check` ticks are
  suppressed; only an emergency action surfaces. Pre-market `nothing_new` earnings polls are
  suppressed. Quarterly meta is silent on the ~89 days it does not run.
- **Failures are classified by whether a human can act on them.** `fetch_error` (SEC
  transient) is suppressed; `analysis_error` notifies, because that one is a real bug.
- **Any exception always notifies, bypassing the whole noise policy** — with the exception
  type and a truncated message.
- **The artifact is the confirmation.** For the daily P&L export, the CSV document *is* the
  push; a separate "sent" status message would be pure noise. Only `error`/`skipped` speak.
- **The notifier can never break trading.** Missing credentials → silent no-op, callers do
  not branch. HTTP failures to Telegram are swallowed: *"a Telegram outage must never affect
  trading."*
- **It is wired into `main.py`'s `finally` block**, so even a `SystemExit` from a wrapper
  kill still produces a push before the process dies.
- Each message carries the **per-session LLM cost**, looked up by `run_id` — and *omits the
  line entirely* if the data is missing rather than rendering `$?.??`.

**Why this is our highest-value architecture item.** We currently have *at least two
standing manual daily checks that exist only because we have no notifier*:

1. **CAS capture** — `make worker` must be up 15:15–15:33 IST daily, and **a missed window
   cannot be back-filled**. The current protocol is "check the row count each morning."
2. **Provisional health** — the forward watch has no scheduler; the protocol is "run
   `scripts/provisional_health.py --days 7` yourself each session."

Both are unrecoverable-or-degrading failures whose detection depends on a human remembering.
That is precisely the job of a notifier with an exception-always-notifies rule. Add the
daily `make analysis` completion, the EOD ingestion self-heal, and the Kite token expiry
(A3) and there is a real surface here.

**A12 — invariants documented with the incident that produced them.** Their CLAUDE.md has a
section titled *"不要违反的约定（这些不看代码就看不出，违反会出事）"* — "conventions not to
violate (you cannot see these from the code, and violating them causes incidents)" — opening
with:

> *"这一节是 CLAUDE.md 的主要价值——约定背后的'为什么'在代码里不写死，所以必须记在这里。"*
> This section is the main value of CLAUDE.md: the *why* behind a convention is not encoded
> in the code, so it has to be recorded here.

**That is our doc-sync ritual's thesis, stated more sharply than we state it.** And every
entry carries a date and an incident:

- SELL `allocation_pct`: `100` = all, `1–99` = partial, `0` = skip — *"stop using 0 to mean
  sell-all"* — and it names **both** places that must honour it, because a filter once
  treated `alloc=0` as a full sell and pre-deducted phantom cash, letting BUYs quietly borrow
  margin (2026-04-19). **Same class as our `size_for_fill` wrong-side bug.**
- Every SELL path must call `cancel_protective_stops()` first, or Alpaca marks the shares
  `held_for_orders` and rejects the sell (2026-04-25, AMZN).
- Daily P&L is `broker.equity − broker.last_equity`, and **the breaker baseline is always
  `last_equity`, never last night's DB snapshot.**
- Inverse ETFs use a **signed** multiplier for net exposure and an **absolute** one for
  per-position and sector caps — two multipliers because they answer two different questions.
- `MARGIN_DEFICIT_FLOOR_USD` is one constant imported in three places: *"do not rebuild a
  private constant in any of them."*

**A13 — a safety mechanism that bypasses all coordination machinery, pinned by a named
test.** `intra_check` (the daily-loss circuit breaker) is explicitly exempt from both the
last-run dedup guard and the cross-session mutex, with the reasoning recorded:

> If the breaker is blocked while a long morning session runs, flash-crash protection goes
> silent — *"the entire reason the breaker exists is negated."* When changing lock logic,
> **always first confirm `intra_check` still passes through** — test:
> `test_run_if_et_window_intra_check_bypasses_session_lock`.

This is the lesson our own bug-hunter round produced — *a documented safety net is worth
nothing without a test that fails when it lapses* (our `unassessed` tripwire was imaginary;
3 of 8 modes passed). They got there first and pinned it by name. **Our circuit breaker
deserves the same treatment**: a test asserting it cannot be suppressed by any scheduling,
locking or mode change.

**A14 — timeouts derived from measurement, and layered.** The 20-minute wrapper timeout is
justified in writing: morning's normal path is tech_analyst 3 chunks × 140–180s + parallel
news/macro + PM 50s + RM + execution, reaching 10–11 minutes on slow OpenAI days (measured
2026-04-24); 600s had killed three consecutive ticks. 20 min is *"1.5–2× worst observed"*.
Three layers: 30s HTTP timeout injected into the Alpaca SDK, `timeout --kill-after=30 1200`
around the wrapper, and `TimeoutStartSec=1500` in the systemd unit — all added after a
**13-hour hang** (2026-04-17). Compare our own `make check` stall at
`test_walkforward_matches_golden`, which we diagnosed as resource starvation but never put a
bound on.

**A15 — window width ≥ scheduler tick interval.** A 25-minute close window against a 30-min
timer missed the close entirely on two consecutive days (2026-04-23/24), because tick phase
can land outside a window narrower than the interval. Non-obvious, and directly applicable:
our CAS capture window is **15:15–15:33, eighteen minutes**, and its miss is unrecoverable.
If anything ever schedules it on a coarser tick, it silently never fires.

**A16 — the protection lifecycle as a state machine with a durable repair queue.** Every
SELL path must do: cancel protective stops → submit → verify broker acceptance → wait for
terminal status → **reprotect on the actual filled quantity, not the submitted one**. Five
failure branches are enumerated, each tagged with the PR and review round that found it
(PR I/J/K/O/R/S; codex r4/r5/r7/r9), including: accepted-then-expired limits, a 15s
non-terminal timeout that must force-cancel before finalising to avoid racing the broker,
and partial restores that persist **only the failed specs** so they do not duplicate stops
already live at the broker. Anything unrepairable writes to a `pending_protection_restores`
table drained at the next session entry, *"so a crash mid-flight cannot leave a position
naked overnight."*

We are pre-live, so this is not actionable today — but it is **the best available map of
what Phase 7's BrokerAdapter and order FSM actually have to handle**, written by someone who
found each branch the hard way. Worth reading in full before that phase starts.

**A17 — cross-provider LLM failover with careful semantics.** On a non-retryable primary
failure (quota, dead key, 402), one single-shot fallback to a different provider — no
retries, to avoid eating the session window. Truncation deliberately does *not* trigger
failover. No-op when the primary already is the fallback provider. Model prices are **pinned**
in a cost table so a cache refresh cannot silently overwrite them with stale values.

## 4.5 What we do better

Stated for balance, because §4.4 is long:

- **Validation.** They have none; we have walk-forward, golden parity fixtures, shadow-mode
  overlays, outcome tracking and a deflated-Sharpe bar.
- **A deterministic, freezable engine.** Their decisions cannot be reproduced; ours can, to
  the integer.
- **Money types.** They are on Python floats for prices throughout; we are `Decimal` /
  `Numeric(12,4)` / `i64·1e-4` end to end.
- **A real UI.** They have none at all — see below.
- **Self-modifying prompts on a live trading system** is a risk we would not take. Their
  guardrails are genuinely thoughtful (append-only, FIFO cap, Jaccard dedup, prohibited-word
  regex, schema-protected agents that the reflector *cannot* name, git auto-commit so
  `git revert <sha>` rolls back a quarter). But a system that rewrites its own decision
  rules quarterly with **no out-of-sample check** is changing behaviour on argument alone —
  the exact failure our constraint #8 exists to prevent, at a larger scale.

## 4.6 UI/UX findings

**There is no UI. Telegram is the entire interface**, and that is itself the finding.

For a single-operator system this is a defensible, even elegant, choice: the interface is a
push feed you already have on your phone, with a CSV document for the numbers. It means zero
frontend surface to maintain and no dashboard that must be visited to be useful — the
information comes to you. Against that: nothing is explorable, there is no way to ask a
question the notifier was not written to answer, and every new view is a code change.

We are building the opposite (19 pages of React), and both can be right — but the lesson
transfers in one direction: **a dashboard nobody opens is worth less than a push nobody has
to remember to check.** Our seven markdown sidecars are currently in the "must remember to
open" category. U1 makes them explorable; A11 makes the important ones come to you. **They
are complements, not alternatives** — and A11 is much cheaper.

One concrete transferable detail: the per-session **LLM cost line** in every push, omitted
entirely when unknown rather than rendered as a placeholder. Ours has an analogue in the
per-run cost of `make analysis` and any future LLM research loop.

## 4.7 Verdict

**The best-engineered repo in this log, and the only one whose headline claims survived
audit.** Adopt no code — it is US equities, Alpaca, floats-for-money and LLM-in-the-money-
path — but read its CLAUDE.md before Phase 7, and take A11 now.

The one-line summary: **he has built the production machine we have not built yet, and none
of the validation we already have.** The two failure modes are not equivalent — his is the
more dangerous one, because an unvalidated system that runs flawlessly is still an
unvalidated system, and it can lose money with perfect uptime.

---

# 5. QuantAgents-NSE — `PreethamSanji/QuantAgents-NSE`

Reviewed 2026-09-03 at `07559c5` (first 2025-12-24, last 2026-04-05). ~7,900 LOC.
**No `LICENSE` file** — so nothing here is safely reusable regardless of merit.

**The first repo in this log on our actual market**, which makes it the most directly
comparable and the easiest to check: I know what NSE costs, what its calendar does, and
what its microstructure looks like. Four named agents (Emily/news, Bob/technical, Dave/risk,
Otto/manager) replicating [QuantAgents (arXiv:2501.04916)](https://arxiv.org/abs/2501.04916)
on the Nifty 50, with FinBERT sentiment, a FinRL PPO model, and a portfolio backtester.

## 5.1 The performance claim, and why it does not survive

The claim is not in the README — it is the headline of the most recent commit:

> `feat: improve backtester **to** Sharpe 0.237, CAGR 8.9% vs Nifty 8.4%`

Note the word *to*. Read alongside the two commits before it (*"add portfolio backtester with
corrected Dave architecture"*, *"fix: correct Sharpe ratio and win rate calculation"*), the
history reads as iteration until the number looked right. Six independent problems, each
verified in source:

**1. Look-ahead — the backtest fills at the same bar it signals on.** In the rebalance loop,
the Otto score for `date` is computed from indicators over the close series *including*
`date`, and the trade executes at `closes.loc[date, sym]` — that same close:

```python
s = otto_scores[sym].get(date, 0.0)     # signal derived from date's close
...
proceeds = holdings[sym] * float(price) * (1 - commission)   # filled at date's close
```

Our constraint #3 is exactly this: compute on candle N, valid from N+1, fill at N+1 open.
Deciding on a close you then transact at is the most common backtest error there is, and it
inflates results systematically. **This is the first repo in the log with look-ahead in the
live backtest path** — repo 2's holdout was at least a commented-out line rather than a
wrong one.

**2. Survivorship bias, twice over.** The default universe is ten names, chosen as *"top 10
Nifty 50 stocks with longest yfinance history"* — RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK,
ITC, SBIN, BHARTIARTL, KOTAKBANK, LT. That is a double hindsight filter: **current** index
membership (so anything demoted over the period is absent) *and* longest history (so anything
delisted, merged or newly listed is absent). These are the ten largest Indian blue chips that
both survived and stayed in the index. Backtesting long-only on the stocks you already know
did well is not a test.

**3. Two of the four agents have no effect on the backtested result.** Verified by grep:

- `in_bull_market = bool(regime.get(date, True))` — **assigned at line 439 and never read.**
  The 200-DMA regime filter whose docstring advertises that it *"eliminates the worst
  drawdown periods (2008, 2011, 2020)"* is dead code in the backtest. (And the sample is
  2020–2025, so 2008 and 2011 are not even in it — the docstring claims out-of-sample virtue
  it never tested.)
- `r_score_today = float(r_score_series.get(date, 0.5))` — **assigned at 448 and never
  read**, with `risk_multiplier = 1.0  # Full deployment` hardcoded on the next line.

So Dave — the risk agent, Equation 3, weighted 30% in `config.yaml` — contributes **nothing**
to the number. The backtest runs Emily + Bob, which is exactly what a different docstring
admits: *"With Otto weights Emily 42.9% + Bob 57.1%…"* (= 0.30/0.70 and 0.40/0.70, Dave
dropped and the rest renormalised). **The system that was backtested is not the system the
README diagrams.** Same species as repo 1's discarded HMM and never-loaded "production
harness".

**4. The tuning is documented in the comments.** To the author's credit these are candid, but
they describe fitting: weekly rebalancing chosen because *"monthly rebalancing creates too
much lag on re-entry… hurting CAGR in recovery phases"*; Emily's ±0.5 cap chosen so that
*"a Bob=+0.4 (net 0.228) can overcome"* it, *"preventing spurious sells"*; asymmetric entry
and exit thresholds of `+0.15` and `−0.10`. Each was selected by looking at the result on the
same sample the result is quoted from.

**5. Risk-free accrual on idle cash, added for the reason it flatters.** The comment is
explicit: *"Without this, every day in cash subtracts rf from the Sharpe numerator; with it,
cash-holding is Sharpe-neutral, so the regime filter only helps by avoiding losses."*
Parking cash in a liquid fund is a real thing and 6% p.a. is a fair Indian assumption — but
the stated justification is about the regime filter, and the regime filter is dead code
(finding 3).

**6. No spread, no slippage, no impact.** Commission is modelled — 0.1% on each leg, so ~0.2%
round trip, which is roughly the right magnitude for real NSE delivery (**STT is 0.1% on
*both* legs for delivery**, plus 0.015% stamp duty on the buy, exchange and SEBI charges, GST
on brokerage + exchange, and a flat DP charge per sell ⇒ ~0.22% round trip at a zero-brokerage
discount broker; our own `app/trading/fees.py` encodes exactly this). Credit where due —
repos 1–3 modelled less. But there is **no bid-ask spread and no impact at all**, and our
6.8.2 measurement found **82% of live NSE books have a half-spread wider than a flat 2 bps.**
Trading at the untouched close is free money the backtest does not pay for.

> *Correction, added while reviewing repo 6 (which ships a full statutory fee table): an
> earlier draft of this section said real round-trip delivery cost was ~0.12–0.13% on the
> grounds that STT applies only to the sell leg. That is wrong — **delivery STT is 0.1% on
> both legs** (intraday is 0.025%, sell-side only). So repo 5's 0.2% is accurate rather than
> conservative, and only the missing spread stands as a cost understatement.*

**And after all six, the result is nothing:** CAGR 8.9% against the Nifty's 8.4% — a **0.5
percentage point** gap — at a Sharpe of **0.237**. For scale, repo 1's committed data has
buy-and-hold SPY at Sharpe 0.896. A 0.5pp edge is well inside the noise of a ten-stock
five-year sample before any of the above; after look-ahead and survivorship, the honest read
is that **no edge is demonstrated and the true number is more likely negative.**

## 5.2 An NSE calendar bug, reproduced

Rebalancing is scheduled as:

```python
rebalance_days = set(closes.resample("W-FRI").last().dropna(how="all").index)
...
if date not in rebalance_days: continue
```

`resample("W-FRI")` labels each bucket with the **calendar Friday**, but `closes.index` holds
**actual trading days**. When Friday is an NSE holiday, the label exists and no trading date
matches it — so the week is silently skipped. I reproduced it against Good Friday 2025
(18 April, a real NSE holiday):

```
rebalance_days labels        : ['2025-04-18']
actual trading dates         : ['2025-04-14','2025-04-15','2025-04-16','2025-04-17']
dates that trigger a rebalance: []
=> NO REBALANCE THIS WEEK (silently skipped)
```

India has roughly 10–15 market holidays a year and several land on Fridays, so a handful of
rebalances vanish across the sample with no error and no log line. This is precisely the
failure our domain rules name — *"trading days need the NSE holiday calendar; calendar-day
arithmetic is a bug"* — and it is satisfying to see the rule earn itself on someone else's
code.

## 5.3 What is worth taking

Modest, but real, and it lands on a slice we have not built.

**A18 / MCE slice 6 — India news sourcing.** Their Emily agent is the only worked example in
this log of Indian financial-news ingestion, and it separates cleanly into a part to copy and
a part to avoid:

- **Take: Google News RSS with India locale parameters** —
  `https://news.google.com/rss/search?q=<query>&hl=en-IN&gl=IN&ceid=IN:en`. Free, stable, no
  scraping, no ToS problem, and India-localised. That is a legitimate starting feed for the
  MCE news veto.
- **Take: FinBERT (`ProsusAI/finbert`) for sentiment**, rather than a general LLM. Purpose-
  built for financial text, runs locally, cheap, and far more reproducible than asking a chat
  model how it feels — which matters because a news *veto* must be auditable, and our
  overlays have to be §8-validatable.
- **Avoid: the MoneyControl and Economic Times HTML scrapers.** The repo ships
  `debug_mc_html.py`, `debug_et_html.py` and `debug_mc.py` — three debug scripts whose
  existence is the evidence that the HTML kept breaking. Scraping those sites is fragile and
  ToS-questionable; an RSS or licensed feed is the right dependency for something on the
  money path.

**Confirms — their weighted-agent synthesis vs our weighted confluence.** Otto combines
Emily 30% / Bob 40% / Dave 30% with Dave always entering as a negative (a risk brake), and
caps confidence at 60% when the risk alert fires. Structurally this is our confluence engine
with agents instead of factors — and the comparison flatters ours: our weights are frozen and
parity-tested, theirs are config values tuned against the same backtest they are reported on.
The one idea worth noting is **the risk term entering with a guaranteed negative sign** — a
component that can only ever subtract. Our overlays are boolean gates; a signed risk penalty
that scales confidence is a different instrument, and closer to what the reverted regime gate
should probably have been (a modifier, not a switch).

**Also worth noting for Dave's Equation 3:** `R = 0.25β + 0.25(1/LR) + 0.25·max(SE) + 0.25σ`
sums four quantities on entirely different scales (beta ≈ 1, inverse liquidity unbounded,
sector concentration ∈ [0,1], annualised vol ≈ 0.2–0.5) with equal weights and no
normalisation, then compares the total to a 0.75 threshold. Whichever term happens to be
largest dominates the score. If we ever build a composite risk scalar, **normalise the
components to a common scale first** — otherwise the weights are decorative.

## 5.4 Verdict

**Adopt no code** (there is no licence, and the backtest has look-ahead). **Take two
ingredients for the MCE news veto** — India-localised Google News RSS and FinBERT — and one
design note about signed risk penalties.

The wider value is calibration. This is the closest repo to our own problem — same exchange,
same index, same broad architecture — and its headline result is a 0.5pp edge produced by a
backtest that fills on the signal bar, over a hindsight-picked survivor universe, with two of
its four agents disconnected. **Our −0.303R expectancy is an uncomfortable number, but it is
a real one**, measured on forward paper trades with spread-aware fills. Given the choice
between an honest negative and a flattering artifact, we already hold the more valuable of
the two.

---

# 6. Three repos reviewed together

Reviewed 2026-09-03. Depth here is proportionate: **6A is substantial and directly overlaps
our paper broker**, 6B is a synthetic-data UI demo, 6C is a real app with one good idea and
one bad one.

---

## 6A. PaperTrade-India — `Mirzabaig313/PaperTrade-India`

`0f9c1b2`-era, MIT (real LICENSE), **~24,800 LOC · 543 tests**, first commit 2026-05-16.
A pip-installable **simulated NSE/BSE broker** — the same job as our `paper_broker`, built as
a standalone library. **The most directly overlapping repo in this entire log.**

Its framing is correct and matches our experience: *"No Indian broker offers a programmatic
paper-trading API"* — Kite, Upstox, Angel One, Dhan, Fyers all ❌. That is exactly why we
built our own.

**What it has that is worth studying:** a date-versioned Indian statutory fee engine, T+1
settlement with deliverable-quantity enforcement, `ProductType.INTRADAY` with 15:15
auto-square-off, tick/lot/price-band snapping and rejection, market/limit/`STOP_MARKET`/
`STOP_LIMIT`/`BRACKET` with OCO, a synthetic L2 book with queue-position tracking and
Almgren-style impact, latency and random-rejection simulation, corporate actions
(`splits`/`bonus`/`dividends`/`rights`), a double-entry cash ledger, and a pluggable
`MarketDataProvider` layer with per-provider circuit breakers and median aggregation across
sources.

That list is essentially our 6.8 slate plus Phase 7's order FSM, in one library.

### The fee table — and a correction to §5

`docs/FEES.md` is the clearest statement of Indian equity costs I have seen in any of these
repos, and checking it against our `app/trading/fees.py` showed **I made an error in §5.2**:
I wrote that real round-trip delivery cost is ~0.12–0.13% because STT applies only to the
sell leg. **Wrong — delivery STT is 0.1% on *both* legs** (intraday is 0.025%, sell-side
only). Real round trip is ~0.22%. §5 now carries the correction inline.

Our own model already encodes this correctly, so nothing in our P&L is affected — the error
was mine in the review, not ours in the code. Worth stating plainly because it changed a
judgement: repo 5's 0.2% commission was *accurate*, not conservative.

### Three findings for us

**★ A21 — our fills are spread-aware but our marks are not.** They use **mark-to-bid**
valuation for unrealized P&L: a long is worth what you could actually sell it for, not the
last traded price. We mark differently — `_open_book_mtm` values every open position at *"the
last 1m close ≤ cutoff"*:

```python
"""Gross unrealized P&L of every paper position OPEN at `cutoff`, each marked to
the last 1m close ≤ cutoff. ..."""
```

Since 6.8.2 our **fills** pay the real half-spread, but our **marks** still use the last
trade. That is an internal inconsistency in the same system: we charge the spread on the way
in and out, then value the book as if we could exit at the untouched last price. With our own
finding that **82% of NSE books have a half-spread wider than 2 bps**, across a ~25-position
book, the reported open-book MTM is systematically optimistic by roughly a half-spread per
position. **We already capture the depth (6.8.1) needed to fix it** — mark longs to bid,
shorts to ask, fall back to last when depth is stale, exactly as the fill model already does.
Cheap, and it makes the two halves consistent.

**A22 — `rebalance_bracket_sibling_qty`.** Their order module has this as a first-class named
function, alongside `cancel_bracket_siblings`. When one leg of a bracket partially fills, the
sibling's quantity must be reduced to match or you are left protecting the wrong size. **Repo
4 described this same failure as the partial-fill mode "that took several iterations to fully
pin down."** Two independent projects hitting it makes it a near-certainty for Phase 7 — and
here it is already factored as a function with tests around it. Read both before building our
order FSM.

**A23 — date-versioned fee schedules.** Theirs are *"configurable per broker and date-versioned
for mid-year statutory changes."* Ours is designed for this — the docstring says costs are
*"versioned by effective date"* and a comment notes a *"future effective-dated registry can
replace this constant"* — but today it is a single constant set. Not a defect (the code is
honest about it), but a real gap the moment a backtest spans a rate change, and Indian STT
rates do change mid-year. Low effort, and it stops a historical backtest silently using
today's rates.

**Verdict:** the one repo in this log I would consider a *reference implementation* rather
than a cautionary tale. It makes no performance claims (there is no strategy — it is
infrastructure), which is the second repo after quant-agent to pass that test. Adopt no code
(we have our own, further along on depth-aware fills), but **read `orders/`, `execution/` and
`docs/FEES.md` before Phase 7.**

---

## 6B. SentimentStock — `artist-hks/SentimentStock`

7 commits, **no LICENSE file** (despite an MIT badge linking to one), React 18 + Vite +
Tailwind + Recharts — the same frontend stack as ours.

**It is a synthetic-data demo, and the README's headline claim does not hold.** It advertises
*"Hinglish NLP sentiment analysis"* and *"LSTM-style stock predictions"*. There is no NLP and
no model: `src/data/generateData.js` produces deterministic pseudo-random series from
`Math.sin(seed) * 10000`, keyed by a hash of the symbol. "LSTM-*style*" is carrying the
sentence. To its credit the README says plainly *"No API keys. No backend"* — so the demo
nature is disclosed even if the capability framing is not.

Judged as what it is — a portfolio UI piece — there is one idea worth taking.

**U19 — the lag-correlation chart.** A bar chart of correlation against lag in hours, with a
`ReferenceLine` at zero and per-bar colour, answering *"at what delay does this signal best
line up with price?"*

We have a live question shaped exactly like this and no visual for it. Our own analysis found
that **we grade multi-day trades on a one-day clock** — entry-day ≥1R is 12%, against 36% for
swing and 54% for positional in-horizon, with +1R typically arriving on d+3. That is a
lag/horizon finding discovered in prose. A horizon-correlation bar chart is its natural
rendering, and it generalises to every shadow overlay we run: *at what horizon does this gate
actually separate winners from losers?* Cheap in Recharts, which we already use.

**CONFIRMS:** `sentimentToLabel` and `sentimentToShortLabel` bucket the same 0–1 score at
different thresholds (`< 0.25` vs `< 0.3` for the bearish boundary), so the same number can
read "Bearish" in one component and "Slightly Bearish" in another. This is precisely why
`lib/format.ts` is the single formatting path in our rules.

---

## 6C. InvestmentPrediction ("BharatiQuant") — `madhusudhan-nikhil/InvestmentPrediction`

52 commits, active (last 2026-09-01), **no LICENSE file**. FastAPI backend + React frontend,
NSE universe, four tabs: portfolio diagnostic/optimisation, target-profit & sell-date
predictor, a macro shock simulator (oil, VIX, FII/DII, RBI rates), and a ticker-universe
manager. The closest thing here to a *consumer product* aimed at Indian retail investors.

**The good idea: Hierarchical Risk Parity for portfolio construction.** HRP is López de
Prado's method — the same source our reading review already flagged for purged CV and the
deflated Sharpe. It builds allocations from a hierarchical clustering of the correlation
matrix instead of inverting it, which is genuinely more robust than mean-variance on noisy
estimates. **This is a real answer to a real gap of ours:** our portfolio heat sits at 45.3%
with no cap and no correlation-aware sizing, and the Varsity review already listed
"correlation-aware heat" as a target. HRP is a defensible way to get there. *(Noted as a
pointer, not a queue item — it belongs to whatever eventually builds portfolio construction,
and it needs the same evidence bar as anything else.)*

**The bad idea, and it is instructive: the "probable exit date".** The engine reports a
specific calendar date on which you can expect to sell at your target. The computation:

```python
mu_daily     = ((1 + exp_ret/100) ** (1/365) - 1) * momentum_mult   # category fudge 0.70–1.45
avg_drift    = ((1 + 0.13) ** (1/365) - 1)                          # 13% baseline
speed_factor = avg_drift / mu_daily
est_days     = holding_days_target * speed_factor
exit_date    = today + timedelta(days=est_days)
```

Three problems, in increasing order of seriousness:

1. **Zero volatility.** Time-to-target is a *first-passage* problem for a stochastic process
   — it has a distribution, not a value. This is a smooth compounded drift path with no
   variance anywhere, yet the output is labelled *"probable"*.
2. **`momentum_mult` is a hardcoded category fudge** (Category C ×1.45, Category D ×0.70)
   applied directly to the drift, with no derivation.
3. **The target return does not enter the date calculation at all.** `target_return_pct` sets
   `target_price`, but `est_days` depends only on `holding_days_target` and the ratio of
   expected returns. **Ask for a 5% target and a 50% target on the same stock with the same
   horizon and you get the same exit date.** The date is independent of the target it is
   presented as the date for.

So the "probable exit date" is the user's own requested horizon, scaled by how the stock's
expected return compares to 13%. It is arithmetic on the input, rendered as a prediction with
a specific date.

**A24 — never render a precise figure without its uncertainty.** A calendar date is read as a
confidence signal; precision without an interval is a claim you have not earned. This is the
same failure as repo 3's vote-share-labelled-"confidence" and repo 1's placeholder-as-metric,
and it is worth a standing rule because **we are exposed to it in a specific way**: the stated
goal of 2–3%/day is exactly the kind of desired return that invites a system to convert a wish
into a confident timeline. Our position is already on record — prove expectancy forward, size
small, measure monthly and yearly *with variance*. This repo is what the alternative looks
like when it is built.

**Also worth noting:** their macro simulator (shock oil/VIX/FII-DII/RBI and see the portfolio
response) is a *scenario* tool rather than a prediction tool, and that framing is the honest
one — "what would happen if" makes no claim about likelihood. We have FII/DII data already;
a scenario view over the paper book would be a legitimate future use of it.

---

# 7. Stock-market-prediction-and-screener — `sumittttttt/Stock-market-prediction-and-screener`

Reviewed 2026-09-03. MIT (real LICENSE), 38 commits, **2022-04 → 2023-01** — a student/portfolio
project, three years old and unmaintained. ~3,900 LOC: a Streamlit multi-page app (fundamentals,
technical indicators, "screener", pattern recognition, next-day forecasting) plus a
`model_comparison.ipynb` that picks the forecasting model.

Judged for what it is, this is a competent student portfolio piece. But it is the **ninth** repo in
this log, and it repeats — in unusually clean, teachable form — three failure modes the previous
eight already established. That is its value here.

## 7.1 The model comparison: leakage, and the missing baseline

The README's headline table selects LSTM for the webapp:

| Model | Large cap | Mid cap | Small cap |
|---|--:|--:|--:|
| Moving Average | 971.40 | 234.64 | 23.10 |
| kNN | 1174.90 | 232.54 | 23.02 |
| Linear Regression | 680.51 | 400.30 | 24.51 |
| **LSTM** | **117.49** | **24.47** | **2.88** |

> *"We can clearly see LSTM has the very low error… So we will use LSTM model in our webapp."*

**Problem 1 — the scaler is fit on the full series, including the validation window.** From
`model_comparison.ipynb`, cell 16, in this order:

```python
dataset = tcs_lstm.values
train   = dataset[0:990,:]
valid   = dataset[990:,:]          # split defined…

scaler      = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(dataset)   # …then fit on the WHOLE thing
```

The min and max of the future test window are baked into the normalisation the model trains
under. For a strongly trending decade of TCS closes, knowing the global maximum is a
substantial hint, and it mechanically prevents the model from predicting outside the realised
range. Textbook leakage — our constraint #3, in its ML form.

**Problem 2 — and the more interesting one — there is no naive baseline.** For a *next-day
price* predictor the only benchmark that matters is persistence: "tomorrow's close = today's
close." It is absent from the table.

The omission is not cosmetic. A large-cap Indian stock trading in the low thousands with ~1.5%
daily volatility has a persistence RMSE of roughly **₹40–50**. The chosen LSTM scores
**117.49**. On that arithmetic the winning model is around **two to three times worse than
predicting no change at all** — while comfortably beating the three other models it was
compared against. *(Order-of-magnitude estimate: I do not have their exact split, so treat the
ratio as indicative rather than exact. The point stands regardless of the constant — the
comparison that would settle it is the one the table omits.)*

This is the cleanest instance in the whole log of synthesis lesson 1: **the elaborate model is
benchmarked only against other elaborate models, and the trivial baseline that would beat them
all is never run.** It is the same shape as AgentQuant's buy-and-hold and QuantHarness's
logistic regression — except here the baseline is so simple it is a single line of pandas.

Underneath it sits the standard trap: an LSTM fed raw price levels learns an approximate
identity function, so RMSE *on levels* looks impressive and says nothing about directional
skill. Evaluating on **returns**, against persistence, is what would have revealed that.

## 7.2 A guard that can never fail — the third instance in this log

`functions.py`:

```python
def is_consolidating(df, percentage=10):
    ...
    if min_close > (max_close * threshold):
        return 'YES'
    return 'NO'                       # ← returns STRINGS

def is_breaking_out(df, percentage=10):
    last_close = df[-1:]['Close'].values[0]
    if is_consolidating(df[:-1], percentage=percentage):   # ← used as a boolean
        recent_closes = df[-16:-1]
        if last_close > recent_closes['Close'].max():
            return 'YES'
    return 'NO'
```

Both `'YES'` and `'NO'` are non-empty strings, so both are truthy — verified:

```
bool('YES') = True
bool('NO')  = True
=> the consolidation precondition is ALWAYS satisfied
```

`is_breaking_out` therefore degrades to a plain 15-day-high check with its defining filter
silently disabled. A breakout *from consolidation* and a breakout *from anything* are very
different signals, and the page reports the latter as the former.

This is the third variant of the same defect class across nine repos — **a guard that cannot
return false**: AgentQuant's `generalization_gap = max(avg − best, 0) ≡ 0`, ai-quant-agents'
`risk_approved = "risk" not in decision.lower()`, and now a string-returning predicate used in
a boolean context. Three different root causes, one symptom. **The generalisable test is
mechanical: for every guard, ask what input makes it fail, and if you cannot name one, it is
not a guard.** Worth adding to `.claude/rules/testing.md` alongside the §1.7 rule — our own
`unassessed` tripwire failed exactly this test.

## 7.3 The "screener" does not screen, and every number on it is truncated

Two UI findings, both *confirms* rather than takes:

**It is not a screener.** `pages/03_Screener.py` opens with `st.selectbox('Enter or Choose
stock', symbol)` — a **single** ticker — then renders indicators for it. A screener filters
many instruments by criteria; this filters nothing. Our own `ScreenerPage` is a real
multi-stock filter (12 fields), so nothing to take — but the mislabelling is a reminder that a
feature name is a promise.

**Every indicator is silently truncated to an integer.** The page does, repeatedly:

```python
rsi_df_tail  = round(rsi_df['RSI'].iloc[-1:].astype('int64'), 2)
macd_df_tail = round(macd_df['macd'].iloc[-1:].astype('int64'), 2)
```

The `astype('int64')` happens **before** the `round(..., 2)`, so RSI 67.83 renders as `67.00` —
fake precision, two decimal places of guaranteed zeros. For MACD it is worse: MACD commonly
sits between −5 and +5, so integer truncation destroys the signal outright (0.83 → 0). This is
precisely why `lib/format.ts` is the single formatting path in our rules, and why "prices to 2
decimals" is a display rule rather than a casting rule.

## 7.4 The one thing worth taking

**A small, clean consolidation primitive.** Stripped of the truthiness bug, `is_consolidating`
is a decent compact base-detector: over the last *N* candles, the stock is consolidating if
`min_close > max_close × (1 − pct/100)` — i.e. the whole recent range fits inside a `pct`% band.
No look-ahead, no parameters beyond window and width, trivially testable.

That is relevant to a research item we already have queued: the **Minervini trend-template
shadow test** (from the e-book review, still unbuilt). Base/consolidation detection is a core
Minervini criterion, and this is a serviceable starting definition — with the obvious upgrades
of returning a real boolean, measuring the range in ATRs rather than raw percent, and
requiring a minimum base length. **Noted as a pointer for that item rather than a new queue
entry**, since the trend-template test is where it would land.

## 7.5 Verdict

**Adopt no code.** A three-year-old unmaintained student project whose model selection rests on
a leaked scaler and a missing baseline, and whose flagship screening primitive has its filter
disabled by a truthiness bug.

Its value is entirely as confirmation. Nine repos in, the pattern is stable enough to state as
a prior: **when a repo picks a model, check what it did *not* compare against; when it ships a
guard, ask what makes the guard fail.** Both questions took under five minutes here and both
returned findings.

---

# 8. express-option-chain — `pramakrishn/express-option-chain`

Reviewed 2026-09-03. MIT, **952 LOC, 3 commits, 2023-01 → 2023-07**, unmaintained. A focused
pip-installable library that streams NSE/MCX/CDS/BCD **option chains over Kite Connect into
Redis**.

**This is the only repo in the log built on our exact stack** — Kite Connect WebSocket +
Redis, Indian derivatives. It is infrastructure with no strategy and no performance claim,
which by lesson 8 predicts it will hold up better than the strategy repos. It mostly does,
and its most valuable contribution is a documented broker quirk that **we are currently
exposed to**.

## 8.1 The finding that matters: Kite can send quote-mode ticks on a full-mode subscription

From `option_stream.py`:

```python
def on_ticks(self, ws, ticks):
    if ticks[0]['mode'] != ws.MODE_FULL:
        # bug: web socket sent ticks in quote mode even though we subscribed in full mode
        log.error('websocket sent ticks in quote mode.. closing connection and reopening another one')
        ws.stop()
        return
```

A field-discovered Kite behaviour, with a workaround: detect the downgrade, tear the socket
down, reopen.

**We subscribe `MODE_FULL` and harvest order-book depth from those ticks — and we never check
the mode.** Verified:

- `live_worker.py:979` — `ws.set_mode(ws.MODE_FULL, list(token_map))`
- `live_worker.py:505` — *"Also harvests top-of-book from the MODE_FULL ticks into…"*
- `tick_consumer.py:256` — *"Order-book depth (6.8.1): cache top-of-book from the MODE_FULL tick"*
- **No `tick['mode']` validation anywhere on either path.**

If Kite exhibits this downgrade against us, the depth fields simply are not in the tick, so
`depth:{stock_id}` goes stale, and **6.8.2's spread-aware fills silently fall back to the flat
`paper_slippage_bps` floor** — which is exactly the fail-open behaviour we designed. That is
correct engineering *and* the reason it is dangerous here: the degradation is invisible. The
only symptom would be paper fills quietly getting cheaper than reality, on a book we are
using to judge whether a −0.303R expectancy is improving.

**A25 — assert the tick mode and count the degradations.** Cheap: check `mode` on the batch,
increment a counter when it is not full, and surface it. It pairs exactly with **A11** (the
session notifier) and with our existing **silent-feed-outage alarm (6.8.6)** — which already
establishes the pattern that a quiet data failure needs a loud signal. Note this is *not* a
bug we have observed; it is a documented broker behaviour we have no detector for, on a path
built to fail open.

## 8.2 Capacity limits done right — the contrast with our own hot-set flood

They name the broker's constraints as constants, with provenance:

```python
# these are the limits set in kite connect 3
MAX_TOKENS_PER_WEBSOCKET = 3000
MAX_WEBSOCKET_CONNECTIONS = 3
```

…shard the token list across `ceil(n / 3000)` processes, and **refuse to start** past the
ceiling with an error that names the actual numbers and two concrete remedies:

> *"You have passed N trading symbols. M instrument tokens must be subscribed… which is
> greater than the allowed value of 9000 tokens. Please lower the number of trading symbols…
> or use a percentage criteria filter to filter out the tokens which are far from spot price."*

**This is the direct contrast with a failure we have already had.** Our `live-worker` hot set
had a cap, breadth alerts flooded it, and **watchlist stocks silently stopped being scored** —
a capacity limit breached without a word. They fail loudly at the boundary and tell you how to
get under it; we failed quietly and found it later. **A26 — when a capacity limit exists,
refuse at the boundary with the numbers and the remedy, rather than degrading silently.**

Their `criteria` percentage filter (drop strikes more than X% from spot) is also the right
domain-shaped answer to a token budget — the same idea as our hot-set selection, applied to
an option chain.

*(One honesty note: the README's example comment says "there is no limit on the number of
symbols to subscribe to", while the code raises at 9000 tokens. Mild, but it is the seventh
of ten repos where a README overstates what the code does.)*

## 8.3 What not to copy — and it is what our own rules already forbid

Four defects, each mapping to a rule we hold:

| Their code | Our rule |
|---|---|
| `self.db.hset('ticks', token, json.dumps(tick))` — **one Redis round-trip per tick**, in a loop, no pipelining. At 9000 instruments that is 9000 calls per batch. | *"Any new live-pipeline feature MUST wire into `live_worker`'s per-batch pipeline, never a per-tick `redis.set`"* — the exact defect perf-auditor caught in our 6.8.1. |
| `threading.Thread(target=self.handle_ticks, …).start()` **on every tick callback** — unbounded thread creation, no queue, no backpressure. | Bounded queues with an explicit overflow policy; every task owned. |
| `hset('ticks', …)` with **no TTL**. | *"Every cache key gets a TTL — eviction policy is volatile-lru, so TTL-less keys are treated as broker-critical and never evicted."* On our Redis this would be actively harmful. |
| `ticks[0]['mode']` — indexes element 0 **without checking the list is non-empty.** | — |

And two operational gaps:

- **Token expiry is unhandled.** `on_noreconnect` logs *"reconnect failed"* and stops. There is
  no `TokenException` path and no refresh. Since the Kite access token dies ~06:00 IST daily,
  a long-running stream simply ends every morning. Our domain rules name this precisely: token
  expiry *"must be treated as a normal lifecycle event (restart + warmup + gap-fill), not an
  error loop."*
- **The process watchdog is a startup check, not a supervisor.** It loops restarting dead
  processes until all are alive, then **returns** — after which a process that dies is never
  restarted. It also rebuilds the `Process` around the *same* `KiteTicker` object from the dead
  process. Compare repo 4's approach, which is the right one: layered timeouts, a durable
  repair queue drained at every session entry.

One thing worth keeping from the same file: an explicit, hardware-anchored latency budget in a
comment — *"make sure this method doesn't take more than 2s. A subscription of about 9000
stocks would surpass the capability of an 8-core Mac laptop."* Stating the budget and the
machine it was measured on is better practice than most of this log.

## 8.4 Verdict

**Adopt no code** — it is unmaintained since 2023, and its Redis and threading patterns are
things our rules explicitly forbid. But it is a useful artifact: the only repo here operating
the same broker API we do, and it hands us **one concrete gap (A25, the unvalidated tick mode
on a fail-open depth path)** and **one sharpened principle (A26, refuse loudly at a capacity
boundary)** that our own hot-set flood already proved we needed.

Its infrastructure-not-strategy character holds up lesson 8 again: three of ten repos make
no performance claim, and all three (quant-agent, PaperTrade-India, this) are the ones whose
code is worth reading.

---

# 9. 股票智能分析系统 — `ZhuLinsen/daily_stock_analysis`

Reviewed 2026-09-03. MIT. **~332,000 LOC · 5,782 test functions · 50 commits · 2026-08-05 →
2026-09-01.** Chinese-language, multi-market (A-shares / HK / US / JP / KR / TW), AI-driven
daily analysis pushed as a "decision dashboard" to WeCom, Feishu, Telegram, Discord, Slack and
email. Trendshift #1 Python repo of the day; arXiv badge; active two days before review.

**By far the largest repo in this log — 330k LOC in 27 days, about 12,000 lines a day.** That is
only reachable with heavy LLM code generation, and the repo says so structurally: it ships
`CLAUDE.md`, `AGENTS.md`, `SKILL.md` and a `.claude/skills/` directory. I mention the ratio not
as a criticism but because it sets the audit question: **does the volume correspond to
substance?** On the parts I checked, unexpectedly, yes — and in one area it is the most careful
work in this entire document.

## 9.1 Its backtest layer is the most methodologically careful in the log

The system grades its own past analyses against realised outcomes — `direction_accuracy_pct`,
`win_rate_pct`, `avg_stock_return_pct`, `avg_simulated_return_pct`. This is the honest version
of what repo 1 faked with a hardcoded placeholder, and it is built properly.

**It resolves the entry bar from the market session phase at analysis time.** The question that
sank repo 5 — *which bar could you actually have acted on?* — is here a first-class concept:

```python
def resolve_historical_daily_bar_date(market, target_date, phase) -> Optional[date]:
    """Resolve the completed daily bar that a historical phase could consume.
    ...
    It fails closed for missing, unknown, or calendar-inconsistent phases.
    """
    normalized_phase = str(phase or "").strip().lower()
    if normalized_phase not in {
        "premarket", "intraday", "lunch_break",
        "closing_auction", "postmarket", "non_trading",
    }:
        return None
```

Four things worth naming:

1. **It fails closed.** An unknown or calendar-inconsistent phase returns `None`, which *excludes
   the record from scoring* rather than guessing. **In every other repo here, ambiguity resolved
   in favour of the flattering answer.** This is the first one that resolves it in favour of
   silence.
2. **Six named session phases**, including `lunch_break` (real for A-shares and HK) and
   **`closing_auction`** — directly interesting to us, since our own CAS work treats the
   3:15–3:35 auction as a distinct regime, and here the auction is a phase that determines which
   bar is consumable.
3. **A real calendar library per market** (`exchange_calendars`), not calendar-day arithmetic —
   the failure I reproduced in repo 5.
4. **A persisted `effective_daily_bar_date` is "the primary authority"**, with this resolver as a
   documented fallback for older snapshots. Provenance over recomputation.

The win-rate definition is also stated rather than assumed — `胜 / (胜 + 负)`, **excluding
neutral outcomes**, with a configurable `neutral_band_pct`. Excluding neutrals is a choice that
can flatter, but it is *documented in the field table*, which is more than most.

**And crucially: the README publishes no accuracy number.** It ships the measuring instrument
and lets you run it on your own history. That is the fourth repo of eleven to decline a
performance claim, and it keeps holding: **the ones that don't claim are the ones worth reading.**

## 9.2 Notification design — additions to A11

This is a daily-analysis-and-push system, which is exactly the shape of `make analysis` plus the
notifier I have been recommending. Two ideas extend **A11** beyond what repo 4 gave us:

**A27 — a notification config dry-run.** `main.py --check-notify` validates the notification
setup *without sending anything*, alongside `--no-notify` (run the analysis, skip the push).
Anyone who has configured a webhook knows the alternative is spamming a real channel to find out
whether the token works. For us this matters more than it sounds: A11's whole value is that it
runs unattended, so the first time it *should* fire is a bad time to discover the credentials
are wrong.

**A28 — classify a delivery failure by whether retrying can help.** Their `ChannelAttemptResult`
carries an explicit `retryable: bool`, and dispatch returns a structured
`NotificationDispatchResult` across channels rather than a single boolean. This is repo 4's
insight (classify failures by whether a human can act) applied one level down, to the transport.
Combined with repo 4's rule that **a notifier outage must never affect trading**, the design is:
try, classify, record, never raise into the caller.

They also carry a "noise reservation" concept with in-flight accounting, and truncate alert
bodies to the top three failed checklist items — both consistent with repo 4's noise policy, and
worth keeping in mind when A11 is built rather than designed from scratch.

## 9.3 Honest cautions

**The recommendations are monetised.** The README opens with a sponsors block, and the
"recommended" LLM, market-data and search providers carry affiliate parameters —
`share_code=`, `?aff=`, `ref=`, `utm_source=`. The free defaults (AkShare, Baostock, YFinance)
genuinely work and the instability disclaimer is fair, but **"we recommend TickFlow/Tushare for
stability" is not a neutral engineering opinion here.** Stated as fact, not as an accusation:
the code is not compromised by it, but the provider comparisons should not be read as
disinterested.

**File sizes are a maintenance risk.** `system_config_service.py` at 5,563 lines,
`config_registry.py` at 5,182, `analyzer.py` at 5,124, and test files at 4,841 and 4,754 lines.
Whatever generated them can regenerate them; a human maintaining them later is a different
proposition. The 5,782 tests are a real asset only to the extent they assert behaviour rather
than restate implementation — which at this volume I did not attempt to verify, and would not
assume.

**Its actual decision layer is an LLM producing scores, buy/sell points and checklists**, which
carries every reproducibility problem already covered in §2.6 and §4.5. Nothing here changes our
position that the money path stays deterministic.

## 9.4 Verdict

**Adopt no code** — wrong market, wrong language for our team, and an LLM decision core we have
deliberately rejected. But **read `src/core/trading_calendar.py`**: its phase-aware,
fails-closed resolution of "which bar could this analysis have acted on" is the single best
treatment of that question in eleven repos, and it is the exact question our own backtests, our
CAS work and our outcome grading all depend on.

Two queue items (**A27**, **A28**) extend A11. And one broader observation: this is the only
repo here where large-scale AI-assisted generation produced work *more* methodologically careful
than the hand-written academic and hobby projects alongside it. The determining factor was not
how the code was written — it was that **someone decided the ambiguous case should fail closed**,
and that decision is cheap, one-line, and absent from almost every other repo in this document.

---

# 10. Qlib — `microsoft/qlib`

Reviewed 2026-09-03. MIT, Microsoft Research. **~56,000 LOC**, an AI-oriented quantitative
investment platform: data layer with an expression engine, model zoo, backtest with a realistic
exchange model, RL execution, and MLflow-shaped experiment tracking.

**This is a different tier from everything else in this log** — a maintained, industrial-grade
research platform rather than a project with a thesis to sell. It makes no performance claim at
all (fifth of twelve), and it is the first repo where the right posture is *study it*, not
*audit it*. Four findings below are gaps it exposed in **our** code.

## 10.1 ★ Point-in-time fundamentals — and the best test in the entire log

Qlib treats point-in-time correctness as a first-class concept: PIT fields carry a `$$` prefix
and are queried through a `P()` operator (`P($$roewa_q)`), so **using non-PIT data is
syntactically visible** rather than an invisible mistake.

The test that pins it (`tests/test_pit.py`) is the single best piece of testing I have seen
across twelve repos:

```python
# Mao Tai published 2019Q2 report at 2019-07-13 & 2019-07-18
#  - http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search
data = D.features(["sh600519"], ["P($$roewa_q)", "P($$yoyni_q)"],
                  start_time="2019-01-01", end_time="2019-07-19")

#            P($$roewa_q)
# 2019-07-17     0.000000
# 2019-07-18     0.175322   ← the value changes on the actual publication date
# 2019-07-19     0.175322
```

**It asserts that a fundamental value changes on the exact date the filing was published, and
cites the real disclosure URL in a comment.** That is a regression test anchored to a verifiable
external fact — it cannot rot into tautology, and it fails loudly the day someone introduces
look-ahead into the fundamentals path. Its sibling `test_no_exist_data` asserts `NaN` for a stock
with no PIT record rather than forward-filling: **fails closed**, again.

**Why this matters to us specifically.** Our **MCE slice 5b (the `market_cap` writer) is
unbuilt and is the keystone blocker** for everything fundamental — and the moment we build it we
inherit exactly this trap: using a company's *currently reported* financials for a backtest date
before that report existed. Nothing in our stack currently expresses "as known on date D."

**T1 — when we build the fundamentals writer, ship a PIT test anchored to a real, cited NSE
filing date.** Pick a Nifty name, cite the BSE/NSE announcement URL in the test, and assert the
value changes on that date and not before. Cheap, permanent, and it is the only kind of test
that makes a look-ahead claim falsifiable.

## 10.2 Their exchange model exposes two gaps in ours

`qlib/backtest/exchange.py` constructor defaults:

```python
open_cost: float = 0.0015,      # asymmetric — buy
close_cost: float = 0.0025,     #              sell costs more (stamp duty is sell-side in CN)
min_cost: float = 5.0,          # a FLOOR per trade
trade_unit = 100,               # round lots (China A)
limit_threshold = ...           # price-limit (circuit) enforcement
```

…and it *warns you when you leave the limit off*: `"limit_threshold not set. The stocks hit the
limit may be bought/sold"` — i.e. it tells you your backtest is about to trade stocks that were
locked limit-up/down and untradeable.

Checked against ours:

**A29 — we have no flat DP charge, and no minimum cost per trade.** Our `FeeSchedule` is
otherwise excellent (delivery STT both legs, intraday sell-only, stamp on buy, GST on the right
base) — but it has no `dp_charge_per_sell`. Zerodha/CDSL levy a **flat ~₹13.5–20 per delivery
sell scrip regardless of size**, which PaperTrade-India (6A) models and we do not. A fixed cost
disproportionately penalises small positions — which is exactly what our notional cap produces,
and exactly the ₹1L / 1–2 position shape live trading will have. **We are under-costing our
paper book, in the direction that flatters an already-negative expectancy.**

**A30 — our backtest does not enforce circuit bands, though our order path does.** We built
`circuit_guard.py` in 6.8.3 so the *paper order path* refuses to enter a name pinned near its
adverse band. Grepping `app/backtest/` for band handling returns nothing (the only hit is
`BBANDS`, a Bollinger indicator). So **the backtest will happily fill orders on days a stock was
locked at a circuit limit and could not be traded at all.**

That is worth naming as a pattern rather than a one-off, because it is now the **third** instance:

| We added realism here | …but not here |
|---|---|
| Spread-aware **fills** (6.8.2) | Open-book **marks** still use last close (**A21**) |
| Circuit bands on the **order path** (6.8.3) | **Backtest** fills ignore bands (**A30**) |
| `MODE_FULL` depth **subscription** | Tick mode never **verified** (**A25**) |

**A31 — when a realism constraint is added to one execution path, add it to every path that
produces a comparable number, in the same change.** Otherwise backtest, paper and live results
silently stop being comparable, which is precisely the property we need them to have.

## 10.3 Experiment tracking — the mature form of H4 and U1

`qlib/workflow/` is an MLflow-shaped recorder: experiments contain runs, and each run records
**params** (what you configured), **metrics** (what came out), and **artifacts** (the files that
prove it) — `log_params` / `log_metrics` / `log_artifact` / `save_objects`.

That three-way split sharpens how I framed **H4** (gate register) and **U1** (registry page). Our
shadow sidecars currently emit one markdown file per gate per day, with the configuration living
in `.env` and the evidence living in prose. The recorder shape says: record the gate mode and
thresholds and cohort definition as *params*; the n, expectancy, DSR and MinTRL as *metrics*; and
the sidecar file and its query as *artifacts*. Then **U1's page is a view over that store and the
review calendar is a query**, rather than either being a thing someone has to maintain by hand.

Worth adopting the vocabulary even if we never adopt MLflow itself.

## 10.4 Test concepts worth stealing — a new `T` queue

The user asked for test ideas, and this is a serious library's answer. Extracted from
`tests/`, the ones that map onto something we have or will have:

**T2 — lifecycle-boundary tests for a simulator.** `test_simulator_first_step`,
`test_simulator_start_middle`, `test_simulator_stop_early`, `test_simulator_stop_twap`. Not "does
it run" but "does it behave when started mid-stream, stopped early, or stopped at a benchmark."
**Directly applicable to Phase 7's order FSM** — resume mid-session, kill mid-flight, square off
early — and it pairs with A22 (bracket sibling qty on partial fill) and A16 (the durable repair
queue), both of which are lifecycle-boundary bugs found the hard way by other people.

**T3 — parametrised fill tests under a participation limit.**
`test_soft_topk_cold_start_impact_limit(impact_limit, expected_fill)` — given a market-impact
cap, assert the resulting fill. We model spread and size-vs-top-of-book impact in 6.8.2 but have
no *volume participation* cap; if we add one, this is its test shape.

**T4 — explicit NaN and corner-case tests.** `test_nan`, `test_nan_option_covariance`,
`test_corner_cases`. We have earned these: a non-finite Redis LTP once 500'd the signal detail
endpoint because `Decimal("nan")` parses without raising. A standing NaN-path test on every
numeric boundary (LTP, ATR, confidence, R:R) is cheap insurance.

**T5 — crash-path tests.** `test_exit_on_crash_finite` / `test_exit_on_crash_infinite`: assert
the system exits *correctly* when it dies, in both bounded and unbounded modes. Repo 4's
"orphaned protection intents drain at the next session entry" is the trading-specific version;
this is the general one.

**T6 — ordered pipeline-stage integration tests.** `test_0_dump_bin` → `test_1_dump_calendars`
→ `test_2_dump_instruments` → `test_3_dump_features`: numeric prefixes deliberately sequence a
data-pipeline test so a failure names the stage that broke. Our EOD ingestion + enrichment chain
has the same shape and currently has no staged integration test.

## 10.5 Verdict

**The only repo in this log I would call a genuine reference for research methodology**, and the
first where nothing needed debunking. Adopt no code — it is a Python research platform for
Chinese and US equities with its own data format, and we have a frozen Rust-backed engine — but
its *concepts* are the most valuable harvest here:

- **PIT-as-syntax** and a filing-date-anchored test (**T1**) — before MCE 5b, not after.
- **Two concrete costing/realism gaps in our code** (**A29**, **A30**) and the pattern behind
  them (**A31**).
- **params / metrics / artifacts** as the shape of H4 and U1.
- **Five test concepts** (T2–T6) that map onto Phase 7 and our ingestion chain.

---

# 11. Retro-mined: Claude Code tooling across the log — a new `W` queue

The user's widened brief prompted a pass back over the repos still on disk for **workbench**
material — agents, skills, hooks, commands, rules. Two repos carry any, and one is genuinely
worth borrowing from.

**Qlib has none** (Microsoft, pre-dating agent tooling conventions). **quant-agent (repo 4)**
has the CLAUDE.md already covered at length in §4.4 — its invariants-with-dated-incidents
section (A12) remains the best example in the log.

**daily_stock_analysis (repo 9)** ships `.claude/skills/` (`fix-issue`, `analyze-issue`,
`analyze-pr`), a root `SKILL.md`, and an `AGENTS.md`. Assessed honestly:

- **Its three skills are GitHub triage workflows.** We are solo with no PR flow, so these are
  *considered and rejected* rather than a gap.
- **Its root `SKILL.md` exposes the product's own analysis capability as a skill**, with the
  output contract documented inline. Interesting, but it overlaps our existing
  `/daily-analysis` — noted, not queued.
- **Its `AGENTS.md` hard rules are the real find.** Several are sharper than our equivalents:

**W1 — make doc/code precedence an explicit rule.** Theirs: *"If this file disagrees with the
repo's scripts, workflows or code, **the executable content wins** — and fix the doc in the same
change so the drift stops."* We hold this belief (our doc-sync ritual says "trust the artifact
over the checkbox") but state it as a habit rather than a precedence rule. Worth promoting to a
one-line rule in CLAUDE.md, because it tells a future session what to do when it finds a conflict
rather than merely that conflicts are bad.

**W2 — "do not add parallel implementations" as a written rule.** Theirs: *"Prefer reusing
existing modules, config entry points, scripts and tests; do not add parallel implementations."*
**This is the rule with the most evidence behind it for us**: our own review round found there
were **five separate Buy surfaces** in the frontend, one of them unwired, and the eligibility
gating had to be retrofitted across all of them. A written rule would not have prevented it
alone, but it names the failure mode.

**W3 — same-commit config hygiene.** Theirs: *"When adding a config item, you must update
`.env.example` and the related docs in the same change."* We have a broad doc-sync ritual; this
is the narrow, checkable instance of it, and config drift is exactly what bit us when a `.env`
gate-mode flip did not reach a running process.

**W4 — extend the git restraint from push to commit and tag.** Theirs forbids `git commit`,
`git tag` and `git push` without explicit confirmation. Our convention reserves *push*. Worth a
deliberate decision rather than an accident — in this session I have been committing freely to a
worktree branch and holding pushes, which has worked well, but the boundary should be written
down rather than inferred.

**W5 — forbid hardcoded model names alongside secrets and paths.** Theirs bans hardcoding
"secrets, accounts, paths, **model names**, ports, or environment-difference logic". The model-name
clause is the non-obvious one, and we have the analogous wound: `STATUS.html` hardcodes gate
modes in prose and an ASCII diagram, so a mode flip silently falsifies it. Same class — a value
that lives in config, copied into a place that cannot track it.

*(Deliberately not queued: their commit-message convention forbids `Co-Authored-By`, which
conflicts with this project's own instruction to include it.)*

---

# 12. VeighNa (vnpy) — `vnpy/vnpy`

Reviewed 2026-09-03. **MIT.** Core framework **~12,800 LOC**; a decade old, and the most
battle-tested open-source live-trading framework in Asian markets — real money, real brokers,
thousands of users.

The core is small **by design**: broker gateways (`vnpy_ctp`, `vnpy_ib`, …) and strategy apps
(`vnpy_ctastrategy`, `vnpy_riskmanager`, …) live in **separate installable packages**. What
remains here is the part we actually care about: the event engine, the OMS, the gateway
abstraction, and the domain objects.

**This is the most Phase-7-relevant repo in the log.** Our NautilusTrader review already named
the gap — *"runtime plumbing (event bus, ExecutionEngine + BrokerAdapter, RiskEngine,
reconciliation)"*. vnpy is a second, independent implementation of exactly that, and unlike
Nautilus's LGPL it is **MIT — so it is legally vendorable, not just readable.** That is a
material difference worth recording against our existing Nautilus note.

## 12.1 The event bus is 145 lines — and that is the finding

The entire event engine:

```python
class EventEngine:
    def __init__(self, interval: int = 1):
        self._queue = Queue()
        self._thread = Thread(target=self._run)          # one consumer
        self._timer  = Thread(target=self._run_timer)    # emits EVENT_TIMER every second
        self._handlers = defaultdict(list)
        self._general_handlers = []

    def _process(self, event):
        if event.type in self._handlers:
            [handler(event) for handler in self._handlers[event.type]]
        if self._general_handlers:
            [handler(event) for handler in self._general_handlers]
```

Three design decisions are worth taking:

1. **One consumer thread, processing serially.** Handlers never run concurrently with each
   other, so none of them needs a lock against another. Most of the simplicity comes from this
   single choice.
2. **Wildcard `general_handlers`.** Logging, recording and UI layers subscribe to *everything*
   without enumerating event types — so adding a new event type does not require touching them.
3. **A timer event generated by the bus itself.** `EVENT_TIMER` fires every second, so
   *everything periodic becomes an ordinary subscriber* — position polling, order timeouts,
   reconnect checks, staleness alarms. **One scheduling primitive instead of a scheduler plus a
   bus.** Elegant, and directly applicable: our 6.8.6 staleness alarm, the provisional-health
   watch and the CAS capture window are all "do this on a clock" problems currently solved three
   different ways.

The headline lesson for Phase 7: **the event bus is not the hard part.** A decade of real-money
trading runs on 145 lines of stdlib Python. The hard parts are the things around it — the order
lifecycle (A22/A16), reconciliation, and the risk engine.

## 12.2 …but I reproduced three robustness gaps in it

**A single handler exception kills the entire bus, silently.** `_run` catches only `queue.Empty`,
so anything a handler raises escapes and terminates the consumer thread. Reproduced:

```
events delivered to the healthy handler: []
event thread still alive? False
```

Two things make this worse than it first looks. The healthy handler received **nothing** — not
even the first event — because the failing handler was registered first and aborted `_process`
before it ran. And **`put()` keeps succeeding afterwards**: the queue accepts events, no
exception reaches any caller, and the process stays up. The system looks alive and is completely
deaf.

In fairness, vnpy's own strategy engines wrap their handlers in `try/except`, so users are
partly protected by convention — but **the bus itself offers no isolation**, and convention is
not a guarantee.

Two more, from reading:

- **The queue is unbounded** (`Queue()` with no `maxsize`). A slow consumer grows memory without
  limit. Our python rules already require *"bounded queues with an explicit overflow policy"*.
- **Handler lists are mutated while being iterated.** `register`/`unregister` append to and
  remove from `self._handlers[type]` from other threads while `_process` iterates that same list
  directly rather than a snapshot.

**A32 — if we build an event bus for Phase 7: isolate exceptions per handler, bound the queue
with a stated overflow policy, iterate a snapshot of the handler list, and make a dead bus
loud.** The last clause matters most: a silently deaf trading system is strictly worse than one
that crashes, and it is exactly the class of failure A11 exists to catch.

## 12.3 The OMS as a projection — the pattern Phase 7 should copy

`OmsEngine` keeps one dict per entity (`ticks`, `orders`, `trades`, `positions`, `accounts`,
`contracts`, `quotes`), all rebuilt purely from broker events, plus:

```python
self.active_orders: dict[str, OrderData] = {}
...
if order.is_active():
    self.active_orders[order.vt_orderid] = order
elif order.vt_orderid in self.active_orders:
    self.active_orders.pop(order.vt_orderid)
```

Three properties worth stealing:

- **The OMS is a *projection* of the event stream, never an independent source of truth.** State
  is derived, so it can always be rebuilt by replaying events — which is what makes
  reconciliation tractable.
- **"Live order" has exactly one definition** — `OrderData.is_active()` — and the active set is
  maintained as a *side effect* of each order event rather than recomputed by scanning. Every
  consumer reads `active_orders`; nobody re-derives the predicate.
- **Ids are gateway-namespaced** (`vt_orderid = f"{gateway}.{orderid}"`), because raw broker
  order ids collide across brokers.

**A33 — Phase 7's OMS should be a projection with a single `is_active()` predicate and one
maintained active set.** We have already been bitten by the inverse: our memory records that
*"`signals.status` is a lifecycle field the sweeper overwrites, so it cannot carry provenance"* —
a mutable status column doing double duty as durable fact. The projection pattern is the clean
separation: immutable events in, derived views out.

## 12.4 Notification is a core engine primitive — third independent hit

`send_notification` is a method on `MainEngine` itself, fanning out to every configured channel
with a default timestamped subject:

```python
def send_notification(self, content: str, subject: str | None = None) -> None:
    if subject is None:
        subject = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email_engine.send_email(subject, content)
    wechat_engine.send_wechat(f"{subject}\n{content}")
```

Any component holding the main engine can notify without knowing which channels exist. Its
transport layer also sets an explicit timeout on every HTTP call and catches `Timeout` separately
from `RequestException` — the transport form of **A28**'s retryable classification.

**This is the third independent repo to treat multi-channel push as a first-class primitive**
(repo 4's Telegram notifier with a noise policy, repo 9's multi-channel dispatcher, now vnpy's
engine method). By lesson 9 — *two independent projects hitting the same thing makes it
near-certain for us* — **A11 is no longer a suggestion; three mature systems independently
concluded that an unattended trading system must be able to speak.**

## 12.5 Packaging: core, gateways and apps as separate installables

The core ships neither a broker adapter nor a strategy engine. That forces the gateway interface
to be a real contract rather than an accident of the first implementation, and it is why vnpy
supports dozens of brokers without core changes.

We will have one broker (Kite) for the foreseeable future, so **splitting packages would be
premature** — but the *discipline* transfers: Phase 7's `BrokerAdapter` should be defined as an
interface a second broker could implement, even while only one does. That is the cheapest
available insurance against a Kite-shaped abstraction leaking through the whole execution path.

## 12.6 Verdict

**Read before Phase 7 — and, uniquely in this log, MIT means we could vendor rather than
reimplement** if a piece fits. Nothing here is adoptable as-is (Qt UI, CTP/China futures
semantics, threads where we are async), but three patterns are:

- **The bus is small** (145 lines) — plus **A32**, the three robustness gaps I reproduced in it.
- **The OMS is a projection** with one `is_active()` predicate (**A33**).
- **A timer event as the single scheduling primitive** — one mechanism for every periodic job.

And its clearest contribution is negative evidence in our favour: the part of Phase 7 we have
been treating as daunting infrastructure turns out to be a small, well-understood component.
**The risk in Phase 7 was never the event bus; it is the order lifecycle and reconciliation**,
which repos 4 and 6A already showed cost 82 defects and 543 tests respectively to get right.

---

# 13. awesome-quant — `wilsonfreitas/awesome-quant`

Reviewed 2026-09-03. A **curated list**, not a codebase — so there is nothing to audit and the
review shape is different: mine it for candidates, cross-check against our existing
`docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` (which concluded *adopt none as dependencies*), and
report only what is genuinely new. Actively maintained — last commit the day before review, with
a daily CI cron that re-parses the list, enriches it with GitHub stars and last-commit dates, and
regenerates a static site.

Most of its ~777 lines are irrelevant to us (crypto, R, FX, fixed income, US-market tooling).
Three findings survive.

## 13.1 ★ The best find: purpose-built anti-overfitting audit tools

Two entries in its **Factor Analysis** section are, essentially, the checklist this entire review
log has been applying by hand — packaged as libraries:

> **Lacuna** — *"Engine-agnostic quantitative research validation for detecting **leakage,
> overfitting, fragile results, unrealistic costs, and missing point-in-time evidence**."*

> **Perception-XAlpha Lite** — *"Backtest-overfitting audit for factor research: **CSCV
> probability of backtest overfitting, deflated Sharpe against the declared trial count, White's
> Reality Check, point-in-time universe membership and disclosure-date alignment.** Ships a worked
> example in which **24 pure-noise series produce a 1.11 Sharpe and the audit says so.**"*

That second description maps onto our situation almost line by line:

| Their check | Our state |
|---|---|
| Deflated Sharpe **against the declared trial count** | We built DSR on 2026-09-03 — and its known weakness is that **we hand-pick the trial count** (we assumed 20). U4 was meant to make it observed. |
| **CSCV** probability of backtest overfitting | We don't have it. A genuine complement to DSR — different test, same question. |
| White's Reality Check | We don't have it. |
| **Point-in-time universe membership** | Exactly the survivorship failure I found in repo 5. |
| **Disclosure-date alignment** | Exactly qlib's T1, and exactly what MCE 5b will need. |

**H8 — the negative control, and it is the single best idea in this repo.** Their worked example
feeds **pure noise** through the audit and shows it producing a 1.11 Sharpe, with the audit
correctly rejecting it. That is a *test of the test*: proof that your overfitting detector
actually fires.

**We should do exactly this to our own deflated-Sharpe bar.** Generate N pure-noise "gates" —
random partitions of the real trade set with no predictive content — run them through the same
`deflated_sharpe.py` path our real gates use, and assert the bar rejects them. If a noise gate
clears our bar, the bar is broken and every readiness banner built on it is worthless. This is
cheap (the machinery already exists), it is a genuine test rather than an argument, and it
directly addresses the thing that has bitten us twice: **promoting on evidence that looked
sufficient.** Our own rule already says a metric that cannot come out badly is not a metric —
this is the same principle applied to the bar itself.

**H9 (research pointer, not queued work)** — CSCV/PBO and White's Reality Check as complements to
DSR, and `mlfinlab`'s **meta-labeling**, which our e-book review already identified as *"our
overlay pattern"* under a different name. Worth a look when the post-watch-mode research queue is
next opened, not before.

## 13.2 Calendar: we are ahead, but our warning is too quiet

The **Calendars & Market Hours** section lists `exchange_calendars` (which qlib uses, and which
ships an **XNSE** calendar) and `pandas_market_calendars`. Worth checking ours against:

Our `app/services/market_calendar.py` is, on inspection, **better than adopting either** —
because of how it sources the past:

> *"the table is seeded from bhavcopy session gaps (past, ground truth) plus published NSE
> circulars (future)."*

Deriving historical holidays from **observed** bhavcopy gaps is ground truth; a published
library's historical list can be wrong and you would never know. We should not replace that.

But the same docstring names the weakness:

> *"Queries beyond the last seeded holiday log a WARNING and fall back to weekday arithmetic —
> add the new year's circular via the admin endpoint when NSE publishes it."*

**A36 — alarm on calendar coverage expiry, don't just warn at query time.** This is the same
pattern this log keeps surfacing: a degradation that is technically announced and practically
invisible. A passive WARNING inside a query is seen by nobody; what is needed is a proactive
"the NSE calendar covers only to `<date>` — N trading days remain" notification (A11), plus a
cheap second opinion by cross-checking upcoming dates against `exchange_calendars`' XNSE. Note
repo 6A solved the same problem a third way — a `scripts/update_nse_holidays.py` refresh plus a
versioned `nse_holidays_2026.json`. Three approaches to one problem; ours has the best data and
the weakest alarm.

## 13.3 Workbench: a markdown list with a test suite

Unusually, the list ships `tests/` — `test_readme_entries.py`, `test_url_probe.py`,
`test_audit_readme.py` — validating entry format, resolving URLs, and detecting dead or archived
projects. Two test names are worth stealing outright:

**T7 — `test_all_finding_kinds_are_mapped_and_sorted_deterministically`.** A test asserting that
the complete set of enum variants is exhaustively mapped and deterministically ordered — so
**adding a new variant without handling it fails the suite.** We have exactly this exposure, and
we have already been burned by it: our review round found *"v1's `unassessed` tripwire was
IMAGINARY — 3 of 8 modes passed"*, which is precisely an enumeration that was not exhaustively
handled with no test to catch it. Gate modes (`off`/`shadow`/`active`), rejection reasons and
sidecar readiness states all want this test.

**`test_api_error_fails_closed`** — the same principle as repo 9's phase resolver and qlib's PIT
`NaN`. **Third independent appearance of "fails closed" as an explicitly named, tested
behaviour**, which is why it is lesson 10.

Its `CLAUDE.md` is a clean, ordinary example of the genre — pipeline description, commands,
architecture — with nothing our own doesn't already do better. Its PR-review automation
(`test_pr_review_workflow.py`) is real but irrelevant to a solo repo.

## 13.4 Verdict

**Adopt nothing; it confirms our existing external-libs review.** Its value is discovery, and it
delivered one item worth real work — **H8, the noise negative-control against our own
deflated-Sharpe bar** — plus **A36** and **T7**, and a research pointer at CSCV/PBO and
meta-labeling.

The meta-observation: a list like this is the correct *first* stop for a question like "does a
tool already exist for the bar I am about to hand-build?" We built the deflated-Sharpe bar from
first principles on 2026-09-03; two libraries in this list already implement it alongside three
tests we do not have. **That does not mean we should have used them** — ours is stdlib-only and
wired into our own evidence path, which is worth a great deal — but it does mean the *design*
could have been informed for free, and the negative-control idea would have arrived a week
earlier.

---

# 14. AKShare — `akfamily/akshare`

Reviewed 2026-09-03. MIT. **~103,000 LOC across 406 modules** — a very large collection of
data-source wrappers for Chinese markets (plus macro, futures, options, funds, and a long tail
of non-financial series). It is the free data source that both repo 5 and repo 9 lean on.

**Verdict up front: adopt nothing from the data layer, take one testing idea that is better than
anything we have for a problem we actually have.**

## 14.1 Why the data layer is not for us

Three checks, all negative:

- **India coverage is incidental.** Grepping for India/Nifty/Sensex returns global-index and
  macro modules (`index_global_em.py`, `macro_bank.py`) and a rich-list scraper. There is nothing
  resembling NSE equity, corporate actions or F&O data. We have Kite plus the NSE bhavcopy and
  indices CSVs; this adds nothing.
- **The resilience story is thin.** **314 modules issue HTTP requests; only 13 mention retry,
  backoff or rate-limiting at all** — about 4%. Most wrappers are a bare `requests.get` against a
  public endpoint. So it is not a model for hardening our own ingestion, and repo 9's own
  disclaimer about free sources being *"subject to upstream throttling, interface changes and
  network volatility"* is well earned.
- Our `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` already settled the data-source question.

## 14.2 ★ How do you test 400 scrapers? You don't — you test the contract

This is the interesting part, and it is a genuinely good answer to a hard problem. You cannot
unit-test a thousand scrapers against live public endpoints — CI would be permanently red
through no fault of the code. So AKShare tests the **contract surface** instead:

`akshare/data/interfaces.json` is a machine-readable record for every public data function —
name, module, category, description, a runnable example, a rate/limit note, and **the full output
schema (column names and dtypes)**. The suite then pins properties of that registry rather than
the network:

```
test_every_registry_entry_is_reachable
test_collect_exports_maps_name_to_module
test_collect_all_names_excludes_dunder_and_third_party
test_interface_info_unknown_name_suggests_candidates
```

**T8 — the self-cleaning baseline, and it is the best idea in this repo.** Five tests govern how
known debt is allowed to exist:

```
test_baseline_allows_known_gaps        # legacy debt does not make CI red
test_baseline_rejects_new_orphan       # …but new debt does
test_baseline_rejects_new_undocumented
test_baseline_rejects_stale_entry      # …and so does a baseline entry that is out of date
test_baseline_rejects_fixed_orphan     # …and so does one you have already FIXED
```

The last two are what make it work. Most "known failures" allowlists rot: items get fixed but
stay on the list forever, so the list stops meaning anything and eventually suppresses real
regressions. **This one fails the build when a baseline entry is no longer a problem** — so the
list can only shrink, and fixing something forces you to remove it. A ratchet, not an amnesty.

We have exactly this shape of problem and no mechanism for it: legacy gaps we do not want to
block on (`make typecheck` historically not covering `scripts/`, `STATUS.html` prose that
duplicates gate modes), but which we also must not silently grow.

**T9 — turn the doc-sync ritual into failing tests. This is the finding that matters most.**
They test their release and documentation consistency mechanically:

```
test_collect_problems_detects_missing_changelog_entry
test_collect_problems_detects_missing_init_history
test_collect_problems_detects_tag_version_mismatch
test_collect_problems_passes_when_all_aligned
test_collect_problems_reports_every_problem_at_once
```

**Our doc-sync ritual is a procedure Claude has to remember to run at the end of every task. Theirs
is a test that fails.** And our own hard-won lesson says precisely why that matters: *"a documented
safety net is worth nothing without a test that fails when it lapses"* — the conclusion we drew
when the `unassessed` tripwire turned out to be imaginary. **We applied that lesson to our code
and never applied it to our process.**

Concretely, three of our ritual's seven steps are mechanically checkable today:

- a test that fails when a new `settings.*` entry has no `.env.example` line (this is **W3**,
  promoted from a rule to a test);
- a test that fails when `docs/PHASES.md`'s `(updated <date>)` stamp is older than the newest
  change to a `docs/phases/*.md`;
- a test that fails when a gate mode named in `STATUS.html` disagrees with `settings` — the exact
  drift our own memory warns about (*"it HARDCODES gate modes in prose + an ASCII diagram, so a
  mode flip silently falsifies it, so grep the gate name on every flip"*). **That "so grep it"
  instruction is a human ritual standing in for a test.**

Small companion idea worth taking: `test_collect_problems_reports_every_problem_at_once` — the
checker returns **all** violations in one run rather than failing on the first, so a drift sweep
is one pass instead of N.

## 14.3 A declared output schema per interface

Every entry in `interfaces.json` carries its output columns and dtypes. That is a heavier
discipline than we need for a handful of data providers — but the *idea* lands on a defect we
have already had: our review round found that **`unknown` was a returned-but-unrendered field
with zero consumers**, i.e. a contract entry nothing used. A declared, tested interface record is
how that gets caught rather than noticed later by a reviewer.

Filed as a note against **U8/A7** (artifact provenance) rather than a new item: the principle is
the same — a field, number or file that cannot name its producer or its consumer should not be in
the contract.

## 14.4 Verdict

**Adopt no code and no dependency.** The data layer is China-specific with thin resilience, and
we have already settled that question elsewhere.

**Take T8 and T9.** They are the answer to a problem this project genuinely has: our process
discipline — the doc-sync ritual, the review calendar, the "grep the gate name on every flip"
instruction — is entirely dependent on an agent remembering to perform it. AKShare shows the
alternative: **make the ritual a test, and let the debt list shrink monotonically.**

That is also the cleanest available response to the standing risk in this whole document. Fourteen
repos in, the most repeated finding is *a guard that cannot fail* — and our own most repeated
process risk is *a ritual nobody is forced to run*. They have the same fix.

---

# 15. Zipline — `quantopian/zipline`

Reviewed 2026-09-03. Apache 2.0, **~65,000 LOC**, **last commit 2020-10-14** — archived when
Quantopian shut down. The maintained successor is `zipline-reloaded` (stefan-jansen), which
appeared in repo 12's list.

Archived, but this is the **ancestor of the entire modern Python backtesting lineage** — it
spawned `trading_calendars` → `exchange_calendars` (which qlib uses), `alphalens`, `pyfolio` and
`empyrical`. It is worth reading for its architecture, not its code, and it contains **the single
best structural idea in this whole log.**

## 15.1 ★ Look-ahead is not forbidden — it is *not expressible*

A Zipline strategy never receives data. It receives a `BarData` object constructed with a
`simulation_dt_func`:

```python
def __init__(self, data_portal, simulation_dt_func, data_frequency,
             trading_calendar, restrictions, universe_func=None):
    self.simulation_dt_func = simulation_dt_func
```

Every accessor — `current()`, `history()`, `can_trade()` — resolves through
`_get_current_minute()`, which asks the simulation clock what "now" is and then queries the data
portal *as of that instant*. **There is no API through which a strategy can request a future
bar.**

That is a categorically stronger guarantee than everything else in this document. Across fifteen
repos I have found look-ahead as: a commented-out holdout (repo 2), same-bar execution (repo 5), a
scaler fit over the test window (repo 7). Each was a *mistake someone could make*. Zipline's
design removes the possibility — the mistake has no syntax.

Two refinements worth noting:

- **`before_trading_start` sets `_adjust_minutes = True`**, so during the pre-market hook "current"
  resolves to the *previous* market minute — because today's bar does not exist yet. **This is the
  second world-class implementation in this log to conclude that the current bar depends on which
  session phase you are in** (repo 9's `premarket` / `closing_auction` / `postmarket` resolver was
  the first). Two independent arrivals at the same design is the strongest signal available here.
- Daily mode maps the minute to a session label through the trading calendar, so daily and minute
  simulations share one clock abstraction rather than forking the logic.

For us the lesson is a design *stance*, not a port: our engine is frozen and our rules already
say "compute on candle N, valid from N+1". But those are rules a reviewer enforces. **Where we
build new evaluation surfaces — the MCE fundamentals path (5b), the sidecar cohort queries — the
cheaper guarantee is an accessor bound to an "as of" timestamp, so the wrong query cannot be
written.** That is the same instinct as qlib's `P($$field)` PIT syntax (T1), arrived at from the
other direction.

## 15.2 ★★ Restrictions as a composable, point-in-time interface — this reshapes A30

`zipline/finance/asset_restrictions.py`:

```python
class Restrictions(ABC)          # is_restricted(assets, dt)
class NoRestrictions
class StaticRestrictions          # a fixed set
class HistoricalRestrictions      # restrictions that VARY OVER TIME
class SecurityListRestrictions
class _UnionRestrictions          # compose several sources into one
```

…and `restrictions.is_restricted` is wired into `BarData` itself, so `can_trade()` — the question
the *strategy* asks — already knows.

**This is a better architecture than what I recommended in A30, and it unifies three of our open
items.** I had suggested "enforce circuit bands in the backtest, as the order path already does".
That is the right goal and the wrong shape. The right shape is:

> **One composable, point-in-time `Restrictions` interface that the backtest, the paper order path
> and the display path all consult** — with each of our tradability rules as a *source*: T2T/-BE
> exclusions, circuit-band proximity, liquidity, market-hours/`allow_offmarket_entry`, and the
> gate modes.

Two properties make it worth the refactor:

- **`HistoricalRestrictions` is point-in-time.** A backtest asks "was this restricted *on that
  date*", which is the only correct question — and the one our backtest cannot currently ask at
  all.
- **`_UnionRestrictions` composes.** We already have restriction logic in at least three places
  (`eligibility.py` for display, the order-path gates, `circuit_guard`), and our own review found
  the cost of that fragmentation: **41 of 204 rows offered a Buy that could only 409**, and five
  separate Buy surfaces needed retrofitting. A composed interface is the structural fix, not
  another synchronisation ritual.

Filed as **A38**, superseding A30's *implementation* while keeping its goal. It also subsumes the
A31 concern for this class of constraint: with one interface, a new restriction lands on every
path by construction rather than by remembering.

## 15.3 Fills are capped by bar volume, with quadratic impact

`VolumeShareSlippage`:

```python
DEFAULT_EQUITY_VOLUME_SLIPPAGE_BAR_LIMIT = 0.025   # you may fill at most 2.5% of the bar's volume
price * (1 + price_impact * (volume_share ** 2))   # impact is QUADRATIC in your share
```

Excess spills to the next bar or is cancelled; over-large orders raise `LiquidityExceeded`.

**We have no participation cap.** Our 6.8.2 model uses the real half-spread plus a
size-vs-top-of-book impact term, which is good — but nothing limits an order to a fraction of the
day's traded volume. Our notional cap bounds a position in **rupees**, not relative to the
stock's **liquidity**.

That gap has a name in our own history: **SRTL — a ₹39 micro-cap, 2,666 shares, −₹3.5k.** The
diversity gate now blocks that entry for a different reason (single-factor), but the *fill* would
still have been modelled as free. A ₹1L position in a stock trading ₹5L a day is 20% of daily
volume and is not fillable at the quoted price.

**A37 — cap paper and backtest fills at a fraction of the bar's traded volume, with impact rising
faster than linearly above a threshold.** We already ingest volume. This is the model behind
qlib's T3 test, and it is what makes a thin-stock backtest honest.

## 15.4 A shipped test-support package — and `ExplodingObject`

`zipline/testing/` is part of the library: fakes (`FakeDataPortal`, `MockDailyBarReader`),
temp-resource fixtures (`tmp_asset_finder`, `tmp_dir`), composable `With*` mixins, and two
diagnostic objects worth taking outright:

```python
class ExplodingObject          # raises UnexpectedAttributeAccess on ANY attribute access
class UnexpectedAttributeAccess
```

**T10 — negative-space assertions.** You inject an `ExplodingObject` where a dependency must
*never* be touched; if the code touches it, the test fails loudly. It proves a code path does
**not** use something — which is normally the hardest kind of property to test.

We have at least three claims of exactly this shape currently held by convention and review:

- **"frozen engine untouched"** — every overlay (`regime_guard`, `circuit_guard`, `entry_quality`,
  `sector_rs`) asserts it does not touch `app/analysis/`.
- **`circuit_guard` "only READS the cache, fail-open"** — it must never write.
- **Overlays must not see future data** — the same property Zipline enforces architecturally.

Each is a documented safety net with no test that fails when it lapses — which is precisely the
failure mode we already named when the `unassessed` tripwire turned out to be imaginary.
`ExplodingObject` is roughly fifteen lines and turns all three into mechanical checks.

## 15.5 Verdict

**Adopt no code** — archived five years, Cython, US-equity-shaped, and superseded by
`zipline-reloaded`. But architecturally this is the most valuable repo in the log after qlib, and
it contributes three items:

- **A38** — a composable, point-in-time `Restrictions` interface consulted by every path.
  **Supersedes A30 and unifies our fragmented eligibility logic.**
- **A37** — a volume-participation cap on fills, aimed at exactly the SRTL-shaped trade.
- **T10** — `ExplodingObject` negative-space assertions for our three "must never touch" claims.

And one stance worth internalising: **the strongest guarantee is the one that removes the syntax
for the mistake.** Fifteen repos have shown look-ahead entering through a comment, a same-bar
fill, and a scaler. Zipline is the only one where a strategy author *cannot* express it. Where we
are building new surfaces — MCE 5b above all — that is the bar to aim at.

---

# 16. abu (阿布量化) — `bbfamily/abu`

Reviewed 2026-09-03. **GPL-3.0**, ~56,000 LOC, last commit 2026-01. A Chinese quant framework
written as the companion codebase to a trading book, with lecture notebooks (`abupy_lecture`) and
a Jupyter-widget UI.

**Licence first: GPL-3 is a hard adoption blocker.** Every other repo in this log has been MIT or
Apache; copyleft means vendoring any of it would impose GPL obligations on our codebase. So this
is a *read-only* review regardless of merit — which is the right frame anyway, because the code
is 2017-era (Python 2/3 compat shims, old sklearn) and the value here is one idea, not any
implementation.

It makes **no performance claim** in its README — the seventh repo to decline, and the pattern
continues to hold.

## 16.1 The module decomposition is thoughtful

`abupy/` splits into `AlphaBu` (strategy) · `BetaBu` (portfolio) · **`FactorBuyBu` / `FactorSellBu`
(buy and sell factors as separate first-class plugin families)** · `PickStockBu` (selection) ·
`SlippageBu` · `MetricsBu` · `MLBu` · `TLineBu` · `SimilarBu` · **`UmpBu`**.

The buy/sell factor split is worth noting because it matches how we actually think: our own
central finding is that *the binding constraint is entry/regime selection, not exit logic*, and a
framework that treats entry and exit factors as distinct composable families makes that
distinction structural rather than incidental.

## 16.2 ★ UMP — "referees" that veto trades, i.e. meta-labeling in 2017

`UmpBu` is abu's signature idea (裁判 = *umpire/referee*), and it is a **two-tier learned veto
layer sitting on top of a primary signal**:

- **主裁 (Main referee)** — clusters historical trades on a feature set, identifies the clusters
  with the **highest failure probability**, and vetoes new trades falling into them. It then
  **saves candlestick snapshots of the worst cluster's trades**, so a human can *see* what the
  losing pattern looks like.
- **边裁 (Edge referee)** — a similarity/k-NN approach: pairwise distances between the candidate's
  feature vector and historical trades, filtered in two rounds
  (`K_DISTANCE_THRESHOLD = 0.668` → top `K_N_TOP_SEED = 100` seeds → `K_SIMILAR_THRESHOLD = 0.91`),
  after which the surviving similar historical trades **vote** on win/lose.

Both come in dimensions — **Deg** (trend angle), **Jump** (gaps), **Price**, **Wave**
(volatility), **Full**, **Mul** (combined) — separately for buy and for sell.

**This is meta-labeling, built years before López de Prado's book made the term standard.** It is
also, structurally, *precisely our overlay pattern*: a frozen primary engine plus a secondary
layer that permits or vetoes based on learned properties of past outcomes. Our reading review
already identified meta-labeling as "our overlay pattern" by another name; repo 12 pointed at
`mlfinlab`'s implementation. **This is the third independent arrival at the same idea, and the
only working implementation of it in this log.**

### Why it is genuinely interesting for us — and why it is dangerous

Our overlays are all **hypothesis-driven**: we posit that transitional ADX is bad, that R:R<1 is
bad, that single-factor entries are bad, and then test the posit. **Two of the three we tested
empirically were reverted** — and our own recorded lesson explains why: *the partition turned out
to be a proxy for something else* (market-regime → side; R:R<1 → wide stop).

abu inverts the direction: **don't guess the partition — cluster the actual losers and let the
clusters define the veto.** That directly attacks the failure mode that has cost us twice.

But it is also, unmistakably, **an overfitting machine.** Clustering your own losing trades and
then vetoing those clusters will *always* look good in-sample; it is the purest possible form of
fitting to the sample. With 99 trades and a −0.303R book, a loser-clustering veto would produce a
beautiful backtest and mean nothing.

So the honest framing, and the reason this is a **research** item rather than a build item:

> **H10 — loser-cluster meta-labeling is worth testing, but only behind the full bar we have
> already built**: the deflated-Sharpe bar with an honest trial count (every cluster configuration
> tried is a trial), MinTRL for the sample size, **and H8's noise negative control** — because a
> method this prone to fitting is exactly the case the negative control exists to catch. Without
> those, it is the most dangerous idea in this document.

Note also its magic constants (`0.668`, `0.91`, `100`) arrive with no derivation — the same
fitted-threshold problem flagged in repo 5. If we ever tried this, those become hyperparameters,
and every one of them multiplies the trial count.

### One idea we can take immediately

**U20 — render the would-block cohort visually.** abu saves candlestick snapshots of the
highest-failure cluster so a human can look at what the model learned. Our shadow sidecars report
that a gate *"would block these 44 trades"* as statistics — expectancy, win rate, DSR — and
**nobody has ever looked at those trades as a set of charts.**

That is a real gap, and cheap to close. When the regime gate was refuted, it was refuted
numerically; a contact sheet of the suppressed entries might have shown *why* far faster, and
would have surfaced the "proxy for side" problem visually rather than after the fact. It also
pairs with U17 (distribution, not scalar) and U10/U15 (the arithmetic and the named evidence):
statistics say whether, charts say what.

## 16.3 Verdict

**Adopt nothing — GPL-3 settles it before age or quality enter the discussion.**

Two items harvested, one for the research queue and one for the UI queue:

- **H10** — loser-cluster meta-labeling as a *candidate* methodology that attacks our
  hypothesis-driven-partition failure mode, gated behind DSR + MinTRL + **H8's negative control**.
  Interesting and dangerous in equal measure; explicitly not a build item.
- **U20** — render the would-block cohort as charts in the shadow sidecars, because we have been
  judging suppressed trade sets numerically and never looking at them.

And a smaller observation worth keeping: **three independent sources have now pointed at
meta-labeling** — our own e-book review, repo 12's `mlfinlab` entry, and this working
implementation. By the two-independent-hits rule that has served well through this log, it
deserves a place on the post-watch-mode research queue rather than continuing to surface
accidentally.

---

# 17. turbovec — `RyanCodrai/turbovec`

Reviewed 2026-09-03. MIT, ~39,600 LOC Rust + Python bindings. **Not a trading repo** — it is a
quantized vector-search index (Google Research's TurboQuant) for RAG and embedding search.

**The honest answer to "is it useful by any chance": no on the domain, yes on one small thing.**

## 17.1 The domain is not ours, and I am not going to manufacture a use

We have no embedding corpus, no RAG, and no similarity search anywhere in the stack. The only
conceivable hook is "find similar historical trades", which is exactly abu's Edge referee from
§16 — and there the bottleneck is **statistical validity, not search speed.** At n≈99 trades you
compute pairwise distances in numpy, as abu does. A quantized ANN index that exists to fit 10
million vectors in 4 GB has nothing to offer a hundred rows.

Filed as **considered and rejected**, deliberately, because the more useful discipline at this
point in the log is refusing to stretch for relevance.

## 17.2 ★ But its supply-chain gate found the log's #1 defect in its own CI

The genuinely valuable thing is `deny.toml` — a **cargo-deny** configuration, enforced by a
`supply-chain.yml` workflow, auditing RustSec advisories, banned crates and sources. Its comment
is the best worked example of this document's most repeated finding:

> *`supply-chain.yml` advertises this gate as "RustSec vulnerabilities + yanked crates", but
> cargo-deny **defaults `yanked` to Warn** and `cargo deny check` **only exits non-zero on
> Deny-level findings** — so **a yanked dependency produced a warning and a green run (#491)**. A
> yank is the registry telling us not to use a version; treat it as blocking.*
> ```toml
> yanked = "deny"
> ```

**A guard that could not fail, caught in the wild, with the issue number cited.** The gate was
true in intent and false in effect, purely because a tool's default severity made it
non-blocking. That is lesson 2 of this log — *a guard that cannot return false* — in its most
instructive form, because nothing in the code was wrong: the *configuration default* was.

Their `ignore` list also carries the **T8 ratchet discipline** without needing a test to enforce
it: *"Keep this list tight and documented — every entry is a consciously accepted residual"*, with
each entry giving the advisory ID, why it is accepted, the PR that accepted it, and the condition
to revisit.

**A39 — we have no supply-chain gate on `engine/` at all.** Our Rust rules specify
`cargo fmt --check`, `cargo clippy -- -D warnings` and `cargo test`; there is no advisory scan and
no licence audit. We ship a compiled wheel (`tradecore`) that runs options math **on the money
path**, built from a dependency graph nobody audits. `cargo-deny` is a config file and a CI step,
and this repo hands us the two settings that make it real: **`yanked = "deny"`**, and a documented
ignore list where every entry is a dated, justified, revisitable exception.

*(Their `.claude/` holds only a `bgIsolation` setting and a plain-English summarise skill —
nothing we need.)*

## 17.3 Verdict

**Reject the library; take `A39`.** The domain is irrelevant to us and saying so plainly is the
correct outcome — but the repo happens to demonstrate, on itself, the exact failure this log has
now catalogued three times in code and once in tooling. That was worth the ten minutes.

It also answers the implicit question well: **a non-trading repo can be worth reviewing, but for
its engineering practice rather than its subject** — and the filter is whether it shares a *stack*
or a *discipline* with us, not whether it shares a domain. This one shares our Rust + PyO3 wheel
shape, which is why the supply-chain finding transferred and nothing else did.

---

# 18. QuantDinger — `OpenByteInc/QuantDinger`

Reviewed 2026-09-03. **Apache 2.0**, ~177,600 LOC, 803 files, **last commit the day of review** —
a commercially backed open-source "AI Trading OS" from Open Byte Inc.

**The closest product-shaped analogue to our platform in the entire log, on nearly our stack**:
Python 3.12, PostgreSQL, Redis, Docker Compose, and the same end-to-end scope — *research →
strategy code → backtest → paper → live execution → monitoring*. It makes **no performance
claim**, the eighth repo to decline.

Because it is scope-for-scope comparable, the useful findings are the pieces we have not built:
its agent surface, its observability, and two design choices we can check ourselves against.

## 18.1 ★ Its MCP server is the best security model in the log for exposing a platform to an agent

**This is the most directly relevant workbench artifact reviewed**, because we *are* a Claude Code
shop — we already drive `make analysis` through skills — and this is what "expose the trading
platform to an agent" looks like done carefully.

> *"The MCP server is a thin, tenant-scoped wrapper over `/api/agent/v1`."*

Seven design decisions worth copying wholesale:

1. **The agent gets an API, not the internals.** `app/routes/agent_v1` is a *separate, versioned
   surface*; the MCP server is a thin wrapper over it rather than a second implementation reaching
   into services or the DB.
2. **Read and write scopes are tabulated per tool group** (`R` vs `R/W`), so the blast radius of
   each tool is visible in the docs rather than inferred from code.
3. **Trading tools are separately "safety-gated"** — the dangerous surface is called out as its own
   category.
4. **Two distinct tokens, and the docs say why**: `QUANTDINGER_AGENT_TOKEN` (upstream, to the
   gateway) and `QUANTDINGER_MCP_AUTH_TOKEN` (inbound, authenticating MCP clients) — *"must not be
   the Agent Gateway token."* Separating inbound auth from upstream auth is routinely got wrong.
5. **Transport security fails closed.** Non-loopback binding *requires* an inbound token;
   authenticated non-loopback listeners *require* HTTPS. The two escape hatches
   (`ALLOW_HTTP`, `ALLOW_INSECURE_HTTP`) are separately named, separately scoped and documented
   with *"never use either on a directly reachable public listener."* **Fails-closed by default
   with named, justified exceptions** — the same discipline as repo 16's `deny.toml` ignore list.
6. **Agent-specific credential hygiene**: *"Never place an agent token in prompts, logs,
   screenshots, source control, or MCP configuration that will be shared. Responses redact
   credential fields."* Secrets leaking through *prompts and screenshots* is a threat model
   specific to agent tooling, and most people never write it down.
7. **Every long-running job exposed to an agent is bounded** —
   `JOB_STREAM_MAX_EVENTS`, `JOB_STREAM_MAX_SECONDS`, `JOB_POLL_MAX_SECONDS`. That is the
   "bounded queue with an explicit overflow policy" principle applied to tool calls, and it
   prevents precisely the failure I found in repo 8: an agent hanging forever on a stream that
   never terminates.

**W6 — if we ever expose our platform over MCP, this is the model.** Not queued as work (we have
no such need today), but recorded so the design is not reinvented badly under time pressure. The
single most important line is (1): **the agent gets a dedicated versioned API, never the
internals.**

*(Also noted: its universe and factor tools are described as "point-in-time research inputs" —
the fourth repo in this log to treat PIT as first-class.)*

## 18.2 Observability: their alerts are infrastructural, ours are domain — we need both

A real stack, pinned to versions: Prometheus + Alertmanager + Grafana + a postgres exporter + **two
separate Redis exporters (cache and jobs)**. The alert rules:

```
QuantDingerApiDown                  up{job="quantdinger-api"} == 0            critical, for 2m
QuantDingerWorkerMissing            quantdinger_workers_healthy{...} < 1      critical, for 2m
QuantDingerHighApiErrorRate         error rate > 5%                           warning, for 5m
QuantDingerSlowApi                  p95 latency > 2s                          warning, for 10m
QuantDingerStrategyCommandFailures  strategy_commands{status="failed"} > 0    warning, for 5m
QuantDingerPostgres/RedisExporterDown                                         warning, for 3m
```

**Every one is about the platform; none is about the market.** There is no "no signals generated
today", no "feed stale", no "position unprotected", no "circuit breaker fired". That is a useful
contrast rather than a criticism: our 6.8.6 staleness alarm and readiness banners are exactly the
*domain* alerts they lack, and their infra alerts are exactly what we lack.

**A40 — export a worker-liveness metric and alert on it.** `quantdinger_workers_healthy{role=~
"trading|scheduler|celery"} < 1` for 2 minutes is precisely the alarm that would have caught our
two standing manual checks:

- **CAS capture** — `make worker` must be up 15:15–15:33 IST daily and **a missed window cannot be
  back-filled**; today the protocol is "check the row count each morning."
- **Provisional health** — no scheduler at all; "run the script yourself each session."

Both are worker-liveness problems dressed as human rituals. This strengthens **A11** rather than
replacing it: the notifier is the delivery channel, worker-liveness is one of the first things
worth delivering.

## 18.3 Separate Redis instances for cache and jobs

They run **two** Redis instances — `redis-cache` and `redis-jobs` — each with its own exporter.
We run one Redis with logical DBs (0 for dev, 15 for tests).

That distinction is not cosmetic. Our own Redis contract documents the workaround we adopted
because the two concerns share an instance:

> *"Every cache key gets a TTL — eviction policy is volatile-lru, so TTL-less keys are treated as
> broker-critical and never evicted."*

That rule exists because volatile cache (`ltp:`, `depth:`, `circuit:`) and things that must not be
lost live under one eviction policy. **Two instances with different policies — `volatile-lru` for
cache, `noeviction` for jobs/durable — removes the conflict rather than documenting around it.**

Filed as **A41**, low priority: our current rule works and is well understood, and this is a
deployment change with real ops cost. Worth doing if we ever add durable queues (Phase 7's repair
queue is exactly that shape).

## 18.4 A multi-timeframe rule worth adopting as a review lens

Buried in their strategy-authoring guidance:

> *"…use the **completed** higher timeframe as the requested confirmation and the fastest timeframe
> as the execution clock. Preserve whether the request means higher-timeframe **bullish alignment**
> (`fast > slow`) or a **fresh crossover event**; **do not silently substitute one meaning for the
> other.** Make low-timeframe order conditions **idempotent** so a persistent higher-timeframe
> state does not cause repeated scale-ins."*

Three correct things in one paragraph: the higher timeframe must be **completed** (no look-ahead
across timeframes); **state and event must not be conflated** ("is bullish" vs "just crossed");
and if a condition is a persistent *state*, the order path must be **idempotent** or it will
re-enter every cycle.

The state-vs-event distinction is a genuinely useful lens for reviewing our own overlays: **is
each gate asking about a state or a transition, and is that what we meant?** We have partial
protection already (`_has_active_signal` for regeneration, risk-first sizing so repeat entries
cannot stack past the budget), so this is a review question rather than a suspected bug — but it
is the kind of question that has caught us before, since our two reverted gates both failed on
*what the partition actually meant*.

## 18.5 Verdict

**Adopt no code** — different market coverage, its own strategy DSL, and a product surface far
wider than ours. But it is the most useful *comparative* repo in the log, because it is the same
shape of thing we are building and it is honest (no performance claims, real observability,
Apache-2).

Three items: **W6** (the MCP exposure model — recorded, not queued), **A40** (worker-liveness
metric and alert, which converts two of our standing human rituals into an alarm), and **A41**
(split Redis by durability, low priority). Plus one review lens on state-vs-event in overlays.

---

# 19. QUANTAXIS — `yutiansut/QUANTAXIS`

Reviewed 2026-09-03. **MIT**, ~66,300 LOC, actively maintained (last commit 2026-09-01). A
long-running Chinese full-stack quant framework: data fetch, indicators, factors, backtest,
account/market simulation, scheduling, pub/sub, a web server, and **QIFI**.

**No performance claim — the ninth repo to decline**, and at this point the correlation is strong
enough to treat as a prior rather than an observation.

Most of its layers replicate patterns this log has already covered in better implementations —
`QAEngine`/`QAPubSub` against vnpy's event bus (§12), `QAFetch` against AKShare (§14),
`QAFactor`/`QAIndicator` against qlib (§10). I am not going to re-derive those. **One module is
genuinely distinctive and produces one queue item.**

## 19.1 QIFI — an account-state protocol, defined as a spec rather than a class

`QUANTAXIS/QIFI/` ships `qifi.md` (the specification), `qifi.sql` (the DDL) and
`QifiAccount.py` (one implementation). **QIFI is an interoperability protocol for representing an
account's complete state** — broker-agnostic, so different systems can exchange account snapshots.

Its account model separates four things our code treats as roughly one:

| QIFI field | Meaning |
|---|---|
| `pre_balance` | yesterday's closing balance |
| `static_balance` | the **settlement baseline** for today |
| `balance` | current value — static balance plus floating P&L |
| `money` | **available** cash — balance minus frozen minus margin |

…plus `frozen` (capital committed but not yet spent), `positions`, `orders`, `trades`, `banks`
(deposits/withdrawals) and `events`, with an explicit daily settlement roll:

```python
self.pre_balance += (self.deposit - self.withdraw + self.close_profit)
self.static_balance = self.pre_balance
```

Two observations.

**First, the vocabulary is right and reinforces a rule we already learned.** Repo 4's CLAUDE.md
records that *"the circuit-breaker baseline is **always** `last_equity`, not last night's DB
snapshot"* — QIFI is that distinction expressed as a schema rather than a convention. Our own
breaker computes from the IST calendar-day start, which is a sound baseline for our
paper-and-realized model, so there is no defect here; the value is the naming.

**Second, and this is the actionable one: we have no concept of frozen capital.** I checked —
every `frozen` in our codebase is `@dataclass(frozen=True)`. Cash committed to a *pending,
unfilled* order is not reserved anywhere.

Today that is harmless, because paper fills are immediate: there is no window in which an order is
outstanding. **Phase 7 removes that property.** With real pending orders at a broker, two orders
can each be sized against the same cash unless something reserves it — and this is precisely the
family of bug repo 4 documented from production:

> *a filter once treated `alloc=0` as a full sell and pre-deducted **phantom cash**, letting BUYs
> quietly borrow margin (2026-04-19).*

Same failure class: cash accounting that does not account for what is in flight.

**A42 — introduce `frozen` / available-cash accounting before Phase 7 places its first real
order.** Cheap to design now while the account model is small and paper-only; expensive to retrofit
once orders can sit unfilled. It pairs with A33 (the OMS as a projection with one `is_active()`
predicate) — the frozen amount is derivable from the active-order set, which is exactly why the
two belong in the same design pass.

## 19.2 One practice note

QIFI is published as **`qifi.md` (spec) + `qifi.sql` (schema) + implementation**, with the
protocol documented independently of any one codebase. That is the right shape for a contract
meant to outlive its first implementation — and it is the same instinct as AKShare's
`interfaces.json` (§14.3) and qlib's PIT field syntax (§10.1): **make the contract an artifact,
not an implementation detail.**

Not queue-worthy for a solo project with one consumer, but worth naming, because it is the third
independent appearance of that instinct in this log.

## 19.3 Verdict

**Adopt no code.** Most of the framework duplicates ground already covered better elsewhere in
this review, and the parts that don't are shaped around Chinese futures/equity settlement
mechanics that do not map to NSE.

**One item: A42, frozen-capital accounting, as a Phase 7 prerequisite.** Plus the ninth
confirmation that repos which decline to publish a performance number are the ones worth reading.

---

# 20. awesome-systematic-trading — `paperswithbacktest/awesome-systematic-trading`

Reviewed 2026-09-03. **No LICENSE file.** A curated list — 299 library rows, 61 showcased
strategies, 55 books, 22 videos, blogs and courses — updated the day of review.

**A note on method, because the ask was "dig deeply into each and every one":** I did not
individually review 299 libraries or 4,843 papers, and any claim that I had would be false. What I
did instead is worth more: **inventoried the whole list programmatically, computed the statistics
it does not compute for you, cross-checked it against the eighteen repos already reviewed here and
against our own open gaps, and kept only what changes something.** The result is three findings,
two of which are new queue items, and one of them re-frames how we should read every evidence
number we produce.

## 20.1 ★★ The replication record is the most valuable thing anyone has shared in this review

Buried above the fold, before the list itself:

> *We have coded and run **4,843** of these papers over their own full history.*
> - *The median replication returns a **Sharpe of 0.37**, and **48% clear a t-statistic of 1.96**.
>   **Half the published record cannot be distinguished from zero on its own sample.***
> - *Median test window **34 years**. A strategy needs roughly `(1.96 / Sharpe)²` years to prove
>   itself, so a Sharpe of 0.4 needs about **24** of them.*
> - *The median strategy carries a **beta of +0.17** to the S&P 500. Removing it takes the median
>   information ratio down to **0.21** — a meaningful slice of the published edge is index exposure
>   rather than skill.*
> - *Across 2,838 papers with a record on both sides of publication, **no measurable decay after
>   publication** once the market period is controlled for.*

This is an **empirical prior on the entire published systematic-trading literature**, produced by
actually running it. Three of the four facts land directly on open questions of ours.

### H11 — the sample-size reality check, and it is uncomfortable

`years ≈ (1.96 / Sharpe)²` is the same statement as our **MinTRL** in `deflated_sharpe.py`
("accrue until n ≈ X"), arrived at independently and expressed in a unit anyone can check:

| annualised Sharpe | years of daily data to reach t = 1.96 |
|---|---|
| 1.00 | ~4 |
| 0.60 | ~11 |
| **0.37** *(their median)* | **~28** |
| 0.20 | ~96 |

**Our gates are being judged on weeks.** The deflated-Sharpe read of 2026-09-03 put every gate's
eligible-set Sharpe *below* its 20-trial benchmark — market-regime −0.004, anti-chase +0.032,
sector-RS −0.105, liquidity −0.150 — on samples of 33 to 72 trades. This table says that even a
*genuinely good* published strategy needs decades to separate from zero.

I want to be precise rather than alarmist: their formula is for an **annualised Sharpe on a daily
return series**, and our gate evidence is **per-trade over a trade count**, which is exactly why we
built MinTRL instead of borrowing a years figure. The units do not transfer. **What transfers is
the shape: required sample scales with the inverse square of effect size**, so halving the edge
quadruples the evidence needed. Our edges are small, so our required samples are enormous, and
this is independent external confirmation of the thing that has already cost us two reverted gates.

**H11 is therefore not "adopt their formula" but "state the implied sample beside every readiness
banner"** — we already compute MinTRL; the missing move is to render it as the headline rather
than a footnote, so "n=44" is never read without "needs ≈N".

### H12 — we compute no beta, and a slice of any edge we find may be index exposure

*The median strategy carries a beta of +0.17; removing it takes the median information ratio to
0.21.* On their own numbers, **beta-stripping roughly halves the apparent edge of the median
published strategy.**

**We compute no beta and no information ratio anywhere.** Our cohorts are judged on raw expectancy
and raw per-trade Sharpe. If a would-block cohort happens to be long-biased in a rising market, its
"edge" is partly the market — and we would never see it.

This is our **H2/U2** finding (put the benchmark in the same table) generalised from the portfolio
level to the *cohort* level: not just "how did we do against NIFTY", but "how much of this gate's
apparent effect survives removing its index exposure". We already have the index bars
(`index_ohlcv_1d`, backfilled) and `benchmark.py` for per-signal alignment, so the inputs exist.

**H12 — add beta-to-NIFTY and an information ratio to every cohort evaluation.** It sits naturally
beside H1 (block-bootstrap p5) and H8 (the noise control) as the third robustness axis: **H1 asks
"is this stable?", H8 asks "does the bar reject noise?", H12 asks "is this just the market?"**

### The calibration, stated plainly

**Median published Sharpe 0.37. Half the literature cannot be distinguished from zero on its own
sample.** That is the yardstick — from 4,843 replications — against which our own expectations
should be set. It is also the most concrete answer available to the standing question of what
return rate is achievable: a *median good published strategy* is a 0.37 Sharpe that takes
~28 years to prove. Our position (−0.303R expectancy, measured honestly, on a book we are still
fixing) is early-stage, not anomalous — and the target of 2–3% a day is not on this distribution
at all.

## 20.2 The selection effect I found in its own presentation

I parsed the 61 showcased strategies and computed what the list does not:

| asset class | n | median Sharpe | max | median vol | median years |
|---|--:|--:|--:|--:|--:|
| Equities | 12 | **1.51** | 1.89 | 6.2% | 37 |
| Multi-asset | 12 | 1.23 | 1.62 | 6.9% | 37 |
| Currencies | 4 | 1.39 | 1.74 | 8.5% | 36 |
| Bonds | 12 | 0.62 | 0.90 | 6.0% | 36 |
| Commodities | 3 | 0.63 | 0.65 | 20.7% | 37 |
| Cryptocurrencies | 8 | 0.63 | 3.39 | 47.9% | 28 |
| Derivatives | 10 | 0.53 | 1.06 | 9.4% | 37 |
| **All showcased** | **61** | **1.06** | 3.39 | 8.6% | 37 |

**The showcased median is 1.06. The population median is 0.37.** The list displays roughly the
best 1.3% of what it has replicated, and a reader who skims the tables anchors on ~1.06 — nearly
three times the truth.

To be fair: **this is disclosed**, in the intro, above the tables, in plain language. That is more
honesty than any other list in this review. But it is the subtlest instance of this log's central
theme — **the selection effect had moved into the presentation layer**, where no code is wrong and
no claim is false, and the reader still ends up mis-calibrated. Our own equivalent risk is exact:
a readiness banner that shows the gates we are *watching* is a selected sample of the gates we
have *tried*, which is precisely why **U4** (a trials-attempted counter) exists.

## 20.3 Curation practice worth noting

**27 of 299 library rows carry a dated maintenance flag** — `` `dormant since 2024-02` ``,
`` `dormant since 2018-04` `` — inline with the entry rather than in a separate "deprecated"
section. Maintenance status as a dated annotation on the thing itself is better than a graveyard
list nobody reads, and it independently corroborates two calls made in this review: zipline
(*dormant since 2024-02*; §15 called it archived) and backtrader.

The books largely overlap our existing e-book review (López de Prado ×2, Jansen), so nothing new
there. The blogs are notable for what they are: **mostly engineering blogs from real firms** —
Jane Street, Hudson River Trading, Two Sigma, Man Group, Proof Engineering — rather than strategy
blogs. By this log's own lesson 8, that makes them the more credible reading: they have engineering
to describe and nothing to sell.

## 20.4 Verdict

**The single most useful source in this review**, and not for its links — for the four sentences of
replication record above them. Two queue items (**H11**, **H12**), one sharpened prior, and a
worked example of a selection effect surviving into a presentation layer that is otherwise honest.

The list itself I would **use as a lookup, not read** — 299 entries of which we have already
reviewed the relevant ones, and its own strategy tables point at a paywalled site. **The free,
durable value is the prior: median 0.37, half indistinguishable from zero, a fifth of the edge is
beta, and the sample you need grows with the square of how small your edge is.**

---

# 21. vectorbt — `polakowo/vectorbt`

Reviewed 2026-09-03. ~62,700 LOC. A vectorised backtesting library — fast, popular, and the
best-known member of its category.

**We have already decided this one.** `docs/EXTERNAL_LIBS_REVIEW_2026-08-02.md` concluded *adopt
none as dependencies*, singling out VectorBT as one that *"would REGRESS invariants"*. This
re-review does not re-litigate that; it **confirms it and supplies two sharper reasons**, one of
which is decisive on its own and was not in the original note.

## 21.1 ★ The licence is not open source, and it springs exactly when we would care

The README badge says "Fair Code"; the licence is **Apache 2.0 with the Commons Clause**. Verbatim:

> *the grant of rights under the License **will not include** … the right to **Sell** the
> Software. … "Sell" means … to provide to third parties, **for a fee or other consideration
> (including without limitation fees for hosting or consulting/support services)**, a product or
> service **whose value derives, entirely or substantially, from the functionality of the
> Software**.*

Set against the first line of our own CLAUDE.md:

> *Personal intelligent stock-suggestion + algo-trading platform for Indian markets (NSE/BSE).
> Solo developer, **personal use first, possible future productization**.*

So: **personal use today is fine** — the Commons Clause does not bite because nothing is being
sold. **Any future productization becomes a live legal problem**, and there is a paid
`vectorbt.pro`, which is precisely why the free edition carries the restriction.

**That makes it worse than a plain incompatible licence, because the trap only springs at
commercialisation** — the moment when the dependency is most deeply embedded and least removable.
Per lesson 16, licence decides before merit, and this decides it. Recorded because a future
session weighing vectorbt on technical grounds needs to hit this first.

## 21.2 The technical regression, now stated precisely

The original note said "regresses invariants" without saying which. It is **constraint #3** —
*compute on candle N, valid from N+1; backtest fills at N+1 open* — and the regression is in
**kind, not degree**.

vectorbt's own documentation is candid about where the responsibility sits:

```
base.py:2307   "...forward, for example, with `signals.vbt.fshift(1)`. In general,
                make sure to use a price..."
base.py:2649   "(for example, by using the closing price), otherwise you may expose
                yourself to a look-ahead bias."
```

Signals are computed **vectorised over the whole array**, then simulated. The simulation loop is
event-driven (its docs fairly claim *"less risk of exposure to look-ahead bias"* for that stage) —
but the **signal generation** has already seen every bar, and the default fill is the same bar. **A
correct backtest requires the user to remember `fshift(1)`.**

For us that converts a structural property into a convention. Our engine computes on completed
candles and our backtest fills at the next open *because it cannot do otherwise*; adopting a
framework where correctness depends on remembering a shift is a regression regardless of how fast
it runs.

## 21.3 ★ This closes the log's look-ahead thread with a clean spectrum

Across twenty-two repos, look-ahead has now been seen at every point on a single axis — and the
position on that axis predicted the outcome every time:

| Design | Look-ahead is… | Observed result |
|---|---|---|
| **Zipline** (§15) — `BarData` bound to the simulation clock, no API for a future bar | **not expressible** | no look-ahead possible |
| **qlib** (§10) — `P($$field)` PIT syntax; unknown phase → `None` | not expressible for PIT fields; **fails closed** | the most careful backtest layer reviewed |
| **daily_stock_analysis** (§9) — phase-aware entry-bar resolver, fails closed | prevented by resolution | correct |
| **vectorbt** (§21) — vectorised signals, same-bar fill by default, `fshift(1)` is the caller's job | **the default unless you remember** | documented, not prevented |
| **QuantHarness** (§2) — holdout is a commented-out line | one edit away | unverifiable results |
| **QuantAgents-NSE** (§5) — signal from the bar's close, filled at that close | **already happened** | +0.5pp "edge" that isn't real |

The bottom two rows are what the fourth row produces downstream. **Repo 5 is what using a
vectorised framework's defaults looks like when nobody remembers the shift** — and its author
almost certainly did not think of it as a choice.

This is the strongest available argument for **A38** (accessors bound to an "as-of" time) and
**T1** (a PIT test anchored to a real filing date): not that convention is unreliable in the
abstract, but that **we have now watched it fail, in this exact way, in two of twenty-two repos,
with a third documenting the trap it declines to remove.**

## 21.4 Verdict

**Reject — and the prior decision stands with better reasons.** Licence first: Commons Clause is
incompatible with our stated possible future productization, and it only bites once removal is
expensive. Technique second: it makes our single most important correctness invariant a matter of
caller discipline.

**No queue items.** The value of this re-review is a decision that now survives someone changing
their mind about the technical merits, plus the spectrum in §21.3 — which is the clearest statement
this document can make about *why* the design stance in A38/T1 is worth paying for.

---

# 22. QuantStats — `ranaroussi/quantstats`

Reviewed 2026-09-03. **Apache 2.0** (declared in `pyproject.toml`; no `LICENSE` file in the tree),
~12,300 LOC, **79 metric functions** in `stats.py`. The canonical portfolio-analytics / tearsheet
library, by the author of `yfinance`.

**This one paid off in an unusual direction: I used it to cross-check our own
`deflated_sharpe.py`, found two bugs in QuantStats, and confirmed ours is right.**

## 22.1 ★★ Cross-checking our PSR against theirs — and the kurtosis trap

We built PSR from first principles on 2026-09-03. QuantStats implements it too, which makes an
independent verification possible. Their formula:

```python
sigma_sr = sqrt((1 + 0.5*SR**2 - skew*SR + ((kurt - 3)/4)*SR**2) / (n - 1))
psr = norm.cdf((SR - rf) / sigma_sr)
```

Ours:

```python
denom_sq = 1.0 - m.skew * sr + ((m.kurtosis - 1.0) / 4.0) * sr**2
z = (sr - benchmark_sharpe) * math.sqrt(m.n - 1) / math.sqrt(denom_sq)
```

**Algebraically these are the same expression.** Collecting their `SR²` terms:
`0.5·SR² + ((γ₄−3)/4)·SR² = ((γ₄−1)/4)·SR²` — exactly ours. Two independent derivations of
Bailey & López de Prado agreeing is a real check on the most important piece of measurement code
we have.

**Except the agreement holds only if both feed the same kurtosis convention — and theirs does
not.** Their `kurtosis()` is:

```python
def kurtosis(returns, prepare_returns=True):
    return returns.kurtosis()          # pandas → EXCESS kurtosis (Fisher, normal = 0)
```

…while the formula's `(kurt − 3)/4` term expects **Pearson** kurtosis (normal = 3). Demonstrated
on 100,000 normal draws:

```
pandas .kurtosis() on a NORMAL series = 0.0314   → excess, not Pearson

SR² coefficient with excess kurtosis (what they pass):  −0.2422
SR² coefficient with Pearson kurtosis (correct)      :  +0.5078
```

For a normal return series the variance term should contribute **+0.5·SR²**; theirs contributes
**−0.25·SR²**. That makes `sigma_sr` too small, the z-score too large, and **PSR systematically
overstated — the library reports more confidence than the data supports**, which is the
dangerous direction.

**A second, separate defect** in the same function:

```python
if annualize:
    return psr * (252 ** 0.5)
```

**PSR is a probability in [0, 1]; this multiplies it by ≈15.87.** A PSR of 0.9 "annualises" to
14.3. It is a unit error hiding behind an optional flag — a new variant of this log's recurring
theme, where nothing in the logic is wrong and a default or a flag makes the output meaningless.

**And ours is correct, with the trap explicitly pinned:**

```python
kurtosis: float  # Pearson (normal = 3.0), not excess
...
kurt = m4 / pop_sd**4 if pop_sd > 0 else 3.0
```

That comment is the difference between the two implementations. **This is the strongest
validation our measurement stack has received in this entire review** — checked against the
best-known reference in the field, and the reference is the one that is wrong.

**T11 — pin our PSR/DSR against known-good values in a test.** The cross-check above was
manual and one-off; it should be a regression test with hand-computed expectations (including a
normal-series case where the `SR²` coefficient must be `+0.5`), so the kurtosis convention can
never silently flip. This is the same discipline as qlib's filing-date-anchored PIT test (T1):
**anchor the test to a value you can derive independently.**

## 22.2 The metric battery is a checklist of what we do not compute

Seventy-nine functions, several of which land on open queue items:

| QuantStats | Our state |
|---|---|
| `information_ratio`, `greeks` / `rolling_greeks` (alpha, beta) | **This is H12.** A reference implementation exists — port the formula rather than derive it. |
| `smart_sharpe`, `smart_sortino`, `autocorr_penalty` | The **parametric** cousin of **H1** (block bootstrap). Two independent answers to "serial correlation inflates Sharpe" — theirs adjusts the statistic, ours resamples the path. Worth having both. |
| `tail_ratio`, `outlier_win_ratio`, `outlier_loss_ratio`, `remove_outliers` | Formalisations of the check we did **ad hoc**: our market-regime cohort had a *trimmed mean of +₹200 against a −₹302 raw mean — trimming reversed the sign.* We caught that by hand; these are the standard named ratios for it. |
| `risk_of_ruin` | We do not compute it. Directly relevant to ₹1L live capital against a currently negative expectancy. |
| `montecarlo`, `montecarlo_sharpe`, `montecarlo_drawdown` | Adjacent to **H8**'s negative control. |
| `kelly_criterion` | Sizing; noted, not needed (we size risk-first from the actual fill). |

## 22.3 Verdict: reference, not dependency

**Do not adopt it as a dependency**, for two structural reasons rather than any doubt about its
usefulness:

1. **Unit mismatch.** The battery operates on a **daily returns Series**. Our evidence unit is the
   **per-trade R-multiple** over a trade count — which is exactly why we built MinTRL rather than
   borrowing a years-based formula (§20.1). Most of the 79 functions would need a synthetic daily
   series to be meaningful, and that synthesis is where errors would enter.
2. **Money types.** Float and pandas throughout; we are `Decimal` end to end. Reporting-side only
   would be defensible, but see (1).

**Do use it as a reference** — it de-risks **H12** (a working alpha/beta/IR implementation),
supplies named formalisations for the tail checks we improvised, and its metric list is a useful
inventory of what a mature analytics surface reports.

**And take the meta-lesson, which is the real find here: when we build a statistical instrument
from a paper, check it against an independent implementation.** It cost twenty minutes, validated
our PSR, and turned up two defects in the field's most-used tearsheet library — including one that
makes it report *more* confidence than the data supports.

---

# 23. FinanceToolkit — `JerBouma/FinanceToolkit`

Reviewed 2026-09-03. **MIT**, ~131,000 LOC, **1,486 tests**, actively maintained. A large financial
metrics library — 95 fundamental ratios plus risk, performance, technicals, options, fixed income
and econometrics modules — whose explicit pitch is **formula transparency**.

Reviewed immediately after QuantStats, deliberately: repo 21 failed a formula audit, and this
library's whole claim is that its formulas are inspectable. **It passes the same audit, explicitly.**

## 23.1 ★ It gets right the exact thing QuantStats got wrong

QuantStats fed pandas' **excess** kurtosis into a formula expecting **Pearson**, silently
overstating PSR (§22.1). FinanceToolkit makes the convention a named, documented, defaulted
parameter:

```python
def get_kurtosis(..., fisher: bool = True, ...):
    """fisher (bool, optional): Whether to return Fisher's definition of kurtosis
    (excess kurtosis, i.e. normal distribution equals 0.0) instead of Pearson's..."""
    ...
    return returns.kurtosis() if fisher else returns.kurtosis() + 3
```

The conversion is correct, the default is stated, and the caller cannot be confused about which
they are getting. **This is the difference between a library you can audit and one you must audit.**

And its formulas carry citations with page numbers. From the Cornish-Fisher VaR docstring:

> *Formula for quantile from "Finance Compact Plus" by Zimmerman; Part 1, page 130-131.
> More material/resources: "Numerical Methods and Optimization in Finance" by Gilli, Maringer &
> Schumann; https://www.value-at-risk.net/the-cornish-fisher-expansion/;
> https://www.diva-portal.org/... Section 2.4.2, p.18; "Risk Management and Financial
> Institutions" by John C. Hull*

Four independent sources, one with a page range, for a single quantile adjustment. **That is the
transparency claim made good** — and the direct opposite of abu's `0.668` / `0.91` magic constants
arriving with no derivation (§16).

## 23.2 It does **not** unblock MCE 5b, and it is worth being clear why

95 ratio formulas — valuation (29), profitability (23), efficiency (20), solvency (15), liquidity
(8) — is exactly the battery MCE slice 5b would eventually need.

**But our 5b blocker is the data half, not the formula half.** Our own record is explicit: *"the
keystone blocker = `market_cap` has no writer → nothing fundamental unlocks until a source is
chosen."* FinanceToolkit computes ratios **from financial statements you supply**, sourced from
**FinancialModelingPrep** (10 README mentions) and yfinance. There is **no India/NSE-specific
support anywhere in it**, and FMP's NSE coverage is neither free nor reliable for mid-caps.

So it solves the half we do not have a problem with. Saying otherwise would be the "manufacturing
relevance" failure I refused in §17.

**What it does contribute to 5b is a warning, and it is the author's own founding observation:**

> *"While browsing a variety of websites, I repeatedly observed **significant fluctuations in the
> same financial metric among different sources**. Similarly, the reported financial statements
> often didn't line up, and there was **limited information on the methodology used to calculate
> each metric**."*

**That is the argument for why 5b's source decision is the whole problem rather than a detail.**
The same metric genuinely differs across vendors, which means whichever source we pick becomes
*part of the definition* of every ratio we compute from it — and a market-cap threshold calibrated
on one vendor's numbers is not portable to another's. When 5b is built, the source must be pinned
alongside the formula, and the PIT test (**T1**) must be anchored to *that vendor's* published
figures.

## 23.3 T12 — and applying it to ourselves

The practice worth taking: **cite the source for every non-obvious formula, and make convention
choices explicit parameters rather than implicit assumptions.**

Checked against our own code, and the result is mixed in an instructive way. Only **two** files in
our trading layer cite a derivation: `atr.py` (Wilder) and `deflated_sharpe.py` (Bailey & López de
Prado, plus the `# Pearson (normal = 3.0), not excess` pin that saved us in §22).

In our defence, the **frozen analysis engine** is specified by `docs/SIGNAL_ENGINE.md` — a
protected spec, which is *better* than inline citations because it is versioned and
regression-gated.

**But the trading layer is not covered by that spec, and it is precisely where our churn has
been.** `profit_lock`'s absolute ladder — breakeven at +₹2k, seal peak−₹1k above ₹3k — and the
various gate thresholds are **fitted constants with no recorded derivation**. That is the same
criticism I levelled at abu's `0.668`, and it applies to us: a constant with no stated origin
cannot be re-derived, re-fitted, or argued about on its merits — it can only be defended by
whoever remembers choosing it.

**T12 — every non-obvious constant and formula in the trading layer records its origin**: a
citation, a fitting procedure with its sample, or an explicit "chosen by judgement on <date>,
never validated". The third option is the important one — it is honest, it is cheap, and it makes
the unvalidated knobs visible to the review calendar instead of indistinguishable from derived
ones.

## 23.4 Verdict

**Adopt no dependency** (FMP-centric, no NSE coverage, and our fundamentals blocker lies
upstream of it), but **keep it as the reference for when 5b is built** — 95 cited ratio definitions
are worth more than deriving them, and lesson 21 says to check our implementations against an
independent one.

Two takeaways: it is the **counter-example to QuantStats** — proof that the kurtosis-convention
trap is avoidable by naming it — and **T12**, which turns its citation practice on our own
trading-layer constants, where we currently have fitted numbers nobody can re-derive.

---

# 24. The .NET batch — seven repos

Reviewed 2026-09-03. All C#/.NET, so **none shares our stack**. Per lesson 17 the filter is shared
*stack* or shared *discipline* — and exactly one of the seven clears it on discipline. Two are
rejected on licence before any technical read. The rest are small, inactive, or covered better by
repos already reviewed.

| Repo | Licence | Verdict |
|---|---|---|
| **facioquo/stock-indicators-dotnet** | Apache 2.0 | ⭐ **The one worth reading** — 518 test files, **80 committed hand-calculated oracles**. Produced two findings about *our* code. |
| StockSharp/StockSharp | **Custom, proprietary** | **Rejected on licence.** |
| StockSharp/AlgoTrading | **Custom, proprietary** | **Rejected on licence** (same terms). |
| srbrettle/Financial-Formulas-Library | MIT | 12 files total. Superseded by FinanceToolkit (§23). |
| mccaffers/backtesting-engine | MIT | *"No longer under active development"* — author moved to C++. One contrast worth noting. |
| SoftAlgoTrade/TradingStrategies | Apache 2.0 | Strategy samples for a .NET platform. Nothing transferable. |
| Krexind/quant-trading-toolkit | MIT | Small hobby bot. Nothing transferable. |

## 24.1 ★ StockSharp's licence is the strongest rejection in this entire log

Not open source, and it says so:

> *"This repository is **not licensed under a general-purpose open source license**. **Viewing,
> downloading, copying, building, modifying, using, distributing, or otherwise accessing** any part
> of this repository is permitted only under the StockSharp End User License Agreement…*
> *StockSharp **may update its license terms** on the official website. **Users are responsible for
> monitoring** the official StockSharp website and complying with the **then-current** terms."*

Two things make this worse than anything else encountered:

1. **The terms are unilaterally mutable**, and the obligation to track changes falls on the user.
   GPL (§16) and the Commons Clause (§21) are restrictive but *stable and knowable*; this is a
   licence that can change after adoption.
2. **Even viewing is nominally gated**, which makes "read it for architecture, adopt nothing" — the
   posture this log has taken with vnpy, zipline and qlib — not obviously available.

Since StockSharp is essentially "vnpy for .NET" and **vnpy is MIT** (§12), there is no reason to
take on that risk: we already have a permissively licensed reference implementation of the same
thing. **Rejected without technical assessment, which is lesson 16 working as intended.**

The licence spectrum across twenty-nine repos now runs: **MIT / Apache** → **no LICENSE at all**
(no grant of rights) → **LGPL** → **GPL-3** → **Commons Clause** (bites at commercialisation) →
**unilaterally mutable proprietary with a monitoring duty**. Only the first tier is safe to build
on, and the difference between tiers is not a matter of degree.

## 24.2 ★★ stock-indicators-dotnet — 80 hand-calculated oracles, and two findings about us

Apache 2.0, active (2026-08), 1,842 files, **518 test files**. Its testing of indicator
correctness is the best in this log, and it is directly comparable to our Rust parity fixtures.

**It commits 80 `.xlsx` spreadsheets as oracles** — `Rsi.Calc.xlsx` sits beside `RsiSeriesTests.cs`,
`Sma.Calc.xlsx` beside the SMA tests, and so on. The expected values are derived **by hand, in
Excel, independently of the code**, and committed. The tests then pin exact values:

```csharp
sut.Should().HaveCount(502);
sut.Where(x => x.Rsi != null).Should().HaveCount(488);
sut[13].Rsi.Should().BeNull();                              // warmup boundary, exactly
sut[14].Rsi.Should().BeApproximately(62.0541, Money4);      // first valid value
sut[249].Rsi.Should().BeApproximately(70.9368, Money4);
sut[501].Rsi.Should().BeApproximately(42.0773, Money4);
```

Note what is pinned: total count, **non-null count**, the **exact warmup boundary** (index 13 null,
index 14 first value), and three values across the series. Plus property tests
(`Results_WithAnyInput_AreAlwaysBounded` — RSI ∈ [0,100]).

And each indicator is tested through **three execution modes** — `Series` (batch), `BufferList`
(incremental), `Hub` (streaming) — which must agree.

### T13 — we have the right test, on two indicators

Their Series/BufferList/Hub triad is the structural form of a test we already wrote:

```
engine-core/src/indicators/sma.rs:80   fn incremental_matches_batch_on_long_series()
engine-core/src/indicators/ema.rs:120  fn incremental_equals_batch()
```

**Two indicators have it. The Wilder family does not** — and RSI/ADX/ATR are precisely where
recursive smoothing makes batch and incremental most likely to diverge, *and* where our own parity
tolerance is loosest (1e-6, against 1e-9 for the EMA family). **T13: extend
`incremental_equals_batch` across the indicator set, Wilder family first.** Small, mechanical, and
it targets the exact place a drift would hide.

### T14 — our fixture chain has no external anchor

Our rust rules state the oracle plainly:

> *Golden fixture files (committed) **generated from the FROZEN Python implementation** are the
> oracle — pandas-ta version recorded inside each fixture.*

So the chain is **Rust ← Python ← pandas-ta**, and recording the pandas-ta version is good
practice. **But nothing validates the chain against independent arithmetic.** If pandas-ta carried
a convention bug — precisely the QuantStats failure of §22 — our fixtures would faithfully encode
it and every parity test would pass, forever, in green.

si-dotnet's committed spreadsheets are the missing anchor: a value a human derived, that no code
produced. **T14: hand-compute a handful of Wilder-family values (RSI, ATR, ADX over a short
series) and pin them as a separate fixture** — not to replace the parity fixtures, but to anchor
them. Perhaps twenty values, once, and the chain stops being self-referential.

This is the same shape as **T1** (qlib's filing-date-anchored PIT test), **T11** (pin PSR against
independently derived values) and **H8** (the noise negative control): *anchor the test to
something the code did not produce.* Four independent arrivals at that idea across this log.

*(It also ships an `AGENTS.md`; nothing in it improves on what we already have.)*

## 24.3 One contrast from the backtesting engine

`mccaffers/backtesting-engine` (MIT, no longer actively developed) is well engineered — QuestDB
for tick storage, SonarCloud quality gates, real CI — and its stated purpose is:

> *"…AWS, for **horizontally scaling strategy permutations and experiments** … enabling rapid
> iteration on trading hypotheses and **more comprehensive strategy exploration** than would be
> feasible on local infrastructure."*

**That capability is the exact thing our deflated-Sharpe bar exists to defend against.** Running
thousands of strategy permutations in parallel is how you manufacture a beautiful false positive:
every permutation is a trial, and `E[max SR]` grows with the trial count. The README frames the
scale as an unalloyed good; §20's replication record (median published Sharpe 0.37, half
indistinguishable from zero) is what that scale produces without a multiple-testing correction.

Not a criticism of the engineering — a reminder that **compute makes the overfitting problem
worse, not better**, and that our H1/H8/H11 axis matters more the faster we can search.

## 24.4 Verdict

**Adopt nothing.** Two licence rejections, four too small or inactive to repay the reading, and one
genuinely excellent test suite that produced **T13** and **T14** — both about our own code, both
small, and both landing on the theme that has run through this entire review: **anchor your tests
to something the code did not produce.**

---

# Where this leaves us

*Written 2026-09-03 after thirty repos, at the close of the first review series.*

**Nothing here is authorised work.** Watch mode holds to Fri 2026-09-04, and every item below is
measurement, reporting surface or test — none touches the money path.

**If only five things are ever done from this document, these five:**

| # | Item | Why it is first |
|---|---|---|
| **A11 + A40** | Session notifier with a noise policy, carrying a worker-liveness alert | **Three independent mature systems** made push a core primitive. We have **two standing daily human rituals** that exist only because we lack it — CAS capture (a missed window **cannot be back-filled**) and provisional health (no scheduler at all). |
| **H8** | Feed pure noise through our own deflated-Sharpe bar and assert it **rejects** | A bar never shown to reject anything is a metric that cannot come out badly. Half a day, and the machinery exists. |
| **A21** | Mark-to-bid, so marks match fills | An internal inconsistency **in our own system**: since 6.8.2 fills pay the real half-spread, marks still use last close. The depth is already captured. |
| **H2 + U2** | Buy-and-hold benchmark, as a **row in the same sorted table** | We have no portfolio benchmark. A benchmark in its own section gets skipped; one in the same sort order cannot be. |
| **A25** | Assert the tick mode on the depth path | Kite is documented to send quote-mode ticks on a full-mode subscription; we never check, on a path built to fail open — so it would degrade **silently**, on the book we judge expectancy with. |

**The five findings that were about *us*, not them.** The most valuable output of this review was
not a library — it was six defects and gaps in our own code, found by comparison:

- **A21** — fills spread-aware, marks not *(PaperTrade-India)*
- **A25** — `MODE_FULL` subscribed, never verified *(express-option-chain)*
- **A29 / A30** — no flat DP charge; the backtest ignores circuit bands the order path enforces *(qlib)*
- **A42** — no frozen-capital concept, harmless until Phase 7 has pending orders *(QUANTAXIS)*
- **T13 / T14** — `incremental_equals_batch` on two indicators only; the fixture chain has no external anchor *(stock-indicators-dotnet)*
- **And one validation:** our PSR is **correct** where QuantStats' is not *(§22)*

**The three sentences worth remembering:**

1. **A headline performance number is the best predictor that a repo's claims will not survive
   contact with its own source.** Seven of thirty; and the twelve that publish no number are the
   ones whose code was worth reading.
2. **The strongest guarantee is the one that removes the syntax for the mistake.** Look-ahead
   appeared at every point on that spectrum, and position on it predicted the outcome every time.
3. **Anchor the test to something the code did not produce.** Arrived at independently four times
   in this log — T1, T11, T14, H8 — and it is the one habit that would have caught the most defects
   found here, including our own.

**And the calibration, from the only population-level evidence anyone has shared** (§20, 4,843
replicated papers): **median Sharpe 0.37, half indistinguishable from zero on their own sample, and
roughly half the median edge is index beta.** A −0.303R book measured honestly is an early-stage
position on that distribution, not an anomalous one. A 2–3%/day target is not on it at all.

---

# Execution plan — sequenced to cycle 2

*Written 2026-09-03. Supersedes the informal ordering in "Where this leaves us" above.*
**Nothing here is authorised.** Watch mode holds to Fri 2026-09-04; this is a plan, not a start.
All 91 queue items are assigned a bucket below — none is left unplaced.

## The rule that orders everything

> **Anything that changes a recorded number must land BEFORE cycle 2's clock starts.**

We have already paid this once. Paper P&L before and after 2026-08-17 is **not comparable**
because the spread-aware fill model landed mid-window, and the 30-day clock had to reset. Cycle 2
is 45–50 trading days on ₹1L. Shipping a costing, fill or eligibility change mid-cycle costs the
whole window.

**The corollary is what makes this tractable:** work that does *not* touch a recorded number —
notifiers, tests, rules, UI — can be built **while the clock runs**. That is most of the backlog.
So the choice is not "build everything first" versus "start accruing"; it is **freeze the
number-changing surface, start the clock, and build the rest underneath it.**

| Bucket | Meaning | Must precede the clock? |
|---|---|---|
| **A** | Changes a recorded number — costs, fills, marks, or which signals exist | **Yes** — or the cycle is invalid |
| **B** | The instruments that will judge the cycle | **Yes** — or we cannot read the result |
| **P7** | Phase 7.1–7.4, already a documented cycle-2 prerequisite | **Yes** — the long pole |
| **MCE** | Slices 5b + 6, already documented prerequisites | **Yes** — gated on a *decision*, not code |
| **C** | Touches no recorded number | **No** — build during accrual |
| **PARK** | Research, or blocked on something that does not exist yet | No |

## Bucket A — freeze the numbers (~7 days)

| Item | What | Effort |
|---|---|---|
| **A38** ✅ **DONE 2026-09-05** | Composable point-in-time `Restrictions` interface — absorbs `eligibility.py`, the order-path gates and `circuit_guard`'s read. **Subsumes A30 and A31.** Shipped as `app/signals/restrictions.py`; both live paths migrated, behaviour proven unchanged by differential fuzz (0 block diffs / 30k cases). ⚠ The **backtest leg is NOT done** — it consults no gate today and `backtest/engine.py` is FROZEN, so it needs sign-off + §8 + regenerated fixtures. | 2–3 d |
| **A21** ✅ **DONE 2026-09-05** | Mark-to-bid, so marks match fills. Shipped as `exit_mark()` routing marks through `simulate_fill` with the EXIT side; wired into `update_position_pnl` (API list, summary, monitor — batched depth) and `_open_book_mtm`. ⚠ Two limits pinned: the HISTORICAL mark cannot be true mark-to-bid (depth is Redis-only, 60s TTL, never persisted), and the flat haircut is a no-op below ~₹125 (smaller than half a ₹0.05 tick). | 0.5 d |
| **A37 + T3** | Volume-participation cap on fills, with its parametrised test | 1 d |
| **A29** | Flat DP charge per delivery sell + per-trade cost floor | 0.25 d |
| **A23** | Date-versioned (effective-dated) fee registry | 0.5 d |
| **A26** | Refuse loudly at the hot-set capacity boundary — **changes which stocks get scored, so it changes which signals exist** | 0.5 d |
| **A25** | Assert tick mode on the depth path + count degradations | 0.25 d |
| **H6** | `MAX_RATIO` sentinel instead of `inf` — changes reported R:R values | 1 h |
| A30, A31 | *Superseded by / written as part of A38* | — |

Each alters a number cycle 2 will record: A21 the marks, A29/A23 the P&L, A37 the fills, A26 the
signal population, A38 which trades are eligible at all, A25 protection against fill quality
regressing silently mid-cycle.

## Bucket B — the instruments that read the cycle (~5 days)

| Item | What | Effort |
|---|---|---|
| **H8** | Noise negative-control — prove the DSR bar rejects | 0.5 d |
| **H1** | Moving-block bootstrap p5 Sharpe beside PSR/DSR/MinTRL | 0.5 d |
| **H12** | Beta-to-NIFTY + information ratio on every cohort | 1 d |
| **H2** | Buy-and-hold benchmark line in the daily report | 0.5 d |
| **H11** | MinTRL as the banner headline — `n=44` never without `needs ≈N` | 2 h |
| **T11** | Pin PSR/DSR against independently derived values | 2 h |
| **H4** | Gate/hypothesis register as data (absorbs **A8**, the failure archive) | 1 d |
| **U4** | Trials-attempted counter — makes `N` observed, not the assumed 20 | 0.5 d |
| **H3** | VIX companion as a trailing percentile (shadow; changes no trade) | 1 d |
| **T7** | Exhaustive-enum mapping test — gate modes, rejection reasons, readiness states | 2 h |
| **A24** | Standing rule: never render a precise figure without its uncertainty | 1 h |

These decide how cycle 2 is *read*. Changing the yardstick mid-window is the same error as
changing the fill model — the halves stop being comparable.

## Bucket P7 — Phase 7.1–7.4, the long pole (weeks, not days)

Already a documented cycle-2 prerequisite: RiskEngine · BrokerAdapter · order FSM ·
reconciliation. **Design these together in one pass** — this review found they are one problem,
not four.

| Item | What |
|---|---|
| **A33** | OMS as a projection of the event stream; one `is_active()` predicate; gateway-namespaced ids |
| **A42** | Frozen / available-cash accounting (derivable from A33's active set) |
| **A35** | `BrokerAdapter` as an interface a second broker *could* implement |
| **A32** | Event-bus robustness — per-handler exception isolation, bounded queue, snapshot iteration, **a dead bus must be loud** |
| **A22** | Bracket sibling-quantity rebalance on partial fill |
| **A16** | Order-protection lifecycle state machine + durable repair queue |
| **T2** | Lifecycle-boundary tests — first step, start mid-stream, stop early |
| **A34** | Timer event as the single scheduling primitive |

**Read before writing a line:** vnpy's 145-line event bus, PaperTrade-India's `orders/`, repo 4's
CLAUDE.md invariants. This review's clearest Phase-7 finding: **the bus is small; the cost is the
order FSM and reconciliation** — 82 defects across two audits in one project, 543 tests in another,
and the *same* partial-fill bug found independently by both.

## Bucket MCE — slices 5b + 6 (blocked on a decision, not on code)

| Item | What | Blocker |
|---|---|---|
| **MCE 5b** | `market_cap` writer | **A vendor must be chosen.** Not a build task. |
| **T1** | PIT test anchored to a real, cited NSE/BSE filing date — **ships with 5b, not after** | — |
| **MCE 6 / A18** | News veto: Google News RSS (`hl=en-IN&gl=IN&ceid=IN:en`) + FinBERT; **not** HTML scraping | — |

**The warning this review produced:** the same fundamental metric differs materially across
vendors, so **the vendor becomes part of the definition** of every ratio. A market-cap threshold
calibrated on one source is not portable to another, and T1 must anchor to *that vendor's*
published figures.

## Bucket C — build during accrual (touches no recorded number)

**Operational safety and alerting** — the largest single win, and safe to ship mid-cycle:
**A11** session notifier with noise policy · **A40** worker-liveness metric + alert ·
**A27** config dry-run · **A28** retryable classification · **A3** broker token status ·
**A36** calendar-expiry alarm · **H7** Sharpe-decay alarm · **A9/A10** progress envelope and
mid-flight results.

**Tests and invariants:** **T9** doc-sync ritual as failing tests · **T8** self-cleaning debt
baseline · **T10** `ExplodingObject` negative-space assertions · **T13** `incremental_equals_batch`
across indicators · **T14** hand-computed fixture anchor · **T12** record every constant's origin ·
**T4** NaN boundaries · **T5** crash paths · **T6** ordered pipeline stages · **A13** breaker
un-suppressibility · **A15** window ≥ tick interval · **H5** warmup enforcer.

**Rules and hygiene (~15 min each):** **W1** doc/code precedence · **W2** no parallel
implementations · **W3** same-commit config hygiene · **W4** git boundary · **W5** no hardcoded
model names · **A12** invariants with their dated incident · **A5** self-documenting schemas ·
**A7** artifact provenance · **A39** `cargo-deny` supply-chain gate.

**UI, in this order:** **U1** registry page (folding in **U2** benchmarks-as-rows, **U3** worst-of
validation, **U5** current-leader callout, **U6** rejected candidates visible) → the signal-detail
trio **U10** arithmetic + **U15** named evidence + **U17** distribution bar → **U20** would-block
cohort as charts → **U11** benchmark on every curve → **U19** horizon correlation →
**U7 / U8 / U9 / U16 / U18 / U12** as polish.

**Deployment and misc:** **A4** constraint pre-validation endpoints · **A14** measured, layered
timeouts · **A17** provider failover + pinned cost table · **A1** two-tier model routing (if an LLM
enters the research loop) · **A41** split Redis by durability — *after* P7 introduces a durable
repair queue.

## Parked — explicitly not now

| Item | Why |
|---|---|
| **H10** | Loser-cluster meta-labeling. Attacks our real failure mode *and* is an overfitting machine. **Not until H8 exists to catch it**, then only behind DSR with an honest trial count. |
| **H9** | CSCV / White's Reality Check / meta-labeling — research pointers. |
| **A19, A20** | Composite-score normalisation; signed risk penalty instead of a boolean gate. No current consumer — revisit only if an overlay is redesigned as a modifier. |
| **A6** | Agent-topology note, not a task. |
| **W6** | MCP exposure model — recorded so it is not reinvented badly under pressure; no current need. |

## Sequence and honest sizing

```
NOW ──────────────────────────────────────────────────────────────────────────►
│
├─ Weeks 1–2   Bucket A (~7 d) + Bucket B (~5 d)          ← freeze the numbers
│              in parallel: the W rules (~1.5 h total)
│
├─ Weeks 3–?   Bucket P7 — design pass first               ← THE LONG POLE
│              (A33 + A42 + A35 together), then A32/A22/A16/T2
│              in parallel: the MCE vendor decision (not a build task)
│
├─ Then        MCE 5b + T1 · MCE 6 (A18) · CAS-2 · tuning
│
├─ THEN        ── cycle 2 clock starts ── 45–50 trading days on ₹1L
│              and underneath it, continuously: all of Bucket C
│
└─ After       Read cycle 2 with instruments frozen before it began
```

**Honest total to the start of cycle 2: three to four months**, dominated by P7 and the MCE
decisions — consistent with the standing "live is 4–6 months out" estimate. Buckets A and B are
about two weeks of that; the rest of the critical path is P7 and decisions, not backlog.

**The discipline this encodes:** every week spent building is a week not accruing, and cycle 2
needs its 45–50 days regardless. Build only what must be frozen, start the clock, and let the
remaining ~60 items land while the evidence accumulates.

---

# Consolidated harvest queue

Two queues: **analysis (`H`)** and **UI/UX (`U`)**. Ranked by value-to-us ÷ effort.
**Nothing here is authorised work** — items enter `docs/PHASES.md` only on the user's
say-so, and we remain in watch mode to Fri 2026-09-04 with no money-path build. Every one
of these is measurement or reporting surface, never the money path.

## Analysis queue

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **H1** | **Moving-block bootstrap p5 Sharpe** beside PSR/DSR/MinTRL | `app/services/deflated_sharpe.py`; one extra line per readiness banner | ~half day + tests | Non-parametric complement to a bar whose own weakness is the independence assumption. Automates the tail-robustness check that constraint #8 currently asks me to do by hand, and that the market-regime trimmed-mean sign flip proved we need. |
| **H2** | **Buy-and-hold benchmark line in the daily report** | `app/services/daily_report.py`, reading the existing `index_ohlcv_1d` (782 bars/index, already backfilled) | ~half day | We do not have one — I checked; `benchmark.py` is per-signal relative strength, not a portfolio baseline. AgentQuant's most sobering number was buy-and-hold beating five years of agent work, and it was invisible until someone opened a CSV. Our book is **−0.303R expectancy**; the honest denominator is what NIFTY did over the same window. Cheap, and it reframes every subsequent gate argument. |
| **H3** | **Re-frame the VIX companion as a trailing percentile** | `app/signals/market_regime.py` | ~1 day | Converts a knob blocked on backfill (`absolute 20`, US-derived, "too shallow to §8-validate") into a self-calibrating, distribution-free one. Does **not** promote anything — market-regime stays shadow and still owes its count and DSR bar. |
| **H4** | **Gate/hypothesis register as data** | new table or a `docs/` machine-readable file: gate · mode · pre-registered prediction · bar · current count · verdict · review-due | ~1 day | Constraint #8 makes me the owner of the review calendar and requires me to raise items *unprompted*. That calendar is prose today. Modelled on `AlphaStore`'s schema, not its code. Would also give the failed-hypothesis archive a home (regime gate, R:R≥1 already populate it). |
| **H8** ✅ **DONE 2026-09-04** | **★ A noise negative-control against our own deflated-Sharpe bar** — generate N random, content-free partitions of the real trade set, run them through the *same* `deflated_sharpe.py` path the real gates use, and assert the bar **rejects** them | `backend/tests/` + `app/services/deflated_sharpe.py` | ~half day | *(repo 12)* A test of the test. If a noise gate clears our bar, the bar is broken and every readiness banner built on it is worthless. The machinery already exists, it is a genuine test rather than an argument, and it targets exactly what has bitten us twice — **promoting on evidence that looked sufficient.** Our own rule says a metric that cannot come out badly is not a metric; this applies it to the bar itself. **✅ SHIPPED 2026-09-04 — and the specification above was INSUFFICIENT.** Asking only whether the bar rejects noise is a test **a bar that rejects everything passes trivially**, which is the exact state ours was in. A power arm was added: plant a known real edge and require the bar to accept it. **Result: the bar is SOUND** (0.00% of random partitions and 1.10% of best-of-20 zero-edge selections clear, against a 5% allowance; 80% power at a true per-trade Sharpe of 0.52). **⭐ Restated, the bar demands t ≈ 3.6 on the trade series and that hurdle is flat in n** — just above Harvey/Liu/Zhu's recommended t > 3.0, so it is defensibly calibrated. ⇒ `sl_atr` decided NO at t ≈ 0.41. `app/services/dsr_control.py` · `scripts/dsr_negative_control.py` · `tests/test_dsr_control.py`. |
| H10 | **Loser-cluster meta-labeling as a research candidate** — don't guess the partition; cluster the actual losing trades and let the clusters define the veto | post-watch-mode research queue | research | *(repo 15)* Attacks the failure mode that cost us twice: **our overlays are hypothesis-driven and two of three were reverted because the partition was a proxy for something else** (market-regime → side; R:R<1 → wide stop). **But it is an overfitting machine** — clustering your own losers always looks good in-sample. **Only behind DSR with an honest trial count (every cluster config is a trial), MinTRL, and H8's negative control.** Explicitly not a build item. Third independent pointer at meta-labeling (e-book review, `mlfinlab`, this). |
| **H11** | **★ Put the implied sample beside every readiness banner** — render MinTRL as the headline, so `n=44` is never read without `needs ≈N` | readiness banners / `deflated_sharpe.py` render path | ~2 hours | *(repo 19)* Independent external confirmation of MinTRL's message, with a number: required sample scales with the **inverse square of effect size**, so a median published strategy (Sharpe 0.37) needs **~28 years** to separate from zero. **Our gates are judged on 33–72 trades.** We already compute MinTRL — the missing move is promoting it from footnote to headline. |
| **H12** | **★ Beta-to-NIFTY and an information ratio on every cohort evaluation** | cohort/sidecar evaluation, using the existing `index_ohlcv_1d` + `benchmark.py` | ~1 day | *(repo 19)* On 4,843 replications the median strategy carries **beta +0.17**, and stripping it takes the median IR to **0.21** — roughly **halving** the apparent edge. **We compute no beta and no IR anywhere**: a would-block cohort that is long-biased in a rising market would look like skill. Third robustness axis beside **H1** (is it stable?) and **H8** (does the bar reject noise?): **is it just the market?** |
| H9 | **CSCV / probability of backtest overfitting, and White's Reality Check**, as complements to DSR; and `mlfinlab`'s **meta-labeling** | post-watch-mode research queue | research | *(repo 12)* Different tests, same question — multiple-testing robustness. Meta-labeling is our overlay pattern under another name (already flagged in the e-book review). **Pointer, not queued work.** |
| H5 | `WarmupEnforcer` / `@enforce_lookback` as a runtime invariant | `app/analysis/` boundary — **frozen engine, so overlay//caller side only** | ~1 day | Turns a review-convention into a loud failure. Low urgency: no look-ahead bug is currently suspected. |
| H6 | `MAX_RATIO` sentinel instead of `inf` for degenerate ratios | wherever R:R / Calmar-like ratios are computed | ~1 hour | We have the `RR≈228` tiny-SL artifact on record. Trivial hygiene. |
| H7 | Sharpe-decay alarm on shadow gates | daily report / readiness banners | ~1 day | The regime gate sat `NOT READY` for 7 report days before action. Detection existed; alarming did not. Partly subsumed by H4. |

## UI/UX queue

Same rule — nothing here is authorised. All of it is *reporting surface*, none of it
touches the money path, and all of it obeys `.claude/rules/ui.md` (tokens, `format.ts`,
5 themes, virtualization ≥200 rows).

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **U1** | **A "Research / Gate Registry" page** — one sortable table over all shadow gates and experiments: name · mode (shadow/active/reverted) · n · metric · bar · **robustness** · **validation** — **default-sorted by the penalised score, not the headline metric** | new `frontend/src/features/analytics/` page + an endpoint over the sidecar data | ~2–3 days | **The biggest UI gap we have.** Our shadow evidence is 7 separate markdown files a human must open one at a time; AgentQuant puts the same job on one screen. This is the UI half of H4 and would subsume the daily banner-reading ritual. |
| **U2** | **Benchmarks as rows in that same table** (NIFTY buy-and-hold, random-entry baseline) | same page | included in U1 | A benchmark in its own section gets skipped; a benchmark in the same sort order cannot be. This is the *right* delivery for H2 — do H2 and U2 together. |
| **U3** | **`Validation` column = worst-of-checks, with per-check reasons on drill-down** | same page | included in U1 | We already compute worst-of in the readiness guards; this renders it scannable and makes the *reason* reachable ("5 trials available for this arm"), not just a tick. Includes honest WARN labels — *"useful benchmark, but not a leakage-safe protocol"*. |
| **U4** | **Trials-attempted counter** (`tried · accepted · watch · rejected` KPI strip) | same page; also one line in the daily report | ~half day | Makes `N` in `E[max SR]` an **observed** number instead of the hand-picked 20 we assume today. Directly hardens H1 — this is the soft spot in our whole DSR bar. |
| **U5** | **"Current leader" callout** — one sentence naming the best current candidate and what to compare against | same page | ~2 hours | Turns a table into a decision. Our banners say READY/NOT READY per gate but never name the anchor. |
| **U6** | **Rejected/reverted candidates stay visible with their damage** | same page | included in U1 | The regime gate (−8R) and R:R≥1 (+₹10,585 cohort blocked) should be permanent rows, not prose in memory files. |
| U7 | **Provenance + regime stamped on every row** (how generated, which regime it ran in) | same page | ~half day | We persist `Signal.regime` and generation provenance already; neither is surfaced. |
| U8 | **`Artifacts` line naming the file/service that produced each number** | banners + registry rows | ~2 hours | §1.7's rule as UI. Cheap, and it makes a stale number traceable instead of arguable. |
| U9 | **Robustness Map** — metric × drawdown scatter, coloured by mode, benchmarks in the same axes | same page | ~half day | No equivalent today. Use the `dataviz` skill. |
| **U10** | **A "Signal Formula" card on the signal detail view** — the confluence arithmetic rendered readably: each factor that scored, its weight, the normalising division, the resulting confidence | `frontend/src/features/` signal detail + an endpoint exposing the stored factor breakdown | ~1–2 days | **The strongest idea for our detail view.** Our engine is opaque at the point of decision: "78%" with no visible derivation. SRTL is exactly this — one 0.8 factor normalises to 80% and clears the ≥70% gate, invisible until the post-mortem. The diversity gate now blocks that case, but the *explanation surface* is still missing and it generalises to every gate verdict we render. DOM, not their matplotlib image. |
| U11 | **Benchmark as a default second series on every equity/P&L curve** | existing charts | ~half day | Chart-level form of U2. Theirs plots one line with nothing to compare against. |
| U12 | Small: headline number annotated *onto* the equity chart; explicit "refresh now" over auto-refetch; free-text symbol add beside preset pickers | existing pages | ~2 hours each | Cheap polish, each independently useful. |

| **U15** | **Named-evidence line on the signal detail view** — the factors that scored, in plain language ("MACD bullish crossover · RSI divergence · volume spike"), beside U10's arithmetic; plus an explicit forecast-horizon label | signal detail view | ~half day on top of U10 | *(repo 2)* The human-readable half of U10. "RSI_DIVERGENCE" alone in an evidence list reads as thin instantly, in a way "78%" never does — which is exactly the SRTL failure. |

| **U17** | **Confidence as a distribution bar, not a scalar** — one stacked bar showing which factors voted and how strongly, with the verdict beside it (zero-value segments collapsed) | signal detail view | ~half day on top of U10 | *(repo 3)* Completes the trio: **U10** the arithmetic, **U15** the named evidence, **U17** the shape of the vote. A 78% scalar hides whether it came from four factors agreeing or one factor carrying everything — which is exactly the SRTL failure. |
| U19 | **Horizon/lag correlation chart** — correlation vs lag, zero reference line, per-bar colour | analytics surfaces; each shadow-overlay sidecar | ~half day | *(repo 6B)* We found in prose that **we grade multi-day trades on a one-day clock** (entry-day ≥1R 12% vs swing 36% / positional 54%, +1R typically on d+3). This is that finding's natural rendering, and it generalises: *at what horizon does this gate actually separate winners from losers?* Recharts, which we already use. |
| U20 | **Render the would-block cohort as charts** in the shadow sidecars, not only as statistics | sidecar output / registry page (U1) | ~half day | *(repo 15)* abu saves candlestick snapshots of its highest-failure cluster so a human can see what the model learned. We report *"this gate would block these 44 trades"* as expectancy/win-rate/DSR and **have never looked at those trades as a set of charts.** The regime gate was refuted numerically; a contact sheet might have surfaced the "proxy for side" problem visually and sooner. Statistics say *whether*; charts say *what*. |
| U16 | **Phase/participant stage-tracker strip** for multi-stage runs | wherever a long job is surfaced | ~half day | *(repo 3)* The visual form of A9; ~40px shows every phase, its participants and what has completed. Fits `make analysis` and walk-forward runs. |
| U18 | **Streaming log with phase tags + explicit per-entry expansion** | sidecar/report output | ~half day | *(repo 3)* Summary inline, detail on demand. Our sidecar output is currently all-or-nothing markdown. |

**If only one UI thing is done: U1 with U2 and U4 folded in.** That single page replaces the
"open seven markdown files and hold them in your head" ritual, puts the benchmark where it
cannot be avoided, and turns the multiple-testing denominator into something we observe
rather than assume.

## Architecture queue

System design rather than screen design. Sourced mostly from repo 2, plus two backfilled
from repo 1.

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **A3** | **Broker credential-status endpoint + topbar banner** — `GET /api/v1/broker/token-status` → `{valid, expires_at, hours_remaining}` | `app/api/v1/`, consumed by the app shell | ~half day | **The highest-value architecture item, because it targets a failure we know recurs daily.** The Kite access token dies ~06:00 IST every day; the rules already class this as a normal lifecycle event, yet its state is only discoverable from a failed request. Makes a silent daily breakage visible. |
| **A4** | **Constraint pre-validation endpoints** — what date ranges / classifications / market sessions are legal, queryable *before* submit | `app/api/v1/`, consumed by order + screener surfaces | ~1 day | The generalisation of a fix we already shipped once: 41/204 rows offered a Buy that could only 409, and every row read clear in the evening while the order path 422'd on off-market. `eligibility.py` centralised the *gate* answers; this centralises the *session and calendar* ones. |
| **A11** | **★ Session notifier with a noise policy** — push on completion/failure; suppress routine success; **any exception always notifies**; the artifact is its own confirmation; a notifier outage must never affect the pipeline | new `app/services/notifier.py` + wiring in the `finally` of each session/task | ~1–2 days | *(repo 4)* **The most actionable item in this document.** We have at least two standing *manual daily human checks* that exist only because we have no notifier — CAS capture (15:15–15:33 IST, **a missed window cannot be back-filled**) and provisional health (no scheduler at all). Both are detected today by someone remembering. Add `make analysis` completion, EOD self-heal and Kite token expiry (A3) and the surface is real. |
| **A13** | **A test that pins the circuit breaker's un-suppressibility** — assert no scheduling, locking or mode change can silence it | `backend/tests/` | ~half day | *(repo 4)* Their breaker is explicitly exempt from both the dedup guard and the session mutex, pinned by a named test, because a breaker that goes quiet during a long session negates its own reason to exist. Our rules say the daily-loss breaker is *never* disableable; we should have the test that fails when that lapses — our `unassessed` tripwire taught us documentation alone is worthless. |
| A12 | **Invariants documented with the incident that produced them** (date + code location + what broke) | our CLAUDE.md / rules | ongoing | *(repo 4)* Their CLAUDE.md states our doc-sync thesis more sharply — *the "why" is not encoded in the code, so it must be recorded here* — and every entry names a dated incident. |
| A14 | **Timeouts derived from measurement, layered** | long-running jobs, `make check` | ~half day | *(repo 4)* Their 20-min wrapper timeout is "1.5–2× worst observed", in three layers, after a 13-hour hang. Our `make check` walk-forward stall has no bound at all. |
| A15 | **Assert scheduling window ≥ scheduler tick interval** | CAS capture + any timed window | ~2 hours | *(repo 4)* A 25-min window on a 30-min timer missed the close two days running. **Our CAS window is 18 minutes and its miss is unrecoverable.** |
| A16 | **Order-protection lifecycle as a state machine + durable repair queue** | Phase 7 BrokerAdapter / order FSM | Phase 7 | *(repo 4)* Not actionable pre-live, but the best available map of what Phase 7 must handle — five failure branches, each found the hard way, incl. reprotect-on-actual-fill and a drain queue so a mid-flight crash cannot leave a position naked overnight. **Read before Phase 7 starts.** |
| A17 | **Provider failover semantics + pinned cost table** | any LLM research loop | ~half day | *(repo 4)* Single-shot fallback on non-retryable failure (never on truncation), and model prices pinned so a cache refresh cannot overwrite them with stale values. |
| **A18** | **India news sourcing for the MCE news veto** — Google News RSS with `hl=en-IN&gl=IN&ceid=IN:en` + **FinBERT** (`ProsusAI/finbert`); **not** HTML-scraping MoneyControl/ET | MCE slice 6 (unbuilt) | ~1–2 days | *(repo 5)* The only worked example of Indian financial-news ingestion in this log, and it lands on a slice we have not built. RSS is stable and ToS-clean where scraping is neither (they ship three HTML-debug scripts — the evidence it kept breaking); FinBERT is local, cheap and reproducible, which a §8-validatable veto requires. |
| **A25** | **★ Assert the tick mode on the depth path, and count degradations** | `live_worker.py` / `tick_consumer.py` tick handlers | ~2 hours | *(repo 8)* Kite is documented to send **quote-mode ticks on a full-mode subscription**; that repo detects it and reopens the socket. We subscribe `MODE_FULL` and harvest depth from it with **no mode check**, so the failure would silently stale `depth:{stock_id}` and drop 6.8.2's spread-aware fills back to the flat floor — invisibly, on the book we judge expectancy with. Pairs with A11 and the 6.8.6 staleness alarm. |
| **A32** | **★ Event-bus robustness rules for Phase 7** — isolate exceptions **per handler**, bound the queue with a stated overflow policy, iterate a **snapshot** of the handler list, and **make a dead bus loud** | Phase 7 runtime | Phase 7 | *(repo 11)* Reproduced in vnpy: one handler exception kills the consumer thread, the healthy handler receives nothing, and `put()` keeps succeeding — the system looks alive and is completely deaf. A silently deaf trading system is strictly worse than one that crashes. |
| **A33** | **★ OMS as a projection of the event stream**, with one `is_active()` predicate maintaining one active-order set, and gateway-namespaced ids | Phase 7 OMS | Phase 7 | *(repo 11)* State derived from events can be rebuilt by replay, which is what makes reconciliation tractable. We have been bitten by the inverse — `signals.status` is a mutable lifecycle field doing double duty as durable fact. |
| **A36** | **Alarm on NSE calendar coverage expiry** — proactive "calendar covers only to `<date>`, N trading days remain", plus a cross-check of upcoming dates against `exchange_calendars`' XNSE | `app/services/market_calendar.py` + A11 | ~2 hours | *(repo 12)* Our calendar is **better sourced than any library** (past holidays derived from observed bhavcopy gaps = ground truth) but its expiry path is a **passive WARNING inside a query**, seen by nobody, falling back to weekday arithmetic. Same pattern as A25/A30: a degradation technically announced and practically invisible. |
| **A42** | **★ Frozen / available-cash accounting — a Phase 7 prerequisite** — reserve capital committed to pending-but-unfilled orders; separate *balance* from *available cash* | account model, before the first real order | ~1 day | *(repo 18)* Verified: **we have no frozen-capital concept at all** (every `frozen` in the codebase is `@dataclass(frozen=True)`). Harmless today because paper fills are immediate — **Phase 7 removes that property**, and two orders can then be sized against the same cash. This is the family of bug repo 4 documented from production: *a filter pre-deducted **phantom cash**, letting BUYs quietly borrow margin*. Pairs with **A33**: the frozen amount is derivable from the active-order set, so both belong in one design pass. |
| **A40** | **★ Export a worker-liveness metric and alert on it** (`workers_healthy{role=…} < 1` for 2 min) | worker heartbeat + A11 delivery | ~half day | *(repo 17)* **Converts two standing human rituals into an alarm.** CAS capture needs `make worker` up 15:15–15:33 IST and **a missed window cannot be back-filled** — today's protocol is "check the row count each morning"; the provisional-health watch has no scheduler at all. Both are worker-liveness problems dressed as rituals. Strengthens A11 rather than replacing it. |
| A41 | **Split Redis by durability** — `volatile-lru` for cache (`ltp:`/`depth:`/`circuit:`), `noeviction` for durable jobs | deployment | ~half day (ops cost) | *(repo 17)* They run separate `redis-cache` and `redis-jobs` instances. Our rule *"TTL-less keys are treated as broker-critical and never evicted"* exists **because** both concerns share one eviction policy — two instances remove the conflict instead of documenting around it. **Low priority** until Phase 7 adds a durable repair queue, which is exactly that shape. |
| **A39** | **A `cargo-deny` supply-chain gate for `engine/`** — RustSec advisories, banned crates, licence audit; **`yanked = "deny"`**; and a documented ignore list where every entry names the advisory, the reason, the PR that accepted it and the revisit condition | `engine/deny.toml` + a CI step | ~2 hours | *(repo 16)* Our Rust gate is `fmt` + `clippy -D warnings` + `test` — **no advisory scan, no licence audit** — and we ship a compiled wheel (`tradecore`) running options math **on the money path** from a dependency graph nobody audits. The source repo also hands us the non-obvious setting: cargo-deny defaults `yanked` to *Warn*, so the gate passes green on a yanked dependency unless you say otherwise. |
| A34 | **A timer event as the single scheduling primitive** — periodic work becomes an ordinary subscriber | Phase 7 runtime; possibly earlier | ~half day | *(repo 11)* Our 6.8.6 staleness alarm, the provisional-health watch and the CAS capture window are all "do this on a clock" problems currently solved three different ways. |
| A35 | **Define `BrokerAdapter` as an interface a second broker could implement**, even while only Kite does | Phase 7 | included in Phase 7 | *(repo 11)* vnpy's core ships no gateway, which forces the interface to be a real contract. The cheapest insurance against a Kite-shaped abstraction leaking through the whole execution path. |
| **A29** | **★ Add the flat DP charge per delivery sell, and a per-trade cost floor** | `app/trading/fees.py` (`FeeSchedule`) | ~2 hours | *(repo 10 + 6A)* Our schedule is otherwise correct but has no `dp_charge_per_sell`; Zerodha/CDSL levy a **flat ~₹13.5–20 per delivery sell scrip regardless of size**. A fixed cost disproportionately hits small positions — exactly what our notional cap produces and exactly the ₹1L / 1–2 position shape live will have. **We are under-costing the paper book, in the direction that flatters an already-negative expectancy.** |
| **A38** | **★★ A composable, point-in-time `Restrictions` interface consulted by the backtest, the order path AND the display path** — each tradability rule a *source* (T2T/-BE, circuit-band proximity, liquidity, market hours / `allow_offmarket_entry`, gate modes), composed, and answerable **as of a date** | new `app/signals/restrictions.py`; absorbs `eligibility.py`, the order-path gates and `circuit_guard`'s read | ~2–3 days | *(repo 14)* **Supersedes A30's implementation while keeping its goal.** Zipline's `HistoricalRestrictions` answers "was this restricted *on that date*" — the only correct backtest question, and one ours cannot ask at all. `_UnionRestrictions` composes sources, which is the structural fix for the fragmentation that already cost us **41/204 rows offering a Buy that could only 409** and five Buy surfaces needing retrofit. A new restriction then lands on every path by construction, not by remembering (subsumes A31 for this class). |
| A30 | *(superseded by A38)* Enforce circuit bands in the backtest as the order path does | `app/backtest/` | — | *(repo 10)* Goal retained, shape replaced — see A38. Kept for the finding: qlib warns explicitly when its `limit_threshold` is unset because an unset limit means the backtest trades stocks that were locked limit-up/down. |
| **A37** | **★ Cap fills at a fraction of the bar's traded volume, with impact rising faster than linearly above a threshold** | `paper_broker` fill model + `app/backtest/` | ~1 day | *(repo 14)* Zipline caps equity fills at **2.5% of bar volume** with **quadratic** price impact. Our 6.8.2 model has real half-spread and size-vs-top-of-book impact but **no participation cap** — our notional cap bounds rupees, not liquidity. **SRTL is the named case**: ₹39 micro-cap, 2,666 shares; a ₹1L position in a stock trading ₹5L/day is 20% of daily volume and is not fillable at the quoted price. |
| **A31** | **Standing rule: a realism constraint added to one execution path must be added to every path that produces a comparable number, in the same change** | rules + review checklist | ~1 hour to write | *(repo 10)* Now three instances: spread-aware fills but last-close marks (A21); circuit bands on the order path but not the backtest (A30); `MODE_FULL` subscribed but never verified (A25). Otherwise backtest, paper and live silently stop being comparable — the one property we need them to have. |
| A27 | **A notification config dry-run** (`--check-notify`-style) plus a `--no-notify` escape hatch | alongside A11 | ~2 hours | *(repo 9)* A11 runs unattended, so the first time it *should* fire is the worst time to discover the credentials are wrong. Validate the setup without spamming a real channel. |
| A28 | **Classify a delivery failure as retryable or not**, and return a structured per-channel dispatch result | alongside A11 | ~2 hours | *(repo 9)* Repo 4's "classify failures by whether a human can act", applied one level down to the transport. Combined rule: try, classify, record, never raise into the caller. |
| A26 | **Refuse loudly at a capacity boundary** — name the numbers and the remedy, never degrade silently | hot-set selection in `live_worker` | ~half day | *(repo 8)* They cap at Kite's `3 × 3000` tokens and refuse to start with an error stating the counts and two concrete fixes. **We had the opposite failure**: breadth alerts flooded the hot set and watchlist stocks silently stopped being scored. |
| **A21** | **★ Mark-to-bid, so marks match fills** — value longs at bid / shorts at ask using the depth we already capture, falling back to last when stale | `_open_book_mtm` in `app/services/daily_report.py`, and any unrealized-P&L surface | ~half day | *(repo 6A)* **An internal inconsistency in our own system**: since 6.8.2 our *fills* pay the real half-spread, but our *marks* still use the last 1m close. With 82% of NSE books wider than 2 bps and a ~25-position book, reported open-book MTM is systematically optimistic. The data is already there. |
| A22 | **Bracket sibling-quantity rebalance on partial fill** | Phase 7 order FSM | Phase 7 | *(repos 6A + 4)* Two independent projects hit this same failure — 6A factors it as a named function with tests; repo 4 called it the partial-fill mode "that took several iterations to fully pin down". Near-certain for us. |
| A23 | **Date-versioned fee schedule** (effective-dated registry) | `app/trading/fees.py` | ~half day | *(repo 6A)* Ours is *designed* for this — the docstring says "versioned by effective date" — but is a single constant set today. Indian STT rates change mid-year; a backtest spanning a change silently uses today's rates. |
| **A24** | **Never render a precise figure without its uncertainty** — no bare point estimate for a date, a target, or a "confidence" | standing rule; `.claude/rules/ui.md` + any predictive surface | ~1 hour to write down | *(repo 6C)* Their "probable exit date" is a calendar date with no volatility term that **does not even depend on the target price it is the date for**. A precise number reads as a confidence signal. Same failure as repo 3's vote-share-as-confidence and repo 1's placeholder-as-metric — and we are specifically exposed, because a 2–3%/day goal invites converting a wish into a timeline. |
| A19 | **Normalise components before summing into a composite risk scalar** | any future composite score | — | *(repo 5)* Their Equation 3 sums beta (~1), inverse liquidity (unbounded), sector concentration (0–1) and annualised vol (~0.2–0.5) at equal weights, then thresholds at 0.75 — whichever term is largest dominates, so the weights are decorative. |
| A20 | **A signed risk penalty that scales confidence, rather than a boolean gate** | overlay design | — | *(repo 5)* Their risk agent always enters synthesis with a negative sign and caps confidence at 60% on alert. Our overlays are on/off switches; **a modifier is closer to what the reverted regime gate should have been.** |
| A1 | **Two-tier model routing** (cheap extract pass / strong judge pass) for the research loop | daily-analysis + review-calendar tooling | ~half day when that work starts | Never in the money path. Applies the moment an LLM step enters the research loop. |
| A5 | **Self-documenting state schemas** — `Annotated[type, "meaning"]` on report/sidecar payload fields | sidecar + report payloads | ~2 hours | Field meaning currently lives in a docstring far from the type. |
| **A9** | **A progress envelope for long-running jobs** — `{phase, step, total_steps, message}` streamed over WS | `make analysis`, backtests, walk-forward replay, EOD ingestion | ~1 day | *(repo 3)* The one genuinely good idea in that repo, and it is LLM-agnostic. Several of our jobs run for minutes with no progress surface at all — the walk-forward replay alone is ~8 minutes of silence. |
| A6 | **Agent topology: independent analysts fan out, never chain** | any future agent graph | — | A standing note, not a task. Repo 2 chains three mutually independent agents and pays 3× latency for it. |
| A10 | **Emit running results mid-flight**, not only at completion | same surfaces as A9 | included in A9 | *(repo 3)* A partial verdict visible while the job runs. |
| A7 | *(repo 1)* **Artifact provenance on every reported number** — the generating service/query named beside the value | banners, registry rows | ~2 hours | Same item as U8, recorded here because it is a contract, not a widget: a number that cannot name its source is not auditable. |
| A8 | *(repo 1)* **Failure archive as a first-class store**, not prose | the H4 register's schema | included in H4 | Reverted gates (regime, R:R≥1) are permanent evidence and should be queryable, not narrated in memory files. |

**Overall, if only one thing is done anywhere: H1, then H2+U2 together.** H1 hardens the
instrument that both recent reversals proved we were missing. H2 is a half-day that
supplies the honest baseline every future gate argument should be measured against — and
it is the specific omission that let AgentQuant celebrate a Sharpe of 0.621 while
buy-and-hold quietly returned 102%. U2 is what stops that baseline from being ignored.

**Explicitly not recommended:** adopting any code from either repo; AgentQuant's
LLM-parameter-proposal pattern, harness-evolution line of work, Streamlit stack,
sidebar-driven layout or raw-dataframe rendering; QuantHarness's forced-trade design,
LLM-emitted risk-reward, natural-language confluence weighting, or vision-LLM chart
reading as a signal source.

## Testing queue

Test *concepts*, not code. Sourced mostly from qlib, which is the only repo here whose test suite
is worth studying as a design artifact.

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **T1** | **★ A point-in-time test anchored to a real, cited filing date** — assert a fundamental value changes on the publication date and not before, with the NSE/BSE announcement URL in the test | with MCE slice 5b (`market_cap` writer) | ~half day, *when 5b is built* | *(repo 10)* MCE 5b is the keystone blocker for everything fundamental, and it inherits the classic trap: using currently-reported financials for a date before the report existed. Nothing in our stack expresses "as known on date D". A test citing a real filing **cannot rot into tautology** and makes the look-ahead claim falsifiable. |
| **T7** | **Exhaustive-enum mapping test** — assert every variant of an enum is handled and deterministically ordered, so adding a variant without handling it **fails the suite** | gate modes, rejection reasons, sidecar readiness states | ~2 hours | *(repo 12)* We have already been burned by exactly this: *"v1's `unassessed` tripwire was IMAGINARY — 3 of 8 modes passed."* An enumeration not exhaustively handled, with no test to catch it. |
| **T8** | **★ A self-cleaning debt baseline (ratchet)** — allow known gaps so CI isn't red, **reject new ones**, and **reject baseline entries that are stale or already fixed** so the list can only shrink | `backend/tests/` + whatever audit script it guards | ~half day | *(repo 13)* Most known-failure allowlists rot into permanent amnesties that suppress real regressions. This one fails the build when an entry is no longer a problem, forcing removal. We have the shape (typecheck coverage gaps, `STATUS.html` prose duplicating gate modes) and no mechanism. |
| **T9** | **★ Turn the doc-sync ritual into failing tests** — a new `settings.*` without an `.env.example` line; a `docs/PHASES.md` `(updated …)` stamp older than the newest `docs/phases/*.md` change; a gate mode in `STATUS.html` disagreeing with `settings`. Report **all** violations in one pass | `backend/tests/` | ~1 day | *(repo 13)* **Our ritual is a procedure an agent must remember; theirs is a test that fails.** Our own lesson — *"a documented safety net is worth nothing without a test that fails when it lapses"* — was applied to our code and never to our process. The memory note *"grep the gate name on every flip"* is a human ritual standing in for a test. Subsumes and promotes **W3**. |
| **T10** | **★ Negative-space assertions via an `ExplodingObject`** — inject an object that raises on *any* attribute access where a dependency must never be touched | `backend/tests/` helpers | ~2 hours | *(repo 14)* Proves a code path does **not** use something — normally the hardest property to test. We hold three such claims by convention alone: **"frozen engine untouched"** (every overlay), **`circuit_guard` only READS the cache**, and overlays never seeing future data. Each is a documented safety net with no test that fails when it lapses — exactly the `unassessed` tripwire failure. ~15 lines. |
| **T13** | **Extend `incremental_equals_batch` across the indicator set, Wilder family first** | `engine/crates/engine-core/src/indicators/` | ~half day | *(repo 23)* We already have this test — on **two** indicators (`sma.rs`, `ema.rs`). **RSI/ADX/ATR do not have it**, and recursive smoothing makes them the most likely to diverge *and* the loosest in our parity tolerance (1e-6 vs 1e-9). si-dotnet tests every indicator through batch / incremental / streaming and requires agreement. |
| **T14** | **★ Anchor the fixture chain with hand-computed values** — ~20 Wilder-family values (RSI/ATR/ADX over a short series) derived by hand and pinned as a separate fixture | `engine/crates/engine-core/tests/fixtures/` | ~half day, once | *(repo 23)* Our oracle chain is **Rust ← Python ← pandas-ta** with **no external anchor**. If pandas-ta carried a convention bug — exactly the QuantStats failure (§22) — our fixtures would encode it and every parity test would pass forever, in green. si-dotnet commits **80 hand-calculated spreadsheets** for this reason. Fourth independent arrival at *anchor the test to something the code did not produce* (with T1, T11, H8). |
| **T12** | **Every non-obvious constant and formula in the trading layer records its origin** — a citation, a fitting procedure with its sample, or an explicit *"chosen by judgement on <date>, never validated"* | `app/trading/`, overlays, gate thresholds | ~half day | *(repo 22)* Only `atr.py` (Wilder) and `deflated_sharpe.py` (Bailey & López de Prado) cite anything. The frozen engine has `SIGNAL_ENGINE.md`, which is better — **but the trading layer has no spec and is exactly where our churn is**: `profit_lock`'s ladder (+₹2k breakeven, peak−₹1k above ₹3k) and the gate thresholds are fitted constants nobody can re-derive. **The third option matters most** — it makes unvalidated knobs visible to the review calendar instead of indistinguishable from derived ones. Same criticism levelled at abu's `0.668`, applied to us. |
| **T11** | **★ Pin PSR/DSR against independently derived values in a regression test** — including a normal-series case where the `SR²` coefficient must be `+0.5`, so the kurtosis convention can never silently flip | `backend/tests/` + `deflated_sharpe.py` | ~2 hours | *(repo 21)* The cross-check that validated our implementation was manual and one-off. QuantStats gets this exact thing wrong — pandas returns **excess** kurtosis into a formula expecting **Pearson** — and its PSR is overstated as a result. Same discipline as T1: **anchor the test to a value you can derive independently.** |
| T2 | **Lifecycle-boundary tests for the execution simulator** — first step, start mid-stream, stop early, stop at benchmark | Phase 7 order FSM | Phase 7 | *(repo 10)* Not "does it run" but "does it behave when interrupted". Pairs with A22 (bracket sibling qty on partial fill) and A16 (durable repair queue) — both lifecycle-boundary bugs other people found the hard way. |
| T3 | **Parametrised fill tests under a participation limit** | if/when we add a volume-participation cap | — | *(repo 10)* We model spread and size-vs-top-of-book impact; we do not cap participation by volume. This is the test shape if we do. |
| T4 | **Explicit NaN / corner-case tests on every numeric boundary** (LTP, ATR, confidence, R:R) | `backend/tests/` | ~half day | *(repo 10)* Earned: a non-finite Redis LTP once 500'd the signal detail endpoint because `Decimal("nan")` parses without raising. |
| T5 | **Crash-path tests** — assert correct exit when the process dies | worker/session entry points | ~half day | *(repo 10)* The general form of repo 4's "orphaned protection intents drain at next session entry". |
| T6 | **Ordered pipeline-stage integration tests** (numeric prefixes so a failure names the stage) | EOD ingestion → enrichment chain | ~half day | *(repo 10)* Our ingestion chain has this exact shape and no staged integration test. |

## Workbench queue

Claude Code tooling and repo rules worth borrowing. Cheap, and they change how every future
session behaves.

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **W1** | **Make doc/code precedence an explicit rule** — "if a doc disagrees with the code, the executable content wins; fix the doc in the same change" | CLAUDE.md | ~15 min | *(repo 9)* We hold this as a habit ("trust the artifact over the checkbox") but state it as a value, not a precedence rule. A rule tells a future session **what to do** on finding a conflict, not merely that conflicts are bad. |
| **W2** | **"Do not add parallel implementations"** as a written rule | CLAUDE.md / rules | ~15 min | *(repo 9)* **The rule with the most evidence behind it for us**: our review round found **five separate Buy surfaces**, one unwired, and eligibility gating had to be retrofitted across all of them. |
| W6 | **The MCP exposure model, if we ever open the platform to an agent** — a dedicated versioned `agent/v1` API (never the internals), R vs R/W scopes tabulated per tool, trading tools separately safety-gated, **two distinct tokens** (inbound client auth ≠ upstream gateway), transport that **fails closed** with named escape hatches, explicit "never put a token in a prompt/log/screenshot" hygiene, and **bounds on every long-running job** | recorded, not queued | — | *(repo 17)* We are a Claude Code shop already driving `make analysis` through skills, so this is the design to copy rather than reinvent under time pressure. The load-bearing decision is the first one: **the agent gets an API, not the internals.** |
| W3 | **Same-commit config hygiene** — a new config item updates `.env.example` and its docs in the same change | rules | ~15 min | *(repo 9)* The narrow checkable instance of our doc-sync ritual. Config drift is what bit us when a `.env` gate flip did not reach a running process. |
| W4 | **Decide the git boundary deliberately** — theirs forbids `commit`/`tag`/`push` without confirmation; ours reserves push only | CLAUDE.md | ~15 min | *(repo 9)* Worth writing down rather than inferring. The current working pattern (commit freely to a worktree branch, hold pushes) is fine — but it should be stated. |
| W5 | **Forbid hardcoded model names alongside secrets, paths and ports** | rules | ~15 min | *(repo 9)* The non-obvious clause. Our analogue: `STATUS.html` hardcodes gate modes in prose and an ASCII diagram, so a mode flip silently falsifies it — a config value copied somewhere that cannot track it. |

## What the repos independently confirm

Three unrelated projects — one hobby, one academic, one commercial — landing on the same
lessons is worth more than any one of them:

0. **Seven of thirty advertise numbers or fields their own code cannot produce — and the
   exception is instructive.** AgentQuant's `generalization_gap` is `max(avg − best, 0)` ≡ 0
   yet ships as 0.124 decaying to 0.048; QuantHarness's only look-ahead holdout is a
   commented-out line and its eval script is absent; ai-quant-agents markets a Risk Manager
   veto behind a `risk_approved` flag that is **hardcoded true**, plus an example output
   whose four actionable fields are unconditionally `{}`.

   QuantAgents-NSE makes it four of five: a commit headline of *"improve backtester **to**
   Sharpe 0.237, CAGR 8.9% vs Nifty 8.4%"* resting on a backtest that fills on the signal
   bar's close, over a hindsight-picked survivor universe, **with two of its four agents
   assigned to variables that are never read**.

   SentimentStock adds a fifth: *"Hinglish NLP sentiment analysis"* and *"LSTM-style stock
   predictions"* over a `Math.sin(seed)` generator.

   **Two repos break the streak, and how they break it is the lesson: neither makes a
   performance claim at all.** quant-agent (repo 4) is a live trading system; PaperTrade-India
   (6A) is broker infrastructure. Both are among the best-engineered here, and both simply
   have nothing to claim — one declines to, the other has no strategy to claim for. Its only numeric claim (874 tests) *understates* reality
   (1,344), and both architectural claims I tested — Python-computed R/R, schema-enforced
   CoT — are true. So the rule is not "public repos lie"; it is narrower and more useful:
   **the claims that fail audit are almost always the performance claims**, and the repos
   that make none are the ones worth reading. Recompute every headline number before quoting
   it — and treat a repo that declines to claim as a positive signal, not a gap.
1. **A simple baseline matches the elaborate system — and is almost never run.** Buy-and-hold
   beat AgentQuant's agent (+102.4% vs +0.7%); logistic regression matches QuantHarness's
   four-agent GPT-4o vision pipeline on 7 of 8 assets; QuantAgents-NSE's four agents beat the
   Nifty by 0.5pp at Sharpe 0.237 — and two of those four were wired to nothing, so the number
   came from two. Repo 7 is the purest case: it selects an LSTM over three other models on RMSE
   and **never runs persistence** ("tomorrow = today"), the one baseline that would plausibly
   have beaten all four. **The operational rule: when a repo picks a winner, look first at what
   it did not compare against.** **Neither repo leads with this, and both ship the data that
   shows it.** Our H2/U2 (benchmark as a row in the same sort order) is the structural
   defence — it is not a reporting nicety, it is the thing that stops this happening to us.
2. **A guard that cannot return false shows up in four of thirty — and it is the single most
   repeated defect in this log.** AgentQuant's `generalization_gap = max(avg − best, 0)` is
   identically zero; ai-quant-agents' `risk_approved = "risk" not in decision.lower()` where
   `decision ∈ {BUY,HOLD,SELL}` is always true; repo 7's `is_breaking_out` calls a predicate
   that returns the strings `'YES'`/`'NO'`, both truthy, so its consolidation filter never
   applies. Three different root causes, one symptom. **The test is mechanical: for every
   guard, name the input that makes it fail — if you cannot, it is not a guard.** Our own
   `unassessed` tripwire failed exactly this (3 of 8 modes passed).

   **Repo 16 adds the most instructive variant: the code was fine and the *configuration default*
   was not.** Its CI advertised a "yanked crates" gate, but `cargo-deny` defaults `yanked` to
   *Warn* and only exits non-zero on Deny-level findings — so a yanked dependency produced a
   warning and a green run. **A gate can be disarmed by a default you never chose**, which means
   the test extends: name the input that makes it fail *and confirm the tool would actually
   fail on it*.
3. **Dead code advertised as a feature shows up in three of thirty.** AgentQuant fits an HMM
   per call and discards the result, and never loads the `.harness/v6_research.json` it calls
   "the production harness"; ai-quant-agents populates `suggested_action` never; QuantAgents-
   NSE computes a regime filter and a risk score into variables nothing reads. **In each case
   the README describes the feature and the code disconnects it** — so "does this code path
   affect the output?" is a faster audit than reading the logic, and `grep` answers it.
4. **The guard that matters is the one that is structural.** AgentQuant's generalization
   gap was a metric that could only return zero; QuantHarness's look-ahead holdout is a
   commented-out line beside the live path. Both are documented safety nets with nothing
   that fails when they lapse — the same finding our own bug-hunter round produced when it
   showed the `unassessed` tripwire was imaginary (3 of 8 modes passed).
5. **Published work stops where the hard part starts — with two exceptions.** None of the
   first three has position sizing, risk limits, or a portfolio. QuantHarness is titled "for High-Frequency Trading"
   and models no position at all; ai-quant-agents leaves `suggested_action` empty. The
   runtime plumbing we have deferred to Phase 7 is not the boring part of this field — it
   is the part almost nobody does. **quant-agent and PaperTrade-India are the exceptions that prove it**:
   the only two with a real broker/order lifecycle. quant-agent needed two audits finding 82
   defects — one leaving positions naked overnight — to get there; PaperTrade-India needed
   543 tests. Nobody arrives at this cheaply.
6. **"Confidence" is repeatedly a share, not a probability.** ai-quant-agents divides the
   modal vote by the total and calls it confidence; agents sharing a model and prompt are
   not independent estimators, so their agreement is correlated by construction. Our own
   confluence normalises by the weight of factors that *scored*, which is the same shape of
   error and is how SRTL entered on a single indicator. **U17 (show the distribution, not
   the scalar) is the fix, and it generalises.**
7. **The two failure modes are opposite, and ours is the safer one.** Repos 1–3 have
   validation theatre with no production system. Repo 4 has a production system with no
   validation. We have real validation and no production system yet — and of the three
   states, only ours makes the missing half safe to build. An unvalidated system that runs
   flawlessly is still unvalidated; it just loses money with better uptime.
8. **The repos worth reading are the ones with nothing to sell — now strong enough to use as a prior.** Across thirty repos, **twelve decline to publish any performance number**, and they are, without exception, the ones whose code was worth reading (quant-agent, PaperTrade-India, express-option-chain, daily_stock_analysis, qlib, vnpy, turbovec, QuantDinger, QUANTAXIS). Most are
   infrastructure; one is a product that ships the *measuring instrument* and lets you run it on
   your own history. The ones that fail are all selling a result: an evolved harness,
   a beaten benchmark, an agent consensus, a probable exit date, an LSTM. **The presence of a
   headline performance number is, empirically, the best available predictor that a repo's
   claims will not survive contact with its own source** — and its absence is the best
   predictor that the code is worth reading.
9. **Two independent projects hitting the same thing makes it near-certain for us.** Bracket
   sibling quantity on partial fill was found the hard way by repo 4 *and* factored as a named
   function in 6A. **And push notification is now a first-class primitive in three independent
   mature systems** — repo 4's noise-policy notifier, repo 9's multi-channel dispatcher, vnpy's
   `MainEngine.send_notification`. Three mature systems independently concluding that an
   unattended trading system must be able to speak settles A11: it is not a nice-to-have. That is the strongest signal in this document about what Phase 7 will
   actually cost — stronger than either repo alone, and the reason A22 is queued before we
   have written a line of it.
10. **One line decides whether a system is honest: what it does with the ambiguous case.**
    Repo 9's bar resolver returns `None` — excluding the record from scoring — for any unknown
    or calendar-inconsistent session phase, and says so: *"it fails closed."* Qlib's PIT layer
    returns `NaN` rather than forward-filling; repo 12 ships a test literally named
    `test_api_error_fails_closed`. **Three independent codebases name and test this as a
    principle**, which is why it sits this high. Every repo that
    failed this audit resolved ambiguity the other way: a missing holdout became the full
    window, an unrecognised phase became "close enough", a `'NO'` string became `True`.
    **Failing closed is cheap, usually one line, and it is the single clearest separator
    between the repos worth reading and the rest.** It is also, directly, why our shadow-first
    overlay pattern and fail-open-with-an-alarm design are the right instincts — provided the
    alarm exists (A11, A25).
11. **Realism gets added to one path and forgotten on the others.** Three separate instances in
    our own code, each surfaced by a different repo: spread-aware fills with last-close marks
    (A21), circuit bands on the order path but not the backtest (A30), a `MODE_FULL`
    subscription never verified (A25). None is a bug in isolation; together they mean
    **backtest, paper and live results silently stop being comparable** — which is the one
    property the whole measurement apparatus depends on. Hence A31 as a standing rule.
12. **The scary part of Phase 7 is not the part we thought.** vnpy runs a decade of real-money
    trading on a **145-line** event bus. The runtime plumbing our NautilusTrader review flagged
    as the daunting gap is, in its core, small and well understood. **What actually costs is the
    order lifecycle and reconciliation** — 82 defects across two audits in repo 4, 543 tests in
    6A, and the same partial-fill bug found independently by both. Budget Phase 7 accordingly:
    little for the bus, a lot for the FSM.
13. **Test the test.** Repo 12's audit tool ships a worked example in which **24 pure-noise
    series produce a 1.11 Sharpe and the audit correctly rejects them** — a negative control
    proving the detector fires. Nothing else in thirteen repos does this, and it is the natural
    extension of our own rule that *a metric which cannot come out badly is not a metric*: a
    **bar** that has never been shown to reject anything is in the same position. Hence H8.
14. **Our most repeated process risk has the same fix as their most repeated code defect.**
    Across seventeen repos the single most common defect is *a guard that cannot fail*. Our own
    equivalent, in process rather than code, is *a ritual nobody is forced to run* — the doc-sync
    ritual, the review calendar, the memory note that says "grep the gate name on every flip".
    AKShare shows the fix is identical in both cases: **make it a test that fails.** We already
    drew this conclusion once, about code, when the `unassessed` tripwire turned out to be
    imaginary — and never applied it to our process. Hence T8 and T9.
15. **★ The strongest guarantee is the one that removes the syntax for the mistake — and the
    position on that spectrum predicted the outcome every time.** §21.3 lays out the full axis,
    from Zipline (look-ahead *not expressible*) through qlib and repo 9 (prevented, fails closed),
    to vectorbt (**the default unless the caller remembers `fshift(1)`**), to repos 2 and 5 where
    it simply happened. **Repo 5 is what the vectorbt row produces downstream**, and its author
    almost certainly never saw it as a choice. Look-ahead
    entered this log four different ways — a commented-out holdout (repo 2), same-bar execution
    (repo 5), a scaler fit over the test window (repo 7), a phase-unaware entry bar (repo 9 got
    this right). Every one was *a mistake someone could make*. Zipline is the only repo where a
    strategy author **cannot express it**: `BarData` is bound to the simulation clock and there is
    no API for a future bar. Qlib reaches the same place from the other direction with `P($$field)`
    PIT syntax. **Rules and reviews catch mistakes; design prevents them** — and where we build new
    evaluation surfaces (MCE 5b above all), an accessor bound to an "as of" timestamp is cheaper
    than a rule and cannot lapse.
16. **Licence is a first-class review criterion, and it decides before merit does.** Across thirty
    repos the spectrum runs **MIT/Apache → no LICENSE at all** (no grant of rights) **→ LGPL →
    GPL-3 → Commons Clause** (bites only at commercialisation) **→ unilaterally mutable
    proprietary with a monitoring duty on the user** (StockSharp, §24.1 — where even *viewing* is
    nominally gated). **Only the first tier is safe to build on, and the gaps between tiers are
    differences in kind.** StockSharp is "vnpy for .NET" and **vnpy is MIT**, so the risk bought
    nothing. Earlier detail: mostly MIT or Apache, one **GPL-3** (abu — unadoptable for us regardless of quality),
    one **LGPL** (NautilusTrader), one **Apache-2 + Commons Clause** (vectorbt — *not open source*,
    and the restriction only bites at commercialisation, i.e. when removal is most expensive),
    and **four with no LICENSE file at all**
    (repos 5, 6B, 6C, and 3's org mismatch) — which is *more* restrictive than GPL, since no
    licence means no grant of rights. **vnpy being MIT is the single most consequential licence
    fact in this document**, because it makes the one repo we would most plausibly borrow from
    (Phase 7 runtime) legally borrowable, where NautilusTrader is not.
17. **A repo outside our domain can still be worth reviewing — the filter is shared *stack* or
    shared *discipline*, not shared subject.** turbovec is vector search for RAG and has nothing
    to say about trading; its domain was rejected without stretching for a use. But it shares our
    Rust + PyO3 wheel shape, and that one structural similarity carried a real finding (A39)
    across. **The corollary matters more: when a repo shares neither stack nor discipline,
    "no" is the correct and complete answer**, and manufacturing relevance would have cost more
    than it returned.
18. **Alerting splits cleanly into platform and domain, and almost nobody has both.** QuantDinger
    ships Prometheus/Alertmanager rules that are **entirely infrastructural** — API down, worker
    missing, error rate, latency, exporters down — and **not one is about the market**. We are the
    mirror image: our 6.8.6 staleness alarm and readiness banners are *domain* alerts, and we have
    no infrastructural alerting at all. **Neither half substitutes for the other**: a green
    Prometheus board tells you nothing about a feed that returned yesterday's prices, and a
    readiness banner tells you nothing about a worker that never started. A11 is the delivery
    channel; A40 (worker liveness) is the first infrastructural thing worth delivering through it.
19. **★ The published literature's own median is a Sharpe of 0.37, and half of it cannot be
    distinguished from zero on its own sample.** From 4,843 replications (repo 19) — the only
    population-level evidence in this entire review, and the correct yardstick for our own
    expectations. Two consequences we had not priced: **required sample grows with the inverse
    square of the edge** (a 0.37 Sharpe needs ~28 years; our gates are judged on 33–72 trades),
    and **the median strategy's beta of +0.17 accounts for roughly half its apparent edge**, which
    we cannot even measure because we compute no beta anywhere. **A −0.303R book measured honestly
    is an early-stage position on this distribution, not an anomalous one** — and a 2–3%/day target
    is not on the distribution at all.
20. **Selection effects survive into presentation layers, where no code is wrong.** Repo 19 is the
    most honest list reviewed — it discloses its replication record in plain language above the
    tables — and its showcased strategies still median **1.06** against a population median of
    **0.37**, because a list shows its best. Nothing is false; a skimming reader is simply
    mis-calibrated by 3×. **Our exact equivalent: a readiness banner shows the gates we are
    watching, which is a selected sample of the gates we have tried** — which is why U4 (a
    trials-attempted counter) exists and why it matters more than it looks.
21. **★ Check every statistical instrument against an independent implementation.** We built PSR
    from the Bailey & López de Prado paper; QuantStats — the field's most-used tearsheet library —
    implements the same formula. Comparing them cost twenty minutes and returned three things:
    **our implementation is correct**, theirs feeds pandas **excess** kurtosis into a formula
    expecting **Pearson** (so its PSR is systematically *overstated*), and its `annualize` flag
    multiplies a probability by √252. **The most-used implementation in a field is not a
    reference — it is another sample.** Hence T11.
22. **A constant with no recorded origin can only be defended by whoever remembers choosing it.**
    FinanceToolkit cites formulas to source and page and makes convention choices explicit
    parameters; abu ships `0.668` and `0.91` with no derivation; QuantStats' bug was an *implicit*
    convention. **We are in the middle**: the frozen engine has `SIGNAL_ENGINE.md` (better than
    citations — versioned and regression-gated), but the **trading layer has no spec at all**, and
    that is exactly where the reverted gates and the fitted ladder constants live. The cheapest fix
    is not to derive them retroactively but to **mark the ones that were judgement calls**, so the
    review calendar can see them. Hence T12.
23. **The most useful findings came from the repos closest to our own stack, and they were
    about *us*.** PaperTrade-India exposed that our fills are spread-aware while our marks are
    not (A21); express-option-chain exposed that we harvest depth from `MODE_FULL` ticks
    without ever checking the mode, on a path built to fail open (A25). **Neither was a defect
    in their code — both were gaps in ours, visible only because someone else had solved the
    same problem and left the guard in.** The lesson for the remaining repos: prioritise the
    ones sharing our exchange, broker, or stack over the ones sharing our ambition.
