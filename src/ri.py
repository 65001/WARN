import requests
import pandas as pd
import os
import json
from datetime import datetime
from src.models import WarnRecord, Employee, Address, WarnType
from src.utils import clean_impacted, parse_address

def parse_date(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    
    date_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def get_col(row, aliases):
    # Normalized search for columns
    # We want to match if any alias is contained in the column name (or vice versa?)
    # Usually exact match on normalized string is best.
    # But here we have "Company Name (* Denotes...)"
    
    row_keys_clean = {k: str(k).replace('\n', ' ').strip().lower() for k in row.keys()}
    
    for alias in aliases:
        alias_clean = alias.lower()
        # Direct match
        for k, k_clean in row_keys_clean.items():
            if alias_clean == k_clean:
                return row[k]
        
        # Check if alias is in k_clean (e.g. 'company' in 'company name (*...)')
        # Only do this for 'company' to avoid false positives on 'date'
        if 'company' in alias_clean:
             for k, k_clean in row_keys_clean.items():
                if 'company' in k_clean:
                    return row[k]

    return None

def scrape_ri():
    url = "https://dlt.ri.gov/media/15796/download?language=en"
    print(f"Fetching RI data from {url}...")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    local_file = "data/ri_warn.xlsx"
    
    if not os.path.exists('data'):
        os.makedirs('data')

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to download RI file. Status: {response.status_code}")
            return

        with open(local_file, "wb") as f:
            f.write(response.content)

        all_records = []
        with pd.ExcelFile(local_file) as xls:
            # Iterate through relevant sheets
            sheets_to_process = [s for s in xls.sheet_names if s in ['2026', '2025', '2024', 'Previous Years']]
            
            if not sheets_to_process:
                 sheets_to_process = xls.sheet_names
    
            for sheet_name in sheets_to_process:
                print(f"Processing sheet: {sheet_name}")
                
                # User specified header is at index 3 (Row 4)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=3)
            
            # Debug: Print columns to verify
            # print(f"Columns in {sheet_name}: {df.columns.tolist()}")

                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    
                    company = get_col(row_dict, ['Company Name', 'Company'])
                    location = get_col(row_dict, ['Location', 'Location of Layoffs'])
                    warn_date_val = get_col(row_dict, ['WARN Date'])
                    effective_date_val = get_col(row_dict, ['Effective Date'])
                    affected_val = get_col(row_dict, ['Number Affected', 'Affected'])
                    closing_val = get_col(row_dict, ['Closing Yes/No'])
                    union_yes_no = get_col(row_dict, ['Union Yes/No'])
                    union_address_val = get_col(row_dict, ['Union Address'])
                    
                    if not company or pd.isna(company):
                        continue
                        
                    # Determine type
                    warn_type = WarnType.TEMPORARY_LAYOFF
                    if closing_val and str(closing_val).lower().strip() == 'yes':
                        warn_type = WarnType.CLOSURE
                    elif closing_val and str(closing_val).lower().strip() == 'no':
                        warn_type = WarnType.PERMANENT_LAYOFF 

                    # Handle Union
                    union_obj = None
                    if union_yes_no and str(union_yes_no).lower().strip() == 'yes':
                        addr = None
                        union_name = "Union" 
                        
                        if union_address_val and not pd.isna(union_address_val):
                            # Use the parser from utils
                            # "Local Union 1033, 410 S Main Street 3rd floor, Providence, RI 02906"
                            parsed = parse_address(str(union_address_val), state_fips='44')
                            
                            addr = Address(
                                street=parsed['street'],
                                municipality=parsed['municipality'],
                                state="RI",
                                zip=parsed['zip']
                            )
                            
                            # Can we extract union name?
                            # Often the first part before the first comma if address parsing fails or leaves valid street
                            # But parse_address logic focuses on address parts.
                            # It doesn't extract name.
                            # However, for RI, the field is "Union Address" but seemingly contains "Union Name, Address"
                            # parse_address might actually treat "Local Union 1033" as part of street if not careful, 
                            # OR if it finds "Providence, RI", it puts everything else in street?
                            # Let's simple split by comma to try to get a name if possible, or just leave name generic.
                            
                            parts = str(union_address_val).split(',', 1)
                            if len(parts) > 1:
                                possible_name = parts[0].strip()
                                # If "street" starts with this, maybe remove it?
                                # But for now, let's keep it simple as requested: just parse address.
                                # We will assume the full string is the address mostly.
                                pass

                        union_obj = Employee(name=union_name, address=addr)

                    record = WarnRecord(
                        employer=Employee(name=str(company).strip()),
                        location=Address(
                            municipality=str(location).strip() if location and not pd.isna(location) else None,
                            state="RI"
                        ),
                        warn_date=parse_date(warn_date_val),
                        layoff_date=parse_date(effective_date_val),
                        type=warn_type,
                        impacted=clean_impacted(affected_val),
                        union=union_obj,
                        link=url,
                        notes=f"Sheet: {sheet_name}"
                    )
                    all_records.append(record.model_dump(mode='json'))

        output_file = "data/ri.json"
        with open(output_file, "w") as f:
            json.dump(all_records, f, indent=2)
            
        print(f"Successfully scraped {len(all_records)} records to {output_file}")
        
    except Exception as e:
        print(f"Error processing RI data: {e}")
    finally:
        if os.path.exists(local_file):
            try:
                os.remove(local_file)
            except:
                pass
        
        # User mentioned .xlsxc, explicitly try to remove it too just in case
        xlsxc_file = local_file + "c"
        if os.path.exists(xlsxc_file):
            try:
                os.remove(xlsxc_file)
            except:
                pass

if __name__ == "__main__":
    scrape_ri()
