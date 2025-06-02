#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

def find_anwb_api_endpoints():
    """Find the actual API endpoints ANWB uses for traffic data"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== SEARCHING FOR ANWB API ENDPOINTS ===")
        
        # Look for script tags that might contain API URLs
        scripts = soup.find_all('script')
        api_patterns = [
            r'https?://[^"\']*api[^"\']*traffic[^"\']*',
            r'https?://[^"\']*traffic[^"\']*api[^"\']*',
            r'https?://[^"\']*verkeer[^"\']*',
            r'https?://[^"\']*file[^"\']*api[^"\']*',
            r'/api/[^"\']*traffic[^"\']*',
            r'/api/[^"\']*verkeer[^"\']*',
            r'api\.anwb\.nl[^"\']*',
            r'traffic\.anwb\.nl[^"\']*'
        ]
        
        found_urls = set()
        
        for script in scripts:
            script_text = script.get_text()
            for pattern in api_patterns:
                matches = re.findall(pattern, script_text, re.IGNORECASE)
                for match in matches:
                    found_urls.add(match)
        
        print(f"Found {len(found_urls)} potential API URLs:")
        for url in sorted(found_urls):
            print(f"  {url}")
        
        # Also check for common ANWB API patterns
        test_endpoints = [
            "https://api.anwb.nl/verkeer/files",
            "https://api.anwb.nl/traffic/current",
            "https://api.anwb.nl/v1/traffic",
            "https://traffic-api.anwb.nl/files",
            "https://verkeer.anwb.nl/api/files",
            "https://anwb.nl/api/verkeer/files",
            "https://anwb.nl/api/traffic",
            "https://api.anwb.nl/verkeersinformatie",
            "https://cdn.anwb.nl/api/traffic"
        ]
        
        print(f"\n=== TESTING COMMON ANWB API ENDPOINTS ===")
        
        for endpoint in test_endpoints:
            try:
                print(f"\nTesting: {endpoint}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': 'https://anwb.nl/verkeer/filelijst'
                }
                
                api_response = session.get(endpoint, headers=headers, timeout=10)
                print(f"  Status: {api_response.status_code}")
                
                if api_response.status_code == 200:
                    try:
                        json_data = api_response.json()
                        print(f"  JSON Response: {type(json_data)}")
                        if isinstance(json_data, dict):
                            print(f"  Keys: {list(json_data.keys())}")
                        elif isinstance(json_data, list):
                            print(f"  List length: {len(json_data)}")
                            if json_data:
                                print(f"  First item keys: {list(json_data[0].keys()) if isinstance(json_data[0], dict) else 'Not a dict'}")
                        
                        # Look for A67 specifically
                        response_text = api_response.text.lower()
                        if 'a67' in response_text:
                            print(f"  *** FOUND A67 REFERENCE! ***")
                            # Extract A67 context
                            a67_context = re.findall(r'.{0,100}a67.{0,100}', response_text, re.IGNORECASE)
                            for context in a67_context[:3]:
                                print(f"    A67 context: {context}")
                        
                    except:
                        content_preview = api_response.text[:200]
                        print(f"  Non-JSON response: {content_preview}")
                
            except Exception as e:
                print(f"  Error: {str(e)}")
        
        # Try to find dynamic loading scripts
        print(f"\n=== CHECKING FOR DYNAMIC LOADING ===")
        
        # Look for fetch() calls or XMLHttpRequest
        fetch_patterns = [
            r'fetch\(["\']([^"\']*)["\']',
            r'XMLHttpRequest.*open\(["\'][^"\']*["\'],\s*["\']([^"\']*)["\']',
            r'axios\.get\(["\']([^"\']*)["\']',
            r'\.get\(["\']([^"\']*api[^"\']*)["\']'
        ]
        
        for script in scripts:
            script_text = script.get_text()
            for pattern in fetch_patterns:
                matches = re.findall(pattern, script_text, re.IGNORECASE)
                for match in matches:
                    if 'traffic' in match.lower() or 'verkeer' in match.lower() or 'api' in match.lower():
                        print(f"  Found dynamic API call: {match}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    find_anwb_api_endpoints()