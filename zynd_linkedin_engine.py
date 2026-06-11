import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import itertools

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 THE SEARCH MATRIX INGREDIENTS
FRAMEWORKS = ["LangGraph", "CrewAI", "n8n", "MCP", "AI agent", "OpenAI Swarm", "Phidata"]
PERSONAS = ["founder", "builder", "CEO", "indie hacker"]
# Appending locations forces Google to bypass its result clustering limits
LOCATIONS = ["San Francisco", "London", "New York", "Remote", "India", "Berlin", "Toronto", "Singapore"]

# 🛑 Employee Blacklist
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "software engineer at", "working at", "employed at", "intern at"
]

# 🎯 Target Whitelist
WHITELIST_WORDS = [
    "founder", "co-founder", "ceo", "cto", "indie", "hacker", 
    "agency", "solopreneur", "builder", "creator", "stealth"
]

def generate_search_matrix():
    """Generates a massive array of hyper-specific queries to bypass Google's clustering limits."""
    queries = []
    # Mix 1: Framework + Persona + Location
    for f, p, l in itertools.product(FRAMEWORKS, PERSONAS, LOCATIONS):
        queries.append(f'linkedin.com/in "{f}" {p} {l}')
    
    # Mix 2: "Built with" variations
    for f in FRAMEWORKS:
        queries.append(f'linkedin.com/in "built with {f}"')
        queries.append(f'linkedin.com/in "using {f}" founder')
        
    # Cap at 100 queries per run to manage execution time (~2 mins) and API credits
    return queries[:100] 

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
    st.success(f"✅ Matrix Generated. Executing {len(search_matrix)} parallel search vectors...")
    
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # UI Elements for long-running task
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, query in enumerate(search_matrix):
        status_text.text(f"↳ Scanning Vector [{idx+1}/{len(search_matrix)}]: {query}")
        progress_bar.progress((idx + 1) / len(search_matrix))
        
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 20  # 20 results per query * 100 queries = 2,000 profiles analyzed
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
                
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn Builder")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                match_context = (raw_title + " " + clean_bio).lower()
                
                # 🛑 Block Employees
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee: continue
                
                # 🎯 Whitelist Founders/Builders
                is_target_persona = False
                for word in WHITELIST_WORDS:
                    if word in match_context:
                        is_target_persona = True
                        break
                if not is_target_persona: continue
                
                new_leads.append([
                    "Serper Matrix Engine", 
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
                
            time.sleep(0.5) # Fast pacing, Serper can handle it
                
        except Exception:
            continue

    progress_bar.empty()
    status_text.empty()

    if new_leads:
        st.success(f"🔥 MASSIVE PULL: Uploading {len(new_leads)} highly-targeted founders to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. No new unique targets found. Try expanding the Matrix LOCATIONS.")
    return 0