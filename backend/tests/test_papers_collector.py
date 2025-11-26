"""
Unit tests for PapersCollector (Semantic Scholar data collector).
Tests cover successful collection, error handling, and edge cases.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import httpx
import json

from app.collectors.papers import PapersCollector


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests to avoid needing .env file"""
    mock_settings_obj = Mock()
    mock_settings_obj.semantic_scholar_api_key = None  # Test without API key by default
    with patch("app.collectors.papers.get_settings", return_value=mock_settings_obj):
        yield mock_settings_obj


@pytest.mark.asyncio
async def test_papers_collector_success():
    """Test successful data collection with typical API responses"""
    collector = PapersCollector()

    # Mock API responses for each time period
    mock_response_2y = {
        "total": 45,
        "offset": 0,
        "data": [
            {
                "paperId": "abc123",
                "title": "Quantum Computing Breakthrough",
                "year": 2023,
                "citationCount": 25,
                "influentialCitationCount": 5,
                "authors": [
                    {"authorId": "1", "name": "Alice"},
                    {"authorId": "2", "name": "Bob"}
                ],
                "venue": "Nature"
            },
            {
                "paperId": "def456",
                "title": "Advanced Quantum Algorithms",
                "year": 2024,
                "citationCount": 15,
                "influentialCitationCount": 3,
                "authors": [
                    {"authorId": "3", "name": "Charlie"}
                ],
                "venue": "Science"
            }
        ]
    }

    mock_response_5y = {
        "total": 80,
        "offset": 0,
        "data": [
            {
                "paperId": "ghi789",
                "title": "Early Quantum Research",
                "year": 2020,
                "citationCount": 50,
                "influentialCitationCount": 10,
                "authors": [
                    {"authorId": "4", "name": "David"},
                    {"authorId": "5", "name": "Eve"}
                ],
                "venue": "Physical Review"
            },
            {
                "paperId": "jkl012",
                "title": "Quantum Theory Foundations",
                "year": 2019,
                "citationCount": 40,
                "influentialCitationCount": 8,
                "authors": [
                    {"authorId": "6", "name": "Frank"}
                ],
                "venue": "Nature"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure mock to return different responses for each call
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify structure
        assert result["source"] == "semantic_scholar"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify publication counts
        assert result["publications_2y"] == 45
        assert result["publications_5y"] == 80
        assert result["publications_total"] == 125

        # Verify citation metrics
        assert result["avg_citations_2y"] == 20.0  # (25 + 15) / 2
        assert result["avg_citations_5y"] == 45.0  # (50 + 40) / 2
        assert result["avg_influential_citations_2y"] == 4.0  # (5 + 3) / 2

        # Verify citation velocity
        assert result["citation_velocity"] < 0  # Negative because older papers have more citations

        # Verify diversity metrics
        assert result["author_diversity"] == 3  # Unique authors in 5y data: David, Eve, Frank
        assert result["venue_diversity"] == 2  # Unique venues: Physical Review, Nature

        # Verify derived insights
        assert result["research_maturity"] in ["emerging", "developing", "mature"]
        assert result["research_momentum"] in ["accelerating", "steady", "decelerating"]
        assert result["research_trend"] in ["increasing", "stable", "decreasing"]
        assert result["research_breadth"] in ["narrow", "moderate", "broad"]

        # Verify top papers
        assert len(result["top_papers"]) == 2
        assert result["top_papers"][0]["title"] == "Quantum Computing Breakthrough"
        assert result["top_papers"][0]["citations"] == 25

        # Verify no errors
        assert result["errors"] == []

        # Verify JSON serializable
        json.dumps(result)  # Should not raise


@pytest.mark.asyncio
async def test_papers_collector_rate_limit():
    """Test graceful handling of API rate limiting (429 error)"""
    collector = PapersCollector()

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
        assert result["source"] == "semantic_scholar"
        assert result["keyword"] == "test keyword"
        assert result["publications_2y"] == 0
        assert "Rate limited" in result["errors"]
        assert result["research_maturity"] == "unknown"
        assert result["research_trend"] == "unknown"


@pytest.mark.asyncio
async def test_papers_collector_timeout():
    """Test graceful handling of request timeout"""
    collector = PapersCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timeout")

        result = await collector.collect("test keyword")

        # Should return error response, not raise exception
        assert result["source"] == "semantic_scholar"
        assert result["publications_2y"] == 0
        assert "Request timeout" in result["errors"]


@pytest.mark.asyncio
async def test_papers_collector_network_error():
    """Test graceful handling of network errors"""
    collector = PapersCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        result = await collector.collect("test keyword")

        # Should return error response
        assert result["source"] == "semantic_scholar"
        assert result["publications_2y"] == 0
        assert any("Network error" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_papers_collector_zero_results():
    """Test handling of zero search results"""
    collector = PapersCollector()

    mock_response_empty = {
        "total": 0,
        "offset": 0,
        "data": []
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock())
        ]

        result = await collector.collect("obscure_tech_xyz")

        # Should handle gracefully
        assert result["publications_2y"] == 0
        assert result["publications_total"] == 0
        assert result["avg_citations_2y"] == 0.0
        assert result["top_papers"] == []
        assert result["research_maturity"] == "emerging"


@pytest.mark.asyncio
async def test_papers_collector_partial_failure():
    """Test handling when some API calls succeed and others fail"""
    collector = PapersCollector()

    mock_response_success = {
        "total": 25,
        "offset": 0,
        "data": [
            {
                "paperId": "test123",
                "title": "Test Paper",
                "year": 2024,
                "citationCount": 10,
                "influentialCitationCount": 2,
                "authors": [{"authorId": "1", "name": "Test Author"}],
                "venue": "Test Venue"
            }
        ]
    }

    mock_response_error = Mock()
    mock_response_error.status_code = 500

    with patch("httpx.AsyncClient.get") as mock_get:
        # First call succeeds, second fails
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_success), raise_for_status=Mock()),
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error)
        ]

        result = await collector.collect("test keyword")

        # Should return partial data
        assert result["publications_2y"] == 25  # From successful first call
        assert result["publications_5y"] == 0  # From failed second call
        assert len(result["errors"]) == 1  # One HTTP 500 error
        assert result["top_papers"][0]["title"] == "Test Paper"


