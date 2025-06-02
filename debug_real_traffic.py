#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json

def debug_anwb_real_time():
    """Debug the ANWB website to find the actual current traffic data"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== DEBUGGING REAL ANWB TRAFFIC DATA ===")
        print(f"Response status: {response.status_code}")
        
        # Look for text containing A67, Eindhoven, Venlo to find the reported traffic jam
        print("\n1. Searching for A67 Eindhoven-Venlo traffic jam...")
        a67_elements = soup.find_all(text=re.compile(r'A67', re.I))
        print(f"Found {len(a67_elements)} elements containing 'A67'")
        
        for i, elem in enumerate(a67_elements[:10]):
            parent = elem.parent
            grandparent = parent.parent if parent.parent else None
            print(f"   A67 text {i+1}: '{elem.strip()}'")
            print(f"   Parent: <{parent.name}> with class={parent.get('class')}")
            if grandparent:
                print(f"   Grandparent: <{grandparent.name}> with class={grandparent.get('class')}")
            print()
        
        # Look for elements containing "Panningen" or "Venlo"
        print("\n2. Searching for Panningen/Venlo locations...")
        location_terms = ['Panningen', 'Venlo', 'Eindhoven']
        for term in location_terms:
            elements = soup.find_all(text=re.compile(term, re.I))
            print(f"Found {len(elements)} elements containing '{term}'")
            for elem in elements[:3]:
                parent = elem.parent
                print(f"   '{elem.strip()}' in <{parent.name}> class={parent.get('class')}")
        
        # Look for elements containing time delays like "+7" or "min"
        print("\n3. Searching for delay information...")
        delay_elements = soup.find_all(text=re.compile(r'\+\s*\d+\s*min', re.I))
        print(f"Found {len(delay_elements)} elements with delay patterns")
        for elem in delay_elements:
            parent = elem.parent
            print(f"   Delay: '{elem.strip()}' in <{parent.name}> class={parent.get('class')}")
        
        # Look for elements containing "ongeval" (accident)
        print("\n4. Searching for accident information...")
        accident_elements = soup.find_all(text=re.compile(r'ongeval', re.I))
        print(f"Found {len(accident_elements)} elements containing 'ongeval'")
        for elem in accident_elements:
            parent = elem.parent
            print(f"   Accident: '{elem.strip()}' in <{parent.name}> class={parent.get('class')}")
        
        # Look for speed camera information
        print("\n5. Searching for speed camera data...")
        camera_terms = ['flits', 'camera', 'controle']
        for term in camera_terms:
            elements = soup.find_all(text=re.compile(term, re.I))
            print(f"Found {len(elements)} elements containing '{term}'")
            for elem in elements[:3]:
                parent = elem.parent
                print(f"   '{elem.strip()}' in <{parent.name}> class={parent.get('class')}")
        
        # Check if there's JSON data embedded in the page
        print("\n6. Looking for JSON data...")
        script_tags = soup.find_all('script')
        for i, script in enumerate(script_tags):
            script_text = script.get_text()
            if 'traffic' in script_text.lower() or 'file' in script_text.lower():
                print(f"Script {i} contains traffic-related data (first 500 chars):")
                print(script_text[:500])
                print("...")
                break
        
        # Look for the actual data structure
        print("\n7. Looking for current page structure...")
        
        # Check for any containers that might hold traffic data
        containers = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'traffic|file|list', re.I))
        print(f"Found {len(containers)} potential traffic containers")
        
        for i, container in enumerate(containers[:5]):
            print(f"\nContainer {i+1}: <{container.name}> class={container.get('class')}")
            # Get some text content
            text_content = container.get_text()[:200]
            print(f"Content preview: {text_content}")
        
        # Check for Next.js data
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            try:
                data = json.loads(next_data.get_text())
                print(f"\n8. Found Next.js data structure")
                print(f"Keys in __NEXT_DATA__: {list(data.keys())}")
                if 'props' in data:
                    print(f"Props keys: {list(data['props'].keys())}")
            except:
                print("Could not parse Next.js data")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_anwb_real_time()