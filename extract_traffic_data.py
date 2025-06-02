#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json

def extract_anwb_traffic_data():
    """Extract actual traffic data from ANWB Next.js data"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        
        if next_data:
            data = json.loads(next_data.get_text())
            
            # Navigate to traffic-list data
            traffic_list = None
            try:
                traffic_list = data['props']['pageProps']['pageContextData']['applicationData']['traffic-list']
                print("=== FOUND ANWB TRAFFIC-LIST DATA ===")
                print(f"Traffic list type: {type(traffic_list)}")
                
                if isinstance(traffic_list, dict):
                    print(f"Traffic list keys: {list(traffic_list.keys())}")
                    
                    # Look for traffic items
                    for key, value in traffic_list.items():
                        print(f"\nKey: {key}")
                        print(f"Value type: {type(value)}")
                        
                        if isinstance(value, list):
                            print(f"List length: {len(value)}")
                            for i, item in enumerate(value[:5]):
                                print(f"  Item {i}: {type(item)} - {str(item)[:100]}")
                        elif isinstance(value, dict):
                            print(f"Dict keys: {list(value.keys())}")
                        else:
                            print(f"Value: {str(value)[:100]}")
                
                elif isinstance(traffic_list, list):
                    print(f"Traffic list length: {len(traffic_list)}")
                    for i, item in enumerate(traffic_list[:10]):
                        print(f"\nTraffic item {i}:")
                        if isinstance(item, dict):
                            for k, v in item.items():
                                print(f"  {k}: {v}")
                        else:
                            print(f"  {item}")
                            
            except KeyError as e:
                print(f"Could not find traffic-list data: {e}")
                
                # Try alternative paths
                alt_paths = [
                    ['props', 'pageProps', 'pageData'],
                    ['props', 'pageProps', 'applicationData'],
                    ['props', 'pageProps'],
                    ['props']
                ]
                
                for path in alt_paths:
                    try:
                        current = data
                        for key in path:
                            current = current[key]
                        print(f"\nFound data at {' -> '.join(path)}:")
                        if isinstance(current, dict):
                            for key in current.keys():
                                if 'traffic' in key.lower() or 'file' in key.lower():
                                    print(f"  Found traffic-related key: {key}")
                                    traffic_data = current[key]
                                    print(f"    Type: {type(traffic_data)}")
                                    if isinstance(traffic_data, dict):
                                        print(f"    Keys: {list(traffic_data.keys())}")
                                    elif isinstance(traffic_data, list):
                                        print(f"    Length: {len(traffic_data)}")
                                        if traffic_data:
                                            print(f"    First item: {traffic_data[0]}")
                        break
                    except:
                        continue
            
            # Also save the full data structure for analysis
            with open('/tmp/anwb_nextjs_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\nSaved full Next.js data to /tmp/anwb_nextjs_data.json")
            
        else:
            print("No Next.js data found")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    extract_anwb_traffic_data()