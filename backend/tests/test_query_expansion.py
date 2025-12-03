"""
Test suite for query expansion functionality.

Tests niche detection, DeepSeek expansion, collector integration,
and end-to-end expansion workflow.
"""
import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
from app.analyzers.hype_classifier import HypeCycleClassifier
from app.analyzers.deepseek import DeepSeekAnalyzer


class TestNicheDetection:
    """Test niche technology detection logic"""

    def test_detect_niche_low_mentions_30d(self):
        """Niche detected when mentions_30d < 50"""
        classifier = HypeCycleClassifier()
        collector_results = {
            "social": {"mentions_30d": 30, "mentions_total": 150},
            "papers": {},
            "patents": {},
            "news": {},
            "finance": {}
        }

        assert classifier._detect_niche(collector_results) is True

    def test_detect_niche_low_mentions_total(self):
        """Niche detected when mentions_total < 100"""
        classifier = HypeCycleClassifier()
        collector_results = {
            "social": {"mentions_30d": 60, "mentions_total": 80},
            "papers": {},
            "patents": {},
            "news": {},
            "finance": {}
        }

        assert classifier._detect_niche(collector_results) is True

    def test_not_niche_sufficient_mentions(self):
        """Not niche when both metrics above thresholds"""
        classifier = HypeCycleClassifier()
        collector_results = {
            "social": {"mentions_30d": 200, "mentions_total": 500},
            "papers": {},
            "patents": {},
            "news": {},
            "finance": {}
        }

        assert classifier._detect_niche(collector_results) is False

    def test_detect_niche_no_social_data(self):
        """No niche detection when social data missing"""
        classifier = HypeCycleClassifier()
        collector_results = {
            "social": None,
            "papers": {},
            "patents": {},
            "news": {},
            "finance": {}
        }

        assert classifier._detect_niche(collector_results) is False


class TestDeepSeekExpansion:
    """Test DeepSeek query expansion generator"""

    @pytest.mark.asyncio
    async def test_generate_expanded_terms_success(self):
        """Successfully generate 3-5 expanded terms"""
        analyzer = DeepSeekAnalyzer(api_key="test-key")

        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"terms": ["term1", "term2", "term3", "term4"]}'
                }
            }]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=Mock(json=Mock(return_value=mock_response))
            )

            terms = await analyzer.generate_expanded_terms("plant cell culture")

            assert len(terms) == 4
            assert "term1" in terms
            assert "term2" in terms

    @pytest.mark.asyncio
    async def test_generate_expanded_terms_rejects_generic(self):
        """Filter out generic terms like 'technology'"""
        analyzer = DeepSeekAnalyzer(api_key="test-key")

        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"terms": ["term1", "technology", "system", "term2", "innovation"]}'
                }
            }]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=Mock(json=Mock(return_value=mock_response))
            )

            # Should raise ValueError because only 2 valid terms after filtering
            with pytest.raises(ValueError, match="Only 2 valid terms"):
                await analyzer.generate_expanded_terms("test keyword")

    @pytest.mark.asyncio
    async def test_generate_expanded_terms_rejects_duplicate_keyword(self):
        """Filter out the original keyword from expanded terms"""
        analyzer = DeepSeekAnalyzer(api_key="test-key")

        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"terms": ["term1", "plant cell culture", "term2", "term3"]}'
                }
            }]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=Mock(json=Mock(return_value=mock_response))
            )

            terms = await analyzer.generate_expanded_terms("plant cell culture")

            assert len(terms) == 3
            assert "plant cell culture" not in terms

    @pytest.mark.asyncio
    async def test_generate_expanded_terms_handles_markdown(self):
        """Strip markdown code blocks from DeepSeek response"""
        analyzer = DeepSeekAnalyzer(api_key="test-key")

        mock_response = {
            "choices": [{
                "message": {
                    "content": '```json\n{"terms": ["term1", "term2", "term3", "term4"]}\n```'
                }
            }]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=Mock(json=Mock(return_value=mock_response))
            )

            terms = await analyzer.generate_expanded_terms("test keyword")

            assert len(terms) == 4


