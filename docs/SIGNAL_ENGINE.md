# Signal Engine Specification

This is the heart of the system. Every rule here was distilled from the user's masterclass notes plus widely-accepted technical-analysis practice. Implement exactly as specified; raise design questions before deviating.

---

## 1. Core philosophy

A "signal" is the output of multiple independent indicators **agreeing at the same price level**. Single-indicator signals (e.g., "RSI dropped below 30, buy!") are noise — they're the reason 90% of retail traders lose money. Our edge is **confluence**: requiring 5–7 conditions to align before recommending a trade. This is the formalization of the masterclass's Double Confirmation (DC1/DC2) principle.

A signal has four parts:
1. **Direction** — `BUY` (long) or `SELL` (short)
2. **Classification** — `scalp`, `intraday`, `swing`, or `positional`
3. **Levels** — entry price, stop-loss, take-profit, suggested quantity
4. **Justification** — which factors fired, their individual scores, the final confidence percentage

---

## 2. The factor universe

These are all the inputs the engine evaluates. Each returns a score from `-1.0` (strongly bearish) to `+1.0` (strongly bullish), with `0.0` meaning "neutral / not applicable."

### 2.1 Single-candlestick patterns

Implemented in `backend/app/analysis/patterns/single.py`. Each detector takes the latest N candles and returns a tuple `(detected: bool, score: float, explanation: str)`.

| Pattern | Trigger | Score |
|---|---|---|
| Marubozu Bullish | Body ≥ 95% of total range, green | +0.8 |
| Marubozu Bearish | Body ≥ 95% of total range, red | -0.8 |
| Doji | \|close − open\| ≤ 5% of total range | 0 (indecision; only useful in context) |
| Spinning Top | Body ≤ 30% of range, upper & lower wicks similar | 0 (indecision) |
| Hammer | Body in upper third, lower wick ≥ 2× body, at swing low | +0.7 |
| Hanging Man | Same shape as Hammer, but at swing high after uptrend | -0.6 |
| Shooting Star | Body in lower third, upper wick ≥ 2× body, at swing high | -0.7 |
| Paper Umbrella | Same shape as Hammer, anywhere; lower confidence than Hammer-at-support | +0.4 |

**Critical:** Pattern detection must be **context-aware**. A hammer mid-trend has no value; a hammer at a known support zone is high-confidence. Patterns get full credit only when location-confirmed (see Section 2.5).

### 2.2 Multi-candlestick patterns

Implemented in `backend/app/analysis/patterns/multi.py`.

| Pattern | Trigger | Score |
|---|---|---|
| Bullish Engulfing | Red candle followed by green candle whose body fully covers prior body | +0.9 |
| Bearish Engulfing | Mirror of above | -0.9 |
| Bullish Harami | Large red, then small green inside prior body | +0.5 |
| Bearish Harami | Large green, then small red inside prior body | -0.5 |
| Piercing Pattern | Red candle, then green candle opening below red's close and closing > 50% into red's body | +0.7 |
| Dark Cloud Cover | Mirror of Piercing | -0.7 |
| Morning Star | Red → small body (any color) gapping down → green closing > 50% into first red | +0.95 |
| Evening Star | Mirror | -0.95 |

### 2.3 Indicators

Implemented in `backend/app/analysis/indicators/`. Use `pandas-ta` or `TA-Lib`; **never roll your own indicator math from scratch** unless documented and tested against a known-good source.

| Indicator | Bullish condition | Score |
|---|---|---|
| RSI (length 14) | RSI between 30 and 50 and rising (RSI[t] > RSI[t-1]) | +0.6 |
| RSI Divergence | Price makes lower low but RSI makes higher low (length 10 per masterclass) | +0.8 |
| MACD (12,26,9) | MACD line crosses above signal line | +0.7 |
| MACD Histogram | Histogram rising from negative toward zero | +0.4 |
| EMA Cross | 20 EMA crosses above 50 EMA (golden-cross-lite) | +0.6 |
| Price vs EMA | Close > 50 EMA and 50 EMA > 200 EMA | +0.5 |
| Multibagger Setup | 20 EMA within 2% of 200 EMA, breakout candle (per masterclass) | +0.9 |
| ADX + DI | ADX > 25 and +DI > -DI | +0.6 |
| Bollinger Bands | Close touches lower band then closes back inside on next candle | +0.5 |
| Volume | Current candle volume ≥ 1.5× 20-period average | +0.5 (confirms whatever else fired) |

