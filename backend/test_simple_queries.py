"""
Test progressively more complex queries
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_query(desc, query, fields):
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    options = {"size": 5}
    headers = {"X-Api-Key": api_key}
    
    q = json.dumps(query)
    f = json.dumps(fields)
    o = json.dumps(options)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    print(f"\n{desc}")
    print(f"Query: {json.dumps(query)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Hits: {data.get('total_hits', 0)}")
                return True
            else:
                print(f"FAIL: {response.status_code}")
                return False
        except Exception as e:
            print(f"ERROR: {e}")
            return False

async def main():
    fields = ["patent_number", "patent_title", "patent_date"]
    
    # Test 1: Simple date range only
    await test_query(
        "Test 1: Date range only",
        {
            "_and": [
                {"_gte": {"patent_date": "2023-01-01"}},
                {"_lte": {"patent_date": "2023-12-31"}}
            ]
        },
        fields
    )
    
    # Test 2: Text search with _text_any (simpler than _text_phrase)
    await test_query(
        "Test 2: _text_any on patent_title",
        {"_text_any": {"patent_title": "quantum"}},
        fields
    )
    
    # Test 3: Combine text and date
    await test_query(
        "Test 3: _text_any + date range",
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
