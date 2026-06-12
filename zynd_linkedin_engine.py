import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🛑 THE AGGRESSIVE BLACKLIST (Zero Tolerance for Employees)
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "langchain employee", "crewai employee", "n8n employee",
    "hiring at", "recruiting for", "developer advocate", "devrel"
]

# 🎯 THE GTM ICP WHITELIST (Must match one of these to be saved)
GTM_PERSONAS = [
    "founder", "agency", "indie hacker", "solopreneur", "ceo", "cto",
    "building", "built", "shipped", "revenue", "mrr", "clients"
]

def generate_gtm_post_queries():
    """Hyper-targeted queries based strictly on your GTM document."""
    frameworks = ["LangGraph", "CrewAI", "n8n", "MCP", "AI agent"]
    # Focus on GTM actions instead of general terms
    actions = ["agency", "founder", "built", "shipped", "production"]
    
    queries = []
    for f in frameworks:
        for a in actions:
            queries.append(f"linkedin.com/posts {f} {a}")
            
    return queries

def run_linkedin_scraper():
    st.info("🔌 Verifying Ecosystem Connections...")
    
    try:
        serper_key = st.secrets["serper"]["api_key"]
    except KeyError:
        st.error("🔑 Serper API Key Missing! Please add it to your Streamlit Secrets panel.")
        return 0

    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("LinkedIn Leads")
        except gspread.exceptions.WorksheetNotFound:
            sheet = client.open_by_key(SHEET_ID).add_worksheet(title="LinkedIn Leads", rows="1000", cols="9")
            sheet.append_row(["Source", "Platform", "Username/Name", "Profile URL", "Post URL", "Query Used", "Snippet", "Date Found", "Lead Score"])
        
        raw_data = sheet.get_all_values()
        existing_posts = set()
        if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
            post_idx = raw_data[0].index('Post URL')
            existing_posts = {str(row[post_idx]).lower().strip() for row in raw_data[1:] if len(row) > post_idx}
            
    except Exception as e:
        st.error(f"❌ Database Initialization Error: {str(e)}")
        return 0
        
    all_queries = generate_gtm_post_queries()
    # 25 high-intent queries * 100 payload = scanning 2,500 targeted posts
    execution_stack = all_queries[:25] 
    
    st.success(f"✅ GTM Matrix Formed. Deploying {len(execution_stack)} strict ICP vectors...")
    
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, query in enumerate(execution_stack):
        status_text.text(f"Extracting GTM Vector [{idx+1}/{len(execution_stack)}]: {query}")
        progress_bar.progress((idx + 1) / len(execution_stack))
        
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 100  # Max payload to offset the strict filtering
            }
            headers = {
                'X-API-KEY': serper_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code != 200:
                continue
                
            data = response.json()
            organic_results = data.get("organic", [])
            
            for result in organic_results:
                post_url = result.get("link", "").strip()
                
                # Verify it's a post link and deduplicate
                if "linkedin.com/" not in post_url.lower() or post_url.lower() in existing_posts:
                    continue
                
                raw_title = result.get("title", "")
                name = "Active Builder"
                if "on linkedin:" in raw_title.lower():
                    name = raw_title.split("on LinkedIn:")[0].strip()
                elif "-" in raw_title:
                    name = raw_title.split("-")[0].strip()
                
                snippet = result.get("snippet", "")
                clean_snippet = str(snippet).replace('\n', ' ')[:300]
                match_context = (raw_title + " " + clean_snippet).lower()
                
                # 🛑 Filter 1: The Corporate Blacklist (Zero exceptions)
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee: 
                    continue
                
                # 🎯 Filter 2: The GTM Whitelist (Must match ICP)
                is_gtm_match = False
                for persona in GTM_PERSONAS:
                    if persona in match_context:
                        is_gtm_match = True
                        break
                if not is_gtm_match:
                    continue
                
                new_leads.append([
                    "Serper GTM Post Net", 
                    "LinkedIn", 
                    name, 
                    post_url, 
                    post_url, 
                    query, 
                    clean_snippet, 
                    today_str, 
                    10 # Perfect ICP Match
                ])
                existing_posts.add(post_url.lower())
                
            time.sleep(2.0)
                
        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    if new_leads:
        from zynd_db_manager import safe_append_rows
        batch_size = 200
        for i in range(0, len(new_leads), batch_size):
            batch = new_leads[i:i + batch_size]
            safe_append_rows("LinkedIn Leads", batch, unique_url_index=4)
            time.sleep(1.5)
            
        st.success(f"🎉 GTM PIPELINE COMPLETE: Captured {len(new_leads)} verified founders and agencies!")
        return len(new_leads)
        
    st.error("🛑 Extraction Window Finalized. 0 new unique posts matched GTM.")
    return 0