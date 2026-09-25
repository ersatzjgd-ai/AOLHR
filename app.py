import os
import streamlit as st
import pandas as pd
from rapidfuzz import fuzz

# --- CONFIGURATION ---
COL_NAME = "Candidate Name"
COL_ROLE = "Role"
COL_INDUSTRY = "Industry"
COL_RESUME = "Resume Link"

SYNONYMS = {
    "frontend": ["react", "angular", "vue", "ui", "javascript", "css"],
    "backend": ["python", "node", "java", "django", "sql", "api"],
    "hr": ["human resources", "recruiter", "talent acquisition"],
    "data": ["analyst", "scientist", "machine learning", "sql", "database"],
}

st.set_page_config(page_title="Candidate Search Hub", page_icon="🔍", layout="wide")

# --- AUTHENTICATION ---
def check_password():
    """Returns True if the user has entered the correct password."""
    # If already authenticated, skip the login screen
    if st.session_state.get("password_correct", False):
        return True

    # Show login screen
    st.title("🔒 HR Candidate Search Hub")
    st.write("Please log in to access the candidate database.")
    
    with st.form("login_form"):
        password = st.text_input("Enter Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            # Look for the password in Railway environment variables or local secrets
            expected_password = os.environ.get("APP_PASSWORD")
            if not expected_password:
                try:
                    if "APP_PASSWORD" in st.secrets:
                        expected_password = st.secrets["APP_PASSWORD"]
                except FileNotFoundError:
                    pass
            
            if not expected_password:
                st.error("System Error: 'APP_PASSWORD' environment variable is not set on the server.")
                return False
                
            if password == expected_password:
                st.session_state["password_correct"] = True
                st.rerun() # Refresh the page to show the main app
            else:
                st.error("Incorrect password")
                
    return False

# Stop execution here if the password is not correct
if not check_password():
    st.stop()


# ==========================================
# --- MAIN APPLICATION (PROTECTED) ---
# ==========================================

# --- INITIALIZE FALLBACK DATAFRAME ---
df = pd.DataFrame(columns=[COL_NAME, COL_ROLE, COL_INDUSTRY, COL_RESUME, "_Search_Text"])

# --- DATA LOADING ---
@st.cache_data(ttl=300) 
def load_data(csv_url):
    data = pd.read_csv(csv_url)
    if COL_NAME in data.columns and COL_ROLE in data.columns:
        data = data.dropna(subset=[COL_NAME, COL_ROLE]) 
    data = data.fillna("")
    data["_Search_Text"] = data.astype(str).apply(lambda row: ' '.join(row.values).lower(), axis=1)
    return data

# --- SECRETS CHECK & EXECUTION ---
csv_url = None

if "SHEET_CSV_URL" in os.environ:
    csv_url = os.environ["SHEET_CSV_URL"].strip().strip('"').strip("'")
else:
    try:
        if "sheet_csv_url" in st.secrets:
            csv_url = st.secrets["sheet_csv_url"].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass 

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
    
    if selected_roles and COL_ROLE in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[COL_ROLE].isin(selected_roles)]
    if selected_industries and COL_INDUSTRY in filtered_df.columns:
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

# Logout button
if st.button("Logout", type="secondary"):
    st.session_state["password_correct"] = False
    st.rerun()

search_query = st.text_input("Search by Name, Skills, or Keywords...", placeholder="e.g., John Doe, Frontend, Python...")

col1, col2 = st.columns(2)
with col1:
    all_roles = sorted(list(df[COL_ROLE].unique())) if COL_ROLE in df.columns else []
    selected_roles = st.multiselect("Filter by Role", all_roles)
with col2:
    all_industries = sorted(list(df[COL_INDUSTRY].unique())) if COL_INDUSTRY in df.columns else []
    selected_industries = st.multiselect("Filter by Industry", all_industries)

st.divider()

# --- DISPLAY RESULTS ---
if not search_query and not selected_roles and not selected_industries:
    st.info("👋 Enter a search term or select filters above to start finding candidates.")
else:
    results_df = search_candidates(df, search_query, selected_roles, selected_industries)

    if results_df.empty:
        st.warning("No candidates found matching your criteria.")
    else:
        st.success(f"Found {len(results_df)} candidate(s)")
        
        for _, row in results_df.iterrows():
            with st.container():
                candidate_name = row.get(COL_NAME, "Unknown Name")
                candidate_role = row.get(COL_ROLE, "N/A")
                candidate_industry = row.get(COL_INDUSTRY, "N/A")
                
                st.markdown(f"""
                    <div style="
                        border: 1px solid #e0e0e0; 
                        border-radius: 8px; 
                        padding: 20px; 
                        margin-bottom: 10px;
                        background-color: #f9f9fb;
                        color: #333;">
                        <h3 style="margin-top: 0; color: #0056b3;">{candidate_name}</h3>
                        <p style="margin-bottom: 5px; font-size: 16px;">
                            <b>Role:</b> {candidate_role} <br>
                            <b>Industry:</b> {candidate_industry}
                        </p>
                    </div>
                """, unsafe_allow_html=True)
                
                resume_link = row.get(COL_RESUME)
                if pd.notna(resume_link) and str(resume_link).strip() != "":
                    st.link_button("📄 View Resume", str(resume_link))
                
                st.write("")
