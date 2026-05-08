import streamlit as st
import pandas as pd
import urllib.parse

# --- THE ENGINES (MODULAR ARCHITECTURE) ---
import zynd_leads
import zynd_master_scraper
import zynd_daily_engine 
import zynd_twitter_sniper

# --- CONFIGURATION ---
st.set_page_config(page_title="Zynd Command Center", page_icon="⚡", layout="wide")
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

@st.cache_data(ttl=600)
def load_data(sheet_name):
    safe_sheet_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={safe_sheet_name}"
    return pd.read_csv(url)

# --- UI HEADER ---
st.title("⚡ Zynd GTM Command Center")
st.markdown("Centralized lead intelligence, Twitter sniping, and automated harvesting.")

# --- NAVIGATION TABS ---
tab_data, tab_twitter, tab_engine = st.tabs(["📊 Intelligence Dashboard", "🐦 Twitter Sniper", "⚙️ Engine Control Room"])

# ==========================================
# TAB 1: INTELLIGENCE DASHBOARD
# ==========================================
with tab_data:
    try:
        df_reddit = load_data("Reddit Leads")
        df_github = load_data("GitHub Leads")
    except Exception as e:
        st.error("Failed to load database. Check your connection.")
        st.stop()

    st.sidebar.header("Filter Leads")
    platform = st.sidebar.selectbox("Select Platform", ["GitHub (Builders)", "Reddit (Intent)"])
    min_score = st.sidebar.slider("Minimum Lead Score", 1, 10, 7)

    if platform == "Reddit (Intent)":
        st.subheader(f"Reddit Intelligence ({len(df_reddit)} Total Leads)")
        filtered_df = df_reddit[df_reddit['Lead Score (1-10)'] >= min_score]
        st.dataframe(filtered_df, use_container_width=True, height=500)

    elif platform == "GitHub (Builders)":
        st.subheader(f"GitHub Builders ({len(df_github)} Total Leads)")
        filtered_df = df_github[df_github['Lead Score (1-10)'] >= min_score]
        st.dataframe(filtered_df, use_container_width=True, height=500)

# ==========================================
# TAB 2: TWITTER SNIPER (PULLS FROM MODULE)
# ==========================================
with tab_twitter:
    st.subheader("Twitter / X Lead Sniper")
    st.markdown("Automated Boolean queries to find live builders, pain points, and competitor complaints.")
    
    st.divider()
    
    # Call the external module to get the target URLs
    urls = zynd_twitter_sniper.get_sniper_urls()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**🎯 Target 1: Building in Public**\nFind founders actively sharing their AI agent progress.")
        st.link_button("Launch 'Build in Public' Radar 🚀", urls["build_in_public"], use_container_width=True)

    with col2:
        st.error("**🔥 Target 2: Active Pain Points**\nFind developers who are currently stuck and need Zynd.")
        st.link_button("Launch 'Pain Point' Radar 🚀", urls["pain_points"], use_container_width=True)

    with col3:
        st.warning("**⚔️ Target 3: Competitor Poaching**\nFind users complaining about the tools you replace.")
        st.link_button("Launch 'Competitor' Radar 🚀", urls["competitor_poaching"], use_container_width=True)

# ==========================================
# TAB 3: ENGINE CONTROL ROOM (THE 3 SCRAPERS)
# ==========================================
with tab_engine:
    st.subheader("Master Engine Controls")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**1. GitHub Harvester**\nHunts for AI agent builders.")
        if st.button("🚀 Run GitHub Engine", use_container_width=True):
            with st.spinner("Scraping GitHub..."):
                try:
                    zynd_leads.harvest_leads()
                    st.success("GitHub database updated!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        st.warning("**2. Master Enricher**\nHacks commit logs for emails.")
        if st.button("⚡ Run Turbo Enricher", use_container_width=True):
            with st.spinner("Finding emails..."):
                try:
                    zynd_master_scraper.enrich_database()
                    st.success("Emails populated!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")
                    
    with col3:
        st.success("**3. Reddit Radar**\nHunts for competitor complaints.")
        if st.button("📡 Run Reddit Engine", use_container_width=True):
            with st.spinner("Scanning Reddit..."):
                try:
                    zynd_daily_engine.run_reddit_scraper() # Assumes you have a main function in this file
                    st.success("Reddit database updated!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")
