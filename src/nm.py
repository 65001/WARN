import requests
import pdfplumber
import pandas as pd
import io
import json
import re
from datetime import datetime

from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

def parse_date(date_str):
    if not date_str:
        return None
    try:
        # Dates in PDF appear as M/D/YY, e.g., 1/16/24
        return datetime.strptime(str(date_str).strip(), "%m/%d/%y").date()
    except ValueError:
        return None

def scrape_nm():
    # NM DWS 2024 WARN Notice URL
    url = "https://www.dws.state.nm.us/Portals/0/DM/Business/2024_WARN.pdf"
    print(f"Fetching {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        records = []
        
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if not tables:
                    continue
                    
                for table in tables:
                    if len(table) < 2:
                        continue
                        
                    # Locate header row
                    header_row_idx = -1
                    for i, row in enumerate(table):
                        # Join row elements into a single string to search for keywords
                        row_str = " ".join([str(cell).replace('\n', ' ') for cell in row if cell]).upper()
                        if "NOTICE DATE" in row_str and "JOB SITE NAME" in row_str:
                            header_row_idx = i
                            break
                    
                    if header_row_idx == -1:
                        continue
                        
                    # Map columns based on index
                    headers = [str(cell).replace('\n', ' ').strip().upper() for cell in table[header_row_idx] if cell]
                    
                    # Create a simple mapping based on header text
                    # Since pdfplumber returns a list of lists, we need column indices
                    # However, table extraction might have merged cells or None.
                    # Let's try to map by column index assuming standard layout or matching header text to index
                    
                    # Refine mapping strategy: Identify column indices by header text
                    header_map = {}
                    raw_header_row = table[header_row_idx]
                    for idx, cell in enumerate(raw_header_row):
                        if not cell: continue
                        text = str(cell).replace('\n', ' ').strip().upper()
                        if "NOTICE DATE" in text: header_map['warn_date'] = idx
                        elif "JOB SITE NAME" in text: header_map['company'] = idx
                        elif "TOTAL LAYOFF" in text: header_map['impacted'] = idx
                        elif "LAYOFF DATE" in text: header_map['layoff_date'] = idx
                        elif "CITY NAME" in text: header_map['city'] = idx
                        
                    # Process data rows
                    for row in table[header_row_idx+1:]:
                        if not row: continue
                        
                        # Extract data using the map
                        try:
                            warn_date_raw = row[header_map.get('warn_date')] if 'warn_date' in header_map and header_map.get('warn_date') < len(row) else None
                            company_raw = row[header_map.get('company')] if 'company' in header_map and header_map.get('company') < len(row) else None
                            impacted_raw = row[header_map.get('impacted')] if 'impacted' in header_map and header_map.get('impacted') < len(row) else None
                            layoff_date_raw = row[header_map.get('layoff_date')] if 'layoff_date' in header_map and header_map.get('layoff_date') < len(row) else None
                            city_raw = row[header_map.get('city')] if 'city' in header_map and header_map.get('city') < len(row) else None
                            
                            if not company_raw:
                                continue

                            record = WarnRecord(
                                employer=Employee(name=str(company_raw).strip()),
                                location=Address(
                                    municipality=str(city_raw).strip() if city_raw else None,
                                    state="nm"
                                ),
                                warn_date=parse_date(warn_date_raw),
                                layoff_date=parse_date(layoff_date_raw),
                                type=None, # Type is not explicitly in the table
                                impacted=clean_impacted(str(impacted_raw)) if impacted_raw else None,
                                link=url,
                                notes=None
                            )
                            records.append(record.model_dump(mode='json'))
                        except Exception as e:
                            print(f"Error processing row: {row} - {e}")
                            continue

        output_file = "data/nm.json"
        with open(output_file, "w") as f:
            json.dump(records, f, indent=2)
        print(f"Successfully scraped {len(records)} records to {output_file}")
        
    except Exception as e:
        print(f"Error scraping NM: {e}")

if __name__ == "__main__":
    scrape_nm()
