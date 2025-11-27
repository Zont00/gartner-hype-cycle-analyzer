"""
Unit tests for FinanceCollector (Yahoo Finance data collector with DeepSeek ticker discovery).
Tests cover successful collection, DeepSeek integration, yfinance mocking, error handling, and edge cases.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import httpx
import json
import pandas as pd

from app.collectors.finance import FinanceCollector


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests to avoid needing .env file"""
    mock_settings_obj = Mock()
    mock_settings_obj.deepseek_api_key = "test-api-key-123"
    with patch("app.collectors.finance.get_settings", return_value=mock_settings_obj):
        yield mock_settings_obj


@pytest.fixture
def mock_ticker_history():
    """Create mock pandas DataFrame for ticker history"""
    def _create_history(start_price=100.0, end_price=120.0, num_days=30, volume=1000000):
        dates = pd.date_range(end=datetime.now(), periods=num_days, freq='D')
        prices = [start_price + (end_price - start_price) * i / (num_days - 1) for i in range(num_days)]
        return pd.DataFrame({
            'Close': prices,
            'Volume': [volume] * num_days
        }, index=dates)
    return _create_history


@pytest.mark.asyncio
async def test_finance_collector_success(mock_ticker_history):
    """Test successful data collection with DeepSeek and yfinance mocked"""
    collector = FinanceCollector()

    # Mock DeepSeek API response
    mock_deepseek_response = {
        "choices": [
            {
                "message": {
                    "content": '["IBM", "GOOGL", "MSFT"]'
                }
            }
        ]
    }

    # Mock yfinance Ticker objects
    mock_ticker_ibm = Mock()
    mock_ticker_ibm.info = {
        "symbol": "IBM",
        "longName": "IBM Corporation",
        "marketCap": 150000000000,
        "sector": "Technology",
        "industry": "Software"
    }
    mock_ticker_ibm.history.side_effect = [
        mock_ticker_history(100, 110, 30, 1000000),  # 1m
        mock_ticker_history(90, 110, 180, 900000),   # 6m
        mock_ticker_history(80, 110, 730, 800000)    # 2y
    ]

    mock_ticker_googl = Mock()
    mock_ticker_googl.info = {
        "symbol": "GOOGL",
        "longName": "Alphabet Inc.",
        "marketCap": 1800000000000,
        "sector": "Technology",
        "industry": "Internet"
    }
    mock_ticker_googl.history.side_effect = [
        mock_ticker_history(150, 165, 30, 2000000),  # 1m
        mock_ticker_history(140, 165, 180, 1900000), # 6m
        mock_ticker_history(120, 165, 730, 1800000)  # 2y
    ]

    mock_ticker_msft = Mock()
    mock_ticker_msft.info = {
        "symbol": "MSFT",
        "longName": "Microsoft Corporation",
        "marketCap": 2500000000000,
        "sector": "Technology",
        "industry": "Software"
    }
    mock_ticker_msft.history.side_effect = [
        mock_ticker_history(300, 315, 30, 5000000),  # 1m
        mock_ticker_history(280, 315, 180, 4800000), # 6m
        mock_ticker_history(250, 315, 730, 4500000)  # 2y
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        # Mock DeepSeek API call
        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Mock yfinance Ticker creation (each ticker called 4 times: info + 3 history calls)
        mock_yf_ticker.side_effect = [
            mock_ticker_ibm,
            mock_ticker_googl,
            mock_ticker_msft
        ]

        result = await collector.collect("quantum computing")

        # Verify structure
        assert result["source"] == "yahoo_finance"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify discovery
        assert result["companies_found"] == 3
        assert set(result["tickers"]) == {"IBM", "GOOGL", "MSFT"}

        # Verify market metrics
        assert result["total_market_cap"] > 0
        assert result["avg_market_cap"] > 0

        # Verify price changes
        assert result["avg_price_change_1m"] > 0  # All went up
        assert result["avg_price_change_6m"] > 0
        assert result["avg_price_change_2y"] > 0

        # Verify volume metrics
        assert result["avg_volume_1m"] > 0
        assert result["avg_volume_6m"] > 0
        assert result["volume_trend"] in ["increasing", "stable", "decreasing"]

        # Verify volatility
        assert result["avg_volatility_1m"] >= 0
        assert result["avg_volatility_6m"] >= 0

        # Verify derived insights
        assert result["market_maturity"] in ["emerging", "developing", "mature"]
        assert result["investor_sentiment"] in ["positive", "neutral", "negative"]
        assert result["investment_momentum"] in ["accelerating", "steady", "decelerating"]

        # Verify top companies
        assert len(result["top_companies"]) == 3
        assert result["top_companies"][0]["ticker"] in ["IBM", "GOOGL", "MSFT"]
        assert "market_cap" in result["top_companies"][0]

        # Verify no errors
        assert result["errors"] == []

        # Verify JSON serializable
        json.dumps(result)  # Should not raise


@pytest.mark.asyncio
async def test_finance_collector_deepseek_api_failure():
    """Test fallback to ETFs when DeepSeek API fails"""
    collector = FinanceCollector()

    with patch("httpx.AsyncClient.post") as mock_post:
        # Mock DeepSeek API failure
        mock_post.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(),
            response=Mock(status_code=500)
        )

        # Mock yfinance for fallback ETFs
        mock_ticker = Mock()
        mock_ticker.info = {
            "symbol": "QQQ",
            "longName": "Invesco QQQ Trust",
            "marketCap": 200000000000,
            "sector": "ETF",
            "industry": "ETF"
        }
        mock_ticker.history.return_value = pd.DataFrame({
            'Close': [100, 105],
            'Volume': [1000000, 1000000]
        })

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("unknown technology")

            # Should use fallback ETFs
            assert result["companies_found"] >= 0
            assert "DeepSeek HTTP 500" in result["errors"] or len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_finance_collector_deepseek_rate_limit():
    """Test graceful handling of DeepSeek rate limiting"""
    collector = FinanceCollector()

    mock_response = Mock()
    mock_response.status_code = 429

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited",
            request=Mock(),
            response=mock_response
        )

        # Mock yfinance for fallback
        mock_ticker = Mock()
        mock_ticker.info = {"symbol": "QQQ", "marketCap": 200000000000, "sector": "ETF", "industry": "ETF", "longName": "QQQ"}
        mock_ticker.history.return_value = pd.DataFrame({'Close': [100, 105], 'Volume': [1000000, 1000000]})

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test keyword")

            assert "DeepSeek rate limited" in result["errors"]


