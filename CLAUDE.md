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
   - Social Media Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\social.py)
   - Research Papers Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py)
   - Patent Collector (C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\patents.py)
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
- Required: DEEPSEEK_API_KEY
- Optional: NEWS_API_KEY, TWITTER_BEARER_TOKEN, GOOGLE_SCHOLAR_API_KEY

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

1. Create file in backend/app/collectors/ (e.g., social.py)
2. Inherit from BaseCollector
3. Implement async collect(keyword) method
4. Return standardized dict with metrics: mentions_count, sentiment, recency, growth_trend
5. Handle API errors gracefully (return partial data or empty structure)

Example structure:
```python
from app.collectors.base import BaseCollector
from typing import Dict, Any

class SocialCollector(BaseCollector):
    async def collect(self, keyword: str) -> Dict[str, Any]:
        # API calls to Twitter/Reddit
        return {
            "mentions_count": 1500,
            "sentiment": 0.75,
            "recency": "high",
            "growth_trend": "increasing"
        }
```

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
│   │   │   ├── social.py        # Social media collector (to be implemented)
│   │   │   ├── papers.py        # Research papers collector (to be implemented)
│   │   │   ├── patents.py       # Patent collector (to be implemented)
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
│   ├── tests/                   # Test files (placeholder)
│   │   └── __init__.py
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

1. **Individual Collectors** (5 tasks):
   - Social media scraping (Twitter/Reddit APIs or web scraping)
   - Research papers (arXiv, Google Scholar APIs)
   - Patent search (USPTO, Google Patents APIs)
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

### Health Check Test
```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","database":"healthy","version":"0.1.0"}
```

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
