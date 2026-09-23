import streamlit as st
import pandas as pd
from rapidfuzz import fuzz

# --- CONFIGURATION ---
# Change these variables to match your exact Google Sheet column names
COL_NAME = "Candidate Name"
COL_ROLE = "Role"
COL_INDUSTRY = "Industry"
COL_RESUME = "Resume Link"

# Basic Semantic Dictionary (Expand this based on your needs)
SYNONYMS = {
    "frontend": ["react", "angular", "vue", "ui", "javascript", "css"],
    "backend": ["python", "node", "java", "django", "sql", "api"],
    "hr": ["human resources", "recruiter", "talent acquisition"],
    "data": ["analyst", "scientist", "machine learning", "sql", "database"],
}

st.set_page_config(page_title="Candidate Search Hub", page_icon="🔍", layout="wide")

# --- DATA LOADING ---
@st.cache_data(ttl=300) # Caches data for 5 mins to auto-refresh changes from Google Sheets
def load_data():
    # Safely get the URL from Streamlit secrets
    try:
        csv_url = st.secrets["sheet_csv_url"]
    except KeyError:
        st.error("Missing 'sheet_csv_url' in secrets.toml (or Railway environment variables)!")
        st.stop()

    # Read the CSV directly from the web URL
    df = pd.read_csv(csv_url)
    
    # Clean empty rows
    df = df.dropna(subset=[COL_NAME, COL_ROLE]) 
    df = df.fillna("")
    
    # Create a hidden combined column for robust searching
    df["_Search_Text"] = df.astype(str).apply(lambda row: ' '.join(row.values).lower(), axis=1)
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Could not read the Google Sheet. Error: {e}")
    st.stop()

# --- HELPER FUNCTIONS ---
def expand_query_with_synonyms(query):
    query = query.lower()
    words = query.split()
    expanded_words = set(words)
    
    for word in words:
        for key, related_terms in SYNONYMS.items():
            if word == key or word in related_terms:
                expanded_words.add(key)
                expanded_words.update(related_terms)
                
    return list(expanded_words)

def search_candidates(dataframe, query, selected_roles, selected_industries):
    filtered_df = dataframe.copy()
    
    # 1. Filter by Dynamic Tags (Roles & Industries)
    if selected_roles:
        filtered_df = filtered_df[filtered_df[COL_ROLE].isin(selected_roles)]
    if selected_industries:
        filtered_df = filtered_df[filtered_df[COL_INDUSTRY].isin(selected_industries)]
        
    # 2. Text Search with Fuzzy & Semantic Matching
    if query:
        expanded_terms = expand_query_with_synonyms(query)
        
        def calculate_match_score(text):
            score = 0
            # Check for exact/partial substring matches of expanded terms (Semantic)
            for term in expanded_terms:
                if term in text:
                    score += 50
            
            # Check for typos against the raw query (Fuzzy)
            fuzzy_score = fuzz.partial_ratio(query.lower(), text)
            if fuzzy_score > 75: # Threshold for typos
                score += fuzzy_score
                
            return score

        filtered_df["_Score"] = filtered_df["_Search_Text"].apply(calculate_match_score)
        # Keep only rows with a score > 0 and sort by best match
        filtered_df = filtered_df[filtered_df["_Score"] > 0].sort_values(by="_Score", ascending=False)
        
    return filtered_df

# --- UI LAYOUT ---
st.title("🔍 HR Candidate Search")

# Search Bar
search_query = st.text_input("Search by Name, Skills, or Keywords...", placeholder="e.g., John Doe, Frontend, Python...")

# Dynamic Tags (Generated automatically from sheet data)
col1, col2 = st.columns(2)
with col1:
    all_roles = sorted(list(df[COL_ROLE].unique()))
    selected_roles = st.multiselect("Filter by Role", all_roles)
with col2:
    all_industries = sorted(list(df[COL_INDUSTRY].unique()))
    selected_industries = st.multiselect("Filter by Industry", all_industries)

st.divider()

# --- DISPLAY RESULTS ---
results_df = search_candidates(df, search_query, selected_roles, selected_industries)

if results_df.empty:
    st.warning("No candidates found matching your criteria.")
else:
    st.success(f"Found {len(results_df)} candidate(s)")
    
    # Render Candidate Cards
    for _, row in results_df.iterrows():
        with st.container():
            st.markdown(f"""
                <div style="
                    border: 1px solid #e0e0e0; 
                    border-radius: 8px; 
                    padding: 20px; 
                    margin-bottom: 10px;
                    background-color: #f9f9fb;
                    color: #333;">
                    <h3 style="margin-top: 0; color: #0056b3;">{row[COL_NAME]}</h3>
                    <p style="margin-bottom: 5px; font-size: 16px;">
                        <b>Role:</b> {row[COL_ROLE]} <br>
                        <b>Industry:</b> {row[COL_INDUSTRY]}
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
            # Link button opens the resume in a new tab natively
            if pd.notna(row[COL_RESUME]) and str(row[COL_RESUME]).strip() != "":
                st.link_button("📄 View Resume", row[COL_RESUME])
            
            st.write("") # small spacer between cards
