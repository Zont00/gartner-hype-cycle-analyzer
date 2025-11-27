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
2. Frontend calls POST /api/analyze endpoint (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py - to be implemented)
3. Backend checks SQLite cache for recent analysis
4. On cache miss, five collectors run in parallel:
   - Social Media Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py) - IMPLEMENTED
   - Research Papers Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py) - IMPLEMENTED
   - Patent Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py) - IMPLEMENTED
   - News Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\news.py)
   - Financial Data Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\finance.py)
5. DeepSeek analyzer classifies technology into hype cycle phase (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py)
6. Result cached in database and returned to frontend
7. Frontend renders position on hype cycle curve

## Key Components

### Backend (FastAPI)

**Main Application** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\main.py)
- FastAPI instance with CORS middleware for cross-origin requests
- Startup event initializes database schema
- Includes health router at /api prefix
- Auto-generated API docs at /api/docs

**Configuration** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py)
- Uses pydantic-settings for type-safe environment variable loading
- Cached singleton pattern via @lru_cache
- Loads from .env file in backend/ directory
- Required: DEEPSEEK_API_KEY, PATENTSVIEW_API_KEY
- Optional: NEWS_API_KEY, TWITTER_BEARER_TOKEN, GOOGLE_SCHOLAR_API_KEY, SEMANTIC_SCHOLAR_API_KEY

**Database** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py)
- Async SQLite via aiosqlite (non-blocking for FastAPI)
- Database file: C:\Users\Hp\Desktop\Gartner's Hype Cycle\data\hype_cycle.db
- Schema: analyses table with keyword, phase, confidence, reasoning, collector data (JSON), timestamps
- Indexes on keyword and expires_at for fast cache lookups
- get_db() provides async context manager for connections

**Health Check Router** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\health.py)
- GET /api/health endpoint
- Tests database connectivity
- Returns status: healthy/degraded, database: healthy/unhealthy, version: 0.1.0

**Base Collector Interface** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\base.py)
- Abstract base class defining collect(keyword) -> Dict[str, Any]
- All collectors inherit from BaseCollector
- Standardized return structure for LLM consumption

