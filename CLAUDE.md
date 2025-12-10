# Gartner Hype Cycle Analyzer - Developer Guide

This project analyzes emerging technologies and positions them on Gartner's Hype Cycle using parallel data collection from five sources combined with LLM-based classification.

## Additional Guidance

@sessions/CLAUDE.sessions.md

This file provides instructions for Claude Code for working in the cc-sessions framework.

## Architecture Overview

### System Design

The application follows a three-tier architecture:

1. **Frontend Layer**: Vanilla HTML/JS interface with Canvas-based visualization
2. **Backend Layer**: FastAPI REST API with async collectors and analyzers
3. **Data Layer**: SQLite database for caching analysis results

### Request Flow

1. User enters technology keyword in web interface (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html)
2. Frontend calls POST /api/analyze endpoint (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py)
3. HypeCycleClassifier orchestrator receives request (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py)
4. Orchestrator checks SQLite cache for recent analysis (WHERE keyword = ? AND expires_at > current_timestamp)
5. On cache miss, five collectors run in parallel via asyncio.gather(return_exceptions=True) with 120s timeout:
   - Social Media Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py) - IMPLEMENTED
   - Research Papers Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py) - IMPLEMENTED
   - Patent Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py) - IMPLEMENTED
   - News Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\news.py) - IMPLEMENTED
   - Financial Data Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\finance.py) - IMPLEMENTED
6. **Niche Detection & Query Expansion** (IMPLEMENTED - hype_classifier.py:240-353):
   - Orchestrator detects niche technologies via social metrics (mentions_30d < 50 OR mentions_total < 100)
   - For niche technologies, DeepSeek generates 3-5 related search terms (e.g., "plant cell culture" → ["plant tissue culture", "in vitro propagation", "micropropagation", "callus culture", "somatic embryogenesis"])
   - Re-runs 4 collectors (Social, Papers, Patents, News) with expanded queries using OR logic
   - FinanceCollector NOT re-run (already uses DeepSeek for ticker discovery)
   - Validation tested: "plant cell culture" improved from 93 → 2,535 papers (+2,626%), 87 → 942 patents (+983%), 1 → 11 social mentions (+1,000%)
   - Query expansion metadata tracked in response (query_expansion_applied: bool, expanded_terms: List[str])
7. Orchestrator validates minimum 3 of 5 collectors succeeded (graceful degradation) - now more likely to succeed after query expansion
8. DeepSeek analyzer performs two-stage classification: 5 per-source analyses + 1 final synthesis (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py)
9. Orchestrator persists result to database with 24-hour cache TTL, JSON-serialized collector data, plus query expansion metadata
10. Comprehensive response assembled with phase, confidence, reasoning, per-source analyses, collector data, metadata, errors, and query expansion details
11. Result returned to frontend
12. Frontend renders hype cycle curve visualization with technology position marker, displays per-source analyses breakdowns, status indicators, and comprehensive error handling

## Key Components

### Backend (FastAPI)

**Main Application** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\main.py)
- FastAPI instance with CORS middleware for cross-origin requests
- Startup event initializes database schema
- Includes health router and analysis router at /api prefix
- Auto-generated API docs at /api/docs and /api/redoc

**Configuration** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py)
- Uses pydantic-settings for type-safe environment variable loading
- Cached singleton pattern via @lru_cache
- Loads from .env file in backend/ directory
- Required: DEEPSEEK_API_KEY, PATENTSVIEW_API_KEY
- Optional: NEWS_API_KEY, TWITTER_BEARER_TOKEN, GOOGLE_SCHOLAR_API_KEY, SEMANTIC_SCHOLAR_API_KEY

**Database** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py)
- Async SQLite via aiosqlite (non-blocking for FastAPI)
- Database file: C:\Users\Hp\Desktop\Gartner's Hype Cycle\data\hype_cycle.db
- Schema: analyses table with keyword, phase, confidence, reasoning, collector data (JSON), per_source_analyses_data (JSON), timestamps
- Indexes on keyword and expires_at for fast cache lookups
- get_db() provides async context manager for connections
- Idempotent migration system: Automatically adds missing columns on startup via PRAGMA table_info check

**Health Check Router** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\health.py)
- GET /api/health endpoint
- Tests database connectivity
- Returns status: healthy/degraded, database: healthy/unhealthy, version: 0.1.0

**Analysis Router** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py) - IMPLEMENTED
- POST /api/analyze endpoint - main entry point for technology analysis
- Request validation: Pydantic AnalyzeRequest model with keyword field (min_length=1, max_length=100, whitespace stripping)
- Response structure: Pydantic AnalyzeResponse model matching HypeCycleClassifier output (15 fields total including query expansion metadata)
- **Query Expansion Fields** (IMPLEMENTED - analysis.py:54-55): query_expansion_applied (bool), expanded_terms (List[str]) in response model
- Integrates with HypeCycleClassifier via dependency injection pattern
- Database connection: async aiosqlite.Connection via Depends(get_db)
- Error handling:
  - HTTP 422 Unprocessable Entity: Automatic validation errors (empty keyword, too long, invalid JSON) - handled by FastAPI/Pydantic
  - HTTP 503 Service Unavailable: Insufficient data (<3 collectors succeeded) - temporary condition with detailed error message (less common now with query expansion)
  - HTTP 500 Internal Server Error: Unexpected errors (database failures, DeepSeek API errors, etc.)
- Performance characteristics:
  - Fresh analysis (mainstream): ~48 seconds (5 collectors + 6 DeepSeek LLM calls)
  - Fresh analysis (niche with expansion): ~60-70 seconds (initial 5 collectors + expansion call + 4 collector re-runs + 6 DeepSeek LLM calls)
  - Cache hit: <1 second (database query only)
  - Cache TTL: 24 hours (configurable via CACHE_TTL_HOURS env var)
- Comprehensive OpenAPI documentation with examples for all HTTP status codes (200, 422, 500, 503)
- Logging: info level for successful analyses, warning for insufficient data, exception tracebacks for unexpected errors
- Returns complete analysis with phase, confidence, reasoning, per-source analyses, collector data, metadata, error tracking, and query expansion details

**Base Collector Interface** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py)
- Abstract base class defining collect(keyword, expanded_terms) -> Dict[str, Any]
- All collectors inherit from BaseCollector
- Standardized return structure for LLM consumption
- **Query Expansion Support** (IMPLEMENTED): Optional expanded_terms parameter (List[str]) for niche query expansion
  - When provided, collectors search for original keyword OR any expanded term
  - Enables broader data collection for niche technologies with low initial results

