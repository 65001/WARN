import pandas as pd
import json
from src.models import WarnRecord, Employee, Address, WarnType
from src.utils import clean_impacted

def scrape_al():
    df = pd.read_html('https://www.madeinalabama.com/warn-list/')
    df = df[0]
    df = df.rename(columns={"Closing or Layoff": "type_str", "Initial Report Date": "warn_date", "Planned Starting Date": "layoff_date", "Company": "company", "City": "municipality", "Planned # of Affected Employees": "employees_impacted"})
    
    df = df.head(-8) # This removes the 1998 data

    records = []
    for _, row in df.iterrows():
        try:
            # Map AL specific types
            warn_type = None
            type_low = str(row['type_str']).lower()
            if 'closing' in type_low or 'closure' in type_low:
                warn_type = WarnType.CLOSURE
            elif 'layoff' in type_low:
                warn_type = WarnType.PERMANENT_LAYOFF

            warn_date = pd.to_datetime(row['warn_date'], errors='coerce')
            layoff_date = pd.to_datetime(row['layoff_date'], errors='coerce')
            if layoff_date == pd.to_datetime('01/01/0001'):
                layoff_date = pd.NaT

            record = WarnRecord(
                employer=Employee(name=row['company'] if pd.notna(row['company']) else None),
                location=Address(
                    municipality=row['municipality'] if pd.notna(row['municipality']) else None,
                    state="al"
                ),
                warn_date=warn_date.date() if pd.notna(warn_date) else None,
                layoff_date=layoff_date.date() if pd.notna(layoff_date) else None,
                type=warn_type,
                impacted=clean_impacted(row['employees_impacted'])
            )
            records.append(record.model_dump(mode='json'))
        except Exception as e:
            print(f"Error parsing row: {e}")

    with open("./data/al.json", "w") as f:
        json.dump(records, f, indent=2)

if __name__ == "__main__":
    scrape_al()