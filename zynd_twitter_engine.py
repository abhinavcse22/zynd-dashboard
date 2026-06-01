import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Expanded matrix using 2026 search weights (combining both x.com and twitter.com)
TWITTER_QUERIES = [
    '(site:x.com OR site:twitter.com) "building an AI agent" -filter:links',
    '(site:x.com OR site:twitter.com) "LangGraph" "error" OR "stuck"',
    '(site:x.com OR site:twitter.com) "CrewAI" "stuck" OR "issue"',
    '(site:x.com OR site:twitter.com) "n8n workflow" "alternative"'
]

def run_twitter_scraper():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    records = sheet.get_all_records()
    existing_urls = {str(row.get('Post URL', '')) for row in records if row.get('Post URL')}
    new_leads = []
    
    # 1. Anti-Throttle: Shuffle queries so patterns don't emerge on the search engine
    shuffled_queries = TWITTER_QUERIES.copy()
    random.shuffle(shuffled_queries)

    for query in shuffled_queries:
        try:
            # Re-instantiating inside the loop mimics a new guest browser session
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=15))
                
                if not results:
                    continue
                    
                for result in results:
                    post_url = result.get('href', '')
                    
                    if post_url in existing_urls or "/status/" not in post_url: 
                        continue
                    
                    # Regex mapping handles both legacy twitter.com and modern x.com links
                    username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status', post_url)
                    username = username_match.group(1) if username_match else "Unknown"
                    
                    score = 8 if any(kw in query.lower() for kw in ['error', 'stuck', 'issue']) else 6
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
            
            # Defensive variable pacing to shield our IP layout
            time.sleep(random.uniform(4.0, 7.0)) 
            
        except Exception as e:
            # If rate-limited, skip quietly or show soft warning instead of hard crash
            if "402" in str(e) or "ratelimit" in str(e).lower():
                print("⚠️ Search engine requested temporary pacing cooldown.")
                break
            continue

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
