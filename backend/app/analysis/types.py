"""Shared types for the signal analysis engine."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorResult:
    """Single factor output from any detector/indicator."""

    name: str
    weight: float
    score: float          # -1.0 … +1.0
    explanation: str
    tags: list[str] = field(default_factory=list)   # e.g. ['pattern', 'bullish']


@dataclass(frozen=True)
class PatternResult:
    detected: bool
    score: float          # -1.0 … +1.0 (0 when not detected)
    explanation: str
    name: str
