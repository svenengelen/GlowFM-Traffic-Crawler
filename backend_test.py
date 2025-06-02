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
        """Test that there is at least one A67 traffic jam with expected data"""
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
                
                if a67_jam.get('length_km') >= 2:
                    print(f"✅ A67 jam has expected length: {a67_jam.get('length_km')} km")
                else:
                    print(f"❌ A67 jam has unexpected length: {a67_jam.get('length_km')} km, expected at least 2 km")
                    return False
                
                return True
            else:
                print("❌ No A67 traffic jams found")
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
            if all(jam['road'] == 'A67' for jam in traffic_jams):
                print(f"✅ Road filtering works correctly, found {len(traffic_jams)} A67 jams")
            else:
                print("❌ Road filtering returned non-A67 jams")
                return False
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
            if all(jam['delay_minutes'] >= 1 for jam in traffic_jams):
                print(f"✅ Delay filtering works correctly, found {len(traffic_jams)} jams with 1+ min delay")
            else:
                print("❌ Delay filtering returned jams with less than 1 min delay")
                return False
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
        tester.test_a67_traffic_jam,
        tester.test_roads_endpoint,
        tester.test_cities_endpoint,
        tester.test_refresh_endpoint,
        tester.test_traffic_filtering
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())