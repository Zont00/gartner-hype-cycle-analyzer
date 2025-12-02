---
name: h-implement-hype-classifier
branch: feature/hype-classifier
status: completed
created: 2025-11-25
---

# Hype Cycle Classifier - Main Orchestration Logic

## Problem/Goal
Implement the main HypeCycleClassifier orchestration logic for the Gartner Hype Cycle Analyzer. This module coordinates the entire analysis workflow: it triggers all 5 data collectors in parallel (social, papers, patents, news, finance), passes each collector's data to DeepSeek for individual source analysis, then synthesizes all 5 analyses into a final hype cycle classification. It handles caching (check SQLite before collecting), error recovery (graceful degradation if a collector fails), and returns the complete analysis result with per-source breakdowns and final positioning. This is the core intelligence orchestrator that ties all components together.

## Success Criteria
- [x] `backend/app/analyzers/hype_classifier.py` module created with HypeCycleClassifier class (290 lines)
- [x] Parallel execution of all 5 collectors (social, papers, patents, news, finance) using asyncio
- [x] Per-source analysis: passes each collector's data to DeepSeek for individual classification
- [x] Final synthesis: aggregates 5 source analyses into one final hype cycle position
- [x] Cache checking: queries SQLite before running collectors to avoid redundant API calls
- [x] Graceful degradation: analysis proceeds even if 1-2 collectors fail (with reduced confidence)
- [x] Returns complete analysis result with source breakdowns and final classification
- [x] Unit tests with mocked collectors and DeepSeek responses (12 tests passing)

## Context Manifest

### How the Current System Works: Data Collection and Analysis Architecture

The Gartner Hype Cycle Analyzer follows a modular, async-first architecture where data collection is completely decoupled from analysis. The system has five fully-implemented data collectors that inherit from `BaseCollector` (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py), each implementing a single async method `collect(keyword: str) -> Dict[str, Any]`. These collectors are:

**1. SocialCollector** (social.py, 368 lines): Queries Hacker News Algolia API across three non-overlapping time windows (30d, 6m, 1y). Returns mention counts, engagement metrics (avg_points, avg_comments), sentiment score (-1.0 to 1.0 via tanh normalization), and derived insights (growth_trend, momentum, recency). All errors are caught gracefully - if API calls fail, it returns a valid response dict with zero values and populated "errors" list. Never raises exceptions.

**2. PapersCollector** (papers.py, 448 lines): Queries Semantic Scholar bulk search API with quote-wrapped keywords for exact phrase matching (critical pattern: `query: f'"{keyword}"'` prevents false positives). Fetches publications across 2y and 5y windows, calculates citation velocity, research maturity (emerging/developing/mature), momentum, breadth metrics. Uses .get() with defaults for all API field access to prevent KeyError. Optional API key via x-api-key header from settings.semantic_scholar_api_key.

