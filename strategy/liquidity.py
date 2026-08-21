"""Liquidity sweep + break of structure (BOS) detection.

Given a swing point and the FVG that formed after it, look for:
  (a) a candle that sweeps liquidity beyond the swing (wicks past it,
      with a body opposite the setup direction), then
  (b) a later candle that closes back through that swing level (BOS).
"""

from dataclasses import dataclass

from strategy.swings import SwingPoint  # noqa: F401  (re-exported for callers' type hints)


@dataclass(frozen=True)
class SweepResult:
    swing: SwingPoint
    sweep_idx: int  # -1 if not found
    bos_idx: int  # -1 if not found
    confirmed: bool  # True iff both sweep_idx and bos_idx were found


def find_sweep_and_bos(candles, swing, fvg, direction):
    sweep_idx = _find_sweep(candles, swing, fvg, direction)
    if sweep_idx == -1:
        return SweepResult(swing=swing, sweep_idx=-1, bos_idx=-1, confirmed=False)

    bos_idx = _find_bos(candles, swing, fvg, sweep_idx, direction)
    return SweepResult(swing=swing, sweep_idx=sweep_idx, bos_idx=bos_idx, confirmed=bos_idx != -1)


def _find_sweep(candles, swing, fvg, direction):
    end = min(fvg.start_idx, len(candles) - 1)
    for i in range(swing.index + 1, end + 1):
        c = candles[i]
        if direction == "bullish":
            if c.close < c.open and c.high > swing.price:
                return i
        else:
            if c.close > c.open and c.low < swing.price:
                return i
    return -1


def _find_bos(candles, swing, fvg, sweep_idx, direction):
    end = min(fvg.end_idx, len(candles) - 1)
    for i in range(sweep_idx + 1, end + 1):
        c = candles[i]
        if direction == "bullish" and c.close > swing.price:
            return i
        if direction == "bearish" and c.close < swing.price:
            return i
    return -1
