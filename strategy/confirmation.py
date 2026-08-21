"""Entry confirmation once price returns into an FVG zone: a momentum
candle, a full engulfing candle, or neither (range, no signal)."""

from dataclasses import dataclass

DEFAULT_MOMENTUM_BODY_RATIO = 0.70

CONFIRMATION_MOMENTUM = "momentum candle"
CONFIRMATION_ENGULFING = "engulfing candle"


@dataclass(frozen=True)
class EntryResult:
    kind: str  # "signal" | "range" | "none"
    candle_idx: int  # -1 if kind == "none"


def _aligned(candle, direction):
    return candle.close > candle.open if direction == "bullish" else candle.close < candle.open


def is_momentum_candle(candle, direction, body_ratio_threshold):
    return _aligned(candle, direction) and candle.body_ratio > body_ratio_threshold


def is_engulfing_candle(candle, previous, direction):
    return (
        _aligned(candle, direction)
        and candle.body_high >= previous.body_high
        and candle.body_low <= previous.body_low
    )


def find_confirmation(candles, fvg, direction, config, search_start_idx):
    body_ratio_threshold = config.get("momentum_body_ratio", DEFAULT_MOMENTUM_BODY_RATIO)

    zone_entry_idx = -1
    for i in range(max(search_start_idx, 0), len(candles)):
        c = candles[i]
        if c.low <= fvg.high and c.high >= fvg.low:
            zone_entry_idx = i
            break
    if zone_entry_idx == -1:
        return EntryResult("none", -1)

    for i in range(zone_entry_idx, len(candles)):
        c = candles[i]
        if is_momentum_candle(c, direction, body_ratio_threshold):
            return EntryResult("signal", i)
        if i > 0 and is_engulfing_candle(c, candles[i - 1], direction):
            return EntryResult("signal", i)
    return EntryResult("range", zone_entry_idx)


def describe_confirmation(candles, idx, direction, config):
    """Re-derive which rule matched at `idx` (momentum checked first,
    then engulfing) so callers can label a confirmation type without
    EntryResult needing an extra field."""
    body_ratio_threshold = config.get("momentum_body_ratio", DEFAULT_MOMENTUM_BODY_RATIO)
    if is_momentum_candle(candles[idx], direction, body_ratio_threshold):
        return CONFIRMATION_MOMENTUM
    return CONFIRMATION_ENGULFING