Bearish counterparts use mirrored conditions returning negative scores.

### 2.4 Trend (Dow Theory)

Implemented in `backend/app/analysis/structure/dow.py`.

Computes swing highs and swing lows over the last 20 candles using a simple pivot algorithm (a candle is a swing high if its high is greater than the highs of N candles on each side; N=3 for intraday, N=5 for daily).

| Condition | Score |
|---|---|
| Higher highs AND higher lows | +0.7 (confirmed uptrend) |
| Lower highs AND lower lows | -0.7 (confirmed downtrend) |
| Mixed / sideways | 0 |
| Recent break of trend (last 3 candles) | flip sign of prior trend, half magnitude |

### 2.5 Support / Resistance + Demand / Supply zones

Implemented in `backend/app/analysis/structure/levels.py`.

**S/R lines** are drawn at swing highs/lows that have been tested at least twice without breaking. Stored in `support_resistance_levels` table per stock with timestamps of touches.

**Zones** (masterclass concept, Class 6) are wider areas:
- *Demand zone:* the last red candle (including wick) before a resistance-breakout green rally
- *Supply zone:* the last green candle (including wick) before a support-breakdown red drop

| Condition | Score |
|---|---|
| Price within 0.5% of obvious support, bullish pattern present | +0.8 |
| Price within 0.5% of obvious resistance, bearish pattern present | -0.8 |
| Price reaching demand zone with reversal pattern (DC1) | +0.85 |
| Price reaching supply zone with reversal pattern | -0.85 |
| Price breaking above resistance with body + 1.5× volume (RRBO) | +0.9 |
| Same breakdown below support | -0.9 |

### 2.6 Fibonacci retracement

Implemented in `backend/app/analysis/structure/fibonacci.py`.

Auto-draws fib from the last major swing high → swing low (uptrend retrace) or vice versa. Scores:

| Condition | Score |
|---|---|
| Price bouncing from 0.5 retracement | +0.4 |
| Price bouncing from 0.618 retracement (golden ratio) | +0.6 |
| Price bouncing from 0.786 (deep retrace) | +0.4 |
| Price breaks 1.0 (full retrace) | -0.5 (trend invalidated) |

### 2.7 FII / DII institutional flow (aftermarkets.in-inspired)

Implemented in `backend/app/analysis/structure/institutional.py`. Daily FII/DII data ingested from NSE in Phase 4.

| Condition (last 5 trading days, aggregated) | Score |
|---|---|
| FII net buying > ₹2,000 Cr cumulative | +0.5 |
| FII net selling > ₹2,000 Cr cumulative | -0.5 |
| DII net buying > ₹1,500 Cr while FII selling (domestic absorption) | +0.3 |
| Both FII and DII net buying same sector | +0.7 |

Stock-specific institutional moves (block deals, bulk deals from BSE/NSE) add ±0.4.

---

## 3. The confluence scorer

Implemented in `backend/app/analysis/confluence.py`.

### Algorithm

