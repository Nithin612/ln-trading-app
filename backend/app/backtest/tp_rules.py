"""§6 take-profit templates (Phase 2 slice 8a).

Shared by the live suggestions pipeline and the backtest engines so the
two can never diverge. SL is NEVER touched here — it stays classification
canon and reject-don't-clamp happened upstream. The Rust mirror is
engine_core::risk::apply_tp_rule (exact: one half-even round at 1e-4,
matching the final quantize below).
"""

from decimal import Decimal


def tp_from_template(
    template: dict[str, object], direction: str, entry: Decimal, stop_loss: Decimal
) -> Decimal:
    kind = str(template.get("kind"))
    sign = 1 if direction == "BUY" else -1
    if kind == "rr":
        ratio = Decimal(str(template["ratio"]))
        risk = abs(entry - stop_loss)
        tp = entry + sign * risk * ratio
    elif kind in ("flat_pct", "flat_pct_trailing"):
        pct = Decimal(str(template["target_pct"]))
        tp = entry * (Decimal("1") + sign * pct / Decimal("100"))
    elif kind == "ema_trail":
        pct = Decimal(str(template["min_target_pct"]))
        tp = entry * (Decimal("1") + sign * pct / Decimal("100"))
    else:  # unreachable — schema rejects unknown kinds at load
        raise ValueError(f"unknown risk template kind {kind!r}")
    return tp.quantize(Decimal("0.0001"))
