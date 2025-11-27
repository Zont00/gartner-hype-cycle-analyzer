"""
Manual test script for NewsCollector with real GDELT API.
This script makes actual API calls to verify the collector works correctly.
"""
import asyncio
import json
from app.collectors.news import NewsCollector


async def test_news_collector():
    """Test NewsCollector with real GDELT API call"""

    collector = NewsCollector()

    # Test with a well-known technology keyword
    keyword = "quantum computing"

    print(f"=" * 80)
    print(f"Testing NewsCollector with keyword: '{keyword}'")
    print(f"=" * 80)
    print()

    try:
        print("Making API calls to GDELT... (this may take 10-30 seconds)")
        result = await collector.collect(keyword)

        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        # Basic info
        print(f"\n[*] Source: {result['source']}")
        print(f"[*] Keyword: {result['keyword']}")
        print(f"[*] Collected at: {result['collected_at']}")

        # Article counts
        print(f"\n[ARTICLE COUNTS]")
        print(f"  - Last 30 days: {result['articles_30d']}")
        print(f"  - 3 months (excluding last 30d): {result['articles_3m']}")
        print(f"  - 1 year (excluding last 3m): {result['articles_1y']}")
        print(f"  - Total: {result['articles_total']}")

        # Geographic distribution
        print(f"\n[GEOGRAPHIC DISTRIBUTION]")
        print(f"  - Unique countries: {result['geographic_diversity']}")
        if result['source_countries']:
            print(f"  - Top 5 countries:")
            sorted_countries = sorted(
                result['source_countries'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            for country, count in sorted_countries:
                print(f"    * {country}: {count} articles")

        # Media diversity
        print(f"\n[MEDIA DIVERSITY]")
        print(f"  - Unique domains: {result['unique_domains']}")
        if result['top_domains']:
            print(f"  - Top 5 domains:")
            for domain_info in result['top_domains']:
                print(f"    * {domain_info['domain']}: {domain_info['count']} articles")

        # Sentiment/tone
        print(f"\n[SENTIMENT ANALYSIS]")
        print(f"  - Average tone: {result['avg_tone']} (-1.0 = negative, +1.0 = positive)")
        print(f"  - Distribution:")
        print(f"    * Positive: {result['tone_distribution']['positive']} articles")
        print(f"    * Neutral: {result['tone_distribution']['neutral']} articles")
        print(f"    * Negative: {result['tone_distribution']['negative']} articles")

        # Volume metrics
        print(f"\n[VOLUME INTENSITY]")
        print(f"  - Last 30 days: {result['volume_intensity_30d']}")
        print(f"  - 3 months: {result['volume_intensity_3m']}")
        print(f"  - 1 year: {result['volume_intensity_1y']}")

        # Derived insights
        print(f"\n[DERIVED INSIGHTS]")
        print(f"  - Media attention: {result['media_attention']}")
        print(f"  - Coverage trend: {result['coverage_trend']}")
        print(f"  - Sentiment trend: {result['sentiment_trend']}")
        print(f"  - Mainstream adoption: {result['mainstream_adoption']}")

        # Top articles
        print(f"\n[TOP RECENT ARTICLES]")
        if result['top_articles']:
            for i, article in enumerate(result['top_articles'][:5], 1):
                print(f"\n  {i}. {article['title']}")
                print(f"     URL: {article['url']}")
                print(f"     Domain: {article['domain']}")
                print(f"     Country: {article['country']}")
                print(f"     Date: {article['date']}")
        else:
            print("  No articles found")

        # Errors
        if result['errors']:
            print(f"\n[WARNING] Errors encountered:")
            for error in result['errors']:
                print(f"  - {error}")
        else:
            print(f"\n[OK] No errors encountered")

        # JSON serialization test
        print(f"\n[JSON SERIALIZATION TEST]")
        try:
            json_str = json.dumps(result, indent=2)
            print(f"  [OK] Result is JSON serializable ({len(json_str)} bytes)")
        except Exception as e:
            print(f"  [ERROR] JSON serialization failed: {e}")

        print("\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

        return result

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\n[*] Starting NewsCollector Real API Test\n")
    result = asyncio.run(test_news_collector())

    if result:
        print("\n[SUCCESS] Test completed successfully!")
        print(f"\nTo test with a different keyword, edit this script and change the 'keyword' variable.")
    else:
        print("\n[FAILED] Test failed - see error details above")
