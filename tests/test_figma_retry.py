"""Tests for Figma API retry logic, rate limiting, and caching."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from processors.enhanced_figma_processor import EnhancedFigmaProcessor


@pytest.fixture
def processor():
    """Processor with a fake token (no real API calls)."""
    p = EnhancedFigmaProcessor(api_token="test-token-123")
    # Override request delay to speed up tests
    p._request_delay = 0.0
    p._cache_ttl = 0.1  # 100ms for cache tests
    yield p
    p.close()


class TestParseRetryAfter:
    def test_parses_seconds(self):
        assert EnhancedFigmaProcessor._parse_retry_after("60") == 60.0

    def test_parses_float_seconds(self):
        assert EnhancedFigmaProcessor._parse_retry_after("0.5") == 0.5

    def test_returns_none_for_empty(self):
        assert EnhancedFigmaProcessor._parse_retry_after("") is None

    def test_returns_none_for_none(self):
        assert EnhancedFigmaProcessor._parse_retry_after(None) is None

    def test_parses_http_date(self):
        # A date 10 seconds in the future
        from email.utils import format_datetime
        from datetime import datetime, timezone, timedelta

        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        date_str = format_datetime(future, usegmt=True)
        result = EnhancedFigmaProcessor._parse_retry_after(date_str)
        # Should be ~10s (allow 2s tolerance for test execution)
        assert result is not None
        assert 8 <= result <= 12

    def test_returns_none_for_invalid_string(self):
        assert EnhancedFigmaProcessor._parse_retry_after("not-a-date") is None


class TestRetryDelay:
    def test_uses_retry_after_when_present(self, processor):
        response = httpx.Response(429, headers={"retry-after": "5"})
        delay = processor._retry_delay(0, response)
        assert delay == 5.0

    def test_caps_retry_after(self, processor):
        response = httpx.Response(429, headers={"retry-after": "300"})
        delay = processor._retry_delay(0, response)
        assert delay <= processor._MAX_RETRY_DELAY

    def test_exponential_backoff_when_no_retry_after(self, processor):
        response = httpx.Response(429)
        d0 = processor._retry_delay(0, response)
        d1 = processor._retry_delay(1, response)
        d2 = processor._retry_delay(2, response)
        # Should be increasing (on average)
        assert d0 < d1 < d2 + 1  # +1 for jitter tolerance

    def test_never_exceeds_max_delay(self, processor):
        response = httpx.Response(429)
        for attempt in range(20):
            delay = processor._retry_delay(attempt, response)
            assert delay <= processor._MAX_RETRY_DELAY


class TestFigmaGetRetry:
    def test_returns_success_on_first_try(self, processor):
        mock_response = httpx.Response(200, json={"ok": True})
        with patch.object(processor._figma_client, "get", return_value=mock_response):
            result = processor._figma_get("https://api.figma.com/v1/files/abc")
            assert result.status_code == 200

    def test_retries_on_429_then_succeeds(self, processor):
        resp_429 = httpx.Response(
            429,
            headers={"retry-after": "0"},
            text="Rate limited",
        )
        resp_200 = httpx.Response(200, json={"ok": True})
        with patch.object(processor._figma_client, "get", side_effect=[resp_429, resp_200]):
            result = processor._figma_get("https://api.figma.com/v1/files/abc")
            assert result.status_code == 200

    def test_gives_up_after_max_retries(self, processor):
        resp_429 = httpx.Response(429, text="Still limited")
        calls = []
        with patch.object(processor._figma_client, "get", side_effect=[resp_429] * 10) as mock_get:
            result = processor._figma_get("https://api.figma.com/v1/files/abc")
            # Should have tried MAX_RETRIES + 1 times
            assert mock_get.call_count == processor._MAX_RETRIES + 1
            assert result.status_code == 429

    def test_caches_successful_response(self, processor):
        resp_200 = httpx.Response(200, json={"data": "cached"})
        with patch.object(processor._figma_client, "get", return_value=resp_200) as mock_get:
            # First call hits the network
            r1 = processor._figma_get("https://api.figma.com/v1/files/abc")
            assert r1.status_code == 200
            assert mock_get.call_count == 1

            # Second call should use cache
            r2 = processor._figma_get("https://api.figma.com/v1/files/abc")
            assert r2.status_code == 200
            assert mock_get.call_count == 1  # no extra network call

    def test_cache_expires(self, processor):
        resp_200 = httpx.Response(200, json={"data": "temp"})
        with patch.object(processor._figma_client, "get", return_value=resp_200) as mock_get:
            processor._figma_get("https://api.figma.com/v1/files/abc")
            assert mock_get.call_count == 1

            # Wait for cache to expire (cache_ttl is 0.1s in fixture)
            time.sleep(0.15)
            processor._figma_get("https://api.figma.com/v1/files/abc")
            assert mock_get.call_count == 2  # network called again


class TestLogRateLimitInfo:
    def test_logs_headers(self, processor, capsys):
        response = httpx.Response(
            429,
            headers={
                "x-rate-limit-limit": "100",
                "x-rate-limit-remaining": "0",
                "x-rate-limit-reset": "1700000000",
                "retry-after": "60",
            },
            text="Too many requests",
        )
        processor._log_rate_limit_info(response)
        captured = capsys.readouterr()
        assert "FIGMA 429" in captured.out
        assert "Limit=100" in captured.out
        assert "Remaining=0" in captured.out
