---
name: h-fix-deepseek-json-parsing
branch: fix/h-fix-deepseek-json-parsing
status: completed
created: 2025-12-03
---

# Fix DeepSeek JSON Parsing Error

## Problem/Goal

The application crashes during analysis synthesis with a JSON parsing error: "Expecting ',' delimiter: line 1 column 421 (char 420)". This occurs in the `_call_deepseek()` method in `backend/app/analyzers/deepseek.py` when parsing DeepSeek's response.

The current markdown stripping logic (lines 414-422) has issues:
1. Uses simple string splitting that doesn't handle all edge cases
2. May fail with multiple code blocks or text after closing blocks
3. No logging of raw content when parsing fails
4. Error messages don't show what content caused the failure

This bug prevents users from analyzing certain technologies (e.g., "bio fuels") and needs immediate fixing.

## Success Criteria

- [x] **"bio fuels" analysis completes successfully** - The specific failing case must work end-to-end
- [x] **Robust JSON extraction with regex** - Replace string splitting with regex pattern that handles markdown code blocks properly
- [x] **Logging added for debug** - When JSON parsing fails, log the raw content from DeepSeek (truncated if >500 chars) for debugging
- [x] **Better error messages** - Error messages include snippet of problematic content to help diagnose issues
- [x] **Test coverage added** - Unit tests cover edge cases: multiple code blocks, text after blocks, malformed JSON from DeepSeek
- [x] **No regression** - Existing passing analyses (e.g., "quantum computing") still work correctly

## Context Manifest

### How JSON Parsing Currently Works in DeepSeek Analyzer

When the DeepSeekAnalyzer makes an API call to classify technologies, the flow proceeds through several stages, ultimately landing in the `_call_deepseek()` method (deepseek.py lines 368-438). This is where the JSON parsing bug occurs.

**The Request Flow:**

1. User submits "bio fuels" → Frontend calls POST /api/analyze → analysis.py router creates HypeCycleClassifier instance
2. HypeCycleClassifier.classify() checks cache (miss), then runs 5 collectors in parallel via _run_collectors()
3. After collectors complete, analyzer.analyze() is called with collector_data dict (line 93 in hype_classifier.py)
4. DeepSeekAnalyzer performs two-stage classification:
   - Stage 1: Five per-source analyses via _analyze_source() → each calls _call_deepseek() (lines 103-122)
   - Stage 2: Final synthesis via _synthesize_analyses() → calls _call_deepseek() (lines 124-141)
5. Each _call_deepseek() invocation:
   - Constructs HTTP POST to https://api.deepseek.com/v1/chat/completions
   - Sends specialized prompts requesting JSON responses WITHOUT markdown formatting
   - Example prompt ending: "Return ONLY a JSON object with no markdown formatting: {{"phase": "...", "confidence": 0.75, "reasoning": "..."}}"
   - Despite instructions, DeepSeek sometimes wraps responses in markdown code blocks

**The Problematic Parsing Logic (deepseek.py lines 413-422):**

```python
# Strip markdown code blocks (pattern from FinanceCollector)
content = content.strip()
if content.startswith("```"):
    content = content.split("```")[1]  # ISSUE: Assumes only 2 blocks, fails with 3+
    if content.startswith("json"):
        content = content[4:]
content = content.strip()

