"""
Unit tests for NewsCollector (GDELT news data collector).
Tests cover successful collection, error handling, and edge cases.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import httpx
import json

from app.collectors.news import NewsCollector


@pytest.mark.asyncio
async def test_news_collector_success():
    """Test successful data collection with typical GDELT API responses"""
    collector = NewsCollector()

    # Mock ArtList response for 30-day period
    mock_artlist_30d = {
        "articles": [
            {
                "url": "https://example.com/article1",
                "title": "Quantum Computing Breakthrough",
                "domain": "nature.com",
                "sourcecountry": "United States",
                "seendate": "20251127T120000Z"
            },
            {
                "url": "https://example.com/article2",
                "title": "New Quantum Algorithm",
                "domain": "sciencemag.org",
                "sourcecountry": "United Kingdom",
                "seendate": "20251126T100000Z"
            }
        ]
    }

    # Mock TimelineVol response
    mock_timeline_30d = {
        "timeline": [
            {
                "series": "Volume Intensity",
                "data": [
                    {"date": "20251127T120000Z", "value": 0.8},
                    {"date": "20251127T121500Z", "value": 0.6},
                    {"date": "20251127T123000Z", "value": 0.9}
                ]
            }
        ]
    }

    # Mock ToneChart response
    mock_tone_30d = {
        "tonechart": [
            {"bin": 8, "count": 30},  # Positive
            {"bin": 5, "count": 20},  # Neutral
            {"bin": 2, "count": 10}   # Negative
        ]
    }

    # Mock responses for 3-month period
    mock_artlist_3m = {
        "articles": [
            {
                "url": "https://example.com/article3",
                "title": "Quantum Research Advances",
                "domain": "reuters.com",
                "sourcecountry": "Germany",
                "seendate": "20251015T080000Z"
            }
        ]
    }

    mock_timeline_3m = {
        "timeline": [
            {
                "series": "Volume Intensity",
                "data": [
                    {"date": "20251015T080000Z", "value": 0.5},
                    {"date": "20251015T081500Z", "value": 0.4}
                ]
            }
        ]
    }

    mock_tone_3m = {
        "tonechart": [
            {"bin": 6, "count": 15},
            {"bin": 4, "count": 10}
        ]
    }

    # Mock responses for 1-year period
    mock_artlist_1y = {"articles": []}
    mock_timeline_1y = {"timeline": [{"series": "Volume Intensity", "data": []}]}
    mock_tone_1y = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure mock to return responses in order:
        # Period 1 (30d): artlist, timeline, tone
        # Period 2 (3m): artlist, timeline, tone
        # Period 3 (1y): artlist, timeline, tone
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist_30d), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_30d), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone_30d), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value=mock_artlist_3m), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_3m), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone_3m), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value=mock_artlist_1y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_1y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone_1y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify structure
        assert result["source"] == "gdelt"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify article counts
        assert result["articles_30d"] == 2
        assert result["articles_3m"] == 1
        assert result["articles_1y"] == 0
        assert result["articles_total"] == 3

        # Verify geographic distribution
        assert "United States" in result["source_countries"]
        assert "United Kingdom" in result["source_countries"]
        assert "Germany" in result["source_countries"]
        assert result["geographic_diversity"] == 3

        # Verify media diversity
        assert result["unique_domains"] == 3  # nature.com, sciencemag.org, reuters.com
        assert len(result["top_domains"]) > 0

        # Verify sentiment/tone
        assert result["avg_tone"] > 0  # Should be positive
        assert "positive" in result["tone_distribution"]
        assert "neutral" in result["tone_distribution"]
        assert "negative" in result["tone_distribution"]

        # Verify volume metrics
        assert result["volume_intensity_30d"] > 0
        assert result["volume_intensity_3m"] > 0

        # Verify derived insights
        assert result["media_attention"] in ["high", "medium", "low"]
        assert result["coverage_trend"] in ["increasing", "stable", "decreasing"]
        assert result["sentiment_trend"] in ["positive", "neutral", "negative"]
        assert result["mainstream_adoption"] in ["mainstream", "emerging", "niche"]

        # Verify top articles
        assert len(result["top_articles"]) == 2
        assert result["top_articles"][0]["title"] == "Quantum Computing Breakthrough"
        assert result["top_articles"][0]["domain"] == "nature.com"

        # Verify no errors
        assert result["errors"] == []

        # Verify JSON serializable
        json.dumps(result)


@pytest.mark.asyncio
async def test_news_collector_rate_limit():
    """Test graceful handling of API rate limiting (429 error)"""
    collector = NewsCollector()

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
        assert result["source"] == "gdelt"
        assert result["keyword"] == "test keyword"
        assert result["articles_30d"] == 0
        assert "Rate limited" in result["errors"]
        assert result["media_attention"] == "unknown"


@pytest.mark.asyncio
async def test_news_collector_timeout():
    """Test graceful handling of request timeout"""
    collector = NewsCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timeout")

        result = await collector.collect("test keyword")

        # Should return error response, not raise exception
        assert result["source"] == "gdelt"
        assert result["articles_30d"] == 0
        assert "Request timeout" in result["errors"]


@pytest.mark.asyncio
async def test_news_collector_network_error():
    """Test graceful handling of network errors"""
    collector = NewsCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        result = await collector.collect("test keyword")

        # Should return error response
        assert result["source"] == "gdelt"
        assert result["articles_30d"] == 0
        assert any("Network error" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_news_collector_zero_results():
    """Test handling of zero search results (obscure technology)"""
    collector = NewsCollector()

    mock_empty_artlist = {"articles": []}
    mock_empty_timeline = {"timeline": []}
    mock_empty_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        # All periods return empty results
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_empty_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value=mock_empty_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_tone), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value=mock_empty_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_empty_tone), raise_for_status=Mock())
        ]

        result = await collector.collect("obscure_tech_xyz")

        # Should handle gracefully
        assert result["articles_30d"] == 0
        assert result["articles_total"] == 0
        assert result["unique_domains"] == 0
        assert result["top_articles"] == []
        assert result["media_attention"] == "low"
        assert result["mainstream_adoption"] == "niche"


@pytest.mark.asyncio
async def test_news_collector_partial_failure():
    """Test handling when some API calls succeed and others fail"""
    collector = NewsCollector()

    mock_success_artlist = {
        "articles": [
            {
                "url": "https://example.com/article1",
                "title": "Test Article",
                "domain": "test.com",
                "sourcecountry": "United States",
                "seendate": "20251127T120000Z"
            }
        ]
    }
    mock_success_timeline = {"timeline": [{"series": "Volume Intensity", "data": [{"value": 0.7}]}]}
    mock_success_tone = {"tonechart": [{"bin": 7, "count": 10}]}

    mock_response_error = Mock()
    mock_response_error.status_code = 500

    with patch("httpx.AsyncClient.get") as mock_get:
        # First period succeeds, second and third periods fail
        mock_get.side_effect = [
            # 30-day period (success)
            Mock(json=Mock(return_value=mock_success_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_success_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_success_tone), raise_for_status=Mock()),
            # 3-month period (fail)
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error),
            # 1-year period (fail)
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error)
        ]

        result = await collector.collect("test keyword")

        # Should return partial data
        assert result["articles_30d"] == 1  # From successful first period
        assert result["articles_3m"] == 0   # From failed second period
        assert result["articles_1y"] == 0   # From failed third period
        assert len(result["errors"]) == 2   # Two HTTP 500 errors
        assert result["top_articles"][0]["title"] == "Test Article"


@pytest.mark.asyncio
async def test_news_collector_missing_fields():
    """Test handling of API responses with missing optional fields"""
    collector = NewsCollector()

    # Articles with missing fields
    mock_incomplete_artlist = {
        "articles": [
            {
                "url": "https://example.com/article1",
                "title": "Article 1"
                # Missing domain, sourcecountry, seendate
            },
            {
                "url": "https://example.com/article2",
                "title": "Article 2",
                "domain": None,
                "sourcecountry": None,
                "seendate": None
            }
        ]
    }

    mock_timeline = {"timeline": [{"series": "Volume Intensity", "data": [{"value": 0.5}]}]}
    mock_tone = {"tonechart": [{"bin": 5, "count": 10}]}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_incomplete_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should handle missing fields gracefully
        assert result["articles_30d"] == 2
        assert "Unknown" in result["source_countries"]  # Default for missing country
        assert len(result["top_articles"]) == 2


@pytest.mark.asyncio
async def test_news_collector_tone_calculation_all_positive():
    """Test tone calculation with all positive sentiment"""
    collector = NewsCollector()

    mock_artlist = {"articles": []}
    mock_timeline = {"timeline": []}
    mock_tone_positive = {
        "tonechart": [
            {"bin": 10, "count": 50},  # Most positive
            {"bin": 9, "count": 30},
            {"bin": 8, "count": 20}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone_positive), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("positive tech")

        # Should detect positive sentiment
        assert result["avg_tone"] > 0.5
        assert result["sentiment_trend"] == "positive"
        assert result["tone_distribution"]["positive"] == 100


@pytest.mark.asyncio
async def test_news_collector_tone_calculation_all_negative():
    """Test tone calculation with all negative sentiment"""
    collector = NewsCollector()

    mock_artlist = {"articles": []}
    mock_timeline = {"timeline": []}
    mock_tone_negative = {
        "tonechart": [
            {"bin": 0, "count": 40},  # Most negative
            {"bin": 1, "count": 30},
            {"bin": 2, "count": 20}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone_negative), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("negative tech")

        # Should detect negative sentiment
        assert result["avg_tone"] < -0.5
        assert result["sentiment_trend"] == "negative"
        assert result["tone_distribution"]["negative"] == 90


@pytest.mark.asyncio
async def test_news_collector_coverage_trend_increasing():
    """Test detection of increasing coverage trend"""
    collector = NewsCollector()

    mock_artlist = {"articles": []}

    # Recent period has high volume
    mock_timeline_30d = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 1.0}, {"value": 0.9}]}]
    }

    # Historical periods have low volume
    mock_timeline_3m = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 0.3}]}]
    }

    mock_timeline_1y = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 0.2}]}]
    }

    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_30d), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_3m), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_1y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock())
        ]

        result = await collector.collect("growing tech")
        assert result["coverage_trend"] == "increasing"


@pytest.mark.asyncio
async def test_news_collector_coverage_trend_decreasing():
    """Test detection of decreasing coverage trend"""
    collector = NewsCollector()

    mock_artlist = {"articles": []}

    # Recent period has low volume
    mock_timeline_30d = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 0.1}]}]
    }

    # Historical periods have high volume
    mock_timeline_3m = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 0.8}]}]
    }

    mock_timeline_1y = {
        "timeline": [{"series": "Volume Intensity", "data": [{"value": 0.9}]}]
    }

    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_30d), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_3m), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline_1y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock())
        ]

        result = await collector.collect("declining tech")
        assert result["coverage_trend"] == "decreasing"


@pytest.mark.asyncio
async def test_news_collector_geographic_diversity():
    """Test geographic diversity calculation"""
    collector = NewsCollector()

    mock_artlist = {
        "articles": [
            {"url": "https://example.com/1", "title": "Article 1", "sourcecountry": "United States", "domain": "test1.com"},
            {"url": "https://example.com/2", "title": "Article 2", "sourcecountry": "United Kingdom", "domain": "test2.com"},
            {"url": "https://example.com/3", "title": "Article 3", "sourcecountry": "Germany", "domain": "test3.com"},
            {"url": "https://example.com/4", "title": "Article 4", "sourcecountry": "China", "domain": "test4.com"},
            {"url": "https://example.com/5", "title": "Article 5", "sourcecountry": "Japan", "domain": "test5.com"}
        ]
    }

    mock_timeline = {"timeline": []}
    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("global tech")

        # Should capture all 5 countries
        assert result["geographic_diversity"] == 5
        assert "United States" in result["source_countries"]
        assert "China" in result["source_countries"]


@pytest.mark.asyncio
async def test_news_collector_mainstream_adoption_mainstream():
    """Test mainstream adoption detection with high domain diversity"""
    collector = NewsCollector()

    # Create articles from 60 different domains
    articles = [
        {
            "url": f"https://domain{i}.com/article",
            "title": f"Article {i}",
            "domain": f"domain{i}.com",
            "sourcecountry": "United States"
        }
        for i in range(60)
    ]

    mock_artlist = {"articles": articles}
    mock_timeline = {"timeline": []}
    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("mainstream tech")

        # Should classify as mainstream (60 domains, high diversity ratio)
        assert result["mainstream_adoption"] == "mainstream"
        assert result["unique_domains"] == 60


@pytest.mark.asyncio
async def test_news_collector_mainstream_adoption_niche():
    """Test niche adoption detection with low domain diversity"""
    collector = NewsCollector()

    # Only 2 articles from 2 domains
    mock_artlist = {
        "articles": [
            {
                "url": "https://domain1.com/article1",
                "title": "Article 1",
                "domain": "domain1.com",
                "sourcecountry": "United States"
            },
            {
                "url": "https://domain2.com/article2",
                "title": "Article 2",
                "domain": "domain2.com",
                "sourcecountry": "United States"
            }
        ]
    }

    mock_timeline = {"timeline": []}
    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("niche tech")

        # Should classify as niche (only 2 domains)
        assert result["mainstream_adoption"] == "niche"
        assert result["unique_domains"] == 2


@pytest.mark.asyncio
async def test_news_collector_json_serializable():
    """Test that all output is JSON serializable"""
    collector = NewsCollector()

    mock_artlist = {
        "articles": [
            {
                "url": "https://example.com/article",
                "title": "Test Article",
                "domain": "example.com",
                "sourcecountry": "United States",
                "seendate": "20251127T120000Z"
            }
        ]
    }

    mock_timeline = {"timeline": [{"series": "Volume Intensity", "data": [{"value": 0.5}]}]}
    mock_tone = {"tonechart": [{"bin": 5, "count": 10}]}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value={"articles": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"timeline": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"tonechart": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should serialize without errors
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

        # Should deserialize back to equivalent structure
        deserialized = json.loads(serialized)
        assert deserialized["keyword"] == "test"
        assert deserialized["source"] == "gdelt"


@pytest.mark.asyncio
async def test_news_collector_media_attention_high():
    """Test high media attention detection"""
    collector = NewsCollector()

    # Create 600 articles (should trigger "high" attention)
    articles = [{"url": f"https://domain.com/{i}", "title": f"Article {i}", "domain": "domain.com"} for i in range(200)]

    mock_artlist = {"articles": articles}
    mock_timeline = {"timeline": []}
    mock_tone = {"tonechart": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        # All three periods return 200 articles each (total 600)
        mock_get.side_effect = [
            # 30-day period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 3-month period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock()),
            # 1-year period
            Mock(json=Mock(return_value=mock_artlist), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_timeline), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_tone), raise_for_status=Mock())
        ]

        result = await collector.collect("popular tech")

        # Should classify as high media attention (600 total articles)
        assert result["media_attention"] == "high"
        assert result["articles_total"] == 600
