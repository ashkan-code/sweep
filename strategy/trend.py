"""Trend direction classification from a sequence of fractal swings."""

from dataclasses import dataclass

DEFAULT_TREND_CONFIRM_SWINGS = 3
DEFAULT_OUTLIER_RANGE_MULTIPLIER = 3.0
DEFAULT_OUTLIER_LOOKBACK_CANDLES = 20


@dataclass(frozen=True)
class TrendResult:
    direction: str  # "bullish" | "bearish" | "none"
    timeframe: str


def _average_range(candles, end_idx, lookback):
    window = candles[max(0, end_idx - lookback) : end_idx]
    if not window:
        return None
    return sum(c.range for c in window) / len(window)


def _is_outlier_swing(swing, candles, lookback, multiplier):
    """A swing candle whose range dwarfs the recent average (a
    liquidity sweep or flash move) shouldn't count as a real structural
    swing for trend purposes."""
    avg_range = _average_range(candles, swing.index, lookback)
    if not avg_range:
        return False
    return candles[swing.index].range > avg_range * multiplier


def _filter_outlier_swings(swings, candles, config):
    lookback = config.get("outlier_lookback_candles", DEFAULT_OUTLIER_LOOKBACK_CANDLES)
    multiplier = config.get("outlier_range_multiplier", DEFAULT_OUTLIER_RANGE_MULTIPLIER)
    return [s for s in swings if not _is_outlier_swing(s, candles, lookback, multiplier)]


def _strictly_increasing(points):
    return all(points[i].price > points[i - 1].price for i in range(1, len(points)))


def _strictly_decreasing(points):
    return all(points[i].price < points[i - 1].price for i in range(1, len(points)))


def classify_trend(swings, candles, timeframe, config=None):
    """Bullish: the last `trend_confirm_swings` swing highs and the last
    `trend_confirm_swings` swing lows are each strictly increasing.
    Bearish: each strictly decreasing. Anything else (including too few
    swings) => none.

    Swing candles with an outsized range relative to the recent average
    (a liquidity sweep or flash move) are excluded first, so one
    exceptional candle can't flip the detected direction on its own.
    """
    config = config or {}
    confirm_swings = config.get("trend_confirm_swings", DEFAULT_TREND_CONFIRM_SWINGS)

    filtered = _filter_outlier_swings(swings, candles, config)
    highs = [s for s in filtered if s.kind == "high"]
    lows = [s for s in filtered if s.kind == "low"]
    if len(highs) < confirm_swings or len(lows) < confirm_swings:
        return TrendResult("none", timeframe)

    recent_highs = highs[-confirm_swings:]
    recent_lows = lows[-confirm_swings:]
    if _strictly_increasing(recent_highs) and _strictly_increasing(recent_lows):
        return TrendResult("bullish", timeframe)
    if _strictly_decreasing(recent_highs) and _strictly_decreasing(recent_lows):
        return TrendResult("bearish", timeframe)
    return TrendResult("none", timeframe)
