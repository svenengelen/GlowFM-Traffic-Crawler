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

    def test_speed_cameras_count(self):
        """Test that there are 0 speed cameras returned"""
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
                print("✅ API returns 0 speed cameras as expected")
                return True
            else:
                print(f"❌ API returns {speed_camera_count} speed cameras, expected 0")
                print(f"Speed cameras found: {speed_cameras}")
                return False
        return success

    def test_highway_sorting_and_count(self):
        """Test that all 14 highways are returned in correct order"""
        success, response = self.run_test(
            "Highway Sorting and Count",
            "GET",
            "traffic",
            200
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            
            # Extract road numbers
            roads = [jam.get('road') for jam in traffic_jams]
            
            # Check if all expected roads are present
            missing_roads = set(self.expected_roads) - set(roads)
            extra_roads = set(roads) - set(self.expected_roads)
            
            if not missing_roads and not extra_roads:
                print(f"✅ All expected roads are present: {', '.join(roads)}")
            else:
                if missing_roads:
                    print(f"❌ Missing roads: {', '.join(missing_roads)}")
                if extra_roads:
                    print(f"❌ Unexpected roads: {', '.join(extra_roads)}")
                success = False
            
            # Check if roads are in correct order
            expected_order = self.expected_roads
            if roads == expected_order:
                print("✅ Roads are in correct chronological order")
            else:
                print(f"❌ Roads are not in correct order")
                print(f"Expected: {', '.join(expected_order)}")
                print(f"Actual: {', '.join(roads)}")
                success = False
                
            # Check Dutch text for "Geen files" and "Vrij" status
            for jam in traffic_jams:
                if "Geen files" not in jam.get('delay_text', '') or "Vrij" not in jam.get('length_text', ''):
                    print(f"❌ Road {jam.get('road')} doesn't have expected Dutch text")
                    print(f"  delay_text: {jam.get('delay_text')}")
                    print(f"  length_text: {jam.get('length_text')}")
                    success = False
                    break
            else:
                print("✅ All roads have correct Dutch text ('Geen files' and 'Vrij')")
                
        return success

    def test_dutch_translations(self):
        """Test that API returns data with correct Dutch translations"""
        success, response = self.run_test(
            "Dutch Translations",
            "GET",
            "traffic",
            200
        )
        if success:
            traffic_jams = response.get('traffic_jams', [])
            
            # Check for Dutch text in delay_text and length_text
            dutch_delay_terms = ["Geen files"]
            dutch_length_terms = ["Vrij"]
            
            if not traffic_jams:
                print("⚠️ No traffic jams found to test Dutch text")
                return True
                
            # Check if traffic jams have correct Dutch text
            all_correct = True
            for jam in traffic_jams:
                delay_text = jam.get('delay_text', '')
                length_text = jam.get('length_text', '')
                
                if not any(term in delay_text for term in dutch_delay_terms):
                    print(f"❌ Road {jam.get('road')} has incorrect delay text: '{delay_text}'")
                    all_correct = False
                
                if not any(term in length_text for term in dutch_length_terms):
                    print(f"❌ Road {jam.get('road')} has incorrect length text: '{length_text}'")
                    all_correct = False
            
            if all_correct:
                print("✅ All traffic jams have correct Dutch translations")
                # Print a sample
                sample = traffic_jams[0]
                print(f"Sample Dutch text: {sample.get('road')} - {sample.get('delay_text')} - {sample.get('length_text')}")
            else:
                print("❌ Some traffic jams have incorrect Dutch translations")
                success = False
                
        return success

    def test_status_endpoint(self):
        """Test the status endpoint for correct road count"""
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
            if speed_camera_count == 0:
                print("✅ Status endpoint reports 0 speed cameras")
            else:
                print(f"❌ Status endpoint reports {speed_camera_count} speed cameras, expected 0")
                success = False
                
        return success

def main():
    # Setup
    tester = GlowFMVerkeerTester()
    
    # Run tests
    tests = [
        tester.test_speed_cameras_count,
        tester.test_highway_sorting_and_count,
        tester.test_dutch_translations,
        tester.test_status_endpoint
    ]
    
    for test in tests:
        test()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())