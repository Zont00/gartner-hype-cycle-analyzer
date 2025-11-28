"""
Real API test for DeepSeek analyzer.
Tests with realistic collector data and actual DeepSeek API calls.

Usage:
    cd backend
    source venv/Scripts/activate
    python test_real_deepseek.py

Requirements:
    - DEEPSEEK_API_KEY must be set in backend/.env
    - This will make 6 real API calls (5 per-source + 1 synthesis)
    - Will consume DeepSeek API credits
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.analyzers.deepseek import DeepSeekAnalyzer
from app.config import get_settings


# Realistic collector data for "quantum computing"
# Based on actual collector implementations and expected data structures
QUANTUM_COMPUTING_DATA = {
    "social": {
        "source": "hacker_news",
        "keyword": "quantum computing",
        "mentions_30d": 156,
        "mentions_6m": 420,
        "mentions_1y": 850,
        "mentions_total": 1247,
        "avg_points_30d": 78.5,
        "avg_comments_30d": 42.3,
        "avg_points_6m": 65.2,
        "avg_comments_6m": 38.7,
        "sentiment": 0.68,
        "recency": "high",
        "growth_trend": "increasing",
        "momentum": "accelerating",
        "top_stories": [
            {
                "title": "Google's Willow quantum chip achieves breakthrough error correction",
                "points": 485,
                "comments": 156,
                "age_days": 2
            },
            {
                "title": "IBM unveils 1000+ qubit quantum processor",
                "points": 352,
                "comments": 98,
                "age_days": 15
            }
        ],
        "errors": []
    },
    "papers": {
        "source": "semantic_scholar",
        "keyword": "quantum computing",
        "publications_2y": 2847,
        "publications_5y": 6523,
        "publications_total": 12456,
        "avg_citations_2y": 18.5,
        "avg_citations_5y": 32.7,
        "citation_velocity": 0.45,
        "research_maturity": "developing",
        "research_momentum": "accelerating",
        "research_trend": "increasing",
        "research_breadth": "broad",
        "author_diversity": 8542,
        "venue_diversity": 245,
        "top_papers": [
            {
                "title": "Quantum supremacy using a programmable superconducting processor",
                "year": 2023,
                "citations": 1247
            },
            {
                "title": "Error mitigation for short-depth quantum circuits",
                "year": 2024,
                "citations": 856
            }
        ],
        "errors": []
    },
    "patents": {
        "source": "patentsview",
        "keyword": "quantum computing",
        "patents_2y": 524,
        "patents_5y": 1847,
        "patents_10y": 3265,
        "patents_total": 4123,
        "avg_citations_2y": 8.5,
        "avg_citations_5y": 15.3,
        "filing_velocity": 0.38,
        "unique_assignees": 147,
        "assignee_concentration": "moderate",
        "geographic_diversity": 18,
        "geographic_reach": "global",
        "patent_maturity": "developing",
        "patent_momentum": "accelerating",
        "patent_trend": "increasing",
        "top_assignees": [
            {"name": "IBM", "count": 342},
            {"name": "Google", "count": 287},
            {"name": "Microsoft", "count": 156},
            {"name": "Intel", "count": 134},
            {"name": "Alibaba", "count": 98}
        ],
        "top_patents": [
            {
                "patent_number": "US11234567B2",
                "title": "Quantum error correction using surface codes",
                "date": "2023-08-15",
                "assignee": "IBM",
                "citations": 42
            }
        ],
        "errors": []
    },
    "news": {
        "source": "gdelt",
        "keyword": "quantum computing",
        "articles_30d": 1247,
        "articles_3m": 3856,
        "articles_1y": 8942,
        "articles_total": 9523,
        "unique_domains": 456,
        "geographic_diversity": 42,
        "avg_tone": 0.58,
        "tone_distribution": {
            "positive": 5247,
            "neutral": 3156,
            "negative": 1120
        },
        "volume_intensity_30d": 41.6,
        "volume_intensity_3m": 42.8,
        "volume_intensity_1y": 24.5,
        "media_attention": "high",
        "coverage_trend": "increasing",
        "sentiment_trend": "positive",
        "mainstream_adoption": "mainstream",
        "top_articles": [
            {
                "url": "https://techcrunch.com/quantum-breakthrough",
                "title": "Google's quantum chip achieves major milestone",
                "domain": "techcrunch.com",
                "source_country": "United States",
                "seendate": "20251125"
            }
        ],
        "errors": []
    },
    "finance": {
        "source": "yahoo_finance",
        "keyword": "quantum computing",
        "companies_found": 6,
        "tickers": ["IBM", "GOOGL", "MSFT", "IONQ", "RGTI", "QBTS"],
        "total_market_cap": 7894523000000,
        "avg_market_cap": 1315753833333,
        "avg_price_change_1m": 12.5,
        "avg_price_change_6m": 28.7,
        "avg_price_change_2y": 65.3,
        "avg_volatility_1m": 24.5,
        "avg_volatility_6m": 28.3,
        "avg_volume_1m": 15234567,
        "avg_volume_6m": 14856234,
        "volume_trend": "increasing",
        "market_maturity": "developing",
        "investor_sentiment": "positive",
        "investment_momentum": "accelerating",
        "top_companies": [
            {
                "ticker": "GOOGL",
                "name": "Alphabet Inc.",
                "market_cap": 1987456000000,
                "price_change_1m": 8.5,
                "price_change_6m": 22.3,
                "price_change_2y": 45.7,
                "sector": "Technology",
                "industry": "Internet Content & Information"
            },
            {
                "ticker": "IBM",
                "name": "IBM",
                "market_cap": 165234000000,
                "price_change_1m": 5.2,
                "price_change_6m": 15.7,
                "price_change_2y": 28.3,
                "sector": "Technology",
                "industry": "Information Technology Services"
            },
            {
                "ticker": "IONQ",
                "name": "IonQ Inc.",
                "market_cap": 3456000000,
                "price_change_1m": 35.7,
                "price_change_6m": 78.5,
                "price_change_2y": 156.3,
                "sector": "Technology",
                "industry": "Computer Hardware"
            }
        ],
        "errors": []
    }
}


async def main():
    """Run real DeepSeek API test with quantum computing data"""
    print("=" * 80)
    print("DeepSeek Analyzer - Real API Test")
    print("=" * 80)
    print()
    print("Technology Keyword: quantum computing")
    print("Data Sources: 5 (social, papers, patents, news, finance)")
    print("API Calls: 6 (5 per-source analyses + 1 synthesis)")
    print()

    # Load settings and check for API key
    try:
        settings = get_settings()
        if not settings.deepseek_api_key:
            print("ERROR: DEEPSEEK_API_KEY not found in backend/.env")
            print("Please add your DeepSeek API key to the .env file:")
            print("  DEEPSEEK_API_KEY=your-api-key-here")
            return
    except Exception as e:
        print(f"ERROR: Failed to load settings: {e}")
        return

    # Initialize analyzer
    analyzer = DeepSeekAnalyzer(api_key=settings.deepseek_api_key)
    print("[OK] DeepSeek analyzer initialized")
    print()

    # Run analysis
    print("-" * 80)
    print("Starting analysis (this will take ~30-60 seconds)...")
    print("-" * 80)
    print()

    try:
        result = await analyzer.analyze(
            keyword="quantum computing",
            collector_data=QUANTUM_COMPUTING_DATA
        )

        # Display per-source analyses
        print("PER-SOURCE ANALYSES:")
        print("=" * 80)
        print()

        source_labels = {
            "social": "Social Media (Hacker News)",
            "papers": "Academic Research (Semantic Scholar)",
            "patents": "Patents (PatentsView)",
            "news": "News Coverage (GDELT)",
            "finance": "Financial Markets (Yahoo Finance)"
        }

        for source_name, label in source_labels.items():
            if source_name in result["per_source_analyses"]:
                analysis = result["per_source_analyses"][source_name]
                print(f"{label}:")
                print(f"  Phase:      {analysis['phase']}")
                print(f"  Confidence: {analysis['confidence']:.2f}")
                print(f"  Reasoning:  {analysis['reasoning']}")
                print()

        # Display final synthesis
        print("=" * 80)
        print("FINAL SYNTHESIS:")
        print("=" * 80)
        print()
        print(f"Phase:      {result['phase']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Reasoning:  {result['reasoning']}")
        print()

        # Display any errors
        if "errors" in result and result["errors"]:
            print("=" * 80)
            print("WARNINGS:")
            print("=" * 80)
            for error in result["errors"]:
                print(f"  - {error}")
            print()

        print("=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print("ERROR DURING ANALYSIS:")
        print("=" * 80)
        print(f"{type(e).__name__}: {e}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