```python
def score_signal(stock_id: int, timeframe: str, candles: pd.DataFrame) -> Signal | None:
    factors = run_all_factors(stock_id, timeframe, candles)
    # factors: list[FactorResult] each with .name, .weight, .score (-1 to +1), .explanation

    total_weighted_score = sum(f.weight * f.score for f in factors)
    total_weight = sum(f.weight for f in factors if f.score != 0)
    if total_weight == 0:
        return None

    normalized = total_weighted_score / total_weight  # -1 to +1
    confidence_pct = int(abs(normalized) * 100)

    if confidence_pct < MIN_SIGNAL_CONFIDENCE:  # 70 from .env
        return None  # logged for backtest but not displayed

    direction = "BUY" if normalized > 0 else "SELL"
    classification = classify(timeframe, factors)
    entry, sl, tp, qty = compute_levels(direction, classification, candles, user.capital, user.risk_pct)
    return build_signal(direction, classification, confidence_pct, factors, entry, sl, tp, qty)
```

### Default factor weights

These are starting values. **Phase 9 strategy lab will re-tune them per market regime** based on backtested win rate.

| Factor group | Default weight | Notes |
|---|---|---|
| Candlestick pattern (any) | 15 | Single highest-scoring pattern, not summed |
| Dow trend | 20 | The "macro" context — heavy weight |
| EMA structure (price vs 50/200, cross) | 15 | |
| RSI (level + divergence) | 10 | |
| MACD (cross + histogram) | 10 | |
| Volume confirmation | 10 | Multiplier-style: only counts if direction matches |
| Support / Resistance / Zones | 10 | |
| Fibonacci | 5 | |
| ADX strength | 5 | Filters out weak-trend setups |
| FII/DII flow | 5 | Lighter weight; sector-level not stock-level for most stocks |
| Multibagger EMA setup (1d only) | bonus +10 | Adds on top, doesn't replace |

**Threshold:** Only signals scoring ≥ 70% confidence are surfaced to the dashboard. Lower-confidence signals are logged for backtest learning but hidden from the UI.

### Conflict resolution

If pattern signals BUY but trend is downward, the trend's negative weight reduces confidence. A 65% buy + 80% trend down nets to ~−14% → no signal, or a SELL signal of ~14% (below threshold, so still no signal). This is correct behavior — counter-trend trades should be hard to surface.

---

## 4. Signal classification

Implemented in `backend/app/signals/classifier.py`.

Classification is determined by which timeframe contributed the strongest confluence:

| Timeframe with highest contribution | Classification | Typical hold time |
|---|---|---|
| 1m or 5m | `scalp` | 5–30 minutes |
| 15m or 1h | `intraday` | Hours, exit by 3:15 PM |
| 1d | `swing` | 3–10 trading days |
| 1d + Multibagger EMA setup | `positional` | Weeks to months |
| 1w | `positional` | Months |

The classifier also categorizes by **volatility regime** and **trend strength** (per requirements):

- ATR (Average True Range, 14) > 3% of price → volatile → reduce position size 25%
- ADX < 20 → weak trend → require +5% extra confidence before surfacing
- ADX > 40 → strong trend → confidence threshold reduced to 65% (in strong trends, simpler setups work)

---

## 5. Signal validity (expiry)

Implemented in `backend/app/signals/expiry_sweeper.py`, runs every 5 minutes via Celery.

| Classification | Validity | Reason |
|---|---|---|
| Scalp | 30 minutes from creation | Fast price decay |
| Intraday | Until 3:15 PM IST same trading day | Must close before market close |
| Swing | 5 trading days OR until SL/TP/EMA exit signal | Daily-chart setups |
| Positional | 30 trading days OR until 20-EMA exit (3-hour timeframe per masterclass) | Long-running |

When a signal expires unfilled, its status updates to `EXPIRED` and it disappears from the dashboard. The historical record stays in DB for backtest analysis.

---

## 6. Position sizing and risk management

Implemented in `backend/app/analysis/risk.py`. **This is mandatory on every signal.**

### The formula (masterclass Class 10)

```python
def compute_quantity(capital: Decimal, risk_pct: Decimal, entry: Decimal, stop_loss: Decimal) -> int:
    risk_amount = capital * (risk_pct / 100)
    risk_per_share = abs(entry - stop_loss)
    if risk_per_share == 0:
        raise ValueError("Stop loss must differ from entry")
    quantity = floor(risk_amount / risk_per_share)
    return max(quantity, 0)
```

