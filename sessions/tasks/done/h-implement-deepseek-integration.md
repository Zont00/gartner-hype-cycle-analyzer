---
name: h-implement-deepseek-integration
branch: feature/deepseek-integration
status: completed
created: 2025-11-25
---

# DeepSeek LLM Integration

## Problem/Goal
Implement the DeepSeek API client and prompt engineering layer for the Gartner Hype Cycle Analyzer. This module will handle communication with the DeepSeek LLM API, craft specialized prompts for each data source (social, papers, patents, news, finance), and parse the LLM responses to extract hype cycle classifications. It will perform per-source analysis (5 individual classifications) and final synthesis (aggregating all sources into one final classification with reasoning). This is the AI intelligence layer that transforms raw data into actionable hype cycle positioning.

## Success Criteria
- [x] `backend/app/analyzers/deepseek.py` module created with DeepSeekClient class
- [x] DeepSeek API integration working (authentication, request/response handling)
- [x] Per-source prompt templates created for each of the 5 collectors (social, papers, patents, news, finance)
- [x] Synthesis prompt template created to aggregate all 5 source analyses
- [x] Response parsing logic to extract phase, confidence, and reasoning from LLM JSON responses
- [x] Error handling for API failures (rate limits, timeouts, invalid responses)
- [x] Unit tests with mocked DeepSeek API responses

## Context Manifest
<!-- Added by context-gathering agent -->

### How the DeepSeek Analyzer Fits Into the Overall System

The Gartner Hype Cycle Analyzer is a three-tier application that collects data from five sources (social media, research papers, patents, news, and finance), then uses AI to synthesize that data into a hype cycle classification. The DeepSeek Analyzer is the **AI intelligence layer** that transforms raw collected data into actionable insights.

**Request Flow - The Complete Journey:**

When a user enters a technology keyword like "quantum computing" in the frontend (`frontend/index.html`), the JavaScript (`frontend/app.js`) sends a POST request to `http://localhost:8000/api/analyze`. This hits the analysis router endpoint (`backend/app/routers/analysis.py` - not yet implemented, but this is what will call the DeepSeek Analyzer). The router first checks the SQLite database (`data/hype_cycle.db`) for a recent cached analysis of the same keyword where `expires_at > current_time`. The cache TTL is configured via `CACHE_TTL_HOURS` environment variable (default: 24 hours).

On cache miss, the router instantiates all five collectors and runs them in parallel using `asyncio.gather()`:
- `SocialCollector()` - Hacker News API
- `PapersCollector()` - Semantic Scholar API
- `PatentsCollector()` - PatentsView API
- `NewsCollector()` - GDELT API
- `FinanceCollector()` - Yahoo Finance + DeepSeek for ticker discovery

Each collector returns a standardized dictionary with metrics specific to that data source. For example, `SocialCollector` returns `{"source": "hacker_news", "mentions_30d": 124, "sentiment": 0.65, "recency": "high", "growth_trend": "increasing", ...}`. All collectors follow the `BaseCollector` abstract interface which requires implementing `async def collect(keyword: str) -> Dict[str, Any]`.

**Critical Pattern - Collector Data Structure:**
All five collectors return JSON-serializable dictionaries with these common patterns:
1. **Source identifier**: `"source": "hacker_news"` (or semantic_scholar, patentsview, gdelt, yahoo_finance)
2. **Timestamp**: `"collected_at": "2025-11-28T10:30:00.123456"` (ISO format string, NOT datetime object)
3. **Keyword echo**: `"keyword": "quantum computing"`
4. **Time-windowed metrics**: Counts/averages for multiple time periods (30d/6m/1y for social, 2y/5y for papers, etc.)
5. **Derived insights**: Categorical classifications like `"research_maturity": "developing"`, `"investor_sentiment": "positive"`
6. **Top items for LLM context**: `"top_stories": [...]`, `"top_papers": [...]`, `"top_patents": [...]`
7. **Error tracking**: `"errors": ["Rate limited", ...]` - non-fatal errors, collectors never raise exceptions

