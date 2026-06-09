import requests
import networkx as nx
import matplotlib.pyplot as plt
import time

# 1. DEFINE YOUR RENOWNED HYDROGEOPHYSICS SEED ARTICLES
SEED_DOIS = [
    "10.1016/j.still.2004.10.004",      # Samouëlian (2005) - Resistivity in soil science
    "10.1002/hyp.10280",               # Binley (2015) - Time-lapse electrical imaging
    "10.1002/2015WR017016",            # Singha/Binley (2015) - Emergence of hydrogeophysics
    "10.1002/wat2.1513",               # Whiteley (2021) - Long-term resistivity monitoring
    "10.1007/s10712-022-09731-2",      # Parisi (2022) - ERT 30-year review / Mining waste
    "10.5194/hess-27-255-2023"         # Hermans (2023) - Towards 4D hydrogeology
]

def fetch_work_by_doi(doi):
    """Fetch core metadata and OpenAlex ID for a given DOI."""
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {'User-Agent': 'mailto:your-brainstorm@example.com'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_citing_works(openalex_id, limit=30):
    """Fetch the top most-cited works that cite a given OpenAlex ID."""
    url = f"https://api.openalex.org/works?filter=cites:{openalex_id}&sort=cited_by_count:desc&per_page={limit}"
    headers = {'User-Agent': 'mailto:your-brainstorm@example.com'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('results', [])
    return []

def main():
    G = nx.DiGraph()
    seed_openalex_ids = set()
    
    print("--- STEP 1: Fetching Seed Data & Downstream Citations ---")
    for doi in SEED_DOIS:
        seed_data = fetch_work_by_doi(doi)
        if not seed_data:
            print(f"Could not resolve DOI: {doi}")
            continue
            
        s_id = seed_data['id']
        seed_openalex_ids.add(s_id)
        
        # Shorten titles for legible graph labels
        short_title = seed_data['title'][:30] + "..."
        G.add_node(s_id, 
                   title=short_title, 
                   year=seed_data['publication_year'], 
                   gcs=seed_data['cited_by_count'] or 1,
                   is_seed=True)
        
        print(f"Resolved Seed: {short_title} ({seed_data['publication_year']})")
        
        # Fetch up to 30 top papers citing this seed (Forward expansion)
        citing_papers = fetch_citing_works(s_id, limit=30)
        for paper in citing_papers:
            p_id = paper['id']
            if p_id not in G:
                G.add_node(p_id, 
                           title=paper['title'][:30] + "...", 
                           year=paper['publication_year'], 
                           gcs=paper['cited_by_count'] or 1,
                           is_seed=False)
            # Add citation edge: Citing Paper -> Cites -> Seed Paper
            G.add_edge(p_id, s_id)
            
        time.sleep(0.2)  # Polite API pacing

    print(f"\nInitial Network Built: {G.number_of_nodes()} nodes, {G.number_of_edges()} links.")

    print("\n--- STEP 2 & 3: Calculating LCS and Applying Adaptive Filtering ---")
    # Calculate Local Citation Score (LCS)
    for node in list(G.nodes()):
        G.nodes[node]['lcs'] = G.in_degree(node)

    # ADAPTIVE FILTER: Keep all seeds, plus any citing paper that has a GCS >= 5 
    # (This prevents dropping highly relevant modern papers just because they are young)
    nodes_to_keep = []
    for node, attrs in G.nodes(data=True):
        if attrs['is_seed'] or attrs['gcs'] >= 5: 
            nodes_to_keep.append(node)
            
    filtered_G = G.subgraph(nodes_to_keep).copy()
    print(f"Filtered Network: {filtered_G.number_of_nodes()} nodes remaining.")

    # --- STEP 4: GENERATE CHRONOLOGICAL TIMELINE LAYOUT ---
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Create a custom layout where X-axis is STRICTLY the publication year
    import random
    random.seed(42)
    pos = {}
    
    # Group nodes by year to spread them out vertically (jittering)
    year_counts = {}
    for node, attrs in filtered_G.nodes(data=True):
        year = attrs['year']
        if year not in year_counts:
            year_counts[year] = 0
        year_counts[year] += 1
        
        # X-coordinate = Year (with a tiny fraction added so nodes don't stack perfectly vertically)
        x_coord = year + random.uniform(-0.15, 0.15)
        # Y-coordinate = Spread evenly over a vertical lane
        y_coord = year_counts[year] * 1.5 - (random.uniform(0, 1))
        
        pos[node] = (x_coord, y_coord)
    
    # Isolate groups for distinct styling
    seed_nodes = [n for n, attr in filtered_G.nodes(data=True) if attr['is_seed']]
    other_nodes = [n for n, attr in filtered_G.nodes(data=True) if not attr['is_seed']]
    
    # 1. Draw Citing Nodes (Circles colored by year)
    if other_nodes:
        sc_other = nx.draw_networkx_nodes(
            filtered_G, pos, nodelist=other_nodes, ax=ax,
            node_color=[filtered_G.nodes[n]['year'] for n in other_nodes],
            cmap=plt.cm.viridis, vmin=2004, vmax=2026,
            node_size=[min(400, max(40, filtered_G.nodes[n]['gcs'] * 0.3)) for n in other_nodes],
            alpha=0.6, edgecolors='none'
        )
    
    # 2. Draw Seed Nodes (Large Red Squares)
    sc_seeds = nx.draw_networkx_nodes(
        filtered_G, pos, nodelist=seed_nodes, node_shape='s', ax=ax,
        node_color=[filtered_G.nodes[n]['year'] for n in seed_nodes],
        cmap=plt.cm.viridis, vmin=2004, vmax=2026,
        node_size=500, edgecolors='red', linewidths=2
    )

    # 3. Draw Citation Paths (Curved lines look cleaner on timelines)
    nx.draw_networkx_edges(
        filtered_G, pos, arrowstyle="->", arrowsize=10, 
        edge_color="#d3d3d3", width=0.8, alpha=0.5, ax=ax,
        connectionstyle="arc3,rad=0.1" # Curves the lines slightly to avoid overlapping straight paths
    )
    
    # 4. Add Clear Text Labels for Seed Papers
    # Using author/year format dynamically rather than full overlapping titles
    seed_labels = {
        n: f"SEED ({filtered_G.nodes[n]['year']})\n{filtered_G.nodes[n]['title'][:20]}..." 
        for n in seed_nodes
    }
    nx.draw_networkx_labels(filtered_G, pos, labels=seed_labels, font_size=8, font_weight="bold", ax=ax)

    # 5. Build Timeline X-Axis Grid
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#444444')
    ax.spines['bottom'].set_linewidth(1.5)
    
    ax.get_yaxis().set_visible(False) # Turn off arbitrary vertical axes
    ax.set_xticks(range(2004, 2027, 2)) # X-ticks every 2 years
    ax.tick_params(axis='x', labelsize=11, colors='#444444')
    ax.grid(axis='x', color='#f0f0f0', linestyle='--', linewidth=1)

    plt.title("Hydrogeophysics Mapping Pipeline: Historical Timeline & Evolution Flow", fontsize=14, weight='bold', pad=20)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()