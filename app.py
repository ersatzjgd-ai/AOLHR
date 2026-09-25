import os
import streamlit as st
import pandas as pd
from rapidfuzz import fuzz

# --- CONFIGURATION ---
COL_NAME = "Name"
COL_ROLE = "Field/Sector"
COL_INDUSTRY = "Field/Sector"
COL_RESUME = "Resume"

SYNONYMS = {
    "frontend": ["react", "angular", "vue", "ui", "javascript", "css"],
    "backend": ["python", "node", "java", "django", "sql", "api"],
    "hr": ["human resources", "recruiter", "talent acquisition"],
    "data": ["analyst", "scientist", "machine learning", "sql", "database"],
}

st.set_page_config(page_title="Candidate Search Hub", page_icon="🔍", layout="wide")

# --- INITIALIZE FALLBACK DATAFRAME ---
df = pd.DataFrame(columns=[COL_NAME, COL_ROLE, COL_INDUSTRY, COL_RESUME, "_Search_Text"])

# --- DATA LOADING ---
@st.cache_data(ttl=300) 
def load_data(csv_url):
    data = pd.read_csv(csv_url)
    data = data.dropna(subset=[COL_NAME, COL_ROLE]) 
    data = data.fillna("")
    data["_Search_Text"] = data.astype(str).apply(lambda row: ' '.join(row.values).lower(), axis=1)
    return data

# --- SECRETS CHECK & EXECUTION ---
csv_url = None

# 1. Try Railway Environment Variables
if "SHEET_CSV_URL" in os.environ:
    csv_url = os.environ["SHEET_CSV_URL"]
else:
    # 2. Try Streamlit Secrets (for local development)
    try:
        if "sheet_csv_url" in st.secrets:
            csv_url = st.secrets["sheet_csv_url"]
    except FileNotFoundError:
        pass # Ignore the error if no secrets file exists

if not csv_url:
    st.error("Missing 'SHEET_CSV_URL'! Ensure your Railway environment variable is set.")
    st.stop()
else:
    try:
        df = load_data(csv_url)
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
    
    if selected_roles:
        filtered_df = filtered_df[filtered_df[COL_ROLE].isin(selected_roles)]
    if selected_industries:
        filtered_df = filtered_df[filtered_df[COL_INDUSTRY].isin(selected_industries)]
        
    if query:
        expanded_terms = expand_query_with_synonyms(query)
        
        def calculate_match_score(text):
            score = 0
            for term in expanded_terms:
                if term in text:
                    score += 50
            
            fuzzy_score = fuzz.partial_ratio(query.lower(), text)
            if fuzzy_score > 75:
                score += fuzzy_score
                
            return score

        filtered_df["_Score"] = filtered_df["_Search_Text"].apply(calculate_match_score)
        filtered_df = filtered_df[filtered_df["_Score"] > 0].sort_values(by="_Score", ascending=False)
        
    return filtered_df

# --- UI LAYOUT ---
st.title("🔍 HR Candidate Search")

search_query = st.text_input("Search by Name, Skills, or Keywords...", placeholder="e.g., John Doe, Frontend, Python...")

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
            
            if pd.notna(row[COL_RESUME]) and str(row[COL_RESUME]).strip() != "":
                st.link_button("📄 View Resume", row[COL_RESUME])
            
            st.write("")
