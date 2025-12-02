# Gartner Hype Cycle Analyzer

MVP application that analyzes emerging technologies and positions them on the Gartner Hype Cycle using five data sources (social media, research papers, patents, news, and financial data) combined with DeepSeek LLM analysis.

## Architecture

- **Backend**: FastAPI (Python 3.14)
- **Frontend**: Vanilla HTML/JS
- **Database**: SQLite
- **LLM**: DeepSeek API

## Prerequisites

- Python 3.14+ installed
- Git
- DeepSeek API key (for LLM analysis)

## Setup Instructions

### Backend Setup

1. **Create virtual environment:**
   ```bash
   cd backend
   python -m venv venv
   source venv/Scripts/activate  # Windows Git Bash
   # OR: venv\Scripts\activate.bat  # Windows CMD
   # OR: venv\Scripts\Activate.ps1  # Windows PowerShell
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your DEEPSEEK_API_KEY
   ```

4. **Run server:**
   ```bash
   uvicorn app.main:app --reload
   ```

   API will be available at http://localhost:8000
   Swagger docs at http://localhost:8000/api/docs

### Frontend Setup

1. **Open in browser:**
   Simply open `frontend/index.html` in your browser, or

2. **Serve with HTTP server:**
   ```bash
   cd frontend
   python -m http.server 3000
   ```

   Access at http://localhost:3000

## Project Structure

```
backend/
  app/
    main.py           # FastAPI app entry point
    config.py         # Configuration management
    database.py       # Database initialization
    collectors/       # Data collection modules
      base.py         # Base collector interface
      social.py       # Social media collector (IMPLEMENTED - Hacker News)
      papers.py       # Research papers collector (IMPLEMENTED - Semantic Scholar)
      patents.py      # Patent collector (IMPLEMENTED - PatentsView)
      news.py         # News collector (IMPLEMENTED - GDELT)
      finance.py      # Financial data collector (IMPLEMENTED - Yahoo Finance + DeepSeek)
    analyzers/        # LLM integration
      deepseek.py     # DeepSeek API client (IMPLEMENTED - 439 lines)
      hype_classifier.py # Main orchestration layer (IMPLEMENTED - 290 lines)
    routers/          # API endpoints
      health.py       # Health check endpoint (IMPLEMENTED)
      analysis.py     # Main analysis endpoint (IMPLEMENTED - 183 lines)
    utils/            # Shared utilities
  tests/              # Test suite
    test_social_collector.py  # 14 tests for SocialCollector
    test_papers_collector.py  # 18 tests for PapersCollector
    test_patents_collector.py # 20 tests for PatentsCollector
    test_news_collector.py    # 16 tests for NewsCollector
    test_finance_collector.py # 17 tests for FinanceCollector
    test_deepseek_analyzer.py # 20 tests for DeepSeekAnalyzer
    test_hype_classifier.py   # 12 tests for HypeCycleClassifier
  test_real_classification.py # Integration test for end-to-end workflow
frontend/
  index.html          # Web interface
  app.js              # Frontend logic
  styles.css          # Styling
data/                 # SQLite database storage
```

## API Endpoints

### Health Check
```
GET /api/health
```
Returns API and database status.