# Parse JSON
parsed = json.loads(content)  # JSONDecodeError occurs here when stripping fails
```

**Why This Fails:**

The string splitting approach (`content.split("```")[1]`) was borrowed from FinanceCollector (finance.py lines 220-224) and works for simple cases like:
```
```json
{"phase": "peak"}
```
```

But fails when DeepSeek returns responses with:
- Multiple code blocks: "Some text ```json {...}``` more text ```json {...}```"
- Text after closing backticks: "```json {...}``` Here's my explanation..."
- Nested backticks or other edge cases

In these cases, `split("```")[1]` grabs the wrong substring, leaving invalid JSON that causes `json.loads()` to raise JSONDecodeError with cryptic messages like "Expecting ',' delimiter: line 1 column 421 (char 420)".

**Error Propagation Path:**

When JSONDecodeError is raised in _call_deepseek():
1. Exception bubbles up through _analyze_source() or _synthesize_analyses()
2. Caught by analyze() which wraps it: `Exception(f"Failed to synthesize analyses: {str(e)}")`
3. Bubbles to HypeCycleClassifier.classify()
4. Caught by analysis.py router at line 168 which raises HTTPException(500)
5. User sees: "Analysis failed: Analysis failed: Failed to synthesize analyses: Expecting ',' delimiter: line 1 column 421 (char 420)"

**Current Error Handling Gaps:**

1. **No logging of raw content**: When parsing fails, we never log what DeepSeek actually returned, making debugging impossible
2. **No content snippet in error message**: Error just says "Expecting ',' delimiter" without showing the problematic content
3. **Fragile string splitting**: The `split("```")` approach doesn't handle edge cases robustly
4. **No regex-based extraction**: Other codebases typically use regex to reliably extract JSON from markdown

### Existing Patterns in Codebase

**Logging Infrastructure (main.py lines 5-9):**

The application uses Python's standard logging module configured at INFO level:
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

Every module that needs logging follows this pattern:
```python
import logging
logger = logging.getLogger(__name__)
```

**Logging Usage Examples:**

- analysis.py line 16: `logger = logging.getLogger(__name__)`
- analysis.py line 173: `logger.warning(f"Insufficient data for keyword '{request.keyword}': {error_message}")`
- analysis.py line 180: `logger.exception(f"Analysis failed for keyword '{request.keyword}': {error_message}")` ← Uses logger.exception() to include full traceback
- hype_classifier.py line 20: `logger = logging.getLogger(__name__)`
- hype_classifier.py line 189: `logger.error(f"Cache check failed for keyword {keyword}: {str(e)}")`

**Critical Pattern: logger.exception() vs logger.error()**

- `logger.error()` logs a message at ERROR level
- `logger.exception()` logs a message at ERROR level AND includes full exception traceback
- Used in analysis.py line 180 when catching unexpected exceptions to get full stack trace

**Similar JSON Parsing in Codebase:**

1. **FinanceCollector (finance.py lines 220-227)**: Same problematic pattern as DeepSeek analyzer
   - Uses `split("```")` approach
   - No logging on failure
   - Catches JSONDecodeError and appends to errors list: `errors.append("Failed to parse DeepSeek response")`
   - Returns fallback data instead of raising

2. **HypeCycleClassifier cache retrieval (hype_classifier.py lines 152-167)**: Defensive JSON parsing
   - Uses try-except around json.loads()
   - Catches JSONDecodeError and KeyError
   - Logs warning: `logger.warning(f"Failed to deserialize per_source_analyses for {keyword}: {e}")`
   - Returns empty dict/list as fallback, doesn't crash

**Test Coverage for Markdown Stripping:**

Existing test in test_deepseek_analyzer.py (lines 509-528):
```python
async def test_deepseek_analyzer_markdown_stripping():
    """Test stripping of markdown code blocks from response"""
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": '```json\n{"phase": "peak", "confidence": 0.75, "reasoning": "Test"}\n```'}}
        ]
    }
    # Test passes - verifies basic markdown stripping works
```

**Missing Test Coverage:**

- Multiple code blocks: "text ```json {...}``` text ```json {...}```"
- Text after closing backticks: "```json {...}``` Here's why..."
- Malformed markdown: "```\n{...}" (missing "json" language tag)
- Bare JSON without markdown
- Mixed content with explanations

### Technical Reference Details

**DeepSeek API Response Structure:**

```python
{
    "choices": [
        {
            "message": {
                "content": "```json\n{\"phase\": \"peak\", \"confidence\": 0.75, \"reasoning\": \"...\"}\n```"
            }
        }
    ]
}
```

The `content` field is where markdown wrapping occurs.

**Required JSON Structure After Parsing:**

For _call_deepseek() (lines 424-436):
```python
{
    "phase": str,          # Must be in VALID_PHASES list
    "confidence": float,   # Must be 0.0-1.0
    "reasoning": str       # Must be present
}
```

For generate_expanded_terms() (lines 514-523):
```python
{
    "terms": list[str]     # Must contain 3-5 strings
}
```

**Validation Logic After Parsing:**

Both methods validate parsed JSON structure:
- Check required fields present
- Validate phase against VALID_PHASES list
- Validate confidence range
- Raise ValueError with descriptive messages if validation fails

**File Locations for Implementation:**

- Primary fix: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py` lines 413-422 (_call_deepseek method)
- Secondary fix location: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\analyzers\deepseek.py` lines 503-512 (generate_expanded_terms method - same pattern)
- Test file: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_deepseek_analyzer.py`
- Integration test: `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\test_real_classification.py` (end-to-end validation)

