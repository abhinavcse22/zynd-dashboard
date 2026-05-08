import requests
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def run_twitter_scraper():
    """Automated Twitter Lead Harvester via Google Search Dorking"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
    except:
        return 0

    # Get existing leads to prevent duplicates
    records = sheet.get_all_records()
    seen_urls = {str(row.get('Tweet URL', '')) for row in records}

    # GTM Search Dorks
    queries = [
        'site:x.com "building an AI agent"',
        'site:x.com "CrewAI" "issue"',
        'site:x.com "LangGraph" "help"'
    ]

    new_leads = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    for query in queries:
        # We search Google for recent indexed tweets
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbs=qdr:d"
        
        try:
            response = requests.get(search_url, headers=headers, timeout=15)
            if response.status_code == 200:
                html = response.text
                # Extract Twitter URLs using Regex
                urls = re.findall(r'https://x\.com/[^/]+/status/[0-9]+', html)
                
                for tweet_url in urls:
                    if tweet_url in seen_urls: continue
                    
                    # Clean the URL
                    clean_url = tweet_url.split('?')[0]
                    # Since we are scraping HTML, we don't have the full text, 
                    # so we label it as a "High-Intent Discovery"
                    author = clean_url.split('/')[3]
                    date = datetime.now().strftime("%Y-%m-%d")
                    
                    new_leads.append(["Twitter", author, clean_url, f"New lead found via {query}", date, 8])
                    seen_urls.add(clean_url)
        except Exception as e:
            continue

    if new_leads:
        sheet.append_rows(new_leads)
        return len(new_leads)
    return 0
