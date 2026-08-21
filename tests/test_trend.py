import unittest

from strategy.swings import find_swings
from strategy.trend import classify_trend
from tests.util import make_candles
from tests.test_swings import ZIGZAG

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
]

# Higher highs but lower lows: not a clean trend either direction.
MIXED = [
    (9.5, 10, 9, 9.8),
    (11, 12, 11, 11.5),
    (10.5, 11, 8, 8.5),
    (13, 15, 13, 14.5),
    (9, 9, 6, 8.5),
    (10, 11, 9, 10.5),
]


class TestClassifyTrend(unittest.TestCase):
    def test_higher_highs_and_higher_lows_is_bullish(self):
        swings = find_swings(make_candles(ZIGZAG), lookback=1)
        result = classify_trend(swings, "4h")
        self.assertEqual(result.direction, "bullish")
        self.assertEqual(result.timeframe, "4h")

    def test_lower_highs_and_lower_lows_is_bearish(self):
        swings = find_swings(make_candles(BEARISH_ZIGZAG), lookback=1)
        result = classify_trend(swings, "1h")
        self.assertEqual(result.direction, "bearish")
        self.assertEqual(result.timeframe, "1h")

    def test_mixed_structure_is_none(self):
        swings = find_swings(make_candles(MIXED), lookback=1)
        result = classify_trend(swings, "4h")
        self.assertEqual(result.direction, "none")

    def test_too_few_swings_is_none(self):
        result = classify_trend([], "4h")
        self.assertEqual(result.direction, "none")


if __name__ == "__main__":
    unittest.main()
