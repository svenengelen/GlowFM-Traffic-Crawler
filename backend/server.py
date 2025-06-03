import os
import time
import asyncio
import requests
import uuid
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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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

    def _create_optimized_driver(self) -> webdriver.Chrome:
        """Create optimized Chrome driver with enhanced error handling and fallback mechanisms"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"Creating Chrome driver (attempt {attempt + 1}/{max_retries})...")
                
                options = webdriver.ChromeOptions()
                
                # Core options for stability and performance
                essential_options = [
                    '--headless=new',
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-features=VizDisplayCompositor'
                ]
                
                # Performance optimizations with error handling
                performance_options = [
                    '--disable-web-security',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-background-timer-throttling',
                    '--disable-client-side-phishing-detection',
                    '--disable-default-apps',
                    '--disable-hang-monitor',
                    '--disable-popup-blocking',
                    '--disable-prompt-on-repost',
                    '--disable-sync',
                    '--disable-translate',
                    '--metrics-recording-only',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-blink-features=AutomationControlled'
                ]
                
                # Memory and resource optimizations  
                resource_options = [
                    '--memory-pressure-off',
                    '--max_old_space_size=4096',
                    '--aggressive-cache-discard',
                    '--disable-background-networking',
                    '--disable-component-update',
                    '--disable-domain-reliability'
                ]
                
                # Add all options with error tolerance
                all_options = essential_options + performance_options + resource_options
                for option in all_options:
                    try:
                        options.add_argument(option)
                    except Exception as e:
                        print(f"Warning: Could not add option {option}: {e}")
                
                # Enhanced user agent for better compatibility
                options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                # Window size for consistent rendering
                options.add_argument('--window-size=1920,1080')
                
                # Prefs for additional optimization
                prefs = {
                    "profile.default_content_setting_values": {
                        "images": 2,  # Block images for faster loading
                        "plugins": 2,
                        "popups": 2,
                        "geolocation": 2,
                        "notifications": 2,
                        "media_stream": 2,
                    },
                    "profile.managed_default_content_settings": {
                        "images": 2
                    }
                }
                options.add_experimental_option("prefs", prefs)
                
                # Enhanced timeouts and error handling
                try:
                    # Try to use the system-installed chromedriver first
                    service = Service(executable_path='/usr/bin/chromedriver')
                    print("Using system chromedriver: /usr/bin/chromedriver")
                except Exception as e:
                    print(f"System chromedriver failed: {e}")
                    try:
                        # Fallback to webdriver-manager
                        service = Service(ChromeDriverManager().install())
                        print("Using webdriver-manager for chromedriver")
                    except Exception as e2:
                        print(f"Webdriver-manager failed: {e2}")
                        # Last resort - try default service
                        service = ChromeService()
                        print("Using default chromedriver service")
                
                service.creation_flags = 0x08000000  # CREATE_NO_WINDOW for Windows compatibility
                
                # Create driver with timeout handling
                driver = webdriver.Chrome(service=service, options=options)
                
                # Configure enhanced timeouts with exponential backoff
                base_timeout = 10 + (attempt * 5)  # Increase timeout with retries
                driver.set_page_load_timeout(base_timeout)
                driver.implicitly_wait(base_timeout // 2)
                
                # Test driver functionality
                try:
                    driver.get("about:blank")
                    print("Driver created successfully and tested")
                    return driver
                except Exception as test_error:
                    print(f"Driver test failed: {test_error}")
                    try:
                        driver.quit()
                    except:
                        pass
                    raise test_error
                    
            except Exception as e:
                print(f"Driver creation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    print("All driver creation attempts failed")
                    raise Exception(f"Failed to create Chrome driver after {max_retries} attempts: {e}")
        
        raise Exception("Unexpected error in driver creation")

    def _debug_page_structure(self, driver, page_type="traffic") -> None:
        """Debug function to analyze current page structure"""
        try:
            print(f"\n🔍 DEBUG: Analyzing {page_type} page structure...")
            
            # Get page title and URL
            print(f"Page URL: {driver.current_url}")
            print(f"Page Title: {driver.title}")
            
            # Look for common traffic-related terms in the page
            page_source = driver.page_source.lower()
            traffic_terms = ['verkeer', 'file', 'vertraging', 'flitser', 'camera', 'snelheidscontrole']
            
            for term in traffic_terms:
                count = page_source.count(term)
                if count > 0:
                    print(f"Found '{term}': {count} times")
            
            # Check for potential data containers
            potential_containers = [
                "article", "section", "div[class*='traffic']", "div[class*='jam']", 
                "div[class*='flitser']", "ul", "li", "[data-testid]", "[data-*]"
            ]
            
            for selector in potential_containers:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector '{selector}'")
                        # Show first element's text if available
                        if elements[0].text.strip():
                            sample_text = elements[0].text.strip()[:100]
                            print(f"  Sample text: {sample_text}...")
                except:
                    continue
            
            # Look for road numbers in the page
            import re
            road_pattern = r'\b(A\d+|N\d+)\b'
            roads_found = set(re.findall(road_pattern, driver.page_source))
            if roads_found:
                print(f"Roads found in page: {list(roads_found)}")
            
        except Exception as e:
            print(f"Debug analysis failed: {e}")

    def _adaptive_traffic_extraction(self, driver) -> List[Dict]:
        """Adaptive traffic jam extraction that works with current website structure"""
        traffic_jams = []
        
        try:
            print("Starting adaptive traffic jam extraction...")
            
            # Debug current page structure
            self._debug_page_structure(driver, "traffic")
            
            # Strategy 1: Look for any elements containing traffic information
            traffic_selectors = [
                # Modern React/Vue component selectors
                "[data-testid*='traffic']", "[data-testid*='jam']", "[data-testid*='road']",
                "[class*='traffic']", "[class*='jam']", "[class*='road']", "[class*='verkeer']",
                
                # Generic content containers
                "article", "section", ".content", ".main", "#content", "#main",
                
                # List-based layouts
                "ul[class*='traffic']", "ul[class*='road']", "li[class*='traffic']", "li[class*='road']",
                
                # Card/item layouts
                ".card", ".item", ".list-item", ".traffic-item", ".road-item"
            ]
            
            all_potential_elements = []
            for selector in traffic_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        all_potential_elements.extend(elements)
                except:
                    continue
            
            # Strategy 2: Text-based search for traffic information
            print("Performing text-based traffic search...")
            
            try:
                # Search for elements containing specific traffic-related text
                traffic_xpath_patterns = [
                    "//*[contains(text(), 'vertraging')]",
                    "//*[contains(text(), 'file')]", 
                    "//*[contains(text(), 'minuten')]",
                    "//*[contains(text(), 'min')]",
                    "//*[contains(text(), 'km')]",
                    "//*[contains(text(), 'richting')]",
                ]
                
                for pattern in traffic_xpath_patterns:
                    try:
                        elements = driver.find_elements(By.XPATH, pattern)
                        all_potential_elements.extend(elements)
                        if elements:
                            print(f"Found {len(elements)} elements with pattern: {pattern}")
                    except:
                        continue
                        
            except Exception as e:
                print(f"Text-based search failed: {e}")
            
            # Strategy 3: Search for road numbers and surrounding content
            print("Searching for road-specific content...")
            
            for road in MONITORED_ROADS:
                try:
                    # Look for road numbers in text
                    road_xpath = f"//*[contains(text(), '{road}')]"
                    road_elements = driver.find_elements(By.XPATH, road_xpath)
                    
                    for element in road_elements:
                        parent = element.find_element(By.XPATH, "./..")
                        all_potential_elements.append(parent)
                        
                    if road_elements:
                        print(f"Found {len(road_elements)} elements mentioning {road}")
                        
                except:
                    continue
            
            # Process all potential elements
            print(f"Processing {len(all_potential_elements)} potential traffic elements...")
            
            processed_texts = set()
            for element in all_potential_elements:
                try:
                    element_text = element.text.strip()
                    
                    # Skip empty or very short text
                    if not element_text or len(element_text) < 10:
                        continue
                    
                    # Skip if already processed (avoid duplicates)
                    text_hash = hash(element_text[:50])
                    if text_hash in processed_texts:
                        continue
                    processed_texts.add(text_hash)
                    
                    # Check if this looks like traffic information
                    text_lower = element_text.lower()
                    
                    # Traffic indicators
                    has_delay = any(term in text_lower for term in ['min', 'minuten', 'vertraging'])
                    has_road = any(road.lower() in text_lower for road in MONITORED_ROADS)
                    has_traffic_terms = any(term in text_lower for term in ['file', 'verkeer', 'richting', 'km'])
                    
                    if (has_delay and has_road) or (has_road and has_traffic_terms):
                        print(f"Potential traffic jam found: {element_text[:100]}...")
                        
                        # Extract information from this element
                        traffic_jam = self._parse_traffic_element(element_text, element)
                        if traffic_jam:
                            traffic_jams.append(traffic_jam)
                
                except Exception as e:
                    continue
            
            print(f"Adaptive traffic extraction complete: {len(traffic_jams)} jams found")
            return traffic_jams
            
        except Exception as e:
            print(f"Error in adaptive traffic extraction: {e}")
            return []

    def _parse_traffic_element(self, text: str, element) -> Dict:
        """Parse individual traffic element with enhanced extraction"""
        try:
            # Enhanced direction extraction
            direction = self._extract_traffic_direction(text)
            
            # Enhanced cause extraction  
            cause = self._extract_traffic_cause(text)
            
            # Extract road information
            road = "Onbekend"
            for monitored_road in MONITORED_ROADS:
                if monitored_road.upper() in text.upper():
                    road = monitored_road
                    break
            
            # Extract delay information
            delay_minutes = self._extract_delay_minutes(text)
            
            # Extract length information  
            length_km = self._extract_length_km(text)
            
            # Only create traffic jam if we have meaningful delay
            if delay_minutes > 0:
                return {
                    'id': f"{road}_{int(time.time())}_{hash(text[:50])}",
                    'road': road,
                    'direction': direction,
                    'source_location': "Locatie extractie in ontwikkeling",
                    'destination_location': "Locatie extractie in ontwikkeling", 
                    'route_details': text[:200],  # Keep original text for debugging
                    'cause': cause,
                    'delay_minutes': delay_minutes,
                    'length_km': length_km,
                    'raw_text': text,  # Keep full text for enhanced processing
                    'enhanced_direction': direction,  # Use enhanced method
                    'enhanced_cause': cause,  # Use enhanced method
                    'last_updated': datetime.now()
                }
            
            return None
            
        except Exception as e:
            print(f"Error parsing traffic element: {e}")
            return None

    def _adaptive_flitser_extraction(self, driver) -> List[Dict]:
        """Adaptive flitser extraction that works with current website structure"""
        speed_cameras = []
        
        try:
            print("Starting adaptive flitser extraction...")
            
            # Debug current page structure
            self._debug_page_structure(driver, "flitser")
            
            # Strategy 1: Look for flitser-specific elements
            flitser_selectors = [
                # Modern React/Vue component selectors
                "[data-testid*='flitser']", "[data-testid*='camera']", "[data-testid*='speed']",
                "[class*='flitser']", "[class*='camera']", "[class*='speed']", "[class*='controle']",
                
                # Generic content containers
                "article", "section", ".content", ".main", "#content", "#main",
                
                # List-based layouts
                "ul[class*='flitser']", "ul[class*='camera']", "li[class*='flitser']", "li[class*='camera']",
                
                # Card/item layouts
                ".card", ".item", ".list-item", ".flitser-item", ".camera-item"
            ]
            
            all_potential_elements = []
            for selector in flitser_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        all_potential_elements.extend(elements)
                except:
                    continue
            
            # Strategy 2: Text-based search for flitser information
            print("Performing text-based flitser search...")
            
            try:
                # Search for elements containing flitser-related text
                flitser_xpath_patterns = [
                    "//*[contains(text(), 'flitser')]",
                    "//*[contains(text(), 'Flitser')]", 
                    "//*[contains(text(), 'camera')]",
                    "//*[contains(text(), 'Camera')]",
                    "//*[contains(text(), 'snelheid')]",
                    "//*[contains(text(), 'controle')]",
                    "//*[contains(text(), 'mobiel')]",
                    "//*[contains(text(), 'hectometer')]",
                    "//*[contains(text(), 'hmp')]",
                ]
                
                for pattern in flitser_xpath_patterns:
                    try:
                        elements = driver.find_elements(By.XPATH, pattern)
                        all_potential_elements.extend(elements)
                        if elements:
                            print(f"Found {len(elements)} elements with pattern: {pattern}")
                    except:
                        continue
                        
            except Exception as e:
                print(f"Text-based flitser search failed: {e}")
            
            # Strategy 3: Search for road numbers with flitser context
            print("Searching for road-specific flitser content...")
            
            for road in MONITORED_ROADS:
                try:
                    # Look for road numbers near flitser text
                    road_xpath = f"//*[contains(text(), '{road}') and (contains(text(), 'flitser') or contains(text(), 'camera') or contains(text(), 'km '))]"
                    road_elements = driver.find_elements(By.XPATH, road_xpath)
                    
                    for element in road_elements:
                        # Include parent and sibling elements that might contain more info
                        parent = element.find_element(By.XPATH, "./..")
                        all_potential_elements.append(parent)
                        all_potential_elements.append(element)
                        
                    if road_elements:
                        print(f"Found {len(road_elements)} flitser elements mentioning {road}")
                        
                except:
                    continue
            
            # Strategy 4: Look for numeric patterns that might indicate hectometer info
            print("Searching for hectometer patterns...")
            
            try:
                # Look for elements with km/hectometer patterns
                hectometer_patterns = [
                    "//*[contains(text(), 'km ') and (string-length(text()) < 200)]",
                    "//*[contains(text(), 'hmp')]",
                    "//*[contains(text(), 'hectometer')]"
                ]
                
                for pattern in hectometer_patterns:
                    try:
                        elements = driver.find_elements(By.XPATH, pattern)
                        # Only add if it also mentions roads or flitsers
                        for element in elements:
                            text = element.text.lower()
                            if any(road.lower() in text for road in MONITORED_ROADS) or 'flitser' in text:
                                all_potential_elements.append(element)
                                
                        if elements:
                            print(f"Found {len(elements)} hectometer elements with pattern: {pattern}")
                    except:
                        continue
                        
            except Exception as e:
                print(f"Hectometer search failed: {e}")
            
            # Process all potential elements
            print(f"Processing {len(all_potential_elements)} potential flitser elements...")
            
            processed_texts = set()
            for element in all_potential_elements:
                try:
                    element_text = element.text.strip()
                    
                    # Skip empty or very short text
                    if not element_text or len(element_text) < 5:
                        continue
                    
                    # Skip if already processed (avoid duplicates)
                    text_hash = hash(element_text[:50])
                    if text_hash in processed_texts:
                        continue
                    processed_texts.add(text_hash)
                    
                    # Check if this looks like flitser information
                    text_lower = element_text.lower()
                    
                    # Flitser indicators
                    has_flitser_terms = any(term in text_lower for term in ['flitser', 'camera', 'snelheid', 'controle', 'mobiel'])
                    has_road = any(road.lower() in text_lower for road in MONITORED_ROADS)
                    has_location_info = any(term in text_lower for term in ['km', 'hmp', 'hectometer', 'richting'])
                    
                    if (has_flitser_terms and has_road) or (has_flitser_terms and has_location_info):
                        print(f"Potential flitser found: {element_text[:100]}...")
                        
                        # Extract information from this element
                        flitser = self._parse_flitser_element(element_text, element)
                        if flitser:
                            speed_cameras.append(flitser)
                
                except Exception as e:
                    continue
            
            print(f"Adaptive flitser extraction complete: {len(speed_cameras)} flitsers found")
            return speed_cameras
            
        except Exception as e:
            print(f"Error in adaptive flitser extraction: {e}")
            return []

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

    async def scrape_with_performance_optimization(self) -> dict:
        """Enhanced scraping with performance optimizations and parallel processing"""
        start_time = time.time()
        
        try:
            print("Starting enhanced ANWB scraping with performance optimizations...")
            
            # Phase 1: Setup optimized driver sessions
            traffic_driver = self._create_optimized_driver()
            flitser_driver = self._create_optimized_driver() 
            
            try:
                # Phase 2: Parallel scraping setup - prepare both sessions concurrently
                print("Setting up parallel scraping sessions...")
                setup_tasks = []
                
                # Setup traffic session
                async def setup_traffic_session():
                    try:
                        traffic_driver.get("https://www.anwb.nl/verkeer")
                        self._wait_for_page_load(traffic_driver, timeout=10)
                        return True
                    except Exception as e:
                        print(f"Traffic session setup failed: {e}")
                        return False
                
                # Setup flitser session  
                async def setup_flitser_session():
                    try:
                        flitser_driver.get("https://www.anwb.nl/verkeer/flitsers")
                        self._wait_for_page_load(flitser_driver, timeout=10)
                        return True
                    except Exception as e:
                        print(f"Flitser session setup failed: {e}")
                        return False
                
                # Execute setup tasks concurrently
                import asyncio
                traffic_ready, flitser_ready = await asyncio.gather(
                    setup_traffic_session(),
                    setup_flitser_session(),
                    return_exceptions=True
                )
                
                if not traffic_ready or not flitser_ready:
                    print("Warning: Some sessions failed to initialize properly")
                
                # Phase 3: Optimized traffic jam extraction with adaptive method
                print("Extracting traffic jams with adaptive strategy...")
                traffic_start = time.time()
                traffic_jams = self._adaptive_traffic_extraction(traffic_driver)
                traffic_time = time.time() - traffic_start
                print(f"Traffic extraction completed in {traffic_time:.2f}s - Found {len(traffic_jams)} jams")
                
                # Phase 4: Optimized flitser extraction with adaptive method
                print("Extracting flitsers with adaptive strategy...")
                flitser_start = time.time()
                flitsers = self._adaptive_flitser_extraction(flitser_driver)
                flitser_time = time.time() - flitser_start
                print(f"Flitser extraction completed in {flitser_time:.2f}s - Found {len(flitsers)} flitsers")
                
                # Phase 5: Data processing and storage
                processing_start = time.time()
                
                # Process traffic jams with enhanced data
                processed_traffic = []
                for jam in traffic_jams:
                    try:
                        # Enhanced processing with new methods
                        enhanced_direction = self._extract_traffic_direction(jam.get('raw_text', ''))
                        enhanced_cause = self._extract_traffic_cause(jam.get('raw_text', ''))
                        
                        processed_jam = {
                            **jam,
                            'enhanced_direction': enhanced_direction,
                            'enhanced_cause': enhanced_cause,
                            'processing_timestamp': int(time.time())
                        }
                        processed_traffic.append(processed_jam)
                    except Exception as e:
                        print(f"Error processing traffic jam: {e}")
                        processed_traffic.append(jam)  # Keep original if processing fails
                
                # Process flitsers with enhanced location data  
                processed_flitsers = []
                for flitser in flitsers:
                    try:
                        # Enhanced processing with new methods
                        enhanced_location = self._extract_flitser_location(
                            flitser.get('raw_text', ''), 
                            flitser.get('hectometer', '')
                        )
                        
                        processed_flitser = {
                            **flitser,
                            'enhanced_location': enhanced_location,
                            'processing_timestamp': int(time.time())
                        }
                        processed_flitsers.append(processed_flitser)
                    except Exception as e:
                        print(f"Error processing flitser: {e}")
                        processed_flitsers.append(flitser)  # Keep original if processing fails
                
                processing_time = time.time() - processing_start
                print(f"Data processing completed in {processing_time:.2f}s")
                
                # Phase 6: Concurrent database storage
                storage_start = time.time()
                
                # Store data concurrently
                async def store_traffic_data():
                    try:
                        await self._store_traffic_data_batch(processed_traffic)
                        return len(processed_traffic)
                    except Exception as e:
                        print(f"Error storing traffic data: {e}")
                        return 0
                
                async def store_flitser_data():
                    try:
                        await self._store_flitser_data_batch(processed_flitsers)
                        return len(processed_flitsers)
                    except Exception as e:
                        print(f"Error storing flitser data: {e}")
                        return 0
                
                stored_traffic, stored_flitsers = await asyncio.gather(
                    store_traffic_data(),
                    store_flitser_data(),
                    return_exceptions=True
                )
                
                storage_time = time.time() - storage_start
                print(f"Data storage completed in {storage_time:.2f}s")
                
                total_time = time.time() - start_time
                
                return {
                    'success': True,
                    'traffic_jams': len(processed_traffic),
                    'flitsers': len(processed_flitsers),
                    'stored_traffic': stored_traffic if isinstance(stored_traffic, int) else 0,
                    'stored_flitsers': stored_flitsers if isinstance(stored_flitsers, int) else 0,
                    'performance': {
                        'total_time': round(total_time, 2),
                        'traffic_time': round(traffic_time, 2),
                        'flitser_time': round(flitser_time, 2), 
                        'processing_time': round(processing_time, 2),
                        'storage_time': round(storage_time, 2),
                        'avg_traffic_per_second': round(len(processed_traffic) / traffic_time, 2) if traffic_time > 0 else 0,
                        'avg_flitser_per_second': round(len(processed_flitsers) / flitser_time, 2) if flitser_time > 0 else 0
                    },
                    'timestamp': int(time.time())
                }
                
            finally:
                # Cleanup drivers
                try:
                    traffic_driver.quit()
                except:
                    pass
                try:
                    flitser_driver.quit()
                except:
                    pass
                    
        except Exception as e:
            print(f"Enhanced scraping failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'traffic_jams': 0,
                'flitsers': 0,
                'performance': {
                    'total_time': round(time.time() - start_time, 2)
                },
                'timestamp': int(time.time())
            }

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
        """Enhanced location information extraction with junction names and geographic precision"""
        try:
            location_parts = []
            
            # Enhanced junction/exit patterns with more comprehensive Dutch road infrastructure terms
            junction_patterns = [
                # Standard exits and interchanges
                r'afrit\s+(\d+[A-Za-z]?)\s*[-:]?\s*([^,\n\.;]+)',
                r'knooppunt\s+([^,\n\.;]+)',
                r'aansluiting\s+([^,\n\.;]+)', 
                r'kruising\s+([^,\n\.;]+)',
                r'rotonde\s+([^,\n\.;]+)',
                
                # Near/at location indicators
                r'bij\s+([^,\n\.;]{3,30})',
                r'ter hoogte van\s+([^,\n\.;]{3,30})',
                r'nabij\s+([^,\n\.;]{3,30})',
                r'voorbij\s+([^,\n\.;]{3,30})',
                r'voor\s+([^,\n\.;]{3,30})',
                r'richting\s+([^,\n\.;]{3,30})',
                
                # Place name patterns
                r'in\s+([A-Z][a-z]{2,20})',
                r'te\s+([A-Z][a-z]{2,20})',
                r'naar\s+([A-Z][a-z]{2,20})',
                
                # Specific road infrastructure
                r'brug\s+([^,\n\.;]+)',
                r'tunnel\s+([^,\n\.;]+)',
                r'viaduct\s+([^,\n\.;]+)',
                r'parallelweg\s+([^,\n\.;]+)',
                r'oprit\s+([^,\n\.;]+)',
                r'afrit\s+([^,\n\.;]+)',
                
                # Commercial/landmark references  
                r'tankstation\s+([^,\n\.;]+)',
                r'servicegebied\s+([^,\n\.;]+)',
                r'industrieterrein\s+([^,\n\.;]+)',
                r'bedrijventerrein\s+([^,\n\.;]+)',
            ]
            
            # Search for junction/location information
            location_found = False
            for pattern in junction_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    if pattern.startswith(r'afrit\s+(\d+'):
                        # Special handling for numbered exits
                        exit_num = match.group(1)
                        exit_name = match.group(2).strip() if len(match.groups()) > 1 else ""
                        if exit_name:
                            location_parts.append(f"afrit {exit_num} ({exit_name})")
                        else:
                            location_parts.append(f"afrit {exit_num}")
                        location_found = True
                    else:
                        # General location extraction
                        location_text = match.group(1).strip()
                        # Clean up common artifacts
                        location_text = re.sub(r'^\s*[-:]\s*', '', location_text)
                        location_text = re.sub(r'\s+', ' ', location_text)
                        
                        # Filter out very short or invalid entries
                        if len(location_text) >= 3 and not re.match(r'^\d+$', location_text):
                            # Determine the type of location reference
                            pattern_type = pattern.split('\\s+')[0].replace('r\'', '')
                            if pattern_type in ['bij', 'ter', 'nabij', 'voorbij', 'voor']:
                                location_parts.append(f"{pattern_type} {location_text}")
                            elif pattern_type in ['knooppunt', 'aansluiting', 'kruising', 'rotonde']:
                                location_parts.append(f"{pattern_type} {location_text}")
                            else:
                                location_parts.append(location_text)
                            location_found = True
            
            # Enhanced city/place detection with context
            if not location_found:
                # Look for Dutch city names (starting with capital letter)
                city_pattern = r'\b([A-Z][a-z]{2,20}(?:\s+[A-Z][a-z]{2,20})?)\b'
                city_matches = re.findall(city_pattern, text)
                
                # Common Dutch cities and towns in the monitoring area
                known_cities = {
                    'Eindhoven', 'Venlo', 'Weert', 'Helmond', 'Tilburg', 'Breda', 'Bergen', 'Roermond',
                    'Maastricht', 'Sittard', 'Heerlen', 'Geleen', 'Venray', 'Deurne', 'Uden', 'Veghel',
                    'Oss', 'Boxtel', 'Vught', 'Oisterwijk', 'Waalwijk', 'Oosterhout', 'Etten-Leur',
                    'Roosendaal', 'Bergen op Zoom', 'Terneuzen', 'Goes', 'Middelburg'
                }
                
                for city in city_matches:
                    if city in known_cities or len(city) >= 4:
                        location_parts.append(f"bij {city}")
                        break
            
            # Enhanced direction/road context extraction
            direction_context = []
            direction_patterns = [
                r'richting\s+([^,\n\.;]{3,25})',
                r'naar\s+([A-Z][a-z]{2,20})',
                r'vanuit\s+([A-Z][a-z]{2,20})',
                r'([ns]oord|[ow]est)(?:elijk)?(?:\s+richting)?',
                r'([A-Z]\d+)\s*(?:richting|naar)',
            ]
            
            for pattern in direction_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    direction_text = match.group(1).strip() if match.group(1) else match.group(0)
                    if len(direction_text) >= 2:
                        direction_context.append(direction_text)
            
            # Combine all location information
            result_parts = []
            
            # Add main location information
            if location_parts:
                # Remove duplicates while preserving order
                seen = set()
                unique_locations = []
                for loc in location_parts:
                    if loc.lower() not in seen:
                        unique_locations.append(loc)
                        seen.add(loc.lower())
                result_parts.extend(unique_locations[:2])  # Limit to 2 most relevant
            
            # Add hectometer if available and meaningful
            if hectometer and hectometer != "Hectometer onbekend":
                result_parts.append(hectometer)
            
            # Add direction context if available
            if direction_context and len(result_parts) < 3:
                result_parts.append(f"richting {direction_context[0]}")
            
            # Format final result
            if result_parts:
                return ", ".join(result_parts)
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

    async def _store_traffic_data_batch(self, traffic_data: list) -> None:
        """Store traffic data in batch with enhanced error handling"""
        if not traffic_data:
            return
        
        try:
            # Clear existing traffic data
            await self.db["traffic_jams"].delete_many({})
            
            # Insert new data in batch with enhanced fields
            enhanced_data = []
            for jam in traffic_data:
                enhanced_jam = {
                    **jam,
                    'batch_id': str(uuid.uuid4()),
                    'created_at': datetime.utcnow(),
                    'data_version': '2.0'  # Mark as enhanced version
                }
                enhanced_data.append(enhanced_jam)
            
            if enhanced_data:
                await self.db["traffic_jams"].insert_many(enhanced_data)
                print(f"Stored {len(enhanced_data)} traffic jams in batch")
            
        except Exception as e:
            print(f"Error storing traffic data batch: {e}")
            raise

    async def _store_flitser_data_batch(self, flitser_data: list) -> None:
        """Store flitser data in batch with enhanced error handling"""
        if not flitser_data:
            return
        
        try:
            # Clear existing flitser data
            await self.db["flitsers"].delete_many({})
            
            # Insert new data in batch with enhanced fields
            enhanced_data = []
            for flitser in flitser_data:
                enhanced_flitser = {
                    **flitser,
                    'batch_id': str(uuid.uuid4()),
                    'created_at': datetime.utcnow(),
                    'data_version': '2.0'  # Mark as enhanced version
                }
                enhanced_data.append(enhanced_flitser)
            
            if enhanced_data:
                await self.db["flitsers"].insert_many(enhanced_data)
                print(f"Stored {len(enhanced_data)} flitsers in batch")
            
        except Exception as e:
            print(f"Error storing flitser data batch: {e}")
            raise

    def _extract_flitsers_enhanced_parallel(self, driver) -> List[Dict]:
        """Enhanced parallel flitser extraction with improved performance"""
        try:
            print("Starting enhanced parallel flitser extraction...")
            
            # Use the existing enhanced method but with better error handling
            flitsers = self._extract_flitsers_fast(driver)
            
            # Additional processing for parallel optimization
            if flitsers:
                print(f"Successfully extracted {len(flitsers)} flitsers with enhanced parallel method")
                
                # Sort by road for better processing order
                flitsers.sort(key=lambda x: x.get('road', 'ZZZ'))
                
            return flitsers
            
        except Exception as e:
            print(f"Error in enhanced parallel flitser extraction: {e}")
            return []

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

    def _extract_traffic_cause(self, raw_text: str) -> str:
        """Enhanced traffic cause detection with comprehensive Dutch traffic terminology"""
        try:
            text = raw_text.lower()
            
            # Comprehensive traffic cause patterns with priority order
            cause_patterns = [
                # Accidents and incidents (high priority)
                (r'\b(ongeval|aanrijding|botsing|kop-staart|collision)\b', 'Ongeval'),
                (r'\b(pechgeval|autopech|liegenblije[nr]|breakdown)\b', 'Pechgeval'),
                (r'\b(brand(?:weer)?|fire)\b', 'Brand'),
                (r'\b(hulpdiensten|ambulance|politie|emergency)\b', 'Hulpdiensten'),
                
                # Roadworks and construction (high priority)
                (r'\b(wegwerkzaamheden|wegwerken|roadworks?)\b', 'Wegwerkzaamheden'),
                (r'\b(afsluiting|afgesloten|closed?|sluiting)\b', 'Afsluiting'),
                (r'\b(versmalling|versmald|rijstrook\s+dicht)\b', 'Versmalling'),
                (r'\b(onderhoud|maintenance|repair)\b', 'Onderhoud'),
                (r'\b(asfaltering|asfaltwerkzaamheden)\b', 'Asfaltering'),
                (r'\b(brug(?:werkzaamheden)?|brugopening)\b', 'Brugwerkzaamheden'),
                
                # Weather conditions (medium priority)
                (r'\b(gladheid|glad|slippery|ijs|ijzel)\b', 'Gladheid'),
                (r'\b(sneeuw|snow|sneeuwval|winter)\b', 'Sneeuw'),
                (r'\b(mist|fog|mistig|nebel|zicht)\b', 'Mist'),
                (r'\b(regen|rain|regenbui|neerslag)\b', 'Regen'),
                (r'\b(storm|wind|harde\s+wind|stormschade)\b', 'Storm'),
                (r'\b(hagel|hail|hagelslag)\b', 'Hagel'),
                
                # Traffic volume and congestion (medium priority)
                (r'\b(drukte|busy|traffic|verkeersdrukte)\b', 'Drukte'),
                (r'\b(spitsuur|rush\s*hour|ochtendspits|avondspits)\b', 'Spitsuur'),
                (r'\b(file|jam|verkeersjam|opstopping)\b', 'File'),
                (r'\b(langzaam\s+verkeer|slow\s+traffic)\b', 'Langzaam verkeer'),
                
                # Events and special circumstances (lower priority)
                (r'\b(evenement|event|manifestatie|festival)\b', 'Evenement'),
                (r'\b(markt|market|braderie)\b', 'Markt'),
                (r'\b(voetbal|football|soccer|wedstrijd|match)\b', 'Sportevenement'),
                (r'\b(demonstratie|protest|march)\b', 'Demonstratie'),
                
                # Special road situations (lower priority)
                (r'\b(omleid(?:ing)?|detour|omrijden)\b', 'Omleiding'),
                (r'\b(grenscontrole|border\s+control|douane)\b', 'Grenscontrole'),
                (r'\b(vracht(?:auto)?|truck|vrachtverkeer)\b', 'Vrachtverkeer'),
                (r'\b(landbouwverkeer|tractors?|agrarisch)\b', 'Landbouwverkeer'),
                
                # Infrastructure issues
                (r'\b(verkeerslich(?:t|ten)|traffic\s+light|stoplicht)\b', 'Verkeerslichten'),
                (r'\b(wegdek|pavement|pothole|gat\s+in\s+(?:de\s+)?weg)\b', 'Wegdekprobleem'),
                (r'\b(signaling|bebakening|afzetting)\b', 'Signalering'),
                
                # Time-specific causes
                (r'\b(nacht(?:werk)?|night\s*work)\b', 'Nachtwerk'),
                (r'\b(weekend(?:werk)?|weekend\s*work)\b', 'Weekendwerk'),
                
                # Emergency and special vehicles
                (r'\b(politie(?:actie)?|police\s+action)\b', 'Politieactie'),
                (r'\b(berging|recovery|sleepwagen|tow\s+truck)\b', 'Berging'),
                (r'\b(schade|damage|beschadig(?:d|ing))\b', 'Schade'),
            ]
            
            # Find the most specific cause
            detected_causes = []
            for pattern, cause_name in cause_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Add context information if available
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end].strip()
                    
                    detected_causes.append((cause_name, len(context), match.start()))
            
            if detected_causes:
                # Sort by priority: longest context first, then earliest position
                detected_causes.sort(key=lambda x: (-x[1], x[2]))
                primary_cause = detected_causes[0][0]
                
                # Check for combined causes (e.g., "accident due to weather")
                secondary_causes = [cause[0] for cause in detected_causes[1:3] 
                                   if cause[0] != primary_cause]
                
                if secondary_causes:
                    return f"{primary_cause} + {secondary_causes[0]}"
                else:
                    return primary_cause
            
            # Enhanced keyword analysis for implicit causes
            # Look for delay indicators that might suggest cause
            if any(word in text for word in ['vertraging', 'delay', 'slow', 'langzaam']):
                if any(word in text for word in ['druk', 'busy', 'veel', 'verkeer']):
                    return 'Drukte'
                elif any(word in text for word in ['werk', 'onderhoud', 'repair']):
                    return 'Wegwerkzaamheden'
            
            # Check for time-based indicators
            import datetime
            current_hour = datetime.datetime.now().hour
            if 7 <= current_hour <= 9 or 16 <= current_hour <= 19:
                if any(word in text for word in ['file', 'drukte', 'verkeer']):
                    return 'Spitsuur'
            
            return "Oorzaak onbekend"
            
        except Exception as e:
            print(f"Error extracting traffic cause: {e}")
            return "Oorzaak onbekend"

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

    def _extract_traffic_direction(self, raw_text: str) -> str:
        """Enhanced traffic direction extraction with better precision"""
        try:
            text = raw_text.lower()
            
            # Enhanced direction patterns with more comprehensive detection
            direction_patterns = [
                # Direct direction indicators
                (r'richting\s+([^,\n\.;]{3,25})', 'richting {}'),
                (r'naar\s+([A-Z][a-z]{2,20})', 'naar {}'),
                (r'vanuit\s+([A-Z][a-z]{2,20})', 'vanuit {}'),
                
                # Cardinal directions with context
                (r'\b(noord(?:elijk)?|noorden)\b', 'noordelijk'),
                (r'\b(zuid(?:elijk)?|zuiden)\b', 'zuidelijk'),
                (r'\b(oost(?:elijk)?|oosten)\b', 'oostelijk'),
                (r'\b(west(?:elijk)?|westen)\b', 'westelijk'),
                
                # Highway-specific directions
                (r'([A-Z]\d+)\s*richting\s*([^,\n\.;]+)', '{} richting {}'),
                (r'([A-Z]\d+)\s*naar\s*([A-Z][a-z]{2,20})', '{} naar {}'),
                
                # More specific location-based directions
                (r'([A-Z]\d+).*?(?:richting|naar)\s*([A-Z][a-z]{3,20})', '{} richting {}'),
                (r'tussen\s+([^,\n\.;]+)\s+en\s+([^,\n\.;]+)', 'tussen {} en {}'),
                
                # Exit/junction based directions
                (r'afrit\s+(\d+[A-Za-z]?)\s*[-:]?\s*([^,\n\.;]+)', 'afrit {} ({})'),
                (r'knooppunt\s+([^,\n\.;]+)', 'knooppunt {}'),
                
                # Fallback patterns for common terms
                (r'\b(linkerrijstrook|rechterrijstrook|middenstrook|vluchtstrook)\b', '{}'),
                (r'\b(beide\s+richtingen|alle\s+rijstroken)\b', '{}'),
            ]
            
            # Try each pattern in order of preference
            for pattern, format_str in direction_patterns:
                match = re.search(pattern, raw_text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 1:
                        direction = groups[0].strip()
                        if len(direction) >= 2:
                            return format_str.format(direction)
                    elif len(groups) == 2:
                        dir1, dir2 = groups[0].strip(), groups[1].strip()
                        if len(dir1) >= 1 and len(dir2) >= 2:
                            return format_str.format(dir1, dir2)
            
            # Enhanced fallback: look for city names as direction indicators
            known_cities = {
                'eindhoven', 'venlo', 'weert', 'helmond', 'tilburg', 'breda', 'bergen', 'roermond',
                'maastricht', 'sittard', 'heerlen', 'amsterdam', 'rotterdam', 'utrecht', 'den haag',
                'apeldoorn', 'arnhem', 'nijmegen', 'enschede', 'groningen', 'leeuwarden', 'zwolle'
            }
            
            # Look for city names that might indicate direction
            words = text.split()
            for i, word in enumerate(words):
                clean_word = re.sub(r'[^\w]', '', word.lower())
                if clean_word in known_cities:
                    # Check if there's a direction indicator before the city
                    if i > 0 and words[i-1].lower() in ['richting', 'naar', 'vanaf']:
                        return f"{words[i-1]} {clean_word.capitalize()}"
                    else:
                        return f"richting {clean_word.capitalize()}"
            
            return "Richting onbekend"
            
        except Exception as e:
            print(f"Error extracting traffic direction: {e}")
            return "Richting onbekend"

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

@app.post("/api/scrape-optimized")
async def scrape_optimized():
    """Enhanced scraping endpoint with performance optimizations and adaptive extraction"""
    try:
        print("Starting optimized ANWB scraping...")
        scraper = ANWBScraper()
        result = await scraper.scrape_with_performance_optimization()
        return result
    except Exception as e:
        print(f"Optimized scraping failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'traffic_jams': 0,
            'flitsers': 0,
            'timestamp': int(time.time())
        }

@app.post("/api/traffic/refresh")
async def refresh_traffic_data():
    """Manually refresh traffic data using enhanced adaptive methods"""
    try:
        print("Manual refresh requested with adaptive methods")
        scraper = ANWBScraper()
        # Use the optimized scraping method for manual refresh too
        result = await scraper.scrape_with_performance_optimization()
        return result
    except Exception as e:
        print(f"Manual refresh failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'traffic_jams': 0,
            'flitsers': 0,
            'timestamp': int(time.time())
        }

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