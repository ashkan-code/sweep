"""Shared helper for building synthetic candle data in tests."""

from data_provider.provider import Candle


def make_candles(ohlc):
    """ohlc: list of (open, high, low, close) tuples -> list[Candle] with
    sequential index/timestamp and zero volume."""
    return [
        Candle(index=i, timestamp=i * 60, open=o, high=h, low=l, close=c, volume=0.0)
        for i, (o, h, l, c) in enumerate(ohlc)
    ]
