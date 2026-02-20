import json
import requests
import pandas as pd
import pdfplumber
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type, parse_address

def parse_date(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    date_str = str(val).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def get_col(row, aliases):
    for alias in aliases:
        if alias in row:
            return row[alias]
        for k in row.keys():
            if str(k).replace('\n', ' ').strip().lower() == alias.lower():
                return row[k]
    return None



def process_xlsx(url):
    print(f"Processing XLSX: {url}")
    local_file = "data/ca_current.xlsx"
    xls = None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        with open(local_file, "wb") as f:
            f.write(response.content)
        
        xls = pd.ExcelFile(local_file)
        sheets = [s for s in xls.sheet_names if 'Detailed' in s]
        sheet_name = sheets[0] if sheets else xls.sheet_names[0]
        
        df = pd.read_excel(xls, sheet_name=sheet_name, header=1)
        # Close handle immediately
        xls.close()
        xls = None
        
        results = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            company = get_col(row_dict, ['Company'])
            address_str = get_col(row_dict, ['Address'])
            warn_date = parse_date(get_col(row_dict, ['Processed Date', 'Received Date', 'Notice Date']))
            layoff_date = parse_date(get_col(row_dict, ['Effective Date']))
            impacted = get_col(row_dict, ['No. Of Employees', 'No. of Employees', 'Number of Employees'])
            type_str = get_col(row_dict, ['Layoff/Closure', 'Type of Action'])
            
            if not company or pd.isna(company):
                continue
            
            parsed = parse_address(address_str, state_fips='06')
            
            record = WarnRecord(
                employer=Employee(name=str(company).strip()),
                location=Address(
                    street=parsed['street'],
                    municipality=parsed['municipality'],
                    state="ca",
                    zip=parsed['zip']
                ),
                warn_date=warn_date,
                layoff_date=layoff_date,
                type=derive_warn_type(str(type_str)) if type_str else None,
                impacted=clean_impacted(str(impacted)),
                link=url
            )
            results.append(record.model_dump(mode='json'))
        return results
    except Exception as e:
        print(f"Error processing XLSX {url}: {e}")
        return []
    finally:
        if xls:
            xls.close()
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except Exception as e:
                print(f"Wait, could not delete {local_file}: {e}")

def process_pdf(url):
    print(f"Processing PDF: {url}")
    filename = url.split('/')[-1]
    local_path = f"data/{filename}"
    try:
        if not os.path.exists(local_path):
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            with open(local_path, "wb") as f:
                f.write(response.content)
        
        results = []
        with pdfplumber.open(local_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table or len(table) < 2:
                    continue
                
                raw_headers = [str(h).replace('\n', ' ').strip() for h in table[0]]
                idx_map = {}
                for i, h in enumerate(raw_headers):
                    h_lower = h.lower()
                    if 'company' in h_lower: idx_map['company'] = i
                    elif 'received' in h_lower or 'processed' in h_lower or 'notice date' in h_lower: idx_map['warn'] = i
                    elif 'effective' in h_lower: idx_map['layoff'] = i
                    elif 'no. of' in h_lower or 'number' in h_lower or 'emp' in h_lower: idx_map['impacted'] = i
                    elif 'layoff/closure' in h_lower or 'action' in h_lower: idx_map['type'] = i
                    elif 'address' in h_lower: idx_map['address'] = i
                    elif 'city' in h_lower: idx_map['city'] = i
                
                if 'company' not in idx_map:
                    continue

                for row in table[1:]:
                    if not row or len(row) <= idx_map['company']:
                        continue
                        
                    company = row[idx_map['company']]
                    if not company or str(company).strip().lower() == 'company':
                        continue
                        
                    warn_date = parse_date(row[idx_map['warn']]) if 'warn' in idx_map else None
                    layoff_date = parse_date(row[idx_map['layoff']]) if 'layoff' in idx_map else None
                    impacted_raw = row[idx_map['impacted']] if 'impacted' in idx_map else None
                    type_str = row[idx_map['type']] if 'type' in idx_map else None
                    address_str = row[idx_map['address']] if 'address' in idx_map else None
                    city_str = row[idx_map['city']] if 'city' in idx_map else None
                    
                    parsed = parse_address(address_str, state_fips='06')
                    
                    # If city was explicit in table, override
                    if city_str:
                         parsed['municipality'] = str(city_str).strip()

                    record = WarnRecord(
                        employer=Employee(name=str(company).strip()),
                        location=Address(
                            street=parsed['street'],
                            municipality=parsed['municipality'],
                            state="ca",
                            zip=parsed['zip']
                        ),
                        warn_date=warn_date,
                        layoff_date=layoff_date,
                        type=derive_warn_type(str(type_str)),
                        impacted=clean_impacted(str(impacted_raw)),
                        link=url
                    )
                    results.append(record.model_dump(mode='json'))
        return results
    except Exception as e:
        print(f"Error parsing PDF {url}: {e}")
        return []
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

def scrape_ca():
    base_url = "https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN/"
    all_results = []
    
    if not os.path.exists('data'):
        os.makedirs('data')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Finding links on {base_url}")
        page.goto(base_url)
        
        links = page.evaluate("""
            () => {
                const results = [];
                const anchorElements = Array.from(document.querySelectorAll('a'));
                for (const a of anchorElements) {
                    const text = a.innerText.toLowerCase();
                    const href = a.href;
                    if (href.includes('.xlsx') || href.includes('.pdf')) {
                        if (text.includes('warn report') || text.includes('listing of warn')) {
                            results.push({text: a.innerText, href: a.href});
                        }
                    }
                }
                for (const a of anchorElements) {
                    if (a.href.includes('/warn/') && a.href.endsWith('.pdf')) {
                        results.push({text: a.innerText, href: a.href});
                    }
                }
                return results;
            }
        """)
        browser.close()
        
    unique_links = {l['href']: l for l in links}.values()
    
    for l in unique_links:
        url = l['href']
        if url.endswith('.xlsx'):
            all_results.extend(process_xlsx(url))
        elif url.endswith('.pdf'):
            all_results.extend(process_pdf(url))
            
    with open("data/ca.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"Scraped {len(all_results)} records across all CA reports to data/ca.json")

if __name__ == "__main__":
    scrape_ca()
