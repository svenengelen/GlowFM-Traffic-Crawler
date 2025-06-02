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
        """Scrape traffic data from ANWB using text-based analysis"""
        try:
            # Use proper browser headers
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
            
            # Get the main page
            main_response = self.session.get("https://anwb.nl/verkeer/filelijst", headers=headers, timeout=30)
            main_response.raise_for_status()
            
            soup = BeautifulSoup(main_response.content, 'html.parser')
            
            traffic_jams = []
            speed_cameras = []
            
            logger.info("Starting text-based ANWB traffic data scraping")
            
            # Get all text from the page
            page_text = soup.get_text()
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            full_text = ' '.join(lines)
            
            logger.info(f"Analyzing {len(full_text)} characters of text from ANWB")
            
            # Check if page shows no traffic
            if '0 files 0 kilometer' in full_text:
                logger.info("ANWB shows '0 files 0 kilometer' - no current traffic jams")
            
            # Pattern to extract traffic information from text
            traffic_patterns = [
                # Pattern: Road + location + delay/issue
                r'(A\d+|N\d+).*?(?:tussen|richting|naar|van|bij|knooppunt|afrit|knp\.?)\s+([A-Za-z][A-Za-z\-\s]+?).*?(\+\s*\d+\s*(?:min|minuten)|afgesloten|gedeeltelijk\s+afgesloten|politie.*?onderzoek|ongeval|file|vertraging)',
                # Pattern: Delay + road + location
                r'(\+\s*\d+\s*(?:min|minuten)).*?(A\d+|N\d+).*?(?:tussen|richting|naar|van|bij)\s+([A-Za-z][A-Za-z\-\s]+)',
                # Pattern: Road closure with reason
                r'(A\d+|N\d+).*?(?:tussen|richting|naar|van|bij)\s+([A-Za-z][A-Za-z\-\s]+?).*?(afgesloten|gedeeltelijk\s+afgesloten|politie.*?onderzoek|werkzaamheden)',
            ]
            
            for pattern in traffic_patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    try:
                        groups = match.groups()
                        road = None
                        location = ""
                        issue = ""
                        delay_text = ""
                        
                        # Parse match groups based on pattern
                        if len(groups) >= 3:
                            if groups[0] and groups[0].startswith(('+', 'A', 'N')):
                                if groups[0].startswith('+'):  # Delay first pattern
                                    delay_text = groups[0].strip()
                                    road = groups[1].strip() if groups[1] else ""
                                    location = groups[2].strip() if groups[2] else ""
                                else:  # Road first pattern
                                    road = groups[0].strip()
                                    location = groups[1].strip() if groups[1] else ""
                                    issue = groups[2].strip() if groups[2] else ""
                                    if '+' in issue and 'min' in issue:
                                        delay_text = issue
                                        issue = ""
                            
                            # Clean up location
                            location = re.sub(r'\s+', ' ', location).strip()
                            location = location[:50]  # Limit length
                            
                            # Only process if we have a valid road from our target list
                            if road and road in TARGET_ROADS:
                                # Check if location matches our target cities
                                if location and self.city_matches_target(location):
                                    traffic_jam = TrafficJam(
                                        road=road,
                                        location=location,
                                        delay_minutes=self.parse_delay(delay_text),
                                        delay_text=delay_text or issue or "File gedetecteerd",
                                        length_km=0.0,
                                        length_text="Lengte onbekend"
                                    )
                                    traffic_jams.append(traffic_jam)
                                    logger.info(f"Found traffic jam: {road} at {location} - {delay_text or issue}")
                    
                    except Exception as e:
                        logger.debug(f"Error parsing traffic match: {str(e)}")
                        continue
            
            # Look for specific current issues mentioned in text
            specific_searches = [
                # Look for A67 specifically
                (r'A67.*?(?:Panningen|Venlo|Eindhoven).*?(?:politie|onderzoek|afgesloten|ongeval|\+\s*\d+\s*min)', 'A67'),
                # Look for other roads with issues
                (r'(A\d+|N\d+).*?(?:politie|onderzoek|afgesloten|ongeval)', 'Road with incident'),
            ]
            
            for pattern, description in specific_searches:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    logger.info(f"Found {description}: {match.group()}")
                    # Extract details from the match
                    match_text = match.group()
                    road_match = re.search(r'(A\d+|N\d+)', match_text)
                    if road_match:
                        road = road_match.group(1)
                        if road in TARGET_ROADS:
                            # Try to extract location and issue
                            location = "Detected from text"
                            issue = "Traffic incident detected"
                            
                            if 'politie' in match_text.lower() or 'onderzoek' in match_text.lower():
                                issue = "Politieonderzoek"
                            elif 'afgesloten' in match_text.lower():
                                issue = "Weg afgesloten"
                            elif 'ongeval' in match_text.lower():
                                issue = "Ongeval"
                            
                            # Extract delay if present
                            delay_match = re.search(r'\+\s*(\d+)\s*min', match_text, re.IGNORECASE)
                            delay_text = ""
                            delay_minutes = 0
                            if delay_match:
                                delay_minutes = int(delay_match.group(1))
                                delay_text = f"+ {delay_minutes} min - {issue}"
                            else:
                                delay_text = issue
                            
                            traffic_jam = TrafficJam(
                                road=road,
                                location=location,
                                delay_minutes=delay_minutes,
                                delay_text=delay_text,
                                length_km=0.0,
                                length_text="Onbekend"
                            )
                            traffic_jams.append(traffic_jam)
                            logger.info(f"Added specific incident: {road} - {issue}")
            
            # Check for speed camera information
            # ANWB typically doesn't show speed cameras on the main traffic page
            # but we can look for flitsers mentions
            camera_pattern = r'(A\d+|N\d+).*?(?:flits|camera|controle).*?(?:km\s*(\d+(?:\.\d+)?)|hectometer\s*(\d+(?:\.\d+)?))'
            camera_matches = re.finditer(camera_pattern, full_text, re.IGNORECASE)
            
            for match in camera_matches:
                road = match.group(1)
                hectometer = match.group(2) or match.group(3)
                if road in TARGET_ROADS and hectometer:
                    camera = SpeedCamera(
                        road=road,
                        location="Detected from text",
                        hectometer=hectometer
                    )
                    speed_cameras.append(camera)
                    logger.info(f"Found speed camera: {road} at km {hectometer}")
            
            # If no traffic found but we found general traffic indicators, note this
            if not traffic_jams:
                if 'file' in full_text.lower() and '0 files 0 kilometer' not in full_text:
                    logger.info("Traffic indicators found but no specific jams extracted")
                else:
                    logger.info("No traffic jams detected - roads appear clear")
            
            # Clear old data and store new data
            await db.traffic_jams.delete_many({})
            if traffic_jams:
                await db.traffic_jams.insert_many([jam.dict() for jam in traffic_jams])
                logger.info(f"Stored {len(traffic_jams)} traffic jams in database")
            
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
            
            logger.info(f"Text-based scraping completed: {len(traffic_jams)} traffic jams and {len(speed_cameras)} speed cameras")
            
        except Exception as e:
            logger.error(f"Error in text-based ANWB scraping: {str(e)}")
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
