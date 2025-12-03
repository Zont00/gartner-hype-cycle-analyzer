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

        # Track query expansion metadata
        query_expansion_applied = False
        expanded_terms = []

        # Check if niche technology
        successful = [r for r in collector_results.values() if r is not None]
        is_niche = self._detect_niche(collector_results)

        if is_niche:
            # Apply query expansion for all niche technologies
            logger.info(f"Niche technology detected ({len(successful)}/5 collectors initially). Applying query expansion...")
            collector_results, collector_errors, expanded_terms = await self._expand_query_and_rerun(
                keyword, collector_results, collector_errors
            )

            # Recount successful collectors after expansion
            successful = [r for r in collector_results.values() if r is not None]
            if expanded_terms:
                query_expansion_applied = True
                logger.info(f"Query expansion completed. Now {len(successful)}/5 collectors succeeded.")

        # Check minimum threshold after potential expansion
        if len(successful) < self.MINIMUM_SOURCES_REQUIRED:
            raise Exception(
                f"Insufficient data: only {len(successful)}/5 collectors succeeded. "
                f"Minimum {self.MINIMUM_SOURCES_REQUIRED} required. "
                f"Errors: {collector_errors}"
            )

        # Run DeepSeek analysis
        analyzer = DeepSeekAnalyzer(api_key=self.settings.deepseek_api_key)
        analysis = await analyzer.analyze(keyword, collector_results)

        # Persist to database with query expansion metadata
        result = await self._persist_result(
            keyword, analysis, collector_results, db,
            query_expansion_applied=query_expansion_applied,
            expanded_terms=expanded_terms
        )

        # Assemble final response
        return self._assemble_response(
            keyword=keyword,
            analysis=analysis,
            collector_results=collector_results,
            collector_errors=collector_errors,
            cache_hit=False,
            created_at=result["created_at"],
            expires_at=result["expires_at"],
            query_expansion_applied=query_expansion_applied,
            expanded_terms=expanded_terms
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

                # Retrieve query expansion metadata
                try:
                    query_expansion_applied = bool(row.get("query_expansion_applied", 0))
                    raw_expanded_terms = row.get("expanded_terms_data")
                    expanded_terms = json.loads(raw_expanded_terms) if raw_expanded_terms else []
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to deserialize expanded_terms for {keyword}: {e}")
                    query_expansion_applied = False
                    expanded_terms = []

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
                    expires_at=row["expires_at"],
                    query_expansion_applied=query_expansion_applied,
                    expanded_terms=expanded_terms
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

    def _detect_niche(self, collector_results: Dict[str, Optional[Dict[str, Any]]]) -> bool:
        """
        Detect if technology is niche based on social media metrics.

        Uses SocialCollector data as primary niche detection signal:
        - mentions_30d < 50 OR mentions_total < 100

        Args:
            collector_results: Results from all collectors

        Returns:
            True if technology appears to be niche, False otherwise
        """
        social_data = collector_results.get("social")
        if not social_data:
            # No social data, can't detect - assume not niche
            return False

        mentions_30d = social_data.get("mentions_30d", 0)
        mentions_total = social_data.get("mentions_total", 0)

        # Niche criteria from task requirements
        is_niche = mentions_30d < 50 or mentions_total < 100

        if is_niche:
            logger.info(
                f"Niche technology detected: mentions_30d={mentions_30d}, "
                f"mentions_total={mentions_total}"
            )

        return is_niche

    async def _expand_query_and_rerun(
        self,
        keyword: str,
        collector_results: Dict[str, Optional[Dict[str, Any]]],
        errors: List[str]
    ) -> tuple[Dict[str, Optional[Dict[str, Any]]], List[str], List[str]]:
        """
        Expand query using DeepSeek and re-run collectors with broader terms.

        Workflow:
        1. Use DeepSeek to generate 3-5 related search terms
        2. Re-run 4 collectors (Social, Papers, Patents, News) with expanded queries
        3. Skip FinanceCollector (already uses DeepSeek for ticker discovery)

        Args:
            keyword: Original technology keyword
            collector_results: Initial collector results (may have failures)
            errors: Initial error list

        Returns:
            Tuple of (updated_collector_results, updated_errors, expanded_terms)
        """
        logger.info(f"Attempting query expansion for niche keyword: {keyword}")

        # Step 1: Generate expanded terms via DeepSeek
        expanded_terms = []
        try:
            analyzer = DeepSeekAnalyzer(api_key=self.settings.deepseek_api_key)
            expanded_terms = await analyzer.generate_expanded_terms(keyword)
            logger.info(f"Generated expanded terms: {expanded_terms}")
        except Exception as e:
            error_msg = f"Query expansion failed: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)
            # Return original results if expansion fails
            return collector_results, errors, []

        # Step 2: Re-instantiate collectors (only 4, NOT Finance)
        collectors_to_rerun = {
            "social": SocialCollector(),
            "papers": PapersCollector(),
            "patents": PatentsCollector(),
            "news": NewsCollector()
        }

        # Step 3: Re-run collectors with expanded terms
        tasks = [
            collector.collect(keyword, expanded_terms=expanded_terms)
            for collector in collectors_to_rerun.values()
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.COLLECTOR_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.warning(f"Expanded query timeout after {self.COLLECTOR_TIMEOUT_SECONDS} seconds")
            errors.append(f"Query expansion: Timeout after {self.COLLECTOR_TIMEOUT_SECONDS}s")
            # Return original results on timeout
            return collector_results, errors, expanded_terms

        # Step 4: Update collector_results with expanded query results
        for source_name, result in zip(collectors_to_rerun.keys(), results):
            if isinstance(result, Exception):
                error_msg = f"Query expansion: {source_name} collector failed: {str(result)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                # Keep original result if re-run failed
            else:
                # Update with expanded query result
                collector_results[source_name] = result
                logger.info(f"Query expansion: {source_name} collector succeeded with expanded terms")

        # Step 5: Log final status
        successful = [r for r in collector_results.values() if r is not None]
        logger.info(
            f"After query expansion: {len(successful)}/5 collectors succeeded "
            f"(expanded terms: {expanded_terms})"
        )

        return collector_results, errors, expanded_terms

    async def _persist_result(
        self,
        keyword: str,
        analysis: Dict[str, Any],
        collector_results: Dict[str, Optional[Dict[str, Any]]],
        db: aiosqlite.Connection,
        query_expansion_applied: bool = False,
        expanded_terms: List[str] = None
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

        # Serialize query expansion data
        expanded_terms_data = json.dumps(expanded_terms) if expanded_terms else None

        # Insert into database
        query = """
            INSERT INTO analyses (
                keyword, phase, confidence, reasoning,
                social_data, papers_data, patents_data, news_data, finance_data,
                per_source_analyses_data,
                query_expansion_applied, expanded_terms_data,
                expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if query_expansion_applied else 0,  # INTEGER boolean
            expanded_terms_data,
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
        expires_at: str,
        query_expansion_applied: bool = False,
        expanded_terms: List[str] = None
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
            query_expansion_applied: Whether query expansion was used
            expanded_terms: List of expanded search terms (None if not used)

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
            "errors": all_errors,

            # Query expansion metadata
            "query_expansion_applied": query_expansion_applied,
            "expanded_terms": expanded_terms if expanded_terms else []
        }

        return response
