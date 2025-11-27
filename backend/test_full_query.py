"""
Test full query with text search and date range
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_full():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    
    # Full query with text + dates
    query = {
        "_and": [
            {"_text_any": {"patent_title": "quantum computing"}},
            {"_gte": {"patent_date": "2020-01-01"}},
            {"_lte": {"patent_date": "2023-12-31"}}
        ]
    }
    
    fields = ["patent_id", "patent_title", "patent_date"]
    options = {"size": 10}
    headers = {"X-Api-Key": api_key}
    
    q = json.dumps(query)
    f = json.dumps(fields)
    o = json.dumps(options)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    print("Testing full query with text + date...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Total hits: {data.get('total_hits', 0)}")
                for i, patent in enumerate(data.get('patents', [])[:3], 1):
                    print(f"{i}. {patent.get('patent_title', 'N/A')}")
            else:
                print(f"ERROR: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_full())
