"""Human-readable signal headline generator."""

from decimal import Decimal

from app.analysis.confluence import ConfluenceResult


def build_headline(
    symbol: str,
    result: ConfluenceResult,
    entry: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    qty: int,
) -> str:
    top_factors = sorted(result.factors, key=lambda f: abs(f.score), reverse=True)[:3]
    factor_names = ", ".join(
        f.name.replace("_", " ").title() for f in top_factors if f.score != 0.0
    )
    return (
        f"{result.direction} {symbol} — {factor_names}, "
        f"{result.confidence_pct}% confidence. "
        f"Entry ₹{entry}, SL ₹{stop_loss}, TP ₹{take_profit}, Qty {qty}."
    )
