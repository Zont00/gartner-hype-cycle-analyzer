"""
Test different citation field names
"""
import httpx
import asyncio
import json
from urllib.parse import quote

async def test_citation_fields():
    api_key = "StKLeQIH.C2px5FnFVBAfX40GwEoxieEKNOPB5vvD"
    base_url = "https://search.patentsview.org/api/v1/patent/"
    query = {"patent_id": "7861317"}
    options = {"size": 1}
    headers = {"X-Api-Key": api_key}
    
    citation_field_names = [
        "patent_num_times_cited_by_us_patents",
        "num_times_cited_by_us_patents",
        "cited_by_patent_count",
        "patent_citation_count",
        "us_patent_citation"
    ]
    
    for field_name in citation_field_names:
        print(f"\nTesting field: {field_name}")
        fields = ["patent_id", "patent_title", field_name]
        
        q = json.dumps(query)
        f = json.dumps(fields)
        o = json.dumps(options)
        url = f'{base_url}?q={quote(q)}&f={quote(f)}&o={quote(o)}'
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS! Field value: {data.get('patents', [{}])[0].get(field_name, 'N/A')}")
            else:
                print(f"FAIL: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_citation_fields())
