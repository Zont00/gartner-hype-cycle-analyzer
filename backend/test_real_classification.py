"""
Real-world test script for HypeCycleClassifier.
Tests the full classification pipeline with real API calls.
"""
import asyncio
import sys
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, '.')

from app.analyzers.hype_classifier import HypeCycleClassifier
from app.database import init_db, get_db
from app.config import get_settings


async def test_real_classification(keyword: str):
    """
    Run a real classification with all collectors and DeepSeek.

    Args:
        keyword: Technology keyword to analyze
    """
    print("=" * 80)
    print(f"GARTNER HYPE CYCLE ANALYZER - REAL CLASSIFICATION TEST")
    print("=" * 80)
    print(f"\nKeyword: {keyword}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("\n" + "-" * 80)

    # Check settings
    settings = get_settings()
    print("\n[1/4] Checking API Keys...")
    print(f"  [OK] DeepSeek API Key: {'*' * 20}{settings.deepseek_api_key[-4:] if settings.deepseek_api_key else 'MISSING'}")
    print(f"  [*] Semantic Scholar: {'Configured' if settings.semantic_scholar_api_key else 'Not configured (optional)'}")
    print(f"  [*] PatentsView: {'Configured' if settings.patentsview_api_key else 'Not configured (optional)'}")

    if not settings.deepseek_api_key:
        print("\n[ERROR] DEEPSEEK_API_KEY is required!")
        print("   Set it in backend/.env file")
        return

    # Initialize database
    print("\n[2/4] Initializing Database...")
    await init_db()
    print("  [OK] Database schema ready")

    # Create classifier
    print("\n[3/4] Running Classification Pipeline...")
    classifier = HypeCycleClassifier()

    # Get database connection
    async for db in get_db():
        try:
            print("  > Checking cache...")
            print("  > Executing 5 collectors in parallel...")
            print("     * SocialCollector (Hacker News)")
            print("     * PapersCollector (Semantic Scholar)")
            print("     * PatentsCollector (PatentsView)")
            print("     * NewsCollector (GDELT)")
            print("     * FinanceCollector (Yahoo Finance + DeepSeek)")
            print("  > Running DeepSeek analysis (6 LLM calls)...")
            print("     * Per-source analysis: 5 calls")
            print("     * Final synthesis: 1 call")
            print("  > Persisting to database...")

            result = await classifier.classify(keyword, db)

            print("\n[4/4] Classification Complete!")
            print("\n" + "=" * 80)
            print("RESULTS")
            print("=" * 80)

            # Main classification
            print(f"\n[FINAL CLASSIFICATION]")
            print(f"   Phase: {result['phase'].upper()}")
            print(f"   Confidence: {result['confidence']:.2%}")
            print(f"   Cache Hit: {'Yes' if result['cache_hit'] else 'No'}")
            print(f"   Collectors Succeeded: {result['collectors_succeeded']}/5")
            print(f"   Partial Data: {'Yes' if result['partial_data'] else 'No'}")

            # Reasoning
            print(f"\n[REASONING]")
            print(f"   {result['reasoning']}")

            # Per-source analyses
            print(f"\n[PER-SOURCE ANALYSES]")
            for source, analysis in result.get('per_source_analyses', {}).items():
                status = "[OK]" if result['collector_data'].get(source) else "[FAIL]"
                print(f"\n   {status} {source.upper()}")
                if analysis:
                    print(f"      Phase: {analysis['phase']}")
                    print(f"      Confidence: {analysis['confidence']:.2%}")
                    print(f"      Reasoning: {analysis['reasoning'][:100]}...")

            # Collector data summary
            print(f"\n[COLLECTOR DATA SUMMARY]")
            for source, data in result['collector_data'].items():
                if data:
                    print(f"\n   [OK] {source.upper()}")
                    # Show key metrics
                    if source == "social":
                        print(f"      Mentions (30d): {data.get('mentions_30d', 'N/A')}")
                        print(f"      Sentiment: {data.get('sentiment', 'N/A')}")
                        print(f"      Growth Trend: {data.get('growth_trend', 'N/A')}")
                    elif source == "papers":
                        print(f"      Publications (2y): {data.get('publications_2y', 'N/A')}")
                        print(f"      Citation Velocity: {data.get('citation_velocity', 'N/A')}")
                        print(f"      Research Maturity: {data.get('research_maturity', 'N/A')}")
                    elif source == "patents":
                        print(f"      Patents (2y): {data.get('patents_2y', 'N/A')}")
                        print(f"      Filing Velocity: {data.get('filing_velocity', 'N/A')}")
                        print(f"      Patent Maturity: {data.get('patent_maturity', 'N/A')}")
                    elif source == "news":
                        print(f"      Articles (30d): {data.get('articles_30d', 'N/A')}")
                        print(f"      Avg Tone: {data.get('avg_tone', 'N/A')}")
                        print(f"      Media Attention: {data.get('media_attention', 'N/A')}")
                    elif source == "finance":
                        print(f"      Companies Found: {data.get('companies_found', 'N/A')}")
                        print(f"      Avg Market Cap: ${data.get('avg_market_cap', 0):,.0f}")
                        print(f"      Market Maturity: {data.get('market_maturity', 'N/A')}")
                else:
                    print(f"\n   [FAIL] {source.upper()} - NO DATA")

            # Errors
            if result['errors']:
                print(f"\n[ERRORS] ({len(result['errors'])})")
                for error in result['errors']:
                    print(f"   * {error}")
            else:
                print(f"\n[NO ERRORS]")

            # Metadata
            print(f"\n[METADATA]")
            print(f"   Timestamp: {result['timestamp']}")
            print(f"   Expires At: {result['expires_at']}")

            # Save full result to JSON file
            output_file = f"classification_result_{keyword.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] Full result saved to: {output_file}")

            print("\n" + "=" * 80)
            print("TEST COMPLETE")
            print("=" * 80)

        except Exception as e:
            print(f"\n[FAILED] CLASSIFICATION FAILED!")
            print(f"   Error: {str(e)}")
            print(f"   Type: {type(e).__name__}")
            import traceback
            print("\n" + traceback.format_exc())

        break  # Exit after first iteration of async generator


if __name__ == "__main__":
    # Get keyword from command line or use default
    if len(sys.argv) > 1:
        keyword = " ".join(sys.argv[1:])
    else:
        keyword = "quantum computing"

    # Run the test
    asyncio.run(test_real_classification(keyword))
