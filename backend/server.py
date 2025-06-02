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
import json
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
TARGET_ROADS = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270", "N279"]
TARGET_CITIES = [
    # Original cities
    "Eindhoven", "Venlo", "Weert", "'s-Hertogenbosch", "Roermond", "Maasbracht",
    "Nijmegen", "Oss", "Zonzeel", "Breda", "Tilburg", "Rotterdam", "Deurne",
    "Helmond", "Venray", "Heerlen", "Maastricht", "Belgische Grens", "Duitse Grens", 
    "Valkenswaard", "Moerdijkbrug", "Culemborg",
    
    # A2 exits (Utrecht – 's-Hertogenbosch – Eindhoven – Maastricht)
    "Utrecht-Centrum", "Nieuwegein", "Nieuwegein-Zuid", "Vianen", "Everdingen", 
    "Beesd", "Geldermalsen", "Waardenburg", "Zaltbommel", "Kerkdriel", "Rosmalen",
    "Veghel", "St. Michielsgestel", "Vught", "'s-Hertogenbosch-Centrum", "Boxtel-Noord", 
    "Boxtel", "Best-West", "Best", "Eindhoven-Airport", "Eindhoven-Centrum", 
    "Meerhoven-Zuid", "Veldhoven", "Veldhoven-Zuid", "High Tech Campus", "Waalre",
    "Leende", "Maarheeze", "Budel", "Weert-Noord", "Nederweert", "Kelpen-Oler",
    "Grathem", "Wessem", "St. Joost", "Echt", "Roosteren", "Born", "Urmond",
    "Elsloo", "Ulestraten", "Meerssen", "Maastricht-Noord", "Maastricht-Centrum Noord",
    "Maastricht-Centrum Zuid", "Maastricht-Zuid", "Gronsveld", "Oost-Maarland", "Eijsden",
    
    # A16 exits (Belgische Grens – Breda – Rotterdam)
    "Rotterdam-Prins Alexander", "Rotterdam-Kralingen", "Capelle aan den IJssel",
    "Rotterdam-Feijenoord", "Hendrik-Ido-Ambacht", "Zwijndrecht", "Dordrecht-Centrum",
    "Dordrecht", "Dordrecht-Willemsdorp", "Zevenbergschen Hoek", "Breda-Noord",
    "Breda-West", "Princeville", "Industrie Breda 6000-7000",
    
    # A50 exits (Eindhoven – Oss – Arnhem)
    "Industrie Ekkersrijt", "Son en Breugel", "St. Oedenrode", "Eerde", "Veghel-Noord",
    "Volkel", "Zeeland", "Nistelrode", "Ravenstein", "Valburg", "Heteren", "Renkum", "Arnhem",
    
    # A58 exits (Eindhoven – Tilburg – Breda)
    "Oirschot", "Moergestel", "Tilburg-Centrum-Oost", "Tilburg-Centrum-West",
    "Tilburg-Reeshof", "Bavel", "Ulvenhout",
    
    # A59 exits (Zonzeel – 's-Hertogenbosch – Oss)
    "Terheijden", "Made", "Oosterhout", "Raamsdonksveer", "Waspik", "Sprang-Capelle-West",
    "Waalwijk", "Waalwijk-Centrum", "Waalwijk-Oost", "Drunen-West", "Heusden", 
    "Nieuwkuijk", "Vlijmen", "Ring 's-Hertogenbosch-West", "Engelen", 
    "'s-Hertogenbosch-Maaspoort", "Rosmalen-Oost", "Kruisstraat", "Nuland", "Oss-Oost",
    
    # A65 exits ('s-Hertogenbosch – Tilburg)
    "Vught-Centrum", "Vught-Zuid", "Helvoirt", "Haaren", "Biezenmortel", "Udenhout",
    "Berkel-Enschot", "Tilburg-Noord",
    
    # A67 exits (Belgische Grens – Eindhoven – Venlo – Duitse Grens)
    "Hapert", "Eersel", "Geldrop", "Someren", "Asten", "Liessel", "Panningen",
    "Venlo-Noordwest", "Noorderbrug", "Velden",
    
    # A73 exits (Nijmegen – Maasbracht)
    "Beuningen", "Wijchen", "Nijmegen-Dukenburg", "Malden", "Cuijk", "Haps",
    "Boxmeer", "Vierlingsbeek", "Venray-Noord", "Horst-Noord", "Horst", "Grubbenvorst",
    "Venlo-West", "Maasbree", "Blerick", "Zuiderbrug", "Venlo-Zuid", "Belfeld",
    "Beesel", "Roermond", "Roermond-Oost", "Linne",
    
    # A76 exits (Belgische Grens – Geleen – Heerlen – Duitse Grens)
    "Stein", "Geleen", "Spaubeek", "Nuth", "Heerlen-Noord", "Simpelveld",
    
    # Junctions (Knooppunten)
    "Knp. Oudenrijn", "Knp. Everdingen", "Knp. Deil", "Knp. Empel", "Knp. Hintham",
    "Knp. Ekkersweijer", "Knp. Batadorp", "Knp. De Hogt", "Knp. Leenderheide",
    "Knp. Het Vonderen", "Knp. Kerensheide", "Knp. Kruisdonk", "Knp. Terbregseplein",
    "Knp. Ridderkerk", "Knp. Klaverpolder", "Knp. Galder", "Knp. Paalgraven",
    "Knp. Bankhoef", "Knp. Ewijk", "Knp. Grijsoord", "Knp. De Baars", "Knp. St. Annabosch",
    "Knp. Hooipolder", "Knp. Vught", "Knp. Zaarderheiken", "Knp. Neerbosch",
    "Knp. Rijkevoort", "Knp. Tiglia", "Knp. Ten Esschen", "Knp. Kunderberg",
    
    # Bridges and Tunnels
    "Van Brienenoordbrug", "Drechttunnel", "Tacitusbrug", "Swalmentunnel", "Roertunnel"
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
        """Scrape traffic data from ANWB using proper browser emulation"""
        try:
            # Use proper browser headers and session management
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
            
            # First, get the main page to establish session
            main_response = self.session.get("https://anwb.nl/verkeer/filelijst", headers=headers, timeout=30)
            main_response.raise_for_status()
            
            # Parse the main page
            soup = BeautifulSoup(main_response.content, 'html.parser')
            
            traffic_jams = []
            speed_cameras = []
            
            logger.info("Starting real ANWB traffic data scraping")
            
            # Try to extract Next.js data first
            next_data = soup.find('script', {'id': '__NEXT_DATA__'})
            if next_data:
                try:
                    data = json.loads(next_data.get_text())
                    
                    # Look for traffic data in various paths
                    traffic_paths = [
                        ['props', 'pageProps', 'pageContextData', 'applicationData', 'traffic-list'],
                        ['props', 'pageProps', 'pageData', 'traffic'],
                        ['props', 'pageProps', 'traffic'],
                        ['props', 'initialState', 'traffic']
                    ]
                    
                    traffic_data_found = False
                    for path in traffic_paths:
                        try:
                            current = data
                            for key in path:
                                current = current[key]
                            
                            if current and current is not None:
                                logger.info(f"Found traffic data at path: {' -> '.join(path)}")
                                traffic_jams = self.process_nextjs_traffic_data(current)
                                traffic_data_found = True
                                break
                        except (KeyError, TypeError):
                            continue
                    
                    if not traffic_data_found:
                        logger.info("No traffic data found in Next.js data structure")
                        
                except json.JSONDecodeError:
                    logger.error("Could not parse Next.js data")
            
            # If Next.js approach failed, try API endpoints with proper session
            if not traffic_jams:
                logger.info("Trying ANWB API endpoints with session cookies")
                
                # Update headers for API calls
                api_headers = headers.copy()
                api_headers.update({
                    'Accept': 'application/json, text/plain, */*',
                    'Referer': 'https://anwb.nl/verkeer/filelijst',
                    'X-Requested-With': 'XMLHttpRequest'
                })
                
                # Try the component rendering endpoints with session
                api_endpoints = [
                    "https://site-production.anwb.bloomreach.cloud/verkeer/resourceapi/filelijst?_hn:type=component-rendering&_hn:ref=p1&preflight=false",
                    "https://site-production.anwb.bloomreach.cloud/verkeer/resourceapi/filelijst",
                    "https://anwb.nl/verkeer/api/traffic",
                    "https://anwb.nl/api/verkeer"
                ]
                
                for endpoint in api_endpoints:
                    try:
                        logger.info(f"Trying API endpoint: {endpoint}")
                        time.sleep(1)  # Be respectful
                        
                        api_response = self.session.get(endpoint, headers=api_headers, timeout=15)
                        
                        if api_response.status_code == 200:
                            try:
                                api_data = api_response.json()
                                logger.info(f"Successfully got JSON from {endpoint}")
                                
                                # Try to extract traffic data from API response
                                if isinstance(api_data, dict):
                                    for key in ['files', 'traffic', 'data', 'items', 'results']:
                                        if key in api_data and api_data[key]:
                                            traffic_jams = self.process_api_traffic_data(api_data[key])
                                            if traffic_jams:
                                                logger.info(f"Found {len(traffic_jams)} traffic jams from API")
                                                break
                                elif isinstance(api_data, list) and api_data:
                                    traffic_jams = self.process_api_traffic_data(api_data)
                                    
                                if traffic_jams:
                                    break
                                    
                            except json.JSONDecodeError:
                                logger.debug(f"Endpoint {endpoint} did not return JSON")
                        else:
                            logger.debug(f"Endpoint {endpoint} returned status {api_response.status_code}")
                            
                    except Exception as e:
                        logger.debug(f"Error with endpoint {endpoint}: {str(e)}")
                        continue
            
            # If still no data, try to parse HTML directly for any traffic indicators
            if not traffic_jams:
                logger.info("Trying HTML parsing for traffic indicators")
                
                # Look for any road numbers in the HTML
                page_text = soup.get_text().lower()
                
                # Check for specific road patterns with traffic indicators
                road_patterns = [
                    (r'a67.*?(?:afgesloten|politie|onderzoek|file|vertraging)', 'A67'),
                    (r'a2.*?(?:afgesloten|politie|onderzoek|file|vertraging)', 'A2'),
                    (r'a16.*?(?:afgesloten|politie|onderzoek|file|vertraging)', 'A16'),
                    (r'a50.*?(?:afgesloten|politie|onderzoek|file|vertraging)', 'A50')
                ]
                
                for pattern, road in road_patterns:
                    matches = re.findall(pattern, page_text, re.IGNORECASE | re.DOTALL)
                    if matches:
                        logger.info(f"Found traffic indicator for {road}: {matches[0][:100]}")
                        
                        # Create a traffic jam entry based on text analysis
                        traffic_jam = TrafficJam(
                            road=road,
                            location="Detected from HTML text",
                            delay_minutes=0,
                            delay_text="Traffic detected - details unknown",
                            length_km=0.0,
                            length_text="Unknown"
                        )
                        traffic_jams.append(traffic_jam)
            
            # If we still have no traffic data but user reported A67 issue, log this discrepancy
            if not traffic_jams:
                logger.warning("No traffic data found via scraping, but user reported A67 police investigation")
                logger.warning("ANWB website may have updated structure or traffic data may be in different format")
                
                # Create a placeholder indicating scraping needs attention
                traffic_jam = TrafficJam(
                    road="SYSTEM",
                    location="Scraper needs update",
                    delay_minutes=0,
                    delay_text="Unable to detect current traffic - scraper may need updating",
                    length_km=0.0,
                    length_text="N/A"
                )
                traffic_jams.append(traffic_jam)
            
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
            
            logger.info(f"Real scraping completed: {len(traffic_jams)} traffic entries and {len(speed_cameras)} speed cameras")
            
        except Exception as e:
            logger.error(f"Error in real ANWB scraping: {str(e)}")
            raise
    
    def process_nextjs_traffic_data(self, traffic_data):
        """Process traffic data from Next.js structure"""
        traffic_jams = []
        
        try:
            if isinstance(traffic_data, list):
                for item in traffic_data:
                    jam = self.parse_traffic_item(item)
                    if jam:
                        traffic_jams.append(jam)
            elif isinstance(traffic_data, dict):
                # Handle different possible structures
                for key, value in traffic_data.items():
                    if isinstance(value, list):
                        for item in value:
                            jam = self.parse_traffic_item(item)
                            if jam:
                                traffic_jams.append(jam)
        except Exception as e:
            logger.error(f"Error processing Next.js traffic data: {str(e)}")
        
        return traffic_jams
    
    def parse_traffic_item(self, item):
        """Parse individual traffic item from various data sources"""
        try:
            if not isinstance(item, dict):
                return None
            
            # Extract road number
            road = None
            for key in ['road', 'route', 'highway', 'weg', 'nummer']:
                if key in item:
                    road = str(item[key]).strip()
                    break
            
            if not road or road not in TARGET_ROADS:
                return None
            
            # Extract location
            location = ""
            for key in ['location', 'plaats', 'locatie', 'van', 'naar', 'tussen']:
                if key in item and item[key]:
                    location = str(item[key]).strip()
                    break
            
            # Check if location matches our target cities
            if location and not self.city_matches_target(location):
                return None
            
            # Extract delay and length
            delay_text = ""
            length_text = ""
            
            for key in ['delay', 'vertraging', 'tijd', 'minutes', 'minuten']:
                if key in item and item[key]:
                    delay_text = str(item[key]).strip()
                    break
            
            for key in ['length', 'lengte', 'afstand', 'km', 'kilometers']:
                if key in item and item[key]:
                    length_text = str(item[key]).strip()
                    break
            
            # Extract reason/subtitle
            subtitle = ""
            for key in ['reason', 'oorzaak', 'type', 'subtitle', 'beschrijving']:
                if key in item and item[key]:
                    subtitle = str(item[key]).strip()
                    break
            
            # Add subtitle to delay text if available
            if subtitle and delay_text:
                delay_text = f"{delay_text} - {subtitle}"
            elif subtitle and not delay_text:
                delay_text = subtitle
            
            traffic_jam = TrafficJam(
                road=road,
                location=location or f"{road} - Gemonitord gebied",
                delay_minutes=self.parse_delay(delay_text),
                delay_text=delay_text or "Verkeersinfo beschikbaar",
                length_km=self.parse_length(length_text),
                length_text=length_text or "Lengte onbekend"
            )
            
            return traffic_jam
            
        except Exception as e:
            logger.error(f"Error parsing traffic item: {str(e)}")
            return None
    
    def process_api_traffic_data(self, traffic_items):
        """Process traffic data from API response"""
        traffic_jams = []
        
        for item in traffic_items:
            try:
                # Extract road information
                road = item.get('road', '').strip()
                if not road or road not in TARGET_ROADS:
                    continue
                
                # Extract location and check if it matches target cities
                location = item.get('location', '').strip()
                if not self.city_matches_target(location):
                    continue
                
                # Extract delay and length
                delay_text = item.get('delay', item.get('delay_text', '')).strip()
                length_text = item.get('length', item.get('length_text', '')).strip()
                subtitle = item.get('subtitle', item.get('reason', '')).strip()
                
                # Add subtitle to delay text if available
                if subtitle and delay_text:
                    delay_text = f"{delay_text} - {subtitle}"
                
                traffic_jam = TrafficJam(
                    road=road,
                    location=location,
                    delay_minutes=self.parse_delay(delay_text),
                    delay_text=delay_text or "Vertraging onbekend",
                    length_km=self.parse_length(length_text),
                    length_text=length_text or "Lengte onbekend"
                )
                traffic_jams.append(traffic_jam)
                
            except Exception as e:
                logger.error(f"Error processing traffic item: {str(e)}")
                continue
        
        return traffic_jams

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
