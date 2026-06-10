import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🎯 Free-Tier Friendly Raw Queries (Broad terms to maximize return payload size)
SERPER_DORKS = [
    'linkedin.com/in LangGraph',
    'linkedin.com/in CrewAI',
    'linkedin.com/in n8n workflow',
    'linkedin.com/in AI automation agency',
    'linkedin.com/in building AI agents',
    'linkedin.com/in MCP server',
    'linkedin.com/in LangChain agent'
]

# 🛑 Employee Blacklist: Only block people employed by the core software providers
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "at n8n", "at openai", "at anthropic",
    "langchain employee", "crewai employee", "n8n employee"
]

# 🎯 Founder/Builder Whitelist: Python forces matches to fit your exact cohort personas
WHITELIST_WORDS = [
    "founder", "co-founder", "ceo", "cto", "owner", "indie", "hacker", 
    "agency", "freelancer", "solopreneur", "builder", "creator", "stealth"
]

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
        
    st.success("✅ Secure. Booting Target Matching Pipeline...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    for query in SERPER_DORKS:
        st.text(f"↳ Gathering Raw Payload: {query}")
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 50  # 🔥 Maximizing pull capacity to 50 results per query block!
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
            
            if not organic_results:
                continue

            for result in organic_results:
                profile_url = result.get("link", "").strip()
                
                # Link Verification & Deduplication
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn Builder")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                
                # Normalize context strings for deep filtering
                match_context = (raw_title + " " + clean_bio).lower()
                
                # 🛑 Filter 1: Check Employee Blacklist
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in match_context:
                        is_employee = True
                        break
                if is_employee:
                    continue  # Skip corporate platform staff
                
                # 🎯 Filter 2: Enforce Target Whitelist (Isolates founders/builders)
                is_target_persona = False
                for word in WHITELIST_WORDS:
                    if word in match_context:
                        is_target_persona = True
                        break
                if not is_target_persona:
                    continue  # Skip users who are not founders or active builders
                
                new_leads.append([
                    "Serper Free Engine", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url, 
                    query, 
                    clean_bio, 
                    today_str, 
                    9  # Premium lead score matching monetization sprint metrics
                ])
                existing_urls.add(profile_url.lower())
                st.text(f"    ↳ ✅ Sniped Target Founder: {name}")
                
            time.sleep(1.0)
                
        except Exception as e:
            st.warning(f"⚠️ Search Error: {str(e)}")

    if new_leads:
        st.success(f"I/O Update: Uploading {len(new_leads)} highly-targeted founders to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. No new unique targets found in this execution window.")
    return 0