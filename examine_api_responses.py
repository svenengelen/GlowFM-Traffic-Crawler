#!/usr/bin/env python3
import requests
import json

def examine_anwb_api_responses():
    """Examine actual ANWB API responses to understand data structure"""
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://anwb.nl/verkeer/filelijst',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # First get the main page to establish session
    main_response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
    
    # Try the API endpoints that are working
    api_endpoints = [
        "https://site-production.anwb.bloomreach.cloud/verkeer/resourceapi/filelijst?_hn:type=component-rendering&_hn:ref=p1&preflight=false",
        "https://site-production.anwb.bloomreach.cloud/verkeer/resourceapi/filelijst"
    ]
    
    for i, endpoint in enumerate(api_endpoints):
        try:
            print(f"\n=== EXAMINING API ENDPOINT {i+1}: {endpoint} ===")
            response = session.get(endpoint, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Status: SUCCESS - Got JSON response")
                    print(f"Response type: {type(data)}")
                    
                    if isinstance(data, dict):
                        print(f"Top-level keys: {list(data.keys())}")
                        
                        # Save full response for detailed analysis
                        with open(f'/tmp/anwb_api_response_{i+1}.json', 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"Saved full response to /tmp/anwb_api_response_{i+1}.json")
                        
                        # Look for traffic-related data
                        def find_traffic_data(obj, path="", max_depth=5):
                            if max_depth <= 0:
                                return
                                
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    new_path = f"{path}.{key}" if path else key
                                    
                                    # Check if this might be traffic data
                                    if any(term in key.lower() for term in ['traffic', 'file', 'jam', 'road', 'highway', 'a67', 'incident']):
                                        print(f"Found potential traffic key: {new_path}")
                                        print(f"  Type: {type(value)}")
                                        if isinstance(value, list):
                                            print(f"  List length: {len(value)}")
                                            if value:
                                                print(f"  First item: {value[0]}")
                                        elif isinstance(value, dict):
                                            print(f"  Dict keys: {list(value.keys())}")
                                        elif isinstance(value, str) and len(value) < 200:
                                            print(f"  Value: {value}")
                                    
                                    # Recursively search
                                    if isinstance(value, (dict, list)):
                                        find_traffic_data(value, new_path, max_depth - 1)
                                        
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    if i > 10:  # Limit to first 10 items
                                        break
                                    find_traffic_data(item, f"{path}[{i}]", max_depth - 1)
                        
                        find_traffic_data(data)
                        
                        # Look for A67 specifically
                        response_text = response.text.lower()
                        if 'a67' in response_text:
                            print(f"\n*** FOUND A67 REFERENCE IN RESPONSE! ***")
                            # Extract context around A67
                            import re
                            a67_contexts = re.findall(r'.{0,200}a67.{0,200}', response_text, re.IGNORECASE)
                            for j, context in enumerate(a67_contexts[:3]):
                                print(f"A67 context {j+1}: {context}")
                        
                        # Look for police/investigation terms
                        investigation_terms = ['politie', 'onderzoek', 'afgesloten', 'investigation', 'police', 'closure']
                        for term in investigation_terms:
                            if term in response_text:
                                print(f"\n*** FOUND '{term.upper()}' IN RESPONSE! ***")
                                contexts = re.findall(f'.{{0,100}}{re.escape(term)}.{{0,100}}', response_text, re.IGNORECASE)
                                for context in contexts[:2]:
                                    print(f"Context: {context}")
                    
                    elif isinstance(data, list):
                        print(f"Response is a list with {len(data)} items")
                        if data:
                            print(f"First item type: {type(data[0])}")
                            if isinstance(data[0], dict):
                                print(f"First item keys: {list(data[0].keys())}")
                    
                except json.JSONDecodeError:
                    print(f"Status: JSON DECODE ERROR")
                    print(f"Response content (first 500 chars): {response.text[:500]}")
            else:
                print(f"Status: ERROR {response.status_code}")
                
        except Exception as e:
            print(f"Status: EXCEPTION - {str(e)}")

if __name__ == "__main__":
    examine_anwb_api_responses()