import pandas as pd
import re
import json

def add_prefix(link):
    if isinstance(link, str):
        return "https://jobs.alaska.gov" + link
    else:
        return link

def clean_date(date_str):
    if not isinstance(date_str, str):
        return None
    
    # Try to find common date patterns like MM/DD/YY or MM/DD/YYYY
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', date_str)
    if match:
        d = match.group(1)
        try:
            return pd.to_datetime(d).strftime('%Y-%m-%d')
        except:
            pass
            
    # Fallback to fuzzy parsing
    try:
        return pd.to_datetime(date_str, fuzzy=True, errors='coerce').strftime('%Y-%m-%d')
    except:
        return date_str

df = pd.read_html('https://jobs.alaska.gov/rr/WARN_notices.htm', extract_links='body')
df = df[0]
df = df.rename(columns={0: "company", 1: "municipality", 2: "warn_date", 3: "layoff_date", 4: "employees_impacted", 5: "note"})

df['company'], df['link'] = zip(*df.company)
df['municipality'], _ = zip(*df.municipality)
df['warn_date'], _ = zip(*df.warn_date)
df['layoff_date'], _ = zip(*df.layoff_date)
df['employees_impacted'], _ = zip(*df.employees_impacted)
df['note'], _ = zip(*df.note)

df['layoff_date'] = df['layoff_date'].apply(clean_date)

# Drop the 1st & 2nd row because it's the headers, and a blank line
df = df.tail(-2)
# Drop the last row because it's a blank line
df = df.head(-1)

df['state'] = 'ak'
df['warn_date'] = df['warn_date'].str.rstrip('*')
df['warn_date'] = pd.to_datetime(df['warn_date']).dt.strftime('%Y-%m-%d')

df['link'] = df['link'].apply(add_prefix)

data = df.to_dict(orient='records')
with open("./data/ak.json", "w") as f:
    json.dump(data, f, indent=2)