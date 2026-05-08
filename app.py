import streamlit as st
import pandas as pd
import urllib.parse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# --- IMPORT ENGINES ---
import zynd_leads
import zynd_master_scraper
import zynd_daily_engine
import zynd_twitter_engine
import zynd_stargazer_engine
import zynd_twitter_sniper

# --- SETTINGS & THEME ---
st.set_page_config(page_title="Zynd | GTM Command Center", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 10px; }
    h1, h2, h3 { color: #58a6ff !important; }
    </style>
    """, unsafe_allow_html=True)

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

@st.cache_data(ttl=300)
def load_full_database():
    """Loads each tab independently so one empty sheet doesn't crash the others."""
    def get_url(name): 
        return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
    
    # Load GitHub
    try: gh = pd.read_csv(get_url("GitHub Leads"))
    except: gh = pd.DataFrame()
    
    # Load Reddit
    try: rd = pd.read_csv(get_url("Reddit Leads"))
    except: rd = pd.DataFrame()
    
    # Load Twitter
    try: tw = pd.read_csv(get_url("Twitter Leads"))
    except: tw = pd.DataFrame()
    
    # Load Stargazer
    try: star = pd.read_csv(get_url("github_stargazer_leads"))
    except: star = pd.DataFrame()
    
    return gh, rd, tw, star

def clean_database():
    """Finds and removes duplicate leads across all tabs in Google Sheets."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    total_removed = 0
    
    try:
        gh_sheet = client.open_by_key(SHEET_ID).worksheet("GitHub Leads")
        gh_data = gh_sheet.get_all_records()
        if gh_data:
            df = pd.DataFrame(gh_data)
            before = len(df)
            df.drop_duplicates(subset=['Project URL'], keep='first', inplace=True)
            after = len(df)
            if before > after:
                gh_sheet.clear()
                gh_sheet.update([df.columns.values.tolist()] + df.values.tolist())
                total_removed += (before - after)
    except: pass

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
df_gh, df_rd, df_tw, df_star = load_full_database()

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
    m1.metric("Total Lead Pool", len(df_gh) + len(df_rd) + len(df_tw) + len(df_star))
    m2.metric("Hot Stargazer Leads", len(df_star[df_star['lead_bucket'] == 'Hot lead']) if not df_star.empty and 'lead_bucket' in df_star.columns else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty and 'Lead Score (1-10)' in df_rd.columns else 0)
    m4.metric("Registered Zynd Agents", len(df_star[df_star['agent_registered'] == 'Yes']) if not df_star.empty and 'agent_registered' in df_star.columns else 0)

    st.divider()
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Recent High-Intent Activity")
        if not df_rd.empty:
            st.dataframe(df_rd.head(25), use_container_width=True)
        else:
            st.write("No recent activity found.")

    with col_right:
        st.subheader("Platform Distribution")
        chart_data = pd.DataFrame({'Source': ['GitHub', 'Reddit', 'Twitter'], 'Count': [len(df_gh), len(df_rd), len(df_tw)]})
        st.bar_chart(chart_data.set_index('Source'))

# ==========================================
# 💻 TAB: GITHUB BUILDERS
# ==========================================
elif menu == "💻 GitHub Builders":
    gh_tab1, gh_tab2 = st.tabs(["🔭 Stargazer Radar (Intent Leads)", "🗄️ Standard Builder DB"])
    
    with gh_tab1:
        st.header("GitHub Stargazer Intelligence")
        if df_star.empty or 'lead_score' not in df_star.columns:
            st.warning("No stargazer leads found. Run the radar in the Control Room.")
        else:
            with st.expander("🔍 Filter Intelligence"):
                col1, col2, col3, col4 = st.columns(4)
                f_repo = col1.multiselect("Source Repo", df_star['source_repo'].dropna().unique())
                f_bucket = col2.multiselect("Lead Bucket", df_star['lead_bucket'].dropna().unique())
                f_has_repo = col3.selectbox("Has AI Agent Repo?", ["All", "Yes", "No"])
                f_outreach = col4.selectbox("Outreach Status", ["All"] + list(df_star['outreach_status'].dropna().unique()))
            
            filtered_star = df_star.copy()
            if f_repo: filtered_star = filtered_star[filtered_star['source_repo'].isin(f_repo)]
            if f_bucket: filtered_star = filtered_star[filtered_star['lead_bucket'].isin(f_bucket)]
            if f_has_repo != "All": filtered_star = filtered_star[filtered_star['has_ai_agent_repo'] == f_has_repo]
            if f_outreach != "All": filtered_star = filtered_star[filtered_star['outreach_status'] == f_outreach]

            st.subheader("Radar Analytics")
            c1, c2 = st.columns(2)
            repo_counts = df_star['source_repo'].value_counts().reset_index()
            repo_counts.columns = ['Repo', 'Count']
            if not repo_counts.empty:
                c1.plotly_chart(px.bar(repo_counts, x='Repo', y='Count', title="Leads by Source Repo", template="plotly_dark"), use_container_width=True)
            
            bucket_counts = df_star['lead_bucket'].value_counts().reset_index()
            bucket_counts.columns = ['Bucket', 'Count']
            if not bucket_counts.empty:
                c2.plotly_chart(px.pie(bucket_counts, names='Bucket', values='Count', title="Lead Quality Distribution", template="plotly_dark"), use_container_width=True)

            st.divider()
            st.subheader("Target List")
            display_cols = ['github_profile_url', 'source_repo', 'matched_keywords', 'lead_score', 'suggested_outreach_action', 'outreach_status']
            existing_cols = [col for col in display_cols if col in filtered_star.columns]
            st.dataframe(filtered_star.sort_values(by='lead_score', ascending=False)[existing_cols] if 'lead_score' in filtered_star.columns else filtered_star, use_container_width=True)
            
            csv = filtered_star.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Export Filtered Leads", data=csv, file_name='zynd_stargazer_leads.csv', mime='text/csv')

    with gh_tab2:
        st.header("Standard Technical Discovery")
        q_col1, q_col2 = st.columns([3, 1])
        with q_col2:
            min_gh = st.slider("Min Lead Score", 1, 10, 7, key="gh_slider")
        
        if not df_gh.empty and 'Lead Score (1-10)' in df_gh.columns:
            filtered_gh = df_gh[df_gh['Lead Score (1-10)'] >= min_gh]
            st.metric("Total GitHub Leads (Filtered)", len(filtered_gh))
            st.dataframe(filtered_gh, use_container_width=True, height=600)
        else:
            st.dataframe(df_gh, use_container_width=True, height=600)

# ==========================================
# 💬 TAB: REDDIT INTENT
# ==========================================
elif menu == "💬 Reddit Intent":
    st.header("Social Intent & Pain Points")
    st.metric("Total Reddit Leads", len(df_rd))
    st.dataframe(df_rd, use_container_width=True, height=600)

# ==========================================
# 🐦 TAB: TWITTER SNIPER
# ==========================================
elif menu == "🐦 Twitter Sniper":
    st.header("Real-time Twitter Harvesting")
    st.metric("Total Twitter Leads", len(df_tw))
    st.dataframe(df_tw, use_container_width=True, height=400)
    
    st.divider()
    st.subheader("Manual Pulse Check (Deep Search)")
    try:
        urls = zynd_twitter_sniper.get_sniper_urls()
        c1, c2, c3 = st.columns(3)
        c1.link_button("Build in Public Radar 🚀", urls["build_in_public"])
        c2.link_button("Pain Point Radar 🔥", urls["pain_points"])
        c3.link_button("Competitor Radar ⚔️", urls["competitor_poaching"])
    except Exception as e:
        st.error("Could not load Twitter sniper URLs. Make sure zynd_twitter_sniper.py is in your repo.")

# ==========================================
# ⚙️ TAB: CONTROL ROOM
# ==========================================
elif menu == "⚙️ Control Room":
    st.header("Engine Control Room")
    
    st.markdown("### 🔭 GitHub Stargazer Radar")
    with st.container(border=True):
        st.write("Scan competitor repositories to extract high-intent AI agent builders.")
        target_repos_input = st.text_area("Target Repositories (owner/repo, one per line)", value="langchain-ai/langchain\ncrewaiinc/crewai\nmicrosoft/autogen")
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        max_repos = col_s1.number_input("Max Repos to Process", 1, 50, 5)
        max_stars = col_s2.number_input("Max Stargazers per Repo", 10, 1000, 100, step=10)
        min_score = col_s3.number_input("Minimum Score to Save", 0, 10, 3)
        dry_run = col_s4.toggle("Dry Run (Don't save to DB)", value=False)
        
        if st.button("🚀 Run Stargazer Radar", type="primary", use_container_width=True):
            repos_list = [r.strip() for r in target_repos_input.split('\n') if r.strip()]
            with st.spinner("Scanning GitHub stargazers..."):
                try:
                    count = zynd_stargazer_engine.run_stargazer_radar(repos_list, max_repos, max_stars, min_score, dry_run)
                    if dry_run:
                        st.success(f"Dry run complete. Found {count} qualified leads.")
                    else:
                        st.success(f"Radar complete! Database updated with {count} total qualified leads.")
                        st.cache_data.clear()
                except Exception as e:
                    st.error(f"Engine Error: {e}")

    st.divider()
    st.markdown("### ⚙️ Standard Harvesters")
    
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        st.subheader("🚀 GitHub Harvester")
        if st.button("Start GitHub Engine"):
            with st.spinner("Executing..."):
                try:
                    zynd_leads.harvest_leads()
                    st.success("GitHub Updated!")
                    st.cache_data.clear()
                except Exception as e: st.error(str(e))

    with row1_col2:
        st.subheader("⚡ Master Enricher")
        if st.button("Engage Turbo Scraper"):
            with st.spinner("Executing..."):
                try:
                    zynd_master_scraper.enrich_database()
                    st.success("Enrichment Complete!")
                    st.cache_data.clear()
                except Exception as e: st.error(str(e))

    with row2_col1:
        st.subheader("📡 Reddit Radar")
        if st.button("Start Reddit Engine"):
            with st.spinner("Executing..."):
                try:
                    zynd_daily_engine.run_reddit_scraper()
                    st.success("Reddit Updated!")
                    st.cache_data.clear()
                except Exception as e: st.error(str(e))

    with row2_col2:
        st.subheader("🐦 Twitter Autopilot")
        if st.button("Start Twitter Engine"):
            with st.spinner("Executing..."):
                try:
                    zynd_twitter_engine.run_twitter_scraper()
                    st.success("Twitter Updated!")
                    st.cache_data.clear()
                except Exception as e: st.error(str(e))

    st.divider()
    
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
