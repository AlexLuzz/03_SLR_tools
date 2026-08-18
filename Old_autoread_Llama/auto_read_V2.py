import os
import re
import requests
import fitz  # PyMuPDF
from tqdm import tqdm
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 🛠️ SYSTEM SETTINGS
Settings.llm = Ollama(model="mistral", request_timeout=3600.0)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

# --- HELPER FUNCTIONS ---

def get_citation_count(doi):
    if not doi or doi.strip() == "": return 0
    url = f"https://api.openalex.org/works/https://doi.org/{doi.strip()}"
    try:
        response = requests.get(url, timeout=10)
        return response.json().get("cited_by_count", 0) if response.status_code == 200 else 0
    except Exception: return 0

def read_template(template_path):
    with open(template_path, "r", encoding="utf-8") as f: return f.read()

def generate_master_list_from_obsidian(concepts_folder):
    if not os.path.exists(concepts_folder): return "No pre-existing concepts found."
    master_list_items = []
    alias_regex = re.compile(r'aliases:\s*\[(.*?)\]|aliases:\s*\n\s*-\s*(.*)')
    for filename in os.listdir(concepts_folder):
        if filename.endswith(".md"):
            concept_title = filename.replace(".md", "").replace("Concept - ", "")
            try:
                with open(os.path.join(concepts_folder, filename), "r", encoding="utf-8") as f:
                    match = alias_regex.search(f.read(500))
                    raw = match.group(1) or match.group(2) if match else None
                    aliases = [a.strip().strip('"').strip("'") for a in raw.split(",")] if raw else []
            except Exception: aliases = []
            master_list_items.append(f"- {concept_title} (Aliases: {', '.join(aliases)})" if aliases else f"- {concept_title}")
    return "\n".join(master_list_items)


# --- MAIN PIPELINE ---

