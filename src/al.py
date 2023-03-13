import pandas as pd

df = pd.read_html('https://www.madeinalabama.com/warn-list/')
df = df[0]
df = df.rename(columns={"Closing or Layoff": "type", "Initial Report Date": "warn_date", "Planned Starting Date": "layoff_date", "Company": "company", "City": "municipality", "Planned # Affected Employees": "employees_impacted"})
df['type'].mask(df['type'] == 'Layoff *', 'layoff', inplace=True)
df['type'].mask(df['type'] == 'Closing *', 'closure', inplace=True)
df['type'].mask(df['type'] == 'Layoff', 'layoff', inplace=True)
df['type'].mask(df['type'] == 'Closure', 'closure', inplace=True)

df['layoff_date'].mask(df['layoff_date'] == '01/01/0001', float('NaN'), inplace=True)

df['state'] = 'al'
df['warn_date'] = pd.to_datetime(df['warn_date'])
df['warn_date'] = df['warn_date'].dt.strftime('%Y-%m-%d')
df['layoff_date'] = pd.to_datetime(df['layoff_date'])
df['layoff_date'] = df['layoff_date'].dt.strftime('%Y-%m-%d')

df = df.head(-8) # This removes the 1998 data
df.to_json("./WARN/data/al.json", orient='records', indent=2)