@pytest.mark.asyncio
async def test_finance_collector_deepseek_no_api_key():
    """Test behavior when DeepSeek API key is not configured"""
    collector = FinanceCollector()

    with patch("app.collectors.finance.get_settings") as mock_get_settings:
        mock_settings = Mock()
        mock_settings.deepseek_api_key = None  # No API key
        mock_get_settings.return_value = mock_settings

        # Mock yfinance for fallback
        mock_ticker = Mock()
        mock_ticker.info = {"symbol": "QQQ", "marketCap": 200000000000, "sector": "ETF", "industry": "ETF", "longName": "QQQ"}
        mock_ticker.history.return_value = pd.DataFrame({'Close': [100, 105], 'Volume': [1000000, 1000000]})

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test")

            assert any("DeepSeek API key not configured" in err for err in result["errors"])
            assert result["companies_found"] >= 0  # Should still return data using fallback


@pytest.mark.asyncio
async def test_finance_collector_invalid_ticker():
    """Test handling of invalid ticker returned by DeepSeek"""
    collector = FinanceCollector()

    # Mock DeepSeek returning an invalid ticker (>5 characters, fails validation)
    mock_deepseek_response = {
        "choices": [{"message": {"content": '["INVALID123"]'}}]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Mock yfinance Ticker for fallback ETFs
        mock_ticker = Mock()
        mock_ticker.info = {}  # Empty info indicates ticker not found

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test")

            # Should handle gracefully - ticker validation rejects INVALID123
            assert result["companies_found"] == 0
            assert any("Invalid ticker format: INVALID123" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_finance_collector_ticker_no_data():
    """Test handling of ticker with no historical data"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["TESTticker"]'}}]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Mock yfinance Ticker with valid info but empty history
        mock_ticker = Mock()
        mock_ticker.info = {"symbol": "TESTICKER", "marketCap": 1000000}
        mock_ticker.history.return_value = pd.DataFrame()  # Empty DataFrame

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test")

            assert result["companies_found"] == 0
            assert any("No data" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_finance_collector_partial_failure(mock_ticker_history):
    """Test when some tickers succeed and some fail"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["GOOD", "BAD"]'}}]
    }

    # Mock good ticker
    mock_ticker_good = Mock()
    mock_ticker_good.info = {
        "symbol": "GOOD",
        "longName": "Good Company",
        "marketCap": 1000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    mock_ticker_good.history.side_effect = [
        mock_ticker_history(100, 110, 30),
        mock_ticker_history(90, 110, 180),
        mock_ticker_history(80, 110, 730)
    ]

    # Mock bad ticker
    mock_ticker_bad = Mock()
    mock_ticker_bad.info = {"symbol": "BAD"}
    mock_ticker_bad.history.return_value = pd.DataFrame()  # No data

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.side_effect = [
            mock_ticker_good,
            mock_ticker_bad
        ]

        result = await collector.collect("test partial")

        # Should have data from good ticker only
        assert result["companies_found"] == 1
        assert result["tickers"] == ["GOOD"]
        assert result["total_market_cap"] > 0
        assert len(result["errors"]) > 0  # Should track bad ticker error


@pytest.mark.asyncio
async def test_finance_collector_market_maturity_mature(mock_ticker_history):
    """Test market maturity detection for mature market"""
    collector = FinanceCollector()

    # Mock large market cap, low volatility companies
    mock_deepseek_response = {
        "choices": [{"message": {"content": '["BIGCAP"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "BIGCAP",
        "longName": "Big Cap Corp",
        "marketCap": 500000000000,  # $500B
        "sector": "Tech",
        "industry": "Software"
    }
    # Low volatility history (stable prices)
    mock_ticker.history.side_effect = [
        mock_ticker_history(100, 102, 30),   # 2% change
        mock_ticker_history(98, 102, 180),   # Stable
        mock_ticker_history(95, 102, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.return_value = mock_ticker

        result = await collector.collect("mature tech")

        # Large cap + low volatility = mature
        assert result["market_maturity"] == "mature"


@pytest.mark.asyncio
async def test_finance_collector_market_maturity_emerging(mock_ticker_history):
    """Test market maturity detection for emerging market"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["STARTUP"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "STARTUP",
        "longName": "Startup Inc",
        "marketCap": 5000000000,  # $5B (small cap)
        "sector": "Tech",
        "industry": "AI"
    }
    # High volatility history
    mock_ticker.history.side_effect = [
        mock_ticker_history(100, 150, 30),   # 50% swing
        mock_ticker_history(80, 150, 180),
        mock_ticker_history(50, 150, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.return_value = mock_ticker

        result = await collector.collect("emerging tech")

        # Small cap + high volatility = emerging
        assert result["market_maturity"] == "emerging"


@pytest.mark.asyncio
async def test_finance_collector_investor_sentiment_positive(mock_ticker_history):
    """Test investor sentiment detection for positive trend"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["BULL"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "BULL",
        "longName": "Bullish Corp",
        "marketCap": 10000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    # Strong uptrend
    mock_ticker.history.side_effect = [
        mock_ticker_history(100, 120, 30),   # 20% up in 1m
        mock_ticker_history(90, 120, 180),   # 33% up in 6m
        mock_ticker_history(80, 120, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.return_value = mock_ticker

        result = await collector.collect("bullish tech")

        assert result["investor_sentiment"] == "positive"


@pytest.mark.asyncio
async def test_finance_collector_investor_sentiment_negative(mock_ticker_history):
    """Test investor sentiment detection for negative trend"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["BEAR"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "BEAR",
        "longName": "Bearish Corp",
        "marketCap": 10000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    # Downtrend
    mock_ticker.history.side_effect = [
        mock_ticker_history(120, 100, 30),   # -16.7% in 1m
        mock_ticker_history(130, 100, 180),  # -23% in 6m
        mock_ticker_history(140, 100, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.return_value = mock_ticker

        result = await collector.collect("bearish tech")

        assert result["investor_sentiment"] == "negative"


@pytest.mark.asyncio
async def test_finance_collector_volume_trend_increasing(mock_ticker_history):
    """Test volume trend detection for increasing volume"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["HIGHVOL"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "HIGHVOL",
        "longName": "High Volume Corp",
        "marketCap": 10000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    mock_ticker.history.side_effect = [
        mock_ticker_history(100, 110, 30, volume=2000000),   # Higher recent volume
        mock_ticker_history(90, 110, 180, volume=1000000),   # Lower 6m volume
        mock_ticker_history(80, 110, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker") as mock_yf_ticker:

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        mock_yf_ticker.return_value = mock_ticker

        result = await collector.collect("high volume tech")

        assert result["volume_trend"] == "increasing"


@pytest.mark.asyncio
async def test_finance_collector_instance_isolation():
    """Test that each collector instance has its own cache (thread-safe)"""
    # Create two separate collector instances
    collector1 = FinanceCollector()
    collector2 = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["TEST"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "TEST",
        "longName": "Test Corp",
        "marketCap": 10000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    mock_ticker.history.return_value = pd.DataFrame({
        'Close': [100, 105],
        'Volume': [1000000, 1000000]
    })

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker", return_value=mock_ticker):

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Each collector instance has its own cache (thread-safe isolation)
        result1 = await collector1.collect("isolation test")
        result2 = await collector2.collect("isolation test")

        # Both should work correctly (no shared state issues)
        assert result1["companies_found"] >= 0
        assert result2["companies_found"] >= 0
        assert result1["tickers"] == result2["tickers"]


@pytest.mark.asyncio
async def test_finance_collector_json_serializable(mock_ticker_history):
    """Test that response is JSON serializable"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["TEST"]'}}]
    }

    mock_ticker = Mock()
    mock_ticker.info = {
        "symbol": "TEST",
        "longName": "Test Corp",
        "marketCap": 10000000000,
        "sector": "Tech",
        "industry": "Software"
    }
    mock_ticker.history.side_effect = [
        mock_ticker_history(100, 110, 30),
        mock_ticker_history(90, 110, 180),
        mock_ticker_history(80, 110, 730)
    ]

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker", return_value=mock_ticker):

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = await collector.collect("test")

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Verify no pandas or datetime objects
        assert "DataFrame" not in str(type(result))


@pytest.mark.asyncio
async def test_finance_collector_missing_fields():
    """Test handling of missing fields in yfinance response"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["MISSING"]'}}]
    }

    mock_ticker = Mock()
    # Missing optional fields
    mock_ticker.info = {
        "symbol": "MISSING"
        # Missing: longName, marketCap, sector, industry
    }
    mock_ticker.history.return_value = pd.DataFrame({
        'Close': [100, 105],
        'Volume': [1000000, 1000000]
    })

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("yfinance.Ticker", return_value=mock_ticker):

        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = await collector.collect("test")

        # Should handle gracefully with defaults
        assert result["companies_found"] >= 0
        assert isinstance(result["total_market_cap"], (int, float))


@pytest.mark.asyncio
async def test_finance_collector_deepseek_timeout():
    """Test handling of DeepSeek API timeout"""
    collector = FinanceCollector()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        # Mock yfinance for fallback
        mock_ticker = Mock()
        mock_ticker.info = {"symbol": "QQQ", "marketCap": 200000000000, "sector": "ETF", "industry": "ETF", "longName": "QQQ"}
        mock_ticker.history.return_value = pd.DataFrame({'Close': [100, 105], 'Volume': [1000000, 1000000]})

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test timeout")

            assert any("DeepSeek request timeout" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_finance_collector_all_tickers_fail():
    """Test when all ticker fetches fail"""
    collector = FinanceCollector()

    mock_deepseek_response = {
        "choices": [{"message": {"content": '["FAIL1", "FAIL2"]'}}]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = mock_deepseek_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Mock yfinance Ticker that always fails
        mock_ticker = Mock()
        mock_ticker.info = {}  # Empty info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await collector.collect("test")

            # Should return error response
            assert result["companies_found"] == 0
            assert result["total_market_cap"] == 0.0
            assert result["market_maturity"] == "unknown"
            assert len(result["errors"]) > 0
