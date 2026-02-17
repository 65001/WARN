import json
import requests
import pandas as pd
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

def parse_date(val):
    """Parse various date formats into date objects."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    date_str = str(val).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def get_col(row, aliases):
    """Get column value by checking various possible header names."""
    for alias in aliases:
        if alias in row:
            return row[alias]
        for k in row.keys():
            if str(k).replace('\n', ' ').strip().lower() == alias.lower():
                return row[k]
    return None

def process_xlsx(url):
    """Download and process the XLSX file from Texas."""
    print(f"Processing XLSX: {url}")
    local_file = "data/tx_current.xlsx"
    xls = None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        with open(local_file, "wb") as f:
            f.write(response.content)
        
        xls = pd.ExcelFile(local_file)
        # Use first sheet or look for relevant sheet
        sheet_name = xls.sheet_names[0]
        
        # Try to detect header row
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Close handle immediately
        xls.close()
        xls = None
        
        results = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            
            # Texas-specific column names
            company = get_col(row_dict, [
                'JOB_SITE_NAME', 'Company', 'Employer', 'Company Name'
            ])
            
            city = get_col(row_dict, [
                'CITY_NAME', 'City', 'Municipality'
            ])
            
            county = get_col(row_dict, [
                'COUNTY_NAME', 'County'
            ])
            
            zip_code = None  # Not in Texas data
            
            warn_date = parse_date(get_col(row_dict, [
                'NOTICE_DATE', 'WFDD_RECEIVED_DATE', 'Notice Date', 'Received Date'
            ]))
            
            layoff_date = parse_date(get_col(row_dict, [
                'LayOff_Date', 'Layoff_Date', 'Effective Date', 'Layoff Date'
            ]))
            
            impacted = get_col(row_dict, [
                'TOTAL_LAYOFF_NUMBER', 'No. of Employees', 'Number of Employees'
            ])
            
            type_str = None  # Not explicitly in Texas data
            
            if not company or pd.isna(company):
                continue
            
            # Build notes with county info if available
            notes = None
            if county and not pd.isna(county):
                notes = f"County: {county}"
            
            record = WarnRecord(
                employer=Employee(name=str(company).strip()),
                location=Address(
                    municipality=str(city).strip() if city and not pd.isna(city) else None,
                    state="tx",
                    zip=zip_code
                ),
                warn_date=warn_date,
                layoff_date=layoff_date,
                type=derive_warn_type(str(type_str)) if type_str and not pd.isna(type_str) else None,
                impacted=clean_impacted(str(impacted)) if impacted and not pd.isna(impacted) else None,
                notes=notes,
                link=url
            )
            results.append(record.model_dump(mode='json'))
        return results
    except Exception as e:
        print(f"Error processing XLSX {url}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if xls:
            xls.close()
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except Exception as e:
                print(f"Could not delete {local_file}: {e}")

def scrape_tx():
    """Scrape Texas WARN data."""
    base_url = "https://www.twc.texas.gov/data-reports/warn-notice"
    all_results = []
    
    if not os.path.exists('data'):
        os.makedirs('data')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Finding XLSX links on {base_url}")
        page.goto(base_url)
        
        # Extract all links to XLSX files
        links = page.evaluate("""
            () => {
                const results = [];
                const anchorElements = Array.from(document.querySelectorAll('a'));
                for (const a of anchorElements) {
                    const href = a.href;
                    if (href.includes('.xlsx') || href.includes('.xls')) {
                        results.push({text: a.innerText, href: a.href});
                    }
                }
                return results;
            }
        """)
        browser.close()
    
    print(f"Found {len(links)} XLSX link(s)")
    
    # Remove duplicates
    unique_links = {l['href']: l for l in links}.values()
    
    for l in unique_links:
        url = l['href']
        print(f"Processing: {l['text']} ({url})")
        all_results.extend(process_xlsx(url))
    
    # Save results
    with open("data/tx.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"Scraped {len(all_results)} records from Texas WARN to data/tx.json")

if __name__ == "__main__":
    scrape_tx()
