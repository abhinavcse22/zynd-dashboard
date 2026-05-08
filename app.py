import streamlit as st
import pandas as pd
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="Zynd Lead Engine", page_icon="⚡", layout="wide")

# Your exact Sheet ID
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A' 

@st.cache_data(ttl=600)
def load_data(sheet_name):
    # This line fixes the space in the tab name!
    safe_sheet_name = urllib.parse.quote(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={safe_sheet_name}"
    return pd.read_csv(url)

# --- UI HEADER ---
st.title("⚡ Zynd Agent Builder Dashboard")
st.markdown("Internal tool for tracking, scoring, and routing high-intent developers.")

# Load the data (Without the hidden error block so we can see what happens)
df_reddit = load_data("Reddit Leads")
df_github = load_data("GitHub Leads")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Leads")
platform = st.sidebar.selectbox("Select Platform", ["GitHub (Builders)", "Reddit (Intent)"])
min_score = st.sidebar.slider("Minimum Lead Score", 1, 10, 7) 

# --- RENDER DATA ---
if platform == "Reddit (Intent)":
    st.subheader(f"Reddit Intelligence ({len(df_reddit)} Total Leads)")
    
    # Filter logic
    filtered_df = df_reddit[df_reddit['Lead Score (1-10)'] >= min_score]
    intent_filter = st.sidebar.multiselect("Intent Category", df_reddit['Intent Category'].unique())
    if intent_filter:
        filtered_df = filtered_df[filtered_df['Intent Category'].isin(intent_filter)]
        
    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("High-Intent Targets", len(filtered_df))
    col2.metric("Competitor Mentions", len(filtered_df[filtered_df['Intent Category'].str.contains('Competitor', na=False)]))
    col3.metric("Pain Points Found", len(filtered_df[filtered_df['Intent Category'].str.contains('Pain Point', na=False)]))

    # Display Table
    st.dataframe(filtered_df, use_container_width=True, height=600)

elif platform == "GitHub (Builders)":
    st.subheader(f"GitHub Builders ({len(df_github)} Total Leads)")
    
    # Filter logic
    filtered_df = df_github[df_github['Lead Score (1-10)'] >= min_score]
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Qualified Builders", len(filtered_df))
    col2.metric("Emails Unlocked", len(filtered_df[filtered_df['Email'].notna()]))
    col3.metric("X Profiles Found", len(filtered_df[filtered_df['Twitter/X'].notna()]))

    # Display Table
    st.dataframe(filtered_df, use_container_width=True, height=600)