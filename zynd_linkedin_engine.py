import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# 🎯 Reusing the exact same reliable scraper you use in zynd_content_engine.py!
from googlesearch import search

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🔥 Deep Google Dorks targeting LinkedIn's post index directly
LINKEDIN_DORKS = [
    'site:linkedin.com/posts/ "LangGraph" (stuck OR error OR issue)',
    'site:linkedin.com/posts/ "CrewAI" (framework OR slow OR help)',
    'site:linkedin.com/posts/ "n8n" "workflow"',
    'site:linkedin.com/posts/ "built an AI agent" "GitHub"'
]

def run_linkedin_scraper():
    # 1. Standard Cloud Database Connection
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("LinkedIn Leads")
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_key(SHEET_ID).add_worksheet(title="LinkedIn Leads", rows="1000", cols="9")
        sheet.append_row(["Source", "Platform", "Username/Name", "Profile URL", "Post URL", "Query Used", "Snippet", "Date Found", "Lead Score"])
    
    # Extract existing URLs to prevent duplicate scraping
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0 and 'Post URL' in raw_data[0]:
        try:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
        except ValueError:
            pass 

    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 2. Native Google Search Extraction (Bypassing Apify entirely)
    for query in LINKEDIN_DORKS:
        try:
            # advanced=True returns objects with titles and descriptions (Google's snippets)
            for result in search(query, num_results=6, advanced=True):
                post_url = getattr(result, 'url', '').strip()
                
                # Verify it's a real post and not a duplicate
                if not post_url or post_url.lower() in existing_urls or "linkedin.com/posts/" not in post_url.lower():
                    continue
                    
                # Clean Google's Title (Google usually indexes as: "John Doe on LinkedIn: I built...")
                title = getattr(result, 'title', 'LinkedIn Builder')
                name = title.split(' on LinkedIn')[0].split('|')[0].strip()
                
                # Extract the post snippet
                snippet = getattr(result, 'description', '')
                clean_text = str(snippet).replace('\n', ' ')[:500]
                
                score = 9 if any(kw in query.lower() for kw in ["stuck", "error", "issue"]) else 7
                
                new_leads.append([
                    "Google Native Engine", 
                    "LinkedIn", 
                    name, 
                    post_url, # Fallback to post URL since we extract via post indices
                    post_url, 
                    query, 
                    clean_text, 
                    today_str, 
                    score
                ])
                existing_urls.add(post_url.lower())
                
            # 🛡️ Pacing: Wait 3 seconds between Google searches so Streamlit doesn't get rate-limited
            time.sleep(3.0)
            
        except Exception as e:
            # If Google temporarily blocks the server (HTTP 429), break safely and save what we have
            if "429" in str(e):
                break
            continue

    # 3. Push to Master CRM
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0