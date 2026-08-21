import unittest

from strategy.fvg import FVGZone
from strategy.liquidity import find_sweep_and_bos
from strategy.swings import SwingPoint
from tests.util import make_candles

BULLISH_SWING = SwingPoint(index=2, price=21, kind="high")
BULLISH_FVG = FVGZone(start_idx=3, end_idx=5, high=21, low=18, direction="bullish", timeframe="15m")

# 0-1 filler, 2 the swing candle itself, 3 sweep (bearish wick above 21),
# 4 filler (no reversal yet), 5 BOS (closes back above 21).
BULLISH_CANDLES = [
    (18, 19, 17, 18.5),
    (19, 20, 18, 19.5),
    (19.5, 21, 19, 20.5),
    (20, 22, 19, 19.5),
    (19.5, 20, 18, 19.8),
    (19.8, 24, 19, 23.5),
]

BEARISH_SWING = SwingPoint(index=2, price=10, kind="low")
BEARISH_FVG = FVGZone(start_idx=3, end_idx=5, high=13, low=10, direction="bearish", timeframe="15m")

# Mirror of the bullish case: sweep is a bullish candle wicking below the
# swing low, BOS is a candle closing back below it.
BEARISH_CANDLES = [
    (13, 14, 12, 13.5),
    (12, 13, 11, 12.5),
    (12, 12.5, 10, 10.5),
    (11, 12, 9, 11.5),
    (11.5, 12.5, 11, 11.2),
    (11.2, 12, 7, 7.5),
]


class TestFindSweepAndBosBullish(unittest.TestCase):
    def test_full_sweep_and_bos_confirmed(self):
        candles = make_candles(BULLISH_CANDLES)
        result = find_sweep_and_bos(candles, BULLISH_SWING, BULLISH_FVG, "bullish")
        self.assertEqual(result.sweep_idx, 3)
        self.assertEqual(result.bos_idx, 5)
        self.assertTrue(result.confirmed)

    def test_no_sweep_never_found(self):
        candles = list(BULLISH_CANDLES)
        candles[3] = (20, 20.5, 19.5, 19.8)  # no wick above swing price 21
        result = find_sweep_and_bos(make_candles(candles), BULLISH_SWING, BULLISH_FVG, "bullish")
        self.assertEqual(result.sweep_idx, -1)
        self.assertEqual(result.bos_idx, -1)
        self.assertFalse(result.confirmed)

    def test_sweep_found_but_no_bos_before_fvg_end(self):
        candles = list(BULLISH_CANDLES)
        candles[5] = (19.8, 20.5, 19, 20.2)  # never closes back above 21
        result = find_sweep_and_bos(make_candles(candles), BULLISH_SWING, BULLISH_FVG, "bullish")
        self.assertEqual(result.sweep_idx, 3)
        self.assertEqual(result.bos_idx, -1)
        self.assertFalse(result.confirmed)

    def test_sweep_out_of_range_is_ignored(self):
        candles = list(BULLISH_CANDLES)
        candles[3] = (19.5, 20, 19, 19.8)  # no sweep at idx3 anymore
        candles[4] = (19.8, 23, 19, 22.5)  # would qualify as a sweep, but idx4 > fvg.start_idx=3
        result = find_sweep_and_bos(make_candles(candles), BULLISH_SWING, BULLISH_FVG, "bullish")
        self.assertEqual(result.sweep_idx, -1)
        self.assertFalse(result.confirmed)


class TestFindSweepAndBosBearish(unittest.TestCase):
    def test_full_sweep_and_bos_confirmed(self):
        candles = make_candles(BEARISH_CANDLES)
        result = find_sweep_and_bos(candles, BEARISH_SWING, BEARISH_FVG, "bearish")
        self.assertEqual(result.sweep_idx, 3)
        self.assertEqual(result.bos_idx, 5)
        self.assertTrue(result.confirmed)


if __name__ == "__main__":
    unittest.main()
