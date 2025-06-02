import requests
import sys
import json
from datetime import datetime

class ANWBTrafficMonitorTester:
    def __init__(self, base_url="https://bc4668cd-3e1d-4a51-8563-9ce46c9a86d6.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

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

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )
        if success:
            print(f"Response: {response}")
        return success

    def test_traffic_endpoint(self):
        """Test the traffic endpoint with no filters"""
        success, response = self.run_test(
            "Traffic Endpoint (No Filters)",
            "GET",
            "traffic",
            200
        )
        if success:
            print(f"Total traffic jams: {response.get('total_jams', 'N/A')}")
            print(f"Filtered traffic jams: {response.get('filtered_jams', 'N/A')}")
            print(f"Speed cameras: {len(response.get('speed_cameras', []))}")
            print(f"Last updated: {response.get('last_updated', 'N/A')}")
        return success

    def test_traffic_endpoint_with_road_filter(self):
        """Test the traffic endpoint with road filter"""
        success, response = self.run_test(
            "Traffic Endpoint (Road Filter)",
            "GET",
            "traffic",
            200,
            params={"roads": "A50,A73"}
        )
        if success:
            print(f"Total traffic jams: {response.get('total_jams', 'N/A')}")
            print(f"Filtered traffic jams: {response.get('filtered_jams', 'N/A')}")
            
            # Verify that all returned traffic jams are for the specified roads
            roads = ["A50", "A73"]
            all_match = all(jam['road'] in roads for jam in response.get('traffic_jams', []))
            if all_match:
                print("✅ All returned traffic jams match the road filter")
            else:
                print("❌ Some traffic jams don't match the road filter")
                success = False
        return success

    def test_traffic_endpoint_with_city_filter(self):
        """Test the traffic endpoint with city filter"""
        success, response = self.run_test(
            "Traffic Endpoint (City Filter)",
            "GET",
            "traffic",
            200,
            params={"cities": "Eindhoven,Rotterdam"}
        )
        if success:
            print(f"Total traffic jams: {response.get('total_jams', 'N/A')}")
            print(f"Filtered traffic jams: {response.get('filtered_jams', 'N/A')}")
            
            # Verify that all returned traffic jams contain the specified cities
            cities = ["eindhoven", "rotterdam"]
            all_match = all(any(city in jam['location'].lower() for city in cities) 
                           for jam in response.get('traffic_jams', []))
            
            if all_match or len(response.get('traffic_jams', [])) == 0:
                print("✅ All returned traffic jams match the city filter (or no jams returned)")
            else:
                print("❌ Some traffic jams don't match the city filter")
                success = False
        return success

    def test_traffic_endpoint_with_delay_filter(self):
        """Test the traffic endpoint with delay filter"""
        min_delay = 15
        success, response = self.run_test(
            f"Traffic Endpoint (Min Delay {min_delay})",
            "GET",
            "traffic",
            200,
            params={"min_delay": min_delay}
        )
        if success:
            print(f"Total traffic jams: {response.get('total_jams', 'N/A')}")
            print(f"Filtered traffic jams: {response.get('filtered_jams', 'N/A')}")
            
            # Verify that all returned traffic jams have at least the minimum delay
            all_match = all(jam.get('delay_minutes', 0) >= min_delay 
                           for jam in response.get('traffic_jams', []))
            
            if all_match or len(response.get('traffic_jams', [])) == 0:
                print(f"✅ All returned traffic jams have delay >= {min_delay} minutes (or no jams returned)")
            else:
                print(f"❌ Some traffic jams have delay < {min_delay} minutes")
                success = False
        return success

    def test_refresh_endpoint(self):
        """Test the refresh endpoint"""
        success, response = self.run_test(
            "Refresh Endpoint",
            "POST",
            "refresh",
            200
        )
        if success:
            print(f"Response: {response}")
        return success

    def test_status_endpoint(self):
        """Test the status endpoint"""
        success, response = self.run_test(
            "Status Endpoint",
            "GET",
            "status",
            200
        )
        if success:
            print(f"Status: {response.get('status', 'N/A')}")
            print(f"Last updated: {response.get('last_updated', 'N/A')}")
            print(f"Traffic jams count: {response.get('traffic_jams_count', 'N/A')}")
            print(f"Speed cameras count: {response.get('speed_cameras_count', 'N/A')}")
            print(f"Target roads: {len(response.get('target_roads', []))}")
            print(f"Target cities: {len(response.get('target_cities', []))}")
        return success

def main():
    # Setup
    tester = ANWBTrafficMonitorTester()
    
    # Run tests
    tests = [
        tester.test_root_endpoint,
        tester.test_traffic_endpoint,
        tester.test_traffic_endpoint_with_road_filter,
        tester.test_traffic_endpoint_with_city_filter,
        tester.test_traffic_endpoint_with_delay_filter,
        tester.test_refresh_endpoint,
        tester.test_status_endpoint
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())