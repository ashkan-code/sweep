import unittest

from strategy.confirmation import describe_confirmation, find_confirmation
from strategy.fvg import FVGZone
from tests.util import make_candles

CONFIG = {"momentum_body_ratio": 0.70}
ZONE = FVGZone(start_idx=0, end_idx=0, high=105, low=100, direction="bullish", timeframe="15m")

MOMENTUM_CANDLES = [
    (95, 96, 94, 95.5),  # 0 outside the zone
    (101, 103, 100.5, 101.5),  # 1 zone entry, weak candle (no confirmation)
    (101, 110, 100, 109),  # 2 momentum candle (body_ratio 0.8, aligned bullish)
]

ENGULFING_CANDLES = [
    (95, 96, 94, 95.5),  # 0 outside the zone
    (102, 102.5, 101.5, 101.8),  # 1 zone entry, weak candle
    (101.7, 105, 101, 102.3),  # 2 engulfing candle, low body_ratio so it isn't also momentum
]

RANGE_CANDLES = [
    (95, 96, 94, 95.5),  # 0 outside the zone
    (102, 103, 101, 102.3),  # 1 zone entry, weak candle
    (102.3, 103, 102, 102.1),  # 2 weak, wrong-direction candle
]

NO_ZONE_ENTRY_CANDLES = [
    (95, 96, 94, 95.5),
    (94, 95, 93, 94.5),
    (93, 94, 92, 93.5),
]

# A momentum candle appears at idx3, but it's stale -- irrelevant candles
# follow it, and the true last candle (idx5) is weak/non-confirming.
CONFIRMATION_NOT_LAST_CANDLES = [
    (95, 96, 94, 95.5),  # 0 outside the zone
    (101, 103, 100.5, 101.5),  # 1 zone entry, weak candle
    (101.5, 102, 101, 101.6),  # 2 filler, weak
    (101, 110, 100, 109),  # 3 momentum candle -- but not the last candle below
    (109, 110, 108, 108.5),  # 4 irrelevant filler after
    (108.5, 109, 107, 107.8),  # 5 irrelevant filler, weak/non-confirming -- the actual last candle
]


class TestFindConfirmation(unittest.TestCase):
    def test_momentum_candle_is_a_signal(self):
        candles = make_candles(MOMENTUM_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "signal")
        self.assertEqual(result.candle_idx, 2)
        self.assertEqual(describe_confirmation(candles, 2, "bullish", CONFIG), "momentum candle")

    def test_engulfing_candle_is_a_signal(self):
        candles = make_candles(ENGULFING_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "signal")
        self.assertEqual(result.candle_idx, 2)
        self.assertEqual(describe_confirmation(candles, 2, "bullish", CONFIG), "engulfing candle")

    def test_zone_entered_but_no_confirmation_is_range(self):
        candles = make_candles(RANGE_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "range")
        self.assertEqual(result.candle_idx, 1)

    def test_zone_never_entered_is_none(self):
        candles = make_candles(NO_ZONE_ENTRY_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "none")
        self.assertEqual(result.candle_idx, -1)

    def test_search_start_past_end_of_candles_is_none(self):
        candles = make_candles(MOMENTUM_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=100)
        self.assertEqual(result.kind, "none")
        self.assertEqual(result.candle_idx, -1)

    def test_stale_momentum_candle_not_the_last_candle_is_range(self):
        candles = make_candles(CONFIRMATION_NOT_LAST_CANDLES)
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "range")

    def test_momentum_candle_that_is_the_last_candle_is_a_signal(self):
        candles = make_candles(CONFIRMATION_NOT_LAST_CANDLES[:4])  # truncated so idx3 is last
        result = find_confirmation(candles, ZONE, "bullish", CONFIG, search_start_idx=0)
        self.assertEqual(result.kind, "signal")
        self.assertEqual(result.candle_idx, 3)


if __name__ == "__main__":
    unittest.main()
