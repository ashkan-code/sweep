import unittest

from strategy.swings import SwingPoint, find_swings
from strategy.trend import classify_trend
from tests.util import make_candles
from tests.test_swings import ZIGZAG as _BASE_ZIGZAG

# Extended for trend tests: the base 7-candle ZIGZAG only has 3 highs and
# 2 lows, one short of the default trend_confirm_swings=3. Its own last
# candle (index 6, a boundary filler in the base fixture) becomes
# checkable once one more filler candle follows it, and turns out to be
# a genuine 3rd swing low (10, up from 9.5) without disturbing the
# original swings. Re-exported here (shadowing the import) since
# tests/test_engine.py imports ZIGZAG from this module.
ZIGZAG = _BASE_ZIGZAG + [
    (10.5, 11, 10.2, 10.8),  # filler (window boundary for index 6's swing low)
]

# Mirror of ZIGZAG (K=26 minus each price, with high/low swapped) so
# every swing high becomes a swing low and vice versa -> lower highs,
# lower lows throughout.
BEARISH_ZIGZAG = [
    (16.5, 17, 16, 16.2),
    (15, 15, 14, 14.5),
    (15.5, 18, 15, 17.5),
    (13, 13, 11, 11.5),
    (16, 16.5, 16, 16.2),
    (10, 12, 8, 8.5),
    (15, 16, 15, 15.5),
    (15.5, 15.8, 15, 15.2),
]

# Same first six candles as ZIGZAG (highs 12/15/18 keep rising), but the
# third low breaks the increasing pattern (8, 9.5, 7) instead of
# continuing it -- a genuine mixed structure, not just too few swings.
MIXED = [
    (9.5, 10, 9, 9.8),
    (11, 12, 11, 11.5),
    (10.5, 11, 8, 8.5),
    (13, 15, 13, 14.5),
    (10, 10, 9.5, 9.8),
    (16, 18, 14, 17.5),
    (16, 16.5, 7, 7.5),  # swing low 7 -- lower than the previous low (9.5)
    (7.5, 9, 7.2, 8.5),  # filler
]


class TestClassifyTrend(unittest.TestCase):
    def test_higher_highs_and_higher_lows_is_bullish(self):
        candles = make_candles(ZIGZAG)
        swings = find_swings(candles, lookback=1)
        result = classify_trend(swings, candles, "4h")
        self.assertEqual(result.direction, "bullish")
        self.assertEqual(result.timeframe, "4h")

    def test_lower_highs_and_lower_lows_is_bearish(self):
        candles = make_candles(BEARISH_ZIGZAG)
        swings = find_swings(candles, lookback=1)
        result = classify_trend(swings, candles, "1h")
        self.assertEqual(result.direction, "bearish")
        self.assertEqual(result.timeframe, "1h")

    def test_mixed_structure_is_none(self):
        candles = make_candles(MIXED)
        swings = find_swings(candles, lookback=1)
        result = classify_trend(swings, candles, "4h")
        self.assertEqual(result.direction, "none")

    def test_too_few_swings_is_none(self):
        result = classify_trend([], [], "4h")
        self.assertEqual(result.direction, "none")

    def test_confirm_swings_is_configurable(self):
        # With only 2 required, the base (unextended) ZIGZAG's 2 lows
        # are already enough to confirm bullish.
        candles = make_candles(_BASE_ZIGZAG)
        swings = find_swings(candles, lookback=1)
        result = classify_trend(swings, candles, "4h", config={"trend_confirm_swings": 2})
        self.assertEqual(result.direction, "bullish")


# A clean uptrend (highs 105/110/115/120, lows 100/102/104, each rising)
# with one candle in the middle whose range is 5x the recent average --
# a liquidity sweep / flash move -- that would otherwise register as a
# much lower swing low (90) and break the increasing-lows pattern.
_OUTLIER_INDEX = 17
_OUTLIER_CANDLES = [
    (100.0, 100.0 + (5.0 if i == _OUTLIER_INDEX else 1.0) / 2,
     100.0 - (5.0 if i == _OUTLIER_INDEX else 1.0) / 2, 100.0)
    for i in range(24)
]
OUTLIER_SWINGS = [
    SwingPoint(index=2, price=105, kind="high"),
    SwingPoint(index=5, price=100, kind="low"),
    SwingPoint(index=8, price=110, kind="high"),
    SwingPoint(index=11, price=102, kind="low"),
    SwingPoint(index=14, price=115, kind="high"),
    SwingPoint(index=_OUTLIER_INDEX, price=90, kind="low"),  # sits on the outlier candle
    SwingPoint(index=20, price=120, kind="high"),
    SwingPoint(index=23, price=104, kind="low"),
]


class TestOutlierFiltering(unittest.TestCase):
    def test_outlier_range_candle_is_excluded_and_trend_stays_bullish(self):
        candles = make_candles(_OUTLIER_CANDLES)
        result = classify_trend(OUTLIER_SWINGS, candles, "4h")
        self.assertEqual(result.direction, "bullish")

    def test_without_filtering_the_outlier_would_break_the_trend(self):
        # Sanity check: with filtering effectively disabled, the fixture
        # really does produce "none" -- proving the fix above is what's
        # keeping it "bullish", not an accident of the data.
        candles = make_candles(_OUTLIER_CANDLES)
        result = classify_trend(
            OUTLIER_SWINGS, candles, "4h", config={"outlier_range_multiplier": 1000}
        )
        self.assertEqual(result.direction, "none")


if __name__ == "__main__":
    unittest.main()
