---
name: h-fix-cache-persource-analyses
branch: fix/h-fix-cache-persource-analyses
status: completed
created: 2025-12-03
---

# Fix Missing Per-Source Analyses in Cached Results

## Problem/Goal
When the HypeCycleClassifier returns cached analysis results (cache_hit=true), the `per_source_analyses` field is an empty dict `{}` instead of containing the 5 individual source classifications (social, papers, patents, news, finance). This causes the frontend to display "Per-source analyses not available" even though the data was originally generated.

Root cause: The database schema is missing a column to store per_source_analyses data. The current schema only has columns for the 5 collector data blobs (social_data, papers_data, etc.) but no column for the DeepSeek per-source analysis results.

This fix will:
1. Add `per_source_analyses_data TEXT` column to the analyses table
2. Update `_persist_result()` to JSON-serialize and save per_source_analyses
3. Update `_check_cache()` to parse and include per_source_analyses in returned results
4. Handle migration for existing database rows

## Success Criteria
- [x] Database schema updated with `per_source_analyses_data TEXT` column in analyses table
- [x] `_persist_result()` method saves per_source_analyses as JSON to new column
- [x] `_check_cache()` method retrieves and parses per_source_analyses from database
- [x] Cached results return complete per_source_analyses dict with all 5 sources (social, papers, patents, news, finance)
- [x] Frontend displays all 5 source analysis cards on cache hit (previously showed "not available")
- [x] Existing test suite passes (no regressions in HypeCycleClassifier tests)
- [x] Manual testing confirms cache hit shows per_source_analyses correctly

## Context Manifest

### How Database Caching Works: The Missing Piece Problem

The HypeCycleClassifier implements a sophisticated caching system that stores complete analysis results in SQLite to avoid expensive re-processing. When a user analyzes a technology keyword like "quantum computing", the full analysis pipeline takes ~48 seconds: it runs 5 parallel data collectors (social media, academic papers, patents, news, financial data), then performs 6 DeepSeek LLM API calls (5 per-source analyses + 1 final synthesis). This is expensive both in time and API costs.

To optimize this, the classifier implements cache-first retrieval: before running any collectors or LLM calls, it queries the database to see if this keyword was analyzed recently (within the last 24 hours by default). If found, it returns the cached result immediately in <1 second, avoiding all the expensive operations.

**The Current Flow - Fresh Analysis (Working Correctly):**

When `classifier.classify(keyword, db)` is called with a cache miss (lines 40-87 in hype_classifier.py):

1. `_check_cache()` runs a SELECT query against the analyses table (lines 100-105), finds no matching row with `expires_at > current_timestamp`, returns None
2. `_run_collectors()` instantiates all 5 collectors and executes them in parallel via `asyncio.gather(*tasks, return_exceptions=True)` with 120-second timeout (lines 150-196)
3. Each collector returns a dict of metrics (e.g., social: `{"mentions_30d": 250, "sentiment": 0.72, ...}`)
4. DeepSeekAnalyzer receives all collector data, performs two-stage analysis (lines 72-73):
   - Stage 1: Calls `_analyze_source()` for each of the 5 data sources independently (5 LLM calls)
   - Stage 2: Calls `_synthesize_analyses()` to combine all 5 into final classification (1 LLM call)
   - Returns: `{"phase": "peak", "confidence": 0.82, "reasoning": "...", "per_source_analyses": {...}, "errors": []}`
5. The complete analysis dict includes `per_source_analyses` (lines 96, 301) - a nested dict with keys "social", "papers", "patents", "news", "finance", each containing `{"phase": str, "confidence": float, "reasoning": str}`
6. `_persist_result()` serializes the analysis to database (lines 198-255):
   - Creates JSON strings for the 5 collector data blobs: `social_data = json.dumps(collector_results.get("social"))` (lines 222-226)
   - **CRITICAL BUG**: Does NOT serialize `per_source_analyses` anywhere
   - INSERT query only includes 9 columns: keyword, phase, confidence, reasoning, social_data, papers_data, patents_data, news_data, finance_data, expires_at (lines 229-235)
   - **Missing column**: There's no `per_source_analyses_data` column being written to
