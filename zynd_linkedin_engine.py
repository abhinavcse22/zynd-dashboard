import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🛑 Strict Corporate Blacklist (Protects the database)
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "langchain employee", "crewai employee", "n8n employee",
    "hiring at", "recruiting for", "talent acquisition",
    "microsoft", "google", "meta", "aws", "amazon"
]

def generate_clean_queries():
    """Generates pure text streams to bypass API blocks while expanding the net massively."""
    frameworks = ["LangGraph", "CrewAI", "n8n", "Phidata", "MCP server"]
    personas = ["founder", "builder", "agency", "indie hacker"]
    # Expanded regions forces Google to dump entirely new buckets of users
    regions = ["San Francisco", "New York", "London", "Remote", "India", "Berlin", "Canada", "Singapore"]
    
    queries = []
    for f in frameworks:
        for p in personas:
            for r in regions:
                queries.append(f"linkedin.com/in/ {f} {p} {r}")
                
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
        
    all_queries = generate_clean_queries()
    
    # 💥 Executing 80 vectors. At 100 results per vector, this pulls 8,000 raw links.
    execution_stack = all_queries[:80] 
    
    st.success(f"✅ Safe Matrix Formed. Deploying {len(execution_stack)} maximum-capacity vectors...")
    
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, query in enumerate(execution_stack):
        status_text.text(f"Extracting Vector [{idx+1}/{len(execution_stack)}]: {query}")
        progress_bar.progress((idx + 1) / len(execution_stack))
        
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 100  # 🔥 MAXIMAL PAYLOAD
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
                
                # Strict Profile Validation
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn User")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                match_context = (raw_title + " " + clean_bio).lower()
                
                # 🛑 Delete Corporate Employees
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee: 
                    continue
                
                # 🔥 Whitelist Removed: If they are a profile, have the keyword, and aren't an employee = LEAD.
                new_leads.append([
                    "Serper Volume Net", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url, 
                    query, 
                    clean_bio, 
                    today_str, 
                    8
                ])
                existing_urls.add(profile_url.lower())
                
            # Keep the API compliant pacing
            time.sleep(2.0)
                
        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    if new_leads:
        batch_size = 300
        for i in range(0, len(new_leads), batch_size):
            batch = new_leads[i:i + batch_size]
            sheet.append_rows(batch)
            time.sleep(2)
            
        st.success(f"🎉 FLOODGATES OPENED: Injected {len(new_leads)} unique builders into the tracking ledger.")
        return len(new_leads)
        
    st.error("🛑 Extraction Window Finalized. 0 new unique records met criteria.")
    return 0