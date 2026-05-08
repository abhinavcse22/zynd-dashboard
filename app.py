import streamlit as st
import pandas as pd
import urllib.parse
import subprocess
import os

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
st.markdown("Centralized lead intelligence and automated harvesting controls.")

# --- NAVIGATION TABS ---
tab_data, tab_engine = st.tabs(["📊 Intelligence Dashboard", "⚙️ Engine Control Room"])

# ==========================================
# TAB 1: INTELLIGENCE DASHBOARD (Your existing UI)
# ==========================================
with tab_data:
    try:
        df_reddit = load_data("Reddit Leads")
        df_github = load_data("GitHub Leads")
    except Exception as e:
        st.error("Failed to load database.")
        st.stop()

    st.sidebar.header("Filter Leads")
    platform = st.sidebar.selectbox("Select Platform", ["GitHub (Builders)", "Reddit (Intent)"])
    min_score = st.sidebar.slider("Minimum Lead Score", 1, 10, 7) 

    if platform == "Reddit (Intent)":
        st.subheader(f"Reddit Intelligence ({len(df_reddit)} Total Leads)")
        filtered_df = df_reddit[df_reddit['Lead Score (1-10)'] >= min_score]
        intent_filter = st.sidebar.multiselect("Intent Category", df_reddit['Intent Category'].unique())
        if intent_filter:
            filtered_df = filtered_df[filtered_df['Intent Category'].isin(intent_filter)]
            
        col1, col2, col3 = st.columns(3)
        col1.metric("High-Intent Targets", len(filtered_df))
        col2.metric("Competitor Mentions", len(filtered_df[filtered_df['Intent Category'].str.contains('Competitor', na=False)]))
        col3.metric("Pain Points Found", len(filtered_df[filtered_df['Intent Category'].str.contains('Pain Point', na=False)]))
        st.dataframe(filtered_df, use_container_width=True, height=500)

    elif platform == "GitHub (Builders)":
        st.subheader(f"GitHub Builders ({len(df_github)} Total Leads)")
        filtered_df = df_github[df_github['Lead Score (1-10)'] >= min_score]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Qualified Builders", len(filtered_df))
        col2.metric("Emails Unlocked", len(filtered_df[filtered_df['Email'].notna()]))
        col3.metric("X Profiles Found", len(filtered_df[filtered_df['Twitter/X'].notna()]))
        st.dataframe(filtered_df, use_container_width=True, height=500)

# ==========================================
# TAB 2: ENGINE CONTROL ROOM
# ==========================================
with tab_engine:
    st.subheader("Master Engine Controls")
    st.markdown("Trigger data harvesting and enrichment scripts directly from the cloud.")
    
    colA, colB = st.columns(2)
    
    with colA:
        st.info("**Top-of-Funnel Harvester**\nHunts for fresh AI agent builders on GitHub and pushes them to the database.")
        if st.button("🚀 Run GitHub Harvester", use_container_width=True):
            with st.spinner("Initializing GitHub Scraper... Check terminal for live logs."):
                try:
                    # Executes your local script
                    subprocess.Popen(["python3", "zynd_leads.py"])
                    st.success("Harvester launched successfully! It is running in the background.")
                except Exception as e:
                    st.error(f"Error launching script: {e}")

    with colB:
        st.warning("**Master Enricher (Turbo Mode)**\nHacks commit logs to find hidden emails for any blank profiles in the database.")
        if st.button("⚡ Run Master Enricher", use_container_width=True):
            with st.spinner("Engaging Turbo Enricher... Check terminal for live logs."):
                try:
                    # Executes your local script
                    subprocess.Popen(["python3", "zynd_master_scraper.py"])
                    st.success("Enricher launched successfully! Watch your Google Sheet to see emails populate.")
                except Exception as e:
                    st.error(f"Error launching script: {e}")
                    
    st.divider()
    st.markdown("*(Note: The Reddit Autopilot runs independently via GitHub Actions at 5:30 AM IST daily).*")
