from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class TradingMode(StrEnum):
    PAPER = "paper"
    SEMI_AUTO = "semi_auto"
    LIVE = "live"


class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SignalClassification(StrEnum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    SWING = "swing"
    POSITIONAL = "positional"


class SignalStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    HIT_TP = "hit_tp"
    HIT_SL = "hit_sl"
    MANUALLY_CLOSED = "manually_closed"
