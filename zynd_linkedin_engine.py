import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import requests

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# High-intent keyword arrays mapped cleanly to the Zynd 14-Day Cohort target personas
KEYWORDS = [
    "LangGraph stuck",
    "CrewAI framework",
    "n8n AI workflow",
    "built an AI agent"
]

def run_linkedin_scraper():
    # 1. Secure Credential Check: Pulls cleanly from Streamlit cloud secrets block
    try:
        apify_token = st.secrets["apify"]["api_token"]
    except KeyError:
        raise Exception("🔑 Apify API Token missing! Please add your token into the Streamlit Cloud Secrets management panel under ['apify']['api_token'].")

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
    if len(raw_data) > 0:
        try:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
        except ValueError:
            pass 

    new_leads = []
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 2. Iterate through core intent signals via targeted API payloads
    for keyword in KEYWORDS:
        actor_id = "harvestapi/linkedin-post-search"
        # Using run-sync-get-dataset-items allows pulling structured JSON inside a single request window
        api_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={apify_token}"
        
        payload = {
            "searchQueries": [keyword],
            "count": 5,
            "lookbackDays": 2
        }
        
        try:
            # Set a 45s threshold to prevent Streamlit worker timeouts
            response = requests.post(api_url, json=payload, timeout=45)
            
            if response.status_code in [200, 201]:
                items = response.json()
                if isinstance(items, list):
                    for item in items:
                        post_url = item.get("postUrl") or item.get("url") or ""
                        post_url_clean = str(post_url).strip()
                        
                        if not post_url_clean or post_url_clean.lower() in existing_urls:
                            continue
                            
                        author_name = item.get("authorName") or item.get("author", {}).get("name") or "LinkedIn Builder"
                        profile_url = item.get("authorProfileUrl") or item.get("author", {}).get("url") or post_url_clean
                        text_snippet = item.get("text") or item.get("body") or ""
                        text_clean = str(text_snippet).replace('\n', ' ')[:500]
                        
                        # High-priority scaling for acute pain points
                        score = 9 if "stuck" in keyword.lower() else 7
                        
                        new_leads.append([
                            "Apify Extraction Node", 
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
        except Exception:
            continue # Skip any timed-out query execution safely to keep the loop moving

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0