**Where DeepSeek Analyzer Comes In:**

After all five collectors complete, the analysis router aggregates their outputs into a single `collector_data` dictionary:
```python
collector_data = {
    "social": social_collector_result,
    "papers": papers_collector_result,
    "patents": patents_collector_result,
    "news": news_collector_result,
    "finance": finance_collector_result
}
```

The router then instantiates `DeepSeekAnalyzer` and calls:
```python
analyzer = DeepSeekAnalyzer(api_key=settings.deepseek_api_key)
analysis_result = await analyzer.analyze(keyword="quantum computing", collector_data=collector_data)
```

The analyzer performs TWO types of LLM calls:

**1. Per-Source Analysis (5 calls):**
For each data source, send a specialized prompt to DeepSeek asking it to classify the hype cycle phase based on ONLY that source's data. This produces 5 individual assessments:
- Social media signals suggest: "peak" (confidence: 0.82)
- Research papers suggest: "slope" (confidence: 0.71)
- Patents suggest: "slope" (confidence: 0.78)
- News coverage suggests: "peak" (confidence: 0.65)
- Financial data suggests: "developing/slope" (confidence: 0.74)

**2. Final Synthesis (1 call):**
Send ALL five per-source analyses to DeepSeek with a synthesis prompt that asks it to weigh the evidence and produce a final classification. This accounts for conflicting signals (e.g., social media hype vs. academic maturity) and produces the authoritative answer:
- Final phase: "peak"
- Final confidence: 0.78
- Reasoning: "While research and patents indicate maturing technology (slope), exceptionally high social media buzz and news coverage combined with strong investor sentiment point to Peak of Inflated Expectations..."

**Response Format - Critical for Database Storage:**

The `analyze()` method must return a dictionary matching the database schema (`backend/app/database.py` lines 17-35):
```python
{
    "phase": "peak",  # One of: innovation_trigger, peak, trough, slope, plateau
    "confidence": 0.78,  # Float 0-1
    "reasoning": "Long explanation string...",
    "per_source_analyses": {  # Optional but valuable for transparency
        "social": {"phase": "peak", "confidence": 0.82, "reasoning": "..."},
        "papers": {"phase": "slope", "confidence": 0.71, "reasoning": "..."},
        # ... etc
    }
}
```

The analysis router then stores this in the `analyses` table:
- `keyword`: "quantum computing"
- `phase`: "peak"
- `confidence`: 0.78
- `reasoning`: "Long explanation..."
- `social_data`: JSON blob of social collector result
- `papers_data`: JSON blob of papers collector result
- (etc for all 5 sources)
- `expires_at`: current_timestamp + CACHE_TTL_HOURS

Finally, the router returns a response to the frontend matching the API contract in `README.md` lines 129-137:
```json
{
  "keyword": "quantum computing",
  "phase": "peak",
  "confidence": 0.85,
  "reasoning": "High social media buzz and research activity...",
  "created_at": "2025-11-25T10:30:00Z"
}
```

The frontend then renders the position on the hype cycle curve using Canvas API (`frontend/app.js` lines 88-94 define the curve points for each phase).

### DeepSeek API Integration - How It Actually Works

**API Endpoint:** `https://api.deepseek.com/v1/chat/completions` (see `FinanceCollector` line 22 for confirmed endpoint)

**Authentication:** Bearer token in Authorization header
```python
headers = {
    "Authorization": f"Bearer {settings.deepseek_api_key}",
    "Content-Type": "application/json"
}
```

**Request Format (OpenAI-compatible):**
```python
payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "You are an expert technology analyst..."},
        {"role": "user", "content": "Analyze this data: ..."}
    ],
    "temperature": 0.3  # Lower = more deterministic (good for classification)
}
```

**Response Format:**
```python
{
    "choices": [
        {
            "message": {
                "content": "The JSON response or text from LLM..."
            }
        }
    ]
}
```

