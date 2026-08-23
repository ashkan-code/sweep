import unittest

from strategy.fvg import detect_fvgs
from tests.util import make_candles

BULLISH_BASE = [
    (100, 101, 99, 100),  # 0 filler
    (100, 102, 99, 101),  # 1 c1: high=102
    (101, 112, 100, 111),  # 2 c2: impulsive bull candle, closes at 111 (> gap_high=105)
    (106, 112, 105, 111),  # 3 c3: low=105 -> gap [102, 105]
    (111, 113, 106, 112),  # 4 validation candle 1 (body [111, 112], doesn't intrude)
    (112, 114, 110, 113),  # 5 validation candle 2 (body [112, 113], doesn't intrude)
]

BEARISH_BASE = [
    (100, 101, 99, 100),  # 0 filler
    (106, 108, 105, 106),  # 1 c1: low=105
    (105, 106, 95, 96),  # 2 c2: impulsive bear candle, closes at 96 (< gap_low=100)
    (97, 100, 94, 95),  # 3 c3: high=100 -> gap [100, 105]
    (95, 96, 90, 91),  # 4 validation candle 1 (body [91, 95], doesn't intrude)
    (91, 93, 88, 90),  # 5 validation candle 2 (body [90, 91], doesn't intrude)
]

# A validation candle's real body closes back into the gap [102, 105] ->
# invalidated. Body is [104, 105.5], overlapping the gap.
BULLISH_BODY_INTRUDES = list(BULLISH_BASE)
BULLISH_BODY_INTRUDES[5] = (104, 106, 103, 105.5)

# Only the wick reaches into/through the gap [102, 105]; the body
# ([112, 113]) stays entirely above it -> still valid.
BULLISH_WICK_ONLY = list(BULLISH_BASE)
BULLISH_WICK_ONLY[5] = (112, 113.5, 101, 113)

# Only one of the two validation candles (i+3) exists yet; i+4 doesn't
# -> not confirmed either way, skipped for now.
BULLISH_NOT_ENOUGH_DATA = BULLISH_BASE[:5]


class TestDetectFvgsBullish(unittest.TestCase):
    def test_valid_bullish_fvg_detected(self):
        candles = make_candles(BULLISH_BASE)
        zones = detect_fvgs(candles, "bullish", "15m")
        self.assertEqual(len(zones), 1)
        zone = zones[0]
        self.assertEqual(zone.start_idx, 1)
        self.assertEqual(zone.end_idx, 3)
        self.assertEqual(zone.low, 102)
        self.assertEqual(zone.high, 105)
        self.assertEqual(zone.direction, "bullish")
        self.assertEqual(zone.timeframe, "15m")

    def test_wrong_color_middle_candle_rejected(self):
        candles = list(BULLISH_BASE)
        candles[2] = (111, 112, 100, 101)  # bearish instead of bullish
        zones = detect_fvgs(make_candles(candles), "bullish", "15m")
        self.assertEqual(zones, [])

    def test_middle_candle_close_does_not_extend_past_gap(self):
        candles = list(BULLISH_BASE)
        candles[2] = (101, 112, 100, 104)  # close=104, inside the gap, not beyond gap_high=105
        zones = detect_fvgs(make_candles(candles), "bullish", "15m")
        self.assertEqual(zones, [])

    def test_no_price_gap_rejected(self):
        candles = list(BULLISH_BASE)
        candles[3] = (95, 112, 94, 111)  # low=94, overlaps c1.high=102
        zones = detect_fvgs(make_candles(candles), "bullish", "15m")
        self.assertEqual(zones, [])

    def test_body_intrusion_invalidates_the_fvg(self):
        zones = detect_fvgs(make_candles(BULLISH_BODY_INTRUDES), "bullish", "15m")
        self.assertEqual(zones, [])

    def test_wick_only_intrusion_does_not_invalidate(self):
        zones = detect_fvgs(make_candles(BULLISH_WICK_ONLY), "bullish", "15m")
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].low, 102)
        self.assertEqual(zones[0].high, 105)

    def test_not_enough_candles_to_confirm_is_skipped(self):
        zones = detect_fvgs(make_candles(BULLISH_NOT_ENOUGH_DATA), "bullish", "15m")
        self.assertEqual(zones, [])


class TestDetectFvgsBearish(unittest.TestCase):
    def test_valid_bearish_fvg_detected(self):
        candles = make_candles(BEARISH_BASE)
        zones = detect_fvgs(candles, "bearish", "15m")
        self.assertEqual(len(zones), 1)
        zone = zones[0]
        self.assertEqual(zone.start_idx, 1)
        self.assertEqual(zone.end_idx, 3)
        self.assertEqual(zone.low, 100)
        self.assertEqual(zone.high, 105)
        self.assertEqual(zone.direction, "bearish")
        self.assertEqual(zone.timeframe, "15m")


class TestDetectFvgsInvalidDirection(unittest.TestCase):
    def test_invalid_direction_raises(self):
        candles = make_candles(BULLISH_BASE)
        with self.assertRaises(ValueError):
            detect_fvgs(candles, "sideways", "15m")


class TestZoneLowLessThanHigh(unittest.TestCase):
    """Downstream stop-loss/target math assumes zone.low < zone.high
    unconditionally, for both directions."""

    def test_bullish_zone_low_less_than_high(self):
        zones = detect_fvgs(make_candles(BULLISH_BASE), "bullish", "15m")
        self.assertEqual(len(zones), 1)
        self.assertLess(zones[0].low, zones[0].high)

    def test_bearish_zone_low_less_than_high(self):
        zones = detect_fvgs(make_candles(BEARISH_BASE), "bearish", "15m")
        self.assertEqual(len(zones), 1)
        self.assertLess(zones[0].low, zones[0].high)


if __name__ == "__main__":
    unittest.main()
