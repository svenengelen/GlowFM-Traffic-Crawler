import requests
import sys
import json
from datetime import datetime

class GlowFMVerkeerTester:
    def __init__(self, base_url="https://bc4668cd-3e1d-4a51-8563-9ce46c9a86d6.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.expected_roads = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270", "N279"]

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

    def test_a67_traffic_jams(self):
        """Test that there are 2 A67 traffic jams with accidents in both directions"""
        success, response = self.run_test(
            "A67 Traffic Jams (Should be 2 with accidents)",
            "GET",
            "traffic",
            200
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            a67_jams = [jam for jam in traffic_jams if jam.get('road') == 'A67']
            
            if len(a67_jams) == 2:
                print(f"✅ API returns 2 A67 traffic jams as expected")
                
                # Check for accident in both directions
                directions = set()
                accident_count = 0
                
                for jam in a67_jams:
                    location = jam.get('location', '')
                    if 'Panningen' in location and 'Venlo-Noordwest' in location:
                        print(f"✅ A67 jam includes correct location: {location}")
                    else:
                        print(f"❌ A67 jam has unexpected location: {location}")
                        return False
                    
                    # Extract direction from location
                    if 'Richting Venlo' in location:
                        directions.add('Venlo')
                    elif 'Richting Eindhoven' in location:
                        directions.add('Eindhoven')
                    
                    # Check for accident in delay text
                    delay_text = jam.get('delay_text', '')
                    if 'Ongeval' in delay_text:
                        accident_count += 1
                        print(f"✅ A67 jam includes accident info: {delay_text}")
                    else:
                        print(f"❌ A67 jam missing accident info: {delay_text}")
                        return False
                
                if len(directions) == 2:
                    print("✅ A67 jams cover both directions (Venlo and Eindhoven)")
                else:
                    print(f"❌ A67 jams don't cover both directions. Found: {directions}")
                    return False
                
                if accident_count == 2:
                    print("✅ Both A67 jams report accidents")
                else:
                    print(f"❌ Not all A67 jams report accidents. Found: {accident_count}/2")
                    return False
                
                return True
            else:
                print(f"❌ API returns {len(a67_jams)} A67 traffic jams, expected 2")
                print(f"Traffic jams found: {traffic_jams}")
                return False
        return success

    def test_speed_cameras_count(self):
        """Test that there are 0 speed cameras (Zevenbergschen Hoek removed)"""
        success, response = self.run_test(
            "Speed Cameras Count (Should be 0)",
            "GET",
            "traffic",
            200
        )
        if success:
            speed_cameras = response.get('speed_cameras', [])
            speed_camera_count = len(speed_cameras)
            
            if speed_camera_count == 0:
                print("✅ API returns 0 speed cameras as expected (Zevenbergschen Hoek removed)")
                return True
            else:
                print(f"❌ API returns {speed_camera_count} speed cameras, expected 0")
                print(f"Speed cameras found: {speed_cameras}")
                return False
        return success

    def test_refresh_endpoint(self):
        """Test the refresh endpoint tries multiple ANWB API endpoints"""
        success, response = self.run_test(
            "Refresh Endpoint",
            "POST",
            "refresh",
            200
        )
        if success:
            # We can't directly test the internal behavior, but we can verify the endpoint works
            if 'message' in response and 'timestamp' in response:
                print("✅ Refresh endpoint returns expected response format")
                return True
            else:
                print(f"❌ Refresh endpoint returns unexpected response format: {response}")
                return False
        return success

    def test_target_cities_filter(self):
        """Test that all exits and junctions are in TARGET_CITIES filter"""
        success, response = self.run_test(
            "Status Endpoint for TARGET_CITIES",
            "GET",
            "status",
            200
        )
        if success:
            target_cities = response.get('target_cities', [])
            
            # Check for key exits
            key_exits = [
                # A2 exits
                "Utrecht-Centrum", "Eindhoven-Centrum", "Maastricht-Noord",
                # A16 exits
                "Rotterdam-Kralingen", "Dordrecht", "Breda-Noord",
                # A50 exits
                "Helmond", "Oss", "Arnhem",
                # A67 exits
                "Panningen", "Venlo-Noordwest",
                # Junctions
                "Knp. Oudenrijn", "Knp. De Hogt", "Knp. Zaarderheiken"
            ]
            
            missing_exits = [exit for exit in key_exits if exit not in target_cities]
            
            if not missing_exits:
                print("✅ All key exits are included in TARGET_CITIES")
                return True
            else:
                print(f"❌ Some key exits are missing from TARGET_CITIES: {missing_exits}")
                return False
        return success

    def test_monitored_roads(self):
        """Test that all 15 roads are monitored including N279"""
        success, response = self.run_test(
            "Status Endpoint for Monitored Roads",
            "GET",
            "status",
            200
        )
        if success:
            target_roads = response.get('target_roads', [])
            
            if len(target_roads) == 15 and set(target_roads) == set(self.expected_roads):
                print(f"✅ Status endpoint returns all 15 expected roads including N279")
                return True
            else:
                print(f"❌ Status endpoint returns incorrect roads")
                print(f"Expected: {', '.join(self.expected_roads)}")
                print(f"Actual: {', '.join(target_roads)}")
                return False
        return success

def main():
    # Setup
    tester = GlowFMVerkeerTester()
    
    # Run tests
    tests = [
        tester.test_a67_traffic_jams,
        tester.test_speed_cameras_count,
        tester.test_refresh_endpoint,
        tester.test_target_cities_filter,
        tester.test_monitored_roads
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())