**Critical Pattern from FinanceCollector (lines 166-271):**
The FinanceCollector already uses DeepSeek successfully for ticker discovery. Key learnings:
1. **Structured output prompting**: Request JSON array format explicitly: "Return ONLY a JSON array of ticker symbols, for example: [\"IBM\", \"GOOGL\"]. No explanations, just the JSON array."
2. **Markdown stripping**: DeepSeek sometimes wraps JSON in markdown code blocks (```json ... ```). Strip these before parsing:
   ```python
   if content.startswith("```"):
       content = content.split("```")[1]
       if content.startswith("json"):
           content = content[4:]
   content = content.strip()
   ```
3. **Lower temperature for determinism**: Use `temperature: 0.3` for classification tasks (line 210)
4. **Graceful fallbacks**: Handle rate limits (429), auth failures (401), timeouts, and JSON parse errors
5. **Caching**: Cache LLM responses when appropriate (FinanceCollector uses instance-level `_ticker_cache`)

**Error Handling Patterns (from all collectors):**
```python
try:
    response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        errors.append("DeepSeek rate limited")
    elif e.response.status_code == 401:
        errors.append("DeepSeek authentication failed")
    else:
        errors.append(f"DeepSeek HTTP {e.response.status_code}")
except httpx.TimeoutException:
    errors.append("DeepSeek request timeout")
except json.JSONDecodeError:
    errors.append("Failed to parse DeepSeek response")
```

### Prompt Engineering Strategy - Per-Source vs. Synthesis

**Per-Source Prompt Template (5 variations needed):**

Each source gets a specialized prompt that understands its unique metrics. For example:

*Social Media Prompt (for SocialCollector data):*
```
You are analyzing social media signals from Hacker News to determine the hype cycle phase for "{keyword}".

Data provided:
- Mentions: 30d={mentions_30d}, 6m={mentions_6m}, 1y={mentions_1y}
- Engagement: avg_points_30d={avg_points_30d}, avg_comments_30d={avg_comments_30d}
- Trends: growth={growth_trend}, momentum={momentum}, sentiment={sentiment}
- Recency: {recency}

Hype Cycle Phases:
1. innovation_trigger: New concept, low mentions (<50), early buzz, low engagement
2. peak: Explosive growth, very high mentions (>200), high sentiment (>0.5), accelerating momentum
3. trough: Declining mentions from peak, negative sentiment shift, decelerating momentum
4. slope: Stabilizing mentions, improving sentiment from trough, steady growth
5. plateau: Sustained moderate volume, neutral sentiment (0.0-0.3), stable trend

Based on these social media signals, classify the hype cycle phase.

Return ONLY a JSON object:
{
  "phase": "one of: innovation_trigger, peak, trough, slope, plateau",
  "confidence": 0.75,
  "reasoning": "1-2 sentence explanation"
}
```

*Research Papers Prompt (for PapersCollector data):*
```
You are analyzing academic research signals from Semantic Scholar for "{keyword}".

Data provided:
- Publications: 2y={publications_2y}, 5y={publications_5y}
- Citations: avg_2y={avg_citations_2y}, velocity={citation_velocity}
- Research maturity: {research_maturity}
- Research momentum: {research_momentum}
- Research breadth: {research_breadth}

Hype Cycle Phases from academic perspective:
1. innovation_trigger: Emerging field (<10 papers), low citations (<5), narrow breadth
2. peak: Rapid publication growth, high momentum (accelerating), broad research
3. trough: Declining publications, negative citation velocity, narrowing focus
4. slope: Steady publications, mature field, moderate citations, improving velocity
5. plateau: Stable publication rate, high citations, broad established field

Return ONLY a JSON object:
{
  "phase": "one of: innovation_trigger, peak, trough, slope, plateau",
  "confidence": 0.80,
  "reasoning": "1-2 sentence explanation"
}
```

Similar specialized prompts needed for:
- **Patents**: Focus on filing velocity, assignee concentration, geographic reach
- **News**: Focus on media attention, coverage trend, sentiment, mainstream adoption
- **Finance**: Focus on market maturity, investor sentiment, investment momentum

**Synthesis Prompt Template:**

After collecting 5 per-source analyses, send them all to DeepSeek for final synthesis:

```
You are an expert technology analyst synthesizing multiple data sources to determine the definitive hype cycle position for "{keyword}".

