---
name: h-implement-assignee-classification
branch: feature/h-implement-assignee-classification
status: pending
created: 2025-12-10
---

# Implement Assignee Type Classification in PatentsCollector

## Problem/Goal

Enhance the PatentsCollector to classify patent assignees by type (University, Research Institute, Corporate, Government, Individual) to better understand technology maturity and commercialization stage.

Currently, the PatentsCollector aggregates assignee organizations but doesn't distinguish between academic institutions and corporations. This distinction is critical for Hype Cycle positioning:
- **Universities/Research Institutes** dominate early phases (Innovation Trigger, early Peak)
- **Corporate assignees** increase toward Slope of Enlightenment and Plateau of Productivity
- The ratio between academic and corporate assignees is a strong signal of technology maturity

The solution will use a hybrid approach:
1. Leverage the `assignee_type` field from PatentsView API (codes 1-9 for company/individual/government)
2. Apply pattern matching on `assignee_organization` names to identify universities and research institutes within corporate assignees
3. Calculate derived metrics (university_ratio, academic_ratio, commercialization_index, innovation_stage)
4. Enhance DeepSeek patent analysis prompts to leverage this new classification data

## Success Criteria

**Data Collection:**
- [ ] PatentsCollector requests `assignee_type` field from PatentsView API
- [ ] All assignees are classified into 5 categories: University, Research Institute, Corporate, Government, Individual

**Metrics Calculation:**
- [ ] Calculate `assignee_type_distribution` (percentage breakdown by category)
- [ ] Calculate `university_ratio` (% universities out of total assignees)
- [ ] Calculate `academic_ratio` (% universities + research institutes)
- [ ] Calculate `commercialization_index` (corporate / academic ratio)
- [ ] Calculate `innovation_stage` with reasoning (early_research, developing, commercialized)

**Testing:**
- [ ] All existing PatentsCollector tests pass
- [ ] New tests added for assignee classification logic
- [ ] New tests verify pattern matching for universities/research institutes
- [ ] Real API validation with at least 2 test keywords (one early-stage, one mature)

**DeepSeek Integration:**
- [ ] Patent analysis prompt updated to interpret assignee type distribution
- [ ] Prompt includes guidance on how university_ratio affects Hype Cycle positioning

**Documentation:**
- [ ] CLAUDE.md updated with new PatentsCollector fields and interpretation guidance
- [ ] Code comments explain classification logic and thresholds

## Context Manifest
<!-- Added by context-gathering agent -->

### How the PatentsCollector Currently Works

The PatentsCollector is the most complex collector in the system, implementing several critical patterns that must be preserved when adding assignee classification. Let me walk through the complete data flow:

**Request Initiation:**
When a user requests analysis for a technology keyword (e.g., "quantum computing"), the HypeCycleClassifier orchestrates parallel execution of all five collectors. The PatentsCollector.collect() method receives the keyword and optionally a list of expanded_terms for niche query expansion. This method is async and MUST complete within the 120-second timeout enforced by HypeCycleClassifier.

**Time-Windowed Data Collection Pattern:**
The collector fetches patent data across THREE non-overlapping time periods that match patent filing and grant cycles:
- 2-year period: current_year - 2 to current_year - 1 (e.g., 2023-2024 for 2025)
- 5-year period: current_year - 7 to current_year - 3 (e.g., 2018-2022 for 2025)
- 10-year period: current_year - 12 to current_year - 8 (e.g., 2013-2017 for 2025)

These non-overlapping windows are CRITICAL - they prevent double-counting patents and allow calculation of filing velocity trends. Each period is fetched via a separate call to _fetch_period(), which runs sequentially (not parallel) to avoid overwhelming the API.

