"""
Test POST request to PatentsView API
"""
import httpx
import json
import asyncio

async def test_post():
    url = "https://search.patentsview.org/api/v1/patent/"
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    
    # Using POST with JSON body
    body = {
        "q": {"patent_id": "7861317"},
        "f": ["patent_number", "patent_title"],
        "o": {"size": 5}
    }
    
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    print("Testing POST request...")
    print(f"Body: {json.dumps(body, indent=2)}")
    print("-" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                url,
                json=body,
                headers=headers
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nSUCCESS! Total: {data.get('total_hits', 0)}")
                if data.get('patents'):
                    print(f"Patent: {data['patents'][0]}")
            
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_post())
