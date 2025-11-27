---
name: h-implement-patents-collector
branch: feature/patents-collector
status: completed
created: 2025-11-25
---

# Patent Data Collector - PatentsView

## Problem/Goal
Implement the patent data collector for the Gartner Hype Cycle Analyzer. This collector will gather patent filing signals about a given technology by querying the PatentsView API. It will analyze patent filing trends, assignee diversity, geographical distribution, and innovation velocity over time to provide insights into industrial investment and commercialization activity around the technology. This is one of the 5 data sources that feed into the DeepSeek LLM for hype cycle classification.

## Success Criteria
- [x] `backend/app/collectors/patents.py` module created with PatentsCollector class (572 lines)
- [x] PatentsView API integration working (search patents by keyword)
- [x] Collector returns structured data: patent count, filing trends, assignee diversity
- [x] Time-based analysis (2y/5y/10y periods, geographical distribution)
- [x] Error handling for API failures (rate limits, missing data, network issues)
- [x] Unit tests for collector logic with mocked API responses (20 tests passing)
- [x] Returns data in standardized format compatible with DeepSeek analyzer
- [x] Real API test successful (889 patents found for "quantum computing" with _text_all operator)
- [x] Documentation updated in CLAUDE.md (will be completed by service-documentation agent)

## Context Manifest

### How Patent Data Collection Fits Into the System

The Gartner Hype Cycle Analyzer is architected as a parallel data collection system where five specialized collectors gather signals about emerging technologies from different domains - social media, research papers, patents, news, and financial data. These signals are then synthesized by a DeepSeek LLM to classify the technology's position on Gartner's Hype Cycle. The PatentsCollector you're implementing is the third of these five critical data sources, specifically responsible for capturing industrial innovation signals that indicate commercial investment, R&D activity, and intellectual property strategy around a technology.

**The Complete Request Flow:**

When a user enters a technology keyword like "quantum computing" into the frontend interface at `C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html` and clicks "Analyze", the JavaScript frontend (`frontend\app.js`, line 22-45) sends a POST request to `http://localhost:8000/api/analyze` with the payload `{"keyword": "quantum computing"}`. This endpoint will be implemented in `backend\app\routers\analysis.py` (currently pending as task h-implement-hype-classifier).

The analysis router first performs a cache lookup against the SQLite database. The database schema is defined in `backend\app\database.py` (lines 17-35) with an `analyses` table containing five separate JSON TEXT columns for each collector's data: `social_data`, `papers_data`, `patents_data`, `news_data`, and `finance_data`. Your PatentsCollector's output will be stored in the `patents_data` column as a JSON string. The router queries for existing analyses where `keyword = ?` AND `expires_at > CURRENT_TIMESTAMP`. The default cache TTL is 24 hours, configurable via `CACHE_TTL_HOURS` environment variable in `.env` (see `backend\app\config.py` line 16).

On a cache miss, the HypeCycleClassifier orchestrator (task h-implement-deepseek-integration, pending) executes all five collectors in parallel using `asyncio.gather()`. This is why the `BaseCollector` interface at `backend\app\collectors\base.py` (lines 8-22) mandates an `async def collect(keyword: str) -> Dict[str, Any]` signature - all collectors must be non-blocking to enable concurrent execution without stalling the FastAPI event loop. The system is designed with graceful degradation: if 1-2 collectors fail due to API rate limits, network timeouts, or invalid queries, the analysis proceeds with the available data, though the LLM will note the missing signals in its confidence score.

**Why Patent Data Matters for Hype Cycle Classification:**

Patent filing signals are fundamentally different from social media buzz or academic publications. Patents indicate:

1. **Commercial investment**: Companies only file patents when they believe a technology has commercialization potential, suggesting movement beyond pure research ("Innovation Trigger") toward practical application ("Slope of Enlightenment")

2. **Industrial maturity**: A surge in patent filings often precedes or coincides with the "Peak of Inflated Expectations" as companies rush to establish IP positions. A plateau or decline may indicate movement through the "Trough of Disillusionment" as hype fades.

3. **Geographical distribution**: Technologies with patents filed across multiple countries (US, Europe, China, Japan) indicate global industrial interest, suggesting broader commercialization efforts typically seen in "Slope of Enlightenment" or "Plateau of Productivity" phases.

4. **Assignee diversity**: A technology with patents from multiple companies/institutions versus dominated by 1-2 players reveals market structure. Broad participation suggests mature commercialization; narrow ownership suggests early-stage or niche technology.

5. **Filing velocity**: The rate of new patent applications over time reveals whether industrial R&D is accelerating (early hype, moving toward Peak), sustaining (Slope/Plateau), or declining (Trough).

