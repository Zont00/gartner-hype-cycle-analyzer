---
name: h-implement-social-collector
branch: feature/social-collector
status: pending
created: 2025-11-25
---

# Social Media Collector - Hacker News

## Problem/Goal
Implement the social media data collector for the Gartner Hype Cycle Analyzer. This collector will gather social media signals about a given technology by querying the Hacker News Algolia API. It will analyze discussion volume, engagement metrics (points, comments), and trends over time to provide insights into how the tech community perceives and discusses the technology. This is one of the 5 data sources that feed into the DeepSeek LLM for hype cycle classification.

## Success Criteria
- [ ] `backend/app/collectors/social.py` module created with SocialCollector class
- [ ] Hacker News Algolia API integration working (search by keyword)
- [ ] Collector returns structured data: story count, engagement metrics, trend direction
- [ ] Data aggregation over time periods (last 30 days, 6 months, 1 year)
- [ ] Error handling for API failures (rate limits, network issues)
- [ ] Unit tests for collector logic with mocked API responses
- [ ] Returns data in standardized format compatible with DeepSeek analyzer

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
