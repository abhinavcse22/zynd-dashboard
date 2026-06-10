import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 "Caveman" Queries: No 'site:', no quotes, no advanced operators.
# This completely bypasses the Serper.dev free tier paywall.
SERPER_DORKS = [
    'linkedin.com/in LangGraph founder',
    'linkedin.com/in LangGraph indie hacker',
    'linkedin.com/in built with LangGraph',
    'linkedin.com/in CrewAI founder',
    'linkedin.com/in CrewAI indie hacker',
    'linkedin.com/in built with CrewAI',
    'linkedin.com/in n8n AI Automation',
    'linkedin.com/in n8n founder',
    'linkedin.com/in building an AI agent',
    'linkedin.com/in MCP server founder'
]

# 🛑 The Employee Blacklist (Python handles what the API won't)
BLACKLIST_PHRASES = [
    "at langchain", "at crewai", "founder of crewai", "at n8n", 
    "working at", "employed at", "software engineer at langchain",
    "software engineer", "developer at"
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
        
    st.success("✅ Secure. Booting Raw Text API Pipeline...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    for query in SERPER_DORKS:
        st.text(f"↳ Routing Raw Query: {query}")
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 40  # Safely pulling 40 results per simple query
            }
            headers = {
                'X-API-KEY': serper_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code != 200:
                st.warning(f"    ↳ API Error: {response.text}")
                continue
                
            data = response.json()
            organic_results = data.get("organic", [])
            
            if not organic_results:
                st.text("    ↳ ⚠️ 0 results returned from Google.")
                continue

            for result in organic_results:
                profile_url = result.get("link", "").strip()
                
                # 🛡️ Because we dropped 'site:', we MUST force Python to check if the link is actually LinkedIn!
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                raw_title = result.get("title", "LinkedIn Builder")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                
                # 🛑 Python executes the Blacklist Filter
                is_employee = False
                for blacklisted in BLACKLIST_PHRASES:
                    if blacklisted in clean_bio.lower() or blacklisted in raw_title.lower():
                        is_employee = True
                        break
                        
                if is_employee:
                    continue  # Skip this person, they triggered the blacklist
                
                new_leads.append([
                    "Serper Free Engine", 
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
                st.text(f"    ↳ ✅ Sniped Verified Founder: {name}")
                
            time.sleep(1.0)
                
        except Exception as e:
            st.warning(f"⚠️ Search Error: {str(e)}")

    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} highly-targeted leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    return 0