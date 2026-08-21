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


if __name__ == "__main__":
    unittest.main()
