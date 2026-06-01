import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# Optimized 2026 keyword arrays designed to capture active profiles and index entries
TWITTER_QUERIES = [
    'site:x.com "AI agent" builder',
    'site:x.com "LangGraph" error OR stuck',
    'site:x.com "CrewAI" issue OR framework',
    'site:x.com "n8n" workflow automation'
]

def run_twitter_scraper():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    
    # Secure row extraction using raw values to bypass header errors completely
    raw_data = sheet.get_all_values()
    existing_urls = set()
    if len(raw_data) > 0:
        try:
            url_idx = raw_data[0].index('Post URL')
            existing_urls = {str(row[url_idx]).lower().strip() for row in raw_data[1:] if len(row) > url_idx}
        except ValueError:
            pass 

    new_leads = []
    ignored_routes = {'home', 'search', 'explore', 'intent', 'share', 'i', 'privacy', 'tos', 'settings', 'about'}
    
    shuffled_queries = TWITTER_QUERIES.copy()
    random.shuffle(shuffled_queries)

    for query in shuffled_queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=15))
                
                if not results:
                    continue
                    
                for result in results:
                    post_url = str(result.get('href', '')).strip()
                    post_url_lower = post_url.lower()
                    
                    if post_url_lower in existing_urls:
                        continue
                    
                    # Intercept any valid x.com or twitter.com base domain
                    if "x.com" not in post_url_lower and "twitter.com" not in post_url_lower:
                        continue
                        
                    # Extract the core handle name cleanly from the primary URL path
                    username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)', post_url)
                    if not username_match:
                        continue
                        
                    username = username_match.group(1).split('?')[0]
                    if username.lower() in ignored_routes:
                        continue
                    
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
                    existing_urls.add(post_url_lower)
            
            # Anti-throttling random delay
            time.sleep(random.uniform(3.0, 5.0)) 
            
        except Exception as e:
            if "402" in str(e) or "ratelimit" in str(e).lower():
                break
            continue

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0