7. `_assemble_response()` builds the final 13-field response dict (lines 257-312), includes `per_source_analyses` from the DeepSeek analysis result (line 301)
8. Frontend receives complete response with all 5 per-source analyses, displays 5 source cards perfectly (app.js lines 231-283)

**The Current Flow - Cache Hit (BROKEN):**

When `classifier.classify(keyword, db)` is called with a cache hit (lines 89-148 in hype_classifier.py):

1. `_check_cache()` runs SELECT query, finds matching row with valid `expires_at` (line 110)
2. Deserializes the 5 collector data JSON blobs from database columns (lines 118-123):
   ```python
   for source in ["social", "papers", "patents", "news", "finance"]:
       data_field = f"{source}_data"
       raw_data = row[data_field]
       collector_results[source] = json.loads(raw_data) if raw_data else None
   ```
3. **CRITICAL BUG**: Attempts to "reconstruct per_source_analyses if available (not in DB schema yet)" (line 125)
4. **Line 127**: Hardcoded `per_source_analyses = {}` - empty dict because there's no database column to read from
5. Calls `_assemble_response()` with the empty `per_source_analyses` dict (lines 130-142)
6. Response includes `"per_source_analyses": {}` (line 301 in _assemble_response)
7. Frontend receives response with empty per_source_analyses, `displayPerSourceAnalyses()` shows "Per-source analyses not available" message (app.js line 236)
8. User cannot see the breakdown of how each data source contributed to the classification, even though this data was originally generated and could have been persisted

**Why This Breaks User Experience:**

The per-source analyses are CRITICAL for understanding the classification reasoning. The final phase might be "peak" with 82% confidence, but the individual sources might tell a nuanced story: social media says "peak" (88% confidence), academic research says "slope" (78% confidence), patents say "peak" (80% confidence). These breakdowns help users understand conflicting signals and trust the analysis.

When cached results return empty per_source_analyses, the frontend cannot render the 5 source cards (Social Media, Research Papers, Patents, News, Finance). The user only sees the final classification without the transparency of per-source reasoning. This is especially problematic because:

1. The data WAS generated during the original analysis (6 expensive LLM calls)
2. It's being thrown away instead of cached
3. Subsequent requests within 24 hours get a degraded experience compared to the first request
4. Users have no way to force regeneration without waiting for cache expiration or manually clearing the database

**The Database Schema Gap:**

Looking at `database.py` lines 17-31, the current analyses table schema:

```sql
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    phase TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    social_data TEXT,      -- JSON blob
    papers_data TEXT,      -- JSON blob
    patents_data TEXT,     -- JSON blob
    news_data TEXT,        -- JSON blob
    finance_data TEXT,     -- JSON blob
    expires_at TIMESTAMP
)
```

Notice: There are 5 columns for collector raw data (social_data, papers_data, etc.) but ZERO columns for the per_source_analyses output from DeepSeek. The schema stores the INPUT to the LLM analysis (collector data) but not the OUTPUT (per-source classifications).

This is architecturally inconsistent: we cache the raw metrics from Hacker News API, Semantic Scholar API, etc., but we don't cache the LLM's interpretation of those metrics. Since the LLM analysis is deterministic (temperature=0.3, same prompt templates in deepseek.py lines 173-310), we could cache it.

**Data Structure Reference for per_source_analyses:**

From DeepSeekAnalyzer (deepseek.py lines 49-101), the per_source_analyses structure returned after Stage 1 analysis:

