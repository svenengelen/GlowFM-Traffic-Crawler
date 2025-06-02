#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json

def debug_anwb_real_current():
    """Debug current ANWB website to find actual traffic data structure"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== CURRENT ANWB TRAFFIC DATA ANALYSIS ===")
        print(f"Response status: {response.status_code}")
        
        # Search for current A67 traffic with police investigation
        print("\n1. Searching for A67 traffic with police investigation...")
        
        # Look for all text containing A67
        a67_texts = soup.find_all(text=re.compile(r'A67', re.I))
        print(f"Found {len(a67_texts)} text elements containing 'A67'")
        
        for i, text in enumerate(a67_texts[:20]):
            print(f"   A67 text {i+1}: '{text.strip()}'")
            parent = text.parent
            if parent:
                parent_text = parent.get_text().strip()
                if parent_text != text.strip():
                    print(f"      Parent context: '{parent_text[:100]}...'")
        
        # Look for police investigation terms
        print("\n2. Searching for police investigation...")
        investigation_terms = ['politie', 'onderzoek', 'afgesloten', 'gedeeltelijk', 'investigation']
        for term in investigation_terms:
            elements = soup.find_all(text=re.compile(term, re.I))
            if elements:
                print(f"Found {len(elements)} elements containing '{term}':")
                for elem in elements[:3]:
                    print(f"   '{elem.strip()}'")
        
        # Look for current traffic structure using different selectors
        print("\n3. Analyzing page structure for traffic data...")
        
        # Try to find the actual data structure
        potential_containers = [
            'div[data-test*="traffic"]',
            'div[class*="traffic"]',
            'div[class*="file"]',
            'article',
            'section[class*="traffic"]',
            'ul[class*="traffic"]',
            '[data-testid*="traffic"]'
        ]
        
        for selector in potential_containers:
            elements = soup.select(selector)
            if elements:
                print(f"\nFound {len(elements)} elements with selector '{selector}':")
                for i, elem in enumerate(elements[:3]):
                    text_content = elem.get_text()[:200]
                    print(f"   Element {i+1}: {text_content}")
        
        # Check for Next.js data again with focus on traffic
        print("\n4. Checking Next.js data structure...")
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            try:
                data = json.loads(next_data.get_text())
                print("Found Next.js data structure")
                
                # Navigate through the data structure
                def find_traffic_data(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            new_path = f"{path}.{key}" if path else key
                            if 'traffic' in key.lower() or 'file' in key.lower():
                                print(f"   Potential traffic key: {new_path}")
                                if isinstance(value, (list, dict)):
                                    print(f"      Type: {type(value)}, Length/Keys: {len(value) if isinstance(value, list) else list(value.keys())[:5]}")
                            
                            if isinstance(value, (dict, list)):
                                find_traffic_data(value, new_path)
                    elif isinstance(obj, list) and obj:
                        for i, item in enumerate(obj[:3]):
                            find_traffic_data(item, f"{path}[{i}]")
                
                find_traffic_data(data)
                
            except:
                print("Could not parse Next.js data")
        
        # Look for specific road numbers and their context
        print("\n5. Analyzing road-specific content...")
        road_numbers = ['A67', 'A2', 'A16', 'A50']
        for road in road_numbers:
            # Find elements containing this road
            road_elements = soup.find_all(text=re.compile(f'\\b{road}\\b', re.I))
            if road_elements:
                print(f"\n{road} context analysis:")
                for elem in road_elements[:3]:
                    parent = elem.parent
                    if parent:
                        # Get surrounding context
                        grandparent = parent.parent
                        if grandparent:
                            context = grandparent.get_text()[:300]
                            print(f"   Context: {context}")
        
        # Save the raw HTML for manual inspection if needed
        with open('/tmp/anwb_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"\n6. Saved HTML to /tmp/anwb_debug.html for inspection")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_anwb_real_current()