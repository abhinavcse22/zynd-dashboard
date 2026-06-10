import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from googlesearch import search

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 Simplified queries to prevent Google from hiding results
GOOGLE_DORKS = [
    'site:linkedin.com/in/ LangGraph',
    'site:linkedin.com/in/ CrewAI',
    'site:linkedin.com/in/ n8n workflow',
    'site:linkedin.com/in/ "AI agent" developer'
]

def run_linkedin_scraper():
    st.info("🔌 Authenticating Database Connection...")
    
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
        
    st.success("✅ Database Secure. Booting Raw URL Sniper...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- RAW URL EXTRACTION ENGINE ---
    for query in GOOGLE_DORKS:
        st.text(f"↳ Deep Scanning Index: {query}")
        try:
            # 🛑 CRITICAL FIX: advanced=True is REMOVED. 
            # We now only ask for raw string URLs, which Google cannot break.
            results_found = False
            
            for url in search(query, num_results=10, sleep_interval=2):
                results_found = True
                
                # Ensure it's a string
                profile_url = str(url).strip()
                
                if "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                    
                # 🪄 MAGIC NAME EXTRACTOR
                # Takes "https://linkedin.com/in/john-doe-12345/" and extracts "John Doe"
                try:
                    url_path = profile_url.lower().split("/in/")[1].split("/")[0]
                    # Strip out numbers and ID tags
                    raw_name = "".join([i for i in url_path if not i.isdigit()])
                    name = raw_name.replace("-", " ").strip().title()
                except Exception:
                    name = "LinkedIn Builder"
                
                new_leads.append([
                    "Google Raw URL Engine", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url, 
                    query, 
                    "High-intent framework builder extracted via raw index routing.", 
                    today_str, 
                    9
                ])
                existing_urls.add(profile_url.lower())
                st.text(f"    ↳ ✅ Sniped Builder: {name}")
                
            if not results_found:
                st.text("    ↳ ⚠️ Google returned 0 URLs for this query.")
                
        except Exception as e:
            if "429" in str(e):
                st.warning("⚠️ Google Rate Limit Hit. Pausing engine to protect IP.")
                break 
            else:
                st.warning(f"⚠️ Search Error: {str(e)}")

    # --- FINAL PUSH ---
    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} fresh leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    return 0