import pandas as pd
import requests
import json
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

# Disable insecure request warning for verify=False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def add_prefix(link):
    if link is not None:
        return "https://www.ctdol.state.ct.us/progsupt/bussrvce/warnreports/" + link
    return link
    
def parse_warn_date(date):
    pins = ['Rec\'d', 'Rec’d', 'Recd', 'Received', 'Revised', 'Not Dated Rec\'d']
    for pin in pins:
        if pin in date:
            start = date.index(pin)
            length = len(pin)
            return date[start + length:].strip()
    return date

def parse(url):
    print('Visiting ' + url)
    try:
        response = requests.get(url, verify=False)
        df = pd.read_html(response.text, extract_links='body')
        df = df[9]
        df = df.tail(-1) # The first row is headers
        df = df.rename(columns={0: "warn_date_raw", 1: "company_raw", 2: "municipality_raw", 3: "employees_impacted_raw", 4: "layoff_date_raw", 8: "union_address_raw"})
        
        records = []
        for _, row in df.iterrows():
            try:
                company_name, link = row['company_raw']
                municipality, _ = row['municipality_raw']
                warn_date_str, _ = row['warn_date_raw']
                layoff_date_str, _ = row['layoff_date_raw']
                impacted_str, _ = row['employees_impacted_raw']
                union_info, _ = row['union_address_raw']

                warn_date_clean = parse_warn_date(warn_date_str)
                warn_date = pd.to_datetime(warn_date_clean, errors='coerce')
                layoff_date = pd.to_datetime(layoff_date_str, errors='coerce')

                record = WarnRecord(
                    employer=Employee(name=company_name),
                    location=Address(
                        municipality=municipality,
                        state="ct"
                    ),
                    union=Employee(name=union_info) if union_info else None,
                    warn_date=warn_date.date() if pd.notna(warn_date) else None,
                    layoff_date=layoff_date.date() if pd.notna(layoff_date) else None,
                    impacted=clean_impacted(impacted_str),
                    link=add_prefix(link)
                )
                records.append(record.model_dump(mode='json'))
            except Exception as e:
                print(f"Error parsing row: {e}")
        return records
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return []

def scrape_ct():
    all_records = []
    # For speed, let's just do a few recent years or a specific range
    for year in range(2022, 2025):
        url = f'https://www.ctdol.state.ct.us/progsupt/bussrvce/warnreports/warn{year}.htm'
        all_records.extend(parse(url))

    with open("./data/ct.json", "w") as f:
        json.dump(all_records, f, indent=2)

if __name__ == "__main__":
    scrape_ct()