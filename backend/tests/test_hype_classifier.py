"""
Tests for HypeCycleClassifier orchestration module.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
from datetime import datetime, timedelta
from app.analyzers.hype_classifier import HypeCycleClassifier


@pytest.fixture
def mock_settings():
    """Mock settings object"""
    settings = Mock()
    settings.deepseek_api_key = "test-deepseek-key"
    settings.cache_ttl_hours = 24
    return settings


@pytest.fixture
def sample_collector_data():
    """Sample collector data for testing"""
    return {
        "social": {
            "source": "hacker_news",
            "mentions_30d": 250,
            "sentiment": 0.72,
            "growth_trend": "increasing",
            "errors": []
        },
        "papers": {
            "source": "semantic_scholar",
            "publications_2y": 120,
            "citation_velocity": 0.35,
            "research_maturity": "developing",
            "errors": []
        },
        "patents": {
            "source": "patentsview",
            "patents_2y": 85,
            "filing_velocity": 0.42,
            "patent_maturity": "developing",
            "errors": []
        },
        "news": {
            "source": "gdelt",
            "articles_30d": 520,
            "avg_tone": 0.65,
            "media_attention": "high",
            "errors": []
        },
        "finance": {
            "source": "yahoo_finance",
            "companies_found": 8,
            "avg_price_change_6m": 18.5,
            "market_maturity": "developing",
            "errors": []
        }
    }


@pytest.fixture
def sample_analysis_result():
    """Sample DeepSeek analysis result"""
    return {
        "phase": "peak",
        "confidence": 0.82,
        "reasoning": "Strong signals across all sources indicating peak hype",
        "per_source_analyses": {
            "social": {"phase": "peak", "confidence": 0.85, "reasoning": "High mentions"},
            "papers": {"phase": "slope", "confidence": 0.78, "reasoning": "Steady research"},
            "patents": {"phase": "peak", "confidence": 0.80, "reasoning": "Accelerating filings"},
            "news": {"phase": "peak", "confidence": 0.88, "reasoning": "High media attention"},
            "finance": {"phase": "peak", "confidence": 0.75, "reasoning": "Strong investor sentiment"}
        },
        "errors": []
    }


@pytest.mark.asyncio
async def test_classifier_initialization(mock_settings):
    """Test classifier initialization"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()
        assert classifier.settings == mock_settings