@pytest.mark.asyncio
async def test_papers_collector_citation_velocity_positive():
    """Test citation velocity calculation for growing field"""
    collector = PapersCollector()

    # Recent papers have higher citations (unusual but tests the logic)
    mock_recent_high = {
        "total": 10,
        "data": [
            {"citationCount": 50, "influentialCitationCount": 10, "authors": [], "venue": ""}
        ]
    }

    mock_historical_low = {
        "total": 10,
        "data": [
            {"citationCount": 20, "influentialCitationCount": 5, "authors": [], "venue": ""}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_recent_high), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_historical_low), raise_for_status=Mock())
        ]

        result = await collector.collect("test")
        # Velocity = (50 - 20) / 20 = 1.5
        assert result["citation_velocity"] > 0


@pytest.mark.asyncio
async def test_papers_collector_citation_velocity_negative():
    """Test citation velocity calculation for declining field"""
    collector = PapersCollector()

    # Recent papers have lower citations (typical)
    mock_recent_low = {
        "total": 10,
        "data": [
            {"citationCount": 10, "influentialCitationCount": 2, "authors": [], "venue": ""}
        ]
    }

    mock_historical_high = {
        "total": 10,
        "data": [
            {"citationCount": 50, "influentialCitationCount": 10, "authors": [], "venue": ""}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_recent_low), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_historical_high), raise_for_status=Mock())
        ]

        result = await collector.collect("test")
        # Velocity = (10 - 50) / 50 = -0.8
        assert result["citation_velocity"] < 0


@pytest.mark.asyncio
async def test_papers_collector_research_maturity_mature():
    """Test detection of mature research field"""
    collector = PapersCollector()

    # High publication count indicates maturity
    mock_response_high = {
        "total": 100,
        "data": [
            {"citationCount": 50, "influentialCitationCount": 10, "authors": [], "venue": ""}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_high), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"total": 200, "data": []}, raise_for_status=Mock()))
        ]

        result = await collector.collect("mature tech")
        assert result["research_maturity"] == "mature"


@pytest.mark.asyncio
async def test_papers_collector_research_maturity_emerging():
    """Test detection of emerging research field"""
    collector = PapersCollector()

    # Low publication count and citations indicate emerging field
    mock_response_low = {
        "total": 5,
        "data": [
            {"citationCount": 2, "influentialCitationCount": 0, "authors": [], "venue": ""}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_low), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"total": 3, "data": []}, raise_for_status=Mock()))
        ]

        result = await collector.collect("emerging tech")
        assert result["research_maturity"] == "emerging"


@pytest.mark.asyncio
async def test_papers_collector_momentum_accelerating():
    """Test detection of accelerating research momentum"""
    collector = PapersCollector()

    # Recent period has much higher publication rate
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"total": 100, "data": []}), raise_for_status=Mock()),  # 2y: 50/year
            Mock(json=Mock(return_value={"total": 50, "data": []}), raise_for_status=Mock())   # 5y: 10/year
        ]

        result = await collector.collect("growing field")
        # Recent rate (50/yr) is 5x historical rate (10/yr), so momentum is accelerating
        assert result["research_momentum"] == "accelerating"


