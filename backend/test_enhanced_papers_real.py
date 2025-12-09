"""
Real-world test of enhanced PapersCollector.
Demonstrates 10-year analysis, paper type distribution, top authors, and enhanced maturity.
"""
import asyncio
import json
from app.collectors.papers import PapersCollector


async def test_enhanced_papers():
    """Test enhanced PapersCollector with real API call"""

    print("\n" + "="*80)
    print("ENHANCED PAPERS COLLECTOR - REAL API TEST")
    print("="*80)

    collector = PapersCollector()
    keyword = "quantum computing"

    print(f"\nTesting keyword: {keyword}")
    print("Making real API call to Semantic Scholar...")

    try:
        result = await collector.collect(keyword)

        print("\n" + "="*80)
        print("TEMPORAL ANALYSIS (10-YEAR HORIZON)")
        print("="*80)
        print(f"Publications (2y):  {result['publications_2y']:,}")
        print(f"Publications (5y):  {result['publications_5y']:,}")
        print(f"Publications (10y): {result['publications_10y']:,}")
        print(f"Total Publications: {result['publications_total']:,}")

        print(f"\nAvg Citations (2y):  {result['avg_citations_2y']:.2f}")
        print(f"Avg Citations (5y):  {result['avg_citations_5y']:.2f}")
        print(f"Avg Citations (10y): {result['avg_citations_10y']:.2f}")
        print(f"Citation Velocity:   {result['citation_velocity']:.3f}")

        print("\n" + "="*80)
        print("PAPER TYPE DISTRIBUTION")
        print("="*80)

        type_dist = result['paper_type_distribution']
        print(f"Papers with type info: {type_dist['papers_with_type_info']:,} / {result['publications_total']:,}")
        print(f"Coverage: {(type_dist['papers_with_type_info'] / max(result['publications_total'], 1) * 100):.1f}%")

        print("\nType Counts:")
        for type_name, count in type_dist['type_counts'].items():
            print(f"  {type_name:15} {count:5,}")

        print("\nType Percentages:")
        for type_key, percentage in sorted(type_dist['type_percentages'].items(),
                                          key=lambda x: x[1], reverse=True):
            type_name = type_key.replace('_percentage', '').title()
            print(f"  {type_name:15} {percentage:5.1f}%")

        print("\n" + "="*80)
        print("TOP AUTHORS (BY PUBLICATION COUNT)")
        print("="*80)

        if result['top_authors']:
            for i, author in enumerate(result['top_authors'][:10], 1):
                print(f"{i:2}. {author['name']:40} ({author['publication_count']:3} papers)")
        else:
            print("No author data available")

        print("\n" + "="*80)
        print("ENHANCED RESEARCH MATURITY CLASSIFICATION")
        print("="*80)
        print(f"Maturity Level: {result['research_maturity'].upper()}")
        print(f"\nReasoning:")
        print(f"  {result['research_maturity_reasoning']}")

        print("\n" + "="*80)
        print("OTHER DERIVED INSIGHTS")
        print("="*80)
        print(f"Research Momentum: {result['research_momentum']}")
        print(f"Research Trend:    {result['research_trend']}")
        print(f"Research Breadth:  {result['research_breadth']}")
        print(f"Author Diversity:  {result['author_diversity']:,} unique authors")
        print(f"Venue Diversity:   {result['venue_diversity']:,} unique venues")

        print("\n" + "="*80)
        print("TOP PAPERS (BY CITATION COUNT)")
        print("="*80)

        for i, paper in enumerate(result['top_papers'][:5], 1):
            print(f"\n{i}. {paper['title']}")
            print(f"   Year: {paper.get('year', 'N/A')}, Citations: {paper['citations']}, "
                  f"Influential: {paper.get('influential_citations', 0)}")
            print(f"   Venue: {paper.get('venue', 'N/A')}")

        print("\n" + "="*80)
        print("ERROR TRACKING")
        print("="*80)
        if result['errors']:
            print("Errors encountered:")
            for error in result['errors']:
                print(f"  - {error}")
        else:
            print("No errors - all data collected successfully!")

        print("\n" + "="*80)
        print("COMPARISON WITH OLD VERSION")
        print("="*80)
        print("\nOLD VERSION PROVIDED:")
        print("  - 2 time periods (2y, 5y)")
        print("  - Simple quantitative maturity (publications + citations only)")
        print("  - No paper type analysis")
        print("  - No author aggregation")
        print("  - Basic reasoning")

        print("\nNEW VERSION PROVIDES:")
        print("  - 3 time periods (2y, 5y, 10y) - longer trend analysis")
        print("  - Type-aware maturity (considers review/journal/conference distribution)")
        print(f"  - Paper type distribution ({type_dist['papers_with_type_info']:,} papers analyzed)")
        print(f"  - Top {len(result['top_authors'])} authors identified")
        print("  - Detailed maturity reasoning with type-based justification")

        print("\n" + "="*80)
        print("FULL JSON OUTPUT (for debugging)")
        print("="*80)
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_enhanced_papers())
