import json
from playwright.sync_api import sync_playwright
from datetime import datetime
import time
from src.models import WarnRecord, Employee, Address, WarnType
from src.utils import clean_impacted, derive_warn_type

def scrape_ok():
    url = "https://www.employoklahoma.gov/Participants/s/warnnotices"
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Navigating to {url}")
        page.goto(url, wait_until="networkidle")
        
        # Wait for the custom component to load
        page.wait_for_selector('c-o-e-s-c_-w-a-r-n-layoff-notices', timeout=30000)
        # Give it a bit more time for the inner content to fetch
        time.sleep(5)
        
        page_num = 1
        while True:
            print(f"Processing page {page_num}...")
            
            # Extract table data by piercing shadow roots via evaluate
            rows = page.evaluate("""
                () => {
                    function getAllShadowRoots(root) {
                        let results = [];
                        if (root.shadowRoot) {
                            results.push(root.shadowRoot);
                            results = results.concat(getAllShadowRoots(root.shadowRoot));
                        }
                        for (const child of root.children) {
                            results = results.concat(getAllShadowRoots(child));
                        }
                        return results;
                    }
                    
                    const roots = getAllShadowRoots(document.body);
                    for (const root of roots) {
                        const table = root.querySelector('table');
                        if (table) {
                            const dataRows = Array.from(table.querySelectorAll('tr')).slice(1); // skip headers
                            return dataRows.map(row => {
                                const cells = Array.from(row.querySelectorAll('td, th'));
                                return cells.map(cell => cell.innerText.trim());
                            });
                        }
                    }
                    return [];
                }
            """)
            
            print(f"Found {len(rows)} records on page {page_num}")
            for row in rows:
                if len(row) < 6:
                    continue
                
                employer_name = row[0]
                city = row[1]
                zip_code = row[2]
                warn_date_str = row[4]
                type_str = row[5]
                
                warn_date = None
                if warn_date_str:
                    try:
                        warn_date = datetime.strptime(warn_date_str, "%m/%d/%Y").date()
                    except:
                        pass

                record = WarnRecord(
                    employer=Employee(name=employer_name),
                    location=Address(
                        municipality=city if city else None,
                        state="ok",
                        zip=zip_code if zip_code else None
                    ),
                    warn_date=warn_date,
                    type=derive_warn_type(type_str)
                )
                results.append(record.model_dump(mode='json'))
            
            # Next button - also inside shadow root
            has_next = page.evaluate("""
                () => {
                    function getAllShadowRoots(root) {
                        let results = [];
                        if (root.shadowRoot) {
                            results.push(root.shadowRoot);
                            results = results.concat(getAllShadowRoots(root.shadowRoot));
                        }
                        for (const child of root.children) {
                            results = results.concat(getAllShadowRoots(child));
                        }
                        return results;
                    }
                    
                    const roots = getAllShadowRoots(document.body);
                    for (const root of roots) {
                        const nextBtn = Array.from(root.querySelectorAll('button, a')).find(el => el.innerText.trim() === 'Next');
                        if (nextBtn && !nextBtn.disabled && nextBtn.getAttribute('disabled') === null) {
                            nextBtn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            if not has_next:
                print("No more pages.")
                break
                
            page_num += 1
            time.sleep(3) # Wait for page transition
            
        browser.close()
        
    with open("data/ok.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Scraped {len(results)} records to data/ok.json")

if __name__ == "__main__":
    scrape_ok()
