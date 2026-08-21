"""Fair Value Gap (FVG) detection: a 3-candle price gap where the middle
candle is a directional, displacing move."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FVGZone:
    start_idx: int  # index of candle i (first gap candle)
    end_idx: int  # index of candle i+2 (third gap candle)
    high: float
    low: float
    direction: str  # "bullish" | "bearish"
    timeframe: str


def detect_fvgs(candles, direction, timeframe):
    """3-candle FVG: a gap between candle i and i+2, where candle i+1 is
    the same color as `direction` and its close extends beyond the gap
    range (true displacement, not just a small overlap)."""
    if direction not in ("bullish", "bearish"):
        raise ValueError("direction must be 'bullish' or 'bearish', got %r" % (direction,))

    zones = []
    for i in range(0, len(candles) - 2):
        c1, c2, c3 = candles[i], candles[i + 1], candles[i + 2]

        if direction == "bullish":
            if not (c1.high < c3.low):
                continue
            gap_low, gap_high = c1.high, c3.low
            impulsive_ok = c2.close > c2.open and c2.close > gap_high
        else:
            if not (c1.low > c3.high):
                continue
            gap_low, gap_high = c3.high, c1.low
            impulsive_ok = c2.close < c2.open and c2.close < gap_low

        if not impulsive_ok:
            continue

        zones.append(
            FVGZone(
                start_idx=i,
                end_idx=i + 2,
                high=gap_high,
                low=gap_low,
                direction=direction,
                timeframe=timeframe,
            )
        )
    return zones
