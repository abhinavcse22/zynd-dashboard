import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 Yahoo uses Bing's index, but its firewall allows Cloud Datacenter IPs
YAHOO_DORKS = [
    'site:linkedin.com/in/ "LangGraph"',
    'site:linkedin.com/in/ "CrewAI"',
    'site:linkedin.com/in/ "n8n" "workflow"',
    'site:linkedin.com/in/ "built an AI agent"'
]

# Standard desktop headers to bypass basic checks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        
    st.success("✅ Database Secure. Booting Yahoo Proxy Sniper...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- YAHOO NATIVE ENGINE ---
    for query in YAHOO_DORKS:
        st.text(f"↳ Scanning Yahoo Index: {query}")
        try:
            # Route the request through Yahoo to bypass the Bing/Google CAPTCHA walls
            url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}"
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code != 200:
                st.warning(f"    ↳ Yahoo returned status code {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            links_found = False
            for a_tag in soup.find_all('a'):
                href = str(a_tag.get('href', '')).strip()
                
                # Verify it contains a LinkedIn profile route
                if "linkedin.com/in/" not in href.lower():
                    continue
                    
                # 🪄 YAHOO DECODER RING: Yahoo wraps URLs in tracking codes (e.g., RU=https://linkedin...)
                if "RU=" in href:
                    try:
                        href = href.split("RU=")[1].split("/RK=")[0]
                        href = urllib.parse.unquote(href)
                    except Exception:
                        pass # Fallback to raw string if splitting fails
                
                # Final deduplication check after unwrapping the URL
                if href.lower() in existing_urls:
                    continue
                    
                links_found = True
                
                # Extract the Name from the clean URL slug
                try:
                    url_path = href.lower().split("/in/")[1].split("/")[0]
                    raw_name = "".join([i for i in url_path if not i.isdigit()])
                    name = raw_name.replace("-", " ").strip().title()
                except Exception:
                    name = "LinkedIn Builder"
                
                new_leads.append([
                    "Yahoo Proxy Engine", 
                    "LinkedIn", 
                    name, 
                    href, 
                    href, 
                    query, 
                    "Builder captured via Yahoo OSINT proxy bypass.", 
                    today_str, 
                    9
                ])
                existing_urls.add(href.lower())
                st.text(f"    ↳ ✅ Sniped Profile: {name}")
                
            if not links_found:
                st.text("    ↳ ⚠️ Yahoo returned 0 profiles for this query.")
                
            # Rest for 4 seconds between searches to prevent Yahoo from catching on
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