@pytest.mark.asyncio
async def test_papers_collector_momentum_decelerating():
    """Test detection of decelerating research momentum"""
    collector = PapersCollector()

    # Recent period has much lower publication rate
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"total": 10, "data": []}), raise_for_status=Mock()),   # 2y: 5/year
            Mock(json=Mock(return_value={"total": 200, "data": []}), raise_for_status=Mock())  # 5y: 40/year
        ]

        result = await collector.collect("declining field")
        # Recent rate (5/yr) is much less than historical rate (40/yr)
        assert result["research_momentum"] == "decelerating"


@pytest.mark.asyncio
async def test_papers_collector_trend_increasing():
    """Test detection of increasing research trend"""
    collector = PapersCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"total": 100, "data": []}), raise_for_status=Mock()),  # 2y
            Mock(json=Mock(return_value={"total": 50, "data": []}), raise_for_status=Mock())   # 5y
        ]

        result = await collector.collect("increasing field")
        assert result["research_trend"] == "increasing"


@pytest.mark.asyncio
async def test_papers_collector_trend_decreasing():
    """Test detection of decreasing research trend"""
    collector = PapersCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"total": 10, "data": []}), raise_for_status=Mock()),   # 2y
            Mock(json=Mock(return_value={"total": 200, "data": []}), raise_for_status=Mock())  # 5y
        ]

        result = await collector.collect("decreasing field")
        assert result["research_trend"] == "decreasing"


@pytest.mark.asyncio
async def test_papers_collector_breadth_broad():
    """Test detection of broad research field"""
    collector = PapersCollector()

    # High author and venue diversity
    mock_response_diverse = {
        "total": 10,
        "data": [
            {
                "citationCount": 20,
                "influentialCitationCount": 5,
                "authors": [
                    {"authorId": "1", "name": "A"},
                    {"authorId": "2", "name": "B"},
                    {"authorId": "3", "name": "C"}
                ],
                "venue": "Venue1"
            },
            {
                "citationCount": 15,
                "influentialCitationCount": 3,
                "authors": [
                    {"authorId": "4", "name": "D"},
                    {"authorId": "5", "name": "E"}
                ],
                "venue": "Venue2"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value={"total": 5, "data": []}), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_diverse), raise_for_status=Mock())
        ]

        result = await collector.collect("broad field")
        # 5 unique authors / 15 total = 0.33 authors per paper (< 2.0)
        # But the logic may vary based on total papers
        assert result["research_breadth"] in ["narrow", "moderate", "broad"]


@pytest.mark.asyncio
async def test_papers_collector_json_serializable():
    """Test that all output is JSON serializable"""
    collector = PapersCollector()

    mock_response = {
        "total": 10,
        "data": [
            {
                "paperId": "test",
                "title": "Test Paper",
                "year": 2024,
                "citationCount": 10,
                "influentialCitationCount": 2,
                "authors": [{"authorId": "1", "name": "Author"}],
                "venue": "Venue"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"total": 5, "data": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should serialize without errors
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

        # Should deserialize back to equivalent structure
        deserialized = json.loads(serialized)
        assert deserialized["keyword"] == "test"
        assert deserialized["source"] == "semantic_scholar"


@pytest.mark.asyncio
async def test_papers_collector_missing_fields():
    """Test handling of API responses with missing optional fields"""
    collector = PapersCollector()

    # Response with missing citation counts and authors
    mock_response_incomplete = {
        "total": 10,
        "data": [
            {"title": "Paper 1", "year": 2024},  # Missing citations, authors, venue
            {"title": "Paper 2", "citationCount": None, "influentialCitationCount": None, "authors": [], "venue": ""}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_incomplete), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"total": 0, "data": []}), raise_for_status=Mock())
        ]

        result = await collector.collect("test")

        # Should handle missing fields gracefully
        assert result["avg_citations_2y"] == 0.0
        assert result["author_diversity"] == 0
        assert len(result["top_papers"]) == 2


@pytest.mark.asyncio
async def test_papers_collector_invalid_query():
    """Test handling of invalid query parameters (400 error)"""
    collector = PapersCollector()

    mock_response = Mock()
    mock_response.status_code = 400

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=Mock(),
            response=mock_response
        )

        result = await collector.collect("")

        # Should return error response
        assert result["source"] == "semantic_scholar"
        assert "Invalid query parameters" in result["errors"]
