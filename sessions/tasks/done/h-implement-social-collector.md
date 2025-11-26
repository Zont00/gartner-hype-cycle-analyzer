---
name: h-implement-social-collector
branch: feature/social-collector
status: completed
created: 2025-11-25
---

# Social Media Collector - Hacker News

## Problem/Goal
Implement the social media data collector for the Gartner Hype Cycle Analyzer. This collector will gather social media signals about a given technology by querying the Hacker News Algolia API. It will analyze discussion volume, engagement metrics (points, comments), and trends over time to provide insights into how the tech community perceives and discusses the technology. This is one of the 5 data sources that feed into the DeepSeek LLM for hype cycle classification.

## Success Criteria
- [x] `backend/app/collectors/social.py` module created with SocialCollector class
- [x] Hacker News Algolia API integration working (search by keyword)
- [x] Collector returns structured data: story count, engagement metrics, trend direction
- [x] Data aggregation over time periods (last 30 days, 6 months, 1 year)
- [x] Error handling for API failures (rate limits, network issues)
- [x] Unit tests for collector logic with mocked API responses
- [x] Returns data in standardized format compatible with DeepSeek analyzer

## Context Manifest

### How the Data Collection System Currently Works

The Gartner Hype Cycle Analyzer is architected as a three-tier application where multiple data collectors work in parallel to gather signals about emerging technologies, which are then synthesized by an LLM (DeepSeek) to classify the technology's position on Gartner's Hype Cycle. Understanding this architecture is critical because the SocialCollector you're implementing is one of five equally-weighted data sources that feed into the final classification.

**The Request Flow (Complete End-to-End):**

When a user types a technology keyword (like "quantum computing") into the frontend input field at `C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html` and clicks "Analyze", the frontend JavaScript (`frontend\app.js`) sends a POST request to `http://localhost:8000/api/analyze` with JSON payload `{"keyword": "quantum computing"}`. This endpoint will be implemented in `backend\app\routers\analysis.py` (currently pending implementation).

The analysis router first checks the SQLite database cache. The database schema (`backend\app\database.py`, lines 17-35) includes an `analyses` table with columns for keyword, phase, confidence, reasoning, and critically, five separate JSON text columns: `social_data`, `papers_data`, `patents_data`, `news_data`, and `finance_data`. Each collector's output is stored in its own column. The cache check queries for existing analyses where `keyword = ?` and `expires_at > CURRENT_TIMESTAMP`. The cache TTL defaults to 24 hours (configurable via `CACHE_TTL_HOURS` in `.env`, see `backend\app\config.py` line 14).

On cache miss, the orchestrator (HypeCycleClassifier, to be implemented in `backend\app\analyzer\hype_classifier.py`) runs all five collectors in parallel using `asyncio.gather()`. This is why the BaseCollector interface at `backend\app\collectors\base.py` mandates an `async def collect(keyword: str)` method - all collectors must be non-blocking to enable concurrent execution. The system is designed with graceful degradation: even if 1-2 collectors fail (network timeout, API rate limit), the analysis proceeds with reduced confidence scores.

**The Collector Contract:**

Every collector inherits from `BaseCollector` (lines 8-22 in `base.py`), which defines a single abstract method:

```python
async def collect(self, keyword: str) -> Dict[str, Any]:
    """
    Collect data for the given keyword.

    Args:
        keyword: Technology keyword to analyze

    Returns:
        Dictionary containing collected metrics
    """
```

The return dictionary structure is critical. Based on the CLAUDE.md documentation (lines 103-113), collectors should return standardized metrics that enable the LLM to reason about hype cycle positioning:

```python
{
    "mentions_count": int,        # Volume of discussion/coverage
    "sentiment": float,           # -1.0 to 1.0 scale
    "recency": str,               # "high", "medium", "low"
    "growth_trend": str           # "increasing", "stable", "decreasing"
}
```

