"""Fractal swing high/low detection."""

from dataclasses import dataclass
from typing import Optional

DEFAULT_SWING_LOOKBACK = 3


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str  # "high" | "low"


def find_swings(candles, lookback=DEFAULT_SWING_LOOKBACK):
    """A candle is a fractal swing high/low if its high/low is the
    max/min within `lookback` candles on both sides."""
    swings = []
    n = len(candles)
    for i in range(lookback, n - lookback):
        window = candles[i - lookback : i + lookback + 1]
        c = candles[i]
        if c.high == max(w.high for w in window):
            swings.append(SwingPoint(index=c.index, price=c.high, kind="high"))
        if c.low == min(w.low for w in window):
            swings.append(SwingPoint(index=c.index, price=c.low, kind="low"))
    return swings


def last_swing_before(swings, index, kind=None):
    """Most recent swing with .index < index (optionally filtered by
    kind), or None. This is the most recent fractal swing point, not the
    extreme of the whole trend leg."""
    candidates = [s for s in swings if s.index < index and (kind is None or s.kind == kind)]
    return candidates[-1] if candidates else None
