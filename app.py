import streamlit as st
import pandas as pd
import urllib.parse
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- IMPORT ENGINES ---
import zynd_leads
import zynd_master_scraper
import zynd_daily_engine
import zynd_twitter_engine

# --- SETTINGS & THEME ---
st.set_page_config(page_title="Zynd | GTM Command Center", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 10px; }
    h1, h2, h3 { color: #58a6ff !important; }
    </style>
    """, unsafe_allow_html=True)

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

@st.cache_data(ttl=300)
def load_full_database():
    try:
        def get_url(name): return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
        gh = pd.read_csv(get_url("GitHub Leads"))
        rd = pd.read_csv(get_url("Reddit Leads"))
        tw = pd.read_csv(get_url("Twitter Leads"))
        return gh, rd, tw
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- THE DEDUPLICATION ENGINE ---
def clean_database():
    """Finds and removes duplicate leads across all tabs in Google Sheets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    total_removed = 0
    
    # 1. Clean GitHub
    try:
        gh_sheet = client.open_by_key(SHEET_ID).worksheet("GitHub Leads")
        gh_data = gh_sheet.get_all_records()
        if gh_data:
            df = pd.DataFrame(gh_data)
            before = len(df)
            df.drop_duplicates(subset=['Project URL'], keep='first', inplace=True) # Drop dupes based on URL
            after = len(df)
            if before > after:
                gh_sheet.clear()
                gh_sheet.update([df.columns.values.tolist()] + df.values.tolist())
                total_removed += (before - after)
    except: pass

    # 2. Clean Reddit
    try:
        rd_sheet = client.open_by_key(SHEET_ID).worksheet("Reddit Leads")
        rd_data = rd_sheet.get_all_records()
        if rd_data:
            df = pd.DataFrame(rd_data)
            before = len(df)
            df.drop_duplicates(subset=['Post URL'], keep='first', inplace=True)
            after = len(df)
            if before > after:
                rd_sheet.clear()
                rd_sheet.update([df.columns.values.tolist()] + df.values.tolist())
                total_removed += (before - after)
    except: pass

    return total_removed

# --- LOAD DATA ---
df_gh, df_rd, df_tw = load_full_database()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=80)
    st.title("Zynd OS")
    st.markdown("---")
    menu = st.radio("Navigation", ["📈 Pipeline Overview", "💻 GitHub Builders", "💬 Reddit Intent", "🐦 Twitter Sniper", "⚙️ Control Room"])
    st.markdown("---")
    st.info(f"**Last Sync:** {pd.Timestamp.now().strftime('%H:%M:%S')}")

# ==========================================
# 📈 TAB: PIPELINE OVERVIEW
# ==========================================
if menu == "📈 Pipeline Overview":
    st.header("Executive GTM Summary")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Lead Pool", len(df_gh) + len(df_rd) + len(df_tw))
    m2.metric("Qualified Builders", len(df_gh[df_gh['Lead Score (1-10)'] >= 8]) if not df_gh.empty else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty else 0)
    m4.metric("Contactable (Emails)", len(df_gh[df_gh['Email'].notna()]) if not df_gh.empty else 0)

    st.divider()
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Recent High-Intent Activity")
        st.dataframe(df_rd.head(25), use_container_width=True)

    with col_right:
        st.subheader("Platform Distribution")
        chart_data = pd.DataFrame({'Source': ['GitHub', 'Reddit', 'Twitter'], 'Count': [len(df_gh), len(df_rd), len(df_tw)]})
        st.bar_chart(chart_data.set_index('Source'))

# ==========================================
# 💻 TAB: GITHUB BUILDERS
# ==========================================
elif menu == "💻 GitHub Builders":
    st.header("Technical Lead Discovery")
    
    q_col1, q_col2 = st.columns([3, 1])
    with q_col2:
        min_gh = st.slider("Min Lead Score", 1, 10, 7, key="gh_slider")
    
    filtered_gh = df_gh[df_gh['Lead Score (1-10)'] >= min_gh] if not df_gh.empty else df_gh
    
    # NEW: Tab Lead Count
    st.metric("Total GitHub Leads (Filtered)", len(filtered_gh))
    st.dataframe(filtered_gh, use_container_width=True, height=600)

# ==========================================
# 💬 TAB: REDDIT INTENT
# ==========================================
elif menu == "💬 Reddit Intent":
    st.header("Social Intent & Pain Points")
    
    # NEW: Tab Lead Count
    st.metric("Total Reddit Leads", len(df_rd))
    st.dataframe(df_rd, use_container_width=True, height=600)

# ==========================================
# 🐦 TAB: TWITTER SNIPER
# ==========================================
elif menu == "🐦 Twitter Sniper":
    st.header("Real-time Twitter Harvesting")
    
    # NEW: Tab Lead Count
    st.metric("Total Twitter Leads", len(df_tw))
    st.dataframe(df_tw, use_container_width=True, height=400)
    
    st.divider()
    st.subheader("Manual Pulse Check (Deep Search)")
    import zynd_twitter_sniper
    urls = zynd_twitter_sniper.get_sniper_urls()
    c1, c2, c3 = st.columns(3)
    c1.link_button("Build in Public Radar 🚀", urls["build_in_public"])
    c2.link_button("Pain Point Radar 🔥", urls["pain_points"])
    c3.link_button("Competitor Radar ⚔️", urls["competitor_poaching"])

# ==========================================
# ⚙️ TAB: CONTROL ROOM
# ==========================================
elif menu == "⚙️ Control Room":
    st.header("Engine Control Room")
    st.warning("Running these scripts will consume API tokens and update the live Google Sheet.")
    
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        st.subheader("🚀 GitHub Harvester")
        if st.button("Start GitHub Engine"):
            with st.spinner("Executing..."):
                zynd_leads.harvest_leads()
                st.success("GitHub Updated!")

    with row1_col2:
        st.subheader("⚡ Master Enricher")
        if st.button("Engage Turbo Scraper"):
            with st.spinner("Executing..."):
                zynd_master_scraper.enrich_database()
                st.success("Enrichment Complete!")

    with row2_col1:
        st.subheader("📡 Reddit Radar")
        if st.button("Start Reddit Engine"):
            with st.spinner("Executing..."):
                zynd_daily_engine.run_reddit_scraper()
                st.success("Reddit Updated!")

    with row2_col2:
        st.subheader("🐦 Twitter Autopilot")
        if st.button("Start Twitter Engine"):
            with st.spinner("Executing..."):
                zynd_twitter_engine.run_twitter_scraper()
                st.success("Twitter Updated!")

    st.divider()
    
    # NEW: DATABASE MAINTENANCE SECTION
    st.subheader("🧹 Database Maintenance")
    st.write("Scan the Google Sheet and permanently delete any duplicate leads.")
    if st.button("Clean Duplicates", type="primary"):
        with st.spinner("Scanning database for duplicates..."):
            removed = clean_database()
            if removed > 0:
                st.success(f"Database clean! Removed {removed} duplicate leads.")
                st.cache_data.clear()
            else:
                st.info("Database is already perfectly clean. No duplicates found.")
