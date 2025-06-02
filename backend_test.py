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
            
            # Check if all roads and cities are filtered by default
            if response.get('total_jams', 0) == response.get('filtered_jams', 0):
                print("✅ All roads and cities are filtered by default")
            else:
                print("❌ Not all roads and cities are filtered by default")
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

    def test_speed_cameras_hectometer(self):
        """Test that speed cameras include hectometer field"""
        success, response = self.run_test(
            "Speed Cameras Hectometer Field",
            "GET",
            "traffic",
            200
        )
        if success:
            speed_cameras = response.get('speed_cameras', [])
            if not speed_cameras:
                print("⚠️ No speed cameras found to test")
                return True
                
            # Check if all speed cameras have hectometer field
            cameras_with_hectometer = [cam for cam in speed_cameras if 'hectometer' in cam and cam['hectometer']]
            
            if cameras_with_hectometer:
                print(f"✅ Found {len(cameras_with_hectometer)}/{len(speed_cameras)} speed cameras with hectometer field")
                # Print a sample hectometer value
                sample = cameras_with_hectometer[0]
                print(f"Sample hectometer: {sample['hectometer']} for {sample['road']} at {sample['location']}")
                return True
            else:
                print("❌ No speed cameras have hectometer field")
                return False
        return success

    def test_dutch_text_format(self):
        """Test that API returns data in Dutch format"""
        success, response = self.run_test(
            "Dutch Text Format",
            "GET",
            "traffic",
            200
        )
        if success:
            # Check for Dutch text in delay_text
            dutch_terms = ["minuten", "geen", "vertraging"]
            
            traffic_jams = response.get('traffic_jams', [])
            if not traffic_jams:
                print("⚠️ No traffic jams found to test Dutch text")
                return True
                
            # Check if any traffic jam has Dutch text
            has_dutch = any(any(term in jam.get('delay_text', '').lower() for term in dutch_terms) 
                           for jam in traffic_jams)
            
            if has_dutch:
                print("✅ Found Dutch text in traffic jam data")
                # Print a sample
                for jam in traffic_jams:
                    if any(term in jam.get('delay_text', '').lower() for term in dutch_terms):
                        print(f"Sample Dutch text: {jam.get('delay_text')} for {jam.get('road')}")
                        break
            else:
                print("❌ No Dutch text found in traffic jam data")
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
        tester.test_traffic_endpoint_with_delay_filter,
        tester.test_speed_cameras_hectometer,
        tester.test_dutch_text_format,
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