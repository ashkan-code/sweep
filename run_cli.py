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
    "symbols_extra_params": {},
    "candles_extra_params": {},
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
    "trend_confirm_swings": 3,
    "outlier_range_multiplier": 3.0,
    "outlier_lookback_candles": 20,
    "fvg_timeframes": ["5m", "15m", "30m", "1h", "2h", "4h"],
    "fvg_lookback_candles": 300,
    "swing_lookback": 3,
    "momentum_body_ratio": 0.70,
    "stop_loss_buffer_mode": "percent",
    "stop_loss_buffer_value": 0.1,
    "bot_cooldown_seconds": 180,
    "check_api_symbol": "",
    "check_api_timeframe": "5m",
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
    parser.add_argument("direction", nargs="?", choices=["bullish", "bearish"], default=None)
    parser.add_argument("--config", default=None, help="Path to config.json (default: ./config.json)")
    parser.add_argument(
        "--check-api",
        action="store_true",
        help="Dump raw symbols/candles endpoint responses for diagnosing config, then exit.",
    )
    return parser.parse_args(argv)


def prompt_direction():
    """Ask interactively until the user answers y/n (case-insensitive),
    re-asking on anything else instead of crashing."""
    while True:
        answer = input("Long? y/n: ").strip().lower()
        if answer == "y":
            return "bullish"
        if answer == "n":
            return "bearish"


def _direction_from_args(args):
    """Explicit CLI direction always wins (and skips the prompt, so
    scripting/automation and --check-api workflows are unaffected). Only
    when no direction was given on the command line -- and --check-api
    wasn't given either -- do we ask interactively."""
    if args.direction is not None:
        return args.direction
    if args.check_api:
        return None
    return prompt_direction()


def resolve_direction(argv=None):
    """Pure, testable wrapper around parse_args + _direction_from_args --
    returns just the resolved direction string (or None for --check-api
    with no explicit direction)."""
    return _direction_from_args(parse_args(argv))


def _run_wake_lock_command(name):
    try:
        subprocess.run([name], check=False)
    except FileNotFoundError:
        pass  # not running under Termux; harmless no-op elsewhere


def run_check_api(provider, config):
    """Dump raw endpoint responses so config/field-mapping mismatches
    can be diagnosed without going through (and being blocked by) the
    normal parsing path."""
    print("=== symbols endpoint ===")
    try:
        print(provider.get_raw_symbols_response())
    except DataProviderError as exc:
        print("ERROR: %s" % exc)
    print()

    symbol = config.get("check_api_symbol", "")
    if not symbol:
        try:
            symbols = provider.get_top_symbols(limit=1)
            symbol = symbols[0] if symbols else ""
        except DataProviderError:
            symbol = ""

    timeframe = config.get("check_api_timeframe", "5m")
    print("=== candles endpoint (symbol=%r timeframe=%s) ===" % (symbol, timeframe))
    if not symbol:
        print(
            "No symbol available to test (parsing the symbols response "
            "failed and no check_api_symbol is configured) -- set "
            "check_api_symbol in config.json and re-run."
        )
        return
    try:
        print(provider.get_raw_candles_response(symbol, timeframe, limit=5))
    except DataProviderError as exc:
        print("ERROR: %s" % exc)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)

    _run_wake_lock_command("termux-wake-lock")
    try:
        provider = MarketDataProvider(config)
        if args.check_api:
            run_check_api(provider, config)
            return 0
        direction = _direction_from_args(args)
        try:
            results = engine.run_scan(direction, provider, config)
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
