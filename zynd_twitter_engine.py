import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Changed to twitter.com - search engines index the old URL structure much better
TWITTER_QUERIES = [
    'site:twitter.com/status "building an AI agent"',
    'site:twitter.com/status "LangGraph" "error"',
    'site:twitter.com/status "n8n workflow"',
    'site:twitter.com/status "CrewAI"'
]

def run_twitter_scraper():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    new_leads = []
    errors_caught = []
    
    ddgs = DDGS()

    for query in TWITTER_QUERIES:
        try:
            # We wrap this in a try block to catch exact IP bans
            results = ddgs.text(query, max_results=10)
            
            if not results:
                continue
                
            for result in results:
                post_url = result.get('href', '')
                
                if post_url in existing_urls or "/status/" not in post_url: 
                    continue
                
                username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status', post_url)
                username = username_match.group(1) if username_match else "Unknown"
                
                score = 8 if 'stuck' in query or 'error' in query else 6
                date_str = datetime.now().strftime('%Y-%m-%d')
                clean_text = str(result.get('body', '')).replace('\n', ' ')[:500]
                
                new_leads.append([
                    "Ghost Search", 
                    "Twitter", 
                    f"@{username}", 
                    f"https://x.com/{username}", 
                    post_url, 
                    query, 
                    clean_text, 
                    date_str, 
                    score
                ])
                existing_urls.add(post_url)
            
            time.sleep(3) 
            
        except Exception as e:
            # Catch the exact error from DuckDuckGo and save it
            errors_caught.append(f"Query failed: {str(e)}")

    # If the search engine blocked us, force the dashboard to show the error
    if errors_caught:
        raise Exception(" | ".join(errors_caught))

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
