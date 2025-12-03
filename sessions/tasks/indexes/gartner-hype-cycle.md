---
index: gartner-hype-cycle
name: Gartner Hype Cycle Analyzer
description: MVP application that analyzes emerging technologies and positions them on the Gartner Hype Cycle using 5 data sources (social, papers, patents, news, finance) and DeepSeek LLM
---

# Gartner Hype Cycle Analyzer

## Active Tasks

### High Priority
- `h-fix-cache-persource-analyses.md` - Fix missing per_source_analyses data in cached database results

### Medium Priority

### Low Priority

### Investigate

## Completed Tasks
- `h-implement-project-setup.md` - Setup project structure, FastAPI backend, SQLite database, and minimal frontend
- `h-implement-social-collector.md` - Implement Hacker News collector for social media signals
- `h-implement-papers-collector.md` - Implement Semantic Scholar collector for research papers
- `h-implement-patents-collector.md` - Implement PatentsView collector for patent data
- `h-implement-news-collector.md` - Implement GDELT collector for news coverage
- `h-implement-finance-collector.md` - Implement Yahoo Finance collector with DeepSeek-based ticker discovery
- `h-implement-deepseek-integration.md` - Implement DeepSeek API client and prompt engineering for hype cycle classification
- `h-implement-hype-classifier.md` - Implement main classifier logic and synthesis of 5 data sources
- `h-implement-api.md` - Implement FastAPI endpoints for analysis and caching
- `m-implement-frontend.md` - Implement minimal HTML/JS frontend with hype cycle visualization
