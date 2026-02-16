import requests
import pdfplumber
import io

def inspect_nm_pdf():
    # URL found from previous step
    pdf_url = "https://www.dws.state.nm.us/Portals/0/DM/Business/2024_WARN.pdf" 
    print(f"Downloading {pdf_url}...")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(pdf_url, headers=headers)
        response.raise_for_status()
        
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            print(f"Pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages):
                print(f"--- Page {i+1} ---")
                text = page.extract_text()
                print("Text preview:")
                print(text[:500])
                
                print("\nTable preview:")
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        print(table[:3]) # Print first 3 rows
                else:
                    print("No tables found.")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_nm_pdf()
