"""
Test the exact query that PatentsCollector is using
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_collector_query():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    
    keyword = "quantum computing"
    
    # Exact query from PatentsCollector
    query = {
        "_and": [
            {
                "_or": [
                    {"_text_phrase": {"patent_title": keyword}},
                    {"_text_phrase": {"patent_abstract": keyword}}
                ]
            },
            {"_gte": {"patent_date": "2023-01-01"}},
            {"_lte": {"patent_date": "2024-12-31"}}
        ]
    }
    
    fields = [
        "patent_number",
        "patent_title",
        "patent_date",
        "patent_year",
        "assignees.assignee_organization",
        "assignees.assignee_country",
        "cited_patent_count"
    ]
    
    options = {"size": 100}
    
    headers = {"X-Api-Key": api_key}
    
    print("Testing exact PatentsCollector query...")
    print(f"Query: {json.dumps(query, indent=2)}")
    print("-" * 70)
    
    # Build URL with manual encoding
    q = json.dumps(query)
    f = json.dumps(fields)
    o = json.dumps(options)
    url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Total hits: {data.get('total_hits', 0)}")
                if data.get('patents'):
                    print(f"First patent: {data['patents'][0].get('patent_title', 'N/A')}")
            else:
                print(f"ERROR: {response.text}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_collector_query())