However, this is a suggested structure. The DeepSeek analyzer (currently a placeholder at `backend\app\analyzers\deepseek.py`) expects `collector_data: Dict[str, Any]` where keys are collector names and values are their output dictionaries. The LLM will receive prompts tailored to each data source type (see task h-implement-deepseek-integration, lines 16-17) and must extract meaning from whatever metrics you provide.

**Why This Architecture:**

The five-source parallel approach provides triangulation. Social media (your collector) captures early buzz and community sentiment. Research papers (Semantic Scholar API) indicate academic validation. Patents show commercial investment. News (GDELT) tracks mainstream awareness. Finance data reflects investor confidence. Together, these map to Gartner's five hype cycle phases:

1. **Innovation Trigger**: Low mentions, high sentiment, recent emergence
2. **Peak of Inflated Expectations**: Explosive growth, very high sentiment, rapid trend increase
3. **Trough of Disillusionment**: Declining mentions, negative sentiment shift, downward trend
4. **Slope of Enlightenment**: Stabilizing mentions, improving sentiment, steady growth
5. **Plateau of Productivity**: Sustained moderate volume, neutral sentiment, stable trend

### Hacker News Algolia API Integration Pattern

The task specifies using Hacker News Algolia API as your social media source. This is a specific architectural decision - Hacker News represents tech community discourse better than general social media for this use case. The Algolia API is free, requires no authentication, and provides historical search capabilities.

**API Endpoint Structure:**

Hacker News Algolia exposes a search API at `http://hn.algolia.com/api/v1/search` with query parameters:
- `query`: The search keyword (URL-encoded)
- `tags`: Filter by content type (story, comment, etc.)
- `numericFilters`: Date range filtering using Unix timestamps

Example request:
```
GET http://hn.algolia.com/api/v1/search?query=quantum%20computing&tags=story&numericFilters=created_at_i>1640995200
```

The response JSON structure:
```json
{
  "hits": [
    {
      "created_at": "2025-01-15T10:30:00.000Z",
      "created_at_i": 1705318200,
      "title": "Breakthrough in Quantum Computing",
      "url": "https://example.com",
      "author": "username",
      "points": 342,
      "story_text": null,
      "comment_text": null,
      "num_comments": 156,
      "objectID": "39284721",
      "_tags": ["story", "author_username", "story_39284721"]
    }
  ],
  "nbHits": 1523,
  "page": 0,
  "nbPages": 76,
  "hitsPerPage": 20,
  "exhaustiveNbHits": true
}
```

**Critical Fields for Analysis:**
- `created_at_i`: Unix timestamp for temporal analysis
- `points`: Upvote count (engagement metric)
- `num_comments`: Discussion depth (engagement metric)
- `nbHits`: Total matching stories (mention count)

**Time Aggregation Strategy:**

The task requires aggregation over three time periods: 30 days, 6 months, 1 year. This enables trend detection. You'll need to make multiple API calls with different `numericFilters`:

```python
import time
from datetime import datetime, timedelta

now = datetime.now()
thirty_days_ago = int((now - timedelta(days=30)).timestamp())
six_months_ago = int((now - timedelta(days=180)).timestamp())
one_year_ago = int((now - timedelta(days=365)).timestamp())

# Query for each period
# 30 days: numericFilters=created_at_i>{thirty_days_ago}
# 6 months: numericFilters=created_at_i>{six_months_ago},created_at_i<{thirty_days_ago}
# 1 year: numericFilters=created_at_i>{one_year_ago},created_at_i<{six_months_ago}
```

By comparing mention counts and engagement across these periods, you can determine `growth_trend`. For example:
- If 30-day count > 6-month average: "increasing"
- If 30-day count < previous periods: "decreasing"
- Otherwise: "stable"

**Async HTTP Client Pattern:**

The project uses `httpx` for async HTTP requests (see `requirements.txt` line 8). FastAPI's async nature means blocking `requests.get()` would stall the entire event loop. Here's the pattern used throughout the codebase:

```python
import httpx
from typing import Dict, Any

async def collect(self, keyword: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "http://hn.algolia.com/api/v1/search",
                params={"query": keyword, "tags": "story"}
            )
            response.raise_for_status()
            data = response.json()
            # Process data...
        except httpx.HTTPError as e:
            # Handle gracefully...
```

### Error Handling and Graceful Degradation

The architecture mandates graceful degradation (see h-implement-hype-classifier.md line 19). If your collector encounters a rate limit (429), timeout, or network error, it should NOT raise an exception that kills the entire analysis. Instead, return partial data or a fallback structure:

```python
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        # Rate limited - return minimal data
        return {
            "mentions_count": 0,
            "sentiment": 0.0,
            "recency": "unknown",
            "growth_trend": "unknown",
            "error": "Rate limited"
        }
except httpx.TimeoutException:
    return {
        "mentions_count": 0,
        "sentiment": 0.0,
        "recency": "unknown",
        "growth_trend": "unknown",
        "error": "Timeout"
    }
```

The HypeCycleClassifier will detect the error field and reduce confidence accordingly. The DeepSeek analyzer will receive a note that social data was unavailable.

### Sentiment Analysis Approach

Hacker News Algolia API does not provide sentiment scores directly. You have two options:

**Option 1: Heuristic Sentiment (Recommended for MVP)**

Use engagement metrics as sentiment proxy:
- High points + high comments = positive sentiment (community finds it interesting/valuable)
- Low points despite high comments = possibly controversial/negative
- Formula: `sentiment = tanh((avg_points - 50) / 100)` to normalize to [-1, 1] range

**Option 2: Title Text Analysis (More Complex)**

Parse story titles and apply simple keyword scoring:
- Positive keywords: "breakthrough", "innovation", "success", "achievement"
- Negative keywords: "failure", "overhyped", "disappointing", "challenges"
- Neutral: everything else

For MVP, Option 1 is simpler and aligns with "no external NLP dependencies" constraint.

### Configuration and Dependency Injection

The codebase uses a settings singleton pattern (`backend\app\config.py`) with `@lru_cache()` decorator (line 28). To access configuration in your collector:

```python
from app.config import get_settings

settings = get_settings()
# Access settings.cache_ttl_hours, settings.log_level, etc.
```

However, Hacker News Algolia requires no API key, so you likely won't need configuration access. If you want to make the API endpoint configurable:

1. Add to `Settings` class in config.py:
   ```python
   hn_api_url: str = "http://hn.algolia.com/api/v1/search"
   ```

2. Add to `.env.example`:
   ```
   HN_API_URL=http://hn.algolia.com/api/v1/search
   ```

### Database Storage Pattern

After collection, the analysis router will store your output in the `social_data` TEXT column as JSON. The database module (`backend\app\database.py`) uses `aiosqlite` with async context managers:

```python
import json
from app.database import get_db

async def store_analysis(keyword: str, social_data: Dict[str, Any]):
    async with get_db() as db:
        await db.execute(
            "UPDATE analyses SET social_data = ? WHERE keyword = ?",
            (json.dumps(social_data), keyword)
        )
        await db.commit()
```

You won't implement this storage logic (that's in the analysis router task), but understanding it helps you design your output format. JSON-serializable types only: dict, list, str, int, float, bool, None. No datetime objects, numpy arrays, or custom classes.

### Integration with DeepSeek Analyzer

The DeepSeek analyzer (`backend\app\analyzers\deepseek.py`) currently has a placeholder `analyze()` method (lines 13-25). When implemented, it will receive your collector output as part of `collector_data` dict:

```python
collector_data = {
    "social": social_collector.collect(keyword),  # Your output here
    "papers": papers_collector.collect(keyword),
    "patents": patents_collector.collect(keyword),
    "news": news_collector.collect(keyword),
    "finance": finance_collector.collect(keyword)
}

result = await deepseek_analyzer.analyze(keyword, collector_data)
```