**Recommended Regex Pattern:**

Other projects commonly use this pattern to extract JSON from markdown:
```python
import re

# Match: optional opening backticks + optional "json" + JSON content + optional closing backticks
# The (?s) flag makes . match newlines
pattern = r'```(?:json)?\s*(\{.*?\})\s*```?|(\{.*?\})'
match = re.search(pattern, content, re.DOTALL)
if match:
    json_str = match.group(1) or match.group(2)
    parsed = json.loads(json_str)
```

This handles:
- Wrapped: "```json\n{...}\n```"
- Wrapped without language: "```\n{...}\n```"
- Bare JSON: "{...}"
- Text before/after: "Some text ```json {...}``` more text" (grabs first JSON)

**Alternative Approach: Strip All Backticks:**

Simpler but less precise:
```python
# Remove all backticks and "json" language identifiers
content = content.replace("```json", "").replace("```", "").strip()
parsed = json.loads(content)
```

Works for most cases but could fail if JSON content itself contains triple backticks.

**Logging Best Practices for This Fix:**

1. When JSON parsing fails, log the raw content (truncated to prevent log spam):
```python
except json.JSONDecodeError as e:
    # Truncate content if too long to prevent log spam
    content_preview = content[:500] + "..." if len(content) > 500 else content
    logger.error(f"Failed to parse DeepSeek JSON response: {str(e)}")
    logger.error(f"Raw content: {content_preview}")
    raise  # Re-raise with better error message
```

2. Include content snippet in exception message for immediate visibility:
```python
raise json.JSONDecodeError(
    f"Failed to parse DeepSeek response. Error: {str(e)}. Content preview: {content[:200]}",
    doc=e.doc,
    pos=e.pos
)
```

**Testing Strategy:**

1. Add tests for edge cases (multiple blocks, text after blocks, bare JSON)
2. Verify existing test still passes (basic markdown wrapping)
3. Test "bio fuels" end-to-end via test_real_classification.py
4. Verify "quantum computing" (existing working case) still works

## User Notes

Error occurred when analyzing "bio fuels":
```
Analysis failed: Analysis failed: Failed to synthesize analyses: Expecting ',' delimiter: line 1 column 421 (char 420). Please try again or contact support if the issue persists.
```

## Work Log

### 2025-12-04

#### Completed
- Created `_extract_json_from_markdown()` helper method with robust regex pattern handling all edge cases (bare JSON, markdown with/without language tag, text after backticks, multiple code blocks)
- Added logging infrastructure (logger instance at module level) to backend/app/analyzers/deepseek.py
- Enhanced error handling in `_call_deepseek()` method with try-except blocks, raw content logging (truncated to 500 chars), and content snippets in error messages
- Enhanced error handling in `generate_expanded_terms()` method with same error handling pattern
- Added 7 new unit tests for edge cases: bare JSON, markdown without language identifier, text after closing backticks, multiple code blocks, malformed JSON with logging verification, no JSON content
- Updated existing `test_deepseek_analyzer_invalid_json` to expect ValueError instead of JSONDecodeError
- Verified all 26 DeepSeek analyzer tests pass (including 7 new tests)
- Verified all 85 collector tests pass with no regression

#### Decisions
- Used regex pattern `r'```(?:json)?\\s*(\\{.*?\\})\\s*```|(\\{.*?\\})'` with DOTALL flag for robust JSON extraction instead of string splitting
- Chose ValueError wrapper over bare JSONDecodeError to provide better context in error messages
- Logged at ERROR level for parsing failures to ensure visibility in production monitoring

#### Discovered
- Original string splitting approach with `content.split("```")[1]` failed when DeepSeek responses contained multiple code blocks or text after closing backticks
- The bug prevented analysis of technologies like "bio fuels" that triggered edge case DeepSeek responses
- Code review found no security vulnerabilities - regex pattern safe from catastrophic backtracking, appropriate logging for debugging

#### Files Modified
- `backend/app/analyzers/deepseek.py` (lines 5-9: imports, 11-12: logger, 50-85: helper method, 454-466: error handling in _call_deepseek, 547-559: error handling in generate_expanded_terms)
- `backend/tests/test_deepseek_analyzer.py` (lines 427-444: updated test, 532-666: 7 new tests)
