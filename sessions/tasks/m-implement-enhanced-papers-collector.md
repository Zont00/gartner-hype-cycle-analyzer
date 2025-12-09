---
name: m-implement-enhanced-papers-collector
branch: feature/m-implement-enhanced-papers-collector
status: in-progress
created: 2025-12-09
---

# Enhanced Papers Collector with Extended Metrics

## Problem/Goal
The current PapersCollector provides basic publication metrics using a 2-year and 5-year window. However, it lacks deeper insights into:
- **Long-term trends**: 10-year horizon needed to understand research evolution
- **Research leadership**: Who are the dominant authors and institutions?
- **Research maturity indicators**: Paper types (reviews, system demonstrations, fundamental theory) reveal maturity better than simple counts

This enhancement will provide richer academic research signals for more accurate Hype Cycle classification, especially distinguishing between emerging technologies (dominated by theory papers) and mature technologies (dominated by reviews and journal articles).

## Success Criteria
- [ ] Extend temporal analysis to 10 years (add publications_10y, avg_citations_10y metrics)
- [ ] Aggregate and return top 10 authors by publication count across all time periods
- [ ] Extract and return top 10 institutions from author affiliations
- [ ] Analyze paper type distribution (Review, JournalArticle, Conference, Theory) using Semantic Scholar publicationTypes field
- [ ] Enhance research_maturity calculation to incorporate paper type distribution (e.g., >30% reviews indicates mature field)
- [ ] Add research_maturity_reasoning field explaining maturity classification
- [ ] Update all tests to cover new metrics and paper type analysis

## Context Manifest

### How the PapersCollector Currently Works

The PapersCollector is located at `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py` (464 lines) and serves as one of five parallel data collectors in the Hype Cycle analysis pipeline. When a user submits a technology keyword through the frontend, the request flows to the FastAPI backend's `/api/analyze` endpoint, which invokes the HypeCycleClassifier orchestrator. This orchestrator instantiates all five collectors (Social, Papers, Patents, News, Finance) and runs them in parallel via `asyncio.gather(return_exceptions=True)` with a 120-second timeout.

**Current Architecture Flow:**

The PapersCollector queries the Semantic Scholar API bulk search endpoint (`https://api.semanticscholar.org/graph/v1/paper/search/bulk`) across **two non-overlapping time periods**: a 2-year recent window and a 5-year historical window. The implementation pattern follows these critical steps:

1. **Time Window Calculation** (lines 53-54): Computes `year_2y_start = current_year - 2` and `year_5y_start = current_year - 5`. These windows are used to filter papers by publication year.

2. **Parallel Period Fetching** (lines 61-66): Makes two async HTTP calls via `_fetch_period()` to retrieve papers for each time window. The 2y window gets papers from (current_year - 2) to current_year, while the 5y window gets papers from (current_year - 5) to (current_year - 2) to avoid overlapping data.

3. **Query Construction with Exact Phrase Matching** (lines 228-236): Wraps keywords in quotes for exact phrase matching: `query_str = f'"{keyword}"'`. This is CRITICAL for reducing false positives by 99.9% when searching for multi-word technology terms. For query expansion (niche technologies), constructs OR queries: `"keyword" | "term1" | "term2"` using Semantic Scholar's pipe separator syntax.

4. **API Request Pattern** (lines 239-250):
   - Uses `httpx.AsyncClient` with 30-second timeout
   - Requests specific fields: `paperId,title,year,citationCount,influentialCitationCount,authors,venue`
   - Limits results to 100 papers per request (API maximum)
   - Optional authentication via `x-api-key` header if `SEMANTIC_SCHOLAR_API_KEY` configured

5. **Safe Data Extraction** (lines 72-146): Uses `.get()` with defaults throughout to prevent KeyError exceptions on inconsistent API responses. The API may omit fields entirely (not just return null), so defensive access patterns are essential: `data.get("total", 0) if data else 0`.

