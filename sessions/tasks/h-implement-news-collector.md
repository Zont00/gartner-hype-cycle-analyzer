---
name: h-implement-news-collector
branch: feature/news-collector
status: pending
created: 2025-11-25
---

# News Coverage Collector - GDELT

## Problem/Goal
Implement the news coverage data collector for the Gartner Hype Cycle Analyzer. This collector will gather media coverage signals about a given technology by querying the GDELT API. It will analyze news volume, sentiment/tone, coverage distribution (mainstream vs niche), and media attention trends over time to provide insights into public perception and mainstream awareness of the technology. This is one of the 5 data sources that feed into the DeepSeek LLM for hype cycle classification.

## Success Criteria
- [ ] `backend/app/collectors/news.py` module created with NewsCollector class
- [ ] GDELT API integration working (search news by keyword)
- [ ] Collector returns structured data: article count, sentiment/tone, coverage volume
- [ ] Time-based analysis (news coverage per time period, trend evolution)
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
