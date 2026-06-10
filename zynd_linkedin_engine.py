import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
from googlesearch import search

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 1. Google Dorks (Deep index, but strict rate limits)
GOOGLE_QUERIES = [
    'site:linkedin.com/posts/ "LangGraph" (stuck OR error)',
    'site:linkedin.com/posts/ "CrewAI" (framework OR issue)',
    'site:linkedin.com/posts/ "n8n" "workflow automation"'
]

# 2. DuckDuckGo Queries (Bypasses site filters using URL matches)
DDG_QUERIES = [
    '"linkedin.com/posts/" "LangGraph" error',
    '"linkedin.com/posts/" "CrewAI" framework',
    '"linkedin.com/posts/" "n8n" automation'
]

def run_linkedin_scraper():
    # DIAGNOSTIC UI LOGGING
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
        if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
            
    except Exception as e:
        st.error(f"❌ Database Auth Error: {str(e)}")
        return 0
        
    st.success("✅ Database Secure. Booting Dual-Scrape Engines...")
    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # --- ENGINE 1: DUCKDUCKGO (Fastest, avoids IP Bans) ---
    st.write("🦆 **Booting Engine 1: DuckDuckGo...**")
    try:
        with DDGS() as ddgs:
            for query in DDG_QUERIES:
                st.text(f"↳ Scanning: {query}")
                results = list(ddgs.text(query, max_results=3))
                
                if not results:
                    st.text("    ↳ 0 results found.")
                    continue
                    
                for result in results:
                    post_url = str(result.get('href', '')).strip()
                    if "linkedin.com" not in post_url.lower() or post_url.lower() in existing_urls:
                        continue
                        
                    title = str(result.get('title', 'LinkedIn Builder'))
                    name = title.split(' | ')[0].split(' on LinkedIn')[0].strip()
                    clean_text = str(result.get('body', '')).replace('\n', ' ')[:500]
                    
                    new_leads.append(["DuckDuckGo", "LinkedIn", name, post_url, post_url, query, clean_text, today_str, 8])
                    existing_urls.add(post_url.lower())
                    st.text(f"    ↳ ✅ Sniped Profile: {name}")
                    
                time.sleep(2)
    except Exception as e:
        st.warning(f"⚠️ DuckDuckGo Blocked: {str(e)}")

    # --- ENGINE 2: GOOGLE (Deeper, highly accurate) ---
    st.write("🌐 **Booting Engine 2: Google Native...**")
    try:
        for query in GOOGLE_QUERIES:
            st.text(f"↳ Scanning: {query}")
            # sleep_interval protects Streamlit's IP from instant bans
            for result in search(query, num_results=3, sleep_interval=4, advanced=True):
                post_url = getattr(result, 'url', '').strip()
                
                if not post_url or "linkedin.com" not in post_url.lower() or post_url.lower() in existing_urls:
                    continue
                    
                title = getattr(result, 'title', 'LinkedIn Builder')
                name = title.split(' on LinkedIn')[0].split('|')[0].strip()
                clean_text = str(getattr(result, 'description', '')).replace('\n', ' ')[:500]
                
                new_leads.append(["Google Engine", "LinkedIn", name, post_url, post_url, query, clean_text, today_str, 8])
                existing_urls.add(post_url.lower())
                st.text(f"    ↳ ✅ Sniped Profile: {name}")
                
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ Google Blocked: Streamlit Cloud IP is currently rate-limited (HTTP 429).")
        else:
            st.warning(f"⚠️ Google Engine Error: {str(e)}")

    # --- FINAL PUSH ---
    if new_leads:
        st.success(f"⬆️ Uploading {len(new_leads)} fresh leads to Database...")
        sheet.append_rows(new_leads)
        return len(new_leads)
        
    st.error("🛑 Scan Complete. 0 new leads found.")
    st.info("💡 If you see yellow warning boxes above, the cloud servers are temporarily blocking the Streamlit IP address. Wait an hour and try again.")
    return 0