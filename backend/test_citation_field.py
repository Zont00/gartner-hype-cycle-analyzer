"""
Test to find correct citation field name
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_fields():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    query = {"patent_id": "7861317"}
    options = {"size": 1}
    headers = {"X-Api-Key": api_key}
    
    # Test 1: Without citation field (baseline)
    fields1 = ["patent_id", "patent_title"]
    q = json.dumps(query)
    f = json.dumps(fields1)
    o = json.dumps(options)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    print("Test 1: Without citation field...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("SUCCESS - baseline works")
    
    # Test 2: With cited_patent_count
    print("\nTest 2: With cited_patent_count...")
    fields2 = ["patent_id", "patent_title", "cited_patent_count"]
    f = json.dumps(fields2)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS! Response: {data.get('patents', [{}])[0]}")
        else:
            print(f"FAIL: {response.text}")
    
    # Test 3: Get full response without field filter to see available fields
    print("\nTest 3: Get full response to see all available fields...")
    url_no_fields = f'{base_url}?q={quote(q)}&o={quote(o)}'
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url_no_fields, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('patents'):
                print("Available fields in response:")
                for key in data['patents'][0].keys():
                    print(f"  - {key}")

if __name__ == "__main__":
    asyncio.run(test_fields())
