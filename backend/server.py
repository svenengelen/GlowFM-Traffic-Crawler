import os
import asyncio
import logging
from datetime import datetime
import time
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional
import uuid
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ANWB Traffic Monitor", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_URL)
db = client.traffic_monitor

# Data models
class TrafficJam(BaseModel):
    id: str
    road: str
    location: str
    delay_minutes: int
    length_km: float
    delay_text: str
    city: Optional[str] = None
    last_updated: datetime

class SpeedCamera(BaseModel):
    id: str
    road: str
    location: str
    city: Optional[str] = None
    last_updated: datetime

class TrafficSummary(BaseModel):
    total_jams: int
    total_cameras: int
    last_updated: datetime
    traffic_jams: List[TrafficJam]
    speed_cameras: List[SpeedCamera]

# Target roads and cities for filtering
TARGET_ROADS = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270"]
TARGET_CITIES = [
    "Eindhoven", "Venlo", "Weert", "'s-Hertogenbosch", "Roermond", "Maasbracht", 
    "Nijmegen", "Oss", "Zonzeel", "Breda", "Tilburg", "Rotterdam", "Deurne", 
    "Helmond", "Venray", "Heerlen", "Maastricht", "Belgische Grens", "Duitse Grens", "Valkenswaard"
]

def extract_delay_minutes(delay_text: str) -> int:
    """Extract delay in minutes from text like '+ 3 min' or '+ 20 min'"""
    if not delay_text:
        return 0
    
    # Remove + and extract number
    match = re.search(r'(\d+)', delay_text.replace('+', '').strip())
    if match:
        return int(match.group(1))
    return 0

def extract_length_km(length_text: str) -> float:
    """Extract length in kilometers from text like '3 km' or '4.5 km'"""
    if not length_text:
        return 0.0
        
    match = re.search(r'([\d.,]+)', length_text.replace('km', '').strip())
    if match:
        try:
            return float(match.group(1).replace(',', '.'))
        except ValueError:
            return 0.0
    return 0.0

def find_matching_city(location: str) -> Optional[str]:
    """Find if location contains any of our target cities"""
    if not location:
        return None
        
    location_lower = location.lower()
    for city in TARGET_CITIES:
        if city.lower() in location_lower:
            return city
    return None

async def scrape_traffic_data():
    """Scrape traffic data from ANWB website"""
    try:
        logger.info("Starting traffic data scraping...")
        
        url = "https://anwb.nl/verkeer/filelijst"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Respectful scraping - add delay
        time.sleep(1)
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        traffic_jams = []
        speed_cameras = []
        
        # Find all traffic list roads
        road_articles = soup.find_all('article', {'data-test-id': 'traffic-list-road'})
        
        for article in road_articles:
            try:
                # Extract road number
                road_span = article.find('span', {'data-test-id': 'traffic-list-road-road-number'})
                if not road_span:
                    continue
                    
                road = road_span.get_text(strip=True)
                
                # Only process target roads
                if road not in TARGET_ROADS:
                    continue
                
                # Check if there's traffic jam data
                delay_div = article.find('div', class_='sc-fd0a2c7e-6')
                if delay_div:
                    spans = delay_div.find_all('span')
                    if len(spans) >= 2:
                        delay_text = spans[0].get_text(strip=True)
                        length_text = spans[1].get_text(strip=True)
                        
                        if delay_text and length_text:
                            # Extract location from h3 tag
                            location_h3 = article.find('h3', class_='sc-fd0a2c7e-5')
                            location = location_h3.get_text(strip=True) if location_h3 else ""
                            
                            # Clean location text (remove arrow icons)
                            location = re.sub(r'\s+', ' ', location).strip()
                            
                            delay_minutes = extract_delay_minutes(delay_text)
                            length_km = extract_length_km(length_text)
                            matching_city = find_matching_city(location)
                            
                            # Only include if it matches our city criteria or if no city filter
                            if matching_city or not TARGET_CITIES:
                                traffic_jam = TrafficJam(
                                    id=str(uuid.uuid4()),
                                    road=road,
                                    location=location,
                                    delay_minutes=delay_minutes,
                                    length_km=length_km,
                                    delay_text=delay_text,
                                    city=matching_city,
                                    last_updated=datetime.utcnow()
                                )
                                traffic_jams.append(traffic_jam)
                
            except Exception as e:
                logger.warning(f"Error processing road article: {e}")
                continue
        
        # Store in database
        current_time = datetime.utcnow()
        
        # Clear old data
        await db.traffic_jams.delete_many({})
        await db.speed_cameras.delete_many({})
        
        # Insert new data
        if traffic_jams:
            await db.traffic_jams.insert_many([jam.dict() for jam in traffic_jams])
            
        # Update summary
        await db.traffic_summary.replace_one(
            {},
            {
                "total_jams": len(traffic_jams),
                "total_cameras": len(speed_cameras),
                "last_updated": current_time,
                "scrape_success": True
            },
            upsert=True
        )
        
        logger.info(f"Successfully scraped {len(traffic_jams)} traffic jams")
        return {"success": True, "traffic_jams": len(traffic_jams), "speed_cameras": len(speed_cameras)}
        
    except Exception as e:
        logger.error(f"Error scraping traffic data: {e}")
        # Update summary with error
        await db.traffic_summary.replace_one(
            {},
            {
                "total_jams": 0,
                "total_cameras": 0,
                "last_updated": datetime.utcnow(),
                "scrape_success": False,
                "error": str(e)
            },
            upsert=True
        )
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