**Social Media Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py) - IMPLEMENTED
- Queries Hacker News Algolia API (https://hn.algolia.com/api/v1/search)
- Time-series analysis across three periods: 30 days, 6 months, 1 year (non-overlapping windows)
- Metrics returned: mentions_30d, mentions_6m, mentions_1y, mentions_total
- **Niche Detection Metrics**: mentions_30d and mentions_total are PRIMARY niche detection signals (mentions_30d < 50 OR mentions_total < 100 triggers query expansion)
- Engagement: avg_points_30d, avg_comments_30d, avg_points_6m, avg_comments_6m
- Derived insights: sentiment (-1.0 to 1.0), recency (high/medium/low), growth_trend (increasing/stable/decreasing), momentum (accelerating/steady/decelerating)
- Returns top 5 stories with titles, points, comments, age for LLM context
- **Query Expansion Support** (IMPLEMENTED - social.py:157-267): When expanded_terms provided, aggregates results from multiple API calls (keyword + each expanded term), deduplicates by objectID
- Graceful error handling - never raises exceptions, returns fallback data on failures
- Errors tracked in "errors" field for partial failure visibility
- IMPORTANT: Uses HTTPS endpoint (HTTP causes 301 redirect)
- Test suite: 14 passing tests covering success, errors, edge cases (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_social_collector.py)

**Research Papers Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py) - IMPLEMENTED
- Queries Semantic Scholar API bulk search endpoint (https://api.semanticscholar.org/graph/v1/paper/search/bulk)
- Time-windowed analysis: 2-year, 5-year, and 10-year periods (non-overlapping windows matching academic publishing cycles)
- Period structure: 2y (current_year-2 to current_year-1), 5y (current_year-7 to current_year-3), 10y (current_year-12 to current_year-8)
- IMPORTANT: Uses bulk endpoint with quote-wrapped keywords for exact phrase matching (reduces false positives by 99.9%)
- **Query Expansion Support** (IMPLEMENTED - papers.py:190-274): Constructs OR query with pipe separator (query: "keyword" | "term1" | "term2") per Semantic Scholar syntax
- Metrics returned: publications_2y, publications_5y, publications_10y, publications_total
- Citation metrics: avg_citations_2y, avg_citations_5y, avg_citations_10y, avg_influential_citations_2y, avg_influential_citations_5y, avg_influential_citations_10y, citation_velocity
- Research breadth: author_diversity, venue_diversity
- Author metrics: top_authors (top 10 by publication count across all periods)
- **Paper type distribution analysis**: Tracks 5 categories (Review, JournalArticle, Conference, Book, Other) using publicationTypes field
  - Returns type_counts, type_percentages, papers_with_type_info
  - 85.6% API coverage validated with real queries
  - Gracefully handles papers without type data (14.4%)
- **Enhanced research maturity**: Type-aware classification with thresholds (>30% reviews = mature, >60% conferences + <20 papers = emerging)
  - Returns maturity level with detailed reasoning: research_maturity_reasoning field explains classification logic
- Derived insights: research_maturity (emerging/developing/mature), research_momentum (accelerating/steady/decelerating), research_trend (increasing/stable/decreasing), research_breadth (narrow/moderate/broad)
- Returns top 5 papers by citation count with titles, years, citation counts, influential citations, author counts, venues for LLM context
- API key authentication: Optional via x-api-key header (configured through SEMANTIC_SCHOLAR_API_KEY env var)
- Graceful error handling with safe dictionary access using .get() to prevent KeyError on inconsistent API responses
- Handles missing fields (citationCount, authors, venue, publicationTypes may be null/missing)
- Test suite: 25 passing tests covering success, errors, edge cases, 10y period, author aggregation, paper type distribution, type-aware maturity (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_papers_collector.py)
- Real API validation: Successfully tested with "quantum computing" (13,336 papers, 79% journal/22% conference/17.5% reviews, top author: George Rajna with 17 papers)

**Patent Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py) - IMPLEMENTED
- Queries PatentsView Search API (https://search.patentsview.org/api/v1/patent/)
- Time-windowed analysis: 2-year, 5-year, and 10-year periods (non-overlapping windows matching patent filing cycles)
- CRITICAL: Requires manual URL encoding with urllib.parse.quote() - httpx params dict encoding does NOT work with this API
- API uses GET requests with JSON-stringified query parameters that must be manually URL-encoded
- Field names: patent_id (not patent_number), patent_num_times_cited_by_us_patents (for citations)
- CRITICAL: Query operator: _text_all for keyword matching in patent_title and patent_abstract fields (ensures ALL words present, prevents false positives)
- **Query Expansion Support** (IMPLEMENTED - patents.py:215-320): Constructs nested OR clauses with _or wrapping multiple _text_all clauses for each term, maintaining exact phrase matching per term
- Metrics returned: patents_2y, patents_5y, patents_10y, patents_total
- Assignee metrics: unique_assignees, top_assignees (top 5 by patent count with type classification)
- **Assignee Type Classification** (IMPLEMENTED - patents.py:555-796): Classifies assignees into 5 categories (University, Research Institute, Corporate, Government, Individual) using pattern matching on organization names and assignee_type codes
  - Pattern matching: Case-insensitive keyword matching for universities ("university", "college", "MIT", "Caltech") and research institutes ("institute", "laboratory", "Max Planck", "Fraunhofer", "NIST")
  - Type code fallback: Uses assignee_type codes (2-3: Individual, 6-7: Government, 4-5: Corporate) when pattern matching doesn't match academic institutions
  - Corporate research exceptions: "IBM Research", "Google Research", etc. classified as Corporate (not Research Institute)
  - New metrics: assignee_type_distribution (percentage breakdown), university_ratio, academic_ratio, commercialization_index (corporate/academic ratio), innovation_stage (early_research/developing/commercialized), innovation_stage_reasoning
  - Interpretation: High university ratio (>40%) indicates early research phase; corporate dominance (>70%) with low academic (<20%) indicates commercialization; balanced mix indicates transition phase
  - Commercialization index >2.0 indicates strong commercial adoption
- Geographic distribution: countries dict with patent counts, geographic_diversity
- Citation metrics: avg_citations_2y, avg_citations_5y
- Derived insights: filing_velocity, assignee_concentration (concentrated/moderate/diverse), geographic_reach (domestic/regional/global), patent_maturity (emerging/developing/mature), patent_momentum (accelerating/steady/decelerating), patent_trend (increasing/stable/decreasing)
- Returns top 5 patents sorted by citation count with patent numbers, titles, dates, assignees, countries for LLM context
- API key authentication: Required via X-Api-Key header (configured through PATENTSVIEW_API_KEY env var)
- Graceful error handling with safe dictionary access using .get() to prevent KeyError on inconsistent API responses
- Handles missing fields (assignees, assignee_country, assignee_type, citation counts may be null/missing)
- Test suite: 30 passing tests covering success, errors, edge cases, authentication, assignee classification (university/research institute/corporate/government/individual), type distribution calculation, pattern matching edge cases, innovation stage classification (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_patents_collector.py)
- Real API validation: Successfully tested with "quantum computing" using _text_all operator (889 patents found with 96% reduction in false positives, 84 unique assignees, 16 countries); assignee classification validated with CRISPR (early-stage, high university ratio) and cloud computing (mature, high corporate ratio)

**News Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\news.py) - IMPLEMENTED
- Queries GDELT Doc API v2 (https://api.gdeltproject.org/api/v2/doc/doc)
- Time-windowed analysis: 30 days, 3 months (excluding last 30d), 1 year (excluding last 3m) - matches news cycle characteristics
- IMPORTANT: Uses quote wrapping for exact phrase matching (same pattern as PapersCollector - reduces false positives by ~99%)
- **Query Expansion Support** (IMPLEMENTED - news.py:213-312): Constructs OR query with parentheses wrapper ("keyword" OR "term1" OR "term2") per GDELT syntax requirements
- Three API modes queried per time period: ArtList (article metadata), TimelineVol (volume trends), ToneChart (sentiment distribution)
- API parameters: Uses GDELT datetime format (YYYYMMDDHHMMSS), maxrecords=250 per period (750 total articles)
- Metrics returned: articles_30d, articles_3m, articles_1y, articles_total
- Geographic distribution: source_countries dict, geographic_diversity (unique country count)
- Media diversity: unique_domains, top_domains (top 5 by article count)
- Sentiment metrics: avg_tone (-1.0 to 1.0 scale), tone_distribution (positive/neutral/negative counts)
- Volume metrics: volume_intensity_30d, volume_intensity_3m, volume_intensity_1y (average intensity from timeline data)
- Derived insights: media_attention (high/medium/low based on article count thresholds), coverage_trend (increasing/stable/decreasing from volume comparison), sentiment_trend (positive/neutral/negative from tone), mainstream_adoption (mainstream/emerging/niche from domain diversity)
- Returns top 5 most recent articles with URLs, titles, domains, countries, dates for LLM context
- API key authentication: None required - GDELT is open access with no API key
- Graceful error handling with safe dictionary access using .get() to prevent KeyError on inconsistent API responses
- Handles missing fields (domain, sourcecountry, seendate may be null/missing)
- Test suite: 16 passing tests covering success, errors, edge cases, sentiment/tone calculation, trend detection (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_news_collector.py)
- Real API validation: Successfully tested with "quantum computing" (750 articles, 29 countries, 138 unique domains)

**Financial Data Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\finance.py) - IMPLEMENTED
- Queries Yahoo Finance via yfinance library with DeepSeek LLM-based ticker discovery
- Time-windowed analysis: 1 month, 6 months, 2 years (matches financial market cycles and earnings seasons)
- CRITICAL: Uses DeepSeek LLM API to intelligently map technology keywords to relevant stock ticker symbols
- Ticker discovery: Sends keyword to DeepSeek with prompt requesting 5-10 relevant tickers, falls back to tech ETFs (QQQ, XLK) on failure
- **Query Expansion NOT Applied**: Finance collector is excluded from query expansion workflow because it already uses DeepSeek for intelligent keyword mapping - applying expanded terms would be redundant and potentially confusing
- Instance-level ticker cache (_ticker_cache dict) for performance optimization - thread-safe per instance
- Ticker format validation: Regex ^[A-Z]{1,5}$ to ensure valid US stock ticker symbols
- IMPORTANT: yfinance is synchronous, wrapped in ThreadPoolExecutor for async compatibility with FastAPI event loop
- Parallel ticker data fetching with controlled concurrency (max 5 workers via ThreadPoolExecutor)
- Metrics returned: companies_found, tickers list, total_market_cap, avg_market_cap
- Price performance: avg_price_change_1m, avg_price_change_6m, avg_price_change_2y (aggregated across companies)
- Volume metrics: avg_volume_1m, avg_volume_6m, volume_trend
- Volatility metrics: avg_volatility_1m, avg_volatility_6m (annualized standard deviation of returns)
- Derived insights: market_maturity (emerging/developing/mature based on market cap + volatility), investor_sentiment (positive/neutral/negative from price trends), investment_momentum (accelerating/steady/decelerating from period comparison), volume_trend (increasing/stable/decreasing)
- Returns top 5 companies sorted by market cap with ticker, name, market cap, price changes, sector, industry for LLM context
- API key authentication: Requires DEEPSEEK_API_KEY for ticker discovery, no key needed for Yahoo Finance (yfinance scrapes public data)
- Graceful error handling with thread-safe error tracking via tuple return pattern (data, errors) from sync functions
- Explicit ThreadPoolExecutor cleanup in finally block to prevent resource leaks
- Handles missing fields in yfinance responses (marketCap, longName, sector, industry may be null/missing)
- Test suite: 17 passing tests covering success, DeepSeek integration, yfinance mocking, errors (rate limits, timeouts, missing API keys), edge cases (invalid tickers, missing data, partial failures), derived insights (maturity, sentiment, trends), instance isolation, JSON serialization (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_finance_collector.py)
- Real API validation: Successfully tested with "quantum computing" (6 companies, $7.9T market cap, developing/positive) and "plant cell culture" (5 companies, $158B market cap, mature/negative)

