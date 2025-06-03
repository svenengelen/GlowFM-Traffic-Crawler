import requests
import sys
import json
from datetime import datetime

class ANWBTrafficTester:
    def __init__(self, base_url="https://02a58650-437a-4820-b348-305719967aeb.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.expected_roads = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270"]
        self.expected_cities = [
            'Eindhoven', 'Venlo', 'Weert', "'s-Hertogenbosch", 'Roermond', 'Maasbracht', 
            'Nijmegen', 'Oss', 'Zonzeel', 'Breda', 'Tilburg', 'Rotterdam', 'Deurne', 
            'Helmond', 'Venray', 'Heerlen', 'Maastricht', 'Belgische Grens', 'Duitse Grens', 'Valkenswaard'
        ]
        # Expected fields in traffic jam objects with enhanced structure
        self.expected_traffic_jam_fields = [
            'id', 'road', 'direction', 'source_location', 'destination_location', 
            'route_details', 'cause', 'delay_minutes', 'length_km', 'last_updated'
        ]
        # Expected fields in speed camera objects with enhanced structure
        self.expected_speed_camera_fields = [
            'id', 'road', 'location', 'direction', 'flitser_type', 'is_active', 'last_updated'
        ]
        # Expected flitser types
        self.expected_flitser_types = [
            'Mobiele flitser', 'Actieve flitser', 'Snelheidscontrole'
        ]
        
        # Enhanced location patterns to check
        self.hectometer_patterns = [
            r'hm \d+\.\d+',  # e.g., "hm 12.3"
            r'hectometerpaal \d+\.\d+',  # e.g., "hectometerpaal 45.7"
            r'\d+\.\d+ km',  # e.g., "45.7 km"
        ]
        
        # Junction/exit terms to check
        self.junction_terms = [
            'knooppunt', 'afslag', 'afrit', 'oprit', 'aansluiting', 
            'kruising', 'rotonde', 'verkeerslicht', 'brug', 'tunnel'
        ]
        
        # Traffic cause terms to check
        self.traffic_cause_terms = {
            'accidents': ['ongeval', 'aanrijding', 'botsing', 'brand', 'hulpdiensten'],
            'roadworks': ['wegwerkzaamheden', 'afsluiting', 'versmalling', 'werkzaamheden'],
            'weather': ['gladheid', 'sneeuw', 'mist', 'regen', 'storm', 'weer'],
            'volume': ['drukte', 'spitsuur', 'file', 'verkeersdrukte']
        }

    def run_test(self, name, method, endpoint, expected_status, params=None, data=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.json()}")
                except:
                    print(f"Response: {response.text}")
                return False, None

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None

    def test_health_endpoint(self):
        """Test the health endpoint"""
        success, response = self.run_test(
            "Health Endpoint",
            "GET",
            "health",
            200
        )
        if success:
            if 'status' in response and response['status'] == 'healthy':
                print("✅ Health endpoint returns healthy status")
                return True
            else:
                print(f"❌ Health endpoint returns unexpected status: {response}")
                return False
        return success

    def test_traffic_endpoint(self):
        """Test the traffic endpoint returns traffic data"""
        success, response = self.run_test(
            "Traffic Data Endpoint",
            "GET",
            "traffic",
            200
        )
        if success:
            if 'traffic_jams' in response and 'last_updated' in response:
                print(f"✅ Traffic endpoint returns data with {response['total_jams']} traffic jams")
                return True
            else:
                print(f"❌ Traffic endpoint returns unexpected format: {response}")
                return False
        return success

    def test_a67_traffic_jam(self):
        """Test that there is at least one A67 traffic jam with expected data, or verify no traffic jams"""
        success, response = self.run_test(
            "A67 Traffic Jam",
            "GET",
            "traffic",
            200,
            params={"road": "A67"}
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            if traffic_jams:
                a67_jam = traffic_jams[0]
                print(f"✅ Found A67 traffic jam: {a67_jam}")
                
                # Check for expected delay and length
                if a67_jam.get('delay_minutes') >= 1:
                    print(f"✅ A67 jam has expected delay: {a67_jam.get('delay_minutes')} minutes")
                else:
                    print(f"❌ A67 jam has unexpected delay: {a67_jam.get('delay_minutes')} minutes, expected at least 1 minute")
                    return False
                
                if a67_jam.get('length_km') >= 1:
                    print(f"✅ A67 jam has expected length: {a67_jam.get('length_km')} km")
                else:
                    print(f"❌ A67 jam has unexpected length: {a67_jam.get('length_km')} km, expected at least 1 km")
                    return False
                
                return True
            else:
                print("ℹ️ No A67 traffic jams found - this is acceptable as traffic conditions change")
                return True
        return success
        
    def test_a270_traffic_jam(self):
        """Test that there is at least one A270 traffic jam with expected data, or verify no traffic jams"""
        success, response = self.run_test(
            "A270 Traffic Jam",
            "GET",
            "traffic",
            200,
            params={"road": "A270"}
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            if traffic_jams:
                a270_jam = traffic_jams[0]
                print(f"✅ Found A270 traffic jam: {a270_jam}")
                
                # Check for expected delay and length
                if a270_jam.get('delay_minutes') >= 1:
                    print(f"✅ A270 jam has expected delay: {a270_jam.get('delay_minutes')} minutes")
                else:
                    print(f"❌ A270 jam has unexpected delay: {a270_jam.get('delay_minutes')} minutes, expected at least 1 minute")
                    return False
                
                if a270_jam.get('length_km') >= 1:
                    print(f"✅ A270 jam has expected length: {a270_jam.get('length_km')} km")
                else:
                    print(f"❌ A270 jam has unexpected length: {a270_jam.get('length_km')} km, expected at least 1 km")
                    return False
                
                return True
            else:
                print("❌ No A270 traffic jams found - this is a problem as A270 currently has a traffic jam")
                return False
        return success

    def test_roads_endpoint(self):
        """Test the roads endpoint returns the expected list of roads"""
        success, response = self.run_test(
            "Monitored Roads Endpoint",
            "GET",
            "roads",
            200
        )
        if success:
            if 'roads' in response:
                roads = response['roads']
                if set(roads) == set(self.expected_roads):
                    print(f"✅ Roads endpoint returns all {len(roads)} expected roads")
                    return True
                else:
                    print(f"❌ Roads endpoint returns unexpected roads")
                    print(f"Expected: {', '.join(sorted(self.expected_roads))}")
                    print(f"Actual: {', '.join(sorted(roads))}")
                    return False
            else:
                print(f"❌ Roads endpoint returns unexpected format: {response}")
                return False
        return success

    def test_cities_endpoint(self):
        """Test the cities endpoint returns the expected list of cities"""
        success, response = self.run_test(
            "Monitored Cities Endpoint",
            "GET",
            "cities",
            200
        )
        if success:
            if 'cities' in response:
                cities = response['cities']
                if set(cities) == set(self.expected_cities):
                    print(f"✅ Cities endpoint returns all {len(cities)} expected cities")
                    return True
                else:
                    print(f"❌ Cities endpoint returns unexpected cities")
                    print(f"Expected: {', '.join(sorted(self.expected_cities))}")
                    print(f"Actual: {', '.join(sorted(cities))}")
                    return False
            else:
                print(f"❌ Cities endpoint returns unexpected format: {response}")
                return False
        return success

    def test_refresh_endpoint(self):
        """Test the refresh endpoint"""
        success, response = self.run_test(
            "Traffic Refresh Endpoint",
            "POST",
            "traffic/refresh",
            200
        )
        if success:
            if 'message' in response and 'timestamp' in response:
                print("✅ Refresh endpoint returns expected response format")
                return True
            else:
                print(f"❌ Refresh endpoint returns unexpected format: {response}")
                return False
        return success

    def test_traffic_jam_data_structure(self):
        """Test that traffic jam objects have the expected enhanced data structure"""
        success, response = self.run_test(
            "Traffic Jam Data Structure",
            "GET",
            "traffic",
            200
        )
        if success:
            if 'traffic_jams' in response:
                traffic_jams = response['traffic_jams']
                if not traffic_jams:
                    print("ℹ️ No traffic jams found - cannot verify data structure")
                    return True
                
                # Check first traffic jam for all expected fields
                first_jam = traffic_jams[0]
                missing_fields = [field for field in self.expected_traffic_jam_fields if field not in first_jam]
                
                if not missing_fields:
                    print(f"✅ Traffic jam has all expected fields: {', '.join(self.expected_traffic_jam_fields)}")
                    
                    # Check that enhanced fields are populated (not default values)
                    enhanced_fields = {
                        'direction': first_jam.get('direction', ''),
                        'source_location': first_jam.get('source_location', ''),
                        'destination_location': first_jam.get('destination_location', ''),
                        'route_details': first_jam.get('route_details', ''),
                        'cause': first_jam.get('cause', '')
                    }
                    
                    default_values = {
                        'direction': 'Onbekende richting',
                        'source_location': 'Onbekend',
                        'destination_location': 'Onbekend',
                        'route_details': 'Route onbekend',
                        'cause': 'Oorzaak onbekend'
                    }
                    
                    populated_fields = [field for field, value in enhanced_fields.items() 
                                       if value and value != default_values.get(field)]
                    
                    if populated_fields:
                        print(f"✅ Enhanced fields are populated: {', '.join(populated_fields)}")
                        print(f"Sample values: {json.dumps({f: enhanced_fields[f] for f in populated_fields}, indent=2)}")
                        return True
                    else:
                        print("❌ Enhanced fields exist but contain default/empty values")
                        print(f"Current values: {json.dumps(enhanced_fields, indent=2)}")
                        return False
                else:
                    print(f"❌ Traffic jam missing expected fields: {', '.join(missing_fields)}")
                    print(f"Available fields: {', '.join(first_jam.keys())}")
                    return False
            else:
                print(f"❌ Traffic endpoint returns unexpected format: {response}")
                return False
        return success

    def test_traffic_filtering(self):
        """Test traffic filtering by road, city, and minimum delay"""
        # Test road filter
        success, response = self.run_test(
            "Traffic Filtering by Road (A67)",
            "GET",
            "traffic",
            200,
            params={"road": "A67"}
        )
        if success and 'traffic_jams' in response:
            traffic_jams = response['traffic_jams']
            if traffic_jams:
                if all(jam['road'] == 'A67' for jam in traffic_jams):
                    print(f"✅ Road filtering works correctly, found {len(traffic_jams)} A67 jams")
                else:
                    print("❌ Road filtering returned non-A67 jams")
                    return False
            else:
                print("ℹ️ No A67 traffic jams found - filter works but no matching data")
        else:
            return False

        # Test minimum delay filter
        success, response = self.run_test(
            "Traffic Filtering by Minimum Delay (1 min)",
            "GET",
            "traffic",
            200,
            params={"min_delay": 1}
        )
        if success and 'traffic_jams' in response:
            traffic_jams = response['traffic_jams']
            if traffic_jams:
                if all(jam['delay_minutes'] >= 1 for jam in traffic_jams):
                    print(f"✅ Delay filtering works correctly, found {len(traffic_jams)} jams with 1+ min delay")
                else:
                    print("❌ Delay filtering returned jams with less than 1 min delay")
                    return False
            else:
                print("ℹ️ No traffic jams with 1+ min delay found - filter works but no matching data")
        else:
            return False

        return True
        
    def test_road_types(self):
        """Test that A-roads and N-roads are correctly identified"""
        success, response = self.run_test(
            "Road Types",
            "GET",
            "traffic",
            200
        )
        if success and 'traffic_jams' in response:
            traffic_jams = response['traffic_jams']
            if not traffic_jams:
                print("ℹ️ No traffic jams found - cannot verify road types")
                return True
                
            a_roads = [jam for jam in traffic_jams if jam['road'].startswith('A')]
            n_roads = [jam for jam in traffic_jams if jam['road'].startswith('N')]
            
            if a_roads:
                print(f"✅ Found {len(a_roads)} A-roads: {', '.join(sorted(set(jam['road'] for jam in a_roads)))}")
            else:
                print("ℹ️ No A-roads found in current traffic data")
                
            if n_roads:
                print(f"✅ Found {len(n_roads)} N-roads: {', '.join(sorted(set(jam['road'] for jam in n_roads)))}")
            else:
                print("ℹ️ No N-roads found in current traffic data")
                
            return True
        return False
        
    def test_speed_cameras_endpoint(self):
        """Test the dedicated speed cameras endpoint"""
        success, response = self.run_test(
            "Speed Cameras Endpoint",
            "GET",
            "speed-cameras",
            200
        )
        if success:
            if 'speed_cameras' in response and 'total_cameras' in response and 'last_updated' in response:
                print(f"✅ Speed cameras endpoint returns data with {response['total_cameras']} cameras")
                return True
            else:
                print(f"❌ Speed cameras endpoint returns unexpected format: {response}")
                return False
        return success
        
    def test_speed_cameras_in_traffic_endpoint(self):
        """Test that speed cameras are included in the traffic endpoint response"""
        success, response = self.run_test(
            "Speed Cameras in Traffic Endpoint",
            "GET",
            "traffic",
            200
        )
        if success:
            if 'speed_cameras' in response:
                print(f"✅ Traffic endpoint includes speed cameras array with {len(response['speed_cameras'])} cameras")
                return True
            else:
                print(f"❌ Traffic endpoint does not include speed cameras")
                return False
        return success
        
    def test_speed_camera_data_structure(self):
        """Test that speed camera objects have the expected enhanced data structure"""
        success, response = self.run_test(
            "Speed Camera Data Structure",
            "GET",
            "speed-cameras",
            200
        )
        if success:
            if 'speed_cameras' in response:
                speed_cameras = response['speed_cameras']
                if not speed_cameras:
                    print("ℹ️ No speed cameras found - cannot verify data structure")
                    return True
                
                # Check first speed camera for all expected fields
                first_camera = speed_cameras[0]
                missing_fields = [field for field in self.expected_speed_camera_fields if field not in first_camera]
                
                if not missing_fields:
                    print(f"✅ Speed camera has all expected fields: {', '.join(self.expected_speed_camera_fields)}")
                    
                    # Check that flitser_type is one of the expected types
                    flitser_type = first_camera.get('flitser_type', '')
                    if flitser_type in self.expected_flitser_types:
                        print(f"✅ Flitser type is valid: {flitser_type}")
                    else:
                        print(f"❌ Unexpected flitser type: {flitser_type}")
                        print(f"Expected one of: {', '.join(self.expected_flitser_types)}")
                        return False
                    
                    # Check that is_active is a boolean
                    is_active = first_camera.get('is_active')
                    if isinstance(is_active, bool):
                        print(f"✅ is_active is valid boolean: {is_active}")
                    else:
                        print(f"❌ Unexpected is_active value: {is_active}, expected boolean")
                        return False
                    
                    print(f"Sample speed camera: {json.dumps(first_camera, indent=2, default=str)}")
                    return True
                else:
                    print(f"❌ Speed camera missing expected fields: {', '.join(missing_fields)}")
                    print(f"Available fields: {', '.join(first_camera.keys())}")
                    return False
            else:
                print(f"❌ Speed cameras endpoint returns unexpected format: {response}")
                return False
        return success
        
    def test_speed_camera_filtering(self):
        """Test speed camera filtering by road and city"""
        # Test road filter
        road_to_test = self.expected_roads[0]  # Use first road as test
        success, response = self.run_test(
            f"Speed Camera Filtering by Road ({road_to_test})",
            "GET",
            "speed-cameras",
            200,
            params={"road": road_to_test}
        )
        if success and 'speed_cameras' in response:
            speed_cameras = response['speed_cameras']
            if speed_cameras:
                if all(cam['road'] == road_to_test for cam in speed_cameras):
                    print(f"✅ Road filtering works correctly, found {len(speed_cameras)} {road_to_test} cameras")
                else:
                    print(f"❌ Road filtering returned non-{road_to_test} cameras")
                    return False
            else:
                print(f"ℹ️ No {road_to_test} speed cameras found - filter works but no matching data")
        else:
            return False

        # Test city filter
        city_to_test = self.expected_cities[0]  # Use first city as test
        success, response = self.run_test(
            f"Speed Camera Filtering by City ({city_to_test})",
            "GET",
            "speed-cameras",
            200,
            params={"city": city_to_test}
        )
        if success and 'speed_cameras' in response:
            speed_cameras = response['speed_cameras']
            if speed_cameras:
                print(f"✅ City filtering returned {len(speed_cameras)} cameras for {city_to_test}")
            else:
                print(f"ℹ️ No speed cameras found for {city_to_test} - filter works but no matching data")
        else:
            return False

        return True
        
    def test_scraper_refresh(self):
        """Test the scraper's ability to refresh and extract traffic data"""
        print("\n🔍 Testing Scraper Refresh...")
        
        # First, trigger a refresh
        success, response = self.run_test(
            "Traffic Refresh Endpoint",
            "POST",
            "traffic/refresh",
            200
        )
        
        if not success:
            print("❌ Failed to trigger traffic refresh")
            return False
            
        # Wait for the scraper to complete (it runs asynchronously)
        print("⏳ Waiting for scraper to complete (5 seconds)...")
        import time
        time.sleep(5)
        
        # Now check the traffic data
        success, response = self.run_test(
            "Traffic Data After Refresh",
            "GET",
            "traffic",
            200
        )
        
        if not success:
            print("❌ Failed to get traffic data after refresh")
            return False
            
        # Check if any traffic jams were found
        traffic_jams = response.get('traffic_jams', [])
        total_jams = len(traffic_jams)
        
        print(f"Found {total_jams} traffic jams after refresh")
        
        if total_jams == 0:
            print("❌ No traffic jams found after refresh - scraper may not be extracting data correctly")
            return False
        else:
            print(f"✅ Scraper found {total_jams} traffic jams")
            
            # Check if A270 is among the roads with traffic jams
            a270_jams = [jam for jam in traffic_jams if jam['road'] == 'A270']
            if a270_jams:
                print(f"✅ Found {len(a270_jams)} traffic jams for A270")
                for jam in a270_jams:
                    print(f"  - Delay: {jam['delay_minutes']} min, Length: {jam['length_km']} km")
                    print(f"  - Direction: {jam['direction']}")
                    print(f"  - Route: {jam['route_details']}")
                    print(f"  - Cause: {jam['cause']}")
            else:
                print("❌ No A270 traffic jams found after refresh - scraper may not be detecting A270 traffic")
                
            # Check the last_updated timestamp
            last_updated = response.get('last_updated')
            if last_updated:
                from datetime import datetime
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    now = datetime.now()
                    diff_minutes = (now - last_updated_dt).total_seconds() / 60
                    
                    if diff_minutes < 10:
                        print(f"✅ Data was recently updated ({diff_minutes:.1f} minutes ago)")
                    else:
                        print(f"⚠️ Data may be stale (last updated {diff_minutes:.1f} minutes ago)")
                except:
                    print(f"⚠️ Could not parse last_updated timestamp: {last_updated}")
            
        return total_jams > 0

    def test_enhanced_location_precision(self):
        """Test the enhanced location precision features"""
        print("\n🔍 Testing Enhanced Location Precision...")
        
        success, response = self.run_test(
            "Traffic Data for Location Precision Analysis",
            "GET",
            "traffic",
            200
        )
        
        if not success:
            print("❌ Failed to get traffic data for location precision analysis")
            return False
            
        traffic_jams = response.get('traffic_jams', [])
        if not traffic_jams:
            print("ℹ️ No traffic jams found - cannot verify location precision")
            return True
            
        # Check for hectometer information
        hectometer_found = False
        for jam in traffic_jams:
            route_details = jam.get('route_details', '')
            for pattern in self.hectometer_patterns:
                import re
                if re.search(pattern, route_details, re.IGNORECASE):
                    hectometer_found = True
                    print(f"✅ Found hectometer information: '{re.search(pattern, route_details, re.IGNORECASE).group(0)}' in: {route_details}")
                    break
            if hectometer_found:
                break
                
        if not hectometer_found:
            print("⚠️ No hectometer information found in any traffic jam")
            
        # Check for junction/exit terms
        junction_found = False
        for jam in traffic_jams:
            route_details = jam.get('route_details', '')
            for term in self.junction_terms:
                if term in route_details.lower():
                    junction_found = True
                    print(f"✅ Found junction/exit term: '{term}' in: {route_details}")
                    break
            if junction_found:
                break
                
        if not junction_found:
            print("⚠️ No junction/exit terms found in any traffic jam")
            
        # Check for "between X and Y" location descriptions
        between_locations_found = False
        for jam in traffic_jams:
            route_details = jam.get('route_details', '')
            if 'tussen' in route_details.lower() and 'en' in route_details.lower():
                between_locations_found = True
                print(f"✅ Found 'between X and Y' description: {route_details}")
                break
                
        if not between_locations_found:
            print("⚠️ No 'between X and Y' location descriptions found")
            
        # Check for city names in location data
        cities_in_locations = []
        for jam in traffic_jams:
            source = jam.get('source_location', '').lower()
            dest = jam.get('destination_location', '').lower()
            route = jam.get('route_details', '').lower()
            
            for city in self.expected_cities:
                city_lower = city.lower()
                if city_lower in source or city_lower in dest or city_lower in route:
                    if city not in cities_in_locations:
                        cities_in_locations.append(city)
        
        if cities_in_locations:
            print(f"✅ Found {len(cities_in_locations)} cities in location data: {', '.join(cities_in_locations)}")
        else:
            print("⚠️ No expected cities found in location data")
            
        # Overall assessment
        location_features_found = sum([hectometer_found, junction_found, between_locations_found, len(cities_in_locations) > 0])
        if location_features_found >= 2:  # At least 2 location features should be found
            print("✅ Enhanced location precision features are working")
            return True
        else:
            print("❌ Enhanced location precision features may not be fully implemented")
            return False
            
    def test_improved_traffic_cause_detection(self):
        """Test the improved traffic cause detection features"""
        print("\n🔍 Testing Improved Traffic Cause Detection...")
        
        success, response = self.run_test(
            "Traffic Data for Cause Analysis",
            "GET",
            "traffic",
            200
        )
        
        if not success:
            print("❌ Failed to get traffic data for cause analysis")
            return False
            
        traffic_jams = response.get('traffic_jams', [])
        if not traffic_jams:
            print("ℹ️ No traffic jams found - cannot verify cause detection")
            return True
            
        # Check for different cause categories
        cause_categories_found = {category: False for category in self.traffic_cause_terms.keys()}
        cause_examples = {}
        
        for jam in traffic_jams:
            cause = jam.get('cause', '').lower()
            if not cause or cause == 'oorzaak onbekend':
                continue
                
            for category, terms in self.traffic_cause_terms.items():
                for term in terms:
                    if term in cause:
                        cause_categories_found[category] = True
                        cause_examples[category] = cause
                        break
        
        # Report findings
        for category, found in cause_categories_found.items():
            if found:
                print(f"✅ Found {category} cause: '{cause_examples[category]}'")
            else:
                print(f"⚠️ No {category} causes found")
                
        # Check for combined causes (e.g., "accident due to weather")
        combined_causes_found = False
        for jam in traffic_jams:
            cause = jam.get('cause', '').lower()
            categories_in_cause = []
            
            for category, terms in self.traffic_cause_terms.items():
                for term in terms:
                    if term in cause:
                        categories_in_cause.append(category)
                        break
                        
            if len(categories_in_cause) >= 2:
                combined_causes_found = True
                print(f"✅ Found combined cause ({'+'.join(categories_in_cause)}): '{cause}'")
                break
                
        if not combined_causes_found:
            print("⚠️ No combined causes found")
            
        # Overall assessment
        causes_found_count = sum(1 for found in cause_categories_found.values() if found)
        if causes_found_count >= 2 or combined_causes_found:  # At least 2 cause categories or a combined cause
            print("✅ Improved traffic cause detection is working")
            return True
        else:
            print("❌ Improved traffic cause detection may not be fully implemented")
            return False
            
    def test_enhanced_error_handling(self):
        """Test the enhanced error handling features"""
        print("\n🔍 Testing Enhanced Error Handling...")
        
        # Test with invalid parameters to check error handling
        success, response = self.run_test(
            "Error Handling - Invalid Road Parameter",
            "GET",
            "traffic",
            200,  # Should still return 200 with empty results, not 500
            params={"road": "INVALID_ROAD_XYZ"}
        )
        
        if not success:
            print("❌ Failed basic error handling test - server error on invalid parameter")
            return False
            
        # Check that response is well-formed even with invalid input
        if 'traffic_jams' in response and isinstance(response['traffic_jams'], list):
            print("✅ Server handles invalid road parameter gracefully")
        else:
            print("❌ Server response is malformed with invalid parameter")
            return False
            
        # Test with invalid city parameter
        success, response = self.run_test(
            "Error Handling - Invalid City Parameter",
            "GET",
            "traffic",
            200,  # Should still return 200 with empty results, not 500
            params={"city": "NONEXISTENT_CITY_XYZ"}
        )
        
        if not success:
            print("❌ Failed city error handling test - server error on invalid parameter")
            return False
            
        # Check that response is well-formed even with invalid input
        if 'traffic_jams' in response and isinstance(response['traffic_jams'], list):
            print("✅ Server handles invalid city parameter gracefully")
        else:
            print("❌ Server response is malformed with invalid city parameter")
            return False
            
        # Test with multiple invalid parameters
        success, response = self.run_test(
            "Error Handling - Multiple Invalid Parameters",
            "GET",
            "traffic",
            200,  # Should still return 200 with empty results, not 500
            params={"road": "INVALID_ROAD_XYZ", "city": "NONEXISTENT_CITY_XYZ", "min_delay": "not_a_number"}
        )
        
        if not success:
            print("❌ Failed multiple error handling test - server error on invalid parameters")
            return False
            
        # Check that response is well-formed even with invalid input
        if 'traffic_jams' in response and isinstance(response['traffic_jams'], list):
            print("✅ Server handles multiple invalid parameters gracefully")
        else:
            print("❌ Server response is malformed with multiple invalid parameters")
            return False
            
        print("✅ Enhanced error handling is working properly")
        return True
        
    def test_performance_optimizations(self):
        """Test the performance optimizations"""
        print("\n🔍 Testing Performance Optimizations...")
        
        # Check if optimized endpoint exists
        success, response = self.run_test(
            "Optimized Scraping Endpoint",
            "GET",
            "scrape-optimized",
            200
        )
        
        optimized_endpoint_exists = success
        
        if not optimized_endpoint_exists:
            print("ℹ️ Optimized scraping endpoint not found - testing regular endpoint performance")
            
        # Test regular endpoint performance
        import time
        start_time = time.time()
        
        success, response = self.run_test(
            "Regular Traffic Endpoint Performance",
            "GET",
            "traffic",
            200
        )
        
        regular_endpoint_time = time.time() - start_time
        print(f"ℹ️ Regular traffic endpoint response time: {regular_endpoint_time:.2f} seconds")
        
        if not success:
            print("❌ Failed to test regular endpoint performance")
            return False
            
        # If optimized endpoint exists, test its performance
        if optimized_endpoint_exists:
            start_time = time.time()
            
            success, response = self.run_test(
                "Optimized Endpoint Performance",
                "GET",
                "scrape-optimized",
                200
            )
            
            optimized_endpoint_time = time.time() - start_time
            print(f"ℹ️ Optimized endpoint response time: {optimized_endpoint_time:.2f} seconds")
            
            if not success:
                print("❌ Failed to test optimized endpoint performance")
                return False
                
            # Compare performance
            if optimized_endpoint_time < regular_endpoint_time:
                print(f"✅ Optimized endpoint is faster by {(regular_endpoint_time - optimized_endpoint_time):.2f} seconds")
            else:
                print(f"⚠️ Optimized endpoint is not faster than regular endpoint")
        
        # Test refresh endpoint performance
        start_time = time.time()
        
        success, response = self.run_test(
            "Refresh Endpoint Performance",
            "POST",
            "traffic/refresh",
            200
        )
        
        refresh_endpoint_time = time.time() - start_time
        print(f"ℹ️ Refresh endpoint response time: {refresh_endpoint_time:.2f} seconds")
        
        if not success:
            print("❌ Failed to test refresh endpoint performance")
            return False
            
        # Check if refresh is asynchronous (should return quickly)
        if refresh_endpoint_time < 1.0:
            print("✅ Refresh endpoint returns quickly (likely asynchronous)")
        else:
            print("⚠️ Refresh endpoint is slow to respond (may not be fully asynchronous)")
            
        print("✅ Performance testing completed successfully")
        return True

def main():
    # Setup
    tester = ANWBTrafficTester()
    
    # Run tests
    tests = [
        tester.test_health_endpoint,
        tester.test_traffic_endpoint,
        tester.test_traffic_jam_data_structure,
        tester.test_a67_traffic_jam,
        tester.test_a270_traffic_jam,
        tester.test_roads_endpoint,
        tester.test_cities_endpoint,
        tester.test_refresh_endpoint,
        tester.test_traffic_filtering,
        tester.test_road_types,
        # Speed camera tests
        tester.test_speed_cameras_endpoint,
        tester.test_speed_cameras_in_traffic_endpoint,
        tester.test_speed_camera_data_structure,
        tester.test_speed_camera_filtering,
        # Enhanced feature tests
        tester.test_enhanced_location_precision,
        tester.test_improved_traffic_cause_detection,
        tester.test_enhanced_error_handling,
        tester.test_performance_optimizations,
        # Scraper test
        tester.test_scraper_refresh
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())