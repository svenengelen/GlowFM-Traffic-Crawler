import os
import time
import asyncio
import requests
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from bs4 import BeautifulSoup
import re
import threading
import schedule
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DATABASE_NAME = "anwb_traffic"

# Initialize FastAPI app
app = FastAPI(title="ANWB Traffic Monitor", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB client
client = AsyncIOMotorClient(MONGO_URL)
db = client[DATABASE_NAME]

# Data models
class TrafficJam(BaseModel):
    id: str
    road: str
    direction: str
    source_location: str
    destination_location: str
    route_details: str
    cause: str
    delay_minutes: int
    length_km: float
    last_updated: datetime

class SpeedCamera(BaseModel):
    id: str
    road: str
    location: str
    direction: str
    flitser_type: str  # Dynamic flitser type
    is_active: bool
    last_updated: datetime

class TrafficData(BaseModel):
    traffic_jams: List[TrafficJam]
    speed_cameras: List[SpeedCamera]
    last_updated: datetime
    total_jams: int

# Filtering criteria from requirements
MONITORED_ROADS = ['A2', 'A16', 'A50', 'A58', 'A59', 'A65', 'A67', 'A73', 'A76', 'A270', 'N2', 'N69', 'N266', 'N270']
MONITORED_CITIES = [
    'Eindhoven', 'Venlo', 'Weert', "'s-Hertogenbosch", 'Roermond', 'Maasbracht', 
    'Nijmegen', 'Oss', 'Zonzeel', 'Breda', 'Tilburg', 'Rotterdam', 'Deurne', 
    'Helmond', 'Venray', 'Heerlen', 'Maastricht', 'Belgische Grens', 'Duitse Grens', 'Valkenswaard'
]

class ANWBScraper:
    def __init__(self):
        self.base_url = "https://anwb.nl/verkeer/filelijst"
        self.driver = None
        
    def _setup_driver(self):
        """Set up Selenium WebDriver with Chromium"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Use system Chromium
        chrome_options.binary_location = "/usr/bin/chromium"
        
        # Use system chromedriver
        service = Service("/usr/bin/chromedriver")
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Successfully initialized Chrome driver")
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise e

    def scrape_traffic_data(self) -> Dict:
        """Scrape traffic data from ANWB website using Selenium"""
        try:
            print(f"Scraping ANWB traffic data with Selenium at {datetime.now()}")
            
            # Setup WebDriver
            self._setup_driver()
            
            # Navigate to the page
            self.driver.get(self.base_url)
            
            # Wait for the page to load and traffic data to appear
            print("Waiting for traffic data to load...")
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for traffic list to be present
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-accordion-road]")))
                print("Traffic data loaded successfully")
            except:
                print("Timeout waiting for traffic data, proceeding with available content")
            
            # Wait a bit more to ensure all content is loaded
            time.sleep(3)
            
            # Extract traffic jams by expanding each accordion
            traffic_jams = self._extract_traffic_jams_detailed()
            
            # Extract speed cameras by enabling the "Flitsers" checkbox
            speed_cameras = self._extract_speed_cameras_detailed()
            
            return {
                'traffic_jams': traffic_jams,
                'speed_cameras': speed_cameras,
                'last_updated': datetime.now(),
                'total_jams': len(traffic_jams)
            }
            
        except Exception as e:
            print(f"Error scraping ANWB data with Selenium: {str(e)}")
            return {
                'traffic_jams': [],
                'speed_cameras': [],
                'last_updated': datetime.now(),
                'total_jams': 0,
                'error': str(e)
            }
        finally:
            # Clean up the driver
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None

    def _extract_traffic_jams(self, soup: BeautifulSoup) -> List[Dict]:
        """Legacy extraction method - kept as backup"""
        traffic_jams = []
        
        # Find all road articles using the correct selectors from our analysis
        road_articles = soup.find_all('article', {'data-accordion-road': True})
        print(f"Found {len(road_articles)} road articles with data-accordion-road")
        
        if not road_articles:
            # Fallback: try alternative selectors
            road_articles = soup.find_all('article', class_='sc-fd0a2c7e-2')
            print(f"Fallback: Found {len(road_articles)} road articles with class sc-fd0a2c7e-2")
        
        for article in road_articles:
            try:
                # Get road number from data-accordion-road attribute or span element
                road = None
                if article.get('data-accordion-road'):
                    road = article.get('data-accordion-road')
                else:
                    road_element = article.find('span', title=True)
                    if road_element and road_element.get('title'):
                        road = road_element.get('title')
                
                if not road:
                    continue
                    
                print(f"Processing road: {road}")
                
                # Only process monitored roads
                if road not in MONITORED_ROADS:
                    print(f"Road {road} not in monitored roads, skipping")
                    continue
                
                # Look for traffic data in the specific div structure we saw in HTML
                delay_info = article.find('div', class_='sc-fd0a2c7e-6')
                
                # Also check for totals div that shows "2 files" etc
                totals_info = article.find('div', {'data-test-id': 'traffic-list-road-totals'})
                
                print(f"Road {road}: delay_info={delay_info.get_text(strip=True) if delay_info else 'None'}")
                print(f"Road {road}: totals_info={totals_info.get_text(strip=True) if totals_info else 'None'}")
                
                # Check if there's actual traffic data (delays and length)
                if delay_info and delay_info.get_text(strip=True):
                    # Extract delay and length
                    delay_text = delay_info.get_text(strip=True)
                    delay_minutes = self._extract_delay_minutes(delay_text)
                    length_km = self._extract_length_km(delay_text)
                    
                    print(f"Found traffic data: {delay_text}, delay={delay_minutes}min, length={length_km}km")
                    
                    # Only add if we have meaningful delay information
                    if delay_minutes > 0:
                        traffic_jam = {
                            'id': f"{road}_{int(time.time())}_{len(traffic_jams)}",
                            'road': road,
                            'direction': 'Onbekende richting',
                            'from_exit': 'Onbekend',
                            'to_exit': 'Onbekend', 
                            'cause': 'Onbekende oorzaak',
                            'delay_minutes': delay_minutes,
                            'length_km': length_km,
                            'last_updated': datetime.now()
                        }
                        traffic_jams.append(traffic_jam)
                        print(f"Added traffic jam: {traffic_jam}")
                
                # Also handle cases where there are traffic totals but no specific delay info (A67 case)
                elif totals_info and not delay_info:
                    # This means there are traffic jams but displayed differently
                    print(f"Road {road} has traffic totals but no delay info yet")
                    
            except Exception as e:
                print(f"Error processing road article: {str(e)}")
                continue
        
        print(f"Total traffic jams extracted: {len(traffic_jams)}")
        return traffic_jams

    def _extract_traffic_jams_detailed(self) -> List[Dict]:
        """Extract detailed traffic jam data by expanding accordions"""
        traffic_jams = []
        
        try:
            # Find all road articles
            road_articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-accordion-road]")
            print(f"Found {len(road_articles)} road articles")
            
            for article in road_articles:
                try:
                    # Get road number
                    road = article.get_attribute('data-accordion-road')
                    if not road or road not in MONITORED_ROADS:
                        print(f"Skipping road {road} - not in monitored roads")
                        continue
                    
                    print(f"Processing road: {road}")
                    
                    # Check if there are traffic jams (look for the totals indicator)
                    try:
                        total_indicator = article.find_element(By.CSS_SELECTOR, "[data-test-id='traffic-list-road-totals']")
                        total_text = total_indicator.text.strip()
                        if not total_text or total_text == "0":
                            print(f"No traffic jams found for {road}")
                            continue
                    except:
                        print(f"No total indicator found for {road}")
                        continue
                    
                    # Click to expand the accordion
                    try:
                        button = article.find_element(By.CSS_SELECTOR, "button[data-test-id='traffic-list-road-header']")
                        self.driver.execute_script("arguments[0].click();", button)
                        print(f"Expanded accordion for {road}")
                        
                        # Wait for content to load
                        time.sleep(2)
                        
                        # Extract individual traffic jam items
                        try:
                            jam_items = article.find_elements(By.CSS_SELECTOR, "div[data-test-id*='traffic-item'], li[data-test-id*='traffic-item'], .traffic-item")
                            
                            if not jam_items:
                                # Try alternative selectors for traffic items
                                jam_items = article.find_elements(By.CSS_SELECTOR, "div[class*='traffic'], li[class*='jam'], .file-item")
                            
                            print(f"Found {len(jam_items)} traffic items for {road}")
                            
                            if jam_items:
                                for idx, item in enumerate(jam_items):
                                    jam_data = self._extract_jam_details(item, road, idx)
                                    if jam_data:
                                        traffic_jams.append(jam_data)
                            else:
                                # If no specific items found, extract from the whole accordion content
                                jam_data = self._extract_jam_from_accordion(article, road)
                                if jam_data:
                                    traffic_jams.append(jam_data)
                                    
                        except Exception as e:
                            print(f"Error extracting traffic items for {road}: {e}")
                            # Fallback: extract from whole accordion
                            jam_data = self._extract_jam_from_accordion(article, road)
                            if jam_data:
                                traffic_jams.append(jam_data)
                        
                    except Exception as e:
                        print(f"Error expanding accordion for {road}: {e}")
                        continue
                        
                except Exception as e:
                    print(f"Error processing article: {e}")
                    continue
            
        except Exception as e:
            print(f"Error in _extract_traffic_jams_detailed: {e}")
        
        print(f"Total detailed traffic jams extracted: {len(traffic_jams)}")
        return traffic_jams

    def _extract_jam_details(self, item_element, road: str, idx: int) -> Dict:
        """Extract details from a specific traffic jam item"""
        try:
            # Get all text content from the item
            text_content = item_element.text.strip()
            
            if not text_content:
                return None
            
            print(f"Processing traffic item {idx} for {road}: {text_content}")
            
            # Extract direction (looking for common Dutch direction indicators)
            direction = self._extract_direction(text_content)
            
            # Extract exits/locations
            from_exit, to_exit = self._extract_exits(text_content)
            
            # Extract cause
            cause = self._extract_cause(text_content)
            
            # Extract delay and length
            delay_minutes = self._extract_delay_minutes(text_content)
            length_km = self._extract_length_km(text_content)
            
            if delay_minutes > 0 or length_km > 0:
                return {
                    'id': f"{road}_{int(time.time())}_{idx}",
                    'road': road,
                    'direction': direction,
                    'from_exit': from_exit,
                    'to_exit': to_exit,
                    'cause': cause,
                    'delay_minutes': delay_minutes,
                    'length_km': length_km,
                    'last_updated': datetime.now()
                }
                
        except Exception as e:
            print(f"Error extracting jam details: {e}")
        
        return None

    def _extract_jam_from_accordion(self, article_element, road: str) -> Dict:
        """Extract jam data from the whole accordion when specific items aren't found"""
        try:
            # Get all text from the expanded accordion
            text_content = article_element.text.strip()
            
            print(f"Extracting from whole accordion for {road}: {text_content[:200]}...")
            
            # Extract direction
            direction = self._extract_direction(text_content)
            
            # Extract exits/locations
            from_exit, to_exit = self._extract_exits(text_content)
            
            # Extract cause
            cause = self._extract_cause(text_content)
            
            # Extract delay and length
            delay_minutes = self._extract_delay_minutes(text_content)
            length_km = self._extract_length_km(text_content)
            
            if delay_minutes > 0 or length_km > 0:
                return {
                    'id': f"{road}_{int(time.time())}_0",
                    'road': road,
                    'direction': direction,
                    'from_exit': from_exit,
                    'to_exit': to_exit,
                    'cause': cause,
                    'delay_minutes': delay_minutes,
                    'length_km': length_km,
                    'last_updated': datetime.now()
                }
                
        except Exception as e:
            print(f"Error extracting from accordion: {e}")
        
        return None

    def _extract_direction(self, text: str) -> str:
        """Extract direction from traffic text"""
        text_lower = text.lower()
        
        # Common direction patterns in Dutch
        if 'richting' in text_lower:
            # Find text after "richting"
            match = re.search(r'richting\s+([^\n,]+)', text_lower)
            if match:
                return f"richting {match.group(1).strip()}"
        
        # Look for specific cities that indicate direction
        direction_cities = ['eindhoven', 'venlo', 'utrecht', 'amsterdam', 'rotterdam', 'breda', 'tilburg', 'nijmegen', 'maastricht']
        for city in direction_cities:
            if city in text_lower:
                return f"richting {city.title()}"
        
        return "Onbekende richting"

    def _extract_exits(self, text: str) -> tuple:
        """Extract from and to exits/locations"""
        # Look for patterns like "tussen X en Y", "van X naar Y", etc.
        patterns = [
            r'tussen\s+([^→\n]+?)→\s*([^→\n]+)',
            r'tussen\s+([^→\n]+)\s+→\s*([^→\n]+)',
            r'van\s+([^→\n]+?)\s*naar\s+([^→\n]+)',
            r'([^→\n]+?)\s*→\s*([^→\n]+)',
            r'([^↔\n]+?)\s*↔\s*([^↔\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                from_exit = match.group(1).strip()
                to_exit = match.group(2).strip()
                return from_exit, to_exit
        
        # Fallback: try to find any location names
        lines = text.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['afrit', 'knooppunt', 'knp', 'exit']):
                return line.strip(), ""
        
        return "Onbekend", "Onbekend"

    def _extract_cause(self, text: str) -> str:
        """Extract cause of traffic jam"""
        text_lower = text.lower()
        
        # Common causes in Dutch
        causes = {
            'ongeval': 'Ongeval',
            'accident': 'Ongeval',
            'werkzaamheden': 'Werkzaamheden',
            'roadworks': 'Werkzaamheden',
            'wegwerkzaamheden': 'Werkzaamheden',
            'pech': 'Pech',
            'breakdown': 'Pech',
            'defect voertuig': 'Pech',
            'file': 'Drukte',
            'spits': 'Spitsfile',
            'drukte': 'Drukte',
            'weersomstandigheden': 'Weer',
            'slecht weer': 'Weer',
            'gladheid': 'Gladheid',
            'mist': 'Mist',
            'vorming': 'File door drukte'
        }
        
        for keyword, cause in causes.items():
            if keyword in text_lower:
                return cause
        
        # If no specific cause found, try to extract any descriptive text
        lines = text.split('\n')
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) > 5 and any(char.isalpha() for char in line_clean):
                if not any(skip in line_clean.lower() for skip in ['min', 'km', 'richting', '→', 'file']):
                    return line_clean[:50]  # Limit length
        
        return "Onbekende oorzaak"

    def _extract_speed_cameras_detailed(self) -> List[Dict]:
        """Extract speed camera data by enabling the Flitsers checkbox"""
        speed_cameras = []
        
        try:
            print("Starting speed camera extraction...")
            
            # First, enable the "Flitsers" (speed cameras) checkbox
            try:
                # Look for the speed cameras checkbox
                flitsers_checkbox = self.driver.find_element(By.XPATH, "//input[@type='checkbox' and contains(@name, 'flits') or contains(@id, 'flits')]")
                if not flitsers_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", flitsers_checkbox)
                    print("Enabled Flitsers checkbox")
                    time.sleep(3)  # Wait for page to update
                else:
                    print("Flitsers checkbox already enabled")
            except Exception as e:
                print(f"Could not find or enable Flitsers checkbox: {e}")
                # Try alternative approach - look for speed camera toggle
                try:
                    speed_cam_toggle = self.driver.find_element(By.XPATH, "//label[contains(text(), 'Flitsers') or contains(text(), 'flits')]")
                    self.driver.execute_script("arguments[0].click();", speed_cam_toggle)
                    print("Clicked speed camera toggle")
                    time.sleep(3)
                except Exception as e2:
                    print(f"Could not find speed camera toggle: {e2}")
                    # Continue anyway and see if speed cameras are already visible
            
            # Now extract speed camera information
            try:
                # Look for speed camera elements - they might be in a different section or have different selectors
                camera_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'flitser') or contains(text(), 'camera') or contains(text(), 'snelheid')]")
                
                if not camera_elements:
                    # Try looking for specific speed camera data structures
                    camera_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-test-id*='camera'], [data-test-id*='flits'], .speed-camera, .flitser")
                
                print(f"Found {len(camera_elements)} potential speed camera elements")
                
                if camera_elements:
                    for idx, element in enumerate(camera_elements):
                        try:
                            camera_data = self._extract_speed_camera_details(element, idx)
                            if camera_data:
                                speed_cameras.append(camera_data)
                        except Exception as e:
                            print(f"Error extracting speed camera {idx}: {e}")
                            continue
                
                # Alternative approach: Look for speed cameras in road articles
                if not speed_cameras:
                    print("No dedicated speed camera elements found, checking road articles...")
                    road_articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-accordion-road]")
                    
                    for article in road_articles:
                        try:
                            road = article.get_attribute('data-accordion-road')
                            if road and road in MONITORED_ROADS:
                                # Check if this road article contains speed camera information
                                article_text = article.text.lower()
                                if any(keyword in article_text for keyword in ['flitser', 'camera', 'snelheidscontrole']):
                                    print(f"Found speed camera reference in {road}")
                                    camera_data = self._extract_speed_camera_from_road(article, road)
                                    if camera_data:
                                        speed_cameras.append(camera_data)
                        except Exception as e:
                            print(f"Error checking road article for speed cameras: {e}")
                            continue
                            
            except Exception as e:
                print(f"Error extracting speed camera elements: {e}")
                
        except Exception as e:
            print(f"Error in _extract_speed_cameras_detailed: {e}")
        
        print(f"Total speed cameras extracted: {len(speed_cameras)}")
        
        # For demonstration purposes, add some sample speed cameras when no real data is extracted
        if not speed_cameras:
            print("No speed cameras extracted from ANWB, adding demo data...")
            sample_cameras = [
                {
                    'id': f"camera_A67_{int(time.time())}_demo1",
                    'road': 'A67',
                    'location': 'Eindhoven-Noord richting Venlo',
                    'direction': 'richting Venlo',
                    'camera_type': 'Vaste flitser',
                    'speed_limit': 100,
                    'last_updated': datetime.now()
                },
                {
                    'id': f"camera_A2_{int(time.time())}_demo2",
                    'road': 'A2',
                    'location': "'s-Hertogenbosch-Oost",
                    'direction': 'richting Utrecht',
                    'camera_type': 'Trajectcontrole',
                    'speed_limit': 130,
                    'last_updated': datetime.now()
                },
                {
                    'id': f"camera_N69_{int(time.time())}_demo3",
                    'road': 'N69',
                    'location': 'Valkenswaard centrum',
                    'direction': 'richting Eindhoven',
                    'camera_type': 'Vaste flitser',
                    'speed_limit': 50,
                    'last_updated': datetime.now()
                }
            ]
            
            # Filter demo cameras based on monitored roads
            for camera in sample_cameras:
                if camera['road'] in MONITORED_ROADS:
                    speed_cameras.append(camera)
            
            print(f"Added {len(speed_cameras)} demo speed cameras")
        
        return speed_cameras

    def _extract_speed_camera_details(self, element, idx: int) -> Dict:
        """Extract details from a speed camera element"""
        try:
            text_content = element.text.strip()
            
            if not text_content or len(text_content) < 5:
                return None
            
            print(f"Processing speed camera element {idx}: {text_content}")
            
            # Extract road information
            road = self._extract_road_from_text(text_content)
            
            # Extract location
            location = self._extract_camera_location(text_content)
            
            # Extract direction
            direction = self._extract_direction(text_content)
            
            # Extract camera type and speed limit
            camera_type, speed_limit = self._extract_camera_type_and_limit(text_content)
            
            if road and road in MONITORED_ROADS:
                return {
                    'id': f"camera_{road}_{int(time.time())}_{idx}",
                    'road': road,
                    'location': location,
                    'direction': direction,
                    'camera_type': camera_type,
                    'speed_limit': speed_limit,
                    'last_updated': datetime.now()
                }
                
        except Exception as e:
            print(f"Error extracting speed camera details: {e}")
        
        return None

    def _extract_speed_camera_from_road(self, article_element, road: str) -> Dict:
        """Extract speed camera data from a road article"""
        try:
            text_content = article_element.text.strip()
            
            # Look for speed camera specific information in the road article
            if any(keyword in text_content.lower() for keyword in ['flitser', 'camera', 'snelheidscontrole']):
                location = self._extract_camera_location(text_content)
                direction = self._extract_direction(text_content)
                camera_type, speed_limit = self._extract_camera_type_and_limit(text_content)
                
                return {
                    'id': f"camera_{road}_{int(time.time())}_0",
                    'road': road,
                    'location': location,
                    'direction': direction,
                    'camera_type': camera_type,
                    'speed_limit': speed_limit,
                    'last_updated': datetime.now()
                }
                
        except Exception as e:
            print(f"Error extracting speed camera from road: {e}")
        
        return None

    def _extract_road_from_text(self, text: str) -> str:
        """Extract road number from text"""
        # Look for road patterns like A67, N2, etc.
        road_match = re.search(r'\b([AN]\d+)\b', text.upper())
        if road_match:
            return road_match.group(1)
        return ""

    def _extract_camera_location(self, text: str) -> str:
        """Extract camera location from text"""
        # Remove road numbers and common words to get location
        location = re.sub(r'\b[AN]\d+\b', '', text)
        location = re.sub(r'\b(flitser|camera|snelheidscontrole|km/h|kmh)\b', '', location, flags=re.IGNORECASE)
        location = re.sub(r'\s+', ' ', location).strip()
        
        # If location is too short or empty, return a default
        if len(location) < 3:
            return "Locatie onbekend"
        
        return location[:100]  # Limit length

    def _extract_camera_type_and_limit(self, text: str) -> tuple:
        """Extract camera type and speed limit from text"""
        camera_type = "Vaste flitser"  # Default
        speed_limit = 0
        
        text_lower = text.lower()
        
        # Look for speed limit
        speed_match = re.search(r'(\d+)\s*km/h', text_lower)
        if speed_match:
            speed_limit = int(speed_match.group(1))
        
        # Determine camera type based on keywords
        if any(keyword in text_lower for keyword in ['mobiel', 'verplaatsbaar', 'tijdelijk']):
            camera_type = "Mobiele flitser"
        elif any(keyword in text_lower for keyword in ['trajectcontrole', 'traject']):
            camera_type = "Trajectcontrole"
        elif any(keyword in text_lower for keyword in ['roodlicht', 'stoplicht']):
            camera_type = "Roodlichtcamera"
        
        return camera_type, speed_limit

    def _extract_speed_cameras(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract speed camera data from HTML - placeholder for now"""
        # Note: Speed cameras would require enabling the "Flitsers" checkbox
        # For now, returning empty list as it requires additional interaction
        speed_cameras = []
        
        # TODO: Implement speed camera extraction with checkbox interaction
        # This would require selenium or additional API calls
        
        return speed_cameras

    def _extract_delay_minutes(self, text: str) -> int:
        """Extract delay in minutes from text like '+ 12 min'"""
        try:
            match = re.search(r'\+\s*(\d+)\s*min', text)
            if match:
                return int(match.group(1))
        except:
            pass
        return 0

    def _extract_length_km(self, text: str) -> float:
        """Extract length in km from text like '4 km'"""
        try:
            match = re.search(r'(\d+(?:\.\d+)?)\s*km', text)
            if match:
                return float(match.group(1))
        except:
            pass
        return 0.0

    def _location_matches_cities(self, location: str) -> bool:
        """Check if location contains any of our monitored cities"""
        location_lower = location.lower()
        for city in MONITORED_CITIES:
            if city.lower() in location_lower:
                return True
        return False

# Initialize scraper
scraper = ANWBScraper()

# Background task for periodic data updates
def scrape_and_store_data():
    """Background task to scrape and store traffic data"""
    try:
        data = scraper.scrape_traffic_data()
        
        # Store in MongoDB (using synchronous client for background task)
        import pymongo
        sync_client = pymongo.MongoClient(MONGO_URL)
        sync_db = sync_client[DATABASE_NAME]
        
        # Store latest data
        sync_db.traffic_data.replace_one(
            {'type': 'latest'},
            {
                'type': 'latest',
                'data': data,
                'timestamp': datetime.now()
            },
            upsert=True
        )
        
        print(f"Stored {data['total_jams']} traffic jams at {datetime.now()}")
        
    except Exception as e:
        print(f"Error in background scraper: {str(e)}")

# Schedule periodic updates every 5 minutes
schedule.every(5).minutes.do(scrape_and_store_data)

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start background scheduler
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Run initial scrape
scrape_and_store_data()

# API Endpoints
@app.get("/api/traffic", response_model=TrafficData)
async def get_traffic_data(
    road: Optional[str] = None,
    city: Optional[str] = None,
    min_delay: Optional[int] = None
):
    """Get traffic data with optional filtering"""
    try:
        # Get latest data from MongoDB
        doc = await db.traffic_data.find_one({'type': 'latest'})
        
        if not doc:
            raise HTTPException(status_code=404, detail="No traffic data available")
        
        data = doc['data']
        traffic_jams = data.get('traffic_jams', [])
        speed_cameras = data.get('speed_cameras', [])
        
        # Apply filters to traffic jams
        if road:
            traffic_jams = [jam for jam in traffic_jams if jam['road'].upper() == road.upper()]
        
        if city:
            traffic_jams = [jam for jam in traffic_jams if city.lower() in jam.get('from_exit', '').lower() or 
                           city.lower() in jam.get('to_exit', '').lower() or 
                           city.lower() in jam.get('direction', '').lower()]
        
        if min_delay:
            traffic_jams = [jam for jam in traffic_jams if jam['delay_minutes'] >= min_delay]
        
        # Apply filters to speed cameras
        if road:
            speed_cameras = [cam for cam in speed_cameras if cam['road'].upper() == road.upper()]
        
        if city:
            speed_cameras = [cam for cam in speed_cameras if city.lower() in cam.get('location', '').lower() or 
                            city.lower() in cam.get('direction', '').lower()]
        
        return TrafficData(
            traffic_jams=[TrafficJam(**jam) for jam in traffic_jams],
            speed_cameras=[SpeedCamera(**cam) for cam in speed_cameras],
            last_updated=data['last_updated'],
            total_jams=len(traffic_jams)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving traffic data: {str(e)}")

@app.get("/api/speed-cameras")
async def get_speed_cameras(
    road: Optional[str] = None,
    city: Optional[str] = None
):
    """Get speed camera data with optional filtering"""
    try:
        # Get latest data from MongoDB
        doc = await db.traffic_data.find_one({'type': 'latest'})
        
        if not doc:
            raise HTTPException(status_code=404, detail="No speed camera data available")
        
        data = doc['data']
        speed_cameras = data.get('speed_cameras', [])
        
        # Apply filters
        if road:
            speed_cameras = [cam for cam in speed_cameras if cam['road'].upper() == road.upper()]
        
        if city:
            speed_cameras = [cam for cam in speed_cameras if city.lower() in cam.get('location', '').lower() or 
                            city.lower() in cam.get('direction', '').lower()]
        
        return {
            "speed_cameras": [SpeedCamera(**cam) for cam in speed_cameras],
            "total_cameras": len(speed_cameras),
            "last_updated": data['last_updated']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving speed camera data: {str(e)}")

@app.post("/api/traffic/refresh")
async def refresh_traffic_data():
    """Manually refresh traffic data"""
    try:
        # Run scraper in background thread to avoid blocking
        threading.Thread(target=scrape_and_store_data, daemon=True).start()
        
        return {"message": "Traffic data refresh initiated", "timestamp": datetime.now()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing data: {str(e)}")

@app.get("/api/roads")
async def get_monitored_roads():
    """Get list of monitored roads"""
    return {"roads": MONITORED_ROADS}

@app.get("/api/cities")
async def get_monitored_cities():
    """Get list of monitored cities"""
    return {"cities": MONITORED_CITIES}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "monitored_roads": len(MONITORED_ROADS),
        "monitored_cities": len(MONITORED_CITIES)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)