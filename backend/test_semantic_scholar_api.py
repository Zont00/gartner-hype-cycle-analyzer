"""
Validation script to test Semantic Scholar API responses.
Verifies that publicationTypes and author affiliations are actually available.
"""
import asyncio
import httpx
import json
from app.config import get_settings


async def test_semantic_scholar_fields():
    """Test what fields Semantic Scholar actually returns"""

    settings = get_settings()
    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"

    # Test with a well-known technology keyword
    keyword = "quantum computing"

    # Request both basic and extended fields
    fields = "paperId,title,year,citationCount,influentialCitationCount,authors,venue,publicationTypes"

    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
        print(f"[+] Using API key: {settings.semantic_scholar_api_key[:10]}...")
    else:
        print("[!] No API key configured - using public rate limits")

    print(f"\n{'='*70}")
    print(f"Testing Semantic Scholar API")
    print(f"{'='*70}")
    print(f"Keyword: {keyword}")
    print(f"Fields requested: {fields}")
    print(f"Year filter: 2023-2024 (recent 2-year period)")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                API_URL,
                params={
                    "query": f'"{keyword}"',
                    "year": "2023-2024",
                    "fields": fields,
                    "limit": 5  # Just get a few papers for testing
                },
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            print(f"\n{'='*70}")
            print(f"API Response Summary")
            print(f"{'='*70}")
            print(f"Total papers found: {data.get('total', 0)}")
            print(f"Papers returned: {len(data.get('data', []))}")

            if data.get('data'):
                print(f"\n{'='*70}")
                print(f"Field Availability Analysis")
                print(f"{'='*70}")

                papers = data['data']

                # Check publicationTypes availability
                papers_with_types = 0
                type_examples = []
                for paper in papers:
                    if paper.get('publicationTypes'):
                        papers_with_types += 1
                        type_examples.append(paper.get('publicationTypes'))

                print(f"\n[publicationTypes field]")
                print(f"  Papers with types: {papers_with_types}/{len(papers)} ({papers_with_types/len(papers)*100:.1f}%)")
                if type_examples:
                    print(f"  Example types found: {set(sum(type_examples, []))}")
                else:
                    print(f"  [!] WARNING: No papers have publicationTypes!")

                # Check author affiliations availability
                papers_with_affiliations = 0
                affiliation_examples = []
                for paper in papers:
                    for author in paper.get('authors', []):
                        if author.get('affiliations'):
                            papers_with_affiliations += 1
                            affiliation_examples.extend(author.get('affiliations', []))
                            break  # Count each paper once

                print(f"\n[author affiliations field]")
                print(f"  Papers with affiliations: {papers_with_affiliations}/{len(papers)} ({papers_with_affiliations/len(papers)*100:.1f}%)")
                if affiliation_examples:
                    print(f"  Example affiliations: {affiliation_examples[:3]}")
                else:
                    print(f"  [!] WARNING: No author affiliations found in basic response!")
                    print(f"  Note: Affiliations may require extended author queries")

                # Display first paper structure
                print(f"\n{'='*70}")
                print(f"Example Paper Structure (First Result)")
                print(f"{'='*70}")
                print(json.dumps(papers[0], indent=2))

                # Test extended author fields
                print(f"\n{'='*70}")
                print(f"Testing Extended Author Fields")
                print(f"{'='*70}")

                first_paper = papers[0]
                if first_paper.get('authors'):
                    first_author = first_paper['authors'][0]
                    author_id = first_author.get('authorId')

                    if author_id:
                        print(f"Querying detailed author info for: {first_author.get('name')}")
                        author_url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"

                        author_response = await client.get(
                            author_url,
                            params={"fields": "name,affiliations,homepage,paperCount"},
                            headers=headers
                        )

                        if author_response.status_code == 200:
                            author_data = author_response.json()
                            print(f"\n[+] Author details retrieved:")
                            print(json.dumps(author_data, indent=2))

                            if author_data.get('affiliations'):
                                print(f"\n[+] SUCCESS: Affiliations ARE available via author endpoint!")
                            else:
                                print(f"\n[!] No affiliations in author endpoint either")
                        else:
                            print(f"\n[-] Author endpoint returned {author_response.status_code}")

            else:
                print("\n[-] No papers returned in response")

            # Final recommendations
            print(f"\n{'='*70}")
            print(f"Recommendations")
            print(f"{'='*70}")

            if papers_with_types == 0:
                print("[!] publicationTypes field is NOT available in bulk search endpoint")
                print("  -> Consider using individual paper endpoint for type data")
                print("  -> Or proceed without type distribution (graceful degradation)")
            else:
                print("[+] publicationTypes field is available - implementation will work!")

            if papers_with_affiliations == 0:
                print("\n[!] Author affiliations are NOT in bulk search response")
                print("  -> Would require individual author API calls (expensive)")
                print("  -> Recommend accepting empty top_institutions list")
                print("  -> Implementation already handles this gracefully")
            else:
                print("\n[+] Author affiliations available - institution tracking will work!")

    except httpx.HTTPStatusError as e:
        print(f"\n[-] HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text[:500]}")
    except Exception as e:
        print(f"\n[-] Error: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_semantic_scholar_fields())