**DeepSeek Analyzer** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py) - IMPLEMENTED
- Two-stage LLM analysis architecture: 5 per-source classifications + 1 final synthesis (6 total API calls)
- **Query Expansion Generator** (IMPLEMENTED - deepseek.py:484-601): generate_expanded_terms(keyword) method uses DeepSeek to produce 3-5 related search terms for niche technologies
  - Temperature: 0.4 (slightly higher for term diversity while maintaining determinism)
  - Validation: Rejects generic terms (technology, system, innovation, solution, etc.), rejects duplicate of original keyword, requires 3-5 valid terms
  - Example expansions: "plant cell culture" → ["plant tissue culture", "in vitro propagation", "micropropagation", "callus culture", "somatic embryogenesis"]
  - Used by HypeCycleClassifier._expand_query_and_rerun() workflow
  - **Robust JSON Parsing** (IMPLEMENTED - deepseek.py:547-559): Uses _extract_json_from_markdown() helper with try-except error handling, logs raw content (truncated to 500 chars) on parsing failures
- Classifies technologies into 5 Gartner Hype Cycle phases:
  - innovation_trigger: Innovation Trigger
  - peak: Peak of Inflated Expectations
  - trough: Trough of Disillusionment
  - slope: Slope of Enlightenment
  - plateau: Plateau of Productivity
- API endpoint: https://api.deepseek.com/v1/chat/completions (OpenAI-compatible)
- Authentication: Bearer token via Authorization header (configured through DEEPSEEK_API_KEY env var)
- Temperature: 0.3 (lower for more deterministic classification results)
- Timeout: 60.0 seconds (LLM calls can be slow)
- analyze(keyword, collector_data) returns {"phase": str, "confidence": float, "reasoning": str, "per_source_analyses": dict}
- Specialized prompt templates for each data source:
  - Social media prompt: focuses on mentions, engagement, sentiment, growth trends with thresholds (innovation_trigger: <50 mentions, peak: >200 in 30d)
  - Academic research prompt: focuses on publications, citations, research maturity/momentum with thresholds (innovation_trigger: <10 papers in 2y, peak: accelerating publications)
  - Patent prompt: focuses on filing velocity, assignee concentration, geographic reach with thresholds (innovation_trigger: <10 patents in 2y, peak: >20 assignees)
  - News prompt: focuses on media attention, coverage trends, sentiment, mainstream adoption with thresholds (innovation_trigger: <50 articles, peak: >500 articles)
  - Finance prompt: focuses on market maturity, investor sentiment, investment momentum with thresholds (innovation_trigger: <3 companies, peak: strong positive returns)
- Each prompt includes full Gartner Hype Cycle phase definitions and interpretation guidance
- Synthesis prompt: aggregates all 5 source analyses, weighs by confidence scores, handles conflicting signals
- **Robust JSON Parsing** (IMPLEMENTED - deepseek.py:53-88): _extract_json_from_markdown(content) helper method handles all edge cases:
  - Markdown-wrapped with language tag: ```json\n{...}\n```
  - Markdown-wrapped without language tag: ```\n{...}\n```
  - Bare JSON: {...}
  - Text before/after code blocks: "Some text ```json {...}``` more text"
  - Multiple code blocks (grabs first JSON object)
  - Uses regex pattern r'```(?:json)?\s*(\{.*?\})\s*```|(\{.*?\})' with DOTALL flag for reliable extraction
  - Raises ValueError with content preview (truncated to 200 chars) if no JSON found
- **Enhanced Error Handling** (IMPLEMENTED - deepseek.py:454-466, 547-559):
  - JSON parsing wrapped in try-except blocks in both _call_deepseek() and generate_expanded_terms() methods
  - Logs raw content (truncated to 500 chars) at ERROR level when parsing fails for debugging
  - Re-raises ValueError with content snippet (first 200 chars) in error message for immediate visibility
  - Module-level logger instance (deepseek.py:11-12) following codebase logging patterns
- Validation: checks phase is one of 5 valid values, confidence is 0-1 float, all required fields present
- Error handling: rate limits (429), authentication failures (401), timeouts, invalid JSON responses, missing fields, invalid phases
- Graceful degradation: continues with ≥3 sources if some collectors fail (minimum 3 required for synthesis)
- Errors tracked in "errors" field for transparency, never raises exceptions unless < 3 sources available
- Test suite: 27 passing tests covering initialization, full analysis, per-source analysis, synthesis, error handling, edge cases, JSON serialization, markdown extraction edge cases (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_deepseek_analyzer.py)
- Real API validation: Successfully tested with "quantum computing" (all 5 sources classified as "peak", final confidence: 0.78, per-source confidence: 0.72-0.85) and "bio fuels" (previously failed, now works after JSON parsing fix)

**Hype Cycle Classifier** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py) - IMPLEMENTED
- Main orchestration layer that coordinates the entire analysis workflow
- Class constants: MINIMUM_SOURCES_REQUIRED = 3, COLLECTOR_TIMEOUT_SECONDS = 120.0
- classify(keyword, db) is the main entry point, returns comprehensive analysis dict
- Cache-first strategy: queries database for existing analysis (WHERE keyword = ? AND expires_at > current_timestamp)
- Returns cached result immediately on cache hit, avoiding all collector/LLM API calls
- Parallel collector execution: instantiates all 5 collectors, runs collect() in parallel via asyncio.gather(return_exceptions=True)
- 120-second timeout for entire collector execution batch (asyncio.wait_for wrapper)
- **Niche Detection** (IMPLEMENTED - hype_classifier.py:240-270): _detect_niche() method checks social_data for mentions_30d < 50 OR mentions_total < 100
- **Query Expansion Workflow** (IMPLEMENTED - hype_classifier.py:272-353): _expand_query_and_rerun() orchestrates expansion for niche technologies
  - Step 1: Call DeepSeekAnalyzer.generate_expanded_terms() to get 3-5 related search terms
  - Step 2: Re-instantiate 4 collectors (Social, Papers, Patents, News) - NOT Finance
  - Step 3: Re-run collectors with expanded_terms parameter, 120s timeout applies to re-run batch
  - Step 4: Update collector_results with expanded query results (keeps original if re-run fails)
  - Step 5: Recount successful collectors after expansion
  - Fallback: If expansion fails (DeepSeek error, timeout), continues with original collector results
  - Logging: Tracks niche detection, expansion attempt, success/failure of re-runs
- Graceful degradation: continues with partial data if ≥3 of 5 collectors succeed (now more achievable after query expansion)
- Raises exception if <3 collectors succeed: "Insufficient data: only X/5 collectors succeeded"
- Error aggregation: tracks which collectors failed with descriptive error messages
- DeepSeek integration: passes collector_results dict to analyzer.analyze() for two-stage classification
- Database persistence: serializes collector data, per_source_analyses, query_expansion_applied (INTEGER 0/1), expanded_terms_data (JSON array) to database TEXT columns
- Cache retrieval: deserializes per_source_analyses, query_expansion_applied, expanded_terms from database with try-except error handling
- Cache TTL: expires_at = created_at + timedelta(hours=settings.cache_ttl_hours) (default 24 hours)
- Comprehensive response structure:
  - Core classification: keyword, phase, confidence, reasoning
  - Per-source breakdowns: per_source_analyses dict from DeepSeek (5 individual classifications) - persisted to cache for consistent experience
  - Raw collector data: collector_data dict for transparency and debugging
  - Metadata: timestamp, cache_hit boolean, expires_at timestamp, query_expansion_applied boolean, expanded_terms list
  - Error tracking: collectors_succeeded count, partial_data boolean, errors list
