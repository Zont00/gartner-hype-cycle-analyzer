---
name: h-fix-cache-persource-analyses
branch: fix/h-fix-cache-persource-analyses
status: pending
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
- [ ] Database schema updated with `per_source_analyses_data TEXT` column in analyses table
- [ ] `_persist_result()` method saves per_source_analyses as JSON to new column
- [ ] `_check_cache()` method retrieves and parses per_source_analyses from database
- [ ] Cached results return complete per_source_analyses dict with all 5 sources (social, papers, patents, news, finance)
- [ ] Frontend displays all 5 source analysis cards on cache hit (previously showed "not available")
- [ ] Existing test suite passes (no regressions in HypeCycleClassifier tests)
- [ ] Manual testing confirms cache hit shows per_source_analyses correctly

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
