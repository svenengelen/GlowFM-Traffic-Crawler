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
    from_exit: str
    to_exit: str
    cause: str
    delay_minutes: int
    length_km: float
    last_updated: datetime

class SpeedCamera(BaseModel):
    id: str
    road: str
    location: str
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
            traffic_jams = self._extract_detailed_traffic_jams()
            
            # Extract speed cameras (placeholder for now)
            speed_cameras = []
            
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

    def _extract_speed_cameras(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract speed camera data from HTML"""
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
        
        # Apply filters
        if road:
            traffic_jams = [jam for jam in traffic_jams if jam['road'].upper() == road.upper()]
        
        if city:
            traffic_jams = [jam for jam in traffic_jams if city.lower() in jam['location'].lower()]
        
        if min_delay:
            traffic_jams = [jam for jam in traffic_jams if jam['delay_minutes'] >= min_delay]
        
        return TrafficData(
            traffic_jams=[TrafficJam(**jam) for jam in traffic_jams],
            speed_cameras=[SpeedCamera(**cam) for cam in data.get('speed_cameras', [])],
            last_updated=data['last_updated'],
            total_jams=len(traffic_jams)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving traffic data: {str(e)}")

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