```python
{
    "social": {
        "phase": "peak",                    # One of: innovation_trigger, peak, trough, slope, plateau
        "confidence": 0.85,                 # Float 0.0-1.0
        "reasoning": "Very high mentions (250 in 30d), strong sentiment (0.72), accelerating momentum"
    },
    "papers": {
        "phase": "slope",
        "confidence": 0.78,
        "reasoning": "Steady publications (120 in 2y), maturing field, moderate citations"
    },
    "patents": {
        "phase": "peak",
        "confidence": 0.80,
        "reasoning": "Rapid filing growth (85 in 2y), diverse assignees, global reach"
    },
    "news": {
        "phase": "peak",
        "confidence": 0.88,
        "reasoning": "Very high coverage (520 articles in 30d), positive tone, mainstream media"
    },
    "finance": {
        "phase": "peak",
        "confidence": 0.75,
        "reasoning": "Strong investor sentiment (18.5% avg return in 6m), developing market maturity"
    }
}
```

This is a simple nested dict structure that is fully JSON-serializable (no datetime objects, no custom classes, just strings/floats/dicts). It can be stored in a TEXT column exactly like the collector data is stored.

**Storage Pattern Consistency:**

The existing _persist_result() method already demonstrates the pattern for JSON serialization (lines 222-226):

```python
social_data = json.dumps(collector_results.get("social")) if collector_results.get("social") else None
papers_data = json.dumps(collector_results.get("papers")) if collector_results.get("papers") else None
# ... etc for all 5 collectors
```

We need to add ONE more line following this exact pattern:

```python
per_source_analyses_data = json.dumps(analysis.get("per_source_analyses")) if analysis.get("per_source_analyses") else None
```

Then include it in the INSERT query parameters tuple (line 236-246).

**Retrieval Pattern Consistency:**

The existing _check_cache() method demonstrates the pattern for JSON deserialization (lines 118-123):

```python
collector_results = {}
for source in ["social", "papers", "patents", "news", "finance"]:
    data_field = f"{source}_data"
    raw_data = row[data_field]
    collector_results[source] = json.loads(raw_data) if raw_data else None
```

We need to add ONE more retrieval following this pattern:

```python
raw_per_source = row["per_source_analyses_data"]
per_source_analyses = json.loads(raw_per_source) if raw_per_source else {}
```

Then pass it to _assemble_response() instead of the hardcoded empty dict (line 136).

### For New Feature Implementation: Database Column Migration

Since we're adding a column to an existing table that may already have data in production (or at least in development testing), we need to handle migration carefully. SQLite has limited ALTER TABLE support, but adding a nullable column is safe and well-supported.

**Migration Strategy Options:**

1. **Simple ALTER TABLE (Recommended for MVP):** Add the column as nullable TEXT, existing rows will have NULL values
2. **Recreate Database:** Delete hype_cycle.db and let init_db() create fresh schema (simplest for development)
3. **Proper Migration System:** Use tools like Alembic (overkill for this simple change, no migration library in requirements.txt)

For this project, we'll use Option 1 (ALTER TABLE) in the init_db() function with an idempotent check. This is the standard pattern for simple schema changes in SQLite applications without migration frameworks.

**Why ALTER TABLE is Safe Here:**

- We're adding a nullable column (TEXT), not changing existing columns
- SQLite supports `ALTER TABLE ADD COLUMN` without locking issues for small tables
- The analyses table is small (one row per keyword per 24 hours), not millions of rows
- Nullable means existing rows work fine with NULL values
- Python's aiosqlite handles the async execution without blocking FastAPI

**Idempotent Migration Pattern:**

We need to check if the column already exists before attempting ALTER TABLE. SQLite stores schema metadata in `pragma_table_info()`. The pattern:

```python
# Check if column exists
cursor = await db.execute("PRAGMA table_info(analyses)")
columns = await cursor.fetchall()
column_names = [col[1] for col in columns]  # col[1] is name field

if "per_source_analyses_data" not in column_names:
    await db.execute("ALTER TABLE analyses ADD COLUMN per_source_analyses_data TEXT")
    await db.commit()
```

This is safe to run multiple times - if the column exists, it skips the ALTER. If it doesn't exist, it adds it.

**Where to Insert Migration Code:**

In `database.py`, the `init_db()` function (lines 12-35) is called on FastAPI startup (via `main.py` startup event). This is the perfect place to add the migration logic:

