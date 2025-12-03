"""
Compare collector results with and without query expansion.
"""
import asyncio
import json
from app.analyzers.hype_classifier import HypeCycleClassifier
from app.database import get_db

async def test_with_expansion_disabled():
    """Test with query expansion disabled."""
    print("=" * 80)
    print("TEST 1: WITHOUT QUERY EXPANSION")
    print("=" * 80)

    # Temporarily disable expansion by setting niche threshold very high
    classifier = HypeCycleClassifier()
    original_detect = classifier._detect_niche
    classifier._detect_niche = lambda x: False  # Always return False (not niche)

    async for db in get_db():
        try:
            # Clear cache first
            await db.execute("DELETE FROM analyses WHERE keyword = 'plant cell culture'")
            await db.commit()

            result = await classifier.classify("plant cell culture", db)

            print("\nCOLLECTOR RESULTS WITHOUT EXPANSION:")
            print("-" * 80)
            for source, data in result["collector_data"].items():
                if data:
                    print(f"\n{source.upper()}:")
                    if source == "social":
                        print(f"  mentions_30d: {data.get('mentions_30d')}")
                        print(f"  mentions_total: {data.get('mentions_total')}")
                    elif source == "papers":
                        print(f"  publications_2y: {data.get('publications_2y')}")
                        print(f"  publications_total: {data.get('publications_total')}")
                    elif source == "patents":
                        print(f"  patents_2y: {data.get('patents_2y')}")
                        print(f"  patents_total: {data.get('patents_total')}")
                        print(f"  unique_assignees: {data.get('unique_assignees')}")
                    elif source == "news":
                        print(f"  articles_30d: {data.get('articles_30d')}")
                        print(f"  articles_total: {data.get('articles_total')}")
                    elif source == "finance":
                        print(f"  companies_found: {data.get('companies_found')}")
                        print(f"  total_market_cap: {data.get('total_market_cap')}")

            print(f"\nQuery expansion applied: {result['query_expansion_applied']}")
            print(f"Expanded terms: {result['expanded_terms']}")

            # Restore original method
            classifier._detect_niche = original_detect
            return result
        finally:
            await db.close()

async def test_with_expansion_enabled():
    """Test with query expansion enabled."""
    print("\n\n" + "=" * 80)
    print("TEST 2: WITH QUERY EXPANSION")
    print("=" * 80)

    classifier = HypeCycleClassifier()

    async for db in get_db():
        try:
            # Clear cache first
            await db.execute("DELETE FROM analyses WHERE keyword = 'plant cell culture'")
            await db.commit()

            result = await classifier.classify("plant cell culture", db)

            print("\nCOLLECTOR RESULTS WITH EXPANSION:")
            print("-" * 80)
            for source, data in result["collector_data"].items():
                if data:
                    print(f"\n{source.upper()}:")
                    if source == "social":
                        print(f"  mentions_30d: {data.get('mentions_30d')}")
                        print(f"  mentions_total: {data.get('mentions_total')}")
                    elif source == "papers":
                        print(f"  publications_2y: {data.get('publications_2y')}")
                        print(f"  publications_total: {data.get('publications_total')}")
                    elif source == "patents":
                        print(f"  patents_2y: {data.get('patents_2y')}")
                        print(f"  patents_total: {data.get('patents_total')}")
                        print(f"  unique_assignees: {data.get('unique_assignees')}")
                    elif source == "news":
                        print(f"  articles_30d: {data.get('articles_30d')}")
                        print(f"  articles_total: {data.get('articles_total')}")
                    elif source == "finance":
                        print(f"  companies_found: {data.get('companies_found')}")
                        print(f"  total_market_cap: {data.get('total_market_cap')}")

            print(f"\nQuery expansion applied: {result['query_expansion_applied']}")
            print(f"Expanded terms: {result['expanded_terms']}")
            return result
        finally:
            await db.close()

