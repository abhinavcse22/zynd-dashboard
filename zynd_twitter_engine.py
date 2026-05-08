import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import feedparser

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_twitter_scraper():
    """Automated Twitter Lead Harvester with Multi-Bridge Failover"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    except:
        return 0

    records = sheet.get_all_records()
    seen_urls = {str(row.get('Tweet URL', '')) for row in records}

    # EXPANDED GTM QUERIES (More aggressive)
    queries = [
        '#buildinpublic "AI agent"',
        '"my AI agent" (stuck OR issue OR help)',
        '"CrewAI" OR "LangGraph" (alternative OR better)',
        'building "AI agents" Python'
    ]

    new_leads = []
    # Using more stable RSS instances
    instances = ["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"]
    
    for query in queries:
        encoded_query = requests.utils.quote(query)
        success = False
        
        for instance in instances:
            if success: break
            search_url = f"{instance}/search/rss?q={encoded_query}"
            
            try:
                resp = requests.get(search_url, timeout=10)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries:
                        t_url = entry.link
                        if t_url in seen_urls: continue
                        
                        author = entry.author if 'author' in entry else "Unknown"
                        content = entry.summary if 'summary' in entry else ""
                        date = datetime.now().strftime("%Y-%m-%d")
                        
                        # High-quality scoring logic
                        score = 6
                        if any(x in content.lower() for x in ['stuck', 'help', 'issue', 'broken']): score = 10
                        elif 'building' in content.lower(): score = 8
                        
                        new_leads.append(["Twitter", author, t_url, content[:200].replace('\n', ' '), date, score])
                        seen_urls.add(t_url)
                    success = True
            except:
                continue

    if new_leads:
        # Sort by score so the best ones go in first
        new_leads.sort(key=lambda x: x[5], reverse=True)
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0
