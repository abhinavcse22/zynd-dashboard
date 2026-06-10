import time
from datetime import datetime
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from duckduckgo_search import DDGS
import re
import random

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

# 🎯 The Phrase Hack: Drop 'site:' completely so DuckDuckGo stops blocking the results
LINKEDIN_QUERIES = [
    '"linkedin.com/posts" "AI agent" builder',
    '"linkedin.com/posts" "LangGraph" error',
    '"linkedin.com/posts" "CrewAI" framework',
    '"linkedin.com/posts" "n8n" workflow automation'
]

def run_linkedin_scraper():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    # 🛡️ Safe Tab Auto-Initialization
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("LinkedIn Leads")
    except gspread.exceptions.WorksheetNotFound:
        # If tab is missing, create it instantly without throwing an error
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
    shuffled_queries = LINKEDIN_QUERIES.copy()
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
                    
                    if "linkedin.com" not in post_url_lower:
                        continue
                        
                    # Extract title/name markers cleanly from the result body
                    title = str(result.get('title', 'LinkedIn Builder'))
                    name = title.split('|')[0].split('-')[0].strip()
                    
                    # Dynamically prioritize pain signals (errors, frustrations) for higher scoring
                    score = 9 if any(kw in query.lower() for kw in ['error', 'stuck', 'issue']) else 7
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    clean_text = str(result.get('body', '')).replace('\n', ' ')[:500]
                    
                    new_leads.append([
                        "Ghost Search", 
                        "LinkedIn", 
                        name, 
                        post_url, # Fallback to post path if specific personal profile link is missing
                        post_url, 
                        query, 
                        clean_text, 
                        date_str, 
                        score
                    ])
                    existing_urls.add(post_url_lower)
            
            # Anti-throttling dynamic delay
            time.sleep(random.uniform(4.0, 6.0)) 
            
        except Exception as e:
            if "ratelimit" in str(e).lower():
                break
            continue

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    
    return 0