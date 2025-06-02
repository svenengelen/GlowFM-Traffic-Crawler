#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

def scrape_anwb_text():
    """Scrape ANWB website text to find traffic information"""
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
    }
    
    try:
        response = session.get("https://anwb.nl/verkeer/filelijst", headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== ANWB TEXT-BASED TRAFFIC ANALYSIS ===")
        
        # Get all text from the page
        page_text = soup.get_text()
        
        # Clean up the text
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        full_text = ' '.join(lines)
        
        print(f"Total text length: {len(full_text)} characters")
        
        # Look for traffic patterns
        traffic_patterns = [
            # Road + location + issue patterns
            (r'(A\d+|N\d+).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*?).*?(\+\s*\d+\s*min|file|vertraging|afgesloten|politie|onderzoek)', 'Traffic with details'),
            # Simple delay patterns
            (r'(\+\s*\d+\s*(?:min|minuten))', 'Delay time'),
            # Road closure patterns  
            (r'(afgesloten|gedeeltelijk\s+afgesloten|politie.*?onderzoek)', 'Road closure'),
            # Specific incident patterns
            (r'(ongeval|incident|werkzaamheden|storing)', 'Incident type'),
        ]
        
        found_traffic = []
        
        for pattern, description in traffic_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                context_start = max(0, match.start() - 100)
                context_end = min(len(full_text), match.end() + 100)
                context = full_text[context_start:context_end]
                
                found_traffic.append({
                    'type': description,
                    'match': match.group(),
                    'context': context.strip()
                })
        
        print(f"\nFound {len(found_traffic)} potential traffic indicators:")
        
        # Analyze each found traffic item
        for i, item in enumerate(found_traffic[:10]):  # Show first 10
            print(f"\n{i+1}. {item['type']}: {item['match']}")
            print(f"   Context: {item['context'][:200]}...")
        
        # Look specifically for A67 and police/investigation
        print(f"\n=== SPECIFIC A67 ANALYSIS ===")
        
        # Search for A67 mentions
        a67_pattern = r'.{0,200}A67.{0,200}'
        a67_matches = re.findall(a67_pattern, full_text, re.IGNORECASE)
        
        print(f"Found {len(a67_matches)} A67 mentions:")
        for i, match in enumerate(a67_matches):
            print(f"{i+1}. {match.strip()}")
        
        # Search for police/investigation terms
        investigation_patterns = [
            r'.{0,150}(politie.*?onderzoek|onderzoek.*?politie).{0,150}',
            r'.{0,150}(afgesloten.*?politie|politie.*?afgesloten).{0,150}',
            r'.{0,150}(gedeeltelijk.*?afgesloten).{0,150}',
            r'.{0,150}(police.*?investigation|investigation.*?police).{0,150}'
        ]
        
        print(f"\n=== POLICE/INVESTIGATION ANALYSIS ===")
        
        investigation_found = []
        for pattern in investigation_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            investigation_found.extend(matches)
        
        print(f"Found {len(investigation_found)} police/investigation mentions:")
        for i, match in enumerate(investigation_found):
            print(f"{i+1}. {match.strip()}")
        
        # Look for road + location combinations
        print(f"\n=== ROAD + LOCATION ANALYSIS ===")
        
        road_location_pattern = r'(A\d+|N\d+).*?(?:tussen|richting|naar|van|bij|knooppunt|afrit|knp\.?)\s+([A-Z][a-z]+(?:[-\s][A-Z][a-z]+)*)'
        road_locations = re.findall(road_location_pattern, full_text, re.IGNORECASE)
        
        print(f"Found {len(road_locations)} road-location combinations:")
        for road, location in road_locations[:10]:
            print(f"  {road} -> {location}")
        
        # Look for delay times
        print(f"\n=== DELAY TIME ANALYSIS ===")
        
        delay_pattern = r'(\+\s*\d+\s*(?:min|minuten|minutes))'
        delays = re.findall(delay_pattern, full_text, re.IGNORECASE)
        
        print(f"Found {len(delays)} delay mentions:")
        for delay in delays[:10]:
            print(f"  {delay}")
        
        # Combine findings for structured traffic data
        print(f"\n=== STRUCTURED TRAFFIC EXTRACTION ===")
        
        # Try to extract structured traffic info
        structured_pattern = r'(A\d+|N\d+).*?(?:tussen|richting|naar|van|bij)\s+([A-Za-z\-\s]+?).*?(\+\s*\d+\s*min|afgesloten|file|vertraging)'
        structured_matches = re.findall(structured_pattern, full_text, re.IGNORECASE)
        
        print(f"Found {len(structured_matches)} structured traffic items:")
        for road, location, issue in structured_matches:
            print(f"  Road: {road.strip()}")
            print(f"  Location: {location.strip()}")
            print(f"  Issue: {issue.strip()}")
            print()
        
        # Save raw text for manual inspection
        with open('/tmp/anwb_page_text.txt', 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"Saved full page text to /tmp/anwb_page_text.txt")
        
        return {
            'structured_traffic': structured_matches,
            'a67_mentions': a67_matches,
            'investigation_mentions': investigation_found,
            'delays': delays,
            'road_locations': road_locations
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    result = scrape_anwb_text()
    
    if result:
        print(f"\n=== SUMMARY ===")
        print(f"Structured traffic items: {len(result['structured_traffic'])}")
        print(f"A67 mentions: {len(result['a67_mentions'])}")
        print(f"Investigation mentions: {len(result['investigation_mentions'])}")
        print(f"Delay times found: {len(result['delays'])}")
        print(f"Road-location pairs: {len(result['road_locations'])}")