"""
Unit tests for SocialCollector (Hacker News data collector).
Tests cover successful collection, error handling, and edge cases.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import httpx
import json

from app.collectors.social import SocialCollector


@pytest.mark.asyncio
async def test_social_collector_success():
    """Test successful data collection with typical API responses"""
    collector = SocialCollector()

    # Mock API responses for each time period
    mock_response_30d = {
        "hits": [
            {
                "title": "Quantum Computing Breakthrough",
                "points": 150,
                "num_comments": 75,
                "created_at_i": int(datetime.now().timestamp()) - 86400  # 1 day ago
            },
            {
                "title": "New Quantum Algorithm",
                "points": 120,
                "num_comments": 50,
                "created_at_i": int(datetime.now().timestamp()) - 172800  # 2 days ago
            }
        ],
        "nbHits": 45
    }

    mock_response_6m = {
        "hits": [
            {"points": 80, "num_comments": 30, "created_at_i": 1700000000},
            {"points": 90, "num_comments": 40, "created_at_i": 1700100000}
        ],
        "nbHits": 120
    }

    mock_response_1y = {
        "hits": [
            {"points": 60, "num_comments": 20, "created_at_i": 1690000000}
        ],
        "nbHits": 80
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure mock to return different responses for each call
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_30d), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_6m), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_1y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify structure
        assert result["source"] == "hacker_news"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify mention counts
        assert result["mentions_30d"] == 45
        assert result["mentions_6m"] == 120
        assert result["mentions_1y"] == 80
        assert result["mentions_total"] == 245

        # Verify engagement metrics
        assert result["avg_points_30d"] == 135.0  # (150 + 120) / 2
        assert result["avg_comments_30d"] == 62.5  # (75 + 50) / 2
        assert result["avg_points_6m"] == 85.0  # (80 + 90) / 2

        # Verify derived insights
        assert result["sentiment"] > 0  # Positive sentiment due to high points
        assert result["recency"] in ["high", "medium", "low"]
        assert result["growth_trend"] in ["increasing", "stable", "decreasing"]
        assert result["momentum"] in ["accelerating", "steady", "decelerating"]

        # Verify top stories
        assert len(result["top_stories"]) == 2
        assert result["top_stories"][0]["title"] == "Quantum Computing Breakthrough"
        assert result["top_stories"][0]["points"] == 150

        # Verify no errors
        assert result["errors"] == []

        # Verify JSON serializable
        json.dumps(result)  # Should not raise


@pytest.mark.asyncio
async def test_social_collector_rate_limit():
    """Test graceful handling of API rate limiting (429 error)"""
    collector = SocialCollector()

    mock_response = Mock()
    mock_response.status_code = 429

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited",
            request=Mock(),
            response=mock_response
        )

        result = await collector.collect("test keyword")

        # Should return error response, not raise exception
        assert result["source"] == "hacker_news"
        assert result["keyword"] == "test keyword"
        assert result["mentions_30d"] == 0
        assert "Rate limited" in result["errors"]
        assert result["recency"] == "unknown"
        assert result["growth_trend"] == "unknown"


@pytest.mark.asyncio
async def test_social_collector_timeout():
    """Test graceful handling of request timeout"""
    collector = SocialCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timeout")

        result = await collector.collect("test keyword")

        # Should return error response, not raise exception
        assert result["source"] == "hacker_news"
        assert result["mentions_30d"] == 0
        assert "Request timeout" in result["errors"]


@pytest.mark.asyncio
async def test_social_collector_network_error():
    """Test graceful handling of network errors"""
    collector = SocialCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        result = await collector.collect("test keyword")

        # Should return error response
        assert result["source"] == "hacker_news"
        assert result["mentions_30d"] == 0
        assert any("Network error" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_social_collector_zero_results():
    """Test handling of zero search results"""
    collector = SocialCollector()

    mock_response_empty = {
        "hits": [],
        "nbHits": 0
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock())
        ]

        result = await collector.collect("obscure_tech_xyz")

        # Should handle gracefully
        assert result["mentions_30d"] == 0
        assert result["mentions_total"] == 0
        assert result["avg_points_30d"] == 0.0
        assert result["avg_comments_30d"] == 0.0
        assert result["top_stories"] == []
        assert result["recency"] == "low"


@pytest.mark.asyncio
async def test_social_collector_partial_failure():
    """Test handling when some API calls succeed and others fail"""
    collector = SocialCollector()

    mock_response_success = {
        "hits": [
            {"points": 100, "num_comments": 50, "created_at_i": 1700000000, "title": "Test Story"}
        ],
        "nbHits": 25
    }

    mock_response_error = Mock()
    mock_response_error.status_code = 500

    with patch("httpx.AsyncClient.get") as mock_get:
        # First call succeeds, second and third fail
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_success), raise_for_status=Mock()),
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error),
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error)
        ]

        result = await collector.collect("test keyword")

        # Should return partial data
        assert result["mentions_30d"] == 25  # From successful first call
        assert result["mentions_6m"] == 0  # From failed second call
        assert result["mentions_1y"] == 0  # From failed third call
        assert len(result["errors"]) == 2  # Two HTTP 500 errors
        assert result["top_stories"][0]["title"] == "Test Story"


@pytest.mark.asyncio
async def test_social_collector_sentiment_calculation():
    """Test sentiment calculation from engagement metrics"""
    collector = SocialCollector()

    # Test high engagement (positive sentiment)
    mock_high_engagement = {
        "hits": [
            {"points": 200, "num_comments": 100, "created_at_i": 1700000000, "title": "Popular"}
        ],
        "nbHits": 10
    }

    # Test low engagement (negative sentiment)
    mock_low_engagement = {
        "hits": [
            {"points": 5, "num_comments": 2, "created_at_i": 1700000000, "title": "Unpopular"}
        ],
        "nbHits": 10
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        # Test positive sentiment
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_high_engagement), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock())
        ]

        result = await collector.collect("popular tech")
        assert result["sentiment"] > 0.5  # Should be positive

    with patch("httpx.AsyncClient.get") as mock_get:
        # Test negative sentiment
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_low_engagement), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock())
        ]

        result = await collector.collect("unpopular tech")
        assert result["sentiment"] < 0  # Should be negative


@pytest.mark.asyncio
async def test_social_collector_growth_trend_increasing():
    """Test detection of increasing growth trend"""
    collector = SocialCollector()

    # Recent period has much higher activity
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"hits": [], "nbHits": 100}), raise_for_status=Mock()),  # 30d
            Mock(json=Mock(return_value={"hits": [], "nbHits": 30}), raise_for_status=Mock()),   # 6m
            Mock(json=Mock(return_value={"hits": [], "nbHits": 20}), raise_for_status=Mock())    # 1y
        ]

        result = await collector.collect("growing tech")
        assert result["growth_trend"] == "increasing"


@pytest.mark.asyncio
async def test_social_collector_growth_trend_decreasing():
    """Test detection of decreasing growth trend"""
    collector = SocialCollector()

    # Recent period has much lower activity
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"hits": [], "nbHits": 10}), raise_for_status=Mock()),   # 30d
            Mock(json=Mock(return_value={"hits": [], "nbHits": 100}), raise_for_status=Mock()),  # 6m
            Mock(json=Mock(return_value={"hits": [], "nbHits": 80}), raise_for_status=Mock())    # 1y
        ]

        result = await collector.collect("declining tech")
        assert result["growth_trend"] == "decreasing"


@pytest.mark.asyncio
async def test_social_collector_json_serializable():
    """Test that all output is JSON serializable"""
    collector = SocialCollector()

    mock_response = {
        "hits": [
            {
                "title": "Test",
                "points": 100,
                "num_comments": 50,
                "created_at_i": int(datetime.now().timestamp())
            }
        ],
        "nbHits": 10
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 5}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 3}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should serialize without errors
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

        # Should deserialize back to equivalent structure
        deserialized = json.loads(serialized)
        assert deserialized["keyword"] == "test"
        assert deserialized["source"] == "hacker_news"


@pytest.mark.asyncio
async def test_social_collector_missing_fields_in_hits():
    """Test handling of API responses with missing optional fields"""
    collector = SocialCollector()

    # Response with missing points and num_comments
    mock_response_incomplete = {
        "hits": [
            {"title": "Story 1", "created_at_i": 1700000000},  # Missing points, comments
            {"title": "Story 2", "points": None, "num_comments": None, "created_at_i": 1700000000}
        ],
        "nbHits": 10
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_incomplete), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should handle missing fields gracefully
        assert result["avg_points_30d"] == 0.0
        assert result["avg_comments_30d"] == 0.0
        assert len(result["top_stories"]) == 2


@pytest.mark.asyncio
async def test_social_collector_recency_high():
    """Test high recency detection when most mentions are recent"""
    collector = SocialCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"hits": [], "nbHits": 100}), raise_for_status=Mock()),  # 30d
            Mock(json=Mock(return_value={"hits": [], "nbHits": 10}), raise_for_status=Mock()),   # 6m
            Mock(json=Mock(return_value={"hits": [], "nbHits": 5}), raise_for_status=Mock())     # 1y
        ]

        result = await collector.collect("recent tech")
        assert result["recency"] == "high"  # 100/115 = 87% in last 30 days


@pytest.mark.asyncio
async def test_social_collector_recency_low():
    """Test low recency detection when most mentions are historical"""
    collector = SocialCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"hits": [], "nbHits": 5}), raise_for_status=Mock()),    # 30d
            Mock(json=Mock(return_value={"hits": [], "nbHits": 50}), raise_for_status=Mock()),   # 6m
            Mock(json=Mock(return_value={"hits": [], "nbHits": 100}), raise_for_status=Mock())   # 1y
        ]

        result = await collector.collect("old tech")
        assert result["recency"] == "low"  # 5/155 = 3% in last 30 days


@pytest.mark.asyncio
async def test_social_collector_null_created_at_i():
    """Test handling of null created_at_i in top stories"""
    collector = SocialCollector()

    mock_response = {
        "hits": [
            {"title": "Story with null timestamp", "points": 50, "num_comments": 10, "created_at_i": None}
        ],
        "nbHits": 10
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"hits": [], "nbHits": 0}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should handle null timestamp gracefully
        assert len(result["top_stories"]) == 1
        assert result["top_stories"][0]["title"] == "Story with null timestamp"
        assert result["top_stories"][0]["age_days"] == 0  # Should default to current time
