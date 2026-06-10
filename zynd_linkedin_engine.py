import time
from datetime import datetime
import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 High-intent profile dorks (Google handles these perfectly via Serper)
SERPER_DORKS = [
    'site:linkedin.com/in/ "LangGraph" (engineer OR builder OR developer)',
    'site:linkedin.com/in/ "CrewAI" (founder OR developer OR engineer)',
    'site:linkedin.com/in/ "n8n" "AI agent"',
    'site:linkedin.com/in/ "building an AI agent"'
]

def run_linkedin_scraper():
    st.info("🔌 Authenticating Database & API Connections...")
    
    # 1. Verify Serper API Key
    try:
        serper_key = st.secrets["serper"]["api_key"]
    except KeyError:
        st.error("🔑 Serper API Key Missing! Go to Streamlit Secrets and add [serper] api_key.")
        return 0

    # 2. Authenticate Google Sheets
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
        
    st.success("✅ Secure. Booting Serper.dev Residential Proxy Engine...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- SERPER GOOGLE API ENGINE ---
    for query in SERPER_DORKS:
        st.text(f"↳ Routing via Residential Proxy: {query}")
        try:
            url = "https://google.serper.dev/search"
            payload = {
                "q": query,
                "num": 10 # Get 10 results per query
            }
            headers = {
                'X-API-KEY': serper_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code != 200:
                st.warning(f"    ↳ API Error: {response.text}")
                continue
                
            data = response.json()
            organic_results = data.get("organic", [])
            
            if not organic_results:
                st.text("    ↳ ⚠️ 0 profiles found for this exact query.")
                continue

            for result in organic_results:
                profile_url = result.get("link", "").strip()
                
                # Verify it's a LinkedIn profile
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                
                # Clean the Name from the Google Title
                raw_title = result.get("title", "LinkedIn Builder")
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                # Get the Bio snippet
                snippet = result.get("snippet", "")
                clean_bio = str(snippet).replace('\n', ' ')[:300]
                
                new_leads.append([
                    "Serper Google API", 
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
                st.text(f"    ↳ ✅ Sniped Profile: {name}")
                
            # Quick pause to be safe, though Serper handles rate limits well
            time.sleep(1.0)
                
        except Exception as e:
            st.warning(f"⚠️ Search Error: {str(e)}")

    # --- FINAL PUSH ---
    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} fresh leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    return 0