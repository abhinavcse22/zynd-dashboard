import streamlit as st
import pandas as pd
import urllib.parse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import math 

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
# 🚀 CORE APPLICATION & CUSTOM UI
# ==========================================
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Secure Sync Time State Management
if 'last_sync_time' not in st.session_state:
    st.session_state['last_sync_time'] = pd.Timestamp.now().strftime('%H:%M')

def display_paginated_table(df, key_prefix, page_size=10):
    """Custom Engine to generate wrapped-text rows, clickable URLs, and Pagination."""
    if df.empty:
        st.info("No data available in this view. Run the associated scraper in the Control Room.")
        return

    # Pagination State Setup
    if f"{key_prefix}_page" not in st.session_state:
        st.session_state[f"{key_prefix}_page"] = 1
        
    total_pages = max(1, math.ceil(len(df) / page_size))
    
    # Safety catch if filters shrink the database
    if st.session_state[f"{key_prefix}_page"] > total_pages:
        st.session_state[f"{key_prefix}_page"] = total_pages
        
    current_page = st.session_state[f"{key_prefix}_page"]
    
    # Slice the Dataframe
    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    df_page = df.iloc[start_idx:end_idx]
    
    # Build HTML Table
    html = "<div style='overflow-x:auto; margin-bottom: 20px;'><table style='width:100%; border-collapse: collapse; font-size: 14px; background-color: #161b22; border-radius: 8px; overflow: hidden;'>"
    
    # Headers
    html += "<thead><tr style='background-color: #21262d;'>"
    for col in df_page.columns:
        html += f"<th style='padding: 12px; text-align: left; color: #c9d1d9; border-bottom: 1px solid #30363d; min-width: 120px;'>{col}</th>"
    html += "</tr></thead><tbody>"
    
    # Rows
    for _, row in df_page.iterrows():
        html += "<tr style='border-bottom: 1px solid #30363d;'>"
        for col in df_page.columns:
            val = str(row[col])
            
            # Format URLs to be clickable buttons
            if val.startswith("http://") or val.startswith("https://"):
                val = f"<a href='{val}' target='_blank' style='color: #58a6ff; text-decoration: none; font-weight: bold;'>View 🔗</a>"
            # Replace physical line breaks with HTML line breaks
            else:
                val = val.replace('\n', '<br>')
                
            html += f"<td style='padding: 12px; color: #c9d1d9; vertical-align: top;'>{val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    
    # Render the table
    st.markdown(html, unsafe_allow_html=True)
    
    # Render Pagination Controls
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    with col2:
        if st.button("⬅️ Previous", key=f"{key_prefix}_prev", disabled=(current_page == 1), use_container_width=True):
            st.session_state[f"{key_prefix}_page"] -= 1
            st.rerun()
    with col3:
        st.markdown(f"<div style='text-align: center; padding-top: 8px; color: #8b949e;'>Page {current_page} of {total_pages} &nbsp;|&nbsp; Total Leads: {len(df)}</div>", unsafe_allow_html=True)
    with col4:
        if st.button("Next ➡️", key=f"{key_prefix}_next", disabled=(current_page == total_pages), use_container_width=True):
            st.session_state[f"{key_prefix}_page"] += 1
            st.rerun()

@st.cache_data(ttl=300, show_spinner=False)
def load_full_database():
    """Securely loads and parses ALL database worksheets including previously hidden ones."""
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
            
            for idx, h in enumerate(headers):
                h_clean = str(h).strip()
                if not h_clean:
                    cleaned_headers.append(f"Unnamed_Col_{idx}")
                elif h_clean in cleaned_headers:
                    cleaned_headers.append(f"{h_clean}_{idx}")
                else:
                    cleaned_headers.append(h_clean)
                    
            return pd.DataFrame(raw_data[1:], columns=cleaned_headers)
        except Exception:
            return pd.DataFrame() # Return empty cleanly if tab doesn't exist yet

    # Load Core Platforms
    gh = secure_load("GitHub Leads")
    rd = secure_load("Reddit Leads")
    tw = secure_load("Twitter Leads")
    star = secure_load("github_stargazer_leads")
    fork = secure_load("Fork Sniper Leads")
    
    # Load Newly Revealed Extensions
    tele = secure_load("Telegram Leads")
    inf = secure_load("Influencer Leads")
    issue = secure_load("Issue Leads")
    disc = secure_load("Discord Leads")
    direc = secure_load("Directory Leads")
    hack = secure_load("Hackathon Leads")
    contrib = secure_load("Contributor Leads")
    
    return gh, rd, tw, star, fork, tele, inf, issue, disc, direc, hack, contrib

