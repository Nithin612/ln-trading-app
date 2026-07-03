"""FII/DII institutional flow factor.

Reads daily flow data and block/bulk deals for a stock.
Scores match SIGNAL_ENGINE.md §2.7.
"""

from decimal import Decimal

from app.analysis.types import FactorResult

_WEIGHT = 5
_FII_BUY_THRESHOLD = Decimal("2000")   # crore INR, 5-day cumulative
_DII_BUY_THRESHOLD = Decimal("1500")
_BLOCK_DEAL_SCORE = 0.4


def fii_dii_factor(
    fii_net_5d: Decimal,
    dii_net_5d: Decimal,
    stock_block_deal_net_cr: Decimal = Decimal("0"),
) -> FactorResult:
    """Score based on aggregated FII/DII flows over the last 5 trading days.

    Args:
        fii_net_5d: cumulative FII net (buy - sell) in crore INR, last 5 days.
        dii_net_5d: cumulative DII net in crore INR, last 5 days.
        stock_block_deal_net_cr: net value of block/bulk deals for this stock.
    """
    score = 0.0
    parts: list[str] = []

    # FII direction
    if fii_net_5d > _FII_BUY_THRESHOLD:
        score += 0.5
        parts.append(f"FII net buy ₹{fii_net_5d:.0f} Cr > {_FII_BUY_THRESHOLD}")
    elif fii_net_5d < -_FII_BUY_THRESHOLD:
        score -= 0.5
        parts.append(f"FII net sell ₹{abs(fii_net_5d):.0f} Cr > {_FII_BUY_THRESHOLD}")

    # DII absorbing FII selling
    if fii_net_5d < 0 and dii_net_5d > _DII_BUY_THRESHOLD:
        score += 0.3
        parts.append(f"DII absorbing FII selling: DII net ₹{dii_net_5d:.0f} Cr")

    # Both buying same direction at significant scale
    if fii_net_5d > _FII_BUY_THRESHOLD and dii_net_5d > _DII_BUY_THRESHOLD:
        score = 0.7
        parts = [f"FII+DII both net buyers: FII ₹{fii_net_5d:.0f} Cr, DII ₹{dii_net_5d:.0f} Cr"]

    # Stock-level block/bulk deals
    if stock_block_deal_net_cr > 0:
        score = min(1.0, score + _BLOCK_DEAL_SCORE)
        parts.append(f"Block/bulk deal net buy ₹{stock_block_deal_net_cr:.0f} Cr")
    elif stock_block_deal_net_cr < 0:
        score = max(-1.0, score - _BLOCK_DEAL_SCORE)
        parts.append(f"Block/bulk deal net sell ₹{abs(stock_block_deal_net_cr):.0f} Cr")

    score = max(-1.0, min(1.0, score))
    explanation = "; ".join(parts) if parts else "FII/DII flows neutral"
    return FactorResult("FII_DII_FLOW", _WEIGHT, score, explanation, ["institutional"])