The DeepSeek LLM receives data from all five collectors and uses prompt engineering to map these multi-dimensional signals to Gartner's five phases. Your patents collector will help the LLM distinguish between technologies that have academic research but no commercial traction (still at Innovation Trigger) versus those with both research AND patent activity (likely at Peak or moving into Trough), versus those with sustained patent filing rates indicating mature commercialization (Slope or Plateau).

### The BaseCollector Contract and Reference Implementations

Every collector in this system inherits from `BaseCollector` defined in `backend\app\collectors\base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseCollector(ABC):
    """Abstract base class for all data collectors"""

    @abstractmethod
    async def collect(self, keyword: str) -> Dict[str, Any]:
        """
        Collect data for the given keyword.

        Args:
            keyword: Technology keyword to analyze

        Returns:
            Dictionary containing collected metrics
        """
        pass
```

This abstract method signature is your contract. The return dictionary structure MUST be JSON-serializable (no datetime objects, no numpy arrays, only dict, list, str, int, float, bool, None) because it gets stored directly in the SQLite TEXT column via `json.dumps()`.

**Critical Pattern: Graceful Error Handling**

Both existing collectors (`SocialCollector` at `backend\app\collectors\social.py` and `PapersCollector` at `backend\app\collectors\papers.py`) demonstrate a critical architectural pattern: **collectors NEVER raise exceptions to the caller**. This is essential for graceful degradation in the parallel collection architecture.

The error handling pattern (visible in both collectors):

1. Initialize an `errors = []` list at the start of `collect()` to track non-fatal issues
2. Wrap the entire collection logic in a try-except block
3. Pass the `errors` list to helper methods like `_fetch_period()` so they can append error messages without raising exceptions
4. If an API call fails (rate limit, timeout, network error), the helper method returns `None` and appends a descriptive error message to the list
5. After all API calls complete, check if ALL calls failed: `if all(d is None for d in [data_2y, data_5y]):` - if so, return `_error_response()` with graceful fallback data
6. If SOME calls succeeded, extract metrics from successful responses, using defaults (0, empty lists) for failed calls
7. Always return a fully-populated dictionary with all expected fields, even if some contain fallback values
8. Include the `errors` list in the return dictionary so the LLM can see what data sources were unavailable

Example error handling from `PapersCollector._fetch_period()` (lines 239-258):

```python
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        errors.append("Rate limited")
    elif e.response.status_code == 400:
        errors.append("Invalid query parameters")
    else:
        errors.append(f"HTTP {e.response.status_code}")
    return None

except httpx.TimeoutException:
    errors.append("Request timeout")
    return None

except httpx.RequestError as e:
    errors.append(f"Network error: {type(e).__name__}")
    return None
```

This pattern ensures that if the Semantic Scholar API is rate-limiting requests but Hacker News and PatentsView APIs are working, the analysis can still proceed with 60% of the data sources available.

**Reference Implementation: SocialCollector Pattern**

The SocialCollector at `backend\app\collectors\social.py` demonstrates the complete structural pattern:

**Module Structure (lines 1-18):**
- Module docstring explaining data source and metrics collected
- Imports: `datetime`, `timedelta`, `httpx`, `math` (for calculations), type hints
- Class inherits from `BaseCollector`
- Class constants: `API_URL`, `TIMEOUT` (30.0 seconds)

**The collect() Method Flow (lines 19-151):**

1. Calculate current timestamp: `now = datetime.now()`
2. Create ISO timestamp for response: `collected_at = now.isoformat()`
3. Calculate time period boundaries as Unix timestamps (30 days ago, 6 months ago, 1 year ago)
4. Initialize error tracking: `errors = []`
5. Wrap everything in try-except that catches any unexpected exception
6. Create async HTTP client context: `async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:`
7. Make multiple API calls using helper method `_fetch_period(client, keyword, start_ts, end_ts, errors)` - note errors list is passed by reference
8. Check for total failure: `if all(d is None for d in [data_30d, data_6m, data_1y]):`
9. Extract raw metrics from successful responses, using safe access patterns: `data_30d["nbHits"] if data_30d else 0`
10. Calculate derived insights by calling helper methods: `_calculate_sentiment()`, `_calculate_recency()`, `_calculate_growth_trend()`, `_calculate_momentum()`
11. Return structured dictionary with metadata, raw metrics, derived insights, sample data for LLM context, and error list

**Helper Method Pattern: _fetch_period() (lines 153-210):**

This is where the actual HTTP call happens. Note the error handling:

