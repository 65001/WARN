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

def _parse_pdf(pdf_file, url):
    """Extract WARN records from an NM PDF file object."""
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
                    row_str = " ".join([str(cell).replace('\n', ' ') for cell in row if cell]).upper()
                    if "NOTICE DATE" in row_str and "JOB SITE NAME" in row_str:
                        header_row_idx = i
                        break

                if header_row_idx == -1:
                    continue

                # Identify column indices by header text
                header_map = {}
                raw_header_row = table[header_row_idx]
                for idx, cell in enumerate(raw_header_row):
                    if not cell:
                        continue
                    text = str(cell).replace('\n', ' ').strip().upper()
                    if "NOTICE DATE" in text:   header_map['warn_date'] = idx
                    elif "JOB SITE NAME" in text: header_map['company'] = idx
                    elif "TOTAL LAYOFF" in text:  header_map['impacted'] = idx
                    elif "LAYOFF DATE" in text:   header_map['layoff_date'] = idx
                    elif "CITY NAME" in text:     header_map['city'] = idx

                # Process data rows
                for row in table[header_row_idx + 1:]:
                    if not row:
                        continue
                    try:
                        def _get(key):
                            idx = header_map.get(key)
                            return row[idx] if idx is not None and idx < len(row) else None

                        company_raw = _get('company')
                        if not company_raw:
                            continue

                        record = WarnRecord(
                            employer=Employee(name=str(company_raw).strip()),
                            location=Address(
                                municipality=str(_get('city')).strip() if _get('city') else None,
                                state="nm"
                            ),
                            warn_date=parse_date(_get('warn_date')),
                            layoff_date=parse_date(_get('layoff_date')),
                            type=None,
                            impacted=clean_impacted(str(_get('impacted'))) if _get('impacted') else None,
                            link=url,
                            notes=None
                        )
                        records.append(record.model_dump(mode='json'))
                    except Exception as e:
                        print(f"Error processing row: {row} - {e}")
                        continue
    return records


def scrape_nm():
    base_url = "https://www.dws.state.nm.us/Portals/0/DM/Business/{year}_WARN.pdf"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    current_year = datetime.now().year
    # NM posts WARN PDFs starting around 2016; adjust START_YEAR if needed
    START_YEAR = 2016

    all_records = []
    for year in range(START_YEAR, current_year + 1):
        url = base_url.format(year=year)
        print(f"Fetching {url}")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 404:
                print(f"  No PDF found for {year} (404), skipping.")
                continue
            response.raise_for_status()

            pdf_file = io.BytesIO(response.content)
            year_records = _parse_pdf(pdf_file, url)
            print(f"  Found {len(year_records)} records for {year}.")
            all_records.extend(year_records)
        except Exception as e:
            print(f"  Error fetching/parsing {year}: {e}")
            continue

    output_file = "data/nm.json"
    with open(output_file, "w") as f:
        json.dump(all_records, f, indent=2)
    print(f"Successfully scraped {len(all_records)} total records to {output_file}")


if __name__ == "__main__":
    scrape_nm()
