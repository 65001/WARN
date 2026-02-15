import json
from playwright.sync_api import sync_playwright
from datetime import datetime
import time
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

def scrape_wa():
    # Direct URL to the WARN database
    url = "https://fortress.wa.gov/esd/file/WARN/Public/SearchWARN.aspx"
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}")
        page.goto(url)
        
        page_num = 1
        while True:
            print(f"Processing page {page_num}...")
            
            # Wait for the table to be visible
            page.wait_for_selector("table", timeout=30000)
            
            # Extract rows
            rows_data = page.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return [];
                    const rows = Array.from(table.querySelectorAll('tr'));
                    // The first few rows might be headers or pagination info
                    // Based on previous snapshot, headings are in rows[2]
                    // and data starts from rows[3]
                    const dataRows = rows.filter(r => r.querySelectorAll('td').length >= 8);
                    
                    // Filter out the header row by searching for 'Company' text
                    const filtered = dataRows.filter(r => !r.innerText.includes('Company'));
                    
                    return filtered.map(row => {
                        const cells = Array.from(row.querySelectorAll('td'));
                        return cells.map(cell => cell.innerText.trim());
                    });
                }
            """)
            
            print(f"Found {len(rows_data)} records on page {page_num}")
            for row in rows_data:
                if len(row) < 7:
                    continue
                    
                company = row[0]
                location = row[1]
                layoff_date_str = row[2]
                impacted_str = row[3]
                action_type = row[4] # Closure/Layoff
                layoff_type = row[5] # Permanent/Temporary
                warn_date_str = row[6]
                
                warn_date = None
                if warn_date_str:
                    try:
                        warn_date = datetime.strptime(warn_date_str, "%m/%d/%Y").date()
                    except:
                        pass

                layoff_date = None
                if layoff_date_str:
                    try:
                        layoff_date = datetime.strptime(layoff_date_str, "%m/%d/%Y").date()
                    except:
                        pass

                record = WarnRecord(
                    employer=Employee(name=company),
                    location=Address(
                        municipality=location,
                        state="wa"
                    ),
                    warn_date=warn_date,
                    layoff_date=layoff_date,
                    type=derive_warn_type(f"{action_type} {layoff_type}"),
                    impacted=clean_impacted(impacted_str),
                    notes=f"Action: {action_type}, Type: {layoff_type}"
                )
                results.append(record.model_dump(mode='json'))
            
            # Check for next page
            target_page = str(page_num + 1)
            next_page_clicked = page.evaluate("""
                (target) => {
                    const pageLinks = Array.from(document.querySelectorAll('a'));
                    const nextLink = pageLinks.find(a => a.innerText.trim() === target);
                    if (nextLink) {
                        nextLink.click();
                        return true;
                    }
                    return false;
                }
            """, target_page)
            
            if not next_page_clicked:
                print("No more pages found.")
                break
                
            page_num += 1
            time.sleep(3) # Wait for page reload
            
        browser.close()
        
    with open("data/wa.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Scraped {len(results)} records to data/wa.json")

if __name__ == "__main__":
    scrape_wa()
