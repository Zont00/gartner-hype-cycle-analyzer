"""
Test with correct field names
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_with_correct_fields():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    
    # Use patent_id instead of patent_number (like in working example)
    query = {"_gte": {"patent_date": "2023-01-01"}}
    fields = ["patent_id", "patent_title", "patent_date"]  # patent_id not patent_number
    options = {"size": 5}
    headers = {"X-Api-Key": api_key}
    
    q = json.dumps(query)
    f = json.dumps(fields)
    o = json.dumps(options)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    print("Testing with patent_id field...")
    print(f"Query: {json.dumps(query)}")
    print(f"Fields: {fields}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Total hits: {data.get('total_hits', 0)}")
                if data.get('patents'):
                    print(f"First patent: {data['patents'][0]}")
            else:
                print(f"ERROR: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_with_correct_fields())
