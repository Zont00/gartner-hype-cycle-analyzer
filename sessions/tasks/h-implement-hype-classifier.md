---
name: h-implement-hype-classifier
branch: feature/hype-classifier
status: pending
created: 2025-11-25
---

# Hype Cycle Classifier - Main Orchestration Logic

## Problem/Goal
Implement the main HypeCycleClassifier orchestration logic for the Gartner Hype Cycle Analyzer. This module coordinates the entire analysis workflow: it triggers all 5 data collectors in parallel (social, papers, patents, news, finance), passes each collector's data to DeepSeek for individual source analysis, then synthesizes all 5 analyses into a final hype cycle classification. It handles caching (check SQLite before collecting), error recovery (graceful degradation if a collector fails), and returns the complete analysis result with per-source breakdowns and final positioning. This is the core intelligence orchestrator that ties all components together.

## Success Criteria
- [ ] `backend/app/analyzer/hype_classifier.py` module created with HypeCycleClassifier class
- [ ] Parallel execution of all 5 collectors (social, papers, patents, news, finance) using asyncio
- [ ] Per-source analysis: passes each collector's data to DeepSeek for individual classification
- [ ] Final synthesis: aggregates 5 source analyses into one final hype cycle position
- [ ] Cache checking: queries SQLite before running collectors to avoid redundant API calls
- [ ] Graceful degradation: analysis proceeds even if 1-2 collectors fail (with reduced confidence)
- [ ] Returns complete analysis result with source breakdowns and final classification
- [ ] Unit tests with mocked collectors and DeepSeek responses

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [YYYY-MM-DD] Started task, initial research