async def compare_results(without, with_exp):
    """Compare the two results."""
    print("\n\n" + "=" * 80)
    print("COMPARISON: WITHOUT vs WITH EXPANSION")
    print("=" * 80)

    for source in ["social", "papers", "patents", "news", "finance"]:
        data_without = without["collector_data"].get(source, {})
        data_with = with_exp["collector_data"].get(source, {})

        if not data_without and not data_with:
            continue

        print(f"\n{source.upper()}:")
        print("-" * 40)

        if source == "social":
            mentions_30d_before = data_without.get('mentions_30d', 0)
            mentions_30d_after = data_with.get('mentions_30d', 0)
            mentions_total_before = data_without.get('mentions_total', 0)
            mentions_total_after = data_with.get('mentions_total', 0)

            print(f"  mentions_30d:    {mentions_30d_before} ->{mentions_30d_after} ", end="")
            if mentions_30d_after > mentions_30d_before:
                increase = ((mentions_30d_after - mentions_30d_before) / max(mentions_30d_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

            print(f"  mentions_total:  {mentions_total_before} ->{mentions_total_after} ", end="")
            if mentions_total_after > mentions_total_before:
                increase = ((mentions_total_after - mentions_total_before) / max(mentions_total_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

        elif source == "papers":
            pubs_2y_before = data_without.get('publications_2y', 0)
            pubs_2y_after = data_with.get('publications_2y', 0)
            pubs_total_before = data_without.get('publications_total', 0)
            pubs_total_after = data_with.get('publications_total', 0)

            print(f"  publications_2y:    {pubs_2y_before} ->{pubs_2y_after} ", end="")
            if pubs_2y_after > pubs_2y_before:
                increase = ((pubs_2y_after - pubs_2y_before) / max(pubs_2y_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

            print(f"  publications_total: {pubs_total_before} ->{pubs_total_after} ", end="")
            if pubs_total_after > pubs_total_before:
                increase = ((pubs_total_after - pubs_total_before) / max(pubs_total_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

        elif source == "patents":
            patents_2y_before = data_without.get('patents_2y', 0)
            patents_2y_after = data_with.get('patents_2y', 0)
            patents_total_before = data_without.get('patents_total', 0)
            patents_total_after = data_with.get('patents_total', 0)
            assignees_before = data_without.get('unique_assignees', 0)
            assignees_after = data_with.get('unique_assignees', 0)

            print(f"  patents_2y:        {patents_2y_before} ->{patents_2y_after} ", end="")
            if patents_2y_after > patents_2y_before:
                increase = ((patents_2y_after - patents_2y_before) / max(patents_2y_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

            print(f"  patents_total:     {patents_total_before} ->{patents_total_after} ", end="")
            if patents_total_after > patents_total_before:
                increase = ((patents_total_after - patents_total_before) / max(patents_total_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

            print(f"  unique_assignees:  {assignees_before} ->{assignees_after} ", end="")
            if assignees_after > assignees_before:
                increase = ((assignees_after - assignees_before) / max(assignees_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

        elif source == "news":
            articles_30d_before = data_without.get('articles_30d', 0)
            articles_30d_after = data_with.get('articles_30d', 0)
            articles_total_before = data_without.get('articles_total', 0)
            articles_total_after = data_with.get('articles_total', 0)

            print(f"  articles_30d:   {articles_30d_before} ->{articles_30d_after} ", end="")
            if articles_30d_after > articles_30d_before:
                increase = ((articles_30d_after - articles_30d_before) / max(articles_30d_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

            print(f"  articles_total: {articles_total_before} ->{articles_total_after} ", end="")
            if articles_total_after > articles_total_before:
                increase = ((articles_total_after - articles_total_before) / max(articles_total_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

        elif source == "finance":
            companies_before = data_without.get('companies_found', 0)
            companies_after = data_with.get('companies_found', 0)

            print(f"  companies_found: {companies_before} ->{companies_after} ", end="")
            if companies_after > companies_before:
                increase = ((companies_after - companies_before) / max(companies_before, 1)) * 100
                print(f"(+{increase:.0f}%)")
            else:
                print("(no change)")

async def main():
    """Run comparison tests."""
    without_expansion = await test_with_expansion_disabled()
    with_expansion = await test_with_expansion_enabled()
    await compare_results(without_expansion, with_expansion)

if __name__ == "__main__":
    asyncio.run(main())
