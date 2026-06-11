import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🛑 Corporate Exclusions (Processed strictly in Python to save API compliance)
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "langchain employee", "crewai employee", "n8n employee",
    "hiring at", "recruiting for", "talent acquisition", "human resources",
    "microsoft", "google", "meta", "aws", "amazon"
]

# 🎯 ICP Inclusions (Processed strictly in Python to bypass the API paywall)
WHITELIST_WORDS = [
    "founder", "co-founder", "ceo", "cto", "owner", "indie", "hacker", 
    "agency", "solopreneur", "builder", "creator", "stealth", "consultant",
    "freelancer", "partner"
]

def generate_clean_queries():
    """Generates pure, operator-free text streams acceptable by Serper Free Tier."""
    frameworks = ["LangGraph", "CrewAI", "n8n", "Phidata", "MCP server"]
    personas = ["founder", "builder", "agency", "indie"]
    regions = ["US", "UK", "Remote", "Europe", "India", "Canada", "APAC"]
    
    queries = []
    # Core structural string generation
    for f in frameworks:
        for p in personas:
            for r in regions:
                queries.append(f"linkedin.com/in {f} {p} {r}")
                
    # Add high-intent action variations
    for f in frameworks:
        queries.append(f"linkedin.com/in built with {f}")
        queries.append(f"linkedin.com/in developed using {f}")
        
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
        existing_urls = set()
        if len(raw_data) > 0 and 'Profile URL' in raw_data[0]:
            url_idx = raw_data[0].index('Profile URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
            
    except Exception as e:
        st.error(f"❌ Database Initialization Error: {str(e)}")
        return 0
        
    # Generate the sequential query stack
    all_queries = generate_clean_queries()
    
    # Cap total execution per run to keep processing times responsive (~3-4 minutes)
    execution_stack = all_queries[:60] 
    
    st.success(f"✅ Safe Matrix Formed. Deploying {len(execution_stack)} execution vectors sequentially...")
    
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, query in enumerate(execution_stack):
        status_text.text(f"Processing Vector [{idx+1}/{len(execution_stack)}]: {query}")
        progress_bar.progress((idx + 1) / len(execution_stack))
        
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 40  # Balanced payload density for clean parsing
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
                profile_url = result.get("link", "").strip()
                
                # Strict LinkedIn Profile Verification and Local Deduplication
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn User")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                match_context = (raw_title + " " + clean_bio).lower()
                
                # 🛑 Client-Side Filter 1: Drop Corporate Employees
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee: 
                    continue
                
                # 🎯 Client-Side Filter 2: Verify Builder/Founder Status
                is_target = False
                for word in WHITELIST_WORDS:
                    if word in match_context:
                        is_target = True
                        break
                if not is_target:
                    continue
                
                new_leads.append([
                    "Serper Free Matrix", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url, 
                    query, 
                    clean_bio, 
                    today_str, 
                    9
                ])
                existing_urls.add(profile_url.lower())
                
            # 🛡️ Mandatory Pacing Delay: Prevents hitting the 40 requests/min free tier cap
            time.sleep(2.5)
                
        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    # --- ATOMIC BATCH RECORD ENTRY ---
    if new_leads:
        batch_size = 200
        for i in range(0, len(new_leads), batch_size):
            batch = new_leads[i:i + batch_size]
            sheet.append_rows(batch)
            time.sleep(1.5)
            
        st.success(f"🎉 Pipeline Complete! Injected {len(new_leads)} unique builders into the tracking ledger.")
        return len(new_leads)
        
    st.error("🛑 Extraction Window Finalized. 0 new unique records met criteria.")
    return 0