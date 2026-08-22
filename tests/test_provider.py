import unittest

import requests

from data_provider.provider import DataProviderError, MarketDataProvider, _request_with_retry

RETRY_CONFIG = {
    "max_retries": 3,
    "retry_base_delay_seconds": 0.001,
    "retry_backoff_multiplier": 2.0,
    "retry_max_delay_seconds": 0.005,
    "retry_status_codes": [429, 500, 502, 503, 504],
    "request_timeout_seconds": 1,
}


class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class _FakeSession:
    """Stubs `.request` with a scripted sequence of outcomes: either an
    exception instance to raise, or an (status_code, json_body) tuple."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.calls_log = []

    def request(self, method, url, params=None, timeout=None):
        self.calls += 1
        self.calls_log.append((method, url, params))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        status, body = step
        return _FakeResponse(status, body)


class TestRequestWithRetry(unittest.TestCase):
    def test_connection_error_retried_then_succeeds(self):
        session = _FakeSession(
            [requests.ConnectionError("boom"), requests.ConnectionError("boom"), (200, {"ok": True})]
        )
        response = _request_with_retry(session, "GET", "http://x/y", {}, RETRY_CONFIG)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(session.calls, 3)

    def test_429_retried_then_succeeds(self):
        session = _FakeSession([(429, {}), (200, {"ok": True})])
        response = _request_with_retry(session, "GET", "http://x/y", {}, RETRY_CONFIG)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(session.calls, 2)

    def test_404_fails_immediately_without_retry(self):
        session = _FakeSession([(404, "not found")])
        with self.assertRaises(DataProviderError):
            _request_with_retry(session, "GET", "http://x/y", {}, RETRY_CONFIG)
        self.assertEqual(session.calls, 1)

    def test_exhausted_retries_raises(self):
        session = _FakeSession([(500, {}), (500, {}), (500, {}), (500, {})])
        with self.assertRaises(DataProviderError):
            _request_with_retry(session, "GET", "http://x/y", {}, RETRY_CONFIG)
        self.assertEqual(session.calls, RETRY_CONFIG["max_retries"] + 1)


class TestMarketDataProviderSymbols(unittest.TestCase):
    def test_default_field_names(self):
        provider = MarketDataProvider({"base_url": "http://fake.invalid", **RETRY_CONFIG})
        provider._session = _FakeSession(
            [(200, {"data": [{"symbol": "SYMBOL-1"}, {"symbol": "SYMBOL-2"}]})]
        )
        self.assertEqual(provider.get_top_symbols(limit=200), ["SYMBOL-1", "SYMBOL-2"])

    def test_custom_field_names(self):
        config = {
            "base_url": "http://fake.invalid",
            "symbol_field_name": "ticker",
            "symbols_response_list_key": "result",
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        provider._session = _FakeSession([(200, {"result": [{"ticker": "SYMBOL-1"}]})])
        self.assertEqual(provider.get_top_symbols(limit=200), ["SYMBOL-1"])


class TestMarketDataProviderCandles(unittest.TestCase):
    def test_custom_candle_field_map_single_page(self):
        config = {
            "base_url": "http://fake.invalid",
            "candle_field_map": {
                "timestamp": "t", "open": "o", "high": "h",
                "low": "l", "close": "c", "volume": "v",
            },
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        raw = [
            {"t": 120, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
            {"t": 60, "o": 2, "h": 3, "l": 1, "c": 2.5, "v": 20},
            {"t": 180, "o": 3, "h": 4, "l": 2, "c": 3.5, "v": 30},
        ]
        provider._session = _FakeSession([(200, {"data": raw})])

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=3)

        self.assertEqual([c.timestamp for c in candles], [60, 120, 180])
        self.assertEqual([c.index for c in candles], [0, 1, 2])
        self.assertEqual(candles[0].open, 2)
        self.assertEqual(candles[0].volume, 20)
        self.assertEqual(provider._session.calls, 1)

    def test_pagination_across_multiple_pages(self):
        config = {
            "base_url": "http://fake.invalid",
            "candles_max_per_request": 3,
            "pagination_cursor_param_name": "end_time",
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        recent_page = [
            {"timestamp": 400, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
            {"timestamp": 500, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
            {"timestamp": 600, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
        ]
        older_page = [
            {"timestamp": 100, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
            {"timestamp": 200, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
            {"timestamp": 300, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1},
        ]
        fake_session = _FakeSession([(200, {"data": recent_page}), (200, {"data": older_page})])
        provider._session = fake_session

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=5)

        self.assertEqual(fake_session.calls, 2)
        self.assertEqual(fake_session.calls_log[1][2]["end_time"], 399)
        self.assertEqual([c.timestamp for c in candles], [200, 300, 400, 500, 600])
        self.assertEqual([c.index for c in candles], [0, 1, 2, 3, 4])


class TestListShapedCandles(unittest.TestCase):
    """Some backends return candles as positional arrays instead of
    objects; the field map can then use integer indices."""

    def test_integer_index_field_map(self):
        config = {
            "base_url": "http://fake.invalid",
            "candle_field_map": {
                "timestamp": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5,
            },
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        raw = [
            [1000, 10, 12, 9, 11, 500],
            [2000, 11, 13, 10, 12, 600],
        ]
        provider._session = _FakeSession([(200, {"data": raw})])

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=2)

        self.assertEqual([c.timestamp for c in candles], [1000, 2000])
        self.assertEqual(candles[0].open, 10)
        self.assertEqual(candles[0].volume, 500)

    def test_row_missing_volume_index_defaults_to_zero(self):
        config = {
            "base_url": "http://fake.invalid",
            "candle_field_map": {
                "timestamp": 0, "open": 1, "high": 2, "low": 3, "close": 4, "volume": 5,
            },
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        raw = [[1000, 10, 12, 9, 11]]  # no volume element at all
        provider._session = _FakeSession([(200, {"data": raw})])

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=1)

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].volume, 0.0)


class TestMultiCandidateFieldNames(unittest.TestCase):
    def test_candle_field_map_tries_candidates_in_order(self):
        config = {
            "base_url": "http://fake.invalid",
            "candle_field_map": {
                "timestamp": ["ts", "time", "t"],
                "open": ["open", "o"],
                "high": ["high", "h"],
                "low": ["low", "l"],
                "close": ["close", "c"],
                "volume": ["baseVol", "vol", "volume", "b"],
            },
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        # Only the last-listed candidate is present for each field.
        raw = [{"t": 1000, "o": 10, "h": 12, "l": 9, "c": 11, "vol": 500}]
        provider._session = _FakeSession([(200, {"data": raw})])

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=1)

        self.assertEqual(candles[0].timestamp, 1000)
        self.assertEqual(candles[0].open, 10)
        self.assertEqual(candles[0].volume, 500)

    def test_candle_field_map_prefers_earlier_candidate(self):
        config = {
            "base_url": "http://fake.invalid",
            "candle_field_map": {
                "timestamp": ["ts", "t"], "open": "open", "high": "high",
                "low": "low", "close": "close", "volume": "volume",
            },
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        raw = [{"ts": 1000, "t": 9999, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1}]
        provider._session = _FakeSession([(200, {"data": raw})])

        candles = provider.get_candles("SYMBOL-1", "15m", lookback=1)

        self.assertEqual(candles[0].timestamp, 1000)  # "ts" wins over "t"

    def test_symbol_field_name_tries_candidates(self):
        config = {
            "base_url": "http://fake.invalid",
            "symbol_field_name": ["symbol", "symbolName"],
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        provider._session = _FakeSession([(200, {"data": [{"symbolName": "SYMBOL-1"}]})])

        self.assertEqual(provider.get_top_symbols(limit=200), ["SYMBOL-1"])

    def test_symbol_field_name_prefers_earlier_candidate(self):
        config = {
            "base_url": "http://fake.invalid",
            "symbol_field_name": ["symbol", "symbolName"],
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        provider._session = _FakeSession(
            [(200, {"data": [{"symbol": "SYMBOL-1", "symbolName": "SYMBOL-WRONG"}]})]
        )

        self.assertEqual(provider.get_top_symbols(limit=200), ["SYMBOL-1"])


class TestExtraStaticParams(unittest.TestCase):
    def test_symbols_extra_params_are_sent(self):
        config = {
            "base_url": "http://fake.invalid",
            "symbols_extra_params": {"category": "linear"},
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        fake_session = _FakeSession([(200, {"data": [{"symbol": "SYMBOL-1"}]})])
        provider._session = fake_session

        provider.get_top_symbols(limit=200)

        params = fake_session.calls_log[0][2]
        self.assertEqual(params["category"], "linear")
        self.assertEqual(params["limit"], 200)

    def test_candles_extra_params_are_sent(self):
        config = {
            "base_url": "http://fake.invalid",
            "candles_extra_params": {"type": "futures"},
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        raw = [{"timestamp": 1000, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1}]
        fake_session = _FakeSession([(200, {"data": raw})])
        provider._session = fake_session

        provider.get_candles("SYMBOL-1", "15m", lookback=1)

        params = fake_session.calls_log[0][2]
        self.assertEqual(params["type"], "futures")
        self.assertEqual(params["symbol"], "SYMBOL-1")


class TestRawDiagnosticMethods(unittest.TestCase):
    def test_get_raw_symbols_response_returns_exact_payload(self):
        config = {
            "base_url": "http://fake.invalid",
            "symbols_extra_params": {"category": "linear"},
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        payload = {"data": [{"symbol": "SYMBOL-1"}], "extra": "field"}
        fake_session = _FakeSession([(200, payload)])
        provider._session = fake_session

        result = provider.get_raw_symbols_response()

        self.assertEqual(result, payload)
        self.assertEqual(fake_session.calls_log[0][2]["category"], "linear")

    def test_get_raw_candles_response_returns_exact_payload(self):
        config = {
            "base_url": "http://fake.invalid",
            "candles_extra_params": {"type": "futures"},
            **RETRY_CONFIG,
        }
        provider = MarketDataProvider(config)
        payload = {"data": [{"anything": "goes"}], "note": "unparsed"}
        fake_session = _FakeSession([(200, payload)])
        provider._session = fake_session

        result = provider.get_raw_candles_response("SYMBOL-1", "15m", limit=5)

        self.assertEqual(result, payload)
        params = fake_session.calls_log[0][2]
        self.assertEqual(params["symbol"], "SYMBOL-1")
        self.assertEqual(params["type"], "futures")


if __name__ == "__main__":
    unittest.main()
