import requests
import sys
import json
from datetime import datetime

class GlowFMVerkeerTester:
    def __init__(self, base_url="https://bc4668cd-3e1d-4a51-8563-9ce46c9a86d6.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.expected_roads = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270"]

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

    def test_traffic_jams_count(self):
        """Test that there are 0 traffic jams returned"""
        success, response = self.run_test(
            "Traffic Jams Count (Should be 0)",
            "GET",
            "traffic",
            200
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            traffic_jam_count = len(traffic_jams)
            
            if traffic_jam_count == 0:
                print("✅ API returns 0 traffic jams as expected")
                return True
            else:
                print(f"❌ API returns {traffic_jam_count} traffic jams, expected 0")
                print(f"Traffic jams found: {traffic_jams}")
                return False
        return success

    def test_speed_cameras_count_and_details(self):
        """Test that there is 1 speed camera on A16 at Zevenbergschen Hoek"""
        success, response = self.run_test(
            "Speed Cameras Count and Details",
            "GET",
            "traffic",
            200
        )
        if success:
            speed_cameras = response.get('speed_cameras', [])
            speed_camera_count = len(speed_cameras)
            
            if speed_camera_count == 1:
                print("✅ API returns 1 speed camera as expected")
                
                # Check camera details
                camera = speed_cameras[0]
                if camera.get('road') == 'A16':
                    print("✅ Speed camera is on A16 as expected")
                else:
                    print(f"❌ Speed camera is on {camera.get('road')}, expected A16")
                    return False
                
                if camera.get('location') == 'Zevenbergschen Hoek':
                    print("✅ Speed camera location is Zevenbergschen Hoek as expected")
                else:
                    print(f"❌ Speed camera location is {camera.get('location')}, expected Zevenbergschen Hoek")
                    return False
                
                if camera.get('hectometer') == '102.8':
                    print("✅ Speed camera hectometer is 102.8 as expected")
                else:
                    print(f"❌ Speed camera hectometer is {camera.get('hectometer')}, expected 102.8")
                    return False
                
                # Check that no A2 or Moerdijkbrug cameras exist
                a2_cameras = [cam for cam in speed_cameras if cam.get('road') == 'A2']
                moerdijk_cameras = [cam for cam in speed_cameras if 'Moerdijk' in cam.get('location', '')]
                
                if not a2_cameras:
                    print("✅ No A2 speed cameras found as expected")
                else:
                    print(f"❌ Found {len(a2_cameras)} A2 speed cameras, expected 0")
                    return False
                
                if not moerdijk_cameras:
                    print("✅ No Moerdijkbrug speed cameras found as expected")
                else:
                    print(f"❌ Found {len(moerdijk_cameras)} Moerdijkbrug speed cameras, expected 0")
                    return False
                
                return True
            else:
                print(f"❌ API returns {speed_camera_count} speed cameras, expected 1")
                print(f"Speed cameras found: {speed_cameras}")
                return False
        return success

    def test_custom_messages(self):
        """Test that API returns custom messages for empty sections"""
        success, response = self.run_test(
            "Custom Messages",
            "GET",
            "traffic",
            200
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            
            # Check that there are 0 traffic jams (for custom message testing)
            if len(traffic_jams) == 0:
                print("✅ No traffic jams found, can test custom message in UI")
            else:
                print(f"❌ Found {len(traffic_jams)} traffic jams, expected 0 for custom message testing")
                return False
                
            # Note: We can't directly test the UI messages here, but we can verify the data
            # that will trigger those messages. The actual UI messages will be tested with Playwright.
            
            return True
        return success

    def test_status_endpoint(self):
        """Test the status endpoint for correct data"""
        success, response = self.run_test(
            "Status Endpoint",
            "GET",
            "status",
            200
        )
        if success:
            target_roads = response.get('target_roads', [])
            
            if len(target_roads) == 14 and set(target_roads) == set(self.expected_roads):
                print(f"✅ Status endpoint returns all 14 expected roads")
            else:
                print(f"❌ Status endpoint returns incorrect roads")
                print(f"Expected: {', '.join(self.expected_roads)}")
                print(f"Actual: {', '.join(target_roads)}")
                success = False
                
            # Check speed camera count
            speed_camera_count = response.get('speed_cameras_count', -1)
            if speed_camera_count == 1:
                print("✅ Status endpoint reports 1 speed camera as expected")
            else:
                print(f"❌ Status endpoint reports {speed_camera_count} speed cameras, expected 1")
                success = False
                
        return success

def main():
    # Setup
    tester = GlowFMVerkeerTester()
    
    # Run tests
    tests = [
        tester.test_traffic_jams_count,
        tester.test_speed_cameras_count_and_details,
        tester.test_custom_messages,
        tester.test_status_endpoint
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())