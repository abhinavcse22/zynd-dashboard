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
    try:
        def get_url(name): return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
        gh = pd.read_csv(get_url("GitHub Leads"))
        rd = pd.read_csv(get_url("Reddit Leads"))
        tw = pd.read_csv(get_url("Twitter Leads"))
        star = pd.read_csv(get_url("github_stargazer_leads"))
        return gh, rd, tw, star
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

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
    m2.metric("Hot Stargazer Leads", len(df_star[df_star['lead_bucket'] == 'Hot lead']) if not df_star.empty else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty else 0)
    
    registered = len(df_star[df_star['agent_registered'] == 'Yes']) if not df_star.empty else 0
    m4.metric("Registered Zynd Agents", registered)

# ==========================================
# 💻 TAB: GITHUB BUILDERS
# ==========================================
elif menu == "💻 GitHub Builders":
    gh_tab1, gh_tab2 = st.tabs(["🔭 Stargazer Radar (Intent Leads)", "🗄️ Standard Builder DB"])
    
    with gh_tab1:
        st.header("GitHub Stargazer Intelligence")
        if df_star.empty:
            st.warning("No stargazer leads found. Run the radar in the Control Room.")
        else:
            # Filters
            with st.expander("🔍 Filter Intelligence"):
                col1, col2, col3, col4 = st.columns(4)
                f_repo = col1.multiselect("Source Repo", df_star['source_repo'].dropna().unique())
                f_bucket = col2.multiselect("Lead Bucket", df_star['lead_bucket'].dropna().unique())
                f_has_repo = col3.selectbox("Has AI Agent Repo?", ["All", "Yes", "No"])
                f_outreach = col4.selectbox("Outreach Status", ["All"] + list(df_star['outreach_status'].dropna().unique()))
            
            # Apply Filters
            filtered_star = df_star.copy()
            if f_repo: filtered_star = filtered_star[filtered_star['source_repo'].isin(f_repo)]
            if f_bucket: filtered_star = filtered_star[filtered_star['lead_bucket'].isin(f_bucket)]
            if f_has_repo != "All": filtered_star = filtered_star[filtered_star['has_ai_agent_repo'] == f_has_repo]
            if f_outreach != "All": filtered_star = filtered_star[filtered_star['outreach_status'] == f_outreach]

            # Charts
            st.subheader("Radar Analytics")
            c1, c2 = st.columns(2)
            
            # 1. Leads by Source Repo
            repo_counts = df_star['source_repo'].value_counts().reset_index()
            repo_counts.columns = ['Repo', 'Count']
            fig1 = px.bar(repo_counts, x='Repo', y='Count', title="Leads by Source Repo", template="plotly_dark")
            c1.plotly_chart(fig1, use_container_width=True)
            
            # 2. Hot/Warm Distribution
            bucket_counts = df_star['lead_bucket'].value_counts().reset_index()
            bucket_counts.columns = ['Bucket', 'Count']
            fig2 = px.pie(bucket_counts, names='Bucket', values='Count', title="Lead Quality Distribution", template="plotly_dark")
            c2.plotly_chart(fig2, use_container_width=True)

            c3, c4 = st.columns(2)
            # 3. Top Keywords
            all_kws = df_star['matched_keywords'].dropna().str.cat(sep=', ').split(', ')
            kw_df = pd.Series([k for k in all_kws if k]).value_counts().head(10).reset_index()
            kw_df.columns = ['Keyword', 'Count']
            fig3 = px.bar(kw_df, x='Keyword', y='Count', title="Top Matched Keywords", template="plotly_dark")
            c3.plotly_chart(fig3, use_container_width=True)

            # 4. Conversion Funnel
            funnel_data = dict(
                number=[len(df_star), len(df_star[df_star['outreach_status'] == 'Contacted']), len(df_star[df_star['reply_status'] == 'Replied']), len(df_star[df_star['agent_registered'] == 'Yes'])],
                stage=["Total Leads", "Contacted", "Replied", "Registered Agents"])
            fig4 = px.funnel(funnel_data, x='number', y='stage', title="Stargazer Conversion Funnel", template="plotly_dark")
            c4.plotly_chart(fig4, use_container_width=True)

            st.divider()
            st.subheader("Target List")
            
            # Table View
            display_cols = ['github_profile_url', 'source_repo', 'matched_keywords', 'lead_score', 'suggested_outreach_action', 'outreach_status']
            st.dataframe(filtered_star.sort_values(by='lead_score', ascending=False)[display_cols], use_container_width=True)
            
            # Export
            csv = filtered_star.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Export Filtered Leads for Outreach Queue", data=csv, file_name='zynd_stargazer_leads.csv', mime='text/csv')

    with gh_tab2:
        st.header("Standard Technical Discovery")
        st.dataframe(df_gh, use_container_width=True)

# ==========================================
# 💬 TAB: REDDIT & 🐦 TWITTER (Omitted for brevity, keep your existing code here)
# ==========================================

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
            with st.spinner("Scanning GitHub stargazers... This may take a few minutes depending on API limits."):
                try:
                    count = zynd_stargazer_engine.run_stargazer_radar(repos_list, max_repos, max_stars, min_score, dry_run)
                    if dry_run:
                        st.success(f"Dry run complete. Found {count} qualified leads.")
                    else:
                        st.success(f"Radar complete! Database updated with {count} total qualified leads.")
                        st.cache_data.clear()
                except Exception as e:
                    st.error(f"Engine Error: {e}")

    # (Keep your existing GitHub, Reddit, Twitter, and Duplicates engines below)
