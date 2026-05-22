import pandas as pd
import requests
import matplotlib.pyplot as plt
import time

# --------------------------------------------------
# Fonction pour récupérer le nombre de citations
# --------------------------------------------------
def get_citation_count(doi):
    """
    Retourne le nombre de citations pour un DOI
    via l'API OpenAlex.
    """
    
    if pd.isna(doi):
        return None

    doi = doi.strip()

    # construction URL OpenAlex
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return data.get("cited_by_count", 0)

        else:
            return None

    except Exception as e:
        print(f"Erreur DOI {doi}: {e}")
        return None


# --------------------------------------------------
# Charger le CSV Zotero
# --------------------------------------------------
# Remplace par ton fichier
csv_file = "C:/Users/alexi/OneDrive - ETS/000-Doctorat/77_Bible_PhD/Litterature review Method.csv"

df = pd.read_csv(csv_file)

# Vérifie le nom exact de la colonne DOI
# Souvent : "DOI"
print(df.columns)

# --------------------------------------------------
# Récupération des citations
# --------------------------------------------------
citation_counts = []

for doi in df["DOI"]:
    count = get_citation_count(doi)
    citation_counts.append(count)

    print(f"{doi} -> {count}")

    # petite pause pour éviter de spammer l'API
    time.sleep(0.5)

df["citations"] = citation_counts

df.to_csv("zotero_with_citations.csv", index=False, sep=";")