**PatentsView API Integration - Critical Details:**
The PatentsView Search API (https://search.patentsview.org/api/v1/patent/) has several quirks that MUST be followed:

1. **Manual URL Encoding Required**: Unlike other collectors that use httpx's params dict, PatentsView REQUIRES manual URL construction with urllib.parse.quote(). The query, fields, and options parameters must be JSON-stringified then URL-encoded manually. Pattern from lines 336-341:
   ```python
   q = json.dumps(query)
   f = json.dumps(fields)
   o = json.dumps(options)
   url = f'{self.API_URL}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
   response = await client.get(url, headers=headers)
   ```
   Without this manual encoding, the API returns 400 "Invalid query parameters".

2. **Query Operator Selection**: Uses _text_all operator (NOT _text_any) for multi-word keywords to ensure ALL words are present. This reduces false positives by 96%. The query structure (lines 277-311) uses nested _and/_or clauses:
   - Outer _and: contains text matching + date filters
   - Inner _or: searches both patent_title AND patent_abstract
   - For query expansion: wraps multiple _text_all clauses in outer _or to match ANY expanded term

3. **Field Names Matter**: API uses specific field names that differ from other patent APIs:
   - `patent_id` (not patent_number) - primary identifier
   - `patent_num_times_cited_by_us_patents` - citation count field
   - `assignees` - array of assignee objects with nested structure
   - Currently requested fields (lines 315-322): patent_id, patent_title, patent_abstract, patent_date, patent_num_times_cited_by_us_patents, assignees

4. **Authentication**: Requires X-Api-Key header (not Bearer token). The API key is loaded from settings.patentsview_api_key. If missing, the collector returns early with error response (lines 329-334).

**Assignee Data Structure - Current Usage:**
Each patent in the API response has an `assignees` array. Currently the collector extracts (lines 102-128):
- `assignee_organization`: Company/organization name (defaults to "Individual" if missing)
- `assignee_country`: Country code for geographic analysis

The assignee_organization values are aggregated into a dictionary (assignee_counts) that tracks patent count per organization. This is used to calculate:
- `unique_assignees`: Total count of distinct organizations
- `top_assignees`: Top 5 by patent count (line 111-118)
- `assignee_concentration`: Classified as "concentrated", "moderate", or "diverse" based on whether top 3 assignees hold >50%, >25%, or <25% of patents (lines 402-434)

**What's Missing - The Gap This Task Fills:**
The PatentsView API provides an `assignee_type` field that is NOT currently requested. According to the task description, this field contains codes 1-9 that classify assignees as company/individual/government. However, this field alone is insufficient because universities and research institutes are typically classified as "company" type but have distinct names like "MIT", "Stanford University", "Max Planck Institute".

The solution requires:
1. Adding `assignee_type` to the fields list in _fetch_period()
2. Extracting assignee_type from each assignee object in the response
3. Applying pattern matching to assignee_organization names to further classify "company" types into University vs Research Institute vs Corporate
4. Calculating new metrics like university_ratio, academic_ratio, commercialization_index, innovation_stage

**Metrics Calculation Pattern - Derived Insights:**
The collector calculates multiple derived insights from raw data (lines 190-200). These follow a consistent pattern:
- Each metric is calculated via a private method (e.g., _calculate_filing_velocity)
- Methods handle edge cases (zero denominators, missing data)
- Results are rounded to appropriate precision (2-3 decimal places)
- Categorical classifications use threshold-based logic with descriptive string returns

Current derived metrics include:
- `filing_velocity`: Growth rate comparing recent vs historical filing rates (line 379-400)
- `assignee_concentration`: Ownership distribution (concentrated/moderate/diverse) (line 402-434)
- `geographic_reach`: Country distribution (domestic/regional/global) (line 436-464)
- `patent_maturity`: Technology stage (emerging/developing/mature) based on patent count and citations (line 466-486)
- `patent_momentum`: Filing rate acceleration (accelerating/steady/decelerating) (line 488-519)
- `patent_trend`: Filing direction (increasing/stable/decreasing) (line 521-552)

**Error Handling and Graceful Degradation:**
The collector NEVER raises exceptions that would kill the entire analysis. Instead:
- All errors are accumulated in an `errors` list passed by reference to _fetch_period()
- If one period fails, the others continue (lines 83-85 check if ALL failed)
- Missing fields use .get() with defaults (e.g., `assignee.get("assignee_organization", "Individual")`)
- If all periods fail, returns _error_response() with zeros and error messages (lines 554-595)

This pattern is CRITICAL because HypeCycleClassifier requires minimum 3 of 5 collectors to succeed. If PatentsCollector crashes, the entire analysis fails.

**Query Expansion Integration:**
The collector supports niche query expansion (lines 280-297). When expanded_terms is provided:
- Constructs nested _or clauses wrapping multiple _text_all operators
- Each expanded term gets its own _text_all clause for title/abstract matching
- Allows finding patents that match original keyword OR any expanded term
- This is used by HypeCycleClassifier when social mentions are low (<50 in 30d)

**Response Structure and JSON Serialization:**
The final response dictionary (lines 202-238) MUST be JSON-serializable because it's:
1. Stored in SQLite database as TEXT (JSON.dumps in hype_classifier.py)
2. Returned directly to the API endpoint
3. Passed to DeepSeek LLM as context

Current response includes:
- Source metadata (source, collected_at, keyword)
- Patent counts (patents_2y, patents_5y, patents_10y, patents_total)
- Assignee metrics (unique_assignees, top_assignees)
- Geographic metrics (countries dict, geographic_diversity)
- Citation metrics (avg_citations_2y, avg_citations_5y)
- Derived insights (6 categorical metrics)
- LLM context (top_patents array with 5 most-cited patents)
- Error tracking (errors array)

### For New Assignee Classification Implementation

**Where the Code Needs to Change:**

1. **_fetch_period() method (lines 248-377):**
   - Add "assignee_type" to the fields list on line 321
   - This is the ONLY change needed in this method
   - The assignee_type values will automatically appear in response data

2. **collect() method assignee aggregation (lines 101-118):**
   - Currently loops through assignees extracting only organization and country
   - Needs to ALSO extract assignee_type from each assignee object
   - Must implement pattern matching logic to classify organizations
   - Pattern matching should check assignee_organization for keywords like "University", "Institut", "College", etc.
   - Build new data structures tracking type distributions

3. **New private methods to add:**
   - `_classify_assignee(assignee_org: str, assignee_type: int) -> str`: Returns "University", "Research Institute", "Corporate", "Government", or "Individual"
   - `_calculate_assignee_type_distribution(classified_assignees: List[str]) -> Dict`: Returns percentage breakdown
   - `_calculate_university_ratio(type_distribution: Dict) -> float`: University percentage
   - `_calculate_academic_ratio(type_distribution: Dict) -> float`: University + Research Institute percentage
   - `_calculate_commercialization_index(type_distribution: Dict) -> float`: Corporate / Academic ratio
   - `_calculate_innovation_stage(type_distribution: Dict, university_ratio: float, total_patents: int) -> tuple[str, str]`: Returns (stage, reasoning) like research_maturity pattern

4. **Response structure (lines 202-238):**
   - Add new fields after assignee metrics section (around line 217):
     - assignee_type_distribution: Dict with percentage breakdown
     - university_ratio: float
     - academic_ratio: float
     - commercialization_index: float
     - innovation_stage: str
     - innovation_stage_reasoning: str (following pattern from papers_collector research_maturity_reasoning)

5. **_error_response() method (lines 554-595):**
   - Add new fields with default/zero values
   - Ensures consistent response structure even on failures

**Pattern Matching Approach - Learning from PapersCollector:**

The PapersCollector implements paper type distribution analysis (lines 509-555) which provides an excellent template. Key patterns:

1. **Aggregation Phase**: Loop through all papers, check publicationTypes field, accumulate counts in a dictionary with predefined categories (Review, JournalArticle, Conference, Book, Other).

2. **Percentage Calculation**: Divide each category count by total items to get percentages. Handle zero division edge case.

3. **Integration with Derived Insights**: The paper_type_distribution is passed to _calculate_research_maturity() which uses type_percentages to inform classification logic (lines 343-406).

For assignee classification, the pattern would be:
1. Loop through all assignees across all periods
2. For each assignee, call _classify_assignee(org_name, type_code)
3. Accumulate counts in categories: University, Research Institute, Corporate, Government, Individual
4. Calculate percentages
5. Use distribution to calculate commercialization_index and innovation_stage

**University/Research Institute Pattern Matching Keywords:**

Based on common patent assignee naming conventions, pattern matching should check for:

Universities:
- Contains "University" or "Universit" (catches international variations)
- Contains "College" (but NOT "College of" which might be corporate training)
- Ends with "State" or "Tech" in US context
- Common abbreviations: MIT, Caltech, ETH, EPFL, etc.

Research Institutes:
- Contains "Institute" or "Institut"
- Contains "Research Center" or "Research Centre"
- Contains "Laboratory" or "Laborator"
- Government research orgs: NASA, NIST, Fraunhofer, Max Planck, CNRS, etc.
- Corporate research labs might be tricky: "IBM Research" should be Corporate, "Sandia National Laboratories" should be Research Institute

The classification logic should be case-insensitive and check for partial matches. Priority matters: Check for University patterns first, then Research Institute, then check assignee_type code for Government/Individual, default to Corporate.

**DeepSeek Patent Analysis Prompt Updates:**

The DeepSeek analyzer has a specialized prompt for patent data in _build_patents_prompt() (lines 267-294). Currently it includes:
- Patent filing counts and citations
- Filing velocity and assignee concentration
- Geographic diversity and reach
- Patent maturity and momentum

The prompt needs to be enhanced with new assignee classification metrics (around line 281, after "Patent momentum" line):
```python
- Assignee classification: university_ratio={data.get('university_ratio', 0):.1f}%, academic_ratio={data.get('academic_ratio', 0):.1f}%, commercialization_index={data.get('commercialization_index', 0):.2f}
- Innovation stage: {data.get('innovation_stage', 'unknown')}
```

And add interpretation guidance (around line 285, in the guidance section):
```
Assignee type distribution indicates technology maturity:
- High university ratio (>40%) suggests early research phase (innovation_trigger or early peak)
- Balanced academic/corporate mix (30-70%) suggests transition phase (peak or slope)
- Corporate dominance (>70%) with low academic (<20%) suggests commercialization (slope or plateau)
- Commercialization index >2.0 indicates strong commercial adoption
```

This guidance helps the LLM correctly interpret assignee patterns for Hype Cycle positioning.

### Technical Reference Details

#### PatentsView API assignee_type Codes

The assignee_type field uses integer codes (mentioned in task description as codes 1-9). Based on typical patent database conventions:
- Code 2 or 3: Likely individual/inventor
- Code 4 or 5: Likely company/organization
- Code 6 or 7: Likely government entity
- Exact mapping needs verification during implementation

**IMPORTANT**: The actual code values should be validated with real API responses during testing. The pattern matching will be MORE reliable than type codes alone for distinguishing universities from corporations.

#### Collector Response Field Additions

Current top_assignees structure (line 111-118):
```python
{"name": "IBM", "patent_count": 42}
```

Should be enhanced to:
```python
{"name": "IBM", "patent_count": 42, "type": "Corporate"}
```

This provides transparency in the top_assignees list and helps LLM understand assignee composition.

#### Database Schema Considerations

The database.py init_db() function creates a schema with patent_data stored as TEXT (JSON serialized). No schema changes are needed - the new fields will be automatically stored in the JSON blob when the response is serialized.

However, the idempotent migration pattern (lines 34-47) provides a template if future schema changes are needed.

#### Test Coverage Requirements

The test suite (test_patents_collector.py) has 20 existing tests covering:
- Success cases with mock responses (lines 22-210)
- Error handling (rate limits, timeouts, network errors, auth failures)
- Edge cases (zero results, missing fields, partial failures)
- Derived metric calculations (velocity, concentration, reach, maturity, momentum, trend)
- JSON serialization verification

New tests needed:
1. test_assignee_classification_university: Mock response with university assignees, verify classification
2. test_assignee_classification_research_institute: Mock response with research institute assignees
3. test_assignee_classification_mixed: Mix of university, corporate, government, verify distribution percentages
4. test_assignee_type_distribution_calculation: Verify percentage math is correct
5. test_university_ratio_calculation: Verify university_ratio metric
6. test_commercialization_index_high: High corporate/low academic should give high index
7. test_innovation_stage_early: High university ratio should classify as early_research
8. test_innovation_stage_commercialized: High corporate ratio should classify as commercialized
9. test_pattern_matching_edge_cases: Test ambiguous names, international variations
10. test_real_api_validation: Integration test with real PatentsView API for "quantum computing" (early-stage, expect high university ratio) and "cloud computing" (mature, expect high corporate ratio)

Tests should follow existing patterns:
- Use @pytest.mark.asyncio decorator
- Mock httpx.AsyncClient.get with controlled responses
- Use autofixture mock_settings to provide API key
- Verify all new fields are present in response
- Verify JSON serialization still works
- Test both success and error paths

#### Integration Points

The HypeCycleClassifier (hype_classifier.py) doesn't need changes - it treats PatentsCollector like a black box. The new fields will automatically flow through to:
1. Database storage (JSON serialization in _persist_result)
2. DeepSeek analysis (_analyze_source receives full collector_data dict)
3. API response (final response includes full collector_data)
4. Frontend display (frontend shows per-source analyses and collector data)

The ONLY integration change needed is the DeepSeek patent prompt update described above.

#### Configuration Requirements

No new configuration needed. The existing patentsview_api_key setting is sufficient. The assignee_type field is part of the standard API response when requested in the fields list.

### Critical Implementation Notes

1. **Preserve Existing Behavior**: All current metrics and response fields MUST remain unchanged. This is additive enhancement only.

2. **Safe Dictionary Access**: Use .get() with defaults for assignee_type field since it might be missing in older API responses or for certain patent records.

3. **Edge Case: Multiple Assignees Per Patent**: Some patents have multiple assignees of different types. The classification should count EACH assignee separately (not per patent). This matches the current top_assignees aggregation logic.

4. **Performance**: The pattern matching logic adds minimal overhead since it only processes assignees from the 100 patents returned (max 300 across 3 periods). No performance concerns.

5. **Testing Strategy**: Start with unit tests using mocked data, then validate with real API calls for 2-3 representative keywords before considering the feature complete.

6. **Error Recovery**: If assignee_type field is missing from API response, the pattern matching should still work based on organization name alone. Log a warning but don't fail the collection.

7. **Documentation**: Update CLAUDE.md PatentsCollector section (around line 95-130) to document the new fields and their interpretation for future developers.

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
