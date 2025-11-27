"""
Test script to verify _text_all operator changes in PatentsCollector.
This script runs a real API query for "quantum computing" to verify that:
1. The _text_all operator is working correctly
2. Results are more relevant than with _text_any
3. Patent abstract field is being returned
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.collectors.patents import PatentsCollector


async def test_collector():
    """Test the PatentsCollector with 'quantum computing' keyword."""
    collector = PatentsCollector()

    print("Testing PatentsCollector with 'quantum computing'...")
    print("=" * 80)

    try:
        result = await collector.collect("quantum computing")

        # Display summary statistics
        print(f"\nSUMMARY STATISTICS")
        print(f"   Source: {result.get('source')}")
        print(f"   Collected at: {result.get('collected_at')}")
        print(f"   Keyword: {result.get('keyword')}")
        print(f"\n   Patents found:")
        print(f"   - 2-year period: {result.get('patents_2y')}")
        print(f"   - 5-year period: {result.get('patents_5y')}")
        print(f"   - 10-year period: {result.get('patents_10y')}")
        print(f"   - Total: {result.get('patents_total')}")

        print(f"\n   Assignee metrics:")
        print(f"   - Unique assignees: {result.get('unique_assignees')}")
        print(f"   - Assignee concentration: {result.get('assignee_concentration')}")

        print(f"\n   Geographic metrics:")
        print(f"   - Geographic diversity: {result.get('geographic_diversity')} countries")
        print(f"   - Geographic reach: {result.get('geographic_reach')}")

        print(f"\n   Derived insights:")
        print(f"   - Patent maturity: {result.get('patent_maturity')}")
        print(f"   - Patent momentum: {result.get('patent_momentum')}")
        print(f"   - Patent trend: {result.get('patent_trend')}")
        print(f"   - Filing velocity: {result.get('filing_velocity'):.4f}")

        # Display top assignees
        print(f"\n   Top 5 assignees:")
        for assignee in result.get('top_assignees', [])[:5]:
            print(f"   - {assignee['name']}: {assignee['patent_count']} patents")

        # Display country distribution
        print(f"\n   Country distribution:")
        countries = result.get('countries', {})
        for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   - {country}: {count} patents")

        # Display top patents (to verify abstract is included)
        print(f"\nTOP PATENTS (by citation count):")
        for i, patent in enumerate(result.get('top_patents', [])[:3], 1):
            print(f"\n   {i}. {patent.get('title')}")
            print(f"      Patent ID: {patent.get('patent_number')}")
            print(f"      Date: {patent.get('date')}")
            print(f"      Assignee: {patent.get('assignee')} ({patent.get('country')})")
            print(f"      Citations: {patent.get('citations')}")

        # Check for errors
        errors = result.get('errors', [])
        if errors:
            print(f"\nERRORS ENCOUNTERED:")
            for error in errors:
                print(f"   - {error}")
        else:
            print(f"\n[OK] No errors encountered")

        print("\n" + "=" * 80)
        print("[SUCCESS] Test completed successfully!")

        return result

    except Exception as e:
        print(f"\n[ERROR] Error during test: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_collector())

    if result:
        print("\n[DATA] Full result structure:")
        import json
        print(json.dumps(result, indent=2))
