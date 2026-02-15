import pandas as pd
import json
from src.models import WarnRecord, Employee, Address
from src.utils import clean_impacted, derive_warn_type

def add_prefix(link):
    if isinstance(link, str):
        return "https://jobs.alaska.gov" + link
    return link

def scrape_ak():
    df = pd.read_html('https://jobs.alaska.gov/rr/WARN_notices.htm', extract_links='body')
    df = df[0]
    df = df.rename(columns={0: "company", 1: "municipality", 2: "warn_date", 3: "layoff_date", 4: "employees_impacted", 5: "note"})

    # Extract links from the 'company' column which was read with extract_links='body'
    df['company_name'], df['link'] = zip(*df.company)
    df['municipality_name'], _ = zip(*df.municipality)
    df['warn_date_str'], _ = zip(*df.warn_date)
    df['layoff_date_str'], _ = zip(*df.layoff_date)
    df['impacted_str'], _ = zip(*df.employees_impacted)
    df['note_str'], _ = zip(*df.note)

    # Drop the 1st & 2nd row because it's the headers, and a blank line
    df = df.tail(-2)
    # Drop the last row because it's a blank line
    df = df.head(-1)

    records = []
    for _, row in df.iterrows():
        try:
            warn_date = pd.to_datetime(row['warn_date_str'], errors='coerce')
            layoff_date = pd.to_datetime(row['layoff_date_str'], errors='coerce')

            record = WarnRecord(
                employer=Employee(name=row['company_name']),
                location=Address(
                    municipality=row['municipality_name'],
                    state="ak"
                ),
                warn_date=warn_date.date() if pd.notna(warn_date) else None,
                layoff_date=layoff_date.date() if pd.notna(layoff_date) else None,
                type=derive_warn_type(row['note_str']),
                impacted=clean_impacted(row['impacted_str']),
                notes=row['note_str'] if row['note_str'] and pd.notna(row['note_str']) else None,
                link=add_prefix(row['link']) if pd.notna(row['link']) else None
            )
            records.append(record.model_dump(mode='json'))
        except Exception as e:
            print(f"Error parsing row: {e}")

    with open("./data/ak.json", "w") as f:
        json.dump(records, f, indent=2)

if __name__ == "__main__":
    scrape_ak()