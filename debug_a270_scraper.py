import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ANWBScraperDebugger:
    def __init__(self):
        self.base_url = "https://anwb.nl/verkeer/filelijst"
        self.driver = None
        self.monitored_roads = ['A2', 'A16', 'A50', 'A58', 'A59', 'A65', 'A67', 'A73', 'A76', 'A270', 'N2', 'N69', 'N266', 'N270']
        
    def _setup_driver(self):
        """Set up Selenium WebDriver with Chromium"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        # Use system Chromium
        chrome_options.binary_location = "/usr/bin/chromium"
        
        # Use system chromedriver
        service = Service("/usr/bin/chromedriver")
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Successfully initialized Chrome driver")
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise e

    def debug_a270_scraper(self):
        """Debug the A270 traffic jam extraction"""
        try:
            print(f"Starting A270 scraper debugging at {datetime.now()}")
            
            # Setup WebDriver
            self._setup_driver()
            
            # Navigate to the page
            self.driver.get(self.base_url)
            
            # Wait for the page to load and traffic data to appear
            print("Waiting for traffic data to load...")
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for traffic list to be present
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-accordion-road]")))
                print("Traffic data loaded successfully")
            except:
                print("Timeout waiting for traffic data, proceeding with available content")
            
            # Wait a bit more to ensure all content is loaded
            time.sleep(3)
            
            # Find all road articles
            road_articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-accordion-road]")
            print(f"Found {len(road_articles)} road articles")
            
            # Look specifically for A270
            a270_article = None
            for article in road_articles:
                road = article.get_attribute('data-accordion-road')
                print(f"Found road article: {road}")
                if road == 'A270':
                    a270_article = article
                    print("Found A270 article!")
                    break
            
            if not a270_article:
                print("A270 article not found in the page")
                return
            
            # Check if there are traffic jams (look for the totals indicator)
            try:
                total_indicator = a270_article.find_element(By.CSS_SELECTOR, "[data-test-id='traffic-list-road-totals']")
                total_text = total_indicator.text.strip()
                print(f"A270 total indicator text: '{total_text}'")
                
                if not total_text or total_text == "0":
                    print("No traffic jams found for A270 according to total indicator")
                else:
                    print(f"A270 has traffic jams according to total indicator: {total_text}")
            except Exception as e:
                print(f"Error finding total indicator for A270: {e}")
            
            # Try to expand the accordion
            try:
                print("Attempting to expand A270 accordion...")
                button = a270_article.find_element(By.CSS_SELECTOR, "button[data-test-id='traffic-list-road-header']")
                self.driver.execute_script("arguments[0].click();", button)
                print("Expanded A270 accordion")
                
                # Wait for content to load
                time.sleep(2)
                
                # Get all text from the expanded accordion
                expanded_text = a270_article.text.strip()
                print(f"A270 expanded accordion text: '{expanded_text}'")
                
                # Extract individual traffic jam items
                try:
                    jam_items = a270_article.find_elements(By.CSS_SELECTOR, "div[data-test-id*='traffic-item'], li[data-test-id*='traffic-item'], .traffic-item")
                    
                    if not jam_items:
                        # Try alternative selectors for traffic items
                        jam_items = a270_article.find_elements(By.CSS_SELECTOR, "div[class*='traffic'], li[class*='jam'], .file-item")
                    
                    print(f"Found {len(jam_items)} traffic items for A270")
                    
                    if jam_items:
                        for idx, item in enumerate(jam_items):
                            item_text = item.text.strip()
                            print(f"A270 traffic item {idx}: '{item_text}'")
                            
                            # Try to extract delay and length
                            delay_minutes = self._extract_delay_minutes(item_text)
                            length_km = self._extract_length_km(item_text)
                            
                            print(f"Extracted delay: {delay_minutes} min, length: {length_km} km")
                    else:
                        print("No specific traffic items found for A270")
                except Exception as e:
                    print(f"Error extracting traffic items for A270: {e}")
                
            except Exception as e:
                print(f"Error expanding accordion for A270: {e}")
            
            # Try to find any traffic-related information in the page source
            page_source = self.driver.page_source
            a270_mentions = page_source.count("A270")
            print(f"A270 is mentioned {a270_mentions} times in the page source")
            
            # Check if there are any elements with A270 text
            a270_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'A270')]")
            print(f"Found {len(a270_elements)} elements containing 'A270' text")
            
            for idx, elem in enumerate(a270_elements):
                try:
                    elem_text = elem.text.strip()
                    elem_tag = elem.tag_name
                    print(f"A270 element {idx} ({elem_tag}): '{elem_text}'")
                except:
                    print(f"Could not get text for A270 element {idx}")
            
        except Exception as e:
            print(f"Error in debug_a270_scraper: {e}")
        finally:
            # Clean up the driver
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
    
    def _extract_delay_minutes(self, text):
        """Extract delay in minutes from text like '+ 12 min'"""
        import re
        try:
            match = re.search(r'\+\s*(\d+)\s*min', text)
            if match:
                return int(match.group(1))
        except:
            pass
        return 0
    
    def _extract_length_km(self, text):
        """Extract length in km from text like '4 km'"""
        import re
        try:
            match = re.search(r'(\d+(?:\.\d+)?)\s*km', text)
            if match:
                return float(match.group(1))
        except:
            pass
        return 0.0

if __name__ == "__main__":
    debugger = ANWBScraperDebugger()
    debugger.debug_a270_scraper()
