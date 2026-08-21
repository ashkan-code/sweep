#!/usr/bin/env python3
"""Entry point: acquire a wake lock, run one full multi-timeframe scan,
print the results, then release the wake lock -- even on failure."""

import argparse
import json
import os
import subprocess
import sys

from bot import formatter
from data_provider.provider import DataProviderError, MarketDataProvider
from strategy import engine

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "base_url": "",
    "api_key": "",
    "api_key_header": "X-API-Key",
    "symbols_endpoint_path": "/symbols",
    "candles_endpoint_path": "/candles",
    "symbol_param_name": "symbol",
    "timeframe_param_name": "interval",
    "timeframe_value_map": {},
    "symbols_limit_param_name": "limit",
    "candles_limit_param_name": "limit",
    "symbols_response_list_key": "data",
    "symbol_field_name": "symbol",
    "candles_response_list_key": "data",
    "candle_field_map": {
        "timestamp": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    },
    "candles_max_per_request": 300,
    "pagination_cursor_param_name": "end_time",
    "pagination_max_pages": 5,
    "request_timeout_seconds": 8,
    "max_retries": 3,
    "retry_base_delay_seconds": 0.5,
    "retry_backoff_multiplier": 2.0,
    "retry_max_delay_seconds": 8.0,
    "retry_status_codes": [429, 500, 502, 503, 504],
    "max_workers": 15,
    "top_symbols_limit": 200,
    "trend_timeframes": ["4h", "1h"],
    "trend_lookback_candles": 250,
    "fvg_timeframes": ["5m", "15m", "30m", "1h", "2h", "4h"],
    "fvg_lookback_candles": 300,
    "swing_lookback": 3,
    "momentum_body_ratio": 0.70,
    "stop_loss_buffer_mode": "percent",
    "stop_loss_buffer_value": 0.1,
    "bot_cooldown_seconds": 180,
}


def load_config(path=None):
    path = path or DEFAULT_CONFIG_PATH
    config = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    else:
        save_config(config, path)
    return config


def save_config(config, path=None):
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run one multi-timeframe SMC scan and print results.")
    parser.add_argument("direction", choices=["bullish", "bearish"])
    parser.add_argument("--config", default=None, help="Path to config.json (default: ./config.json)")
    return parser.parse_args(argv)


def resolve_direction(argv=None):
    """Pure, testable wrapper around parse_args -- returns just the
    validated direction string."""
    return parse_args(argv).direction


def _run_wake_lock_command(name):
    try:
        subprocess.run([name], check=False)
    except FileNotFoundError:
        pass  # not running under Termux; harmless no-op elsewhere


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)

    _run_wake_lock_command("termux-wake-lock")
    try:
        provider = MarketDataProvider(config)
        try:
            results = engine.run_scan(args.direction, provider, config)
        except DataProviderError as exc:
            print("Scan failed: %s" % exc, file=sys.stderr)
            return 1
        for message in formatter.format_results(results):
            print(message)
            print()
        return 0
    finally:
        _run_wake_lock_command("termux-wake-unlock")


if __name__ == "__main__":
    sys.exit(main())
