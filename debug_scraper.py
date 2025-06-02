#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

def debug_anwb_structure():
    """Debug the ANWB website structure to understand the HTML"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== DEBUGGING ANWB WEBSITE STRUCTURE ===")
        print(f"Response status: {response.status_code}")
        print(f"Content length: {len(response.content)}")
        
        # Look for any articles
        all_articles = soup.find_all('article')
        print(f"\n1. Found {len(all_articles)} total <article> elements")
        
        # Look for elements with data-test-id containing 'traffic'
        traffic_elements = soup.find_all(attrs={'data-test-id': re.compile(r'traffic')})
        print(f"\n2. Found {len(traffic_elements)} elements with data-test-id containing 'traffic'")
        for i, elem in enumerate(traffic_elements[:5]):
            print(f"   {i+1}: {elem.name} with data-test-id='{elem.get('data-test-id')}'")
        
        # Look for elements with data-test-id='traffic-list-road'
        road_articles = soup.find_all('article', {'data-test-id': 'traffic-list-road'})
        print(f"\n3. Found {len(road_articles)} articles with data-test-id='traffic-list-road'")
        
        # Look for any elements containing road numbers like A15, A27, etc.
        road_patterns = ['A15', 'A27', 'A50', 'A73', 'N99']
        for pattern in road_patterns:
            elements = soup.find_all(text=re.compile(pattern))
            print(f"\n4. Found {len(elements)} text elements containing '{pattern}'")
            if elements:
                for elem in elements[:2]:
                    parent = elem.parent
                    print(f"   Text: '{elem.strip()}' in <{parent.name}> with class={parent.get('class')}")
        
        # Look for elements with class containing 'traffic'
        traffic_class_elements = soup.find_all(class_=re.compile(r'traffic', re.I))
        print(f"\n5. Found {len(traffic_class_elements)} elements with class containing 'traffic'")
        for i, elem in enumerate(traffic_class_elements[:3]):
            print(f"   {i+1}: {elem.name} with class='{elem.get('class')}'")
        
        # Look for any div with id or class containing 'list'
        list_elements = soup.find_all(['div', 'section'], class_=re.compile(r'list', re.I))
        print(f"\n6. Found {len(list_elements)} div/section elements with class containing 'list'")
        for i, elem in enumerate(list_elements[:3]):
            print(f"   {i+1}: {elem.name} with class='{elem.get('class')}'")
        
        # Check if content is dynamically loaded
        script_tags = soup.find_all('script')
        react_scripts = [script for script in script_tags if script.get_text() and ('react' in script.get_text().lower() or 'reactroot' in script.get_text().lower())]
        print(f"\n7. Found {len(script_tags)} script tags, {len(react_scripts)} appear to be React-related")
        
        # Look for __NEXT_DATA__ or similar client-side data
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data:
            print("\n8. Found __NEXT_DATA__ script (Next.js app with server-side data)")
        else:
            print("\n8. No __NEXT_DATA__ found (might be client-side rendered)")
        
        # Check for data-reactroot
        react_root = soup.find(attrs={'data-reactroot': True})
        if react_root:
            print(f"\n9. Found React root element: <{react_root.name}>")
        else:
            print("\n9. No React root element found")
            
        print("\n=== SAMPLE HTML AROUND TRAFFIC CONTENT ===")
        traffic_list_div = soup.find('div', class_=re.compile(r'traffic'))
        if traffic_list_div:
            print("Found traffic-related div:")
            print(traffic_list_div.prettify()[:1000] + "...")
        else:
            print("No traffic-related div found")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_anwb_structure()