def analyze_paper_map_reduce(pdf_path, concepts_folder, template_path):
    print("🔄 Syncing live concept list and template from Obsidian...")
    live_concept_list = generate_master_list_from_obsidian(concepts_folder)
    raw_template = read_template(template_path)
    
    print(f"📖 Step 1: Parsing PDF text using PyMuPDF...")
    # 🚀 THE NEW ENGINE: Directly reading the decoded text layer
    doc = fitz.open(pdf_path)
    extracted_pages = []
    for page in doc:
        extracted_pages.append(page.get_text("text"))
    
    raw_text = str("\n\n".join(extracted_pages))
    
    # 🔍 DIAGNOSTIC PREVIEW: This should now look like beautiful, readable English
    print(f"\n   🔍 RAW EXTRACTION PREVIEW (First 400 Chars):")
    print(f"   {'-'*50}\n   {raw_text[:400].strip()}\n   {'-'*50}\n")
    
    total_raw_chars = len(raw_text)
    
    print("✂️ Scanning for Bibliography to optimize text load...")
    halfway_idx = total_raw_chars // 2
    matches = list(re.finditer(r'(References|Bibliography|Literature\s+Cited)', raw_text, re.IGNORECASE))
    cutoff_index = total_raw_chars
    
    for match in matches:
        if match.start() >= halfway_idx:
            following_sample = raw_text[match.start():match.start() + 3000]
            years_count = len(re.findall(r'\b(19\d{2}|20\d{2})\b', following_sample))
            
            if years_count >= 8:  
                cutoff_index = match.start()
                print(f"   🛑 Found true Bibliography section! Truncating text stream.")
                break
                
    clean_text = raw_text[:cutoff_index]
    
    print("🌳 Step 2: Dividing text into standard processing blocks...")
    words = clean_text.split()
    
    # 📊 CRITICAL DIAGNOSTIC PRINT: Words should finally be in the ~15,000 range
    print(f"   📊 Clean Diagnostic -> Total Characters: {len(clean_text)} | Total Words parsed: {len(words)}")
    
    words_per_chunk = 1500  
    overlap = 150
    chunks = []
    
    for i in range(0, len(words), words_per_chunk - overlap):
        chunk_words = words[i:i + words_per_chunk]
        chunks.append(" ".join(chunk_words))
        if i + words_per_chunk >= len(words):
            break
            
    total_chunks = len(chunks)
    print(f"🧩 Split into {total_chunks} blocks. Starting Map Phase...")
    
    # 🗺️ PHASE 1: MAP
    extracted_data_pool = []
    for idx, chunk_text in enumerate(tqdm(chunks, desc="Mapping Chunks", unit="chunk")):
        map_prompt = f"""
        Analyze this isolated text chunk from a hydrogeophysics paper. Extract any explicit mentions of:
        - Metadata (Title, Authors, Year, DOI, Journal)
        - Core methodology keypoints
        - Main results or governing equations
        - Key discussion or conclusion points
        - Specific concepts that match or relate to this Master List:\n{live_concept_list}
        
        Keep your extractions concise and bulleted. If a section has no data, skip it.
        
        TEXT CHUNK:\n{chunk_text}
        """
        try:
            response = Settings.llm.complete(map_prompt)
            extracted_data_pool.append(response.text)
        except Exception as e:
            print(f"\n⚠️ Error on chunk {idx+1}: {e}. Skipping chunk.")

    print("\n📦 Compiling raw extractions... Starting Reduce Phase (Formatting Template)...")
    
    # 📉 PHASE 2: REDUCE
    all_extracted_text = "\n\n=== NEXT CHUNK DATA ===\n\n".join(extracted_data_pool)
    
    reduce_prompt = f"""
    You are an expert academic research assistant. Synthesize these raw data points extracted from a full paper and organize them into the provided Markdown template.
    
    CRITICAL RULES:
    1. ZERO HALLUCINATION: Fill Title, Authors, Year, DOI, and Journal based strictly on the extracted data.
    2. THE DOI FORMAT: Extract ONLY the text string of the DOI (e.g., 10.1002/2015WR017016). No URLs.
    3. PRESERVE PLACEHOLDERS: Leave 'LN_date: {{{{date}}}}' and 'citations: {{CITATION_PLACEHOLDER}}' exactly as written.
    4. TAGS: Choose only from 'data/synthetic', 'data/field-scale', 'approach/coupled', or 'approach/sequential'.
    5. CONCEPTS: Group findings under exact matching titles from this Master Concept List if relevant:
    {live_concept_list}

    RAW EXTRACTED DATA:
    {all_extracted_text[:15000]}

    TEMPLATE TO FILL EXPLICITLY:
    {raw_template}
    """
    
    final_synthesis = Settings.llm.complete(reduce_prompt)
    draft_note = final_synthesis.text

    print("🌐 Step 4: Fetching live citation data from OpenAlex...")
    doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9a-z]+)', draft_note)
    citation_count = get_citation_count(doi_match.group(1)) if doi_match else 0

    final_note = re.sub(r'citations:.*', f'citations: {citation_count}', draft_note)
    print("\n🚀 ANALYSIS COMPLETE!\n")
    print(final_note)


if __name__ == "__main__":
    home = "alexi"
    user = home
    VAULT_PATH = f"C:/Users/{user}/OneDrive - ETS/000-Doctorat/77_Bible_PhD/Bible PhD/"
    CONCEPTS_DIR = VAULT_PATH + "02_Concepts"
    TEMPLATE_FILE = VAULT_PATH + "00_Templates/Litterature note.md"
    PAPER_Path = f"C:/Users/{user}/OneDrive - ETS/00-Maitrise_Recherche/01-Geophysique/01-Papiers/"
    TARGET_PAPER = PAPER_Path + "Binley et al. - 2015 - The emergence of hydrogeophysics.pdf" 
    
    analyze_paper_map_reduce(TARGET_PAPER, CONCEPTS_DIR, TEMPLATE_FILE)