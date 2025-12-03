---
name: m-implement-niche-query-expansion
branch: feature/niche-query-expansion
status: completed
created: 2025-12-03
completed: 2025-12-03
---

# Implement Niche Query Expansion with DeepSeek

## Problem/Goal
For niche technologies with limited online presence, the current system often fails to collect sufficient data (minimum 3/5 collectors required). This results in HTTP 503 errors and no analysis for users. The goal is to implement intelligent query expansion using DeepSeek LLM to generate related search terms when initial data collection indicates a niche technology, improving coverage without sacrificing quality for mainstream technologies.

## Success Criteria
- [x] **Niche detection via SocialCollector**: System automatically identifies when a technology is "niche" based solely on low social media metrics (e.g., mentions_30d < 50 OR mentions_total < 100)
- [x] **DeepSeek query expansion**: When niche is detected, DeepSeek generates 3-5 related search terms with validation (relevance check, no generic terms like "technology" or "system")
- [x] **Selective collector application**: Query expansion applied ONLY to 4 collectors (Social, Papers, Patents, News), NOT to FinanceCollector (which already uses DeepSeek for ticker discovery)
- [x] **Improved coverage for niche technologies**: For tested niche technologies (e.g., "plant cell culture", "CRISPR base editing"), system now succeeds (≥3 collectors) where it previously failed (<3 collectors)
- [x] **Quality preservation for mainstream**: For mainstream technologies (e.g., "blockchain", "quantum computing"), behavior remains unchanged (no expansion triggered, same results as before)
- [x] **Transparent metadata**: Response includes fields indicating whether query expansion was used (`query_expansion_applied: bool`) and which expanded terms were applied (`expanded_terms: List[str]`)
- [x] **Comprehensive test coverage**: Tests for niche detection logic, DeepSeek integration, expansion application per collector, fallback behavior on API errors, and end-to-end scenarios

## Context Manifest

### How the Current System Works: Data Collection and Classification Flow

When a user submits a technology keyword (e.g., "quantum computing") through the frontend, the request flows through a carefully orchestrated pipeline that collects data from five parallel sources and uses LLM-based analysis to classify the technology on Gartner's Hype Cycle.

**Entry Point - Analysis Router (analysis.py:138-182):**
The POST /api/analyze endpoint receives the keyword, validates it using Pydantic (min_length=1, max_length=100, whitespace stripping), and passes it to HypeCycleClassifier. The endpoint has sophisticated error handling that maps specific failure types to appropriate HTTP status codes: 422 for validation errors (automatic), 503 for insufficient data (temporary condition, <3 collectors succeeded), and 500 for unexpected errors (database failures, DeepSeek API errors).

**Cache-First Strategy (hype_classifier.py:89-152):**
Before running any collectors, the classifier checks the SQLite database for cached results using a WHERE clause that matches both the keyword AND expires_at > current_timestamp. The cache TTL is configurable (default 24 hours via CACHE_TTL_HOURS env var). On cache hit, the system deserializes collector data AND per_source_analyses from JSON-stored TEXT columns, then immediately returns the cached result with cache_hit=True. This makes cached responses complete in under 1 second. On cache miss, the system logs the miss and proceeds to fresh data collection.

**Parallel Collector Execution (hype_classifier.py:154-200):**
The classifier instantiates all five collectors (Social, Papers, Patents, News, Finance) and runs their collect() methods in parallel using asyncio.gather(*tasks, return_exceptions=True). The CRITICAL pattern here is return_exceptions=True, which prevents one collector failure from cancelling the others - each collector operates independently and can succeed or fail without affecting its peers. The entire batch has a 120-second timeout (COLLECTOR_TIMEOUT_SECONDS = 120.0). Each collector returns a standardized Dict[str, Any] with metrics specific to that data source.

**How Each Collector Works:**

*SocialCollector (social.py) - Hacker News Algolia API:*
Queries https://hn.algolia.com/api/v1/search across three time periods (30 days, 6 months, 1 year) using Unix timestamp filters. Returns mentions_30d, mentions_6m, mentions_1y, mentions_total as the PRIMARY metrics for niche detection. Also calculates avg_points_30d, avg_comments_30d for engagement, and derives sentiment (-1.0 to 1.0), recency (high/medium/low), growth_trend (increasing/stable/decreasing), and momentum (accelerating/steady/decelerating). The collector uses direct params dictionary (query, tags="story", numericFilters) and MUST use HTTPS endpoint (not HTTP which causes 301 redirect). Returns top 5 stories with titles, points, comments, age_days for LLM context. Graceful error handling - NEVER raises exceptions, returns _error_response with zero metrics on total failure.