**3. PatentsCollector** (patents.py, 573 lines): Queries PatentsView Search API with CRITICAL manual URL encoding pattern (httpx params dict doesn't work - must use urllib.parse.quote on JSON-stringified params). Uses `_text_all` operator (not _text_any) to ensure ALL keywords present in patent_title or patent_abstract, reducing false positives by 96%. Requires API key via X-Api-Key header (settings.patentsview_api_key). Fetches 2y, 5y, 10y windows, returns assignee diversity, geographic distribution, citation counts, filing velocity.

**4. NewsCollector** (news.py, 499 lines): Queries GDELT Doc API v2 (no API key needed - open access). Makes THREE parallel API calls per time period (ArtList for metadata, TimelineVol for trends, ToneChart for sentiment distribution). Quote-wraps keywords like PapersCollector. Returns article counts, tone metrics (avg_tone on -1.0 to 1.0 scale, tone_distribution), geographic diversity, domain diversity, derived insights (media_attention, coverage_trend, mainstream_adoption).

**5. FinanceCollector** (finance.py, 579 lines): UNIQUE TWO-STAGE PATTERN - first calls DeepSeek LLM to map keyword to 5-10 stock tickers (instance-level cache via _ticker_cache dict), then fetches Yahoo Finance data via yfinance library. CRITICAL: yfinance is synchronous, so wraps all operations in ThreadPoolExecutor with loop.run_in_executor for async compatibility. Returns tuple pattern (data, errors) from sync functions for thread-safe error collection. Fetches 1m, 6m, 2y windows, calculates price changes, volatility (annualized std dev), volume trends, market maturity.

All collectors follow consistent error handling: they NEVER raise exceptions. Instead, they accumulate errors in an "errors" list field, return valid response dicts with zero/unknown values on total failure, and include partial data when some API calls succeed but others fail. This graceful degradation is CRITICAL for the orchestrator.

**DeepSeek Analyzer Architecture** (deepseek.py, 439 lines): Implements TWO-STAGE LLM analysis. The `analyze(keyword, collector_data)` method:

Stage 1 (Lines 76-88): Iterates through 5 source names ["social", "papers", "patents", "news", "finance"], calls `_analyze_source()` for each, which builds specialized prompt via source-specific methods (_build_social_prompt, _build_papers_prompt, etc.). Each prompt includes full PHASE_DEFINITIONS string, domain-specific metrics from collector data, interpretation guidance with numeric thresholds (e.g., social: innovation_trigger <50 mentions, peak >200 in 30d), and instructs DeepSeek to return JSON object with {phase, confidence, reasoning}. Uses temperature=0.3 for deterministic results.

Stage 2 (Lines 94-101): If ≥3 sources succeeded (minimum viable threshold), calls `_synthesize_analyses()` which builds synthesis prompt aggregating all per-source results with their phases/confidences/reasonings. Synthesis prompt instructs weighing by confidence scores, considering signal conflicts, and accounting for different source velocities (social/news trend faster than papers/patents).

**Response Parsing** (Lines 368-438): `_call_deepseek()` strips markdown code blocks (```json ... ```) using split/trim logic from FinanceCollector pattern, parses JSON, validates required fields [phase, confidence, reasoning], checks phase is in VALID_PHASES list, validates confidence is 0-1 float. Raises exceptions for rate limits (429), auth failures (401), timeouts, invalid JSON, missing fields, invalid phases.

**Error Handling Philosophy**: Analyzer raises exceptions (unlike collectors) because it needs ≥3 sources minimum. If <3 sources available, raises Exception with error list. If DeepSeek calls fail, raises httpx errors or ValueError. This is intentional - classifier orchestrator must handle these failures and decide retry strategy.

**Database Schema** (database.py, 36 lines): SQLite at C:\Users\Hp\Desktop\Gartner's Hype Cycle\data\hype_cycle.db with async via aiosqlite. Table `analyses` has columns:
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- keyword (TEXT NOT NULL, indexed)
- created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- phase (TEXT NOT NULL) - one of: innovation_trigger, peak, trough, slope, plateau
- confidence (REAL) - 0.0 to 1.0
- reasoning (TEXT) - LLM explanation
- social_data, papers_data, patents_data, news_data, finance_data (TEXT) - JSON strings
- expires_at (TIMESTAMP, indexed) - for cache TTL checking

Indexes on keyword and expires_at for fast cache lookups. The `get_db()` function returns async context manager that yields Connection with row_factory=aiosqlite.Row for dict-like access. `init_db()` creates schema on startup (called from main.py app.on_event("startup")).

**Configuration System** (config.py, 35 lines): Pydantic BaseSettings with @lru_cache singleton pattern via get_settings(). Loads from backend/.env file. Required: DEEPSEEK_API_KEY (for both analyzer and FinanceCollector ticker discovery). Optional: SEMANTIC_SCHOLAR_API_KEY, PATENTSVIEW_API_KEY (required for PatentsCollector but optional check is collector's responsibility), NEWS_API_KEY (unused - GDELT is open), TWITTER_BEARER_TOKEN (unused - using Hacker News instead). cache_ttl_hours defaults to 24.

**FastAPI Application Structure** (main.py, 52 lines): Creates FastAPI app with CORS middleware (allow_origins=["*"] for dev - should restrict in prod). Startup event calls init_db() to create schema. Currently includes only health router at /api prefix. Health router (health.py) provides GET /api/health endpoint that tests DB connection with "SELECT 1" query, returns {"status": "healthy/degraded", "database": "healthy/unhealthy", "version": "0.1.0"}.

### What Needs to Be Built: HypeCycleClassifier Orchestration Layer

The missing piece is a stateful orchestrator class `HypeCycleClassifier` that will live in `backend/app/analyzers/hype_classifier.py` (NEW FILE). This class coordinates the entire analysis workflow:

**Orchestration Flow**:

1. **Cache Check Phase**: Accept keyword input, query database for existing analysis where keyword matches AND expires_at > current_timestamp. If cache hit found, return cached result immediately (avoid all collector/LLM calls). Cache TTL comes from settings.cache_ttl_hours (default 24 hours).

2. **Parallel Collection Phase**: If cache miss, instantiate all 5 collectors (SocialCollector(), PapersCollector(), PatentsCollector(), NewsCollector(), FinanceCollector()). Execute all 5 collect() methods in parallel using `asyncio.gather(*tasks, return_exceptions=True)` pattern (same as FinanceCollector line 295). This pattern is CRITICAL - return_exceptions=True prevents one collector failure from cancelling others. Gather results and check if each is Exception or valid dict.

3. **Error Tolerance Strategy**: The system MUST proceed with partial data. Minimum viable threshold: ≥3 successful collectors (matching DeepSeekAnalyzer's requirement at line 90). If <3 collectors succeed, raise exception indicating insufficient data. If ≥3 succeed, continue with partial data and track which collectors failed for error reporting.

4. **DeepSeek Analysis Phase**: Construct collector_data dict with keys ["social", "papers", "patents", "news", "finance"] mapping to collector results (or None/empty dict for failed collectors). Instantiate DeepSeekAnalyzer with settings.deepseek_api_key (from get_settings()). Call analyzer.analyze(keyword, collector_data) which returns dict with {phase, confidence, reasoning, per_source_analyses, errors}. This makes 6 total LLM calls (5 per-source + 1 synthesis).

5. **Database Persistence Phase**: Calculate expires_at timestamp as current time + timedelta(hours=settings.cache_ttl_hours). Serialize each collector result dict to JSON string using json.dumps() for storage in TEXT columns (social_data, papers_data, etc.). Insert new row into analyses table with all fields populated. Commit transaction. This cache enables instant responses for repeated keyword queries within TTL window.

6. **Response Assembly**: Return comprehensive result dict containing final classification (phase, confidence, reasoning), per-source breakdowns (from per_source_analyses), raw collector data (for transparency), metadata (timestamp, keyword, cache status), and error tracking (which collectors failed, any LLM errors).

**Critical Implementation Patterns**:

**Parallel Execution Pattern**: Must use asyncio.gather with return_exceptions=True, then iterate results checking `isinstance(result, Exception)`. Pattern from FinanceCollector lines 289-310 shows proper exception handling in gather results.

**Settings Access**: Import get_settings from app.config, call once to get cached singleton, access settings.deepseek_api_key, settings.cache_ttl_hours. Never instantiate Settings() directly.

**Database Operations**: Use async context manager: `async with db.execute(query, params) as cursor:` then `await cursor.fetchone()` or `await cursor.fetchall()`. For writes, must call `await db.commit()`. Row access via dict-like syntax if row_factory=aiosqlite.Row is set (which it is in get_db()).

**JSON Serialization**: All collector dicts are already JSON-serializable (they avoid datetime objects per collector requirement comment). Use json.dumps(data) for DB storage, json.loads(text) for retrieval. Handle None values gracefully (collectors may be None if they failed).

**Error Response Structure**: Include "errors" list at top level with detailed messages like "SocialCollector failed: timeout", "PatentsCollector failed: missing API key". Also include "partial_data" boolean flag and "collectors_succeeded" count for transparency.

**Graceful Degradation Examples**:
- If only SocialCollector fails but other 4 succeed: proceed, confidence may be slightly lower, note in errors list
- If FinanceCollector and NewsCollector fail (3 remain): proceed at minimum threshold
- If PatentsCollector, NewsCollector, FinanceCollector fail (only 2 remain): raise exception "Insufficient data: only 2/5 collectors succeeded"
- If DeepSeek API fails during synthesis after per-source analysis: this is unrecoverable, raise exception, don't cache partial result

**Testing Patterns** (from test_deepseek_analyzer.py): Use pytest.mark.asyncio, mock httpx.AsyncClient responses with AsyncMock, mock collector instantiation and collect() methods to return test data dicts, mock database operations to avoid actual DB I/O, test cache hit vs cache miss paths separately, test partial failure scenarios (3/5, 4/5 collectors succeed), test complete failure (<3 collectors), test DeepSeek failures (401, 429, timeout), verify JSON serialization of final result.

### Technical Reference Details

#### Class Structure

```python
# backend/app/analyzers/hype_classifier.py (NEW FILE)
from typing import Dict, Any, Optional, List
import asyncio
import aiosqlite
from datetime import datetime, timedelta
import json

from app.collectors.social import SocialCollector
from app.collectors.papers import PapersCollector
from app.collectors.patents import PatentsCollector
from app.collectors.news import NewsCollector
from app.collectors.finance import FinanceCollector
from app.analyzers.deepseek import DeepSeekAnalyzer
from app.config import get_settings
from app.database import get_db

class HypeCycleClassifier:
    """
    Orchestrates hype cycle classification workflow:
    1. Check database cache
    2. Parallel collector execution
    3. DeepSeek analysis
    4. Result persistence
    """

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
        collector_results = await self._run_collectors(keyword)

        # Check minimum threshold
        successful = [r for r in collector_results.values() if r is not None]
        if len(successful) < 3:
            raise Exception(f"Insufficient data: only {len(successful)}/5 collectors succeeded")

        # Run DeepSeek analysis
        analyzer = DeepSeekAnalyzer(api_key=self.settings.deepseek_api_key)
        analysis = await analyzer.analyze(keyword, collector_results)

        # Persist to database
        result = await self._persist_result(keyword, analysis, collector_results, db)

        return result
```

#### Database Query Patterns

**Cache Check**:
```python
query = """
    SELECT * FROM analyses
    WHERE keyword = ? AND expires_at > ?
    ORDER BY created_at DESC
    LIMIT 1
"""
params = (keyword, datetime.now().isoformat())
async with db.execute(query, params) as cursor:
    row = await cursor.fetchone()
    if row:
        return self._row_to_dict(row)
```

**Insert Result**:
```python
query = """
    INSERT INTO analyses (
        keyword, phase, confidence, reasoning,
        social_data, papers_data, patents_data, news_data, finance_data,
        expires_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
expires_at = datetime.now() + timedelta(hours=self.settings.cache_ttl_hours)
params = (
    keyword,
    analysis["phase"],
    analysis["confidence"],
    analysis["reasoning"],
    json.dumps(collector_results.get("social")),
    json.dumps(collector_results.get("papers")),
    json.dumps(collector_results.get("patents")),
    json.dumps(collector_results.get("news")),
    json.dumps(collector_results.get("finance")),
    expires_at.isoformat()
)
await db.execute(query, params)
await db.commit()
```

#### Parallel Collector Execution Pattern

```python
async def _run_collectors(self, keyword: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """Run all collectors in parallel, return dict mapping source names to results"""
    collectors = {
        "social": SocialCollector(),
        "papers": PapersCollector(),
        "patents": PatentsCollector(),
        "news": NewsCollector(),
        "finance": FinanceCollector()
    }

    tasks = [collector.collect(keyword) for collector in collectors.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    collector_results = {}
    errors = []
    for source_name, result in zip(collectors.keys(), results):
        if isinstance(result, Exception):
            errors.append(f"{source_name}: {str(result)}")
            collector_results[source_name] = None
        else:
            collector_results[source_name] = result

    return collector_results
```

#### Response Structure

```python
{
    "keyword": "quantum computing",
    "phase": "peak",
    "confidence": 0.82,
    "reasoning": "Strong signals across all sources...",
    "timestamp": "2025-12-02T10:30:00",
    "cache_hit": False,
    "expires_at": "2025-12-03T10:30:00",

    # Per-source breakdowns from DeepSeek
    "per_source_analyses": {
        "social": {"phase": "peak", "confidence": 0.85, "reasoning": "..."},
        "papers": {"phase": "slope", "confidence": 0.78, "reasoning": "..."},
        # ... etc
    },

    # Raw collector data (optional, for debugging/transparency)
    "collector_data": {
        "social": {"mentions_30d": 250, "sentiment": 0.72, ...},
        "papers": {"publications_2y": 120, ...},
        # ... etc
    },

    # Error tracking
    "collectors_succeeded": 5,
    "errors": []  # Empty if all succeeded
}
```

#### File Locations

- Implementation: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py` (NEW FILE)
- Tests: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_hype_classifier.py` (NEW FILE)
- Integration point: Will be imported by analysis router (not yet implemented): `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py` (FUTURE)

#### Dependencies Already Available

All imports already installed in venv (see requirements.txt):
- asyncio (stdlib)
- aiosqlite==0.21.0 (async SQLite)
- httpx (for collectors, already used)
- json (stdlib)
- datetime (stdlib)

No new pip installs needed.

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log

### 2025-12-02

#### Completed
- Implemented `backend/app/analyzers/hype_classifier.py` (290 lines)
- Created HypeCycleClassifier class with complete orchestration workflow
- Implemented cache-first strategy with SQLite (checks expires_at before running collectors)
- Implemented parallel collector execution using asyncio.gather(return_exceptions=True)
- Implemented minimum threshold validation (requires ≥3 of 5 collectors)
- Integrated DeepSeekAnalyzer with two-stage analysis (5 per-source + 1 synthesis)
- Implemented database persistence with JSON serialization for collector data
- Implemented comprehensive response assembly with metadata, errors, and per-source analyses
- Created `backend/tests/test_hype_classifier.py` with 12 passing tests
- Comprehensive test coverage: initialization, cache hit/miss, partial failures, error handling, JSON serialization
- Fixed async context manager mocking issue in test_classify_with_cache_hit
- Created `backend/test_real_classification.py` for real-world integration testing

#### Technical Decisions
- Used asyncio.gather(return_exceptions=True) pattern for parallel execution without cascade failures
- Async context managers for database operations to prevent connection leaks
- Instance-level settings via get_settings() cached singleton
- Error aggregation from collectors and analyzer into unified errors list
- Tuple return pattern from _run_collectors for clean separation of data and errors
- MagicMock for database mocks (not AsyncMock) - db.execute returns cursor synchronously for async with usage

#### Discovered
- Database mock setup required careful handling of async context managers
- db.execute() returns cursor directly (not awaited), cursor itself is async context manager
- Mock pattern: `mock_db.execute = Mock(return_value=mock_cursor)` where mock_cursor has `__aenter__` and `__aexit__`
- All 12 tests passing after fixing async mock configuration
- Real-world test script created for validation with actual API calls

#### Next Steps
- Complete real-world testing with quantum computing keyword (in progress)
- Fix Unicode encoding issues in test script for Windows terminals
- Create analysis router for REST API endpoint
- Update task success criteria checkboxes