**Response:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "version": "0.1.0"
}
```

### Analyze Technology
```
POST /api/analyze
```
Analyzes a technology and positions it on the Gartner Hype Cycle using five parallel data collectors and DeepSeek LLM classification.

**Features:**
- Cache-first strategy with 24-hour TTL
- Parallel execution of 5 collectors (social, papers, patents, news, finance)
- Two-stage LLM analysis (5 per-source + 1 synthesis)
- Graceful degradation (requires minimum 3 of 5 collectors)
- Comprehensive error tracking

**Request:**
```json
{
  "keyword": "quantum computing"
}
```

**Response:**
```json
{
  "keyword": "quantum computing",
  "phase": "peak",
  "confidence": 0.82,
  "reasoning": "Strong signals across all sources indicate peak hype...",
  "timestamp": "2025-12-02T10:30:45.123456",
  "cache_hit": false,
  "expires_at": "2025-12-03T10:30:45.123456",
  "per_source_analyses": {
    "social": {"phase": "peak", "confidence": 0.85, "reasoning": "..."},
    "papers": {"phase": "peak", "confidence": 0.78, "reasoning": "..."},
    "patents": {"phase": "slope", "confidence": 0.80, "reasoning": "..."},
    "news": {"phase": "peak", "confidence": 0.83, "reasoning": "..."},
    "finance": {"phase": "peak", "confidence": 0.84, "reasoning": "..."}
  },
  "collector_data": {
    "social": {"mentions_30d": 245, "sentiment": 0.72, "...": "..."},
    "papers": {"publications_2y": 156, "avg_citations_2y": 23.4, "...": "..."},
    "patents": {"patents_2y": 89, "unique_assignees": 42, "...": "..."},
    "news": {"articles_30d": 312, "avg_tone": 0.15, "...": "..."},
    "finance": {"companies_found": 6, "total_market_cap": 7900000000000, "...": "..."}
  },
  "collectors_succeeded": 5,
  "partial_data": false,
  "errors": []
}
```

**Performance:**
- Fresh analysis: ~48 seconds (5 collectors + 6 LLM calls)
- Cache hit: <1 second

**HTTP Status Codes:**
- 200: Successful analysis (cache hit or fresh)
- 422: Validation error (invalid keyword format)
- 500: Internal server error (database/LLM failures)
- 503: Service unavailable (insufficient data - <3 collectors succeeded)

## Development

- FastAPI auto-reloads on code changes with `--reload` flag
- Access interactive API docs at `/api/docs` for testing
- Database schema auto-initializes on startup
- SQLite database stored in `data/hype_cycle.db`

## Environment Variables

See `backend/.env.example` for all available configuration options:

- `DEEPSEEK_API_KEY` - Required for LLM analysis
- `PATENTSVIEW_API_KEY` - Required for patents collector
- `NEWS_API_KEY` - Not used (GDELT is open access)
- `TWITTER_BEARER_TOKEN` - Optional for social media collector
- `SEMANTIC_SCHOLAR_API_KEY` - Optional for research papers collector (higher rate limits)
- `DATABASE_PATH` - Path to SQLite database
- `CACHE_TTL_HOURS` - Cache expiration time

## Implementation Status

### Completed
- ✓ Project setup and configuration
- ✓ FastAPI backend with health check endpoint
- ✓ Database schema and async SQLite integration
- ✓ Social media collector (Hacker News) with comprehensive tests (14 tests)
- ✓ Research papers collector (Semantic Scholar) with comprehensive tests (18 tests)
- ✓ Patent collector (PatentsView) with comprehensive tests (20 tests)
- ✓ News collector (GDELT) with comprehensive tests (16 tests)
- ✓ Financial data collector (Yahoo Finance + DeepSeek ticker discovery) with comprehensive tests (17 tests)
- ✓ DeepSeek analyzer with two-stage classification (5 per-source + 1 synthesis) with comprehensive tests (20 tests)
- ✓ HypeCycleClassifier orchestration layer with cache-first strategy, parallel execution, graceful degradation with comprehensive tests (12 tests)
- ✓ Analysis endpoint (POST /api/analyze) with Pydantic validation, error handling, OpenAPI documentation

### Next Steps

Subsequent tasks will implement:

1. Enhanced frontend visualization with per-source breakdowns
2. Interactive tooltips and detailed collector data display
3. Integration testing and deployment preparation

## Testing

### Run Unit Tests

```bash
cd backend
source venv/Scripts/activate
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_social_collector.py
```

### Verify Backend Setup

```bash
# 1. Ensure server is running
cd backend
source venv/Scripts/activate
uvicorn app.main:app --reload

# 2. In another terminal, test health endpoint
curl http://localhost:8000/api/health

# Expected: {"status":"healthy","database":"healthy","version":"0.1.0"}

# 3. Test analysis endpoint (requires DEEPSEEK_API_KEY in .env)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"keyword": "blockchain"}'

# Expected: Complete analysis with phase, confidence, per-source analyses, collector data
# First request: ~48 seconds (fresh analysis)
# Subsequent requests: <1 second (cache hit)
```

### Test Coverage
- **SocialCollector**: 14 tests covering API integration, error handling, edge cases
- **PapersCollector**: 18 tests covering API integration, error handling, edge cases, citation metrics, derived insights
- **PatentsCollector**: 20 tests covering API integration, error handling, edge cases, authentication, filing velocity, geographic reach
- **NewsCollector**: 16 tests covering API integration, error handling, edge cases, sentiment/tone calculation, coverage trends, media attention
- **FinanceCollector**: 17 tests covering DeepSeek integration, yfinance mocking, error handling, edge cases, market maturity, investor sentiment, instance isolation
- **DeepSeekAnalyzer**: 20 tests covering initialization, full analysis, per-source analysis, synthesis, error handling, edge cases, JSON serialization
- **HypeCycleClassifier**: 12 tests covering cache hit/miss, partial success scenarios, insufficient data error, parallel execution, database persistence, response assembly
- **Integration Test**: End-to-end workflow validation with real API calls (test_real_classification.py)

## License

MIT
