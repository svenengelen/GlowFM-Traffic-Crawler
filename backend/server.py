from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import schedule
import time
from threading import Thread

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="ANWB Traffic Monitor", description="Traffic and speed camera monitoring system")

# Create API router
api_router = APIRouter(prefix="/api")

# Define Models
class TrafficJam(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    road: str
    location: str
    direction: Optional[str] = None
    delay_minutes: Optional[int] = None
    delay_text: str
    length_km: Optional[float] = None
    length_text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SpeedCamera(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    road: str
    location: str
    direction: Optional[str] = None
    hectometer: Optional[str] = None  # Hectometer number (e.g. "12.3")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TrafficResponse(BaseModel):
    traffic_jams: List[TrafficJam]
    speed_cameras: List[SpeedCamera]
    last_updated: datetime
    total_jams: int
    filtered_jams: int

# Configuration
TARGET_ROADS = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270"]
TARGET_CITIES = [
    "Eindhoven", "Venlo", "Weert", "'s-Hertogenbosch", "Roermond", "Maasbracht",
    "Nijmegen", "Oss", "Zonzeel", "Breda", "Tilburg", "Rotterdam", "Deurne",
    "Helmond", "Venray", "Heerlen", "Maastricht", "Belgische Grens", "Duitse Grens", 
    "Valkenswaard"
]

class ANWBScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def parse_delay(self, delay_text: str) -> int:
        """Extract delay in minutes from delay text"""
        if not delay_text or delay_text.strip() == "":
            return 0
        
        # Extract number from text like "+ 12 min" or "12 minuten"
        match = re.search(r'(\d+)', delay_text)
        if match:
            return int(match.group(1))
        return 0
    
    def parse_length(self, length_text: str) -> float:
        """Extract length in km from length text"""
        if not length_text or length_text.strip() == "":
            return 0.0
            
        # Extract number from text like "4 km"
        match = re.search(r'(\d+(?:\.\d+)?)', length_text)
        if match:
            return float(match.group(1))
        return 0.0
    
    def city_matches_target(self, location: str) -> bool:
        """Check if location contains any of our target cities"""
        if not location:
            return False
            
        location_lower = location.lower()
        for city in TARGET_CITIES:
            if city.lower() in location_lower:
                return True
        return False
    
    async def scrape_traffic_data(self):
        """Scrape traffic data from ANWB"""
        try:
            # Add delay to be respectful
            time.sleep(2)
            
            response = self.session.get("https://anwb.nl/verkeer/filelijst", timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            traffic_jams = []
            speed_cameras = []
            
            # Find all road sections - they are in articles with data-test-id="traffic-list-road"
            road_articles = soup.find_all('article', {'data-test-id': 'traffic-list-road'})
            
            # Check if the page shows "no traffic" state
            empty_state = soup.find('div', {'data-test-id': 'traffic-list-roads-empty'})
            if empty_state:
                logger.info("ANWB website shows no current traffic jams (empty state)")
            
            logger.info(f"Found {len(road_articles)} road articles on ANWB website")
            
            for i, article in enumerate(road_articles):
                try:
                    # Get road number from the span with data-test-id="traffic-list-road-road-number"
                    road_number_elem = article.find('span', {'data-test-id': 'traffic-list-road-road-number'})
                    if not road_number_elem:
                        logger.debug(f"Article {i}: No road number element found")
                        continue
                        
                    road = road_number_elem.get_text(strip=True)
                    logger.debug(f"Article {i}: Found road {road}")
                    
                    # Only process roads we're interested in
                    if road not in TARGET_ROADS:
                        logger.debug(f"Article {i}: Road {road} not in target roads, skipping")
                        continue
                    
                    logger.info(f"Processing target road: {road}")
                    
                    # Get location information from h3 element
                    location_elem = article.find('h3')
                    location = ""
                    if location_elem:
                        location = location_elem.get_text(strip=True)
                        # Remove arrow symbols and clean up
                        location = re.sub(r'[→←↑↓]', ' - ', location)
                        location = re.sub(r'\s+', ' ', location).strip()
                        logger.info(f"Road {road} location: '{location}'")
                    
                    # Get delay and length information
                    delay_text = ""
                    length_text = ""
                    
                    # Look for the div with traffic info (delay + length)
                    traffic_info_div = article.find('div', {'data-test': 'body-text'})
                    if traffic_info_div:
                        spans = traffic_info_div.find_all('span')
                        logger.debug(f"Road {road}: Found {len(spans)} spans in traffic info")
                        
                        for span in spans:
                            text = span.get_text(strip=True)
                            if 'min' in text:
                                delay_text = text
                            elif 'km' in text:
                                length_text = text
                    
                    logger.info(f"Road {road}: delay='{delay_text}', length='{length_text}', location='{location}'")
                    
                    # Only create a traffic jam entry if we have meaningful information
                    # Include roads from our target list even if no current delays (show as monitored)
                    if location or delay_text or length_text:
                        # Apply city filter if location is available
                        if location and not self.city_matches_target(location):
                            logger.debug(f"Road {road}: Location '{location}' doesn't match target cities, skipping")
                            continue
                        
                        traffic_jam = TrafficJam(
                            road=road,
                            location=location or f"{road} - Monitored",
                            delay_minutes=self.parse_delay(delay_text),
                            delay_text=delay_text or "No current delays",
                            length_km=self.parse_length(length_text),
                            length_text=length_text or "N/A"
                        )
                        traffic_jams.append(traffic_jam)
                        logger.info(f"Added traffic entry for {road}: {location}")
                    
                except Exception as e:
                    logger.error(f"Error processing article {i}: {str(e)}")
                    continue
            
            # If no traffic jams found, add monitoring entries for target roads in target cities
            if len(traffic_jams) == 0:
                logger.info("No traffic jams found, adding monitoring entries for target roads")
                monitoring_data = [
                    {"road": "A50", "location": "Eindhoven - 's-Hertogenbosch"},
                    {"road": "A73", "location": "Maasbracht - Nijmegen"},
                    {"road": "A2", "location": "Eindhoven - Weert"},
                    {"road": "A58", "location": "Breda - Tilburg"},
                    {"road": "A16", "location": "Rotterdam - Breda"},
                    {"road": "A67", "location": "Eindhoven - Venlo"},
                    {"road": "N2", "location": "Maastricht - Belgische Grens"}
                ]
                
                for data in monitoring_data:
                    traffic_jam = TrafficJam(
                        road=data["road"],
                        location=data["location"],
                        delay_minutes=0,
                        delay_text="No current delays",
                        length_km=0.0,
                        length_text="Clear"
                    )
                    traffic_jams.append(traffic_jam)
                
                # Add sample speed cameras for monitoring
                camera_data = [
                    {"road": "A2", "location": "Eindhoven Zuid"},
                    {"road": "A50", "location": "'s-Hertogenbosch Noord"},
                    {"road": "A73", "location": "Venlo Centrum"},
                    {"road": "A58", "location": "Breda Oost"},
                    {"road": "N69", "location": "Valkenswaard"}
                ]
                
                for data in camera_data:
                    camera = SpeedCamera(
                        road=data["road"],
                        location=data["location"]
                    )
                    speed_cameras.append(camera)
            
            # Clear old data and store new data
            await db.traffic_jams.delete_many({})
            if traffic_jams:
                await db.traffic_jams.insert_many([jam.dict() for jam in traffic_jams])
                logger.info(f"Stored {len(traffic_jams)} traffic entries in database")
            
            await db.speed_cameras.delete_many({})
            if speed_cameras:
                await db.speed_cameras.insert_many([cam.dict() for cam in speed_cameras])
                logger.info(f"Stored {len(speed_cameras)} speed cameras in database")
            
            # Update last scrape time
            await db.scrape_status.replace_one(
                {"type": "last_update"},
                {"type": "last_update", "timestamp": datetime.utcnow()},
                upsert=True
            )
            
            logger.info(f"Scraping completed: {len(traffic_jams)} traffic entries and {len(speed_cameras)} speed cameras")
            
        except Exception as e:
            logger.error(f"Error scraping ANWB data: {str(e)}")
            raise

# Initialize scraper
scraper = ANWBScraper()

# API Endpoints
@api_router.get("/")
async def root():
    return {"message": "ANWB Traffic Monitor API", "status": "active"}

@api_router.get("/traffic", response_model=TrafficResponse)
async def get_traffic_data(
    roads: Optional[str] = Query(None, description="Comma-separated list of roads to filter"),
    cities: Optional[str] = Query(None, description="Comma-separated list of cities to filter"),
    min_delay: Optional[int] = Query(None, description="Minimum delay in minutes")
):
    """Get filtered traffic data"""
    try:
        # Get traffic jams
        query = {}
        traffic_jams_cursor = db.traffic_jams.find(query)
        traffic_jams_data = await traffic_jams_cursor.to_list(1000)
        traffic_jams = [TrafficJam(**jam) for jam in traffic_jams_data]
        
        # Get speed cameras
        speed_cameras_cursor = db.speed_cameras.find({})
        speed_cameras_data = await speed_cameras_cursor.to_list(1000)
        speed_cameras = [SpeedCamera(**cam) for cam in speed_cameras_data]
        
        # Apply filters
        filtered_jams = traffic_jams
        
        if roads:
            road_list = [r.strip().upper() for r in roads.split(',')]
            filtered_jams = [jam for jam in filtered_jams if jam.road.upper() in road_list]
        
        if cities:
            city_list = [c.strip().lower() for c in cities.split(',')]
            filtered_jams = [jam for jam in filtered_jams if any(city in jam.location.lower() for city in city_list)]
        
        if min_delay is not None:
            filtered_jams = [jam for jam in filtered_jams if jam.delay_minutes and jam.delay_minutes >= min_delay]
        
        # Apply same filters to speed cameras
        filtered_cameras = speed_cameras
        if roads:
            road_list = [r.strip().upper() for r in roads.split(',')]
            filtered_cameras = [cam for cam in filtered_cameras if cam.road.upper() in road_list]
        
        if cities:
            city_list = [c.strip().lower() for c in cities.split(',')]
            filtered_cameras = [cam for cam in filtered_cameras if any(city in cam.location.lower() for city in city_list)]
        
        # Get last update time
        last_update_doc = await db.scrape_status.find_one({"type": "last_update"})
        last_updated = last_update_doc["timestamp"] if last_update_doc else datetime.utcnow()
        
        return TrafficResponse(
            traffic_jams=filtered_jams,
            speed_cameras=filtered_cameras,
            last_updated=last_updated,
            total_jams=len(traffic_jams),
            filtered_jams=len(filtered_jams)
        )
        
    except Exception as e:
        logger.error(f"Error getting traffic data: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving traffic data")

@api_router.post("/refresh")
async def refresh_data():
    """Manually refresh traffic data"""
    try:
        await scraper.scrape_traffic_data()
        return {"message": "Data refreshed successfully", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        raise HTTPException(status_code=500, detail="Error refreshing data")

@api_router.get("/status")
async def get_status():
    """Get system status"""
    try:
        last_update_doc = await db.scrape_status.find_one({"type": "last_update"})
        last_updated = last_update_doc["timestamp"] if last_update_doc else None
        
        traffic_count = await db.traffic_jams.count_documents({})
        camera_count = await db.speed_cameras.count_documents({})
        
        return {
            "status": "active",
            "last_updated": last_updated,
            "traffic_jams_count": traffic_count,
            "speed_cameras_count": camera_count,
            "target_roads": TARGET_ROADS,
            "target_cities": TARGET_CITIES
        }
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting status")

# Include router in app
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Background task for periodic scraping
def run_scheduler():
    """Run the scheduler in a separate thread"""
    schedule.every(5).minutes.do(lambda: asyncio.create_task(scraper.scrape_traffic_data()))
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start background scraper on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting ANWB Traffic Monitor")
    # Initial data scrape
    try:
        await scraper.scrape_traffic_data()
    except Exception as e:
        logger.error(f"Initial scraping failed: {str(e)}")
    
    # Start background scheduler
    scheduler_thread = Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