@pytest.mark.asyncio
async def test_classify_with_cache_hit(mock_settings):
    """Test classification when cache hit occurs"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        # Mock database with cached result
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_row = {
            "keyword": "quantum computing",
            "phase": "peak",
            "confidence": 0.82,
            "reasoning": "Cached analysis",
            "created_at": "2025-12-02T10:00:00",
            "expires_at": "2025-12-03T10:00:00",
            "social_data": json.dumps({"mentions": 250}),
            "papers_data": json.dumps({"publications": 120}),
            "patents_data": json.dumps({"patents": 85}),
            "news_data": json.dumps({"articles": 520}),
            "finance_data": json.dumps({"companies": 8})
        }

        # Mock row dictionary access
        def getitem(key):
            return mock_row[key]
        mock_row_obj = Mock()
        mock_row_obj.__getitem__ = Mock(side_effect=getitem)

        # Set up async context manager for cursor
        mock_cursor.fetchone = AsyncMock(return_value=mock_row_obj)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)

        # db.execute returns cursor directly (not awaited)
        mock_db.execute = Mock(return_value=mock_cursor)

        result = await classifier.classify("quantum computing", mock_db)

        # Verify cache hit
        assert result["cache_hit"] is True
        assert result["keyword"] == "quantum computing"
        assert result["phase"] == "peak"
        assert result["confidence"] == 0.82


@pytest.mark.asyncio
async def test_classify_cache_miss_all_collectors_succeed(
    mock_settings, sample_collector_data, sample_analysis_result
):
    """Test classification with cache miss and all collectors succeeding"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        # Mock database with no cached result
        mock_db = AsyncMock()
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=None)
        mock_cursor_check.__aenter__ = AsyncMock(return_value=mock_cursor_check)
        mock_cursor_check.__aexit__ = AsyncMock(return_value=None)

        # Mock insert cursor
        mock_cursor_insert = AsyncMock()
        mock_cursor_insert.__aenter__ = AsyncMock(return_value=mock_cursor_insert)
        mock_cursor_insert.__aexit__ = AsyncMock(return_value=None)

        async def execute_side_effect(query, params=None):
            if "SELECT" in query:
                return mock_cursor_check
            return mock_cursor_insert

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.commit = AsyncMock()

        # Mock collectors
        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(return_value=sample_collector_data["patents"])
            mock_news.return_value.collect = AsyncMock(return_value=sample_collector_data["news"])
            mock_finance.return_value.collect = AsyncMock(return_value=sample_collector_data["finance"])

            # Mock DeepSeek analyzer
            with patch("app.analyzers.hype_classifier.DeepSeekAnalyzer") as mock_analyzer_class:
                mock_analyzer = AsyncMock()
                mock_analyzer.analyze = AsyncMock(return_value=sample_analysis_result)
                mock_analyzer_class.return_value = mock_analyzer

                result = await classifier.classify("quantum computing", mock_db)

                # Verify result structure
                assert result["cache_hit"] is False
                assert result["keyword"] == "quantum computing"
                assert result["phase"] == "peak"
                assert result["confidence"] == 0.82
                assert result["collectors_succeeded"] == 5
                assert result["partial_data"] is False
                assert len(result["errors"]) == 0
                assert "per_source_analyses" in result
                assert "collector_data" in result

                # Verify database was written
                mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_classify_partial_success_3_collectors(
    mock_settings, sample_collector_data, sample_analysis_result
):
    """Test classification with 3/5 collectors succeeding (minimum threshold)"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        # Mock database
        mock_db = AsyncMock()
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=None)
        mock_cursor_check.__aenter__ = AsyncMock(return_value=mock_cursor_check)
        mock_cursor_check.__aexit__ = AsyncMock(return_value=None)

        mock_cursor_insert = AsyncMock()
        mock_cursor_insert.__aenter__ = AsyncMock(return_value=mock_cursor_insert)
        mock_cursor_insert.__aexit__ = AsyncMock(return_value=None)

        async def execute_side_effect(query, params=None):
            if "SELECT" in query:
                return mock_cursor_check
            return mock_cursor_insert

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.commit = AsyncMock()

        # Mock collectors - 3 succeed, 2 fail
        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(return_value=sample_collector_data["patents"])
            mock_news.return_value.collect = AsyncMock(side_effect=Exception("News API timeout"))
            mock_finance.return_value.collect = AsyncMock(side_effect=Exception("Finance API error"))

            # Mock DeepSeek analyzer
            modified_analysis = sample_analysis_result.copy()
            modified_analysis["errors"] = ["Missing news data", "Missing finance data"]

            with patch("app.analyzers.hype_classifier.DeepSeekAnalyzer") as mock_analyzer_class:
                mock_analyzer = AsyncMock()
                mock_analyzer.analyze = AsyncMock(return_value=modified_analysis)
                mock_analyzer_class.return_value = mock_analyzer

                result = await classifier.classify("quantum computing", mock_db)

                # Verify partial success
                assert result["collectors_succeeded"] == 3
                assert result["partial_data"] is True
                assert len(result["errors"]) >= 2  # At least the 2 collector failures
                assert any("news" in err.lower() for err in result["errors"])
                assert any("finance" in err.lower() for err in result["errors"])


@pytest.mark.asyncio
async def test_classify_insufficient_collectors(mock_settings, sample_collector_data):
    """Test classification fails with <3 collectors (below threshold)"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        # Mock database
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_cursor.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        # Mock collectors - only 2 succeed
        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(side_effect=Exception("API error"))
            mock_news.return_value.collect = AsyncMock(side_effect=Exception("API error"))
            mock_finance.return_value.collect = AsyncMock(side_effect=Exception("API error"))

            # Should raise exception
            with pytest.raises(Exception, match="Insufficient data: only 2/5 collectors succeeded"):
                await classifier.classify("quantum computing", mock_db)


@pytest.mark.asyncio
async def test_run_collectors_all_succeed(mock_settings, sample_collector_data):
    """Test _run_collectors with all collectors succeeding"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(return_value=sample_collector_data["patents"])
            mock_news.return_value.collect = AsyncMock(return_value=sample_collector_data["news"])
            mock_finance.return_value.collect = AsyncMock(return_value=sample_collector_data["finance"])

            collector_results, errors = await classifier._run_collectors("quantum computing")

            assert len(collector_results) == 5
            assert all(v is not None for v in collector_results.values())
            assert len(errors) == 0


@pytest.mark.asyncio
async def test_run_collectors_with_failures(mock_settings, sample_collector_data):
    """Test _run_collectors with some collectors failing"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(side_effect=Exception("API rate limit"))
            mock_news.return_value.collect = AsyncMock(return_value=sample_collector_data["news"])
            mock_finance.return_value.collect = AsyncMock(side_effect=Exception("Network timeout"))

            collector_results, errors = await classifier._run_collectors("quantum computing")

            assert len(collector_results) == 5
            assert collector_results["social"] is not None
            assert collector_results["papers"] is not None
            assert collector_results["patents"] is None
            assert collector_results["news"] is not None
            assert collector_results["finance"] is None
            assert len(errors) == 2
            assert any("patents" in err for err in errors)
            assert any("finance" in err for err in errors)