```python
async def init_db():
    """Initialize database schema"""
    DATABASE_PATH.parent.mkdir(exist_ok=True)  # Ensure data/ exists

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create table if not exists (original schema)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                phase TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                social_data TEXT,
                papers_data TEXT,
                patents_data TEXT,
                news_data TEXT,
                finance_data TEXT,
                expires_at TIMESTAMP
            )
        """)

        # MIGRATION: Add per_source_analyses_data column if missing
        cursor = await db.execute("PRAGMA table_info(analyses)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "per_source_analyses_data" not in column_names:
            await db.execute("ALTER TABLE analyses ADD COLUMN per_source_analyses_data TEXT")

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_keyword ON analyses(keyword)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_expires ON analyses(expires_at)")
        await db.commit()
```

This migration runs automatically on server startup. For development, you can restart uvicorn to apply it. For production, it would run during deployment.

### Technical Reference Details

#### Database Schema Change

**File:** `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py`

**Add to init_db() function after CREATE TABLE block (after line 32, before index creation):**

```python
# MIGRATION: Add per_source_analyses_data column if it doesn't exist
cursor = await db.execute("PRAGMA table_info(analyses)")
columns = await cursor.fetchall()
column_names = [col[1] for col in columns]

if "per_source_analyses_data" not in column_names:
    await db.execute("ALTER TABLE analyses ADD COLUMN per_source_analyses_data TEXT")
```

**Column specification:**
- Name: `per_source_analyses_data`
- Type: `TEXT` (stores JSON string)
- Nullable: Yes (existing rows will have NULL, which is safe)
- Default: None (NULL in SQL)

#### HypeCycleClassifier._persist_result() Changes

**File:** `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py`

**Current method signature (line 198):**
```python
async def _persist_result(
    self,
    keyword: str,
    analysis: Dict[str, Any],           # Contains per_source_analyses nested dict
    collector_results: Dict[str, Optional[Dict[str, Any]]],
    db: aiosqlite.Connection
) -> Dict[str, Any]:
```

**Add JSON serialization after line 226 (after finance_data assignment):**

```python
# Serialize per-source analyses from DeepSeek
per_source_analyses_data = json.dumps(analysis.get("per_source_analyses")) if analysis.get("per_source_analyses") else None
```

**Update INSERT query (lines 229-235) to include new column:**

```sql
INSERT INTO analyses (
    keyword, phase, confidence, reasoning,
    social_data, papers_data, patents_data, news_data, finance_data,
    per_source_analyses_data,  -- ADD THIS LINE
    expires_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  -- ADD one more placeholder
```

**Update params tuple (lines 236-246) to include new value:**

```python
params = (
    keyword,
    analysis["phase"],
    analysis["confidence"],
    analysis["reasoning"],
    social_data,
    papers_data,
    patents_data,
    news_data,
    finance_data,
    per_source_analyses_data,  -- ADD THIS LINE
    expires_at.isoformat()
)
```

#### HypeCycleClassifier._check_cache() Changes

**File:** `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py`

**Current hardcoded empty dict (lines 125-127):**

```python
# Reconstruct per_source_analyses if available (not in DB schema yet)
# For now, just return the final classification
per_source_analyses = {}
```

**Replace with database retrieval (after line 123, before comment):**

```python
# Retrieve per_source_analyses from database
raw_per_source = row["per_source_analyses_data"]
per_source_analyses = json.loads(raw_per_source) if raw_per_source else {}
```

**Safe access pattern:** Using `json.loads()` with None-check prevents errors if column has NULL value (existing rows before migration)

#### Data Flow Verification Points

**Test that fresh analysis persists correctly:**
1. Clear cache: `DELETE FROM analyses WHERE keyword = 'test'`
2. POST /api/analyze with keyword="test"
3. Check database: `SELECT per_source_analyses_data FROM analyses WHERE keyword = 'test'`
4. Should see: JSON string like `{"social": {"phase": "...", "confidence": 0.85, "reasoning": "..."}, ...}`

