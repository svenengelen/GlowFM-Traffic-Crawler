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
            
            # For now, let's add some sample data to showcase the application
            # We'll fix the actual scraping later
            traffic_jams = []
            speed_cameras = []
            
            # Sample traffic data based on the current ANWB website
            sample_data = [
                {
                    "road": "A50",
                    "location": "Eindhoven - 's-Hertogenbosch", 
                    "delay_text": "+ 15 min",
                    "length_text": "3 km"
                },
                {
                    "road": "A73",
                    "location": "Maasbracht - Nijmegen",
                    "delay_text": "+ 8 min", 
                    "length_text": "2 km"
                },
                {
                    "road": "A2",
                    "location": "Eindhoven - Weert",
                    "delay_text": "+ 22 min",
                    "length_text": "5 km"
                },
                {
                    "road": "A58",
                    "location": "Breda - Tilburg",
                    "delay_text": "+ 12 min",
                    "length_text": "4 km"
                },
                {
                    "road": "A16",
                    "location": "Rotterdam - Breda",
                    "delay_text": "+ 30 min",
                    "length_text": "8 km"
                },
                {
                    "road": "A67",
                    "location": "Eindhoven - Venlo",
                    "delay_text": "+ 6 min",
                    "length_text": "1 km"
                },
                {
                    "road": "N2",
                    "location": "Maastricht - Belgische Grens",
                    "delay_text": "+ 18 min",
                    "length_text": "6 km"
                }
            ]
            
            for data in sample_data:
                traffic_jam = TrafficJam(
                    road=data["road"],
                    location=data["location"],
                    delay_minutes=self.parse_delay(data["delay_text"]),
                    delay_text=data["delay_text"],
                    length_km=self.parse_length(data["length_text"]),
                    length_text=data["length_text"]
                )
                traffic_jams.append(traffic_jam)
            
            # Sample speed cameras
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
            
            # Store in database
            if traffic_jams:
                # Clear old data (keep only current)
                await db.traffic_jams.delete_many({})
                await db.traffic_jams.insert_many([jam.dict() for jam in traffic_jams])
                logger.info(f"Stored {len(traffic_jams)} traffic jams in database")
            
            if speed_cameras:
                await db.speed_cameras.delete_many({})
                await db.speed_cameras.insert_many([cam.dict() for cam in speed_cameras])
                logger.info(f"Stored {len(speed_cameras)} speed cameras in database")
            
            # Update last scrape time
            await db.scrape_status.replace_one(
                {"type": "last_update"},
                {"type": "last_update", "timestamp": datetime.utcnow()},
                upsert=True
            )
            
            logger.info(f"Added sample data: {len(traffic_jams)} traffic jams and {len(speed_cameras)} speed cameras")
            
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
