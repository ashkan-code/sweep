import unittest

from data_provider.provider import DataProviderError
from strategy.engine import run_scan
from tests.test_trend import MIXED, ZIGZAG
from tests.util import make_candles

CONFIG = {
    "swing_lookback": 1,
    "stop_loss_buffer_mode": "ticks",
    "stop_loss_buffer_value": 0.5,
    "max_workers": 4,
}

# Full bullish funnel on the 15m timeframe: swing high @ idx1 (price 12),
# sweep (bearish wick above 12) @ idx3, BOS (close back above 12) + FVG
# impulsive candle @ idx4, FVG gap [13, 16] closed by idx3/idx5, zone
# re-entered @ idx5, momentum confirmation candle @ idx6.
SIGNAL_15M = [
    (9.5, 10, 9, 9.8),  # 0
    (11, 12, 11, 11.5),  # 1 swing high 12
    (11.5, 11.8, 10, 10.5),  # 2
    (11, 13, 10.5, 10.8),  # 3 sweep + FVG c1 (high=13)
    (11, 19, 10.5, 18),  # 4 BOS + FVG c2 (impulsive, closes 18 > gap_high 16)
    (17, 20, 16, 19),  # 5 FVG c3 (low=16); zone re-entry, not confirmed
    (15, 25, 14, 24),  # 6 momentum confirmation candle
]

# Same funnel through BOS/FVG formation, but without a confirmation
# candle afterward -> stays "range".
RANGE_15M = SIGNAL_15M[:6]


class _FakeProvider:
    def __init__(self, symbols, candles_by_key, fail_symbols=()):
        self._symbols = symbols
        self._candles_by_key = candles_by_key
        self._fail_symbols = set(fail_symbols)

    def get_top_symbols(self, limit=200):
        return self._symbols[:limit]

    def get_candles(self, symbol, timeframe, lookback):
        if symbol in self._fail_symbols:
            raise DataProviderError("synthetic failure")
        return self._candles_by_key.get((symbol, timeframe), [])


class TestRunScan(unittest.TestCase):
    def setUp(self):
        symbols = ["SYMBOL-1", "SYMBOL-2", "SYMBOL-3", "SYMBOL-4"]
        candles_by_key = {
            ("SYMBOL-1", "4h"): make_candles(ZIGZAG),
            ("SYMBOL-1", "15m"): make_candles(SIGNAL_15M),
            ("SYMBOL-2", "4h"): make_candles(ZIGZAG),
            ("SYMBOL-2", "15m"): make_candles(RANGE_15M),
            ("SYMBOL-3", "4h"): make_candles(MIXED),
        }
        self.provider = _FakeProvider(symbols, candles_by_key, fail_symbols=["SYMBOL-4"])

    def test_signal_range_filter_and_failure_are_all_handled(self):
        results = run_scan("bullish", self.provider, CONFIG)
        by_symbol = {r.symbol: r for r in results}

        self.assertIn("SYMBOL-1", by_symbol)
        signal_result = by_symbol["SYMBOL-1"]
        self.assertEqual(signal_result.kind, "signal")
        self.assertEqual(signal_result.fvg_timeframe, "15m")
        signal = signal_result.signal
        self.assertEqual(signal.confirmation_type, "momentum candle")
        self.assertEqual(signal.entry, 24)
        self.assertEqual(signal.stop_loss, 12.5)  # fvg.low(13) - buffer(0.5)
        self.assertEqual(signal.target, 58.5)  # entry + 3*(entry - stop_loss)

        self.assertIn("SYMBOL-2", by_symbol)
        range_result = by_symbol["SYMBOL-2"]
        self.assertEqual(range_result.kind, "range")
        self.assertIsNone(range_result.signal)

        self.assertNotIn("SYMBOL-3", by_symbol)  # filtered out at the trend stage
        self.assertNotIn("SYMBOL-4", by_symbol)  # every get_candles call fails

    def test_invalid_direction_raises(self):
        with self.assertRaises(ValueError):
            run_scan("sideways", self.provider, CONFIG)


if __name__ == "__main__":
    unittest.main()
