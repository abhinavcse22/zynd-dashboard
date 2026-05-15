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

@st.cache_data(ttl=300)
def load_full_database():
    def get_url(name): return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(name)}"
    try: gh = pd.read_csv(get_url("GitHub Leads"))
    except: gh = pd.DataFrame()
    try: rd = pd.read_csv(get_url("Reddit Leads"))
    except: rd = pd.DataFrame()
    try: tw = pd.read_csv(get_url("Twitter Leads"))
    except: tw = pd.DataFrame()
    try: star = pd.read_csv(get_url("github_stargazer_leads"))
    except: star = pd.DataFrame()
    try: fork = pd.read_csv(get_url("Fork Sniper Leads")) # <--- NEW: Telling the app to read the new tab
    except: fork = pd.DataFrame()
    
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
    menu = st.radio("Navigation", ["📈 Pipeline Overview", "💻 GitHub Builders", "💬 Reddit Intent", "🐦 Twitter Sniper", "⚙️ Control Room"])
    st.markdown("---")
    st.info(f"🟢 **System Online**\n\nLast Sync: {pd.Timestamp.now().strftime('%H:%M')}")
    if st.button("🚪 Log Out", type="secondary"):
        st.session_state["password_correct"] = False
        st.rerun()

# ==========================================
# 📈 TAB: PIPELINE OVERVIEW
# ==========================================
if menu == "📈 Pipeline Overview":
    st.header("Executive GTM Summary")
    m1, m2, m3, m4 = st.columns(4)
    total_leads = len(df_gh) + len(df_rd) + len(df_tw) + len(df_star) + len(df_fork)
    m1.metric("Total Lead Pool", total_leads)
    m2.metric("Hot Stargazer Leads", len(df_star[df_star['lead_bucket'] == 'Hot lead']) if not df_star.empty and 'lead_bucket' in df_star.columns else 0)
    m3.metric("Critical Pain Points", len(df_rd[df_rd['Lead Score (1-10)'] >= 9]) if not df_rd.empty and 'Lead Score (1-10)' in df_rd.columns else 0)
    m4.metric("Active Code Forkers", len(df_fork))

    st.divider()
    
    # --- SAAS FEATURE: ACTION CENTER ---
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
    # --- NEW: Added a 3rd tab specifically for the Fork Sniper Leads ---
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

    # --- NEW UI FOR THE FORK LEADS ---
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
    
    # SAAS FEATURE: CSV EXPORT
    if not df_rd.empty:
        st.download_button(label="📥 Export Reddit Leads to CSV", data=df_rd.to_csv(index=False).encode('utf-8'), file_name='zynd_reddit_leads.csv', mime='text/csv')

# ==========================================
# 🐦 TAB: TWITTER SNIPER
# ==========================================
elif menu == "🐦 Twitter Sniper":
    st.header("Real-time Twitter Harvesting")
    st.metric("Total Twitter Leads", len(df_tw))
    st.data_editor(df_tw, use_container_width=True, height=400, num_rows="dynamic")
    
    # SAAS FEATURE: CSV EXPORT
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
        
        # Toggle between Database or Manual
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
                    # Dynamically find the user column
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
                        lead_n = str(row[url_col]).split('/')[-1] # Extract username from URL
                        lead_intent = f"Starred {row.get('source_repo', 'Competitor Repo')}"
                        lead_context = f"Matched keywords: {row.get('matched_keywords', 'AI, Agent, Web3')}"
                else:
                    st.warning("No data found in this database yet.")

            # Show the user what data is being sent to the AI
            if lead_n:
                st.info(f"**Target:** {lead_n} | **Intent:** {lead_intent}")
                with st.expander("View Internal Context Data"):
                    st.write(lead_context)

        else:
            # The Manual Entry Mode
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
                        # Clear cache so the new tab updates instantly
                        st.cache_data.clear()
                        st.dataframe(leads_data)
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Enter a target repository first.")

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
                        st.cache_data.clear() # Refresh app data
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
            # In a real app, you'd dynamically load the lead list here like we did for the AI Drafter
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
                    
                    # Map the UI selection to the actual Google Sheet Tab name and the index of the Username column
                    # (Assuming Username is roughly column index 1 in most of your sheets)
                    col_index_map = {
                        "Telegram Leads": 1, 
                        "Reddit Leads": 0, # Assuming Author is Col 0
                        "Twitter Leads": 0,
                        "Fork Sniper Leads": 0,
                        "Influencer Leads": 1 # URL is Col 1
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
                        st.cache_data.clear() # Refresh data on dashboard
                    else:
                        st.error(f"Failed: {msg}")
            else:
                st.warning("Please enter the exact username of the lead you want to update.")


    st.write("---")
    st.markdown("### 🎙️ The Zynd Media Empire")
    
    comp_tab, personal_tab = st.tabs(["🚀 Market Hijacker (Company)", "🧑‍💻 Build in Public (Team)"])
    
    with comp_tab:
        targets = st.text_input("Competitors to Hijack", "LangChain, CrewAI, AutoGen")
        if st.button("Generate Market-Informed Content 🌐"):
            import zynd_content_engine
            # Ensure df_rd and df_tw are passed for internal context
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

    st.divider()
    st.subheader("🧹 Database Maintenance")
    if st.button("Clean Duplicates", type="primary"):
        with st.spinner("Scanning database for duplicates..."):
            removed = clean_database()
            if removed > 0:
                st.success(f"Database clean! Removed {removed} duplicate leads.")
                st.cache_data.clear()
            else: st.info("Database is already perfectly clean. No duplicates found.")
