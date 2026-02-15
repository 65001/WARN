from src.scrape_ajc import scrape_ajc

if __name__ == "__main__":
    url = "https://www.vermontjoblink.com/search/warn_lookups?q%5Bnotice_eq%5D=true&commit=Search"
    scrape_ajc(url, "vt", "data/vt.json")
