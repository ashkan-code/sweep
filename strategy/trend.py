"""Trend direction classification from a sequence of fractal swings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrendResult:
    direction: str  # "bullish" | "bearish" | "none"
    timeframe: str


def classify_trend(swings, timeframe):
    """Higher highs + higher lows (across the last two swings of each
    kind) => bullish. Lower highs + lower lows => bearish. Anything else
    (including too few swings) => none."""
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return TrendResult("none", timeframe)

    if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
        return TrendResult("bullish", timeframe)
    if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
        return TrendResult("bearish", timeframe)
    return TrendResult("none", timeframe)
