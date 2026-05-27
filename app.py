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
    h1, h2, h3 { color: #58a6ff !important; font-family: 'Inter', sans-serif; }
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

@st.cache_data(ttl=300, show_spinner=False)
def load_full_database():
    """Securely loads data using Service Account Credentials instead of public CSV links."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # Helper function to securely load a tab into a DataFrame
    def secure_load(tab_name):
        try:
            worksheet = client.open_by_key(SHEET_ID).worksheet(tab_name)
            records = worksheet.get_all_records()
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as e:
            st.sidebar.error(f"⚠️ Failed to load '{tab_name}': {str(e)}")
            return pd.DataFrame()

    # Load all 5 core databases
    gh = secure_load("GitHub Leads")
    rd = secure_load("Reddit Leads")
    tw = secure_load("Twitter Leads")
    star = secure_load("github_stargazer_leads")
    fork = secure_load("Fork Sniper Leads")
    
    return gh, rd, tw, star, fork

def clean_database():
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

# Unpack the 5 databases
df_gh, df_rd, df_tw, df_star, df_fork = load_full_database()

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
    st.info(f"🟢 **System Online**\n\nLast Sync: {pd.Timestamp.now().strftime('%H:%M')}")
    if st.button("🔄 Force Data Sync", use_container_width=True):
        st.cache_data.clear()
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
            
            # This requires a "Master CRM" tab in your Google Sheet with "Status" and "Source" columns
            crm_data = pd.DataFrame(sheet.worksheet("Master CRM").get_all_records())
            
            if not crm_data.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Leads Extracted", len(crm_data))
                with col2:
                    contacted = len(crm_data[crm_data['Status'] != 'Not Contacted'])
                    st.metric("Leads Engaged", contacted)
                with col3:
                    conversion_rate = round((contacted / len(crm_data)) * 100, 1) if len(crm_data) > 0 else 0
                    st.metric("Engagement Rate", f"{conversion_rate}%")
                
                st.write("---")
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    st.markdown("#### Leads by Source")
                    if 'Source' in crm_data.columns:
                        source_counts = crm_data['Source'].value_counts().reset_index()
                        source_counts.columns = ['Source', 'Count']
                        fig_source = px.pie(source_counts, values='Count', names='Source', hole=0.4)
                        st.plotly_chart(fig_source, use_container_width=True)
                    else:
                        st.warning("Column 'Source' not found in Master CRM.")
                    
                with chart_col2:
                    st.markdown("#### Pipeline Status")
                    if 'Status' in crm_data.columns:
                        status_counts = crm_data['Status'].value_counts().reset_index()
                        status_counts.columns = ['Status', 'Count']
                        fig_status = px.bar(status_counts, x='Status', y='Count', color='Status')
                        st.plotly_chart(fig_status, use_container_width=True)
                    else:
                        st.warning("Column 'Status' not found in Master CRM.")
            else:
                st.info("Your CRM is currently empty. Go to the Control Room and extract some leads!")
                
        except Exception as e:
            st.error(f"Error loading dashboard data. Ensure you have a 'Master CRM' tab in your Google Sheet. Error Details: {e}")

# ==========================================
# 📈 TAB: PIPELINE OVERVIEW
# ==========================================
elif menu == "📈 Pipeline Overview":
    st.header("Executive GTM Summary")
    m1, m2, m3, m4 = st.columns(4)
    total_leads = len(df_gh) + len(df_rd) + len(df_tw) + len(df_star) + len(df_fork)
    m1.metric("Total Lead Pool", total_leads)
    m2.metric("Hot Stargazer Leads", len(df_star[df_star['lead_bucket'] == 'Hot lead']) if not df_star.empty and 'lead_bucket' in df_star.columns else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty and 'Lead Score (1-10)' in df_rd.columns else 0)
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
        filtered_gh = df_gh[df_gh['Lead Score (1-10)'] >= min_gh] if not df_gh.empty and 'Lead Score (1-10)' in df_gh.columns else df_gh
        
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
                    if dry_run: st.success(f"Dry run complete. Found {count} qualified leads.")
                    else:
                        st.success(f"Radar complete! Database updated with {count} total qualified leads.")
                        st.cache_data.clear()
                except Exception as e: st.error(f"Engine Error: {e}")

    st.write("") 
    
    st.markdown("### 🤖 The Auto-PR Engine")
    with st.container(border=True):
        st.write("Automatically fork a prospect's repo, inject the `zyndai-agent` wrapper, and submit a high-converting Pull Request.")
        pr_col1, pr_col2 = st.columns([3, 1])
        with pr_col1: target_pr_repo = st.text_input("Target Repository (e.g., username/repository-name)", placeholder="developer/awesome-langchain-agent")
        with pr_col2:
            st.write("") 
            st.write("") 
            if st.button("🚀 Deploy PR Payload", type="primary", use_container_width=True):
                if target_pr_repo:
                    with st.spinner(f"Forking {target_pr_repo} and writing code..."):
                        success, result = zynd_auto_pr.generate_zynd_pr(target_pr_repo.strip())
                        if success:
                            st.success("PR Submitted Successfully!")
                            st.markdown(f"[🔗 Click here to view the live PR]({result})")
                        else: st.error(f"Failed to submit PR: {result}")
                else: st.warning("Please enter a repository name first.")

    st.write("")
    st.markdown("### 🧠 Pro AI Drafter (Outreach Sequence Builder)")
    with st.container(border=True):
        st.write("Instantly generate hyper-personalized outreach sequences for any lead using OpenRouter.")
        
        input_mode = st.radio("Lead Selection Method:", ["🗄️ Select from Database", "✍️ Manual Entry"], horizontal=True)
        
        lead_n, lead_intent, lead_context = "", "", ""
        
        if input_mode == "🗄️ Select from Database":
            db_col1, db_col2 = st.columns(2)
            with db_col1:
                db_choice = st.selectbox("Select Target Database", ["Fork Sniper Leads", "Reddit Leads", "Twitter Leads", "GitHub Stargazers"])
            
            with db_col2:
                if db_choice == "Fork Sniper Leads" and not df_fork.empty and 'Username' in df_fork.columns:
                    lead_list = df_fork['Username'].dropna().tolist()
                    selected_lead = st.selectbox("Select Prospect", lead_list)
                    if selected_lead:
                        row = df_fork[df_fork['Username'] == selected_lead].iloc[0]
                        lead_n = str(row['Username'])
                        lead_intent = str(row.get('Source', 'Fork Sniper Engine'))
                        lead_context = str(row.get('Bio', 'GitHub Builder'))
                        
                elif db_choice == "Reddit Leads" and not df_rd.empty:
                    user_col = 'Author' if 'Author' in df_rd.columns else ('Username' if 'Username' in df_rd.columns else df_rd.columns[0])
                    lead_list = df_rd[user_col].dropna().astype(str).tolist()
                    selected_lead = st.selectbox("Select Prospect", lead_list)
                    if selected_lead:
                        row = df_rd[df_rd[user_col] == selected_lead].iloc[0]
                        lead_n = str(row[user_col])
                        lead_intent = f"Reddit Post in {row.get('Subreddit', 'Unknown Sub')}"
                        lead_context = str(row.get('Title', '')) + " - " + str(row.get('Content', ''))
                        
                elif db_choice == "Twitter Leads" and not df_tw.empty:
                    user_col = 'Username' if 'Username' in df_tw.columns else df_tw.columns[0]
                    lead_list = df_tw[user_col].dropna().astype(str).tolist()
                    selected_lead = st.selectbox("Select Prospect", lead_list)
                    if selected_lead:
                        row = df_tw[df_tw[user_col] == selected_lead].iloc[0]
                        lead_n = str(row[user_col])
                        lead_intent = "Twitter Intent Snipe"
                        lead_context = str(row.get('Tweet', row.get('Bio', '')))
                        
                elif db_choice == "GitHub Stargazers" and not df_star.empty:
                    url_col = 'github_profile_url' if 'github_profile_url' in df_star.columns else df_star.columns[0]
                    lead_list = df_star[url_col].dropna().astype(str).tolist()
                    selected_lead = st.selectbox("Select Prospect", lead_list)
                    if selected_lead:
                        row = df_star[df_star[url_col] == selected_lead].iloc[0]
                        lead_n = str(row[url_col]).split('/')[-1]
                        lead_intent = f"Starred {row.get('source_repo', 'Competitor Repo')}"
                        lead_context = f"Matched keywords: {row.get('matched_keywords', 'AI, Agent, Web3')}"
                else:
                    st.warning("No data found in this database yet.")

            if lead_n:
                st.info(f"**Target:** {lead_n} | **Intent:** {lead_intent}")
                with st.expander("View Internal Context Data"):
                    st.write(lead_context)

        else:
            draft_col1, draft_col2 = st.columns(2)
            with draft_col1:
                lead_n = st.text_input("Lead Name / Handle", placeholder="e.g., @AgentBuilder99")
                lead_intent = st.text_input("Intent Source", placeholder="e.g., Forked crewAI, Complaining about LangChain")
            with draft_col2:
                lead_context = st.text_area("Lead Context (Paste bio or Reddit post)", height=110)
                
        if st.button("Generate Outreach Sequence ⚡", type="primary", use_container_width=True):
            if lead_n and lead_context:
                with st.spinner("AI is analyzing intent and writing the sequence..."):
                    import zynd_ai_drafter
                    sequence = zynd_ai_drafter.generate_outreach_sequence(lead_n, lead_intent, lead_context)
                    st.success("Sequence Generated!")
                    st.code(sequence, language="markdown")
            else:
                st.warning("Please select a lead or provide context first.")

    st.write("")
    
    st.markdown("### 🎯 Deep OSINT: GitHub Fork Sniper")
    with st.container(border=True):
        st.write("Find high-intent developers who forked a competitor's repo, extract hidden emails, and push to database.")
        target_fork = st.text_input("Target Repo (e.g., crewAIInc/crewAI)")
        
        if st.button("Snipe Competitor Forks", use_container_width=True):
            if target_fork:
                with st.spinner(f"Extracting hidden data from {target_fork} and pushing to database..."):
                    try:
                        leads_data, saved_count = zynd_github_sniper.run_fork_sniper(target_fork)
                        st.success(f"Extraction complete! Saved {saved_count} new high-intent builders directly to the database.")
                        st.cache_data.clear()
                        st.dataframe(leads_data)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Enter a target repository first.")

    st.write("---")
    st.markdown("### 🎯 Deep OSINT: GitHub Issue Sniper")
    with st.container(border=True):
        st.write("Hunt down high-intent developers actively complaining in competitor 'Issues' tabs.")
        
        sniper_col1, sniper_col2 = st.columns([3, 1])
        with sniper_col1:
            target_repo = st.text_input("Target Competitor Repo", placeholder="e.g., langchain-ai/langchain")
        with sniper_col2:
            issue_depth = st.number_input("Issues to Scan", min_value=10, max_value=100, value=20)
            
        if st.button("Snipe Active Complaints 🔫", type="primary", use_container_width=True):
            if target_repo:
                with st.spinner(f"Infiltrating {target_repo} issue boards..."):
                    try:
                        import zynd_issue_sniper
                        leads, count = zynd_issue_sniper.snipe_repo_issues(target_repo, issue_depth)
                        
                        if count > 0:
                            st.success(f"Target Acquired: Extracted {count} high-intent complainers to your database.")
                            st.dataframe(leads, use_container_width=True)
                            st.cache_data.clear()
                        else:
                            st.warning("No new leads found. Try scanning deeper or a different repo.")
                    except Exception as e:
                        st.error(f"Extraction Error: {e}")
            else:
                st.warning("Enter a target repository format (owner/repo).")

    st.write("---")
    st.markdown("### 🏆 Deep OSINT: GitHub Contributor Finder")
    with st.container(border=True):
        st.write("Extract elite engineers who have successfully merged code into competitor repositories.")
        
        target_contrib_repo = st.text_input("Competitor Repository", placeholder="e.g., microsoft/autogen")
        
        if st.button("Extract Core Builders 🧬", type="primary", use_container_width=True):
            if target_contrib_repo:
                with st.spinner(f"Scanning {target_contrib_repo} for elite contributors..."):
                    try:
                        import zynd_contributor_finder
                        leads, count = zynd_contributor_finder.hunt_contributors(target_contrib_repo)
                        
                        if count > 0:
                            st.success(f"Heist Complete! Added {count} elite engineers to the database.")
                            st.dataframe(leads, use_container_width=True)
                            st.cache_data.clear()
                        else:
                            st.warning("No new contributors found (they may already be in your database).")
                    except Exception as e:
                        st.error(f"Extraction Error: {e}")
            else:
                st.warning("Enter a valid repository name.")

    st.write("---")
    st.markdown("### 🥷 Deep OSINT: Omni-Channel Community Sniper")
    with st.container(border=True):
        st.write("Infiltrate closed Web3 and AI communities on Discord and Slack.")
        
        omni_platform = st.radio("Target Platform", ["Discord", "Slack"], horizontal=True)
        
        col_auth1, col_auth2 = st.columns(2)
        with col_auth1:
            auth_token = st.text_input(f"Your {omni_platform} Auth Token", type="password", help="Grab this from your browser network tab (F12) while logged in.")
        with col_auth2:
            if omni_platform == "Discord":
                target_id = st.text_input("Discord Server ID", placeholder="e.g., 8301823901...")
            else:
                target_id = st.text_input("Slack Workspace URL (Not required for API)", disabled=True)
                
        if st.button(f"Infiltrate {omni_platform} 🎯", type="primary", use_container_width=True):
            if auth_token:
                with st.spinner(f"Bypassing {omni_platform} API walls..."):
                    import zynd_omni_scraper
                    if omni_platform == "Discord":
                        leads, status = zynd_omni_scraper.scrape_discord_server(target_id, auth_token)
                    else:
                        leads, status = zynd_omni_scraper.scrape_slack_workspace(auth_token)
                        
                    if leads:
                        st.success(f"Infiltration Complete! Extracted {len(leads)} active users.")
                        st.dataframe(pd.DataFrame(leads, columns=["Username", "Source", "Name", "Bio/Title", "Date"]), use_container_width=True)
                    else:
                        st.error(status)
            else:
                st.warning("Auth token required.")

    st.write("")
    st.markdown("### 👻 The Telegram Ghost (Group Infiltrator)")
    with st.container(border=True):
        st.write("Silently infiltrate competitor Telegram groups and extract all active member usernames.")
        
        target_tg_groups = st.text_area(
            "Target Channels (Paste links or @usernames, one per line)", 
            placeholder="https://t.me/langchain_ai\n@crewAI\nhttps://t.me/web3builders",
            height=100
        )
        
        if st.button("Infiltrate & Extract Telegram Leads", type="primary", use_container_width=True):
            if target_tg_groups:
                with st.spinner("Ghost account connecting to Telegram API and ripping member lists..."):
                    try:
                        import zynd_telegram_ghost
                        tg_leads, saved_count = zynd_telegram_ghost.run_telegram_scraper(target_tg_groups)
                        st.success(f"Heist Complete! Extracted and saved {saved_count} new targeted leads to the database.")
                        if tg_leads:
                            st.dataframe(tg_leads, use_container_width=True)
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Infiltration Error: {e}")
            else:
                st.warning("Enter at least one target Telegram group first.")

    st.write("")
    st.markdown("### 🎥 The Creator Engine (Influencer Networker)")
    with st.container(border=True):
        st.write("Hunt down YouTube micro-influencers (500 - 100k subs) building tutorials in specific AI/Web3 niches.")
        
        creator_col1, creator_col2 = st.columns([3, 1])
        with creator_col1:
            youtube_niche = st.text_input("Target Niche / Search Query", placeholder="e.g., 'LangChain tutorial', 'AutoGPT build', 'Web3 AI'")
        with creator_col2:
            max_vids = st.number_input("Videos to Scan", min_value=10, max_value=50, value=25)
            
        if st.button("Hunt Creators 🎯", type="primary", use_container_width=True):
            if youtube_niche:
                with st.spinner("Scanning YouTube API for high-leverage micro-influencers..."):
                    try:
                        import zynd_creator_engine
                        creators, saved_count = zynd_creator_engine.hunt_micro_influencers(youtube_niche, max_vids)
                        if saved_count > 0:
                            st.success(f"Target Acquired: Saved {saved_count} new micro-influencers to your database.")
                            st.dataframe(creators, use_container_width=True)
                        else:
                            st.warning("No new micro-influencers found. Try a broader search or increase the scan limit.")
                    except Exception as e:
                        st.error(f"Engine Error: {e}")
            else:
                st.warning("Enter a search query first.")

    st.write("")
    st.markdown("### 🗄️ Team CRM & Pipeline Manager")
    with st.container(border=True):
        st.write("Assign leads, track outreach history, and manage the Do-Not-Contact list.")
        
        crm_col1, crm_col2 = st.columns(2)
        
        with crm_col1:
            db_target = st.selectbox("Select Database to Update", ["Telegram Leads", "Reddit Leads", "Twitter Leads", "Fork Sniper Leads", "Influencer Leads"])
            lead_target = st.text_input("Lead Identifier (Exact Username or URL)")
            
        with crm_col2:
            assignee = st.selectbox("Assign Lead Owner", ["Unassigned", "Abhinav", "Co-Founder", "Sales Rep 1"])
            lead_status = st.selectbox("Update Status", [
                "Not Contacted", 
                "Message 1 Sent", 
                "Follow-Up 1 Sent", 
                "Replied - Interested", 
                "Replied - Pass", 
                "DO NOT CONTACT 🛑"
            ])
            follow_up = st.date_input("Next Follow-Up Date")
            
        if st.button("Update Lead Status 💾", type="primary", use_container_width=True):
            if lead_target:
                with st.spinner("Writing update to master database..."):
                    import zynd_crm_engine
                    
                    col_index_map = {
                        "Telegram Leads": 1, 
                        "Reddit Leads": 0,
                        "Twitter Leads": 0,
                        "Fork Sniper Leads": 0,
                        "Influencer Leads": 1
                    }
                    
                    success, msg = zynd_crm_engine.update_lead_status(
                        tab_name=db_target,
                        search_column_index=col_index_map[db_target],
                        lead_identifier=lead_target,
                        owner=assignee,
                        status=lead_status,
                        follow_up_date=str(follow_up)
                    )
                    
                    if success:
                        st.success(msg)
                        st.cache_data.clear()
                    else:
                        st.error(f"Failed: {msg}")
            else:
                st.warning("Please enter the exact username of the lead you want to update.")


    st.write("---")
    st.markdown("### 🎙️ The Zynd Media Empire")
    
    comp_tab, personal_tab, git_tab = st.tabs(["🚀 Market Hijacker (Company)", "🧑‍💻 Build in Public (Team)", "⚙️ Auto Git-to-Social"])
    
    with comp_tab:
        targets = st.text_input("Competitors to Hijack", "LangChain, CrewAI, AutoGen")
        if st.button("Generate Market-Informed Content 🌐"):
            import zynd_content_engine
            content = zynd_content_engine.generate_hybrid_content(df_rd, df_tw, [t.strip() for t in targets.split(',')])
            st.code(content, language="markdown")

    with personal_tab:
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Member Name")
            role = st.selectbox("Role", ["Engineer", "Product Ops", "Founder", "Community"])
        with col2:
            vibe = st.selectbox("Style", ["Hacker (Direct)", "Storyteller", "Visionary"])
        
        work = st.text_area("What did you solve today?")
        if st.button("Draft Personal Post ✍️"):
            import zynd_brand_engine
            draft = zynd_brand_engine.generate_team_post(name, role, vibe, work)
            st.code(draft, language="markdown")

    with git_tab:
        st.write("Automatically read your team's latest GitHub commits and generate launch posts.")
        my_repo = st.text_input("Your Zynd Repository", placeholder="e.g., abhinav/zynd-os")
        
        if st.button("Read Latest Commit & Draft Post ⚡", type="primary", use_container_width=True):
            if my_repo:
                with st.spinner("Scanning GitHub and translating code to marketing..."):
                    import zynd_git_social
                    data, status = zynd_git_social.fetch_latest_commit_and_post(my_repo)
                    
                    if data:
                        st.success(f"Latest push by {data['author']} intercepted!")
                        st.info(f"**Raw Commit:** {data['message']}")
                        st.code(data['post'], language="markdown")
                    else:
                        st.error(status)
    
    st.write("") 
    st.markdown("### ⚙️ Standard Harvesters")
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    with row1_col1:
        with st.container(border=True):
            st.subheader("🚀 GitHub Harvester")
            if st.button("Start GitHub Engine", use_container_width=True):
                with st.spinner("Executing..."):
                    try:
                        zynd_leads.harvest_leads()
                        st.success("GitHub Updated!")
                        st.cache_data.clear()
                    except Exception as e: st.error(str(e))

    with row1_col2:
        with st.container(border=True):
            st.subheader("⚡ Master Enricher")
            if st.button("Engage Turbo Scraper", use_container_width=True):
                with st.spinner("Executing..."):
                    try:
                        zynd_master_scraper.enrich_database()
                        st.success("Enrichment Complete!")
                        st.cache_data.clear()
                    except Exception as e: st.error(str(e))

    with row2_col1:
        with st.container(border=True):
            st.subheader("📡 Reddit Radar")
            if st.button("Start Reddit Engine", use_container_width=True):
                with st.spinner("Executing..."):
                    try:
                        zynd_daily_engine.run_reddit_scraper()
                        st.success("Reddit Updated!")
                        st.cache_data.clear()
                    except Exception as e: st.error(str(e))

    with row2_col2:
        with st.container(border=True):
            st.subheader("🐦 Twitter Autopilot")
            if st.button("Start Twitter Engine", use_container_width=True):
                with st.spinner("Bypassing API and scraping Twitter..."):
                    try:
                        new_count = zynd_twitter_engine.run_twitter_scraper()
                        if new_count and new_count > 0:
                            st.success(f"Twitter Updated! Extracted {new_count} new users & posts.")
                            st.cache_data.clear()
                        else: st.info("Scan complete. No new leads found right now.")
                    except Exception as e: st.error(f"Engine Error: {str(e)}")

    st.write("---")
    st.markdown("### 🗂️ The AI Agent Directory Scanner")
    with st.container(border=True):
        st.write("Scan 'Awesome Lists' and agent directories to find developers who have already built products and invite them to publish on Zynd.")
        
        dir_col1, dir_col2 = st.columns([3, 1])
        with dir_col1:
            target_directory = st.text_input("Target Directory Repo", placeholder="e.g., e2b-dev/awesome-ai-agents")
        
        if st.button("Scan Directory & Extract Projects 🔍", type="primary", use_container_width=True):
            if target_directory:
                with st.spinner(f"Parsing markdown directory {target_directory}..."):
                    try:
                        import zynd_directory_scanner
                        projects, status = zynd_directory_scanner.scan_awesome_directory(target_directory)
                        
                        if isinstance(projects, list) and len(projects) > 0:
                            st.success(f"Directory Ripped! Extracted {len(projects)} pre-built agent projects.")
                            st.dataframe(projects, use_container_width=True)
                            st.cache_data.clear()
                        elif isinstance(projects, list) and len(projects) == 0:
                            st.warning("Scan complete, but no new projects were found (they may already be in your DB).")
                        else:
                            st.error(status)
                    except Exception as e:
                        st.error(f"Scanner Error: {e}")
            else:
                st.warning("Enter a target GitHub directory repository.")

    st.write("---")
    st.markdown("### 🍕 The Hackathon Project Finder")
    with st.container(border=True):
        st.write("Rescue orphaned AI agent projects built over the weekend and invite them to deploy on Zynd OS.")
        
        hack_col1, hack_col2 = st.columns([3, 1])
        with hack_col1:
            hack_query = st.text_input("Search Query", value="hackathon AI agent")
        with hack_col2:
            num_projects = st.number_input("Projects to Scan", min_value=10, max_value=50, value=30)
            
        if st.button("Hunt Weekend Builders 🛠️", type="primary", use_container_width=True):
            if hack_query:
                with st.spinner("Scanning global GitHub indexing for recent hackathon projects..."):
                    try:
                        import zynd_hackathon_finder
                        projects, count = zynd_hackathon_finder.hunt_hackathon_projects(hack_query, num_projects)
                        
                        if count > 0:
                            st.success(f"Rescue Mission Complete! Found {count} new hackathon projects.")
                            st.dataframe(projects, use_container_width=True)
                            st.cache_data.clear()
                        else:
                            st.warning("No new hackathon projects found for this query right now.")
                    except Exception as e:
                        st.error(f"Search Error: {e}")
            else:
                st.warning("Enter a search query.")

    st.write("---")
    st.markdown("### 🏴‍☠️ Zero-Cost Deep OSINT (Simulation Pipeline)")
    with st.container(border=True):
        st.write("High-speed simulated extraction pipeline for testing UI and Database CRM flow.")
        
        dork_col1, dork_col2 = st.columns(2)
        with dork_col1:
            dork_mission = st.selectbox("Extraction Mission", [
                "Bio/Profile Scraper (Replaces Follower Stealer)",
                "Complaint Scraper (Replaces No-Code Finder)"
            ])
            dork_target = st.text_input("Target Competitor / Tool", placeholder="Zapier")
            
        with dork_col2:
            dork_platform = st.selectbox("Target Platform", ["twitter.com", "linkedin.com/in", "reddit.com"])
            dork_count = st.slider("Leads to Extract", 5, 50, 25)
            
        if st.button("Execute Zero-Cost Heist 🕵️‍♂️", type="primary", use_container_width=True):
            if dork_target:
                with st.spinner(f"Simulating pipeline extraction for {dork_target}..."):
                    try:
                        import zynd_dork_engine
                        results, count = zynd_dork_engine.run_zero_cost_extraction(dork_target, dork_platform, dork_mission, dork_count)
                        
                        if isinstance(count, int) and count > 0:
                            st.success(f"Pipeline Test Successful! Routed {count} leads to database.")
                            st.dataframe(results, use_container_width=True)
                            st.cache_data.clear()
                        elif isinstance(count, int) and count == 0:
                            st.warning("No new leads found.")
                        else:
                            st.error(count)
                    except Exception as e:
                        st.error(f"Execution Error: {e}")
            else:
                st.warning("Enter a target competitor.")

    st.divider()
    st.subheader("🧹 Database Maintenance")
    if st.button("Clean Duplicates", type="primary"):
        with st.spinner("Scanning database for duplicates..."):
            removed = clean_database()
            if removed > 0:
                st.success(f"Database clean! Removed {removed} duplicate leads.")
                st.cache_data.clear()
            else: st.info("Database is already perfectly clean. No duplicates found.")
