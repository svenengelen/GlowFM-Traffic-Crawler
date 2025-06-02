#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import time
import json

def find_real_anwb_traffic():
    """Find the real ANWB traffic data by trying different approaches"""
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
    }
    
    print("=== TRYING DIFFERENT ANWB TRAFFIC SOURCES ===")
    
    # Try different ANWB URLs
    urls_to_try = [
        "https://anwb.nl/verkeer/filelijst",
        "https://anwb.nl/verkeer",
        "https://anwb.nl/verkeer/files",
        "https://anwb.nl/verkeer/kaart",
        "https://www.anwb.nl/verkeer/filelijst",
        "https://www.anwb.nl/verkeer/files",
        "https://verkeer.anwb.nl/filelijst",
        "https://verkeer.anwb.nl/files"
    ]
    
    for i, url in enumerate(urls_to_try):
        try:
            print(f"\n{i+1}. Trying URL: {url}")
            response = session.get(url, headers=headers, timeout=15)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text = soup.get_text().lower()
                
                # Look for A67 specifically
                if 'a67' in text:
                    print(f"   *** FOUND A67 MENTION! ***")
                    
                    # Extract A67 context
                    import re
                    a67_contexts = re.findall(r'.{0,200}a67.{0,200}', text, re.IGNORECASE)
                    for j, context in enumerate(a67_contexts[:3]):
                        print(f"   A67 context {j+1}: {context}")
                
                # Look for traffic indicators
                traffic_indicators = ['file', 'vertraging', '+', 'min', 'venlo', 'eindhoven']
                found_indicators = [indicator for indicator in traffic_indicators if indicator in text]
                print(f"   Traffic indicators found: {found_indicators}")
                
                # Check content length
                print(f"   Content length: {len(text)} chars")
                
                # Save this response if it looks promising
                if 'a67' in text or len(found_indicators) > 3:
                    filename = f'/tmp/anwb_response_{i+1}.html'
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"   Saved response to {filename}")
                
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    # Try mobile version (sometimes has different data)
    print(f"\n=== TRYING MOBILE VERSION ===")
    mobile_headers = headers.copy()
    mobile_headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", headers=mobile_headers, timeout=15)
        print(f"Mobile version status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text().lower()
            
            if 'a67' in text:
                print("*** MOBILE VERSION HAS A67! ***")
                a67_contexts = re.findall(r'.{0,200}a67.{0,200}', text, re.IGNORECASE)
                for context in a67_contexts:
                    print(f"Mobile A67: {context}")
            
            with open('/tmp/anwb_mobile.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Saved mobile version to /tmp/anwb_mobile.html")
    
    except Exception as e:
        print(f"Mobile error: {str(e)}")
    
    # Try with different Accept headers (API-like)
    print(f"\n=== TRYING API-STYLE REQUESTS ===")
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://anwb.nl/verkeer/filelijst',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    api_urls = [
        "https://anwb.nl/api/verkeer/files",
        "https://anwb.nl/api/traffic",
        "https://anwb.nl/verkeer/api/filelijst",
        "https://api.anwb.nl/verkeer/files",
        "https://api.anwb.nl/traffic/current"
    ]
    
    for url in api_urls:
        try:
            print(f"API trying: {url}")
            response = session.get(url, headers=api_headers, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   JSON response: {type(data)}")
                    if isinstance(data, dict):
                        print(f"   Keys: {list(data.keys())}")
                    elif isinstance(data, list):
                        print(f"   List length: {len(data)}")
                        
                    # Check for A67 in JSON
                    response_text = response.text.lower()
                    if 'a67' in response_text:
                        print("   *** API HAS A67 DATA! ***")
                        with open(f'/tmp/anwb_api_{url.split("/")[-1]}.json', 'w') as f:
                            json.dump(data, f, indent=2)
                        
                except json.JSONDecodeError:
                    content_preview = response.text[:200]
                    print(f"   Non-JSON response: {content_preview}")
                    
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    # Try waiting and checking again (maybe data loads after delay)
    print(f"\n=== CHECKING WITH DELAY (simulating page load) ===")
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", headers=headers, timeout=15)
        print("Waiting 5 seconds for potential JS loading...")
        time.sleep(5)
        
        # Check if there are any script tags that might load data
        soup = BeautifulSoup(response.content, 'html.parser')
        scripts = soup.find_all('script')
        
        print(f"Found {len(scripts)} script tags")
        
        for i, script in enumerate(scripts):
            script_text = script.get_text()
            if 'a67' in script_text.lower() or 'traffic' in script_text.lower() or 'file' in script_text.lower():
                print(f"Script {i} has traffic-related content:")
                print(script_text[:300] + "...")
                
                with open(f'/tmp/anwb_script_{i}.js', 'w', encoding='utf-8') as f:
                    f.write(script_text)
                
    except Exception as e:
        print(f"Delay check error: {str(e)}")

if __name__ == "__main__":
    find_real_anwb_traffic()