**Social Media Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py) - IMPLEMENTED
- Queries Hacker News Algolia API (https://hn.algolia.com/api/v1/search)
- Time-series analysis across three periods: 30 days, 6 months, 1 year (non-overlapping windows)
- Metrics returned: mentions_30d, mentions_6m, mentions_1y, mentions_total
- Engagement: avg_points_30d, avg_comments_30d, avg_points_6m, avg_comments_6m
- Derived insights: sentiment (-1.0 to 1.0), recency (high/medium/low), growth_trend (increasing/stable/decreasing), momentum (accelerating/steady/decelerating)
- Returns top 5 stories with titles, points, comments, age for LLM context
- Graceful error handling - never raises exceptions, returns fallback data on failures
- Errors tracked in "errors" field for partial failure visibility
- IMPORTANT: Uses HTTPS endpoint (HTTP causes 301 redirect)
- Test suite: 14 passing tests covering success, errors, edge cases (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_social_collector.py)

**Research Papers Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py) - IMPLEMENTED
- Queries Semantic Scholar API bulk search endpoint (https://api.semanticscholar.org/graph/v1/paper/search/bulk)
- Time-windowed analysis: 2-year and 5-year periods (suitable for academic publishing cycles)
- IMPORTANT: Uses bulk endpoint with quote-wrapped keywords for exact phrase matching (reduces false positives by 99.9%)
- Metrics returned: publications_2y, publications_5y, publications_total
- Citation metrics: avg_citations_2y, avg_citations_5y, citation_velocity
- Research breadth: author_diversity, venue_diversity
- Derived insights: research_maturity (emerging/developing/mature), research_momentum (accelerating/steady/decelerating), research_trend (increasing/stable/decreasing), research_breadth (narrow/moderate/broad)
- Returns top 5 papers by citation count with titles, years, citation counts for LLM context
- API key authentication: Optional via x-api-key header (configured through SEMANTIC_SCHOLAR_API_KEY env var)
- Graceful error handling with safe dictionary access using .get() to prevent KeyError on inconsistent API responses
- Handles missing fields (citationCount, authors, venue may be null/missing)
- Test suite: 18 passing tests covering success, errors, edge cases (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_papers_collector.py)

**Patent Collector** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py) - IMPLEMENTED
- Queries PatentsView Search API (https://search.patentsview.org/api/v1/patent/)
- Time-windowed analysis: 2-year, 5-year, and 10-year periods (non-overlapping windows matching patent filing cycles)
- CRITICAL: Requires manual URL encoding with urllib.parse.quote() - httpx params dict encoding does NOT work with this API
- API uses GET requests with JSON-stringified query parameters that must be manually URL-encoded
- Field names: patent_id (not patent_number), patent_num_times_cited_by_us_patents (for citations)
- CRITICAL: Query operator: _text_all for keyword matching in patent_title and patent_abstract fields (ensures ALL words present, prevents false positives)
- Metrics returned: patents_2y, patents_5y, patents_10y, patents_total
- Assignee metrics: unique_assignees, top_assignees (top 5 by patent count)
- Geographic distribution: countries dict with patent counts, geographic_diversity
- Citation metrics: avg_citations_2y, avg_citations_5y
- Derived insights: filing_velocity, assignee_concentration (concentrated/moderate/diverse), geographic_reach (domestic/regional/global), patent_maturity (emerging/developing/mature), patent_momentum (accelerating/steady/decelerating), patent_trend (increasing/stable/decreasing)
- Returns top 5 patents sorted by citation count with patent numbers, titles, dates, assignees, countries for LLM context
- API key authentication: Required via X-Api-Key header (configured through PATENTSVIEW_API_KEY env var)
- Graceful error handling with safe dictionary access using .get() to prevent KeyError on inconsistent API responses
- Handles missing fields (assignees, assignee_country, citation counts may be null/missing)
- Test suite: 20 passing tests covering success, errors, edge cases, authentication (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_patents_collector.py)
- Real API validation: Successfully tested with "quantum computing" using _text_all operator (889 patents found with 96% reduction in false positives, 84 unique assignees, 16 countries)

**DeepSeek Analyzer** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py)
- Placeholder class for LLM integration
- Will implement prompt engineering to classify into 5 phases:
  - innovation_trigger: Innovation Trigger
  - peak: Peak of Inflated Expectations
  - trough: Trough of Disillusionment
  - slope: Slope of Enlightenment
  - plateau: Plateau of Productivity
- analyze(keyword, collector_data) returns phase, confidence, reasoning

### Frontend (Vanilla JS)

**HTML Structure** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\index.html)
- Input field for technology keyword
- Analyze button triggering API call
- Loading state with spinner
- Results section with canvas visualization and details
- Error display area

**JavaScript Logic** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\app.js)
- API_BASE_URL: http://localhost:8000/api
- analyzeKeyword() fetches POST /api/analyze
- displayResults() renders phase, confidence, reasoning
- drawHypeCycle() uses Canvas API to draw curve and position marker
- Enter key support in input field

**Styling** (C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\styles.css)
- Modern gradient background
- Responsive container layout
- Spinner animation for loading state
- Canvas visualization styling

## Technology Stack

- **Python**: 3.14 (note: bleeding edge version, some packages use >= constraints for compatibility)
- **FastAPI**: 0.122.0 - async web framework with automatic OpenAPI docs
- **Uvicorn**: 0.38.0 - ASGI server with --reload for development
- **Pydantic**: 2.12.4 - data validation and settings management
- **aiosqlite**: 0.21.0 - async SQLite database driver
- **httpx**: Async HTTP client for external API calls
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
- Always wrap multi-word keywords in quotes for exact phrase matching (PapersCollector line 226)
- Use .get() with defaults for all API response field access to prevent KeyError (PapersCollector lines 70, 78, 107)
- Optional API key authentication via headers dict (PapersCollector lines 216-219)
- Manual URL encoding with urllib.parse.quote() for APIs that don't work with httpx params dict (PatentsCollector lines 313-318)
- Use _text_all operator (not _text_any) for PatentsView API to prevent false positives (PatentsCollector lines 277-287)
- Calculate derived insights from raw metrics for better LLM reasoning

