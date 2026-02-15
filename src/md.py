import pandas as pd

def parse(url):
    print('Visiting ' + url)
    df = pd.read_html(url)
    df = df[0]

    df = df.tail(-1) # The first row is headers
    df = df.drop([1], axis=1)
    df = df.rename(columns={0: "warn_date", 2: "company", 3: "street_address", 4: "municipality",5: "employees_impacted", 6: "layoff_date", 7: "note"})
    df['state'] = 'md'

    df['warn_date'] = df['warn_date'].str.rstrip('*')
    df['warn_date'] = pd.to_datetime(df['warn_date'])
    df['warn_date'] = df['warn_date'].dt.strftime('%Y-%m-%d')

    df['layoff_date'] = df['layoff_date'].str.rstrip('*')
    df['layoff_date'] = pd.to_datetime(df['layoff_date'])
    df['layoff_date'] = df['layoff_date'].dt.strftime('%Y-%m-%d')
    print(df)
    return df

def archive_parse_2010(url):
    print('Visiting ' + url)
    df = pd.read_html(url)
    df = df[0]

    df = df.tail(-1) # The first row is headers
    df = df.drop([1], axis=1)
    df['state'] = 'md'
    df = df.rename(columns={0: "warn_date", 2: "company", 3: "municipality",4: "employees_impacted", 5: "layoff_date", 6: "note"})


    print(df)
    return df

def archive_parse(url):
    print('Visiting ' + url)


years = [parse('https://www.dllr.state.md.us/employment/warn.shtml'), archive_parse_2010('https://www.dllr.state.md.us/employment/warn2010.shtml') ]