import unittest

from bot.formatter import (
    format_range_line,
    format_result,
    format_results,
    format_signal_block,
    split_into_messages,
)
from strategy.engine import ScanResult, SignalOutput


def _signal_result(symbol="SYMBOL-1", direction="bullish"):
    signal = SignalOutput(
        symbol=symbol,
        direction=direction,
        fvg_timeframe="15m",
        confirmation_type="momentum candle",
        entry=1.2345,
        stop_loss=1.2,
        target=1.3035,
    )
    return ScanResult("signal", symbol, direction, "15m", signal)


def _range_result(symbol="SYMBOL-2"):
    return ScanResult("range", symbol, "bullish", "15m", None)


class TestFormatSignalBlock(unittest.TestCase):
    def test_exact_text(self):
        block = format_signal_block(_signal_result())
        expected = (
            "\U0001F7E2 SYMBOL-1 | bullish\n"
            "FVG timeframe: 15m\n"
            "Confirmation: momentum candle\n"
            "Entry: 1.2345\n"
            "Stop loss: 1.2\n"
            "Target (1:3): 1.3035"
        )
        self.assertEqual(block, expected)


class TestFormatRangeLine(unittest.TestCase):
    def test_exact_text(self):
        line = format_range_line(_range_result())
        self.assertEqual(line, "⚪ SYMBOL-2 in range, no confirmation yet")


class TestSplitIntoMessages(unittest.TestCase):
    def test_small_list_fits_one_message(self):
        blocks = [format_result(_signal_result()), format_result(_range_result())]
        messages = split_into_messages(blocks)
        self.assertEqual(len(messages), 1)

    def test_large_list_splits_without_truncating_blocks(self):
        results = [_signal_result(symbol="SYMBOL-%d" % i) for i in range(40)]
        blocks = [format_result(r) for r in results]

        messages = split_into_messages(blocks)

        self.assertGreater(len(messages), 1)
        for message in messages:
            self.assertLessEqual(len(message), 4096)

        recovered = "\n\n".join(messages).split("\n\n")
        self.assertEqual(recovered, blocks)

    def test_single_oversized_block_is_still_emitted_alone(self):
        huge_block = "A" * 50
        messages = split_into_messages([huge_block], max_length=10)
        self.assertEqual(messages, [huge_block])


class TestFormatResults(unittest.TestCase):
    def test_empty_results(self):
        self.assertEqual(format_results([]), ["No results this scan."])


if __name__ == "__main__":
    unittest.main()