*PapersCollector (papers.py) - Semantic Scholar Bulk API:*
Queries https://api.semanticscholar.org/graph/v1/paper/search/bulk with two time windows (2 years, 5 years) matching academic publishing cycles. CRITICAL pattern: wraps keyword in quotes (line 226: query: f'"{keyword}"') for exact phrase matching, reducing false positives by 99.9%. Uses optional API key authentication via x-api-key header if SEMANTIC_SCHOLAR_API_KEY is configured. Returns publications_2y, publications_5y, publications_total plus citation metrics (avg_citations_2y, avg_citations_5y, citation_velocity). Calculates author_diversity and venue_diversity by extracting unique author IDs and venue names from response. Derives research_maturity (emerging: <10 papers in 2y, developing: 10-50, mature: >50), research_momentum (accelerating/steady/decelerating based on publication rate comparison), research_trend (increasing/stable/decreasing), and research_breadth (narrow/moderate/broad from diversity ratios). Uses .get() with defaults for ALL API field access to prevent KeyError on inconsistent responses (lines 70, 78, 107 - handles missing citationCount, authors, venue fields).

*PatentsCollector (patents.py) - PatentsView Search API:*
Queries https://search.patentsview.org/api/v1/patent/ with three time periods (2y, 5y, 10y) matching patent filing cycles. CRITICAL: Requires manual URL encoding with urllib.parse.quote() (lines 313-318) because httpx params dict encoding does NOT work with this API. Uses GET requests with JSON-stringified query parameters that must be manually URL-encoded. The query uses _text_all operator (NOT _text_any) to ensure ALL keywords are present (lines 277-287), preventing false positives - reduces "quantum computing" results from 22,886 to 889 patents (96% reduction). Searches both patent_title and patent_abstract fields with _or. Requires PATENTSVIEW_API_KEY via X-Api-Key header (returns None if missing, line 310). Returns patents_2y, patents_5y, patents_10y, patents_total plus assignee metrics (unique_assignees, top_assignees), geographic data (countries dict, geographic_diversity), and citation metrics. Derives filing_velocity, assignee_concentration (concentrated/moderate/diverse), geographic_reach (domestic/regional/global), patent_maturity, patent_momentum, patent_trend. Safe dictionary access with .get() to prevent KeyError on missing assignee_country, citation counts.

*NewsCollector (news.py) - GDELT API:*
Queries https://api.gdeltproject.org/api/v2/doc/doc with three time periods (30 days, 3 months, 1 year) matching news cycle characteristics. CRITICAL: Wraps keyword in quotes (line 242: search_query = f'"{keyword}"') for exact phrase matching, same pattern as PapersCollector. Makes THREE API mode queries per period: ArtList (article metadata with maxrecords=250), TimelineVol (volume trends), ToneChart (sentiment distribution). No API key required - GDELT is open access. Returns articles_30d, articles_3m, articles_1y, articles_total plus geographic data (source_countries dict, geographic_diversity), media diversity (unique_domains, top_domains), and sentiment metrics (avg_tone -1.0 to 1.0, tone_distribution with positive/neutral/negative counts). Calculates volume_intensity from timeline data. Derives media_attention (high: >500 articles, medium: 100-500, low: <100), coverage_trend (increasing/stable/decreasing), sentiment_trend (positive/neutral/negative), mainstream_adoption (mainstream: >50 domains, emerging: >20, niche: <20). Uses .get() for safe field access on domain, sourcecountry, seendate which may be null/missing.