- Logging: cache hit/miss, collector completion count, individual collector failures, niche detection, query expansion attempts
- Database operations: async context managers for cursor management (async with db.execute())
- Settings access: uses get_settings() cached singleton for configuration
- Test suite: 12 passing tests covering initialization, cache hit/miss, partial success (3/5, 4/5 collectors), insufficient data (<3 collectors), error handling, JSON serialization (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_hype_classifier.py)
- Query expansion test suite: 12 additional passing tests in backend/tests/test_query_expansion.py covering niche detection, DeepSeek integration, collector re-runs, fallback behavior
- Integration test: backend/test_real_classification.py validates end-to-end workflow with real API calls
- CRITICAL pattern: return_exceptions=True in asyncio.gather prevents one collector failure from cancelling others

### Frontend (Vanilla JS) - IMPLEMENTED

**HTML Structure** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html) - COMPLETED
- Input field for technology keyword with autocomplete disabled
- Analyze button triggering API call
- Loading state with spinner and "up to 2 minutes" message
- Status indicators section for cache status, collector counts, and expiration times
- Warning banner for partial data scenarios (hidden by default)
- Results section with:
  - Canvas-based hype cycle visualization
  - Core details display (phase, confidence, reasoning)
  - Per-source analyses section with 5 source cards
- Error display area for all HTTP error types
- Responsive design with mobile support

**JavaScript Logic** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\app.js) - COMPLETED
- API_BASE_URL: http://localhost:8000/api
- Event handlers:
  - Analyze button click with keyword validation
  - Enter key support in input field
- Core functions:
  - analyzeKeyword(keyword): Fetches POST /api/analyze, manages loading state, handles all error types
  - displayResults(data): Renders complete analysis results with all 13 response fields
  - drawHypeCycle(phase): Canvas API visualization with Bezier curve, position marker, and phase labels
- Per-source analysis display:
  - displayPerSourceAnalyses(perSourceAnalyses): Creates 5 source cards (Social, Papers, Patents, News, Finance)
  - Color-coded phase badges and confidence badges
  - Full reasoning text for each source
- Status indicators:
  - displayStatusIndicators(data): Shows cache hits, fresh analysis markers, collector success counts, expiration times
- Error handling:
  - handleErrorResponse(status, errorData): Differentiates between HTTP 422 (validation), 503 (service unavailable), 500 (internal error)
  - Network error handling with user-friendly messages
- Helper functions:
  - formatPhase(phase): Maps phase keys to display names
  - getConfidenceClass(confidence): Traffic light color classification (high ≥80%, medium 60-80%, low <60%)
- Security: All dynamic content uses textContent (not innerHTML) to prevent XSS vulnerabilities
- No framework dependencies: Pure vanilla JavaScript with modern ES6+ features

**Styling** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\styles.css) - COMPLETED
- Modern gradient background (purple to violet)
- Responsive container layout (max-width 900px, mobile-friendly)
- Loading state:
  - Spinner animation (@keyframes spin)
  - Loading note styling in subtle gray
- Status indicators:
  - Color-coded badges: blue (cache), green (fresh), purple (collectors), yellow (expiry)
  - Flexbox layout with gap and wrap
- Warning banner:
  - Yellow background with orange left border
  - Hidden by default, shown for partial data scenarios
