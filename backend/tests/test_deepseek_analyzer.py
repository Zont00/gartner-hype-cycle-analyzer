"""
Tests for DeepSeek analyzer module.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
import json
from app.analyzers.deepseek import DeepSeekAnalyzer


@pytest.mark.asyncio
async def test_deepseek_analyzer_initialization():
    """Test analyzer initialization with valid API key"""
    analyzer = DeepSeekAnalyzer(api_key="test-api-key")
    assert analyzer.api_key == "test-api-key"


@pytest.mark.asyncio
async def test_deepseek_analyzer_missing_api_key():
    """Test analyzer initialization fails without API key"""
    with pytest.raises(ValueError, match="DeepSeek API key is required"):
        DeepSeekAnalyzer(api_key=None)

    with pytest.raises(ValueError, match="DeepSeek API key is required"):
        DeepSeekAnalyzer(api_key="")


@pytest.mark.asyncio
async def test_deepseek_analyzer_successful_analysis():
    """Test successful end-to-end analysis with mocked DeepSeek API"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    # Mock collector data
    collector_data = {
        "social": {
            "mentions_30d": 200,
            "mentions_6m": 450,
            "mentions_1y": 800,
            "mentions_total": 1200,
            "avg_points_30d": 85.5,
            "avg_comments_30d": 42.3,
            "sentiment": 0.75,
            "growth_trend": "increasing",
            "momentum": "accelerating",
            "recency": "high"
        },
        "papers": {
            "publications_2y": 120,
            "publications_5y": 450,
            "publications_total": 650,
            "avg_citations_2y": 12.5,
            "avg_citations_5y": 18.3,
            "citation_velocity": 0.35,
            "research_maturity": "developing",
            "research_momentum": "accelerating",
            "research_breadth": "broad",
            "author_diversity": 320,
            "venue_diversity": 45
        },
        "patents": {
            "patents_2y": 85,
            "patents_5y": 280,
            "patents_10y": 450,
            "patents_total": 520,
            "avg_citations_2y": 5.2,
            "avg_citations_5y": 8.7,
            "filing_velocity": 0.42,
            "unique_assignees": 35,
            "assignee_concentration": "moderate",
            "geographic_diversity": 12,
            "geographic_reach": "global",
            "patent_maturity": "developing",
            "patent_momentum": "accelerating"
        },
        "news": {
            "articles_30d": 520,
            "articles_3m": 1200,
            "articles_1y": 2800,
            "articles_total": 3200,
            "unique_domains": 145,
            "geographic_diversity": 28,
            "avg_tone": 0.65,
            "media_attention": "high",
            "coverage_trend": "increasing",
            "sentiment_trend": "positive",
            "mainstream_adoption": "mainstream"
        },
        "finance": {
            "companies_found": 8,
            "total_market_cap": 2500000000000,
            "avg_market_cap": 312500000000,
            "avg_price_change_1m": 5.2,
            "avg_price_change_6m": 18.5,
            "avg_price_change_2y": 42.3,
            "avg_volatility_1m": 22.5,
            "avg_volatility_6m": 28.3,
            "volume_trend": "increasing",
            "market_maturity": "developing",
            "investor_sentiment": "positive",
            "investment_momentum": "accelerating"
        }
    }

    # Mock DeepSeek API responses (6 calls: 5 per-source + 1 synthesis)
    per_source_responses = [
        '{"phase": "peak", "confidence": 0.82, "reasoning": "Very high mentions with accelerating momentum"}',
        '{"phase": "slope", "confidence": 0.75, "reasoning": "Strong publication growth with developing maturity"}',
        '{"phase": "slope", "confidence": 0.78, "reasoning": "Accelerating patent filings with global reach"}',
        '{"phase": "peak", "confidence": 0.71, "reasoning": "High media coverage with positive sentiment"}',
        '{"phase": "peak", "confidence": 0.80, "reasoning": "Strong positive returns with high market cap"}'
    ]
    synthesis_response = '{"phase": "peak", "confidence": 0.77, "reasoning": "Consensus across social, news, and finance indicates Peak of Inflated Expectations despite maturing research and patents"}'

    all_responses = per_source_responses + [synthesis_response]
    response_index = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal response_index
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": all_responses[response_index]}}
            ]
        }
        mock_response.raise_for_status = Mock()
        response_index += 1
        return mock_response

    with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
        result = await analyzer.analyze(keyword="quantum computing", collector_data=collector_data)

        # Verify final result structure
        assert result["phase"] == "peak"
        assert result["confidence"] == 0.77
        assert "reasoning" in result
        assert "per_source_analyses" in result
        assert len(result["per_source_analyses"]) == 5

        # Verify per-source analyses
        assert result["per_source_analyses"]["social"]["phase"] == "peak"
        assert result["per_source_analyses"]["papers"]["phase"] == "slope"
        assert result["per_source_analyses"]["patents"]["phase"] == "slope"
        assert result["per_source_analyses"]["news"]["phase"] == "peak"
        assert result["per_source_analyses"]["finance"]["phase"] == "peak"

        # Verify JSON serializable
        json.dumps(result)


