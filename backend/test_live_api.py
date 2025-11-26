"""
Manual test script for SocialCollector with real Hacker News API.
Run this to verify the collector works with live data.
"""
import asyncio
import json
from app.collectors.social import SocialCollector


async def test_live_api():
    """Test SocialCollector with real API call"""
    collector = SocialCollector()

    # Test with a well-known technology keyword
    test_keywords = [
        "rust programming",
        "kubernetes",
        "chatgpt"
    ]

    print("=" * 80)
    print("TESTING SOCIAL COLLECTOR WITH LIVE HACKER NEWS API")
    print("=" * 80)

    for keyword in test_keywords:
        print(f"\n{'=' * 80}")
        print(f"Testing keyword: '{keyword}'")
        print("=" * 80)

        try:
            result = await collector.collect(keyword)

            # Print formatted results
            print(f"\nRESULTS FOR '{keyword}':")
            print(f"  Source: {result['source']}")
            print(f"  Collected at: {result['collected_at']}")
            print(f"\n  MENTION COUNTS:")
            print(f"    Last 30 days: {result['mentions_30d']}")
            print(f"    Last 6 months: {result['mentions_6m']}")
            print(f"    Last 1 year: {result['mentions_1y']}")
            print(f"    Total: {result['mentions_total']}")

            print(f"\n  ENGAGEMENT METRICS:")
            print(f"    Avg points (30d): {result['avg_points_30d']}")
            print(f"    Avg comments (30d): {result['avg_comments_30d']}")
            print(f"    Avg points (6m): {result['avg_points_6m']}")
            print(f"    Avg comments (6m): {result['avg_comments_6m']}")

            print(f"\n  DERIVED INSIGHTS:")
            print(f"    Sentiment: {result['sentiment']:.3f} ({'positive' if result['sentiment'] > 0 else 'negative' if result['sentiment'] < 0 else 'neutral'})")
            print(f"    Recency: {result['recency']}")
            print(f"    Growth trend: {result['growth_trend']}")
            print(f"    Momentum: {result['momentum']}")

            if result['top_stories']:
                print(f"\n  TOP STORIES (Last 30 days):")
                for i, story in enumerate(result['top_stories'][:3], 1):
                    print(f"    {i}. {story['title'][:60]}...")
                    print(f"       Points: {story['points']}, Comments: {story['comments']}, Age: {story['age_days']} days")

            if result['errors']:
                print(f"\n  ERRORS: {result['errors']}")

            # Verify JSON serializable
            json_str = json.dumps(result, indent=2)
            print(f"\n  [OK] JSON serializable: {len(json_str)} characters")

        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 80}")
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_live_api())