*FinanceCollector (finance.py) - Yahoo Finance with DeepSeek Ticker Discovery:*
This collector is UNIQUE because it already uses DeepSeek LLM for intelligent data discovery. The workflow: (1) Check instance-level _ticker_cache dict for keyword, (2) If cache miss, call DeepSeek API with prompt requesting 5-10 relevant stock ticker symbols for the technology, (3) Validate tickers with regex ^[A-Z]{1,5}$ and cache results per instance, (4) Fall back to ["QQQ", "XLK"] tech ETFs if DeepSeek fails or returns invalid tickers. CRITICAL: yfinance is synchronous, so it's wrapped in ThreadPoolExecutor via loop.run_in_executor (lines 284-315) for async compatibility with FastAPI event loop. Queries Yahoo Finance for three periods (1 month, 6 months, 2 years) matching financial market cycles. Returns companies_found, tickers list, total_market_cap, avg_market_cap plus price performance (avg_price_change_1m, avg_price_change_6m, avg_price_change_2y), volume metrics, volatility metrics. Derives market_maturity (emerging: <$10B or >60% vol, developing: middle, mature: >$100B and <30% vol), investor_sentiment (positive/neutral/negative), investment_momentum (accelerating/steady/decelerating), volume_trend. Thread-safe error tracking using tuple return pattern (data, errors) from sync functions instead of shared list mutations. Explicit executor.shutdown(wait=True, cancel_futures=True) in finally block to prevent resource leaks.

**Graceful Degradation - Minimum 3 of 5 Collectors (hype_classifier.py:63-69):**
After parallel execution completes, the classifier counts successful collectors (those returning non-None results). If <3 collectors succeeded, it raises Exception with message "Insufficient data: only X/5 collectors succeeded. Minimum 3 required. Errors: [...]" which the analysis router catches and converts to HTTP 503 Service Unavailable. This graceful degradation pattern means the system can tolerate up to 2 collector failures and still produce a classification, but won't attempt analysis with severely incomplete data.

**DeepSeek Two-Stage Analysis (deepseek.py:49-101):**
The DeepSeekAnalyzer performs a two-stage classification workflow: (1) Per-source analysis for each of the 5 collectors (5 LLM API calls), (2) Final synthesis aggregating all per-source results (1 LLM API call). Total: 6 DeepSeek API calls per analysis.

*Stage 1 - Per-Source Analysis (deepseek.py:103-122):*
For each collector that succeeded, the analyzer calls _analyze_source() which builds a specialized prompt template for that data source. Each template includes the phase definitions, the collected metrics in formatted text, and interpretation guidance with specific thresholds for that source. For example, the social media prompt uses thresholds like "innovation_trigger: <50 total mentions, peak: >200 in 30d, accelerating momentum" while the academic prompt uses "innovation_trigger: <10 papers in 2y, peak: accelerating publications, many authors". The prompts explicitly request JSON-only responses with no markdown: {"phase": "...", "confidence": 0.75, "reasoning": "..."}. Temperature is set to 0.3 for deterministic classification (vs. 0.7+ for creative text). Each source analysis returns a dict with phase, confidence, reasoning.

*Stage 2 - Synthesis (deepseek.py:124-141):*
After collecting individual source analyses, the synthesize method builds a final prompt that presents all per-source results with their phases, confidence scores, and reasoning. The synthesis prompt instructs the LLM to: weight sources by confidence scores, consider that social media trends faster than academic validation, recognize that patents and finance lag behind hype but indicate real investment, and handle conflicting signals which may indicate transition phases. The final analysis includes the per_source_analyses dict for transparency.

*Response Parsing and Validation (deepseek.py:368-438):*
The _call_deepseek method handles the HTTP request to https://api.deepseek.com/v1/chat/completions with Bearer token auth, 60-second timeout, and temperature parameter. After receiving the response, it strips markdown code blocks using the pattern from FinanceCollector: checks if content starts with "```", splits on "```", checks for "json" prefix, then strips again. Parses the JSON and validates: (1) All required fields present (phase, confidence, reasoning), (2) Phase is in VALID_PHASES list (innovation_trigger, peak, trough, slope, plateau), (3) Confidence is float between 0-1. Raises ValueError for invalid structure, httpx.HTTPStatusError for 401/429 errors, json.JSONDecodeError for invalid JSON.

**Database Persistence (hype_classifier.py:202-264):**
After successful DeepSeek analysis, the classifier persists the result to SQLite. Calculates created_at = datetime.now() and expires_at = created_at + timedelta(hours=settings.cache_ttl_hours). Serializes ALL collector data to JSON strings (social_data, papers_data, patents_data, news_data, finance_data) for the TEXT columns. CRITICALLY: Also serializes per_source_analyses from the DeepSeek analysis result to per_source_analyses_data column (line 233). This ensures cached responses include the same per-source breakdowns as fresh analyses. Inserts into analyses table with 11 fields total. The database schema has idempotent migration logic (database.py:34-40) that checks for per_source_analyses_data column existence via PRAGMA table_info and only runs ALTER TABLE if needed.

