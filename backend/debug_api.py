"""
Debug script to test PatentsView API query format
"""
import httpx
import json
import asyncio

async def test_api():
    url = "https://search.patentsview.org/api/v1/patent/"
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    
    # Simple test query
    query = {
        "_text_phrase": {
            "patent_title": "quantum computing"
        }
    }
    
    fields = ["patent_number", "patent_title"]
    options = {"size": 10}
    
    headers = {"X-Api-Key": api_key}
    
    print("Testing PatentsView API...")
    print(f"URL: {url}")
    print(f"Query: {json.dumps(query, indent=2)}")
    print(f"Fields: {fields}")
    print(f"Options: {options}")
    print("-" * 70)
    
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
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nSuccess! Found {data.get('total_hits', 0)} patents")
                if data.get('patents'):
                    print(f"First patent: {data['patents'][0].get('patent_title', 'N/A')}")
            else:
                print(f"\nError: {response.status_code}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
