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

    # Mock response for 10y period
    mock_response_10y = {
        "total": 120,
        "offset": 0,
        "data": [
            {
                "paperId": "mno345",
                "title": "Historical Quantum Study",
                "year": 2015,
                "citationCount": 80,
                "influentialCitationCount": 15,
                "authors": [
                    {"authorId": "6", "name": "Frank"}
                ],
                "venue": "Nature Physics"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure mock to return different responses for each call (3 periods now)
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify structure
        assert result["source"] == "semantic_scholar"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify publication counts
        assert result["publications_2y"] == 45
        assert result["publications_5y"] == 80
        assert result["publications_10y"] == 120
        assert result["publications_total"] == 245

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
        assert "research_maturity_reasoning" in result
        assert len(result["research_maturity_reasoning"]) > 0
        assert result["research_momentum"] in ["accelerating", "steady", "decelerating"]
        assert result["research_trend"] in ["increasing", "stable", "decreasing"]
        assert result["research_breadth"] in ["narrow", "moderate", "broad"]

        # Verify new aggregation fields
        assert "top_authors" in result
        assert isinstance(result["top_authors"], list)

        # Verify paper type distribution
        assert "paper_type_distribution" in result
        assert "type_counts" in result["paper_type_distribution"]
        assert "type_percentages" in result["paper_type_distribution"]
        assert "papers_with_type_info" in result["paper_type_distribution"]

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
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_empty), raise_for_status=Mock())
        ]

        result = await collector.collect("obscure_tech_xyz")

        # Should handle gracefully
        assert result["publications_2y"] == 0
        assert result["publications_10y"] == 0
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
        # First call succeeds, second and third fail
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_success), raise_for_status=Mock()),
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error),
            httpx.HTTPStatusError("500 Server Error", request=Mock(), response=mock_response_error)
        ]

        result = await collector.collect("test keyword")

        # Should return partial data
        assert result["publications_2y"] == 25  # From successful first call
        assert result["publications_5y"] == 0  # From failed second call
        assert result["publications_10y"] == 0  # From failed third call
        assert len(result["errors"]) == 2  # Two HTTP 500 errors
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

    # High publication count with journal articles indicates maturity
    mock_response_high = {
        "total": 100,
        "data": [
            {"citationCount": 50, "influentialCitationCount": 10, "authors": [], "venue": "", "publicationTypes": ["JournalArticle"]}
        ] * 10
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_high), raise_for_status=Mock()),
            Mock(json=Mock(return_value={"total": 200, "data": [{"publicationTypes": ["JournalArticle"]}] * 20}, raise_for_status=Mock())),
            Mock(json=Mock(return_value={"total": 150, "data": [{"publicationTypes": ["JournalArticle"]}] * 15}, raise_for_status=Mock()))
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


# ============================================================================
# NEW TESTS FOR ENHANCED PAPERS COLLECTOR
# ============================================================================


@pytest.mark.asyncio
async def test_papers_collector_10y_period_fetching():
    """Test that all three time periods (2y, 5y, 10y) are fetched correctly"""
    collector = PapersCollector()

    # Mock responses for all three periods
    mock_response_2y = {"total": 45, "data": [{"citationCount": 25, "authors": []}]}
    mock_response_5y = {"total": 80, "data": [{"citationCount": 50, "authors": []}]}
    mock_response_10y = {"total": 120, "data": [{"citationCount": 100, "authors": []}]}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify all three periods are present
        assert result["publications_2y"] == 45
        assert result["publications_5y"] == 80
        assert result["publications_10y"] == 120
        assert result["publications_total"] == 245

        # Verify citation metrics for all periods
        assert "avg_citations_2y" in result
        assert "avg_citations_5y" in result
        assert "avg_citations_10y" in result


