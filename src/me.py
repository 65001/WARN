from src.scrape_ajc import scrape_ajc

if __name__ == "__main__":
    url = "https://joblink.maine.gov/search/warn_lookups?q%5Bnotice_eq%5D=true&commit=Search"
    scrape_ajc(url, "me", "data/me.json")