@pytest.mark.asyncio
async def test_deepseek_analyzer_per_source_social():
    """Test per-source analysis for social media data"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {
        "mentions_30d": 50,
        "mentions_6m": 80,
        "mentions_1y": 120,
        "mentions_total": 150,
        "avg_points_30d": 25.5,
        "avg_comments_30d": 12.3,
        "sentiment": 0.45,
        "growth_trend": "stable",
        "momentum": "steady",
        "recency": "medium"
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "slope", "confidence": 0.68, "reasoning": "Stable mentions with steady momentum"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "slope"
        assert result["confidence"] == 0.68
        assert "reasoning" in result


@pytest.mark.asyncio
async def test_deepseek_analyzer_per_source_papers():
    """Test per-source analysis for academic papers data"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    papers_data = {
        "publications_2y": 5,
        "publications_5y": 12,
        "publications_total": 18,
        "avg_citations_2y": 2.5,
        "avg_citations_5y": 4.3,
        "citation_velocity": 0.15,
        "research_maturity": "emerging",
        "research_momentum": "steady",
        "research_breadth": "narrow",
        "author_diversity": 12,
        "venue_diversity": 3
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "innovation_trigger", "confidence": 0.85, "reasoning": "Very few publications with narrow research breadth"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("papers", papers_data, "test tech")

        assert result["phase"] == "innovation_trigger"
        assert result["confidence"] == 0.85


@pytest.mark.asyncio
async def test_deepseek_analyzer_per_source_patents():
    """Test per-source analysis for patents data"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    patents_data = {
        "patents_2y": 150,
        "patents_5y": 380,
        "patents_10y": 520,
        "patents_total": 600,
        "avg_citations_2y": 8.5,
        "avg_citations_5y": 12.3,
        "filing_velocity": 0.25,
        "unique_assignees": 45,
        "assignee_concentration": "moderate",
        "geographic_diversity": 18,
        "geographic_reach": "global",
        "patent_maturity": "mature",
        "patent_momentum": "steady"
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "plateau", "confidence": 0.73, "reasoning": "Stable filing rate with mature patents and global coverage"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("patents", patents_data, "test tech")

        assert result["phase"] == "plateau"
        assert result["confidence"] == 0.73


@pytest.mark.asyncio
async def test_deepseek_analyzer_per_source_news():
    """Test per-source analysis for news data"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    news_data = {
        "articles_30d": 800,
        "articles_3m": 1500,
        "articles_1y": 3200,
        "articles_total": 3500,
        "unique_domains": 220,
        "geographic_diversity": 35,
        "avg_tone": 0.55,
        "media_attention": "high",
        "coverage_trend": "increasing",
        "sentiment_trend": "positive",
        "mainstream_adoption": "mainstream"
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.79, "reasoning": "Very high coverage with positive sentiment and mainstream adoption"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("news", news_data, "test tech")

        assert result["phase"] == "peak"
        assert result["confidence"] == 0.79


