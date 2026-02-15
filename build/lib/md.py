import pandas as pd
import re
import json

def parse(url):
    print('Visiting ' + url)
    df = pd.read_html(url)
    df = df[0]

    df = df.tail(-1) # The first row is headers
    # Drop columns that are not in our list
    df = df.rename(columns={0: "warn_date", 2: "company", 3: "street_address", 4: "municipality", 5: "employees_impacted", 6: "layoff_date", 7: "note"})
    df = df[["warn_date", "company", "street_address", "municipality", "employees_impacted", "layoff_date", "note"]]
    df['state'] = 'md'

    df['warn_date'] = df['warn_date'].str.rstrip('*')
    df['warn_date'] = pd.to_datetime(df['warn_date'], errors='coerce').dt.strftime('%Y-%m-%d')

    df['layoff_date'] = df['layoff_date'].str.rstrip('*')
    df['layoff_date'] = pd.to_datetime(df['layoff_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    return df

def archive_parse_2010(url):
    print('Visiting ' + url)
    df = pd.read_html(url)
    df = df[0]

    df = df.tail(-1) # The first row is headers
    df = df.rename(columns={0: "warn_date", 2: "company", 3: "municipality", 4: "employees_impacted", 5: "layoff_date", 6: "note"})
    df = df[["warn_date", "company", "municipality", "employees_impacted", "layoff_date", "note"]]
    df['state'] = 'md'
    
    df['warn_date'] = pd.to_datetime(df['warn_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['layoff_date'] = pd.to_datetime(df['layoff_date'], errors='coerce').dt.strftime('%Y-%m-%d')

    return df

years = [parse('https://www.dllr.state.md.us/employment/warn.shtml'), archive_parse_2010('https://www.dllr.state.md.us/employment/warn2010.shtml') ]
df = pd.concat(years)

import json
data = df.to_dict(orient='records')
with open("./data/md.json", "w") as f:
    json.dump(data, f, indent=2)
