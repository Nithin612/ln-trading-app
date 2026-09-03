# Quant / AI-agent repo findings

A running review log. Each external repo the user shares gets one section: what it is,
what survives scrutiny, what we should harvest, and what we should refuse. The last
section is the consolidated **harvest queue** — the only part that should ever turn into
work.

Ground rule for this document, and the reason it exists in this form: we have twice
promoted a gate on an argument and had to revert it (regime gate, R:R≥1 — see the
CLAUDE.md hard constraint #8). **A claim in someone else's README is exactly the class of
unchecked premise that rule was written about.** So every number quoted below was
recomputed from the repo's own code and committed data, not read off the README. Where
the README and the code disagree, that disagreement is itself reported as a finding.

| # | Repo | Reviewed | Verdict |
|---|---|---|---|
| 1 | [OnePunchMonk/AgentQuant](https://github.com/OnePunchMonk/AgentQuant) | 2026-09-03 | **Harvest 4 ideas, adopt no code, reject the thesis** |

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

## 1.6 The most useful thing in the repo is a warning

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

# Consolidated harvest queue

Ranked by value-to-us ÷ effort. **Nothing here is authorised work** — items enter
`docs/PHASES.md` only on the user's say-so, and we remain in watch mode to Fri 2026-09-04
with no money-path build. Every one of these is measurement, not money path.

| # | Item | Where it lands | Effort | Why now |
|---|---|---|---|---|
| **H1** | **Moving-block bootstrap p5 Sharpe** beside PSR/DSR/MinTRL | `app/services/deflated_sharpe.py`; one extra line per readiness banner | ~half day + tests | Non-parametric complement to a bar whose own weakness is the independence assumption. Automates the tail-robustness check that constraint #8 currently asks me to do by hand, and that the market-regime trimmed-mean sign flip proved we need. |
| **H2** | **Buy-and-hold benchmark line in the daily report** | `app/services/daily_report.py`, reading the existing `index_ohlcv_1d` (782 bars/index, already backfilled) | ~half day | We do not have one — I checked; `benchmark.py` is per-signal relative strength, not a portfolio baseline. AgentQuant's most sobering number was buy-and-hold beating five years of agent work, and it was invisible until someone opened a CSV. Our book is **−0.303R expectancy**; the honest denominator is what NIFTY did over the same window. Cheap, and it reframes every subsequent gate argument. |
| **H3** | **Re-frame the VIX companion as a trailing percentile** | `app/signals/market_regime.py` | ~1 day | Converts a knob blocked on backfill (`absolute 20`, US-derived, "too shallow to §8-validate") into a self-calibrating, distribution-free one. Does **not** promote anything — market-regime stays shadow and still owes its count and DSR bar. |
| **H4** | **Gate/hypothesis register as data** | new table or a `docs/` machine-readable file: gate · mode · pre-registered prediction · bar · current count · verdict · review-due | ~1 day | Constraint #8 makes me the owner of the review calendar and requires me to raise items *unprompted*. That calendar is prose today. Modelled on `AlphaStore`'s schema, not its code. Would also give the failed-hypothesis archive a home (regime gate, R:R≥1 already populate it). |
| H5 | `WarmupEnforcer` / `@enforce_lookback` as a runtime invariant | `app/analysis/` boundary — **frozen engine, so overlay//caller side only** | ~1 day | Turns a review-convention into a loud failure. Low urgency: no look-ahead bug is currently suspected. |
| H6 | `MAX_RATIO` sentinel instead of `inf` for degenerate ratios | wherever R:R / Calmar-like ratios are computed | ~1 hour | We have the `RR≈228` tiny-SL artifact on record. Trivial hygiene. |
| H7 | Sharpe-decay alarm on shadow gates | daily report / readiness banners | ~1 day | The regime gate sat `NOT READY` for 7 report days before action. Detection existed; alarming did not. Partly subsumed by H4. |

**If only one thing is done: H1, then H2.** H1 hardens the instrument that both recent
reversals proved we were missing. H2 is a half-day that supplies the honest baseline every
future gate argument should be measured against — and it is the specific omission that let
AgentQuant celebrate a Sharpe of 0.621 while buy-and-hold quietly returned 102%.

**Explicitly not recommended:** adopting any AgentQuant code, the LLM-parameter-proposal
pattern, or anything from the harness-evolution line of work.
