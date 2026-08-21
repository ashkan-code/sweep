import unittest

from strategy.swings import find_swings, last_swing_before
from tests.util import make_candles

# Generic synthetic zigzag: alternating swing highs/lows.
# idx1 -> swing high 12, idx2 -> swing low 8,
# idx3 -> swing high 15, idx4 -> swing low 9.5, idx5 -> swing high 18.
ZIGZAG = [
    (9.5, 10, 9, 9.8),
    (11, 12, 11, 11.5),
    (10.5, 11, 8, 8.5),
    (13, 15, 13, 14.5),
    (10, 10, 9.5, 9.8),
    (16, 18, 14, 17.5),
    (11, 11, 10, 10.5),
]


class TestFindSwings(unittest.TestCase):
    def test_detects_alternating_highs_and_lows(self):
        candles = make_candles(ZIGZAG)
        swings = find_swings(candles, lookback=1)

        highs = [(s.index, s.price) for s in swings if s.kind == "high"]
        lows = [(s.index, s.price) for s in swings if s.kind == "low"]

        self.assertEqual(highs, [(1, 12), (3, 15), (5, 18)])
        self.assertEqual(lows, [(2, 8), (4, 9.5)])

    def test_insufficient_candles_returns_empty(self):
        candles = make_candles(ZIGZAG[:2])
        self.assertEqual(find_swings(candles, lookback=3), [])


class TestLastSwingBefore(unittest.TestCase):
    def setUp(self):
        candles = make_candles(ZIGZAG)
        self.swings = find_swings(candles, lookback=1)

    def test_returns_most_recent_swing_strictly_before_index(self):
        swing = last_swing_before(self.swings, index=5, kind="high")
        self.assertIsNotNone(swing)
        self.assertEqual((swing.index, swing.price), (3, 15))

    def test_none_when_no_matching_swing_before_index(self):
        swing = last_swing_before(self.swings, index=2, kind="low")
        self.assertIsNone(swing)


if __name__ == "__main__":
    unittest.main()
