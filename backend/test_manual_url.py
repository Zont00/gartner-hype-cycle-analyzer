"""
Test with manually constructed URL like in documentation
"""
import httpx
import asyncio
from urllib.parse import quote

async def test_manual():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    
    # Manually construct URL like in documentation example
    base_url = "https://search.patentsview.org/api/v1/patent/"
    q = '{"patent_id":"7861317"}'
    f = '["patent_id","patent_title"]'
    o = '{"size":5}'
    
    # Build full URL with proper encoding
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    headers = {"X-Api-Key": api_key}
    
    print("Testing with manually constructed URL...")
    print(f"URL: {url}")
    print("-" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Response: {data}")
            else:
                print(f"ERROR: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_manual())
