import os
import re
import requests
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

Settings.llm = Ollama(model="mistral", request_timeout=600.0)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

# --- HELPER FUNCTIONS ---

def get_citation_count(doi):
    """Fetches citation count from OpenAlex API using the provided DOI."""
    if not doi or doi.strip() == "":
        return 0
        
    doi = doi.strip()
    # construction URL OpenAlex
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("cited_by_count", 0)
        else:
            return 0 # Changed to 0 instead of None for cleaner Obsidian formatting
    except Exception as e:
        print(f"⚠️ OpenAlex API Error: {e}")
        return 0

def read_template(template_path):
    """Reads the raw Markdown template from Obsidian."""
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

def generate_master_list_from_obsidian(concepts_folder):
    """Scans the Obsidian concepts folder to build a live vocabulary list."""
    if not os.path.exists(concepts_folder):
        return "No pre-existing concepts found."
    
    master_list_items = []
    alias_regex = re.compile(r'aliases:/s*/[(.*?)/]|aliases:/s*/n/s*-/s*(.*)')

    for filename in os.listdir(concepts_folder):
        if filename.endswith(".md"):
            concept_title = filename.replace(".md", "").replace("Concept - ", "")
            file_path = os.path.join(concepts_folder, filename)
            aliases = []
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read(500) 
                    match = alias_regex.search(content)
                    if match:
                        raw_aliases = match.group(1) or match.group(2)
                        if raw_aliases:
                            aliases = [a.strip().strip('"').strip("'") for a in raw_aliases.split(",")]
            except Exception:
                pass 
            
            if aliases and aliases != ['']:
                master_list_items.append(f"- {concept_title} (Aliases: {(', '.join(aliases))})")
            else:
                master_list_items.append(f"- {concept_title}")

    return "/n".join(master_list_items)


# --- MAIN PIPELINE ---

def analyze_paper(pdf_path, concepts_folder, template_path):
    print("🔄 Syncing live concept list and template from Obsidian...")
    live_concept_list = generate_master_list_from_obsidian(concepts_folder)
    raw_template = read_template(template_path)
    
    print(f"📖 Step 1: Parsing and embedding {os.path.basename(pdf_path)}...")
    reader = SimpleDirectoryReader(input_files=[pdf_path])
    documents = reader.load_data()
    
    db = chromadb.EphemeralClient()
    chroma_collection = db.get_or_create_collection("temporary_paper_analysis")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    query_engine = index.as_query_engine(similarity_top_k=5)
    
    print("🧠 Step 2: Extracting data and filling template...")
    
    obsidian_prompt = f"""
    You are an expert academic research assistant. Analyze the provided text segments from the paper.

    Here is the CURRENT MASTER CONCEPT LIST:
    {live_concept_list}

    Your job is to extract the paper's metadata and generate a clean summary by filling out the following template exactly as it is formatted.
    
    RULES:
    1. Extract Title, Authors (as a bracketed list), Year, DOI (just the number, no url), and Journal to fill the top properties. Leave LN_date, citations, grade, and link exactly as they are.
    2. Fill the "Data/Approach" tag with either 'data/synthetic', 'data/field-scale', 'approach/coupled', or 'approach/sequential'.
    3. Ground your methodology, results, and discussion summaries strictly in the text.
    4. For Concepts, if it matches an item or alias in the Master Concept List, use the exact terminology inside brackets.

    TEMPLATE TO FILL:
    {raw_template}
    """
    
    response = query_engine.query(obsidian_prompt)
    draft_note = str(response)

    print("🌐 Step 3: Fetching live citation data from OpenAlex...")
    # Regex to find the DOI Mistral extracted (looks for "doi: 10.xxxx/xxxx")
    doi_match = re.search(r'doi:/s*(10/./d{4,9}/[-._;()/:A-Z0-9]+)', draft_note, re.IGNORECASE)
    
    if doi_match:
        extracted_doi = doi_match.group(1)
        print(f"   Found DOI: {extracted_doi}")
        citation_count = get_citation_count(extracted_doi)
        print(f"   Citations: {citation_count}")
    else:
        print("   No valid DOI found in extraction.")
        citation_count = 0

    # Replace the placeholder in the template with the real data
    final_note = draft_note.replace("{CITATION_PLACEHOLDER}", str(citation_count))

    print("/n🚀 ANALYSIS COMPLETE!/n")
    print(final_note)


if __name__ == "__main__":
    home = "alexi"
    ETS = "AQ96560"
    user = home
    VAULT_PATH = f"C:/Users/{user}/OneDrive - ETS/000-Doctorat/77_Bible_PhD/Bible PhD/"
    CONCEPTS_DIR = VAULT_PATH + "02_Concepts"
    TEMPLATE_FILE = VAULT_PATH + "00_Templates/Litterature note.md"
    PAPER_Path = f"C:/Users/{user}/OneDrive - ETS/00-Maitrise_Recherche/01-Geophysique/01-Papiers/"
    TARGET_PAPER = PAPER_Path + "Binley et al. - 2015 - The emergence of hydrogeophysics.pdf" 
    
    analyze_paper(TARGET_PAPER, VAULT_PATH, TEMPLATE_FILE)