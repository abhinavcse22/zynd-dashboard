import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# We use advanced Google Dorks (site:x.com/status) to force the search engine 
# to only return specific tweets about these topics.
TWITTER_QUERIES = [
    'site:x.com/status "building an AI agent"',
    'site:x.com/status "my AI agent"',
    'site:x.com/status "LangGraph" "stuck"',
    'site:x.com/status "n8n workflow"',
    'site:x.com/status "built an MCP"'
]

def run_twitter_scraper():
    # 1. Connect to Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    new_leads = []
    
    print("👻 Booting up Ghost Engine (Token-Free Scraper)...")
    ddgs = DDGS()

    # 2. Scrape the Search Engine Index
    for query in TWITTER_QUERIES:
        try:
            # Bypass Twitter entirely, scrape the search engine directly
            results = ddgs.text(query, max_results=15)
            
            if not results:
                continue
                
            for result in results:
                post_url = result.get('href', '')
                
                # Only save actual tweet URLs, ignore profile pages
                if post_url in existing_urls or "/status/" not in post_url: 
                    continue
                
                # Extract the username right out of the URL
                username_match = re.search(r'x\.com/([^/]+)/status', post_url)
                if not username_match:
                    username_match = re.search(r'twitter\.com/([^/]+)/status', post_url)
                    
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
                    query.replace('site:x.com/status ', ''), 
                    clean_text, 
                    date_str, 
                    score
                ])
                existing_urls.add(post_url)
            
            # Short delay so DuckDuckGo doesn't get mad
            time.sleep(2) 
            
        except Exception as e:
            print(f"Failed to scrape query {query}: {e}")

    # 3. Push to Database
    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
