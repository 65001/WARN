import pandas as pd

al = pd.read_html('https://www.madeinalabama.com/warn-list/')
al = al[0]
al = al.rename(columns={"Closing or Layoff": "type", "Initial Report Date": "warn_date", "Planned Starting Date": "layoff_date", "Company": "company", "City": "municipality", "Planned # Affected Employees": "employees_impacted"})
al['type'].mask(al['type'] == 'Layoff *', 'layoff', inplace=True)
al['type'].mask(al['type'] == 'Closing *', 'closure', inplace=True)
al['type'].mask(al['type'] == 'Layoff', 'layoff', inplace=True)
al['type'].mask(al['type'] == 'Closure', 'closure', inplace=True)
al['state'] = 'al'
al.to_json("./WARN/data/al.json", orient='records', indent=2)

# Manually remove the bad 1998 data.