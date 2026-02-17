import pandas as pd
import json
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

def parse(url):
    print('Visiting ' + url)
    df = pd.read_html(url)
    df = df[0]

    df = df.tail(-1) # The first row is headers
    # Rename columns to match our processing logic
    df = df.rename(columns={0: "warn_date", 2: "company", 3: "street_address", 4: "municipality", 5: "employees_impacted", 6: "layoff_date", 7: "note"})
    df = df[["warn_date", "company", "street_address", "municipality", "employees_impacted", "layoff_date", "note"]]
    df['state'] = 'md'

    records = []
    for _, row in df.iterrows():
        try:
            # Handle potential NaN in company
            company_name = str(row['company']) if pd.notna(row['company']) else None
            if not company_name or company_name == "NO WARNS REPORTED":
                continue

            warn_date = pd.to_datetime(row['warn_date'], errors='coerce')
            layoff_date = pd.to_datetime(row['layoff_date'], errors='coerce')

            record = WarnRecord(
                employer=Employee(name=company_name),
                location=Address(
                    street=str(row['street_address']) if pd.notna(row['street_address']) else None,
                    municipality=str(row['municipality']) if pd.notna(row['municipality']) else None,
                    state="md"
                ),
                warn_date=warn_date.date() if pd.notna(warn_date) else None,
                layoff_date=layoff_date.date() if pd.notna(layoff_date) else None,
                type=derive_warn_type(row['note']),
                impacted=clean_impacted(row['employees_impacted']),
                notes=str(row['note']) if pd.notna(row['note']) else None
            )
            records.append(record.model_dump(mode='json'))
        except Exception as e:
            print(f"Error parsing row: {e}")
    
    return records

urls = ['https://www.dllr.state.md.us/employment/warn.shtml']
# Add years 2025 down to 2010
for year in range(2025, 2009, -1):
    urls.append(f'https://www.dllr.state.md.us/employment/warn{year}.shtml')

all_records = []
for url in urls:
    all_records.extend(parse(url))

with open("./data/md.json", "w") as f:
    json.dump(all_records, f, indent=2)
