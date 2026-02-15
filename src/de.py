from src.scrape_ajc import scrape_ajc

if __name__ == "__main__":
    de_url = "https://joblink.delaware.gov/search/warn_lookups?q%5Bnotice_eq%5D=true&commit=Search"
    scrape_ajc(de_url, "de", "data/de.json")
