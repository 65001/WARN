import json
import requests
import pandas as pd
import pdfplumber
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

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

def parse_address(address_str):
    if not address_str or pd.isna(address_str):
        return {"street": None, "municipality": None, "zip": None}
    
    addr = str(address_str).strip()
    zip_code = None
    state_part = None
    city = None
    street = None
    
    # Try to extract zip at the end
    # "City CA 90210" or "City, CA 90210"
    # Check last chunk
    parts = addr.split(' ')
    if len(parts) > 0:
        last = parts[-1].strip()
        # format 90210 or 90210-1234
        if last.replace('-','').isdigit() and len(last) >= 5:
            zip_code = last
            # Remove zip from addr for further processing
            addr = addr[:-len(last)].strip()

    # Now look for " CA "
    if ' CA ' in addr:
        pre_ca, post_ca = addr.split(' CA ', 1)
        pre_ca = pre_ca.strip()
        # Post CA might have been just the zip, which we handled, or empty.
        
        # Now parse pre_ca for City
        # Use our strategy from before to separate Street from City
        if '  ' in pre_ca:
            segments = pre_ca.split('  ')
            # Assuming last segment is city, previous is street
            # Filter empty
            segments = [s.strip() for s in segments if s.strip()]
            if len(segments) >= 2:
                city = segments[-1]
                street = " ".join(segments[:-1])
            elif len(segments) == 1:
                # Ambiguous, but maybe just city or just street?
                # Usually if "  " matches, it splits them
                pass 
                
        if not city:
             # Try comma
            if ',' in pre_ca:
                segs = pre_ca.split(',')
                city = segs[-1].strip()
                street = ",".join(segs[:-1]).strip()
                
                # Cleanup common fragments from Street that might leak into city via comma
                # (e.g. "123 Main St, Suite 100, City") -> City is fine
                # But "123 Main St, City" -> City is fine
        
        if not city:
             # Suffix fallback
            suffixes = [
                ' Blvd', ' St', ' Ave', ' Rd', ' Ln', ' Dr', ' Way', ' Pl', ' Ct', ' Ter', ' Cir', 
                ' Hwy', ' Pkwy', ' Sq'
            ]
            for suffix in suffixes:
                # Suffix with period
                s_dot = suffix + '.'
                if s_dot in pre_ca:
                    parts = pre_ca.split(s_dot)
                    if len(parts) > 1:
                        street = parts[0].strip() + s_dot
                        city = "".join(parts[1:]).strip(' ,')
                        break
                
                # Suffix without period
                if not city and suffix in pre_ca:
                    parts = pre_ca.split(suffix)
                    # Be careful not to match partial words, but we have leading space in suffix list
                    if len(parts) > 1:
                        # reconstruct street with suffix
                        # "123 Main St City" -> split " St" -> ["123 Main", " City"]
                        street = parts[0].strip() + suffix
                        city = "".join(parts[1:]).strip(' ,')
                        break
    
    # Fallbacks if strict parsing failed
    if not city and not street and ',' in addr:
        # "City, CA" (zip removed)
        segs = addr.split(',')
        if len(segs) >= 2:
             # This assumes CA was handled or missing? 
             # actually if we are here, ' CA ' wasn't found or failed
             pass

    # Clean up fields
    if city:
        # Check for numeric suite info leaking into city
        # "Suite 100 City" -> split failed?
        pass
    
    return {
        "street": street,
        "municipality": city,
        "zip": zip_code
    }

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
            
            parsed = parse_address(address_str)
            
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
                    
                    parsed = parse_address(address_str)
                    
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
