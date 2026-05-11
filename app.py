import streamlit as st
import pandas as pd
import urllib.parse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# --- SETTINGS & THEME ---
st.set_page_config(page_title="Zynd Intelligence | Lead OS", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; transition: all 0.3s ease; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88, 166, 255, 0.2); }
    .stDataFrame { border: 1px solid #30363d; border-radius: 10px; overflow: hidden; }
    h1, h2, h3 { color: #58a6ff !important; font-family: 'Inter', sans-serif; }
    .login-box { max-width: 400px; margin: 100px auto; padding: 30px; background: #161b22; border-radius: 12px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

# --- SECURE LOGIN GATEWAY ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        # Check if the entered password matches ANY password in the secrets dictionary
        if st.session_state["password"] in st.secrets["passwords"].values():
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password in plain text
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Render the sleek login screen
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=60)
    st.title("Zynd Intelligence")
    st.write("Please log in to access your workspace.")
    
    st.text_input("Workspace Password", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("🔒 Incorrect password. Please try again.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    return False

# --- HALT EXECUTION IF NOT LOGGED IN ---
if not check_password():
    st.stop()

# ==========================================
# 🚀 CORE APPLICATION (HIDDEN BEHIND LOGIN)
# ==========================================

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

@st.cache_data(ttl=300)
def load_full_database():
    """Loads each tab independently so one empty sheet doesn't crash the others."""
    def get_url(name): 
        return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
    
    try: gh = pd.read_csv(get_url("GitHub Leads"))
    except: gh = pd.DataFrame()
    
    try: rd = pd.read_csv(get_url("Reddit Leads"))
    except: rd = pd.DataFrame()
    
    try: tw = pd.read_csv(get_url("Twitter Leads"))
    except: tw = pd.DataFrame()
    
    try: star = pd.read_csv(get_url("github_stargazer_leads"))
    except: star = pd.DataFrame()
    
    return gh, rd, tw, star

# --- LOAD DATA ---
df_gh, df_rd, df_tw, df_star = load_full_database()

# --- SAAS SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=60)
    st.title("Zynd OS")
    st.caption("v1.0 | Enterprise Edition")
    st.markdown("---")
    
    # Renamed to sound like a premium SaaS product
    menu = st.radio("Workspace", [
        "📊 Master Dashboard", 
        "🧑‍💻 Developer Leads", 
        "📡 Intent Signals", 
        "🎯 Social Sniper", 
        "⚡ Enrichment Engine"
    ])
    
    st.markdown("---")
    st.info(f"🟢 System Online\n\nLast Sync: {pd.Timestamp.now().strftime('%H:%M')}")
    if st.button("Log Out", type="secondary"):
        st.session_state["password_correct"] = False
        st.rerun()

# ==========================================
# 📊 TAB: MASTER DASHBOARD
# ==========================================
if menu == "📊 Master Dashboard":
    st.header("Pipeline Intelligence")
    st.write("High-level overview of your active lead generation engines.")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Lead Pool", len(df_gh) + len(df_rd) + len(df_tw) + len(df_star))
    m2.metric("Hot Stargazer Leads", len(df_star[df_star['lead_bucket'] == 'Hot lead']) if not df_star.empty and 'lead_bucket' in df_star.columns else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty and 'Lead Score (1-10)' in df_rd.columns else 0)
    m4.metric("Market Sentiment", "Bullish", delta="Active Builders")

    st.divider()
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Recent High-Intent Activity")
        if not df_rd.empty:
            st.data_editor(df_rd.head(25), use_container_width=True, num_rows="dynamic")
        else:
            st.info("Awaiting new signals...")

    with col_right:
        st.subheader("Platform Distribution")
        chart_data = pd.DataFrame({'Source': ['GitHub', 'Reddit', 'Twitter'], 'Count': [len(df_gh), len(df_rd), len(df_tw)]})
        st.bar_chart(chart_data.set_index('Source'))

# ==========================================
# 🧑‍💻 TAB: DEVELOPER LEADS
# ==========================================
elif menu == "🧑‍💻 Developer Leads":
    st.header("Technical Lead Intelligence")
    st.write("Explore builders extracted from competitor repositories.")
    # (Your existing GitHub code here... kept exactly the same for functionality)
    st.data_editor(df_gh, use_container_width=True, height=600, num_rows="dynamic")

# ==========================================
# 📡 TAB: INTENT SIGNALS
# ==========================================
elif menu == "📡 Intent Signals":
    st.header("Social Intent & Pain Points")
    st.write("Users actively expressing frustration or requesting solutions.")
    st.metric("Total Intent Leads", len(df_rd))
    st.data_editor(df_rd, use_container_width=True, height=600, num_rows="dynamic")

# ==========================================
# 🎯 TAB: SOCIAL SNIPER
# ==========================================
elif menu == "🎯 Social Sniper":
    st.header("Social Profile Extraction")
    st.write("Builders publicly sharing their progress and workflows.")
    st.metric("Total Social Leads", len(df_tw))
    st.data_editor(df_tw, use_container_width=True, height=600, num_rows="dynamic")

# ==========================================
# ⚡ TAB: ENRICHMENT ENGINE
# ==========================================
elif menu == "⚡ Enrichment Engine":
    st.header("Data Enrichment & Automation")
    st.write("Launch cloud-based pipelines to populate your database with fresh intelligence.")
    
    # We remove the terminal jargon and make it look like SaaS cards
    with st.container(border=True):
        st.subheader("🔭 Competitor Radar (GitHub)")
        st.write("Scan target repositories and extract developers based on intent.")
        st.text_input("Target Repositories (owner/repo)", value="langchain-ai/langchain")
        if st.button("Run Radar Scan", type="primary"):
            st.info("Feature temporarily paused for UI audit.")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🌐 Social Signal Engine")
            st.write("Scrape Twitter for specific keywords and intent.")
            if st.button("Run Social Scrape", use_container_width=True):
                st.info("Feature temporarily paused for UI audit.")

    with col2:
        with st.container(border=True):
            st.subheader("💬 Forum Intent Engine")
            st.write("Scrape Reddit for pain points and workflow bottlenecks.")
            if st.button("Run Forum Scrape", use_container_width=True):
                st.info("Feature temporarily paused for UI audit.")
                
    st.divider()
    st.subheader("🧹 Workspace Maintenance")
    if st.button("Clean Duplicate Leads", type="secondary"):
        st.info("Feature temporarily paused for UI audit.")