You have analyzed this technology from 5 independent perspectives:

1. Social Media (Hacker News):
   Phase: {social_phase}
   Confidence: {social_confidence}
   Reasoning: {social_reasoning}

2. Academic Research (Semantic Scholar):
   Phase: {papers_phase}
   Confidence: {papers_confidence}
   Reasoning: {papers_reasoning}

3. Patents (PatentsView):
   Phase: {patents_phase}
   Confidence: {patents_confidence}
   Reasoning: {patents_reasoning}

4. News Coverage (GDELT):
   Phase: {news_phase}
   Confidence: {news_confidence}
   Reasoning: {news_reasoning}

5. Financial Markets (Yahoo Finance):
   Phase: {finance_phase}
   Confidence: {finance_confidence}
   Reasoning: {finance_reasoning}

Synthesize these perspectives into ONE final classification. Consider:
- Conflicting signals may indicate transition phases
- Weight sources by confidence scores
- Social media trends faster than academic validation
- Patents and finance lag behind hype but indicate real investment
- News bridges mainstream adoption

Return ONLY a JSON object:
{
  "phase": "one of: innovation_trigger, peak, trough, slope, plateau",
  "confidence": 0.85,
  "reasoning": "2-3 sentence explanation synthesizing key evidence from all sources"
}
```

### Hype Cycle Phase Definitions (CRITICAL for prompt context)

These definitions must be included in prompts so the LLM understands the phases:

**1. Innovation Trigger (innovation_trigger):**
- New technology concept emerges
- Limited mentions/publications/patents
- Early adopters experimenting
- Low engagement/citations
- Narrow focus, niche coverage

**2. Peak of Inflated Expectations (peak):**
- Explosive growth in all metrics
- Very high social media buzz
- Rapid increase in publications/patents
- Mainstream media coverage begins
- High sentiment/optimism
- Accelerating momentum

**3. Trough of Disillusionment (trough):**
- Declining mentions from peak levels
- Negative sentiment shift
- Publication/patent growth slows or reverses
- Media coverage drops
- Investor sentiment turns negative
- Reality check on limitations

**4. Slope of Enlightenment (slope):**
- Stabilizing metrics after trough
- Improving sentiment from lows
- Steady, sustainable growth
- Maturing research and patents
- Practical applications emerge
- Institutional adoption begins

**5. Plateau of Productivity (plateau):**
- Sustained moderate activity
- Neutral sentiment (technology normalized)
- Stable publication/patent rates
- Broad established field
- Mainstream adoption
- Mature market

### Technical Reference Details

#### DeepSeek Analyzer Class Structure

**File:** `backend/app/analyzers/deepseek.py` (currently placeholder, lines 1-26)

**Required Implementation:**
```python
class DeepSeekAnalyzer:
    """Client for DeepSeek API to classify technologies on Hype Cycle"""

    API_URL = "https://api.deepseek.com/v1/chat/completions"
    TIMEOUT = 60.0  # LLM calls can be slow

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def analyze(self, keyword: str, collector_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze collected data and classify technology on Hype Cycle.

        Performs two-stage analysis:
        1. Per-source analysis (5 LLM calls)
        2. Final synthesis (1 LLM call)

        Args:
            keyword: Technology keyword
            collector_data: Dict with keys "social", "papers", "patents", "news", "finance"

        Returns:
            {
                "phase": str,  # innovation_trigger, peak, trough, slope, plateau
                "confidence": float,  # 0-1
                "reasoning": str,
                "per_source_analyses": Dict[str, Any]  # Optional but valuable
            }
        """

    async def _analyze_source(
        self,
        source_name: str,
        source_data: Dict[str, Any],
        keyword: str
    ) -> Dict[str, Any]:
        """Analyze single data source using specialized prompt"""

    async def _synthesize_analyses(
        self,
        keyword: str,
        per_source_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize all source analyses into final classification"""

    def _build_source_prompt(
        self,
        source_name: str,
        source_data: Dict[str, Any],
        keyword: str
    ) -> str:
        """Build specialized prompt for each data source"""

    def _build_synthesis_prompt(
        self,
        keyword: str,
        per_source_results: Dict[str, Any]
    ) -> str:
        """Build synthesis prompt from all source analyses"""

    async def _call_deepseek(
        self,
        prompt: str,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """Make HTTP call to DeepSeek API and parse JSON response"""
```

#### Configuration Access

**From `backend/app/config.py` (lines 1-34):**
```python
from app.config import get_settings

settings = get_settings()  # Cached singleton
api_key = settings.deepseek_api_key  # Required field

# Other available settings:
# settings.cache_ttl_hours (default: 24)
# settings.database_path (default: "data/hype_cycle.db")
```

**API Key Check:**
```python
if not settings.deepseek_api_key:
    raise ValueError("DEEPSEEK_API_KEY environment variable not set")
```

#### HTTP Client Pattern (async httpx)

**From collector patterns:**
```python
import httpx

async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.3
        }
    )
    response.raise_for_status()
    result = response.json()
    content = result["choices"][0]["message"]["content"]
