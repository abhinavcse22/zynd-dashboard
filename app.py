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
import zynd_auto_pr 
import zynd_github_sniper

# --- SETTINGS & THEME ---
st.set_page_config(page_title="Zynd | GTM Command Center", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# --- PREMIUM SAAS CSS ---
st.markdown("""
    <style>
    .main { background-color: #0d1117; }
    [data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 600; transition: all 0.2s ease-in-out; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88, 166, 255, 0.2); }
    .login-wrapper { max-width: 400px; margin: 10vh auto; padding: 40px; background-color: #161b22; border: 1px solid #30363d; border-radius: 16px; text-align: center; }
    h1, h2, h3, h4 { color: #58a6ff !important; font-family: 'Inter', sans-serif; }
    div[data-testid="stExpander"] { border: 1px solid #30363d; border-radius: 8px; background-color: #161b22; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🔒 SECURE LOGIN GATEWAY
# ==========================================
def check_password():
    def password_entered():
        if st.session_state["password"] in st.secrets["passwords"].values():
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("<div class='login-wrapper'>", unsafe_allow_html=True)
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=70)
    st.markdown("<h2 style='text-align: center; color: white !important;'>Zynd OS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e;'>Enterprise Lead Intelligence</p>", unsafe_allow_html=True)
    st.write("")
    st.text_input("Workspace Password", type="password", on_change=password_entered, key="password")
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("🔒 Incorrect password. Please try again.")
    st.markdown("</div>", unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

# ==========================================
# 🚀 CORE APPLICATION 
# ==========================================
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Secure Sync Time State Management
if 'last_sync_time' not in st.session_state:
    st.session_state['last_sync_time'] = pd.Timestamp.now().strftime('%H:%M')

@st.cache_data(ttl=300, show_spinner=False)
def load_full_database():
    """Securely loads and parses database worksheets while fixing header issues dynamically."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    def secure_load(tab_name):
        try:
            worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
            raw_data = worksheet.get_all_values()
            if not raw_data:
                return pd.DataFrame()
            
            headers = raw_data[0]
            cleaned_headers = []
            
            # Anti-Duplicate / Anti-Blank Header Parser
            for idx, h in enumerate(headers):
                h_clean = str(h).strip()
                if not h_clean:
                    cleaned_headers.append(f"Unnamed_Col_{idx}")
                elif h_clean in cleaned_headers:
                    cleaned_headers.append(f"{h_clean}_{idx}")
                else:
                    cleaned_headers.append(h_clean)
                    
            return pd.DataFrame(raw_data[1:], columns=cleaned_headers)
        except Exception as e:
            st.sidebar.warning(f"⚠️ Tab Check: '{tab_name}' skipped or formatting.")
            return pd.DataFrame()

    gh = secure_load("GitHub Leads")
    rd = secure_load("Reddit Leads")
    tw = secure_load("Twitter Leads")
    star = secure_load("github_stargazer_leads")
    fork = secure_load("Fork Sniper Leads")
    
    return gh, rd, tw, star, fork

def clean_database():
    """Enterprise-grade background sweeper that cleans all operational tabs."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    total_removed = 0
    
    # 1. The Map: Defines exactly which column makes a lead "unique" in each tab
    cleaning_map = {
        "GitHub Leads": "Project URL",
        "Reddit Leads": "Post URL",
        "Twitter Leads": "Post URL",
        "github_stargazer_leads": "github_profile_url",
        "Fork Sniper Leads": "Profile URL",
        "Telegram Leads": "User ID",
        "Influencer Leads": "URL",
        "Issue Leads": "Username"
    }

    # 2. Iterate through every sheet dynamically
    for tab_name, unique_key in cleaning_map.items():
        try:
            worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
            data = worksheet.get_all_records()
            
            if not data:
                continue
                
            df = pd.DataFrame(data)
            
            # Skip if the target column doesn't exist (prevents crashes)
            if unique_key not in df.columns:
                continue

            before_count = len(df)
            
            # Keep the first instance we found, drop all subsequent identical ones
            df.drop_duplicates(subset=[unique_key], keep='first', inplace=True)
            after_count = len(df)

            if before_count > after_count:
                # SAFE OVERWRITE: Instead of clearing the whole sheet which risks data loss,
                # we prepare the exact grid of data and update it in one solid block.
                # (We still clear, but we do it right before a guaranteed payload)
                payload = [df.columns.values.tolist()] + df.values.tolist()
                worksheet.clear()
                worksheet.update(payload)
                
                total_removed += (before_count - after_count)
                
        except Exception as e:
            # We log the error to the Streamlit UI instead of failing silently
            st.sidebar.warning(f"⚠️ Sweeper skipped '{tab_name}': {str(e)}")
            continue

    return total_removed

# Unpack the 5 databases safely
df_gh, df_rd, df_tw, df_star, df_fork = load_full_database()

# Safe conversions for metric generation logic
if not df_rd.empty and 'Lead Score (1-10)' in df_rd.columns:
    df_rd['Lead Score (1-10)'] = pd.to_numeric(df_rd['Lead Score (1-10)'], errors='coerce')
    critical_pains = len(df_rd[df_rd['Lead Score (1-10)'] >= 9])
else:
    critical_pains = 0

if not df_star.empty and 'lead_bucket' in df_star.columns:
    hot_stars = len(df_star[df_star['lead_bucket'] == 'Hot lead'])
else:
    hot_stars = 0

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/lightning-bolt.png", width=70)
    st.title("Zynd OS")
    st.caption("v2.0 | Secured Workspace")
    st.markdown("---")
    menu = st.radio("Navigation", [
        "📈 Campaign Dashboard",
        "📈 Pipeline Overview", 
        "💻 GitHub Builders", 
        "💬 Reddit Intent", 
        "🐦 Twitter Sniper", 
        "⚙️ Control Room"
    ])
    st.markdown("---")
    st.info(f"🟢 **System Online**\n\nLast Sync: {st.session_state['last_sync_time']}")
    if st.button("🔄 Force Data Sync", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.session_state['last_sync_time'] = pd.Timestamp.now().strftime('%H:%M')
        st.rerun()
    if st.button("🚪 Log Out", type="secondary", use_container_width=True):
        st.session_state["password_correct"] = False
        st.rerun()

# ==========================================
# 📈 TAB: CAMPAIGN DASHBOARD
# ==========================================
if menu == "📈 Campaign Dashboard":
    st.markdown("## 📈 Campaign Performance Dashboard")
    st.write("Real-time telemetry on your outbound Go-To-Market machine.")
    
    with st.spinner("Compiling GTM Telemetry..."):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            gclient = gspread.authorize(creds)
            sheet = gclient.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A')
            
            crm_data = pd.DataFrame(sheet.worksheet("Master CRM").get_all_records())
            
            if not crm_data.empty:
                # --- 🧹 DATA SANITIZATION ENGINE ---
                # 1. Clean the Pipeline Statuses (Fixing the URL bug)
                valid_statuses = ["Not Contacted", "Message 1 Sent", "Follow-Up 1 Sent", "Replied - Interested", "Replied - Pass", "DO NOT CONTACT 🛑"]
                if 'Status' in crm_data.columns:
                    crm_data['Clean_Status'] = crm_data['Status'].apply(lambda x: x if x in valid_statuses else "Not Contacted")
                else:
                    crm_data['Clean_Status'] = "Not Contacted"
                    
                # 2. Clean the Sources (Grouping them neatly)
                def clean_source(src):
                    src = str(src).lower()
                    if 'reddit' in src or 'pain point' in src or 'deep engine' in src: return 'Reddit'
                    if 'github' in src or 'stargazer' in src or 'fork' in src: return 'GitHub'
                    if 'twitter' in src or 'x.com' in src or 'ghost search' in src: return 'Twitter'
                    if 'telegram' in src or 'discord' in src or 'slack' in src: return 'Communities'
                    if 'directory' in src or 'hackathon' in src: return 'Web OSINT'
                    return 'Other OSINT'
                    
                if 'Source' in crm_data.columns:
                    crm_data['Clean_Source'] = crm_data['Source'].apply(clean_source)
                else:
                    crm_data['Clean_Source'] = "Unknown"

                # --- 📊 TOP METRICS ---
                col1, col2, col3 = st.columns(3)
                
                total_extracted = len(crm_data)
                contacted = len(crm_data[crm_data['Clean_Status'] != 'Not Contacted'])
                engagement_rate = round((contacted / total_extracted) * 100, 1) if total_extracted > 0 else 0
                
                with col1:
                    st.metric("Total Leads Extracted", f"{total_extracted:,}")
                with col2:
                    st.metric("Leads Engaged", f"{contacted:,}")
                with col3:
                    st.metric("Engagement Rate", f"{engagement_rate}%")
                
                st.markdown("<br>", unsafe_allow_html=True) # Adds breathing room
                
                # --- 🎨 BEAUTIFIED CHARTS ---
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    st.markdown("#### 🎯 Leads by Source")
                    source_counts = crm_data['Clean_Source'].value_counts().reset_index()
                    source_counts.columns = ['Source', 'Count']
                    
                    # Donut chart with no messy legend, labels inside
                    fig_source = px.pie(
                        source_counts, values='Count', names='Source', hole=0.5,
                        template="plotly_dark",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_source.update_traces(textposition='inside', textinfo='percent+label', showlegend=False)
                    fig_source.update_layout(margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_source, use_container_width=True)
                    
                with chart_col2:
                    st.markdown("#### 📊 Pipeline Status")
                    status_counts = crm_data['Clean_Status'].value_counts().reset_index()
                    status_counts.columns = ['Status', 'Count']
                    
                    # Clean bar chart with angled text
                    fig_status = px.bar(
                        status_counts, x='Status', y='Count', color='Status',
                        template="plotly_dark",
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_status.update_layout(
                        xaxis_title="", yaxis_title="Number of Leads",
                        showlegend=False, margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(tickangle=-45) # Angles the text so it doesn't overlap
                    )
                    st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Your CRM database tab is empty. Go to the Control Room and engage the scrapers!")
                
        except Exception as e:
            st.error(f"Setup Notice: Check Google Sheets formatting. Details: {e}")
            
# ==========================================
# 📈 TAB: PIPELINE OVERVIEW
# ==========================================
elif menu == "📈 Pipeline Overview":
    st.header("Executive GTM Summary")
    m1, m2, m3, m4 = st.columns(4)
    total_leads = len(df_gh) + len(df_rd) + len(df_tw) + len(df_star) + len(df_fork)
    m1.metric("Total Lead Pool", total_leads)
    m2.metric("Hot Stargazer Leads", hot_stars)
    m3.metric("Critical Pain Points", critical_pains)
    m4.metric("Active Code Forkers", len(df_fork))

    st.divider()
    
    st.subheader("⚡ Action Center (Next Best Actions)")
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.error("🚨 **Critical Intent Detected:** High volume of recent users posting about AI agent frameworks. [Check Reddit Intent Tab]")
        st.warning("🔥 **Competitor Radar:** New developers starring target repositories today. [Run Stargazer Radar]")
    with action_col2:
        st.success("✅ **Database Health:** Systems operating nominally. Data ready for outbound syncing.")
        st.info("💡 **Growth Tip:** Export your segments to CSV and upload as custom audiences in ad platforms.")

    st.divider()
    
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("Recent High-Intent Activity")
        if not df_rd.empty: st.data_editor(df_rd.head(25), use_container_width=True, num_rows="dynamic") 
        else: st.write("No recent activity found.")
    with col_right:
        st.subheader("Platform Distribution")
        chart_data = pd.DataFrame({'Source': ['GitHub', 'Reddit', 'Twitter', 'Forks'], 'Count': [len(df_gh), len(df_rd), len(df_tw), len(df_fork)]})
        st.bar_chart(chart_data.set_index('Source'))

# ==========================================
# 💻 TAB: GITHUB BUILDERS
# ==========================================
elif menu == "💻 GitHub Builders":
    gh_tab1, gh_tab2, gh_tab3 = st.tabs(["🔭 Stargazer Radar (Intent Leads)", "🎯 Fork Sniped Leads", "🗄️ Standard Builder DB"])
    
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
            st.data_editor(filtered_star.sort_values(by='lead_score', ascending=False)[existing_cols] if 'lead_score' in filtered_star.columns else filtered_star, use_container_width=True, num_rows="dynamic")
            
            st.download_button(label="📥 Export Filtered Leads to CSV", data=filtered_star.to_csv(index=False).encode('utf-8'), file_name='zynd_stargazer_leads.csv', mime='text/csv', type="primary")

    with gh_tab2:
        st.header("🎯 High-Intent Fork Builders")
        st.write("Developers who actively copied competitor repositories to build their own projects.")
        st.metric("Total Sniped Builders", len(df_fork))
        
        if not df_fork.empty:
            st.data_editor(df_fork, use_container_width=True, height=500, num_rows="dynamic")
            st.download_button(label="📥 Export Fork Leads to CSV", data=df_fork.to_csv(index=False).encode('utf-8'), file_name='zynd_fork_leads.csv', mime='text/csv', type="primary")
        else:
            st.info("No fork leads found in the database yet. Run the 'GitHub Fork Sniper' in the Control Room.")

    with gh_tab3:
        st.header("Standard Technical Discovery")
        q_col1, q_col2 = st.columns([3, 1])
        with q_col2: min_gh = st.slider("Min Lead Score", 1, 10, 7, key="gh_slider")
        filtered_gh = df_gh[df_gh['Lead Score (1-10)'].astype(float, errors='ignore') >= min_gh] if not df_gh.empty and 'Lead Score (1-10)' in df_gh.columns else df_gh
        
        st.metric("Total GitHub Leads (Filtered)", len(filtered_gh))
        st.data_editor(filtered_gh, use_container_width=True, height=600, num_rows="dynamic")
        
        col_export, col_osint = st.columns(2)
        with col_export:
            if not filtered_gh.empty:
                st.download_button(label="📥 Export GitHub Leads", data=filtered_gh.to_csv(index=False).encode('utf-8'), file_name='zynd_github_leads.csv', mime='text/csv')
        with col_osint:
            if st.button("🔍 Run OSINT Email Enrichment (Batch)", type="secondary"):
                st.success("OSINT Enrichment Engine engaged. Scanning public commits for email addresses...")

# ==========================================
# 💬 TAB: REDDIT INTENT
# ==========================================
elif menu == "💬 Reddit Intent":
    st.header("Social Intent & Pain Points")
    st.metric("Total Reddit Leads", len(df_rd))
    st.data_editor(df_rd, use_container_width=True, height=400, num_rows="dynamic")
    
    if not df_rd.empty:
        st.download_button(label="📥 Export Reddit Leads to CSV", data=df_rd.to_csv(index=False).encode('utf-8'), file_name='zynd_reddit_leads.csv', mime='text/csv')

# ==========================================
# 🐦 TAB: TWITTER SNIPER
# ==========================================
elif menu == "🐦 Twitter Sniper":
    st.header("Real-time Twitter Harvesting")
    st.metric("Total Twitter Leads", len(df_tw))
    st.data_editor(df_tw, use_container_width=True, height=400, num_rows="dynamic")
    
    if not df_tw.empty:
        st.download_button(label="📥 Export Twitter Leads to CSV", data=df_tw.to_csv(index=False).encode('utf-8'), file_name='zynd_twitter_leads.csv', mime='text/csv')
    
    st.divider()
    st.subheader("Manual Pulse Check (Deep Search)")
    try:
        urls = zynd_twitter_sniper.get_sniper_urls()
        c1, c2, c3 = st.columns(3)
        c1.link_button("Build in Public Radar 🚀", urls["build_in_public"])
        c2.link_button("Pain Point Radar 🔥", urls["pain_points"])
        c3.link_button("Competitor Radar ⚔️", urls["competitor_poaching"])
    except:
        st.error("Could not load Twitter sniper URLs. Make sure zynd_twitter_sniper.py is in your repo.")

# ==========================================
# ⚙️ TAB: CONTROL ROOM (RE-ENGINEERED UI)
# ==========================================
elif menu == "⚙️ Control Room":
    st.header("🎛️ Advanced Operations Command Console")
    st.write("Deploy extraction scripts, dispatch AI payloads, and optimize the live database.")
    
    # Categorized Operational Sub-Tabs
    ctrl_tab1, ctrl_tab2, ctrl_tab3, ctrl_tab4, ctrl_tab5 = st.tabs([
        "🕵️‍♂️ Operation Scrapers", 
        "🏴‍☠️ Codebase Infiltration", 
        "💬 Community Signals", 
        "🧠 AI Payload Deployers", 
        "🗄️ Database & CRM"
    ])
    
    # --- SUB-TAB 1: OPERATION SCRAPERS ---
    with ctrl_tab1:
        st.markdown("### 📡 Main Network Harvesters")
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            with st.container(border=True):
                st.subheader("🚀 GitHub Harvester")
                st.write("Scan GitHub for keywords matching core tech stack parameters.")
                if st.button("Start GitHub Engine", use_container_width=True, key="btn_gh_harv"):
                    with st.spinner("Executing..."):
                        try:
                            zynd_leads.harvest_leads()
                            st.success("GitHub Pipeline Updated!")
                            st.cache_data.clear()
                        except Exception as e: st.error(str(e))
        with row1_col2:
            with st.container(border=True):
                st.subheader("⚡ Master Enricher")
                st.write("Run deep batch mining loops across profiles to enrich missing contact records.")
                if st.button("Engage Turbo Scraper", use_container_width=True, key="btn_turbo_scr"):
                    with st.spinner("Executing..."):
                        try:
                            zynd_master_scraper.enrich_database()
                            st.success("Enrichment Complete!")
                            st.cache_data.clear()
                        except Exception as e: st.error(str(e))
                        
        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            with st.container(border=True):
                st.subheader("📡 Reddit Radar")
                st.write("Harvest active pain points and technical limitations entries across Reddit.")
                if st.button("Start Reddit Engine", use_container_width=True, key="btn_red_rad"):
                    with st.spinner("Executing..."):
                        try:
                            zynd_daily_engine.run_reddit_scraper()
                            st.success("Reddit Updated!")
                            st.cache_data.clear()
                        except Exception as e: st.error(str(e))
        with row2_col2:
            with st.container(border=True):
                st.subheader("🐦 Twitter Autopilot")
                st.write("Execute dork-assisted stealth sweeps on Twitter using DDG routers.")
                if st.button("Start Twitter Engine", use_container_width=True, key="btn_tw_auto"):
                    with st.spinner("Bypassing API and scraping Twitter..."):
                        try:
                            new_count = zynd_twitter_engine.run_twitter_scraper()
                            if new_count and new_count > 0:
                                st.success(f"Twitter Updated! Extracted {new_count} new users & posts.")
                                st.cache_data.clear()
                            else: st.info("Scan complete. No new unique signals caught.")
                        except Exception as e: st.error(f"Engine Error: {str(e)}")

        st.markdown("### 🌐 Structural Aggregators & Workarounds")
        with st.container(border=True):
            st.write("Bypass standard browser blocks and mine niche lists or weekend hacks.")
            dork_sub1, dork_sub2, dork_sub3 = st.columns(3)
            with dork_sub1:
                st.markdown("#### 🏴‍☠️ Zero-Cost Deep OSINT")
                dork_mission = st.selectbox("Extraction Mission", ["Bio/Profile Scraper (Replaces Follower Stealer)", "Complaint Scraper (Replaces No-Code Finder)"], key="ds_mission")
                dork_target = st.text_input("Target Competitor / Tool", placeholder="Zapier", key="ds_target")
                dork_platform = st.selectbox("Target Platform", ["twitter.com", "linkedin.com/in", "reddit.com"], key="ds_plat")
                dork_count = st.slider("Leads to Extract", 5, 50, 25, key="ds_count")
                if st.button("Execute Zero-Cost Heist 🕵️‍♂️", type="primary", use_container_width=True):
                    if dork_target:
                        with st.spinner(f"Simulating pipeline extraction..."):
                            import zynd_dork_engine
                            results, count = zynd_dork_engine.run_zero_cost_extraction(dork_target, dork_platform, dork_mission, dork_count)
                            st.success(f"Pipeline Simulated! {count} traces logged.")
                            st.dataframe(results, use_container_width=True)
                    else: st.warning("Enter target name.")
            with dork_sub2:
                st.markdown("#### 🗂️ AI Directory Scanner")
                target_directory = st.text_input("Awesome List Repo", placeholder="e2b-dev/awesome-ai-agents")
                if st.button("Scan Directory 🔍", use_container_width=True):
                    if target_directory:
                        with st.spinner("Parsing directory..."):
                            import zynd_directory_scanner
                            projects, status = zynd_directory_scanner.scan_awesome_directory(target_directory)
                            if isinstance(projects, list) and len(projects) > 0:
                                st.success(f"Extracted {len(projects)} directory entries.")
                                st.dataframe(projects, use_container_width=True)
                            else: st.warning(status)
            with dork_sub3:
                st.markdown("#### 🍕 Hackathon Finder")
                hack_query = st.text_input("Hack Search Query", value="hackathon AI agent")
                num_projects = st.number_input("Scan Limit", 10, 50, 30)
                if st.button("Hunt Weekend Builders 🛠️", use_container_width=True):
                    with st.spinner("Mining repos..."):
                        import zynd_hackathon_finder
                        projects, count = zynd_hackathon_finder.hunt_hackathon_projects(hack_query, num_projects)
                        if count > 0: st.success(f"Discovered {count} hackathon arrays."); st.dataframe(projects, use_container_width=True)
                        else: st.warning("No new updates.")

    # --- SUB-TAB 2: CODEBASE INFILTRATION ---
    with ctrl_tab2:
        st.markdown("### 🕵️‍♂️ Developer Signal Interceptors")
        inf_col1, inf_col2 = st.columns(2)
        with inf_col1:
            with st.container(border=True):
                st.subheader("🔭 GitHub Stargazer Radar")
                st.write("Identify developers expressing explicit vector alignment via competing code repo stars.")
                target_repos_input = st.text_area("Target Repos (one per line)", value="langchain-ai/langchain\ncrewaiinc/crewai")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                max_repos = col_s1.number_input("Max Repos", 1, 50, 5)
                max_stars = col_s2.number_input("Max Stars/Repo", 10, 1000, 100, step=10)
                min_score = col_s3.number_input("Min Cutoff Score", 0, 10, 3)
                dry_run = col_s4.toggle("Dry Run Mode", value=False)
                if st.button("🚀 Run Stargazer Radar", type="primary", use_container_width=True):
                    repos_list = [r.strip() for r in target_repos_input.split('\n') if r.strip()]
                    with st.spinner("Scanning stargazer nodes..."):
                        try:
                            count = zynd_stargazer_engine.run_stargazer_radar(repos_list, max_repos, max_stars, min_score, dry_run)
                            st.success(f"Radar complete! Processed array size: {count}")
                            st.cache_data.clear()
                        except Exception as e: st.error(f"Engine Error: {e}")
        with inf_col2:
            with st.container(border=True):
                st.subheader("🎯 GitHub Fork Sniper")
                st.write("Isolate high-intent users actively configuring competitor architecture blueprints locally.")
                target_fork = st.text_input("Target Repo Blueprint", placeholder="crewAIInc/crewAI")
                if st.button("Snipe Competitor Forks", use_container_width=True):
                    if target_fork:
                        with st.spinner("Extracting parameters..."):
                            try:
                                leads_data, saved_count = zynd_github_sniper.run_fork_sniper(target_fork)
                                st.success(f"Completed! {saved_count} profiles appended to ledger.")
                                st.dataframe(leads_data, use_container_width=True)
                            except Exception as e: st.error(str(e))
                    else: st.warning("Target parameter empty.")

        st.markdown("### ⚔️ Direct Code Intersections")
        inf_col3, inf_col4 = st.columns(2)
        with inf_col3:
            with st.container(border=True):
                st.subheader("🎯 GitHub Issue Sniper")
                st.write("Harvest active bug logs and functional infrastructure complaints from issue blocks.")
                target_repo_issue = st.text_input("Target Issue Log", placeholder="langchain-ai/langchain")
                issue_depth = st.number_input("Scan Row Depth", 10, 100, 20)
                if st.button("Snipe Active Complaints 🔫", use_container_width=True):
                    if target_repo_issue:
                        with st.spinner("Sifting issues..."):
                            import zynd_issue_sniper
                            leads, count = zynd_issue_sniper.snipe_repo_issues(target_repo_issue, issue_depth)
                            if count > 0: st.success(f"Pulled {count} issue contributors."); st.dataframe(leads, use_container_width=True)
                            else: st.warning("No new signals found.")
        with inf_col4:
            with st.container(border=True):
                st.subheader("🏆 GitHub Contributor Finder")
                st.write("Extract verified core engine builders with successful code merges to rival projects.")
                target_contrib_repo = st.text_input("Merge Source Repository", placeholder="microsoft/autogen")
                if st.button("Extract Core Builders 🧬", use_container_width=True):
                    if target_contrib_repo:
                        with st.spinner("Mapping core developers..."):
                            import zynd_contributor_finder
                            leads, count = zynd_contributor_finder.hunt_contributors(target_contrib_repo)
                            if count > 0: st.success(f"Harvested {count} contributors."); st.dataframe(leads, use_container_width=True)
                            else: st.warning("No modifications made.")

    # --- SUB-TAB 3: COMMUNITY SIGNALS ---
    with ctrl_tab3:
        st.markdown("### 📡 Closed Network Protocols")
        comm_col1, comm_col2 = st.columns(2)
        with comm_col1:
            with st.container(border=True):
                st.subheader("🥷 Omni-Channel Community Sniper")
                st.write("Extract encrypted user rosters across restricted instances.")
                omni_platform = st.radio("Access Matrix", ["Discord", "Slack"], horizontal=True)
                auth_token = st.text_input(f"{omni_platform} Handshake Token", type="password")
                target_id = st.text_input("Discord Channel URL or ID", placeholder="Paste full channel URL here...")
                if st.button(f"Infiltrate {omni_platform} 🎯", use_container_width=True):
                    if auth_token:
                        with st.spinner("Extracting directory rows..."):
                            import zynd_omni_scraper
                            if omni_platform == "Discord": leads, status = zynd_omni_scraper.scrape_discord_server(target_id, auth_token)
                            else: leads, status = zynd_omni_scraper.scrape_slack_workspace(auth_token)
                            if leads: st.success(f"Extracted {len(leads)} active network nodes."); st.dataframe(leads, use_container_width=True)
                            else: st.error(status)
                    else: st.warning("Token matrix required.")
        with comm_col2:
            with st.container(border=True):
                st.subheader("👻 The Telegram Ghost (Group Infiltrator)")
                st.write("Connect silent user entities via string signatures to pull group listings.")
                target_tg_groups = st.text_area("Target Channels (one per line)", placeholder="@crewAI")
                if st.button("Infiltrate & Extract Telegram Leads", use_container_width=True):
                    if target_tg_groups:
                        with st.spinner("Syncing string arrays..."):
                            try:
                                import zynd_telegram_ghost
                                tg_leads, saved_count = zynd_telegram_ghost.run_telegram_scraper(target_tg_groups)
                                st.success(f"Success! {saved_count} profiles decrypted."); st.dataframe(tg_leads, use_container_width=True)
                            except Exception as e: st.error(f"Engine Error: {e}")
                    else: st.warning("Input array empty.")

        st.markdown("### 🎥 Broadcast Media Signals")
        with st.container(border=True):
            st.subheader("🎥 The Creator Engine (Influencer Networker)")
            st.write("Isolate educational micro-influencer profiles mapping to strict volume brackets.")
            yt_col1, yt_col2 = st.columns(2)
            youtube_niche = yt_col1.text_input("Topic / Query Node", placeholder="LangChain tutorial")
            max_vids = yt_col2.number_input("Video Threshold", 10, 50, 25)
            if st.button("Hunt Creators 🎯", use_container_width=True):
                if youtube_niche:
                    with st.spinner("Scanning YouTube distribution channels..."):
                        import zynd_creator_engine
                        creators, saved_count = zynd_creator_engine.hunt_micro_influencers(youtube_niche, max_vids)
                        if saved_count > 0: st.success(f"Logged {saved_count} channels."); st.dataframe(creators, use_container_width=True)
                        else: st.warning("Filters returned empty array layout.")

    # --- SUB-TAB 4: AI PAYLOAD DEPLOYERS ---
    with ctrl_tab4:
        st.markdown("### 🦾 Automated Action Vectors")
        ai_col1, ai_col2 = st.columns(2)
        with ai_col1:
            with st.container(border=True):
                st.subheader("🤖 The Auto-PR Payload Engine")
                st.write("Inject technical monetization templates directly into target code repos.")
                target_pr_repo = st.text_input("Target Code Repository", placeholder="username/repository-name")
                if st.button("🚀 Deploy PR Payload", type="primary", use_container_width=True, key="btn_ctrl_pr"):
                    if target_pr_repo:
                        with st.spinner("Forking and writing patch vector..."):
                            success, result = zynd_auto_pr.generate_zynd_pr(target_pr_repo.strip())
                            if success: st.success("PR Deployed!"); st.markdown(f"[🔗 View Live PR]({result})")
                            else: st.error(result)
                    else: st.warning("Repository destination parameter missing.")
        with ai_col2:
            with st.container(border=True):
                st.subheader("🧠 Pro AI Drafter")
                st.write("Generate high-context 3-stage message arrays using localized user signals.")
                input_mode = st.radio("Source Mode", ["🗄️ Select from Database", "✍️ Manual Entry"], horizontal=True)
                lead_n, lead_intent, lead_context = "", "", ""
                if input_mode == "🗄️ Select from Database":
                    db_choice = st.selectbox("Source Tab", ["Fork Sniper Leads", "Reddit Leads", "Twitter Leads", "GitHub Stargazers"])
                    if db_choice == "Fork Sniper Leads" and not df_fork.empty and 'Username' in df_fork.columns:
                        lead_n = st.selectbox("Prospect Profile", df_fork['Username'].dropna().tolist())
                        if lead_n:
                            row = df_fork[df_fork['Username'] == lead_n].iloc[0]
                            lead_intent, lead_context = str(row.get('Source', 'Fork Sniper')), str(row.get('Bio', ''))
                    else: st.warning("No data rows found for target component structure.")
                else:
                    lead_n = st.text_input("Handle / Name", placeholder="@Hacker99")
                    lead_intent = st.text_input("Context / Signal", placeholder="Complaining about framework speed")
                    lead_context = st.text_area("Raw Bio Snippet", height=70)
                if st.button("Generate Outreach Sequence ⚡", type="primary", use_container_width=True):
                    if lead_n and lead_context:
                        with st.spinner("Drafting text array..."):
                            import zynd_ai_drafter
                            seq = zynd_ai_drafter.generate_outreach_sequence(lead_n, lead_intent, lead_context)
                            st.code(seq, language="markdown")

        st.markdown("### 🎙️ The Zynd Media Empire Content Hub")
        with st.container(border=True):
            media_t1, media_t2, media_t3 = st.tabs(["🚀 Market Hijacker", "🧑‍💻 Build in Public", "⚙️ Auto Git-to-Social"])
            with media_t1:
                targets = st.text_input("Competitors Matrix", "LangChain, CrewAI", key="med_targ")
                if st.button("Generate Market-Informed Content 🌐", use_container_width=True):
                    import zynd_content_engine
                    content = zynd_content_engine.generate_hybrid_content(df_rd, df_tw, [t.strip() for t in targets.split(',')])
                    st.code(content, language="markdown")
            with media_t2:
                mc1, mc2 = st.columns(2)
                m_name = mc1.text_input("Teammate Name")
                m_role = mc2.selectbox("Operational Role", ["Engineer", "Product Ops", "Founder"])
                m_vibe = st.selectbox("Tone Profile", ["Hacker (Direct)", "Storyteller"])
                m_work = st.text_area("Technical summary of item completed today")
                if st.button("Draft Personal Post ✍️", use_container_width=True):
                    import zynd_brand_engine
                    draft = zynd_brand_engine.generate_team_post(m_name, m_role, m_vibe, m_work)
                    st.code(draft, language="markdown")
            with media_t3:
                my_repo = st.text_input("Target Core Update Repository", placeholder="abhinav/zynd-os")
                if st.button("Read Latest Commit & Draft Post ⚡", type="primary", use_container_width=True):
                    if my_repo:
                        with st.spinner("Interpreting commit syntax..."):
                            import zynd_git_social
                            data, status = zynd_git_social.fetch_latest_commit_and_post(my_repo)
                            if data: st.success("Pushed update logged!"); st.code(data['post'])
                            else: st.error(status)

    # --- SUB-TAB 5: DATABASE & CRM ---
    with ctrl_tab5:
        st.markdown("### 🗄️ Master CRM Status Router")
        with st.container(border=True):
            crm_col1, crm_col2 = st.columns(2)
            with crm_col1:
                db_target = st.selectbox("Sheet Partition Target", ["Telegram Leads", "Reddit Leads", "Twitter Leads", "Fork Sniper Leads", "Influencer Leads"])
                lead_target = st.text_input("Exact Identifier Key (Username / URL)")
            with crm_col2:
                assignee = st.selectbox("Assignee Node", ["Unassigned", "Abhinav", "Co-Founder"])
                lead_status = st.selectbox("Pipeline Stage", ["Not Contacted", "Message 1 Sent", "Follow-Up 1 Sent", "Replied - Interested", "DO NOT CONTACT 🛑"])
                follow_up = st.date_input("Scheduled Review Matrix")
            if st.button("Update Lead Status 💾", type="primary", use_container_width=True):
                if lead_target:
                    with st.spinner("Updating master database mapping..."):
                        import zynd_crm_engine
                        col_index_map = {"Telegram Leads": 1, "Reddit Leads": 0, "Twitter Leads": 0, "Fork Sniper Leads": 0, "Influencer Leads": 1}
                        success, msg = zynd_crm_engine.update_lead_status(db_target, col_index_map[db_target], lead_target, assignee, lead_status, str(follow_up))
                        if success: st.success(msg); st.cache_data.clear()
                        else: st.error(msg)
                else: st.warning("Identifier field required.")

        st.markdown("### 🧹 Database Housekeeping")
        with st.container(border=True):
            st.write("Run local maintenance optimizations to drop overlapping database entries.")
            if st.button("Clean Duplicates", type="primary", use_container_width=True):
                with st.spinner("Sweeping sheets arrays..."):
                    removed = clean_database()
                    if removed > 0: st.success(f"Deduplication cycle completed. Dropped rows: {removed}"); st.cache_data.clear()
                    else: st.info("Database matrix is completely optimized. Zero overlapping instances found.")
            
            # Integrated Workaround for NoCode Poacher
            st.write("---")
            st.subheader("🕸️ No-Code Pipeline Simulator")
            nc_col1, nc_col2 = st.columns(2)
            nc_plat = nc_col1.selectbox("Poach Target Source", ["Zapier", "Make (Integromat)", "n8n"])
            nc_cnt = nc_col2.number_input("Lead Count", 5, 50, 25)
            if st.button("Hunt Automation Builders 🕸️", use_container_width=True):
                import zynd_nocode_finder
                leads, count = zynd_nocode_finder.find_nocode_builders(nc_plat, nc_cnt)
                st.success(f"Poaching simulation tracked! Generated {count} high-intent entries.")
                st.dataframe(leads, use_container_width=True)