- Per-source analyses:
  - Source cards with hover effects
  - Phase badges color-coded by Hype Cycle position:
    - innovation_trigger: blue (#3b82f6)
    - peak: red (#ef4444)
    - trough: orange (#f97316)
    - slope: yellow (#eab308)
    - plateau: green (#22c55e)
  - Confidence badges with traffic light colors (green high, yellow medium, red low)
  - Source name styling with 600 font-weight
  - Reasoning text in gray with line-height 1.6
- Canvas visualization styling (gray background, rounded corners, padding)
- Error styling (red background with darker red border)
- Responsive adjustments for mobile (<768px):
  - Vertical source card layout
  - Full-width status badges
  - Stacked header elements

**Features Implemented:**
- Complete MVP requirements fulfilled
- Accepts technology keyword input with validation
- Calls POST /api/analyze endpoint with proper error handling
- Displays loading state with realistic time expectations
- Shows comprehensive results:
  - Final hype cycle classification with canvas visualization
  - Per-source analyses breakdown for all 5 data sources
  - Status indicators for cache hits and data quality
  - Warning banners for partial data scenarios
- Comprehensive error handling:
  - HTTP 422: Displays validation error details
  - HTTP 503: Suggests retry with user-friendly message
  - HTTP 500: Shows server error details
  - Network errors: Guidance to check backend status
- Responsive design works on desktop and mobile devices
- Zero build process - works directly in browser or via simple HTTP server

## Technology Stack

- **Python**: 3.14 (note: bleeding edge version, some packages use >= constraints for compatibility)
- **FastAPI**: 0.122.0 - async web framework with automatic OpenAPI docs
- **Uvicorn**: 0.38.0 - ASGI server with --reload for development
- **Pydantic**: 2.12.4 - data validation and settings management
- **aiosqlite**: 0.21.0 - async SQLite database driver
- **httpx**: Async HTTP client for external API calls
- **yfinance**: 0.2.32 - Yahoo Finance data fetching for financial collector
- **beautifulsoup4**: HTML parsing for web scraping collectors
- **Frontend**: Vanilla HTML/JS (no build process, no frameworks)

## Development Workflow

### Running the Application

```bash
# Activate virtual environment
cd "C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend"
source venv/Scripts/activate  # Windows Git Bash

# Start FastAPI server
uvicorn app.main:app --reload

# Server runs at: http://localhost:8000
# API docs at: http://localhost:8000/api/docs
# Health check: http://localhost:8000/api/health
# Analysis endpoint: POST http://localhost:8000/api/analyze
```

### Opening Frontend

```bash
# Option 1: Direct file open
# Open C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html in browser

# Option 2: HTTP server
cd "C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend"
python -m http.server 3000
# Access at: http://localhost:3000
```

### Environment Setup

1. Copy backend/.env.example to backend/.env
2. Add DEEPSEEK_API_KEY (required for LLM analysis)
3. Add optional API keys for collectors (NEWS_API_KEY, TWITTER_BEARER_TOKEN, etc.)

## Code Patterns

### Adding a New Collector

1. Create file in backend/app/collectors/ (e.g., papers.py)
2. Inherit from BaseCollector
3. Implement async collect(keyword) method
4. Return standardized dict with metrics appropriate for data source
5. Handle API errors gracefully (return partial data or empty structure)
6. MUST use async HTTP client (httpx.AsyncClient) for non-blocking I/O
7. MUST return JSON-serializable data only (no datetime objects, use ISO strings)
8. SHOULD include error field in response dict to track non-fatal issues

Example - see SocialCollector and PapersCollector implementations:
```python
from app.collectors.base import BaseCollector
from typing import Dict, Any
import httpx

class SocialCollector(BaseCollector):
    async def collect(self, keyword: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch data from API
            response = await client.get(...)
            # Process and return structured data
            return {
                "source": "hacker_news",
                "mentions_30d": 124,
                "sentiment": 0.65,
                "recency": "high",
                "growth_trend": "increasing",
                "errors": []
            }
```

Key patterns from implemented collectors:
- Always wrap multi-word keywords in quotes for exact phrase matching (PapersCollector line 283, NewsCollector line 242)
- Use .get() with defaults for all API response field access to prevent KeyError (PapersCollector lines 83-85, 92-151; NewsCollector lines 86-88, 97-109)
- Optional API key authentication via headers dict (PapersCollector lines 270-273; PatentsCollector requires key, NewsCollector does not)
- Manual URL encoding with urllib.parse.quote() for APIs that don't work with httpx params dict (PatentsCollector lines 313-318)
- Use _text_all operator (not _text_any) for PatentsView API to prevent false positives (PatentsCollector lines 277-287)
- Calculate derived insights from raw metrics for better LLM reasoning (all collectors)
- Multiple API mode queries per period for richer data (NewsCollector: ArtList + TimelineVol + ToneChart)
- Wrap synchronous libraries in ThreadPoolExecutor for async compatibility (FinanceCollector uses loop.run_in_executor for yfinance)
- Instance-level caching for performance optimization while maintaining thread safety (FinanceCollector._ticker_cache)
- LLM-based dynamic data discovery for mapping keywords to external identifiers (FinanceCollector uses DeepSeek to find stock tickers)

### Adding a New API Endpoint

1. Create router file in backend/app/routers/ (e.g., analysis.py)
2. Create APIRouter instance
3. Define async endpoint functions with type hints
4. Use Depends() for database connections and settings
5. Include router in main.py with prefix and tags

Example from analysis.py implementation:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from app.database import get_db
from app.analyzers.hype_classifier import HypeCycleClassifier
import aiosqlite

router = APIRouter()

class AnalyzeRequest(BaseModel):
    keyword: str = Field(
        ...,  # Required
        min_length=1,
        max_length=100,
        description="Technology keyword to analyze",
        examples=["quantum computing", "blockchain"]
    )

    @field_validator('keyword')
    @classmethod
    def strip_keyword(cls, v: str) -> str:
        return v.strip()

class AnalyzeResponse(BaseModel):
    keyword: str
    phase: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    # ... additional fields ...

@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_200_OK)
async def analyze_technology(
    request: AnalyzeRequest,
    db: aiosqlite.Connection = Depends(get_db)
) -> AnalyzeResponse:
    try:
        classifier = HypeCycleClassifier()
        result = await classifier.classify(request.keyword, db)
        return result
    except Exception as e:
        if "Insufficient data" in str(e):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(e)}")
```

Register in main.py:
```python
from app.routers import health, analysis
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
```

Key patterns:
- Use Pydantic models for request/response validation and automatic OpenAPI schema generation
- Order parameters: request body first, then dependencies (ensures validation happens before DB connection)
- Use field_validator for custom validation (e.g., whitespace stripping)
- Use Field() constraints (min_length, max_length, ge, le) for automatic validation
- Map exception types to appropriate HTTP status codes (503 for temporary failures, 500 for unexpected errors)
- Include comprehensive OpenAPI documentation with examples in responses parameter

### Database Operations

Always use async/await with aiosqlite:
```python
from app.database import get_db
from fastapi import Depends
import aiosqlite

async def some_route(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM analyses WHERE keyword = ?", (keyword,)) as cursor:
        result = await cursor.fetchone()
```

### Configuration Access

Use cached settings singleton:
```python
from app.config import get_settings

settings = get_settings()
api_key = settings.deepseek_api_key
```

### Using the Orchestration Layer

The HypeCycleClassifier is the main entry point for analysis. See the implemented analysis router for production usage pattern:

```python
# See C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py for full implementation
from app.analyzers.hype_classifier import HypeCycleClassifier
from app.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import aiosqlite

router = APIRouter()

class AnalyzeRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)

@router.post("/analyze")
async def analyze_technology(
    request: AnalyzeRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    try:
        classifier = HypeCycleClassifier()
        result = await classifier.classify(request.keyword, db)
        return result
    except Exception as e:
        if "Insufficient data" in str(e):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(e)}")
```

Key behaviors:
- Returns cached result immediately if found (cache_hit=True, <1 second response time)
- Runs all 5 collectors in parallel on cache miss (120s timeout, ~48 seconds typical)
- Requires minimum 3 of 5 collectors to succeed
- Raises exception if <3 collectors succeed (handle with 503 Service Unavailable)
- Response includes per-source analyses, collector data, metadata, and error tracking (13 total fields)
- Automatically persists result to database with 24-hour cache TTL (configurable via CACHE_TTL_HOURS)
- Comprehensive error aggregation: tracks which collectors/analysis steps failed with descriptive messages

### Critical API Integration Patterns

Based on lessons learned from implemented collectors:

**1. Exact Phrase Matching for Multi-Word Keywords**
- Always wrap keywords in quotes for API searches to get exact phrase matches
- Example: `query: f'"{keyword}"'` (PapersCollector line 283)
- Without quotes, "quantum computing" searches for "quantum" OR "computing" anywhere
- With quotes, searches for exact phrase "quantum computing"
- Reduces false positives by 99.9% for multi-word technology terms

**2. Safe Dictionary Access Pattern**
- NEVER use direct dictionary access: `data["key"]` can raise KeyError
- ALWAYS use .get() with defaults: `data.get("key", default_value)`
- API responses may omit fields entirely (not just set to null)
- Example pattern: `publications = data.get("total", 0) if data else 0`
- Protects against both None data and missing keys

**3. Optional API Key Authentication**
- Check if API key is configured before adding to headers
- Pattern:
```python
from app.config import get_settings

settings = get_settings()
headers = {}
if settings.api_key_name:
    headers["x-api-key"] = settings.api_key_name
response = await client.get(url, headers=headers)
```
- Works with or without API key configuration
- Enables higher rate limits when key is available

**4. Bulk/Specialized Endpoints**
- Some APIs have specialized endpoints that provide better results
- Example: Semantic Scholar has both /paper/search and /paper/search/bulk
- Bulk endpoint provides more targeted results for technology searches
- Always research available API endpoints before implementing

**5. Time-Scale Matching**
- Match time windows to data source characteristics
- Social media: 30 days, 6 months, 1 year (fast-moving)
- Academic papers: 2 years, 5 years, 10 years (slower cycles, long-term research trends)
- Patents: 2 years, 5 years, 10 years (patent filing and grant cycles)
- News media: 30 days, 3 months, 1 year (faster than patents, slower than social media)
- Financial markets: 1 month, 6 months, 2 years (earnings cycles, market trend cycles)
- Choose periods that reveal meaningful trends for that domain
- Use non-overlapping windows to prevent double-counting (e.g., 2y: 2023-2024, 5y: 2018-2022, 10y: 2013-2017)

**6. Manual URL Encoding Pattern (PatentsView API)**
- CRITICAL: Some APIs don't work with httpx's built-in params dict encoding
- PatentsView API requires manual URL encoding using urllib.parse.quote()
- Pattern:
```python
from urllib.parse import quote
import json

query = {"_and": [...]}
fields = ["patent_id", "patent_title", ...]
options = {"size": 100}

# Manually construct URL with encoded JSON params
q = json.dumps(query)
f = json.dumps(fields)
o = json.dumps(options)
url = f'{API_URL}?q={quote(q)}&f={quote(f)}&o={quote(o)}'

# Use URL directly, not params dict
response = await client.get(url, headers=headers)
```
- This pattern was discovered through debugging PatentsView integration
- Without manual encoding, API returns 400 "Invalid query parameters"
- NEVER use params dict with PatentsView API

**7. Query Operator Selection for Multi-Word Keywords (PatentsView API)**
- CRITICAL: Use _text_all operator for multi-word technology terms, NOT _text_any
- _text_all: Matches documents containing ALL words (e.g., "quantum computing" requires both "quantum" AND "computing")
- _text_any: Matches documents containing ANY word (e.g., "quantum computing" matches "quantum mechanics" OR "distributed computing")
- Pattern:
```python
query = {
    "_and": [
        {
            "_or": [
                {"_text_all": {"patent_title": keyword}},
                {"_text_all": {"patent_abstract": keyword}}
            ]
        },
        {"_gte": {"patent_date": date_start}},
        {"_lte": {"patent_date": date_end}}
    ]
}
```
- Using _text_all prevents false positives - reduces "quantum computing" results from 22,886 to 889 (96% reduction)
- Without _text_all, searches return patents containing ANY keyword, drastically reducing result relevance
- This pattern is essential for accurate technology analysis

**8. Wrapping Synchronous Libraries for Async Compatibility (FinanceCollector Pattern)**
- CRITICAL: FastAPI collectors MUST be async to work with parallel execution via asyncio.gather()
- Some libraries (yfinance, pandas, etc.) are synchronous and will block the event loop
- Solution: Use asyncio.run_in_executor with ThreadPoolExecutor to run sync code in threads
- Pattern:
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def collect(self, keyword: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=5)

    try:
        # Submit sync function to thread pool
        tasks = [
            loop.run_in_executor(executor, self._sync_function, arg)
            for arg in args_list
        ]

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results in async context
        return self._process_results(results)
    finally:
        # CRITICAL: Explicitly shutdown executor to prevent resource leaks
        executor.shutdown(wait=True, cancel_futures=True)
```
- Thread safety considerations: Use tuple returns (data, errors) instead of shared list mutations
- Always cleanup executors in finally blocks to prevent thread pool exhaustion
- Use instance-level caching (_ticker_cache) rather than class-level to avoid race conditions

**9. LLM-Based Dynamic Discovery Pattern (FinanceCollector Pattern)**
- For collectors where keywords don't directly map to API identifiers, use LLM to bridge the gap
- Example: "quantum computing" → stock tickers ["IBM", "GOOGL", "IONQ", "RGTI", "MSFT"]
- Pattern:
```python
async def _get_relevant_identifiers(self, keyword: str, errors: List[str]) -> List[str]:
    # Check instance cache first
    if keyword in self._identifier_cache:
        return self._identifier_cache[keyword]

    # Use LLM to discover identifiers
    prompt = f"List 5-10 identifiers for {keyword}. Return only JSON array: [\"ID1\", \"ID2\"]"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}]}
        )
        result = response.json()
        identifiers = json.loads(result["choices"][0]["message"]["content"])

    # Validate identifiers (regex, format checks)
    validated = [id for id in identifiers if regex_pattern.match(id)]

    # Cache for future requests
    self._identifier_cache[keyword] = validated
    return validated
```
- Benefits: Works for any keyword without manual mapping maintenance
- Fallback strategy: Provide default identifiers (e.g., tech ETFs) when LLM fails
- Cost consideration: Cache results per instance to minimize LLM API calls

**10. Two-Stage LLM Analysis Pattern (DeepSeekAnalyzer Pattern)**
- For complex classification tasks, use two-stage analysis: per-source analysis + final synthesis
- Stage 1: Analyze each data source independently with specialized prompts (5 LLM calls for 5 sources)
- Stage 2: Synthesize all per-source analyses into final classification (1 LLM call)
- Pattern:
```python
async def analyze(self, keyword: str, collector_data: Dict[str, Any]) -> Dict[str, Any]:
    errors = []
    per_source_analyses = {}

    # Stage 1: Analyze each source independently
    for source_name in ["social", "papers", "patents", "news", "finance"]:
        source_data = collector_data.get(source_name, {})
        if not source_data:
            errors.append(f"Missing {source_name} data")
            continue

        try:
            # Use specialized prompt template for this source
            analysis = await self._analyze_source(source_name, source_data, keyword)
            per_source_analyses[source_name] = analysis
        except Exception as e:
            errors.append(f"Failed to analyze {source_name}: {str(e)}")

    # Require minimum 3 sources for robust classification
    if len(per_source_analyses) < 3:
        raise Exception(f"Insufficient data for analysis. Errors: {errors}")

    # Stage 2: Synthesize all source analyses into final classification
    final_analysis = await self._synthesize_analyses(keyword, per_source_analyses)
    final_analysis["per_source_analyses"] = per_source_analyses
    if errors:
        final_analysis["errors"] = errors
    return final_analysis
```
- Benefits: Provides transparency (see individual source classifications), better reasoning (specialized prompts per source), graceful degradation (continues with ≥3 sources)
- Specialized prompts: Each source gets domain-specific thresholds and interpretation guidance (e.g., social media: >200 mentions = peak, academic: <10 papers = innovation_trigger)
- Synthesis prompt: Weighs all sources by confidence scores, handles conflicting signals (e.g., social hype vs. academic maturity)
- Response validation: Strip markdown code blocks (```json ... ```), validate required fields, check value ranges
- Temperature: Use 0.3 for deterministic classification (vs. 0.7+ for creative text generation)
- Graceful degradation: Track errors in "errors" field, continue with partial data if ≥3 sources succeed

**11. Niche Query Expansion Pattern (HypeCycleClassifier Pattern)**
- For niche technologies with low data availability, use LLM to generate broader search terms
- Detection: Check primary data source metrics (e.g., social mentions_30d < 50 OR mentions_total < 100)
- Expansion workflow: Generate terms → Re-run subset of collectors → Update results
- Pattern:
```python
async def _expand_query_and_rerun(self, keyword: str, collector_results: Dict, errors: List[str]):
    # Step 1: Generate expanded terms via LLM
    analyzer = DeepSeekAnalyzer(api_key=self.settings.deepseek_api_key)
    expanded_terms = await analyzer.generate_expanded_terms(keyword)

    # Step 2: Re-run applicable collectors (exclude those already using LLM)
    collectors_to_rerun = {
        "social": SocialCollector(),
        "papers": PapersCollector(),
        "patents": PatentsCollector(),
        "news": NewsCollector()
        # Skip FinanceCollector - already uses LLM for ticker discovery
    }

    # Step 3: Run with expanded_terms parameter
    tasks = [collector.collect(keyword, expanded_terms=expanded_terms)
             for collector in collectors_to_rerun.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4: Update collector_results (keep original on failure)
    for source_name, result in zip(collectors_to_rerun.keys(), results):
        if not isinstance(result, Exception):
            collector_results[source_name] = result

    return collector_results, errors, expanded_terms
```
- Benefits: Improves data availability for niche technologies (+2,626% papers, +983% patents verified), maintains quality for mainstream technologies (no expansion triggered)
- Term generation: Use temperature 0.4 for diversity, validate against generic terms list, require 3-5 terms
- Selective application: Only re-run collectors that benefit from term expansion (exclude those with existing LLM mapping)
- Transparent metadata: Track query_expansion_applied boolean and expanded_terms list in response and database
- Fallback behavior: On expansion failure, continue with original collector results
- Example: "plant cell culture" → ["plant tissue culture", "in vitro propagation", "micropropagation", "callus culture", "somatic embryogenesis"]

**12. Robust LLM JSON Parsing Pattern (DeepSeekAnalyzer Pattern)**
- LLM APIs (DeepSeek, OpenAI, etc.) often return JSON wrapped in markdown code blocks despite prompts requesting bare JSON
- Simple string splitting fails with edge cases (multiple blocks, text after blocks, missing language tags)
- Solution: Use regex-based extraction helper method with comprehensive error handling
- Pattern:
```python
import re
import json
import logging

logger = logging.getLogger(__name__)

def _extract_json_from_markdown(self, content: str) -> str:
    """Extract JSON from markdown code blocks or bare JSON"""
    content = content.strip()

    # Regex pattern: match markdown-wrapped or bare JSON
    # Handles: ```json\n{...}\n```, ```\n{...}\n```, {...}
    pattern = r'```(?:json)?\s*(\{.*?\})\s*```|(\{.*?\})'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        # Return first non-None group
        json_str = match.group(1) or match.group(2)
        return json_str.strip()

    # Raise with content preview for debugging
    content_preview = content[:200] if len(content) > 200 else content
    raise ValueError(f"Could not extract JSON from content. Preview: {content_preview}")

async def _call_llm_api(self, prompt: str) -> Dict[str, Any]:
    """Call LLM API and parse JSON response with robust error handling"""
    # Make API call
    response = await client.post(API_URL, json={"prompt": prompt})
    content = response.json()["choices"][0]["message"]["content"]

    # Extract and parse JSON with comprehensive error handling
    try:
        json_str = self._extract_json_from_markdown(content)
        parsed = json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        # Log raw content (truncated) for debugging
        content_preview = content[:500] + "..." if len(content) > 500 else content
        logger.error(f"Failed to parse LLM JSON response: {str(e)}")
        logger.error(f"Raw content: {content_preview}")
        # Re-raise with content snippet for immediate visibility
        raise ValueError(
            f"Failed to parse LLM response. Error: {str(e)}. Content preview: {content[:200]}"
        ) from e

    return parsed
```
- Benefits: Handles all markdown edge cases, provides debugging context when failures occur, prevents cryptic JSONDecodeError messages
- Regex pattern explained: `r'```(?:json)?\s*(\{.*?\})\s*```|(\{.*?\})'`
  - `(?:json)?` - Optional "json" language tag (non-capturing)
  - `\s*` - Optional whitespace
  - `(\{.*?\})` - Capture group for JSON object (non-greedy match)
  - `|(\{.*?\})` - Alternative: bare JSON without markdown
  - `re.DOTALL` flag - Makes `.` match newlines for multi-line JSON
- Error handling: Logs raw content at ERROR level (truncated to 500 chars to prevent log spam), includes content snippet in exception message
- Logging setup: Module-level logger instance following codebase patterns: `logger = logging.getLogger(__name__)`
- Test coverage: Verify with edge cases (bare JSON, markdown without language tag, text after blocks, multiple blocks, malformed JSON)

## Project Structure Reference

```
C:\Users\Hp\Desktop\Gartner's Hype Cycle\
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry point with CORS, startup events
│   │   ├── config.py            # Pydantic settings from .env
│   │   ├── database.py          # SQLite async initialization
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Abstract BaseCollector interface
│   │   │   ├── social.py        # Social media collector (IMPLEMENTED - Hacker News)
│   │   │   ├── papers.py        # Research papers collector (IMPLEMENTED - Semantic Scholar, 642 lines)
│   │   │   ├── patents.py       # Patent collector (IMPLEMENTED - PatentsView)
│   │   │   ├── news.py          # News collector (IMPLEMENTED - GDELT)
│   │   │   └── finance.py       # Financial data collector (IMPLEMENTED - Yahoo Finance + DeepSeek)
│   │   ├── analyzers/
│   │   │   ├── __init__.py
│   │   │   ├── deepseek.py      # DeepSeek LLM client (IMPLEMENTED - 601 lines with robust JSON parsing)
│   │   │   └── hype_classifier.py # Main orchestration layer (IMPLEMENTED - 290 lines)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py        # Health check endpoint (IMPLEMENTED)
│   │   │   └── analysis.py      # Main analysis endpoint (IMPLEMENTED - 183 lines)
│   │   ├── models/              # Database models or schemas (placeholder)
│   │   │   └── __init__.py
│   │   └── utils/               # Shared utilities (placeholder)
│   │       └── __init__.py
│   ├── tests/                   # Test files
│   │   ├── __init__.py
│   │   ├── test_social_collector.py  # SocialCollector tests (14 tests)
│   │   ├── test_papers_collector.py  # PapersCollector tests (25 tests)
│   │   ├── test_patents_collector.py # PatentsCollector tests (20 tests)
│   │   ├── test_news_collector.py    # NewsCollector tests (16 tests)
│   │   ├── test_finance_collector.py # FinanceCollector tests (17 tests)
│   │   ├── test_deepseek_analyzer.py # DeepSeekAnalyzer tests (27 tests - includes 7 new JSON parsing edge case tests)
│   │   ├── test_hype_classifier.py   # HypeCycleClassifier tests (12 tests)
│   │   └── test_query_expansion.py   # Query expansion tests (12 tests)
│   ├── test_real_classification.py  # Integration test for end-to-end workflow
│   ├── test_expansion_comparison.py # Query expansion validation script (compares before/after metrics)
│   ├── venv/                    # Python virtual environment (gitignored)
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Environment variable template
│   └── .env                     # Actual config (gitignored, create from .env.example)
├── frontend/
│   ├── index.html               # Main HTML structure
│   ├── app.js                   # JavaScript API calls and visualization
│   └── styles.css               # CSS styling with gradient background
├── data/
│   ├── .gitkeep                 # Ensures directory exists in git
│   └── hype_cycle.db            # SQLite database (gitignored, auto-created)
├── sessions/                    # cc-sessions framework (do not modify)
├── .gitignore                   # Python, venv, .env, database exclusions
├── CLAUDE.md                    # This file - developer guidance
└── README.md                    # Setup instructions and project overview
```

## Important Notes

### Database Schema

The analyses table stores cached results:
- id: Primary key
- keyword: Technology keyword searched
- created_at: Timestamp of analysis
- phase: Hype cycle phase (innovation_trigger, peak, trough, slope, plateau)
- confidence: LLM confidence score (0-1)
- reasoning: LLM explanation text
- social_data, papers_data, patents_data, news_data, finance_data: JSON blobs from collectors
- per_source_analyses_data: JSON blob containing per-source LLM analyses (5 individual classifications)
- **query_expansion_applied**: INTEGER (0=False, 1=True) indicating whether query expansion was used for this analysis
- **expanded_terms_data**: TEXT storing JSON array of expanded search terms (e.g., ["plant tissue culture", "in vitro propagation", "micropropagation"])
- expires_at: Cache expiration timestamp (default: 24 hours)

Note: The per_source_analyses_data, query_expansion_applied, and expanded_terms_data columns were added via idempotent migrations in database.py init_db() function (lines 34-47). The migration checks for column existence using PRAGMA table_info and only runs ALTER TABLE if needed.

### CORS Configuration

FastAPI middleware allows all origins with `allow_origins=["*"]`. This is acceptable for local development but should be restricted to specific frontend URL in production.

### Async Patterns

All collectors, database operations, and API calls use async/await. This enables parallel execution of the five collectors without blocking. FastAPI handles async natively.

### Error Handling

Collectors should handle API failures gracefully. If one collector fails, others should continue. The LLM should work with partial data if needed.

### Cache Strategy

Before running collectors, check database for recent analysis of same keyword where expires_at > current time. Cache TTL configured via CACHE_TTL_HOURS environment variable (default: 24).

## Next Development Steps

Based on project implementation status:

1. **Individual Collectors** (5 tasks, 5/5 complete):
   - ✓ Social media (Hacker News Algolia API) - COMPLETED
   - ✓ Research papers (Semantic Scholar API) - COMPLETED
   - ✓ Patent search (PatentsView Search API) - COMPLETED
   - ✓ News aggregation (GDELT API) - COMPLETED
   - ✓ Financial data (Yahoo Finance with DeepSeek ticker discovery) - COMPLETED

2. **DeepSeek Integration** (1 task, 1/1 complete):
   - ✓ Prompt engineering for classification - COMPLETED
   - ✓ API client implementation - COMPLETED
   - ✓ JSON response parsing - COMPLETED

3. **Orchestration Layer** (1 task, 1/1 complete):
   - ✓ HypeCycleClassifier implementation - COMPLETED
   - ✓ Cache checking logic - COMPLETED
   - ✓ Parallel collector execution with asyncio.gather() - COMPLETED
   - ✓ DeepSeek integration - COMPLETED
   - ✓ Result persistence - COMPLETED
   - ✓ Graceful degradation (minimum 3 of 5 collectors) - COMPLETED
   - ✓ Comprehensive test suite (12 tests) - COMPLETED

4. **Analysis Endpoint** (1 task, 1/1 complete):
   - ✓ FastAPI router integration (backend/app/routers/analysis.py) - COMPLETED
   - ✓ POST /api/analyze endpoint with request/response models - COMPLETED
   - ✓ HypeCycleClassifier invocation with database dependency injection - COMPLETED
   - ✓ Error handling and HTTP status codes (200, 422, 500, 503) - COMPLETED
   - ✓ OpenAPI documentation with examples - COMPLETED
   - ✓ Request validation (min_length, max_length, whitespace stripping) - COMPLETED
   - ✓ Performance tested (48s fresh, <1s cache hit) - COMPLETED

5. **Frontend Implementation** (1 task, 1/1 complete):
   - ✓ HTML structure with input form, results display, status indicators, warning banners - COMPLETED
   - ✓ JavaScript API integration with POST /api/analyze endpoint - COMPLETED
   - ✓ Per-source analyses display for all 5 data sources - COMPLETED
   - ✓ Comprehensive error handling (422/500/503 status codes) - COMPLETED
   - ✓ Status indicators (cache hits, collector counts, expiration times) - COMPLETED
   - ✓ Canvas-based hype cycle visualization with position marker - COMPLETED
   - ✓ Responsive CSS styling with color-coded badges - COMPLETED
   - ✓ Loading state with realistic time expectations - COMPLETED
   - ✓ XSS protection via textContent (no innerHTML) - COMPLETED

6. **Future Enhancements** (optional):
   - Add interactive tooltips on hype cycle curve
   - Display detailed collector data metrics (expandable sections)
   - Add animation/transitions for results display
   - Implement result history/favorites feature
   - Add export functionality (PDF/JSON)

## Testing

### Running Tests

```bash
# Activate virtual environment
cd backend
source venv/Scripts/activate

# Run all tests
pytest

# Run specific test file
pytest tests/test_social_collector.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app
```

### Health Check Test
```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","database":"healthy","version":"0.1.0"}
```

### Social Collector Test
The SocialCollector has comprehensive test coverage (14 tests):
- Success cases with typical API responses
- Error handling (rate limits, timeouts, network errors)
- Edge cases (zero results, partial failures, missing fields)
- Sentiment calculation validation
- Growth trend detection
- JSON serialization verification

### Papers Collector Test
The PapersCollector has comprehensive test coverage (25 tests):
- Success cases with typical API responses for all 3 time periods (2y, 5y, 10y)
- Error handling (rate limits, timeouts, network errors, invalid queries)
- Edge cases (zero results, partial failures, missing fields)
- 10-year period fetching with non-overlapping time windows
- Author aggregation across all periods (top 10 by publication count)
- Paper type distribution analysis (5 categories: Review, JournalArticle, Conference, Book, Other)
- Enhanced research maturity with type-aware thresholds (high review percentage = mature, high conference percentage = emerging)
- Research maturity reasoning generation with detailed explanations
- Citation velocity calculation (positive and negative)
- Research momentum detection (accelerating, steady, decelerating)
- Research trend detection (increasing, stable, decreasing)
- Research breadth detection (narrow, moderate, broad)
- Partial data handling (10y period failure while 2y/5y succeed)
- JSON serialization verification for all new fields

### Patents Collector Test
The PatentsCollector has comprehensive test coverage (20 tests):
- Success cases with typical API responses
- Error handling (rate limits, timeouts, network errors, authentication failures)
- Edge cases (zero results, partial failures, missing fields, missing API key)
- Filing velocity calculation (positive and negative)
- Assignee concentration detection (concentrated, diverse)
- Geographic reach detection (domestic, global)
- Patent maturity detection (emerging, mature)
- Patent momentum detection (accelerating)
- Patent trend detection (increasing)
- JSON serialization verification

### News Collector Test
The NewsCollector has comprehensive test coverage (16 tests):
- Success cases with typical API responses
- Error handling (rate limits, timeouts, network errors)
- Edge cases (zero results, partial failures, missing fields)
- Tone calculation (all positive, all negative, mixed)
- Coverage trend detection (increasing, decreasing, stable)
- Media attention classification (high, medium, low)
- Mainstream adoption detection (mainstream, emerging, niche)
- Geographic diversity calculation
- JSON serialization verification

### Finance Collector Test
The FinanceCollector has comprehensive test coverage (17 tests):
- Success cases with DeepSeek and yfinance mocked responses
- DeepSeek integration (API failures, rate limiting, timeouts, missing API key)
- Error handling (invalid tickers, missing data, partial failures)
- Edge cases (all tickers fail, no historical data, missing fields)
- Market maturity detection (emerging, developing, mature)
- Investor sentiment detection (positive, neutral, negative)
- Investment momentum detection (accelerating, steady, decelerating)
- Volume trend detection (increasing, stable, decreasing)
- Instance isolation (thread-safe per-instance caching)
- JSON serialization verification

### DeepSeek Analyzer Test
The DeepSeekAnalyzer has comprehensive test coverage (27 tests):
- Initialization and API key validation (missing API key raises ValueError)
- Full end-to-end analysis with all 5 data sources (6 total LLM calls: 5 per-source + 1 synthesis)
- Individual per-source analysis for each collector (social, papers, patents, news, finance)
- Final synthesis aggregation logic (weighs multiple source analyses)
- Error handling (rate limits 429, authentication failures 401, timeouts, invalid JSON)
- Invalid response handling (missing required fields, invalid phase values, confidence out of range)
- **Robust markdown extraction** (7 new tests covering edge cases):
  - Bare JSON without markdown wrapping: {...}
  - Markdown-wrapped without language identifier: ```\n{...}\n```
  - Text after closing backticks: ```json {...}``` Here's my explanation
  - Multiple code blocks (extracts first JSON object)
  - Malformed JSON with logging verification (ensures ERROR logs captured)
  - No JSON content found (raises ValueError with content preview)
  - Updated existing test to expect ValueError instead of JSONDecodeError
- Edge cases (insufficient sources <3, partial collector failures, graceful degradation)
- Response structure validation (phase in valid set, confidence 0-1, reasoning present)
- JSON serialization verification (result is fully JSON-serializable)
- Real API validation: Successfully tested with "quantum computing" (all 5 sources classified as "peak", final confidence: 0.78, per-source confidence: 0.72-0.85) and "bio fuels" (previously failed with JSON parsing error, now works correctly)

### Hype Cycle Classifier Test
The HypeCycleClassifier has comprehensive test coverage (12 tests):
- Initialization with settings injection
- Cache hit scenario (returns cached result without running collectors)
- Cache miss with all 5 collectors succeeding (full analysis workflow)
- Partial success scenarios (3/5 and 4/5 collectors succeed at minimum threshold)
- Insufficient data error (<3 collectors succeed raises exception)
- Parallel collector execution (_run_collectors method with all successes)
- Parallel collector execution with partial failures (2/5 collectors fail)
- Database persistence (_persist_result writes correctly to database)
- Response assembly with full data (all collectors succeed)
- Response assembly with partial data (some collectors failed)
- Response assembly combines collector and analysis errors
- JSON serialization of final result
- Integration test: backend/test_real_classification.py validates end-to-end workflow with real API calls to all 5 collectors + DeepSeek

### Analysis Endpoint Test
Manual testing results for POST /api/analyze endpoint:
- Fresh analysis ("blockchain"): 48 seconds response time, HTTP 200, phase: "trough", confidence: 0.78, all 5 collectors succeeded
- Cache hit (repeated "blockchain"): <1 second response time, HTTP 200, cache_hit: true, identical results
- Validation error (empty keyword): HTTP 422 Unprocessable Entity, automatic FastAPI/Pydantic validation
- Comprehensive response structure: 13 fields including keyword, phase, confidence, reasoning, per_source_analyses, collector_data, metadata, error tracking
- DeepSeek execution: 6 total LLM API calls (5 per-source analyses + 1 final synthesis) as expected
- Graceful degradation: Semantic Scholar returned HTTP 429 rate limit during test, but remaining collectors succeeded (5/5 overall)
- Cache behavior: Response includes expires_at timestamp (24 hours from created_at), cache_hit boolean toggles correctly

### Frontend Testing
The frontend implementation has been manually tested with multiple scenarios:

**Fresh Analysis Test:**
- Technology: "quantum computing"
- Result: All 5 source cards displayed with color-coded phase badges and confidence scores
- Loading state: Displayed spinner with "up to 2 minutes" message
- Status indicators: "Fresh analysis" badge, "Based on 5/5 data sources" badge
- Canvas visualization: Position marker correctly placed on hype cycle curve
- Response time: ~48 seconds (as expected for fresh analysis)

**Cache Hit Test:**
- Technology: Repeated "quantum computing" within 24 hours
- Result: Core classification displayed correctly with all 5 per-source analysis cards
- Status indicators: "Cached result from [timestamp]" badge, "Expires in ~X hours" badge
- Response time: <1 second (as expected for cache hit)
- Per-source analyses correctly retrieved from database cache

**Error Handling Tests:**
- Empty keyword: Displays "Please enter a technology keyword"
- Network error (backend offline): "Network Error: Failed to fetch. Please check your internet connection and ensure the backend is running."
- HTTP 422 validation error: Displays parsed validation error details
- HTTP 503 insufficient data: "Service temporarily unavailable: [detail]. Please try again later or try a different keyword."

**Partial Data Test:**
- Scenario: 4/5 collectors succeeded (one collector failed)
- Result: Warning banner displayed with yellow background: "This analysis was performed with partial data (4/5 collectors succeeded). Results may be less reliable."
- Partial_data flag correctly triggers warning visibility
- All 4 successful source analyses displayed in cards

**Responsive Design Test:**
- Desktop (>768px): Side-by-side layout for source cards, horizontal status badges
- Mobile (<768px): Vertical source card layout, stacked status badges, full-width elements
- Canvas visualization scales appropriately on different screen sizes

**Security Test:**
- All dynamic content uses textContent (not innerHTML) - XSS protection verified
- No inline script execution possible
- Input validation on both frontend and backend

**Browser Compatibility:**
- Tested in modern browsers: Chrome, Firefox, Edge
- Canvas API, Fetch API, ES6+ features work correctly
- No build process required - works directly via file:// or HTTP server

### API Documentation
Access interactive Swagger UI at http://localhost:8000/api/docs to test endpoints directly in browser.

#### Available Endpoints
- GET /api/health - Health check endpoint
- POST /api/analyze - Technology analysis endpoint with comprehensive OpenAPI documentation
- GET /api/docs - Swagger UI interactive documentation
- GET /api/redoc - ReDoc alternative documentation interface

#### Testing POST /api/analyze via Swagger UI
1. Navigate to http://localhost:8000/api/docs
2. Expand POST /api/analyze endpoint
3. Click "Try it out"
4. Enter keyword in request body: `{"keyword": "quantum computing"}`
5. Click "Execute"
6. View response with complete analysis results (phase, confidence, reasoning, collector data, etc.)

#### Testing POST /api/analyze via curl
```bash
# Fresh analysis
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"keyword": "blockchain"}'

# Response (abbreviated):
{
  "keyword": "blockchain",
  "phase": "trough",
  "confidence": 0.78,
  "reasoning": "...",
  "cache_hit": false,
  "collectors_succeeded": 5,
  "partial_data": false,
  "errors": []
}

# Cache hit (repeat same keyword within 24 hours)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"keyword": "blockchain"}'

# Response includes cache_hit: true, completes in <1 second
```

## Common Issues

### Virtual Environment Activation
On Windows, use the appropriate activation script:
- Git Bash: `source backend/venv/Scripts/activate`
- CMD: `backend\venv\Scripts\activate.bat`
- PowerShell: `backend\venv\Scripts\Activate.ps1`

### Python 3.14 Compatibility
Some packages may not have pre-built wheels for Python 3.14. The requirements.txt uses `>=` constraints to allow newer compatible versions.

### Database Path Resolution
DATABASE_PATH in database.py uses Path(__file__).parent.parent.parent to resolve to project root regardless of working directory when running uvicorn.

### CORS Errors
If frontend shows CORS policy errors, verify CORSMiddleware is configured in main.py and backend is running.

### Database Migration Notes
The database schema was updated to include per_source_analyses_data column for caching LLM analysis results. An idempotent migration in database.py init_db() automatically adds this column on server startup if it doesn't exist. The migration uses PRAGMA table_info to check column existence before running ALTER TABLE, ensuring safe execution across multiple startups and deployments.