```python
async def _fetch_period(
    self,
    client: httpx.AsyncClient,
    keyword: str,
    start_ts: int,
    end_ts: int | None,
    errors: List[str]
) -> Dict[str, Any] | None:
    try:
        response = await client.get(
            self.API_URL,
            params={...}
        )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            errors.append("Rate limited")
        else:
            errors.append(f"HTTP {e.response.status_code}")
        return None

    except httpx.TimeoutException:
        errors.append("Request timeout")
        return None

    except httpx.RequestError as e:
        errors.append(f"Network error: {type(e).__name__}")
        return None
```

Note how every exception path appends to `errors` and returns `None` rather than raising. The caller checks for `None` to determine if data is available.

**Reference Implementation: PapersCollector Advanced Patterns**

The PapersCollector at `backend\app\collectors\papers.py` demonstrates additional patterns you need:

**API Key Authentication Pattern (lines 216-219):**

```python
from app.config import get_settings

settings = get_settings()
headers = {}
if settings.semantic_scholar_api_key:
    headers["x-api-key"] = settings.semantic_scholar_api_key

response = await client.get(
    self.API_URL,
    params={...},
    headers=headers  # Empty dict if no key configured
)
```

This pattern allows the collector to work with or without an API key. When a key is configured (via `.env` file), it's added to the request headers for higher rate limits. When no key is present, the request proceeds without authentication, relying on the API's public tier.

**Safe Dictionary Access Pattern (lines 70, 78, 107):**

```python
# NEVER do this (raises KeyError if field missing):
publications_2y = data_2y["total"]

# ALWAYS do this (returns default if field missing):
publications_2y = data_2y.get("total", 0) if data_2y else 0

# For nested access:
if data_2y and data_2y.get("data"):
    papers = data_2y.get("data", [])
    for paper in papers:
        citations = paper.get("citationCount", 0) or 0  # Handle None case too
```

This is critical because API responses may omit fields entirely (not just set them to null). The PatentsView API is known for inconsistent field presence depending on the patent record completeness.

**Exact Phrase Matching Pattern (line 226):**

```python
params={
    "query": f'"{keyword}"',  # Always wrap in quotes for exact phrase matching
    "year": year_filter,
    ...
}
```

This is a CRITICAL lesson from PapersCollector testing. Without quotes, a search for "quantum computing" searches for "quantum" OR "computing" anywhere in the document, returning millions of false positives. With quotes, it searches for the exact phrase "quantum computing", reducing results by 99.9% but making them actually relevant. You MUST apply this pattern to patent title/abstract searches.

**Time Window Selection for Academic Data:**

SocialCollector uses 30 days, 6 months, 1 year (fast-moving social media cycles).
PapersCollector uses 2 years, 5 years (slower academic publishing cycles).

For patents, you should use time windows that match the patent filing lifecycle:
- 2 years: Very recent filings (often still pending, not yet published)
- 5 years: Recent grants (shows current industrial R&D)
- 10 years: Historical baseline (shows technology maturity)

This aligns with the typical 18-24 month delay between filing and publication in most patent systems.

### PatentsView API Integration Details

You will use the PatentsView API, which provides access to USPTO (United States Patent and Trademark Office) patent data through a free, open JSON API. This is the recommended API for this task because:

1. No API key required (truly open access)
2. Comprehensive US patent data from 1976-present
3. Supports full-text search in titles and abstracts
4. Provides assignee (company/institution) information
5. Includes geographic data for assignees
6. Fast response times with well-documented JSON structure

**API Endpoint Structure:**

PatentsView exposes a search API at `https://api.patentsview.org/patents/query` using POST requests (not GET like the other collectors). The request body is JSON with a query DSL:

```json
{
  "q": {
    "_and": [
      {
        "_or": [
          {"_text_all": {"patent_title": "quantum computing"}},
          {"_text_all": {"patent_abstract": "quantum computing"}}
        ]
      },
      {"_gte": {"patent_date": "2020-01-01"}},
      {"_lte": {"patent_date": "2024-12-31"}}
    ]
  },
  "f": [
    "patent_id",
    "patent_title",
    "patent_abstract",
    "patent_date",
    "assignees",
    "patent_num_times_cited_by_us_patents"
  ],
  "o": {"per_page": 100},
  "s": [{"patent_date": "desc"}]
}
```

**IMPORTANT: Using _text_all for Relevant Results**

The PatentsView API uses the `_text_all` operator to ensure ALL words in the keyword are present in the results. This is critical for multi-word technology terms like "quantum computing" to avoid false positives:

- `_text_all`: Matches documents containing ALL words (e.g., "quantum computing" requires both "quantum" AND "computing")
- `_text_any`: Matches documents containing ANY word (e.g., "quantum computing" would match "quantum mechanics" or "distributed computing")

