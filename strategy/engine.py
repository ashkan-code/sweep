"""Pipeline orchestrator: trend filter -> FVG -> sweep/BOS -> confirmation.

`run_scan` is the single entry point both the CLI and the future bot use.
It never prints or otherwise performs I/O beyond calling the provider —
it just returns data, so it stays fully testable with a fake provider.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import NamedTuple, Optional

from data_provider.provider import DataProviderError
from strategy import confirmation, fvg, liquidity, swings
from strategy import trend as trend_module

logger = logging.getLogger(__name__)

DEFAULT_TOP_SYMBOLS_LIMIT = 200
DEFAULT_TREND_TIMEFRAMES = ["4h", "1h"]
DEFAULT_FVG_TIMEFRAMES = ["5m", "15m", "30m", "1h", "2h", "4h"]
DEFAULT_MAX_WORKERS = 15
DEFAULT_TREND_LOOKBACK_CANDLES = 250
DEFAULT_FVG_LOOKBACK_CANDLES = 300


@dataclass
class SignalOutput:
    symbol: str
    direction: str
    fvg_timeframe: str
    fvg_low: float
    fvg_high: float
    confirmation_type: str
    confirmation_timestamp: int
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None


class ScanResult(NamedTuple):
    kind: str  # "signal" | "range"
    symbol: str
    direction: str
    fvg_timeframe: str
    signal: Optional[SignalOutput]


def run_scan(direction, provider, config):
    if direction not in ("bullish", "bearish"):
        raise ValueError("direction must be 'bullish' or 'bearish', got %r" % (direction,))

    max_workers = config.get("max_workers", DEFAULT_MAX_WORKERS)
    symbols = provider.get_top_symbols(config.get("top_symbols_limit", DEFAULT_TOP_SYMBOLS_LIMIT))

    passing = _filter_by_trend(symbols, direction, provider, config, max_workers)

    tasks = [
        (symbol, tf)
        for symbol in passing
        for tf in config.get("fvg_timeframes", DEFAULT_FVG_TIMEFRAMES)
    ]
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_scan_one, provider, symbol, tf, direction, config)
            for symbol, tf in tasks
        ]
        for future in as_completed(futures):
            result = future.result()  # _scan_one never raises
            if result is not None:
                results.append(result)
    return results


def _check_trend_one(provider, symbol, timeframe, direction, config):
    try:
        candles = provider.get_candles(
            symbol, timeframe, config.get("trend_lookback_candles", DEFAULT_TREND_LOOKBACK_CANDLES)
        )
    except DataProviderError:
        return symbol, False
    found = swings.find_swings(candles, config.get("swing_lookback", swings.DEFAULT_SWING_LOOKBACK))
    result = trend_module.classify_trend(found, candles, timeframe, config)
    return symbol, result.direction == direction


def _filter_by_trend(symbols, direction, provider, config, max_workers):
    trend_timeframes = config.get("trend_timeframes", DEFAULT_TREND_TIMEFRAMES)
    tasks = [(s, tf) for s in symbols for tf in trend_timeframes]
    aligned = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_check_trend_one, provider, s, tf, direction, config) for s, tf in tasks
        ]
        for future in as_completed(futures):
            symbol, ok = future.result()
            if ok:
                aligned.add(symbol)  # OR-filter: either timeframe aligning is enough
    return [s for s in symbols if s in aligned]  # preserve original order


def _scan_one(provider, symbol, timeframe, direction, config):
    try:
        candles = provider.get_candles(
            symbol, timeframe, config.get("fvg_lookback_candles", DEFAULT_FVG_LOOKBACK_CANDLES)
        )
    except DataProviderError:
        return None

    zones = fvg.detect_fvgs(candles, direction, timeframe)
    if not zones:
        return None
    target_fvg = zones[-1]  # most recently formed

    swing_kind = "high" if direction == "bullish" else "low"
    swing_points = swings.find_swings(
        candles, config.get("swing_lookback", swings.DEFAULT_SWING_LOOKBACK)
    )
    swing = swings.last_swing_before(swing_points, target_fvg.start_idx, kind=swing_kind)
    if swing is None:
        return None

    sweep_result = liquidity.find_sweep_and_bos(candles, swing, target_fvg, direction)
    if not sweep_result.confirmed:
        return None

    entry_result = confirmation.find_confirmation(
        candles, target_fvg, direction, config, sweep_result.bos_idx + 1
    )
    if entry_result.kind == "none":
        return None
    if entry_result.kind == "range":
        return ScanResult("range", symbol, direction, timeframe, None)

    confirmation_type = confirmation.describe_confirmation(
        candles, entry_result.candle_idx, direction, config
    )
    signal = _build_signal(
        symbol, direction, timeframe, candles[entry_result.candle_idx], target_fvg, confirmation_type, config
    )
    if not _signal_is_consistent(signal):
        logger.warning(
            "dropping inconsistent signal for %s %s %s: entry=%s stop_loss=%s target=%s "
            "(fvg=[%s, %s])",
            symbol, direction, timeframe, signal.entry, signal.stop_loss, signal.target,
            signal.fvg_low, signal.fvg_high,
        )
        return None
    return ScanResult("signal", symbol, direction, timeframe, signal)


def _build_signal(symbol, direction, timeframe, confirmation_candle, fvg_zone, confirmation_type, config):
    signal = SignalOutput(
        symbol=symbol,
        direction=direction,
        fvg_timeframe=timeframe,
        fvg_low=fvg_zone.low,
        fvg_high=fvg_zone.high,
        confirmation_type=confirmation_type,
        confirmation_timestamp=confirmation_candle.timestamp,
    )
    buffer = _compute_stop_buffer(fvg_zone, config)
    entry = confirmation_candle.close
    if direction == "bullish":
        stop_loss = fvg_zone.low - buffer
        target = entry + 3 * (entry - stop_loss)
    else:
        stop_loss = fvg_zone.high + buffer
        target = entry - 3 * (stop_loss - entry)
    signal.entry = entry
    signal.stop_loss = stop_loss
    signal.target = target
    return signal


def _signal_is_consistent(signal):
    """Sanity check every signal must satisfy before it's ever returned:
    bullish needs stop_loss < entry < target, bearish the mirror. A
    violation (e.g. the confirmation candle's price having drifted far
    from the FVG zone by the time it fired) means the signal is not
    safe to act on and must be dropped rather than shown."""
    if signal.direction == "bullish":
        return signal.stop_loss < signal.entry < signal.target
    return signal.stop_loss > signal.entry > signal.target


def _compute_stop_buffer(fvg_zone, config):
    mode = config.get("stop_loss_buffer_mode", "percent")
    value = config.get("stop_loss_buffer_value", 0.1)
    if mode == "ticks":
        return value
    zone_height = fvg_zone.high - fvg_zone.low
    return zone_height * (value / 100.0)
