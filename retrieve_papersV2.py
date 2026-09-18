import requests
import time
import pandas as pd
from tqdm import tqdm

EMAIL = "alexis.luzy.1@ens.etsmtl.ca"
BASE_URL = "https://api.openalex.org/works"

# OpenAlex search syntax:
# - Use "double quotes" for exact multi-word phrases: "data availability"
# - Single words do not need quotes: dataset, zenodo, figshare
# - Use uppercase AND, OR, NOT as Boolean operators
# - Use parentheses (...) to group expressions and control Boolean logic
# - The outer 'single quotes' are Python syntax only; they are NOT sent to OpenAlex
# - Adjacent Python strings inside (...) are automatically joined, so:
# ('"data available" OR dataset '
# 'OR "data repository"')
# becomes the single OpenAlex query:
# "data available" OR dataset OR "data repository"

SEARCH = {
    "title": None,

    "abstract": None,

    "fulltext": (
    '("raw data" OR "raw DAS data" OR "raw seismic data" OR "continuous data" '
    'OR "waveform data" OR "strain rate data" OR "strain-rate data") '
    'AND '
    '("publicly available" OR "freely available" OR "openly available" '
    'OR "data repository" OR "data archive" OR "data portal" '
    'OR zenodo OR figshare OR dataverse OR dryad OR pubdas) '
    'NOT '
    '("available on request" OR "available upon request")'
    ),

    "title_and_abstract": (
        '("DAS" OR "Distributed Acoustic Sensing" '
        'OR "Distributed Fiber Sensors" OR "Distributed Sensors" OR "Fiber-optic seismic sensing ")'
    ),

    "year_min": 2020,
    "year_max": 2026,
    "citations_min": 5,
    "citations_max": None,
    "journals": None,
    "open_access": True,
    "has_fulltext": None,

    "output": "C:/Users/AQ96560/Downloads/papers.csv"
}


def build_filters(s):
    filters = ["type:article", "is_retracted:false"]

    fields = {
        "title": "title.search",
        "abstract": "abstract.search",
        "fulltext": "fulltext.search",
        "title_and_abstract": "title_and_abstract.search"
    }

    filters += [f"{field}:{s[key]}" for key, field in fields.items() if s[key]]

    if s["year_min"]:
        filters.append(f"publication_year:>{s['year_min'] - 1}")
    if s["year_max"]:
        filters.append(f"publication_year:<{s['year_max'] + 1}")
    if s["citations_min"] is not None:
        filters.append(f"cited_by_count:>{s['citations_min'] - 1}")
    if s["citations_max"] is not None:
        filters.append(f"cited_by_count:<{s['citations_max'] + 1}")
    if s["journals"]:
        filters.append(f"locations.source.issn:{s['journals']}")
    if s["open_access"] is not None:
        filters.append(f"is_oa:{str(s['open_access']).lower()}")
    if s["has_fulltext"] is not None:
        filters.append(f"has_fulltext:{str(s['has_fulltext']).lower()}")

    return ",".join(filters)


def request(params):
    while True:
        try:
            r = requests.get(BASE_URL, params=params, timeout=30)
            if r.ok:
                return r.json()
            time.sleep(60 if r.status_code == 429 else 15)
        except requests.RequestException:
            time.sleep(30)


def abstract(paper):
    index = paper.get("abstract_inverted_index")
    if not index:
        return ""

    words = [(pos, word) for word, positions in index.items() for pos in positions]
    return " ".join(word for _, word in sorted(words))


params = {
    "filter": build_filters(SEARCH),
    "per-page": 200,
    "cursor": "*",
    "mailto": EMAIL
}

first = request(params)
total = first["meta"]["count"]

print(f"Found {total} papers.")

papers = []
cursor = "*"

with tqdm(total=total) as pbar:
    while cursor:
        params["cursor"] = cursor
        data = request(params)

        for p in data["results"]:
            source = (p.get("primary_location") or {}).get("source") or {}
            oa = p.get("open_access") or {}
            best = p.get("best_oa_location") or {}

            papers.append({
                "Title": p.get("title"),
                "Citations": p.get("cited_by_count"),
                "Journal": source.get("display_name"),
                "DOI": p.get("doi"),
                "URL": best.get("landing_page_url") or p.get("doi"),
                "Authors": [
                    a["author"]["display_name"]
                    for a in p.get("authorships", [])
                    if a.get("author")
                ],
                "Year": p.get("publication_year"),
                "Open Access": oa.get("is_oa"),
                "PDF": best.get("pdf_url"),
                "Abstract": abstract(p)
                })

        pbar.update(len(data["results"]))
        cursor = data["meta"].get("next_cursor")
        time.sleep(1)

pd.DataFrame(papers).to_csv(SEARCH["output"], index=False, encoding="utf-8")
print(f"Saved {len(papers)} papers to {SEARCH['output']}.")
