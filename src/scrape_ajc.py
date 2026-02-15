import json
from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import os
from src.models import WarnRecord, Employee, Address, Contact
from src.utils import clean_impacted, derive_warn_type

def scrape_ajc(base_url, state_code, output_file):
    print(f"Starting scrape for {state_code} at {base_url}")
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = context.new_page()
        
        page.goto(base_url)
        
        # In some cases we might need to click search if it's the base lookup page
        if "commit=Search" not in base_url and page.query_selector("input[name='commit']"):
             page.click("input[name='commit']")
        
        page_num = 1
        while True:
            print(f"[{state_code}] Processing page {page_num}...")
            
            # Wait for table
            try:
                page.wait_for_selector("table", timeout=15000)
            except:
                print(f"[{state_code}] Table not found on page {page_num}")
                break
                
            # Find all detail links (numeric IDs only)
            all_links = page.eval_on_selector_all(
                "a[href*='/search/warn_lookups/']",
                "links => links.map(a => a.href)"
            )
            # Filter for numeric IDs
            links = [l for l in all_links if l.rstrip('/').split('/')[-1].isdigit()]
            # Dedup links
            links = list(set(links))
            print(f"[{state_code}] Found {len(links)} records on page {page_num}")
            
            for link in links:
                # Use a new page to keep search results alive
                detail_page = context.new_page()
                try:
                    print(f"[{state_code}] Scraping detail: {link}")
                    detail_page.goto(link, timeout=30000)
                    
                    # Extract Data
                    # Helper to get field by label
                    def get_field(label):
                        # Try a few variations of selectors
                        selectors = [
                            f"h3:has-text('{label}') + *",
                            f"h4:has-text('{label}') + *",
                            f"strong:has-text('{label}') + *",
                            f"div:has-text('{label}') + div"
                        ]
                        for sel in selectors:
                            loc = detail_page.locator(sel)
                            if loc.count() > 0:
                                return loc.first.inner_text().strip()
                        return None

                    # Specific fields
                    company = detail_page.locator("h1").first.inner_text().strip() if detail_page.locator("h1").count() > 0 else "Unknown"
                    address_text = get_field("Address")
                    warn_date_str = get_field("Notice Date")
                    impacted_str = get_field("Number of Employees Affected")
                    
                    # Check for layoff date or type if available
                    layoff_date_str = get_field("Layoff Date") or get_field("Effective Date")
                    warn_type_str = get_field("Type") or get_field("Notice Type")
                    
                    # Handle Address
                    street = None
                    municipality = None
                    zip_code = None
                    if address_text:
                        parts = address_text.split('\n')
                        street = parts[0].strip() if len(parts) > 0 else None
                        if len(parts) > 1:
                            # City, State Zip
                            city_state = parts[1].split(',')
                            municipality = city_state[0].strip()
                            if len(city_state) > 1:
                                sz = city_state[1].strip().rsplit(' ', 1)
                                zip_code = sz[-1] if len(sz) > 1 else None

                    # Parse dates
                    warn_date = None
                    if warn_date_str:
                        try:
                            warn_date = datetime.strptime(warn_date_str, "%m/%d/%Y").date()
                        except:
                            try:
                                warn_date = datetime.strptime(warn_date_str, "%b %d, %Y").date()
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
                            street=street,
                            municipality=municipality,
                            state=state_code,
                            zip=zip_code
                        ),
                        warn_date=warn_date,
                        layoff_date=layoff_date,
                        type=derive_warn_type(warn_type_str) if warn_type_str else None,
                        impacted=clean_impacted(impacted_str),
                        link=link
                    )
                    results.append(record.model_dump(mode='json'))
                except Exception as e:
                    print(f"[{state_code}] Error on {link}: {e}")
                finally:
                    detail_page.close()
            
            # Save progress after each page
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)

            # Next page
            next_link = page.query_selector("a.next_page, a[rel='next']")
            if next_link:
                page_url = next_link.get_attribute("href")
                if page_url.startswith("/"):
                    # Reconstruct URL
                    domain = "/".join(page.url.split("/")[:3])
                    next_url = domain + page_url
                else:
                    next_url = page_url
                
                print(f"[{state_code}] Moving to next page: {next_url}")
                page.goto(next_url)
                page_num += 1
                time.sleep(2)
            else:
                print(f"[{state_code}] No next page link found.")
                break
                
        browser.close()
        
    print(f"[{state_code}] Finished. Total results: {len(results)}")

if __name__ == "__main__":
    # Test with AZ
    az_url = "https://www.azjobconnection.gov/search/warn_lookups/new"
    scrape_ajc(az_url, "az", "data/az.json")