**Response Assembly (hype_classifier.py:266-320):**
The final response combines: (1) Core classification (keyword, phase, confidence, reasoning) from DeepSeek synthesis, (2) Per-source analyses dict (5 individual classifications), (3) Raw collector_data dict for transparency, (4) Metadata (timestamp, cache_hit, expires_at), (5) Error tracking (collectors_succeeded count, partial_data boolean, errors list combining collector and analysis failures). This 13-field response structure matches the AnalyzeResponse Pydantic model in the router.

**Current Limitation - Niche Technologies:**
For niche technologies like "plant cell culture" or "CRISPR base editing", the keyword may be too specific to return sufficient results from the APIs. For example:
- SocialCollector: "plant cell culture" might return mentions_30d=15, mentions_total=42 (well below mainstream thresholds)
- PapersCollector: Exact phrase "plant cell culture" might return publications_2y=3 (very low)
- PatentsCollector: _text_all operator requires ALL words present, so "plant cell culture" must match exactly (might return patents_2y=8)
- NewsCollector: Exact phrase in quotes might return articles_30d=12 (low coverage)
- FinanceCollector: DeepSeek might struggle to find companies specifically focused on "plant cell culture" as a distinct business segment

With these low result counts, multiple collectors may effectively "fail" (return minimal/zero data) even though the API requests technically succeed. If <3 collectors return meaningful data, the system raises "Insufficient data" exception and returns HTTP 503, preventing any analysis.

### What Query Expansion Needs to Do

**Niche Detection Strategy:**
The task specifies using SocialCollector metrics as the niche detection signal: mentions_30d < 50 OR mentions_total < 100. This makes sense because social media is the fastest-moving indicator - if there's low Hacker News discussion, it's a strong signal the keyword is either truly niche or needs broader search terms. The detection happens AFTER SocialCollector runs but BEFORE we fail on insufficient data.