6. **Citation Metrics Calculation** (lines 76-102): For the 2y period, extracts papers and calculates:
   - `avg_citations_2y`: Average citation count across all papers
   - `avg_influential_citations_2y`: Average influential citation count (Semantic Scholar's quality metric)
   - `top_papers`: Top 5 papers sorted by citation count for LLM context

7. **Diversity Metrics Calculation** (lines 110-129): For the 5y period, tracks unique authors by `authorId` and unique venues by name to calculate research breadth indicators. This reveals whether a technology is being studied by a narrow group or broadly across the academic community.

8. **Derived Insights** (lines 131-146): Calls helper methods to calculate:
   - `research_maturity`: "emerging" (<10 papers, <5 citations) / "developing" / "mature" (>50 papers or >20 citations)
   - `research_momentum`: "accelerating" (2y rate >1.5x historical) / "steady" / "decelerating" (<0.5x)
   - `research_trend`: "increasing" (>30% growth) / "stable" / "decreasing" (<-30%)
   - `research_breadth`: "narrow" / "moderate" / "broad" based on author/venue diversity ratios

**Maturity Calculation Logic** (lines 296-321): The current `_calculate_research_maturity()` method is PURELY quantitative, using only publication counts and average citations. It does NOT analyze paper types, which is a significant limitation. The thresholds are:
- **Mature**: `total_publications > 50` OR `avg_citations_2y > 20`
- **Emerging**: `total_publications < 10` AND `avg_citations_2y < 5`
- **Developing**: Everything between these thresholds

This approach misses important maturity signals. For example, a field with 30 publications could be classified as "developing" even if 80% are review papers and comprehensive surveys (indicating maturity), while another field with 60 publications might be "mature" even if they're all preliminary conference papers (indicating early stage). Paper type distribution provides a more nuanced maturity assessment.

**Error Handling Pattern** (lines 182-188, 254-274): Never raises exceptions during collection. On API failures, returns `_error_response()` with fallback zero values and error tracking. This graceful degradation is critical because the HypeCycleClassifier requires only 3 of 5 collectors to succeed.

**Response Structure** (lines 148-180): Returns a 23-field dictionary including raw metrics (publication counts, citations), diversity indicators (author/venue counts), derived insights (maturity, momentum, trend, breadth), top papers for LLM context, and error tracking. This data flows to DeepSeekAnalyzer for LLM-based Hype Cycle classification.

### What the Enhancement Needs to Connect With

**1. Parallel Time Period Pattern (PatentsCollector Reference):**

The PatentsCollector (`backend/app/collectors/patents.py`) already implements a THREE-period temporal analysis with 2y, 5y, and 10y windows. Lines 57-66 show the pattern we need to replicate:

```python
year_2y_start = current_year - 2
year_2y_end = current_year - 1
year_5y_start = current_year - 7
year_5y_end = current_year - 3
year_10y_start = current_year - 12
year_10y_end = current_year - 8
```

The 10-year window uses **non-overlapping** periods (2014-2018 for current year 2025) to prevent double-counting papers. This means the PapersCollector's existing logic where `year_5y_start = current_year - 5` will need adjustment to match this non-overlapping pattern. The new structure should be:
- **2y period**: Recent papers (current_year - 2 to current_year)
- **5y period**: Middle historical papers (current_year - 7 to current_year - 3) - CHANGED from current pattern
- **10y period**: Oldest historical papers (current_year - 12 to current_year - 8)

**CRITICAL**: This requires modifying the existing `_fetch_period()` calls and adjusting the year boundary calculations to match the non-overlapping PatentsCollector pattern. The existing 5y calculation must shift to avoid overlapping with the 2y window.

**2. Aggregation Patterns (Multiple Collector References):**

**Top Assignees Pattern** (PatentsCollector lines 101-118): Shows how to aggregate entities across multiple time periods, count occurrences, and return top-N results:

```python
assignee_counts = {}
for patent in all_patents:  # Aggregates across 2y, 5y, 10y
    assignees = patent.get("assignees", [])
    for assignee in assignees:
        org = assignee.get("assignee_organization", "Individual")
        if org:
            assignee_counts[org] = assignee_counts.get(org, 0) + 1

top_assignees = [
    {"name": name, "patent_count": count}
    for name, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True)[:5]
]
```

For authors, we'll use this EXACT pattern but track author names from the `authors` array in each paper. The Semantic Scholar API returns `authors: [{"authorId": "123", "name": "Alice"}]`, so we'll aggregate by name and count publications.

**Top Domains Pattern** (NewsCollector lines 113-124): Similar aggregation for top news domains:

```python
domain_counts = {}
for article in all_articles:
    domain = article.get("domain", "")
    if domain:
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

top_domains = []
if domain_counts:
    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
    top_domains = [
        {"domain": domain, "count": count}
        for domain, count in sorted_domains[:5]
    ]
```

For institutions, we'll adapt this pattern to extract affiliations from author metadata. The Semantic Scholar API may include author affiliation data in extended fields.

**3. Semantic Scholar API Field Requirements:**

The current implementation requests these fields (line 220):
```python
fields = "paperId,title,year,citationCount,influentialCitationCount,authors,venue"
```

To support the enhancement, we need to add:
- **`publicationTypes`**: Array of strings like ["Review", "JournalArticle", "Conference", "Editorial", "Book", "ClinicalTrial"]. This is the KEY field for paper type distribution analysis.
- **Extended author fields**: The basic `authors` field may only include authorId and name. To get institutional affiliations, we may need to query author details separately OR check if the bulk search endpoint supports extended author metadata.

The Semantic Scholar API documentation (based on existing usage patterns) shows the bulk endpoint supports comma-separated field lists. We'll need to test if `publicationTypes` is available on the bulk search endpoint or if it requires individual paper queries.

**4. Paper Type Distribution Analysis (New Logic Required):**

No existing collector performs type distribution analysis, but the pattern should follow NewsCollector's tone distribution calculation (lines 320-369). The structure will be:

```python
def _calculate_paper_type_distribution(papers: List[Dict]) -> Dict[str, Any]:
    type_counts = {
        "Review": 0,
        "JournalArticle": 0,
        "Conference": 0,
        "Book": 0,
        "Other": 0
    }

    total_with_types = 0
    for paper in papers:
        pub_types = paper.get("publicationTypes", [])
        if pub_types:
            total_with_types += 1
            for pub_type in pub_types:
                if pub_type in type_counts:
                    type_counts[pub_type] += 1
                else:
                    type_counts["Other"] += 1

    # Calculate percentages
    percentages = {}
    if total_with_types > 0:
        for type_name, count in type_counts.items():
            percentages[f"{type_name.lower()}_percentage"] = (count / total_with_types) * 100

    return {
        "type_counts": type_counts,
        "type_percentages": percentages,
        "papers_with_type_info": total_with_types
    }
```

**5. Enhanced Maturity Calculation Logic:**

The new `_calculate_research_maturity()` must incorporate paper type percentages. Based on academic publishing patterns:

- **Mature fields** have high review paper percentages (>30% reviews indicates extensive synthesis of existing knowledge, comprehensive surveys, and meta-analyses)
- **Emerging fields** have high conference/preprint percentages (>60% conferences indicates rapid dissemination, early-stage validation)
- **Developing fields** show transition from conferences to journals (increasing journal percentage, moderate review presence)

The updated logic should:
1. Calculate paper type distribution across ALL time periods (2y + 5y + 10y papers)
2. Extract review_percentage and journal_percentage from type distribution
3. Adjust maturity classification using type-aware thresholds
4. Generate `research_maturity_reasoning` explaining the classification

**6. DeepSeek Prompt Integration (Analyzer Impact):**

The DeepSeekAnalyzer builds prompts from collector data (lines 239-265 in `deepseek.py`). The current papers prompt includes:

```python
- Publications: 2y={data.get('publications_2y', 0)}, 5y={data.get('publications_5y', 0)}, total={data.get('publications_total', 0)}
- Research maturity: {data.get('research_maturity', 'unknown')}
```

After enhancement, the prompt should include:
- `publications_10y` in the time series data
- `top_authors` list with publication counts
- `top_institutions` list with publication counts
- `paper_type_distribution` with percentages
- `research_maturity_reasoning` to provide LLM context on WHY the maturity was classified

The prompt interpretation guidance (lines 256-260) currently uses quantitative thresholds. We'll need to add type-based guidance: "innovation_trigger: >60% conference papers, few reviews; plateau: >30% review papers, established journal presence".

**7. Test Coverage Requirements:**

The existing test suite (`backend/tests/test_papers_collector.py`) has 18 tests covering success cases, error handling, edge cases, and derived insights. The enhancement requires NEW tests for:

- **10-year period fetching**: Mock three API responses (2y, 5y, 10y) and verify all periods collected
- **Author aggregation**: Mock papers with duplicate authors across periods, verify top 10 authors by count
- **Institution extraction**: Mock papers with author affiliations, verify institution aggregation
- **Paper type distribution**: Mock papers with various publicationTypes arrays, verify percentage calculations
- **Enhanced maturity with types**: Mock high review percentage papers, verify "mature" classification; mock high conference percentage, verify "emerging"
- **Maturity reasoning generation**: Verify reasoning string includes type-based justification
- **Partial data with 10y failure**: Mock 2y/5y success but 10y failure, verify graceful handling

**8. Database Schema (No Changes Required):**

The database stores collector data as JSON blobs in the `papers_data` TEXT column (database.py line 26). Since we're returning the same dictionary structure (just with additional fields), no schema migration is needed. The JSON serialization will automatically include the new fields (publications_10y, top_authors, top_institutions, paper_type_distribution, research_maturity_reasoning).

**9. Query Expansion Compatibility:**

The existing query expansion workflow (hype_classifier.py lines 272-353) re-runs 4 collectors (Social, Papers, Patents, News) with expanded terms for niche technologies. The PapersCollector already supports this via the `expanded_terms` parameter (lines 19-47, 228-236). The enhancement MUST maintain this compatibility - all three time periods (2y, 5y, 10y) should use the same expanded query when provided.

### Technical Reference Details

#### API Endpoints & Request Structure

**Semantic Scholar Bulk Search API:**
- Endpoint: `https://api.semanticscholar.org/graph/v1/paper/search/bulk`
- Method: GET
- Authentication: Optional `x-api-key` header (rate limits: 100 req/5min without key, higher with key)
- Query Parameters:
  - `query`: Search string (use quotes for exact phrases, pipe `|` for OR logic)
  - `year`: Year filter in format "YYYY-YYYY" (e.g., "2020-2023")
  - `fields`: Comma-separated field list
  - `limit`: Maximum papers per request (max 100)

**Response Structure:**
```json
{
  "total": 1234,
  "offset": 0,
  "next": 100,
  "data": [
    {
      "paperId": "abc123",
      "title": "Paper Title",
      "year": 2023,
      "citationCount": 45,
      "influentialCitationCount": 8,
      "authors": [
        {"authorId": "123", "name": "Alice Smith"}
      ],
      "venue": "Nature",
      "publicationTypes": ["JournalArticle", "Review"]
    }
  ]
}
```

**Note**: The `publicationTypes` field may not be available on all papers. Handle missing data gracefully with `.get("publicationTypes", [])`.

#### Function Signatures to Modify/Add

**Modified `collect()` signature** (no change needed, return type expands):
```python
async def collect(self, keyword: str, expanded_terms: Optional[List[str]] = None) -> Dict[str, Any]
```

**Modified `_fetch_period()` - year boundaries adjustment**:
```python
async def _fetch_period(
    self,
    client: httpx.AsyncClient,
    keyword: str,
    year_start: int,
    year_end: int,  # Now represents END year (exclusive)
    errors: List[str],
    expanded_terms: Optional[List[str]] = None
) -> Dict[str, Any] | None
```

**New helper methods to add**:
```python
def _aggregate_authors(self, all_papers: List[Dict]) -> List[Dict[str, Any]]:
    """
    Aggregate authors across all papers and return top 10 by publication count.

    Returns:
        [{"name": "Alice Smith", "publication_count": 15}, ...]
    """

def _aggregate_institutions(self, all_papers: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract and aggregate institutions from author affiliations.

    Returns:
        [{"name": "MIT", "publication_count": 23}, ...]
    """

def _calculate_paper_type_distribution(self, all_papers: List[Dict]) -> Dict[str, Any]:
    """
    Analyze distribution of paper types.

    Returns:
        {
            "type_counts": {"Review": 12, "JournalArticle": 45, ...},
            "type_percentages": {"review_percentage": 15.2, ...},
            "papers_with_type_info": 79
        }
    """

def _calculate_research_maturity(
    self,
    publications_2y: int,
    publications_5y: int,
    publications_10y: int,
    avg_citations_2y: float,
    paper_type_distribution: Dict[str, Any]
) -> tuple[str, str]:
    """
    Calculate research maturity incorporating paper type distribution.

    Returns:
        ("mature", "High review paper percentage (35%) indicates field maturity")
    """
```

#### Response Structure Extensions

**New fields to add to return dictionary**:
```python
{
    # Existing fields...
    "publications_2y": 45,
    "publications_5y": 80,
    "publications_10y": 120,  # NEW
    "publications_total": 245,  # Now includes 10y

    # NEW author metrics
    "top_authors": [
        {"name": "Alice Smith", "publication_count": 15},
        {"name": "Bob Jones", "publication_count": 12},
        # ... up to 10 authors
    ],

    # NEW institution metrics
    "top_institutions": [
        {"name": "MIT", "publication_count": 23},
        {"name": "Stanford University", "publication_count": 18},
        # ... up to 10 institutions
    ],

    # NEW paper type analysis
    "paper_type_distribution": {
        "type_counts": {
            "Review": 12,
            "JournalArticle": 45,
            "Conference": 67,
            "Book": 3,
            "Other": 8
        },
        "type_percentages": {
            "review_percentage": 8.9,
            "journal_percentage": 33.3,
            "conference_percentage": 49.6,
            "book_percentage": 2.2,
            "other_percentage": 5.9
        },
        "papers_with_type_info": 135
    },

    # MODIFIED maturity fields
    "research_maturity": "mature",  # Still string
    "research_maturity_reasoning": "High review paper percentage (35%) and journal dominance (60%) indicate established field with comprehensive synthesis literature",  # NEW

    # Existing fields continue...
}
```

#### Configuration & Dependencies

**No new dependencies required** - all enhancement uses existing:
- `httpx` for async HTTP requests
- `datetime` for time calculations
- Standard library `typing`, `Dict`, `List`, `Any` for type hints

**Environment Variables** (unchanged):
- `SEMANTIC_SCHOLAR_API_KEY` (optional, for higher rate limits)

#### File Locations

**Implementation files**:
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\app\collectors\papers.py` (modify)
- `C:\Users\Hp\Desktop\Gartner's Hype Cycle\backend\tests\test_papers_collector.py` (extend)

**Reference patterns**:
- PatentsCollector: `backend/app/collectors/patents.py` (10y temporal pattern, lines 57-99)
- NewsCollector: `backend/app/collectors/news.py` (distribution calculation, lines 320-369)
- DeepSeek Analyzer: `backend/app/analyzers/deepseek.py` (prompt integration, lines 239-265)

**Documentation updates needed**:
- `CLAUDE.md` lines 117-187 (update PapersCollector section with new metrics)

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