The LLM receives a prompt like:

```
You are analyzing "{keyword}" for hype cycle positioning.

Social Media Data (Hacker News):
- Mentions (30d): 45 stories
- Mentions (6m): 120 stories
- Mentions (1y): 200 stories
- Average engagement: 85 points, 32 comments per story
- Sentiment: 0.65 (positive)
- Trend: increasing (30d mentions higher than historical average)

Based on this social signal, what hype cycle phase does this indicate?
```

Design your output dictionary keys to be human-readable for LLM consumption.

### Testing Strategy

The task requires unit tests with mocked API responses (success criterion line 19). The codebase has a `backend\tests\` directory structure ready. Use `pytest` with `pytest-asyncio` for async test support. Mock pattern:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.collectors.social import SocialCollector

@pytest.mark.asyncio
async def test_social_collector_success():
    mock_response = {
        "hits": [{"points": 100, "num_comments": 50, "created_at_i": 1700000000}],
        "nbHits": 25
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None

        collector = SocialCollector()
        result = await collector.collect("test keyword")

        assert result["mentions_count"] == 25
        assert result["growth_trend"] in ["increasing", "stable", "decreasing"]

@pytest.mark.asyncio
async def test_social_collector_rate_limit():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited",
            request=...,
            response=Mock(status_code=429)
        )

        collector = SocialCollector()
        result = await collector.collect("test keyword")

        assert "error" in result
        assert result["mentions_count"] == 0
```

### Technical Reference Details

#### BaseCollector Interface

**File**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseCollector(ABC):
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

#### Recommended Output Schema

```python
{
    "source": "hacker_news",
    "collected_at": "2025-11-26T10:30:00Z",  # ISO format timestamp
    "keyword": str,  # Echo back the keyword

    # Mention counts by time period
    "mentions_30d": int,
    "mentions_6m": int,
    "mentions_1y": int,
    "mentions_total": int,

    # Engagement metrics (averages)
    "avg_points_30d": float,
    "avg_comments_30d": float,
    "avg_points_6m": float,
    "avg_comments_6m": float,

    # Derived insights
    "sentiment": float,  # -1.0 to 1.0
    "recency": str,  # "high", "medium", "low"
    "growth_trend": str,  # "increasing", "stable", "decreasing"
    "momentum": str,  # "accelerating", "steady", "decelerating"

    # Raw data for LLM context
    "top_stories": [
        {"title": str, "points": int, "comments": int, "age_days": int}
    ],

    # Error tracking
    "errors": []  # List of non-fatal errors encountered
}
```

#### Hacker News API Response Structure

**Endpoint**: `http://hn.algolia.com/api/v1/search`

**Parameters**:
- `query` (string): Search term
- `tags` (string): Filter by type (story, comment, poll, etc.)
- `numericFilters` (string): Numeric field filters like `created_at_i>1640995200`
- `hitsPerPage` (int): Results per page (default 20, max 1000)
- `page` (int): Page number for pagination

**Response**:
```json
{
  "hits": [...],          // Array of story/comment objects
  "nbHits": 1523,         // Total matching items
  "page": 0,              // Current page
  "nbPages": 76,          // Total pages
  "hitsPerPage": 20,      // Items per page
  "exhaustiveNbHits": true,
  "query": "quantum computing",
  "params": "query=quantum%20computing&tags=story"
}
```

**Hit Object**:
```json
{
  "created_at": "2025-01-15T10:30:00.000Z",
  "created_at_i": 1705318200,        // Unix timestamp
  "title": "Story title",
  "url": "https://example.com",
  "author": "username",
  "points": 342,                     // Upvotes
  "num_comments": 156,               // Comment count
  "objectID": "39284721"             // Unique ID
}
```

#### Dependencies