class TestCollectorExpansion:
    """Test collector integration with expanded_terms"""

    @pytest.mark.asyncio
    async def test_social_collector_with_expanded_terms(self):
        """SocialCollector aggregates results from multiple terms"""
        from app.collectors.social import SocialCollector

        collector = SocialCollector()

        # Mock multiple API responses
        mock_responses = [
            {
                "nbHits": 10,
                "hits": [{"objectID": "1", "title": "Story 1", "points": 50, "num_comments": 10}]
            },
            {
                "nbHits": 15,
                "hits": [{"objectID": "2", "title": "Story 2", "points": 60, "num_comments": 20}]
            }
        ]

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=[
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[0])),
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[1])),
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[0])),
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[1])),
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[0])),
                Mock(raise_for_status=Mock(), json=Mock(return_value=mock_responses[1]))
            ])
            mock_client.return_value.__aenter__.return_value.get = mock_get

            result = await collector.collect("keyword", expanded_terms=["term1"])

            # Should have aggregated nbHits from both keyword and term1
            assert result["mentions_30d"] >= 10  # At least original keyword results

    @pytest.mark.asyncio
    async def test_papers_collector_with_expanded_terms(self):
        """PapersCollector constructs OR query with expanded terms"""
        from app.collectors.papers import PapersCollector

        collector = PapersCollector()

        mock_response = {
            "total": 50,
            "data": [
                {"paperId": "1", "title": "Paper 1", "year": 2023, "citationCount": 10}
            ]
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=Mock(
                raise_for_status=Mock(),
                json=Mock(return_value=mock_response)
            ))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            result = await collector.collect("keyword", expanded_terms=["term1", "term2"])

            # Verify OR query was constructed
            calls = mock_get.call_args_list
            assert len(calls) == 2  # 2 time periods
            query_param = calls[0][1]['params']['query']
            assert 'OR' in query_param
            assert '"keyword"' in query_param
            assert '"term1"' in query_param


class TestEndToEndExpansion:
    """Test complete query expansion workflow"""

    @pytest.mark.asyncio
    async def test_expansion_triggered_for_niche_insufficient_data(self):
        """Query expansion triggers when niche AND <3 collectors"""
        from app.analyzers.hype_classifier import HypeCycleClassifier

        classifier = HypeCycleClassifier()

        # Mock initial collectors: niche (low social mentions) + only 2 successful
        initial_results = {
            "social": {"mentions_30d": 20, "mentions_total": 50},  # Niche
            "papers": None,
            "patents": None,
            "news": {"articles_30d": 5},
            "finance": None
        }

        # Mock expanded results: now 4 collectors succeed
        expanded_results = {
            "social": {"mentions_30d": 100, "mentions_total": 250},  # Expanded
            "papers": {"publications_2y": 30},  # Now succeeds
            "patents": {"patents_2y": 15},  # Now succeeds
            "news": {"articles_30d": 50},  # Expanded
            "finance": None
        }

        expanded_terms = ["term1", "term2", "term3"]

        with patch.object(classifier, '_run_collectors', return_value=(initial_results, [])):
            with patch.object(classifier, '_expand_query_and_rerun', return_value=(expanded_results, [], expanded_terms)):
                with patch('app.analyzers.deepseek.DeepSeekAnalyzer') as mock_analyzer:
                    mock_analyzer.return_value.analyze = AsyncMock(return_value={
                        "phase": "innovation_trigger",
                        "confidence": 0.75,
                        "reasoning": "Test reasoning",
                        "per_source_analyses": {}
                    })

                    with patch('aiosqlite.connect'):
                        # Mock database
                        mock_db = AsyncMock()
                        mock_db.execute = AsyncMock()
                        mock_db.commit = AsyncMock()

                        result = await classifier.classify("plant cell culture", mock_db)

                        # Verify expansion was applied
                        assert result["query_expansion_applied"] is True
                        assert result["expanded_terms"] == expanded_terms

    @pytest.mark.asyncio
    async def test_no_expansion_for_mainstream(self):
        """No query expansion for mainstream technologies"""
        from app.analyzers.hype_classifier import HypeCycleClassifier

        classifier = HypeCycleClassifier()

        # Mock collectors: NOT niche (high social mentions) + all 5 succeed
        mainstream_results = {
            "social": {"mentions_30d": 500, "mentions_total": 2000},  # NOT niche
            "papers": {"publications_2y": 200},
            "patents": {"patents_2y": 150},
            "news": {"articles_30d": 800},
            "finance": {"companies_found": 10}
        }

        with patch.object(classifier, '_run_collectors', return_value=(mainstream_results, [])):
            with patch('app.analyzers.deepseek.DeepSeekAnalyzer') as mock_analyzer:
                mock_analyzer.return_value.analyze = AsyncMock(return_value={
                    "phase": "peak",
                    "confidence": 0.85,
                    "reasoning": "Test reasoning",
                    "per_source_analyses": {}
                })

                with patch('aiosqlite.connect'):
                    mock_db = AsyncMock()
                    mock_db.execute = AsyncMock()
                    mock_db.commit = AsyncMock()

                    result = await classifier.classify("quantum computing", mock_db)

                    # Verify NO expansion
                    assert result["query_expansion_applied"] is False
                    assert result["expanded_terms"] == []
