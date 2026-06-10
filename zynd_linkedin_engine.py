import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 Bing-Optimized Profile Dorks
BING_DORKS = [
    'site:linkedin.com/in/ "LangGraph"',
    'site:linkedin.com/in/ "CrewAI"',
    'site:linkedin.com/in/ "n8n" "workflow"',
    'site:linkedin.com/in/ "built an AI agent"'
]

# Stealth headers to mimic a real Mac user on Chrome
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

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
        
    st.success("✅ Database Secure. Booting Bing Stealth Sniper...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- BING NATIVE ENGINE ---
    for query in BING_DORKS:
        st.text(f"↳ Scanning Bing Index: {query}")
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            response = requests.get(url, headers=HEADERS, timeout=10)
            
            if response.status_code != 200:
                st.warning(f"    ↳ Bing returned status code {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract every single link from the search results
            links_found = False
            for a_tag in soup.find_all('a'):
                href = str(a_tag.get('href', '')).strip()
                
                # Check if the link goes to a LinkedIn profile
                if "linkedin.com/in/" not in href.lower() or href.lower() in existing_urls:
                    continue
                    
                links_found = True
                
                # Extract the Name from the raw URL slug natively
                try:
                    url_path = href.lower().split("/in/")[1].split("/")[0]
                    # Strip out ID numbers to leave just the name
                    raw_name = "".join([i for i in url_path if not i.isdigit()])
                    name = raw_name.replace("-", " ").strip().title()
                except Exception:
                    name = "LinkedIn Builder"
                
                new_leads.append([
                    "Bing Native Engine", 
                    "LinkedIn", 
                    name, 
                    href, 
                    href, 
                    query, 
                    "Builder captured via Bing native profile extraction.", 
                    today_str, 
                    9
                ])
                existing_urls.add(href.lower())
                st.text(f"    ↳ ✅ Sniped Profile: {name}")
                
            if not links_found:
                st.text("    ↳ ⚠️ Bing returned 0 profiles for this query.")
                
            # Rest for 4 seconds between searches to mimic human pacing
            time.sleep(4.0)
                
        except Exception as e:
            st.warning(f"⚠️ Search Error: {str(e)}")

    # --- FINAL PUSH ---
    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} fresh leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    return 0