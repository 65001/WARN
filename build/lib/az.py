import json
from playwright.sync_api import sync_playwright
from datetime import datetime
import time

def scrape_az():
    url = "https://www.azjobconnection.gov/search/warn_lookups/new"
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Navigating to {url}")
        page.goto(url)
        
        # Click search to get all results
        page.click("input[name='commit']")
        page.wait_for_selector("table")
        
        page_num = 1
        while True:
            print(f"Scraping results page {page_num}...")
            # Get detail links from current page
            detail_links = page.eval_on_selector_all(
                "table tbody tr td:first-child a",
                "links => links.map(a => a.href)"
            )
            
            for link in detail_links:
                detail_page = browser.new_page()
                detail_page.goto(link)
                
                # Extract data from detail page
                try:
                    company = detail_page.locator("h3:has-text('Company Name') + p").inner_text().strip()
                    address_text = detail_page.locator("h3:has-text('Address') + p").inner_text().strip()
                    # Address format: 
                    # 3333 S. 59th Ave
                    # Phoenix, Arizona 85043
                    address_parts = address_text.split('\n')
                    street_address = address_parts[0] if len(address_parts) > 0 else ""
                    
                    municipality = ""
                    zip_code = ""
                    if len(address_parts) > 1:
                        city_state_zip = address_parts[1].split(',')
                        municipality = city_state_zip[0].strip()
                        if len(city_state_zip) > 1:
                            # Arizona 85043
                            state_zip = city_state_zip[1].strip().split(' ')
                            if len(state_zip) > 1:
                                zip_code = state_zip[-1]
                    
                    warn_date_raw = detail_page.locator("h3:has-text('Notice Date') + p").inner_text().strip()
                    # Format: Dec 13, 2023
                    warn_date = datetime.strptime(warn_date_raw, "%b %d, %Y").strftime("%Y-%m-%d")
                    
                    employees_impacted = detail_page.locator("h3:has-text('Number of Employees Affected') + p").inner_text().strip()
                    
                    results.append({
                        "warn_date": warn_date,
                        "company": company,
                        "street_address": street_address,
                        "municipality": municipality,
                        "zip_code": zip_code,
                        "employees_impacted": employees_impacted,
                        "state": "az"
                    })
                except Exception as e:
                    print(f"Error scraping {link}: {e}")
                
                detail_page.close()
            
            # Check for next page
            next_link = page.query_selector("a.next_page")
            if next_link:
                next_url = next_link.get_attribute("href")
                page.goto(f"https://www.azjobconnection.gov{next_url}")
                page_num += 1
                # Add a small delay to be nice
                time.sleep(1)
            else:
                break
                
        browser.close()
        
    with open("data/az.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Scraped {len(results)} records to data/az.json")

if __name__ == "__main__":
    scrape_az()
