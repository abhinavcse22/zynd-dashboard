import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🎯 High-intent search queries matching your exact cohort's signal matrix
KEYWORDS = [
    "LangGraph stuck",
    "CrewAI framework",
    "n8n AI workflow",
    "monetize AI agent",
    "MCP server tools"
]

def run_linkedin_scraper():
    # 1. Secure Credential Extraction
    try:
        apify_token = st.secrets["apify"]["api_token"]
    except KeyError:
        raise Exception("🔑 Apify Token Missing! Go to Streamlit Cloud Settings -> Secrets and add your key inside [apify] api_token.")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # 2. Automated Ledger Validation
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("LinkedIn Leads")
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open_by_key(SHEET_ID).add_worksheet(title="LinkedIn Leads", rows="1000", cols="9")
        sheet.append_row(["Source", "Platform", "Username/Name", "Profile URL", "Post URL", "Query Used", "Snippet", "Date Found", "Lead Score"])
    
    # Extract existing URLs to prevent duplicate entries completely
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0:
        try:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
        except ValueError:
            pass 

    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 3. Synchronous Query Distribution Loop
    for keyword in KEYWORDS:
        actor_id = "harvestapi/linkedin-post-search"
        api_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={apify_token}"
        
        # ⚠️ CRITICAL CORRECTION: Exact keys required by the Apify endpoint mapping
        payload = {
            "searchQueries": [keyword],
            "maxPosts": 5,             # Corrected field constraint mapping
            "postedLimit": "week",     # Corrected temporal constraint range enum
            "sortBy": "date"
        }
        
        try:
            # Setting a 45s execution ceiling to accommodate platform spikes safely
            response = requests.post(api_url, json=payload, timeout=45)
            
            if response.status_code in [200, 201]:
                items = response.json()
                if isinstance(items, list):
                    for item in items:
                        # Parse out individual tracking metrics based on output dataset signatures
                        post_url = item.get("linkedinUrl") or item.get("url") or ""
                        post_url_clean = str(post_url).strip()
                        
                        if not post_url_clean or post_url_clean.lower() in existing_urls:
                            continue
                            
                        # Extract deep nested author attributes safely
                        author_obj = item.get("author", {})
                        author_name = author_obj.get("name") or "LinkedIn Builder"
                        profile_url = author_obj.get("linkedinUrl") or post_url_clean
                        
                        text_snippet = item.get("text") or ""
                        text_clean = str(text_snippet).replace('\n', ' ')[:500]
                        
                        # Apply high prioritization variables to builders dealing with bottlenecks
                        score = 9 if any(kw in keyword.lower() for kw in ["stuck", "monetize"]) else 7
                        
                        new_leads.append([
                            "Apify Cloud Engine", 
                            "LinkedIn", 
                            author_name, 
                            profile_url, 
                            post_url_clean, 
                            keyword, 
                            text_clean, 
                            today_str, 
                            score
                        ])
                        existing_urls.add(post_url_clean.lower())
                        
            # Short defensive breather to manage rate limits cleanly
            time.sleep(1.0)
            
        except Exception:
            continue

    # 4. Atomic Block Insertion
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0