```python
keyword = "quantum computing"
query_body = {
    "q": {
        "_and": [
            {
                "_or": [
                    {"_text_all": {"patent_title": keyword}},
                    {"_text_all": {"patent_abstract": keyword}}
                ]
            },
            {"_gte": {"patent_date": "2020-01-01"}},
            {"_lte": {"patent_date": "2024-12-31"}}
        ]
    },
    ...
}
```

Using `_text_all` ensures that only patents containing ALL words from the keyword are returned, significantly reducing false positives for multi-word technology terms.

**Response Structure:**

```json
{
  "patents": [
    {
      "patent_number": "11123456",
      "patent_title": "Method for Quantum Computing Error Correction",
      "patent_date": "2023-09-15",
      "patent_year": "2023",
      "assignees": [
        {
          "assignee_organization": "IBM",
          "assignee_country": "US"
        }
      ],
      "inventors": [
        {
          "inventor_country": "US"
        }
      ],
      "cited_patent_count": "25"
    }
  ],
  "count": 1247,
  "total_patent_count": 1247
}
```

**Field Presence and Null Handling:**

PatentsView API has notoriously inconsistent field presence:
- `assignee_organization` may be null for individual inventors
- `assignee_country` may be missing entirely for old patents
- `cited_patent_count` may be "0" (string) or null or missing
- `assignees` array may be empty for some patents

You MUST use safe dictionary access patterns throughout:

```python
patent_number = patent.get("patent_number", "unknown")
assignees = patent.get("assignees", [])
for assignee in assignees:
    org = assignee.get("assignee_organization", "Individual")
    country = assignee.get("assignee_country", "Unknown")
```

**Time-Windowed Queries:**

The PatentsView API supports year-based filtering:

```python
query_body = {
    "q": {
        "_and": [
            {
                "_or": [
                    {"_text_all": {"patent_title": keyword}},
                    {"_text_all": {"patent_abstract": keyword}}
                ]
            },
            {
                "_gte": {"patent_year": "2020"}  # Greater than or equal to 2020
            },
            {
                "_lte": {"patent_year": "2024"}  # Less than or equal to 2024
            }
        ]
    },
    ...
}
```

For your implementation, you'll make three separate POST requests with different year filters:
- 2-year window: 2023-2024 (very recent activity)
- 5-year window: 2019-2022 (recent but excluding the 2-year window to avoid double-counting)
- 10-year window: 2013-2018 (historical baseline)

This approach mirrors the time-windowing pattern in SocialCollector and PapersCollector but adapted for patent publishing timelines.

### Metrics to Return from PatentsCollector

Based on the patterns in the existing collectors and the needs of the DeepSeek LLM, your `collect()` method should return:

```python
{
    # Metadata
    "source": "patentsview",
    "collected_at": "2025-11-26T10:30:00",  # ISO format string
    "keyword": "quantum computing",

    # Raw patent counts by time period
    "patents_2y": 45,
    "patents_5y": 120,
    "patents_10y": 200,
    "patents_total": 365,

    # Assignee diversity metrics
    "unique_assignees": 78,
    "top_assignees": [
        {"name": "IBM", "patent_count": 12},
        {"name": "Google LLC", "patent_count": 8},
        {"name": "Microsoft", "patent_count": 7}
    ],  # Top 5 assignees by patent count

    # Geographic distribution
    "countries": {
        "US": 250,
        "CN": 80,
        "JP": 20,
        "DE": 10,
        "GB": 5
    },
    "geographic_diversity": 5,  # Number of unique countries

    # Citation metrics (if available)
    "avg_citations_2y": 8.5,
    "avg_citations_5y": 15.2,

    # Derived insights (calculated from raw metrics)
    "filing_velocity": 0.35,  # Growth rate indicator
    "assignee_concentration": "moderate",  # "concentrated", "moderate", "diverse"
    "geographic_reach": "global",  # "domestic", "regional", "global"
    "patent_maturity": "developing",  # "emerging", "developing", "mature"
    "patent_momentum": "accelerating",  # "accelerating", "steady", "decelerating"
    "patent_trend": "increasing",  # "increasing", "stable", "decreasing"

    # Sample patents for LLM context (top 5 by citation count or recency)
    "top_patents": [
        {
            "patent_number": "11123456",
            "title": "Method for Quantum Computing Error Correction",
            "date": "2023-09-15",
            "assignee": "IBM",
            "country": "US",
            "citations": 25
        },
        ...
    ],

    # Error tracking
    "errors": []  # List of error messages if any API calls failed
}
```

**Derived Insights Calculation Logic:**

Following the pattern from SocialCollector and PapersCollector, you should implement helper methods to calculate derived insights:

**filing_velocity** (like citation_velocity in PapersCollector):
- Compare recent patent rate to historical rate
- `velocity = (patents_2y / 2.0 - patents_5y / 5.0) / (patents_5y / 5.0)`
- Returns float where >0 means accelerating, <0 means decelerating

**assignee_concentration**:
- Calculate what % of patents come from top 3 assignees
- If >50%: "concentrated" (dominated by few companies)
- If 25-50%: "moderate" (healthy competition)
- If <25%: "diverse" (broad participation)

**geographic_reach**:
- Count unique countries with >5% of patents
- If 1 country: "domestic"
- If 2-3 countries: "regional"
- If 4+ countries: "global"

**patent_maturity** (similar to research_maturity in PapersCollector):
- If patents_total > 500 or avg_citations_2y > 15: "mature"
- If patents_total < 50 and avg_citations_2y < 5: "emerging"
- Else: "developing"

**patent_momentum** (similar to research_momentum):
- Compare 2-year rate vs 5-year rate
- `recent_rate = patents_2y / 2.0`
- `historical_rate = patents_5y / 5.0`
- `growth_ratio = recent_rate / historical_rate`
- If growth_ratio > 1.5: "accelerating"
- If growth_ratio < 0.5: "decelerating"
- Else: "steady"

**patent_trend** (similar to research_trend):
- Same as momentum but with 30% threshold instead of 50%
- If diff_ratio > 0.3: "increasing"
- If diff_ratio < -0.3: "decreasing"
- Else: "stable"

### Implementation File Structure

Create `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py` with:

1. Module docstring explaining data source
2. Imports: `datetime`, `httpx`, `Dict`, `Any`, `List` from typing
3. `PatentsCollector` class inheriting from `BaseCollector`
4. Class constants: `API_URL`, `TIMEOUT = 30.0`
5. `async def collect(self, keyword: str) -> Dict[str, Any]` main method
6. Helper methods:
   - `async def _fetch_period(client, keyword, year_start, year_end, errors) -> Dict | None`
   - `def _calculate_filing_velocity(...) -> float`
   - `def _calculate_assignee_concentration(...) -> str`
   - `def _calculate_geographic_reach(...) -> str`
   - `def _calculate_patent_maturity(...) -> str`
   - `def _calculate_patent_momentum(...) -> str`
   - `def _calculate_patent_trend(...) -> str`
   - `def _error_response(...) -> Dict[str, Any]`

### Testing Requirements

Create `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_patents_collector.py` following the patterns in `test_social_collector.py` and `test_papers_collector.py`:

**Required Test Cases (minimum 15 tests):**

1. `test_patents_collector_success()` - Mock successful API responses for all three time periods, verify all fields in response
2. `test_patents_collector_rate_limit()` - Mock 429 HTTP error, verify graceful error response
3. `test_patents_collector_timeout()` - Mock httpx.TimeoutException, verify graceful handling
4. `test_patents_collector_network_error()` - Mock httpx.ConnectError, verify graceful handling
5. `test_patents_collector_zero_results()` - Mock API response with `"count": 0`, verify all fields are 0/empty but structure is valid
6. `test_patents_collector_partial_failure()` - Mock success for 2y window but failures for 5y and 10y, verify partial data collection
7. `test_patents_collector_missing_fields()` - Mock API response with missing `assignees`, `cited_patent_count` fields, verify safe dictionary access prevents KeyError
8. `test_filing_velocity_positive()` - Test velocity calculation with accelerating patent rate
9. `test_filing_velocity_negative()` - Test velocity calculation with decelerating patent rate
10. `test_assignee_concentration_concentrated()` - Test with top 3 assignees having >50% of patents
11. `test_assignee_concentration_diverse()` - Test with broad distribution across many assignees
12. `test_geographic_reach_domestic()` - Test with patents from only 1 country
13. `test_geographic_reach_global()` - Test with patents from 5+ countries
14. `test_patent_maturity_emerging()` - Test with <50 patents and low citations
15. `test_patent_maturity_mature()` - Test with >500 patents or high citations
16. `test_patent_momentum_accelerating()` - Test with recent rate > 1.5x historical
17. `test_patent_trend_increasing()` - Test with >30% increase in recent rate
18. `test_json_serialization()` - Verify entire response can be serialized with `json.dumps()`

**Testing Pattern with Mocked Settings:**