### Adding a New API Endpoint

1. Create router file in backend/app/routers/ (e.g., analysis.py)
2. Create APIRouter instance
3. Define async endpoint functions with type hints
4. Use Depends() for database connections and settings
5. Include router in main.py with prefix and tags

Example in main.py:
```python
from app.routers import health, analysis
app.include_router(analysis.router, prefix="/api", tags=["analysis"])
```

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

### Critical API Integration Patterns

Based on lessons learned from implemented collectors:

**1. Exact Phrase Matching for Multi-Word Keywords**
- Always wrap keywords in quotes for API searches to get exact phrase matches
- Example: `query: f'"{keyword}"'` (PapersCollector line 226)
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
- Academic papers: 2 years, 5 years (slower cycles)
- Patents: 2 years, 5 years, 10 years (patent filing and grant cycles)
- Choose periods that reveal meaningful trends for that domain

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
│   │   │   ├── papers.py        # Research papers collector (IMPLEMENTED - Semantic Scholar)
│   │   │   ├── patents.py       # Patent collector (IMPLEMENTED - PatentsView)
│   │   │   ├── news.py          # News collector (to be implemented)
│   │   │   └── finance.py       # Financial data collector (to be implemented)
│   │   ├── analyzers/
│   │   │   ├── __init__.py
│   │   │   └── deepseek.py      # DeepSeek LLM client (to be implemented)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py        # Health check endpoint (implemented)
│   │   │   └── analysis.py      # Main analysis endpoint (to be implemented)
│   │   ├── models/              # Database models or schemas (placeholder)
│   │   │   └── __init__.py
│   │   └── utils/               # Shared utilities (placeholder)
│   │       └── __init__.py
│   ├── tests/                   # Test files
│   │   ├── __init__.py
│   │   ├── test_social_collector.py  # SocialCollector tests (14 tests)
│   │   ├── test_papers_collector.py  # PapersCollector tests (18 tests)
│   │   └── test_patents_collector.py # PatentsCollector tests (20 tests)
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
- expires_at: Cache expiration timestamp (default: 24 hours)

### CORS Configuration

FastAPI middleware allows all origins with `allow_origins=["*"]`. This is acceptable for local development but should be restricted to specific frontend URL in production.

### Async Patterns

All collectors, database operations, and API calls use async/await. This enables parallel execution of the five collectors without blocking. FastAPI handles async natively.

### Error Handling

Collectors should handle API failures gracefully. If one collector fails, others should continue. The LLM should work with partial data if needed.

### Cache Strategy

Before running collectors, check database for recent analysis of same keyword where expires_at > current time. Cache TTL configured via CACHE_TTL_HOURS environment variable (default: 24).

## Next Development Steps

Based on project setup completion, upcoming tasks will implement:

1. **Individual Collectors** (5 tasks, 3/5 complete):
   - ✓ Social media (Hacker News Algolia API) - COMPLETED
   - ✓ Research papers (Semantic Scholar API) - COMPLETED
   - ✓ Patent search (PatentsView Search API) - COMPLETED
   - News aggregation (News API or RSS feeds)
   - Financial data (funding rounds, VC investments)

2. **DeepSeek Integration**:
   - Prompt engineering for classification
   - API client implementation
   - JSON response parsing

3. **Analysis Endpoint**:
   - Cache checking logic
   - Parallel collector execution with asyncio.gather()
   - LLM orchestration
   - Result persistence

4. **Frontend Enhancement**:
   - Improve hype cycle curve visualization
   - Add interactive tooltips
   - Display collector data details

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
The PapersCollector has comprehensive test coverage (18 tests):
- Success cases with typical API responses
- Error handling (rate limits, timeouts, network errors, invalid queries)
- Edge cases (zero results, partial failures, missing fields)
- Citation velocity calculation (positive and negative)
- Research maturity detection (emerging, developing, mature)
- Research momentum detection (accelerating, steady, decelerating)
- Research trend detection (increasing, stable, decreasing)
- Research breadth detection (narrow, moderate, broad)
- JSON serialization verification

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

### API Documentation
Access interactive Swagger UI at http://localhost:8000/api/docs to test endpoints directly in browser.

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
