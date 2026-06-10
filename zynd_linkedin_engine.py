import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from googlesearch import search

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 The Fix: Target Public Profiles (/in/) instead of Posts.
# Google indexes Profiles perfectly, but hides Posts from search engines.
GOOGLE_DORKS = [
    'site:linkedin.com/in/ "LangGraph" (engineer OR builder OR developer)',
    'site:linkedin.com/in/ "CrewAI" (founder OR developer OR engineer)',
    'site:linkedin.com/in/ "n8n" "AI agent"',
    'site:linkedin.com/in/ "building an AI agent"'
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
        
        # Extract existing URLs to prevent duplicates
        raw_data = sheet.get_all_values()
        existing_urls = set()
        if len(raw_data) > 0 and 'Profile URL' in raw_data[0]:
            url_idx = raw_data[0].index('Profile URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
            
    except Exception as e:
        st.error(f"❌ Database Auth Error: {str(e)}")
        return 0
        
    st.success("✅ Database Secure. Booting Google Profile Sniper...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- GOOGLE NATIVE ENGINE ---
    for query in GOOGLE_DORKS:
        st.text(f"↳ Deep Scanning Index: {query}")
        try:
            # advanced=True gets us the titles (names) and descriptions (bios)
            for result in search(query, num_results=6, sleep_interval=3, advanced=True):
                profile_url = getattr(result, 'url', '').strip()
                
                # Verify it is a valid LinkedIn profile and not a duplicate
                if not profile_url or "linkedin.com/in/" not in profile_url.lower() or profile_url.lower() in existing_urls:
                    continue
                    
                # Google indexes LinkedIn titles as "First Last - Job Title - Company | LinkedIn"
                raw_title = getattr(result, 'title', 'LinkedIn Lead')
                name = raw_title.split('-')[0].split('|')[0].strip()
                
                # Extract their bio/headline snippet
                raw_desc = getattr(result, 'description', '')
                clean_bio = str(raw_desc).replace('\n', ' ')[:300]
                
                new_leads.append([
                    "Google Profile Engine", 
                    "LinkedIn", 
                    name, 
                    profile_url, 
                    profile_url,  # Duplicated for Post URL column consistency
                    query, 
                    clean_bio, 
                    today_str, 
                    9             # High intent score for matching framework stacks
                ])
                existing_urls.add(profile_url.lower())
                st.text(f"    ↳ ✅ Sniped Builder: {name}")
                
        except Exception as e:
            if "429" in str(e):
                st.warning("⚠️ Google Rate Limit Hit. Pausing engine to protect IP.")
                break # Stop scanning gracefully to prevent a strict server ban
            else:
                st.warning(f"⚠️ Search Error: {str(e)}")

    # --- FINAL PUSH ---
    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} fresh leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    return 0