**Test that cache retrieval works:**
1. POST /api/analyze with same keyword (within 24 hours)
2. Response should have `cache_hit: true`
3. Response should have `per_source_analyses` dict with all 5 sources
4. Frontend should display all 5 source cards

**Frontend verification (app.js):**
- Line 111: `displayPerSourceAnalyses(data.per_source_analyses)` is called
- Line 235-236: If per_source_analyses is empty dict, shows "not available"
- Lines 250-283: If per_source_analyses has keys, creates source cards for each
- After fix, cached results should display same source cards as fresh results

#### Error Handling Considerations

**Scenario 1: Database has old rows without per_source_analyses_data column**
- Migration adds column to schema
- Old rows have NULL values
- `json.loads(None)` would raise exception
- Solution: `json.loads(raw_per_source) if raw_per_source else {}` handles NULL gracefully

**Scenario 2: Database has column but NULL values (pre-migration cache entries)**
- `row["per_source_analyses_data"]` returns None
- Fallback to empty dict `{}`
- Frontend shows "Per-source analyses not available" (same as current behavior)
- Not a regression - these entries would have expired soon anyway (24h TTL)

**Scenario 3: Fresh analysis fails to generate per_source_analyses (DeepSeek errors)**
- DeepSeekAnalyzer returns analysis dict without "per_source_analyses" key
- `analysis.get("per_source_analyses")` returns None
- Serialization: `json.dumps(None) if None else None` = None
- Database stores NULL
- Cache retrieval falls back to `{}`
- Not a regression - analysis itself would have failed or returned partial data

**Scenario 4: JSON deserialization fails (corrupted database)**
- `json.loads(raw_per_source)` raises JSONDecodeError
- Should wrap in try-except block for robustness
- Fallback to empty dict, log warning
- Cache retrieval continues with degraded experience rather than crashing

**Recommended safety wrapper for _check_cache():**

```python
try:
    raw_per_source = row["per_source_analyses_data"]
    per_source_analyses = json.loads(raw_per_source) if raw_per_source else {}
except (json.JSONDecodeError, KeyError) as e:
    logger.warning(f"Failed to deserialize per_source_analyses for {keyword}: {e}")
    per_source_analyses = {}
```

#### File Locations Summary

Files to modify:
1. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\database.py` - Add migration logic (7 lines)
2. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\hype_classifier.py` - Update _persist_result() and _check_cache() (~10 lines)

