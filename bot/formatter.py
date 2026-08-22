"""Render ScanResult objects into short text blocks/messages. Used now
by run_cli.py; reused later, unchanged, by the Telegram bot."""

MAX_MESSAGE_LENGTH = 4096

_DIRECTION_EMOJI = {"bullish": "\U0001F7E2", "bearish": "\U0001F534"}  # 🟢 / 🔴
_RANGE_EMOJI = "⚪"  # ⚪
_DIRECTION_LABEL = {"bullish": "صعودی", "bearish": "نزولی"}
_CONFIRMATION_LABEL = {"momentum candle": "کندل ممنتوم", "engulfing candle": "کندل انگالف"}


def _fmt_price(value):
    return "%.8g" % value


def format_signal_block(result):
    emoji = _DIRECTION_EMOJI.get(result.direction, _RANGE_EMOJI)
    label = _DIRECTION_LABEL.get(result.direction, result.direction)
    signal = result.signal
    confirmation_label = _CONFIRMATION_LABEL.get(signal.confirmation_type, signal.confirmation_type)
    return "\n".join(
        [
            "%s %s | %s" % (emoji, result.symbol, label),
            "تایم‌فریم FVG: %s" % result.fvg_timeframe,
            "محدوده FVG: %s تا %s" % (_fmt_price(signal.fvg_low), _fmt_price(signal.fvg_high)),
            "تأیید: %s" % confirmation_label,
            "زمان کندل تأییدی: %s" % signal.confirmation_timestamp,
            "ورود: %s" % _fmt_price(signal.entry),
            "حد ضرر: %s" % _fmt_price(signal.stop_loss),
            "تارگت (1:3): %s" % _fmt_price(signal.target),
        ]
    )


def format_range_line(result):
    return "%s %s در محدوده، تأییدی نیومده" % (_RANGE_EMOJI, result.symbol)


def format_result(result):
    return format_signal_block(result) if result.kind == "signal" else format_range_line(result)


def split_into_messages(blocks, max_length=MAX_MESSAGE_LENGTH):
    """Pack pre-rendered blocks into as few messages as possible, each
    <= max_length chars, joined by a blank line. Never splits a block
    across two messages."""
    messages = []
    current = []
    current_len = 0
    for block in blocks:
        add_len = len(block) + (2 if current else 0)
        if current and current_len + add_len > max_length:
            messages.append("\n\n".join(current))
            current, current_len = [block], len(block)
        else:
            current.append(block)
            current_len += add_len
    if current:
        messages.append("\n\n".join(current))
    return messages


def format_results(results):
    if not results:
        return ["No results this scan."]
    return split_into_messages([format_result(r) for r in results])
