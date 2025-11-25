---
name: h-implement-patents-collector
branch: feature/patents-collector
status: pending
created: 2025-11-25
---

# Patent Data Collector - PatentsView

## Problem/Goal
Implement the patent data collector for the Gartner Hype Cycle Analyzer. This collector will gather patent filing signals about a given technology by querying the PatentsView API. It will analyze patent filing trends, assignee diversity, geographical distribution, and innovation velocity over time to provide insights into industrial investment and commercialization activity around the technology. This is one of the 5 data sources that feed into the DeepSeek LLM for hype cycle classification.

## Success Criteria
- [ ] `backend/app/collectors/patents.py` module created with PatentsCollector class
- [ ] PatentsView API integration working (search patents by keyword)
- [ ] Collector returns structured data: patent count, filing trends, assignee diversity
- [ ] Time-based analysis (patents per year, geographical distribution over time)
- [ ] Error handling for API failures (rate limits, missing data, network issues)
- [ ] Unit tests for collector logic with mocked API responses
- [ ] Returns data in standardized format compatible with DeepSeek analyzer

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