Files to verify (no changes needed):
3. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py` - Already generates per_source_analyses correctly
4. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\routers\analysis.py` - Already passes response through correctly
5. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\frontend\app.js` - Already displays per_source_analyses when present

Test file to update:
6. `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_hype_classifier.py` - Update test_classify_with_cache_hit() to verify per_source_analyses persistence (line 104-109 mock data should include per_source_analyses_data column)

#### Testing Strategy

**Unit Tests (test_hype_classifier.py):**

Update `test_classify_with_cache_hit()` fixture (lines 96-109):
```python
mock_row = {
    "keyword": "quantum computing",
    "phase": "peak",
    "confidence": 0.82,
    "reasoning": "Cached analysis",
    "created_at": "2025-12-02T10:00:00",
    "expires_at": "2025-12-03T10:00:00",
    "social_data": json.dumps({"mentions": 250}),
    "papers_data": json.dumps({"publications": 120}),
    "patents_data": json.dumps({"patents": 85}),
    "news_data": json.dumps({"articles": 520}),
    "finance_data": json.dumps({"companies": 8}),
    # ADD THIS:
    "per_source_analyses_data": json.dumps({
        "social": {"phase": "peak", "confidence": 0.85, "reasoning": "High mentions"},
        "papers": {"phase": "slope", "confidence": 0.78, "reasoning": "Steady research"},
        "patents": {"phase": "peak", "confidence": 0.80, "reasoning": "Accelerating"},
        "news": {"phase": "peak", "confidence": 0.88, "reasoning": "High media"},
        "finance": {"phase": "peak", "confidence": 0.75, "reasoning": "Strong returns"}
    })
}
```

Add assertion after line 131:
```python
assert "per_source_analyses" in result
assert len(result["per_source_analyses"]) == 5
assert "social" in result["per_source_analyses"]
```

**Manual Testing:**

1. Start backend: `uvicorn app.main:app --reload` (migration runs automatically)
2. Test fresh analysis: POST /api/analyze with keyword="blockchain"
3. Verify response has per_source_analyses with 5 sources
4. Query database: `SELECT per_source_analyses_data FROM analyses WHERE keyword='blockchain'`
5. Verify JSON string is present
6. Test cache hit: POST /api/analyze with keyword="blockchain" again (within 24h)
7. Verify response has `cache_hit: true` AND per_source_analyses with 5 sources
8. Open frontend, verify 5 source cards are displayed for both fresh and cached requests

#### Performance Impact

**Storage overhead:**
- Per-source analyses JSON: ~500-800 bytes per analysis (5 sources * ~150 bytes each)
- Negligible compared to collector data JSON (~5-10 KB per analysis)
- TEXT column in SQLite has no fixed size limit

**Query performance:**
- SELECT retrieval: No impact (same single row fetch as before)
- INSERT persistence: No measurable impact (one additional column in tuple)
- JSON serialization: ~0.1ms (already doing this for 5 collector columns)
- JSON deserialization: ~0.1ms (already doing this for 5 collector columns)

**Cache effectiveness:**
- Slightly increased database size (0.5-1 KB per cached entry)
- Same cache hit rate as before (24-hour TTL unchanged)
- Massively improved user experience: 5 source cards displayed instead of "not available" message

#### Dependencies and Assumptions

**Assumptions:**
1. SQLite version supports ALTER TABLE ADD COLUMN (requires SQLite 3.1.0+, shipped with Python 3.x)
2. aiosqlite version supports PRAGMA queries (0.19.0+ does, in requirements.txt)
3. JSON serialization is safe (per_source_analyses structure is already JSON-serializable by design)
4. No concurrent migrations (single FastAPI process startup, or k8s rolling update pattern)

**Dependencies (all already in requirements.txt):**
- aiosqlite>=0.19.0 for async database operations
- fastapi>=0.104.1 for startup event handling
- No new dependencies required

**Configuration:**
- No new environment variables needed
- CACHE_TTL_HOURS applies to entire cached result including per_source_analyses
- No feature flags needed (this is a bug fix, not a new feature)

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log

### 2025-12-03

#### Completed
- Added idempotent database migration to `backend/app/database.py` (lines 34-40) using PRAGMA table_info to check column existence before ALTER TABLE
- Updated `_persist_result()` method in `backend/app/analyzers/hype_classifier.py` (lines 228-250) to serialize per_source_analyses as JSON and include in INSERT query
- Updated `_check_cache()` method in `backend/app/analyzers/hype_classifier.py` (lines 125-131) to deserialize per_source_analyses from database with try-except error handling
- Updated test fixtures in `backend/tests/test_hype_classifier.py` (lines 109-115, 140-147) to include per_source_analyses_data column and verify persistence
- All 12 existing tests passed with no regressions
- Manual testing confirmed cache hit now returns complete per_source_analyses with all 5 sources (social, papers, patents, news, finance)
- Frontend successfully displays all 5 source analysis cards on both fresh analysis and cache hit

#### Decisions
- Used idempotent migration pattern with PRAGMA table_info instead of manual migration scripts - appropriate for MVP with single-user SQLite database
- Followed existing JSON serialization pattern from collector data storage (social_data, papers_data, etc.) for consistency
- Added try-except wrapper in _check_cache() for graceful degradation on corrupted JSON - returns empty dict and logs warning
- Did not add migration logging per code review suggestion - deferred as non-critical enhancement

#### Discovered
- Database schema was missing per_source_analyses_data column - stored collector INPUT data but not DeepSeek LLM OUTPUT data
- Frontend already had complete support for displaying per_source_analyses - fix was purely backend
- Migration runs automatically on server startup via init_db() FastAPI startup event
