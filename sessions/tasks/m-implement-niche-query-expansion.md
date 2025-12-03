---
name: m-implement-niche-query-expansion
branch: feature/niche-query-expansion
status: pending
created: 2025-12-03
---

# Implement Niche Query Expansion with DeepSeek

## Problem/Goal
For niche technologies with limited online presence, the current system often fails to collect sufficient data (minimum 3/5 collectors required). This results in HTTP 503 errors and no analysis for users. The goal is to implement intelligent query expansion using DeepSeek LLM to generate related search terms when initial data collection indicates a niche technology, improving coverage without sacrificing quality for mainstream technologies.

## Success Criteria
- [ ] **Niche detection via SocialCollector**: System automatically identifies when a technology is "niche" based solely on low social media metrics (e.g., mentions_30d < 50 OR mentions_total < 100)
- [ ] **DeepSeek query expansion**: When niche is detected, DeepSeek generates 3-5 related search terms with validation (relevance check, no generic terms like "technology" or "system")
- [ ] **Selective collector application**: Query expansion applied ONLY to 4 collectors (Social, Papers, Patents, News), NOT to FinanceCollector (which already uses DeepSeek for ticker discovery)
- [ ] **Improved coverage for niche technologies**: For tested niche technologies (e.g., "plant cell culture", "CRISPR base editing"), system now succeeds (≥3 collectors) where it previously failed (<3 collectors)
- [ ] **Quality preservation for mainstream**: For mainstream technologies (e.g., "blockchain", "quantum computing"), behavior remains unchanged (no expansion triggered, same results as before)
- [ ] **Transparent metadata**: Response includes fields indicating whether query expansion was used (`query_expansion_applied: bool`) and which expanded terms were applied (`expanded_terms: List[str]`)
- [ ] **Comprehensive test coverage**: Tests for niche detection logic, DeepSeek integration, expansion application per collector, fallback behavior on API errors, and end-to-end scenarios

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