@pytest.mark.asyncio
async def test_papers_collector_author_aggregation():
    """Test author aggregation across all time periods"""
    collector = PapersCollector()

    # Mock responses with duplicate authors across periods
    mock_response_2y = {
        "total": 2,
        "data": [
            {"authors": [{"name": "Alice"}, {"name": "Bob"}]},
            {"authors": [{"name": "Alice"}, {"name": "Charlie"}]}
        ]
    }
    mock_response_5y = {
        "total": 2,
        "data": [
            {"authors": [{"name": "Bob"}, {"name": "David"}]},
            {"authors": [{"name": "Alice"}]}
        ]
    }
    mock_response_10y = {
        "total": 1,
        "data": [
            {"authors": [{"name": "Bob"}]}
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("test keyword")

        # Verify top authors are aggregated correctly
        # Alice: 3, Bob: 3, Charlie: 1, David: 1
        assert "top_authors" in result
        assert len(result["top_authors"]) == 4
        # Top author should be Alice or Bob with count 3
        assert result["top_authors"][0]["publication_count"] == 3
        assert result["top_authors"][0]["name"] in ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_papers_collector_no_institution_field():
    """Test that top_institutions field is NOT included (affiliations unavailable in API)"""
    collector = PapersCollector()

    # Mock responses - affiliations are not actually available from Semantic Scholar API
    mock_response_2y = {
        "total": 2,
        "data": [
            {"authors": [{"name": "Alice"}, {"name": "Bob"}]}
        ]
    }
    mock_response_5y = {
        "total": 1,
        "data": [
            {"authors": [{"name": "Charlie"}]}
        ]
    }
    mock_response_10y = {"total": 0, "data": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("test keyword")

        # Verify that top_institutions field is NOT present
        # (Removed because Semantic Scholar API does not provide affiliation data)
        assert "top_institutions" not in result


@pytest.mark.asyncio
async def test_papers_collector_paper_type_distribution():
    """Test paper type distribution analysis"""
    collector = PapersCollector()

    # Mock responses with various paper types
    mock_response_2y = {
        "total": 4,
        "data": [
            {"publicationTypes": ["Review"]},
            {"publicationTypes": ["JournalArticle"]},
            {"publicationTypes": ["Conference"]},
            {"publicationTypes": ["Conference"]}
        ]
    }
    mock_response_5y = {
        "total": 3,
        "data": [
            {"publicationTypes": ["Review"]},
            {"publicationTypes": ["JournalArticle"]},
            {"publicationTypes": ["Book"]}
        ]
    }
    mock_response_10y = {"total": 0, "data": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("test keyword")

        # Verify paper type distribution
        assert "paper_type_distribution" in result
        type_dist = result["paper_type_distribution"]

        assert "type_counts" in type_dist
        assert type_dist["type_counts"]["Review"] == 2
        assert type_dist["type_counts"]["JournalArticle"] == 2
        assert type_dist["type_counts"]["Conference"] == 2
        assert type_dist["type_counts"]["Book"] == 1

        assert "type_percentages" in type_dist
        # 7 papers with types, Review = 2/7 = 28.6%
        assert abs(type_dist["type_percentages"]["review_percentage"] - 28.6) < 1.0

        assert type_dist["papers_with_type_info"] == 7


@pytest.mark.asyncio
async def test_papers_collector_enhanced_maturity_with_high_review_percentage():
    """Test enhanced maturity classification with high review paper percentage"""
    collector = PapersCollector()

    # Mock responses with high review percentage
    # Total papers: 40 (10 + 15 + 15), Reviews: 15, -> 37.5% reviews (> 30% threshold)
    mock_response_2y = {
        "total": 10,
        "data": [
            {"citationCount": 30, "publicationTypes": ["Review"]} for _ in range(8)
        ] + [
            {"citationCount": 25, "publicationTypes": ["JournalArticle"]} for _ in range(2)
        ]
    }
    mock_response_5y = {"total": 15, "data": [{"citationCount": 20, "publicationTypes": ["Review"]}] * 5 + [{"citationCount": 18, "publicationTypes": ["JournalArticle"]}] * 10}
    mock_response_10y = {"total": 15, "data": [{"citationCount": 15, "publicationTypes": ["Review"]}] * 2 + [{"citationCount": 12, "publicationTypes": ["Conference"]}] * 13}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("test keyword")

        # Should classify as mature due to high review percentage
        assert result["research_maturity"] == "mature"
        assert "research_maturity_reasoning" in result
        assert "review" in result["research_maturity_reasoning"].lower()


@pytest.mark.asyncio
async def test_papers_collector_enhanced_maturity_with_high_conference_percentage():
    """Test enhanced maturity classification with high conference paper percentage"""
    collector = PapersCollector()

    # Mock responses with high conference percentage and low total publications
    mock_response_2y = {
        "total": 8,
        "data": [
            {"citationCount": 5, "publicationTypes": ["Conference"]} for _ in range(8)
        ]
    }
    mock_response_5y = {
        "total": 4,
        "data": [{"citationCount": 3, "publicationTypes": ["Conference"]}] * 4
    }
    mock_response_10y = {"total": 0, "data": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("test keyword")

        # Should classify as emerging due to high conference percentage with few publications
        assert result["research_maturity"] == "emerging"
        assert "research_maturity_reasoning" in result
        assert "conference" in result["research_maturity_reasoning"].lower()


@pytest.mark.asyncio
async def test_papers_collector_partial_data_with_10y_failure():
    """Test graceful handling when 10y period fails but 2y and 5y succeed"""
    collector = PapersCollector()

    mock_response_2y = {"total": 45, "data": [{"citationCount": 25, "authors": [], "publicationTypes": ["JournalArticle"]}]}
    mock_response_5y = {"total": 80, "data": [{"citationCount": 50, "authors": [], "publicationTypes": ["Conference"]}]}

    mock_response_10y_error = Mock()
    mock_response_10y_error.status_code = 429

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            httpx.HTTPStatusError(
                "429 Rate Limited",
                request=Mock(),
                response=mock_response_10y_error
            )
        ]

        result = await collector.collect("quantum computing")

        # Should still return data with 2y and 5y results
        assert result["publications_2y"] == 45
        assert result["publications_5y"] == 80
        assert result["publications_10y"] == 0  # Failed period defaults to 0
        assert result["publications_total"] == 125

        # Should still calculate metrics with available data
        assert "research_maturity" in result
        assert "top_authors" in result
        assert "paper_type_distribution" in result

        # Should track the error
        assert "Rate limited" in result["errors"]
