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
      finance.py      # Financial data collector (to be implemented)
    analyzers/        # LLM integration
      deepseek.py     # DeepSeek API client (to be implemented)
    routers/          # API endpoints
      health.py       # Health check endpoint
      analysis.py     # Main analysis endpoint (to be implemented)
    utils/            # Shared utilities
  tests/              # Test suite
    test_social_collector.py  # 14 tests for SocialCollector
    test_papers_collector.py  # 18 tests for PapersCollector
    test_patents_collector.py # 20 tests for PatentsCollector
    test_news_collector.py    # 16 tests for NewsCollector
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

### Analyze Technology (To Be Implemented)
```
POST /api/analyze
```
Analyzes a technology and positions it on the Hype Cycle.

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
  "confidence": 0.85,
  "reasoning": "High social media buzz and research activity...",
  "created_at": "2025-11-25T10:30:00Z"
}
```

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

### Next Steps

Subsequent tasks will implement:

1. Data collectors (1 remaining: finance)
2. DeepSeek analyzer with prompt engineering
3. Analysis endpoint with caching logic
4. Enhanced frontend visualization

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
```

### Test Coverage
- **SocialCollector**: 14 tests covering API integration, error handling, edge cases
- **PapersCollector**: 18 tests covering API integration, error handling, edge cases, citation metrics, derived insights
- **PatentsCollector**: 20 tests covering API integration, error handling, edge cases, authentication, filing velocity, geographic reach
- **NewsCollector**: 16 tests covering API integration, error handling, edge cases, sentiment/tone calculation, coverage trends, media attention

## License

MIT