@pytest.mark.asyncio
async def test_deepseek_analyzer_per_source_finance():
    """Test per-source analysis for finance data"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    finance_data = {
        "companies_found": 12,
        "total_market_cap": 5200000000000,
        "avg_market_cap": 433333333333,
        "avg_price_change_1m": -8.5,
        "avg_price_change_6m": -22.3,
        "avg_price_change_2y": -35.7,
        "avg_volatility_1m": 38.5,
        "avg_volatility_6m": 42.3,
        "volume_trend": "decreasing",
        "market_maturity": "developing",
        "investor_sentiment": "negative",
        "investment_momentum": "decelerating"
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "trough", "confidence": 0.81, "reasoning": "Declining returns with negative sentiment and high volatility"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("finance", finance_data, "test tech")

        assert result["phase"] == "trough"
        assert result["confidence"] == 0.81


@pytest.mark.asyncio
async def test_deepseek_analyzer_synthesis():
    """Test synthesis of multiple source analyses"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    per_source_results = {
        "social": {"phase": "peak", "confidence": 0.82, "reasoning": "High buzz"},
        "papers": {"phase": "slope", "confidence": 0.75, "reasoning": "Maturing research"},
        "patents": {"phase": "slope", "confidence": 0.78, "reasoning": "Steady filings"},
        "news": {"phase": "peak", "confidence": 0.71, "reasoning": "Mainstream coverage"},
        "finance": {"phase": "peak", "confidence": 0.80, "reasoning": "Strong returns"}
    }

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.77, "reasoning": "Majority of sources indicate peak despite some maturing indicators"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._synthesize_analyses("test tech", per_source_results)

        assert result["phase"] == "peak"
        assert result["confidence"] == 0.77
        assert "reasoning" in result


@pytest.mark.asyncio
async def test_deepseek_analyzer_rate_limit():
    """Test graceful handling of rate limiting (429 error)"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50},
        "patents": {"patents_2y": 30},
        "news": {"articles_30d": 200},
        "finance": {"companies_found": 5}
    }

    mock_response = Mock()
    mock_response.status_code = 429

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited",
            request=Mock(),
            response=mock_response
        )

        with pytest.raises(Exception):
            await analyzer.analyze(keyword="test", collector_data=collector_data)


@pytest.mark.asyncio
async def test_deepseek_analyzer_auth_failure():
    """Test handling of authentication failure (401 error)"""
    analyzer = DeepSeekAnalyzer(api_key="invalid-key")

    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50},
        "patents": {"patents_2y": 30},
        "news": {"articles_30d": 200},
        "finance": {"companies_found": 5}
    }

    mock_response = Mock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=Mock(),
            response=mock_response
        )

        with pytest.raises(Exception):
            await analyzer.analyze(keyword="test", collector_data=collector_data)


@pytest.mark.asyncio
async def test_deepseek_analyzer_timeout():
    """Test handling of request timeout"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50},
        "patents": {"patents_2y": 30},
        "news": {"articles_30d": 200},
        "finance": {"companies_found": 5}
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(Exception):
            await analyzer.analyze(keyword="test", collector_data=collector_data)


@pytest.mark.asyncio
async def test_deepseek_analyzer_invalid_json():
    """Test handling of invalid JSON response"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": "This is not valid JSON!"}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        # Now raises ValueError with better error message instead of bare JSONDecodeError
        with pytest.raises(ValueError, match="Failed to parse DeepSeek response"):
            await analyzer._analyze_source("social", social_data, "test tech")


@pytest.mark.asyncio
async def test_deepseek_analyzer_missing_fields():
    """Test handling of response with missing required fields"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Response missing "reasoning" field
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.75}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="missing required fields"):
            await analyzer._analyze_source("social", social_data, "test tech")


@pytest.mark.asyncio
async def test_deepseek_analyzer_invalid_phase():
    """Test handling of response with invalid phase value"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "invalid_phase", "confidence": 0.75, "reasoning": "Test"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Invalid phase"):
            await analyzer._analyze_source("social", social_data, "test tech")


@pytest.mark.asyncio
async def test_deepseek_analyzer_confidence_out_of_range():
    """Test handling of confidence value outside 0-1 range"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Confidence > 1
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 1.5, "reasoning": "Test"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Confidence must be float between 0-1"):
            await analyzer._analyze_source("social", social_data, "test tech")


@pytest.mark.asyncio
async def test_deepseek_analyzer_markdown_stripping():
    """Test stripping of markdown code blocks from response"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Response wrapped in markdown code block
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '```json\n{"phase": "peak", "confidence": 0.75, "reasoning": "Test"}\n```'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "peak"
        assert result["confidence"] == 0.75


@pytest.mark.asyncio
async def test_deepseek_analyzer_bare_json():
    """Test handling of bare JSON without markdown wrapping"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Bare JSON without markdown
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "trough", "confidence": 0.65, "reasoning": "Bare JSON test"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "trough"
        assert result["confidence"] == 0.65


