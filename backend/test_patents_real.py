"""
Quick test script to verify PatentsCollector with real API
"""
import asyncio
import json
from app.collectors.patents import PatentsCollector


async def main():
    print("Testing PatentsCollector with real PatentsView API...")
    print("=" * 70)

    collector = PatentsCollector()

    # Test with a well-known technology
    keyword = "quantum computing"
    print(f"\nSearching for: '{keyword}'")
    print("-" * 70)

    result = await collector.collect(keyword)

    # Pretty print key metrics
    print(f"\n[OK] Source: {result['source']}")
    print(f"[OK] Keyword: {result['keyword']}")
    print(f"[OK] Collected at: {result['collected_at']}")
    print()

    print("PATENT COUNTS:")
    print(f"  - Last 2 years:  {result['patents_2y']}")
    print(f"  - Prior 5 years: {result['patents_5y']}")
    print(f"  - Prior 10 years: {result['patents_10y']}")
    print(f"  - TOTAL:         {result['patents_total']}")
    print()

    print("ASSIGNEE METRICS:")
    print(f"  - Unique assignees: {result['unique_assignees']}")
    print(f"  - Top 5 assignees:")
    for assignee in result['top_assignees'][:5]:
        print(f"    - {assignee['name']}: {assignee['patent_count']} patents")
    print()

    print("GEOGRAPHIC DISTRIBUTION:")
    print(f"  - Countries represented: {result['geographic_diversity']}")
    print(f"  - Top countries:")
    for country, count in sorted(result['countries'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    - {country}: {count} patents")
    print()

    print("CITATION METRICS:")
    print(f"  - Avg citations (2y):  {result['avg_citations_2y']}")
    print(f"  - Avg citations (5y):  {result['avg_citations_5y']}")
    print()

    print("DERIVED INSIGHTS:")
    print(f"  - Filing velocity:        {result['filing_velocity']:.3f}")
    print(f"  - Assignee concentration: {result['assignee_concentration']}")
    print(f"  - Geographic reach:       {result['geographic_reach']}")
    print(f"  - Patent maturity:        {result['patent_maturity']}")
    print(f"  - Patent momentum:        {result['patent_momentum']}")
    print(f"  - Patent trend:           {result['patent_trend']}")
    print()

    if result['top_patents']:
        print("TOP PATENTS (by citations):")
        for i, patent in enumerate(result['top_patents'][:3], 1):
            print(f"  {i}. {patent['title'][:60]}...")
            print(f"     Patent: {patent['patent_number']} | Assignee: {patent['assignee']}")
            print(f"     Date: {patent['date']} | Citations: {patent['citations']}")
        print()

    if result['errors']:
        print("[!] ERRORS ENCOUNTERED:")
        for error in result['errors']:
            print(f"  - {error}")
        print()
    else:
        print("[OK] No errors - all API calls successful!")
        print()

    # Verify JSON serialization
    try:
        json_str = json.dumps(result, indent=2)
        print(f"[OK] JSON serialization successful ({len(json_str)} bytes)")
        print()
    except Exception as e:
        print(f"[ERROR] JSON serialization failed: {e}")
        print()

    print("=" * 70)
    print("Test complete!\n")

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
