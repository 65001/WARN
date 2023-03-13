import pandas as pd

def add_prefix(link):
    if link is not None:
        return "https://jobs.alaska.gov" + link
    else:
        return link

df = pd.read_html('https://jobs.alaska.gov/rr/WARN_notices.htm', extract_links='body')
df = df[0]
df = df.rename(columns={0: "company", 1: "municipality", 2: "warn_date", 3: "layoff_date", 4: "employees_impacted", 5: "note"})

df['company'], df['link'] = zip(*df.company)
df['municipality'], _ = zip(*df.municipality)
df['warn_date'], _ = zip(*df.warn_date)
df['layoff_date'], _ = zip(*df.layoff_date)
df['employees_impacted'], _ = zip(*df.employees_impacted)
df['note'], _ = zip(*df.note)

# Drop the 1st & 2nd row because it's the headers, and a blank line
df = df.tail(-2)
# Drop the last row because it's a blank line
df = df.head(-1)

df['state'] = 'ak'
df['warn_date'] = df['warn_date'].str.rstrip('*')
df['warn_date'] = pd.to_datetime(df['warn_date'])
df['warn_date'] = df['warn_date'].dt.strftime('%Y-%m-%d')

df['link'] = df['link'].apply(add_prefix)

df.to_json("./WARN/data/ak.json", orient='records', indent=2)