```

#### JSON Response Parsing

**Clean markdown wrapping (from FinanceCollector lines 220-224):**
```python
content = content.strip()
if content.startswith("```"):
    content = content.split("```")[1]
    if content.startswith("json"):
        content = content[4:]
content = content.strip()

parsed = json.loads(content)
```

**Validate response structure:**
```python
required_fields = ["phase", "confidence", "reasoning"]
if not all(field in parsed for field in required_fields):
    raise ValueError(f"DeepSeek response missing required fields: {parsed}")

valid_phases = ["innovation_trigger", "peak", "trough", "slope", "plateau"]
if parsed["phase"] not in valid_phases:
    raise ValueError(f"Invalid phase: {parsed['phase']}")

if not 0 <= parsed["confidence"] <= 1:
    raise ValueError(f"Confidence out of range: {parsed['confidence']}")
```

#### Testing Patterns

**From existing collector tests (e.g., `test_finance_collector.py`):**

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
import json

@pytest.mark.asyncio
async def test_deepseek_analyzer_success():
    """Test successful analysis with mocked DeepSeek API"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    # Mock DeepSeek API responses
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '{"phase": "peak", "confidence": 0.85, "reasoning": "High buzz"}'}}
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await analyzer.analyze(
            keyword="quantum computing",
            collector_data={
                "social": {"mentions_30d": 200, "sentiment": 0.8, ...},
                "papers": {...},
                # etc
            }
        )

        assert result["phase"] == "peak"
        assert result["confidence"] == 0.85
        assert "reasoning" in result

        # Verify JSON serializable
        json.dumps(result)

@pytest.mark.asyncio
async def test_deepseek_analyzer_rate_limit():
    """Test graceful handling of rate limiting"""
    analyzer = DeepSeekAnalyzer(api_key="test-key")

    mock_response = Mock()
    mock_response.status_code = 429

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited",
            request=Mock(),
            response=mock_response
        )

        with pytest.raises(Exception):  # Or handle gracefully
            await analyzer.analyze(keyword="test", collector_data={...})

@pytest.mark.asyncio
async def test_deepseek_analyzer_invalid_json():
    """Test handling of malformed DeepSeek response"""
    # Mock response with invalid JSON
    # Verify error handling

@pytest.mark.asyncio
async def test_deepseek_analyzer_missing_api_key():
    """Test behavior when API key not configured"""
    with pytest.raises(ValueError):
        analyzer = DeepSeekAnalyzer(api_key=None)
```

#### File Locations

