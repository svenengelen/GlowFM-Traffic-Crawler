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
    hectometer: str  # Hectometer pole information
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
        """Scrape traffic data from ANWB website using separate short sessions"""
        try:
            print(f"Starting ANWB traffic data scraping at {datetime.now()}")
            
            # Session 1: Extract traffic jams
            traffic_jams = self._scrape_traffic_jams_session()
            
            # Small delay between sessions
            time.sleep(2)
            
            # Session 2: Extract flitsers
            speed_cameras = self._scrape_flitsers_session()
            
            return {
                'traffic_jams': traffic_jams,
                'speed_cameras': speed_cameras,
                'last_updated': datetime.now(),
                'total_jams': len(traffic_jams)
            }
            
        except Exception as e:
            print(f"Error in main scraping coordinator: {str(e)}")
            return {
                'traffic_jams': [],
                'speed_cameras': [],
                'last_updated': datetime.now(),
                'total_jams': 0,
                'error': str(e)
            }

    def _scrape_traffic_jams_session(self) -> List[Dict]:
        """Dedicated short session for traffic jam extraction"""
        traffic_jams = []
        driver = None
        
        try:
            print("=== TRAFFIC JAM SESSION START ===")
            
            # Setup dedicated driver for traffic jams
            driver = self._create_driver_session("traffic_jams")
            if not driver:
                return traffic_jams
            
            # Navigate to ANWB
            driver.get(self.base_url)
            print("Navigated to ANWB website")
            
            # Wait for page load
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            time.sleep(3)
            
            # Extract traffic jams quickly
            traffic_jams = self._extract_traffic_jams_fast(driver)
            
            print(f"=== TRAFFIC JAM SESSION END - Found {len(traffic_jams)} jams ===")
            
        except Exception as e:
            print(f"Error in traffic jam session: {e}")
        finally:
            # Always cleanup driver
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        return traffic_jams

    def _scrape_flitsers_session(self) -> List[Dict]:
        """Dedicated short session for flitser extraction"""
        speed_cameras = []
        driver = None
        
        try:
            print("=== FLITSER SESSION START ===")
            
            # Setup dedicated driver for flitsers
            driver = self._create_driver_session("flitsers")
            if not driver:
                return speed_cameras
            
            # Navigate to ANWB
            driver.get(self.base_url)
            print("Navigated to ANWB website for flitsers")
            
            # Wait for page load
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)
            
            # Extract flitsers quickly
            speed_cameras = self._extract_flitsers_fast(driver)
            
            print(f"=== FLITSER SESSION END - Found {len(speed_cameras)} flitsers ===")
            
        except Exception as e:
            print(f"Error in flitser session: {e}")
        finally:
            # Always cleanup driver
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
        return speed_cameras

    def _create_driver_session(self, session_type: str):
        """Create a fresh ChromeDriver session with optimized settings"""
        try:
            print(f"Creating {session_type} driver session...")
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1280,720")  # Smaller window
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Faster loading
            chrome_options.add_argument("--disable-javascript")  # Re-enable for dynamic content
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            # Remove JavaScript disable for dynamic content
            chrome_options.arguments.remove("--disable-javascript")
            
            # Use system Chromium
            chrome_options.binary_location = "/usr/bin/chromium"
            
            # Use system chromedriver with shorter timeouts
            service = Service("/usr/bin/chromedriver")
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set shorter timeouts for faster sessions
            driver.set_page_load_timeout(20)
            driver.implicitly_wait(5)
            
            print(f"Successfully created {session_type} driver session")
            return driver
            
        except Exception as e:
            print(f"Error creating {session_type} driver session: {e}")
            return None

    def _extract_traffic_jams_fast(self, driver) -> List[Dict]:
        """Fast traffic jam extraction with minimal accordion interaction"""
        traffic_jams = []
        
        try:
            print("Starting fast traffic jam extraction...")
            
            # Find all road articles quickly
            road_articles = driver.find_elements(By.CSS_SELECTOR, "article[data-accordion-road]")
            print(f"Found {len(road_articles)} road articles")
            
            for article in road_articles:
                try:
                    # Get road number
                    road = article.get_attribute('data-accordion-road')
                    if not road or road not in MONITORED_ROADS:
                        continue
                    
                    print(f"Processing road: {road}")
                    
                    # Check if there are traffic jams (look for summary info)
                    try:
                        # Look for delay and length info in the collapsed view
                        summary_info = article.find_element(By.CSS_SELECTOR, "[class*='sc-fd0a2c7e-6'], [class*='sc-fd0a2c7e-4']")
                        summary_text = summary_info.text.strip()
                        
                        if summary_text and ('+' in summary_text or 'min' in summary_text):
                            print(f"Found traffic summary for {road}: {summary_text}")
                            
                            # Extract delay and length from summary
                            delay_minutes = self._extract_delay_minutes(summary_text)
                            length_km = self._extract_length_km(summary_text)
                            
                            if delay_minutes > 0:
                                # Try to click and get more details (but timeout quickly)
                                direction = "Onbekende richting"
                                route_details = "Route onbekend"
                                cause = "Oorzaak onbekend"
                                
                                try:
                                    # Quick click to expand
                                    button = article.find_element(By.CSS_SELECTOR, "button")
                                    driver.execute_script("arguments[0].click();", button)
                                    time.sleep(1)  # Short wait
                                    
                                    # Get expanded content quickly
                                    expanded_text = article.text
                                    direction, source_location, destination_location = self._extract_detailed_direction_and_locations(expanded_text, [])
                                    route_details = self._extract_route_details(expanded_text, [])
                                    cause = self._extract_detailed_cause(expanded_text, [])
                                    
                                except Exception as e:
                                    print(f"Could not expand {road} accordion: {e}")
                                    # Use fallback values
                                    source_location = "Onbekend"
                                    destination_location = "Onbekend"
                                
                                traffic_jam = {
                                    'id': f"{road}_{int(time.time())}_{len(traffic_jams)}",
                                    'road': road,
                                    'direction': direction,
                                    'source_location': source_location,
                                    'destination_location': destination_location,
                                    'route_details': route_details,
                                    'cause': cause,
                                    'delay_minutes': delay_minutes,
                                    'length_km': length_km,
                                    'last_updated': datetime.now()
                                }
                                traffic_jams.append(traffic_jam)
                                print(f"Added traffic jam: {road} - {delay_minutes}min, {length_km}km")
                    
                    except Exception as e:
                        print(f"No traffic summary found for {road}")
                        continue
                        
                except Exception as e:
                    print(f"Error processing road {road}: {e}")
                    continue
            
        except Exception as e:
            print(f"Error in fast traffic extraction: {e}")
        
        print(f"Fast traffic extraction complete: {len(traffic_jams)} jams found")
        return traffic_jams

    def _extract_flitsers_fast(self, driver) -> List[Dict]:
        """Enhanced flitser extraction to find more flitsers with better detection"""
        speed_cameras = []
        
        try:
            print("Starting enhanced flitser extraction...")
            
            # First, try to enable flitsers with multiple approaches
            try:
                print("Attempting to enable flitser display...")
                
                # Approach 1: Look for checkboxes
                checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                for checkbox in checkboxes:
                    try:
                        parent_text = checkbox.find_element(By.XPATH, "./..").text.lower()
                        if 'flits' in parent_text:
                            if not checkbox.is_selected():
                                driver.execute_script("arguments[0].click();", checkbox)
                                print(f"Enabled flitser checkbox: {parent_text}")
                                time.sleep(2)
                            break
                    except:
                        continue
                
                # Approach 2: Look for toggle buttons or labels
                toggles = driver.find_elements(By.XPATH, "//*[contains(text(), 'Flits') or contains(text(), 'flits')]")
                for toggle in toggles[:5]:  # Try first 5
                    try:
                        driver.execute_script("arguments[0].click();", toggle)
                        print(f"Clicked flitser toggle: {toggle.text[:30]}")
                        time.sleep(2)
                        break
                    except:
                        continue
                        
            except Exception as e:
                print(f"Could not enable flitser toggle: {e}")
            
            # Wait longer for flitser data to load
            time.sleep(3)
            
            # Enhanced container detection with multiple strategies
            try:
                print("Searching for flitser data with enhanced detection...")
                
                all_containers = []
                
                # Strategy 1: Direct text search with broader patterns
                text_selectors = [
                    "//*[contains(text(), 'flitser')]",
                    "//*[contains(text(), 'Flitser')]", 
                    "//*[contains(text(), 'camera')]",
                    "//*[contains(text(), 'Camera')]",
                    "//*[contains(text(), 'snelheid')]",
                    "//*[contains(text(), 'controle')]",
                    "//*[contains(text(), 'km ')]",  # Hectometer references
                    "//*[contains(text(), 'hmp')]",   # Hectometer pole
                ]
                
                for selector in text_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        if elements:
                            print(f"Found {len(elements)} elements with selector: {selector}")
                            all_containers.extend(elements)
                    except Exception as e:
                        print(f"Selector failed: {selector} - {e}")
                        continue
                
                # Strategy 2: Look for list items that might contain flitsers
                try:
                    list_items = driver.find_elements(By.TAG_NAME, "li")
                    for item in list_items:
                        if 'flitser' in item.text.lower() or 'camera' in item.text.lower():
                            all_containers.append(item)
                            
                    print(f"Found {len([li for li in list_items if 'flitser' in li.text.lower()])} list items with flitser content")
                except Exception as e:
                    print(f"List item search failed: {e}")
                
                # Strategy 3: Look for div containers with flitser data
                try:
                    div_containers = driver.find_elements(By.TAG_NAME, "div")
                    flitser_divs = []
                    for div in div_containers:
                        div_text = div.text.strip()
                        if (len(div_text) > 10 and len(div_text) < 200 and  # Reasonable length
                            ('flitser' in div_text.lower() or 
                             ('km ' in div_text and any(road in div_text.upper() for road in MONITORED_ROADS)))):
                            flitser_divs.append(div)
                    
                    all_containers.extend(flitser_divs)
                    print(f"Found {len(flitser_divs)} div containers with potential flitser data")
                except Exception as e:
                    print(f"Div container search failed: {e}")
                
                print(f"Total containers found: {len(all_containers)}")
                
                # Process containers with improved deduplication
                processed_texts = set()
                for idx, container in enumerate(all_containers[:50]):  # Process more containers
                    try:
                        container_text = container.text.strip()
                        
                        # Skip if empty, too short, or already processed
                        if not container_text or len(container_text) < 8:
                            continue
                            
                        # Create a more specific hash to avoid over-deduplication
                        text_hash = hash(container_text[:100])  # Use first 100 chars for hash
                        if text_hash in processed_texts:
                            continue
                        processed_texts.add(text_hash)
                        
                        print(f"Processing container {idx}:")
                        print(f"  Text preview: '{container_text[:100]}...'")
                        
                        # Try multiple extraction approaches
                        flitser_data = None
                        
                        # Approach 1: Direct flitser info extraction
                        if 'flitser' in container_text.lower():
                            flitser_data = self._extract_detailed_flitser_info(container_text, idx)
                            
                        # Approach 2: Road + km pattern (even without explicit "flitser")
                        elif any(road in container_text.upper() for road in MONITORED_ROADS) and 'km ' in container_text:
                            print(f"  Found road+km pattern, treating as potential flitser")
                            flitser_data = self._extract_detailed_flitser_info(container_text, idx)
                            
                        # Approach 3: Look for parent/sibling context
                        if not flitser_data:
                            try:
                                # Check parent element for more context
                                parent = container.find_element(By.XPATH, "./..")
                                parent_text = parent.text.strip()
                                if (len(parent_text) > len(container_text) and 
                                    ('flitser' in parent_text.lower() or 
                                     any(road in parent_text.upper() for road in MONITORED_ROADS))):
                                    print(f"  Trying parent context")
                                    flitser_data = self._extract_detailed_flitser_info(parent_text, idx)
                            except:
                                pass
                        
                        if flitser_data:
                            # Check for duplicates based on road and location
                            is_duplicate = False
                            for existing in speed_cameras:
                                if (existing['road'] == flitser_data['road'] and 
                                    existing['hectometer'] == flitser_data['hectometer']):
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                speed_cameras.append(flitser_data)
                                print(f"  ✅ Added flitser: {flitser_data['road']} - {flitser_data['hectometer']} - {flitser_data['direction']}")
                            else:
                                print(f"  ⚠️  Skipped duplicate flitser")
                        else:
                            print(f"  ❌ No flitser data extracted")
                            
                    except Exception as e:
                        print(f"Error processing container {idx}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error in enhanced flitser detection: {e}")
                
        except Exception as e:
            print(f"Error in enhanced flitser extraction: {e}")
        
        print(f"Enhanced flitser extraction complete: {len(speed_cameras)} unique flitsers found")
        return speed_cameras

    def _extract_detailed_flitser_info(self, text: str, idx: int) -> Dict:
        """Extract detailed flitser information including road, direction, and hectometer"""
        try:
            print(f"Analyzing flitser text: '{text}'")
            
            # Extract road information
            road = self._extract_road_from_text(text)
            if not road or road not in MONITORED_ROADS:
                print(f"No monitored road found in text: '{text}' (extracted road: {road})")
                return None
            
            print(f"Found monitored road: {road}")
            
            # Extract direction information
            direction = self._extract_flitser_direction(text)
            
            # Extract hectometer information  
            hectometer = self._extract_hectometer_info(text)
            
            # Extract location (combine hectometer and other location info)
            location = self._extract_flitser_location(text, hectometer)
            
            # Determine flitser type and status
            flitser_type, is_active = self._extract_flitser_type_and_status(text)
            
            # Create detailed flitser data
            flitser_data = {
                'id': f"flitser_{road}_{int(time.time())}_{idx}",
                'road': road,
                'location': location,
                'direction': direction,
                'hectometer': hectometer,
                'flitser_type': flitser_type,
                'is_active': is_active,
                'last_updated': datetime.now()
            }
            
            print(f"Created detailed flitser: {flitser_data}")
            return flitser_data
            
        except Exception as e:
            print(f"Error extracting detailed flitser info: {e}")
            return None

    def _extract_flitser_direction(self, text: str) -> str:
        """Extract direction information from flitser text"""
        try:
            text_lower = text.lower()
            
            # Look for direction patterns specific to flitsers
            direction_patterns = [
                r'richting\s+([^→\n,\.]+)',
                r'naar\s+([^→\n,\.]+)',
                r'→\s*([^→\n,\.]+)',
                r'in de richting van\s+([^→\n,\.]+)'
            ]
            
            for pattern in direction_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    direction = match.group(1).strip()
                    return f"richting {direction}"
            
            # Look for major cities in the text that indicate direction
            cities = ['eindhoven', 'venlo', 'utrecht', 'amsterdam', 'rotterdam', 'breda', 'tilburg', 'nijmegen', 'maastricht', "'s-hertogenbosch", 'weert', 'roermond']
            for city in cities:
                if city in text_lower:
                    return f"richting {city.title()}"
            
            return "Richting onbekend"
            
        except Exception as e:
            print(f"Error extracting flitser direction: {e}")
            return "Richting onbekend"

    def _extract_hectometer_info(self, text: str) -> str:
        """Enhanced hectometer pole information extraction with better precision"""
        try:
            # Enhanced hectometer patterns with more precise detection
            hectometer_patterns = [
                # Direct kilometer references
                r'km\s+(\d+(?:[,\.]\d+)?)',
                r'kilometer\s+(\d+(?:[,\.]\d+)?)',
                r'hmp\s+(\d+(?:[,\.]\d+)?)', 
                r'hectometerpaal\s+(\d+(?:[,\.]\d+)?)',
                r'kilometerpaaltje\s+(\d+(?:[,\.]\d+)?)',
                
                # Position indicators
                r'bij\s+km\s+(\d+(?:[,\.]\d+)?)',
                r'ter hoogte van\s+km\s+(\d+(?:[,\.]\d+)?)',
                r'nabij\s+km\s+(\d+(?:[,\.]\d+)?)',
                r'rond\s+km\s+(\d+(?:[,\.]\d+)?)',
                
                # Reverse patterns (number before km)
                r'(\d+(?:[,\.]\d+)?)\s*km',
                r'(\d+(?:[,\.]\d+)?)\s*kilometer',
                
                # Range patterns (between X and Y km)
                r'tussen\s+km\s+(\d+(?:[,\.]\d+)?)\s+en\s+km\s+(\d+(?:[,\.]\d+)?)',
                r'van\s+km\s+(\d+(?:[,\.]\d+)?)\s+tot\s+km\s+(\d+(?:[,\.]\d+)?)',
                
                # More specific location patterns
                r'hectometer\s+(\d+(?:[,\.]\d+)?)',
                r'hm\s+(\d+(?:[,\.]\d+)?)',
                r'km-paal\s+(\d+(?:[,\.]\d+)?)',
            ]
            
            # Try each pattern
            for pattern in hectometer_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Handle range patterns (take the middle point)
                    groups = match.groups()
                    if len(groups) == 2 and groups[1]:  # Range pattern
                        try:
                            km1 = float(groups[0].replace(',', '.'))
                            km2 = float(groups[1].replace(',', '.'))
                            avg_km = (km1 + km2) / 2
                            return f"km {avg_km:.1f} (tussen {km1}-{km2})"
                        except:
                            continue
                    else:
                        # Single value pattern
                        km_value = groups[0].replace(',', '.')  # Convert Dutch decimal
                        try:
                            km_float = float(km_value)
                            if 0 <= km_float <= 300:  # Extended reasonable range
                                return f"km {km_float}"
                        except:
                            continue
            
            # Enhanced numeric search with context validation
            text_words = text.split()
            for i, word in enumerate(text_words):
                # Look for standalone numbers that might be kilometers
                if re.match(r'^\d+(?:[,\.]\d+)?$', word):
                    try:
                        km_val = float(word.replace(',', '.'))
                        if 0 <= km_val <= 300:
                            # Check context around the number
                            context_start = max(0, i-2)
                            context_end = min(len(text_words), i+3)
                            context = ' '.join(text_words[context_start:context_end]).lower()
                            
                            # Strong context indicators
                            if any(indicator in context for indicator in ['km', 'kilometer', 'hectometer', 'paal', 'hmp']):
                                return f"km {km_val}"
                            
                            # Moderate context indicators (road-related)
                            if any(indicator in context for indicator in ['richting', 'bij', 'ter hoogte', 'nabij', 'afrit']):
                                return f"km {km_val} (geschat)"
                    except:
                        continue
            
            return "Hectometer onbekend"
            
        except Exception as e:
            print(f"Error extracting hectometer info: {e}")
            return "Hectometer onbekend"

    def _extract_flitser_location(self, text: str, hectometer: str) -> str:
        """Extract location information combining hectometer and other details"""
        try:
            # Start with hectometer if available
            location_parts = []
            
            if hectometer and hectometer != "Hectometer onbekend":
                location_parts.append(hectometer)
            
            # Look for additional location indicators
            location_indicators = [
                r'bij\s+([^→\n,\.]+)',
                r'ter hoogte van\s+([^→\n,\.]+)', 
                r'nabij\s+([^→\n,\.]+)',
                r'tussen\s+([^→\n,\.]+)',
                r'afrit\s+([^→\n,\.]+)'
            ]
            
            for pattern in location_indicators:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    location_detail = match.group(1).strip()
                    if location_detail not in [part for part in location_parts]:
                        location_parts.append(location_detail)
                    break
            
            # Combine location parts
            if location_parts:
                return " - ".join(location_parts)
            else:
                return "Locatie onbekend"
                
        except Exception as e:
            print(f"Error extracting flitser location: {e}")
            return "Locatie onbekend"

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
        """Extract detailed information from a specific traffic jam item"""
        try:
            # Get all text content from the item
            text_content = item_element.text.strip()
            
            if not text_content:
                return None
            
            print(f"Processing traffic item {idx} for {road}: {text_content}")
            
            # Try to get more detailed HTML structure for better extraction
            try:
                # Look for direction/route information in specific elements
                direction_elements = item_element.find_elements(By.CSS_SELECTOR, "[class*='direction'], [class*='route'], h3, h4")
                route_elements = item_element.find_elements(By.CSS_SELECTOR, "[class*='location'], [class*='exit'], [class*='afrit']")
                cause_elements = item_element.find_elements(By.CSS_SELECTOR, "[class*='cause'], [class*='reason'], em, i, [style*='italic']")
                
                # Extract direction and locations
                direction, source_location, destination_location = self._extract_detailed_direction_and_locations(text_content, direction_elements)
                
                # Extract route details (like "afrit panningen - venlo-noordwest")
                route_details = self._extract_route_details(text_content, route_elements)
                
                # Extract cause (cursive/italic text like "Langzaam rijdend verkeer")
                cause = self._extract_detailed_cause(text_content, cause_elements)
                
            except Exception as e:
                print(f"Error extracting detailed elements: {e}")
                # Fallback to text-based extraction
                direction, source_location, destination_location = self._extract_detailed_direction_and_locations(text_content, [])
                route_details = self._extract_route_details(text_content, [])
                cause = self._extract_detailed_cause(text_content, [])
            
            # Extract delay and length
            delay_minutes = self._extract_delay_minutes(text_content)
            length_km = self._extract_length_km(text_content)
            
            if delay_minutes > 0 or length_km > 0:
                return {
                    'id': f"{road}_{int(time.time())}_{idx}",
                    'road': road,
                    'direction': direction,
                    'source_location': source_location,
                    'destination_location': destination_location,
                    'route_details': route_details,
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
                    'source_location': from_exit,
                    'destination_location': to_exit,
                    'route_details': f"{from_exit} → {to_exit}",
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

    def _extract_detailed_direction_and_locations(self, text: str, direction_elements: list) -> tuple:
        """Extract detailed direction with source and destination locations"""
        direction = "Onbekende richting"
        source_location = "Onbekend"
        destination_location = "Onbekend"
        
        try:
            # First, try to extract from HTML elements if available
            for element in direction_elements:
                element_text = element.text.strip()
                if element_text and len(element_text) > 3:
                    # Look for direction patterns
                    if 'richting' in element_text.lower():
                        direction = element_text
                        # Extract destination from direction
                        match = re.search(r'richting\s+([^→\n,]+)', element_text)
                        if match:
                            destination_location = match.group(1).strip()
                    break
            
            # Enhanced text-based extraction with better patterns
            if direction == "Onbekende richting":
                text_lines = text.split('\n')
                
                # Look for clear direction indicators in the text
                for line in text_lines:
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    
                    # Pattern 1: "richting [city]"
                    if 'richting' in line_clean.lower():
                        match = re.search(r'richting\s+([^→\n,\.;]+)', line_clean, re.IGNORECASE)
                        if match:
                            dest = match.group(1).strip()
                            destination_location = dest
                            direction = f"richting {dest}"
                            print(f"Found direction from 'richting': {direction}")
                            break
                    
                    # Pattern 2: "naar [city]" 
                    elif 'naar' in line_clean.lower() and len(line_clean) < 50:  # Short lines more likely to be directions
                        match = re.search(r'naar\s+([^→\n,\.;]+)', line_clean, re.IGNORECASE)
                        if match:
                            dest = match.group(1).strip()
                            destination_location = dest
                            direction = f"richting {dest}"
                            print(f"Found direction from 'naar': {direction}")
                            break
                    
                    # Pattern 3: Arrow notation "A → B"
                    elif '→' in line_clean:
                        parts = line_clean.split('→')
                        if len(parts) == 2:
                            source_location = parts[0].strip()
                            destination_location = parts[1].strip()
                            direction = f"van {source_location} richting {destination_location}"
                            print(f"Found direction from arrow: {direction}")
                            break
                
                # If still no direction found, look for city names that are likely destinations
                if direction == "Onbekende richting":
                    # Major Dutch cities that are likely destinations
                    major_cities = [
                        'maastricht', 'eindhoven', 'venlo', 'utrecht', 'amsterdam', 
                        'rotterdam', 'breda', 'tilburg', 'nijmegen', "'s-hertogenbosch",
                        'weert', 'roermond', 'heerlen', 'sittard', 'geleen'
                    ]
                    
                    text_lower = text.lower()
                    for city in major_cities:
                        if city in text_lower:
                            # Check if this city appears in a context that suggests it's a destination
                            city_context = re.search(f'.{{0,30}}{city}.{{0,30}}', text_lower)
                            if city_context:
                                context = city_context.group(0)
                                if any(indicator in context for indicator in ['richting', 'naar', '→']):
                                    destination_location = city.title()
                                    direction = f"richting {destination_location}"
                                    print(f"Found direction from city context: {direction}")
                                    break
                        
        except Exception as e:
            print(f"Error extracting detailed direction: {e}")
        
        # Clean up the extracted values
        if destination_location and destination_location != "Onbekend":
            destination_location = destination_location.replace("'s-", "'s-").title()
        if source_location and source_location != "Onbekend":
            source_location = source_location.replace("'s-", "'s-").title()
        
        return direction, source_location, destination_location

    def _extract_route_details(self, text: str, route_elements: list) -> str:
        """Extract route details like 'afrit panningen - venlo-noordwest'"""
        try:
            # First, try to extract from HTML elements
            for element in route_elements:
                element_text = element.text.strip()
                if element_text and ('afrit' in element_text.lower() or 'knooppunt' in element_text.lower() or '-' in element_text):
                    return element_text
            
            # Fallback to text-based extraction
            lines = text.split('\n')
            for line in lines:
                line_clean = line.strip()
                if line_clean and any(keyword in line_clean.lower() for keyword in ['afrit', 'knooppunt', 'knp']):
                    # Clean up the line
                    route_details = re.sub(r'^(afrit|knooppunt|knp)\s*', '', line_clean, flags=re.IGNORECASE).strip()
                    if route_details:
                        return f"afrit {route_details}" if 'afrit' not in route_details.lower() else route_details
            
            # Look for patterns with dashes or arrows that might indicate route details
            route_pattern = re.search(r'([a-zA-Z][^→\n]*?-[^→\n]*?[a-zA-Z])', text)
            if route_pattern:
                return route_pattern.group(1).strip()
                
        except Exception as e:
            print(f"Error extracting route details: {e}")
        
        return "Route onbekend"

    def _extract_detailed_cause(self, text: str, cause_elements: list) -> str:
        """Extract detailed cause from cursive/italic text"""
        try:
            # First, try to extract from HTML elements (em, i, italic styles)
            for element in cause_elements:
                element_text = element.text.strip()
                if element_text and len(element_text) > 5:
                    return element_text
            
            # Fallback to text-based extraction
            lines = text.split('\n')
            for line in lines:
                line_clean = line.strip()
                
                # Look for specific Dutch traffic cause phrases
                if any(phrase in line_clean.lower() for phrase in [
                    'langzaam rijdend verkeer',
                    'file door',
                    'wegwerkzaamheden',
                    'ongeval',
                    'pech',
                    'defect voertuig',
                    'spitsfile',
                    'weersomstandigheden',
                    'gladheid',
                    'zeer druk'
                ]):
                    return line_clean
            
            # Look for any descriptive text that might be a cause
            for line in lines:
                line_clean = line.strip()
                if (len(line_clean) > 10 and 
                    not any(skip in line_clean.lower() for skip in ['min', 'km', 'richting', '→', 'afrit', 'knooppunt']) and
                    any(char.isalpha() for char in line_clean)):
                    return line_clean[:100]  # Limit length
                    
        except Exception as e:
            print(f"Error extracting detailed cause: {e}")
        
        return "Oorzaak onbekend"

    def _extract_speed_cameras_detailed(self) -> List[Dict]:
        """Extract dynamic flitsers (speed cameras) from ANWB website"""
        speed_cameras = []
        
        try:
            print("Starting dynamic flitsers extraction...")
            
            # Check if driver is still alive
            if not self.driver:
                print("No driver available for flitser extraction")
                return speed_cameras
            
            try:
                # Test driver connectivity
                current_url = self.driver.current_url
                print(f"Driver connected, current URL: {current_url}")
            except Exception as e:
                print(f"Driver connection test failed: {e}")
                return speed_cameras
            
            # First, try to enable the "Flitsers" checkbox to show dynamic speed cameras
            try:
                # Look for flitsers checkbox or toggle - be more specific
                print("Looking for flitsers toggle...")
                
                # Try multiple approaches to find flitser toggle
                flitser_found = False
                
                # Approach 1: Look for checkbox inputs
                try:
                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                    for checkbox in checkboxes:
                        try:
                            parent = checkbox.find_element(By.XPATH, "./..")
                            if 'flits' in parent.text.lower():
                                print(f"Found flitser checkbox: {parent.text}")
                                if not checkbox.is_selected():
                                    self.driver.execute_script("arguments[0].click();", checkbox)
                                    print("Enabled flitser checkbox")
                                    time.sleep(2)
                                flitser_found = True
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"Checkbox approach failed: {e}")
                
                # Approach 2: Look for labels containing "flits"
                if not flitser_found:
                    try:
                        labels = self.driver.find_elements(By.TAG_NAME, "label")
                        for label in labels:
                            if 'flits' in label.text.lower():
                                print(f"Found flitser label: {label.text}")
                                self.driver.execute_script("arguments[0].click();", label)
                                print("Clicked flitser label")
                                time.sleep(2)
                                flitser_found = True
                                break
                    except Exception as e:
                        print(f"Label approach failed: {e}")
                
                if not flitser_found:
                    print("No flitser toggle found, proceeding with available data")
                
            except Exception as e:
                print(f"Error enabling flitsers: {e}")
            
            # Now look for flitser data in the page
            try:
                print("Searching for flitser data...")
                
                # Check if driver is still alive before proceeding
                try:
                    page_source_length = len(self.driver.page_source)
                    print(f"Page source available, length: {page_source_length}")
                except Exception as e:
                    print(f"Cannot access page source: {e}")
                    return speed_cameras
                
                # Look for any elements containing flitser information
                flitser_elements = []
                
                # Try different selectors to find flitser elements
                selectors_to_try = [
                    "//*[contains(text(), 'flitser')]",
                    "//*[contains(text(), 'Flitser')]", 
                    "//*[contains(text(), 'camera')]",
                    "//*[contains(text(), 'Camera')]",
                    "//*[contains(@class, 'flitser')]",
                    "//*[contains(@class, 'camera')]"
                ]
                
                for selector in selectors_to_try:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            print(f"Found {len(elements)} elements with selector: {selector}")
                            flitser_elements.extend(elements)
                    except Exception as e:
                        print(f"Selector {selector} failed: {e}")
                        continue
                
                # Remove duplicates
                unique_elements = []
                seen_texts = set()
                for element in flitser_elements:
                    try:
                        text = element.text.strip()
                        if text and text not in seen_texts and len(text) > 3:
                            unique_elements.append(element)
                            seen_texts.add(text)
                    except:
                        continue
                
                print(f"Found {len(unique_elements)} unique flitser elements")
                
                # Process each flitser element
                for idx, element in enumerate(unique_elements):
                    try:
                        print(f"Processing flitser element {idx}")
                        flitser_data = self._extract_flitser_details(element, idx)
                        if flitser_data:
                            speed_cameras.append(flitser_data)
                            print(f"Successfully extracted flitser: {flitser_data}")
                    except Exception as e:
                        print(f"Error extracting flitser {idx}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error searching for flitser data: {e}")
                
        except Exception as e:
            print(f"Error in _extract_speed_cameras_detailed: {e}")
        
        print(f"Total dynamic flitsers extracted: {len(speed_cameras)}")
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

    def _extract_speed_camera_details(self, element, idx: int) -> Dict:
        """Legacy method - redirects to flitser extraction"""
        return self._extract_flitser_details(element, idx)

    def _extract_speed_camera_from_road(self, article_element, road: str) -> Dict:
        """Legacy method - redirects to flitser extraction"""
        return self._extract_flitser_from_road(article_element, road)

    def _extract_flitser_details(self, element, idx: int) -> Dict:
        """Extract details from a dynamic flitser element"""
        try:
            # Get text content with better error handling
            try:
                text_content = element.text.strip()
            except Exception as e:
                print(f"Error getting text from element {idx}: {e}")
                return None
            
            if not text_content or len(text_content) < 3:
                print(f"Flitser element {idx} has no meaningful text: '{text_content}'")
                return None
            
            print(f"Processing flitser element {idx}: {text_content}")
            
            # Extract road information with better patterns
            road = self._extract_road_from_text(text_content)
            
            # If no road found in text, try to find it in parent elements or nearby elements
            if not road:
                try:
                    parent = element.find_element(By.XPATH, "./..")
                    parent_text = parent.text.strip()
                    road = self._extract_road_from_text(parent_text)
                    print(f"Found road in parent: {road}")
                except:
                    pass
            
            # Only process if we found a monitored road
            if not road or road not in MONITORED_ROADS:
                print(f"No monitored road found for flitser element {idx}, road: {road}")
                return None
            
            print(f"Found monitored road: {road}")
            
            # Extract location and direction
            location = self._extract_camera_location(text_content)
            direction, _, _ = self._extract_detailed_direction_and_locations(text_content, [])
            
            # Determine flitser type and activity status
            flitser_type, is_active = self._extract_flitser_type_and_status(text_content)
            
            # Create flitser data
            flitser_data = {
                'id': f"flitser_{road}_{int(time.time())}_{idx}",
                'road': road,
                'location': location,
                'direction': direction,
                'flitser_type': flitser_type,
                'is_active': is_active,
                'last_updated': datetime.now()
            }
            
            print(f"Created flitser data: {flitser_data}")
            return flitser_data
                
        except Exception as e:
            print(f"Error extracting flitser details for element {idx}: {e}")
        
        return None

    def _extract_flitser_from_road(self, article_element, road: str) -> Dict:
        """Extract flitser data from a road article"""
        try:
            text_content = article_element.text.strip()
            
            # Look for flitser specific information in the road article
            if 'flitser' in text_content.lower():
                location = self._extract_camera_location(text_content)
                direction, _, _ = self._extract_detailed_direction_and_locations(text_content, [])
                flitser_type, is_active = self._extract_flitser_type_and_status(text_content)
                
                return {
                    'id': f"flitser_{road}_{int(time.time())}_0",
                    'road': road,
                    'location': location,
                    'direction': direction,
                    'flitser_type': flitser_type,
                    'is_active': is_active,
                    'last_updated': datetime.now()
                }
                
        except Exception as e:
            print(f"Error extracting flitser from road: {e}")
        
        return None

    def _extract_flitser_type_and_status(self, text: str) -> tuple:
        """Extract flitser type and activity status"""
        flitser_type = "Mobiele flitser"  # Default for dynamic flitsers
        is_active = True  # Assume active if mentioned
        
        text_lower = text.lower()
        
        # Determine flitser type based on keywords
        if any(keyword in text_lower for keyword in ['mobiel', 'verplaatsbaar', 'tijdelijk']):
            flitser_type = "Mobiele flitser"
        elif any(keyword in text_lower for keyword in ['actief', 'geplaatst', 'opgesteld']):
            flitser_type = "Actieve flitser"
        elif any(keyword in text_lower for keyword in ['controle', 'snelheidscontrole']):
            flitser_type = "Snelheidscontrole"
        
        # Check activity status
        if any(keyword in text_lower for keyword in ['inactief', 'weggehaald', 'gestopt', 'niet actief']):
            is_active = False
        
        return flitser_type, is_active

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
            traffic_jams = [jam for jam in traffic_jams if city.lower() in jam.get('source_location', '').lower() or 
                           city.lower() in jam.get('destination_location', '').lower() or 
                           city.lower() in jam.get('direction', '').lower() or
                           city.lower() in jam.get('route_details', '').lower()]
        
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