"""
Test different query formats for PatentsView API
"""
import httpx
import json
import asyncio

async def test_query(query_desc, query, fields):
    url = "https://search.patentsview.org/api/v1/patent/"
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    headers = {"X-Api-Key": api_key}
    options = {"size": 5}
    
    print(f"\nTest: {query_desc}")
    print(f"Query: {json.dumps(query)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                url,
                params={
                    "q": json.dumps(query),
                    "f": json.dumps(fields),
                    "o": json.dumps(options)
                },
                headers=headers
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Total hits: {data.get('total_hits', 0)}")
                return True
            else:
                print(f"ERROR: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"Exception: {e}")
            return False

async def main():
    fields = ["patent_number", "patent_title", "patent_date"]
    
    print("=" * 70)
    print("Testing different query formats for PatentsView API")
    print("=" * 70)
    
    # Test 1: Simple patent_id query
    await test_query(
        "Simple patent_id query",
        {"patent_id": "7861317"},
        fields
    )
    
    # Test 2: _text_any with patent_title
    await test_query(
        "_text_any with patent_title",
        {"_text_any": {"patent_title": "quantum"}},
        fields
    )
    
    # Test 3: _text_phrase with patent_title
    await test_query(
        "_text_phrase with patent_title",
        {"_text_phrase": {"patent_title": "quantum computing"}},
        fields
    )
    
    # Test 4: _contains with patent_title
    await test_query(
        "_contains with patent_title",
        {"_contains": {"patent_title": "quantum"}},
        fields
    )
    
    # Test 5: _and with _text_any and date range
    await test_query(
        "_and with _text_any and date",
        {
            "_and": [
                {"_text_any": {"patent_title": "quantum"}},
                {"_gte": {"patent_date": "2020-01-01"}}
            ]
        },
        fields
    )

if __name__ == "__main__":
    asyncio.run(main())