From `requirements.txt`:
- `httpx>=0.25.2` - Async HTTP client (line 8)
- `aiosqlite>=0.19.0` - Async SQLite (line 12)
- `python-dotenv>=1.0.0` - Environment variables (line 15)
- `pytest` and `pytest-asyncio` - For testing (add if missing)

#### File Locations

- **Implementation**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py`
- **Base class**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py`
- **Tests**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_social_collector.py` (create new)
- **Config**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py`

#### Integration Points

**Analysis Router** (to be implemented):
```python
from app.collectors.social import SocialCollector

social_collector = SocialCollector()
social_data = await social_collector.collect(keyword)
# Store in database social_data column
```

**HypeCycleClassifier** (to be implemented):
```python
results = await asyncio.gather(
    social_collector.collect(keyword),
    papers_collector.collect(keyword),
    # ... other collectors
)
social_data, papers_data, ... = results
```

### Additional Context: Hype Cycle Phase Indicators

Understanding what each phase looks like in social media helps you design metrics:

**Innovation Trigger**:
- Low mention count (< 20 stories in 1 year)
- Recent emergence (most mentions in last 30 days)
- High engagement per story (community curiosity)
- Positive sentiment (excitement about potential)

**Peak of Inflated Expectations**:
- Explosive growth (30d mentions >> 6m average)
- Very high engagement (100+ points average)
- Extremely positive sentiment (> 0.7)
- Accelerating momentum

**Trough of Disillusionment**:
- Declining mentions (30d < 6m average)
- Lower engagement than peak period
- Negative sentiment shift (< 0.3)
- Stories about "failures", "overhyped"

**Slope of Enlightenment**:
- Stabilizing mentions (steady counts)
- Moderate, consistent engagement
- Neutral to slightly positive sentiment
- Stories about "practical applications", "real use cases"

**Plateau of Productivity**:
- Sustained baseline mentions
- Moderate engagement (50-80 points)
- Neutral sentiment (0.4-0.6)
- Stories about "adoption", "integration", "standards"

These patterns should inform your trend analysis logic.

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log

### 2025-11-25
- Task file created with comprehensive context manifest
- Success criteria established (7 requirements)
- Task added to project index

### 2025-11-26

#### Implementation
- Implemented SocialCollector class in `backend/app/collectors/social.py` (~400 lines)
  - Async HTTP client using httpx with 30s timeout
  - Three-period time aggregation (30d, 6m, 1y) with non-overlapping windows
  - Hacker News Algolia API integration
  - Sentiment calculation using engagement-based heuristic (tanh normalization)
  - Trend detection (increasing/stable/decreasing) and momentum analysis
  - Top 5 stories extraction for LLM context
  - Graceful error handling - returns fallback response, never raises exceptions

#### Testing
- Created comprehensive test suite with 14 test cases:
  - Successful collection with typical responses
  - Rate limiting (429) and timeout handling
  - Network error recovery
  - Zero results edge case
  - Partial failure (some API calls succeed, others fail)
  - Sentiment calculation validation
  - Growth trend detection (increasing/decreasing)
  - Recency calculations (high/medium/low)
  - Missing/null field handling
  - JSON serialization verification
- All tests passing (pytest-asyncio, mocked httpx responses)

#### Live Validation
- Created manual test script (`backend/test_live_api.py`)
- Discovered HTTP 301 redirect issue - fixed by updating API_URL from HTTP to HTTPS
- Successfully validated with real Hacker News data:
  - Rust Programming: 124 mentions, increasing trend, accelerating momentum
  - Kubernetes: 655 mentions, stable trend, slight negative sentiment (retirement news)
  - ChatGPT: 3,251 mentions, positive sentiment, decelerating momentum

#### Code Review
- Ran code-review agent - found null safety issue in top stories extraction
- Fixed: Changed `hit.get("created_at_i", default)` to `(hit.get("created_at_i") or default)` pattern
- Added test case for null `created_at_i` handling
- Final test run: 14/14 passing

#### Status
- All success criteria met and verified
- Implementation complete and production-ready
