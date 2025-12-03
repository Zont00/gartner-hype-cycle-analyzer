"""
HypeCycleClassifier - Main orchestration logic for Hype Cycle analysis.
Coordinates data collection, LLM analysis, caching, and error recovery.
"""
from typing import Dict, Any, Optional, List
import asyncio
import aiosqlite
from datetime import datetime, timedelta
import json
import logging

from app.collectors.social import SocialCollector
from app.collectors.papers import PapersCollector
from app.collectors.patents import PatentsCollector
from app.collectors.news import NewsCollector
from app.collectors.finance import FinanceCollector
from app.analyzers.deepseek import DeepSeekAnalyzer
from app.config import get_settings

logger = logging.getLogger(__name__)


class HypeCycleClassifier:
    """
    Orchestrates hype cycle classification workflow:
    1. Check database cache
    2. Parallel collector execution
    3. DeepSeek analysis
    4. Result persistence
    """

    # Configuration constants
    MINIMUM_SOURCES_REQUIRED = 3
    COLLECTOR_TIMEOUT_SECONDS = 120.0

    def __init__(self):
        """Initialize classifier with settings"""
        self.settings = get_settings()

    async def classify(self, keyword: str, db: aiosqlite.Connection) -> Dict[str, Any]:
        """
        Main entry point for classification.

        Args:
            keyword: Technology keyword to analyze
            db: Database connection (from Depends(get_db))

        Returns:
            Classification result dict with phase, confidence, reasoning, data

        Raises:
            Exception: If <3 collectors succeed or DeepSeek fails
        """
        # Check cache first
        cached = await self._check_cache(keyword, db)
        if cached:
            return cached

        # Run collectors in parallel
        collector_results, collector_errors = await self._run_collectors(keyword)

        # Check minimum threshold
        successful = [r for r in collector_results.values() if r is not None]
        if len(successful) < self.MINIMUM_SOURCES_REQUIRED:
            raise Exception(
                f"Insufficient data: only {len(successful)}/5 collectors succeeded. "
                f"Minimum {self.MINIMUM_SOURCES_REQUIRED} required. "
                f"Errors: {collector_errors}"
            )

        # Run DeepSeek analysis
        analyzer = DeepSeekAnalyzer(api_key=self.settings.deepseek_api_key)
        analysis = await analyzer.analyze(keyword, collector_results)

        # Persist to database
        result = await self._persist_result(keyword, analysis, collector_results, db)

        # Assemble final response
        return self._assemble_response(
            keyword=keyword,
            analysis=analysis,
            collector_results=collector_results,
            collector_errors=collector_errors,
            cache_hit=False,
            created_at=result["created_at"],
            expires_at=result["expires_at"]
        )

    async def _check_cache(self, keyword: str, db: aiosqlite.Connection) -> Optional[Dict[str, Any]]:
        """
        Check database for cached analysis result.

        Args:
            keyword: Technology keyword
            db: Database connection

        Returns:
            Cached result dict if found and not expired, None otherwise
        """
        query = """
            SELECT * FROM analyses
            WHERE keyword = ? AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        now = datetime.now().isoformat()

        try:
            async with db.execute(query, (keyword, now)) as cursor:
                row = await cursor.fetchone()

                if not row:
                    logger.info(f"Cache miss for keyword: {keyword}")
                    return None

                logger.info(f"Cache hit for keyword: {keyword}")

                # Parse JSON fields for collector data
                collector_results = {}
                for source in ["social", "papers", "patents", "news", "finance"]:
                    data_field = f"{source}_data"
                    raw_data = row[data_field]
                    collector_results[source] = json.loads(raw_data) if raw_data else None

                # Retrieve per_source_analyses from database
                try:
                    raw_per_source = row["per_source_analyses_data"]
                    per_source_analyses = json.loads(raw_per_source) if raw_per_source else {}
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to deserialize per_source_analyses for {keyword}: {e}")
                    per_source_analyses = {}

                # Assemble cached response
                return self._assemble_response(
                    keyword=keyword,
                    analysis={
                        "phase": row["phase"],
                        "confidence": row["confidence"],
                        "reasoning": row["reasoning"],
                        "per_source_analyses": per_source_analyses
                    },
                    collector_results=collector_results,
                    collector_errors=[],
                    cache_hit=True,
                    created_at=row["created_at"],
                    expires_at=row["expires_at"]
                )
        except Exception as e:
            # Cache check failure should not block analysis
            # Log error and continue with fresh analysis
            logger.error(f"Cache check failed for keyword {keyword}: {str(e)}")
            return None

    async def _run_collectors(self, keyword: str) -> tuple[Dict[str, Optional[Dict[str, Any]]], List[str]]:
        """
        Run all collectors in parallel.

        Args:
            keyword: Technology keyword

        Returns:
            Tuple of (collector_results dict, errors list)
        """
        # Instantiate all collectors
        collectors = {
            "social": SocialCollector(),
            "papers": PapersCollector(),
            "patents": PatentsCollector(),
            "news": NewsCollector(),
            "finance": FinanceCollector()
        }

        # Execute all in parallel with exception handling and timeout
        tasks = [collector.collect(keyword) for collector in collectors.values()]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.COLLECTOR_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning(f"Collector execution timeout after {self.COLLECTOR_TIMEOUT_SECONDS} seconds")
            # Treat timeout as failure for all collectors
            results = [Exception(f"Timeout after {self.COLLECTOR_TIMEOUT_SECONDS}s")] * len(tasks)

        # Process results and track errors
        collector_results = {}
        errors = []

        for source_name, result in zip(collectors.keys(), results):
            if isinstance(result, Exception):
                error_msg = f"{source_name} collector failed: {str(result)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                collector_results[source_name] = None
            else:
                collector_results[source_name] = result

        logger.info(f"Collectors completed: {len([r for r in collector_results.values() if r is not None])}/5 succeeded")
        return collector_results, errors

    async def _persist_result(
        self,
        keyword: str,
        analysis: Dict[str, Any],
        collector_results: Dict[str, Optional[Dict[str, Any]]],
        db: aiosqlite.Connection
    ) -> Dict[str, Any]:
        """
        Persist analysis result to database.

        Args:
            keyword: Technology keyword
            analysis: DeepSeek analysis result
            collector_results: Raw collector data
            db: Database connection

        Returns:
            Dict with created_at and expires_at timestamps
        """
        # Calculate timestamps
        created_at = datetime.now()
        expires_at = created_at + timedelta(hours=self.settings.cache_ttl_hours)

        # Serialize collector data to JSON
        social_data = json.dumps(collector_results.get("social")) if collector_results.get("social") else None
        papers_data = json.dumps(collector_results.get("papers")) if collector_results.get("papers") else None
        patents_data = json.dumps(collector_results.get("patents")) if collector_results.get("patents") else None
        news_data = json.dumps(collector_results.get("news")) if collector_results.get("news") else None
        finance_data = json.dumps(collector_results.get("finance")) if collector_results.get("finance") else None

        # Serialize per-source analyses from DeepSeek
        per_source_analyses_data = json.dumps(analysis.get("per_source_analyses")) if analysis.get("per_source_analyses") else None

        # Insert into database
        query = """
            INSERT INTO analyses (
                keyword, phase, confidence, reasoning,
                social_data, papers_data, patents_data, news_data, finance_data,
                per_source_analyses_data,
                expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            keyword,
            analysis["phase"],
            analysis["confidence"],
            analysis["reasoning"],
            social_data,
            papers_data,
            patents_data,
            news_data,
            finance_data,
            per_source_analyses_data,
            expires_at.isoformat()
        )

        await db.execute(query, params)
        await db.commit()

        return {
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat()
        }

    def _assemble_response(
        self,
        keyword: str,
        analysis: Dict[str, Any],
        collector_results: Dict[str, Optional[Dict[str, Any]]],
        collector_errors: List[str],
        cache_hit: bool,
        created_at: str,
        expires_at: str
    ) -> Dict[str, Any]:
        """
        Assemble comprehensive response with all data.

        Args:
            keyword: Technology keyword
            analysis: DeepSeek analysis result
            collector_results: Raw collector data
            collector_errors: List of collector error messages
            cache_hit: Whether result came from cache
            created_at: ISO timestamp of analysis
            expires_at: ISO timestamp of cache expiration

        Returns:
            Complete response dict
        """
        # Count successful collectors
        collectors_succeeded = sum(1 for r in collector_results.values() if r is not None)

        # Combine errors from collectors and analysis
        all_errors = collector_errors.copy()
        if "errors" in analysis:
            all_errors.extend(analysis["errors"])

        # Build comprehensive response
        response = {
            "keyword": keyword,
            "phase": analysis["phase"],
            "confidence": analysis["confidence"],
            "reasoning": analysis["reasoning"],
            "timestamp": created_at,
            "cache_hit": cache_hit,
            "expires_at": expires_at,

            # Per-source breakdowns from DeepSeek
            "per_source_analyses": analysis.get("per_source_analyses", {}),

            # Raw collector data (for transparency/debugging)
            "collector_data": collector_results,

            # Error tracking
            "collectors_succeeded": collectors_succeeded,
            "partial_data": collectors_succeeded < 5,
            "errors": all_errors
        }

        return response