@pytest.mark.asyncio
async def test_persist_result(mock_settings, sample_collector_data, sample_analysis_result):
    """Test _persist_result writes to database correctly"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        result = await classifier._persist_result(
            "quantum computing",
            sample_analysis_result,
            sample_collector_data,
            mock_db
        )

        # Verify result structure
        assert "created_at" in result
        assert "expires_at" in result

        # Verify database was called
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify INSERT query structure
        call_args = mock_db.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO analyses" in query
        assert params[0] == "quantum computing"
        assert params[1] == "peak"
        assert params[2] == 0.82


@pytest.mark.asyncio
async def test_assemble_response_full_data(sample_collector_data, sample_analysis_result):
    """Test _assemble_response with full data"""
    classifier = HypeCycleClassifier.__new__(HypeCycleClassifier)

    response = classifier._assemble_response(
        keyword="quantum computing",
        analysis=sample_analysis_result,
        collector_results=sample_collector_data,
        collector_errors=[],
        cache_hit=False,
        created_at="2025-12-02T10:00:00",
        expires_at="2025-12-03T10:00:00"
    )

    # Verify structure
    assert response["keyword"] == "quantum computing"
    assert response["phase"] == "peak"
    assert response["confidence"] == 0.82
    assert response["cache_hit"] is False
    assert response["collectors_succeeded"] == 5
    assert response["partial_data"] is False
    assert len(response["errors"]) == 0
    assert "per_source_analyses" in response
    assert "collector_data" in response


@pytest.mark.asyncio
async def test_assemble_response_partial_data(sample_collector_data, sample_analysis_result):
    """Test _assemble_response with partial data"""
    classifier = HypeCycleClassifier.__new__(HypeCycleClassifier)

    partial_collectors = sample_collector_data.copy()
    partial_collectors["news"] = None
    partial_collectors["finance"] = None

    response = classifier._assemble_response(
        keyword="quantum computing",
        analysis=sample_analysis_result,
        collector_results=partial_collectors,
        collector_errors=["news collector failed: timeout", "finance collector failed: error"],
        cache_hit=False,
        created_at="2025-12-02T10:00:00",
        expires_at="2025-12-03T10:00:00"
    )

    assert response["collectors_succeeded"] == 3
    assert response["partial_data"] is True
    assert len(response["errors"]) >= 2


@pytest.mark.asyncio
async def test_assemble_response_with_analysis_errors(sample_collector_data, sample_analysis_result):
    """Test _assemble_response combines collector and analysis errors"""
    classifier = HypeCycleClassifier.__new__(HypeCycleClassifier)

    analysis_with_errors = sample_analysis_result.copy()
    analysis_with_errors["errors"] = ["DeepSeek analysis warning"]

    response = classifier._assemble_response(
        keyword="quantum computing",
        analysis=analysis_with_errors,
        collector_results=sample_collector_data,
        collector_errors=["collector error"],
        cache_hit=False,
        created_at="2025-12-02T10:00:00",
        expires_at="2025-12-03T10:00:00"
    )

    assert len(response["errors"]) == 2
    assert "collector error" in response["errors"]
    assert "DeepSeek analysis warning" in response["errors"]


@pytest.mark.asyncio
async def test_result_json_serializable(
    mock_settings, sample_collector_data, sample_analysis_result
):
    """Test that final result is JSON serializable"""
    with patch("app.analyzers.hype_classifier.get_settings", return_value=mock_settings):
        classifier = HypeCycleClassifier()

        # Mock database
        mock_db = AsyncMock()
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=None)
        mock_cursor_check.__aenter__ = AsyncMock(return_value=mock_cursor_check)
        mock_cursor_check.__aexit__ = AsyncMock(return_value=None)

        mock_cursor_insert = AsyncMock()
        mock_cursor_insert.__aenter__ = AsyncMock(return_value=mock_cursor_insert)
        mock_cursor_insert.__aexit__ = AsyncMock(return_value=None)

        async def execute_side_effect(query, params=None):
            if "SELECT" in query:
                return mock_cursor_check
            return mock_cursor_insert

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.commit = AsyncMock()

        # Mock collectors and analyzer
        with patch("app.analyzers.hype_classifier.SocialCollector") as mock_social, \
             patch("app.analyzers.hype_classifier.PapersCollector") as mock_papers, \
             patch("app.analyzers.hype_classifier.PatentsCollector") as mock_patents, \
             patch("app.analyzers.hype_classifier.NewsCollector") as mock_news, \
             patch("app.analyzers.hype_classifier.FinanceCollector") as mock_finance, \
             patch("app.analyzers.hype_classifier.DeepSeekAnalyzer") as mock_analyzer_class:

            mock_social.return_value.collect = AsyncMock(return_value=sample_collector_data["social"])
            mock_papers.return_value.collect = AsyncMock(return_value=sample_collector_data["papers"])
            mock_patents.return_value.collect = AsyncMock(return_value=sample_collector_data["patents"])
            mock_news.return_value.collect = AsyncMock(return_value=sample_collector_data["news"])
            mock_finance.return_value.collect = AsyncMock(return_value=sample_collector_data["finance"])

            mock_analyzer = AsyncMock()
            mock_analyzer.analyze = AsyncMock(return_value=sample_analysis_result)
            mock_analyzer_class.return_value = mock_analyzer

            result = await classifier.classify("quantum computing", mock_db)

            # Should not raise exception
            json_str = json.dumps(result)
            assert json_str is not None
            assert len(json_str) > 0

            # Verify can be parsed back
            parsed = json.loads(json_str)
            assert parsed["keyword"] == "quantum computing"
