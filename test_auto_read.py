import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

# 1. CONFIGURE THE BRAIN & TRANSLATOR
# We configure LlamaIndex global settings to use Ollama (Mistral) and BGE-Small
Settings.llm = Ollama(model="mistral", request_timeout=1200.0)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

def analyze_paper(pdf_path):
    print(f"📖 Step 1: Parsing and embedding {os.path.basename(pdf_path)}...")
    
    # 2. READ THE PDF (Uses PyMuPDF under the hood automatically)
    reader = SimpleDirectoryReader(input_files=[pdf_path])
    documents = reader.load_data()
    
    # 3. SET UP CHROMADB (Ephemeral local database for this specific paper)
    db = chromadb.EphemeralClient() # Keeps it in memory since we do it one-by-one
    chroma_collection = db.get_or_create_collection("temporary_paper_analysis")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # 4. INDEX THE DOCUMENT
    # This cuts the text into chunks, passes them to BGE-Small, and saves them to Chroma
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context
    )
    
    # 5. CREATE THE QUERY ENGINE
    # We configure it to pull the top 5 most relevant blocks of text for our questions
    query_engine = index.as_query_engine(similarity_top_k=5)
    
    print("🧠 Step 2: Extracting concepts and formatting for Obsidian...")
    
    # 6. THE PROMPT
    # We instruct Mistral to format the output to match our exact Obsidian templates
    obsidian_prompt = """
    You are an expert academic research assistant. Analyze the provided text segments from the paper and output a clean Markdown literature summary.
    
    Strictly follow this layout format:
    
    ---
    aliases: []
    tags: [concept, auto-summary]
    ---
    # [Insert Clear Paper Short Title / Citation Key here]
    
    > **Core Theme:** 1-2 sentence high-level summary of what this paper accomplishes.
    
    ### 💡 Key Concepts & Findings
    Identify the main concepts, methodologies (like specific imaging methods or equations), or parameters analyzed. For each, provide a bullet point with a brief explanation.
    
    ### 🛠️ Key Equations & Data Formulations
    List any crucial governing equations, petrophysical relations, or exact parameter boundaries mentioned in the text segments.
    
    ### 📝 Discussion & Key Takeaways
    What are the primary conclusions, limitations, or instrumentation gaps the authors encountered?
    """
    
    response = query_engine.query(obsidian_prompt)
    
    print("\n🚀 ANALYSIS COMPLETE! Copy the text below into your Obsidian vault:\n")
    print(response)

if __name__ == "__main__":
    # Change this path to point directly to any PDF paper on your machine
    target_paper = "C:/Users/alexi/Downloads/gao2015.pdf" 
    analyze_paper(target_paper)