@pytest.mark.asyncio
async def test_deepseek_analyzer_markdown_without_language():
    """Test markdown code block without 'json' language identifier"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Markdown without 'json' identifier
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '```\n{"phase": "slope", "confidence": 0.70, "reasoning": "No language tag"}\n```'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "slope"
        assert result["confidence"] == 0.70


@pytest.mark.asyncio
async def test_deepseek_analyzer_text_after_closing_backticks():
    """Test handling of text after closing markdown backticks"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Text after closing backticks (was problematic with old string splitting)
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '```json\n{"phase": "plateau", "confidence": 0.80, "reasoning": "With trailing text"}\n```\nHere is my explanation of the analysis.'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "plateau"
        assert result["confidence"] == 0.80


@pytest.mark.asyncio
async def test_deepseek_analyzer_multiple_code_blocks():
    """Test handling of multiple code blocks (grabs first JSON)"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Multiple code blocks (old splitting would fail)
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": 'Some text ```json\n{"phase": "innovation_trigger", "confidence": 0.55, "reasoning": "First block"}\n``` more text ```json\n{"invalid": "second"}\n```'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer._analyze_source("social", social_data, "test tech")

        assert result["phase"] == "innovation_trigger"
        assert result["confidence"] == 0.55


@pytest.mark.asyncio
async def test_deepseek_analyzer_malformed_json_with_logging(caplog):
    """Test error logging when JSON is malformed"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # Invalid JSON
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.75, "reasoning": "Missing closing brace"'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Failed to parse DeepSeek response"):
            await analyzer._analyze_source("social", social_data, "test tech")

        # Verify logging occurred
        assert "Failed to parse DeepSeek JSON response" in caplog.text
        assert "Raw content:" in caplog.text


@pytest.mark.asyncio
async def test_deepseek_analyzer_no_json_content():
    """Test error when no JSON content found in response"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    social_data = {"mentions_30d": 100}

    # No JSON in response
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": 'This is just plain text with no JSON at all.'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with pytest.raises(ValueError, match="Failed to parse DeepSeek response"):
            await analyzer._analyze_source("social", social_data, "test tech")


@pytest.mark.asyncio
async def test_deepseek_analyzer_insufficient_sources():
    """Test handling when too many sources fail"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    # Only provide 2 sources (need at least 3)
    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50}
    }

    with pytest.raises(Exception, match="Insufficient data for analysis"):
        await analyzer.analyze(keyword="test", collector_data=collector_data)


@pytest.mark.asyncio
async def test_deepseek_analyzer_partial_source_failure():
    """Test analysis continues when some sources fail"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50},
        "patents": {"patents_2y": 30},
        "news": {"articles_30d": 200},
        "finance": {"companies_found": 5}
    }

    # First call (social) succeeds, second (papers) fails, rest succeed
    call_count = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 2:  # papers analysis fails
            raise httpx.TimeoutException("Timeout")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"phase": "peak", "confidence": 0.75, "reasoning": "Test"}'}}
            ]
        }
        mock_response.raise_for_status = Mock()
        return mock_response

    with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
        result = await analyzer.analyze(keyword="test", collector_data=collector_data)

        # Should succeed with 4 sources (social, patents, news, finance + synthesis)
        assert "phase" in result
        assert "confidence" in result
        assert "errors" in result
        assert len(result["errors"]) > 0  # Should have error for failed papers source


@pytest.mark.asyncio
async def test_deepseek_analyzer_json_serialization():
    """Test that analysis result is JSON serializable"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    collector_data = {
        "social": {"mentions_30d": 100},
        "papers": {"publications_2y": 50},
        "patents": {"patents_2y": 30},
        "news": {"articles_30d": 200},
        "finance": {"companies_found": 5}
    }

    # Mock all 6 API calls
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.75, "reasoning": "Test analysis"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer.analyze(keyword="test", collector_data=collector_data)

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Should round-trip correctly
        deserialized = json.loads(json_str)
        assert deserialized["phase"] == result["phase"]
        assert deserialized["confidence"] == result["confidence"]
