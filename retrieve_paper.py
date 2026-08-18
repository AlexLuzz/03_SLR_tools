import requests
import time
import pandas as pd
from tqdm import tqdm

# --- Configuration ---
EMAIL = "alexis.luzy.1@ens.etsmtl.ca"
BASE_URL = "https://api.openalex.org/works"

search_string = (
    '("near surface geophysics" OR "hydrogeophysics" OR "electrical resistivity tomography") '
    'AND ("monitoring" OR "time-lapse") '
    'AND ("inversion" OR "processing" OR "bottleneck" OR "trend")'
)

("near surface geophysics" OR "hydrogeophysics" OR "electrical resistivity tomography" OR "ground penetrating radar" OR "distributed temperature sensing") 
AND ("time-lapse" OR "monitoring" OR "4D" OR "spatio-temporal") 
AND ("inversion" OR "assimilation" OR "machine learning" OR "deep learning" OR "neural network")

# OpenAlex supports pipe '|' as an OR operator for ISSNs
journal_issns = "0016-8033|0043-1397|0926-9851|1569-4445|0169-3298"
# "filter": f"locations.source.issn:{journal_issns},publication_year:>1995,type:article,is_retracted:false,cited_by_count:>5"

params = {
    "search": search_string,
    # By default, search for the search_string in the Title, Abstract and Full Text of the paper. 
    "filter": "publication_year:>1995,type:article,is_retracted:false,cited_by_count:>5",
    # To specify to only search in title and abstract, you can use the following filter instead:
    #"filter": f"title_and_abstract.search:{search_string},publication_year:>1995,type:article,is_retracted:false,cited_by_count:>5",
    "per-page": 200,
    "cursor": "*",
    "mailto": EMAIL
}

# --- Bulletproof Request Function ---
def make_robust_request(url, parameters):
    """Makes an API call that refuses to crash, waiting out 429 Rate Limits."""
    while True:
        try:
            response = requests.get(url, params=parameters, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("\n[!] Rate limit hit (429 Penalty Box).")
                print("[!] Sleeping for 60 seconds to clear the block before retrying...")
                time.sleep(60)
            else:
                print(f"\n[!] Unexpected Server Error {response.status_code}. Retrying in 15s...")
                time.sleep(15)
                
        except requests.exceptions.RequestException as e:
            print(f"\n[!] Network drop/timeout: {e}. Retrying in 30s...")
            time.sleep(30)

# --- Execution ---
print("Contacting OpenAlex to calculate total results...")

# 1. Get initial data and total count
first_page = make_robust_request(BASE_URL, params)
total_results = first_page.get("meta", {}).get("count", 0)
print(f"Found {total_results} papers. Beginning extraction...\n")

extracted_data = []

# Setup progress bar
pbar = tqdm(total=total_results)
current_cursor = "*"

try:
    while current_cursor:
        # Update the cursor in the parameters for the next page
        params["cursor"] = current_cursor
        data = make_robust_request(BASE_URL, params)
        
        results = data.get("results", [])
        
        # If the page is empty, we've reached the end
        if not results:
            break
            
        for paper in results:
            # Safely extract authors
            authors = [author.get('author', {}).get('display_name', '') 
                       for author in paper.get('authorships', []) if author.get('author')]
            author_string = "; ".join(authors)
            
            # Safely extract journal name
            journal = paper.get('primary_location', {})
            journal_name = journal.get('source', {}).get('display_name', 'Unknown') if journal and journal.get('source') else "Unknown"
            
            # Reconstruct the abstract from the inverted index
            abstract_inverted = paper.get('abstract_inverted_index')
            abstract = "No abstract available."
            if abstract_inverted:
                word_index = []
                for word, positions in abstract_inverted.items():
                    for pos in positions:
                        word_index.append((pos, word))
                word_index.sort()
                abstract = " ".join([word for pos, word in word_index])

            extracted_data.append({
                "Title": paper.get('title'),
                "Authors": author_string,
                "Year": paper.get('publication_year'),
                "Journal": journal_name,
                "DOI": paper.get('doi'),
                "Citations": paper.get('cited_by_count'),
                "Abstract": abstract
            })
            
            pbar.update(1)
            
        # Get the next cursor for the deep pagination
        current_cursor = data.get("meta", {}).get("next_cursor")
        
        # Highly polite delay between pages (2 seconds) to avoid future 429s
        time.sleep(2)

except KeyboardInterrupt:
    print("\n[!] Manual interruption detected. Stopping extraction...")

finally:
    pbar.close()
    print("\nSaving data to CSV...")
    df = pd.DataFrame(extracted_data)
    output_filename = "near_surface_monitoring_review.csv"
    df.to_csv(output_filename, index=False, encoding='utf-8')
    print(f"Successfully saved {len(df)} papers to {output_filename}.")