def clean_database():
    """Enterprise-grade background sweeper that cleans all operational tabs."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    total_removed = 0
    
    cleaning_map = {
        "GitHub Leads": "Project URL",
        "Reddit Leads": "Post URL",
        "Twitter Leads": "Post URL",
        "github_stargazer_leads": "github_profile_url",
        "Fork Sniper Leads": "Profile URL",
        "Telegram Leads": "User ID",
        "Influencer Leads": "URL",
        "Issue Leads": "Username",
        "Discord Leads": "Username",
        "Hackathon Leads": "Repo Link",
        "Contributor Leads": "Developer"
    }

    for tab_name, unique_key in cleaning_map.items():
        try:
            worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
            data = worksheet.get_all_records()
            if not data: continue
                
            df = pd.DataFrame(data)
            if unique_key not in df.columns: continue

            before_count = len(df)
            df.drop_duplicates(subset=[unique_key], keep='first', inplace=True)
            after_count = len(df)

            if before_count > after_count:
                payload = [df.columns.values.tolist()] + df.values.tolist()
                worksheet.clear()
                worksheet.update(payload)
                total_removed += (before_count - after_count)
                
        except Exception as e:
            continue

    return total_removed

# Unpack all 12 databases safely
df_gh, df_rd, df_tw, df_star, df_fork, df_tele, df_inf, df_issue, df_disc, df_dir, df_hack, df_contrib = load_full_database()

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
        "💬 Communities & Comms", 
        "🌐 Web & Influencers",
        "⚙️ Control Room",
        "📚 System Documentation"
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
                valid_statuses = ["Not Contacted", "Message 1 Sent", "Follow-Up 1 Sent", "Replied - Interested", "Replied - Pass", "DO NOT CONTACT 🛑"]
                if 'Status' in crm_data.columns:
                    crm_data['Clean_Status'] = crm_data['Status'].apply(lambda x: x if x in valid_statuses else "Not Contacted")
                else:
                    crm_data['Clean_Status'] = "Not Contacted"
                    
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
                
                st.markdown("<br>", unsafe_allow_html=True) 
                
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    st.markdown("#### 🎯 Leads by Source")
                    source_counts = crm_data['Clean_Source'].value_counts().reset_index()
                    source_counts.columns = ['Source', 'Count']
                    
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
                    
                    fig_status = px.bar(
                        status_counts, x='Status', y='Count', color='Status',
                        template="plotly_dark",
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_status.update_layout(
                        xaxis_title="", yaxis_title="Number of Leads",
                        showlegend=False, margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(tickangle=-45) 
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
    
    st.subheader("🗄️ Automated CRM Router")
    router_col1, router_col2 = st.columns(2)
    
    with router_col1:
        st.write("Distribute fresh leads and enforce DNC protocols.")
        if st.button("🔄 Execute Round-Robin Auto-Assignment", use_container_width=True):
            with st.spinner("Routing leads & checking DNC firewall..."):
                import zynd_pipeline_manager
                dnc_count = zynd_pipeline_manager.enforce_dnc_list()
                if dnc_count > 0:
                    st.warning(f"🛑 Moved {dnc_count} opted-out developers to the DNC Vault.")
                
                assigned_count = zynd_pipeline_manager.auto_assign_leads()
                st.success(f"✅ Auto-assigned {assigned_count} fresh leads across the team.")

    with router_col2:
        st.write("Leads requiring immediate outreach today.")
        if st.button("📡 Scan Follow-Up Radar", use_container_width=True):
            with st.spinner("Scanning cross-channel database..."):
                import zynd_pipeline_manager
                due_leads = zynd_pipeline_manager.get_followup_radar()
                if due_leads:
                    st.error(f"🚨 {len(due_leads)} leads are due for follow-up today!")
                    st.dataframe(due_leads, use_container_width=True)
                else:
                    st.success("✅ Inbox Zero! No follow-ups due today.")

    st.divider()
    
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("Recent High-Intent Activity")
        if not df_rd.empty: 
            display_paginated_table(df_rd.head(25), "pipeline_rd", page_size=5)
        else: 
            st.write("No recent activity found.")
    with col_right:
        st.subheader("Platform Distribution")
        chart_data = pd.DataFrame({'Source': ['GitHub', 'Reddit', 'Twitter', 'Forks'], 'Count': [len(df_gh), len(df_rd), len(df_tw), len(df_fork)]})
        st.bar_chart(chart_data.set_index('Source'))

# ==========================================
# 💻 TAB: GITHUB BUILDERS
# ==========================================
elif menu == "💻 GitHub Builders":
    gh_tab1, gh_tab2, gh_tab3, gh_tab4, gh_tab5 = st.tabs([
        "🔭 Stargazer Radar", "🎯 Fork Snipers", "🐛 Issue Snipers", "🏆 Core Contributors", "🗄️ Standard Builder DB"
    ])
    
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

            st.divider()
            st.subheader("Target List")
            display_cols = ['github_profile_url', 'source_repo', 'matched_keywords', 'lead_score', 'suggested_outreach_action', 'outreach_status']
            existing_cols = [col for col in display_cols if col in filtered_star.columns]
            
            final_view_df = filtered_star.sort_values(by='lead_score', ascending=False)[existing_cols] if 'lead_score' in filtered_star.columns else filtered_star
            display_paginated_table(final_view_df, "gh_star_tbl")
            
            st.download_button(label="📥 Export Filtered Leads to CSV", data=filtered_star.to_csv(index=False).encode('utf-8'), file_name='zynd_stargazer_leads.csv', mime='text/csv', type="primary")

    with gh_tab2:
        st.header("🎯 High-Intent Fork Builders")
        st.write("Developers who actively copied competitor repositories to build their own projects.")
        display_paginated_table(df_fork, "gh_fork_tbl")
        if not df_fork.empty:
            st.download_button(label="📥 Export Fork Leads to CSV", data=df_fork.to_csv(index=False).encode('utf-8'), file_name='zynd_fork_leads.csv', mime='text/csv')

    with gh_tab3:
        st.header("🐛 Active Issue Snipes")
        st.write("Developers actively complaining or logging bugs in competitor repositories.")
        display_paginated_table(df_issue, "gh_issue_tbl")
        if not df_issue.empty:
            st.download_button(label="📥 Export Issue Leads to CSV", data=df_issue.to_csv(index=False).encode('utf-8'), file_name='zynd_issue_leads.csv', mime='text/csv')

    with gh_tab4:
        st.header("🏆 Verified Core Contributors")
        st.write("Elite developers with verified, merged code patches to target repositories within the last 180 days.")
        display_paginated_table(df_contrib, "gh_contrib_tbl")
        if not df_contrib.empty:
            st.download_button(label="📥 Export Contributor Leads", data=df_contrib.to_csv(index=False).encode('utf-8'), file_name='zynd_contributor_leads.csv', mime='text/csv')

    with gh_tab5:
        st.header("Standard Technical Discovery")
        q_col1, q_col2 = st.columns([3, 1])
        with q_col2: min_gh = st.slider("Min Lead Score", 1, 10, 7, key="gh_slider")
        filtered_gh = df_gh[df_gh['Lead Score (1-10)'].astype(float, errors='ignore') >= min_gh] if not df_gh.empty and 'Lead Score (1-10)' in df_gh.columns else df_gh
        
        st.metric("Total GitHub Leads (Filtered)", len(filtered_gh))
        display_paginated_table(filtered_gh, "gh_std_tbl")
        
        col_export, col_osint = st.columns(2)
        with col_export:
            if not filtered_gh.empty:
                st.download_button(label="📥 Export GitHub Leads", data=filtered_gh.to_csv(index=False).encode('utf-8'), file_name='zynd_github_leads.csv', mime='text/csv')
        with col_osint:
            if st.button("🔍 Run OSINT Email Enrichment (Batch)", type="secondary"):
                with st.spinner("Executing Database Enricher..."):
                    import zynd_master_scraper
                    zynd_master_scraper.enrich_database()
                    st.success("OSINT Enrichment Complete. Data updated in background.")

# ==========================================
# 💬 TAB: REDDIT INTENT
# ==========================================
elif menu == "💬 Reddit Intent":
    st.header("Social Intent & Pain Points")
    st.metric("Total Reddit Leads", len(df_rd))
    display_paginated_table(df_rd, "rd_tbl")
    if not df_rd.empty:
        st.download_button(label="📥 Export Reddit Leads to CSV", data=df_rd.to_csv(index=False).encode('utf-8'), file_name='zynd_reddit_leads.csv', mime='text/csv')

# ==========================================
# 🐦 TAB: TWITTER SNIPER
# ==========================================
elif menu == "🐦 Twitter Sniper":
    st.header("Real-time Twitter Harvesting")
    st.metric("Total Twitter Leads", len(df_tw))
    display_paginated_table(df_tw, "tw_tbl")
    
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
# 💬 TAB: COMMUNITIES & COMMS (NEW)
# ==========================================
elif menu == "💬 Communities & Comms":
    st.header("Encrypted Network Intelligence")
    st.write("Leads extracted directly from targeted Discord, Slack, and Telegram channels.")
    
    c_tab1, c_tab2 = st.tabs(["👻 Telegram Leads", "🥷 Discord/Slack Leads"])
    
    with c_tab1:
        st.subheader("Telegram Extracted Profiles")
        display_paginated_table(df_tele, "tele_tbl")
        if not df_tele.empty:
            st.download_button(label="📥 Export Telegram Leads", data=df_tele.to_csv(index=False).encode('utf-8'), file_name='zynd_telegram_leads.csv', mime='text/csv')
            
    with c_tab2:
        st.subheader("Discord & Slack Active Network Nodes")
        display_paginated_table(df_disc, "disc_tbl")
        if not df_disc.empty:
            st.download_button(label="📥 Export Discord Leads", data=df_disc.to_csv(index=False).encode('utf-8'), file_name='zynd_discord_leads.csv', mime='text/csv')

# ==========================================
# 🌐 TAB: WEB & INFLUENCERS (NEW)
# ==========================================
elif menu == "🌐 Web & Influencers":
    st.header("Web OSINT & Broadcast Media")
    st.write("Micro-influencers, Hackathon builders, and curated Web3 directories.")
    
    w_tab1, w_tab2, w_tab3 = st.tabs(["🎥 Influencer Leads", "🗂️ Directory Leads", "🍕 Hackathon Leads"])
    
    with w_tab1:
        st.subheader("Targeted Micro-Influencers (YouTube)")
        display_paginated_table(df_inf, "inf_tbl")
        if not df_inf.empty:
            st.download_button(label="📥 Export Influencers", data=df_inf.to_csv(index=False).encode('utf-8'), file_name='zynd_influencer_leads.csv', mime='text/csv')
            
    with w_tab2:
        st.subheader("Awesome List & Directory Targets")
        display_paginated_table(df_dir, "dir_tbl")
        if not df_dir.empty:
            st.download_button(label="📥 Export Directory Leads", data=df_dir.to_csv(index=False).encode('utf-8'), file_name='zynd_directory_leads.csv', mime='text/csv')
            
    with w_tab3:
        st.subheader("Recent Hackathon Projects")
        display_paginated_table(df_hack, "hack_tbl")
        if not df_hack.empty:
            st.download_button(label="📥 Export Hackathon Leads", data=df_hack.to_csv(index=False).encode('utf-8'), file_name='zynd_hackathon_leads.csv', mime='text/csv')

# ==========================================
# ⚙️ TAB: CONTROL ROOM
# ==========================================
elif menu == "⚙️ Control Room":
    st.header("🎛️ Advanced Operations Command Console")
    st.write("Deploy extraction scripts, dispatch AI payloads, and optimize the live database.")
    
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
            dork_sub1, dork_sub2 = st.columns(2)
            with dork_sub1:
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
            with dork_sub2:
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

            with st.container(border=True):
                st.subheader("🤖 Autonomous Campaign Deployer")
                st.write("Scout GitHub for target frameworks and execute high-volume deployment.")
                keyword = st.text_input("Target Keyword", value="crewai")
                pr_limit = st.slider("Max PRs to Deploy", 1, 10, 5)

                if st.button("🔥 Launch Autonomous Campaign", use_container_width=True):
                    with st.spinner(f"Scouting GitHub for '{keyword}' developers... This will take a few minutes."):
                        import zynd_auto_pr
                        results = zynd_auto_pr.autonomous_pr_campaign(target_keyword=keyword, max_deploys=pr_limit)
                        
                        if not results:
                            st.error("Campaign finished, but no eligible targets were found or deployed.")
                        else:
                            st.success(f"Deployed {len(results)} payloads successfully!")
                            for res in results:
                                st.markdown(res)

            with st.container(border=True):
                st.subheader("📡 Automated Stealth Email Dispatcher")
                st.write("Fires personalized sequences to scripter logs containing public emails.")
                
                # New Template UI Engine
                email_mode = st.radio("Outreach Generation Mode", ["🧠 AI Personalized", "✍️ Custom Template"], horizontal=True)
                
                custom_subj = ""
                custom_msg = ""
                
                if email_mode == "✍️ Custom Template":
                    st.info("Variables you can use: `{name}`, `{repo}`, `{bio}`")
                    custom_subj = st.text_input("Subject Line", "Quick question about {repo}")
                    custom_msg = st.text_area("Email Body", "Hey {name},\n\nSaw you contributing to {repo}. I'm working on a platform called Zynd for AI agents...\n\nCheers,\nAbhinav", height=150)
                
                email_cap = st.slider("Max Broadcast Allocation (Daily Safety Limit)", 1, 20, 5, key="email_broadcast_cap")
                status_placeholder = st.empty() 
                
                if st.button("🚀 Initialize Email Outreach Matrix", type="primary", use_container_width=True):
                    with st.spinner("Executing sequence... Do not close this tab. Stealth delays are active."):
                        import zynd_email_dispatcher
                        sent_count, msg = zynd_email_dispatcher.dispatch_campaign(
                            max_emails=email_cap, 
                            mode=email_mode,
                            custom_subject=custom_subj,
                            custom_body=custom_msg,
                            status_container=status_placeholder
                        )
                        
                        status_placeholder.empty() 
                        if sent_count > 0:
                            st.success(f"Success! Safely deployed {sent_count} tracking payloads.")
                            st.info(msg)
                            st.cache_data.clear()
                        else:
                            st.warning(msg)

            # ==========================================
            # 🚨 THE NEW C2 CLOUD TRIGGER BLOCK 🚨
            # ==========================================
            with st.container(border=True):
                st.subheader("🐦 Local Twitter DM Autopilot")
                st.write("Triggers your Mac M2's local background worker using your home residential network.")
                
                tw_mode = st.radio("Twitter Generation Mode", ["🧠 AI Personalized", "✍️ Custom Template"], horizontal=True, key="tw_radio")
                
                tw_custom_msg = ""
                if tw_mode == "✍️ Custom Template":
                    st.info("Variables you can use: `{name}`, `{bio}`")
                    tw_custom_msg = st.text_area("DM Content", "Hey @{name}, saw you're building in the agent space...", height=100)
                
                twitter_cap = st.slider("Max DMs to Dispatch", 1, 15, 3, key="twitter_cap")
                
                if st.button("📡 Queue Local Dispatcher", use_container_width=True):
                    with st.spinner("Writing sequence instructions to Master Database..."):
                        try:
                            # 1. Connect to sheet
                            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
                            client = gspread.authorize(creds)
                            sheet = client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet("Twitter Leads")
                            
                            # 2. Write "START" to cell Z1 (Row 1, Column 26) to wake up the Mac Worker
                            sheet.update_cell(1, 26, "START")
                            
                            st.success("🤖 Dispatch signal broadcasted! The Mac M2 execution drone has been awakened and is processing leads in the background.")
                        except Exception as e:
                            st.error(f"Failed to communicate with master sheet: {str(e)}")
                                
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
            media_t1, media_t2, media_t3, media_t4 = st.tabs(["🚀 Market Hijacker", "🧑‍💻 Build in Public", "⚙️ Auto Git-to-Social", "⚔️ Competitor Radar"])
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
            with media_t4:
                st.markdown("#### ⚔️ Real-Time Competitor Infiltration Matrix")
                st.write("Scan competitor landing pages or code wrappers, identify feature shifts, and auto-build counter messaging blueprints.")
                
                comp_c1, comp_c2 = st.columns(2)
                comp_name = comp_c1.text_input("Competitor Identifier", placeholder="CrewAI")
                comp_url = comp_c2.text_input("Target URL Extraction Node", placeholder="https://www.crewai.com/")
                
                if st.button("🛰️ Scan and Intercept Competitor Vector", use_container_width=True):
                    if comp_name and comp_url:
                        with st.spinner(f"Intercepting {comp_name} node headers... Analysis in flight..."):
                            import zynd_competitor_radar
                            response_matrix = zynd_competitor_radar.execute_competitor_radar_sweep(comp_name, comp_url)
                            
                            if response_matrix["status"] == "No Change":
                                st.success(response_matrix["message"])
                            elif response_matrix["status"] == "Updated":
                                st.error(f"🚨 Tactical Update Logged: New positioning variations or features deployed by {comp_name}!")
                                st.markdown("### 📝 Auto-Generated Counter Positioning Blueprint:")
                                st.code(response_matrix["payload"], language="markdown")
                            else:
                                st.error(response_matrix["message"])
                    else:
                        st.warning("Ensure both target identifier and URL nodes are populated.")

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
                        if success: 
                            st.success(msg)
                            st.cache_data.clear()
                        else: 
                            st.error(msg)

        st.divider()
        st.markdown("### 🎯 Global Intent Scorer")
        st.write("Scan all leads and assign a 0-100 score based on competitor mentions and high-value actions (forking, complaining).")
        if st.button("Calculate Competitor Intent Scores 🧠", use_container_width=True):
            with st.spinner("Aggregating cross-platform interactions..."):
                import zynd_intent_scorer
                scored_count = zynd_intent_scorer.run_global_intent_scoring()
                if scored_count > 0:
                    st.success(f"Scoring Complete! Assigned weighted priority to {scored_count} fresh leads.")
                    st.cache_data.clear()
                else:
                    st.info("All leads have already been scored.")
                        
        st.divider()
        st.markdown("### 🧹 Database Integrity Engine")
        st.write("Scan all database partitions and purge duplicate records to prevent system bloat.")
        if st.button("Run Master Deduplication Sweep 🧹", use_container_width=True):
            with st.spinner("Scanning database records for duplicates..."):
                removed_count = clean_database()
                if removed_count > 0:
                    st.success(f"Sweep complete! Purged {removed_count} duplicate records from the ecosystem.")
                    st.cache_data.clear()
                else:
                    st.info("Database is clean. No duplicate records found.")
        
        st.divider()
        st.markdown("### 🎥 Influencer Campaign Matrix")
        st.write("Manage active YouTube sponsorships, track deliverables, and measure ROI.")
        
        with st.container(border=True):
            inf_col1, inf_col2, inf_col3 = st.columns(3)
            with inf_col1:
                target_channel = st.text_input("YouTube Channel Name")
                inf_stage = st.selectbox("Campaign Stage", ["Initial Outreach", "Negotiating Rates", "Awaiting Draft", "Content Live 🚀", "Paid & Closed"])
            with inf_col2:
                sponsorship_cost = st.number_input("Sponsorship Cost ($)", min_value=0, value=0, step=50)
                views_tracked = st.number_input("Views Delivered", min_value=0, value=0, step=100)
            with inf_col3:
                live_link = st.text_input("Live Video URL (If published)")
                
            if st.button("Update Creator Campaign 📊", type="primary", use_container_width=True):
                if target_channel:
                    with st.spinner("Logging financial and campaign metrics..."):
                        import zynd_influencer_tracker
                        success, msg = zynd_influencer_tracker.update_influencer_stage(
                            target_channel, inf_stage, sponsorship_cost, views_tracked, live_link
                        )
                        if success: st.success(msg)
                        else: st.error(msg)
                else:
                    st.warning("Please enter a target Channel Name.")

        st.divider()
        st.markdown("### 📝 Outreach History Ledger")
        st.write("Maintain a permanent, append-only log of all communications to prevent collision and track team velocity.")
        
        with st.container(border=True):
            hist_col1, hist_col2, hist_col3 = st.columns(3)
            with hist_col1:
                hist_lead = st.text_input("Lead Identifier (Handle/URL)", key="hist_lead")
                hist_owner = st.selectbox("Executing Owner", ["Abhinav", "Co-Founder"], key="hist_owner")
            with hist_col2:
                hist_platform = st.selectbox("Platform", ["Twitter / X", "GitHub PR", "GitHub Issue", "Email", "LinkedIn", "Telegram", "Discord"])
                hist_type = st.selectbox("Message Type", ["Initial Pitch", "Follow-up 1 (Value Add)", "Follow-up 2 (Breakup)", "Custom Reply"])
            with hist_col3:
                hist_notes = st.text_area("Notes / Message Snippet", height=110)
                
            if st.button("Log Outreach Event 💾", type="primary", use_container_width=True):
                if hist_lead:
                    with st.spinner("Appending event to permanent ledger..."):
                        import zynd_outreach_history
                        success, msg = zynd_outreach_history.log_outreach_event(
                            hist_lead, hist_owner, hist_platform, hist_type, hist_notes
                        )
                        if success: st.success(msg)
                        else: st.error(msg)
                else:
                    st.warning("A Lead Identifier is required to log an event.")

# ==========================================
# 📚 TAB: SYSTEM GUIDE & DOCUMENTATION
# ==========================================
elif menu == "📚 System Documentation":
    st.header("📚 Zynd OS: Master Playbook & Documentation")
    st.write("Complete operational guides, feature breakdowns, and navigation paths for your Go-To-Market machine.")

    doc_t1, doc_t2, doc_t3 = st.tabs([
        "🕵️‍♂️ Phase 1: Lead Harvesting & OSINT", 
        "🗄️ Phase 2: CRM Routing & Enrichment", 
        "🤖 Phase 3: AI Payloads & Content"
    ])

    # --- PHASE 1: LEAD HARVESTING ---
    with doc_t1:
        st.subheader("Phase 1: Finding High-Intent Builders")
        st.write("These tools scrape the web for developers building AI agents, Web3 infrastructure, or complaining about competitors.")
        
        with st.expander("1. GitHub Stargazer Radar (High Intent)", expanded=True):
            st.markdown("""
            **What it does:** Scans competitors (like LangChain or CrewAI), pulls all users who recently "starred" their repo, evaluates their bio for keywords, and scores them 1-10. Enforces a strict 180-day activity wall.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🏴‍☠️ Codebase Infiltration`**
            2. Enter target repos (e.g., `langchain-ai/langchain`).
            3. Set your cut-off score (recommend 5+).
            4. Click **Run Stargazer Radar**.
            5. View results in: **`💻 GitHub Builders`** ➡️ **`🔭 Stargazer Radar`**.
            """)

        with st.expander("2. GitHub Fork Sniper"):
            st.markdown("""
            **What it does:** Finds users who actively clicked "Fork" on a competitor's repo to build their own custom version locally. Runs a deep OSINT check to find hidden commit emails.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🏴‍☠️ Codebase Infiltration`**
            2. Enter the target blueprint (e.g., `crewAIInc/crewAI`).
            3. Click **Snipe Competitor Forks**.
            4. View results in: **`💻 GitHub Builders`** ➡️ **`🎯 Fork Snipers`**.
            """)

        with st.expander("3. Reddit & Twitter Intent Radars"):
            st.markdown("""
            **What it does:** Monitors social feeds for specific pain points (e.g., "CrewAI is stuck", "LangGraph error"). 
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🕵️‍♂️ Operation Scrapers`**
            2. Click **Start Reddit Engine** or **Start Twitter Engine**.
            3. View Reddit results in: **`💬 Reddit Intent`** tab.
            4. View Twitter results in: **`🐦 Twitter Sniper`** tab.
            """)
            
        with st.expander("4. The Creator Engine (YouTube)"):
            st.markdown("""
            **What it does:** Finds technical micro-influencers (500 to 100k subs) making tutorials about your competitors, allowing you to sponsor them or get them to feature Zynd.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`💬 Community Signals`**
            2. Enter a niche query (e.g., `LangChain tutorial`).
            3. Click **Hunt Creators**. 
            4. View results in: **`🌐 Web & Influencers`** ➡️ **`🎥 Influencer Leads`**.
            """)

    # --- PHASE 2: CRM & ENRICHMENT ---
    with doc_t2:
        st.subheader("Phase 2: Data Maturation & Team Assignment")
        st.write("Tools to find missing emails, distribute leads to the team, and track your funnel.")
        
        with st.expander("1. Master OSINT Enricher (Email Finder)", expanded=True):
            st.markdown("""
            **What it does:** Deploys a 5-thread worker swarm to re-scan your database. If a lead doesn't have an email, it hacks their public GitHub commit logs to extract the hidden email address.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🕵️‍♂️ Operation Scrapers`**
            2. Click **Engage Turbo Scraper**. It will run in the background and update Google Sheets automatically.
            """)

        with st.expander("2. Automated CRM Router (Round-Robin)"):
            st.markdown("""
            **What it does:** Enforces your "Do Not Contact" (DNC) list, then takes all fresh, unassigned leads and splits them evenly between you and your Co-Founder.
            
            **How to use it:**
            1. Navigate to: **`📈 Pipeline Overview`**
            2. Scroll down to **🗄️ Automated CRM Router**.
            3. Click **Execute Round-Robin Auto-Assignment**.
            """)

        with st.expander("3. Database Integrity Engine"):
            st.markdown("""
            **What it does:** Sweeps every single tab in your Google Sheets database and deletes any accidental duplicate records to keep your CRM clean and fast.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🗄️ Database & CRM`**
            2. Scroll down to **🧹 Database Integrity Engine**.
            3. Click **Run Master Deduplication Sweep 🧹**.
            """)

        with st.expander("4. Outreach History Ledger"):
            st.markdown("""
            **What it does:** An immutable log of every DM, PR, or Email sent. Prevents you and your Co-Founder from accidentally messaging the same developer twice.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🗄️ Database & CRM`**
            2. Scroll down to **Outreach History Ledger**.
            3. Input the lead identifier, platform, and paste the message sent, then click **Log Outreach Event**.
            """)

    # --- PHASE 3: AI PAYLOADS ---
    with doc_t3:
        st.subheader("Phase 3: Automated Outbound & Marketing")
        st.write("Deploy AI agents to write code, submit PRs, and generate social content.")
        
        with st.expander("1. Autonomous Auto-PR Campaigner", expanded=True):
            st.markdown("""
            **What it does:** Searches GitHub for new AI agents, automatically forks their repo, writes a `zynd_wrapper.py` monetization patch, and submits a Pull Request to the builder while you sleep.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🧠 AI Payload Deployers`**
            2. Enter a target keyword (e.g., `ai-agent`).
            3. Set the PR limit (Keep this low, 5-10 max per day, to avoid GitHub bans).
            4. Click **Launch Autonomous Campaign**.
            """)

        with st.expander("2. Pro AI Drafter (Cold Outreach)"):
            st.markdown("""
            **What it does:** Reads a developer's bio, their recent complaints, and their tech stack, then generates a highly technical 3-step outreach sequence (Initial, Value Add, Breakup).
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🧠 AI Payload Deployers`**
            2. Look for **Pro AI Drafter**.
            3. Select a lead directly from the database dropdown, or manually paste their bio.
            4. Click **Generate Outreach Sequence**.
            """)

        with st.expander("3. Competitor Infiltration Matrix"):
            st.markdown("""
            **What it does:** Scrapes a competitor's live website (e.g., crewai.com). If it detects a new feature launch or text change, it commands OpenRouter to instantly write a counter-positioning social media post.
            
            **How to use it:**
            1. Navigate to: **`⚙️ Control Room`** ➡️ **`🧠 AI Payload Deployers`**
            2. Select the **⚔️ Competitor Radar** tab.
            3. Input the competitor name and URL.
            4. Click **Scan and Intercept Competitor Vector**.
            """)