import requests

def search_openalex_articles(keyword, max_results=10):
    """
    Query the free OpenAlex API for scientific literature matching a keyword phrase.
    """
    print(f"Searching for: '{keyword}'...")
    
    # Format the query for the OpenAlex API endpoint
    encoded_keyword = keyword.replace(" ", "+")
    url = f"https://api.openalex.org/works?search={encoded_keyword}&per_page={max_results}"
    
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return []
    
    data = response.json()
    results = []
    
    for work in data.get('results', []):
        results.append({
            "title": work.get("title"),
            "year": work.get("publication_year"),
            "citations": work.get("cited_by_count", 0),
            "doi": work.get("doi"),
            "id": work.get("id") # OpenAlex unique identifier
        })
        
    return results

# --- EXECUTION ---
if __name__ == "__main__":
    # Test query mimicking your recent discussion
    query_phrase = "physics informed neural network"
    articles = search_openalex_articles(query_phrase, max_results=5)
    
    print("\n--- Top Results Found ---")
    for idx, art in enumerate(articles, 1):
        print(f"{idx}. [{art['year']}] {art['title']}")
        print(f"   Citations: {art['citations']} | DOI: {art['doi']}\n")