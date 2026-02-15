import json
from playwright.sync_api import sync_playwright
from datetime import datetime
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted

def scrape_ut():
    url = "https://jobs.utah.gov/employer/business/warnnotices.html"
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}")
        page.goto(url)
        
        # Utah lists them in tables per year
        tables = page.locator("table")
        count = tables.count()
        print(f"Found {count} tables")
        
        for i in range(count):
            table = tables.nth(i)
            rows = table.locator("tr")
            row_count = rows.count()
            
            # Skip header row
            for j in range(1, row_count):
                cols = rows.nth(j).locator("td")
                if cols.count() >= 4:
                    date_str = cols.nth(0).inner_text().strip()
                    company = cols.nth(1).inner_text().strip()
                    location_str = cols.nth(2).inner_text().strip()
                    impacted_str = cols.nth(3).inner_text().strip()
                    
                    # Parse date MM/DD/YYYY
                    warn_date = None
                    try:
                        warn_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                    except:
                        pass
                    
                    # Location usually "City, UT" or just "City"
                    municipality = location_str.split(',')[0].strip()
                    
                    record = WarnRecord(
                        employer=Employee(name=company),
                        location=Address(
                            municipality=municipality,
                            state="ut"
                        ),
                        warn_date=warn_date,
                        impacted=clean_impacted(impacted_str)
                    )
                    results.append(record.model_dump(mode='json'))
        
        browser.close()
        
    with open("data/ut.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Scraped {len(results)} records to data/ut.json")

if __name__ == "__main__":
    scrape_ut()
