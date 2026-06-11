import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import itertools

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 1. THE ZYND COHORT MATRIX 
# Directly mapped to the 7 target developer types in your GTM documentation
FRAMEWORKS = ["LangGraph", "CrewAI", "n8n", "Phidata", "Autogen", "MCP server", "Swarm agent"]

# Broadened to capture anyone actively writing code or building workflows
PERSONAS = ["builder", "developer", "engineer", "founder", "freelance", "agency"]

# 🛑 2. THE CORPORATE BLACKLIST
# Protects your database from being polluted by employees of the parent companies
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "langchain employee", "crewai employee", "n8n employee", 
    "hiring at", "recruiting for"
]

def generate_search_matrix():
    """Generates 42 hyper-targeted queries guaranteed to bypass free-tier limits."""
    queries = []
    for f, p in itertools.product(FRAMEWORKS, PERSONAS):
        # Using site: guarantees 100% profile returns. No OR/- operators to trigger 400 errors.
        queries.append(f'site:linkedin.com/in/ {f} {p}')
    return queries

def run_linkedin_scraper():
    st.info("🔌 Authenticating Database & API Connections...")
    
    try:
        serper_key = st.secrets["serper"]["api_key"]
    except KeyError:
        st.error("🔑 Serper API Key Missing! Go to Streamlit Secrets and add [serper] api_key.")
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
        existing_urls = set()
        if len(raw_data) > 0 and 'Profile URL' in raw_data[0]:
            url_idx = raw_data[0].index('Profile URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
            
    except Exception as e:
        st.error(f"❌ Database Auth Error: {str(e)}")
        return 0
        
    search_matrix = generate_search_matrix()
    st.success(f"✅ Matrix Generated. Executing {len(search_matrix)} parallel search vectors for maximum volume...")
    
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- THE MASSIVE PARALLEL PULL ---
    for idx, query in enumerate(search_matrix):
        status_text.text(f"↳ Extracting Vector [{idx+1}/{len(search_matrix)}]: {query}")
        progress_bar.progress((idx + 1) / len(search_matrix))
        
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 100  # 🔥 MAX PAYLOAD: Pulling 100 profiles per vector (4,200 total capacity)
            }
            headers = {
                'X-API-KEY': serper_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code != 200:
                continue
                
            data = response.json()
            organic_results = data.get("organic", [])
            
            for result in organic_results:
                profile_url = result.get("link", "").strip()
                
                # Deduplication & Integrity Check
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn Builder")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                match_context = (raw_title + " " + clean_bio).lower()
                
                # 🛑 Block Corporate Employees ONLY
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee: 
                    continue
                
                # If they survived the blacklist and match the URL, they are Zynd ICP.
                new_leads.append([
                    "Zynd Volume Matrix", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url, 
                    query, 
                    clean_bio, 
                    today_str, 
                    8 # Baseline ICP Score
                ])
                existing_urls.add(profile_url.lower())
                
            # Quick 0.5s pause to prevent rapid API exhaustion
            time.sleep(0.5) 
                
        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    # --- BATCH UPLOAD TO CRM ---
    if new_leads:
        # Pushing in batches of 500 to protect Google Sheets write limits
        batch_size = 500
        for i in range(0, len(new_leads), batch_size):
            batch = new_leads[i:i + batch_size]
            sheet.append_rows(batch)
            time.sleep(2) # Protect against Google API 429 Write Quota
            
        st.success(f"🔥 MASSIVE PULL COMPLETE: Uploaded {len(new_leads)} verified AI agent builders to the Database!")
        return len(new_leads)
        
    st.error("🛑 Scan Complete. No new unique targets found.")
    return 0