# Background task for periodic scraping
async def periodic_scraping():
    """Run scraping every 5 minutes"""
    while True:
        try:
            await scrape_traffic_data()
            # Wait 5 minutes (300 seconds)
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Periodic scraping error: {e}")
            # Wait 1 minute before retrying if there's an error
            await asyncio.sleep(60)

# Start periodic scraping on startup
@app.on_event("startup")
async def startup_event():
    # Run initial scraping
    try:
        await scrape_traffic_data()
    except Exception as e:
        logger.error(f"Initial scraping failed: {e}")
    
    # Start background task
    asyncio.create_task(periodic_scraping())

# API Endpoints
@app.get("/")
async def root():
    return {"message": "ANWB Traffic Monitor API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/api/scrape")
async def manual_scrape():
    """Manually trigger traffic data scraping"""
    return await scrape_traffic_data()

@app.get("/api/traffic-jams")
async def get_traffic_jams(
    road: Optional[str] = None,
    city: Optional[str] = None,
    min_delay: Optional[int] = None
):
    """Get traffic jams with optional filtering"""
    
    # Build query
    query = {}
    if road:
        query["road"] = road
    if city:
        query["city"] = city
    if min_delay is not None:
        query["delay_minutes"] = {"$gte": min_delay}
    
    # Get traffic jams
    cursor = db.traffic_jams.find(query)
    traffic_jams = []
    
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
        traffic_jams.append(doc)
    
    return {
        "traffic_jams": traffic_jams,
        "count": len(traffic_jams),
        "filters": {"road": road, "city": city, "min_delay": min_delay}
    }

@app.get("/api/speed-cameras")
async def get_speed_cameras(
    road: Optional[str] = None,
    city: Optional[str] = None
):
    """Get speed cameras with optional filtering"""
    
    # Build query
    query = {}
    if road:
        query["road"] = road
    if city:
        query["city"] = city
    
    # Get speed cameras
    cursor = db.speed_cameras.find(query)
    speed_cameras = []
    
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
        speed_cameras.append(doc)
    
    return {
        "speed_cameras": speed_cameras,
        "count": len(speed_cameras),
        "filters": {"road": road, "city": city}
    }

@app.get("/api/summary")
async def get_summary():
    """Get traffic summary"""
    summary = await db.traffic_summary.find_one({})
    if not summary:
        return {
            "total_jams": 0,
            "total_cameras": 0,
            "last_updated": None,
            "scrape_success": False
        }
    
    summary["_id"] = str(summary["_id"])  # Convert ObjectId to string
    return summary

@app.get("/api/roads")
async def get_available_roads():
    """Get list of available roads"""
    return {"roads": TARGET_ROADS}

@app.get("/api/cities")
async def get_available_cities():
    """Get list of available cities"""
    return {"cities": TARGET_CITIES}

@app.get("/api/delay-filters")
async def get_delay_filters():
    """Get available delay filter options"""
    return {
        "delay_options": [1, 5, 10, 15, 20, 25, 30],
        "description": "Filter traffic jams by minimum delay in minutes"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