- **Implementation**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py`
- **Tests**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_deepseek_analyzer.py` (create new)
- **Config**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\config.py` (already has `deepseek_api_key`)
- **Database schema**: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py` (lines 17-35)
- **Collector examples**: All files in `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\`

#### Dependencies

Already in `requirements.txt`:
- `httpx` - Async HTTP client for DeepSeek API calls
- `pydantic` - Settings validation (config.py)
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support

No new dependencies needed.

### Self-Verification Checklist

Before considering implementation complete, verify:

- [ ] Can instantiate `DeepSeekAnalyzer(api_key="test")` without errors
- [ ] `analyze()` method accepts keyword and collector_data dict
- [ ] Performs 6 total LLM calls: 5 per-source + 1 synthesis
- [ ] Returns dict with required fields: phase, confidence, reasoning
- [ ] Phase is one of the 5 valid values
- [ ] Confidence is float between 0-1
- [ ] Handles DeepSeek API errors gracefully (429, 401, timeout, JSON parse)
- [ ] Strips markdown code blocks from responses
- [ ] Validates LLM response structure
- [ ] All prompts include hype cycle phase definitions
- [ ] Per-source prompts are specialized for each data source
- [ ] Synthesis prompt weighs all 5 sources
- [ ] Uses temperature=0.3 for deterministic classification
- [ ] Response is JSON-serializable (no datetime objects)
- [ ] Unit tests cover success, errors, invalid responses
- [ ] Tests mock DeepSeek API (no real API calls in tests)

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log

### 2025-11-28

#### Completed
- Implemented DeepSeekAnalyzer class (439 lines) with two-stage analysis architecture
- Created 5 specialized prompt templates for each data source (social media, research papers, patents, news coverage, financial markets)
- Implemented synthesis prompt template to aggregate all 5 source analyses into final classification
- Added robust response parsing with markdown code block stripping and comprehensive validation
- Implemented comprehensive error handling for API failures (rate limits, authentication errors, timeouts, invalid JSON responses)
- Created complete test suite with 20 passing tests covering success cases, error handling, and edge cases
- Created real API test script (test_real_deepseek.py) with realistic collector data
- Successfully validated implementation with real DeepSeek API test using "quantum computing" keyword

#### Implementation Details
- Two-stage LLM analysis: 5 per-source classifications + 1 final synthesis (6 total API calls)
- Each prompt template includes hype cycle phase definitions and data source-specific thresholds
- Social media prompt: focuses on mentions, engagement, sentiment, growth trends
- Academic research prompt: focuses on publications, citations, research maturity and momentum
- Patent prompt: focuses on filing velocity, assignee concentration, geographic reach
- News prompt: focuses on media attention, coverage trends, sentiment, mainstream adoption
- Finance prompt: focuses on market maturity, investor sentiment, investment momentum
- Synthesis prompt: weighs all 5 sources with confidence scores, handles conflicting signals
- Response validation: checks for required fields (phase, confidence, reasoning), valid phase values, confidence range (0-1)
- Graceful degradation: continues with ≥3 sources if some collectors fail
- Follows established project patterns: async/await, error tracking, JSON-serializable responses

#### Test Coverage
- Initialization and API key validation
- Full end-to-end analysis with all 5 data sources
- Individual per-source analysis for each collector
- Final synthesis aggregation logic
- Error handling: rate limits (429), authentication failures (401), timeouts, invalid JSON, missing fields, invalid phases
- Edge cases: markdown stripping, insufficient sources, partial collector failures, confidence range validation
- Data validation: JSON serialization, response structure

#### Real API Validation
- Technology tested: "quantum computing"
- All 5 sources classified as "peak" (Peak of Inflated Expectations)
- Per-source confidence scores: 0.72-0.85
- Final synthesis confidence: 0.78
- Reasoning quality: DeepSeek provided detailed, contextual explanations synthesizing evidence from all sources
- API integration: authentication, request/response handling, JSON parsing all working correctly

#### Decisions
- Used two-stage analysis instead of single-pass to provide transparency and better reasoning
- Specialized prompts per data source rather than generic prompt for more accurate classification
- Temperature set to 0.3 for more deterministic classification results
- Minimum 3 sources required for synthesis to ensure robust classification
- Error tracking in "errors" field rather than raising exceptions for graceful degradation
- Markdown stripping pattern from FinanceCollector (handles ```json wrapping from DeepSeek responses)
