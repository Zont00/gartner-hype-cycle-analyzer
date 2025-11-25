---
name: h-implement-deepseek-integration
branch: feature/deepseek-integration
status: pending
created: 2025-11-25
---

# DeepSeek LLM Integration

## Problem/Goal
Implement the DeepSeek API client and prompt engineering layer for the Gartner Hype Cycle Analyzer. This module will handle communication with the DeepSeek LLM API, craft specialized prompts for each data source (social, papers, patents, news, finance), and parse the LLM responses to extract hype cycle classifications. It will perform per-source analysis (5 individual classifications) and final synthesis (aggregating all sources into one final classification with reasoning). This is the AI intelligence layer that transforms raw data into actionable hype cycle positioning.

## Success Criteria
- [ ] `backend/app/analyzers/deepseek.py` module created with DeepSeekClient class
- [ ] DeepSeek API integration working (authentication, request/response handling)
- [ ] Per-source prompt templates created for each of the 5 collectors (social, papers, patents, news, finance)
- [ ] Synthesis prompt template created to aggregate all 5 source analyses
- [ ] Response parsing logic to extract phase, confidence, and reasoning from LLM JSON responses
- [ ] Error handling for API failures (rate limits, timeouts, invalid responses)
- [ ] Unit tests with mocked DeepSeek API responses

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