### Stop-loss placement rules (per classification)

| Classification | Default SL | Maximum SL | Source |
|---|---|---|---|
| Scalp | 0.3% from entry | 0.5% | Class 6/11 |
| Intraday | Below last swing low (long) | 0.5% of entry price | Class 6/11 |
| Swing | Below last swing low | 8% of entry price | Class 4/5 |
| Positional | Trailing 20 EMA on daily | n/a | Class 5 |

If the natural SL placement (e.g., last swing low) exceeds the maximum, **the signal is rejected** — do not artificially tighten an SL to fit the rule. This matches the masterclass: "if swing low is too far, avoid the trade."

### Take-profit placement (RR targets)

| Strategy | Risk:Reward |
|---|---|
| 9:25 AM Top Gainer/Loser, 10 AM Strategy | 1:1.5 |
| RSI Divergence, DC1, DC2, PDH/PDL, TL Breakout | 1:2 |
| Swing RRBO (basic) | flat 6% target |
| Swing RRBO (trailing) | 6% first booking, trail rest |
| Multibagger | 15% minimum, trail with 20 EMA daily |

### Trailing stop loss

When a signal hits its first target:
- 50% of position closed
- Remaining 50% SL moved to entry price (break-even guarantee)
- If price hits next 6% target, book another 25%, trail again

The system tracks this state in the `positions` table with fields `trail_state` (`none` / `breakeven` / `trailing_1` / `trailing_2`) and `trail_sl_price`.

---

## 7. Worked example (verification)

Stock: TATAMOTORS, timeframe: 1d.

Factor outputs for today's candle:
- Bullish Engulfing detected: weight 15, score +0.9 → +13.5
- Dow trend = uptrend: weight 20, score +0.7 → +14.0
- Price > 50 EMA > 200 EMA: weight 15, score +0.5 → +7.5
- RSI 32 and rising: weight 10, score +0.6 → +6.0
- MACD bullish cross last candle: weight 10, score +0.7 → +7.0
- Volume 1.6× avg: weight 10, score +0.5 → +5.0
- At demand zone with bullish reversal pattern: weight 10, score +0.85 → +8.5
- Fib bounce from 0.618: weight 5, score +0.6 → +3.0
- ADX = 28, +DI > −DI: weight 5, score +0.6 → +3.0
- FII net buying auto sector last 5 days: weight 5, score +0.5 → +2.5

Total weighted = +70.0 across total weight = 105 (all factors fired).
Normalized = 70 / 105 = 0.667 → confidence = 66.7%.

**Result: no signal surfaced** (below 70% threshold). This is the correct behavior — even with many factors aligned, not all were maximum strength. The user sees nothing; the system logs it for backtest.

Now imagine bumping a few factor scores (cleaner engulfing pattern, RSI divergence detected too):
- Bullish Engulfing → +0.95 → +14.25
- Add RSI divergence under RSI factor weight → +0.8 → +8.0

New total = +73.75, weight = 105, normalized = 0.703 → **70.3% confidence → BUY signal surfaced**.

Then risk sizer: entry ₹490, SL ₹482 (below recent swing low, within 8% rule), TP ₹506 (1:2 RR), suggested qty = floor(₹2000 risk / ₹8) = 250 shares.

Final signal: `"Buy TATAMOTORS — Bullish Engulfing with RSI divergence at demand zone, FII net positive, 70.3% confidence. Entry ₹490, SL ₹482, TP ₹506, Qty 250."`

---

## 8. Testing strategy for the engine

Every factor module needs golden-value tests: known input candles → known expected score. Use real historical NSE data for these (snapshot a few months of Nifty50 stocks). Tests live in `backend/tests/analysis/`.

Run a regression backtest after any factor or weight change:
```bash
make backtest STOCKS=NIFTY50 PERIOD=2Y
```

If win rate, Sharpe, or max drawdown changes by more than 5%, the change requires explicit user approval before merging.