Like PapersCollector tests (lines 14-20), use a fixture to mock settings:

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests to avoid needing .env file"""
    mock_settings_obj = Mock()
    # PatentsView doesn't require API key, but mock anyway for consistency
    with patch("app.collectors.patents.get_settings", return_value=mock_settings_obj):
        yield mock_settings_obj
```

**Mocking POST Requests:**

Unlike the other collectors which use GET requests, PatentsView uses POST. Your mocking needs to target `httpx.AsyncClient.post` instead of `.get`:

```python
with patch("httpx.AsyncClient.post") as mock_post:
    mock_post.side_effect = [
        Mock(json=Mock(return_value=mock_response_2y), raise_for_status=Mock()),
        Mock(json=Mock(return_value=mock_response_5y), raise_for_status=Mock()),
        Mock(json=Mock(return_value=mock_response_10y), raise_for_status=Mock())
    ]

    result = await collector.collect("quantum computing")
    # assertions...
```

### Technical Reference Details

#### PatentsView API Query DSL Structure

```python
# Full query structure example
query = {
    "_and": [
        {
            "_or": [
                {"_text_all": {"patent_title": "quantum computing"}},
                {"_text_all": {"patent_abstract": "quantum computing"}}
            ]
        },
        {"_gte": {"patent_date": "2020-01-01"}},
        {"_lte": {"patent_date": "2024-12-31"}}
    ]
}

fields = [
    "patent_id",
    "patent_title",
    "patent_abstract",
    "patent_date",
    "assignees",
    "patent_num_times_cited_by_us_patents"
]

options = {"size": 100}

# Manual URL encoding required
from urllib.parse import quote
import json

q = json.dumps(query)
f = json.dumps(fields)
o = json.dumps(options)
url = f'https://search.patentsview.org/api/v1/patent/?q={quote(q)}&f={quote(f)}&o={quote(o)}'

# GET request with API key
headers = {"X-Api-Key": api_key}
response = await client.get(url, headers=headers)
```

#### Response Field Mapping

| API Field | Python Variable | Type | Notes |
|-----------|----------------|------|-------|
| `count` | `patents_2y`, `patents_5y`, `patents_10y` | int | Total matching patents |
| `patents[].patent_number` | `top_patents[].patent_number` | str | USPTO patent number |
| `patents[].patent_title` | `top_patents[].title` | str | Patent title |
| `patents[].patent_date` | `top_patents[].date` | str | Grant date (YYYY-MM-DD) |
| `patents[].assignees[].assignee_organization` | `top_assignees[].name` | str | May be null for individuals |
| `patents[].assignees[].assignee_country` | `countries` dict | str | ISO country code |
| `patents[].cited_patent_count` | `avg_citations_2y` | str | Number as string, may be null |

#### Configuration Requirements

No API key required for PatentsView, but you may want to add a configuration option for future extensibility:

In `backend\app\config.py`, you could add (optional):
```python
patentsview_api_key: str | None = None  # For future premium tier
```

But this is NOT required for the current implementation as PatentsView is fully open access.

#### File Locations

**Implementation:**
- Primary file: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py`
- Base class: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py` (reference only, don't modify)
- Config: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py` (reference for settings pattern)

**Testing:**
- Test file: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_patents_collector.py`
- Reference tests:
  - `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_social_collector.py` (14 tests)
  - `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_papers_collector.py` (18 tests)

**Reference implementations:**
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py` - Complete reference for structure, error handling, time windowing, derived insights
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py` - Reference for API key handling, safe dictionary access, exact phrase matching

**Database:**
- Schema: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py` (line 27: `patents_data TEXT` column)
- Your collector's output will be serialized to JSON and stored in this column

**Frontend (for context only, no changes needed):**
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html` - Where user enters keyword
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\app.js` - POST to /api/analyze endpoint

#### Running Tests

```bash
cd "C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend"
source venv/Scripts/activate  # Windows Git Bash

# Run all tests
pytest

# Run only patents tests
pytest tests/test_patents_collector.py

# Run with verbose output
pytest tests/test_patents_collector.py -v

# Run specific test
pytest tests/test_patents_collector.py::test_patents_collector_success -v
```

#### Running the Application to Test Integration

```bash
cd "C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend"
source venv/Scripts/activate
uvicorn app.main:app --reload

# In Python REPL (another terminal):
python
>>> from app.collectors.patents import PatentsCollector
>>> import asyncio
>>> collector = PatentsCollector()
>>> result = asyncio.run(collector.collect("quantum computing"))
>>> print(result)
```

### Prescribed File Reading Order

Before starting implementation, read these files in this order to build complete mental model:

1. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py` - Understand the abstract contract (2 minutes)

2. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py` - Study complete reference implementation:
   - Lines 1-18: Module structure and imports
   - Lines 19-151: Main collect() method flow with error handling
   - Lines 153-210: Helper method _fetch_period() with exception handling
   - Lines 212-329: Derived insight calculation methods
   - Lines 330-367: Error response structure

3. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py` - Study advanced patterns:
   - Lines 216-219: API key configuration pattern
   - Lines 70, 78, 107: Safe dictionary access with .get()
   - Line 226: Exact phrase matching with quote wrapping
   - Lines 239-258: Comprehensive exception handling

4. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_social_collector.py` - Study testing patterns:
   - Lines 14-94: Success test with mock API responses
   - Lines 97-120: Rate limit error test
   - Lines 123-136: Timeout error test
   - Lines 139-151: Network error test

5. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_papers_collector.py` - Study advanced testing:
   - Lines 14-20: Settings mocking fixture
   - Lines 23-135: Comprehensive success test
   - Testing all derived insights calculation methods

6. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py` - Verify patents_data column (line 27)

7. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py` - Understand settings pattern (lines 1-33)

### Critical Success Factors

1. **Never raise exceptions from collect()** - Always return a dictionary, even if it's an error response with zero/empty values

2. **Use safe dictionary access everywhere** - `data.get("field", default)` instead of `data["field"]`

3. **Wrap keyword in quotes for PatentsView** - `f'"{keyword}"'` inside the query DSL for exact phrase matching

4. **Use POST requests not GET** - PatentsView API requires POST with JSON body, unlike the other collectors

5. **Make non-overlapping time windows** - 2023-2024, 2019-2022, 2013-2018 (don't double-count patents)

6. **Return JSON-serializable data only** - No datetime objects, use `.isoformat()` strings

7. **Include "errors" field in response** - So the LLM knows what data was unavailable

8. **Provide LLM context samples** - Include top_patents list with titles and assignees for better reasoning

9. **Calculate derived insights** - Don't just return raw counts, provide filing_velocity, assignee_concentration, etc.

10. **Test comprehensive error handling** - Rate limits, timeouts, network errors, missing fields, zero results, partial failures

### Common Pitfalls to Avoid

1. **Don't use HTTP GET** - PatentsView requires POST with JSON body
2. **Don't forget quote wrapping** - Without quotes, "quantum computing" matches "quantum" OR "computing"
3. **Don't assume fields exist** - Assignees, countries, citation counts may be null/missing
4. **Don't forget to handle string numbers** - `cited_patent_count` is a string "25", not int 25
5. **Don't overlap time windows** - Calculate non-overlapping periods to avoid inflating counts
6. **Don't raise exceptions** - Always return dictionary with error tracking
7. **Don't return datetime objects** - Use .isoformat() strings for JSON serialization
8. **Don't hardcode API URL** - Use class constant `API_URL` for testability
9. **Don't forget timeout parameter** - `httpx.AsyncClient(timeout=30.0)`
10. **Don't skip derived insights** - The LLM needs filing_velocity, momentum, trend, not just raw counts

### Discovered During Implementation
[Date: 2025-11-26]

During implementation, we discovered that the **PatentsView API documentation in the original context was outdated and referred to a deprecated API endpoint**. The actual working API has significantly different characteristics that weren't documented in the original context. This caused several hours of debugging and iterative testing to identify the correct integration patterns.

**API Endpoint Migration:**

The original context documented `https://api.patentsview.org/patents/query` as the endpoint with POST request JSON DSL. This API has been deprecated. The current API is:
- **Endpoint**: `https://search.patentsview.org/api/v1/patent/`
- **Method**: GET (not POST)
- **Parameters**: JSON-stringified query, fields, and options passed as URL parameters

**Critical Discovery: Manual URL Encoding Required**

The most significant integration challenge discovered was that **httpx's built-in `params` dict parameter does not correctly encode JSON query parameters for the PatentsView API**. When using the standard httpx pattern:

```python
response = await client.get(
    API_URL,
    params={
        "q": json.dumps(query),
        "f": json.dumps(fields),
        "o": json.dumps(options)
    }
)
```

The API returns a 400 "Invalid query parameters" error. The working solution requires **manual URL encoding using `urllib.parse.quote()`**:

```python
from urllib.parse import quote
import json

q = json.dumps(query)
f = json.dumps(fields)
o = json.dumps(options)
url = f'{API_URL}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
response = await client.get(url, headers=headers)
```

This pattern was discovered through iterative testing after multiple failed attempts with standard httpx parameter encoding. **Future implementations of PatentsView collectors must use manual URL encoding, not httpx params dict**.

**Field Name Mismatches:**

The actual API uses different field names than documented:
- `patent_id` (the context documented `patent_number`)
- `patent_num_times_cited_by_us_patents` (the context suggested `cited_patent_count`)

These field names were discovered by:
1. Examining successful API responses from the documentation example
2. Systematic testing of different citation field name variations
3. Cross-referencing with the PatentsView API field documentation

**Query Operator Behavior:**

The `_text_all` operator is used to ensure ALL words in the keyword are present in the results. This is critical for multi-word technology terms to avoid false positives. The query structure that works:

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

**Note:** Initially `_text_any` was used, but this caused false positives where "quantum computing" would match "quantum mechanics" or "distributed computing". Using `_text_all` ensures only patents containing ALL keywords are returned.

#### Updated Technical Details

**Working API Request Pattern:**
```python
# Correct implementation pattern
from urllib.parse import quote
import json
import httpx

query = {"_and": [...]}  # Query structure
fields = ["patent_id", "patent_title", "patent_num_times_cited_by_us_patents", ...]
options = {"size": 100}

# CRITICAL: Manual URL encoding required
q = json.dumps(query)
f = json.dumps(fields)
o = json.dumps(options)
url = f'https://search.patentsview.org/api/v1/patent/?q={quote(q)}&f={quote(f)}&o={quote(o)}'

headers = {"X-Api-Key": api_key}
response = await client.get(url, headers=headers)
```

**Response Structure (Corrected):**
```json
{
  "error": false,
  "count": 100,
  "total_hits": 22886,
  "patents": [
    {
      "patent_id": "11123456",
      "patent_title": "Method for Quantum Computing",
      "patent_date": "2023-09-15",
      "patent_num_times_cited_by_us_patents": 25,
      "assignees": [...]
    }
  ]
}
```

**Impact on Future Implementations:**

Anyone implementing similar PatentsView integrations needs to know:
1. The old `api.patentsview.org/patents/query` POST endpoint is deprecated
2. httpx params dict encoding doesn't work - manual `urllib.parse.quote()` is mandatory
3. Field names differ from intuitive names: use `patent_id` and `patent_num_times_cited_by_us_patents`
4. `_text_all` operator is required for multi-word keywords to avoid false positives (not `_text_any` which matches ANY word, nor `_text_phrase`)

These discoveries represent breaking changes from the original documented API and would have saved significant debugging time if known upfront.

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log

### 2025-11-27

#### Completed
- Fixed critical query operator bug: changed from `_text_any` to `_text_all` in PatentsView API queries
- Added patent_abstract field to search queries (now searches both title and abstract)
- Added patent_abstract and assignees fields to API response fields
- Updated task file documentation with correct `_text_all` operator explanation
- Fixed critical test suite bug: updated all mock field names from `cited_patent_count` to `patent_num_times_cited_by_us_patents`
- Fixed test mock field names from `patent_number` to `patent_id` for API consistency
- All 20 unit tests now passing after field name corrections

#### Discovered
- Critical bug identified: `_text_any` operator caused 96% false positives for multi-word keywords
- With `_text_any`, "quantum computing" matched "quantum mechanics" OR "distributed computing" (22,886 results)
- With `_text_all`, only patents containing BOTH "quantum" AND "computing" are returned (889 results)
- Test suite had wrong field names causing citation calculations to fail silently in tests
- Actual API uses `patent_num_times_cited_by_us_patents` not `cited_patent_count`

#### Test Results
- All 20 unit tests passing (after field name corrections)
- Real API test with `_text_all` operator for "quantum computing":
  - 889 total patents (397 in 2y, 439 in 5y, 53 in 10y) - 96% reduction from `_text_any`
  - 84 unique assignees (IBM: 37 patents, Microsoft: 18, Rigetti: 18, Intel: 17, Google: 12)
  - 16 countries represented (US: 195, CA: 21, JP: 10, IE: 7)
  - Citation metrics: avg 0.76 for 2y period, 13.51 for 5y period
  - Top patent: Anonos Inc. with 281 citations
- **Result quality dramatically improved** - top assignees now all major quantum computing companies

#### Impact
The `_text_all` operator fix is critical for result relevance. Before: matched unrelated patents containing ANY keyword. After: only patents containing ALL keywords. This prevents false positives like "distributed computing" matching "quantum computing" searches.

### 2025-11-26

#### Completed
- Added `patentsview_api_key` configuration to backend/app/config.py
- Implemented PatentsCollector class (572 lines) with complete collector architecture
- Implemented all 8 helper methods
- Created comprehensive test suite with 20 unit tests
- Fixed critical API integration issues through iterative debugging

#### Discovered
- PatentsView API requires manual URL encoding with urllib.parse.quote()
- Correct API field names: `patent_id`, `patent_num_times_cited_by_us_patents`
- API requires GET requests with JSON-stringified, URL-encoded query parameters

#### Next Steps
- PatentsCollector ready for integration into analysis pipeline
- Consider implementing caching strategy for expensive API calls