**Query Expansion Workflow:**
When niche is detected, the system should:
1. Use DeepSeek LLM to generate 3-5 related/broader search terms for the keyword
2. Validate the expanded terms (relevance check, no generic terms like "technology" or "system")
3. Re-run the 4 collectors (Social, Papers, Patents, News) with COMBINED queries (original keyword OR expanded terms)
4. NOT apply expansion to FinanceCollector (which already uses DeepSeek for ticker discovery and doesn't benefit from query expansion)
5. Continue with normal DeepSeek analysis using the expanded data

**Why NOT FinanceCollector:**
FinanceCollector already uses DeepSeek to map keywords to stock tickers (finance.py:166-271). It doesn't search for the keyword text directly - instead it asks DeepSeek "which companies are investing in this technology" and gets ticker symbols. Query expansion wouldn't help because the LLM is already interpreting the keyword contextually. Adding query expansion would be redundant and might confuse the ticker discovery process.

**Integration Points:**

*Where Niche Detection Happens:*
After _run_collectors() completes in HypeCycleClassifier.classify() (after line 60), check if social_data exists and meets niche criteria: social_data.get("mentions_30d", 0) < 50 OR social_data.get("mentions_total", 0) < 100. If niche detected AND collectors_succeeded < 3, trigger query expansion rather than failing immediately.

*Where Query Expansion Logic Lives:*
New method in HypeCycleClassifier: async def _expand_query_and_rerun(keyword, collector_results, errors) -> tuple. This method: (1) Calls DeepSeek with prompt requesting 3-5 related search terms, (2) Validates the expanded terms, (3) Re-instantiates Social/Papers/Patents/News collectors, (4) Modifies their collect() calls to use expanded queries, (5) Returns updated collector_results and errors.

*How Collectors Accept Expanded Queries:*
Each collector's collect() method currently takes a single keyword string. For query expansion, we need to modify the method signature to: async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None). When expanded_terms is provided, the collector constructs API queries that match the original keyword OR any of the expanded terms.

*API Query Construction Patterns:*

For SocialCollector: Algolia API supports OR via multiple query parameter (docs show you can pass an array). Alternatively, construct separate queries for each term and aggregate results, deduplicating by story ID.

For PapersCollector: Semantic Scholar query parameter supports Boolean operators. Instead of query: f'"{keyword}"', use query: f'"{keyword}" OR "{term1}" OR "{term2}"' (maintaining quote wrapping for each term).

For PatentsCollector: PatentsView query JSON supports _or at the root level. Modify the query from lines 277-287 to have _or wrapping multiple _text_all clauses, one for each term.

For NewsCollector: GDELT query parameter supports OR operator. Instead of search_query = f'"{keyword}"', use search_query = f'"{keyword}" OR "{term1}" OR "{term2}"'.

*Metadata in Response:*
Add two new fields to the response assembly in _assemble_response: query_expansion_applied (bool), expanded_terms (List[str]). Update the AnalyzeResponse Pydantic model in analysis.py to include these fields. Persist to database by adding two new columns: query_expansion_applied INTEGER (0/1 for bool), expanded_terms_data TEXT (JSON-serialized list).

**Preserving Quality for Mainstream Technologies:**
If mentions_30d >= 50 AND mentions_total >= 100, niche detection returns False and query expansion is never triggered. The system continues with the original single-keyword queries. This ensures "quantum computing" or "blockchain" get the same precise, high-quality results as before - no change in behavior for mainstream technologies.

**Error Handling and Fallbacks:**
If DeepSeek query expansion call fails (rate limit, timeout, invalid response), log the error, add to errors list, but DON'T block the analysis - proceed with original collector results and fail with HTTP 503 if still <3 collectors. If query expansion succeeds but re-running collectors still yields <3 successful, fail with HTTP 503 including both original and expansion errors for transparency.

**Cache Behavior with Query Expansion:**
When caching expanded queries, store the expansion metadata (query_expansion_applied=True, expanded_terms=["term1", "term2"]) so cache hits return the same metadata. The cache key remains the original keyword - we don't want separate cache entries for expanded vs. non-expanded versions of the same keyword, because the expansion decision is deterministic based on social metrics.

### Technical Reference Details

#### Key Functions and Their Signatures

**HypeCycleClassifier (hype_classifier.py):**
```python
class HypeCycleClassifier:
    MINIMUM_SOURCES_REQUIRED = 3  # Threshold for analysis
    COLLECTOR_TIMEOUT_SECONDS = 120.0  # Per-batch timeout

    async def classify(self, keyword: str, db: aiosqlite.Connection) -> Dict[str, Any]
    async def _check_cache(self, keyword: str, db: aiosqlite.Connection) -> Optional[Dict[str, Any]]
    async def _run_collectors(self, keyword: str) -> tuple[Dict[str, Optional[Dict[str, Any]]], List[str]]
    async def _persist_result(self, keyword: str, analysis: Dict[str, Any], collector_results: Dict[str, Optional[Dict[str, Any]]], db: aiosqlite.Connection) -> Dict[str, Any]
    def _assemble_response(self, keyword: str, analysis: Dict[str, Any], collector_results: Dict[str, Optional[Dict[str, Any]]], collector_errors: List[str], cache_hit: bool, created_at: str, expires_at: str) -> Dict[str, Any]

    # NEW METHODS NEEDED:
    async def _detect_niche(self, collector_results: Dict[str, Optional[Dict[str, Any]]]) -> bool
    async def _expand_query_and_rerun(self, keyword: str, collector_results: Dict[str, Optional[Dict[str, Any]]], errors: List[str]) -> tuple[Dict[str, Optional[Dict[str, Any]]], List[str], List[str]]
```

**BaseCollector Interface (base.py):**
```python
class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, keyword: str) -> Dict[str, Any]

    # MODIFIED SIGNATURE NEEDED:
    async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]
```

**SocialCollector Key Metrics (social.py:115-143):**
```python
{
    "mentions_30d": int,      # PRIMARY niche detection metric
    "mentions_6m": int,
    "mentions_1y": int,
    "mentions_total": int,    # PRIMARY niche detection metric
    "avg_points_30d": float,
    "avg_comments_30d": float,
    "sentiment": float,       # -1.0 to 1.0
    "recency": str,           # "high" | "medium" | "low"
    "growth_trend": str,      # "increasing" | "stable" | "decreasing"
    "momentum": str,          # "accelerating" | "steady" | "decelerating"
    "top_stories": List[Dict],
    "errors": List[str]
}
```

**DeepSeekAnalyzer (deepseek.py):**
```python
class DeepSeekAnalyzer:
    API_URL = "https://api.deepseek.com/v1/chat/completions"
    TIMEOUT = 60.0
    VALID_PHASES = ["innovation_trigger", "peak", "trough", "slope", "plateau"]

    async def analyze(self, keyword: str, collector_data: Dict[str, Any]) -> Dict[str, Any]
    async def _analyze_source(self, source_name: str, source_data: Dict[str, Any], keyword: str) -> Dict[str, Any]
    async def _synthesize_analyses(self, keyword: str, per_source_results: Dict[str, Any]) -> Dict[str, Any]
    async def _call_deepseek(self, prompt: str, temperature: float = 0.3) -> Dict[str, Any]

    # NEW METHOD NEEDED FOR QUERY EXPANSION:
    async def generate_expanded_terms(self, keyword: str) -> List[str]
```

#### Database Schema (database.py:17-44)

**Current analyses table:**
```sql
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phase TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    social_data TEXT,           -- JSON
    papers_data TEXT,           -- JSON
    patents_data TEXT,          -- JSON
    news_data TEXT,             -- JSON
    finance_data TEXT,          -- JSON
    per_source_analyses_data TEXT,  -- JSON (added via migration)
    expires_at TIMESTAMP
);
CREATE INDEX idx_keyword ON analyses(keyword);
CREATE INDEX idx_expires ON analyses(expires_at);
```

**NEW columns needed:**
```sql
ALTER TABLE analyses ADD COLUMN query_expansion_applied INTEGER DEFAULT 0;  -- 0=False, 1=True
ALTER TABLE analyses ADD COLUMN expanded_terms_data TEXT;  -- JSON array ["term1", "term2"]
```

#### API Query Patterns for Expanded Terms

**SocialCollector - Hacker News Algolia (social.py:181-189):**
```python
# Current single-term query
response = await client.get(
    self.API_URL,
    params={
        "query": keyword,
        "tags": "story",
        "numericFilters": numeric_filter,
        "hitsPerPage": 20
    }
)

# Expanded query pattern (Algolia supports OR implicitly with multiple words)
# Or make separate requests and aggregate, deduping by objectID
if expanded_terms:
    all_hits = []
    seen_ids = set()
    for term in [keyword] + expanded_terms:
        response = await client.get(self.API_URL, params={"query": term, ...})
        for hit in response.json()["hits"]:
            if hit["objectID"] not in seen_ids:
                all_hits.append(hit)
                seen_ids.add(hit["objectID"])
```

**PapersCollector - Semantic Scholar (papers.py:223-232):**
```python
# Current single-term query
response = await client.get(
    self.API_URL,
    params={
        "query": f'"{keyword}"',
        "year": year_filter,
        "fields": fields,
        "limit": 100
    },
    headers=headers
)

# Expanded query pattern
if expanded_terms:
    query_str = " OR ".join([f'"{keyword}"'] + [f'"{term}"' for term in expanded_terms])
    params["query"] = query_str
```

**PatentsCollector - PatentsView (patents.py:277-318):**
```python
# Current single-term query
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

# Expanded query pattern
if expanded_terms:
    text_clauses = []
    for term in [keyword] + expanded_terms:
        text_clauses.append({
            "_or": [
                {"_text_all": {"patent_title": term}},
                {"_text_all": {"patent_abstract": term}}
            ]
        })
    query = {
        "_and": [
            {"_or": text_clauses},  # Match ANY of the terms
            {"_gte": {"patent_date": date_start}},
            {"_lte": {"patent_date": date_end}}
        ]
    }
```

**NewsCollector - GDELT (news.py:238-255):**
```python
# Current single-term query
search_query = f'"{keyword}"'
artlist_params = {**base_params, "mode": "ArtList", "maxrecords": 250}

# Expanded query pattern
if expanded_terms:
    terms_str = " OR ".join([f'"{keyword}"'] + [f'"{term}"' for term in expanded_terms])
    search_query = terms_str
```

#### Response Structure (analysis.py:39-53)

**Current AnalyzeResponse:**
```python
class AnalyzeResponse(BaseModel):
    keyword: str
    phase: str
    confidence: float
    reasoning: str
    timestamp: str
    cache_hit: bool
    expires_at: str
    per_source_analyses: Dict[str, Any]
    collector_data: Dict[str, Any]
    collectors_succeeded: int
    partial_data: bool
    errors: List[str]

    # NEW FIELDS NEEDED:
    query_expansion_applied: bool
    expanded_terms: List[str]
```

#### Configuration (config.py)

**Settings class should include:**
```python
class Settings(BaseSettings):
    deepseek_api_key: str  # Already exists, used for both analysis and query expansion
    cache_ttl_hours: int = 24  # Already exists
    # No new settings needed - reuse existing DeepSeek API key
```

#### File Locations for Implementation

- **Niche detection logic:** `backend/app/analyzers/hype_classifier.py` (new method _detect_niche around line 153)
- **Query expansion orchestration:** `backend/app/analyzers/hype_classifier.py` (new method _expand_query_and_rerun around line 200)
- **DeepSeek expansion prompt:** `backend/app/analyzers/deepseek.py` (new method generate_expanded_terms around line 440)
- **Collector modifications:** All four collectors in `backend/app/collectors/` (modify collect() signature and query construction)
- **Database migration:** `backend/app/database.py` (add migration logic similar to lines 34-40 for new columns)
- **Response model update:** `backend/app/routers/analysis.py` (add fields to AnalyzeResponse around line 53)
- **Cache persistence:** `backend/app/analyzers/hype_classifier.py` (update _persist_result around line 236 and _check_cache around line 125)
- **Tests:** New test file `backend/tests/test_query_expansion.py` plus updates to existing collector tests

#### Critical Patterns to Follow

1. **Safe dictionary access:** Always use .get() with defaults for API response fields (pattern from all collectors)
2. **Exact phrase matching:** Maintain quote wrapping for all search terms in expanded queries (pattern from Papers/News collectors)
3. **Error aggregation:** Track errors in List[str] and include in response, never block on non-fatal errors (pattern from all collectors)
4. **Async/await consistency:** All collector methods are async, use asyncio.gather for parallel execution (pattern from HypeCycleClassifier)
5. **JSON serialization:** All database TEXT columns store JSON.dumps() output, deserialize with json.loads() on retrieval (pattern from _persist_result)
6. **Graceful degradation:** Continue with partial data if possible, only fail if <3 collectors (pattern from HypeCycleClassifier)
7. **Response validation:** Validate DeepSeek JSON responses for required fields and value ranges (pattern from DeepSeekAnalyzer._call_deepseek)
8. **Markdown stripping:** Handle ```json code blocks in LLM responses (pattern from DeepSeekAnalyzer and FinanceCollector)
9. **Instance-level caching:** Use instance variables for per-request caching, not class variables (pattern from FinanceCollector._ticker_cache)
10. **Idempotent migrations:** Check for column existence before ALTER TABLE (pattern from database.py lines 34-40)

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
- [2025-12-03] Task started, context gathering completed
- [2025-12-03] Implemented database migration for query_expansion_applied and expanded_terms_data columns (database.py)
- [2025-12-03] Implemented DeepSeek.generate_expanded_terms() with validation and generic term filtering (deepseek.py:440-553)
- [2025-12-03] Implemented HypeCycleClassifier._detect_niche() method using social media metrics (hype_classifier.py:240-270)
- [2025-12-03] Implemented HypeCycleClassifier._expand_query_and_rerun() orchestration (hype_classifier.py:272-353)
- [2025-12-03] Modified BaseCollector signature to accept Optional[List[str]] expanded_terms (base.py)
- [2025-12-03] Modified SocialCollector to aggregate results from multiple terms (social.py:157-267)
- [2025-12-03] Modified PapersCollector with OR query construction (papers.py:190-274)
- [2025-12-03] Modified PatentsCollector with nested OR clauses (patents.py:215-320)
- [2025-12-03] Modified NewsCollector with OR query construction (news.py:213-312)
- [2025-12-03] Updated AnalyzeResponse model with query_expansion_applied and expanded_terms fields (analysis.py:54-55)
- [2025-12-03] Created comprehensive test suite: test_query_expansion.py (12 tests, all passing)
- [2025-12-03] Initial testing revealed critical bugs in OR query syntax
- [2025-12-03] Fixed PapersCollector: Changed " OR " to " | " for Semantic Scholar syntax (papers.py:233)
- [2025-12-03] Fixed NewsCollector: Added parentheses wrapper for GDELT OR syntax (news.py:249)
- [2025-12-03] Created test_expansion_comparison.py script for before/after verification
- [2025-12-03] Verification testing with "plant cell culture" showed massive improvements:
  - Papers: 93 → 2,535 publications (+2,626%)
  - Patents: 87 → 942 patents (+983%)
  - Social: 1 → 11 mentions (+1,000%)
  - News: 9 → 76 articles (+744%)
- [2025-12-03] All 7 success criteria met and verified
- [2025-12-03] Code review completed: 0 critical issues, 4 warnings documented for future improvements
- [2025-12-03] Task completed successfully
