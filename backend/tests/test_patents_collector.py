"""
Tests for PatentsCollector.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.collectors.patents import PatentsCollector


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests to avoid needing .env file"""
    mock_settings_obj = Mock()
    mock_settings_obj.patentsview_api_key = "test_api_key_12345"
    with patch("app.collectors.patents.get_settings", return_value=mock_settings_obj):
        yield mock_settings_obj


@pytest.mark.asyncio
async def test_patents_collector_success():
    """Test successful patent data collection"""
    collector = PatentsCollector()

    # Mock response for 2y period
    mock_response_2y = {
        "error": False,
        "count": 3,
        "total_hits": 45,
        "patents": [
            {
                "patent_id": "11123456",
                "patent_title": "Method for Quantum Computing Error Correction",
                "patent_date": "2023-09-15",
                "patent_year": "2023",
                "assignees": [
                    {
                        "assignee_organization": "IBM",
                        "assignee_country": "US"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "25"
            },
            {
                "patent_id": "11123457",
                "patent_title": "Quantum Computing Device",
                "patent_date": "2023-08-10",
                "patent_year": "2023",
                "assignees": [
                    {
                        "assignee_organization": "Google LLC",
                        "assignee_country": "US"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "15"
            },
            {
                "patent_id": "11123458",
                "patent_title": "Quantum Algorithm Optimization",
                "patent_date": "2024-01-20",
                "patent_year": "2024",
                "assignees": [
                    {
                        "assignee_organization": "Microsoft",
                        "assignee_country": "US"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "10"
            }
        ]
    }

    # Mock response for 5y period
    mock_response_5y = {
        "error": False,
        "count": 3,
        "total_hits": 120,
        "patents": [
            {
                "patent_id": "10123456",
                "patent_title": "Quantum Computing System",
                "patent_date": "2020-05-15",
                "patent_year": "2020",
                "assignees": [
                    {
                        "assignee_organization": "Intel",
                        "assignee_country": "US"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "30"
            },
            {
                "patent_id": "10123457",
                "patent_title": "Quantum Gate Implementation",
                "patent_date": "2021-03-10",
                "patent_year": "2021",
                "assignees": [
                    {
                        "assignee_organization": "Alibaba",
                        "assignee_country": "CN"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "20"
            },
            {
                "patent_id": "10123458",
                "patent_title": "Quantum Circuit Design",
                "patent_date": "2021-11-20",
                "patent_year": "2021",
                "assignees": [
                    {
                        "assignee_organization": "IBM",
                        "assignee_country": "US"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "18"
            }
        ]
    }

    # Mock response for 10y period
    mock_response_10y = {
        "error": False,
        "count": 2,
        "total_hits": 200,
        "patents": [
            {
                "patent_id": "9123456",
                "patent_title": "Quantum Information Processing",
                "patent_date": "2015-08-15",
                "patent_year": "2015",
                "assignees": [
                    {
                        "assignee_organization": "NTT",
                        "assignee_country": "JP"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "50"
            },
            {
                "patent_id": "9123457",
                "patent_title": "Quantum State Measurement",
                "patent_date": "2016-12-10",
                "patent_year": "2016",
                "assignees": [
                    {
                        "assignee_organization": "Samsung",
                        "assignee_country": "KR"
                    }
                ],
                "patent_num_times_cited_by_us_patents": "40"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
            Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
        ]

        result = await collector.collect("quantum computing")

        # Verify basic structure
        assert result["source"] == "patentsview"
        assert result["keyword"] == "quantum computing"
        assert "collected_at" in result

        # Verify patent counts
        assert result["patents_2y"] == 45
        assert result["patents_5y"] == 120
        assert result["patents_10y"] == 200
        assert result["patents_total"] == 365

        # Verify assignee metrics
        assert result["unique_assignees"] == 7  # IBM, Google LLC, Microsoft, Intel, Alibaba, NTT, Samsung
        assert len(result["top_assignees"]) <= 5

        # Verify geographic metrics
        assert "US" in result["countries"]
        assert result["geographic_diversity"] >= 3  # US, CN, JP, KR

        # Verify citation metrics
        assert result["avg_citations_2y"] > 0
        assert result["avg_citations_5y"] > 0

        # Verify derived insights
        assert result["filing_velocity"] != 0
        assert result["assignee_concentration"] in ["concentrated", "moderate", "diverse"]
        assert result["geographic_reach"] in ["domestic", "regional", "global"]
        assert result["patent_maturity"] in ["emerging", "developing", "mature"]
        assert result["patent_momentum"] in ["accelerating", "steady", "decelerating"]
        assert result["patent_trend"] in ["increasing", "stable", "decreasing"]

        # Verify top patents
        assert len(result["top_patents"]) > 0
        assert result["top_patents"][0]["citations"] >= result["top_patents"][-1]["citations"]

        # Verify no errors
        assert result["errors"] == []

        # Verify API was called with correct parameters
        assert mock_get.call_count == 3
        for call in mock_get.call_args_list:
            args, kwargs = call
            assert "headers" in kwargs
            assert kwargs["headers"]["X-Api-Key"] == "test_api_key_12345"


@pytest.mark.asyncio
async def test_patents_collector_rate_limit():
    """Test handling of rate limit (429) errors"""
    collector = PatentsCollector()

    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(raise_for_status=Mock(side_effect=__import__('httpx').HTTPStatusError(
                "Rate limited", request=Mock(), response=mock_response
            ))),
            Mock(raise_for_status=Mock(side_effect=__import__('httpx').HTTPStatusError(
                "Rate limited", request=Mock(), response=mock_response
            ))),
            Mock(raise_for_status=Mock(side_effect=__import__('httpx').HTTPStatusError(
                "Rate limited", request=Mock(), response=mock_response
            )))
        ]

        result = await collector.collect("quantum computing")

        # Should return error response with all zeros
        assert result["source"] == "patentsview"
        assert result["patents_total"] == 0
        assert len(result["errors"]) > 0
        assert any("Rate limited" in err for err in result["errors"])
        assert any("60" in err for err in result["errors"])  # Retry-After value


@pytest.mark.asyncio
async def test_patents_collector_timeout():
    """Test handling of timeout errors"""
    collector = PatentsCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = __import__('httpx').TimeoutException("Request timeout")

        result = await collector.collect("quantum computing")

        assert result["source"] == "patentsview"
        assert result["patents_total"] == 0
        assert len(result["errors"]) > 0
        assert any("timeout" in err.lower() for err in result["errors"])


@pytest.mark.asyncio
async def test_patents_collector_network_error():
    """Test handling of network errors"""
    collector = PatentsCollector()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = __import__('httpx').ConnectError("Network error")

        result = await collector.collect("quantum computing")

        assert result["source"] == "patentsview"
        assert result["patents_total"] == 0
        assert len(result["errors"]) > 0
        assert any("Network error" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_patents_collector_zero_results():
    """Test handling of zero results from API"""
    collector = PatentsCollector()

    mock_response = {
        "error": False,
        "count": 0,
        "total_hits": 0,
        "patents": []
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Mock(
            json=Mock(return_value=mock_response),
            raise_for_status=Mock()
        )

        result = await collector.collect("nonexistent technology xyz")

        assert result["source"] == "patentsview"
        assert result["patents_total"] == 0
        assert result["unique_assignees"] == 0
        assert result["geographic_diversity"] == 0
        assert len(result["top_patents"]) == 0
        assert result["errors"] == []


@pytest.mark.asyncio
async def test_patents_collector_partial_failure():
    """Test handling when some API calls succeed and others fail"""
    collector = PatentsCollector()

    mock_response_2y = {
        "error": False,
        "count": 1,
        "total_hits": 45,
        "patents": [
            {
                "patent_id": "11123456",
                "patent_title": "Test Patent",
                "patent_date": "2023-09-15",
                "patent_year": "2023",
                "assignees": [{"assignee_organization": "IBM", "assignee_country": "US"}],
                "patent_num_times_cited_by_us_patents": "25"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = [
            Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
            Mock(raise_for_status=Mock(side_effect=__import__('httpx').TimeoutException("Timeout"))),
            Mock(raise_for_status=Mock(side_effect=__import__('httpx').TimeoutException("Timeout")))
        ]

        result = await collector.collect("quantum computing")

        # Should still return data from successful call
        assert result["patents_2y"] == 45
        assert result["patents_5y"] == 0
        assert result["patents_10y"] == 0
        assert result["patents_total"] == 45
        assert len(result["errors"]) == 2  # Two timeouts


@pytest.mark.asyncio
async def test_patents_collector_missing_fields():
    """Test handling of missing fields in API response"""
    collector = PatentsCollector()

    mock_response = {
        "error": False,
        "count": 2,
        "total_hits": 10,
        "patents": [
            {
                "patent_id": "11123456",
                "patent_title": "Test Patent 1",
                "patent_date": "2023-09-15",
                # Missing assignees
                # Missing patent_num_times_cited_by_us_patents
            },
            {
                "patent_id": "11123457",
                "patent_title": "Test Patent 2",
                "patent_date": "2023-08-10",
                "assignees": [],  # Empty assignees
                "patent_num_times_cited_by_us_patents": None  # Null citation count
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Mock(
            json=Mock(return_value=mock_response),
            raise_for_status=Mock()
        )

        # Should not raise KeyError or TypeError
        result = await collector.collect("quantum computing")

        assert result["source"] == "patentsview"
        assert result["patents_total"] >= 0
        assert result["errors"] == []


@pytest.mark.asyncio
async def test_filing_velocity_positive():
    """Test filing velocity calculation with accelerating patent rate"""
    collector = PatentsCollector()

    # Recent rate higher than historical
    velocity = collector._calculate_filing_velocity(patents_2y=100, patents_5y=150)

    # Recent: 100/2 = 50 per year
    # Historical: 150/5 = 30 per year
    # Velocity: (50-30)/30 = 0.667
    assert velocity > 0
    assert abs(velocity - 0.667) < 0.01


@pytest.mark.asyncio
async def test_filing_velocity_negative():
    """Test filing velocity calculation with decelerating patent rate"""
    collector = PatentsCollector()

    # Recent rate lower than historical
    velocity = collector._calculate_filing_velocity(patents_2y=40, patents_5y=150)

    # Recent: 40/2 = 20 per year
    # Historical: 150/5 = 30 per year
    # Velocity: (20-30)/30 = -0.333
    assert velocity < 0
    assert abs(velocity + 0.333) < 0.01


@pytest.mark.asyncio
async def test_assignee_concentration_concentrated():
    """Test assignee concentration with concentrated ownership"""
    collector = PatentsCollector()

    assignee_counts = {
        "IBM": 60,
        "Google": 25,
        "Microsoft": 10,
        "Intel": 3,
        "Others": 2
    }

    concentration = collector._calculate_assignee_concentration(assignee_counts, 100)

    # Top 3 have 95% of patents
    assert concentration == "concentrated"


@pytest.mark.asyncio
async def test_assignee_concentration_diverse():
    """Test assignee concentration with diverse ownership"""
    collector = PatentsCollector()

    # 20 companies each with 5 patents = very diverse
    assignee_counts = {
        f"Company {chr(65+i)}": 5 for i in range(20)
    }

    concentration = collector._calculate_assignee_concentration(assignee_counts, 100)

    # Top 3 have 15% of patents (< 25%)
    assert concentration == "diverse"


@pytest.mark.asyncio
async def test_geographic_reach_domestic():
    """Test geographic reach with single country"""
    collector = PatentsCollector()

    country_counts = {"US": 95, "CA": 3, "GB": 2}

    reach = collector._calculate_geographic_reach(country_counts)

    # Only US has >5% of patents
    assert reach == "domestic"


@pytest.mark.asyncio
async def test_geographic_reach_global():
    """Test geographic reach with multiple countries"""
    collector = PatentsCollector()

    country_counts = {
        "US": 30,
        "CN": 25,
        "JP": 20,
        "DE": 15,
        "GB": 10
    }

    reach = collector._calculate_geographic_reach(country_counts)

    # 5 countries with >5% each
    assert reach == "global"


@pytest.mark.asyncio
async def test_patent_maturity_emerging():
    """Test patent maturity with emerging technology"""
    collector = PatentsCollector()

    maturity = collector._calculate_patent_maturity(total_patents=30, avg_citations_2y=3.0)

    assert maturity == "emerging"


@pytest.mark.asyncio
async def test_patent_maturity_mature():
    """Test patent maturity with mature technology"""
    collector = PatentsCollector()

    maturity = collector._calculate_patent_maturity(total_patents=600, avg_citations_2y=10.0)

    assert maturity == "mature"


@pytest.mark.asyncio
async def test_patent_momentum_accelerating():
    """Test patent momentum with accelerating filing rate"""
    collector = PatentsCollector()

    # Recent rate significantly higher than historical
    momentum = collector._calculate_patent_momentum(patents_2y=100, patents_5y=100)

    # Recent: 100/2 = 50 per year
    # Historical: 100/5 = 20 per year
    # Ratio: 50/20 = 2.5 > 1.5
    assert momentum == "accelerating"


@pytest.mark.asyncio
async def test_patent_trend_increasing():
    """Test patent trend with increasing filing rate"""
    collector = PatentsCollector()

    # Recent rate moderately higher than historical
    trend = collector._calculate_patent_trend(patents_2y=80, patents_5y=100)

    # Recent: 80/2 = 40 per year
    # Historical: 100/5 = 20 per year
    # Diff ratio: (40-20)/20 = 1.0 > 0.3
    assert trend == "increasing"


@pytest.mark.asyncio
async def test_json_serialization():
    """Test that entire response can be JSON serialized"""
    collector = PatentsCollector()

    mock_response = {
        "error": False,
        "count": 1,
        "total_hits": 10,
        "patents": [
            {
                "patent_id": "11123456",
                "patent_title": "Test Patent",
                "patent_date": "2023-09-15",
                "patent_year": "2023",
                "assignees": [{"assignee_organization": "IBM", "assignee_country": "US"}],
                "patent_num_times_cited_by_us_patents": "25"
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Mock(
            json=Mock(return_value=mock_response),
            raise_for_status=Mock()
        )

        result = await collector.collect("quantum computing")

        # Should not raise TypeError
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Verify can be deserialized
        deserialized = json.loads(json_str)
        assert deserialized["source"] == "patentsview"


@pytest.mark.asyncio
async def test_patents_collector_authentication_failure():
    """Test handling of authentication failure (401)"""
    collector = PatentsCollector()

    mock_response = Mock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = __import__('httpx').HTTPStatusError(
            "Authentication failed", request=Mock(), response=mock_response
        )

        result = await collector.collect("quantum computing")

        assert result["source"] == "patentsview"
        assert result["patents_total"] == 0
        assert len(result["errors"]) > 0
        assert any("Authentication failed" in err or "invalid API key" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_patents_collector_missing_api_key(mock_settings):
    """Test handling when API key is missing from settings"""
    collector = PatentsCollector()

    # Override mock to return None for API key
    mock_settings.patentsview_api_key = None

    result = await collector.collect("quantum computing")

    assert result["source"] == "patentsview"
    assert result["patents_total"] == 0
    assert len(result["errors"]) > 0
    assert any("Missing PatentsView API key" in err for err in result["errors"])
