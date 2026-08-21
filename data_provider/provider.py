"""Generic market data access layer.

Every detail that is specific to a particular data backend (base URL,
endpoint paths, request parameter names, response JSON field names) is
read from the config dict passed into MarketDataProvider. Swapping the
underlying data source is a config change, never a code change.
"""

import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter

DEFAULT_MAX_WORKERS = 15
DEFAULT_REQUEST_TIMEOUT_SECONDS = 8
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY_SECONDS = 0.5
DEFAULT_RETRY_BACKOFF_MULTIPLIER = 2.0
DEFAULT_RETRY_MAX_DELAY_SECONDS = 8.0
DEFAULT_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
DEFAULT_CANDLES_MAX_PER_REQUEST = 300
DEFAULT_PAGINATION_MAX_PAGES = 5

DEFAULT_CANDLE_FIELD_MAP = {
    "timestamp": "timestamp",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
}


class DataProviderError(Exception):
    """Raised for any data-access failure: network error, bad status,
    or a response shape that doesn't match the configured field map."""


@dataclass(frozen=True)
class Candle:
    index: int
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        rng = self.range
        return self.body_size / rng if rng > 0 else 0.0


def _sleep_backoff(attempt, base_delay, multiplier, max_delay):
    delay = min(base_delay * (multiplier ** attempt), max_delay)
    time.sleep(delay)


def _request_with_retry(session, method, url, params, config):
    """Retry on connection errors/timeouts and configured HTTP status
    codes (default: 429 and 5xx), with exponential backoff. A plain 4xx
    (bad request, auth, not found) fails immediately without retrying."""
    max_retries = config.get("max_retries", DEFAULT_MAX_RETRIES)
    base_delay = config.get("retry_base_delay_seconds", DEFAULT_RETRY_BASE_DELAY_SECONDS)
    multiplier = config.get("retry_backoff_multiplier", DEFAULT_RETRY_BACKOFF_MULTIPLIER)
    max_delay = config.get("retry_max_delay_seconds", DEFAULT_RETRY_MAX_DELAY_SECONDS)
    retry_statuses = set(config.get("retry_status_codes", DEFAULT_RETRY_STATUS_CODES))
    timeout = config.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)

    attempt = 0
    while True:
        try:
            response = session.request(method, url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt >= max_retries:
                raise DataProviderError(
                    "request failed after %d attempt(s): %s" % (attempt + 1, exc)
                ) from exc
            _sleep_backoff(attempt, base_delay, multiplier, max_delay)
            attempt += 1
            continue

        if response.status_code in retry_statuses:
            if attempt >= max_retries:
                raise DataProviderError(
                    "request returned HTTP %d after %d attempt(s)"
                    % (response.status_code, attempt + 1)
                )
            _sleep_backoff(attempt, base_delay, multiplier, max_delay)
            attempt += 1
            continue

        if not response.ok:
            raise DataProviderError(
                "request returned HTTP %d: %s" % (response.status_code, response.text[:300])
            )
        return response


class MarketDataProvider:
    """Config-driven data access. Nothing about the actual backend is
    hardcoded here: endpoint paths, parameter names, and response field
    names all come from `config`."""

    def __init__(self, config):
        base_url = config["base_url"].rstrip("/")
        self._config = config
        self._symbols_url = base_url + config.get("symbols_endpoint_path", "/symbols")
        self._candles_url = base_url + config.get("candles_endpoint_path", "/candles")

        max_workers = config.get("max_workers", DEFAULT_MAX_WORKERS)
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=max_workers, pool_maxsize=max_workers)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        api_key = config.get("api_key", "")
        if api_key:
            self._session.headers[config.get("api_key_header", "X-API-Key")] = api_key

    def get_top_symbols(self, limit=200):
        params = {self._config.get("symbols_limit_param_name", "limit"): limit}
        response = _request_with_retry(
            self._session, "GET", self._symbols_url, params, self._config
        )
        payload = response.json()
        list_key = self._config.get("symbols_response_list_key", "data")
        data = payload.get(list_key, payload) if list_key else payload
        if not isinstance(data, list):
            raise DataProviderError("unexpected symbols response shape: expected a list")
        field = self._config.get("symbol_field_name", "symbol")
        symbols = [item[field] for item in data if field in item]
        return symbols[:limit]

    def get_candles(self, symbol, timeframe, lookback):
        per_request = min(lookback, self._config.get(
            "candles_max_per_request", DEFAULT_CANDLES_MAX_PER_REQUEST
        ))
        max_pages = self._config.get("pagination_max_pages", DEFAULT_PAGINATION_MAX_PAGES)
        interval = self._config.get("timeframe_value_map", {}).get(timeframe, timeframe)

        collected = []
        cursor = None
        for _ in range(max_pages):
            if len(collected) >= lookback:
                break
            params = {
                self._config.get("symbol_param_name", "symbol"): symbol,
                self._config.get("timeframe_param_name", "interval"): interval,
                self._config.get("candles_limit_param_name", "limit"): per_request,
            }
            if cursor is not None:
                params[self._config.get("pagination_cursor_param_name", "end_time")] = cursor
            response = _request_with_retry(
                self._session, "GET", self._candles_url, params, self._config
            )
            page = self._parse_candles(response.json())
            if not page:
                break
            collected = page + collected
            cursor = page[0].timestamp - 1
            if len(page) < per_request:
                break

        collected.sort(key=lambda c: c.timestamp)
        trimmed = collected[-lookback:] if lookback else collected
        return [
            Candle(
                index=i,
                timestamp=c.timestamp,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for i, c in enumerate(trimmed)
        ]

    def _parse_candles(self, payload):
        list_key = self._config.get("candles_response_list_key", "data")
        data = payload.get(list_key, payload) if list_key else payload
        if not isinstance(data, list):
            raise DataProviderError("unexpected candles response shape: expected a list")
        field_map = self._config.get("candle_field_map", DEFAULT_CANDLE_FIELD_MAP)
        candles = []
        for raw in data:
            try:
                candles.append(
                    Candle(
                        index=0,
                        timestamp=int(raw[field_map["timestamp"]]),
                        open=float(raw[field_map["open"]]),
                        high=float(raw[field_map["high"]]),
                        low=float(raw[field_map["low"]]),
                        close=float(raw[field_map["close"]]),
                        volume=float(raw.get(field_map["volume"], 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise DataProviderError("could not parse a candle entry: %s" % exc) from exc
        return candles
