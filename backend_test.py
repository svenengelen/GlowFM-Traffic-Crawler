import requests
import sys
import json
from datetime import datetime

class ANWBTrafficTester:
    def __init__(self, base_url="https://bc4668cd-3e1d-4a51-8563-9ce46c9a86d6.preview.emergentagent.com"):
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
                    
                    # Check that direction, from_exit, to_exit, and cause are populated (not default values)
                    enhanced_fields = {
                        'direction': first_jam.get('direction', ''),
                        'from_exit': first_jam.get('from_exit', ''),
                        'to_exit': first_jam.get('to_exit', ''),
                        'cause': first_jam.get('cause', '')
                    }
                    
                    default_values = {
                        'direction': 'Onbekende richting',
                        'from_exit': 'Onbekend',
                        'to_exit': 'Onbekend',
                        'cause': 'Onbekende oorzaak'
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
        """Test that speed camera objects have the expected data structure"""
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
                    
                    # Check that camera_type is one of the expected types
                    camera_type = first_camera.get('camera_type', '')
                    if camera_type in self.expected_camera_types:
                        print(f"✅ Camera type is valid: {camera_type}")
                    else:
                        print(f"❌ Unexpected camera type: {camera_type}")
                        print(f"Expected one of: {', '.join(self.expected_camera_types)}")
                        return False
                    
                    # Check that speed_limit is a reasonable value
                    speed_limit = first_camera.get('speed_limit', 0)
                    if isinstance(speed_limit, int) and 0 <= speed_limit <= 130:
                        print(f"✅ Speed limit is valid: {speed_limit} km/h")
                    else:
                        print(f"❌ Unexpected speed limit value: {speed_limit}")
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

def main():
    # Setup
    tester = ANWBTrafficTester()
    
    # Run tests
    tests = [
        tester.test_health_endpoint,
        tester.test_traffic_endpoint,
        tester.test_traffic_jam_data_structure,
        tester.test_a67_traffic_jam,
        tester.test_roads_endpoint,
        tester.test_cities_endpoint,
        tester.test_refresh_endpoint,
        tester.test_traffic_filtering,
        tester.test_road_types,
        # Speed camera tests
        tester.test_speed_cameras_endpoint,
        tester.test_speed_cameras_in_traffic_endpoint,
        tester.test_speed_camera_data_structure,
        tester.test_speed_camera_filtering
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())