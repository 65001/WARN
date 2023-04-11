import pandas as pd

def add_prefix(link):
    if link is not None:
        return "https://www.ctdol.state.ct.us/progsupt/bussrvce/warnreports/" + link
    else:
        return link
    
def parse_warn_date(date):
    pin = 'Rec\'d'
    if 'Rec’d' in date:
        pin = 'Rec’d'
    if 'Recd' in date:
        pin ='Recd'
    if 'Received' in date:
        pin = 'Received'
    if 'Revised' in date:
        pin = 'Revised'
    if 'Not Dated Rec\'d' in date:
        pin = 'Not Dated Rec\'d'
    start = date.index(pin)
    length = len(pin)
    return date[start + length:]

def parse(url):
    df = pd.read_html(url, extract_links='body')
    df = df[9]
    df = df.tail(-1) # The first row is headers
    df = df.rename(columns={0: "warn_date", 1: "company", 2: "municipality",3: "employees_impacted", 4: "layoff_date", 8: "union_address"})
    df = df.drop([5,6,7], axis=1)
    df['company'], df['link'] = zip(*df.company)
    df['municipality'], _ = zip(*df.municipality)
    df['warn_date'], _ = zip(*df.warn_date)
    df['layoff_date'], _ = zip(*df.layoff_date)
    df['employees_impacted'], _ = zip(*df.employees_impacted)
    df['union_address'], _ = zip(*df.union_address)
    df['link'] = df['link'].apply(add_prefix)

    df['warn_date'] = df['warn_date'].apply(parse_warn_date)
    df['warn_date'] = pd.to_datetime(df['warn_date'])
    df['warn_date'] = df['warn_date'].dt.strftime('%Y-%m-%d')

    df['state'] = 'ct'
    return df

years = []
for year in range(2015, 2024):
    url = 'https://www.ctdol.state.ct.us/progsupt/bussrvce/warnreports/warn' + str(year) + '.htm'
    years.append(parse(url))
df = pd.concat(years)   
df.to_json("./WARN/data/ct.json", orient='records', indent=2)
    