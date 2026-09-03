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

So three numbered queues, kept separate because they land in different places and have
different owners: **`H`** analysis/methodology · **`U`** UI/UX · **`A`** architecture.

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

## What the repos independently confirm

Three unrelated projects — one hobby, one academic, one commercial — landing on the same
lessons is worth more than any one of them:

0. **Five of eight advertise numbers or fields their own code cannot produce — and the
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
1. **A simple baseline matches the elaborate system.** Buy-and-hold beat AgentQuant's agent
   (+102.4% vs +0.7%); logistic regression matches QuantHarness's four-agent GPT-4o vision
   pipeline on 7 of 8 assets; QuantAgents-NSE's four agents beat the Nifty by 0.5pp at
   Sharpe 0.237 — and two of those four were wired to nothing, so the number came from two. **Neither repo leads with this, and both ship the data that
   shows it.** Our H2/U2 (benchmark as a row in the same sort order) is the structural
   defence — it is not a reporting nicety, it is the thing that stops this happening to us.
2. **Dead code advertised as a feature shows up in three of eight.** AgentQuant fits an HMM
   per call and discards the result, and never loads the `.harness/v6_research.json` it calls
   "the production harness"; ai-quant-agents populates `suggested_action` never; QuantAgents-
   NSE computes a regime filter and a risk score into variables nothing reads. **In each case
   the README describes the feature and the code disconnects it** — so "does this code path
   affect the output?" is a faster audit than reading the logic, and `grep` answers it.
3. **The guard that matters is the one that is structural.** AgentQuant's generalization
   gap was a metric that could only return zero; QuantHarness's look-ahead holdout is a
   commented-out line beside the live path. Both are documented safety nets with nothing
   that fails when they lapse — the same finding our own bug-hunter round produced when it
   showed the `unassessed` tripwire was imaginary (3 of 8 modes passed).
4. **Published work stops where the hard part starts — with two exceptions.** None of the
   first three has position sizing, risk limits, or a portfolio. QuantHarness is titled "for High-Frequency Trading"
   and models no position at all; ai-quant-agents leaves `suggested_action` empty. The
   runtime plumbing we have deferred to Phase 7 is not the boring part of this field — it
   is the part almost nobody does. **quant-agent and PaperTrade-India are the exceptions that prove it**:
   the only two with a real broker/order lifecycle. quant-agent needed two audits finding 82
   defects — one leaving positions naked overnight — to get there; PaperTrade-India needed
   543 tests. Nobody arrives at this cheaply.
5. **"Confidence" is repeatedly a share, not a probability.** ai-quant-agents divides the
   modal vote by the total and calls it confidence; agents sharing a model and prompt are
   not independent estimators, so their agreement is correlated by construction. Our own
   confluence normalises by the weight of factors that *scored*, which is the same shape of
   error and is how SRTL entered on a single indicator. **U17 (show the distribution, not
   the scalar) is the fix, and it generalises.**
6. **The two failure modes are opposite, and ours is the safer one.** Repos 1–3 have
   validation theatre with no production system. Repo 4 has a production system with no
   validation. We have real validation and no production system yet — and of the three
   states, only ours makes the missing half safe to build. An unvalidated system that runs
   flawlessly is still unvalidated; it just loses money with better uptime.
7. **The repos worth reading are the ones with nothing to sell.** Across eight, the two that
   survive audit cleanly (quant-agent, PaperTrade-India) are both *infrastructure* — a
   personal trading harness and a broker simulator. The ones that fail are all selling a
   result: an evolved harness, a beaten benchmark, an agent consensus, a probable exit date.
   **The presence of a headline performance number is, empirically, the best available
   predictor that a repo's claims will not survive contact with its own source.**
8. **Two independent projects hitting the same bug makes it near-certain for us.** Bracket
   sibling quantity on partial fill was found the hard way by repo 4 *and* factored as a named
   function in 6A. That is the strongest signal in this document about what Phase 7 will
   actually cost — stronger than either repo alone, and the reason A22 is queued before we
   have written a line of it.
